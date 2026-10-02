"""Current suit tracking and backpack capacity for Field Ops' Inventory content.

The journal never reports backpack capacity, so it is hardcoded here per suit
type and looked up from the SuitName / SuitMods fields of SuitLoadout and
SwitchSuitLoadout. In-game the categories are called Goods (journal: Item),
Assets (journal: Component) and Data.

The hardcoded table only distinguishes "Extra Backpack Capacity present or
not" — it can't capture engineering grade, and has no entry at all for the
Flight Suit. Commanders can correct individual categories per owned suit
loadout (keyed by the journal's LoadoutID) from the Settings tab; see
`known_loadouts_for` / `set_override`.
"""

from __future__ import annotations

import json
from typing import Any, Dict, Mapping, Optional

from config import config

# Suit mod that raises backpack capacity ("Extra Backpack Capacity").
BACKPACK_CAPACITY_MOD = "suit_backpackcapacity"

# EDMC config key for user-entered per-loadout capacity overrides.
CONFIG_SUIT_OVERRIDES = "wntb_inventory_suit_overrides"

SUIT_DISPLAY_NAMES: Dict[str, str] = {
    "explorationsuit": "Artemis Suit",
    "tacticalsuit": "Dominator Suit",
    "utilitysuit": "Maverick Suit",
    "flightsuit": "Flight Suit",
}

# Backpack capacity per suit type, by journal category.
# "base" = unmodified, "modded" = suit_backpackcapacity fitted.
# None means the capacity is unknown; the UI then shows a plain count with no
# limit rather than guessing.
CapacityMap = Dict[str, int]
SuitCapacities = Dict[str, CapacityMap]

CAPACITIES: Dict[str, Optional[SuitCapacities]] = {
    # Maverick
    "utilitysuit": {
        "base": {"Item": 40, "Component": 60, "Data": 20},
        "modded": {"Item": 80, "Component": 120, "Data": 40},
    },
    # Artemis
    "explorationsuit": {
        "base": {"Item": 20, "Component": 40, "Data": 10},
        "modded": {"Item": 40, "Component": 80, "Data": 20},
    },
    # Dominator
    "tacticalsuit": {
        "base": {"Item": 10, "Component": 20, "Data": 10},
        "modded": {"Item": 20, "Component": 40, "Data": 20},
    },
    "flightsuit": None,
}

# Per-loadout capacity overrides, keyed by commander then LoadoutID (both as
# strings, since JSON object keys are always strings):
#   {cmdr: {loadout_id: {"name": str, "suit_key": str, "grade": Optional[int],
#                         "has_capacity_mod": bool, "overrides": {category: int}}}}
# "overrides" holds only the categories the commander has explicitly entered;
# a category missing from it means "use the hardcoded CAPACITIES default".
LoadoutRecord = Dict[str, Any]
_KNOWN_LOADOUTS: Dict[str, Dict[str, LoadoutRecord]] = {}


def load_overrides() -> None:
    """Restore known loadouts and their overrides from EDMC config."""
    raw = config.get_str(CONFIG_SUIT_OVERRIDES)
    if not raw:
        return

    try:
        loaded = json.loads(raw)
    except (TypeError, ValueError):
        return

    if isinstance(loaded, dict):
        _KNOWN_LOADOUTS.update(loaded)


def save_overrides() -> None:
    """Persist known loadouts and their overrides to EDMC config."""
    config.set(CONFIG_SUIT_OVERRIDES, json.dumps(_KNOWN_LOADOUTS))


def known_loadouts_for(cmdr: str) -> Dict[str, LoadoutRecord]:
    """Known suit loadouts (and any overrides) recorded for one commander."""
    return _KNOWN_LOADOUTS.get(cmdr, {})


