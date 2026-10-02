"""Rare Goods Finder window for Powerplay mode: nearest rare commodities to
the current system, with each origin system's live controlling Power.

Built on the shared window kit (plugin/uikit: WindowShell + DataTable - see
docs/WINDOW_FRAMEWORK_SPEC.md); module-level show/refresh/close and saved
geometry as in powerplay_window.py.
"""

from __future__ import annotations

import logging
import os
import tkinter as tk
import webbrowser
from typing import Any, Callable, Dict, List, Optional, Tuple

from config import appname, config

from . import powerplay_control_lookup, rare_goods
from .uikit import palette as P
from .uikit.shell import WindowShell
from .uikit.table import Column, DataTable
from .uikit.widgets import FlatButton

plugin_name = os.path.basename(os.path.dirname(__file__))
logger = logging.getLogger(f"{appname}.{plugin_name}")

CONFIG_GEOMETRY = "wntb_rares_window_geometry"
CONFIG_LIMIT = "wntb_rares_limit"

MIN_WIDTH = 940
MIN_HEIGHT = 420
DEFAULT_SIZE = (960, 560)
DEFAULT_LIMIT = 10

_window: Optional["RareGoodsWindow"] = None

Coords = Tuple[float, float, float]

# Widths sized to the bundled dataset's longest values per column (e.g.
# "Ultra-Compact Processor Prototypes", "Stefanyshyn-Piper Station").
_COLUMNS = (
    Column("rare", "Rare Good", 290, stretch=True),
    Column("system", "Origin System", 150),
    Column("station", "Station", 220),
    Column("pad", "Pad", 60, anchor="center"),
    Column("power", "Controlling Power", 170),
)


def _max_limit() -> int:
    return max(1, rare_goods.dataset_size())


def _saved_limit() -> int:
    raw = config.get_str(CONFIG_LIMIT)
    try:
        value = int(raw) if raw else DEFAULT_LIMIT
    except ValueError:
        value = DEFAULT_LIMIT
    return max(1, min(value, _max_limit()))


def show(parent: tk.Misc, current_system: Optional[str], current_coords: Optional[Coords]) -> None:
    """Open the Rare Goods window, or raise it if already open."""
    global _window

    if _window is not None and _window.alive:
        _window.refresh(current_system, current_coords)
        _window.lift()
        return

    _window = RareGoodsWindow(parent, current_system, current_coords)


def refresh(current_system: Optional[str], current_coords: Optional[Coords]) -> None:
    if _window is not None and _window.alive:
        _window.refresh(current_system, current_coords)


def close() -> None:
    if _window is not None and _window.alive:
        _window.close()


class RareGoodsWindow:
    def __init__(
        self, parent: tk.Misc, current_system: Optional[str], current_coords: Optional[Coords],
    ) -> None:
        self._current_system = current_system
        self._current_coords = current_coords
        self._refresh_seq = 0
        self._id64_to_iids: Dict[int, List[str]] = {}

        self._shell = WindowShell(
            parent, "Rare Goods Finder", "", size=DEFAULT_SIZE, min_size=(MIN_WIDTH, MIN_HEIGHT),
            load_geometry=lambda: config.get_str(CONFIG_GEOMETRY) or "",
            save_geometry=lambda geometry: config.set(CONFIG_GEOMETRY, geometry))
        self._shell.window.protocol("WM_DELETE_WINDOW", self.close)
        self._shell.add_action("Refresh", lambda: self.refresh(self._current_system, self._current_coords))

        controls = tk.Frame(self._shell.body, bg=P.BG)
        controls.pack(fill="x", pady=(0, P.PAD_SM))
        tk.Label(controls, text="Show nearest:", fg=P.MUTED, bg=P.BG).pack(side="left")
        self._limit_var = tk.StringVar(value=str(_saved_limit()))
        limit_entry = tk.Entry(controls, textvariable=self._limit_var, width=4)
        limit_entry.pack(side="left", padx=(6, 6))
        limit_entry.bind("<Return>", lambda _e: self._apply_limit())
        FlatButton(controls, "Apply", self._apply_limit).pack(side="left")

        self._table = DataTable(self._shell.body, _COLUMNS, on_activate=self._open_selected)
        self._table.pack(fill="both", expand=True, pady=(0, P.PAD_SM))
        self._shell.set_status(
            "Double-click a row to open that rare good's page on Inara. Sorted by distance from your current "
            "system (click a heading to re-sort). Controlling Power is looked up live from Spansh — “…” while "
            "loading, “—” if unclaimed or unreachable.")

        self.refresh(current_system, current_coords)

    @property
    def alive(self) -> bool:
        return self._shell.alive

    def lift(self) -> None:
        self._shell.window.deiconify()
        self._shell.window.lift()

    def _limit(self) -> int:
        try:
            value = int(self._limit_var.get())
        except (ValueError, AttributeError):
            return DEFAULT_LIMIT
        return max(1, min(value, _max_limit()))

    def _apply_limit(self) -> None:
        limit = self._limit()
        self._limit_var.set(str(limit))
        config.set(CONFIG_LIMIT, str(limit))
        self.refresh(self._current_system, self._current_coords)

    def refresh(self, current_system: Optional[str], current_coords: Optional[Coords]) -> None:
        if not self.alive:
            return
        self._current_system = current_system
        self._current_coords = current_coords
        self._refresh_seq += 1
        seq = self._refresh_seq
        self._id64_to_iids = {}

        self._table.clear()

        if not current_coords:
            self._shell.set_subtitle("Awaiting system data…")
            self._table.insert("waiting", ("(waiting for a system jump or login to know where you are)", "", "", "", ""))
            return

        self._shell.set_subtitle(f"Current system: {current_system or '(unknown)'}")

        for entry in rare_goods.nearest(current_coords, self._limit()):
            iid = str(entry["inaraId"])
            self._table.insert(iid, self._row_values(entry))
            id64 = entry.get("spanshId64")
            if id64 is not None:
                self._id64_to_iids.setdefault(id64, []).append(iid)

        powerplay_control_lookup.fetch_missing(self._id64_to_iids.keys(), self._lookup_callback(seq))

    def _lookup_callback(self, seq: int) -> Callable[[int, Optional[str]], None]:
        def on_result(id64: int, power: Optional[str]) -> None:
            # Runs on the lookup's worker thread; hop to the Tk thread. The
            # window can be destroyed while lookups are still finishing, so
            # a dead toplevel is simply ignored.
            try:
                self._shell.window.after(0, lambda: self._apply_power_result(seq, id64, power))
            except (tk.TclError, RuntimeError):
                pass
        return on_result

    def _apply_power_result(self, seq: int, id64: int, power: Optional[str]) -> None:
        if seq != self._refresh_seq or not self.alive:
            return
        for iid in self._id64_to_iids.get(id64, ()):
            if self._table.exists(iid):
                self._table.set(iid, "power", power or "—")

    @staticmethod
    def _row_values(entry: Dict[str, Any]) -> tuple:
        id64 = entry.get("spanshId64")
        found, power = powerplay_control_lookup.cached(id64) if id64 is not None else (True, None)
        return (
            entry["rare"],
            entry["system"],
            entry["station"],
            entry["pad"],
            (power or "—") if found else "…",
        )

    def _open_selected(self, iid: str) -> None:
        try:
            inara_id = int(iid)
        except ValueError:
            return
        webbrowser.open(rare_goods.inara_commodity_url(inara_id))

    def close(self) -> None:
        self._shell.close()
