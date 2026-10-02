"""
Pure logic (no Tk) for Region Sweep — a second Boxel Survey mode that tracks
completion across a user-curated queue of cubes, rather than walking one flat
sequence within a single boxel like boxel_walker.BoxelWalker does.

A "cube" here is exactly the same unit BoxelWalker already walks one instance
of: sector + cube_id + mass_code. Region Sweep manages several of them at
once — each with its own BoxelWalker for within-cube advance/retreat — plus
completion tracking (which known systems in that cube have been visited/
scanned) and an "empty" flag so a cube confirmed to have nothing worth
surveying can be permanently skipped in the future.

Deliberately has no notion of moving between cubes spatially (no id64/
coordinate math) — see boxel.py's module docstring for why WNTB doesn't do
that (a similar, much simpler attempt was tried and reverted). Cubes are
only ever added here from real external sources (a typed seed name, an EDSM
nearby-systems result, a Spansh boxel query) which supply spatial truth;
this module only tracks completion state for cubes it's told about, and
never invents a "next boxel" itself.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from config import appname

from . import boxel
from .boxel_walker import BoxelWalker, WalkerSnapshot

plugin_name = os.path.basename(os.path.dirname(__file__))
logger = logging.getLogger(f"{appname}.{plugin_name}")


def cube_key(sector: str, cube_id: str, mass_code: str) -> str:
    """Canonical dict key for one cube — sector + cube_id + mass_code, the
    same triple BoxelWalker already treats as one walkable unit."""
    return f"{sector}|{cube_id}|{mass_code}"


@dataclass
class CubeEntry:
    """One queued cube's completion state, plus its own BoxelWalker for
    within-cube advance/retreat — reusing that already-tested sequence math
    unchanged rather than reimplementing it here."""

    sector: str
    cube_id: str
    mass_code: str
    systems: Dict[str, bool] = field(default_factory=dict)  # name -> complete
    empty: bool = False
    walker: BoxelWalker = field(default_factory=BoxelWalker, repr=False, compare=False)

    @property
    def key(self) -> str:
        return cube_key(self.sector, self.cube_id, self.mass_code)

    @property
    def prefix(self) -> str:
        """Display-friendly cube label, independent of walker position."""
        return f"{self.sector} {self.cube_id} {self.mass_code}"

    @property
    def known_count(self) -> int:
        return len(self.systems)

    @property
    def complete_count(self) -> int:
        return sum(1 for done in self.systems.values() if done)

    @property
    def complete(self) -> bool:
        """A cube counts as complete once marked empty, or once every
        *known* (discovered) system in it is marked complete. There's no
        way to know a cube's true total system count with certainty —
        Spansh/EDSM only index what's been found/submitted — so this is
        necessarily "complete relative to what's been discovered so far"."""
        if self.empty:
            return True
        return bool(self.systems) and all(self.systems.values())

    def seed_name(self) -> str:
        """A synthetic starting name (<sector> <cube_id> <mass_code>0) used
        to prime this cube's own BoxelWalker when no known system exists yet
        to seed it with directly — mirrors what a commander would type into
        Sequence mode's own seed entry for a brand-new boxel."""
        return f"{self.sector} {self.cube_id} {self.mass_code}0"


@dataclass
class RegionSweepSnapshot:
    """Serializable snapshot of a RegionSweepQueue, for persistence."""

    cubes: List[Dict[str, Any]]
    current_index: int


