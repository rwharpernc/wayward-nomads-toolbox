"""Engineering blueprints: what each one takes and where the ingredients are found. The pure part (no Tk); the data is `blueprints_data.py`
(imported from EDEngineer, MIT; see its header and THIRD-PARTY-NOTICES.md) and the counts it is weighed against are the commander's materials
(`materials.py`) and Odyssey inventory (`inventory.py`).

A blueprint is a module type (Frame Shift Drive, Suit, ...), a name (Increased Range), a grade (1 to 5, or 0 for one that has none: a
Technology Broker unlock, a Guardian item, an engineer unlock, a synthesis recipe) and the ingredients ONE craft takes. How many crafts it
takes to reach a result is up to the game's rolls, which WNTB cannot know; the wishlist (`blueprint_wishlist.py`) asks the commander for it.

Engineers: the data lists who offers a blueprint, with two stand-ins, `@Synthesis` (a recipe anyone can make with the synthesis panel) and
`@Technology` (the Technology Broker), shown here as "Synthesis" and "Technology Broker".

Each ingredient has a kind, because the counts live in different places: `SHIP` (Raw, Manufactured and Encoded materials, key as in
`materials.py`), `ODYSSEY` (micro-resources, key as in the Inventory) and `COMMODITY` (a Technology Broker unlock needs trade goods; not
counted). The data is older than the game: blueprints or materials added since March 2024 may be missing, and the guide says so."""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Tuple

from .blueprints_data import BLUEPRINT_ROWS, INGREDIENT_ROWS
from .materials import CATALOG

SHIP = "ship"
ODYSSEY = "odyssey"
COMMODITY = "commodity"

STAND_INS = {"@Synthesis": "Synthesis", "@Technology": "Technology Broker"}
UNLOCK_TYPE = "Unlock"

# Names the blueprint data spells differently from the game's material table (FDevIDs), checked 2026-10-13. Case-folded.
ALIASES = {
    "abnormal compact emission data": "compactemissionsdata",
    "guardian wreckage components": "guardian_sentinel_wreckagecomponents",
}

_SHIP_KINDS = ("Material", "Data")
_BY_NAME: Dict[str, str] = {m.name.casefold(): m.key for m in CATALOG.values()}


@dataclass(frozen=True)
class Ingredient:
    name: str
    count: int
    kind: str                     # SHIP, ODYSSEY or COMMODITY
    key: Optional[str]            # what the counts are kept under; None when the name could not be matched
    group: str                    # the data's own group, e.g. "ShieldData" or "Chemicals"
    found: Tuple[str, ...]        # where it is found, in the data's words


@dataclass(frozen=True)
class Effect:
    prop: str
    effect: str
    good: bool


@dataclass(frozen=True)
class Blueprint:
    type: str
    name: str
    grade: int
    engineers: Tuple[str, ...]
    ingredients: Tuple[Ingredient, ...]
    effects: Tuple[Effect, ...]

    @property
    def id(self) -> str:
        return f"{self.type}|{self.name}|{self.grade}"

    @property
    def title(self) -> str:
        return f"{self.name} (grade {self.grade})" if self.grade else self.name

    @property
    def is_unlock(self) -> bool:
        return self.type == UNLOCK_TYPE


def ship_key(name: str) -> Optional[str]:
    """The key of a Raw, Manufactured or Encoded material given its display name (case and spacing ignored), or None."""
    text = " ".join(str(name or "").split()).casefold()
    return _BY_NAME.get(text) or ALIASES.get(text)


def _build_sources() -> Dict[str, Tuple[str, Optional[str], str, Tuple[str, ...]]]:
    out: Dict[str, Tuple[str, Optional[str], str, Tuple[str, ...]]] = {}
    for name, kind, formatted, group, origins in INGREDIENT_ROWS:
        if kind in _SHIP_KINDS:
            out[name] = (SHIP, ship_key(name), group, tuple(origins))
        elif kind == "OdysseyIngredient":
            out[name] = (ODYSSEY, formatted, group, tuple(origins))
        else:
            out[name] = (COMMODITY, formatted.casefold(), group, tuple(origins))
    return out


_SOURCES = _build_sources()


def _build() -> Tuple[Blueprint, ...]:
    out: List[Blueprint] = []
    for kind, name, grade, engineers, ingredients, effects in BLUEPRINT_ROWS:
        made = []
        for ingredient, count in ingredients:
            what, key, group, found = _SOURCES.get(ingredient, (COMMODITY, None, "", ()))
            made.append(Ingredient(ingredient, count, what, key, group, found))
        out.append(Blueprint(kind, name, grade, tuple(STAND_INS.get(e, e) for e in engineers), tuple(made),
                             tuple(Effect(p, e, g) for p, e, g in effects)))
    return tuple(out)


ALL: Tuple[Blueprint, ...] = _build()
_BY_ID: Dict[str, Blueprint] = {b.id: b for b in ALL}


def get(blueprint_id: str) -> Optional[Blueprint]:
    return _BY_ID.get(blueprint_id)


def types() -> List[str]:
    """Every module type, A to Z."""
    return sorted({b.type for b in ALL}, key=str.casefold)


def names_for(kind: str) -> List[str]:
    """The blueprint names of a module type, A to Z."""
    return sorted({b.name for b in ALL if b.type == kind}, key=str.casefold)


def grades_for(kind: str, name: str) -> List[Blueprint]:
    """The grades of one blueprint, lowest first."""
    return sorted((b for b in ALL if b.type == kind and b.name == name), key=lambda b: b.grade)


def search(query: str = "", kind: Optional[str] = None, limit: int = 400) -> List[Blueprint]:
    """Blueprints whose type, name, engineers, effects or ingredients contain every word of `query` (case-folded), optionally for one
    module type, at most `limit`."""
    words = [w for w in re.split(r"\s+", query.casefold().strip()) if w]
    found: List[Blueprint] = []
    for b in ALL:
        if kind and b.type != kind:
            continue
        text = " ".join((b.type, b.name, *b.engineers, *(f"{e.prop} {e.effect}" for e in b.effects), *(i.name for i in b.ingredients))).casefold()
        if all(w in text for w in words):
            found.append(b)
            if len(found) >= limit:
                break
    return found


def unresolved(blueprints: Iterable[Blueprint] = ALL) -> List[Tuple[str, str]]:
    """(blueprint, ingredient) pairs whose ingredient could not be matched to anything that is counted. Empty for the shipped data except
    commodities, which are never counted."""
    return [(b.id, i.name) for b in blueprints for i in b.ingredients if i.kind != COMMODITY and i.key is None]
