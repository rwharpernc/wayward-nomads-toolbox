"""
Locates and reads the current journal file so mining_panel.py can replay
it through `handle_event()` on a mid-session EDMC start. Same "find the
journal dir, glob for log files" pattern as this project's own
journal_scan.py (Missions mode), trimmed down to just the single
most-recent file (today's session), not full history: Mining mode's run
state is naturally bounded by the current Undocked/LaunchSRV, so anything
from a previous day's file is already stale/irrelevant.
"""
import json
import logging
import os
from pathlib import Path
from typing import Any, Iterator, Optional

from config import appname, config

plugin_name = os.path.basename(os.path.dirname(__file__))
logger = logging.getLogger(f"{appname}.{plugin_name}")

RELEVANT_EVENTS = frozenset({
    "Commander", "Undocked", "Docked", "SupercruiseEntry", "SupercruiseExit",
    "LaunchSRV", "DockSRV", "SRVDestroyed", "Died",
    "ProspectedAsteroid", "AsteroidCracked", "LaunchDrone", "BuyDrones",
    "Loadout", "MiningRefined", "Cargo", "CargoTransfer",
    "MaterialCollected", "SAASignalsFound", "Location", "FSDJump",
    "ApproachBody", "LeaveBody", "Touchdown", "Liftoff", "Scan",
})
"""Must track mining_panel.py's `handle_event()` elif chain (plus
"Commander", which handle_event never branches on itself but this module
needs to follow who the replayed events belong to) - every event that
function acts on needs to be here too, or a mid-session start silently
misses it."""


def _journal_dir() -> Optional[str]:
    # config.get_str is the current EDMC config API; config.get is the
    # older one some still-supported EDMC versions expose instead - same
    # fallback journal_scan.py uses.
    if hasattr(config, "get_str"):
        location = config.get_str("journaldir")
    else:
        location = config.get("journaldir")  # type: ignore[attr-defined]
    if not location:
        location = config.default_journal_dir
    return location


def find_current_journal_file() -> Optional[Path]:
    """The journal file EDMC is currently tailing - the most recently
    modified `Journal.*.log` in the configured journal directory. None if
    the directory is unset/inaccessible or has no journal files yet."""
    location = _journal_dir()
    if not location:
        return None
    try:
        candidates = [path for path in Path(location).glob("Journal.*.log") if path.is_file()]
        if not candidates:
            return None
        return max(candidates, key=lambda path: path.stat().st_mtime)
    except OSError:
        logger.exception("Mining journal backfill: couldn't list journal directory")
        return None


def read_entries(path: Path) -> Iterator[dict[str, Any]]:
    """Yields each relevant, parseable line from `path` in file order.
    Malformed lines (mid-write truncation, bad JSON) are skipped rather
    than aborting the whole replay - never raises."""
    try:
        with open(path, "r", encoding="utf8", errors="replace") as journal_file:
            for line in journal_file:
                try:
                    entry = json.loads(line)
                except (json.JSONDecodeError, ValueError):
                    continue
                if entry.get("event") in RELEVANT_EVENTS:
                    yield entry
    except OSError:
        logger.exception("Mining journal backfill: couldn't read %s", path)