class RegionSweepQueue:
    """Manages a flat, ordered queue of cubes and tracks completion across
    all of them."""

    def __init__(self) -> None:
        self._cubes: List[CubeEntry] = []
        self._current_index: int = -1

    # --- queue management ----------------------------------------------

    @property
    def cubes(self) -> List[CubeEntry]:
        return list(self._cubes)

    @property
    def current(self) -> Optional[CubeEntry]:
        if 0 <= self._current_index < len(self._cubes):
            return self._cubes[self._current_index]
        return None

    def _find(self, sector: str, cube_id: str, mass_code: str) -> Optional[int]:
        key = cube_key(sector, cube_id, mass_code)
        for i, cube in enumerate(self._cubes):
            if cube.key == key:
                return i
        return None

    def add_cube(self, sector: str, cube_id: str, mass_code: str) -> CubeEntry:
        """Add a cube to the queue if not already present (a no-op — just
        returns the existing entry — if it is), and make it current if
        nothing is current yet."""
        idx = self._find(sector, cube_id, mass_code)
        if idx is not None:
            return self._cubes[idx]
        entry = CubeEntry(sector=sector, cube_id=cube_id, mass_code=mass_code)
        entry.walker.set_seed(entry.seed_name())
        self._cubes.append(entry)
        if self._current_index < 0:
            self._current_index = len(self._cubes) - 1
        return entry

    def add_cube_from_system(self, system_name: str) -> Optional[CubeEntry]:
        """Convenience wrapper: parse a full system name and add its cube.
        Returns None if the name isn't procedural-shaped."""
        parsed = boxel.parse_system_name(system_name)
        if parsed is None:
            return None
        return self.add_cube(parsed.sector, parsed.cube_id, parsed.mass_code)

    def remove_cube(self, sector: str, cube_id: str, mass_code: str) -> bool:
        idx = self._find(sector, cube_id, mass_code)
        if idx is None:
            return False
        del self._cubes[idx]
        if not self._cubes:
            self._current_index = -1
        elif idx <= self._current_index:
            self._current_index = max(0, self._current_index - 1)
        return True

    def set_current(self, sector: str, cube_id: str, mass_code: str) -> bool:
        idx = self._find(sector, cube_id, mass_code)
        if idx is None:
            return False
        self._current_index = idx
        return True

    def mark_current_empty(self) -> None:
        cube = self.current
        if cube is not None:
            cube.empty = True

    def unmark_current_empty(self) -> None:
        cube = self.current
        if cube is not None:
            cube.empty = False

    # --- discovery -------------------------------------------------------

    def merge_known_systems(self, sector: str, cube_id: str, mass_code: str, names: List[str]) -> CubeEntry:
        """Merge externally-discovered system names into the matching
        cube's known-systems set (adding the cube to the queue first if it
        isn't already there). Never overwrites an already-True completion
        flag with a fresh, not-yet-complete entry.

        If this is a brand-new cube whose walker hasn't moved off its
        synthetic <mass_code>0 seed yet, reseed it from the lowest-numbered
        actually-known system in `names` instead — a made-up seed almost
        never corresponds to a real system, so "next target" would
        otherwise walk a sequence unrelated to what was just discovered."""
        entry = self.add_cube(sector, cube_id, mass_code)
        was_untouched = entry.walker.current == entry.seed_name()
        had_no_known_systems = not entry.systems
        for name in names:
            entry.systems.setdefault(name, False)
        if was_untouched and had_no_known_systems and names:
            parsed = [(boxel.parse_system_name(n), n) for n in names]
            valid = [(p, n) for p, n in parsed if p is not None]
            if valid:
                valid.sort(key=lambda pair: (pair[0].primary, pair[0].secondary if pair[0].secondary is not None else -1))
                entry.walker.set_seed(valid[0][1])
        return entry

    # --- completion --------------------------------------------------------

    def mark_visited(self, system_name: str) -> None:
        """Record `system_name` as visited (not necessarily complete) in
        whichever queued cube it belongs to — always safe to call on every
        jump regardless of the active completion criterion. No-op if the
        name doesn't match any queued cube."""
        parsed = boxel.parse_system_name(system_name)
        if parsed is None:
            return
        idx = self._find(parsed.sector, parsed.cube_id, parsed.mass_code)
        if idx is None:
            return
        cube = self._cubes[idx]
        cube.walker.mark_visited(system_name)
        cube.systems.setdefault(system_name, False)

    def mark_system_complete(self, system_name: str) -> None:
        """Record `system_name` as complete (implies visited). Callers
        decide *when* a system counts as complete (on jump, vs. only after
        an async EDSM full-scan confirmation) — this just records the
        outcome once decided."""
        self.mark_visited(system_name)
        parsed = boxel.parse_system_name(system_name)
        if parsed is None:
            return
        idx = self._find(parsed.sector, parsed.cube_id, parsed.mass_code)
        if idx is not None:
            self._cubes[idx].systems[system_name] = True

    # --- targeting -----------------------------------------------------

    def advance_cube(self) -> Optional[CubeEntry]:
        """Move to the next incomplete, non-empty cube in the queue
        (wrapping from the end back to the start), or None if every cube
        is complete/empty, or the queue itself is empty."""
        if not self._cubes:
            return None
        n = len(self._cubes)
        for step in range(1, n + 1):
            idx = (self._current_index + step) % n
            cube = self._cubes[idx]
            if not cube.complete:
                self._current_index = idx
                return cube
        return None

    def on_jump(self, system_name: str, *, skip_visited: bool = True, complete: bool = True) -> Optional[str]:
        """
        Handle arrival at system_name. Always marks it visited; marks it
        complete too unless `complete` is False (the panel passes False
        when the "require full FSS scan" setting is on, and calls
        mark_system_complete() itself later once that's confirmed).

        If system_name is the current cube's current target, advances
        within that cube — or to the next incomplete cube, if this one is
        now exhausted. Returns the new target, or None if there's nothing
        to advance to (no current cube, or the arrival wasn't the target).
        """
        if complete:
            self.mark_system_complete(system_name)
        else:
            self.mark_visited(system_name)

        cube = self.current
        if cube is None or system_name != cube.walker.current:
            return None

        target = cube.walker.advance(skip_visited=skip_visited)
        if cube.complete:
            next_cube = self.advance_cube()
            return next_cube.walker.current if next_cube else target
        return target

    # --- stats -----------------------------------------------------------

    @property
    def cubes_complete(self) -> int:
        return sum(1 for c in self._cubes if c.complete)

    @property
    def systems_complete(self) -> int:
        return sum(c.complete_count for c in self._cubes)

    @property
    def systems_known(self) -> int:
        return sum(c.known_count for c in self._cubes)

    # --- persistence -------------------------------------------------------

    def snapshot(self) -> RegionSweepSnapshot:
        cubes: List[Dict[str, Any]] = []
        for cube in self._cubes:
            walker_snap = cube.walker.snapshot()
            cubes.append({
                "sector": cube.sector,
                "cube_id": cube.cube_id,
                "mass_code": cube.mass_code,
                "systems": dict(cube.systems),
                "empty": cube.empty,
                "walker_seed": walker_snap.seed,
                "walker_current": walker_snap.current,
                "walker_visited": walker_snap.visited,
            })
        return RegionSweepSnapshot(cubes=cubes, current_index=self._current_index)

    def restore(self, snap: RegionSweepSnapshot) -> None:
        cubes: List[CubeEntry] = []
        for raw in snap.cubes:
            try:
                entry = CubeEntry(
                    sector=raw["sector"], cube_id=raw["cube_id"], mass_code=raw["mass_code"],
                    systems=dict(raw.get("systems", {})), empty=bool(raw.get("empty", False)),
                )
            except KeyError:
                logger.warning("Skipping malformed saved cube entry: %r", raw)
                continue
            try:
                entry.walker.restore(WalkerSnapshot(
                    seed=raw.get("walker_seed"), current=raw.get("walker_current"),
                    visited=raw.get("walker_visited", []),
                ))
            except Exception:
                logger.exception("Failed to restore walker for cube %s", entry.key)
            if entry.walker.current is None:
                entry.walker.set_seed(entry.seed_name())
            cubes.append(entry)
        self._cubes = cubes
        self._current_index = snap.current_index if 0 <= snap.current_index < len(self._cubes) else (
            0 if self._cubes else -1
        )
