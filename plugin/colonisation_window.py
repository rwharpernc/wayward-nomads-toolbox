"""Colonisation Sites window - the commander's construction sites on the left, and the selected site's shopping list on
the right: progress, the totals (still to get, the ship's capacity, trips to finish the build), filters, and a sortable commodity table with
what the ship and the fleet carrier already cover. Beneath that, "Where to buy" finds the closest stations (and, if
asked, fleet carriers) with the picked commodity in stock. Same singleton window + geometry-persistence convention as
the other WNTB windows, built on the shared window kit (plugin/uikit - see docs/WINDOW_FRAMEWORK_SPEC.md). What is
shown and how it adds up lives in colonisation_view.py, and the search in colonisation_sources.py; this file only
draws them."""

from __future__ import annotations

import logging
import os
import threading
import tkinter as tk
from typing import Any, Callable, Dict, List, Mapping, Optional

from config import appname, config

from . import colonisation, colonisation_sources as sources, colonisation_view as view, panelkit
from .colonisation_carrier import CarrierCargo
from .colonisation import Site
from .colonisation_data import SiteRepository
from .uikit import palette as P, style
from .uikit.shell import WindowShell
from .uikit.table import Column, DataTable
from .uikit.widgets import Combobox, FlatButton, ProgressBar, StatTile, section_header

plugin_name = os.path.basename(os.path.dirname(__file__))
logger = logging.getLogger(f"{appname}.{plugin_name}")

CONFIG_GEOMETRY = "wntb_colonisation_window_geometry"

MIN_WIDTH = 1180
MIN_HEIGHT = 640
DEFAULT_SIZE = (1300, 780)

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
    Column("trips", "Trips Left", 90, anchor="e", max_chars=10),
)
# Shown only for a commander with a fleet carrier: tons moved onto it (colonisation_carrier.py).
_FC_COLUMN = Column("fc", "FC", 70, anchor="e", max_chars=10)
_SOURCE_COLUMNS = (
    Column("station", "Station", 120, stretch=True, max_chars=32),
    Column("system", "System", 110, stretch=True, max_chars=30),
    Column("kind", "Type", 100, max_chars=20),
    Column("planetary", "Planetary", 80, anchor="center", max_chars=4),
    Column("pad", "Pad", 60, max_chars=8),
    Column("distance", "Distance", 70, anchor="e", max_chars=12),
    Column("arrival", "Arrival", 80, anchor="e", max_chars=12),
    Column("price", "Price", 70, anchor="e", max_chars=10),
    Column("supply", "Supply", 70, anchor="e", max_chars=10),
)
_PAD_ORDER = {"Large": 0, "Medium": 1, "Small": 2, "?": 3}
_NO_LIMIT = "No limit"
_SORT_CHOICES = (("Closest first", sources.SORT_DISTANCE), ("Cheapest first", sources.SORT_PRICE))
_POLL_MS = 150
_ERROR_MAX = 90    # a failure message from outside is clipped to this
_NAME_MAX = 60     # a site's name or system is clipped to this in the detail heading
_window: Optional["ColonisationWindow"] = None


def show(parent: tk.Misc, repository: SiteRepository, cmdr: str, cargo: Mapping[str, int],
         carrier: Optional[CarrierCargo] = None, capacity: Optional[Callable[[], int]] = None,
         current_system: Optional[Callable[[], str]] = None) -> None:
    """Open the window for `cmdr`, or raise/refresh it if already open. `capacity` returns the current ship's cargo
    capacity (0 when unknown), for the trips figure; `current_system` the system the commander is in, for the
    "Here" button of the where-to-buy search."""
    global _window
    if _window is not None and _window.alive:
        _window.set_cmdr(cmdr)
        _window.set_cargo(cargo)
        _window.lift()
        return
    _window = ColonisationWindow(parent, repository, cmdr, cargo, carrier, capacity, current_system)


