"""
Great-circle distance/bearing math for mining_overlay.py's waypoint
arrow: a recorded hotspot's lat/lon vs. the commander's live position
(mining_live_position.py), both assumed to be on the same body - a
spherical-body approximation (haversine distance, initial bearing) is
accurate enough for "which way and how far", without needing the game's
actual (slightly non-spherical, sometimes irregular) terrain model.
"""
import math

_COMPASS_POINTS = ("N", "NE", "E", "SE", "S", "SW", "W", "NW")
_ARROW_GLYPHS = ("↑", "↗", "→", "↘", "↓", "↙", "←", "↖")
"""Up, up-right, right, down-right, down, down-left, left, up-left -
the closest a text-only overlay send can get to a rotating arrow when a
vector shape isn't available. Index order matches arrow_glyph()'s
relative-bearing buckets: 0=ahead, 90=right, 180=behind, 270=left."""


def distance_m(lat1: float, lon1: float, lat2: float, lon2: float, radius_m: float) -> float:
    """Haversine great-circle distance between two lat/lon points (in
    degrees) on a sphere of `radius_m` - the body's radius, from a `Scan`
    event (mining_surface.py) or Status.json's live `PlanetRadius`."""
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return radius_m * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def initial_bearing_deg(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Initial compass bearing (0-360, 0 = North) from point 1 to point 2,
    both in degrees."""
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dlambda = math.radians(lon2 - lon1)
    x = math.sin(dlambda) * math.cos(phi2)
    y = math.cos(phi1) * math.sin(phi2) - math.sin(phi1) * math.cos(phi2) * math.cos(dlambda)
    return math.degrees(math.atan2(x, y)) % 360


def compass_point(bearing_deg: float) -> str:
    """0-360 (0 = North) -> one of 8 compass points."""
    return _COMPASS_POINTS[round(bearing_deg / 45) % 8]


def arrow_glyph(relative_bearing_deg: float) -> str:
    """Relative bearing (target bearing minus current heading, 0-360,
    0 = straight ahead, 90 = directly to your right) -> a rotated unicode
    arrow glyph at 8-point resolution."""
    return _ARROW_GLYPHS[round(relative_bearing_deg / 45) % 8]


def format_distance_m(distance_m: float) -> str:
    """Meters -> a "500m"/"1.50km" tiered string - on-foot/SRV ranges
    rarely if ever reach Mm scale, so this only tiers up to km."""
    if distance_m > 1000:
        return f"{distance_m / 1000:.2f}km"
    return f"{distance_m:.0f}m"


def arrow_vector_points(cx: int, cy: int, size: float, relative_bearing_deg: float) -> list[dict]:
    """Vertices for a HUD-overlay `"shape": "vect"` polyline: an arrow
    centered at `(cx, cy)`, continuously rotated (not snapped to 8
    points like arrow_glyph()) to point along `relative_bearing_deg` (0 =
    straight ahead/up, 90 = right), in the overlay's own pixel coordinate
    space (origin top-left, y downward).

    Drawn as one stroke: shaft from the tail to the tip, then back out along
    each barb, so the overlay needs only a single polyline. Built in the
    arrow's own frame (forward = +1 along `heading`, sideways along
    `across`) and mapped to pixels at the end."""
    theta = math.radians(relative_bearing_deg)
    # Unit vectors in screen space: forward is "up" at bearing 0 and swings
    # clockwise; sideways is forward turned 90 degrees clockwise.
    heading = (math.sin(theta), -math.cos(theta))
    across = (math.cos(theta), math.sin(theta))

    def at(forward: float, sideways: float) -> dict:
        return {"x": round(cx + heading[0] * forward + across[0] * sideways),
                "y": round(cy + heading[1] * forward + across[1] * sideways)}

    tip_reach, tail_reach, barb_back, barb_spread = size, 0.8 * size, 0.5 * size, 0.5 * size
    tail = at(-tail_reach, 0)
    tip = at(tip_reach, 0)
    return [tail, tip,
            at(tip_reach - barb_back, -barb_spread), tip,
            at(tip_reach - barb_back, barb_spread)]
