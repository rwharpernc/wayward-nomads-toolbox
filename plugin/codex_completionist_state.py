"""JSON persistence for Codex Completionist's tally, one tally **per commander**, stored alongside the plugin.

A Codex tally is "what this commander has found", so two commanders on one install never share one. The file holds a
separate payload for each (`commander_data.py`):

    {"entries": [...], "last_event_at": "<ISO time of the newest find counted>", "rebuild_pending": <bool>}

A file written before this was a single tally (a bare list, or `{"entries", "last_event_at"}`) mixed every commander's
finds and cannot be split, so it is **not** handed to anyone: it is kept untouched under `legacy`, and each commander's
tally is rebuilt from their own journals the first time they are seen (`rebuild_pending`).

Atomic-write pattern as boxel_state.py/region_sweep_state.py. Unlike Discovery/Interdiction/Landing's ephemeral
precedent, this state genuinely persists across restarts - see codex_completionist.py's own docstring for why."""

from __future__ import annotations

import calendar
import os
import time
from typing import Any, Dict, Optional

from . import commander_data

STATE_FILENAME = "codex_completionist_state.json"
OLD_TALLY_KEEP_DAYS = 60   # how long the old shared tally is kept (unused) before it is removed


def _state_path(plugin_dir: str) -> str:
    return os.path.join(plugin_dir, STATE_FILENAME)


def _read(plugin_dir: str) -> commander_data.Store:
    return commander_data.read(_state_path(plugin_dir), is_legacy=lambda raw: isinstance(raw, (list, dict)))


def load_commander(plugin_dir: str, cmdr: str) -> Optional[Dict[str, Any]]:
    """This commander's saved payload, or None if they have none yet. The old shared tally is never returned."""
    store = _read(plugin_dir)
    if not commander_data.known(store, cmdr):
        return None
    payload = store["commanders"][commander_data.key_for(cmdr)]["data"]
    return payload if isinstance(payload, dict) else None


def has_old_shared_tally(plugin_dir: str) -> bool:
    """Was a tally saved before codex tallies were per commander (so each commander needs a rebuild)?"""
    return _read(plugin_dir).get("legacy") is not None


def save_commander(plugin_dir: str, cmdr: str, payload: Dict[str, Any]) -> None:
    """Save this commander's payload, leaving every other commander's (and the old shared tally) untouched."""
    if not commander_data.key_for(cmdr):
        return
    store = _read(plugin_dir)
    commander_data.put(store, cmdr, payload)
    commander_data.write(_state_path(plugin_dir), store)


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _epoch(stamp: Any) -> Optional[float]:
    try:
        return float(calendar.timegm(time.strptime(str(stamp), "%Y-%m-%dT%H:%M:%SZ")))
    except ValueError:
        return None


def tidy_old_tally(plugin_dir: str, now: Optional[str] = None) -> bool:
    """Housekeeping for the old shared tally, which nothing reads any more (each commander gets a rebuild from their own
    journals). It is kept for OLD_TALLY_KEEP_DAYS from the first time it was seen, in case something goes wrong with a
    rebuild, then removed - but only once at least one commander has a tally of their own. Returns True if it was
    removed. Safe to call on every start."""
    path = _state_path(plugin_dir)
    store = _read(plugin_dir)
    if store.get("legacy") is None:
        return False
    stamp = now or _now()
    first_seen = store["meta"].get("legacy_since")
    if _epoch(first_seen) is None:
        store["meta"]["legacy_since"] = stamp
        commander_data.write(path, store)
        return False
    age_days = ((_epoch(stamp) or 0.0) - (_epoch(first_seen) or 0.0)) / 86400.0
    if age_days < OLD_TALLY_KEEP_DAYS or not store["commanders"]:
        return False
    store["legacy"] = None
    store["meta"].pop("legacy_since", None)
    commander_data.write(path, store)
    return True
