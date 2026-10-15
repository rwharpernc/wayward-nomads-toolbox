"""Credits Ledger window: what the commander earned, by activity, kept apart from every mode's panel.

Opened by clicking the "Credits this session" line under the mode buttons. Built on the shared window kit (plugin/uikit), with the
same `show(parent, ...)` entry point and geometry persistence as the other report windows. Tabs:

- **Income**: credits earned per activity for today, the last 7 days, the last 30 days and everything counted.
- **By day**: one row per day, a column per activity and the day's total.
- **Lifetime**: the game's own career totals (its `Statistics` event), which the game writes at login only.

Each activity is its own column, never merged with another: Trade is market trading only, Exploration is exploration data sold,
Exobiology is organic data sold. The data and the rules are in income_ledger.py; this module only lays them out.
"""
from __future__ import annotations

import logging
import os
import tkinter as tk
from typing import Any, Optional

from config import appname, config

from . import income_ledger as ledger, lifetime_stats
from .uikit import palette as P
from .uikit.shell import WindowShell
from .uikit.table import Column, DataTable
from .uikit.widgets import NoteLabel, ScrollFrame, Tabs, section_header

plugin_name = os.path.basename(os.path.dirname(__file__))
logger = logging.getLogger(f"{appname}.{plugin_name}")

CONFIG_GEOMETRY = "wntb_ledger_window_geometry"
MIN_WIDTH = 900
MIN_HEIGHT = 420
DEFAULT_SIZE = (960, 560)

LEGEND = (
    "Income only, by activity. Trade is the profit on market sales (sale minus what the tonnes cost); Exploration and Exobiology are "
    "the data you sold; Mission rewards are credits only; Bounties and bonds are vouchers cashed in. Mining has no income line here "
    "because the journal does not say which commodity sold was mined: the game's own Mining profits are on the Lifetime tab. "
    "Days are UTC, as the journal writes them. Anything earned before WNTB first read your journals is counted by Rebuild."
)

_INCOME_COLUMNS = (Column("activity", "Activity", 200, stretch=True),
                   Column("today", "Today (UTC)", 110, anchor="e"), Column("week", "Last 7 days", 110, anchor="e"),
                   Column("month", "Last 30 days", 110, anchor="e"), Column("all", "All counted", 130, anchor="e"))
_DAY_COLUMNS = (Column("day", "Day (UTC)", 110), *(Column(a, ledger.LABELS[a], 120, anchor="e") for a in ledger.ACTIVITIES),
                Column("total", "Day total", 120, anchor="e"))
_LIFE_COLUMNS = (Column("what", "Figure", 260, stretch=True), Column("value", "Value", 200, anchor="e"))

_window: Optional["LedgerWindow"] = None


def show(parent: tk.Misc, controller: Any) -> None:
    """Open the window, or refresh and raise it if it is open."""
    global _window
    if _window is not None and _window.alive:
        _window.refresh(controller)
        _window.lift()
        return
    _window = LedgerWindow(parent, controller)


def refresh_if_open(controller: Any) -> None:
    if _window is not None and _window.alive:
        _window.refresh(controller)


def close() -> None:
    if _window is not None and _window.alive:
        _window.close()


def _cr(value: int) -> str:
    return f"{value:,}" if value else "0"


def income_rows(record: ledger.Record, today: Optional[Any] = None) -> list:
    """The Income tab: a row per activity and a total row, one column per period."""
    periods = [ledger.totals(record, since) for _label, since in ledger.period_starts(today)]
    rows = [(ledger.LABELS[a], *(_cr(p[a]) for p in periods)) for a in ledger.ACTIVITIES]
    rows.append(("Total", *(_cr(sum(p.values())) for p in periods)))
    return rows


class LedgerWindow:
    def __init__(self, parent: tk.Misc, controller: Any) -> None:
        self._controller = controller
        self._shell = WindowShell(
            parent, "Credits Ledger", "", size=DEFAULT_SIZE, min_size=(MIN_WIDTH, MIN_HEIGHT),
            load_geometry=lambda: config.get_str(CONFIG_GEOMETRY) or "",
            save_geometry=lambda geometry: config.set(CONFIG_GEOMETRY, geometry))
        self._shell.window.protocol("WM_DELETE_WINDOW", self.close)
        self._rebuild = self._shell.add_action("Rebuild from journals", self._on_rebuild)
        self._shell.set_status(LEGEND)
        self._tabs = Tabs(self._shell.body)
        self._tabs.pack(fill="both", expand=True)
        income = self._tabs.add("Income")
        self._income = DataTable(income, _INCOME_COLUMNS, sortable=False, visible_rows=len(ledger.ACTIVITIES) + 1,
                                 empty_text="Nothing counted yet.")
        self._income.pack(fill="x", padx=P.PAD, pady=P.PAD)
        self._income_note = NoteLabel(income, text="")
        self._income_note.pack(fill="x", padx=P.PAD)
        self._days = DataTable(self._tabs.add("By day"), _DAY_COLUMNS, sortable=False,
                               empty_text="No income has been counted yet.")
        self._days.pack(fill="both", expand=True, padx=P.PAD, pady=P.PAD)
        life = ScrollFrame(self._tabs.add("Lifetime"))
        life.pack(fill="both", expand=True)
        self._life_body = life.body
        self.refresh(controller)

    @property
    def alive(self) -> bool:
        return self._shell.alive

    def _on_rebuild(self) -> None:
        self._controller.rebuild()      # sets its status and refreshes this window straight away

    def lift(self) -> None:
        self._shell.window.deiconify()
        self._shell.window.lift()

    def refresh(self, controller: Any) -> None:
        if not self.alive:
            return
        self._controller = controller
        record = controller.record()
        cmdr = controller.cmdr
        busy = controller.rebuilding()
        self._shell.set_subtitle((cmdr or "No commander yet") + (f"  -  {controller.status}" if controller.status else ""))
        self._rebuild.set_enabled(not busy)
        self._income.set_rows(income_rows(record))
        first = ledger.first_day(record)
        note = (f"Counted since {first}." if first else "No income has been counted yet.")
        if controller.status:
            note += " " + controller.status
        self._income_note.configure(text=note)
        self._days.set_rows(ledger.day_rows(record))
        self._draw_lifetime(controller.lifetime())

    def _draw_lifetime(self, life: Optional[lifetime_stats.Lifetime]) -> None:
        for child in self._life_body.winfo_children():
            child.destroy()
        if life is None:
            NoteLabel(self._life_body, text="The game writes its lifetime statistics when you log in; none has been read for this "
                                            "commander yet.").pack(fill="x", padx=P.PAD, pady=P.PAD)
            return
        for title, rows in lifetime_stats.groups(life):
            section_header(self._life_body, title).pack(fill="x")
            table = DataTable(self._life_body, _LIFE_COLUMNS, sortable=False, visible_rows=len(rows))
            table.pack(fill="x", padx=P.PAD, pady=(0, P.PAD))
            table.set_rows(rows)
        NoteLabel(self._life_body, text=lifetime_stats.taken_note(life)).pack(fill="x", padx=P.PAD, pady=(0, P.PAD))

    def close(self) -> None:
        self._shell.close()
