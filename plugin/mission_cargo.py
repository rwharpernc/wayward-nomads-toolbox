"""
Cargo mission progress: how much of a collect or delivery mission's cargo has been collected and delivered.

The journal writes `CargoDepot` whenever you collect or hand in mission cargo (and when a wing-mate does), with the
mission's `ItemsCollected`, `ItemsDelivered` and `TotalItemsToDeliver`. The newest event per mission is the current
state, so the journal scan at start-up only has to keep the last one it sees for each.

The Missions view uses it to show how far a mission is and to take collected cargo off the "commodities needed" total.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

from .notifier import Notifier


@dataclass(frozen=True)
class CargoProgress:
    collected: int
    delivered: int
    total: int

    @property
    def still_to_collect(self) -> int:
        """Units not yet picked up (delivering counts as having collected them)."""
        return max(0, self.total - max(self.collected, self.delivered))


def from_event(entry: Dict[str, Any]) -> Optional[CargoProgress]:
    """A `CargoDepot` event -> progress, or None if it lacks a usable total."""
    total, collected, delivered = (entry.get(k) for k in ("TotalItemsToDeliver", "ItemsCollected", "ItemsDelivered"))
    if not all(isinstance(v, int) and not isinstance(v, bool) for v in (total, collected, delivered)) or total <= 0:
        return None
    return CargoProgress(collected=collected, delivered=delivered, total=total)


class MissionCargo:
    def __init__(self) -> None:
        self.changed = Notifier()
        self._progress: Dict[str, Dict[int, CargoProgress]] = {}

    def initialize(self, events_by_cmdr: Dict[str, Dict[int, Dict[str, Any]]]) -> None:
        """Seed from the journal scan: {commander: {mission id: newest CargoDepot event}}."""
        self._progress = {}
        for cmdr, by_mission in events_by_cmdr.items():
            for mission_id, entry in by_mission.items():
                progress = from_event(entry)
                if progress is not None:
                    self._progress.setdefault(cmdr, {})[mission_id] = progress

    def update(self, cmdr: str, entry: Dict[str, Any]) -> None:
        mission_id, progress = entry.get("MissionID"), from_event(entry)
        if not cmdr or not isinstance(mission_id, int) or progress is None:
            return
        if self._progress.setdefault(cmdr, {}).get(mission_id) != progress:
            self._progress[cmdr][mission_id] = progress
            self.changed.notify()

    def forget(self, cmdr: str, mission_id: int) -> None:
        if self._progress.get(cmdr, {}).pop(mission_id, None) is not None:
            self.changed.notify()

    def get(self, cmdr: Optional[str], mission_id: int) -> Optional[CargoProgress]:
        return self._progress.get(cmdr or "", {}).get(mission_id)


tracker = MissionCargo()
