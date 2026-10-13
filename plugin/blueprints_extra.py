"""Hand-added entries for what the blueprint table (EDEngineer, March 2024) lacks: the four Colonia on-foot engineers, Baltanos, Eleanor Bresa,
Rosa Dayette and Yi Shen, who the journal lists but the table does not.

**Sources**, all read on 2026-10-13 and none of them from Frontier:
- The unlock steps and the referral items are from Elite Dangerous Odyssey Materials Helper's English text (MIT; `blueprint.description.engineer_d1_1`
  to `engineer_d3`): Baltanos asks for Friendly reputation with the Colonia Council; Rosa Dayette for 10 Culinary or Cocktail Recipes sold in
  Colonia; Eleanor Bresa for docking and disembarking at 5 settlements in the Colonia system; Yi Shen opens once the referral task of each of the
  other three is done (10 Faction Associates to Baltanos, 10 Manufacturing Instructions to Rosa Dayette, 10 Digital Designs to Eleanor Bresa).
  A Frontier forum thread and a community engineering guide (edblackbox.com's checklist, steps 50 to 53) say the same.
- The places are from that guide only, and it marks them unconfirmed: Baltanos at The Divine Apparatus in Deriso, Eleanor Bresa at Bresa
  Modifications in Desy, Rosa Dayette at Rosa's Shop in Kojeara, Yi Shen at Eidolon Hold in Einheriar.
- They offer suit and weapon modifications. Which modification each offers is NOT here: the sources disagree, so it is not guessed.

What goes in the table: one "Unlock" row for Yi Shen, so the wishlist and shopping list can count the three sets of items. The other three unlocks
are actions, not items, so they are text only (`NOTES`). The ingredients are micro-resources the Inventory already counts."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Tuple

# Same shape as blueprints_data.BLUEPRINT_ROWS: (type, name, grade, engineers, ((ingredient, count), ...), ((property, effect, is good), ...)).
# For this row the "engineers" are the three who are handed the items.
EXTRA_ROWS: Tuple[tuple, ...] = (
    ("Unlock", "Yi Shen", 0, ("Baltanos", "Eleanor Bresa", "Rosa Dayette"),
     (("Faction Associates", 10), ("Digital Designs", 10), ("Manufacturing Instructions", 10)), ()),
)

# Same shape as blueprints_data.INGREDIENT_ROWS: (name, kind, canonical name, group, where it is found). The canonical names are the Inventory's keys.
EXTRA_INGREDIENTS: Tuple[tuple, ...] = (
    ("Faction Associates", "OdysseyIngredient", "factionassociates", "Data", ("Downloaded from the CMD data ports in settlement command rooms",)),
    ("Digital Designs", "OdysseyIngredient", "digitaldesigns", "Data", ()),
    ("Manufacturing Instructions", "OdysseyIngredient", "manufacturinginstructions", "Data", ()),
)


@dataclass(frozen=True)
class Note:
    name: str       # the engineer's name as the game writes it
    where: str       # system and settlement, from the community guide (unconfirmed)
    unlock: str      # what unlocking them asks for, in words
    source: str


_SOURCE = "Odyssey Materials Helper (MIT) and a community guide; none from Frontier."
NOTES: Dict[str, Note] = {
    "baltanos": Note("Baltanos", "The Divine Apparatus, Deriso", "Reach Friendly reputation with the Colonia Council.", _SOURCE),
    "eleanor bresa": Note("Eleanor Bresa", "Bresa Modifications, Desy", "Dock and disembark at 5 settlements in the Colonia system.", _SOURCE),
    "rosa dayette": Note("Rosa Dayette", "Rosa's Shop, Kojeara", "Sell 10 Culinary or Cocktail Recipes in total to stations in Colonia.", _SOURCE),
    "yi shen": Note("Yi Shen", "Eidolon Hold, Einheriar", "Complete all three referral tasks.", _SOURCE),
}
"""By `engineers.name_key` of the engineer."""
