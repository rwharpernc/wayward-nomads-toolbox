"""
The Credits Ledger feature: what the commander earned from each activity, kept apart from every mode's panel.

A mode's panel shows the present (this session, this cycle, the project in progress) and nothing historical. The past lives in
report windows, and this is the one for money: the Credits Ledger window (ledger_window.py), opened by clicking the "Credits this
session" line under the mode buttons. It adds up income by activity and by day (income_ledger.py) and shows the game's own
lifetime totals (lifetime_stats.py). Trade, Exploration, Exobiology, Missions and Bounties stay separate columns; they are only
added together for a total.

This module is the one entry point for `load.py` / `ui.py`: it folds live journal events into the commander's book, rebuilds the
past from every journal once per commander on a worker thread (so a commander with years of journals does not stall EDMC), and
reads each commander's newest `Statistics` event so the Lifetime tab has figures straight after EDMC starts.
"""
from __future__ import annotations

import logging
import os
import queue
import threading
import tkinter as tk
from typing import Any, Dict, List, Optional, Tuple

from . import commander_data, income_catchup, income_ledger, journal_files, lifetime_stats

try:
    from config import appname
except ImportError:  # unit tests outside EDMC
    appname = "EDMarketConnector"

plugin_name = os.path.basename(os.path.dirname(__file__))
logger = logging.getLogger(f"{appname}.{plugin_name}")

_POLL_MS = 700


class CreditsLedger:
    def __init__(self) -> None:
        self.book = income_ledger.IncomeBook()
        self.cmdr = ""
        self._lifetime: Dict[str, lifetime_stats.Lifetime] = {}
        self._widget: Optional[tk.Misc] = None
        self._pending: set = set()                                   # commander keys whose rebuild is running
        self._rebuilt: "queue.Queue[Tuple[str, str, List[Dict[str, Any]]]]" = queue.Queue()
        self._live: List[Tuple[str, Dict[str, Any]]] = []            # live events seen while a rebuild was running
        self._lifetimes: "queue.Queue[Dict[str, lifetime_stats.Lifetime]]" = queue.Queue()
        self._polling = False

    # --- lifecycle -------------------------------------------------------------------------------

    def start(self, plugin_dir: str) -> None:
        self.book.load(plugin_dir)

    def stop(self) -> None:
        self._widget = None

    def attach(self, widget: tk.Misc) -> None:
        """The widget the window opens from; its event loop also runs the worker-result polling."""
        self._widget = widget
        widget.bind("<Button-1>", lambda _e: self.show(), add="+")
        self._schedule()

    # --- journal ---------------------------------------------------------------------------------

    def handle_event(self, entry: Dict[str, Any], cmdr: str) -> None:
        event = entry.get("event")
        if cmdr and cmdr != self.cmdr:
            self.cmdr = cmdr
        if not self.cmdr:
            return
        if event in ("LoadGame", "StartUp"):
            self._begin(self.cmdr)
        elif event == "Statistics":
            life = lifetime_stats.parse(entry)
            if life is not None:
                self._lifetime[commander_data.key_for(self.cmdr)] = life
                self._changed()
        if event in income_ledger.EVENTS:
            if commander_data.key_for(self.cmdr) in self._pending:
                self._live.append((self.cmdr, entry))     # the rebuild in progress may not have read this one
            if self.book.apply(self.cmdr, entry):
                self.book.commit()

    def _begin(self, cmdr: str) -> None:
        """Start the once-only rebuild of this commander's past, and the read of their newest lifetime statistics."""
        key = commander_data.key_for(cmdr)
        if not key:
            return
        if key not in self._lifetime:
            threading.Thread(target=self._read_lifetime, args=([cmdr],), name="WNTB-ledger-lifetime", daemon=True).start()
        if self.book.backfilled(cmdr) or key in self._pending:
            return
        self._pending.add(key)
        threading.Thread(target=self._read_past, args=(cmdr, key), name="WNTB-ledger-rebuild", daemon=True).start()
        self._schedule()

    def rebuild(self) -> None:
        """Count the past again from every journal (the window's Rebuild button)."""
        key = commander_data.key_for(self.cmdr)
        if not key or key in self._pending:
            return
        self._pending.add(key)
        threading.Thread(target=self._read_past, args=(self.cmdr, key), name="WNTB-ledger-rebuild", daemon=True).start()
        self._schedule()

    def _read_past(self, cmdr: str, key: str) -> None:
        try:
            self._rebuilt.put((cmdr, key, income_catchup.read_all_events(cmdr)))
        except Exception:
            logger.exception("Credits Ledger rebuild failed for %s", cmdr)
            self._rebuilt.put((cmdr, key, []))

    def _read_lifetime(self, cmdrs: List[str]) -> None:
        try:
            self._lifetimes.put(lifetime_stats.latest_in_journals(cmdrs, journal_files.journal_folder()))
        except Exception:
            logger.exception("Could not read the lifetime statistics from the journal")

    # --- worker results (Tk thread) --------------------------------------------------------------

    def _schedule(self) -> None:
        if self._widget is None or self._polling:
            return
        self._polling = True
        self._widget.after(_POLL_MS, self._poll)

    def _poll(self) -> None:
        self._polling = False
        if self._widget is None:
            return
        try:
            while True:
                found = self._lifetimes.get_nowait()
                for key, life in found.items():
                    self._lifetime.setdefault(key, life)    # a Statistics event seen live since is newer than what was read
                self._changed()
        except queue.Empty:
            pass
        try:
            while True:
                cmdr, key, entries = self._rebuilt.get_nowait()
                newer = [e for who, e in self._live if commander_data.key_for(who) == key]
                self._live = [(who, e) for who, e in self._live if commander_data.key_for(who) != key]
                try:
                    self.book.rebuild(cmdr, entries, newer)
                    self.book.commit()
                except Exception:
                    logger.exception("Could not apply the rebuilt Credits Ledger for %s", cmdr)
                self._pending.discard(key)
        except queue.Empty:
            pass
        if self._pending or any(t.name == "WNTB-ledger-lifetime" and t.is_alive() for t in threading.enumerate()):
            self._schedule()

    def _changed(self) -> None:
        from . import ledger_window
        ledger_window.refresh_if_open(self)

    # --- what the window reads -------------------------------------------------------------------

    def record(self) -> income_ledger.Record:
        return self.book.record(self.cmdr)

    def lifetime(self) -> Optional[lifetime_stats.Lifetime]:
        return self._lifetime.get(commander_data.key_for(self.cmdr))

    def rebuilding(self) -> bool:
        return commander_data.key_for(self.cmdr) in self._pending

    def show(self) -> None:
        if self._widget is None:
            return
        from . import ledger_window
        ledger_window.show(self._widget, self)


controller = CreditsLedger()


def start(plugin_dir: str) -> None:
    controller.start(plugin_dir)
    controller.book.add_listener(controller._changed)   # noqa: SLF001 - same package


def stop() -> None:
    controller.stop()


def attach(widget: tk.Misc) -> None:
    controller.attach(widget)


def handle_event(entry: Dict[str, Any], cmdr: str, system: Optional[str], station: Optional[str], state: Dict[str, Any]) -> None:
    controller.handle_event(entry, cmdr)