def refresh_cargo(cargo: Mapping[str, int]) -> None:
    """Called by the controller whenever the ship's cargo changes; a no-op while the
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
                 carrier: Optional[CarrierCargo] = None, capacity: Optional[Callable[[], int]] = None,
                 current_system: Optional[Callable[[], str]] = None) -> None:
        self._repository = repository
        self._carrier = carrier
        self._capacity = capacity or (lambda: 0)
        self._current_system = current_system or (lambda: "")
        self._with_fc = False
        self._cmdr = cmdr
        self._cargo: Dict[str, int] = dict(cargo)
        self._sites: Dict[int, Site] = {}
        self._selected: Optional[int] = None   # the market id of the site shown on the right
        self._sort_key = "label"
        self._sort_desc = False
        self._row_label: Dict[str, str] = {}     # commodity table row id -> the commodity's name
        self._wanted: Optional[str] = None       # the commodity row picked for the where-to-buy search
        self._system_edited = False              # the commander typed their own search system
        self._search_id = 0                      # which search the window waits for; older answers are dropped
        self._result: Optional[sources.SearchResult] = None
        self._result_label = ""
        self._source_sort = ("distance", False)
        self._source_rows: Dict[str, str] = {}   # result row id -> its system name, for Copy System

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
        self._system_var = tk.StringVar(master=self._toplevel, value="")
        self._carriers_var = tk.BooleanVar(master=self._toplevel, value=False)

        panes = tk.PanedWindow(self._shell.body, orient="horizontal", bg=P.BG, bd=0, sashwidth=6,
                               sashrelief="flat", opaqueresize=True)
        panes.pack(fill="both", expand=True, pady=(0, P.PAD_SM))

        left = tk.Frame(panes, bg=P.PANE)
        section_header(left, "Sites").pack(fill="x")
        self._site_table = DataTable(
            left, _SITE_COLUMNS, sortable=False, on_select=self._on_pick_site,
            empty_text="No construction sites yet - dock at a construction depot to register one.")
        self._site_table.tag_configure("done", foreground=P.MUTED)
        self._site_table.pack(fill="both", expand=True)
        panes.add(left, stretch="never", minsize=300, width=340)

        right = tk.Frame(panes, bg=P.PANE)
        panes.add(right, stretch="always", minsize=760)
        self._build_detail(right)

        self._commodity_table = self._build_commodity_table()
        self._build_sources(self._sources_host)
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
        self._tile_get = StatTile(tiles, "–", "t still to get", P.ACCENT)
        self._tile_remaining = StatTile(tiles, "–", "t remaining")
        self._tile_hold = StatTile(tiles, "–", "t already in your ship", P.OK)
        self._tile_ship = StatTile(tiles, "–", "t ship capacity")
        self._tile_trips = StatTile(tiles, "–", "trips to finish", P.INFO)
        for tile in (self._tile_get, self._tile_remaining, self._tile_hold, self._tile_ship, self._tile_trips):
            tile.pack(side="left", padx=(0, P.PAD_SM))

        filters = tk.Frame(right, bg=P.PANE, padx=P.PAD, pady=P.PAD_SM)
        filters.pack(fill="x")
        tk.Label(filters, text="Filter", fg=P.MUTED, bg=P.PANE).pack(side="left")
        entry = tk.Entry(filters, textvariable=self._filter_text, width=20)
        entry.pack(side="left", padx=(P.PAD_SM, P.PAD))
        self._filter_text.trace_add("write", lambda *_: self._refresh_detail())
        tk.Checkbutton(filters, text="Hide rows already covered", variable=self._hide_covered,
                       command=self._refresh_detail).pack(side="left")

        # The commodity table above, the where-to-buy panel below; the divider between them can be dragged.
        rows = tk.PanedWindow(right, orient="vertical", bg=P.BG, bd=0, sashwidth=6, sashrelief="flat",
                              opaqueresize=True)
        rows.pack(fill="both", expand=True)
        self._table_host = tk.Frame(rows, bg=P.PANE)
        rows.add(self._table_host, stretch="always", minsize=150)
        self._sources_host = tk.Frame(rows, bg=P.PANE)
        rows.add(self._sources_host, stretch="always", minsize=230)

    def _build_commodity_table(self) -> DataTable:
        columns = _COMMODITY_COLUMNS + ((_FC_COLUMN,) if self._with_fc else ())
        table = DataTable(self._table_host, columns, sortable=False, on_header=self._on_sort,
                          on_select=self._on_pick_commodity, empty_text="Nothing left to deliver here.")
        # Whole-row tints: green when the ship plus the fleet carrier covers the need, orange when it is more than needed.
        table.tag_configure(view.STATE_ENOUGH, foreground=P.TEXT, background=P.ROW_OK)
        table.tag_configure(view.STATE_OVER, foreground=P.TEXT, background=P.ROW_OVER)
        table.pack(fill="both", expand=True)
        table.mark_sorted(self._sort_key, self._sort_desc)
        return table

    def _build_sources(self, host: tk.Frame) -> None:
        """The where-to-buy search: its options, the Find nearest button and the table of results."""
        section_header(host, "Where to buy").pack(fill="x")
        options = tk.Frame(host, bg=P.PANE, padx=P.PAD, pady=P.PAD_SM)
        options.pack(fill="x")
        first = tk.Frame(options, bg=P.PANE)
        first.pack(fill="x")
        tk.Label(first, text="Around", fg=P.MUTED, bg=P.PANE).pack(side="left")
        entry = tk.Entry(first, textvariable=self._system_var, width=26)
        entry.pack(side="left", padx=(P.PAD_SM, P.PAD_SM))
        entry.bind("<KeyRelease>", lambda _e: setattr(self, "_system_edited", True))
        FlatButton(first, "Here", self._on_here).pack(side="left", padx=(0, P.PAD))
        tk.Label(first, text="Within", fg=P.MUTED, bg=P.PANE).pack(side="left")
        self._radius = Combobox(first, state="readonly", width=9,
                                values=[f"{r} ly" for r in sources.RADIUS_CHOICES] + [_NO_LIMIT])
        self._radius.set(f"{sources.DEFAULT_RADIUS_LY} ly")
        self._radius.pack(side="left", padx=(P.PAD_SM, P.PAD))
        tk.Label(first, text="Sort", fg=P.MUTED, bg=P.PANE).pack(side="left")
        self._sort = Combobox(first, state="readonly", width=14, values=[label for label, _ in _SORT_CHOICES])
        self._sort.current(0)
        self._sort.pack(side="left", padx=(P.PAD_SM, 0))

        second = tk.Frame(options, bg=P.PANE, pady=P.PAD_SM)
        second.pack(fill="x")
        tk.Label(second, text="Landing pad", fg=P.MUTED, bg=P.PANE).pack(side="left")
        self._pad = Combobox(second, state="readonly", width=17, values=[label for _, label in sources.PAD_CHOICES])
        self._pad.current(0)
        self._pad.pack(side="left", padx=(P.PAD_SM, P.PAD))
        tk.Checkbutton(second, text="Include fleet carriers", variable=self._carriers_var).pack(side="left")
        self._find_button = FlatButton(second, "Find nearest", self._on_find, kind="accent")
        self._find_button.pack(side="right")
        FlatButton(second, "Copy System", self._on_copy_system).pack(side="right", padx=(0, 6))

        self._sources_note = tk.Label(host, text="Pick a commodity row above, then Find nearest.", fg=P.MUTED,
                                      bg=P.PANE, anchor="w", justify="left", padx=P.PAD)
        self._sources_note.pack(fill="x")
        host.bind("<Configure>", lambda e: self._sources_note.configure(wraplength=max(e.width - 2 * P.PAD, 100)))
        self._source_table = DataTable(host, _SOURCE_COLUMNS, sortable=False, on_header=self._on_source_sort,
                                       empty_text="No search yet.")
        self._source_table.tag_configure("carrier", foreground=P.INFO)
        self._source_table.pack(fill="both", expand=True)

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
            self._wanted = None
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
        self._wanted = None
        self._refresh_detail()

    def _on_pick_commodity(self, iid: str) -> None:
        self._wanted = self._row_label.get(iid)
        if self._wanted:
            self._sources_note.configure(text=f"Ready to search for {self._wanted}. Press Find nearest.")

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
                "remaining": row.remaining, "cargo": row.in_cargo, "trips": row.remaining,
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
        self._row_label.clear()
        if site is None:
            self._title.configure(text="No site selected")
            self._where.configure(text="")
            self._progress.set(0)
            for tile in (self._tile_get, self._tile_remaining, self._tile_hold, self._tile_ship, self._tile_trips):
                tile.set("–")
            return

        self._title.configure(text=_clip(site.display_name(), _NAME_MAX))
        self._where.configure(text=_clip(site.system, _NAME_MAX) + f"  ·  {view.site_status(site)}"
                              if site.system else view.site_status(site))
        self._progress.set(100 if site.complete else site.progress * 100, P.OK if site.complete else P.INFO)
        if site.system and not self._system_edited:   # search around the site unless the commander chose elsewhere
            self._system_var.set(site.system)
        on_carrier = self._carrier.tonnes(self._cmdr) if wants_fc and self._carrier else {}
        capacity = self._capacity()
        totals = view.totals(site, self._cargo, capacity, on_carrier)
        self._tile_get.set(f"{totals.to_get:,}")
        self._tile_remaining.set(f"{totals.remaining:,}")
        self._tile_hold.set(f"{totals.in_hold:,}")
        self._tile_ship.set(f"{capacity:,}" if capacity > 0 else "–")
        self._tile_trips.set(f"{totals.trips:,}" if totals.trips else "–")

        rows: List[view.CommodityRow] = view.commodity_rows(
            site, self._cargo, on_carrier, self._hide_covered.get(), self._filter_text.get(), capacity)
        rows.sort(key=self._commodity_value, reverse=self._sort_desc)
        self._commodity_table.mark_sorted(self._sort_key, self._sort_desc)
        for row in rows:
            values = (row.label, f"{row.required:,}", f"{row.delivered:,}", f"{row.remaining:,}",
                      f"{row.in_cargo:,}" if row.in_cargo else "", view.format_trips(row.trips))
            if wants_fc:
                values += (f"{row.on_carrier:,}" if row.on_carrier else "",)
            tag = None if row.state == view.STATE_SHORT else row.state
            iid = f"{site.market_id}:{row.key}"
            self._row_label[iid] = row.label
            self._commodity_table.insert(iid, values, tag=tag)
        wanted_iid = next((i for i, label in self._row_label.items() if label == self._wanted), None)
        if wanted_iid:
            self._commodity_table.select(wanted_iid)
        if totals.lines and not rows:
            self._shell.set_status("The filters hide every commodity this site still needs.")
        else:
            ship = (f"Your {capacity:,} t ship takes {totals.trips:,} trip{'s' if totals.trips != 1 else ''} to finish."
                    if capacity > 0 and totals.trips else "Your ship's cargo capacity isn't known yet.")
            self._shell.set_status(f"{totals.lines} commodit{'y' if totals.lines == 1 else 'ies'} still needed, "
                                   f"{totals.covered} covered by your ship and carrier. {ship}")

    # --- where to buy ----------------------------------------------------------

    def _on_here(self) -> None:
        here = self._current_system()
        if not here:
            self._sources_note.configure(text="WNTB hasn't seen which system you are in yet.")
            return
        self._system_var.set(here)
        self._system_edited = True

    def _radius_ly(self) -> Optional[float]:
        text = self._radius.get()
        if text == _NO_LIMIT:
            return None
        try:
            return float(text.split()[0])
        except (ValueError, IndexError):
            return float(sources.DEFAULT_RADIUS_LY)

    def _pad_choice(self) -> str:
        label = self._pad.get()
        return next((key for key, text in sources.PAD_CHOICES if text == label), sources.PAD_ANY)

    def _sort_choice(self) -> str:
        label = self._sort.get()
        return next((key for text, key in _SORT_CHOICES if text == label), sources.SORT_DISTANCE)

    def _on_find(self) -> None:
        """Starts the search on a worker thread (Spansh can take seconds) and polls for its answer."""
        if not self._wanted:
            self._sources_note.configure(text="Pick a commodity row above first.")
            return
        system = self._system_var.get().strip()
        if not system:
            self._sources_note.configure(text="Enter a system to search around, or press Here.")
            return
        commodity, radius, pad = self._wanted, self._radius_ly(), self._pad_choice()
        carriers, order = bool(self._carriers_var.get()), self._sort_choice()
        self._search_id += 1
        job: Dict[str, Any] = {"id": self._search_id, "done": False, "result": None, "error": ""}
        self._find_button.set_enabled(False)
        self._sources_note.configure(text=f"Searching for {commodity} around {_clip(system, _NAME_MAX)}…")

        def work() -> None:
            try:
                job["result"] = sources.find(system, commodity, radius_ly=radius, pad=pad,
                                             include_carriers=carriers, sort=order)
            except Exception as exc:   # network, parse or bad input: shown, not raised into the main thread
                logger.exception("Colonization where-to-buy search failed")
                job["error"] = str(exc) or exc.__class__.__name__
            job["done"] = True

        threading.Thread(target=work, daemon=True, name="WNTB-colonisation-sources").start()
        self._toplevel.after(_POLL_MS, self._poll_search, job, commodity, system)

    def _poll_search(self, job: Dict[str, Any], commodity: str, system: str) -> None:
        if not self.alive or job["id"] != self._search_id:
            return
        if not job["done"]:
            self._toplevel.after(_POLL_MS, self._poll_search, job, commodity, system)
            return
        self._find_button.set_enabled(True)
        if job["error"]:
            self._sources_note.configure(
                text=f"The search failed: {_clip(job['error'], _ERROR_MAX)}. Spansh may be busy; try again shortly.")
            return
        self._result, self._result_label = job["result"], commodity
        self._render_sources(system)

    def _on_source_sort(self, key: str) -> None:
        descending = self._source_sort[0] == key and not self._source_sort[1]
        self._source_sort = (key, descending)
        if self._result is not None:
            self._render_sources()

    @staticmethod
    def _source_value(source: sources.Source, key: str):
        return {"station": source.station.casefold(), "system": source.system.casefold(), "kind": source.kind.casefold(),
                "planetary": source.is_planetary, "pad": _PAD_ORDER.get(source.pad, 3), "distance": source.distance_ly, "arrival": source.arrival_ls,
                "price": source.price, "supply": source.supply}[key]

    def _render_sources(self, system: str = "") -> None:
        result = self._result
        if result is None or not self.alive:
            return
        key, descending = self._source_sort
        self._source_table.clear()
        self._source_table.mark_sorted(key, descending)
        self._source_rows.clear()

        def add(group: List[sources.Source], prefix: str, tag: Optional[str], parent: Optional[str]) -> None:
            for index, item in enumerate(sorted(group, key=lambda s: self._source_value(s, key), reverse=descending)):
                iid = f"{prefix}{index}"
                self._source_rows[iid] = item.system
                self._source_table.insert(
                    iid, (item.station, item.system, item.kind, "Yes" if item.is_planetary else "No", item.pad,
                          f"{item.distance_ly:,.1f} ly",
                          f"{item.arrival_ls:,.0f} ls" if item.arrival_ls else "", f"{item.price:,}",
                          f"{item.supply:,}"), tag=tag, parent=parent)

        add(result.stations, "s", None, None)
        if result.carriers:
            self._source_table.insert("carriers", (f"Fleet carriers ({len(result.carriers)})", "", "", "", "", "", "", "", ""),
                                      tag="carrier", group=True, open=True)
            add(result.carriers, "c", "carrier", "carriers")
        stations, carriers = len(result.stations), len(result.carriers)
        if not stations and not carriers:
            self._sources_note.configure(
                text=f"Nothing found with {self._result_label} in stock. Try a larger radius, any landing pad size, "
                     f"or include fleet carriers.")
            return
        extra = f" and {carriers} fleet carrier{'s' if carriers != 1 else ''}" if carriers else ""
        around = f" around {_clip(system, _NAME_MAX)}" if system else ""
        self._sources_note.configure(
            text=f"{self._result_label}: {stations} station{'s' if stations != 1 else ''}{extra}{around}. Price is per "
                 f"ton; the data is from players' own market updates, so confirm on arrival.")

    def _on_copy_system(self) -> None:
        selection = self._source_table.selection()
        system = self._source_rows.get(selection[0]) if selection else None
        if not system:
            self._sources_note.configure(text="Select a result row first.")
            return
        if panelkit.copy_to_clipboard(self._toplevel, system):
            self._sources_note.configure(text=f"Copied {_clip(system, _NAME_MAX)} to the clipboard.")

    # --- buttons -----------------------------------------------------------

    def _selected_site(self) -> Optional[Site]:
        return self._sites.get(self._selected) if self._selected is not None else None

    def _carrier_tons(self) -> Dict[str, int]:
        """Tons moved onto the commander's fleet carrier, or nothing for a commander without one."""
        if self._carrier and self._cmdr and self._carrier.has_carrier(self._cmdr):
            return self._carrier.tonnes(self._cmdr)
        return {}

    def _on_copy(self) -> None:
        site = self._selected_site()
        if site is None:
            self._shell.set_status("Select a site on the left first.")
            return
        lines = [f"{site.display_name()}{f' ({site.system})' if site.system else ''} - still to get:"]
        lines += [f"{amount:,} t  {label}" for label, amount in colonisation.shopping_list(site, self._cargo, self._carrier_tons())]
        if len(lines) == 1:
            lines.append("(nothing - everything needed is already on your ship, on your carrier or delivered)")
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
        self._search_id += 1   # a search still running has nowhere to show its answer
        self._shell.close()
