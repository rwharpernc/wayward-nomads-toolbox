"""Colonisation Sites window - the commander's construction sites on the left, and the selected site's shopping list on
the right: progress, the totals (still to source, trips in this ship), filters, and a sortable commodity table with
what the hold and the fleet carrier already cover. Same singleton window + geometry-persistence convention as the other
WNTB windows, built on the shared window kit (plugin/uikit - see docs/WINDOW_FRAMEWORK_SPEC.md). What is shown and
how it adds up lives in colonisation_view.py; this file only draws it."""

from __future__ import annotations

import logging
import os
import tkinter as tk
from typing import Callable, Dict, List, Mapping, Optional

from config import appname, config

from . import colonisation, colonisation_view as view, panelkit
from .colonisation_carrier import CarrierCargo
from .colonisation import Site
from .colonisation_data import SiteRepository
from .uikit import palette as P, style
from .uikit.shell import WindowShell
from .uikit.table import Column, DataTable
from .uikit.widgets import Card, ProgressBar, StatTile, section_header

plugin_name = os.path.basename(os.path.dirname(__file__))
logger = logging.getLogger(f"{appname}.{plugin_name}")

CONFIG_GEOMETRY = "wntb_colonisation_window_geometry"

MIN_WIDTH = 860
MIN_HEIGHT = 460
DEFAULT_SIZE = (1100, 640)

_SITE_COLUMNS = (
    Column("name", "Site", 190, stretch=True, max_chars=40),
    Column("left", "Left", 70, anchor="e", max_chars=10),
    Column("status", "Status", 80, anchor="e", max_chars=10),
)
_COMMODITY_COLUMNS = (
    Column("label", "Commodity", 200, stretch=True, max_chars=40),
    Column("required", "Required", 80, anchor="e", max_chars=10),
    Column("delivered", "Delivered", 80, anchor="e", max_chars=10),
    Column("remaining", "Remaining", 80, anchor="e", max_chars=10),
    Column("cargo", "In Cargo", 80, anchor="e", max_chars=10),
    Column("source", "To Source", 80, anchor="e", max_chars=10),
)
# Shown only for a commander with a fleet carrier: tonnes moved onto it (colonisation_carrier.py).
_FC_COLUMN = Column("fc", "FC", 70, anchor="e", max_chars=10)

_NAME_MAX = 60    # a site's name or system is clipped to this in the detail heading
_window: Optional["ColonisationWindow"] = None


def show(parent: tk.Misc, repository: SiteRepository, cmdr: str, cargo: Mapping[str, int],
         carrier: Optional[CarrierCargo] = None, capacity: Optional[Callable[[], int]] = None) -> None:
    """Open the window for `cmdr`, or raise/refresh it if already open. `capacity` returns the current ship's cargo
    capacity (0 when unknown), for the trips figure."""
    global _window
    if _window is not None and _window.alive:
        _window.set_cmdr(cmdr)
        _window.set_cargo(cargo)
        _window.lift()
        return
    _window = ColonisationWindow(parent, repository, cmdr, cargo, carrier, capacity)


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


def _clip(text: str, limit: int) -> str:
    return text if len(text) <= limit else text[:limit - 1] + "…"


