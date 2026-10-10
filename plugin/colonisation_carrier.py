"""
How much of each commodity has been moved onto the commander's fleet carrier, for the Colonization Sites window's FC
column. Pure logic plus a small per-commander JSON file (`colonisation_carrier.json` beside the plugin).

Where the numbers come from: `CargoTransfer` (`Transfers` of `Type`, `Count`, `Direction` "tocarrier" / "toship") written
while docked at the commander's own fleet carrier (`StationType` "FleetCarrier" in `Docked` / `Location`; only the owner
can transfer cargo, and a squadron carrier is a different `StationType`). The figure for a commodity is the net tonnes
moved there: to the carrier minus back to the ship, never below zero.

What it cannot see: stock that reached the carrier another way (bought through its market, a trade order) or left it
(sold, a trade order, moved by a squadron mate) is not a `CargoTransfer`, so it is not counted. It is "what this tool
saw you transfer", not the carrier's hold.

A commander "has a fleet carrier" as Trade sees it (`set_external_check`: their Settings choice there, else a fleet
carrier Trade has recorded, which it reads from the recent journals at start-up), or once we have seen one: a transfer at it, a `CarrierStats` / `CarrierBuy` for one, or a
dock at a fleet carrier. Only then does the window show the column.

Like colonization deliveries, a transfer is an addition, so counting one twice would be wrong. Each commander's record
keeps `journal_at`, the time of the newest transfer folded in, and a transfer is applied only if it is newer. That makes
the start-up catch-up from the journals (`catch_up`) safe next to the live events.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Dict, Iterable, List, Optional

from . import colonisation, commander_data, journal_files

try:
    from config import appname
except ImportError:  # unit tests outside EDMC
    appname = "EDMarketConnector"

plugin_name = os.path.basename(os.path.dirname(__file__))
logger = logging.getLogger(f"{appname}.{plugin_name}")

STATE_FILENAME = "colonisation_carrier.json"
FLEET_STATION = "FleetCarrier"
DEFAULT_DAYS = 14
MAX_DAYS = 30
_WANTED = journal_files.event_pattern(
    "Commander", "LoadGame", "Docked", "Location", "Undocked", "CargoTransfer", "CarrierStats", "CarrierBuy")

Record = Dict[str, Any]   # {"has_carrier": bool, "tonnes": {commodity key: int}, "journal_at": iso}


def _empty() -> Record:
    return {"has_carrier": False, "tonnes": {}, "journal_at": ""}


def _is_legacy(_raw: Any) -> bool:
    return False   # the file is new; nothing older to claim


class CarrierCargo:
    """Per-commander count of tonnes transferred to the fleet carrier. Constructed empty; `load(plugin_dir)` is called
    from the colonization panel's start."""

    def __init__(self) -> None:
        self._store = commander_data.new_store()
        self._plugin_dir: Optional[str] = None
        self._listeners: List[Callable[[], None]] = []
        self._external: Optional[Callable[[str], Optional[bool]]] = None

    def set_external_check(self, check: Callable[[str], Optional[bool]]) -> None:
        """Another feature that knows about the commander's carriers (Trade). It answers True / False when it knows,
        None when it does not; its answer wins, so both features always agree and a commander's Settings choice in
        Trade (None, Fleet, Squadron, Both, Auto) applies here too."""
        self._external = check

    # --- persistence ---------------------------------------------------------
    def load(self, plugin_dir: str) -> None:
        self._plugin_dir = plugin_dir
        self._store = commander_data.read(os.path.join(plugin_dir, STATE_FILENAME), _is_legacy)

    def add_listener(self, callback: Callable[[], None]) -> None:
        self._listeners.append(callback)

    def _save_and_notify(self) -> None:
        if self._plugin_dir is not None:
            commander_data.write(os.path.join(self._plugin_dir, STATE_FILENAME), self._store)
        for listener in self._listeners:
            listener()

    # --- reading -------------------------------------------------------------
    def _record(self, cmdr: str) -> Record:
        return commander_data.payload_for(self._store, cmdr, _empty)

    def has_carrier(self, cmdr: str) -> bool:
        if not cmdr:
            return False
        if self._external is not None:
            try:
                answer = self._external(cmdr)
            except Exception:
                logger.debug("The external fleet carrier check failed", exc_info=True)
                answer = None
            if answer is not None:
                return answer
        return commander_data.known(self._store, cmdr) and bool(self._record(cmdr).get("has_carrier"))

    def tonnes(self, cmdr: str) -> Dict[str, int]:
        """Net tonnes moved to the carrier, by commodity key (only commodities with some there)."""
        if not cmdr or not commander_data.known(self._store, cmdr):
            return {}
        return {key: amount for key, amount in self._record(cmdr).get("tonnes", {}).items() if amount > 0}

    def watermark(self, cmdr: str) -> Optional[datetime]:
        if not cmdr or not commander_data.known(self._store, cmdr):
            return None
        return colonisation._parse_time(self._record(cmdr).get("journal_at"))   # noqa: SLF001 - same package

    # --- writing -------------------------------------------------------------
    def note_carrier(self, cmdr: str) -> bool:
        """Remember that this commander has a fleet carrier. True if that was news."""
        if not commander_data.key_for(cmdr):
            return False
        record = self._record(cmdr)
        if record.get("has_carrier"):
            return False
        record["has_carrier"] = True
        return True

    def apply_transfer(self, cmdr: str, entry: Dict[str, Any]) -> bool:
        """Fold a `CargoTransfer` made at the commander's fleet carrier in. True if anything changed."""
        if not commander_data.key_for(cmdr):
            return False
        record = self._record(cmdr)
        stamp = str(entry.get("timestamp") or "")
        if stamp and record.get("journal_at") and stamp <= record["journal_at"]:
            return False   # already counted (a journal read twice, or caught up after the live event)
        changed = self.note_carrier(cmdr)
        tonnes = record.setdefault("tonnes", {})
        for transfer in entry.get("Transfers") or []:
            if not isinstance(transfer, dict):
                continue
            direction = str(transfer.get("Direction") or "").lower()
            key = colonisation.commodity_key(transfer.get("Type"))
            try:
                count = int(transfer.get("Count") or 0)
            except (TypeError, ValueError):
                count = 0
            if not key or count <= 0 or direction not in ("tocarrier", "toship"):
                continue
            before = tonnes.get(key, 0)
            after = max(0, before + (count if direction == "tocarrier" else -count))
            if after != before:
                tonnes[key] = after
                changed = True
        if stamp:
            record["journal_at"] = stamp
            changed = True
        return changed

    def commit(self) -> None:
        self._save_and_notify()


