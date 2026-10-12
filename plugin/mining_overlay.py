"""
Mining mode's EDMCModernOverlay HUD push - two independent
pieces:

- `push_stats_overlay(page)` - the same live numbers the panel itself is
  showing (cargo, mining rate, limpets remaining), gated by the "Enable
  HUD Overlay" setting. A background rect behind several lines of
  narrower text.
- `push_waypoint_overlay()` - a directional arrow (vector line + text)
  pointing at the nearest recorded hotspot on the current body, gated
  by "Enable Surface Waypoint Overlay".

Both panels now register an EDMCModernOverlay Plugin Group
(`GROUP_NAME`/`GROUP_PREFIX` below, wired up in load.py), matching
Landing/Inventory: without a registered group, a panel's background can
render invisible under EDMCModernOverlay (see overlay.py's docstring).

Rewired onto the shared `overlay.OverlayClient` - state is read
synchronously on the caller's thread (cheap attribute reads off the
mining repositories), then the actual socket sends are dispatched on a
short-lived daemon thread wrapped in try/except OSError, matching every
other overlay-drawing feature in this project.
"""
import logging
import os
import threading
from typing import List, Optional

from config import appname

from . import mining_bearing as bearing
from . import mining_hotspots as hotspots
from . import mining_live_position as live_position
from . import mining_pages
from . import mining_render as render
from . import mining_space as space_mining
from . import mining_surface as surface_mining
from . import overlay, overlay_appearance, overlay_placement
from .overlay_style import LEGACY, Look

plugin_name = os.path.basename(os.path.dirname(__file__))
logger = logging.getLogger(f"{appname}.{plugin_name}")

_OVERLAY_X = 20
_OVERLAY_Y_START = 100
_OVERLAY_TTL_S = 3
"""The HUD overlay text's anchor in the overlay's own coordinate space (a separate top-level canvas the companion app
draws, not EDMC's plugin_app window); where it ends up on screen is set by Overlay Placement. The line spacing and glyph
widths come from the overlay look (overlay_style.py). ttl a little over the once-a-second periodic re-render that
resends it (see mining_render.py), so each line gets replaced before it would expire on its own - a stale value only
lingers a couple of seconds past the last successful send (run ended, overlay app closed, etc.)."""

"""Colors come from the overlay's look (overlay_style.py): the panel's border and fill, and the title color for the text, which
at the default scheme is the Elite-orange-on-black HUD styling this display always had. Every measure below is the base one at
the legacy look; the text size, padding and line spacing chosen on the Appearance tab are added to it (`_stat_pitch`,
`_panel_rect`, `_waypoint_geometry`), so a larger size makes a larger panel and the text still fits inside the border."""

_OVERLAY_PANEL_PAD_X = 10
_OVERLAY_PANEL_PAD_Y = 8

_WAYPOINT_OVERLAY_Y = 250
"""Below _OVERLAY_Y_START's stats lines (100 + up to 3*22 = 166), clear
of them with headroom to spare - a separate screen area for the
directional line so the two overlay features don't overlap when both
are enabled."""

_WAYPOINT_ARROW_CENTER_X = _OVERLAY_X + 10
_WAYPOINT_ARROW_SIZE = 18
"""Below the text line with enough clearance for the arrow's own size -
placement for bearing.arrow_vector_points()'s rotated polyline, drawn
alongside (not instead of) the 8-point glyph already in the text line,
since the glyph degrades gracefully on an overlay app that ignores
"vect" shapes and the vector arrow doesn't."""

_WAYPOINT_ARROW_GAP = 14
"""Between the waypoint text line and the arrow's center (the legacy layout has the arrow center 40 below the text's top, which is
the 26-high line plus this 14)."""

_BG_ID = "wntb_mining_stats_bg"
_WAYPOINT_BG_ID = "wntb_mining_waypoint_bg"
_WAYPOINT_ARROW_ID = "wntb_mining_waypoint_arrow"
_WAYPOINT_TEXT_ID = "wntb_mining_waypoint"

# This mode's own EDMCModernOverlay Plugin Group - same treatment as
# landing.py's GROUP_NAME/GROUP_PREFIX (see load.py's registration call
# and this module's own docstring for why).
GROUP_NAME = "wntb_mining"
GROUP_PREFIX = "wntb_mining_"

_client: overlay.OverlayClient = overlay.OverlayClient()


def set_overlay_client(client: overlay.OverlayClient) -> None:
    global _client
    _client = client


