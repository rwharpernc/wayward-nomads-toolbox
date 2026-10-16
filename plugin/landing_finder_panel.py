"""Nearest place to land: the Exploration panel's row for it (what it does and the button that opens the window).

The lookup is `landing_finder.py` and the window `landing_finder_window.py`. This module is the journal hook and the controller: it remembers the position (`StarPos`) and the ship (`Loadout`)
the commander last had, reads them back from the newest journals when EDMC starts in the middle of a session, and opens the window. It does nothing online by itself: the search runs only when
Find is pressed in the window and its box is ticked.
"""
from __future__ import annotations

import logging
import os
import tkinter as tk
from typing import Any, Dict, Optional, Tuple

from config import appname

from . import landing_finder, landing_finder_window, panelkit, restore

plugin_name = os.path.basename(os.path.dirname(__file__))
logger = logging.getLogger(f"{appname}.{plugin_name}")

PANEL_PLACEMENT = "exploration"

_WRAP_PX = 200


class FinderController:
    """Also the `ctx` the window reads the position, system and ship from."""

    def __init__(self) -> None:
        self.tracker = landing_finder.Tracker()
        self._parent: Optional[tk.Misc] = None
        self._summary: Optional[tk.StringVar] = None

    # --- what the window asks ---------------------------------------------------------------------------------------
    def position(self) -> Optional[Tuple[float, float, float]]:
        return self.tracker.position

    def system(self) -> str:
        return self.tracker.system

    def ship(self) -> str:
        return self.tracker.ship

    # --- journal ----------------------------------------------------------------------------------------------------
    def handle_event(self, entry: Dict[str, Any], cmdr: str, system: Optional[str], station: Optional[str], state: Dict[str, Any]) -> None:
        if entry.get("event") == restore.RESTORE_EVENT:
            self._restore()
            return
        if entry.get("event") in (*landing_finder.Tracker.POSITION_EVENTS, "Loadout") and self.tracker.apply(entry):
            self._changed()

    def _restore(self) -> None:
        """EDMC started in the middle of a session: take the position and ship from the newest journals."""
        if self.tracker.position is None or not self.tracker.ship:
            found = landing_finder.read_from_journals()
            if self.tracker.position is None:
                self.tracker.position, self.tracker.system = found.position, found.system
            if not self.tracker.ship:
                self.tracker.ship = found.ship
            self._changed()

    def _changed(self) -> None:
        try:
            if self._summary is not None:
                self._summary.set(summary_text(self.tracker))
        except tk.TclError:
            pass   # the panel is gone
        landing_finder_window.refresh()

    # --- the panel --------------------------------------------------------------------------------------------------
    def build_panel(self, parent: tk.Frame) -> None:
        self._parent = parent
        self._summary = tk.StringVar(value=summary_text(self.tracker))
        body = panelkit.collapsible_section(parent, "Nearest place to land", "wntb_landing_finder_collapsed")
        panelkit.wrap_label(body, min_wrap=_WRAP_PX, textvariable=self._summary, anchor="w").grid(row=1, column=0, columnspan=3, sticky=tk.W, pady=(2, 0))
        button = tk.Button(body, text="FIND", command=self._open)
        button.grid(row=2, column=0, sticky=tk.W, pady=(4, 0))
        panelkit.add_tooltip(button, "Find the nearest station that can take your ship (repair, refuel, rearm), and fleet carriers open to all. Online, only when you press Find in the window.")

    def _open(self) -> None:
        if self._parent is not None:
            landing_finder_window.show(self._parent, self)

    def stop(self) -> None:
        landing_finder_window.close()


def summary_text(tracker: landing_finder.Tracker) -> str:
    """The line under the section's title: where you are and what pad you need, or that neither is known yet."""
    if tracker.position is None:
        return "Needs your position: it comes from your next jump, or from the journal when you log in."
    pad = landing_finder.ship_pad(tracker.ship)
    return f"From {tracker.system or 'your position'}" + (f"; your ship needs a {pad} pad." if pad else ".")


controller = FinderController()


def handle_event(entry: Dict[str, Any], cmdr: str, system: Optional[str], station: Optional[str], state: Dict[str, Any]) -> None:
    controller.handle_event(entry, cmdr, system, station, state)


def build_panel(parent: tk.Frame) -> None:
    controller.build_panel(parent)


def start(plugin_dir: str) -> None:
    pass


def stop() -> None:
    controller.stop()