class Feeder:
    """Turns a stream of journal events (one commander's, in order) into updates on a `CarrierCargo`. Tracks whether the
    commander is docked at a fleet carrier, which is the only place a transfer is theirs to count."""

    def __init__(self, cargo: CarrierCargo, cmdr: str = "") -> None:
        self.cargo = cargo
        self.cmdr = cmdr
        self._at_fleet_carrier = False

    def feed(self, entry: Dict[str, Any]) -> bool:
        """True if the stored figures changed (the caller then `commit`s)."""
        event = entry.get("event")
        if event == "Commander" and entry.get("Name"):
            self.cmdr = str(entry["Name"])
            return False
        if event == "LoadGame":
            if entry.get("Commander"):
                self.cmdr = str(entry["Commander"])
            self._at_fleet_carrier = False
            return False
        if event in ("Docked", "Location"):
            docked = event == "Docked" or bool(entry.get("Docked"))
            self._at_fleet_carrier = docked and entry.get("StationType") == FLEET_STATION
            return False
        if event == "Undocked":
            self._at_fleet_carrier = False
            return False
        if not self.cmdr:
            return False
        if event in ("CarrierStats", "CarrierBuy"):
            ctype = entry.get("CarrierType")
            if ctype in (None, "", "FleetCarrier"):   # CarrierBuy of an old build carries no type
                return self.cargo.note_carrier(self.cmdr)
            return False
        if event == "CargoTransfer" and self._at_fleet_carrier:
            return self.cargo.apply_transfer(self.cmdr, entry)
        return False


def start_epoch(cargo: CarrierCargo, cmdrs: Iterable[str], now: Optional[datetime] = None) -> float:
    """Where to read the journals from: the oldest watermark among the known commanders, else DEFAULT_DAYS back; never
    further than MAX_DAYS."""
    now = now or datetime.now(timezone.utc)
    floor = now - timedelta(days=MAX_DAYS)
    since = now - timedelta(days=DEFAULT_DAYS)
    for cmdr in cmdrs:
        mark = cargo.watermark(cmdr)
        if mark is not None and mark < since:
            since = mark
    return max(since, floor).timestamp()


def catch_up(cargo: CarrierCargo, cmdrs: Iterable[str], folder: Optional[str] = None) -> int:
    """Read the recent journals and fold in transfers not yet counted. Returns how many files changed something."""
    changed = 0
    for path in journal_files.files_modified_since(start_epoch(cargo, cmdrs), folder):
        feeder = Feeder(cargo)
        touched = False
        for entry in journal_files.read_events(path, _WANTED):
            touched = feeder.feed(entry) or touched
        if touched:
            changed += 1
    if changed:
        cargo.commit()
    return changed


carrier_cargo = CarrierCargo()
