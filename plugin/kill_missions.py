"""
The kill-count ("massacre") missions among the active ones — both
ship-based ("Mission_Massacre...") and on-foot settlement missions — and an
estimate of kill progress for each.

`view` follows `active_missions.tracker`: whenever the active set changes it
rebuilds its list and tells its own subscribers (`view.changed`).
"""
from __future__ import annotations

import logging
import os
from collections import defaultdict
from dataclasses import dataclass
from operator import attrgetter
from typing import Optional

from config import appname

from . import active_missions, kill_tracker, mission_types
from .notifier import Notifier

plugin_name = os.path.basename(os.path.dirname(__file__))
logger = logging.getLogger(f"{appname}.{plugin_name}")


@dataclass
class KillMission:
    """One accepted kill-count mission, ship or on foot."""
    id: int
    accepted_at: str
    """ISO timestamp of the MissionAccepted event (sortable as a string)"""
    source_faction: str
    target_faction: str
    target_type: str
    target_system: str
    target_settlement: str
    count: int
    reward: int
    is_wing: bool
    is_ground: bool
    is_illegal: bool

    @classmethod
    def from_event(cls, event: dict) -> "KillMission":
        return cls(
            id=event["MissionID"],
            accepted_at=event.get("timestamp", ""),
            source_faction=event.get("Faction", "?"),
            target_faction=event.get("TargetFaction", "?"),
            target_type=event.get("TargetType", ""),
            target_system=event.get("DestinationSystem", "?"),
            target_settlement=event.get("DestinationSettlement", ""),
            count=event.get("KillCount", 0),
            reward=event.get("Reward", 0),
            is_wing=event.get("Wing", False),
            is_ground=mission_types.is_ground_mission(event),
            is_illegal=mission_types.is_illegal(event),
        )


def estimate_progress(missions: list[KillMission]) -> dict[int, int]:
    """Estimated kills done per mission for the current commander.

    How the game behaves, and so how this counts:
    - A redirected mission is finished.
    - A qualifying kill (a Bounty on the target faction, in the same arena —
      ground or space — and after the mission was accepted) counts toward the
      oldest unfinished mission of *each* mission-giving faction. That is what
      makes massacre stacking work.
    """
    cmdr = kill_tracker.current_cmdr
    redirected = kill_tracker.get_redirected(cmdr)
    done = {m.id: (m.count if m.id in redirected else 0) for m in missions}

    queues: dict[str, list[KillMission]] = defaultdict(list)
    for mission in sorted((m for m in missions if m.id not in redirected), key=attrgetter("accepted_at")):
        queues[mission.source_faction].append(mission)
    if not queues:
        return done

    for bounty in kill_tracker.get_bounties(cmdr):
        victim = bounty.get("VictimFaction")
        if victim is None:
            continue
        when = bounty.get("timestamp", "")
        on_foot = kill_tracker.is_ground_kill(bounty)
        for queue in queues.values():
            credited = next((m for m in queue
                             if m.target_faction == victim and m.is_ground == on_foot
                             and done[m.id] < m.count and when >= m.accepted_at), None)
            if credited is not None:
                done[credited.id] += 1  # one kill counts once per mission giver
    return done


class KillMissionView:
    def __init__(self, source: active_missions.ActiveMissions) -> None:
        self.changed = Notifier()
        self.missions: Optional[dict[int, KillMission]] = None
        """Kill missions of the current commander, or None while their active
        missions are unknown (no login "Missions" event seen yet)."""
        source.changed.connect(self._on_active_missions)
        kill_tracker.kill_data_changed_listeners.append(self.refresh)

    def _on_active_missions(self, active: Optional[dict[int, dict]]) -> None:
        if active is None:
            logger.info("Active mission list unknown for the current CMDR")
            self.missions = None
            self.changed.notify(None)
            return
        logger.info(f"Received a new Missions State with {len(active)} Missions.")
        found: dict[int, KillMission] = {}
        for event in active.values():
            if not mission_types.is_massacre_shaped(event):
                logger.info(f"Ignoring non-massacre mission {event.get('Name')}")
                continue
            mission = KillMission.from_event(event)
            found[mission.id] = mission
            arena = "ground" if mission.is_ground else "space"
            logger.info(f"Tracking {arena} mission {event.get('Name')} "
                        f"(target: {mission.target_faction}, kills: {mission.count})")
        logger.info(f"{len(found)} of those are Massacre Missions")
        self.missions = found
        self.changed.notify(found)

    def refresh(self) -> None:
        """Tell subscribers again (e.g. after new kill data arrived)."""
        if self.missions is not None:
            self.changed.notify(self.missions)


view = KillMissionView(active_missions.tracker)
