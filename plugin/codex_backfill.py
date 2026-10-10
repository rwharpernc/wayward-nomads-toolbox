"""
Journal readers for Codex Completionist. A Codex tally belongs to one commander, so both readers take the commander and
return only that commander's `CodexEntry` events (a journal file says whose events follow in its `Commander` /
`LoadGame` lines, and one file can hold more than one commander).

`scan_all_codex_entries` is the full-history scan for the "Backfill from Journal History" button and the one-time rebuild
after codex tallies became per commander. journal_scan.py (Missions mode) is bounded to two weeks, which is far too
short for a lifetime codex tally, so this has no date cutoff. It is real I/O (years of journal files), so it is
explicitly user-triggered or one-time. `scan_since` is the small automatic one: only the files written since the tally
last saw an event.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional

from config import appname, config

from . import commander_data, journal_files

plugin_name = os.path.basename(os.path.dirname(__file__))
logger = logging.getLogger(f"{appname}.{plugin_name}")


def _journal_dir() -> str:
    # Same fallback journal_scan.py/mining_journal_backfill.py already use -
    # config.get_str is the current EDMC config API, config.get is the
    # older one some still-supported EDMC versions expose instead.
    if hasattr(config, "get_str"):
        location = config.get_str("journaldir")
    else:
        location = config.get("journaldir")  # type: ignore[attr-defined]
    return location or config.default_journal_dir


_WANTED = journal_files.event_pattern("Commander", "LoadGame", "CodexEntry")


def _commander_events(path: str, wanted_key: str):
    """The `CodexEntry` events in one journal file that belong to the commander with this key. A file names whose events
    follow in its `Commander` / `LoadGame` lines (one file can hold more than one commander)."""
    current = ""
    for entry in journal_files.read_events(path, _WANTED):
        kind = entry.get("event")
        if kind == "Commander" and entry.get("Name"):
            current = commander_data.key_for(entry["Name"])
        elif kind == "LoadGame" and entry.get("Commander"):
            current = commander_data.key_for(entry["Commander"])
        elif kind == "CodexEntry" and current == wanted_key:
            yield entry


def scan_since(stamp: str, cmdr: str, folder: Optional[str] = None) -> List[Dict[str, Any]]:
    """`cmdr`'s `CodexEntry` events written after `stamp` (an ISO timestamp), oldest first. Reads only the journal files
    modified since then, so it is cheap enough to run at every start-up (unlike the full history scan)."""
    import calendar
    import time

    try:
        since = calendar.timegm(time.strptime(stamp, "%Y-%m-%dT%H:%M:%SZ")) - 86400   # a day's slack for clock drift
    except ValueError:
        return []
    key = commander_data.key_for(cmdr)
    events: List[Dict[str, Any]] = []
    for path in journal_files.files_modified_since(since, folder):
        events.extend(e for e in _commander_events(path, key) if (e.get("timestamp") or "") > stamp)
    return events


def scan_all_codex_entries(cmdr: str, folder: Optional[str] = None) -> List[Dict[str, Any]]:
    """Every `CodexEntry` event `cmdr` has in the journal directory (oldest file first), for the Backfill button and the
    one-time rebuild. Other commanders' events in the same files are left out. Runs synchronously - callers must run it
    off the Tk main thread (see codex_completionist_panel.py's worker-thread/queue pattern), since years of journal
    history means real disk I/O time."""
    location = _journal_dir() if folder is None else folder
    if not location:
        # No configured journal folder and no EDMC default (common on Linux, where it lives inside the Wine/Proton
        # prefix): an empty path would silently mean the current directory.
        logger.warning("No journal directory configured; set one in EDMC's settings")
        return []
    if not os.path.isdir(location):
        logger.warning("Journal directory not found: %s", location)
        return []
    key = commander_data.key_for(cmdr)
    files = journal_files.files_modified_since(0.0, location)
    entries: List[Dict[str, Any]] = []
    for path in files:
        entries.extend(_commander_events(path, key))
    logger.info("Backfill scanned %d journal file(s) for %s, found %d CodexEntry event(s)", len(files), cmdr, len(entries))
    return entries
