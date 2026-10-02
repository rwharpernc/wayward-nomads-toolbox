"""JSON persistence for Boxel Survey's walker state, stored alongside the
plugin, keyed per commander (case-preserved for storage, matched
case-insensitively) - same convention as ship_builds_data.py's own
ShipBuildRepository - so two commanders on the same install each keep
their own boxel position instead of silently sharing/overwriting one."""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict, Optional

from config import appname

plugin_name = os.path.basename(os.path.dirname(__file__))
logger = logging.getLogger(f"{appname}.{plugin_name}")

STATE_FILENAME = "boxel_state.json"


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


def _is_legacy_shape(data: Dict[str, Any]) -> bool:
    """This file's pre-per-commander shape had seed/current/visited
    directly at the top level, written by a single commander (whoever
    was running WNTB before this update) rather than keyed by name."""
    return "seed" in data or "current" in data or "visited" in data


def load_state(plugin_dir: str, cmdr: str) -> Optional[Dict[str, Any]]:
    """Load this commander's persisted walker state, or None if there's
    nothing saved for them yet / it's unreadable.

    A legacy (pre-per-commander) file is a one-time special case: it has
    no commander name attached to it at all, so whichever commander is
    first seen after upgrading adopts it (better than silently discarding
    real survey progress) - the file is then rewritten into the new
    per-commander shape so this doesn't re-trigger next launch."""
    if not cmdr or not cmdr.strip():
        return None
    data = _read_raw(plugin_dir)
    if data is None:
        return None
    if _is_legacy_shape(data):
        logger.info("Migrating pre-per-commander boxel_state.json to commander %r", cmdr)
        save_state(plugin_dir, cmdr, data)
        return data
    key = cmdr.strip().casefold()
    for stored_cmdr, value in data.items():
        if stored_cmdr.casefold() == key:
            return value
    return None


def save_state(plugin_dir: str, cmdr: str, data: Dict[str, Any]) -> None:
    """Save this commander's walker state, writing to a temp file and
    replacing atomically so a crash or EDMC being killed mid-write can't
    leave a corrupt/truncated state file. Every other commander's own
    entry in the same file is preserved untouched."""
    if not cmdr or not cmdr.strip():
        return
    path = _state_path(plugin_dir)
    all_state = _read_raw(plugin_dir) or {}
    if _is_legacy_shape(all_state):
        all_state = {}
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
