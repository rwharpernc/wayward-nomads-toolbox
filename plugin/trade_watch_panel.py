"""Market watch list: the commodities the commander wants prices for, in Trade mode's panel.

A collapsible "Watch list" row shows each watched commodity's best buy and sell price in a few short lines, with a REFRESH button
(asks Spansh for the best prices near the system you are in) and a WATCH button that opens the window (`trade_watch_window.py`) to
add, remove and read every price with where and when it was seen. Prices come from two places (`trade_watch_data.py`): the markets
you open (`Market.json`, read when the game writes the `Market` event; nothing is sent anywhere) and, only when you press REFRESH
with Trade's lookups turned on in Settings, Spansh. The list is kept per commander and never leaves the computer."""
from __future__ import annotations

import logging
import os
import queue
import threading
import tkinter as tk
from typing import Any, Dict, List, Mapping, Optional, Tuple

from config import appname, config

from . import panelkit, trade_market, trade_watch_data, trade_watch_lookup, trade_watch_window

plugin_name = os.path.basename(os.path.dirname(__file__))
logger = logging.getLogger(f"{appname}.{plugin_name}")

PANEL_PLACEMENT = "trade"

_LOCATION_EVENTS = ("FSDJump", "Location", "CarrierJump")
_CFG_LOOKUPS = "wntb_trade_lookups_enabled"      # Trade's own switch for every Spansh lookup (trade_panel.py)
_CFG_RADIUS = "wntb_trade_near_radius_ly"        # how far Trade's Market page looks (trade_panel.py)
_DEFAULT_RADIUS_LY = 100
_LINES_SHOWN = 5       # watched commodities listed in the panel; the window shows them all
_NAME_SHOWN = 16       # characters of a commodity name shown in a panel line
_WRAP_PX = 200         # the summary wraps here: what it shows comes from the game and Spansh, and must not widen EDMC's window
_POLL_MS = 500

book = trade_watch_data.WatchBook()


def lookups_enabled() -> bool:
    return config.get_bool(_CFG_LOOKUPS, default=False)


def _radius() -> int:
    try:
        return max(5, min(5000, int(config.get_int(_CFG_RADIUS, default=_DEFAULT_RADIUS_LY))))
    except (TypeError, ValueError):
        return _DEFAULT_RADIUS_LY


def _journal_dir() -> str:
    getter = getattr(config, "get_str", None) or config.get   # type: ignore[attr-defined]
    return getter("journaldir") or getattr(config, "default_journal_dir", "") or ""


def price_text(quote: Optional[trade_watch_data.Quote]) -> str:
    return f"{quote.price:,}" if quote is not None else "-"


def line_for(book_: trade_watch_data.WatchBook, commodity: str) -> str:
    """`Gold: buy 9,100 / sell 11,200` for the panel; `-` for a side nobody has a price for."""
    name = trade_watch_data.clip(commodity, _NAME_SHOWN)
    return f"{name}: buy {price_text(book_.best_buy(commodity))} / sell {price_text(book_.best_sell(commodity))}"