def _stat_pitch(look: Look = LEGACY) -> int:
    """Distance between the stats lines: the normal line height plus two (22 at the legacy look)."""
    return look.line_px("normal") + 2


def _panel_rect(x: int, y: int, lines: List[str], look: Look = LEGACY, base: str = "normal", extra_h: int = 0,
                line_height: int = 0) -> tuple:
    """(left, top, width, height) of the backing panel for `lines` drawn at size `base` with their text origin at (x, y)."""
    pad_x, pad_y = look.pad_x(_OVERLAY_PANEL_PAD_X), look.pad_y(_OVERLAY_PANEL_PAD_Y)
    width = look.text_width(max(lines, key=len), base) + 2 * pad_x
    height = len(lines) * (line_height or _stat_pitch(look)) + 2 * pad_y + extra_h
    return x - pad_x, y - pad_y, width, height


def _waypoint_geometry(look: Look = LEGACY) -> tuple:
    """(line height, arrow center y, extra panel height) for the waypoint line at the look's size: the arrow sits a fixed gap below
    the (large) text line, and the panel is taller than the line by enough to hold it."""
    line = look.line_px("large")
    center_y = _WAYPOINT_OVERLAY_Y + line + _WAYPOINT_ARROW_GAP
    extra_h = max((center_y + _WAYPOINT_ARROW_SIZE) - (_WAYPOINT_OVERLAY_Y + line), 0)
    return line, center_y, extra_h


def _send_overlay_panel(client, msg_id: str, x: int, y: int, lines: List[str], look: Look = LEGACY, base: str = "normal",
                        extra_h: int = 0, line_height: int = 0) -> None:
    """Draws the backing rect for a stack of `lines` about to be sent as text at `x`/`y` (the same origin the
    caller passes to its first text send) - see this module's colors note for why this exists. `extra_h` grows the panel past the
    text lines' own height for a caller drawing something else below
    them (e.g. the waypoint arrow). No-op if `lines` is empty - an empty
    panel would just be a stray box with nothing in it."""
    if not lines:
        return
    left, top, width, height = _panel_rect(x, y, lines, look, base, extra_h, line_height)
    client.send_shape(msg_id, "rect", look.color("border"), look.color("fill"), left, top, width, height, ttl=_OVERLAY_TTL_S)


def _in_supercruise() -> bool:
    """Whether the ship is currently in supercruise -
    `SpaceMiningRun.is_paused`, set on `SupercruiseEntry`/
    `SupercruiseExit` regardless of which page is active or whether the
    Rhino's even involved, so it doubles as a general "ship is currently
    travelling, not sitting at a body" signal. Used to hide the Surface
    Mining HUD overlay - recovering the Rhino and jumping to supercruise
    would otherwise leave stale Rhino stats/waypoint arrow on screen,
    since the panel deliberately keeps showing them ("Rhino stowed
    (last deployment)") until the next LaunchSRV."""
    run = space_mining.space_mining_repository.current_run()
    return run is not None and run.is_paused


def push_stats_overlay(page: str, *, display_cargo_bar: bool, display_session_totals: bool,
                       display_prospector_hints: bool) -> None:
    """Sends the same live numbers the panel itself is already showing,
    gated by the same "Display ..." toggles as the in-panel lines so
    turning one off hides it in both places consistently. Only called
    when the "Enable HUD Overlay" setting is on."""
    lines: List[str] = []

    if page == mining_pages.SPACE_MINING:
        run = space_mining.space_mining_repository.current_run()
        if run is not None and run.has_data():
            if display_cargo_bar:
                lines.append(render.format_ship_cargo(run.cargo))
            if display_session_totals:
                lines.append(f"Mining rate: {render.format_rpm(run)}")
            if display_prospector_hints:
                launched_total = sum(run.limpets_launched.values())
                onboard = max(run.limpets_bought - launched_total, 0)
                if run.limpets_bought:
                    lines.append(f"Limpets remaining: ~{onboard}")
    elif page == mining_pages.SURFACE_MINING:
        repo = surface_mining.surface_mining_repository
        run = repo.current_run()
        if run is not None and (repo.is_active or run.has_data()) and not _in_supercruise():
            if display_cargo_bar:
                lines.append(render.format_srv_cargo(run.cargo))
                ship_run = space_mining.space_mining_repository.current_run()
                if ship_run is not None:
                    lines.append(render.format_ship_cargo(ship_run.cargo))
            if display_session_totals:
                lines.append(f"Mining rate: {render.format_rpm(run)}")

    def worker() -> None:
        try:
            # Drawn at the fixed origin above; the Overlay Placement setting moves it to where the commander put it.
            look = overlay_appearance.current_look()
            placed = (overlay_placement.client_for("mining_stats", _client, _panel_rect(_OVERLAY_X, _OVERLAY_Y_START, lines, look))
                      if lines else _client)
            _send_overlay_panel(placed, _BG_ID, _OVERLAY_X, _OVERLAY_Y_START, lines, look)
            for index, text in enumerate(lines):
                placed.send_message(f"wntb_mining_stat_{index}", text, look.color("title"),
                                    _OVERLAY_X, _OVERLAY_Y_START + index * _stat_pitch(look),
                                    ttl=_OVERLAY_TTL_S, size=look.size("normal"))
        except OSError:
            logger.debug("Could not reach the overlay for Mining stats", exc_info=True)

    threading.Thread(target=worker, name="WNTB-mining-overlay", daemon=True).start()


