"""
Codex Completionist: pure logic (no Tk) for a personal "how many of each
scannable thing have I ever found" tally.

Meant to sit alongside the EDMC-Canonn plugin rather than duplicate it - same
principle as organic_scan.py. That plugin submits codex data to Canonn's cloud;
this module never talks to any network service itself. The galaxy-wide list of
possible entries (what the window's "Not found" tab diffs against) is
Canonn's own catalog, fetched and cached by codex_catalog.py - this module
stays pure and only knows what the commander has actually found.
codex_completionist_panel.py's "View Canonn Codex" link and the per-entry
reference links are the rest of the synergy - point at Canonn's site, don't
reimplement it.

Unlike Discovery/Interdiction/Landing's ephemeral precedent, this DOES
persist across restarts (codex_completionist_state.py) - it's a lifetime
collection record, not a live/transient status, same reasoning
survey_log.py's own notable-finds log already persists.

Follows survey_log.py's/waypoint_route.py's/organic_scan.py's own
`try/except ImportError` fallback for `appname` so this stays genuinely
unit-testable outside a live EDMC install.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

try:
    from config import appname
except ImportError:
    appname = "EDMarketConnector"

plugin_name = os.path.basename(os.path.dirname(__file__))
logger = logging.getLogger(f"{appname}.{plugin_name}")


def _as_int(value: Any) -> int:
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return 0


@dataclass
class CodexEntryRecord:
    """One distinct codex entry this commander has ever found. Keyed
    (see CodexTally) by the raw, unlocalized `Name` field - stable
    identity regardless of the game's display language, same reasoning
    boxel.py/survey_log.py already key off raw journal strings rather than
    display text."""

    name: str
    name_localised: str
    category: str
    category_localised: str
    subcategory: str
    subcategory_localised: str
    first_system: str
    first_seen: str  # ISO timestamp, straight from the journal event
    times_found: int = 1
    was_first_discovery: bool = False  # True if any sighting had IsNewEntry: True
    entry_id: int = 0  # journal `EntryID`; 0 when unknown (entries saved before this was kept)


class CodexTally:
    """Accumulates CodexEntryRecords from raw `CodexEntry` journal events."""

    def __init__(self) -> None:
        self._records: Dict[str, CodexEntryRecord] = {}

    @property
    def records(self) -> List[CodexEntryRecord]:
        return list(self._records.values())

    @property
    def total_distinct(self) -> int:
        return len(self._records)

    @property
    def total_finds(self) -> int:
        return sum(r.times_found for r in self._records.values())

    def first_systems_matching(self, *category_keywords: str) -> set:
        """Returns the set of `first_system` values for every record whose
        raw `category` OR `category_localised` contains any of
        `category_keywords` (case-insensitive) - e.g.
        `first_systems_matching("guardian")` for every system this commander
        has ever *first* logged a Guardian-category codex entry in.

        Checks both the raw and localised category fields: the exact raw
        `$Codex_Category_*;` string for Guardian/Thargoid entries isn't
        confirmed against a live game client in this codebase, so matching
        only the raw field risks silently matching nothing - checking both
        is the safer default until confirmed otherwise.

        Best-effort, not exhaustive: `first_system` only records where a
        given *distinct* codex entry type was first found, not every system
        a commander has since revisited with that category - a commander
        who found the same Guardian entry type at two different sites will
        only have the first one here. Used by canonn_poi_panel.py to filter
        "nearest site" results, not as an authoritative visit history.
        """
        keywords = [k.lower() for k in category_keywords]
        return {
            r.first_system for r in self._records.values()
            if r.first_system and r.first_system != "Unknown"
            and any(k in r.category.lower() or k in r.category_localised.lower() for k in keywords)
        }

    def by_category(self) -> Dict[str, List[CodexEntryRecord]]:
        grouped: Dict[str, List[CodexEntryRecord]] = {}
        for record in self._records.values():
            grouped.setdefault(record.category_localised or record.category, []).append(record)
        for entries in grouped.values():
            entries.sort(key=lambda r: r.name_localised or r.name)
        return grouped

    def category_counts(self) -> Dict[str, int]:
        return {category: len(entries) for category, entries in self.by_category().items()}

    def record(self, entry: Dict[str, Any], system: Optional[str]) -> Optional[CodexEntryRecord]:
        """Parses one raw `CodexEntry` journal event dict. Returns the
        created-or-updated record, or None if the event is missing the
        one field (`Name`) this module treats as required identity."""
        name = entry.get("Name")
        if not name:
            return None

        existing = self._records.get(name)
        if existing is not None:
            existing.times_found += 1
            if not existing.entry_id:
                existing.entry_id = _as_int(entry.get("EntryID"))
            if entry.get("IsNewEntry"):
                existing.was_first_discovery = True
            return existing

        record = CodexEntryRecord(
            name=name,
            name_localised=entry.get("Name_Localised") or name,
            category=entry.get("Category") or "",
            category_localised=entry.get("Category_Localised") or entry.get("Category") or "Unknown",
            subcategory=entry.get("SubCategory") or "",
            subcategory_localised=entry.get("SubCategory_Localised") or entry.get("SubCategory") or "",
            first_system=system or entry.get("System") or "Unknown",
            first_seen=entry.get("timestamp") or "",
            times_found=1,
            was_first_discovery=bool(entry.get("IsNewEntry")),
            entry_id=_as_int(entry.get("EntryID")),
        )
        self._records[name] = record
        return record

    def merge_history(self, entries: List[Dict[str, Any]]) -> None:
        """Fold a full journal-history scan (every `CodexEntry` event the journals hold, including ones already
        counted live) into the tally without counting anything twice. Safe to run any number of times.

        `record()` adds one find per event, which is right for live events but wrong here, because the journals
        also contain what was already counted. So per entry the history's own event count is compared with the
        tally's: `times_found` becomes the larger of the two (the tally can hold finds from journals that have
        since been deleted, so it never goes down), a first discovery anywhere in the history is kept, and an
        earlier first sighting replaces a later one."""
        by_name: Dict[str, List[Dict[str, Any]]] = {}
        for entry in entries:
            name = entry.get("Name")
            if name:
                by_name.setdefault(name, []).append(entry)
        for name, events in by_name.items():
            events.sort(key=lambda e: e.get("timestamp") or "")
            earliest = events[0]
            existing = self._records.get(name)
            if existing is None:
                created = self.record(earliest, earliest.get("System"))
                if created is not None:
                    created.times_found = len(events)
                    created.was_first_discovery = any(e.get("IsNewEntry") for e in events)
                continue
            existing.times_found = max(existing.times_found, len(events))
            if any(e.get("IsNewEntry") for e in events):
                existing.was_first_discovery = True
            if not existing.entry_id:
                existing.entry_id = _as_int(earliest.get("EntryID"))
            stamp = earliest.get("timestamp") or ""
            if stamp and (not existing.first_seen or stamp < existing.first_seen):
                existing.first_seen = stamp
                existing.first_system = earliest.get("System") or existing.first_system

    # --- persistence -----------------------------------------------------

    def snapshot(self) -> List[Dict[str, Any]]:
        return [
            {
                "name": r.name, "name_localised": r.name_localised, "category": r.category,
                "category_localised": r.category_localised, "subcategory": r.subcategory,
                "subcategory_localised": r.subcategory_localised, "first_system": r.first_system,
                "first_seen": r.first_seen, "times_found": r.times_found,
                "was_first_discovery": r.was_first_discovery, "entry_id": r.entry_id,
            }
            for r in self._records.values()
        ]

    def restore(self, data: List[Dict[str, Any]]) -> None:
        records: Dict[str, CodexEntryRecord] = {}
        for raw in data:
            try:
                record = CodexEntryRecord(
                    name=raw["name"], name_localised=raw.get("name_localised", raw["name"]),
                    category=raw.get("category", ""), category_localised=raw.get("category_localised", "Unknown"),
                    subcategory=raw.get("subcategory", ""), subcategory_localised=raw.get("subcategory_localised", ""),
                    first_system=raw.get("first_system", "Unknown"), first_seen=raw.get("first_seen", ""),
                    times_found=int(raw.get("times_found", 1)),
                    was_first_discovery=bool(raw.get("was_first_discovery", False)),
                    entry_id=_as_int(raw.get("entry_id")),
                )
            except KeyError:
                logger.warning("Skipping malformed saved codex entry: %r", raw)
                continue
            records[record.name] = record
        self._records = records
