"""Ship Builds management window - list every saved build link for one
commander, with Add/Edit/Delete/Open/Copy - same singleton window +
geometry-persistence convention as the other WNTB windows, built on the
shared window kit (plugin/uikit - see docs/WINDOW_FRAMEWORK_SPEC.md)."""

from __future__ import annotations

import logging
import os
import tkinter as tk
import webbrowser
from typing import Optional

from config import appname, config

from . import panelkit
from .ship_builds_data import ShipBuild, ShipBuildRepository
from .ship_builds_dialog import open_ship_build_dialog
from .uikit import palette as P
from .uikit.shell import WindowShell
from .uikit.table import Column, DataTable

plugin_name = os.path.basename(os.path.dirname(__file__))
logger = logging.getLogger(f"{appname}.{plugin_name}")

CONFIG_GEOMETRY = "wntb_ship_builds_window_geometry"

MIN_WIDTH = 700
MIN_HEIGHT = 380
DEFAULT_SIZE = (860, 480)

_COLUMNS = (
    Column("name", "Name", 220, stretch=True, max_chars=50),
    Column("ship", "Ship", 130, max_chars=24),
    Column("role", "Role", 110, max_chars=24),
    Column("site", "Site", 120, max_chars=24),
    Column("updated", "Updated", 100, anchor="e"),
)

_window: Optional["ShipBuildsWindow"] = None


def show(parent: tk.Misc, repository: ShipBuildRepository, cmdr: str, prefill_ship: str) -> None:
    """Open the management window for `cmdr`, or raise/refresh it if
    already open. `prefill_ship` seeds a new build's Ship field with the
    commander's currently-flown ship (best-effort, see
    ship_builds_panel.py)."""
    global _window
    if _window is not None and _window.alive:
        _window.set_cmdr(cmdr, prefill_ship)
        _window.lift()
        return
    _window = ShipBuildsWindow(parent, repository, cmdr, prefill_ship)


class ShipBuildsWindow:
    def __init__(self, parent: tk.Misc, repository: ShipBuildRepository, cmdr: str, prefill_ship: str) -> None:
        self._repository = repository
        self._cmdr = cmdr
        self._prefill_ship = prefill_ship
        self._builds: list[ShipBuild] = []

        self._shell = WindowShell(
            parent, "Ship Builds", "", size=DEFAULT_SIZE, min_size=(MIN_WIDTH, MIN_HEIGHT),
            load_geometry=lambda: config.get_str(CONFIG_GEOMETRY) or "",
            save_geometry=lambda geometry: config.set(CONFIG_GEOMETRY, geometry))
        self._shell.window.protocol("WM_DELETE_WINDOW", self.close)
        self._toplevel = self._shell.window

        self._shell.add_action("Add", self._on_add, accent=True)
        self._shell.add_action("Edit", self._on_edit)
        self._shell.add_action("Delete", self._on_delete)
        self._shell.add_action("Open Link", self._on_open)
        self._shell.add_action("Copy Link", self._on_copy)

        self._table = DataTable(self._shell.body, _COLUMNS, on_activate=lambda _iid: self._on_edit())
        self._table.pack(fill="both", expand=True, pady=(0, P.PAD_SM))
        self._shell.set_status("Select a build, then use the buttons above. Double-click a row to edit it.")

        repository.add_listener(self._refresh)
        self._refresh()

    @property
    def alive(self) -> bool:
        return self._shell.alive

    def lift(self) -> None:
        self._toplevel.deiconify()
        self._toplevel.lift()

    def set_cmdr(self, cmdr: str, prefill_ship: str) -> None:
        self._cmdr = cmdr
        self._prefill_ship = prefill_ship
        self._refresh()

    def _refresh(self) -> None:
        if not self.alive:
            return
        self._builds = sorted(self._repository.for_cmdr(self._cmdr), key=lambda b: b.updated, reverse=True)
        cmdr_label = self._cmdr or "(no commander detected yet)"
        self._shell.set_subtitle(
            f"{cmdr_label} — {len(self._builds)} saved build{'s' if len(self._builds) != 1 else ''}")

        self._table.clear()
        for build in self._builds:
            self._table.insert(build.id, (build.name, build.ship, build.role, build.site, build.updated[:10]))

    def _selected(self) -> Optional[ShipBuild]:
        selection = self._table.selection()
        if not selection:
            return None
        build_id = selection[0]
        return next((b for b in self._builds if b.id == build_id), None)

    def _on_add(self) -> None:
        if not self._cmdr:
            return
        open_ship_build_dialog(
            self._toplevel, on_save=lambda b: self._repository.add(self._cmdr, b),
            prefill_ship=self._prefill_ship,
        )

    def _on_edit(self) -> None:
        build = self._selected()
        if build is None or not self._cmdr:
            return
        open_ship_build_dialog(
            self._toplevel, on_save=lambda b: self._repository.update(self._cmdr, b), existing=build,
        )

    def _on_delete(self) -> None:
        build = self._selected()
        if build is None or not self._cmdr:
            return
        self._repository.remove(self._cmdr, build.id)

    def _on_open(self) -> None:
        build = self._selected()
        if build is None:
            return
        webbrowser.open(build.url)

    def _on_copy(self) -> None:
        build = self._selected()
        if build is None:
            return
        panelkit.copy_to_clipboard(self._toplevel, build.url)

    def close(self) -> None:
        self._shell.close()
