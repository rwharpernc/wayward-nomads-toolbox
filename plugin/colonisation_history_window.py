"""Colonization History window: what the commander has delivered over time, kept off the Colonization panel.

The panel shows the project being built now; the past is here, opened by the panel's HISTORY button. Built on the shared window
kit (plugin/uikit) with the same `show(parent, ...)` entry point and geometry persistence as the other report windows. Tabs:

- **Overview**: sites done and in progress, tonnes delivered, this week and month, best day, busiest site, claims, average build.
- **By day**: tonnes delivered on each day, newest first.
- **Commodities**: every commodity delivered, most first.
- **Sites**: every construction site delivered to, most first.

The figures are worked out in colonisation_stats.py from the commander's delivery ledger (colonisation_history.py); this module
only lays them out.
"""
from __future__ import annotations

import logging
import os
import tkinter as tk
from typing import Any, Callable, Dict, Mapping, Optional, Sequence, Tuple

from config import appname, config

from . import colonisation_stats as stats
from .colonisation import Site
from .uikit import palette as P
from .uikit.shell import WindowShell
from .uikit.table import Column, DataTable
from .uikit.widgets import Tabs

plugin_name = os.path.basename(os.path.dirname(__file__))
logger = logging.getLogger(f"{appname}.{plugin_name}")

CONFIG_GEOMETRY = "wntb_colonisation_history_window_geometry"
MIN_WIDTH = 560
MIN_HEIGHT = 380
DEFAULT_SIZE = (680, 480)

LEGEND = ("Only your own deliveries are counted, from the journal. Deliveries made before WNTB first read your journals are "
          "counted once from the older journals; if you deleted old journals those are missing. Days are UTC.")

_OVERVIEW = (Column("what", "", 160), Column("value", "", 360, stretch=True, max_chars=120))
_DAY = (Column("day", "Day (UTC)", 160), Column("tonnes", "Tonnes", 140, anchor="e"))
_COMMODITY = (Column("name", "Commodity", 260, stretch=True, max_chars=40), Column("tonnes", "Tonnes", 140, anchor="e"))
_SITE = (Column("name", "Construction site", 320, stretch=True, max_chars=60), Column("tonnes", "Tonnes", 140, anchor="e"))

# What the window reads when it draws: (commander, the tracked sites, the commander's delivery record).
Provider = Callable[[], Tuple[str, Sequence[Site], Mapping[str, Any]]]

_window: Optional["HistoryWindow"] = None


def show(parent: tk.Misc, provider: Provider) -> None:
    """Open the window, or refresh and raise it if it is open."""
    global _window
    if _window is not None and _window.alive:
        _window.refresh(provider)
        _window.lift()
        return
    _window = HistoryWindow(parent, provider)


def refresh_if_open(provider: Provider) -> None:
    if _window is not None and _window.alive:
        _window.refresh(provider)


def close() -> None:
    if _window is not None and _window.alive:
        _window.close()


class HistoryWindow:
    def __init__(self, parent: tk.Misc, provider: Provider) -> None:
        self._shell = WindowShell(
            parent, "Colonization History", "", size=DEFAULT_SIZE, min_size=(MIN_WIDTH, MIN_HEIGHT),
            load_geometry=lambda: config.get_str(CONFIG_GEOMETRY) or "",
            save_geometry=lambda geometry: config.set(CONFIG_GEOMETRY, geometry))
        self._shell.window.protocol("WM_DELETE_WINDOW", self.close)
        self._shell.set_status(LEGEND)
        tabs = Tabs(self._shell.body)
        tabs.pack(fill="both", expand=True)
        self._tables: Dict[str, DataTable] = {}
        for key, title, columns, empty in (
                ("overview", "Overview", _OVERVIEW, "Nothing counted yet."), ("days", "By day", _DAY, "No deliveries counted yet."),
                ("commodities", "Commodities", _COMMODITY, "No deliveries counted yet."),
                ("sites", "Sites", _SITE, "No deliveries counted yet.")):
            table = DataTable(tabs.add(title), columns, sortable=False, empty_text=empty)
            table.pack(fill="both", expand=True, padx=P.PAD, pady=P.PAD)
            self._tables[key] = table
        self.refresh(provider)

    @property
    def alive(self) -> bool:
        return self._shell.alive

    def lift(self) -> None:
        self._shell.window.deiconify()
        self._shell.window.lift()

    def refresh(self, provider: Provider) -> None:
        if not self.alive:
            return
        cmdr, sites, record = provider()
        self._shell.set_subtitle(cmdr or "No commander yet")
        self._tables["overview"].set_rows(stats.overview_rows(stats.history_for(sites, record)))
        self._tables["days"].set_rows(stats.day_rows(record))
        self._tables["commodities"].set_rows(stats.commodity_rows(record))
        self._tables["sites"].set_rows(stats.site_rows(sites, record))

    def close(self) -> None:
        self._shell.close()
