"""The Odyssey suits and weapons the commander owns, from the journal: which item, what class it is now, and which modifications are fitted.

The Upgrade planner uses it to fill in the starting class and to leave out modifications an item already carries. The game writes a `SuitLoadout` event for each
loadout when you log in on foot (and `SwitchSuitLoadout`, `CreateSuitLoadout` when one changes), and each lists the suit (`SuitName` ends in `_classN`, `SuitMods`
are its modifications) and its weapons (`ModuleName`, `Class`, `WeaponMods`). The newest state of each suit and weapon wins, and `UpgradeSuit` / `UpgradeWeapon`
events after it raise the class. Only the commander of the newest journal is read (a journal names one commander), going back through the newest journals until
two of them have loadouts: a session that never went on foot has none. So it is what the game last listed, not a live inventory. Read on demand; nothing is
stored or sent.

The journal names modifications by their own ids (`suit_nightvision`, `weapon_range`); `SUIT_MODS` and `WEAPON_MODS` give the planner's names (a weapon's range,
headshot damage and hip-fire accuracy have one id for the three weapon families, which the planner spells with the family in brackets). The ids and the item
names are the game's, as EDDI's definitions and real journals agree."""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass, replace
from typing import Any, Dict, List, Optional, Tuple

from . import journal_files, odyssey_upgrade_plan

try:
    from config import appname
except ImportError:  # unit tests outside EDMC
    appname = "EDMarketConnector"

plugin_name = os.path.basename(os.path.dirname(__file__))
logger = logging.getLogger(f"{appname}.{plugin_name}")

MAX_FILES = 80                     # how far back to look for a journal with loadouts
LOADOUT_FILES = 2                  # stop after this many journals with loadouts in them
_LOADOUT_EVENTS = ("SuitLoadout", "SwitchSuitLoadout", "CreateSuitLoadout")
_EVENTS = journal_files.event_pattern(*_LOADOUT_EVENTS, "UpgradeSuit", "UpgradeWeapon", "Commander")

SUITS = {"utilitysuit": "Maverick", "explorationsuit": "Artemis", "tacticalsuit": "Dominator"}
"""The journal's suit kind (the part of `SuitName` before `_classN`) to the planner's name. The Flight Suit has no upgrades."""

WEAPONS = {
    "wpn_m_assaultrifle_kinetic_fauto": "Karma AR-50", "wpn_m_submachinegun_kinetic_fauto": "Karma C-44", "wpn_s_pistol_kinetic_sauto": "Karma P-15",
    "wpn_m_launcher_rocket_sauto": "Karma L-6",
    "wpn_m_assaultrifle_laser_fauto": "TK Aphelion", "wpn_m_submachinegun_laser_fauto": "TK Eclipse", "wpn_s_pistol_laser_sauto": "TK Zenith",
    "wpn_m_sniper_plasma_charged": "Manticore Executioner", "wpn_m_shotgun_plasma_doublebarrel": "Manticore Intimidator",
    "wpn_m_assaultrifle_plasma_fauto": "Manticore Oppressor", "wpn_s_pistol_plasma_charged": "Manticore Tormentor",
}

SUIT_MODS = {
    "suit_increasedmeleedamage": "Added melee damage", "suit_adsmovementspeed": "Combat Movement Speed", "suit_improvedarmourrating": "Damage resistance",
    "suit_improvedradar": "Enhanced tracking", "suit_increasedammoreserves": "Extra ammo capacity", "suit_backpackcapacity": "Extra backpack capacity",
    "suit_increasedshieldregen": "Faster shield regen", "suit_increasedbatterycapacity": "Improved battery capacity",
    "suit_improvedjumpassist": "Improved jump assist", "suit_increasedo2capacity": "Increased air reserves",
    "suit_increasedsprintduration": "Increased sprint duration", "suit_nightvision": "Night vision", "suit_quieterfootsteps": "Quieter footsteps",
    "suit_reducedtoolbatteryconsumption": "Reduced tool battery consumption",
}
WEAPON_MODS = {
    "weapon_suppression_unpressurised": "Audio Masking", "weapon_handling": "Faster handling", "weapon_range": "Greater range ({family})",
    "weapon_headshotdamage": "Headshot damage ({family})", "weapon_accuracy": "Improved Hip Fire Accuracy ({family})", "weapon_clipsize": "Magazine size",
    "weapon_suppression_pressurised": "Noise suppressor", "weapon_reloadspeed": "Reload speed", "weapon_scope": "Scope", "weapon_stability": "Stability",
    "weapon_backpackreloading": "Stowed reloading",
}


