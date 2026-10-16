"""Expedition Log: the Exploration panel's row for it (what is running, START and STOP, and the button that opens the archive window).

The model, the totals and the saving are `expedition_log.py`; the window is `expedition_log_window.py`; the overlay card is `expedition_log_overlay.py`. This module is the
journal hook and the controller they share: it hands every journal event to the log (`book.apply`, which counts it for the expedition that is running), remembers the
system and the ship the commander is in (so a new expedition starts with them), and starts and stops expeditions for the row and the window. Nothing leaves the
computer.
"""
from __future__ import annotations

import logging
import os
import tkinter as tk
from typing import Any, Dict, Optional

from config import appname

from . import expedition_log, expedition_log_window, panelkit

plugin_name = os.path.basename(os.path.dirname(__file__))
logger = logging.getLogger(f"{appname}.{plugin_name}")

PANEL_PLACEMENT = "exploration"

_NAME_SHOWN = 50
_WRAP_PX = 200

book = expedition_log.LogBook()


def summary_text(book_: expedition_log.LogBook, now: Optional[float] = None) -> str:
    """The lines under the row's title: what is running and how it is going, or what to do."""
    if not book_.ready:
        return "Log in to use the Expedition Log."
    run = book_.running()
    if run is None:
        count = len(book_.runs())
        return f"No expedition running ({count} in the archive)." if count else "No expedition yet. START one when you set off."
    totals = run.totals
    lines = [f"{expedition_log.clip(run.name, _NAME_SHOWN)}: {expedition_log.duration_text(run.elapsed(now))}",
             f"{len(run.systems):,} systems · {totals.jumps:,} jumps · {totals.light_years:,.0f} ly",
             f"{totals.bodies_scanned:,} bodies · {totals.bio_species:,} species",
             f"Earned {expedition_log.short_credits(totals.earned)} · unsold ~{expedition_log.short_credits(totals.unsold)}"]
    return "\n".join(lines)


class LogController:
    def __init__(self) -> None:
        self._plugin_dir: Optional[str] = None
        self._system = ""
        self._ship = ""
        self._parent: Optional[tk.Misc] = None
        self._summary_var: Optional[tk.StringVar] = None
        self._buttons: Dict[str, tk.Button] = {}
        book.add_listener(self._update)

    # --- lifecycle ------------------------------------------------------------------------------------------------
    def start(self, plugin_dir: str) -> None:
        self._plugin_dir = plugin_dir
        book.load(plugin_dir)

    def stop(self) -> None:
        book.flush()

    # --- the journal ----------------------------------------------------------------------------------------------
    def handle_event(self, entry: Dict[str, Any], cmdr: str, system: Optional[str], station: Optional[str], state: Dict[str, Any]) -> None:
        if cmdr:
            book.set_commander(cmdr)
        event = entry.get("event")
        if system:
            self._system = system
        if event in ("FSDJump", "CarrierJump", "Location") and entry.get("StarSystem"):
            self._system = str(entry["StarSystem"])
        if event == "Loadout":
            self._ship = expedition_log.ship_label(entry) or self._ship
        book.apply(entry)

    # --- what the row and the window do ---------------------------------------------------------------------------
    def system(self) -> str:
        return self._system

    def ship(self) -> str:
        return self._ship

    def commander(self) -> str:
        return book.commander

    def start_expedition(self, name: str = "") -> Optional[expedition_log.Run]:
        """Starts an expedition from here, in the ship the commander is in (stopping the one that is running)."""
        return book.start(name, self._system, self._ship)

    def plan_since_last_sale(self, folder: Optional[str] = None) -> Optional[dict]:
        """What an expedition carried on from the data the commander is holding would be (see `expedition_log.plan_since_last_sale`). Reads files only, so it may run on a worker
        thread; `begin_since_last_sale` then starts it on the main thread."""
        return expedition_log.plan_since_last_sale(book.commander, folder) if book.commander else None

    def begin_since_last_sale(self, plan: dict, name: str = "") -> Optional[expedition_log.Run]:
        """Starts the expedition `plan_since_last_sale` worked out, in the ship the commander is in; it carries on counting live from there."""
        return book.start_at(plan["started"], name or "Expedition since my last sale", self._system, self._ship, plan["rebuilt"])

    def stop_expedition(self) -> Optional[expedition_log.Run]:
        return book.stop()

    def rescan_totals(self, run_id: str, folder: Optional[str] = None) -> Optional[expedition_log.Run]:
        """What a run's totals come to when worked out again from the commander's journals between its start and end. Reads files and changes nothing, so it can run on
        a worker thread; `rescan` applies it (on the main thread, since the window listens to the log)."""
        run = book.get(run_id)
        if run is None or not book.commander:
            return None
        return expedition_log.rescan(run, book.commander, folder)

    def rescan(self, run_id: str, folder: Optional[str] = None) -> Optional[expedition_log.Run]:
        rebuilt = self.rescan_totals(run_id, folder)
        return book.replace_totals(run_id, rebuilt) if rebuilt is not None else None

    # --- the panel ------------------------------------------------------------------------------------------------
    def build_panel(self, parent: tk.Frame) -> None:
        self._parent = parent
        self._summary_var = tk.StringVar()
        body = panelkit.collapsible_section(parent, "Expedition Log", "wntb_expedition_log_collapsed")
        panelkit.wrap_label(body, min_wrap=_WRAP_PX, textvariable=self._summary_var, anchor="w").grid(
            row=1, column=0, columnspan=3, sticky=tk.W, pady=(2, 0))
        for column, (key, text, command, tip) in enumerate((
                ("start", "START", self._on_start, "Start a new expedition here, in this ship (stops the one that is running)"),
                ("stop", "STOP", self._on_stop, "Stop the running expedition"),
                ("log", "LOG", self._open_window, "Open the Expedition Log: the archive of your expeditions, to name, edit, reset and rescan them"))):
            button = tk.Button(body, text=text, command=command)
            button.grid(row=2, column=column, sticky=tk.W, padx=(0 if column == 0 else 6, 0), pady=(4, 0))
            panelkit.add_tooltip(button, tip)
            self._buttons[key] = button
        self._update()

    def _update(self) -> None:
        try:
            if self._summary_var is not None:
                self._summary_var.set(summary_text(book))
            if "stop" in self._buttons:
                self._buttons["stop"].configure(state=tk.NORMAL if book.running() is not None else tk.DISABLED)
                self._buttons["start"].configure(state=tk.NORMAL if book.ready else tk.DISABLED)
        except tk.TclError:
            pass   # the panel is gone

    def _on_start(self) -> None:
        self.start_expedition()

    def _on_stop(self) -> None:
        self.stop_expedition()

    def _open_window(self) -> None:
        if self._parent is not None:
            expedition_log_window.show(self._parent, book, self)


controller = LogController()


def start(plugin_dir: str) -> None:
    controller.start(plugin_dir)


def stop() -> None:
    controller.stop()


def handle_event(entry: Dict[str, Any], cmdr: str, system: Optional[str], station: Optional[str], state: Dict[str, Any]) -> None:
    controller.handle_event(entry, cmdr, system, station, state)


def build_panel(parent: tk.Frame) -> None:
    controller.build_panel(parent)
