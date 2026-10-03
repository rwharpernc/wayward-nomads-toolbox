"""JSON persistence for BGS tracking, stored alongside the plugin, keyed
per commander (case-preserved for storage, matched case-insensitively) -
same convention as boxel_state.py/organic_scan_state.py/ship_builds_data.py,
so two commanders on the same install each keep their own BGS data instead of
silently sharing/overwriting one.

Unlike Discovery/Interdiction/Landing's ephemeral precedent, this persists
across restarts *and* survives EDMC being closed entirely - a commander's
tick totals and last-known faction states shouldn't vanish just because they
logged out (same reasoning organic_scan.py's own per-body state now follows).

Schema (per commander):

    {
        "ledger": {            # the current tick period - see bgs_ledger.TickLedger.to_dict()
            "tick_start": "<ISO timestamp of the tick that began this period, or null>",
            "activity": {"<system>|<faction> (casefold)": {...FactionActivity fields...}},
            "tracks": {"<system>|<faction> (casefold)": {"system", "faction", "before", "now"}},
            "open_missions": {"<MissionID>": ["<faction>", "<system>"]}
        },
        "archive": [           # closed tick periods, newest first, pruned to the archive-days setting
            {"tick_start", "tick_end", "activity": {...}, "tracks": {...}}
        ]
    }

Older files (tracked systems/factions, snapshots, previous_activity) are
still readable: those keys are simply ignored, and the old
`tick.last_seen_at` seeds the period start until the next tick check.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict, Optional

from config import appname

plugin_name = os.path.basename(os.path.dirname(__file__))
logger = logging.getLogger(f"{appname}.{plugin_name}")

STATE_FILENAME = "bgs_state.json"

_DEFAULT_STATE: Dict[str, Any] = {
    "ledger": {"tick_start": None, "activity": {}, "tracks": {}, "open_missions": {}},
    "archive": [],
}


def default_state() -> Dict[str, Any]:
    return json.loads(json.dumps(_DEFAULT_STATE))  # cheap deep copy, no mutable sharing across cmdrs


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
    """Load this commander's persisted BGS state, or None if there's
    nothing saved for them yet / it's unreadable."""
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
    """Save this commander's BGS state, writing to a temp file and
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
    all_state[key] = data
    tmp_path = f"{path}.tmp"
    try:
        with open(tmp_path, "w", encoding="utf-8") as fh:
            json.dump(all_state, fh, indent=2, sort_keys=True)
        os.replace(tmp_path, path)
    except OSError as exc:
        logger.warning("Could not write %s: %s", path, exc)
