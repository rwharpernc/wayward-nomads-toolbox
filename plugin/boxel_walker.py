"""
Mode-agnostic "advance on jump" state machine for boxel-survey walking.

BoxelWalker currently drives Boxel Survey only. It's kept separate from
boxel.py (pure sequence math) and from boxel_survey.py (EDMC wiring) so the
same advance/visited-tracking/persistence machinery could be reused for a
future waypoint route mode without duplicating it.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from typing import List, Optional, Set

from config import appname

from . import boxel

plugin_name = os.path.basename(os.path.dirname(__file__))
logger = logging.getLogger(f"{appname}.{plugin_name}")

# Hard cap on how many candidates advance() will silently skip past when
# avoiding already-visited systems, so a corrupted/oversized visited set
# can't spin the sequence forward forever.
MAX_SKIP_STEPS = 1000


@dataclass
class WalkerSnapshot:
    """Serializable snapshot of a BoxelWalker's state, for persistence."""

    seed: Optional[str]
    current: Optional[str]
    visited: List[str] = field(default_factory=list)


class BoxelWalker:
    """Walks the procedural sequence of a single boxel, tracking visits."""

    def __init__(self) -> None:
        self._parsed: Optional[boxel.ProcSystemName] = None
        self._seed: Optional[str] = None
        self._visited: Set[str] = set()

    def set_seed(self, name: str) -> None:
        """Start (or restart) a survey at the given system name."""
        parsed = boxel.parse_system_name(name)
        if parsed is None:
            raise ValueError(f"{name!r} is not a recognized procedural boxel name")
        self._seed = name
        self._parsed = parsed

    @property
    def current(self) -> Optional[str]:
        return self._parsed.format() if self._parsed else None

    def advance(self, *, skip_visited: bool = True) -> Optional[str]:
        """Move to the next candidate name, optionally skipping visited ones."""
        if self._parsed is None:
            return None
        for _ in range(MAX_SKIP_STEPS):
            self._parsed = boxel.next_in_sequence(self._parsed)
            candidate = self._parsed.format()
            if not skip_visited or candidate not in self._visited:
                return candidate
        logger.warning("advance(): hit MAX_SKIP_STEPS without finding an unvisited candidate")
        return self._parsed.format()

    def retreat(self) -> Optional[str]:
        """
        Move to the previous candidate name, or raise ValueError if already at
        the start of the sequence (<N1>/<N2> would go negative).
        """
        if self._parsed is None:
            return None
        self._parsed = boxel.previous_in_sequence(self._parsed)
        return self._parsed.format()

    def mark_visited(self, system_name: str) -> None:
        self._visited.add(system_name)

    def on_jump(self, system_name: str, *, skip_visited: bool = True) -> Optional[str]:
        """
        Handle arrival at system_name (from an FSDJump/Location journal event).

        Always records the arrival as visited. If it matches the current
        target, advances to the next candidate and returns it; otherwise
        returns None — the commander jumped somewhere off the planned
        sequence, so the target doesn't change.
        """
        self.mark_visited(system_name)
        if self._parsed is not None and system_name == self._parsed.format():
            return self.advance(skip_visited=skip_visited)
        return None

    def snapshot(self) -> WalkerSnapshot:
        return WalkerSnapshot(seed=self._seed, current=self.current, visited=sorted(self._visited))

    def restore(self, snapshot: WalkerSnapshot) -> None:
        """Restore from a previously saved snapshot. The saved position wins over the seed."""
        self._visited = set(snapshot.visited)
        self._seed = snapshot.seed
        target = snapshot.current or snapshot.seed
        if not target:
            return
        parsed = boxel.parse_system_name(target)
        if parsed is not None:
            self._parsed = parsed
        else:
            logger.warning("restore(): saved target %r no longer parses; state not restored", target)
