"""
Fleet carrier cargo space for Trade mode: how much of the carrier's cargo capacity is used and
free. Pure logic plus a small per-commander JSON file (`trade_carrier.json` beside the plugin).

Not every commander owns a carrier, so nothing is shown until one has been seen for the
current commander; a commander with none never sees a carrier line.

Where the numbers come from (journal events, as documented by Frontier):
- `CarrierStats` - written when the carrier management screen is opened - carries
  `SpaceUsage`: `TotalCapacity`, `Crew`, `Cargo`, `CargoSpaceReserved`, `ShipPacks`,
  `ModulePacks`, `FreeSpace`. The cargo bay is what is left after crew services and any
  ship/module packs, so cargo capacity = TotalCapacity - Crew - ShipPacks - ModulePacks.
- `CargoTransfer` with `Direction` "tocarrier" / "toship" moves tonnes in and out, so the used
  figure follows transfers between management-screen visits.
- `CarrierBuy` says a carrier exists (name and callsign) before any usage is known.
Trade orders and market sales made by the carrier itself are only reflected on the next
`CarrierStats`, so the figure is "as of" the last time the management screen was opened.
"""
from __future__ import annotations

import json
import logging
import os
import time
from typing import Any, Dict, List, Optional

try:
    from config import appname
except ImportError:  # unit tests outside EDMC
    appname = "EDMarketConnector"

plugin_name = os.path.basename(os.path.dirname(__file__))
logger = logging.getLogger(f"{appname}.{plugin_name}")

STATE_FILENAME = "trade_carrier.json"

CarrierRecord = Dict[str, Any]


def _int(value: Any) -> int:
    return int(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else 0


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


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
        "name": str(entry.get("Name") or ""), "callsign": str(entry.get("Callsign") or ""),
        "total": total, "capacity": capacity, "cargo": cargo, "reserved": reserved, "free": free,
        "updated": str(entry.get("timestamp") or _now()),
    }


def note_purchase(entry: Dict[str, Any]) -> CarrierRecord:
    """`CarrierBuy`: a carrier now exists; usage stays unknown until its first CarrierStats."""
    return {"name": "", "callsign": str(entry.get("Callsign") or ""), "total": 0, "capacity": 0,
            "cargo": 0, "reserved": 0, "free": 0, "updated": str(entry.get("timestamp") or _now())}


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
        new_cargo = max(0, record.get("cargo", 0) + delta)
        applied = new_cargo - record.get("cargo", 0)
        record["cargo"] = new_cargo
        record["free"] = max(0, record.get("free", 0) - applied)
        changed = changed or applied != 0
    if changed:
        record["updated"] = str(entry.get("timestamp") or _now())
    return changed


def cargo_lines(record: Optional[CarrierRecord]) -> List[str]:
    """Display lines for the Session page. Empty when there is no carrier to show."""
    if not record:
        return []
    who = record.get("name") or record.get("callsign") or "Fleet carrier"
    head = f"Fleet carrier: {who}"
    capacity = record.get("capacity", 0)
    if not capacity:
        return [head, "  Open Carrier Management once to read its cargo space."]
    used, reserved, free = record.get("cargo", 0), record.get("reserved", 0), record.get("free", 0)
    lines = [head, f"  Cargo: {used:,}/{capacity:,} t used, {free:,} t free"]
    if reserved:
        lines.append(f"  {reserved:,} t reserved for trade orders")
    return lines


# --- persistence (one record per commander) ---------------------------------------------------

def load_all(plugin_dir: str) -> Dict[str, CarrierRecord]:
    try:
        with open(os.path.join(plugin_dir, STATE_FILENAME), "r", encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, ValueError):
        return {}
    return {str(k): v for k, v in data.items() if isinstance(v, dict)} if isinstance(data, dict) else {}


def save_all(plugin_dir: str, records: Dict[str, CarrierRecord]) -> None:
    path = os.path.join(plugin_dir, STATE_FILENAME)
    tmp = f"{path}.tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as handle:
            json.dump(records, handle, indent=2, sort_keys=True)
        os.replace(tmp, path)
    except OSError:
        logger.warning("Could not write %s", path, exc_info=True)
