"""Map Frontier internal microresource IDs to human-readable display names."""

from __future__ import annotations

import json
from typing import Dict, Optional

from config import config

from .inventory_names_fdevids import FDEVIDS_DISPLAY_NAMES

# EDMC config key for names learned in previous sessions.
CONFIG_LEARNED_NAMES = "wntb_inventory_learned_names"

# Hand-curated overrides/additions, checked before FDEVIDS_DISPLAY_NAMES.
# The bulk of the table is generated (inventory_names_fdevids.py); these are
# internal names seen (or expected) in-game that the generated table doesn't
# (yet) list under this exact symbol. Kept as a safety net rather than
# deleted outright — remove an entry here once the generated table has it.
# Keys are canonicalised (lowercase, no spaces) Frontier internal names.
DISPLAY_NAMES: Dict[str, str] = {
    "biologicaldata": "Biological Data",
    "compositionalanalysis": "Compositional Analysis",
    "datamaterial": "Data Material",
    "electromagneticcoil": "Electromagnetic Coil",
    "energyconverter": "Energy Converter",
    "microswarmmissiles": "Micro Swarm Missiles",
    "microthermalcooler": "Micro Thermal Cooler",
    "microtransmitter": "Micro Transmitter",
    "microweavefiltering": "Micro Weave Filtering",
    "networkarchitecture": "Network Architecture",
    "networksecurity": "Network Security",
    "powerconverter": "Power Converter",
    "powerregulator": "Power Regulator",
    "radiationreport": "Radiation Report",
    "reactivearmour": "Reactive Armour",
    "reactorbalancingreport": "Reactor Balancing Report",
    "settlementplans": "Settlement Plans",
    "settlementprospects": "Settlement Prospects",
    "stabilisingcompound": "Stabilising Compound",
    "suitblueprint": "Suit Blueprint",
    "suitinstructions": "Suit Instructions",
    "thermalcoolingunits": "Thermal Cooling Units",
    "weaponblueprint": "Weapon Blueprint",
    "weaponexperimentals": "Weapon Experimentals",
    "weaponinstructions": "Weapon Instructions",
}


# Display names learned from Name_Localised at runtime, for resources not listed
# in DISPLAY_NAMES. Seeded from EDMC config at startup (see load_learned_names)
# and persisted back on shutdown, so the cache survives across sessions.
_LEARNED_NAMES: Dict[str, str] = {}


def load_learned_names() -> None:
    """Restore names learned in previous sessions from EDMC config."""
    raw = config.get_str(CONFIG_LEARNED_NAMES)
    if not raw:
        return

    try:
        learned = json.loads(raw)
    except (TypeError, ValueError):
        return

    if isinstance(learned, dict):
        _LEARNED_NAMES.update(
            (str(key), str(value)) for key, value in learned.items()
        )


def save_learned_names() -> None:
    """Persist names learned this session to EDMC config."""
    config.set(CONFIG_LEARNED_NAMES, json.dumps(_LEARNED_NAMES))


def canonicalise(name: str) -> str:
    """Match EDMC's canonicalisation: lowercase with no spaces."""
    return name.lower().replace(" ", "")


def remember(internal_name: str, localised_name: Optional[str]) -> None:
    """
    Learn a display name the journal told us about.

    Backpack / ShipLocker / BackpackChange entries carry Name_Localised for any
    resource whose display name differs from its internal ID, so the game itself
    supplies names for resources missing from DISPLAY_NAMES. Frontier's
    unresolved "$Token;" placeholders are ignored.
    """
    if not localised_name:
        return

    key = canonicalise(internal_name)
    label = localised_name.strip()
    if not key or not label or label.startswith("$"):
        return

    _LEARNED_NAMES[key] = label


def display_name(
    internal_name: str,
    localised_name: Optional[str] = None,
) -> str:
    """
    Resolve a journal item name to a human-readable label.

    Prefers the journal's Name_Localised when present, then our hand-curated
    overrides (DISPLAY_NAMES), then the generated FDevIDs table
    (FDEVIDS_DISPLAY_NAMES), then a name learned from an earlier journal
    entry, then a title-cased fallback derived from the internal ID.
    """
    if localised_name:
        return localised_name

    key = canonicalise(internal_name)
    if key in DISPLAY_NAMES:
        return DISPLAY_NAMES[key]
    if key in FDEVIDS_DISPLAY_NAMES:
        return FDEVIDS_DISPLAY_NAMES[key]
    if key in _LEARNED_NAMES:
        return _LEARNED_NAMES[key]

    # Fallback: split camelCase-ish internal IDs into words.
    return internal_name.replace("_", " ").title()