@dataclass(frozen=True)
class OwnedGear:
    item: odyssey_upgrade_plan.Gear
    current: int                       # the class it is now, 1 to 5
    fitted: Tuple[str, ...]            # the planner's names of the modifications it carries
    unknown_mods: Tuple[str, ...]      # journal ids the planner has no name for
    loadout: str                       # the loadout it was last seen in

    @property
    def label(self) -> str:
        return f"{self.item.label}, class {self.current}" + (f" ({self.loadout})" if self.loadout else "")


def _class(value: Any) -> int:
    return value if isinstance(value, int) and not isinstance(value, bool) and 1 <= value <= 5 else 0


def _mods(raw: Any, names: Dict[str, str], family: str = "") -> Tuple[List[str], List[str]]:
    known, unknown = [], []
    for mod in raw if isinstance(raw, list) else []:
        if not isinstance(mod, str):
            continue
        name = names.get(mod)
        (known if name else unknown).append(name.format(family=family) if name else mod)
    return known, unknown


def from_loadouts(entries: List[Dict[str, Any]]) -> List[OwnedGear]:
    """The suits and weapons in `entries` (loadout and upgrade events, oldest first); the newest sighting of each suit and weapon wins, and an upgrade
    after it raises the class. Anything with no upgrade table (the Flight Suit, a weapon the planner does not know) is left out."""
    found: Dict[Any, OwnedGear] = {}
    for entry in entries:
        event = entry.get("event")
        if event in ("UpgradeSuit", "UpgradeWeapon"):
            key = ("suit", entry.get("SuitID")) if event == "UpgradeSuit" else ("weapon", entry.get("SuitModuleID"))
            if key in found and _class(entry.get("Class")):
                found[key] = replace(found[key], current=entry["Class"])
            continue
        loadout = str(entry.get("LoadoutName") or "")[:40]
        suit_name = str(entry.get("SuitName") or "")
        kind, _, tail = suit_name.rpartition("_class")
        suit = odyssey_upgrade_plan.gear(f"{SUITS[kind]} suit") if kind in SUITS else None
        if suit is not None and tail.isdigit() and _class(int(tail)):
            known, unknown = _mods(entry.get("SuitMods"), SUIT_MODS)
            found[("suit", entry.get("SuitID") or suit_name)] = OwnedGear(suit, int(tail), tuple(known), tuple(unknown), loadout)
        for module in entry.get("Modules") if isinstance(entry.get("Modules"), list) else []:
            if not isinstance(module, dict):
                continue
            weapon = odyssey_upgrade_plan.gear(WEAPONS.get(str(module.get("ModuleName") or ""), ""))
            if weapon is None or not _class(module.get("Class")):
                continue
            known, unknown = _mods(module.get("WeaponMods"), WEAPON_MODS, weapon.family)
            found[("weapon", module.get("SuitModuleID") or module.get("ModuleName"))] = OwnedGear(weapon, module["Class"], tuple(known), tuple(unknown), loadout)
    return sorted(found.values(), key=lambda g: (g.item.kind != "Suit", g.item.name.casefold(), g.current))


def owned_gear(folder: Optional[str] = None) -> List[OwnedGear]:
    """The suits and weapons the commander of the newest journal owns, from the newest journals. An empty list when there is no journal folder or no loadout."""
    entries: List[Dict[str, Any]] = []
    try:
        files = journal_files.files_modified_since(0.0, folder)
        commander: Optional[str] = None
        with_loadouts = 0
        for path in reversed(files[-MAX_FILES:]):
            events = list(journal_files.read_events(path, _EVENTS))
            name = next((str(e.get("Name") or "") for e in events if e.get("event") == "Commander"), "")
            if commander is None:
                commander = name
            if name != commander:
                continue                                           # another commander's session
            entries[:0] = [e for e in events if e.get("event") != "Commander"]
            if any(e.get("event") in _LOADOUT_EVENTS for e in events):
                with_loadouts += 1
                if with_loadouts >= LOADOUT_FILES:
                    break
    except Exception:
        logger.debug("Could not read the commander's gear from the journals", exc_info=True)
        return []
    return from_loadouts(entries)
