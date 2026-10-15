"""The ship the commander is flying now, from the journals: the newest `Loadout` event.

The Ship planner can subtract what this ship already has (its engineering) from a planned build. The game writes a `Loadout` event at login and whenever
the ship's fit changes, so the last one in the newest journal that has one is the current fit. It is read on demand, not kept: nothing is stored and
nothing is sent anywhere. The journals of a different commander are not told apart here (a `Loadout` carries no commander name); the newest file is the
session being played.
"""
from __future__ import annotations

import logging
import os
from typing import Any, Dict, Optional

from . import journal_files, ship_plan

try:
    from config import appname
except ImportError:  # unit tests outside EDMC
    appname = "EDMarketConnector"

plugin_name = os.path.basename(os.path.dirname(__file__))
logger = logging.getLogger(f"{appname}.{plugin_name}")

NEWEST_FILES = 3          # the newest journal may be empty (the game just started), so look back a few
_LOADOUT = journal_files.event_pattern("Loadout")


def latest_loadout(folder: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """The last `Loadout` event in the newest journal that has one, or None (no journal folder, no journals, no ship fitted yet)."""
    try:
        files = journal_files.files_modified_since(0.0, folder)
        for path in reversed(files[-NEWEST_FILES:]):
            last = None
            for entry in journal_files.read_events(path, _LOADOUT):
                if entry.get("event") == "Loadout" and isinstance(entry.get("Modules"), list):
                    last = entry
            if last is not None:
                return last
    except Exception:
        logger.debug("Could not read the current ship from the journals", exc_info=True)
    return None


def current_build(folder: Optional[str] = None) -> Optional[ship_plan.Build]:
    """The current ship as a build the planner can compare against, or None."""
    loadout = latest_loadout(folder)
    if loadout is None:
        return None
    try:
        return ship_plan.build_from(loadout)
    except ship_plan.PlanError:
        return None