def push_waypoint_overlay() -> None:
    """Points a HUD-overlay arrow at the nearest recorded hotspot on the
    current body, with distance and compass direction. Needs three
    things to line up, any of which can be legitimately missing: a live
    position (mining_live_position.py, from Status.json - only
    available on foot or in a vehicle on a landable surface), at least
    one recorded hotspot with a pinned lat/lon on the current body
    (mining_hotspots.py - a hotspot without one, per its own docstring,
    only means "something's here" with no exact spot yet), and that
    body's radius (preferably mining_live_position.py's Status.json-
    reported `planet_radius`, falling back to mining_surface.py's
    `Scan`-derived one for a body reached without ever being scanned).
    Silently sends nothing if any is missing - same "just don't show
    it" gating as the rest of the panel's conditional lines."""
    position = live_position.current_position()
    if position is None:
        return
    repo = surface_mining.surface_mining_repository
    radius = position.planet_radius or repo.radius_for_current_body()
    if radius is None:
        return
    matches = [h for h in hotspots.hotspot_repository.for_body(repo.current_system, repo.current_body)
              if h.has_position()]
    if not matches:
        return

    nearest = min(matches, key=lambda h: bearing.distance_m(
        position.latitude, position.longitude, h.latitude, h.longitude, radius))
    distance = bearing.distance_m(position.latitude, position.longitude,
                                  nearest.latitude, nearest.longitude, radius)
    target_bearing = bearing.initial_bearing_deg(position.latitude, position.longitude,
                                                 nearest.latitude, nearest.longitude)
    compass = bearing.compass_point(target_bearing)
    distance_str = bearing.format_distance_m(distance)

    points: Optional[List[dict]] = None
    if position.heading is not None:
        relative_bearing = (target_bearing - position.heading) % 360
        glyph = bearing.arrow_glyph(relative_bearing)
        text = f"{glyph} {nearest.material} - {distance_str} {compass}"
        points = bearing.arrow_vector_points(
            _WAYPOINT_ARROW_CENTER_X, _waypoint_geometry(overlay_appearance.current_look())[1],
            _WAYPOINT_ARROW_SIZE, relative_bearing)
    else:
        # No heading yet (rare - a Status.json update can have valid
        # lat/lon a beat before heading catches up) - show the compass
        # direction without a you-relative arrow rather than guessing.
        text = f"{nearest.material} - {distance_str} {compass}"

    def worker() -> None:
        try:
            look = overlay_appearance.current_look()
            line, _center_y, extra_h = _waypoint_geometry(look)
            panel = dict(look=look, base="large", extra_h=extra_h, line_height=line)
            placed = overlay_placement.client_for(
                "mining_waypoint", _client, _panel_rect(_OVERLAY_X, _WAYPOINT_OVERLAY_Y, [text], **panel))
            _send_overlay_panel(placed, _WAYPOINT_BG_ID, _OVERLAY_X, _WAYPOINT_OVERLAY_Y, [text], **panel)
            placed.send_message(_WAYPOINT_TEXT_ID, text, look.color("title"), _OVERLAY_X,
                                _WAYPOINT_OVERLAY_Y, ttl=_OVERLAY_TTL_S, size=look.size("large"))
            if points is not None:
                placed.send_vector(_WAYPOINT_ARROW_ID, points, look.color("border"), ttl=_OVERLAY_TTL_S)
        except OSError:
            logger.debug("Could not reach the overlay for Mining waypoint", exc_info=True)

    threading.Thread(target=worker, name="WNTB-mining-waypoint-overlay", daemon=True).start()
