"""
Which missions each commander has accepted, and which of those are active
right now.

Each commander gets their own roster, so one commander's missions can never
show up in another's view. Subscribers to `ActiveMissions.changed` are told
about the *focused* commander's active missions whenever they change, or
`None` while that commander's active set is still unknown (the game's
"Missions" login event, which lists the active ids, hasn't been seen yet).

The module keeps one shared tracker, `tracker`; feature modules subscribe to
`tracker.changed` and missions.py feeds it from the journal.
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from typing import Iterable, Mapping, Optional

from config import appname

from .notifier import Notifier

plugin_name = os.path.basename(os.path.dirname(__file__))
logger = logging.getLogger(f"{appname}.{plugin_name}")


@dataclass
class _Roster:
    """One commander's missions."""
    accepted: dict[int, dict] = field(default_factory=dict)
    """Every MissionAccepted event known for them, active or not."""
    active: dict[int, dict] = field(default_factory=dict)
    synced: bool = False
    """True once their "Missions" login event has been processed."""


class ActiveMissions:
    def __init__(self) -> None:
        self.changed = Notifier()
        self._rosters: dict[str, _Roster] = {}
        self._focus: Optional[str] = None

    # --- reading -------------------------------------------------------------

    @property
    def commander(self) -> Optional[str]:
        return self._focus

    def snapshot(self) -> Optional[dict[int, dict]]:
        """The focused commander's active missions (id -> MissionAccepted
        event), or None while that set is unknown."""
        roster = self._rosters.get(self._focus) if self._focus else None
        if roster is None or not roster.synced:
            return None
        return roster.active

    # --- feeding ---------------------------------------------------------------

    def load_history(self, accepted_by_cmdr: Mapping[str, Mapping[int, dict]],
                     active_ids_by_cmdr: Optional[Mapping[str, Iterable[int]]] = None) -> None:
        """Start over from missions found in old journals. Without `active_ids_by_cmdr`, nothing counts as
        active until each commander's login event arrives. With it (the set the journals leave active), a
        commander's missions show straight away, which is what restarting EDMC mid-game needs because the game
        sends no login event then. The login event, when it comes, replaces this with the authoritative list."""
        self._rosters = {cmdr: _Roster(accepted=dict(events)) for cmdr, events in accepted_by_cmdr.items()}
        for cmdr, ids in (active_ids_by_cmdr or {}).items():
            roster = self._rosters.setdefault(cmdr, _Roster())
            roster.active = {i: roster.accepted[i] for i in ids if i in roster.accepted}
            roster.synced = True
        self._focus = None

    def switch_to(self, cmdr: str) -> None:
        """Make `cmdr` the focused commander; subscribers immediately get
        that commander's data."""
        if not cmdr or cmdr == self._focus:
            return
        logger.info(f"Active commander is now CMDR {cmdr}")
        self._focus = cmdr
        self._announce()

    def sync_login(self, cmdr: str, mission_ids: list[int]) -> None:
        """The login "Missions" event: these ids are the active ones. Only
        ids whose acceptance we have seen can be shown."""
        if not cmdr:
            logger.error("Missions event without a CMDR name - ignoring")
            return
        roster = self._rosters.setdefault(cmdr, _Roster())
        roster.active = {}
        for mission_id in mission_ids:
            event = roster.accepted.get(mission_id)
            if event is None:
                logger.warning(f"Mission {mission_id} is active for CMDR {cmdr} but was not "
                               f"found in the scanned journals")
            else:
                roster.active[mission_id] = event
        roster.synced = True
        self._focus = cmdr
        self._announce()

    def accept(self, cmdr: str, event: dict) -> None:
        if not cmdr:
            logger.error("MissionAccepted without a CMDR name - ignoring")
            return
        mission_id = event["MissionID"]
        logger.info(f"CMDR {cmdr} accepted mission {mission_id}")
        roster = self._rosters.setdefault(cmdr, _Roster())
        roster.accepted[mission_id] = event
        roster.active[mission_id] = event
        if cmdr == self._focus:
            self._announce()

    def finish(self, cmdr: str, mission_id: int) -> None:
        """A mission was handed in, abandoned or failed."""
        roster = self._rosters.get(cmdr) if cmdr else None
        if roster is None:
            return
        roster.accepted.pop(mission_id, None)
        if roster.active.pop(mission_id, None) is None:
            return
        logger.info(f"Mission {mission_id} of CMDR {cmdr} has been removed")
        if cmdr == self._focus:
            self._announce()

    def _announce(self) -> None:
        self.changed.notify(self.snapshot())


tracker = ActiveMissions()
