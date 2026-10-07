"""Ship Builds: a per-commander catalog of *links* to builds designed on
external shipyard sites (Coriolis, EDSY, Spansh, ...) - see
ship_builds_data.py's own docstring for the "we don't build loadouts,
EDMC's own Shipyard provider setting already does that for your current
ship - this just organizes the links a commander saves after designing a
build on one of those sites" framing.

Field Ops only (PANEL_PLACEMENT = "fieldops") - ship loadouts are part of
gearing up for on-foot/cargo ops, not every mode.
Keeps the main-panel footprint to one summary line + one button (same
"summary in panel, full CRUD list in a popup window" split as
codex_completionist_panel.py/codex_completionist_window.py) since the
actual list belongs in ship_builds_window.py's Treeview, not this narrow
panel.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, Optional

import tkinter as tk

import myNotebook as nb
from config import appname

from . import panelkit, ship_builds_window
from .ship_builds_data import ShipBuildRepository, ship_build_repository

plugin_name = os.path.basename(os.path.dirname(__file__))
logger = logging.getLogger(f"{appname}.{plugin_name}")

PANEL_PLACEMENT = "fieldops"

_NO_CMDR_TEXT = "Ship Builds: (waiting for commander login)"


class ShipBuildsController:
    def __init__(self, repository: ShipBuildRepository) -> None:
        self._repository = repository
        self._cmdr: Optional[str] = None
        # Best-effort prefill for the dialog's Ship field, from the
        # journal's own Loadout/LoadGame events - not authoritative (no
        # internal-name-to-display-name table exists anywhere in WNTB, see
        # this module's own docstring), just saves retyping the common
        # case. A commander can always correct it before saving.
        self._current_ship: str = ""

        self._summary_var: Optional[tk.StringVar] = None
        self._parent: Optional[tk.Frame] = None

    # --- lifecycle ----------------------------------------------------------

    def start(self, plugin_dir: str) -> None:
        self._repository.load(plugin_dir)
        self._repository.add_listener(self._refresh_summary)

    # --- journal dispatch -----------------------------------------------

    def handle_event(self, entry: Dict[str, Any], cmdr: str, system: Optional[str], station: Optional[str], state: Dict[str, Any]) -> None:
        if cmdr and cmdr != self._cmdr:
            self._cmdr = cmdr
            self._refresh_summary()

        event = entry.get("event")
        if event in ("Loadout", "LoadGame"):
            ship = entry.get("Ship_Localised") or entry.get("Ship")
            if isinstance(ship, str) and ship:
                self._current_ship = ship

    def _refresh_summary(self) -> None:
        if self._summary_var is None:
            return
        if not self._cmdr:
            self._summary_var.set(_NO_CMDR_TEXT)
            return
        count = len(self._repository.for_cmdr(self._cmdr))
        self._summary_var.set(f"Ship Builds: {count} saved for {self._cmdr}")

    # --- main-panel widgets -----------------------------------------------

    def build_panel(self, parent: tk.Frame) -> None:
        self._parent = parent
        self._summary_var = tk.StringVar(value=_NO_CMDR_TEXT)
        self._refresh_summary()

        tk.Label(parent, text="Ship Builds", font=panelkit.bold_font(parent)).grid(
            row=0, column=0, columnspan=3, sticky=tk.W,
        )
        panelkit.wrap_label(parent, textvariable=self._summary_var, anchor="w").grid(
            row=1, column=0, columnspan=3, sticky=tk.W, pady=(2, 0),
        )
        manage_button = tk.Button(parent, text="BLD", command=self._on_manage_clicked)
        manage_button.grid(row=2, column=0, sticky=tk.W, pady=(4, 0))
        panelkit.add_tooltip(manage_button, "Manage Ship Builds - open your ship builds")

    def _on_manage_clicked(self) -> None:
        if self._parent is None:
            return
        ship_builds_window.show(self._parent, self._repository, self._cmdr or "", self._current_ship)

    # --- Settings tab --------------------------------------------------

    def build_settings(self, notebook: nb.Notebook) -> None:
        frame = nb.Frame(notebook)
        frame.columnconfigure(0, weight=1)
        notebook.add(frame, text="Ship Builds")

        nb.Label(frame, text="Ship Builds", font=("TkDefaultFont", 9, "bold")).grid(
            row=0, column=0, sticky=tk.W, padx=10, pady=(10, 4),
        )
        nb.Label(
            frame,
            text=(
                "A per-commander catalog of links to builds you've designed on an external "
                "shipyard site (Coriolis, EDSY, Spansh, or anywhere else). WNTB doesn't build "
                "loadouts itself — keep doing that on those sites — this just organizes the links "
                "so you can find the right build again later. Click \"Manage Ship Builds\" (visible "
                "in every mode) to add, edit, or remove entries."
            ),
            wraplength=440, justify=tk.LEFT,
        ).grid(row=1, column=0, sticky=tk.W, padx=10, pady=(0, 10))

    def save_settings(self) -> None:
        pass


controller = ShipBuildsController(ship_build_repository)


def start(plugin_dir: str) -> None:
    controller.start(plugin_dir)


def handle_event(entry: Dict[str, Any], cmdr: str, system: Optional[str], station: Optional[str], state: Dict[str, Any]) -> None:
    controller.handle_event(entry, cmdr, system, station, state)


def build_panel(parent: tk.Frame) -> None:
    controller.build_panel(parent)


def build_settings(notebook: nb.Notebook) -> None:
    controller.build_settings(notebook)


def save_settings() -> None:
    controller.save_settings()
