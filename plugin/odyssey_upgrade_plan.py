"""Odyssey suit and weapon upgrade planner - pure logic (no Tk, no network): what it costs to take a suit or a weapon from one class to another, and to fit
up to four modifications, ready for the wishlist.

**Upgrades.** Taking an item to the next class takes materials (the "Merchant" rows of the blueprint table, type Suit or Weapon, named for the item, one per
class 2 to 5) and credits. The materials were corrected on 2026-10-15 to what the game charges today (see blueprints_data.py): the schematic, the family item
and Manufacturing Instructions (or Health Monitor) take 1, 2, 4 and 5 for classes 2 to 5, and the item's other two materials 2, 5, 9 and 12. The credits are
a per-item unit times 1, 3, 6 and 10 for classes 2 to 5 (`CLASS_FACTOR`); the unit is known only for the items seen in real `UpgradeSuit` / `UpgradeWeapon`
journal events (`CREDIT_UNIT`), so for the others the credits are reported as unknown rather than guessed.

**Modifications.** An item can carry up to four (`MAX_MODS`). Each is a Suit or Weapon blueprint of the table with its materials; a weapon modification
whose name ends in a family in brackets, such as "(Kinematic kinetic)", is only for that family (Karma is Kinematic kinetic, Manticore is Manticore plasma, TK
is Takada laser) and the rest are offered for every weapon. Whether the game offers every one of those for every weapon is not known. The engineer's fee for
a modification is not in the table, so it is not counted.

`Plan.entries()` gives (blueprint id, 1) for each step and modification, for blueprint_wishlist.WishBook.add_many."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Tuple

from . import blueprints

MAX_MODS = 4
CLASSES = (1, 2, 3, 4, 5)
CLASS_FACTOR: Dict[int, int] = {2: 1, 3: 3, 4: 6, 5: 10}
"""Credits to reach a class, as a multiple of the item's unit: seen for classes 2 to 5 on several items (1, 3, 6, 10)."""

CREDIT_UNIT: Dict[str, int] = {
    "Karma AR-50": 625_000, "Karma C-44": 375_000, "Karma L-6": 700_000, "Manticore Tormentor": 250_000, "Manticore Executioner": 875_000,
    "Maverick": 750_000, "Artemis": 750_000, "Dominator": 600_000,
}
"""Credits to reach class 2, per item, from `UpgradeSuit` / `UpgradeWeapon` events in real journals (2025-2026). Each is confirmed by at least one event
(for example the Karma AR-50 cost 1,875,000 to class 3, 3,750,000 to 4 and 6,250,000 to 5). The other items are not here until one is seen."""

FAMILIES = (("Karma", "Kinematic kinetic"), ("Manticore", "Manticore plasma"), ("TK", "Takada laser"))
NOT_GEAR = ("Unlock",)


class OdysseyPlanError(ValueError):
    """The choice cannot be planned; the message says why."""


@dataclass(frozen=True)
class Gear:
    name: str                          # the table's name: "Karma AR-50", "Maverick"
    kind: str                          # "Suit" or "Weapon"
    family: str                        # a weapon's family as modification names spell it, "" for a suit

    @property
    def label(self) -> str:
        return f"{self.name} suit" if self.kind == "Suit" else self.name

    @property
    def credit_unit(self) -> Optional[int]:
        return CREDIT_UNIT.get(self.name)

    @property
    def confirmed(self) -> bool:
        """Its credits (and so its materials) were seen in a real upgrade event."""
        return self.name in CREDIT_UNIT


def _family(name: str) -> str:
    return next((family for prefix, family in FAMILIES if name.startswith(prefix + " ")), "")


def _gear() -> Tuple[Gear, ...]:
    seen: Dict[Tuple[str, str], Gear] = {}
    for b in blueprints.ALL:
        if b.type in ("Suit", "Weapon") and b.grade >= 2 and "Merchant" in b.engineers:
            seen.setdefault((b.type, b.name), Gear(b.name, b.type, _family(b.name) if b.type == "Weapon" else ""))
    return tuple(sorted(seen.values(), key=lambda g: (g.kind != "Suit", g.name.casefold())))


