"""JSON persistence for Boxel Survey's per-commander "visited systems" log.

Records every system a commander has genuinely arrived at (FSDJump/Location),
independent of which Boxel Survey sub-mode (Sequence/Region Sweep/Waypoints)
is selected at the time - unlike `BoxelWalker`'s own internal visited set
(persisted via `boxel_state.py`), which only accumulates while Sequence mode
is the active sub-mode and exists purely to drive that walker's own
skip-visited advance logic.

This log exists for the "Random" button (`boxel_survey.py`): EDSM's
`system_known()` check alone isn't enough to guarantee a candidate is
genuinely new to *this commander* - EDSM sync can lag, or a commander may not
upload at all - so a system they already visited this trip could otherwise
come back as a "not listed in EDSM" false positive and get suggested again.
Checking this local log first (before spending an EDSM call) closes that gap.

Same case-preserved-storage/case-insensitive-match, per-commander,
atomic-write-via-temp-file convention as `boxel_state.py` - see that module's
docstring for the full rationale. Kept as its own file/module rather than
folded into `boxel_state.py` since it isn't part of any walker's snapshot and
has its own independent "Clear" action (Settings -> Boxel Survey)."""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict, Optional, Set

from config import appname

from . import journal_files

plugin_name = os.path.basename(os.path.dirname(__file__))
logger = logging.getLogger(f"{appname}.{plugin_name}")

STATE_FILENAME = "visited_systems.json"


def _state_path(plugin_dir: str) -> str:
    return os.path.join(plugin_dir, STATE_FILENAME)


def _read_raw(plugin_dir: str) -> Optional[Dict[str, Any]]:
    path = _state_path(plugin_dir)
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except FileNotFoundError:
        return None
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("Could not read %s: %s", path, exc)
        return None
    return data if isinstance(data, dict) else None


def load_visited(plugin_dir: str, cmdr: str) -> Set[str]:
    """Load this commander's visited-systems set, or an empty set if
    there's nothing saved for them yet / it's unreadable."""
    if not cmdr or not cmdr.strip():
        return set()
    data = _read_raw(plugin_dir)
    if data is None:
        return set()
    key = cmdr.strip().casefold()
    for stored_cmdr, value in data.items():
        if stored_cmdr.casefold() == key and isinstance(value, list):
            return {name for name in value if isinstance(name, str)}
    return set()


def save_visited(plugin_dir: str, cmdr: str, visited: Set[str]) -> None:
    """Save this commander's visited-systems set, writing to a temp file and
    replacing atomically so a crash or EDMC being killed mid-write can't
    leave a corrupt/truncated state file. Every other commander's own entry
    in the same file is preserved untouched."""
    if not cmdr or not cmdr.strip():
        return
    path = _state_path(plugin_dir)
    all_state = _read_raw(plugin_dir) or {}
    key = cmdr.strip()
    for stored_cmdr in all_state:
        if stored_cmdr.casefold() == key.casefold():
            key = stored_cmdr
            break
    all_state[key] = sorted(visited)
    tmp_path = f"{path}.tmp"
    try:
        with open(tmp_path, "w", encoding="utf-8") as fh:
            json.dump(all_state, fh, indent=2, sort_keys=True)
        os.replace(tmp_path, path)
    except OSError as exc:
        logger.warning("Could not write %s: %s", path, exc)


# --- catching up from the journals -------------------------------------------------------------------------------

CATCH_UP_DAYS = 14   # how far back the start-up pass reads
_ARRIVALS = journal_files.event_pattern("Commander", "LoadGame", "FSDJump", "Location")


def arrivals_since(cmdr: str, since_epoch: float, folder: Optional[str] = None) -> Set[str]:
    """The systems `cmdr` arrived at (FSDJump / Location) in journals modified since `since_epoch`. EDMC only passes a
    plugin the jumps made while it runs; this finds the ones made with it closed. Adding a system to a set twice is
    harmless, so no watermark is needed."""
    wanted = cmdr.strip().casefold()
    found: Set[str] = set()
    if not wanted:
        return found
    for path in journal_files.files_modified_since(since_epoch, folder):
        current = ""
        for entry in journal_files.read_events(path, _ARRIVALS):
            kind = entry.get("event")
            if kind == "Commander" and entry.get("Name"):
                current = str(entry["Name"]).strip().casefold()
            elif kind == "LoadGame" and entry.get("Commander"):
                current = str(entry["Commander"]).strip().casefold()
            elif kind in ("FSDJump", "Location") and current == wanted and entry.get("StarSystem"):
                found.add(str(entry["StarSystem"]))
    return found
