"""Colonisation: tracks what each colonisation construction site still needs
delivered (see colonisation.py), and compares it to the cargo currently
aboard so a hauler can see what's left to source.

Field Ops only (PANEL_PLACEMENT = "fieldops") - hauling is ship/SRV cargo
work, alongside Inventory and Ship Builds. Same "one summary line + one
button in the panel, full list in a popup window" split as Ship Builds, so
the main panel stays narrow however many sites or commodities there are.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, Optional

import tkinter as tk

import myNotebook as nb
from config import appname

from . import colonisation, colonisation_window, panelkit
from .colonisation import Site
from .colonisation_data import SiteRepository, site_repository

plugin_name = os.path.basename(os.path.dirname(__file__))
logger = logging.getLogger(f"{appname}.{plugin_name}")

PANEL_PLACEMENT = "fieldops"

_NO_CMDR_TEXT = "Colonisation: (waiting for commander login)"
_NAME_MAX = 40


def _clip(text: str, limit: int) -> str:
    return text if len(text) <= limit else text[:limit - 1] + "…"


class ColonisationController:
    def __init__(self, repository: SiteRepository) -> None:
        self._repository = repository
        self._cmdr: Optional[str] = None
        # The depot events carry only a MarketID, so the station name is
        # remembered from the latest Docked (MarketID -> (station, system)).
        self._docked: Dict[int, tuple] = {}
        self._cargo: Dict[str, int] = {}

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

        cargo = colonisation.cargo_by_key(state.get("Cargo"))
        if cargo != self._cargo:
            self._cargo = cargo
            colonisation_window.refresh_cargo(cargo)

        event = entry.get("event")
        if not self._cmdr:
            return
        if event == "Docked":
            market_id = entry.get("MarketID")
            if isinstance(market_id, int) and entry.get("StationName"):
                self._docked[market_id] = (str(entry["StationName"]), str(entry.get("StarSystem") or system or ""))
        elif event == colonisation.EVENT_DEPOT:
            market_id = entry.get("MarketID")
            existing = self._repository.get(self._cmdr, market_id) if isinstance(market_id, int) else None
            # Work on a copy so the repository can tell whether anything changed.
            working = Site.from_dict(existing.to_dict()) if existing else None
            name, docked_system = self._docked.get(market_id, ("", system or "")) if isinstance(market_id, int) else ("", "")
            site = colonisation.apply_depot_event(entry, working, name=name, system=docked_system)
            if site is not None:
                self._repository.upsert(self._cmdr, site)
        elif event == colonisation.EVENT_CONTRIBUTION:
            market_id = entry.get("MarketID")
            existing = self._repository.get(self._cmdr, market_id) if isinstance(market_id, int) else None
            if existing is not None:
                working = Site.from_dict(existing.to_dict())
                if colonisation.apply_contribution(working, entry):
                    self._repository.upsert(self._cmdr, working)

    def _refresh_summary(self) -> None:
        if self._summary_var is None:
            return
        if not self._cmdr:
            self._summary_var.set(_NO_CMDR_TEXT)
            return
        active = [s for s in self._repository.for_cmdr(self._cmdr) if s.active]
        if not active:
            self._summary_var.set("Colonisation: no active construction sites")
            return
        latest = active[0]
        extra = f" (+{len(active) - 1} more)" if len(active) > 1 else ""
        self._summary_var.set(
            f"Colonisation: {_clip(latest.display_name(), _NAME_MAX)} — "
            f"{latest.progress:.0%}, {latest.remaining_total:,} t to go{extra}"
        )

    # --- main-panel widgets -----------------------------------------------

    def build_panel(self, parent: tk.Frame) -> None:
        self._parent = parent
        self._summary_var = tk.StringVar(value=_NO_CMDR_TEXT)
        self._refresh_summary()

        tk.Label(parent, text="Colonisation", font=panelkit.bold_font(parent)).grid(
            row=0, column=0, columnspan=3, sticky=tk.W,
        )
        panelkit.wrap_label(parent, textvariable=self._summary_var, anchor="w").grid(
            row=1, column=0, columnspan=3, sticky=tk.W, pady=(2, 0),
        )
        manage_button = tk.Button(parent, text="COL", command=self._on_manage_clicked)
        manage_button.grid(row=2, column=0, sticky=tk.W, pady=(4, 0))
        panelkit.add_tooltip(manage_button, "Colonisation Sites - open your colonisation sites")

    def _on_manage_clicked(self) -> None:
        if self._parent is None:
            return
        colonisation_window.show(self._parent, self._repository, self._cmdr or "", self._cargo)

    # --- Settings tab --------------------------------------------------

    def build_settings(self, notebook: nb.Notebook) -> None:
        frame = nb.Frame(notebook)
        frame.columnconfigure(0, weight=1)
        notebook.add(frame, text="Colonisation")

        nb.Label(frame, text="Colonisation", font=("TkDefaultFont", 9, "bold")).grid(
            row=0, column=0, sticky=tk.W, padx=10, pady=(10, 4),
        )
        nb.Label(
            frame,
            text=(
                "Tracks what each colonisation construction site still needs delivered. Dock at a "
                "construction depot (or open its market) once to register it; deliveries are then "
                "tallied from your journal. Click \"Colonisation Sites\" (visible in Field Ops) to "
                "see each site's outstanding commodities against the cargo you're carrying, and to "
                "copy a shopping list."
            ),
            wraplength=440, justify=tk.LEFT,
        ).grid(row=1, column=0, sticky=tk.W, padx=10, pady=(0, 10))

    def save_settings(self) -> None:
        pass


controller = ColonisationController(site_repository)


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
