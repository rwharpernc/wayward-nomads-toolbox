"""
The market category of each colonization commodity, so a shopping list can be grouped the way the in-game market groups it.

The grouping and its spelling follow SrvSurvey's (see docs/ATTRIBUTIONS.md): the category a commodity is listed under in the game's
commodity market. Keys are the lower-case journal names that `colonisation.commodity_key` gives. A commodity not listed here falls
under `OTHER`, which sorts last, so a commodity added by a later game update still shows.
"""
from __future__ import annotations

from typing import Dict

OTHER = "Other"

_BY_CATEGORY = {
    "Chemicals": ("liquidoxygen", "pesticides", "surfacestabilisers", "water"),
    "Consumer Items": ("evacuationshelter", "survivalequipment"),
    "Foods": ("animalmeat", "coffee", "fish", "foodcartridges", "fruitandvegetables", "grain", "tea"),
    "Industrial Materials": ("ceramiccomposites", "cmmcomposite", "insulatingmembrane", "polymers", "semiconductors", "superconductors"),
    "Legal Drugs": ("beer", "liquor", "wine"),
    "Machinery": ("buildingfabricators", "cropharvesters", "emergencypowercells", "geologicalequipment", "microbialfurnaces",
                  "heliostaticfurnaces", "mineralextractors", "powergenerators", "thermalcoolingunits", "waterpurifiers"),
    "Medicines": ("agriculturalmedicines", "basicmedicines", "combatstabilisers", "combatstabilizers"),
    "Metals": ("aluminium", "copper", "steel", "titanium"),
    "Technology": ("advancedcatalysers", "autofabricators", "bioreducinglichen", "computercomponents", "hazardousenvironmentsuits",
                   "landenrichmentsystems", "terrainenrichmentsystems", "medicaldiagnosticequipment", "microcontrollers", "muonimager",
                   "mutomimager", "resonatingseparators", "robotics", "structuralregulators"),
    "Textiles": ("militarygradefabrics",),
    "Waste": ("biowaste",),
    "Weapons": ("battleweapons", "nonlethalweapons", "reactivearmour"),
}

CATEGORY_OF: Dict[str, str] = {key: category for category, keys in _BY_CATEGORY.items() for key in keys}


def category_for(key: str) -> str:
    """The market category of a commodity key, or OTHER."""
    return CATEGORY_OF.get(key, OTHER)


def sort_key(category: str) -> tuple:
    """Categories in the order the market lists them (alphabetical), with OTHER last."""
    return (category == OTHER, category.casefold())
