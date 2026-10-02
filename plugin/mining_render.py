"""
Mining mode's per-page content rendering: this module owns "what goes on the panel for the Space Mining /
Surface Mining page", while
`mining_panel.py` owns the panel's persistent chrome (page nav, the
scrollable Canvas/Scrollbar frame, the persistent hotspot/finder
buttons) and calls into `render_space_mining()`/`render_surface_mining()`
each time it needs to redraw.

Every label showing variable-length content uses the `wrap` value
`mining_panel.py` derives from the canvas's real measured width, never a
fixed wraplength - see the main-window-sizing rule in this repo's
CLAUDE.md.
"""
import tkinter as tk
import dataclasses
from dataclasses import dataclass
from typing import Dict, List, Optional

from . import mining_coverage as coverage
from . import mining_coverage_render as coverage_render
from . import mining_deposit
from . import mining_ground
from . import mining_hotspots as hotspots
from . import mining_live_position as live_position
from . import mining_methods
from . import mining_rate
from . import mining_space as space_mining
from . import mining_surface as surface_mining
from .mining_body_survey import system_body_survey

_ROW_LIMIT = 8
"""Cap on distinct commodities/limpet-types shown per summary line - a
long mining trip can rack up a dozen+ distinct materials, and every line
below already goes through wraplength, but capping the count keeps a
single line from becoming a wall of text no one reads."""

_WARNING_COLOR = "#c0392b"
"""Same hex as mining_reserve_lookup_dialog.py's own warning color -
kept in sync deliberately so the passive ring-caution line here and the
manual dialog's result read as the same warning, not two different
reds."""


@dataclass
class PanelSettings:
    """The subset of mining_panel.py's config Mining's own render/overlay
    logic needs - passed in explicitly rather than each render function
    reaching into config itself, so this module stays a pure "given this
    state, build these widgets" layer."""
    display_session_totals: bool
    display_cargo_bar: bool
    display_prospector_hints: bool
    spansh_hotspot_finder_enabled: bool
    spansh_price_finder_enabled: bool
    edsm_reserve_lookup_enabled: bool
    display_coverage_minimap: bool


@dataclass
class PanelButtons:
    """The panel's persistent buttons (see mining_panel.py's module
    docstring for why they're created once and only grid()/grid_remove()'d
    rather than destroyed/recreated every render - the same native-widget-
    flicker lesson every WNTB feature with a persistent button follows)."""
    hotspot_finder: tk.Button
    save_hotspot: tk.Button
    price_finder: tk.Button
    reserve_lookup: tk.Button
    hotspot_import_export: tk.Button
    ledger: tk.Button


def format_counts(counts: Dict[str, int], with_mine_via: bool = False) -> str:
    """{"Palladium": 12, "Osmium": 3} -> "Palladium x12, Osmium x3" -
    highest count first, capped at _ROW_LIMIT distinct entries so a trip
    with a dozen+ commodities doesn't produce one unreadably long line.

    with_mine_via appends each commodity's mining_methods.py extraction-
    method hint, e.g. "Painite x3 (Mine via: Core, Laser Surface or
    Sub-surface Deposit)" - only meaningful for dicts keyed by commodity
    display name (refined/prospected_commodities), not limpet types."""
    if not counts:
        return "none yet"
    items = sorted(counts.items(), key=lambda kv: -kv[1])[:_ROW_LIMIT]
    parts = []
    for name, count in items:
        text = f"{name} x{count}"
        if with_mine_via:
            hint = mining_methods.format_methods(mining_methods.methods_for(name))
            if hint:
                text += f" (Mine via: {hint})"
        parts.append(text)
    text = ", ".join(parts)
    if len(counts) > _ROW_LIMIT:
        text += ", ..."
    return text