GEAR: Tuple[Gear, ...] = _gear()
_BY_LABEL: Dict[str, Gear] = {g.label: g for g in GEAR}
_GEAR_NAMES = {(g.kind, g.name) for g in GEAR}


def labels() -> List[str]:
    return [g.label for g in GEAR]


def gear(label: str) -> Optional[Gear]:
    return _BY_LABEL.get(label)


def modifications_for(item: Gear) -> List[str]:
    """The names of the modifications the table offers for `item`, A to Z."""
    names = set()
    for b in blueprints.ALL:
        if b.type != item.kind or b.grade != 0 or (b.type, b.name) in _GEAR_NAMES or b.type in NOT_GEAR:
            continue
        if item.kind == "Weapon" and "(" in b.name:
            if not b.name.endswith(f"({item.family})"):
                continue
        names.add(b.name)
    return sorted(names, key=str.casefold)


def _steps(item: Gear, current: int, target: int) -> List[blueprints.Blueprint]:
    steps = []
    for grade in range(current + 1, target + 1):
        found = next((b for b in blueprints.grades_for(item.kind, item.name) if b.grade == grade), None)
        if found is None:
            raise OdysseyPlanError(f"The table has no class {grade} upgrade for {item.label}.")
        steps.append(found)
    return steps


def credits_to(item: Gear, current: int, target: int) -> Optional[int]:
    """Credits to take `item` from class `current` to `target`, or None when the item's unit is not known."""
    unit = item.credit_unit
    if unit is None:
        return None
    return sum(unit * CLASS_FACTOR[cls] for cls in range(current + 1, target + 1))


@dataclass(frozen=True)
class Plan:
    item: Gear
    current: int
    target: int
    steps: Tuple[blueprints.Blueprint, ...]
    mods: Tuple[blueprints.Blueprint, ...]
    credits: Optional[int]                    # None when the item's credit cost is not known (and 0 when no class step is planned)

    def entries(self) -> List[Tuple[str, int]]:
        """(blueprint id, crafts) for the whole plan: each class step once and each modification once."""
        return [(b.id, 1) for b in (*self.steps, *self.mods)]

    def notes(self) -> List[str]:
        out = []
        if self.steps:
            if self.credits is None:
                out.append(f"The credit cost of {self.item.label} has not been recorded yet, so no credits are shown for it.")
            if not self.item.confirmed:
                out.append(f"{self.item.label}'s materials are EDEngineer's list for it with the game's current counts; they have not been confirmed by an "
                           "upgrade event of this item.")
        if self.mods:
            out.append("Modification fees (the engineer's credits) are not in the table and not counted.")
        return out


def plan(item: Gear, current: int, target: int, mod_names: Sequence[str] = ()) -> Plan:
    """The plan for taking `item` from class `current` to `target` (equal means no upgrade) and fitting `mod_names`."""
    for value in (current, target):
        if isinstance(value, bool) or value not in CLASSES:
            raise OdysseyPlanError("A class is a whole number from 1 to 5.")
    if target < current:
        raise OdysseyPlanError("The target class cannot be lower than the current one.")
    chosen = [n for n in mod_names if n]
    if len(chosen) > MAX_MODS:
        raise OdysseyPlanError(f"An item carries at most {MAX_MODS} modifications.")
    if len(set(chosen)) != len(chosen):
        raise OdysseyPlanError("Each modification can be fitted once.")
    allowed = set(modifications_for(item))
    mods = []
    for name in chosen:
        if name not in allowed:
            raise OdysseyPlanError(f"{name} is not offered for {item.label}.")
        mods.append(next(b for b in blueprints.ALL if b.type == item.kind and b.name == name and b.grade == 0))
    steps = _steps(item, current, target)
    return Plan(item, current, target, tuple(steps), tuple(mods), credits_to(item, current, target))
