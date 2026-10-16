"""The Bio radar: a small top-down plot of where you are standing against the places you have taken samples, drawn on the overlay. Pure: no Tk, no EDMC.

Each sample point carries a circle as wide as the genus's minimum distance between samples (the Colonial Range: 100 m to 1000 m depending on the genus).
The next sample of that genus must be taken outside every one of its circles, so a circle is red while you are inside it and green once you are clear.
The plot is centered on you and turned so that straight ahead is up (it uses the heading Status.json reports), the way SrvSurvey's plot and the in-game
radar read. The ship and the SRV are marked where they touched down or were left, with their distance and bearing beneath. The scale adapts so every
circle fits inside the panel, and the overlay cannot clip a shape, so a circle that would not fit is left out rather than drawn across the screen.

`radar_plan` returns what to draw as plain tuples; `RadarLayout.render` sends it. The geometry (`offset_m`) is the flat-earth approximation that is accurate
over the few hundred meters a sampling walk covers.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Callable, List, Optional, Tuple

from . import organic_scan
from .overlay_card import ACCENT_W
from .overlay_style import CARD_PAD_X, CARD_PAD_Y, LEGACY, Look, with_alpha

SIZE = 260                  # the plot's width and height in pixels (the Default radar size; the Radar size setting makes it larger)
SIZE_RANGE = (200, 800)     # what the Radar size setting may be: 260 is the default, 520 twice that
FILL_RANGE = (0, 100)       # the circle fill, percent opaque while you are inside a circle
FILL_DEFAULT = 70
LINE_RANGE = (1, 6)         # the circle outline thickness in pixels
LINE_DEFAULT = 2     # the Radar size setting: a larger plot draws the circles larger, as wide as the genus needs
MIN_EXTENT_M = 150.0        # the plot never shows less than this radius
MAX_EXTENT_M = 3000.0       # nor more than this
MARGIN = 1.12               # room around the outermost circle
ARROW_SIZE = 6.0             # half the width of a little pointer
BOTTOM_LINES = 3            # lines under the plot: the first two samples, then which plant is being tracked and how far


def offset_m(here: Tuple[float, float], there: Tuple[float, float], radius_m: float, heading: Optional[float]) -> Tuple[float, float]:
    """(right, ahead) in meters from `here` to `there` on a body of `radius_m`, for a commander facing `heading` degrees (north when None)."""
    lat1, lon1 = here
    north = math.radians(there[0] - lat1) * radius_m
    east = math.radians(there[1] - lon1) * radius_m * math.cos(math.radians(lat1))
    turn = math.radians(heading or 0.0)
    return east * math.cos(turn) - north * math.sin(turn), east * math.sin(turn) + north * math.cos(turn)


def distance_m(here: Tuple[float, float], there: Tuple[float, float], radius_m: float) -> float:
    return organic_scan.haversine_distance_m(here[0], here[1], there[0], there[1], radius_m)


def distance_text(meters: float) -> str:
    return f"{meters / 1000:.1f} km" if meters >= 1000 else f"{meters:.0f} m"


@dataclass(frozen=True)
class Circle:
    x: float                # pixels from the plot's center, right
    y: float                # pixels from the plot's center, up
    radius: float           # pixels
    inside: bool            # you are inside it: too close to take the next sample
    active: bool = True     # the circle of the genus being sampled; the others are drawn dimmer


def bearing_text(right: float, ahead: float) -> str:
    """Where a point is relative to the way you face: 'ahead', 'behind', or the angle to your right or left ('30° right')."""
    angle = math.degrees(math.atan2(right, ahead))
    size = abs(angle)
    if size < 8:
        return "ahead"
    if size > 172:
        return "behind"
    return f"{size:.0f}° {'right' if angle > 0 else 'left'}"


def genus_label(waypoint: organic_scan.Waypoint) -> str:
    """The genus of a plant ('Tussock'), from the data, else the first word of its name."""
    info = organic_scan.species_data.GENUS.get(waypoint.genus_key)
    return info.name if info else (waypoint.name.split(" ")[0] or waypoint.name)


@dataclass(frozen=True)
class Tracked:
    """The plant being followed for one genus: the latest one identified and not yet sampled, with where it is from here."""
    waypoint: organic_scan.Waypoint
    color: int           # which of the series colors it is drawn in, the same on the plot, under it and on Bio status
    distance: float      # meters
    right: float         # meters to the right of the way you face
    ahead: float         # meters ahead of you

    @property
    def name(self) -> str:
        return genus_label(self.waypoint)

    @property
    def error(self) -> float:
        """How far from the plant the marker may be, meters (it is where the commander was when the scanner named the plant)."""
        return self.waypoint.error_m

    @property
    def distance_label(self) -> str:
        """The distance, with a ~ when the marker is only near the plant (scanned from a vehicle) and not at it."""
        return ("" if self.waypoint.exact else "~") + distance_text(self.distance)

    @property
    def text(self) -> str:
        return f"{self.name} {self.distance_label}"


def tracked(view: Optional[organic_scan.BodyView]) -> Tuple[Tracked, ...]:
    """One tracked plant per genus (the most recently identified that has not been sampled), in the order the genera were found. Empty with no position or no plants."""
    if view is None or view.here is None or view.radius_m <= 0 or not view.waypoints:
        return ()
    latest: dict = {}
    for waypoint in view.waypoints:                       # oldest first, so a later one of the genus replaces an earlier
        latest[waypoint.genus_key] = waypoint
    order = [g.key for g in view.genera]
    keys = sorted(latest, key=lambda k: order.index(k) if k in order else len(order))
    found = []
    for index, key in enumerate(keys):
        waypoint = latest[key]
        right, ahead = offset_m(view.here, (waypoint.lat, waypoint.lon), view.radius_m, view.heading)
        found.append(Tracked(waypoint, index % 4, math.hypot(right, ahead), right, ahead))
    return tuple(found)


def track_lines(view: Optional[organic_scan.BodyView]) -> Tuple[str, ...]:
    """One line per tracked plant that leads you back to it: 'Tussock: 94 m, 60° right'. Empty when none is being tracked."""
    return tuple(f"{t.name}: {t.distance_label}, {bearing_text(t.right, t.ahead)}" for t in tracked(view))


@dataclass(frozen=True)
class Item:
    """One labeled distance under the plot, with the bearing of the thing it names (degrees clockwise from straight ahead) for the little pointer drawn
    before it, or None for no pointer."""
    text: str
    angle: Optional[float] = None
    role: str = "text"


def arrow_points(cx: float, cy: float, angle: float, size: float = 6.0) -> List[dict]:
    """The outline of a small arrowhead centered on (cx, cy) pointing `angle` degrees clockwise from up, as the overlay's polyline points (closed)."""
    shape = ((0.0, -size), (size * 0.75, size * 0.85), (0.0, size * 0.35), (-size * 0.75, size * 0.85), (0.0, -size))
    turn = math.radians(angle)
    sin, cos = math.sin(turn), math.cos(turn)
    return [{"x": round(cx + x * cos - y * sin, 1), "y": round(cy + x * sin + y * cos, 1)} for x, y in shape]


