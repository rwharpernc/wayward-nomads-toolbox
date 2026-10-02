"""
Holds mission state strictly separated per CMDR and emits an event whenever
the active mission set of the *current* CMDR changes.

Every mutation is keyed by the CMDR the journal event belongs to, so one
commander's missions can never leak into another commander's view. Listeners
receive either the current CMDR's active missions, or None when no
"Missions" login event has been seen for that CMDR yet (i.e. we don't know
their active set).
"""
import logging
import os
from typing import Callable, Optional

from config import appname

plugin_name = os.path.basename(os.path.dirname(__file__))
logger = logging.getLogger(f"{appname}.{plugin_name}")

# Callback: active missions of the current CMDR as dict[mission_id,
# MissionAccepted event], or None when the current CMDR's active mission
# list is unknown.
active_missions_changed_event_listeners: list[
    Callable[[Optional[dict[int, dict]]], None]] = []


class MissionRepository:
    """
    Built from historic journal data (all CMDRs) plus per-CMDR
    "Missions"-events, which list the mission IDs actually active for the
    CMDR that just logged in.
    """

    def __init__(self, mission_store: dict[str, dict[int, dict]]):
        self._cmdr: Optional[str] = None
        self._mission_store = mission_store
        """CMDR -> (Mission ID -> MissionAccepted event), active or not"""
        self._active_by_cmdr: dict[str, dict[int, dict]] = {}
        """CMDR -> their currently active missions"""
        self._initialized_cmdrs: set[str] = set()
        """CMDRs for whom a "Missions" login event has been processed"""

    @property
    def current_cmdr(self) -> Optional[str]:
        return self._cmdr

    @property
    def active_missions(self) -> Optional[dict[int, dict]]:
        """Active missions of the current CMDR, or None if unknown."""
        if self._cmdr is None or self._cmdr not in self._initialized_cmdrs:
            return None
        return self._active_by_cmdr.get(self._cmdr, {})

    def set_current_cmdr(self, cmdr: str):
        """
        Called for every journal event carrying a CMDR name. On a commander
        switch the UI is immediately re-fed with *that* commander's data.
        """
        if not cmdr or cmdr == self._cmdr:
            return
        logger.info(f"Active commander is now CMDR {cmdr}")
        self._cmdr = cmdr
        self.__emit_changed()

    def notify_about_active_mission_uuids(self, uuids: list[int], cmdr: str):
        """
        Called when a "Missions"-event arrives (at login). Active missions
        are the intersection of the given IDs and the missions found in the
        journals for this CMDR.
        """
        if not cmdr:
            logger.error("Missions event without a CMDR name - ignoring")
            return

        known_missions = self._mission_store.get(cmdr, {})
        active: dict[int, dict] = {}
        for uuid in uuids:
            if uuid in known_missions:
                active[uuid] = known_missions[uuid]
            else:
                logger.warning(
                    f"Mission {uuid} is active for CMDR {cmdr} but was not "
                    f"found in the scanned journals")

        self._active_by_cmdr[cmdr] = active
        self._initialized_cmdrs.add(cmdr)
        self._cmdr = cmdr
        self.__emit_changed()

    def notify_about_new_mission_accepted(self, mission: dict, cmdr: str):
        if not cmdr:
            logger.error("MissionAccepted without a CMDR name - ignoring")
            return
        logger.info(
            f"CMDR {cmdr} accepted mission {mission['MissionID']}")
        self._mission_store.setdefault(cmdr, {})[mission["MissionID"]] = mission
        self._active_by_cmdr.setdefault(cmdr, {})[mission["MissionID"]] = mission
        if cmdr == self._cmdr:
            self.__emit_changed()

    def notify_about_mission_gone(self, mission_uuid: int, cmdr: str):
        """Called when a mission is handed in, abandoned or failed."""
        if not cmdr:
            return
        self._mission_store.get(cmdr, {}).pop(mission_uuid, None)
        active = self._active_by_cmdr.get(cmdr, {})
        if mission_uuid not in active:
            return
        logger.info(f"Mission {mission_uuid} of CMDR {cmdr} has been removed")
        del active[mission_uuid]
        if cmdr == self._cmdr:
            self.__emit_changed()

    def __emit_changed(self):
        data = self.active_missions
        for listener in active_missions_changed_event_listeners:
            listener(data)


mission_repository: Optional[MissionRepository] = None


def set_new_repo(missions: dict[str, dict[int, dict]]):
    global mission_repository
    mission_repository = MissionRepository(missions)


def set_active_uuids(uuids: list[int], cmdr: str):
    if mission_repository is not None:
        mission_repository.notify_about_active_mission_uuids(uuids, cmdr)


def set_current_cmdr(cmdr: str):
    if mission_repository is not None:
        mission_repository.set_current_cmdr(cmdr)