def format_materials_seen(run: space_mining.SpaceMiningRun) -> str:
    """Like format_counts(with_mine_via=True), but for
    prospected_commodities specifically: each entry also gets a "%
    Range" yield hint (min-avg-max Materials[].Proportion seen this run,
    space_mining.format_yield_range()) before the Mine via hint - not
    something format_counts's generic counts dict shape can express,
    since it needs the separate prospected_proportions samples."""
    counts = run.prospected_commodities
    if not counts:
        return "none yet"
    items = sorted(counts.items(), key=lambda kv: -kv[1])[:_ROW_LIMIT]
    parts = []
    for name, count in items:
        text = f"{name} x{count}"
        proportions = run.prospected_proportions.get(name)
        if proportions:
            text += f" [{space_mining.format_yield_range(proportions)}]"
        hint = mining_methods.format_methods(mining_methods.methods_for(name))
        if hint:
            text += f" (Mine via: {hint})"
        parts.append(text)
    text = ", ".join(parts)
    if len(counts) > _ROW_LIMIT:
        text += ", ..."
    return text


def format_rpm(run) -> str:
    """Renders mining_rate.current_rate() for a run with a
    `refined_timestamps` list (SpaceMiningRun or SurfaceMiningRun) as
    e.g. "12/min" - always a multiple of 60/mining_rate.RPM_WINDOW_SECONDS,
    since the window is fixed-width rather than a smoothed average."""
    return f"{mining_rate.current_rate(run.refined_timestamps):.0f}/min"


def format_ship_cargo(cargo: int) -> str:
    """"Ship cargo: 18/64 (46 free)" when the ship's CargoCapacity is
    known (from a `Loadout` event - see mining_space.py), else just the
    bare count."""
    capacity = space_mining.space_mining_repository.cargo_capacity()
    if not capacity:
        return f"Ship cargo: {cargo}"
    return f"Ship cargo: {cargo}/{capacity} ({max(capacity - cargo, 0)} free)"


def format_srv_cargo(cargo: int) -> str:
    """"SRV cargo: 40/72 (32 free)" - the Rhino's capacity is a fixed
    constant (mining_surface.RHINO_CARGO_CAPACITY), unlike the ship's,
    so this is always known once a run exists."""
    free = max(surface_mining.RHINO_CARGO_CAPACITY - cargo, 0)
    return f"SRV cargo: {cargo}/{surface_mining.RHINO_CARGO_CAPACITY} ({free} free)"


def format_hotspot(hotspot: hotspots.Hotspot) -> str:
    text = hotspot.material
    if hotspot.rigs is not None:
        text += f" ({hotspot.rigs}R)"
    if hotspot.signal_number is not None:
        text += f" [Signal {hotspot.signal_number}]"
    if hotspot.has_position():
        text += f" @ {hotspot.latitude:.2f}, {hotspot.longitude:.2f}"
    # Rigs and Amount together are what mining_deposit.describe() needs -
    # a hotspot with only one of the two (or neither) shows no estimate
    # rather than a misleading partial one.
    estimate = mining_deposit.describe(hotspot.rigs, hotspot.amount, hotspot.density, hotspot.mined_tons)
    if estimate:
        text += f" [{estimate}]"
    if hotspot.notes:
        text += f" ({hotspot.notes})"
    return text


def format_hotspots(matches: List[hotspots.Hotspot]) -> str:
    items = matches[:_ROW_LIMIT]
    text = ", ".join(format_hotspot(h) for h in items)
    if len(matches) > _ROW_LIMIT:
        text += ", ..."
    return text


def add_line(content: tk.Frame, row: int, wrap: int, text: str, fg: Optional[str] = None) -> None:
    # fg only passed through when the caller wants a fixed color (e.g.
    # the ring-caution warning below) - a widget that sets its own fg at
    # creation, before theme.update() ever sees it, keeps that color
    # permanently (EDMC's theme system only auto-colors a widget's
    # foreground if it didn't already have one at first registration),
    # which is exactly what a warning line wants.
    kwargs = {"fg": fg} if fg else {}
    tk.Label(content, text=text, anchor=tk.W, justify=tk.LEFT,
             wraplength=wrap, **kwargs).grid(row=row, column=0, sticky="w", padx=6, pady=2)


