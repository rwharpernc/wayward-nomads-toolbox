"""
A generic view of ALL active missions, of any type — not just the
kill-count missions kill_missions.py specializes in. It backs the "All
Missions" view: a broad overview of everything currently accepted (name,
giver, destination, reward, time left) rather than kill-stacking math.
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Optional

from config import appname

from . import active_missions, kill_tracker, mission_types
from .notifier import Notifier

plugin_name = os.path.basename(os.path.dirname(__file__))
logger = logging.getLogger(f"{appname}.{plugin_name}")


@dataclass
class MissionSummary:
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

    @classmethod
    def from_event(cls, event: dict) -> "MissionSummary":
        supplied = mission_types.needs_commodity_supply(event)
        commodity = event.get("Commodity_Localised", "")
        return cls(
            id=event["MissionID"],
            name=_title_of(event),
            source_faction=event.get("Faction", "?"),
            destination_system=event.get("DestinationSystem", ""),
            destination_station=event.get("DestinationStation", ""),
            reward=event.get("Reward", 0),
            is_wing=event.get("Wing", False),
            expiry=event.get("Expiry", ""),
            accepted_at=event.get("timestamp", ""),
            category=mission_types.classify(event),
            is_illegal=mission_types.is_illegal(event),
            commodity=commodity if mission_types.is_mining_mission(event) else "",
            needed_commodity=commodity if supplied else "",
            needed_commodity_count=event.get("Count", 0) if supplied else 0,
        )


def _title_of(event: dict) -> str:
    localised = event.get("LocalisedName")
    if localised:
        return localised
    # LocalisedName is rarely missing; internal names look like
    # "Mission_Courier_Boom", which reads better as "Courier Boom".
    raw = event.get("Name", "Mission")
    return raw.replace("Mission_", "").replace("_", " ").strip() or "Mission"


class AllMissionsView:
    def __init__(self, source: active_missions.ActiveMissions) -> None:
        self.changed = Notifier()
        self.missions: Optional[dict[int, MissionSummary]] = None
        """The current commander's active missions, or None if unknown."""
        source.changed.connect(self._on_active_missions)
        kill_tracker.kill_data_changed_listeners.append(self.refresh)

    def _on_active_missions(self, active: Optional[dict[int, dict]]) -> None:
        if active is None:
            self.missions = None
            self.changed.notify(None)
            return
        # Colonisation missions are dropped entirely (not just recategorized)
        # per user preference; every other active mission is included.
        self.missions = {mission_id: MissionSummary.from_event(event)
                         for mission_id, event in active.items()
                         if not mission_types.is_colonisation_mission(event)}
        logger.info(f"All-missions view tracking {len(self.missions)} active mission(s)")
        self.changed.notify(self.missions)

    def refresh(self) -> None:
        """Tell subscribers again (e.g. after a live MissionRedirected), so
        missions_ui.py's per-mission Pending/Complete status and drop-off
        location - read live from kill_tracker when drawn, not stored here -
        redraw without waiting for the mission set to change."""
        if self.missions is not None:
            self.changed.notify(self.missions)


view = AllMissionsView(active_missions.tracker)
