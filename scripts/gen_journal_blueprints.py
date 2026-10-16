#!/usr/bin/env python3
"""Regenerate plugin/journal_blueprints.py: how the journal names an engineering blueprint and how WNTB's blueprint table names it.

The ship's `Loadout` journal event (and the SLEF files EDSY and Coriolis export) name an engineered module's blueprint with an internal name such as
`Weapon_LongRange`, a level 1-5, and optionally an experimental effect such as `special_weapon_toughened`. WNTB's table (plugin/blueprints_data.py,
EDEngineer's) names blueprints for people: ("Beam Laser", "Long Range", grade 3). This script links the two. Run it by hand, never at build time:

    python scripts/gen_journal_blueprints.py

It needs the network and reads three public files (nothing about any player):
- EDCD/coriolis-data  modifications/blueprints.json and specials.json: the internal names, with a UUID per blueprint grade.
- msarilar/EDEngineer Resources/Data/blueprints.json: each of its rows carries the Coriolis UUID of its grade, so a UUID joins the two.
- plugin/blueprints_data.py (this repository): the names a match must land on, so a link to a row WNTB does not have is never written.

A blueprint with no UUID match falls back to a name match; whatever neither finds is printed, not guessed. Review the diff before committing.
"""
from __future__ import annotations

import json
import os
import re
import sys
import urllib.request
from collections import defaultdict

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)

from plugin import blueprints_data  # noqa: E402

CORIOLIS = "https://raw.githubusercontent.com/EDCD/coriolis-data/master/modifications/"
EDENGINEER = "https://raw.githubusercontent.com/msarilar/EDEngineer/master/EDEngineer/Resources/Data/blueprints.json"
OUT = os.path.join(ROOT, "plugin", "journal_blueprints.py")
NOT_SHIP_MODULES = ("Suit", "Weapon", "Unlock", "Human", "Guardian", "Technology")


def fetch(url: str):
    with urllib.request.urlopen(url, timeout=60) as response:
        return json.loads(response.read().decode("utf-8-sig"))


def norm(text: str) -> str:
    return re.sub(r"[^a-z0-9]", "", re.sub(r"\(.*?\)", "", text.lower()))


def plural_blind(text: str) -> str:
    return norm(text).rstrip("s")


WEAPONS = {"Beam Laser", "Burst Laser", "Cannon", "Fragment Cannon", "Mine Launcher", "Missile Rack", "Multi-cannon", "Plasma Accelerator",
           "Pulse Laser", "Rail Gun", "Torpedo Pylon"}
UTILITIES = {"Chaff Launcher", "Electronic Countermeasure", "Heat Sink Launcher", "Point Defence", "Wake Scanner", "Kill Warrant Scanner", "Manifest Scanner"}
SCANNERS = {"Wake Scanner", "Kill Warrant Scanner", "Manifest Scanner"}
FAMILY_TYPES = {
    "AFM": {"Auto Field-Maintenance Unit"}, "Armour": {"Armour"}, "CollectionLimpet": {"Collector Limpet Controller"}, "Engine": {"Thrusters"},
    "FSD": {"Frame Shift Drive"}, "FSDinterdictor": {"Frame Shift Drive Interdictor"}, "FuelScoop": {"Fuel Scoop"},
    "FuelTransferLimpet": {"Fuel Transfer Limpet Controller"}, "HatchBreakerLimpet": {"Hatch Breaker Limpet Controller"},
    "HullReinforcement": {"Hull Reinforcement Package"}, "LifeSupport": {"Life Support"}, "Misc": UTILITIES, "PowerDistributor": {"Power Distributor"},
    "PowerPlant": {"Power Plant"}, "ProspectingLimpet": {"Prospector Limpet Controller"}, "Refineries": {"Refinery"}, "Scanner": SCANNERS,
    "ShieldBooster": {"Shield Booster"}, "ShieldCellBank": {"Shield Cell Bank"}, "ShieldGenerator": {"Shield Generator"}, "Weapon": WEAPONS, "MC": WEAPONS,
    "Sensor": {"Sensors"},
}
"""Which of the table's module types a journal blueprint family applies to. Needed because EDEngineer gives every blueprint that shares a name
("Lightweight", "Reinforced", "Shielded") the same Coriolis UUID, whatever the module."""
FDNAME_TYPES = {
    "Misc_ChaffCapacity": {"Chaff Launcher"}, "Misc_HeatSinkCapacity": {"Heat Sink Launcher"}, "Misc_PointDefenseCapacity": {"Point Defence"},
    "Sensor_FastScan": SCANNERS, "Sensor_Expanded": {"Surface Scanner"},
}