def record_loadout(
    cmdr: str,
    loadout_id: str,
    *,
    name: str,
    suit_key: str,
    grade: Optional[int],
    has_capacity_mod: bool,
) -> None:
    """
    Upsert a loadout's identity fields, e.g. when it is worn or switched to.

    Preserves any overrides already entered for this loadout; only the
    identity fields (name/suit/grade/mod) are refreshed.
    """
    if not cmdr or not loadout_id:
        return

    commander_loadouts = _KNOWN_LOADOUTS.setdefault(cmdr, {})
    record = commander_loadouts.setdefault(loadout_id, {"overrides": {}})
    record["name"] = name
    record["suit_key"] = suit_key
    record["grade"] = grade
    record["has_capacity_mod"] = has_capacity_mod
    record.setdefault("overrides", {})


def default_capacity(suit_key: str, has_capacity_mod: bool) -> CapacityMap:
    """Hardcoded default capacity for a suit type/mod state, ignoring overrides."""
    table = CAPACITIES.get(suit_key)
    if table is None:
        return {}
    return dict(table["modded"] if has_capacity_mod else table["base"])


def set_override(cmdr: str, loadout_id: str, category: str, value: Optional[int]) -> None:
    """Set (or, with value=None, clear) a per-category capacity override."""
    record = _KNOWN_LOADOUTS.get(cmdr, {}).get(loadout_id)
    if record is None:
        return

    if value is None:
        record["overrides"].pop(category, None)
    else:
        record["overrides"][category] = value


class SuitState:
    """Tracks the suit the commander is currently wearing."""

    def __init__(self) -> None:
        self._suit_key: Optional[str] = None
        self._localised: Optional[str] = None
        self._grade: Optional[int] = None
        self._mods: tuple = ()
        self._loadout_id: Optional[str] = None
        self._loadout_name: Optional[str] = None

    @property
    def known(self) -> bool:
        return self._suit_key is not None

    @property
    def has_capacity_mod(self) -> bool:
        return BACKPACK_CAPACITY_MOD in self._mods

    @property
    def display_name(self) -> str:
        if self._suit_key is None:
            return "No suit data yet"

        name = SUIT_DISPLAY_NAMES.get(self._suit_key, self._suit_key)
        if self._grade:
            name = f"{name} (Grade {self._grade})"
        if self.has_capacity_mod:
            name = f"{name} + Extra Backpack Capacity"
        if self._loadout_name:
            name = f'{name} — "{self._loadout_name}"'
        return name

    def apply_suit_loadout(self, entry: Mapping[str, Any], cmdr: Optional[str] = None) -> None:
        """Read SuitName / SuitMods from a SuitLoadout or SwitchSuitLoadout event."""
        suit_name = str(entry.get("SuitName", "")).lower()
        if not suit_name:
            return

        self._suit_key, self._grade = _split_suit_name(suit_name)
        mods = entry.get("SuitMods", [])
        self._mods = tuple(str(mod).lower() for mod in mods) if isinstance(mods, list) else ()

        loadout_id = entry.get("LoadoutID")
        self._loadout_id = str(loadout_id) if loadout_id is not None else None
        self._loadout_name = str(entry.get("LoadoutName") or "") or None

        if cmdr and self._loadout_id:
            record_loadout(
                cmdr,
                self._loadout_id,
                name=self._loadout_name or "",
                suit_key=self._suit_key,
                grade=self._grade,
                has_capacity_mod=self.has_capacity_mod,
            )

    def capacities(self, cmdr: Optional[str] = None) -> CapacityMap:
        """Backpack capacity per category; missing keys mean unknown."""
        if self._suit_key is None:
            return {}

        default = default_capacity(self._suit_key, self.has_capacity_mod)

        if not cmdr or not self._loadout_id:
            return default

        record = known_loadouts_for(cmdr).get(self._loadout_id)
        overrides = record.get("overrides", {}) if record else {}
        return {**default, **overrides}


def _split_suit_name(suit_name: str) -> tuple:
    """"explorationsuit_class3" -> ("explorationsuit", 3)."""
    key, _, suffix = suit_name.partition("_class")
    try:
        grade = int(suffix) if suffix else None
    except ValueError:
        grade = None
    return key, grade