def render_ring_caution(content: tk.Frame, wrap: int, row: int, enabled: bool) -> int:
    """Passive counterpart to the "Check Ring Reserve Level..." button -
    shows the automatic lookup's result (see mining_panel.py's ring-
    reserve auto-lookup) for whichever ring the commander is currently
    at, if any. Silently renders nothing while unknown (no ring tracked
    yet, EDSM has no data for it, or the lookup hasn't completed) rather
    than showing stale/wrong data - same principle as the surface
    waypoint overlay's "show nothing until known" rule."""
    if not enabled:
        return row
    caution = space_mining.space_mining_repository.ring_caution()
    if caution is None:
        return row
    reserve_text = caution.reserve_level or "Unknown"
    text = f"Ring: {caution.ring_name} ({caution.ring_type}) - Reserve: {reserve_text}"
    if not caution.is_metallic:
        text += " - not Metallic: premium laser-mined yields are typically best on Metallic rings"
    add_line(content, row, wrap, text, fg=None if caution.is_metallic else _WARNING_COLOR)
    return row + 1


def set_button_row(button: tk.Button, row: Optional[int]) -> None:
    """Grids `button` at `row`, or hides it if row is None - but only
    touches the widget's grid mapping when the target state actually
    differs from its current one (compares against button.grid_info(),
    which is {} while hidden), so a periodic redraw that doesn't change
    anything doesn't unmap/remap the native widget (which flickers
    visibly on Windows even when the colors come out the same)."""
    info = button.grid_info()
    if row is None:
        if info:
            button.grid_remove()
        return
    if info.get("row") == row:
        return
    button.grid(row=row, column=0, sticky="w", padx=6, pady=(2, 6))


def place_gated_button(button: tk.Button, enabled: bool, row: int) -> None:
    """Grids a persistent, opt-in-gated button at the given row - never
    creates a new Button (that's what caused the flicker this replaced).
    Goes through set_button_row so a periodic redraw that doesn't change
    anything doesn't re-touch the widget's grid mapping either."""
    set_button_row(button, row if enabled else None)


def render_space_mining(content: tk.Frame, wrap: int, buttons: PanelButtons, settings: PanelSettings) -> None:
    repo = space_mining.space_mining_repository
    run = repo.current_run()
    row = 0

    if run is None:
        add_line(content, row, wrap, "No commander detected yet.")
        row += 1
        set_button_row(buttons.hotspot_finder, None)
        # The Mining Book needs nothing from a run (saved hotspots aren't
        # per-commander), so it's offered on both pages - Mining opens on the
        # Space Mining page, which is where people look first.
        set_button_row(buttons.ledger, row)
        row += 1
        # Find Best Price / Check Ring Reserve Level stay available even
        # pre-commander-detection - both are on-demand lookups that don't
        # need an active run, unlike the hotspot finder (which searches
        # relative to the reference system tracked from journal events).
        place_gated_button(buttons.price_finder, settings.spansh_price_finder_enabled, row)
        row += 1
        place_gated_button(buttons.reserve_lookup, settings.edsm_reserve_lookup_enabled, row)
        return

    if not run.has_data():
        add_line(content, row, wrap,
                "No active mining run. Undock to start tracking a new run.")
        row += 1
        row = render_ring_caution(content, wrap, row, settings.edsm_reserve_lookup_enabled)
        set_button_row(buttons.ledger, row)
        row += 1
        place_gated_button(buttons.hotspot_finder, settings.spansh_hotspot_finder_enabled, row)
        row += 1
        place_gated_button(buttons.price_finder, settings.spansh_price_finder_enabled, row)
        row += 1
        place_gated_button(buttons.reserve_lookup, settings.edsm_reserve_lookup_enabled, row)
        return

    if run.is_paused:
        add_line(content, row, wrap, "Paused (in supercruise)")
        row += 1
    row = render_ring_caution(content, wrap, row, settings.edsm_reserve_lookup_enabled)
    if settings.display_cargo_bar:
        add_line(content, row, wrap, format_ship_cargo(run.cargo))
        row += 1
    if settings.display_prospector_hints:
        grades = ", ".join(f"{grade} x{count}" for grade, count in sorted(
            run.content_counts.items(), key=lambda kv: -kv[1]))
        suffix = f" ({grades})" if grades else ""
        if run.duplicate_prospected:
            suffix += f" [{run.duplicate_prospected} duplicate(s) ignored]"
        add_line(content, row, wrap, f"Asteroids prospected: {run.prospected_count}{suffix}")
        row += 1
        if run.prospected_commodities:
            add_line(content, row, wrap, f"Materials seen: {format_materials_seen(run)}")
            row += 1
        if run.asteroids_cracked:
            add_line(content, row, wrap, f"Asteroids cracked (core mining): {run.asteroids_cracked}")
            row += 1
        launched_total = sum(run.limpets_launched.values())
        onboard = max(run.limpets_bought - launched_total, 0)
        onboard_suffix = f" (~{onboard} on board)" if run.limpets_bought else ""
        add_line(content, row, wrap,
                f"Limpets launched: {format_counts(run.limpets_launched)}{onboard_suffix}")
        row += 1
    if settings.display_session_totals:
        add_line(content, row, wrap,
                f"Refined: {format_counts(run.refined, with_mine_via=settings.display_prospector_hints)}")
        row += 1
        add_line(content, row, wrap, f"Refining rate: {format_rpm(run)}")
        row += 1

    set_button_row(buttons.ledger, row)
    row += 1
    place_gated_button(buttons.hotspot_finder, settings.spansh_hotspot_finder_enabled, row)
    row += 1
    place_gated_button(buttons.price_finder, settings.spansh_price_finder_enabled, row)
    row += 1
    place_gated_button(buttons.reserve_lookup, settings.edsm_reserve_lookup_enabled, row)


