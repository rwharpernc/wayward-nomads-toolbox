"""
Each commander's route start for Trade: the last (non-carrier) station they docked at.

Spansh plans routes from a station, and lookups are mostly made while docked at a fleet carrier or not docked
at all, so the last real station is remembered. It is kept per commander and saved to `trade_route_start.json`
beside the plugin, so it survives an EDMC restart and a switch of commander.

Each start carries the time of the dock it came from, and a dock only replaces a start that is not newer. That
lets the journal scan feed in docks from files written while EDMC was closed (or copied from another computer,
in any order) without an old file ever overwriting a newer dock.
"""
from __future__ import annotations

import json
import logging
import os
import time
from typing import Any, Dict, Iterable, Optional, Tuple

logger = logging.getLogger(__name__)

STATE_FILENAME = "trade_route_start.json"
CARRIER_STATION_TYPES = ("FleetCarrier", "SquadronCarrier")  # journal StationType values: never a route start

Starts = Dict[str, Dict[str, str]]  # commander key -> {"system", "station", "at"}


def key_for(cmdr: str) -> str:
    """Commanders are keyed by name ignoring case, like the carrier records."""
    return str(cmdr or "").strip().casefold()


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def remember(starts: Starts, cmdr: str, system: str, station: str, at: str = "") -> bool:
    """Record a dock made at `at` (an ISO timestamp; now if blank). Ignored if the commander already has a newer one.
    Returns True if anything changed (so the caller knows to save)."""
    key = key_for(cmdr)
    if not key or not system or not station:
        return False
    at = str(at or _now())
    held = starts.get(key)
    if held is not None and at < held.get("at", ""):
        return False
    new = {"system": str(system), "station": str(station), "at": at}
    if held == new:
        return False
    starts[key] = new
    return True


def lookup(starts: Starts, cmdr: str) -> Optional[Tuple[str, str]]:
    """(system, station) or None."""
    held = starts.get(key_for(cmdr))
    return (held["system"], held["station"]) if held else None


def replay(starts: Starts, events: Iterable[Dict[str, Any]]) -> bool:
    """Fold the docks in a journal file's events into `starts`. The file says whose they are through its `Commander`
    and `LoadGame` events. Returns True if any start changed."""
    cmdr, changed = "", False
    for entry in events:
        event = entry.get("event")
        if event == "Commander" and entry.get("Name"):
            cmdr = str(entry["Name"])
        elif event == "LoadGame" and entry.get("Commander"):
            cmdr = str(entry["Commander"])
        elif event == "Docked" and cmdr and str(entry.get("StationType") or "") not in CARRIER_STATION_TYPES:
            changed = remember(starts, cmdr, entry.get("StarSystem") or "", entry.get("StationName") or "",
                               str(entry.get("timestamp") or "")) or changed
    return changed


def load_all(plugin_dir: str) -> Starts:
    try:
        with open(os.path.join(plugin_dir, STATE_FILENAME), "r", encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, ValueError):
        return {}
    starts: Starts = {}
    for cmdr, value in (data.items() if isinstance(data, dict) else []):
        if (isinstance(value, dict) and isinstance(value.get("system"), str) and isinstance(value.get("station"), str)
                and value["system"] and value["station"]):
            at = value.get("at")
            starts[key_for(cmdr)] = {"system": value["system"], "station": value["station"],
                                     "at": at if isinstance(at, str) else ""}
    return starts


def save_all(plugin_dir: str, starts: Starts) -> None:
    path = os.path.join(plugin_dir, STATE_FILENAME)
    tmp = f"{path}.tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as handle:
            json.dump(starts, handle, indent=2, sort_keys=True)
        os.replace(tmp, path)
    except OSError:
        logger.warning("Could not write %s", path, exc_info=True)
