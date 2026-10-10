"""
Which journal files WNTB has already read, so new ones are found and read on their own.

The two computers share nothing but the journals (copied across by hand or by a sync tool), and each keeps
its own trade ledger, stock book and carrier record. So whenever a journal file appears that this computer
has not read, or one it has read has grown, Trade reads it once and folds it in. `trade_journal_scan.json` (beside
the plugin) is the record of what was read: for each file, its size when it was last read.

Size, not modified time, tells a file has changed: a copied file gets a new modified time without having
changed. The file being played right now is left alone (EDMC delivers its events live); it is read on a
later pass, once the game has moved on to another file or EDMC is restarted.

Reading is separate from applying: `read_events` runs on a worker thread and only returns parsed events, and
the Tk thread applies them (to the ledger, the stock book and the carrier tracker, each of which already
refuses to count an event twice) and then calls `mark`. A pass may therefore run any number of times.
"""
from __future__ import annotations

import json
import logging
import os
import re
import time
from typing import Any, Dict, List, Optional, Tuple

from . import trade_carrier
from . import trade_ledger
from . import trade_stock

try:
    from config import appname
except ImportError:  # unit tests outside EDMC
    appname = "EDMarketConnector"

plugin_name = os.path.basename(os.path.dirname(__file__))
logger = logging.getLogger(f"{appname}.{plugin_name}")

STATE_FILENAME = "trade_journal_scan.json"
MAX_PER_PASS = 80        # files read in one pass; a longer list is finished on the next passes
KEEP_RECORDS = 2000      # files remembered, newest first

Registry = Dict[str, Any]   # {"files": {name: {"size": int, "scanned": iso}}, "floor": epoch, "last_pass": iso, "last_found": int}

# Cheap test for "could this journal line matter?" before paying to parse it. Everything Trade uses.
_WANTED = re.compile(
    r'"event"\s*:\s*"(?:MarketBuy|MarketSell|RefuelAll|RefuelPartial|Repair|RepairAll|BuyAmmo|RestockVehicle|BuyDrones|'
    r'SellDrones|FSDJump|CarrierJump|Docked|Undocked|Location|LoadGame|Commander|CarrierStats|CarrierBuy|CargoTransfer)"')


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def new_registry() -> Registry:
    return {"files": {}, "floor": 0, "last_pass": "", "last_found": 0}


def file_start(path: str) -> str:
    """When a journal file began (its first line's timestamp), so files are read oldest first even when copying has
    scrambled their modified times. Falls back on the modified time."""
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as handle:
            first = handle.readline()
        match = re.search(r'"timestamp"\s*:\s*"([^"]+)"', first)
        if match:
            return match.group(1)
        return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(os.path.getmtime(path)))
    except OSError:
        return ""


def pending(journal_dir: str, registry: Registry, skip: Optional[str] = None,
            limit: int = MAX_PER_PASS) -> List[Tuple[str, int]]:
    """(path, size) of the journal files not read yet or grown since they were, oldest first, at most `limit`. `skip` is
    the file being played now. On a first pass (nothing recorded) only the newest `limit` files are taken."""
    known = registry.get("files") or {}
    floor = float(registry.get("floor") or 0)
    skip_name = os.path.basename(skip) if skip else ""
    found: List[Tuple[float, str, str, int]] = []
    try:
        for name in os.listdir(journal_dir):
            if not (name.startswith("Journal.") and name.endswith(".log")) or name == skip_name:
                continue
            path = os.path.join(journal_dir, name)
            try:
                stat = os.stat(path)
            except OSError:
                continue
            if (known.get(name) or {}).get("size") == stat.st_size or stat.st_mtime < floor:
                continue
            found.append((stat.st_mtime, name, path, stat.st_size))
    except OSError:
        return []
    found.sort()
    if not known and not floor:
        found = found[-limit:]       # first pass: the newest files; older history is never read
        if found:
            registry["floor"] = found[0][0]      # and nothing last written before the oldest of them is looked at later
    chosen = sorted(((file_start(path), name, path, size) for _m, name, path, size in found))[:limit]
    return [(path, size) for _start, _name, path, size in chosen]


def read_events(path: str) -> List[Dict[str, Any]]:
    """The events in one journal file that Trade can use, parsed, in file order. Safe on a worker thread."""
    events: List[Dict[str, Any]] = []
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as handle:
            for line in handle:
                if not _WANTED.search(line):
                    continue
                try:
                    entry = json.loads(line)
                except ValueError:
                    continue
                if isinstance(entry, dict):
                    events.append(entry)
    except OSError:
        return []
    return events


def apply(events: List[Dict[str, Any]], ledgers: Dict[str, Dict[str, Any]], stock: trade_stock.StockBook,
          carrier_records: trade_carrier.Records) -> Dict[str, bool]:
    """Fold one file's `events` into each commander's session, the stock book and the carrier records. Each of these
    already skips what it has counted, so a file may be applied more than once. A session with nothing counted and no
    start time is left alone (it has no point to catch up from). Returns which of "ledger", "stock" and "carrier" changed."""
    changed = {"ledger": False, "stock": False, "carrier": False}
    for ledger in ledgers.values():
        if trade_ledger._parse_timestamp(trade_ledger.watermark(ledger)) is None:
            continue
        if trade_ledger.replay_entries(ledger, events, str(ledger.get("cmdr") or "")):
            changed["ledger"] = True
    changed["stock"] = trade_stock.replay_entries(stock, events)
    tracker = trade_carrier.CarrierTracker(carrier_records)    # its own dock state, so the live panel's is not disturbed
    for entry in events:
        if tracker.feed(entry):
            changed["carrier"] = True
    return changed


def mark(registry: Registry, path: str, size: int) -> None:
    """Record that `path` was read when it was `size` bytes."""
    files = registry.setdefault("files", {})
    files[os.path.basename(path)] = {"size": int(size), "scanned": _now()}
    if len(files) > KEEP_RECORDS:
        for name in sorted(files, key=lambda n: files[n].get("scanned", ""))[: len(files) - KEEP_RECORDS]:
            del files[name]


def note_pass(registry: Registry, found: int) -> None:
    registry["last_pass"] = _now()
    registry["last_found"] = int(found)


def summary(registry: Registry) -> str:
    """One line for the Session page: how many files are on record and what the last pass found."""
    files = registry.get("files") or {}
    if not files and not registry.get("last_pass"):
        return "Journals: not scanned yet."
    last = str(registry.get("last_pass") or "")
    when = f" Last check {last[11:16]} UTC, {registry.get('last_found', 0)} new or grown." if last else ""
    return f"Journals read: {len(files)} file(s).{when}"


def load(plugin_dir: str) -> Registry:
    try:
        with open(os.path.join(plugin_dir, STATE_FILENAME), "r", encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, ValueError):
        return new_registry()
    if not isinstance(data, dict) or not isinstance(data.get("files"), dict):
        return new_registry()
    files = {str(k): v for k, v in data["files"].items() if isinstance(v, dict) and isinstance(v.get("size"), int)}
    return {"files": files, "floor": float(data.get("floor") or 0), "last_pass": str(data.get("last_pass") or ""), "last_found": int(data.get("last_found") or 0)}


def save(plugin_dir: str, registry: Registry) -> None:
    path = os.path.join(plugin_dir, STATE_FILENAME)
    tmp = f"{path}.tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as handle:
            json.dump(registry, handle, indent=1, sort_keys=True)
        os.replace(tmp, path)
    except OSError:
        logger.warning("Could not write %s", path, exc_info=True)
