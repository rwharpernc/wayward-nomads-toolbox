"""
Your fleet carrier and squadron carrier cargo space, for Trade mode: how much of each carrier's
cargo bay is used and free. Pure logic plus a small JSON file (`trade_carrier.json` beside the
plugin).

Not every commander owns a carrier, and some own a fleet carrier, a squadron carrier or both, so
Settings has a per-commander choice (`visible_types`): Auto (show whatever has been seen), None,
Fleet, Squadron or Both. Nothing is shown for a carrier that is not in that choice.

Where the numbers come from (journal events):
- `CarrierStats` (written only when the Carrier Management screen is opened) carries `CarrierID`,
  `CarrierType` (`FleetCarrier` / `SquadronCarrier`) and `SpaceUsage`: `TotalCapacity`, `Crew`,
  `Cargo`, `CargoSpaceReserved`, `ShipPacks`, `ModulePacks`, `FreeSpace`. The cargo bay is what is left
  after crew services and any ship/module packs: capacity = TotalCapacity - Crew - ShipPacks - ModulePacks.
- `CargoTransfer` (`Direction` "tocarrier" / "toship") moves tonnes in and out. It does not say which
  carrier, so the transfer goes to the carrier you are docked at: `Docked` / `Location` carry the
  station's `MarketID` (equal to the carrier's `CarrierID`) and `StationType`. Docked at anyone else's
  carrier, nothing is counted. With only one carrier of yours on record and no dock information, it
  goes to that one.
- `CarrierBuy` says a carrier exists before any usage is known.
- Running the carrier (tritium, location, planned jump, trade orders, balance) comes from the events listed in
  `trade_carrier_ops`.
A trade order being placed or cancelled is recorded (`CarrierTradeOrder`), but the tonnes an order later moves are
not: they show only on the next `CarrierStats`, so the figure is "as of" the last visit to Carrier Management. When transfers alone add up to more than the bay can
hold (or take out more than it holds), something unlogged changed it: the record is flagged `estimate`
and the panel asks for a visit to Carrier Management. A `CarrierStats` replaces the record and clears it.

`CarrierStats` is not written at login and EDMC does not replay old events when it starts, so a baseline
seen before WNTB started would be missed. `backfill` replays the recent journal files for the last
baseline and the transfers after it. Commander names are matched ignoring case (the journal may say
"BOCHEAUX" where EDMC says "Bocheaux").
"""
from __future__ import annotations

import json
import logging
import os
import re
import time
from typing import Any, Dict, Iterable, List, Optional

from . import trade_carrier_ops as ops
from .trade_blocks import Block, Heading, Note, Pair, to_text

try:
    from config import appname
except ImportError:  # unit tests outside EDMC
    appname = "EDMarketConnector"

plugin_name = os.path.basename(os.path.dirname(__file__))
logger = logging.getLogger(f"{appname}.{plugin_name}")

STATE_FILENAME = "trade_carrier.json"
BACKFILL_FILES = 40  # newest journal files read at startup

FLEET = "FleetCarrier"
SQUADRON = "SquadronCarrier"
TYPE_ORDER = (FLEET, SQUADRON)
TYPE_LABEL = {FLEET: "Fleet carrier", SQUADRON: "Squadron carrier"}

# Settings choices, per commander.
AUTO, NONE, FLEET_ONLY, SQUADRON_ONLY, BOTH = "auto", "none", "fleet", "squadron", "both"
MODES = (AUTO, NONE, FLEET_ONLY, SQUADRON_ONLY, BOTH)
_MODE_TYPES = {NONE: (), FLEET_ONLY: (FLEET,), SQUADRON_ONLY: (SQUADRON,), BOTH: (FLEET, SQUADRON)}

# Cheap test for "could this journal line matter?" before paying to parse it; tolerant of spacing.
_WANTED = re.compile(r'"event"\s*:\s*"(?:CarrierStats|CarrierBuy|CargoTransfer|LoadGame|Commander|Docked|Undocked|Location|'
                     r'CarrierDepositFuel|CarrierLocation|CarrierJumpRequest|CarrierJumpCancelled|CarrierTradeOrder|CarrierFinance)"')

CarrierRecord = Dict[str, Any]
Records = Dict[str, Dict[str, CarrierRecord]]  # commander key -> carrier type -> record


