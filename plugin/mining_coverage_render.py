"""
Draws mining_coverage.py's recorded drive history as a small top-down
map: PIL only, no tkinter (mining_render.py/mining_panel.py turn the
result into a tk.PhotoImage for the Surface Mining page - see
to_photo_data() below, which follows screenshot_convert.py's own
thumbnail_photo_data() pattern exactly, including capping *both*
dimensions per the main-window-sizing rule (docs/TECHNICAL.md section 5), even
though MAP_SIZE_PX already makes the canvas an exact fixed square by
construction - the extra thumbnail() call is a deliberate belt-and-
suspenders match to that convention, not dead code).

Flat-earth projection via mining_bearing's own haversine distance/
bearing from the body's recorded center point: accurate enough at the
VIEW_M scale this map shows (a few km), same reasoning
mining_bearing.py itself already uses for the waypoint arrow.

Deliberately small in scope: no zoom levels, no lines joining hotspots,
no clustering, no hotkeys to move the map's center. It paints driven
ground, shows recorded hotspots and the current position, north up, at a
fixed size.
"""
from __future__ import annotations

import io
import math
from typing import Optional

from PIL import Image, ImageDraw

from . import mining_bearing as bearing
from . import mining_coverage as coverage
from . import mining_hotspots as hotspots

MAP_SIZE_PX = 220
"""Both dimensions - a fixed square, never derived from source data, so
this can never be the widget that widens EDMC's main window (see
docs/TECHNICAL.md section 5)."""

VIEW_M = 6000.0
"""Half-width of what the map shows around its center - 12 km across
total."""

GRID_M = 1000.0

_BG_COLOR = (40, 40, 40)
_GRID_COLOR = (64, 64, 64)
_COVERAGE_COLOR = (46, 92, 58)
_HOTSPOT_COLOR = (238, 232, 190)
_DEPLETED_COLOR = (150, 150, 150)
_POSITION_COLOR = (70, 170, 255)
_POSITION_OUTLINE = (255, 255, 255)
_POSITION_RADIUS_PX = 4
# Colours chosen to stay distinguishable without telling red from green
# (deliberately): a live hotspot is a pale
# filled dot, a depleted one a hollow grey ring - shape, not hue, carries
# the state - and the position marker is blue with a white outline (it
# used to be red on green coverage).


def _project(center: coverage.CoveragePoint, latitude: float, longitude: float,
             radius_m: float, scale_px_per_m: float) -> tuple[float, float]:
    """A lat/lon point -> (x, y) pixel offset from the map's center,
    north up (smaller y = further north)."""
    distance = bearing.distance_m(center.latitude, center.longitude, latitude, longitude, radius_m)
    initial_bearing = math.radians(bearing.initial_bearing_deg(
        center.latitude, center.longitude, latitude, longitude))
    east_m = distance * math.sin(initial_bearing)
    north_m = distance * math.cos(initial_bearing)
    half = MAP_SIZE_PX / 2
    return half + east_m * scale_px_per_m, half - north_m * scale_px_per_m


def render(body_coverage: Optional[coverage.BodyCoverage], radius_m: Optional[float],
          current: Optional[coverage.CoveragePoint],
          known_hotspots: list[hotspots.Hotspot]) -> Optional[Image.Image]:
    """None when there's nothing to draw yet - no coverage recorded for
    this body and no live position either - so the caller can show
    nothing rather than a blank grey square."""
    center = body_coverage.center if body_coverage else None
    if center is None:
        center = current
    if center is None or not radius_m:
        return None

    scale = MAP_SIZE_PX / (2 * VIEW_M)
    image = Image.new("RGB", (MAP_SIZE_PX, MAP_SIZE_PX), _BG_COLOR)
    draw = ImageDraw.Draw(image)

    # Grid, pinned to the map's center so it reads as "north up" rather
    # than tied to any single recorded point. Walks outward from the
    # center in both directions at once so it stays symmetric regardless
    # of MAP_SIZE_PX's parity.
    step_px = GRID_M * scale
    half_px = MAP_SIZE_PX / 2
    if step_px >= 4:  # a grid finer than a few px just reads as noise
        offset = 0.0
        while offset <= half_px:
            for coordinate in {half_px + offset, half_px - offset}:
                draw.line([(coordinate, 0), (coordinate, MAP_SIZE_PX)], fill=_GRID_COLOR)
                draw.line([(0, coordinate), (MAP_SIZE_PX, coordinate)], fill=_GRID_COLOR)
            offset += step_px

    # Painted ground: a disc per recorded point.
    scan_radius_px = coverage.SCAN_RADIUS_M * scale
    for point in (body_coverage.points if body_coverage else ()):
        px, py = _project(center, point.latitude, point.longitude, radius_m, scale)
        draw.ellipse([px - scan_radius_px, py - scan_radius_px,
                     px + scan_radius_px, py + scan_radius_px], fill=_COVERAGE_COLOR)

    # Recorded hotspots on this body, if within view.
    for hotspot in known_hotspots:
        if not hotspot.has_position():
            continue
        px, py = _project(center, hotspot.latitude, hotspot.longitude, radius_m, scale)
        if 0 <= px <= MAP_SIZE_PX and 0 <= py <= MAP_SIZE_PX:
            r = 3
            box = [px - r, py - r, px + r, py + r]
            if hotspot.amount == "Depleted":
                draw.ellipse(box, outline=_DEPLETED_COLOR, width=1)
            else:
                draw.ellipse(box, fill=_HOTSPOT_COLOR)

    # The Rhino's current position, drawn last so it's never hidden
    # under a coverage disc.
    if current is not None:
        px, py = _project(center, current.latitude, current.longitude, radius_m, scale)
        r = _POSITION_RADIUS_PX
        draw.ellipse([px - r, py - r, px + r, py + r], fill=_POSITION_COLOR,
                     outline=_POSITION_OUTLINE)

    return image


def to_photo_data(image: Image.Image) -> bytes:
    """GIF bytes suitable for tk.PhotoImage(data=...) - see this
    module's docstring for why the thumbnail() call stays even though
    `image` is already exactly MAP_SIZE_PX square."""
    copy = image.copy()
    copy.thumbnail((MAP_SIZE_PX, MAP_SIZE_PX), Image.Resampling.LANCZOS)
    buffer = io.BytesIO()
    copy.convert("RGB").save(buffer, format="GIF")
    return buffer.getvalue()
