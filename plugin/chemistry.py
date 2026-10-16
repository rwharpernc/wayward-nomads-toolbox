"""Element symbols and compound formulas, so the plugin names a substance the same short way everywhere: iron is Fe, sodium is Na, sulfur is S, carbon dioxide is CO2.

Elite's materials, the atmospheres and compositions in a scan, and volcanism descriptions all name chemicals in words ("sulphur", "CarbonDioxide", "thin carbon
dioxide atmosphere"). Cards are narrow, so WNTB writes the symbol or formula the periodic table and ordinary chemistry use instead. One place decides how:

- `element(name)`: the symbol for an element's name (English and the game's spellings: sulphur and sulfur, aluminium and aluminum), or None.
- `gas(name)`: the formula of an atmosphere component, which the scan gives in CamelCase ("CarbonDioxide", "Nitrogen"). Nitrogen, oxygen and hydrogen are the
  molecules (N2, O2, H2) as they are in an atmosphere; the noble gases are single atoms (He, Ne, Ar).
- `shorten(text)`: the compounds and gases named inside a description ("thin carbon dioxide atmosphere" becomes "thin CO2 atmosphere", "sulphur dioxide magma" becomes
  "SO2 magma"). Other words, and a silicate or metallic vapour, are left alone.
- `label(name)`: what to show for a material or element name: the symbol when it is one and the style is symbols, else the name as given.

The style is the Appearance setting "Element and compound names": Symbols (the default) or Full names. Everything that shows such a name asks here, so the choice
applies to every card, panel and window. Pure apart from reading that one setting; no Tk.
"""

from __future__ import annotations

import re
from typing import Dict, Optional

try:
    from config import config
except ImportError:   # unit tests outside EDMC
    config = None

CFG_STYLE = "wntb_chemistry_style"
SYMBOLS, NAMES = "symbols", "names"
STYLE_CHOICES = (("Symbols (Fe, CO2)", SYMBOLS), ("Full names (Iron, carbon dioxide)", NAMES))
DEFAULT_STYLE = SYMBOLS

ELEMENTS: Dict[str, str] = {
    "hydrogen": "H", "helium": "He", "lithium": "Li", "beryllium": "Be", "boron": "B", "carbon": "C", "nitrogen": "N", "oxygen": "O", "fluorine": "F", "neon": "Ne",
    "sodium": "Na", "magnesium": "Mg", "aluminium": "Al", "aluminum": "Al", "silicon": "Si", "phosphorus": "P", "sulphur": "S", "sulfur": "S", "chlorine": "Cl",
    "argon": "Ar", "potassium": "K", "calcium": "Ca", "scandium": "Sc", "titanium": "Ti", "vanadium": "V", "chromium": "Cr", "manganese": "Mn", "iron": "Fe",
    "cobalt": "Co", "nickel": "Ni", "copper": "Cu", "zinc": "Zn", "gallium": "Ga", "germanium": "Ge", "arsenic": "As", "selenium": "Se", "bromine": "Br",
    "krypton": "Kr", "yttrium": "Y", "zirconium": "Zr", "niobium": "Nb", "molybdenum": "Mo", "technetium": "Tc", "ruthenium": "Ru", "palladium": "Pd", "silver": "Ag",
    "cadmium": "Cd", "indium": "In", "tin": "Sn", "antimony": "Sb", "tellurium": "Te", "iodine": "I", "xenon": "Xe", "hafnium": "Hf", "tantalum": "Ta",
    "tungsten": "W", "rhenium": "Re", "osmium": "Os", "platinum": "Pt", "gold": "Au", "mercury": "Hg", "lead": "Pb", "bismuth": "Bi", "polonium": "Po",
    "thorium": "Th", "uranium": "U",
}

# Compounds and the gases of an atmosphere, by the words the game uses (lower case, spaces for the CamelCase gaps).
COMPOUNDS: Dict[str, str] = {
    "carbon dioxide": "CO2", "sulphur dioxide": "SO2", "sulfur dioxide": "SO2", "methane": "CH4", "ammonia": "NH3", "water": "H2O",
    "nitrogen": "N2", "oxygen": "O2", "hydrogen": "H2", "helium": "He", "neon": "Ne", "argon": "Ar", "krypton": "Kr", "xenon": "Xe",
    "carbon monoxide": "CO", "nitrous oxide": "N2O", "ozone": "O3",
}

_COMPOUND_WORDS = re.compile(r"\b(" + "|".join(sorted((re.escape(k) for k in COMPOUNDS), key=len, reverse=True)) + r")\b", re.IGNORECASE)


def style() -> str:
    """The saved style: symbols unless the commander chose full names."""
    if config is None:
        return DEFAULT_STYLE
    try:
        value = config.get_str(CFG_STYLE)
    except Exception:
        return DEFAULT_STYLE
    return NAMES if value == NAMES else DEFAULT_STYLE


def symbols_on() -> bool:
    return style() == SYMBOLS


def element(name: str) -> Optional[str]:
    """The symbol for an element's name ("Sulphur" gives "S"), or None when it is not one."""
    return ELEMENTS.get(str(name or "").strip().casefold())


def _words(name: str) -> str:
    """'CarbonDioxide' as 'carbon dioxide'; text that already has spaces is just lower-cased."""
    text = str(name or "").strip()
    if " " not in text:
        text = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", text)
    return text.casefold()


def gas(name: str) -> str:
    """The formula of an atmosphere component ("CarbonDioxide" gives "CO2"), or the name itself when it is not one WNTB knows; the name as given with full names."""
    if not symbols_on():
        return str(name or "")
    return COMPOUNDS.get(_words(name), str(name or ""))


def shorten(text: str) -> str:
    """`text` with the compounds and gases it names written as formulas ("thin carbon dioxide atmosphere" gives "thin CO2 atmosphere"); unchanged with full names."""
    if not symbols_on() or not text:
        return text
    return _COMPOUND_WORDS.sub(lambda m: COMPOUNDS[m.group(1).casefold()], text)


def label(name: str) -> str:
    """What to show for a material or element name: its symbol when it is an element (or a compound) and the style is symbols, else the name as given."""
    if not symbols_on():
        return str(name or "")
    found = element(name)
    return found if found is not None else str(name or "")
