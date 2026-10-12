"""
Catching the Boxel Survey log up from recent journals, for the scans made while EDMC was closed.

EDMC only passes a plugin the events that happen while it runs, so a system scanned with it closed is missing from the survey
log (the notable bodies in it, and its scanned count). The journals have every `Scan`, so this reads the recent ones and replays
them into the log. The game's journals are only ever read.

Replaying must not count a scan twice, and the log's "bodies scanned" is a running count with no record of which bodies it
holds. So the rule is deliberately conservative:
- the notable finds (Earthlike, water and ammonia worlds, terraformables, biological signals) are keyed by body name and merge
  harmlessly, so they are recovered for every system, however many times this runs;
- the scanned count is only set for a system the log did not have before this run, counting each distinct body once; a system
  already in the log keeps the count it has.
Run twice, the second pass adds nothing: the systems it created the first time are now "already in the log".
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

from . import journal_files, survey_log

logger = logging.getLogger(__name__)

CATCH_UP_DAYS = 14
_WANTED = journal_files.event_pattern("Commander", "LoadGame", "Location", "FSDJump", "CarrierJump", "Scan",
                                      "FSSBodySignals", "SAASignalsFound")
_SYSTEM_EVENTS = frozenset({"Location", "FSDJump", "CarrierJump"})
_SCAN_EVENTS = frozenset({"Scan", "FSSBodySignals", "SAASignalsFound"})

Replay = Tuple[str, Dict[str, Any]]   # (system the event happened in, the journal entry)


@dataclass
class CatchUp:
    systems_added: int = 0
    notable_found: int = 0
    scans_seen: int = 0


def read_since(cmdr: str, since_epoch: float, folder: Optional[str] = None) -> List[Replay]:
    """The scan and signal events `cmdr` made in journals modified since `since_epoch`, oldest first, each with the system it
    happened in. A `Scan` names its system; the signal events do not, so the system is followed from the jumps and `Location`
    events before them. A file says whose events follow in its `Commander` / `LoadGame` lines."""
    wanted = cmdr.strip().casefold()
    found: List[Replay] = []
    if not wanted:
        return found
    for path in journal_files.files_modified_since(since_epoch, folder):
        current = ""
        system = ""
        for entry in journal_files.read_events(path, _WANTED):
            kind = entry.get("event")
            if kind == "Commander" and entry.get("Name"):
                current = str(entry["Name"]).strip().casefold()
            elif kind == "LoadGame" and entry.get("Commander"):
                current = str(entry["Commander"]).strip().casefold()
            elif current != wanted:
                continue
            elif kind in _SYSTEM_EVENTS and entry.get("StarSystem"):
                system = str(entry["StarSystem"])
            elif kind in _SCAN_EVENTS:
                named = str(entry.get("StarSystem") or system)
                if named:
                    found.append((named, entry))
    return found


def apply(log: survey_log.SurveyLog, events: List[Replay],
          boxel_key_for: Callable[[str], Optional[str]] = lambda system: None) -> CatchUp:
    """Replay `events` into `log` by the rule in the module docstring. Returns what it recovered."""
    result = CatchUp()
    known: Set[str] = {system for system, _entry in events if log.has_system(system)}   # in the log before this run
    counted: Set[Tuple[str, str]] = set()
    for system, entry in events:
        kind = entry.get("event")
        body = entry.get("BodyName")
        if not body:
            continue
        result.scans_seen += 1
        seen_at = str(entry.get("timestamp") or "") or None
        was_new = not log.has_system(system)
        notable_before = _notable_count(log, system)
        if kind == "Scan":
            first_time = (system, body) not in counted
            counted.add((system, body))
            log.record_scan(
                system, body, boxel_key=boxel_key_for(system), planet_class=entry.get("PlanetClass"),
                terraform_state=entry.get("TerraformState") or None, distance_ls=entry.get("DistanceFromArrivalLS"),
                count=system not in known and first_time, seen_at=seen_at)
        else:
            bio = 0
            for signal in entry.get("Signals") or []:
                if isinstance(signal, dict) and signal.get("Type") == survey_log.BIO_SIGNAL_TYPE:
                    bio += int(signal.get("Count") or 0)
            log.record_signals(system, body, boxel_key=boxel_key_for(system), bio_signal_count=bio, seen_at=seen_at)
        if was_new and log.has_system(system):
            result.systems_added += 1
        result.notable_found += max(0, _notable_count(log, system) - notable_before)
    return result


def _notable_count(log: survey_log.SurveyLog, system: str) -> int:
    entry = log._systems.get(system)     # noqa: SLF001 - same package; the log keeps no public per-system accessor
    return len(entry.notable_bodies) if entry else 0
