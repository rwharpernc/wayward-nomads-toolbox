"""
Pure logic (no Tk) for Waypoint Route — Boxel Survey's third sub-mode.

Where Sequence walks one flat boxel sequence and Region Sweep tracks
completion across a queue of cubes, Waypoint Route is a general
point-to-point route tool: a commander adds arbitrary systems (hand-named
or procedural — a fixed rendezvous, a POI, a squadron staging system,
whatever) and this module helps visit them in a sensible order, optionally
importing the list from a CSV file.

Unlike Sequence/Region Sweep, this genuinely needs real coordinates for its
nearest-neighbor reordering - there's no way around that when the whole
point is "which of these is closest." Those coordinates always come from a
live EDSM lookup (edsm_client.systems_coords(), called from
waypoint_route_panel.py), never computed or guessed locally - same
principle as edsm_client.py's own nearby_systems(), just applied to named
systems instead of a spatial cube query.

Kept pure (no EDMC/Tk imports) so it's unit-testable the same way
boxel.py/survey_log.py are - follows survey_log.py's own `try/except
ImportError` fallback for `appname` rather than boxel_walker.py's hard
`config` import, specifically so this stays importable under a plain
`python -m unittest` run outside a live EDMC install.
"""

from __future__ import annotations

import csv
import logging
import math
import os
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

try:
    from config import appname
except ImportError:
    # EDMC's `config` module isn't on sys.path outside a running EDMC
    # instance (e.g. under `python -m unittest`) - this module's actual
    # logic has no other EDMC dependency, so fall back to a plain name
    # rather than make the whole module require the EDMC runtime to import.
    appname = "EDMarketConnector"

plugin_name = os.path.basename(os.path.dirname(__file__))
logger = logging.getLogger(f"{appname}.{plugin_name}")

_CSV_HEADER_NAMES = {"system", "name", "waypoint", "system name", "systemname"}


@dataclass
class Waypoint:
    name: str
    x: Optional[float] = None
    y: Optional[float] = None
    z: Optional[float] = None
    visited: bool = False

    @property
    def has_coords(self) -> bool:
        return self.x is not None and self.y is not None and self.z is not None

    @property
    def xyz(self) -> Optional[Tuple[float, float, float]]:
        return (self.x, self.y, self.z) if self.has_coords else None


def _distance(a: Tuple[float, float, float], b: Tuple[float, float, float]) -> float:
    return math.dist(a, b)


class WaypointRoute:
    """Manages an ordered list of waypoints. Order is the route: the first
    not-yet-visited waypoint is always the current target."""

    def __init__(self) -> None:
        self._waypoints: List[Waypoint] = []

    @property
    def waypoints(self) -> List[Waypoint]:
        return list(self._waypoints)

    def _find(self, name: str) -> Optional[int]:
        key = name.casefold()
        for i, wp in enumerate(self._waypoints):
            if wp.name.casefold() == key:
                return i
        return None

    def add(self, name: str) -> Waypoint:
        """Append a waypoint if not already present (case-insensitive) -
        a no-op returning the existing entry if it is."""
        idx = self._find(name)
        if idx is not None:
            return self._waypoints[idx]
        wp = Waypoint(name=name)
        self._waypoints.append(wp)
        return wp

    def add_many(self, names: List[str]) -> int:
        """Add several names at once (e.g. from a CSV import). Returns how
        many were genuinely new (not already present)."""
        added = 0
        for name in names:
            before = len(self._waypoints)
            self.add(name)
            if len(self._waypoints) > before:
                added += 1
        return added

    def remove(self, name: str) -> bool:
        idx = self._find(name)
        if idx is None:
            return False
        del self._waypoints[idx]
        return True

    def move(self, name: str, delta: int) -> bool:
        """Manually reorder: swap `name` with its neighbor `delta` positions
        away (delta=-1 moves up, +1 moves down). No-op (returns False) at
        either end of the list."""
        idx = self._find(name)
        if idx is None:
            return False
        target = idx + delta
        if target < 0 or target >= len(self._waypoints):
            return False
        self._waypoints[idx], self._waypoints[target] = self._waypoints[target], self._waypoints[idx]
        return True

    def set_coords(self, name: str, x: float, y: float, z: float) -> bool:
        idx = self._find(name)
        if idx is None:
            return False
        wp = self._waypoints[idx]
        wp.x, wp.y, wp.z = x, y, z
        return True

    def reorder_nearest_neighbor(self, start: Tuple[float, float, float]) -> int:
        """Greedily reorders the *unvisited, coordinate-resolved* subset by
        nearest-neighbor distance from `start` (typically the commander's
        current position). Already-visited waypoints and ones EDSM
        couldn't locate keep their existing relative position, appended
        after the newly-ordered ones - never dropped, never silently
        mis-ordered by a missing coordinate. Returns how many were
        actually reordered."""
        visited = [wp for wp in self._waypoints if wp.visited]
        pending = [wp for wp in self._waypoints if not wp.visited]
        resolved = [wp for wp in pending if wp.has_coords]
        unresolved = [wp for wp in pending if not wp.has_coords]

        ordered: List[Waypoint] = []
        remaining = list(resolved)
        current = start
        while remaining:
            nearest = min(remaining, key=lambda wp: _distance(current, wp.xyz))  # type: ignore[arg-type]
            ordered.append(nearest)
            remaining.remove(nearest)
            current = nearest.xyz  # type: ignore[assignment]

        self._waypoints = visited + ordered + unresolved
        return len(ordered)

    def mark_visited(self, name: str) -> bool:
        idx = self._find(name)
        if idx is None:
            return False
        self._waypoints[idx].visited = True
        return True

    def current_target(self) -> Optional[Waypoint]:
        for wp in self._waypoints:
            if not wp.visited:
                return wp
        return None

    def on_jump(self, system_name: str) -> Optional[str]:
        """Handle arrival at system_name. Marks it visited if it's in the
        list (wherever it sits - not just if it's the current target, so
        skipping ahead or arriving out of order is still recorded).
        Returns the new current target's name, or None if there isn't
        one."""
        self.mark_visited(system_name)
        target = self.current_target()
        return target.name if target else None

    @staticmethod
    def parse_csv_names(path: str) -> List[str]:
        """Reads one system name per row's first column. Blank rows and an
        obvious header row (first column reads "system"/"name"/"waypoint"/
        etc., case-insensitive) are skipped; every other row's first
        column, stripped, is treated as a system name."""
        names: List[str] = []
        with open(path, newline="", encoding="utf-8-sig") as fh:
            reader = csv.reader(fh)
            for row in reader:
                if not row:
                    continue
                candidate = row[0].strip()
                if not candidate:
                    continue
                if candidate.casefold() in _CSV_HEADER_NAMES:
                    continue
                names.append(candidate)
        return names

    # --- persistence -----------------------------------------------------

    def snapshot(self) -> List[Dict[str, Any]]:
        return [
            {"name": wp.name, "x": wp.x, "y": wp.y, "z": wp.z, "visited": wp.visited}
            for wp in self._waypoints
        ]

    def restore(self, data: List[Dict[str, Any]]) -> None:
        waypoints: List[Waypoint] = []
        for raw in data:
            try:
                waypoints.append(Waypoint(
                    name=raw["name"], x=raw.get("x"), y=raw.get("y"), z=raw.get("z"),
                    visited=bool(raw.get("visited", False)),
                ))
            except KeyError:
                logger.warning("Skipping malformed saved waypoint: %r", raw)
        self._waypoints = waypoints