class WatchController:
    def __init__(self) -> None:
        self._system = ""
        self._summary_var: Optional[tk.StringVar] = None
        self._status_var: Optional[tk.StringVar] = None
        self._section: Optional[tk.Frame] = None
        self._parent: Optional[tk.Frame] = None
        self._refresh_button: Optional[tk.Button] = None
        self._results: "queue.Queue[Tuple[Dict[str, trade_watch_data.Lookup], List[str], str]]" = queue.Queue()
        self._cancel: Optional[threading.Event] = None
        self._running = False
        self.status = ""   # the last thing said about a refresh, for the window
        book.add_listener(self._update_summary)

    # --- what the game tells us -----------------------------------------------------------------------------------------

    def start(self, plugin_dir: str) -> None:
        book.load(plugin_dir)

    def stop(self) -> None:
        if self._cancel is not None:
            self._cancel.set()
        trade_watch_window.close()

    def handle_event(self, entry: Mapping[str, Any], cmdr: str, system: Optional[str], station: Optional[str],
                     state: Dict[str, Any]) -> None:
        if entry.get("event") in _LOCATION_EVENTS:
            place = str(entry.get("StarSystem") or "").strip()
        else:
            place = ""
        place = place or (system or self._system or "").strip()
        moved = place != self._system
        self._system = place
        changed = book.set_commander(cmdr)   # a new commander tells the book's listeners (this row, an open window) itself
        if entry.get("event") == "Market" and book.count():
            market = trade_market.read_market_file(_journal_dir())
            where = str(entry.get("StationName") or station or "")
            book.record_market(where, str(entry.get("StarSystem") or self._system), market)   # tells the listeners itself
        elif moved and not changed:
            trade_watch_window.refresh()

    def system(self) -> str:
        return self._system

    # --- the panel row ---------------------------------------------------------------------------------------------------

    def summary(self) -> Tuple[str, str]:
        """(the lines under the title, the note after the title when folded)."""
        if not book.ready:
            return "Log in to use the watch list.", ""
        watched = book.watched()
        if not watched:
            return "Nothing watched yet. Press WATCH to add commodities.", ""
        lines = [line_for(book, name) for name in watched[:_LINES_SHOWN]]
        if len(watched) > _LINES_SHOWN:
            lines.append(f"+{len(watched) - _LINES_SHOWN} more in the window")
        return "\n".join(lines), f"- {len(watched)} watched"

    def _update_summary(self) -> None:
        if self._summary_var is None:
            return
        try:
            text, suffix = self.summary()
            self._summary_var.set(text)
            if self._section is not None:
                self._section.set_title_suffix(suffix)   # type: ignore[attr-defined]
        except tk.TclError:
            pass   # the panel is being torn down

    def build_panel(self, parent: tk.Frame) -> None:
        self._parent = parent
        self._summary_var = tk.StringVar()
        self._status_var = tk.StringVar()

        body = panelkit.collapsible_section(parent, "Watch list", "wntb_trade_watch_collapsed")
        self._section = body
        # A plain label with a hard wrap, not panelkit.wrap_label: that one never wraps narrower than 300 px, and long names would then
        # make this the widest row in the panel (and so widen the whole EDMC window).
        tk.Label(body, textvariable=self._summary_var, anchor="w", justify=tk.LEFT, wraplength=_WRAP_PX).grid(
            row=1, column=0, columnspan=3, sticky=tk.W, pady=(2, 0))
        tk.Label(body, textvariable=self._status_var, anchor="w", justify=tk.LEFT, wraplength=_WRAP_PX).grid(
            row=2, column=0, columnspan=3, sticky=tk.W)
        self._refresh_button = tk.Button(body, text="REFRESH", command=self.refresh)
        self._refresh_button.grid(row=3, column=0, sticky=tk.W, pady=(4, 0))
        panelkit.add_tooltip(self._refresh_button, "Ask Spansh for the best buy and sell price of each watched commodity near this "
                                                   "system (needs Trade lookups turned on in Settings)")
        watch = tk.Button(body, text="WATCH", command=self._open_window)
        watch.grid(row=3, column=1, sticky=tk.W, padx=(4, 0), pady=(4, 0))
        panelkit.add_tooltip(watch, "Open the watch list window: add or remove commodities and read every price")
        self._update_summary()

    def _open_window(self) -> None:
        if self._parent is not None:
            trade_watch_window.show(self._parent, book, self)

    # --- the Spansh refresh ----------------------------------------------------------------------------------------------

    def refresh_blocker(self) -> str:
        """Why a refresh cannot start now, or an empty string when it can."""
        if self._running:
            return "A refresh is already running."
        if not lookups_enabled():
            return "Turn on Trade lookups in Settings (Trade tab) to ask Spansh."
        if not book.ready:
            return "Log in first."
        if not book.watched():
            return "Nothing is watched yet."
        if not self._system:
            return "Your system is not known yet."
        return ""

    def refresh(self) -> None:
        blocker = self.refresh_blocker()
        if blocker:
            self.say(blocker)
            return
        names, reference, radius = book.watched(), self._system, _radius()
        self._cancel = cancel = threading.Event()
        self._running = True
        self.say(f"Asking Spansh about {len(names)} commodit{'y' if len(names) == 1 else 'ies'} near {trade_watch_data.clip(reference, 30)}...")
        trade_watch_window.refresh()

        def work() -> None:
            try:
                found, problems = trade_watch_lookup.refresh(names, reference, radius, cancel=cancel)
            except Exception:
                logger.exception("Watch list refresh failed")
                found, problems = {}, ["Lookup failed - check your connection and try again (see the EDMC log)."]
            self._results.put((found, problems, reference))

        threading.Thread(target=work, name="WNTB-trade-watch", daemon=True).start()
        self._poll()

    def _poll(self) -> None:
        try:
            found, problems, reference = self._results.get_nowait()
        except queue.Empty:
            if self._parent is not None and self._running:
                try:
                    self._parent.after(_POLL_MS, self._poll)
                except tk.TclError:
                    self._running = False
            return
        self._running = False
        if found:
            book.set_lookups(found)
        if problems and not found:
            self.say(f"Spansh could not be reached: {trade_watch_data.clip(problems[0], 120)}")
        elif problems:
            self.say(f"Updated {len(found)}; {len(problems)} failed ({trade_watch_data.clip(problems[0], 80)}).")
        else:
            self.say(f"Updated from Spansh near {trade_watch_data.clip(reference, 30)}.")
        trade_watch_window.refresh()

    def say(self, text: str) -> None:
        self.status = text
        if self._status_var is not None:
            try:
                self._status_var.set(trade_watch_data.clip(text, 160))
            except tk.TclError:
                pass

    @property
    def running(self) -> bool:
        return self._running


controller = WatchController()


def start(plugin_dir: str) -> None:
    controller.start(plugin_dir)


def stop() -> None:
    controller.stop()


def handle_event(entry: Dict[str, Any], cmdr: str, system: Optional[str], station: Optional[str], state: Dict[str, Any]) -> None:
    controller.handle_event(entry, cmdr, system, station, state)


def build_panel(parent: tk.Frame) -> None:
    controller.build_panel(parent)
