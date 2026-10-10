"""
Mining mode's feature-module contract entry point. Owns the panel's
persistent chrome (page nav between Space Mining/Surface Mining, the
scrollable Canvas/Scrollbar frame mirroring missions_ui.py's own
pattern, and the six persistent hotspot/finder buttons - see their own
docstring below for why they're never destroyed/recreated), the
Settings tab, and the full journal/dashboard dispatch. Per-page content
rendering lives in `mining_render.py`; HUD-overlay pushes live in
`mining_overlay.py`; the data models live in `mining_space.py`/
`mining_surface.py`/`mining_hotspots.py`.

`PANEL_PLACEMENT = "mining"` - the last mode this project's own
placeholder ("Mining - coming soon.") covered; landing this file's
import in `ui.py`'s FEATURES tuple is what makes that placeholder
disappear.
"""
from __future__ import annotations

import logging
import os
import threading
import tkinter as tk
from typing import Any, Dict, Optional

import myNotebook as nb
from config import appname, config

from . import edsm_client
from . import mining_body_survey as body_survey
from . import mining_ledger as ledger
from . import mining_coverage as coverage
from . import mining_hotspot_finder_dialog as hotspot_finder_dialog
from . import mining_hotspot_import_export as hotspot_import_export
from . import mining_hotspot_settings
from . import mining_hotspots as hotspots
from . import mining_journal_backfill as journal_backfill
from . import mining_live_position as live_position
from . import mining_location as location
from . import mining_overlay
from . import mining_pages
from . import mining_price_finder_dialog as price_finder_dialog
from . import mining_render as render
from . import mining_reserve_lookup_dialog as reserve_lookup_dialog
from . import mining_session_archive as session_archive
from . import mining_space as space_mining
from . import mining_surface as surface_mining
from . import overlay
from . import panelkit

plugin_name = os.path.basename(os.path.dirname(__file__))
logger = logging.getLogger(f"{appname}.{plugin_name}")

PANEL_PLACEMENT = "mining"

# --- Config keys (wntb_mining_*) -------------------------------------------

_CFG_DISPLAY_SESSION_TOTALS = "wntb_mining_display_session_totals"
_CFG_DISPLAY_CARGO_BAR = "wntb_mining_display_cargo_bar"
_CFG_DISPLAY_PROSPECTOR_HINTS = "wntb_mining_display_prospector_hints"
_CFG_SPANSH_HOTSPOT_FINDER_ENABLED = "wntb_mining_spansh_hotspot_finder_enabled"
_CFG_SPANSH_PRICE_FINDER_ENABLED = "wntb_mining_spansh_price_finder_enabled"
_CFG_EDSM_RESERVE_LOOKUP_ENABLED = "wntb_mining_edsm_reserve_lookup_enabled"
_CFG_OVERLAY_ENABLED = "wntb_mining_overlay_enabled"
_CFG_WAYPOINT_OVERLAY_ENABLED = "wntb_mining_waypoint_overlay_enabled"
_CFG_DISPLAY_COVERAGE_MINIMAP = "wntb_mining_display_coverage_minimap"
_CFG_ARCHIVE_SESSIONS = "wntb_mining_archive_sessions"
_CFG_CURRENT_PAGE = "wntb_mining_current_page"

_MAX_PANEL_HEIGHT = 260
"""Hard cap on the scrollable content area's rendered height, in pixels
- past this the content scrolls internally instead of growing EDMC's
window. This bounds one axis; wraplength (panelkit.wrap_label-derived)
bounds the other."""

_CONTENT_RIGHT_MARGIN = 8
_WRAP_FALLBACK = 280
_PERIODIC_TICK_MS = 1000
"""How often the panel re-renders itself with no new journal event, so
the "Refining rate" hint (mining_rate.py) visibly decays back toward
zero during a mining lull rather than freezing at its last value."""



def _cfg_bool(key: str, default: bool) -> bool:
    return config.get_bool(key, default=default)


