"""Colonisation Sites window - every tracked construction site for one
commander as a collapsible group, its outstanding commodities beneath it,
with what's already in the hold and what's still to source. Same singleton
window + geometry-persistence convention as the other WNTB windows, built on
the shared window kit (plugin/uikit - see docs/WINDOW_FRAMEWORK_SPEC.md)."""

from __future__ import annotations

import logging
import os
import tkinter as tk
from typing import Dict, Mapping, Optional

from config import appname, config

from . import colonisation, panelkit
from .colonisation_carrier import CarrierCargo
from .colonisation import Site
from .colonisation_data import SiteRepository
from .uikit import palette as P
from .uikit.shell import WindowShell
from .uikit.table import Column, DataTable

plugin_name = os.path.basename(os.path.dirname(__file__))
logger = logging.getLogger(f"{appname}.{plugin_name}")

CONFIG_GEOMETRY = "wntb_colonisation_window_geometry"

MIN_WIDTH = 700
MIN_HEIGHT = 380
DEFAULT_SIZE = (820, 520)

_COLUMNS = (
    Column("name", "Site / Commodity", 260, stretch=True, max_chars=44),
    Column("required", "Required", 90, anchor="e", max_chars=10),
    Column("delivered", "Delivered", 90, anchor="e", max_chars=10),
    Column("remaining", "Remaining", 90, anchor="e", max_chars=10),
    Column("cargo", "In Cargo", 90, anchor="e", max_chars=10),
    Column("source", "To Source", 90, anchor="e", max_chars=10),
)
# Shown only for a commander with a fleet carrier: tonnes moved onto it (colonisation_carrier.py).
_FC_COLUMN = Column("fc", "FC", 70, anchor="e", max_chars=10)

_window: Optional["ColonisationWindow"] = None


def show(parent: tk.Misc, repository: SiteRepository, cmdr: str, cargo: Mapping[str, int],
         carrier: Optional[CarrierCargo] = None) -> None:
    """Open the window for `cmdr`, or raise/refresh it if already open."""
    global _window
    if _window is not None and _window.alive:
        _window.set_cmdr(cmdr)
        _window.set_cargo(cargo)
        _window.lift()
        return
    _window = ColonisationWindow(parent, repository, cmdr, cargo, carrier)


def refresh_cargo(cargo: Mapping[str, int]) -> None:
    """Called by the controller whenever the hold changes; a no-op while the
    window isn't open."""
    if _window is not None and _window.alive:
        _window.set_cargo(cargo)


def refresh_cmdr(cmdr: str) -> None:
    """Called by the controller when the active commander changes, so an open window follows them instead of
    staying on the previous commander's sites."""
    if _window is not None and _window.alive:
        _window.set_cmdr(cmdr)


