"""
What is in the ship's hold beyond the commodity counts EDMC gives us: how much of it is mission cargo and how much is
stolen.

The journal's `Cargo` event (and `Cargo.json`, which EDMC reads) lists the hold as `Inventory` entries of `Name`, `Count`,
`Stolen` and, for cargo that belongs to a mission, `MissionID` (checked against a real journal: every entry has `Stolen`;
`MissionID` appears only on mission cargo). EDMC's own state merges them into one count per commodity, so the split has to
come from these entries. Mission cargo takes hold space like any other, which is why it is worth showing.
"""
from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional, Tuple

CARGO_FILE = "Cargo.json"
DRONES = "drones"   # limpets: counted as cargo by the game and shown on their own


def split_inventory(inventory: Any) -> Tuple[int, int]:
    """(mission tonnes, stolen tonnes) in a `Cargo` inventory list. Limpets are left out of both."""
    mission = stolen = 0
    for item in inventory if isinstance(inventory, list) else []:
        if not isinstance(item, dict) or str(item.get("Name", "")).lower() == DRONES:
            continue
        count = item.get("Count")
        if not isinstance(count, int) or isinstance(count, bool) or count <= 0:
            continue
        if item.get("MissionID"):
            mission += count
        elif item.get("Stolen"):
            stolen += count
    return mission, stolen


def read_cargo_file(journal_dir: str) -> Optional[List[Dict[str, Any]]]:
    """The hold's inventory from `Cargo.json` in the journal folder, or None if it is missing or unreadable."""
    if not journal_dir:
        return None
    try:
        with open(os.path.join(journal_dir, CARGO_FILE), "r", encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, ValueError):
        return None
    inventory = data.get("Inventory") if isinstance(data, dict) else None
    return inventory if isinstance(inventory, list) else None


def describe(cargo_tonnes: int, mission: int, stolen: int) -> str:
    """'312 t cargo' with, when there is any, '(40 t mission, 12 t stolen)' after it."""
    extras = [f"{amount:,} t {label}" for amount, label in ((mission, "mission"), (stolen, "stolen")) if amount > 0]
    return f"{cargo_tonnes:,} t cargo" + (f" ({', '.join(extras)})" if extras else "")
