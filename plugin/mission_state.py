"""
Builds a generic view of ALL active missions, of any type - not just the
kill-count/massacre missions massacre_state.py specializes in. This backs
the "All Missions" view, a broad overview of everything currently accepted
(name, giver, destination, reward, time left) rather than detailed
kill-stacking math.
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
class Mission:
    """One accepted mission of any type."""
    id: int
    name: str
    source_faction: str
    destination_system: str
    destination_station: str
    reward: int
    is_wing: bool
    expiry: str
    """ISO timestamp the mission expires at, or "" if the mission has none."""
    accepted_at: str
    """ISO timestamp of the MissionAccepted event (sortable as a string)"""
    category: str
    """One of the mission_types.CATEGORY_ORDER keys."""
    is_illegal: bool
    commodity: str
    """Target commodity display name - only set for mining missions (see
    mission_types.is_mining_mission), empty otherwise. Other Trade-category
    missions (Collect, Delivery) also carry a Commodity field but don't
    require mining it yourself, so it's deliberately left blank for those
    rather than showing a misleading mining-method hint."""
    needed_commodity: str
    """Commodity display name for missions where it must still be sourced -
    mined or bought/collected (see mission_types.needs_commodity_supply) -
    empty otherwise, including plain Delivery (cargo already in hand from
    acceptance). Independent of `commodity` above: a Collect mission gets
    this field but not `commodity`, since collecting isn't mining. Backs the
    Trade & Mining page's "Commodities needed" summary in missions_ui.py."""
    needed_commodity_count: int
    """Units still needed of `needed_commodity`; 0 when that's empty."""


def __display_name(event: dict) -> str:
    localised = event.get("LocalisedName")
    if localised:
        return localised
    # Fallback for the rare case LocalisedName is missing: internal names
    # look like "Mission_Courier_Boom", turn that into "Courier Boom".
    name = event.get("Name", "Mission")
    return name.replace("Mission_", "").replace("_", " ").strip() or "Mission"


def __build_from_event(event: dict) -> Mission:
    return Mission(
        id=event["MissionID"],
        name=__display_name(event),
        source_faction=event.get("Faction", "?"),
        destination_system=event.get("DestinationSystem", ""),
        destination_station=event.get("DestinationStation", ""),
        reward=event.get("Reward", 0),
        is_wing=event.get("Wing", False),
        expiry=event.get("Expiry", ""),
        accepted_at=event.get("timestamp", ""),
        category=mission_types.classify(event),
        is_illegal=mission_types.is_illegal(event),
        commodity=event.get("Commodity_Localised", "")
        if mission_types.is_mining_mission(event) else "",
        needed_commodity=event.get("Commodity_Localised", "")
        if mission_types.needs_commodity_supply(event) else "",
        needed_commodity_count=event.get("Count", 0)
        if mission_types.needs_commodity_supply(event) else 0,
    )


mission_listeners: list[Callable[[Optional[dict[int, Mission]]], None]] = []
"""Notified with the current CMDR's full mission set, or None if unknown."""

_mission_store: Optional[dict[int, Mission]] = None


def __handle_new_missions_state(data: Optional[dict[int, dict]]):
    """
    Callback used by the Mission Repository when the active mission set
    changes (including commander switches). Colonisation missions are
    dropped entirely (not just recategorized) per user preference; every
    other active mission is included.
    """
    global _mission_store

    if data is None:
        _mission_store = None
        __emit()
        return

    _mission_store = {mission_id: __build_from_event(event)
                      for mission_id, event in data.items()
                      if not mission_types.is_colonisation_mission(event)}
    logger.info(f"All-missions view tracking {len(_mission_store)} active mission(s)")

    __emit()


def __emit():
    for listener in mission_listeners:
        listener(_mission_store)


def refresh():
    """Re-emit the current store (e.g. after a live MissionRedirected event),
    so missions_ui.py's per-mission Pending/Complete status and drop-off
    location - read live from kill_tracker at render time, not stored here -
    redraw with the latest data instead of waiting for the mission set to
    change."""
    if _mission_store is not None:
        __emit()


mission_repository.active_missions_changed_event_listeners.append(__handle_new_missions_state)
kill_tracker.kill_data_changed_listeners.append(refresh)
