"""
Filters the active mission set down to massacre missions — both ship-based
("Mission_Massacre...") and on-foot settlement missions (names containing
"OnFoot") — and computes estimated kill progress per mission.
"""
import logging
import os
from dataclasses import dataclass
from typing import Callable, Optional

from config import appname

from . import kill_tracker, mission_repository, mission_types

plugin_name = os.path.basename(os.path.dirname(__file__))
logger = logging.getLogger(f"{appname}.{plugin_name}")


@dataclass
class MassacreMission:
    """One accepted massacre mission, ship or on-foot."""
    id: int
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
    accepted_at: str
    """ISO timestamp of the MissionAccepted event (sortable as a string)"""


def __build_from_event(event: dict) -> MassacreMission:
    return MassacreMission(
        id=event["MissionID"],
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
        accepted_at=event.get("timestamp", ""),
    )


massacre_mission_listeners: list[Callable[[Optional[dict[int, MassacreMission]]], None]] = []

_massacre_mission_store: Optional[dict[int, MassacreMission]] = None
"""
Massacre missions of the current CMDR, or None while that CMDR's active
mission list is unknown (no "Missions" login event seen yet).
"""


def compute_progress(missions: list[MassacreMission]) -> dict[int, int]:
    """
    Estimate kills done per mission for the current CMDR.

    Rules mirroring in-game behaviour:
    - A MissionRedirected event marks a mission fully complete.
    - Each qualifying kill (Bounty with matching VictimFaction, matching
      ground/space arena, after the mission was accepted) counts toward the
      EARLIEST unfinished mission of EACH distinct mission-giver faction —
      this is what makes massacre stacking work.
    """
    cmdr = kill_tracker.current_cmdr
    redirected = kill_tracker.get_redirected(cmdr)
    bounties = kill_tracker.get_bounties(cmdr)

    progress: dict[int, int] = {}
    open_missions: list[MassacreMission] = []
    for mission in missions:
        if mission.id in redirected:
            progress[mission.id] = mission.count
        else:
            progress[mission.id] = 0
            open_missions.append(mission)

    if not open_missions:
        return progress

    # Group open missions by mission giver, oldest first
    by_giver: dict[str, list[MassacreMission]] = {}
    for mission in sorted(open_missions, key=lambda m: m.accepted_at):
        by_giver.setdefault(mission.source_faction, []).append(mission)

    for bounty in bounties:
        victim_faction = bounty.get("VictimFaction")
        if victim_faction is None:
            continue
        bounty_time = bounty.get("timestamp", "")
        ground_kill = kill_tracker.is_ground_kill(bounty)

        for giver_missions in by_giver.values():
            for mission in giver_missions:
                if (mission.target_faction == victim_faction
                        and mission.is_ground == ground_kill
                        and progress[mission.id] < mission.count
                        and bounty_time >= mission.accepted_at):
                    progress[mission.id] += 1
                    break  # one kill counts once per mission giver

    return progress


def __handle_new_missions_state(data: Optional[dict[int, dict]]):
    """
    Callback used by the Mission Repository when the active mission set
    changes (including commander switches). Filters out non-massacre
    missions and re-emits. None means "active missions unknown for the
    current CMDR" and is passed through unchanged.
    """
    global _massacre_mission_store

    if data is None:
        logger.info("Active mission list unknown for the current CMDR")
        _massacre_mission_store = None
        __emit()
        return

    logger.info(f"Received a new Missions State with {len(data)} Missions.")
    _massacre_mission_store = {}
    for mission_event in data.values():
        if mission_types.is_massacre_shaped(mission_event):
            mission = __build_from_event(mission_event)
            _massacre_mission_store[mission.id] = mission
            arena = "ground" if mission.is_ground else "space"
            logger.info(
                f"Tracking {arena} mission {mission_event.get('Name')} "
                f"(target: {mission.target_faction}, kills: {mission.count})")
        else:
            # Logged so unrecognized kill-mission types can be reported
            logger.info(f"Ignoring non-massacre mission {mission_event.get('Name')}")
    logger.info(f"{len(_massacre_mission_store)} of those are Massacre Missions")

    __emit()


def refresh():
    """Re-emit the current store (e.g. after new kill data arrived)."""
    if _massacre_mission_store is not None:
        __emit()


def __emit():
    for listener in massacre_mission_listeners:
        listener(_massacre_mission_store)


mission_repository.active_missions_changed_event_listeners.append(__handle_new_missions_state)
kill_tracker.kill_data_changed_listeners.append(refresh)