def _angle(right: float, ahead: float) -> float:
    return math.degrees(math.atan2(right, ahead))


@dataclass(frozen=True)
class Plan:
    circles: Tuple[Circle, ...] = ()
    markers: Tuple[Tuple[str, float, float], ...] = ()      # (label, x, y) for the ship and the SRV
    top: str = ""                                            # "Ship: 7 m   SRV: 7 m"
    bottom: str = ""                                         # "Scan one: 342 m   Scan two: 0 m"
    scale: str = ""                                          # what half the plot's width is, e.g. "300 m"
    visible: bool = False
    targets: Tuple[Tuple[str, float, float, int, float], ...] = ()  # (label, x, y, color, ring radius) of each plant being tracked that fits in the plot; the ring is as wide as the marker may be off
    pointers: Tuple[Tuple[float, float, int], ...] = ()      # a unit direction (x right, y up) and color to each tracked plant, drawn from the center
    track: Tuple[str, ...] = ()                              # one line per tracked plant that says which and how far
    rows: Tuple[Tuple[Item, ...], ...] = ()                  # what is drawn under the plot, a row at a time, each item with its little pointer
    north: Optional[float] = None                            # where north lies on the plot, in degrees clockwise from up (the plot is turned to your heading, so north moves as you turn)


def build_plan(view: Optional[organic_scan.BodyView], size: int = SIZE) -> Plan:
    """The plot for `view`, or an empty plan when there is nothing to plot (no position, or no samples and no ship or SRV)."""
    if view is None or view.here is None or view.radius_m <= 0:
        return Plan()
    here, radius = view.here, view.radius_m
    active = view.active_genus
    spots: List[Tuple[Tuple[float, float], float, bool, str]] = []           # (position, range m, active, genus key)
    for genus in view.genera:
        for position in genus.positions:
            spots.append((position, genus.min_distance_m, genus.key == (active.key if active else genus.key), genus.key))
    followed = tracked(view)
    if not spots and view.ship is None and view.srv is None and not followed:
        return Plan()
    reach = [distance_m(here, p, radius) + r for p, r, _a, _k in spots]
    reach += [distance_m(here, p, radius) for p in (view.ship, view.srv) if p is not None]
    reach += [t.distance for t in followed]
    extent = min(MAX_EXTENT_M, max(MIN_EXTENT_M, MARGIN * max(reach, default=0.0)))
    half = size / 2 - 10
    per_m = half / extent
    circles = []
    for position, range_m, is_active, _key in spots:
        right, ahead = offset_m(here, position, radius, view.heading)
        if math.hypot(right, ahead) + range_m > extent:
            continue
        circles.append(Circle(right * per_m, ahead * per_m, max(2.0, range_m * per_m), math.hypot(right, ahead) < range_m, is_active))
    markers = []
    parts = []
    vehicles: List[Item] = []
    for label, position in (("Ship", view.ship), ("SRV", view.srv)):
        if position is None:
            continue
        right, ahead = offset_m(here, position, radius, view.heading)
        parts.append(f"{label}: {distance_text(distance_m(here, position, radius))}")
        vehicles.append(Item(parts[-1], _angle(right, ahead), "info"))
        if math.hypot(right, ahead) <= extent:
            markers.append((label[0], right * per_m, ahead * per_m))
    bottom = ""
    scan_items: List[Item] = []
    if active is not None and active.positions:
        scans = []
        for name, p in list(zip(("1", "2", "3"), active.positions))[:2]:
            right, ahead = offset_m(here, p, radius, view.heading)
            scans.append(f"Scan {name}: {distance_text(distance_m(here, p, radius))}")
            scan_items.append(Item(scans[-1], _angle(right, ahead)))
        bottom = "   ".join(scans)
    targets = []
    pointers = []
    track_items: List[Tuple[Item, ...]] = []
    for t in followed:
        if t.distance <= extent:
            targets.append((t.name[:1], t.right * per_m, t.ahead * per_m, t.color, max(8.0, min(half, t.error * per_m))))
        if t.distance > 0:
            pointers.append((t.right / t.distance, t.ahead / t.distance, t.color))
        track_items.append((Item(t.text, _angle(t.right, t.ahead), f"series{t.color}"),))
    rows: List[Tuple[Item, ...]] = [tuple(vehicles)]
    if scan_items:
        rows.append(tuple(scan_items))
    rows.extend(track_items)
    return Plan(tuple(circles), tuple(markers), "   ".join(parts), bottom, distance_text(extent), True, tuple(targets), tuple(pointers), track_lines(view), tuple(rows),
                north=-(view.heading or 0.0))


