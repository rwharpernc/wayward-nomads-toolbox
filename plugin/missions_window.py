"""The Missions window: every active mission in a table with its progress, reward and time left, the same missions grouped by where to hand them in, and the
detail of the one you select. Replaces the old "All" popup of the Missions panel (and its separate detail popup).

You can pin missions here: a pinned mission is listed first on the Missions overlay card, under PINNED, whatever else is on the board (`mission_pins.py`).
The window reads the Missions mode's data and the journal's jump events; it opens nothing online. **Sources** opens the Source commodities window (the one
part that asks Spansh, and only when you press its button)."""
from __future__ import annotations

import tkinter as tk
from datetime import datetime, timezone
from typing import Callable, Dict, List, Optional

from . import mission_pins, missions_board, panelkit
from .missions_overlay import BLUE, GREEN, LIME, RED, time_left
from .uikit import palette as P
from .uikit.shell import WindowShell
from .uikit.table import Column, DataTable
from .uikit.widgets import Tabs

try:
    from config import config
except ImportError:  # unit tests outside EDMC
    config = None

_CFG_GEOMETRY = "wntb_missions_window_geometry"
_TICK_MS = 30_000
_ACTIVE_COLUMNS = (
    Column("pin", "", 34, anchor="center"),
    Column("title", "Mission", 230, stretch=True, max_chars=44),
    Column("kind", "Kind", 130, max_chars=24),
    Column("faction", "Faction", 150, max_chars=26),
    Column("where", "Go to", 230, max_chars=44),
    Column("progress", "Progress", 190, anchor="e", max_chars=30),
    Column("reward", "Reward", 80, anchor="e"),
    Column("left", "Left", 70, anchor="e"),
)
_PLACE_COLUMNS = (
    Column("title", "Mission", 280, stretch=True, max_chars=48),
    Column("station", "Station", 220, max_chars=40),
    Column("progress", "Progress", 190, anchor="e", max_chars=30),
    Column("reward", "Reward", 80, anchor="e"),
    Column("left", "Left", 70, anchor="e"),
)
_PIN = "★"
_BAR = 6


def _bar(row: missions_board.Row) -> str:
    """'████░░ 36/60 held': a small bar then the count, so progress reads at a glance and by shape as well as colour."""
    if row.fraction is None:
        return row.progress
    filled = round(row.fraction * _BAR)
    return "█" * filled + "░" * (_BAR - filled) + " " + row.progress


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _tag(row: missions_board.Row, now: datetime) -> Optional[str]:
    if row.ready:
        return "ready"
    if row.expiry is not None:
        left = (row.expiry - now).total_seconds()
        if left < missions_board.SOON_MINUTES * 60:
            return "soon"
        if left < 6 * 3600:
            return "warn"
    return row.tier if row.tier in ("high", "low") else None