class ColonisationWindow:
    def __init__(self, parent: tk.Misc, repository: SiteRepository, cmdr: str, cargo: Mapping[str, int],
                 carrier: Optional[CarrierCargo] = None) -> None:
        self._repository = repository
        self._carrier = carrier
        self._with_fc = False
        self._cmdr = cmdr
        self._cargo: Dict[str, int] = dict(cargo)
        self._sites: Dict[int, Site] = {}
        self._row_site: Dict[str, int] = {}

        self._shell = WindowShell(
            parent, "Colonisation Sites", "", size=DEFAULT_SIZE, min_size=(MIN_WIDTH, MIN_HEIGHT),
            load_geometry=lambda: config.get_str(CONFIG_GEOMETRY) or "",
            save_geometry=lambda geometry: config.set(CONFIG_GEOMETRY, geometry))
        self._shell.window.protocol("WM_DELETE_WINDOW", self.close)
        self._toplevel = self._shell.window

        self._shell.add_action("Copy Shopping List", self._on_copy, accent=True)
        self._shell.add_action("Remove Site", self._on_remove)
        self._shell.add_action("Remove Finished", self._on_remove_finished)

        self._table = self._build_table()
        self._shell.set_status("Select a commodity row (or use the site's first one), then use the buttons above.")

        repository.add_listener(self._refresh)
        if carrier is not None:
            carrier.add_listener(self._refresh)
        self._refresh()

    def _build_table(self) -> DataTable:
        columns = _COLUMNS + ((_FC_COLUMN,) if self._with_fc else ())
        table = DataTable(self._shell.body, columns, sortable=False,
                          empty_text="No construction sites yet - dock at a construction depot to register one.")
        table.tag_configure("done", foreground=P.MUTED)
        table.pack(fill="both", expand=True, pady=(0, P.PAD_SM))
        return table

    @property
    def alive(self) -> bool:
        return self._shell.alive

    def lift(self) -> None:
        self._toplevel.deiconify()
        self._toplevel.lift()

    def set_cmdr(self, cmdr: str) -> None:
        self._cmdr = cmdr
        self._refresh()

    def set_cargo(self, cargo: Mapping[str, int]) -> None:
        self._cargo = dict(cargo)
        self._refresh()

    def _refresh(self) -> None:
        if not self.alive:
            return
        sites = self._repository.for_cmdr(self._cmdr)
        self._sites = {s.market_id: s for s in sites}
        active = sum(1 for s in sites if s.active)
        cmdr_label = self._cmdr or "(no commander detected yet)"
        self._shell.set_subtitle(f"{cmdr_label} — {active} active of {len(sites)} site{'s' if len(sites) != 1 else ''}")

        wants_fc = bool(self._carrier and self._cmdr and self._carrier.has_carrier(self._cmdr))
        if wants_fc != self._with_fc:   # the column set changes with the commander: rebuild the table
            self._with_fc = wants_fc
            self._table.destroy()
            self._table = self._build_table()
        on_carrier = self._carrier.tonnes(self._cmdr) if wants_fc and self._carrier else {}
        extra = (lambda value: (value,)) if wants_fc else (lambda value: ())

        selection = self._table.selection()
        self._table.clear()
        self._row_site.clear()
        for site in sites:
            group_id = f"site{site.market_id}"
            status = "complete" if site.complete else "failed" if site.failed else f"{site.progress:.0%}"
            heading = site.display_name() + (f" — {site.system}" if site.system else "")
            self._table.insert(
                group_id, (heading, "", "", f"{site.remaining_total:,}", "", status) + extra(""),
                tag=None if site.active else "done", group=True, open=site.active)
            for resource in site.resources:
                if resource.remaining <= 0:
                    continue
                in_cargo = self._cargo.get(resource.key, 0)
                row_id = f"{group_id}:{resource.key}"
                self._table.insert(
                    row_id,
                    (resource.label, f"{resource.required:,}", f"{resource.provided:,}",
                     f"{resource.remaining:,}", f"{in_cargo:,}" if in_cargo else "",
                     f"{colonisation.still_to_source(resource, self._cargo):,}")
                    + extra(f"{on_carrier[resource.key]:,}" if on_carrier.get(resource.key) else ""),
                    parent=group_id)
                self._row_site[row_id] = site.market_id
        if selection and self._table.exists(selection[0]):
            self._table.select(selection[0])

    def _selected_site(self) -> Optional[Site]:
        selection = self._table.selection()
        if not selection:
            return None
        return self._sites.get(self._row_site.get(selection[0], 0))

    def _on_copy(self) -> None:
        site = self._selected_site()
        if site is None:
            self._shell.set_status("Select a commodity row under the site you want first.")
            return
        lines = [f"{site.display_name()}{f' ({site.system})' if site.system else ''} - still to source:"]
        lines += [f"{amount:,} t  {label}" for label, amount in colonisation.shopping_list(site, self._cargo)]
        if len(lines) == 1:
            lines.append("(nothing - everything needed is already in the hold or delivered)")
        if panelkit.copy_to_clipboard(self._toplevel, "\n".join(lines)):
            self._shell.set_status(f"Copied the shopping list for {site.display_name()}.")

    def _on_remove(self) -> None:
        site = self._selected_site()
        if site is None or not self._cmdr:
            self._shell.set_status("Select a commodity row under the site you want to remove first.")
            return
        self._repository.remove(self._cmdr, site.market_id)

    def _on_remove_finished(self) -> None:
        """Completed/failed sites have no outstanding commodity rows to
        select, so they're cleared in bulk instead."""
        if not self._cmdr:
            return
        finished = [s.market_id for s in self._sites.values() if not s.active]
        for market_id in finished:
            self._repository.remove(self._cmdr, market_id)
        self._shell.set_status(f"Removed {len(finished)} finished site{'s' if len(finished) != 1 else ''}.")

    def close(self) -> None:
        self._shell.close()
