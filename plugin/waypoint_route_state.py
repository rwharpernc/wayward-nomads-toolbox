"""JSON persistence for Waypoint Route's list state, stored alongside the
plugin, keyed per commander - same reasoning as boxel_state.py/
region_sweep_state.py, in its own file so this mode's state format is
independent of the other two Boxel Survey sub-modes."""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict, List, Optional, Union

from config import appname

plugin_name = os.path.basename(os.path.dirname(__file__))
logger = logging.getLogger(f"{appname}.{plugin_name}")

STATE_FILENAME = "waypoint_route_state.json"


def _state_path(plugin_dir: str) -> str:
    return os.path.join(plugin_dir, STATE_FILENAME)


def _read_raw(plugin_dir: str) -> Optional[Union[Dict[str, List[Any]], List[Any]]]:
    path = _state_path(plugin_dir)
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except FileNotFoundError:
        return None
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("Could not read %s: %s", path, exc)
        return None


def load_state(plugin_dir: str, cmdr: str) -> Optional[List[Any]]:
    """Load this commander's persisted waypoint list, or None if there's
    nothing saved for them yet / it's unreadable.

    A legacy (pre-per-commander) file stored the waypoint list itself
    directly at the top level (a JSON array, not an object) - a one-time
    special case with no commander name attached to it at all, so
    whichever commander is first seen after upgrading adopts it (better
    than silently discarding a real route) - the file is then rewritten
    into the new per-commander shape so this doesn't re-trigger next
    launch."""
    if not cmdr or not cmdr.strip():
        return None
    data = _read_raw(plugin_dir)
    if data is None:
        return None
    if isinstance(data, list):
        logger.info("Migrating pre-per-commander waypoint_route_state.json to commander %r", cmdr)
        save_state(plugin_dir, cmdr, data)
        return data
    if not isinstance(data, dict):
        return None
    key = cmdr.strip().casefold()
    for stored_cmdr, value in data.items():
        if stored_cmdr.casefold() == key:
            return value
    return None


def save_state(plugin_dir: str, cmdr: str, data: List[Any]) -> None:
    """Save this commander's waypoint list, writing to a temp file and
    replacing atomically so a crash or EDMC being killed mid-write can't
    leave a corrupt/truncated state file. Every other commander's own
    entry in the same file is preserved untouched."""
    if not cmdr or not cmdr.strip():
        return
    path = _state_path(plugin_dir)
    raw = _read_raw(plugin_dir)
    all_state: Dict[str, List[Any]] = raw if isinstance(raw, dict) else {}
    key = cmdr.strip()
    for stored_cmdr in all_state:
        if stored_cmdr.casefold() == key.casefold():
            key = stored_cmdr
            break
    all_state[key] = data
    tmp_path = f"{path}.tmp"
    try:
        with open(tmp_path, "w", encoding="utf-8") as fh:
            json.dump(all_state, fh, indent=2, sort_keys=True)
        os.replace(tmp_path, path)
    except OSError as exc:
        logger.warning("Could not write %s: %s", path, exc)
