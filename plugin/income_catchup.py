"""
Reading a commander's income events out of the journal folder, for the one-time rebuild of the Credits Ledger (income_ledger.py).

A journal file says whose events follow in its `Commander` / `LoadGame` lines, and one file can hold more than one commander.
Real file reading over years of journals, so callers run it off the Tk thread.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from . import commander_data, income_ledger, journal_files

logger = logging.getLogger(__name__)

_WANTED = journal_files.event_pattern("Commander", "LoadGame", *sorted(income_ledger.EVENTS))
_MARKS = tuple(name.encode() for name in sorted(income_ledger.EVENTS))


def _has_income(path: str) -> bool:
    try:
        with open(path, "rb") as handle:
            data = handle.read()
    except OSError:
        return False
    return any(mark in data for mark in _MARKS)


def read_all_events(cmdr: str, folder: Optional[str] = None) -> List[Dict[str, Any]]:
    """Every income event `cmdr` has in the journal folder (no date limit), oldest first."""
    location = journal_files.journal_folder() if folder is None else folder
    wanted = commander_data.key_for(cmdr)
    found: List[Dict[str, Any]] = []
    if not wanted or not location:
        return found
    for path in journal_files.files_modified_since(0.0, location):
        if not _has_income(path):
            continue
        current = ""
        for entry in journal_files.read_events(path, _WANTED):
            kind = entry.get("event")
            if kind == "Commander" and entry.get("Name"):
                current = commander_data.key_for(entry["Name"])
            elif kind == "LoadGame" and entry.get("Commander"):
                current = commander_data.key_for(entry["Commander"])
            elif current == wanted and kind in income_ledger.EVENTS:
                found.append(entry)
    found.sort(key=lambda e: str(e.get("timestamp") or ""))
    logger.info("Credits Ledger: found %d income event(s) for %s", len(found), cmdr)
    return found
