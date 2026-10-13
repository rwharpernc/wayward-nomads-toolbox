"""What a blueprint, or the whole wishlist, needs against what the commander holds. Pure (no Tk): the counts are passed in as a `Holdings`, so
this is tested without a game.

Counts: ship materials (Raw, Manufactured, Encoded) come from `materials.py`; Odyssey micro-resources from the Inventory's backpack and ship
locker (not the fleet carrier's locker, which cannot be crafted from). Commodities (a Technology Broker unlock takes trade goods) and anything the
tables could not match are NOT counted: they show as needed with no holding, and an entry that needs one says so instead of claiming to be
ready or not.

**Ready** is worked out in the order of the list, as the commander would craft: each entry takes what it needs from what is held, and a later
entry only sees what is left. An entry that cannot be made takes nothing, so one that is short does not use up materials a later entry could
use. The combined list adds the same ingredient across entries and weighs it once against what is held."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Dict, Iterable, List, Optional, Tuple

from . import blueprints
from .blueprint_wishlist import WishItem


@dataclass(frozen=True)
class Holdings:
    ship: Callable[[str], int]       # a ship material's key -> pieces held
    odyssey: Callable[[str], int]    # a micro-resource's key -> pieces in the backpack and ship locker

    def of(self, ingredient: blueprints.Ingredient) -> Optional[int]:
        """Pieces held of an ingredient; None when the ingredient is not counted."""
        if ingredient.key is None:
            return None
        if ingredient.kind == blueprints.SHIP:
            return max(0, int(self.ship(ingredient.key)))
        if ingredient.kind == blueprints.ODYSSEY:
            return max(0, int(self.odyssey(ingredient.key)))
        return None


@dataclass(frozen=True)
class Need:
    """One ingredient and how much of it is needed, held and short."""
    ingredient: blueprints.Ingredient
    need: int
    have: Optional[int]          # None when the ingredient is not counted

    @property
    def short(self) -> Optional[int]:
        return None if self.have is None else max(0, self.need - self.have)


@dataclass(frozen=True)
class EntryStatus:
    item: WishItem
    blueprint: blueprints.Blueprint
    needs: Tuple[Need, ...]      # for the entry alone, weighed against what is left after the entries before it
    ready: bool                  # every counted ingredient is covered
    uncounted: Tuple[str, ...]   # names of the ingredients that could not be counted


@dataclass(frozen=True)
class Shopping:
    entries: Tuple[EntryStatus, ...]
    needs: Tuple[Need, ...]      # the whole list added up, ingredient by ingredient, weighed once against what is held

    @property
    def short_pieces(self) -> int:
        return sum(n.short or 0 for n in self.needs)

    @property
    def ready_count(self) -> int:
        return sum(1 for e in self.entries if e.ready)

    @property
    def all_ready(self) -> bool:
        return bool(self.entries) and self.short_pieces == 0


def needs_for(blueprint: blueprints.Blueprint, crafts: int, holdings: Holdings) -> List[Need]:
    """The ingredients of `crafts` crafts of a blueprint against what is held."""
    return [Need(i, i.count * max(1, crafts), holdings.of(i)) for i in blueprint.ingredients]


def _slot(ingredient: blueprints.Ingredient) -> Tuple[str, str]:
    return (ingredient.kind, ingredient.key or ingredient.name.casefold())


def shopping_list(items: Iterable[WishItem], holdings: Holdings) -> Shopping:
    """Weigh every wishlist entry, in order, against what is held, and add the whole list up."""
    left: Dict[Tuple[str, str], int] = {}
    totals: Dict[Tuple[str, str], Need] = {}
    entries: List[EntryStatus] = []
    for item in items:
        blueprint = item.blueprint
        if blueprint is None:
            continue
        needs: List[Need] = []
        for ingredient in blueprint.ingredients:
            slot = _slot(ingredient)
            have = holdings.of(ingredient)
            if have is not None and slot not in left:
                left[slot] = have
            amount = ingredient.count * item.crafts
            needs.append(Need(ingredient, amount, None if have is None else left[slot]))
            old = totals.get(slot)
            totals[slot] = Need(ingredient, amount + (old.need if old else 0), have)
        uncounted = tuple(n.ingredient.name for n in needs if n.have is None)
        ready = all(n.have is None or n.have >= n.need for n in needs)
        if ready:
            for n in needs:
                if n.have is not None:
                    left[_slot(n.ingredient)] -= n.need
        entries.append(EntryStatus(item, blueprint, tuple(needs), ready, uncounted))
    ordered = sorted(totals.values(), key=lambda n: (n.have is None, -(n.short or 0), n.ingredient.name.casefold()))
    return Shopping(tuple(entries), tuple(ordered))
