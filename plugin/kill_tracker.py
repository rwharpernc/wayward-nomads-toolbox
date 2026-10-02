"""
Tracks per-mission completion evidence, keyed by CMDR and independent of
which specific missions are currently active:

- Bounty events: fired for ship kills AND on-foot kills of wanted targets.
  The VictimFaction field tells us which faction the victim belonged to.
  Used by massacre_state.py to estimate kill-stacking progress.
- MissionRedirected events: fired when a mission's objective is complete
  and the game sends you back to turn it in. This is the authoritative
  completion signal for any mission type, not just massacre - missions_ui.py
  uses plain membership in `_redirected` as the "Pending"/"Complete" status
  shown on the All Missions pages, and NewDestinationStation/System (when
  present) as the drop-off location to show once complete.
- The periodic "Missions" event's Complete[] array is a second completion
  signal for the same concept, folded into the same `_redirected` set (see
  mark_complete): a mission can be done-but-not-yet-redirected (e.g. right
  after a relog, before the game re-sends MissionRedirected), and this
  event tells us that authoritatively without waiting for the redirect.
"""
import logging
import os
from typing import Callable, Optional

from config import appname

plugin_name = os.path.basename(os.path.dirname(__file__))
logger = logging.getLogger(f"{appname}.{plugin_name}")

current_cmdr: Optional[str] = None

_bounties: dict[str, list[dict]] = {}
_redirected: dict[str, set[int]] = {}
_redirect_destinations: dict[str, dict[int, dict]] = {}
"""CMDR -> (Mission ID -> {"station": ..., "system": ...}), only present
when the MissionRedirected event carried a new turn-in location."""

# Notified (no arguments) whenever kill data changes and progress should be
# recomputed.
kill_data_changed_listeners: list[Callable[[], None]] = []


def initialize(bounties_by_cmdr: dict[str, list[dict]],
               redirected_by_cmdr: dict[str, set[int]],
               redirect_destinations_by_cmdr: Optional[dict[str, dict[int, dict]]] = None):
    """Seed the tracker with data recovered from the journal scan."""
    global _bounties, _redirected, _redirect_destinations
    _bounties = bounties_by_cmdr
    _redirected = redirected_by_cmdr
    _redirect_destinations = redirect_destinations_by_cmdr or {}


def set_current_cmdr(cmdr: str):
    global current_cmdr
    if cmdr:
        current_cmdr = cmdr


def get_bounties(cmdr: Optional[str]) -> list[dict]:
    if cmdr is None:
        return []
    return _bounties.get(cmdr, [])


def get_redirected(cmdr: Optional[str]) -> set[int]:
    if cmdr is None:
        return set()
    return _redirected.get(cmdr, set())


def get_redirect_destination(cmdr: Optional[str], mission_id: int) -> Optional[dict]:
    """The redirect's new turn-in location ({"station", "system"}), or None
    if this mission was never redirected or the event carried no
    destination change."""
    if cmdr is None:
        return None
    return _redirect_destinations.get(cmdr, {}).get(mission_id)


def add_bounty(cmdr: str, entry: dict):
    if not cmdr:
        return
    _bounties.setdefault(cmdr, []).append(entry)
    __emit_changed()


def add_redirect(cmdr: str, entry: dict):
    if not cmdr:
        return
    mission_id = entry["MissionID"]
    logger.info(f"Mission {mission_id} redirected -> objective complete")
    _redirected.setdefault(cmdr, set()).add(mission_id)
    new_station = entry.get("NewDestinationStation")
    new_system = entry.get("NewDestinationSystem")
    if new_station or new_system:
        _redirect_destinations.setdefault(cmdr, {})[mission_id] = {
            "station": new_station or "",
            "system": new_system or "",
        }
    __emit_changed()


def mark_complete(cmdr: str, mission_ids: set[int]):
    """Folds mission IDs from the "Missions" event's Complete[] array into
    the same completion set MissionRedirected feeds - see the module
    docstring. No destination info to store here (that event carries none),
    so `_redirect_destinations` is untouched."""
    if not cmdr or not mission_ids:
        return
    logger.info(f"Mission(s) {sorted(mission_ids)} reported complete by the Missions event")
    _redirected.setdefault(cmdr, set()).update(mission_ids)
    __emit_changed()


def forget_mission(cmdr: str, mission_id: int):
    """Drop completion state once a mission is handed in / abandoned."""
    if not cmdr:
        return
    _redirected.setdefault(cmdr, set()).discard(mission_id)
    _redirect_destinations.get(cmdr, {}).pop(mission_id, None)


def is_ground_kill(bounty: dict) -> bool:
    """
    Classify a Bounty event as on-foot or ship kill. On-foot victims have
    NPC suit archetypes as their Target (e.g. "suitai_scientist"), whereas
    ship kills carry a ship type (e.g. "anaconda").
    """
    target = str(bounty.get("Target", "")).lower()
    return "suitai" in target or "citizen" in target or target.startswith("suit_")


def __emit_changed():
    for listener in kill_data_changed_listeners:
        listener()
