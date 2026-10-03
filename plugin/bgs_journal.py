"""Reads the commander's recent journal files for BGS mode, so the current
tick period's totals are rebuilt from the game's own record rather than
depending on EDMC having been running the whole time.

Only the events bgs_ledger.TickLedger understands are kept. A missing folder,
unreadable file or malformed line never raises: you get what could be read.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timedelta
from typing import Any, Dict, List

from config import appname

from . import bgs_ledger

plugin_name = os.path.basename(os.path.dirname(__file__))
logger = logging.getLogger(f"{appname}.{plugin_name}")

LOOKBACK_DAYS = 3
"""How far before the tick to read. The extra days supply each faction's
last pre-tick snapshot and the missions accepted before the tick."""

_RELEVANT = (
    "FSDJump", "Location", "CarrierJump", "Docked", "Undocked", "MissionAccepted",
    "MissionCompleted", "MissionFailed", "MissionAbandoned", "RedeemVoucher", "MarketBuy",
    "MarketSell", "SellExplorationData", "MultiSellExplorationData", "CommitCrime", "Commander",
)
_NEEDLES = tuple(f'"{name}"' for name in _RELEVANT)


def _journal_files(folder: str, since_ts: float) -> List[str]:
    found: List[tuple] = []
    try:
        with os.scandir(folder) as entries:
            for entry in entries:
                if entry.name.startswith("Journal") and entry.name.endswith(".log") and entry.is_file():
                    modified = entry.stat().st_mtime
                    if modified >= since_ts:
                        found.append((modified, entry.path))
    except OSError:
        logger.warning("BGS journal scan: could not list %s", folder)
        return []
    found.sort()
    return [path for _modified, path in found]


def read_events(cmdr: str, tick_start: str, folder: str = "") -> List[Dict[str, Any]]:
    """Relevant journal entries for `cmdr` from `LOOKBACK_DAYS` before
    `tick_start` up to now, in journal order. `folder` defaults to EDMC's
    configured journal folder."""
    start = bgs_ledger.parse_timestamp(tick_start)
    if not folder:
        from . import journal_scan  # deferred: only needed for EDMC's configured folder
        folder = journal_scan._journal_folder()
    if not folder:
        logger.warning("BGS journal replay skipped: no journal folder (set EDMC's Journal directory "
                       "in Settings - Configuration; on Linux there is no default)")
        return []
    if not cmdr or start is None:
        return []
    window_start: datetime = start - timedelta(days=LOOKBACK_DAYS)
    wanted = cmdr.strip().casefold()

    events: List[Dict[str, Any]] = []
    for path in _journal_files(folder, window_start.timestamp()):
        file_cmdr = ""
        file_events: List[Dict[str, Any]] = []
        try:
            with open(path, encoding="utf8", errors="replace") as handle:
                for line in handle:
                    if not any(needle in line for needle in _NEEDLES):
                        continue
                    try:
                        entry = json.loads(line)
                    except ValueError:
                        continue
                    if not isinstance(entry, dict):
                        continue
                    if entry.get("event") == "Commander":
                        file_cmdr = str(entry.get("Name", "")).strip().casefold()
                        continue
                    when = bgs_ledger.parse_timestamp(entry.get("timestamp"))
                    if when is not None and when < window_start:
                        continue
                    file_events.append(entry)
        except OSError:
            logger.warning("BGS journal scan: could not read %s", path)
            continue
        if file_cmdr == wanted:
            events.extend(file_events)
    return events