def _settings() -> render.PanelSettings:
    return render.PanelSettings(
        display_session_totals=_cfg_bool(_CFG_DISPLAY_SESSION_TOTALS, True),
        display_cargo_bar=_cfg_bool(_CFG_DISPLAY_CARGO_BAR, True),
        display_prospector_hints=_cfg_bool(_CFG_DISPLAY_PROSPECTOR_HINTS, True),
        spansh_hotspot_finder_enabled=_cfg_bool(_CFG_SPANSH_HOTSPOT_FINDER_ENABLED, False),
        spansh_price_finder_enabled=_cfg_bool(_CFG_SPANSH_PRICE_FINDER_ENABLED, False),
        edsm_reserve_lookup_enabled=_cfg_bool(_CFG_EDSM_RESERVE_LOOKUP_ENABLED, False),
        display_coverage_minimap=_cfg_bool(_CFG_DISPLAY_COVERAGE_MINIMAP, False),
    )


class MiningPanelController:
    def __init__(self) -> None:
        self._plugin_dir: Optional[str] = None
        self._parent: Optional[tk.Frame] = None
        self._nav: Optional[tk.Frame] = None
        self._page_label: Optional[tk.Label] = None
        self._canvas: Optional[tk.Canvas] = None
        self._scrollbar: Optional[tk.Scrollbar] = None
        self._content: Optional[tk.Frame] = None
        self._content_window: Optional[int] = None
        self._wrap = _WRAP_FALLBACK
        self._buttons: Optional[render.PanelButtons] = None
        self._current_page = config.get_str(_CFG_CURRENT_PAGE) or mining_pages.PAGE_ORDER[0]
        if self._current_page not in mining_pages.PAGE_ORDER:
            self._current_page = mining_pages.PAGE_ORDER[0]

        self._backfilling = False
        """True only while replaying today's journal file through
        handle_event() on a mid-session start. Guards the two side
        effects that only make sense for a live event: the automatic
        EDSM ring-reserve lookup (would otherwise fire once per ring
        visited today, hammering edsm.net on every EDMC restart) and
        session-archive writes (would otherwise re-archive a run an
        earlier EDMC process already wrote to disk, under a fresh
        now()-stamped filename each time)."""
        self._ring_reserve_cache: Dict[Any, Optional[space_mining.RingCaution]] = {}
        """(system, ring) -> the EDSM lookup result, keyed casefold -
        see _check_ring_reserve(). Ring composition/reserve level is
        static game data, so this never needs invalidating; it just
        stops repeated supercruise hops within the same belt from
        re-querying edsm.net every time."""

        # Settings-tab variables, populated in build_settings().
        self._display_session_totals_var: Optional[tk.BooleanVar] = None
        self._display_cargo_bar_var: Optional[tk.BooleanVar] = None
        self._display_prospector_hints_var: Optional[tk.BooleanVar] = None
        self._spansh_hotspot_finder_var: Optional[tk.BooleanVar] = None
        self._spansh_price_finder_var: Optional[tk.BooleanVar] = None
        self._edsm_reserve_lookup_var: Optional[tk.BooleanVar] = None
        self._overlay_enabled_var: Optional[tk.BooleanVar] = None
        self._waypoint_overlay_enabled_var: Optional[tk.BooleanVar] = None
        self._display_coverage_minimap_var: Optional[tk.BooleanVar] = None
        self._archive_sessions_var: Optional[tk.BooleanVar] = None

    # --- lifecycle -----------------------------------------------------

    def start(self, plugin_dir: str) -> None:
        self._plugin_dir = plugin_dir
        hotspots.hotspot_repository.load(plugin_dir)
        coverage.coverage_repository.load(plugin_dir)
        space_mining.space_mining_repository.add_listener(lambda _run: self._redraw_if_alive())
        surface_mining.surface_mining_repository.add_listener(lambda _run: self._redraw_if_alive())
        hotspots.hotspot_repository.add_listener(self._redraw_if_alive)

    def set_overlay_client(self, client: overlay.OverlayClient) -> None:
        mining_overlay.set_overlay_client(client)

    def stop(self) -> None:
        hotspots.hotspot_repository.flush()  # mined-ton counts are saved on a throttle, not per ton

    def _credit_mined_ton(self, surface_repo: surface_mining.SurfaceMiningRepository) -> None:
        """One refined ton -> the nearest recorded hotspot (see
        HotspotRepository.add_mined_tons). Skipped during journal
        backfill, where live position isn't available anyway."""
        position = live_position.current_position()
        radius = surface_repo.radius_for_current_body()
        system, body = surface_repo.current_system, surface_repo.current_body
        if self._backfilling or position is None or not radius or not system or not body:
            return
        hotspots.hotspot_repository.add_mined_tons(
            system, body, position.latitude, position.longitude, radius)

    # --- panel chrome ----------------------------------------------------

    def build_panel(self, parent: tk.Frame) -> None:
        parent.columnconfigure(0, weight=1)
        parent.columnconfigure(1, weight=0)  # the scrollbar column keeps its natural width
        self._parent = parent

        self._nav = tk.Frame(parent)
        self._nav.grid(column=0, row=0, columnspan=2, sticky="ew")
        panelkit.nav_arrow(self._nav, -1, lambda: self._step_page(-1)).pack(side=tk.LEFT)
        self._page_label = tk.Label(self._nav, anchor=tk.CENTER)
        self._page_label.pack(side=tk.LEFT, fill=tk.X, expand=True)
        panelkit.nav_arrow(self._nav, 1, lambda: self._step_page(1)).pack(side=tk.LEFT)

        # width=1: a bare Canvas requests 10 cm of width, which would widen EDMC's window; it
        # stretches to the panel's width instead (sticky="ew").
        self._canvas = tk.Canvas(parent, width=1, highlightthickness=0, borderwidth=0, yscrollincrement=24)
        self._canvas.grid(column=0, row=1, sticky="ew")
        self._scrollbar = tk.Scrollbar(parent, orient="vertical", command=self._canvas.yview)
        self._scrollbar.grid(column=1, row=1, sticky="ns")
        self._canvas.configure(yscrollcommand=self._scrollbar.set)

        self._content = tk.Frame(self._canvas)
        self._content.columnconfigure(0, weight=1)
        self._content_window = self._canvas.create_window((0, 0), window=self._content, anchor="nw")

        # These six buttons are created once and kept alive for the life
        # of the panel, unlike every other widget in self._content
        # (destroyed and rebuilt on every _redraw() call, including once
        # a second from the periodic tick). A plain tk.Button uses
        # native OS chrome, and destroying/recreating one every second
        # produces a visible flicker on Windows even when theme colors
        # come out right each time - see mining_render.py's
        # place_button_bar().
        # All six live in one frame (the "bar"), so a page can show them side by
        # side in a single row instead of one per row (render.place_button_bar).
        button_bar = tk.Frame(self._content)
        self._buttons = render.PanelButtons(
            bar=button_bar,
            hotspot_finder=tk.Button(
                button_bar, text="H.S.",
                command=lambda: hotspot_finder_dialog.open_hotspot_finder_dialog(self._content)),
            save_hotspot=tk.Button(
                button_bar, text="+H.S.",
                command=lambda: render.open_add_hotspot_dialog(self._content)),
            price_finder=tk.Button(
                button_bar, text="PRICE",
                command=lambda: price_finder_dialog.open_price_finder_dialog(
                    self._content, suggested_commodities=self._current_run_refined_commodities())),
            reserve_lookup=tk.Button(
                button_bar, text="RES",
                command=lambda: reserve_lookup_dialog.open_reserve_lookup_dialog(self._content)),
            hotspot_import_export=tk.Button(
                button_bar, text="I/E",
                command=lambda: hotspot_import_export.open_import_export_dialog(self._content)),
            ledger=tk.Button(
                button_bar, text="BOOK",
                command=lambda: ledger.show(self._content)),
        )
        for button, tip in (
                (self._buttons.hotspot_finder, "Find Nearby Hotspots - find rings with a confirmed hotspot for a commodity (Spansh)"),
                (self._buttons.save_hotspot, "Save Hotspot Here - save the current ring as a hotspot"),
                (self._buttons.price_finder, "Find Best Price - find the best-paying station for a commodity (Spansh)"),
                (self._buttons.reserve_lookup, "Check Ring Reserve Level - look up a ring's reserve level"),
                (self._buttons.hotspot_import_export, "Import/Export Hotspots - import or export your saved hotspots"),
                (self._buttons.ledger, "Mining Book - open your mining ledger")):
            panelkit.add_tooltip(button, tip)
        for button in (self._buttons.hotspot_finder, self._buttons.save_hotspot,
                      self._buttons.price_finder, self._buttons.reserve_lookup,
                      self._buttons.hotspot_import_export, self._buttons.ledger):
            button.grid_remove()

        self._content.bind("<Configure>", self._sync_scroll_region)
        self._canvas.bind("<Configure>", self._on_canvas_resize)
        self._canvas.bind("<Enter>", lambda _e: self._bind_mousewheel())
        self._canvas.bind("<Leave>", lambda _e: self._unbind_mousewheel())

        self._redraw()
        parent.after(100, self._redraw_if_alive)
        parent.after(_PERIODIC_TICK_MS, self._periodic_tick)

    def _redraw_if_alive(self) -> None:
        if self._parent is not None and self._parent.winfo_exists():
            self._redraw()

    def _periodic_tick(self) -> None:
        if self._parent is None or not self._parent.winfo_exists():
            return
        self._redraw()
        self._parent.after(_PERIODIC_TICK_MS, self._periodic_tick)

    def _on_canvas_resize(self, event: tk.Event) -> None:
        width = max(event.width - _CONTENT_RIGHT_MARGIN, 0)
        self._canvas.itemconfigure(self._content_window, width=width)
        if width > 1:
            self._wrap = max(width - 20, 80)

    def _sync_scroll_region(self, _event: Optional[tk.Event] = None) -> None:
        if self._canvas is None:
            return
        self._canvas.update_idletasks()
        bbox = self._canvas.bbox("all")
        content_height = (bbox[3] - bbox[1]) if bbox else 0
        self._canvas.configure(scrollregion=bbox, height=min(content_height, _MAX_PANEL_HEIGHT))
        if content_height > _MAX_PANEL_HEIGHT:
            self._scrollbar.grid()
        else:
            self._scrollbar.grid_remove()

    def _bind_mousewheel(self) -> None:
        self._canvas.bind_all("<MouseWheel>", self._on_mousewheel)
        self._canvas.bind_all("<Button-4>", self._on_mousewheel)
        self._canvas.bind_all("<Button-5>", self._on_mousewheel)

    def _unbind_mousewheel(self) -> None:
        self._canvas.unbind_all("<MouseWheel>")
        self._canvas.unbind_all("<Button-4>")
        self._canvas.unbind_all("<Button-5>")

    def _on_mousewheel(self, event: tk.Event) -> None:
        if getattr(event, "num", None) == 4:
            self._canvas.yview_scroll(-3, "units")
        elif getattr(event, "num", None) == 5:
            self._canvas.yview_scroll(3, "units")
        elif event.delta:
            self._canvas.yview_scroll(-3 if event.delta > 0 else 3, "units")

    def _step_page(self, direction: int) -> None:
        order = mining_pages.PAGE_ORDER
        idx = order.index(self._current_page)
        self._current_page = order[(idx + direction) % len(order)]
        config.set(_CFG_CURRENT_PAGE, self._current_page)
        self._redraw()

    def _current_run_refined_commodities(self) -> list:
        """Whichever page is showing when "Find Best Price..." is
        clicked, suggest commodities from *that* page's own current run
        - the button is shared since both mining types produce
        commodities worth a price check, but each page's `refined` dict
        lives on a different repository/run type."""
        if self._current_page == mining_pages.SURFACE_MINING:
            run = surface_mining.surface_mining_repository.current_run()
        else:
            run = space_mining.space_mining_repository.current_run()
        return list(run.refined.keys()) if run is not None else []

    def _redraw(self) -> None:
        if self._content is None or not self._content.winfo_exists():
            return

        frame_bg = self._parent.cget("background")

        for child in self._content.winfo_children():
            if child is self._buttons.bar:
                continue
            child.destroy()

        self._page_label.configure(text=self._current_page)
        settings = _settings()

        if self._current_page == mining_pages.SPACE_MINING:
            render.render_space_mining(self._content, self._wrap, self._buttons, settings)
        elif self._current_page == mining_pages.SURFACE_MINING:
            render.render_surface_mining(self._content, self._wrap, self._buttons, settings)

        if _cfg_bool(_CFG_OVERLAY_ENABLED, False):
            mining_overlay.push_stats_overlay(
                self._current_page, display_cargo_bar=settings.display_cargo_bar,
                display_session_totals=settings.display_session_totals,
                display_prospector_hints=settings.display_prospector_hints,
            )
        if self._current_page == mining_pages.SURFACE_MINING and _cfg_bool(_CFG_WAYPOINT_OVERLAY_ENABLED, False):
            mining_overlay.push_waypoint_overlay()

        panelkit.apply_theme_deep(self._content)
        self._canvas.configure(background=frame_bg)
        self._content.configure(background=frame_bg)
        self._sync_scroll_region()

    # --- journal/dashboard dispatch --------------------------------------

    def handle_event(self, entry: Dict[str, Any], cmdr: Optional[str], system: Optional[str],
                     station: Optional[str], state: Dict[str, Any]) -> None:
        if cmdr:
            hotspots.hotspot_repository.set_commander(cmdr)
            coverage.coverage_repository.set_commander(cmdr)
            space_mining.space_mining_repository.set_current_cmdr(cmdr)
            surface_mining.surface_mining_repository.set_current_cmdr(cmdr)
        location.set_current_system(system)

        event = entry.get("event")
        space_repo = space_mining.space_mining_repository
        surface_repo = surface_mining.surface_mining_repository

        if event == "StartUp":
            # EDMC sends this synthetic event once, only when it's
            # started while the game is already running - the only
            # signal a mid-session start happened.
            self._backfill_from_journal(cmdr)

        elif event == "Undocked":
            space_repo.start_new_run()

        elif event == "Docked":
            run = space_repo.current_run()
            if not self._backfilling and _cfg_bool(_CFG_ARCHIVE_SESSIONS, False) and run is not None and run.has_data():
                session_archive.archive_run(self._plugin_dir, "space", cmdr, run)

        elif event == "SupercruiseEntry":
            space_repo.pause_run()
            space_repo.set_current_ring(system, None)

        elif event == "SupercruiseExit":
            space_repo.resume_run()
            ring = entry.get("Body") if entry.get("BodyType") == "PlanetaryRing" else None
            space_repo.set_current_ring(system, ring)
            if ring and _cfg_bool(_CFG_EDSM_RESERVE_LOOKUP_ENABLED, False) and not self._backfilling:
                self._check_ring_reserve(system, ring)

        elif event == "LaunchSRV":
            if entry.get("SRVType") == surface_mining.RHINO_SRV_TYPE:
                surface_repo.start_run(entry.get("ID"))

        elif event == "DockSRV":
            if entry.get("SRVType") == surface_mining.RHINO_SRV_TYPE:
                run = surface_repo.current_run()
                if run is not None and run.cargo:
                    # Docking the Rhino automatically transfers whatever's
                    # still in its hold to the ship - move it over
                    # directly rather than leaving the panel/overlay
                    # showing cargo that's no longer actually in the SRV
                    # (a later authoritative Cargo event, if one arrives,
                    # just overwrites this).
                    space_repo.adjust_cargo(run.cargo)
                    surface_repo.update_cargo(0)
                surface_repo.end_run(entry.get("ID"))
                run = surface_repo.current_run()
                if (not self._backfilling and _cfg_bool(_CFG_ARCHIVE_SESSIONS, False)
                        and run is not None and run.has_data()):
                    session_archive.archive_run(self._plugin_dir, "surface", cmdr, run)

        elif event in ("SRVDestroyed", "Died"):
            surface_repo.force_end_run()

        elif event == "ProspectedAsteroid":
            space_repo.record_prospected(entry.get("Content", ""), entry.get("Content_Localised"),
                                         entry.get("Materials"))

        elif event == "AsteroidCracked":
            space_repo.record_asteroid_cracked()

        elif event == "LaunchDrone":
            space_repo.record_limpet(entry.get("Type", "Unknown"))

        elif event == "BuyDrones":
            space_repo.record_limpets_bought(entry.get("Count", 0))

        elif event == "Loadout":
            capacity = entry.get("CargoCapacity")
            if isinstance(capacity, int):
                space_repo.update_cargo_capacity(capacity)

        elif event == "MiningRefined":
            # Same event for ship-based and Rhino mining - nothing in
            # the event itself says which. Route by whether a Rhino is
            # currently deployed.
            commodity = entry.get("Type_Localised") or entry.get("Type", "Unknown")
            if surface_repo.is_active:
                surface_repo.record_refined(commodity)
                self._credit_mined_ton(surface_repo)
            else:
                space_repo.record_refined(commodity)

        elif event == "Cargo":
            vessel = entry.get("Vessel")
            count = entry.get("Count", 0)
            if vessel == "Ship":
                space_repo.update_cargo(count)
            elif vessel == "SRV":
                surface_repo.update_cargo(count)

        elif event == "CargoTransfer":
            for transfer in entry.get("Transfers", []):
                if transfer.get("Direction") != "toship":
                    continue
                commodity = transfer.get("Type_Localised") or str(transfer.get("Type", "Unknown")).capitalize()
                count = transfer.get("Count", 0)
                surface_repo.record_transfer_to_ship(commodity, count)
                space_repo.adjust_cargo(count)

        elif event == "MaterialCollected":
            if surface_repo.is_active:
                material = entry.get("Name_Localised") or str(entry.get("Name", "Unknown")).capitalize()
                surface_repo.record_raw_material(material, entry.get("Count", 0))

        elif event == "SAASignalsFound":
            for signal in entry.get("Signals", []):
                if signal.get("Type") == surface_mining.MINING_LOCATION_SIGNAL_TYPE:
                    body_name = entry.get("BodyName", "?")
                    surface_repo.record_mining_location_signal(body_name, signal.get("Count", 0))
                    body_survey.system_body_survey.record_signal(system, body_name, signal.get("Count", 0))

        elif event == "Location":
            body = entry.get("Body") if entry.get("BodyType") == "Planet" else None
            surface_repo.set_current_location(entry.get("StarSystem"), body)
            body_survey.system_body_survey.on_system_changed(entry.get("StarSystem"))

        elif event == "FSDJump":
            surface_repo.set_current_location(entry.get("StarSystem"), None)
            body_survey.system_body_survey.on_system_changed(entry.get("StarSystem"))

        elif event == "ApproachBody":
            surface_repo.set_current_location(entry.get("StarSystem"), entry.get("Body"))

        elif event == "LeaveBody":
            surface_repo.set_current_location(entry.get("StarSystem"), None)

        elif event == "Touchdown":
            latitude, longitude = entry.get("Latitude"), entry.get("Longitude")
            if isinstance(latitude, (int, float)) and isinstance(longitude, (int, float)):
                surface_repo.record_touchdown(latitude, longitude)

        elif event == "Liftoff":
            surface_repo.clear_touchdown()

        elif event == "Scan":
            radius = entry.get("Radius")
            body_name = entry.get("BodyName")
            if isinstance(radius, (int, float)) and body_name:
                surface_repo.record_body_radius(body_name, radius)
            body_survey.system_body_survey.record_scan(
                system, body_name, entry.get("PlanetClass"), entry.get("Volcanism"),
                bool(entry.get("Landable", False)))

    def _backfill_from_journal(self, cmdr: str) -> None:
        """Replays today's journal file through handle_event() itself
        (the same method this is called from), so a mid-session EDMC
        start ends up with the same state as if EDMC had been running
        the whole time - the in-progress run, current cargo, current
        body (needed for the "Save Hotspot Here" button to even
        appear), last touchdown, etc. Reuses handle_event()'s own
        dispatch rather than duplicating it, since replaying an entry is
        exactly what handle_event() already does for a live one.

        `cmdr` starts as whatever EDMC's StartUp event carried, but a
        journal file can span more than one commander if the player
        switched account without restarting the game, so it's
        re-derived per `Commander` event while walking the file."""
        path = journal_backfill.find_current_journal_file()
        if path is None:
            return
        self._backfilling = True
        try:
            current_cmdr = cmdr
            current_system = ""
            for line_entry in journal_backfill.read_entries(path):
                event = line_entry.get("event")
                if event == "Commander":
                    name = line_entry.get("Name")
                    if name:
                        current_cmdr = name
                    continue
                system = line_entry.get("StarSystem")
                if system:
                    current_system = system
                self.handle_event(line_entry, current_cmdr, current_system, "", {})
        except Exception:
            logger.exception("Mining journal backfill failed")
        finally:
            self._backfilling = False
        self._redraw_if_alive()

    def _check_ring_reserve(self, system: str, ring: str) -> None:
        """Automatic counterpart to mining_reserve_lookup_dialog.py's
        on-demand search - fired from `SupercruiseExit` when the
        "Enable EDSM Ring Reserve Lookup" setting is on, so the passive
        Space Mining panel line doesn't need a button press. A cache hit
        resolves synchronously (main thread, no network call); a miss
        runs on a background thread, marshaling the result back via
        `after(0, ...)`."""
        key = (system.casefold(), ring.casefold())
        if key in self._ring_reserve_cache:
            space_mining.space_mining_repository.set_ring_caution(system, ring, self._ring_reserve_cache[key])
            return

        def _worker() -> None:
            raw_bodies = edsm_client.system_bodies(system)
            if raw_bodies is None:
                return
            bodies = reserve_lookup_dialog.parse_ringed_bodies(raw_bodies)
            match = reserve_lookup_dialog.find_body_or_ring(bodies, ring)
            caution = None
            if match is not None:
                ring_info = next(
                    (r for r in match.rings if r.name.strip().casefold() == ring.strip().casefold()), None)
                if ring_info is not None:
                    caution = space_mining.RingCaution(
                        ring_name=ring, reserve_level=match.reserve_level,
                        ring_type=ring_info.ring_type, is_metallic=ring_info.is_metallic())
            self._ring_reserve_cache[key] = caution
            if self._parent is not None and self._parent.winfo_exists():
                self._parent.after(0, lambda: space_mining.space_mining_repository.set_ring_caution(
                    system, ring, caution))

        threading.Thread(target=_worker, daemon=True, name="WNTB-mining-edsm-auto-lookup").start()

    def dashboard_status(self, entry: Dict[str, Any]) -> None:
        """Status.json's live Latitude/Longitude/Heading - a separate
        hook from handle_event above, since Status.json isn't a
        discrete journal event (see mining_live_position.py's module
        docstring). The periodic tick picks up whatever this last
        recorded the next time it redraws, so there's no need to force
        a refresh here."""
        live_position.set_status(entry)

        # Coverage minimap: only while a Rhino is actually deployed
        # (surface_mining_repository.is_active, set from LaunchSRV/
        # DockSRV journal events - not Status.json's own SRV flag, no
        # reason to parse that separately when this is already tracked)
        # and a body radius is known - without one there's no way to
        # convert lat/lon into metres for the map's geometry.
        surface_repo = surface_mining.surface_mining_repository
        position = live_position.current_position()
        radius = surface_repo.radius_for_current_body()
        if surface_repo.is_active and position is not None and radius:
            system, body = surface_repo.current_system, surface_repo.current_body
            if system and body:
                coverage.coverage_repository.record(system, body, position.latitude,
                                                    position.longitude, radius)

    # --- Settings tab ----------------------------------------------------

    def build_settings(self, notebook: nb.Notebook) -> None:
        frame = nb.Frame(notebook)
        frame.columnconfigure(0, weight=1)
        notebook.add(frame, text="Mining")

        self._display_session_totals_var = tk.BooleanVar(value=_cfg_bool(_CFG_DISPLAY_SESSION_TOTALS, True))
        self._display_cargo_bar_var = tk.BooleanVar(value=_cfg_bool(_CFG_DISPLAY_CARGO_BAR, True))
        self._display_prospector_hints_var = tk.BooleanVar(value=_cfg_bool(_CFG_DISPLAY_PROSPECTOR_HINTS, True))
        self._spansh_hotspot_finder_var = tk.BooleanVar(value=_cfg_bool(_CFG_SPANSH_HOTSPOT_FINDER_ENABLED, False))
        self._spansh_price_finder_var = tk.BooleanVar(value=_cfg_bool(_CFG_SPANSH_PRICE_FINDER_ENABLED, False))
        self._edsm_reserve_lookup_var = tk.BooleanVar(value=_cfg_bool(_CFG_EDSM_RESERVE_LOOKUP_ENABLED, False))
        self._overlay_enabled_var = tk.BooleanVar(value=_cfg_bool(_CFG_OVERLAY_ENABLED, False))
        self._waypoint_overlay_enabled_var = tk.BooleanVar(value=_cfg_bool(_CFG_WAYPOINT_OVERLAY_ENABLED, False))
        self._display_coverage_minimap_var = tk.BooleanVar(value=_cfg_bool(_CFG_DISPLAY_COVERAGE_MINIMAP, False))
        self._archive_sessions_var = tk.BooleanVar(value=_cfg_bool(_CFG_ARCHIVE_SESSIONS, False))

        nb.Label(frame, text="UI Settings").grid(row=0, column=0, sticky=tk.W, padx=10, pady=(10, 2))
        nb.Checkbutton(frame, text="Display Session Totals",
                       variable=self._display_session_totals_var).grid(row=1, column=0, sticky=tk.W, padx=10)
        nb.Checkbutton(frame, text="Display Cargo Bar",
                       variable=self._display_cargo_bar_var).grid(row=2, column=0, sticky=tk.W, padx=10)
        nb.Checkbutton(frame, text="Display Prospector Hints",
                       variable=self._display_prospector_hints_var).grid(row=3, column=0, sticky=tk.W, padx=10)

        nb.Checkbutton(
            frame, text="Enable Spansh Nearby Hotspot Finder (Space Mining page - contacts spansh.co.uk)",
            variable=self._spansh_hotspot_finder_var,
        ).grid(row=4, column=0, sticky=tk.W, padx=10, pady=(6, 0))
        nb.Checkbutton(
            frame, text="Enable Spansh Best Price Finder (both pages - contacts spansh.co.uk)",
            variable=self._spansh_price_finder_var,
        ).grid(row=5, column=0, sticky=tk.W, padx=10)
        nb.Checkbutton(
            frame, text=("Enable EDSM Ring Reserve Lookup (Space Mining page - automatically contacts "
                        "edsm.net every time you drop into a ring, plus manual search)"),
            variable=self._edsm_reserve_lookup_var,
        ).grid(row=6, column=0, sticky=tk.W, padx=10)
        nb.Checkbutton(
            frame, text="Enable HUD Overlay (sends live stats to the overlay - see the Overlay Connection tab)",
            variable=self._overlay_enabled_var,
        ).grid(row=7, column=0, sticky=tk.W, padx=10)
        nb.Checkbutton(
            frame, text=("Enable Surface Waypoint Overlay (arrow + distance to the nearest known "
                        "hotspot on the current body)"),
            variable=self._waypoint_overlay_enabled_var,
        ).grid(row=8, column=0, sticky=tk.W, padx=10)
        nb.Checkbutton(
            frame, text=("Show Coverage Minimap (Surface Mining page - a small map of ground the "
                        "Rhino has driven over on the current body; redrawn once a second while "
                        "deployed)"),
            variable=self._display_coverage_minimap_var,
        ).grid(row=9, column=0, sticky=tk.W, padx=10)
        nb.Checkbutton(
            frame, text="Archive Completed Mining Runs (writes a JSON file per run)",
            variable=self._archive_sessions_var,
        ).grid(row=10, column=0, sticky=tk.W, padx=10)

        mining_hotspot_settings.build(frame, start_row=11)

    def save_settings(self) -> None:
        if self._display_session_totals_var is None:
            return
        config.set(_CFG_DISPLAY_SESSION_TOTALS, bool(self._display_session_totals_var.get()))
        config.set(_CFG_DISPLAY_CARGO_BAR, bool(self._display_cargo_bar_var.get()))
        config.set(_CFG_DISPLAY_PROSPECTOR_HINTS, bool(self._display_prospector_hints_var.get()))
        config.set(_CFG_SPANSH_HOTSPOT_FINDER_ENABLED, bool(self._spansh_hotspot_finder_var.get()))
        config.set(_CFG_SPANSH_PRICE_FINDER_ENABLED, bool(self._spansh_price_finder_var.get()))
        config.set(_CFG_EDSM_RESERVE_LOOKUP_ENABLED, bool(self._edsm_reserve_lookup_var.get()))
        config.set(_CFG_OVERLAY_ENABLED, bool(self._overlay_enabled_var.get()))
        config.set(_CFG_WAYPOINT_OVERLAY_ENABLED, bool(self._waypoint_overlay_enabled_var.get()))
        config.set(_CFG_DISPLAY_COVERAGE_MINIMAP, bool(self._display_coverage_minimap_var.get()))
        config.set(_CFG_ARCHIVE_SESSIONS, bool(self._archive_sessions_var.get()))
        self._redraw_if_alive()


controller = MiningPanelController()


def set_overlay_client(client: overlay.OverlayClient) -> None:
    controller.set_overlay_client(client)


def start(plugin_dir: str) -> None:
    controller.start(plugin_dir)


def stop() -> None:
    controller.stop()


def build_panel(parent: tk.Frame) -> None:
    controller.build_panel(parent)


def build_settings(notebook: nb.Notebook) -> None:
    controller.build_settings(notebook)


def save_settings() -> None:
    controller.save_settings()


def handle_event(entry: Dict[str, Any], cmdr: Optional[str], system: Optional[str],
                 station: Optional[str], state: Dict[str, Any]) -> None:
    controller.handle_event(entry, cmdr, system, station, state)


def dashboard_status(entry: Dict[str, Any]) -> None:
    controller.dashboard_status(entry)
