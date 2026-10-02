"""Odyssey on-foot backpack, ship locker, and fleet carrier inventory tracking."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, Iterable, List, Mapping, Optional, Tuple, Union

from .inventory_names import canonicalise, display_name, remember

# Categories tracked for suit/weapon upgrade assets.
TRACKED_CATEGORIES: Tuple[str, ...] = ("Component", "Item", "Data")

# Short in-game wording per category, e.g. for warning/status messages.
CATEGORY_SHORT: Dict[str, str] = {
    "Component": "Assets",
    "Item": "Goods",
    "Data": "Data",
}

# Ship locker holds up to 1000 of each category.
SHIP_LOCKER_CAPACITY: Dict[str, int] = {category: 1000 for category in TRACKED_CATEGORIES}

# Fraction of SHIP_LOCKER_CAPACITY at which ship_locker_capacity_warnings() fires.
WARNING_THRESHOLD = 0.9

# CAPI /fleetcarrier carrierLocker keys → journal microresource categories.
# Frontier labels locker sections assets/goods/data; journal uses Component/Item/Data.
CARRIER_LOCKER_CATEGORY_MAP: Dict[str, str] = {
    "assets": "Component",
    "goods": "Item",
    "data": "Data",
}

InventoryStore = Dict[str, Dict[str, int]]
CarrierCacheEntry = Tuple[InventoryStore, Optional[str]]


def _empty_store() -> InventoryStore:
    return {category: {} for category in TRACKED_CATEGORIES}


class InventoryTracker:
    """Maintains backpack, ship locker, and fleet carrier counts for upgrade microresources."""

    def __init__(self) -> None:
        self._backpack: InventoryStore = _empty_store()
        self._ship_locker: InventoryStore = _empty_store()
        self._fleet_carrier_locker: InventoryStore = _empty_store()
        self._fleet_carrier_callsign: Optional[str] = None
        self._commander: Optional[str] = None
        self._carrier_cache: Dict[str, CarrierCacheEntry] = {}
        self._backpack_baseline_seen: bool = False
        self._locker_capacity_warned: set = set()

    @property
    def commander(self) -> Optional[str]:
        return self._commander

    @property
    def backpack_baseline_seen(self) -> bool:
        """
        Whether a real Backpack/Resupply baseline has been received this session.

        EDMC only populates state['BackPack'] in response to a Backpack/Resupply
        journal event, and clears it on LoadGame. A commander who logs in already
        on foot may not get a fresh Backpack event for a while, during which the
        backpack reads as empty without this actually meaning "empty".
        """
        return self._backpack_baseline_seen

    @property
    def backpack(self) -> InventoryStore:
        return self._backpack

    @property
    def ship_locker(self) -> InventoryStore:
        return self._ship_locker

    @property
    def fleet_carrier_locker(self) -> InventoryStore:
        return self._fleet_carrier_locker

    @property
    def fleet_carrier_callsign(self) -> Optional[str]:
        return self._fleet_carrier_callsign

    def sync_backpack_from_state(self, state: Mapping[str, Any]) -> None:
        """Replace backpack counts from EDMC monitor state."""
        backpack_state = state.get("BackPack", {})
        self._backpack = self._store_from_edmc_categories(backpack_state)

    def sync_ship_locker_from_state(self, state: Mapping[str, Any]) -> None:
        """Replace ship locker counts from EDMC monitor state."""
        self._ship_locker = self._store_from_edmc_categories(state)

    def sync_all_from_state(self, state: Mapping[str, Any]) -> None:
        """Synchronise both backpack and ship locker from EDMC state."""
        # EDMC clears state['BackPack'] on LoadGame too, so the baseline flag
        # resets in lockstep with the data it describes.
        self._backpack_baseline_seen = False
        self.sync_backpack_from_state(state)
        self.sync_ship_locker_from_state(state)

    def ship_locker_capacity_warnings(self) -> List[Tuple[str, int, int]]:
        """
        Categories that have just crossed WARNING_THRESHOLD of ship locker capacity.

        A category only yields once per crossing: it won't repeat on
        subsequent calls while still over threshold, but rearms (can warn
        again) once it drops back under threshold and later crosses again —
        e.g. after offloading via a ship or an Apex shuttle mid-mission.
        """
        warnings = []

        for category in TRACKED_CATEGORIES:
            capacity = SHIP_LOCKER_CAPACITY[category]
            total = sum(self._ship_locker.get(category, {}).values())
            over_threshold = total >= capacity * WARNING_THRESHOLD

            if over_threshold and category not in self._locker_capacity_warned:
                self._locker_capacity_warned.add(category)
                warnings.append((category, total, capacity))
            elif not over_threshold:
                self._locker_capacity_warned.discard(category)

        return warnings

    def set_commander(self, cmdr: str) -> bool:
        """
        Switch the active commander.

        Persists the outgoing commander's carrier locker to an in-memory cache
        and restores any cached carrier data for the new commander. Commanders
        without a carrier (or not yet fetched via CAPI) start with an empty
        carrier locker.
        """
        if not cmdr:
            return False
        if cmdr == self._commander:
            return False

        self._persist_carrier_cache()
        self._commander = cmdr
        self._restore_carrier_cache(cmdr)
        return True

    def apply_backpack_baseline(self, entry: Mapping[str, Any]) -> None:
        """Apply a Backpack / Resupply journal entry or Backpack.json payload."""
        self._backpack = self._store_from_journal_sections(entry)
        self._backpack_baseline_seen = True

    def apply_ship_locker_baseline(self, entry: Mapping[str, Any]) -> None:
        """Apply a ShipLocker journal entry or ShipLocker.json payload."""
        self._ship_locker = self._store_from_journal_sections(entry, ship_locker=True)

    def apply_backpack_change(
        self,
        entry: Mapping[str, Any],
    ) -> Iterable[Tuple[str, str, str, int, int]]:
        """
        Process a BackpackChange event.

        Yields (display_label, internal_name, category, delta, new_backpack_total)
        for each Added item. Removed items update counts but are not yielded.
        """
        if entry.get("Added"):
            for item in entry["Added"]:
                yield from self._apply_change_item(item, delta_sign=1, pillage=True)

        if entry.get("Removed"):
            for item in entry["Removed"]:
                for _ in self._apply_change_item(item, delta_sign=-1, pillage=False):
                    pass

    def get_backpack_total(self, internal_name: str, category: str) -> int:
        key = canonicalise(internal_name)
        return self._backpack.get(category, {}).get(key, 0)

    def get_combined_total(self, internal_name: str, category: str) -> int:
        key = canonicalise(internal_name)
        backpack = self._backpack.get(category, {}).get(key, 0)
        locker = self._ship_locker.get(category, {}).get(key, 0)
        carrier = self._fleet_carrier_locker.get(category, {}).get(key, 0)
        return backpack + locker + carrier

    def apply_fleet_carrier_locker(
        self,
        carrier_locker: Mapping[str, Any],
        *,
        callsign: Optional[str] = None,
        cmdr: str,
    ) -> int:
        """
        Replace fleet carrier microresource counts from CAPI carrierLocker data.

        Data is stored per commander so switching accounts does not bleed counts
        between CMDRs. Returns the number of distinct resource stacks stored.
        """
        store = _store_from_carrier_locker(carrier_locker)
        stack_count = sum(len(items) for items in store.values())
        self._carrier_cache[cmdr] = (deepcopy(store), callsign)

        if cmdr == self._commander:
            self._fleet_carrier_locker = store
            self._fleet_carrier_callsign = callsign

        return stack_count

    def clear_fleet_carrier_locker(self) -> None:
        """Drop active fleet carrier locker data."""
        self._fleet_carrier_locker = _empty_store()
        self._fleet_carrier_callsign = None

    def clear_fleet_carrier_for_commander(self, cmdr: str) -> None:
        """Drop cached and active carrier locker data for one commander."""
        self._carrier_cache.pop(cmdr, None)
        if cmdr == self._commander:
            self.clear_fleet_carrier_locker()

    def _persist_carrier_cache(self) -> None:
        if self._commander:
            self._carrier_cache[self._commander] = (
                deepcopy(self._fleet_carrier_locker),
                self._fleet_carrier_callsign,
            )

    def _restore_carrier_cache(self, cmdr: str) -> None:
        cached = self._carrier_cache.get(cmdr)
        if cached is None:
            self.clear_fleet_carrier_locker()
            return

        self._fleet_carrier_locker, self._fleet_carrier_callsign = (
            deepcopy(cached[0]),
            cached[1],
        )

    def snapshot(self) -> Dict[str, InventoryStore]:
        return {
            "backpack": deepcopy(self._backpack),
            "ship_locker": deepcopy(self._ship_locker),
            "fleet_carrier_locker": deepcopy(self._fleet_carrier_locker),
        }

    def _apply_change_item(
        self,
        item: Mapping[str, Any],
        *,
        delta_sign: int,
        pillage: bool,
    ) -> Iterable[Tuple[str, str, str, int, int]]:
        category = self._normalise_category(item.get("Type", ""))
        if category not in TRACKED_CATEGORIES:
            return

        internal_name = canonicalise(str(item.get("Name", "")))
        if not internal_name:
            return

        remember(internal_name, item.get("Name_Localised"))
        count = int(item.get("Count", 0))
        delta = count * delta_sign
        store = self._backpack[category]
        new_total = max(0, store.get(internal_name, 0) + delta)
        store[internal_name] = new_total

        if pillage and delta > 0:
            label = display_name(
                internal_name,
                item.get("Name_Localised"),
            )
            yield label, internal_name, category, delta, new_total

    @staticmethod
    def _normalise_category(category: str) -> str:
        mapping = {
            "component": "Component",
            "item": "Item",
            "data": "Data",
            "consumable": "Consumable",
        }
        return mapping.get(category.lower(), category)

    @classmethod
    def _store_from_edmc_categories(
        cls,
        source: Mapping[str, Any],
    ) -> InventoryStore:
        store = _empty_store()
        for category in TRACKED_CATEGORIES:
            category_data = source.get(category, {})
            if isinstance(category_data, Mapping):
                store[category] = {
                    canonicalise(str(name)): int(count)
                    for name, count in category_data.items()
                    if int(count) > 0
                }
        return store

    @classmethod
    def _store_from_journal_sections(
        cls,
        entry: Mapping[str, Any],
        *,
        ship_locker: bool = False,
    ) -> InventoryStore:
        section_map = {
            "Component": "Components" if ship_locker else "Components",
            "Item": "Items" if ship_locker else "Items",
            "Data": "Data",
        }
        store = _empty_store()

        for category, section_key in section_map.items():
            for item in entry.get(section_key, []):
                name = canonicalise(str(item.get("Name", "")))
                count = int(item.get("Count", 0))
                remember(name, item.get("Name_Localised"))
                if name and count > 0:
                    store[category][name] = count

        return store


def _store_from_carrier_locker(carrier_locker: Mapping[str, Any]) -> InventoryStore:
    store = _empty_store()
    for section_key, category in CARRIER_LOCKER_CATEGORY_MAP.items():
        for entry in _iter_capi_locker_entries(carrier_locker.get(section_key)):
            name = canonicalise(str(entry.get("name", "")))
            quantity = int(entry.get("quantity", 0))
            remember(name, entry.get("locName"))
            if name and quantity > 0:
                store[category][name] = quantity
    return store


def _iter_capi_locker_entries(
    section: Union[List[Any], Mapping[str, Any], None],
) -> Iterable[Mapping[str, Any]]:
    """Normalise CAPI list-or-dict sections into locker entry mappings."""
    if isinstance(section, list):
        for entry in section:
            if isinstance(entry, Mapping):
                yield entry
        return

    if isinstance(section, Mapping):
        for entry in section.values():
            if isinstance(entry, Mapping):
                yield entry
