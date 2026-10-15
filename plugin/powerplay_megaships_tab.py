"""The Megaships tab of the Powerplay Sessions window: the megaships whose datalink the commander scanned, cycle by cycle.

Each row is one megaship in one system, scanned in one Powerplay cycle, with when it was scanned and the merits that scan earned (blank when the journal
showed none, for example when the commander was not pledged). The live cycle comes first. The names come from the journal's `SupercruiseDestinationDrop`
just before the scan (see megaship_scans.py), so a scan made without dropping out of supercruise at the megaship first has no name and is not listed.
The rows and the summary are built by plain functions so they can be tested without a window."""
from __future__ import annotations

import tkinter as tk
from typing import List, Optional, Sequence, Tuple

from .megaship_scans import MegaShipScan
from .powerplay_ledger import CycleView, parse_ts
from .powerplay_systems_tab import SystemsPane
from .uikit import palette as P
from .uikit import style
from .uikit.table import Column, DataTable
from .uikit.widgets import NoteLabel

_COLUMNS = (
    Column("cycle", "Cycle", 110),
    Column("name", "Megaship", 330, stretch=True, max_chars=64),
    Column("system", "System", 220, max_chars=44),
    Column("at", "Scanned (UTC)", 150),
    Column("merits", "Merits", 80, anchor="e"),
)
_FORMAT = "%Y-%m-%d %H:%M"


def cycle_name(view: CycleView) -> str:
    return f"Cycle {view.number}" if view.number is not None else "Cycle ?"


def rows(views: Sequence[CycleView]) -> List[Tuple[str, str, str, str, str]]:
    """One row per scan, the live cycle first and, inside a cycle, the latest scan first."""
    out: List[Tuple[str, str, str, str, str]] = []
    for view in views:
        label = cycle_name(view) + (" (live)" if view.current else "")
        for scan in sorted(view.megaships, key=lambda s: s.at, reverse=True):
            when = parse_ts(scan.at)
            out.append((label, scan.name, scan.system, when.strftime(_FORMAT) if when else scan.at, f"{scan.merits:,}" if scan.merits else ""))
    return out


def summary(views: Sequence[CycleView]) -> str:
    """'Cycle 101: 12 megaships, 5,400 merits. Earlier cycles: 30 megaships.'"""
    if not views:
        return ""
    live = next((v for v in views if v.current), views[0])
    text = f"{cycle_name(live)}: {_ships(len(live.megaships))}"
    if live.megaship_merits():
        text += f", {live.megaship_merits():,} merits"
    earlier = sum(len(v.megaships) for v in views if v is not live)
    return text + "." + (f" Earlier cycles: {_ships(earlier)}." if earlier else "")


def _ships(count: int) -> str:
    return f"{count} megaship{'s' if count != 1 else ''}"


class MegaShipsTab:
    def __init__(self, parent: tk.Frame) -> None:
        self._heading = tk.Label(parent, bg=P.PANE, fg=P.MUTED, anchor="w", justify="left", padx=P.PAD, wraplength=900, font=style.font(P.FONT_SMALL),
                                 text="Megaships whose datalink you scanned, one per megaship per system each Powerplay cycle. The name comes from the megaship "
                                      "you dropped out of supercruise at just before the scan; merits are those the scan earned.")
        self._heading.pack(fill="x", pady=(P.PAD_SM, 0))
        self._summary = tk.Label(parent, bg=P.PANE, fg=P.TEXT, anchor="w", justify="left", padx=P.PAD, pady=P.PAD_SM, font=style.font(P.FONT_BOLD))
        self._summary.pack(side="bottom", fill="x")
        self._status = NoteLabel(parent)
        self._status.pack(side="bottom", fill="x", pady=(0, P.PAD_SM))
        self._table = DataTable(parent, _COLUMNS, sortable=False, empty_text="No megaship scans recorded yet for this commander.")
        self._table.pack(fill="both", expand=True, padx=P.PAD, pady=(P.PAD_SM, P.PAD_SM))

    def update(self, pane: Optional[SystemsPane]) -> None:
        if pane is None:
            return
        views = pane.views()
        self._status.configure(text=pane.status())
        self._table.clear()
        for index, row in enumerate(rows(views)):
            self._table.insert(str(index), row)
        self._summary.configure(text=summary(views))
