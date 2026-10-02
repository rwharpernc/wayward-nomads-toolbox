"""
Full-journal-history scan for Codex Completionist's "Backfill from Journal
History" button.

journal_scan.py (Missions mode) already globs every `*.log` file in the
journal directory and replays events from them, but it's bounded to a
2-week lookback (`_JOURNAL_SCAN_LOOKBACK`) - appropriate for missions
(which expire) but far too short for a lifetime codex tally. This module
is deliberately a separate, small glob function rather than reaching into
journal_scan.py's own name-mangled private helpers across modules: no
date cutoff at all, and filtered to `CodexEntry` events only.

Explicitly user-triggered (a button, never automatic on EDMC start) -
scanning years of journal files is real I/O cost.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, List

from config import appname, config

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


def scan_all_codex_entries() -> List[Dict[str, Any]]:
    """Reads every `*.log` file in the journal directory (oldest first) and
    returns every `CodexEntry` event found, in chronological order. Runs
    synchronously - callers must run this off the Tk main thread (see
    codex_completionist_panel.py's own worker-thread/queue pattern), since
    a commander with years of journal history means real disk I/O time."""
    location = _journal_dir()
    if not location:
        # No configured journal folder and no EDMC default (common on Linux,
        # where it lives inside the Wine/Proton prefix): Path("") would
        # silently scan the current directory instead.
        logger.warning("No journal directory configured; set one in EDMC's settings")
        return []
    journal_dir = Path(location)
    if not journal_dir.is_dir():
        logger.warning("Journal directory not found: %s", journal_dir)
        return []

    log_files = sorted(
        (p for p in journal_dir.glob("*.log") if p.is_file()),
        key=lambda p: p.stat().st_mtime,
    )

    entries: List[Dict[str, Any]] = []
    for log_file in log_files:
        try:
            with open(log_file, "r", encoding="utf-8", errors="replace") as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        event = json.loads(line)
                    except ValueError:
                        continue
                    if event.get("event") == "CodexEntry":
                        entries.append(event)
        except OSError as exc:
            logger.warning("Could not read journal file %s: %s", log_file, exc)
            continue

    logger.info("Backfill scanned %d journal file(s), found %d CodexEntry event(s)", len(log_files), len(entries))
    return entries
