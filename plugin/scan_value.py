"""Exploration scan values: the estimate of what scanning a planet or star pays, as a pure module (no Tk, no EDMC).

The formula (per-planet-class k values plus a terraforming bonus, a mass exponent, and a first-discovery multiplier) is the same community-reverse-
engineered game formula every exploration-value tool uses; the constants come from Faber38/CMDRHelper (GPL-3.0, notice in THIRD-PARTY-NOTICES.md). These are
empirically determined game constants, not original creative expression. The base value is k + k * Q * mass^0.2 (at least 500); `estimate_planet_scan_value` is what scanning
pays and `estimate_planet_mapped_value` what scanning and mapping pays (the multipliers and the Odyssey and efficiency bonuses are from EDDiscovery's table, and OD Explorer's
figures agree with it).

`exploration_value.py` (the Exploration Value readout) and `system_survey.py` (the System targets and Body info cards) both use it.
"""

from __future__ import annotations

import math
from typing import Dict, Optional

# --- Formula constants -----------------------------------------------------

# Mass exponent applied to every planet class's base k value.
Q = 0.56591828

# Scan-time multiplier for a body nobody has ever scanned before.
FIRST_DISCOVERY_MULTIPLIER = 2.6

# (k, terraforming bonus) per PlanetClass, as the journal spells it.
# Terraformable bodies (TerraformState == "Terraformable") add the second
# number to k before applying the mass exponent below.
PLANET_K_VALUES: Dict[str, tuple[float, float]] = {
    "Ammonia world": (96932, 93328),
    "Earthlike body": (64831, 116295),
    "Water world": (64831, 116295),
    "High metal content body": (9654, 100677),
    "Metal rich body": (21790, 65631),
    "Icy body": (300, 93328),
    "Rocky body": (300, 93328),
    "Rocky ice body": (300, 93328),
    "Sudarsky class I gas giant": (1656, 93328),
    "Sudarsky class II gas giant": (9654, 100677),
    "Sudarsky class III gas giant": (300, 93328),
    "Sudarsky class IV gas giant": (300, 93328),
    "Sudarsky class V gas giant": (300, 93328),
    "Gas giant with ammonia based life": (300, 93328),
    "Gas giant with water based life": (300, 93328),
    "Helium rich gas giant": (300, 93328),
    "Helium gas giant": (300, 93328),
    "Water giant": (300, 93328),
    "Water giant with life": (300, 93328),
}
_DEFAULT_PLANET_K = (300.0, 93328.0)

STAR_K_MAIN_SEQUENCE = 1200.0
STAR_K_WHITE_DWARF = 14057.0
STAR_K_NEUTRON_OR_BLACK_HOLE = 22628.0

# StarType prefixes/values for the two exotic tiers above - everything else
# (O/B/A/F/G/K/M and their variants, T Tauri, Wolf-Rayet, carbon stars,
# etc.) uses the flat main-sequence k. White dwarf codes all start with
# "D" (DA/DAB/DAO/DAZ/DAV/DB/DBZ/DBV/DO/DOV/DQ/DC/DCV/DX); neutron stars
# are "N"; black holes are "H" or "SupermassiveBlackHole".
_WHITE_DWARF_PREFIX = "D"
_NEUTRON_OR_BLACK_HOLE_TYPES = {"N", "H", "SupermassiveBlackHole"}


def _star_k(star_type: str) -> float:
    if star_type in _NEUTRON_OR_BLACK_HOLE_TYPES:
        return STAR_K_NEUTRON_OR_BLACK_HOLE
    if star_type.startswith(_WHITE_DWARF_PREFIX):
        return STAR_K_WHITE_DWARF
    return STAR_K_MAIN_SEQUENCE


def _planet_base(planet_class: str, mass_em: Optional[float], terraformable: bool) -> float:
    """The base value of a planet before any multiplier: k plus k times Q times the mass to the 0.2 (at least 500). An Earth-like world is always counted as
    terraformable, as in the game's own table."""
    k, terra_bonus = PLANET_K_VALUES.get(planet_class, _DEFAULT_PLANET_K)
    if terraformable or planet_class == "Earthlike body":
        k += terra_bonus
    mass = mass_em if isinstance(mass_em, (int, float)) and mass_em > 0 else 1.0
    return max(k + k * math.pow(mass, 0.2) * Q, 500.0)


def estimate_planet_scan_value(
    planet_class: str, mass_em: Optional[float], terraformable: bool, was_discovered: Optional[bool],
) -> int:
    """Estimated credit value of scanning this planet (the value the in-game "Scan" event itself pays), before any DSS mapping. `was_discovered` is the
    journal's own field - False (nobody's ever scanned it) applies the first-discovery multiplier; True or None (already known, or undeterminable) does not."""
    value = _planet_base(planet_class, mass_em, terraformable)
    if was_discovered is False:
        value *= FIRST_DISCOVERY_MULTIPLIER
    return max(int(value), 0)


# Mapping multipliers on a planet's base value, from EDDiscovery's estimated values (Apache-2.0, notice in THIRD-PARTY-NOTICES.md), which agree with OD Explorer's:
# a body nobody had discovered or mapped; one that was discovered but never mapped; one already mapped. A good probe run (the efficiency target met) pays 25% more,
# and Odyssey adds 30% to the mapping part.
MAP_FIRST_DISCOVERED_AND_MAPPED = 3.699622554
MAP_FIRST_MAPPED_ONLY = 8.0956
MAP_ALREADY_MAPPED = 3.3333333
EFFICIENCY_BONUS = 1.25
ODYSSEY_BONUS = 0.3


def estimate_planet_mapped_value(
    planet_class: str, mass_em: Optional[float], terraformable: bool, was_discovered: Optional[bool], was_mapped: Optional[bool],
    efficient: bool = True, odyssey: bool = True,
) -> int:
    """Estimated credits for scanning and then mapping a planet (the mapping replaces the scan figure, it does not add to it). `was_discovered` and
    `was_mapped` are the journal's own fields (False: nobody had); `efficient` is whether the probe run met the efficiency target."""
    base = _planet_base(planet_class, mass_em, terraformable)
    first_discovery = was_discovered is False
    first_map = was_mapped is False
    if first_discovery and first_map:
        multiplier = MAP_FIRST_DISCOVERED_AND_MAPPED
    elif first_map:
        multiplier = MAP_FIRST_MAPPED_ONLY
    else:
        multiplier = MAP_ALREADY_MAPPED
    value = base * multiplier
    if odyssey:
        value += max(value * ODYSSEY_BONUS, 555.0)
    if first_discovery and first_map:
        value *= FIRST_DISCOVERY_MULTIPLIER
    if efficient:
        value *= EFFICIENCY_BONUS
    return max(int(value), 0)


def estimate_star_scan_value(
    stellar_mass: Optional[float], was_discovered: Optional[bool], star_type: str = "",
) -> int:
    """Estimated credit value of scanning this star for the first time this
    session. Stars can't be DSS-mapped, so this is their only scan value.
    `star_type` selects the k-value tier (main-sequence/white-dwarf/
    neutron-or-black-hole) - omit it (or pass an unrecognized type) for the
    flat main-sequence estimate."""
    k = _star_k(star_type)
    mass = stellar_mass if isinstance(stellar_mass, (int, float)) and stellar_mass > 0 else 1.0
    value = k + (mass * k / 66.25)
    if was_discovered is False:
        value *= FIRST_DISCOVERY_MULTIPLIER
    return max(int(value), 0)
