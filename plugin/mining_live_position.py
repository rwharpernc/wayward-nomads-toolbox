"""
The commander's live surface position (Latitude/Longitude/Heading) from
Status.json, fed from load.py's `dashboard_entry` hook - EDMC's own
`journal_entry` only fires for discrete journal events, never for this
continuously-updated telemetry file (EDMC calls `dashboard_entry` roughly
once a second, whenever Status.json changes - see PLUGINS.md's "Player
Dashboard" section), so this needs its own plugin hook rather than
piggybacking on mining_surface.py's journal-event-driven tracking.

Only meaningful while Status.json's `Flags` has `FlagsHasLatLong` (bit
21, per EDCD's edmc_data.py) set - i.e. on foot or in a vehicle on a
landable body's surface, which is where a Rhino deployment's recorded
hotspots would be. Used by mining_overlay.py's bearing/distance
calculation to the nearest recorded hotspot on the current body.

Status.json also carries a live `PlanetRadius` (meters) alongside
Latitude/Longitude/Heading whenever they're populated. mining_surface.py's
`Scan`-derived radius predates noticing this field and remains as a
fallback for the case this one is ever absent from a given game/EDMC
version.
"""
from dataclasses import dataclass
from typing import Any, Optional

FLAGS_HAS_LAT_LONG = 1 << 21


@dataclass
class LivePosition:
    latitude: float
    longitude: float
    heading: Optional[float]
    """None on the rare Status.json update that has valid lat/lon but no
    heading yet - callers needing a directional arrow should treat that
    as "can't orient yet" rather than assuming 0."""
    planet_radius: Optional[float]
    """Meters, from Status.json's own `PlanetRadius` field when present.
    None on a game/EDMC version that doesn't populate it - callers should
    fall back to mining_surface.py's Scan-derived radius rather than
    skip the waypoint overlay entirely."""
    altitude: Optional[float] = None
    """Meters above the surface, from Status.json's `Altitude` (present
    alongside Latitude/Longitude). None when absent - the in-ship
    minimap treats that as "unknown", not "low"."""


_current: Optional[LivePosition] = None


def set_status(entry: dict[str, Any]) -> None:
    """Called from load.py's dashboard_entry() with the raw Status.json
    dict on every update. Clears the tracked position the moment
    FlagsHasLatLong drops (lifting off, boarding a taxi, fast-travelling
    away, etc.) so a stale position doesn't linger and point
    mining_overlay.py at a spot that's no longer meaningful."""
    global _current
    flags = entry.get("Flags")
    if not isinstance(flags, int) or not (flags & FLAGS_HAS_LAT_LONG):
        _current = None
        return
    latitude, longitude = entry.get("Latitude"), entry.get("Longitude")
    if not isinstance(latitude, (int, float)) or not isinstance(longitude, (int, float)):
        _current = None
        return
    heading = entry.get("Heading")
    radius = entry.get("PlanetRadius")
    altitude = entry.get("Altitude")
    _current = LivePosition(
        latitude=latitude, longitude=longitude,
        heading=heading if isinstance(heading, (int, float)) else None,
        planet_radius=radius if isinstance(radius, (int, float)) and radius > 0 else None,
        altitude=altitude if isinstance(altitude, (int, float)) else None)


def current_position() -> Optional[LivePosition]:
    return _current