def allowed_types(fdname: str) -> set:
    return set(FDNAME_TYPES.get(fdname) or FAMILY_TYPES.get(fdname.split("_")[0], set()))


def main() -> int:
    coriolis = fetch(CORIOLIS + "blueprints.json")
    specials = fetch(CORIOLIS + "specials.json")
    edengineer = fetch(EDENGINEER)

    module_rows = [r for r in blueprints_data.BLUEPRINT_ROWS if r[0] not in NOT_SHIP_MODULES and r[3] and not r[3][0].startswith("@")]
    table_types = {r[0] for r in module_rows}
    graded = defaultdict(set)      # module type -> blueprint names that have grades
    effects = defaultdict(set)     # module type -> experimental effect names (grade 0)
    for kind, name, grade, *_ in module_rows:
        (effects if grade == 0 else graded)[kind].add(name)

    by_uuid = defaultdict(set)
    for row in edengineer:
        if row.get("CoriolisGuid"):
            by_uuid[row["CoriolisGuid"]].add((row["Type"], row["Name"]))

    blueprint_names, unmapped, gaps = {}, [], []
    for fdname, info in sorted(coriolis.items()):
        allowed = allowed_types(fdname) & table_types
        by_type = {}
        for kind in sorted(allowed):
            linked = {n for k, n in set().union(*(by_uuid.get(gd["uuid"], set()) for gd in info["grades"].values())) if k == kind and n in graded[k]}
            words = set(re.findall(r"[a-z0-9]+", info["name"].lower()))
            worded = {n for n in graded[kind] if words <= set(re.findall(r"[a-z0-9]+", n.lower()))}
            exact = {n for n in (linked | worded) if norm(n) == norm(info["name"])}
            # a UUID link wins, but EDEngineer sometimes reuses a UUID inside one module type, so the words must agree; with no link, the words decide
            match = exact or ((linked & worded) if linked else worded) or linked
            if len(match) == 1:
                by_type[kind] = next(iter(match))
            elif match:
                gaps.append((fdname, kind, "ambiguous", sorted(match)))
            else:
                gaps.append((fdname, kind, "none", []))
        if by_type:
            blueprint_names[fdname] = by_type
        else:
            unmapped.append((fdname, info["name"]))

    special_names, unmapped_specials = {}, []
    for fdname, info in sorted(specials.items()):
        wanted = plural_blind(info["name"])
        candidates = sorted({n for names in effects.values() for n in names if plural_blind(n) == wanted})
        if candidates:
            special_names[fdname] = tuple(candidates)
        else:
            unmapped_specials.append((fdname, info["name"]))

    lines = ['"""How the journal names an engineering blueprint, and what WNTB\'s blueprint table calls it.', "",
             "AUTO-GENERATED by scripts/gen_journal_blueprints.py - do not hand-edit. Joins EDCD/coriolis-data's internal names (`modifications/blueprints.json`",
             "and `specials.json`; no license declared, so only the names are used) to plugin/blueprints_data.py (EDEngineer's, MIT) through the Coriolis UUID",
             "EDEngineer records for each blueprint grade, with a name match where it has none. See THIRD-PARTY-NOTICES.md.", '"""', "",
             "from __future__ import annotations", "", "from typing import Dict, Tuple", "",
             "# journal BlueprintName -> {module type: blueprint name} (grades 1 to 5 of that blueprint are in the table under that module type and name)",
             "BLUEPRINT_NAMES: Dict[str, Dict[str, str]] = {"]
    for fdname, kinds in blueprint_names.items():
        lines.append(f"    {fdname!r}: {kinds!r},")
    lines += ["}", "", "# journal ExperimentalEffect -> the names it can have in the table (grade 0 rows; the module type picks which one exists)",
              "SPECIAL_NAMES: Dict[str, Tuple[str, ...]] = {"]
    for fdname, names in special_names.items():
        lines.append(f"    {fdname!r}: {names!r},")
    lines += ["}", ""]
    with open(OUT, "w", encoding="utf-8", newline="\n") as handle:
        handle.write("\n".join(lines))
    print(f"{len(blueprint_names)} blueprints linked, {len(unmapped)} not: {unmapped}")
    print(f"{len(gaps)} module types with no single match: {gaps}")
    print(f"{len(special_names)} experimental effects linked, {len(unmapped_specials)} not: {unmapped_specials}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
