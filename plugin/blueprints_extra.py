"""Hand-added entries the blueprint table lacks (EDEngineer's, March 2024): the Yi Shen unlock, which asks the commander to hand each of the other
three Colonia on-foot engineers (Baltanos, Eleanor Bresa, Rosa Dayette) a set of items.

**Sources**, all read in October 2026 and none of them from Frontier:
- The referral items are from Elite Dangerous Odyssey Materials Helper's English text (MIT; `blueprint.description.engineer_d1_1` to
  `engineer_d3`): 10 Faction Associates to Baltanos, 10 Manufacturing Instructions to Rosa Dayette, 10 Digital Designs to Eleanor Bresa. A Frontier forum
  thread and a community engineering guide (edblackbox.com's checklist, steps 50 to 53) say the same.
- Where each of the four is and how to unlock them is in `engineers_data.py` (EDDiscovery's table, which lists all four). Which suit and weapon
  upgrades each offers is in `blueprints_data.py`, from EDCoPilot's engineer list as ED-DDT applied it.

What goes in the table: one "Unlock" row for Yi Shen, so the wishlist and shopping list can count the three sets of items. The other three unlocks
are actions, not items, so they are text only (in `engineers_data.py`). The ingredients are micro-resources the Inventory already counts."""
from __future__ import annotations

from typing import Tuple

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