def _int(value: Any) -> int:
    return int(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else 0


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def journal_files(journal_dir: str, max_files: int) -> List[str]:
    """Full paths of the newest `max_files` journal files, oldest first. Ordered by modified time, not by name:
    the game has used two naming styles (`Journal.2026-10-09T053605.01.log` and `Journal.260228162446.01.log`)
    and they don't sort chronologically together."""
    try:
        found = []
        for name in os.listdir(journal_dir):
            if name.startswith("Journal.") and name.endswith(".log"):
                path = os.path.join(journal_dir, name)
                found.append((os.path.getmtime(path), name, path))
    except OSError:
        return []
    found.sort()
    return [path for _mtime, _name, path in found[-max_files:]]


def key_for(cmdr: str) -> str:
    """Records and settings are keyed by commander name ignoring case."""
    return str(cmdr or "").strip().casefold()


def _type_of(entry: Dict[str, Any]) -> str:
    return SQUADRON if str(entry.get("CarrierType") or "") == SQUADRON else FLEET


def parse_stats(entry: Dict[str, Any]) -> Optional[CarrierRecord]:
    """A `CarrierStats` event -> a record, or None if it carries no usable space figures."""
    usage = entry.get("SpaceUsage")
    if not isinstance(usage, dict) or not _int(usage.get("TotalCapacity")):
        return None
    total = _int(usage.get("TotalCapacity"))
    crew, ship_packs, module_packs = _int(usage.get("Crew")), _int(usage.get("ShipPacks")), _int(usage.get("ModulePacks"))
    capacity = max(0, total - crew - ship_packs - module_packs)
    cargo, reserved = _int(usage.get("Cargo")), _int(usage.get("CargoSpaceReserved"))
    free = _int(usage["FreeSpace"]) if "FreeSpace" in usage else max(0, capacity - cargo - reserved)
    return {
        "type": _type_of(entry), "id": _int(entry.get("CarrierID")),
        "name": str(entry.get("Name") or ""), "callsign": str(entry.get("Callsign") or ""),
        "total": total, "capacity": capacity, "cargo": cargo, "reserved": reserved, "free": free,
        "crew": crew, "packs": ship_packs + module_packs,
        "updated": str(entry.get("timestamp") or _now()),
        **ops.stats_facts(entry, str(entry.get("timestamp") or _now())),
    }


def note_purchase(entry: Dict[str, Any]) -> CarrierRecord:
    """`CarrierBuy`: a carrier now exists; usage stays unknown until its first CarrierStats."""
    return {"type": _type_of(entry), "id": _int(entry.get("CarrierID")), "name": "",
            "callsign": str(entry.get("Callsign") or ""), "total": 0, "capacity": 0, "cargo": 0, "reserved": 0,
            "free": 0, "updated": str(entry.get("timestamp") or _now())}


def apply_transfer(record: CarrierRecord, entry: Dict[str, Any]) -> bool:
    """Fold a `CargoTransfer` into the used figure. Returns True if anything changed."""
    changed = False
    for transfer in entry.get("Transfers") or []:
        if not isinstance(transfer, dict):
            continue
        count = _int(transfer.get("Count"))
        direction = str(transfer.get("Direction") or "").lower()
        if count <= 0 or direction not in ("tocarrier", "toship"):
            continue
        delta = count if direction == "tocarrier" else -count
        wanted = record.get("cargo", 0) + delta
        capacity = record.get("capacity", 0)
        new_cargo = max(0, min(wanted, capacity) if capacity else wanted)
        if new_cargo != wanted:
            record["estimate"] = True  # more went in (or out) than the bay allows, so the journal is missing something
        applied = new_cargo - record.get("cargo", 0)
        record["cargo"] = new_cargo
        record["free"] = max(0, record.get("free", 0) - applied)
        changed = changed or applied != 0 or new_cargo != wanted
    if changed:
        record["updated"] = str(entry.get("timestamp") or _now())
    return changed


class CarrierTracker:
    """Folds journal events into per-commander, per-type carrier records. Used live by the panel and,
    event by event, by `backfill`."""

    def __init__(self, records: Optional[Records] = None) -> None:
        self.records: Records = records if records is not None else {}
        self.cmdr = ""
        self._docked_id = 0
        self._docked_type = ""

    def set_cmdr(self, cmdr: str) -> None:
        self.cmdr = key_for(cmdr)

    def dock_state(self) -> tuple:
        return self._docked_id, self._docked_type

    def set_dock(self, market_id: int, station_type: str) -> None:
        self._docked_id, self._docked_type = market_id, station_type

    def _mine(self) -> Dict[str, CarrierRecord]:
        return self.records.get(self.cmdr, {})

    def feed(self, entry: Dict[str, Any]) -> bool:
        """Returns True if a record changed."""
        event = entry.get("event")
        if event == "Commander" and entry.get("Name"):
            self.cmdr = key_for(entry["Name"])
            return False
        if event == "LoadGame":
            if entry.get("Commander"):
                self.cmdr = key_for(entry["Commander"])
            self._docked_id, self._docked_type = 0, ""
            return False
        if event in ("Docked", "Location"):
            docked = event == "Docked" or bool(entry.get("Docked"))
            self._docked_id = _int(entry.get("MarketID")) if docked else 0
            self._docked_type = str(entry.get("StationType") or "") if docked else ""
            return False
        if event == "Undocked":
            self._docked_id, self._docked_type = 0, ""
            return False
        if not self.cmdr:
            return False
        if event == "CarrierStats":
            parsed = parse_stats(entry)
            if parsed is None:
                return False
            held = self._mine().get(parsed["type"])
            if held is not None and held.get("updated") and str(parsed["updated"]) < str(held["updated"]):
                return False   # an older baseline (a journal scanned late) never replaces a newer figure
            if held is not None:
                ops.merge_facts(parsed, held)   # keep location, jump and orders; a newer fuel or balance beats the report's
            self.records.setdefault(self.cmdr, {})[parsed["type"]] = parsed
            return True
        if event in ops.OPS_EVENTS:
            target = self._ops_target(entry)
            return target is not None and ops.apply_event(target, entry)
        if event == "CarrierBuy":
            note = note_purchase(entry)
            return self.records.setdefault(self.cmdr, {}).setdefault(note["type"], note) is note
        if event == "CargoTransfer":
            target = self._transfer_target()
            stamp = str(entry.get("timestamp") or "")
            if target is not None and stamp and stamp <= str(target.get("updated") or ""):
                return False   # already inside this figure (a journal read twice, or scanned after a newer one)
            return target is not None and apply_transfer(target, entry)
        return False

    def _ops_target(self, entry: Dict[str, Any]) -> Optional[CarrierRecord]:
        """The record a running-the-carrier event is about: the carrier with that `CarrierID`, else the commander's
        carrier of that `CarrierType`. A carrier first met through such an event gets a record with no space figures."""
        mine = self._mine()
        carrier_id = _int(entry.get("CarrierID"))
        if carrier_id:
            for record in mine.values():
                if record.get("id") == carrier_id:
                    return record
        ctype = str(entry.get("CarrierType") or "")
        if ctype not in TYPE_ORDER:
            return None
        record = mine.get(ctype)
        if record is not None:
            return record if (not record.get("id") or not carrier_id) else None   # a different carrier of the same type
        if entry.get("event") not in ops.CREATES_RECORD:
            return None
        stub = note_purchase({"CarrierType": ctype, "CarrierID": carrier_id, "timestamp": ""})
        stub["updated"] = ""   # no space report behind it, so any real CarrierStats (or saved record) wins
        self.records.setdefault(self.cmdr, {})[ctype] = stub
        return stub

    def _transfer_target(self) -> Optional[CarrierRecord]:
        """The carrier a transfer just now went to: the one we are docked at, else (no dock information)
        the commander's only carrier. Docked at a carrier that is not theirs: none."""
        mine = self._mine()
        if self._docked_id:
            for record in mine.values():
                if record.get("id") == self._docked_id:
                    return record
            if self._docked_type in mine and not mine[self._docked_type].get("id"):
                return mine[self._docked_type]  # a purchase noted without its id
            return None
        return next(iter(mine.values())) if len(mine) == 1 else None


def replay(events: Iterable[Dict[str, Any]], tracker: Optional[CarrierTracker] = None) -> Records:
    tracker = tracker or CarrierTracker()
    for entry in events:
        tracker.feed(entry)
    return tracker.records


def backfill(journal_dir: str, max_files: int = BACKFILL_FILES) -> Records:
    return backfill_tracker(journal_dir, max_files).records


def backfill_tracker(journal_dir: str, max_files: int = BACKFILL_FILES) -> CarrierTracker:
    """Read the newest journal files and return a tracker holding what they say about each commander's
    carriers (and where the commander was docked at the end). Only lines that can matter are parsed, so
    this is cheap even for big journals."""
    tracker = CarrierTracker()
    for path in journal_files(journal_dir, max_files):
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as handle:
                for line in handle:
                    if _WANTED.search(line):
                        try:
                            parsed = json.loads(line)
                        except ValueError:
                            continue
                        if isinstance(parsed, dict):
                            tracker.feed(parsed)
        except OSError:
            continue
    return tracker


# --- what to show --------------------------------------------------------------------------------

def visible_types(mode: str, present: Iterable[str]) -> List[str]:
    """Which carrier types to show for a commander's Settings choice. Auto shows what has been seen."""
    if mode in _MODE_TYPES:
        return list(_MODE_TYPES[mode])
    seen = set(present)
    return [t for t in TYPE_ORDER if t in seen]


def _space_breakdown(record: CarrierRecord) -> List[Block]:
    """What the rest of the carrier's space is spent on (everything that is not the cargo bay). A record saved
    before crew and packs were kept only knows the sum, so that is shown as one line."""
    total, capacity = record.get("total", 0), record.get("capacity", 0)
    if "crew" in record:
        lines = [("Carrier crew services", record.get("crew", 0)), ("Carrier ship / module packs", record.get("packs", 0))]
    else:
        lines = [("Carrier crew and packs", max(0, total - capacity))]
    return [Pair(label, f"{tonnes:,} t") for label, tonnes in lines if tonnes > 0]


def cargo_blocks(records: Optional[Dict[str, CarrierRecord]], mode: str = AUTO) -> List[Block]:
    """Session-page sections, one per visible carrier. Empty when there is nothing to show."""
    records = records or {}
    blocks: List[Block] = []
    for ctype in visible_types(mode, records):
        record = records.get(ctype)
        label = TYPE_LABEL[ctype]
        who = (record or {}).get("name") or (record or {}).get("callsign")
        blocks.append(Heading(f"{label}: {who}" if who else label))
        capacity = (record or {}).get("capacity", 0)
        if not record or not capacity:
            blocks += ops.ops_blocks(record) if record else []
            blocks.append(Note("Open Carrier Management once to read its cargo space.", warn=True))
            continue
        used, reserved, free = record.get("cargo", 0), record.get("reserved", 0), record.get("free", 0)
        guess = "~" if record.get("estimate") else ""
        blocks.append(Pair("Carrier cargo used", f"{guess}{used:,} / {capacity:,} t"))
        blocks.append(Pair("Carrier cargo free", f"{guess}{free:,} t", bold=True))
        blocks += _space_breakdown(record)
        if reserved:
            blocks.append(Pair("Carrier reserved for orders", f"{reserved:,} t"))
        blocks += ops.ops_blocks(record)
        if guess:
            blocks.append(Note("Estimate: the transfers seen add up to more than the bay holds, so cargo left the carrier "
                               "without a journal entry (a trade order or sale). Open Carrier Management for the real figure.",
                               warn=True))
    return blocks


def cargo_lines(records: Optional[Dict[str, CarrierRecord]], mode: str = AUTO) -> List[str]:
    """`cargo_blocks` as plain lines (for tests and logs)."""
    return to_text(cargo_blocks(records, mode))


def newer(candidate: CarrierRecord, existing: Optional[CarrierRecord]) -> bool:
    """Is `candidate` more recent than what is held? (ISO timestamps compare as text.)"""
    return existing is None or str(candidate.get("updated", "")) > str(existing.get("updated", ""))


def merge(target: Records, found: Records) -> bool:
    """Take every record in `found` that is newer than the one in `target`. Returns True if any changed."""
    changed = False
    for cmdr, by_type in found.items():
        for ctype, record in by_type.items():
            held = target.get(cmdr, {}).get(ctype)
            if newer(record, held):
                if held is not None:
                    ops.merge_facts(record, held)   # facts the held record learned live may be newer
                target.setdefault(cmdr, {})[ctype] = record
                changed = True
            elif held is not None:
                changed = ops.merge_facts(held, record) or changed
    return changed


# --- persistence ----------------------------------------------------------------------------------

def load_all(plugin_dir: str) -> Records:
    """Saved records. An older save held one flat record per commander; that was always a fleet carrier."""
    try:
        with open(os.path.join(plugin_dir, STATE_FILENAME), "r", encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, ValueError):
        return {}
    records: Records = {}
    for cmdr, value in (data.items() if isinstance(data, dict) else []):
        if not isinstance(value, dict):
            continue
        if "capacity" in value or "cargo" in value:  # old flat format
            records[key_for(cmdr)] = {FLEET: {**value, "type": FLEET}}
        else:
            records[key_for(cmdr)] = {t: r for t, r in value.items() if t in TYPE_ORDER and isinstance(r, dict)}
    return records


def save_all(plugin_dir: str, records: Records) -> None:
    path = os.path.join(plugin_dir, STATE_FILENAME)
    tmp = f"{path}.tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as handle:
            json.dump(records, handle, indent=2, sort_keys=True)
        os.replace(tmp, path)
    except OSError:
        logger.warning("Could not write %s", path, exc_info=True)
