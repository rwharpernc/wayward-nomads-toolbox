"""JSON persistence for the per-system Powerplay ledger, keyed per commander
(case-preserved for storage, matched case-insensitively) - the same convention
as bgs_state.py, so two commanders on one install keep separate Powerplay data.

Schema (per commander):

    {
        "ledger": {            # powerplay_ledger.PowerplayLedger.to_dict()
            "cycle_start": "<ISO timestamp of the cycle's Thursday 07:00 UTC start, or null>",
            "systems": {"<system (casefold)>": {...SystemRecord fields...}},
            "archive": [{"cycle_start", "cycle_end", "systems": {...}}]
        },
        "pinned_systems": ["System Name", ...],    # at most MAX_PINNED
        "hidden_systems": ["System Name", ...]
    }

This is separate from sessions.json (merit tallies per game login), which is
unchanged."""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict, Optional

from config import appname

plugin_name = os.path.basename(os.path.dirname(__file__))
logger = logging.getLogger(f"{appname}.{plugin_name}")

STATE_FILENAME = "powerplay_state.json"


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


def load_state(plugin_dir: str, cmdr: str) -> Optional[Dict[str, Any]]:
    """This commander's saved state, or None if there is none / it's unreadable."""
    if not cmdr or not cmdr.strip():
        return None
    data = _read_raw(plugin_dir)
    if data is None:
        return None
    key = cmdr.strip().casefold()
    for stored_cmdr, value in data.items():
        if stored_cmdr.casefold() == key:
            return value if isinstance(value, dict) else None
    return None


def save_state(plugin_dir: str, cmdr: str, data: Dict[str, Any]) -> None:
    """Save this commander's state atomically (temp file, then os.replace);
    every other commander's entry in the file is preserved untouched."""
    if not cmdr or not cmdr.strip():
        return
    path = _state_path(plugin_dir)
    all_state = _read_raw(plugin_dir) or {}
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