def render_surface_mining(content: tk.Frame, wrap: int, buttons: PanelButtons, settings: PanelSettings) -> None:
    repo = surface_mining.surface_mining_repository
    run = repo.current_run()
    row = 0

    if run is None:
        add_line(content, row, wrap, "No commander detected yet.")
        row += 1
        set_button_row(buttons.save_hotspot, None)
        # The Mining Book / Import/Export Hotspots stay available
        # even pre-commander-detection: mining_hotspots.py's list isn't
        # per-commander, so neither needs anything from `run`.
        set_button_row(buttons.ledger, row)
        row += 1
        place_gated_button(buttons.price_finder, settings.spansh_price_finder_enabled, row)
        row += 1
        set_button_row(buttons.hotspot_import_export, row)
        return

    is_active = repo.is_active
    if is_active or run.has_data():
        add_line(content, row, wrap,
                "Rhino deployed" if is_active else "Rhino stowed (last deployment)")
        row += 1
        if settings.display_cargo_bar:
            add_line(content, row, wrap, format_srv_cargo(run.cargo))
            row += 1
            ship_run = space_mining.space_mining_repository.current_run()
            if ship_run is not None:
                add_line(content, row, wrap, format_ship_cargo(ship_run.cargo))
                row += 1
        if settings.display_session_totals:
            add_line(content, row, wrap, f"Refined: {format_counts(run.refined)}")
            row += 1
            add_line(content, row, wrap, f"Refining rate: {format_rpm(run)}")
            row += 1
            add_line(content, row, wrap,
                    f"Transferred to ship: {format_counts(run.transferred_to_ship)}")
            row += 1
            add_line(content, row, wrap,
                    f"Raw materials: {format_counts(run.raw_materials)}")
            row += 1
    else:
        add_line(content, row, wrap,
                "No active Rhino deployment. Launch the Rhino to start tracking a new run.")
        row += 1

    if settings.display_prospector_hints:
        signal = repo.latest_signal()
        if signal is not None:
            add_line(content, row, wrap,
                    f"Last DSS scan: {signal.count} Planetary Mining Location(s) on {signal.body_name}")
            row += 1

    current_system, current_body = repo.current_system, repo.current_body
    matches: list = []
    if current_body:
        matches = hotspots.hotspot_repository.for_body(current_system, current_body)
        if matches:
            add_line(content, row, wrap, f"Known hotspots here: {format_hotspots(matches)}")
            row += 1
        set_button_row(buttons.save_hotspot, row)
        row += 1
    else:
        set_button_row(buttons.save_hotspot, None)

    if settings.display_coverage_minimap and current_body:
        row = render_coverage_minimap(content, row, current_system, current_body, matches)

    set_button_row(buttons.ledger, row)
    row += 1
    place_gated_button(buttons.price_finder, settings.spansh_price_finder_enabled, row)
    row += 1
    set_button_row(buttons.hotspot_import_export, row)


