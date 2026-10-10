"""
Reads recent journal files so Missions mode's state survives EDMC restarts.

`read_backlog(since)` replays every journal modified after a given date and
collects, per commander:
- accepted missions (all of them; which are active is decided later)
- bounty and combat-bond kills (to estimate kill progress)
- ids of missions the game redirected (the authoritative "objective done" signal)
- Community Goal progress
- cargo mission progress (CargoDepot: collected and delivered so far)
- which missions are still active at the end of the journals (see below)

The game lists the active missions only in its login "Missions" event, so that is the authoritative source. Restarting
EDMC mid-game gives no such event, so the active set is also worked out from the journals: start from the newest
"Missions" event, add each MissionAccepted after it and remove each MissionCompleted, MissionAbandoned and
MissionFailed. A mission that expired without a journal entry stays in that set until the next login corrects it.

A missing journal folder, an unreadable file or a malformed line never
raises: you get whatever could be read.
"""
from __future__ import annotations

import datetime as dt
import json
import logging
import os
from dataclasses import dataclass, field
from typing import Any, Callable, Iterator

from config import appname, config

plugin_name = os.path.basename(os.path.dirname(__file__))
logger = logging.getLogger(f"{appname}.{plugin_name}")


@dataclass
class Backlog:
    accepted: dict[str, dict[int, dict]] = field(default_factory=dict)
    """cmdr -> {mission id -> MissionAccepted event}"""
    bounties: dict[str, list[dict]] = field(default_factory=dict)
    """cmdr -> Bounty events, in journal order"""
    redirected: dict[str, set[int]] = field(default_factory=dict)
    """cmdr -> mission ids that were redirected"""
    redirect_targets: dict[str, dict[int, dict]] = field(default_factory=dict)
    """cmdr -> {mission id -> {"station", "system"}}: the new turn-in place,
    when the redirect named one."""
    goals: dict[str, dict[int, dict]] = field(default_factory=dict)
    """cmdr -> {CGID -> newest CurrentGoals entry seen}"""
    cargo: dict[str, dict[int, dict]] = field(default_factory=dict)
    """cmdr -> {mission id -> newest CargoDepot event}: collect / delivery progress of cargo missions"""
    active_ids: dict[str, set[int]] = field(default_factory=dict)
    """cmdr -> ids of the missions the journals leave active. Only commanders with a Missions or MissionAccepted
    event in the scanned files are present."""


def _journal_folder() -> str:
    # config.get_str is the current EDMC API; older EDMC exposes config.get.
    getter = getattr(config, "get_str", None) or config.get  # type: ignore[attr-defined]
    return getter("journaldir") or config.default_journal_dir or ""


def _files_changed_since(day: dt.date) -> list[str]:
    """Journal files modified after the end of `day` (UTC), oldest first."""
    folder = _journal_folder()
    if not folder:
        # No configured folder and no EDMC default (common on Linux).
        return []
    cutoff = (dt.datetime(day.year, day.month, day.day, tzinfo=dt.timezone.utc)
              + dt.timedelta(days=1)).timestamp()
    found: list[tuple[float, str]] = []
    try:
        with os.scandir(folder) as entries:
            for entry in entries:
                if not entry.name.endswith(".log") or not entry.is_file():
                    continue
                modified = entry.stat().st_mtime
                if modified >= cutoff:
                    found.append((modified, entry.path))
    except OSError:
        logger.warning(f"Could not list journal folder {folder}")
        return []
    found.sort()
    logger.debug(f"Found {len(found)} journal files to scan")
    return [path for _modified, path in found]


def _lines_as_events(path: str) -> Iterator[dict[str, Any]]:
    try:
        with open(path, encoding="utf8", errors="replace") as handle:
            for line in handle:
                try:
                    event = json.loads(line)
                except ValueError:
                    continue
                if isinstance(event, dict):
                    yield event
    except OSError:
        logger.warning(f"Failed to read File {path}. Skipping...")


def _take_accepted(log: Backlog, cmdr: str, event: dict) -> None:
    log.accepted.setdefault(cmdr, {})[event["MissionID"]] = event
    log.active_ids.setdefault(cmdr, set()).add(event["MissionID"])


def _take_bounty(log: Backlog, cmdr: str, event: dict) -> None:
    log.bounties.setdefault(cmdr, []).append(event)


def _take_redirect(log: Backlog, cmdr: str, event: dict) -> None:
    mission_id = event["MissionID"]
    log.redirected.setdefault(cmdr, set()).add(mission_id)
    station = event.get("NewDestinationStation")
    system = event.get("NewDestinationSystem")
    if station or system:
        log.redirect_targets.setdefault(cmdr, {})[mission_id] = {
            "station": station or "", "system": system or ""}


def _take_goals(log: Backlog, cmdr: str, event: dict) -> None:
    known = log.goals.setdefault(cmdr, {})
    for goal in event.get("CurrentGoals", []):
        goal_id = goal.get("CGID")
        if goal_id is not None:
            known[goal_id] = goal


def _take_cargo_depot(log: Backlog, cmdr: str, event: dict) -> None:
    log.cargo.setdefault(cmdr, {})[event["MissionID"]] = event


def _take_missions(log: Backlog, cmdr: str, event: dict) -> None:
    """The login list is authoritative: it replaces whatever was worked out before it."""
    log.active_ids[cmdr] = {int(m["MissionID"]) for m in event.get("Active", [])}


def _take_finished(log: Backlog, cmdr: str, event: dict) -> None:
    log.active_ids.setdefault(cmdr, set()).discard(event["MissionID"])


_TAKERS: dict[str, Callable[[Backlog, str, dict], None]] = {
    "MissionAccepted": _take_accepted,
    "Missions": _take_missions,
    "CargoDepot": _take_cargo_depot,
    "MissionCompleted": _take_finished,
    "MissionAbandoned": _take_finished,
    "MissionFailed": _take_finished,
    "Bounty": _take_bounty,
    "FactionKillBond": _take_bounty,   # a combat-zone kill; counts toward massacre missions like a bounty
    "MissionRedirected": _take_redirect,
    "CommunityGoal": _take_goals,
}


def read_backlog(since: dt.date) -> Backlog:
    """Replay every journal modified after `since` and collect what Missions
    mode needs.

    The accepted missions found here are not all active: the game's login
    "Missions" event lists the active ids, and `ActiveMissions` intersects
    the two."""
    log = Backlog()
    for path in _files_changed_since(since):
        cmdr = ""
        for event in _lines_as_events(path):
            kind = event.get("event")
            if kind == "Commander":
                cmdr = str(event.get("Name", cmdr))
                continue
            taker = _TAKERS.get(kind)
            if taker is None:
                continue
            try:
                taker(log, cmdr, event)
            except (KeyError, TypeError, AttributeError):
                continue  # an entry missing a field we need - skip it
    return log
