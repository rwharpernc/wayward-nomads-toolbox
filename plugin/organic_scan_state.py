"""JSON persistence for Organic Scanning's per-body state (habitability
conditions, detected genera, and confirmed-species scan progress), stored
alongside the plugin, keyed per commander (case-preserved for storage,
matched case-insensitively) - same convention as boxel_state.py's own
walker state / ship_builds_data.py's ShipBuildRepository, so two
commanders on the same install each keep their own biology data instead of
silently sharing/overwriting one.

This is what makes organic_scan_panel.py's per-body data survive a
log-out/relog (a new journal file, so the FSSBodySignals/Scan/ScanOrganic
events that originally populated it never get replayed) - see
organic_scan.py's own docstring for the "ephemeral by design" precedent
this now supersedes for the per-body data specifically."""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict, Optional

from config import appname

plugin_name = os.path.basename(os.path.dirname(__file__))
logger = logging.getLogger(f"{appname}.{plugin_name}")

STATE_FILENAME = "organic_scan_state.json"


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
    """Load this commander's persisted per-body organic-scan state, or None
    if there's nothing saved for them yet / it's unreadable."""
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
    """Save this commander's per-body organic-scan state, writing to a temp
    file and replacing atomically so a crash or EDMC being killed mid-write
    can't leave a corrupt/truncated state file. Every other commander's own
    entry in the same file is preserved untouched."""
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