SHIP_MINIMAP_MAX_ALTITUDE_M = 2000.0
"""With no Rhino deployed the minimap shows only under this altitude (the
2 km radar range), so a ship cruising high over a body doesn't keep a map
up. Altitude unknown counts as too high. In the Rhino it always shows."""


def render_coverage_minimap(content: tk.Frame, row: int, system: Optional[str], body: str,
                            known_hotspots: list) -> int:
    """The current body's coverage minimap (mining_coverage.py/
    mining_coverage_render.py), as a fixed-size in-panel image - see
    mining_coverage_render.py's module docstring for the scope
    deliberately left out of this first pass. Renders nothing (returns
    `row` unchanged) rather than a blank/stale image when there's
    nothing recorded yet for this body and no live position either, same
    "say nothing until known" principle used throughout this project."""
    body_coverage = coverage.coverage_repository.for_body(system, body)
    radius = surface_mining.surface_mining_repository.radius_for_current_body()
    position = live_position.current_position()
    if (not surface_mining.surface_mining_repository.is_active and position is not None
            and (position.altitude is None or position.altitude > SHIP_MINIMAP_MAX_ALTITUDE_M)):
        return row  # in the ship, the map only appears inside scanner range of the ground
    current_point = (coverage.CoveragePoint(position.latitude, position.longitude)
                     if position is not None else None)
    image = coverage_render.render(body_coverage, radius, current_point, known_hotspots)
    if image is None:
        return row

    photo = tk.PhotoImage(data=coverage_render.to_photo_data(image))
    label = tk.Label(content, image=photo)
    label.image = photo  # keep a reference - PhotoImage has no other owner
    label.grid(row=row, column=0, pady=(2, 4))
    return row + 1


def open_add_hotspot_dialog(parent: tk.Misc) -> None:
    from . import mining_hotspot_dialog as hotspot_dialog

    repo = surface_mining.surface_mining_repository
    # Prefer the live on-foot/on-vehicle position (mining_live_position.py,
    # from Status.json) over the ship's last Touchdown spot - a commander
    # hitting this button has usually driven the Rhino away from the
    # touchdown point to the actual deposit by then, so Touchdown would
    # pre-fill a stale location. Falls back to Touchdown only when live
    # position isn't available (FlagsHasLatLong not currently set, or an
    # older game/EDMC version that doesn't populate it).
    position = live_position.current_position()
    if position is not None:
        prefill_latitude, prefill_longitude = position.latitude, position.longitude
    else:
        touchdown = repo.last_touchdown
        prefill_latitude = touchdown.latitude if touchdown else None
        prefill_longitude = touchdown.longitude if touchdown else None
    hotspot_dialog.open_hotspot_dialog(
        parent,
        on_save=lambda hotspot: hotspots.hotspot_repository.add_or_merge(
            dataclasses.replace(hotspot, ground=mining_ground.ground_in_survey(
                system_body_survey, hotspot.system, hotspot.body)),
            repo.radius_for_current_body()),
        prefill_system=repo.current_system or "",
        prefill_body=repo.current_body or "",
        prefill_latitude=prefill_latitude,
        prefill_longitude=prefill_longitude,
    )