class MissionsWindow:
    def __init__(self, parent: tk.Misc, rows: Callable[[], List[missions_board.Row]], cmdr: Callable[[], Optional[str]],
                 here: Callable[[], str], next_system: Callable[[], str], on_pins_changed: Callable[[], None] = lambda: None,
                 open_sources: Callable[[], None] = lambda: None) -> None:
        self._rows, self._cmdr, self._here, self._next = rows, cmdr, here, next_system
        self._on_pins_changed, self._open_sources = on_pins_changed, open_sources
        self._by_id: Dict[int, missions_board.Row] = {}
        self._selected: Optional[int] = None
        self._signatures: Dict[str, list] = {}
        self._shell = WindowShell(
            parent, "WNTB - Missions", "", size=(1180, 720), min_size=(820, 480),
            load_geometry=lambda: (config.get_str(_CFG_GEOMETRY) if config else "") or "",
            save_geometry=lambda value: config.set(_CFG_GEOMETRY, value) if config else None)
        self._shell.window.protocol("WM_DELETE_WINDOW", self.close)
        self._shell.add_action("Pin / Unpin", self.toggle_pin, accent=True)
        self._shell.add_action("Pin all here", self.pin_here)
        self._shell.add_action("Unpin all", self.unpin_all)
        self._shell.add_action("Copy system", self.copy_system)
        self._shell.add_action("Sources", self._open_sources)

        self._detail = tk.Frame(self._shell.window, bg=P.BG, padx=P.PAD * 2, pady=P.PAD_SM)
        self._detail.pack(side="bottom", fill="x")
        self._detail_labels: List[tk.Label] = []
        self._tabs = Tabs(self._shell.body)
        self._tabs.pack(fill="both", expand=True, pady=(0, P.PAD_SM))
        active_tab, place_tab = self._tabs.add("Active"), self._tabs.add("By place")
        self._active = DataTable(active_tab, _ACTIVE_COLUMNS, on_select=self._pick, sortable=False,
                                 empty_text="No active missions. They appear here once you have accepted some.")
        self._places = DataTable(place_tab, _PLACE_COLUMNS, on_select=self._pick, sortable=False, select_groups=False,
                                 empty_text="No active missions.")
        for table in (self._active, self._places):
            table.pack(fill="both", expand=True)
            table.tag_configure("ready", foreground=GREEN)
            table.tag_configure("soon", foreground=RED)
            table.tag_configure("warn", foreground=P.WARN)
            table.tag_configure("high", foreground=LIME)
            table.tag_configure("low", foreground=BLUE)
            table.tag_configure("here", foreground=P.INFO)
        self.refresh()
        self._tick()

    # --- window ------------------------------------------------------------------------------------------------------------

    @property
    def alive(self) -> bool:
        return self._shell.alive

    def lift(self) -> None:
        self._shell.window.lift()
        self._shell.window.focus_force()

    def close(self) -> None:
        self._shell.close()

    def _tick(self) -> None:
        """Times left move on their own."""
        if not self.alive:
            return
        self.refresh()
        self._shell.window.after(_TICK_MS, self._tick)

    # --- filling -----------------------------------------------------------------------------------------------------------

    def refresh(self) -> None:
        """Redraw from the current missions. A table whose rows have not changed is left alone, so a selection and scroll position stay put."""
        if not self.alive:
            return
        now = _now()
        rows = self._rows()
        self._by_id = {row.id: row for row in rows}
        self._shell.set_subtitle(missions_board.totals(rows, now).text())
        self._fill_active(rows, now)
        self._fill_places(rows, now)
        if self._selected not in self._by_id:
            self._selected = None
        self._show_detail(now)

    def _fill_active(self, rows: List[missions_board.Row], now: datetime) -> None:
        cells = [[_PIN if r.pinned else "", ("✓ " if r.ready else "") + r.title, r.kind, r.faction, r.where(), _bar(r),
                  missions_board.money(r.reward) if r.reward else "-", time_left(r.expiry, now)] for r in rows]
        signature = [(r.id, _tag(r, now), tuple(c)) for r, c in zip(rows, cells)]
        if self._signatures.get("active") != signature:
            self._signatures["active"] = signature
            self._active.clear()
            for row, cell in zip(rows, cells):
                self._active.insert(f"m{row.id}", cell, _tag(row, now))
            self._reselect(self._active)

    def _fill_places(self, rows: List[missions_board.Row], now: datetime) -> None:
        places = missions_board.by_place(rows, self._here(), self._next())
        signature = [(p.system, p.here, p.next_jump, [(r.id, _tag(r, now), r.pinned, r.progress, time_left(r.expiry, now)) for r in p.rows]) for p in places]
        if self._signatures.get("places") == signature:
            return
        self._signatures["places"] = signature
        self._places.clear()
        for index, place in enumerate(places):
            note = " (you are here)" if place.here else " (next jump)" if place.next_jump else ""
            ready = sum(r.ready for r in place.rows)
            title = f"{place.system}{note} - {len(place.rows)} mission{'s' if len(place.rows) != 1 else ''}" + (f", {ready} ready" if ready else "")
            group = f"p{index}"
            self._places.insert(group, [title, "", "", "", ""], "here" if place.here or place.next_jump else None, group=True)
            for row in place.rows:
                self._places.insert(f"m{row.id}", [(_PIN + " " if row.pinned else "") + ("✓ " if row.ready else "") + row.title, row.station or "-", _bar(row),
                                                   missions_board.money(row.reward) if row.reward else "-", time_left(row.expiry, now)],
                                    _tag(row, now), parent=group)
        self._reselect(self._places)

    def _reselect(self, table: DataTable) -> None:
        if self._selected is not None and table.exists(f"m{self._selected}"):
            table.select(f"m{self._selected}")

    # --- selection and detail ----------------------------------------------------------------------------------------------

    def _pick(self, iid: str) -> None:
        if iid.startswith("m"):
            self._selected = int(iid[1:])
            self._show_detail(_now())

    def _show_detail(self, now: datetime) -> None:
        for label in self._detail_labels:
            label.destroy()
        self._detail_labels = []
        row = self._by_id.get(self._selected) if self._selected is not None else None
        if row is None:
            lines = [("", "Select a mission to see its detail. Pin it to keep it at the top of the overlay card.")]
        else:
            lines = missions_board.detail(row, now)
        # two columns of "label  value" so the strip stays short
        half = (len(lines) + 1) // 2
        for column, chunk in enumerate((lines[:half], lines[half:])):
            for index, (name, value) in enumerate(chunk):
                text = f"{name}: {value}" if name else value
                label = tk.Label(self._detail, text=text, fg=P.TEXT if name else P.MUTED, bg=P.BG, anchor="w", justify="left", wraplength=560)
                label.grid(row=index, column=column, sticky="w", padx=(0, P.PAD * 2))
                self._detail_labels.append(label)

    def select(self, mission_id: int) -> None:
        """Show a mission (the panel opens the window on the one you clicked)."""
        self._selected = mission_id
        self.refresh()
        for table in (self._active, self._places):
            self._reselect(table)

    # --- actions -----------------------------------------------------------------------------------------------------------

    def _selected_row(self) -> Optional[missions_board.Row]:
        return self._by_id.get(self._selected) if self._selected is not None else None

    def toggle_pin(self) -> None:
        row, cmdr = self._selected_row(), self._cmdr()
        if row is None:
            self._shell.set_status("Select a mission first.")
            return
        if not cmdr:
            self._shell.set_status("WNTB does not know the commander yet: log in to the game.")
            return
        pinned = mission_pins.book.toggle(cmdr, row.id)
        self._shell.set_status(f"{'Pinned' if pinned else 'Unpinned'}: {row.title}")
        self._changed()

    def pin_here(self) -> None:
        here, cmdr = self._here(), self._cmdr()
        ids = [r.id for r in self._by_id.values() if here and r.system.casefold() == here.casefold()]
        if not cmdr or not ids:
            self._shell.set_status("No missions for this system." if cmdr else "WNTB does not know the commander yet: log in to the game.")
            return
        mission_pins.book.pin_many(cmdr, ids)
        self._shell.set_status(f"Pinned {len(ids)} mission{'s' if len(ids) != 1 else ''} for {here}.")
        self._changed()

    def unpin_all(self) -> None:
        mission_pins.book.clear(self._cmdr())
        self._shell.set_status("Unpinned all.")
        self._changed()

    def copy_system(self) -> None:
        row = self._selected_row()
        if row is None or not row.system:
            self._shell.set_status("Select a mission with a destination first.")
        elif panelkit.copy_to_clipboard(self._shell.window, row.system):
            self._shell.set_status(f"Copied {row.system}.")

    def _changed(self) -> None:
        self._on_pins_changed()
        self.refresh()
