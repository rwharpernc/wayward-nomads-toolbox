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
from typing import Any, List, Optional, Tuple

from . import organic_scan
from .overlay_card import ACCENT_W
from .overlay_style import CARD_PAD_X, CARD_PAD_Y, LEGACY, Look, with_alpha

SIZE = 260                  # the plot's width and height in pixels
MIN_EXTENT_M = 150.0        # the plot never shows less than this radius
MAX_EXTENT_M = 3000.0       # nor more than this
MARGIN = 1.12               # room around the outermost circle


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


@dataclass(frozen=True)
class Plan:
    circles: Tuple[Circle, ...] = ()
    markers: Tuple[Tuple[str, float, float], ...] = ()      # (label, x, y) for the ship and the SRV
    top: str = ""                                            # "Ship: 7 m   SRV: 7 m"
    bottom: str = ""                                         # "Scan one: 342 m   Scan two: 0 m"
    scale: str = ""                                          # what half the plot's width is, e.g. "300 m"
    visible: bool = False


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
    if not spots and view.ship is None and view.srv is None:
        return Plan()
    reach = [distance_m(here, p, radius) + r for p, r, _a, _k in spots]
    reach += [distance_m(here, p, radius) for p in (view.ship, view.srv) if p is not None]
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
    for label, position in (("Ship", view.ship), ("SRV", view.srv)):
        if position is None:
            continue
        right, ahead = offset_m(here, position, radius, view.heading)
        parts.append(f"{label}: {distance_text(distance_m(here, position, radius))}")
        if math.hypot(right, ahead) <= extent:
            markers.append((label[0], right * per_m, ahead * per_m))
    bottom = ""
    if active is not None and active.positions:
        scans = [f"Scan {name}: {distance_text(distance_m(here, p, radius))}" for name, p in zip(("one", "two", "three"), active.positions)]
        bottom = "   ".join(scans[:2])
    return Plan(tuple(circles), tuple(markers), "   ".join(parts), bottom, distance_text(extent), True)


class RadarLayout:
    """Draws a `Plan` in its own panel at a fixed origin. Shapes and texts use overlay ids under `prefix`; unused ones are cleared."""

    MAX_CIRCLES = 12

    def __init__(self, prefix: str, x: int, y: int, accent: str = "border") -> None:
        self.prefix, self.x, self.y, self.accent = prefix, x, y, accent
        self.panel_id = f"{prefix}panel"
        self._used_circles = 0
        self._used_texts = 0

    def block_rect(self, look: Look = LEGACY) -> Tuple[int, int, int, int]:
        pad_x, pad_y = look.pad_x(CARD_PAD_X), look.pad_y(CARD_PAD_Y)
        line = look.line_px("normal")
        return self.x - pad_x, self.y - pad_y, SIZE + 2 * pad_x, SIZE + 2 * line + 2 * pad_y + 8

    def render(self, plan: Plan, client: Any, look: Look = LEGACY, ttl: int = 4) -> None:
        if not plan.visible:
            self.clear(client)
            return
        left, top, width, height = self.block_rect(look)
        line = look.line_px("normal")
        size = look.size("normal")
        client.send_shape(self.panel_id, "rect", look.soft(look.color("border")), look.color("fill"), left, top, width, height, ttl=ttl, thickness=1)
        client.send_shape(f"{self.prefix}bar", "rect", look.color(self.accent), look.color(self.accent), left, top, ACCENT_W, height, ttl=ttl, thickness=1)
        cx, cy = self.x + SIZE / 2, self.y + line + 4 + SIZE / 2
        texts: List[tuple] = []
        if plan.top:
            texts.append((plan.top, "text", self.x, self.y))
        plot_bottom = self.y + line + 4 + SIZE + 4
        if plan.bottom:
            texts.append((plan.bottom, "text", self.x, plot_bottom))
        texts.append((plan.scale, "muted", self.x + SIZE - look.measured_width(plan.scale), self.y + line + 4))
        for index, circle in enumerate(plan.circles[:self.MAX_CIRCLES]):
            role = "danger" if circle.inside else "ok"
            color = look.color(role) if circle.active else look.color("muted")
            fill = with_alpha(look.color(role), 0x55) if circle.inside else "#00000000"
            client.send_circle(f"{self.prefix}c{index}", color, fill, cx + circle.x, cy - circle.y, circle.radius, ttl=ttl, thickness=2)
        for index in range(min(len(plan.circles), self.MAX_CIRCLES), self._used_circles):
            client.send_circle(f"{self.prefix}c{index}", "", "", cx, cy, 1, ttl=1)
        self._used_circles = min(len(plan.circles), self.MAX_CIRCLES)
        # you: a small filled circle at the center, with a short line ahead
        client.send_circle(f"{self.prefix}me", look.color("title"), look.color("title"), cx, cy, 4, ttl=ttl, thickness=1)
        client.send_vector(f"{self.prefix}ahead", [{"x": cx, "y": cy - 4}, {"x": cx, "y": cy - 20}], look.color("title"), ttl=ttl)
        for index, (label, mx, my) in enumerate(plan.markers):
            texts.append((label, "info", cx + mx - 4, cy - my - 9))
            client.send_circle(f"{self.prefix}m{index}", look.color("info"), "#00000000", cx + mx, cy - my, 8, ttl=ttl, thickness=2)
        for index in range(len(plan.markers), 2):
            client.send_circle(f"{self.prefix}m{index}", "", "", cx, cy, 1, ttl=1)
        for index, (text, role, tx, ty) in enumerate(texts):
            client.send_message(f"{self.prefix}x{index}", text, look.color(role), int(tx), int(ty), ttl=ttl, size=size)
        for index in range(len(texts), self._used_texts):
            client.send_message(f"{self.prefix}x{index}", "", "white", self.x, self.y, ttl=1)
        self._used_texts = len(texts)

    def clear(self, client: Any) -> None:
        left, top, _w, _h = self.block_rect(LEGACY)
        for shape_id in (self.panel_id, f"{self.prefix}bar"):
            client.send_shape(shape_id, "rect", "", "", left, top, 0, 0, ttl=1)
        for shape_id in [f"{self.prefix}c{i}" for i in range(self._used_circles)] + [f"{self.prefix}m0", f"{self.prefix}m1", f"{self.prefix}me"]:
            client.send_circle(shape_id, "", "", left, top, 1, ttl=1)
        client.send_vector(f"{self.prefix}ahead", [], "white", ttl=1)
        for index in range(self._used_texts):
            client.send_message(f"{self.prefix}x{index}", "", "white", self.x, self.y, ttl=1)
        self._used_circles = self._used_texts = 0