class ColonisationWindow:
    def __init__(self, parent: tk.Misc, repository: SiteRepository, cmdr: str, cargo: Mapping[str, int],
                 carrier: Optional[CarrierCargo] = None, capacity: Optional[Callable[[], int]] = None) -> None:
        self._repository = repository
        self._carrier = carrier
        self._capacity = capacity or (lambda: 0)
        self._with_fc = False
        self._cmdr = cmdr
        self._cargo: Dict[str, int] = dict(cargo)
        self._sites: Dict[int, Site] = {}
        self._selected: Optional[int] = None   # the market id of the site shown on the right
        self._sort_key = "label"
        self._sort_desc = False

        self._shell = WindowShell(
            parent, "Colonisation Sites", "", size=DEFAULT_SIZE, min_size=(MIN_WIDTH, MIN_HEIGHT),
            load_geometry=lambda: config.get_str(CONFIG_GEOMETRY) or "",
            save_geometry=lambda geometry: config.set(CONFIG_GEOMETRY, geometry))
        self._shell.window.protocol("WM_DELETE_WINDOW", self.close)
        self._toplevel = self._shell.window

        self._shell.add_action("Copy Shopping List", self._on_copy, accent=True)
        self._shell.add_action("Remove Site", self._on_remove)
        self._shell.add_action("Remove Finished", self._on_remove_finished)

        self._hide_covered = tk.BooleanVar(master=self._toplevel, value=False)
        self._filter_text = tk.StringVar(master=self._toplevel, value="")

        panes = tk.PanedWindow(self._shell.body, orient="horizontal", bg=P.BG, bd=0, sashwidth=6,
                               sashrelief="flat", opaqueresize=True)
        panes.pack(fill="both", expand=True, pady=(0, P.PAD_SM))

        left = tk.Frame(panes, bg=P.PANE)
        section_header(left, "Sites").pack(fill="x")
        self._site_table = DataTable(
            left, _SITE_COLUMNS, sortable=False, on_activate=self._on_pick_site,
            empty_text="No construction sites yet - dock at a construction depot to register one.")
        self._site_table.tag_configure("done", foreground=P.MUTED)
        self._site_table.pack(fill="both", expand=True)
        panes.add(left, stretch="never", minsize=300, width=340)

        right = tk.Frame(panes, bg=P.PANE)
        panes.add(right, stretch="always", minsize=480)
        self._build_detail(right)

        self._commodity_table = self._build_commodity_table()
        self._shell.set_status("Select a site on the left. Everything on the right, and the buttons above, are for it.")

        repository.add_listener(self._refresh)
        if carrier is not None:
            carrier.add_listener(self._refresh)
        self._refresh()

    # --- layout ----------------------------------------------------------

    def _build_detail(self, right: tk.Frame) -> None:
        self._detail = right
        head = tk.Frame(right, bg=P.PANE, padx=P.PAD, pady=P.PAD_SM)
        head.pack(fill="x")
        self._title = tk.Label(head, text="", fg=P.TEXT, bg=P.PANE, anchor="w", font=style.font(P.FONT_SECTION))
        self._title.pack(fill="x")
        self._where = tk.Label(head, text="", fg=P.MUTED, bg=P.PANE, anchor="w")
        self._where.pack(fill="x")
        self._progress = ProgressBar(head, width=200, height=10)
        self._progress.pack(fill="x", pady=(P.PAD_SM, 0))

        tiles = tk.Frame(right, bg=P.PANE, padx=P.PAD, pady=P.PAD_SM)
        tiles.pack(fill="x")
        self._tile_source = StatTile(tiles, "–", "t still to source", P.ACCENT)
        self._tile_remaining = StatTile(tiles, "–", "t remaining")
        self._tile_hold = StatTile(tiles, "–", "t already in the hold", P.OK)
        self._tile_trips = StatTile(tiles, "–", "trips in this ship", P.INFO)
        for tile in (self._tile_source, self._tile_remaining, self._tile_hold, self._tile_trips):
            tile.pack(side="left", padx=(0, P.PAD_SM))

        filters = tk.Frame(right, bg=P.PANE, padx=P.PAD, pady=P.PAD_SM)
        filters.pack(fill="x")
        tk.Label(filters, text="Filter", fg=P.MUTED, bg=P.PANE).pack(side="left")
        entry = tk.Entry(filters, textvariable=self._filter_text, width=20)
        entry.pack(side="left", padx=(P.PAD_SM, P.PAD))
        self._filter_text.trace_add("write", lambda *_: self._refresh_detail())
        tk.Checkbutton(filters, text="Hide those the hold already covers", variable=self._hide_covered,
                       command=self._refresh_detail).pack(side="left")

    def _build_commodity_table(self) -> DataTable:
        columns = _COMMODITY_COLUMNS + ((_FC_COLUMN,) if self._with_fc else ())
        table = DataTable(self._detail, columns, sortable=False, on_header=self._on_sort,
                          empty_text="Nothing left to deliver here.")
        table.tag_configure("covered", foreground=P.OK)
        table.tag_configure("surplus", foreground=P.WARN)
        table.pack(fill="both", expand=True, pady=(0, P.PAD_SM))
        table.mark_sorted(self._sort_key, self._sort_desc)
        return table

    # --- state ------------------------------------------------------------

    @property
    def alive(self) -> bool:
        return self._shell.alive

    def lift(self) -> None:
        self._toplevel.deiconify()
        self._toplevel.lift()

    def set_cmdr(self, cmdr: str) -> None:
        if cmdr != self._cmdr:
            self._selected = None
        self._cmdr = cmdr
        self._refresh()

    def set_cargo(self, cargo: Mapping[str, int]) -> None:
        self._cargo = dict(cargo)
        self._refresh()

    def _on_pick_site(self, iid: str) -> None:
        try:
            self._selected = int(iid)
        except ValueError:
            return
        self._refresh_detail()

    def _on_sort(self, key: str) -> None:
        self._sort_desc = (self._sort_key == key) and not self._sort_desc
        self._sort_key = key
        self._refresh_detail()

    def _refresh(self) -> None:
        if not self.alive:
            return
        sites = self._repository.for_cmdr(self._cmdr)
        self._sites = {s.market_id: s for s in sites}
        active = sum(1 for s in sites if s.active)
        cmdr_label = self._cmdr or "(no commander detected yet)"
        self._shell.set_subtitle(f"{cmdr_label} — {active} active of {len(sites)} site{'s' if len(sites) != 1 else ''}")

        if self._selected not in self._sites:   # nothing picked yet, or the picked site was removed
            first_active = next((s for s in sites if s.active), None)
            self._selected = (first_active or sites[0]).market_id if sites else None

        self._site_table.clear()
        for site in sites:
            self._site_table.insert(
                str(site.market_id), (site.display_name(), f"{site.remaining_total:,} t", view.site_status(site)),
                tag=None if site.active else "done")
        if self._selected is not None:
            self._site_table.select(str(self._selected))
        self._refresh_detail()

    def _commodity_value(self, row: view.CommodityRow):
        return {"label": row.label.casefold(), "required": row.required, "delivered": row.delivered,
                "remaining": row.remaining, "cargo": row.in_cargo, "source": row.to_source,
                "fc": row.on_carrier}.get(self._sort_key, row.label.casefold())

    def _refresh_detail(self) -> None:
        if not self.alive:
            return
        site = self._sites.get(self._selected) if self._selected is not None else None

        wants_fc = bool(self._carrier and self._cmdr and self._carrier.has_carrier(self._cmdr))
        if wants_fc != self._with_fc:   # the column set changes with the commander: rebuild the table
            self._with_fc = wants_fc
            self._commodity_table.destroy()
            self._commodity_table = self._build_commodity_table()

        self._commodity_table.clear()
        if site is None:
            self._title.configure(text="No site selected")
            self._where.configure(text="")
            self._progress.set(0)
            for tile in (self._tile_source, self._tile_remaining, self._tile_hold, self._tile_trips):
                tile.set("–")
            return

        self._title.configure(text=_clip(site.display_name(), _NAME_MAX))
        self._where.configure(text=_clip(site.system, _NAME_MAX) + f"  ·  {view.site_status(site)}"
                              if site.system else view.site_status(site))
        self._progress.set(100 if site.complete else site.progress * 100, P.OK if site.complete else P.INFO)
        totals = view.totals(site, self._cargo, self._capacity())
        self._tile_source.set(f"{totals.to_source:,}")
        self._tile_remaining.set(f"{totals.remaining:,}")
        self._tile_hold.set(f"{totals.in_hold:,}")
        self._tile_trips.set(f"{totals.trips:,}" if totals.trips else "–")

        on_carrier = self._carrier.tonnes(self._cmdr) if wants_fc and self._carrier else {}
        rows: List[view.CommodityRow] = view.commodity_rows(
            site, self._cargo, on_carrier, self._hide_covered.get(), self._filter_text.get())
        rows.sort(key=self._commodity_value, reverse=self._sort_desc)
        self._commodity_table.mark_sorted(self._sort_key, self._sort_desc)
        for row in rows:
            values = (row.label, f"{row.required:,}", f"{row.delivered:,}", f"{row.remaining:,}",
                      f"{row.in_cargo:,}" if row.in_cargo else "", f"{row.to_source:,}")
            if wants_fc:
                values += (f"{row.on_carrier:,}" if row.on_carrier else "",)
            tag = "surplus" if row.in_cargo > row.remaining else "covered" if row.covered else None
            self._commodity_table.insert(f"{site.market_id}:{row.key}", values, tag=tag)
        if totals.lines and not rows:
            self._shell.set_status("The filters hide every commodity this site still needs.")
        else:
            self._shell.set_status(f"{totals.lines} commodit{'y' if totals.lines == 1 else 'ies'} still needed, "
                                   f"{totals.covered} covered by the hold.")

    # --- buttons -----------------------------------------------------------

    def _selected_site(self) -> Optional[Site]:
        return self._sites.get(self._selected) if self._selected is not None else None

    def _on_copy(self) -> None:
        site = self._selected_site()
        if site is None:
            self._shell.set_status("Select a site on the left first.")
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
            self._shell.set_status("Select the site you want to remove on the left first.")
            return
        self._repository.remove(self._cmdr, site.market_id)

    def _on_remove_finished(self) -> None:
        """Clears every completed or failed site at once."""
        if not self._cmdr:
            return
        finished = [s.market_id for s in self._sites.values() if not s.active]
        for market_id in finished:
            self._repository.remove(self._cmdr, market_id)
        self._shell.set_status(f"Removed {len(finished)} finished site{'s' if len(finished) != 1 else ''}.")

    def close(self) -> None:
        self._shell.close()