class RadarLayout:
    """Draws a `Plan` in its own panel at a fixed origin. Shapes and texts use overlay ids under `prefix`; unused ones are cleared."""

    MAX_CIRCLES = 12
    MAX_ARROWS = 10
    MAX_TARGETS = 5

    def __init__(self, prefix: str, x: int, y: int, accent: str = "border", size_fn: Optional[Callable[[], int]] = None,
                 fill_fn: Optional[Callable[[], int]] = None, line_fn: Optional[Callable[[], int]] = None) -> None:
        self.prefix, self.x, self.y, self.accent = prefix, x, y, accent
        self._size_fn, self._fill_fn, self._line_fn = size_fn, fill_fn, line_fn
        self.panel_id = f"{prefix}panel"
        self._used_circles = 0
        self._used_texts = 0

    @property
    def size(self) -> int:
        """The plot's width and height in pixels now: the Radar size setting, or the default."""
        return int(self._size_fn()) if self._size_fn else SIZE

    @property
    def fill_alpha(self) -> int:
        """The alpha byte of a circle's fill while you are inside it, from the Circle fill setting (percent opaque)."""
        percent = int(self._fill_fn()) if self._fill_fn else FILL_DEFAULT
        return round(255 * max(FILL_RANGE[0], min(FILL_RANGE[1], percent)) / 100)

    @property
    def line_width(self) -> int:
        """The thickness of the circle outlines, pixels."""
        return max(LINE_RANGE[0], min(LINE_RANGE[1], int(self._line_fn()))) if self._line_fn else LINE_DEFAULT

    def block_rect(self, look: Look = LEGACY, plan: Optional[Plan] = None) -> Tuple[int, int, int, int]:
        """(left, top, width, height): the plot with a row above it and a row under it for each thing listed (the rows grow with the plants tracked)."""
        pad_x, pad_y = look.pad_x(CARD_PAD_X), look.pad_y(CARD_PAD_Y)
        line = look.line_px("normal")
        rows = (1 + BOTTOM_LINES) if plan is None or not plan.rows else max(2, len(plan.rows))
        return self.x - pad_x, self.y - pad_y, self.size + 2 * pad_x, self.size + rows * (line + 2) + 2 * pad_y + 4

    def render(self, plan: Plan, client: Any, look: Look = LEGACY, ttl: int = 4) -> None:
        if not plan.visible:
            self.clear(client)
            return
        left, top, width, height = self.block_rect(look, plan)
        line = look.line_px("normal")
        size = look.size("normal")
        client.send_shape(self.panel_id, "rect", look.color("fill"), look.color("fill"), left, top, width, height, ttl=ttl * 2, thickness=1)   # a plain panel
        cx, cy = self.x + self.size / 2, self.y + line + 4 + self.size / 2
        texts: List[tuple] = []
        plot_bottom = self.y + line + 4 + self.size + 4
        row_y = [self.y] + [plot_bottom + n * (line + 2) for n in range(max(0, len(plan.rows) - 1))]
        arrows: List[tuple] = []                                  # (angle, role, x, y) of the little pointers
        for row, items in enumerate(plan.rows[:len(row_y)]):
            x = float(self.x)
            for item in items:
                if item.angle is not None:
                    arrows.append((item.angle, item.role, x + ARROW_SIZE, row_y[row] + line / 2 - 2))
                    x += 2 * ARROW_SIZE + 4
                texts.append((item.text, item.role, x, row_y[row]))
                x += look.measured_width(item.text) + 16
        texts.append((plan.scale, "muted", self.x + self.size - look.measured_width(plan.scale), self.y + line + 4))
        for index, circle in enumerate(plan.circles[:self.MAX_CIRCLES]):
            role = "danger" if circle.inside else "ok"
            color = look.color(role) if circle.active else look.color("muted")
            fill = with_alpha(look.color(role), self.fill_alpha) if circle.inside and self.fill_alpha else "#00000000"
            client.send_circle(f"{self.prefix}c{index}", color, fill, cx + circle.x, cy - circle.y, circle.radius, ttl=ttl, thickness=self.line_width)
        for index in range(min(len(plan.circles), self.MAX_CIRCLES), self._used_circles):
            client.send_circle(f"{self.prefix}c{index}", "", "", cx, cy, 1, ttl=1)
        self._used_circles = min(len(plan.circles), self.MAX_CIRCLES)
        # you: a small filled circle at the center, with a short line ahead
        client.send_circle(f"{self.prefix}me", look.color("title"), look.color("title"), cx, cy, 4, ttl=ttl, thickness=1)
        client.send_vector(f"{self.prefix}ahead", [{"x": cx, "y": cy - 4}, {"x": cx, "y": cy - 20}], look.color("title"), ttl=ttl)
        if plan.north is not None:
            # north, on the edge of the plot: the plot turns with you, so this says which way the map's north is (an arrowhead and an N)
            edge = self.size / 2 - 6
            nx, ny = math.sin(math.radians(plan.north)), math.cos(math.radians(plan.north))
            client.send_vector(f"{self.prefix}north", arrow_points(cx + nx * edge, cy - ny * edge, plan.north, ARROW_SIZE), look.color("muted"), ttl=ttl)
            texts.append(("N", "muted", cx + nx * (edge - 14) - 4, cy - ny * (edge - 14) - 9))
        for index, (label, mx, my) in enumerate(plan.markers):
            texts.append((label, "info", cx + mx - 4, cy - my - 9))
            client.send_circle(f"{self.prefix}m{index}", look.color("info"), "#00000000", cx + mx, cy - my, 8, ttl=ttl, thickness=2)
        for index in range(len(plan.markers), 2):
            client.send_circle(f"{self.prefix}m{index}", "", "", cx, cy, 1, ttl=1)
        # the plants being tracked: a ring with the genus's letter, and a line from you toward the nearest one (to the edge of the plot if it is further)
        for index, (label, tx, ty, color, ring) in enumerate(plan.targets[:self.MAX_TARGETS]):
            texts.append((label, f"series{color}", cx + tx - 4, cy - ty - 9))
            client.send_circle(f"{self.prefix}t{index}", look.color(f"series{color}"), "#00000000", cx + tx, cy - ty, ring, ttl=ttl, thickness=self.line_width)
        for index in range(min(len(plan.targets), self.MAX_TARGETS), self.MAX_TARGETS):
            client.send_circle(f"{self.prefix}t{index}", "", "", cx, cy, 1, ttl=1)
        reach = self.size / 2 - 14
        for index, (px, py, color) in enumerate(plan.pointers[:self.MAX_TARGETS]):
            client.send_vector(f"{self.prefix}point{index}", [{"x": cx + px * 8, "y": cy - py * 8}, {"x": cx + px * reach, "y": cy - py * reach}],
                               look.color(f"series{color}"), ttl=ttl)
        for index in range(min(len(plan.pointers), self.MAX_TARGETS), self.MAX_TARGETS):
            client.send_vector(f"{self.prefix}point{index}", [], "white", ttl=1)
        for index, (text, role, tx, ty) in enumerate(texts):
            client.send_message(f"{self.prefix}x{index}", text, look.color(role), int(tx), int(ty), ttl=ttl, size=size)
        for index, (angle, role, ax, ay) in enumerate(arrows[:self.MAX_ARROWS]):
            client.send_vector(f"{self.prefix}a{index}", arrow_points(ax, ay, angle, ARROW_SIZE), look.color(role), ttl=ttl)
        for index in range(min(len(arrows), self.MAX_ARROWS), self.MAX_ARROWS):
            client.send_vector(f"{self.prefix}a{index}", [], "white", ttl=1)
        for index in range(len(texts), self._used_texts):
            client.send_message(f"{self.prefix}x{index}", "", "white", self.x, self.y, ttl=1)
        self._used_texts = len(texts)

    def clear(self, client: Any) -> None:
        left, top, _w, _h = self.block_rect(LEGACY)
        for shape_id in (self.panel_id, f"{self.prefix}bar"):
            client.send_shape(shape_id, "rect", "", "", left, top, 0, 0, ttl=1)
        for shape_id in [f"{self.prefix}c{i}" for i in range(self._used_circles)] + [f"{self.prefix}m0", f"{self.prefix}m1", f"{self.prefix}me"] + [
                f"{self.prefix}t{i}" for i in range(self.MAX_TARGETS)]:
            client.send_circle(shape_id, "", "", left, top, 1, ttl=1)
        client.send_vector(f"{self.prefix}ahead", [], "white", ttl=1)
        client.send_vector(f"{self.prefix}north", [], "white", ttl=1)
        for index in range(self.MAX_TARGETS):
            client.send_vector(f"{self.prefix}point{index}", [], "white", ttl=1)
        for index in range(self.MAX_ARROWS):
            client.send_vector(f"{self.prefix}a{index}", [], "white", ttl=1)
        for index in range(self._used_texts):
            client.send_message(f"{self.prefix}x{index}", "", "white", self.x, self.y, ttl=1)
        self._used_circles = self._used_texts = 0
