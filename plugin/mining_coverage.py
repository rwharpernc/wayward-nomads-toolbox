"""
Tracks ground the Rhino's scanner has driven over, per body, for the
Surface Mining page's coverage minimap (mining_coverage_render.py draws
the actual picture - this module is pure geometry/persistence, no PIL,
no tkinter).

"Painted" means driven within scanner range of a point, not scanned -
nothing the journal or Status.json says means a scan happened, so this
can't and doesn't claim to track real surface-scan coverage, only where
the Rhino has been. The design is deliberately simple: paint a disc of
SCAN_RADIUS_M at each recorded point rather than trying to reconstruct
the SRV's exact path.

Fed from mining_panel.py's dashboard_status() (Status.json's live
Latitude/Longitude via mining_live_position.py) whenever
mining_surface.surface_mining_repository.is_active is true - i.e. a
Rhino is actually deployed - and a body radius is known (also read off
mining_surface.py). Not fed from journal events: like
mining_live_position.py itself, this needs Status.json's
once-a-second telemetry, not discrete journal lines.
"""
from __future__ import annotations

import json
import logging
import os
from dataclasses import asdict, dataclass, field
from typing import Optional

try:
    from config import appname
except ImportError:  # pragma: no cover - real EDMC runtime always provides this
    appname = "EDMarketConnector"

from . import commander_data
from . import mining_bearing as bearing

plugin_name = os.path.basename(os.path.dirname(__file__))
logger = logging.getLogger(f"{appname}.{plugin_name}")

COVERAGE_FILENAME = "mining_coverage.json"
"""Not committed to git and not part of any release build - the
commander's own drive history, same reasoning as mining_hotspots.py's
HOTSPOTS_FILENAME. One file, a separate map per commander
(commander_data.py)."""

SCAN_RADIUS_M = 2000.0
"""What the Rhino's scanner sees from wherever it's standing, in
meters - a community figure (Frontier hasn't published one)."""

STAMP_M = 250.0
"""Minimum distance from the last recorded point before a new one is
added - a straight line of stamped discs SCAN_RADIUS_M wide doesn't
need a point every meter driven to look continuous once rendered."""

MAX_POINTS_PER_BODY = 2000
"""Keeps a body's coverage file bounded across a long session's driving
- same "keep history bounded" reasoning as store.py's MAX_HISTORY.
Oldest points are dropped first once this is hit; losing the very
first stamps of a long-since-covered area matters far less than losing
recent ones."""


@dataclass
class CoveragePoint:
    latitude: float
    longitude: float


@dataclass
class BodyCoverage:
    """One body's drive history. `center` is the first point ever
    recorded for this body - fixed for the body's lifetime so the map
    doesn't re-anchor (and silently discard the visual relationship
    between old and new points) every time coverage is rendered."""
    center: Optional[CoveragePoint] = None
    points: list[CoveragePoint] = field(default_factory=list)

    def record(self, latitude: float, longitude: float, radius_m: float) -> bool:
        """Adds a point if it's at least STAMP_M from the last one
        recorded (or if this is the first point for the body, which
        also sets `center`). Returns whether a point was actually
        added, so the caller only re-renders/saves on real change."""
        if self.center is None:
            self.center = CoveragePoint(latitude, longitude)
            self.points.append(CoveragePoint(latitude, longitude))
            return True
        if self.points:
            last = self.points[-1]
            if bearing.distance_m(last.latitude, last.longitude, latitude, longitude, radius_m) < STAMP_M:
                return False
        self.points.append(CoveragePoint(latitude, longitude))
        if len(self.points) > MAX_POINTS_PER_BODY:
            del self.points[: len(self.points) - MAX_POINTS_PER_BODY]
        return True


class CoverageRepository:
    """Constructed empty, `load(plugin_dir)` called once from
    mining_panel.start() - same convention as
    mining_hotspots.HotspotRepository."""

    def __init__(self) -> None:
        self._by_body: dict[str, BodyCoverage] = {}   # the current commander's; empty until one is known
        self._plugin_dir: Optional[str] = None
        self._store = commander_data.new_store()
        self._cmdr = ""

    def load(self, plugin_dir: str) -> None:
        """Read the file. Nothing is shown until `set_commander` says whose map to use. A file written before coverage
        was per commander is claimed by the first commander seen."""
        self._plugin_dir = plugin_dir
        path = os.path.join(plugin_dir, COVERAGE_FILENAME)
        try:
            self._store = commander_data.read(path, is_legacy=lambda raw: isinstance(raw, dict))
        except Exception:
            logger.exception("Failed to load %s - starting with no recorded coverage", COVERAGE_FILENAME)
            self._store = commander_data.new_store()

    def set_commander(self, cmdr: str) -> None:
        """Switch to this commander's recorded ground (the previous commander's is already saved)."""
        key = commander_data.key_for(cmdr)
        if not key or key == commander_data.key_for(self._cmdr):
            return
        self._cmdr = str(cmdr).strip()
        claimed = not commander_data.known(self._store, cmdr) and self._store.get("legacy") is not None
        try:
            raw = commander_data.payload_for(self._store, cmdr, dict)
            self._by_body = {
                body_key: BodyCoverage(
                    center=CoveragePoint(**entry["center"]) if entry.get("center") else None,
                    points=[CoveragePoint(**p) for p in entry.get("points", [])],
                )
                for body_key, entry in raw.items()
            }
        except Exception:
            logger.exception("Failed to read %s's coverage - starting with none", cmdr)
            self._by_body = {}
        if claimed:
            self._save()

    @staticmethod
    def _key(system: str, body: str) -> str:
        return f"{system.strip().casefold()}|{body.strip().casefold()}"

    def for_body(self, system: Optional[str], body: Optional[str]) -> Optional[BodyCoverage]:
        if not system or not body:
            return None
        return self._by_body.get(self._key(system, body))

    def record(self, system: str, body: str, latitude: float, longitude: float, radius_m: float) -> None:
        if not system or not body:
            return
        key = self._key(system, body)
        coverage = self._by_body.setdefault(key, BodyCoverage())
        if coverage.record(latitude, longitude, radius_m):
            self._save()

    def clear_body(self, system: str, body: str) -> None:
        """Drops all recorded coverage for one body - a safety valve for
        a commander who wants a fresh map (e.g. after driving somewhere
        irrelevant by mistake), cheap to provide given the
        JSON-file-per-repository storage every other WNTB feature already
        uses."""
        if self._by_body.pop(self._key(system, body), None) is not None:
            self._save()

    def _save(self) -> None:
        if self._plugin_dir is None or not self._cmdr:
            return
        try:
            path = os.path.join(self._plugin_dir, COVERAGE_FILENAME)
            payload = {
                key: {
                    "center": asdict(coverage.center) if coverage.center else None,
                    "points": [asdict(p) for p in coverage.points],
                }
                for key, coverage in self._by_body.items()
            }
            commander_data.put(self._store, self._cmdr, payload)
            commander_data.write(path, self._store)
        except Exception:
            logger.exception("Failed to save %s", COVERAGE_FILENAME)


coverage_repository = CoverageRepository()
