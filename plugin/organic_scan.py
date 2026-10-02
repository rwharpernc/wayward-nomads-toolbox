"""
Organic Scanning: pure logic (no Tk) for exobiology tracking.

Meant to sit alongside the EDMC-Canonn plugin (a separate EDMC plugin, not a
WNTB dependency) rather than duplicate it: that plugin submits
codex/journal/biology data to Canonn's cloud and shows per-system codex
icons, but does not do per-genus species prediction, per-organism
scan-stage tracking, scan-distance/exclusion-zone guidance, or credit
estimates. That gap is this module's whole scope - a local, read-only
companion, never a second submission pipeline. Nothing
here talks to any network service.

Species/genus reference data (organic_species_data.py) is empirically-
determined game data - see that module's own docstring and
THIRD-PARTY-NOTICES.md for the sourcing note.

Scope boundaries (see organic_species_data.py's own comments for the
full list): no first-discovery credit bonus (Odyssey exobiology analysis
reward is a flat per-species value regardless of who found it first).
Per-body state (conditions, detected genera, confirmed-species scan
progress) *does* persist across sessions - see organic_scan_state.py and
organic_scan_panel.py's own cmdr-switch handling - unlike
discovery.py/interdiction.py/landing.py's ephemeral precedent, since a
planet's biology doesn't reset just because you logged out. Galactic-region,
Guardian-proximity, and trace-atmosphere-composition matching (the three
gaps this module's predictions used to carry unconditionally) are now
implemented - see ruleset_matches() and organic_region_data.py.

Follows survey_log.py's/waypoint_route.py's own `try/except ImportError`
fallback for `appname` so this stays genuinely unit-testable outside a
live EDMC install.
"""

from __future__ import annotations

import logging
import math
import os
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

try:
    from config import appname
except ImportError:
    appname = "EDMarketConnector"

from . import organic_region_data as region_data
from . import organic_species_data as species_data

plugin_name = os.path.basename(os.path.dirname(__file__))
logger = logging.getLogger(f"{appname}.{plugin_name}")

# ScanOrganic's own ScanType progression - Log (first visit), Sample (second,
# far enough from the first), Analyse (third, far enough from the second -
# this is the one that actually pays out).
STAGE_ORDER = ("Log", "Sample", "Analyse")
REQUIRED_SAMPLES = len(STAGE_ORDER)

# Journal unit conversions to the units organic_species_data.py's rulesets
# use (G, confirmed against the well-known community fact that every
# bio-bearing world is capped at 0.605-0.61G surface gravity - the data's own
# max_gravity values cluster right at that boundary).
_STANDARD_GRAVITY_MS2 = 9.80665
_PASCALS_PER_ATM = 101325.0


def gravity_ms2_to_g(surface_gravity_ms2: float) -> float:
    return surface_gravity_ms2 / _STANDARD_GRAVITY_MS2


def pressure_pa_to_atm(surface_pressure_pa: float) -> float:
    return surface_pressure_pa / _PASCALS_PER_ATM


@dataclass
class BodyConditions:
    """Conditions of the body currently being surveyed - built from its own
    Scan journal event (see organic_scan_panel.py) plus the system name and
    the illuminating star's StarType (approximated as the system's main/
    arrival star, same simplification exploration_value.py's own system-age
    readout already makes - may be wrong for a body orbiting a secondary
    star in a multi-star system)."""

    body_name: str
    planet_class: Optional[str] = None
    atmosphere: Optional[str] = None
    gravity_g: Optional[float] = None
    temperature_k: Optional[float] = None
    pressure_atm: Optional[float] = None
    volcanism: Optional[str] = None  # raw journal string, e.g. "major water geysers volcanism", or "" for none
    star_type: Optional[str] = None
    system_name: Optional[str] = None
    galactic_position: Optional[Tuple[float, float, float]] = None
    """The system's own journal-reported StarPos (x, y, z, light years) -
    feeds SpeciesRuleset.regions/guardian via organic_region_data.py. None
    when no FSDJump/Location event carrying StarPos has been seen yet this
    session (matches every other "unknown doesn't eliminate" field here)."""
    atmosphere_components: Optional[Dict[str, float]] = None
    """Trace-gas name -> percent, from the body's own Scan event
    `AtmosphereComposition` array - not the same thing as `atmosphere`
    (AtmosphereType, the dominant gas only). Feeds
    SpeciesRuleset.atmosphere_component."""
    system_body_types: Optional[Tuple[str, ...]] = None
    """Every PlanetClass scanned so far this system (not just the body
    currently being evaluated) - feeds SpeciesRuleset.bodies, which asks
    "does this *system* have a body of one of these types anywhere",
    unrelated to `planet_class` above (the scanned body's own type).
    Computed fresh by the caller (organic_scan_panel.py) from every body
    it's tracked this system, not tracked here - this class stays "one
    body's own state" otherwise."""


def _in_range(value: Optional[float], lo: Optional[float], hi: Optional[float]) -> bool:
    if lo is not None and (value is None or value < lo):
        return False
    if hi is not None and (value is None or value > hi):
        return False
    return True


def _region_id(cond: BodyConditions) -> Optional[int]:
    if cond.galactic_position is None:
        return None
    return region_data.region_id_for_position(*cond.galactic_position)


def _region_matches(codes: Tuple[str, ...], region_id: int) -> bool:
    """One `SpeciesRuleset.regions` entry, evaluated the same way the
    source data's own checker does: every '!code' entry must NOT contain
    `region_id` (any violation eliminates immediately), and if there's at
    least one non-'!' entry, `region_id` must appear in one of them."""
    positive_codes = [c for c in codes if not c.startswith("!")]
    for code in codes:
        if code.startswith("!") and region_id in region_data.REGION_GROUPS.get(code[1:], ()):
            return False
    if positive_codes and not any(region_id in region_data.REGION_GROUPS.get(c, ()) for c in positive_codes):
        return False
    return True


def _distance_ly(position: Tuple[float, float, float], coordinates: Tuple[float, float, float]) -> float:
    dx = position[0] - coordinates[0]
    dy = position[1] - coordinates[1]
    dz = position[2] - coordinates[2]
    return math.sqrt(dx * dx + dy * dy + dz * dz)


def _guardian_matches(cond: BodyConditions) -> bool:
    if cond.galactic_position is None:
        return True  # unknown position: don't eliminate, same as every other unset field
    for max_distance_ly, coordinates in region_data.GUARDIAN_ZONES.values():
        if _distance_ly(cond.galactic_position, coordinates) < max_distance_ly:
            return True
    return False


def _tuber_matches(zones: Tuple[str, ...], cond: BodyConditions) -> bool:
    if cond.galactic_position is None:
        return True  # unknown position: don't eliminate, same as every other unset field
    check_all = "Any" in zones
    for name, (distance_range, coordinates) in region_data.TUBER_ZONES.items():
        if not check_all and name not in zones:
            continue
        min_ly, max_ly = distance_range
        distance = _distance_ly(cond.galactic_position, coordinates)
        if min_ly <= distance <= max_ly:
            return True
    return False


def _bodies_matches(required_types: Tuple[str, ...], cond: BodyConditions) -> bool:
    if cond.system_body_types is None:
        return True  # not yet computed/known: don't eliminate, same as every other unset field
    return any(t in required_types for t in cond.system_body_types)


def ruleset_matches(ruleset: species_data.SpeciesRuleset, cond: BodyConditions) -> bool:
    """Whether `cond` satisfies `ruleset` - conservative in one direction
    only: a condition this module doesn't check (orbital period/parent-
    star/body's-own-distance-requirement - see organic_species_data.py's
    own comment) is simply not evaluated, so a species may show as a
    candidate slightly more often than the real game would allow, never
    less. The same holds for `regions`/`guardian`/`tuber`/`bodies`
    specifically when the relevant state isn't known yet (no
    FSDJump/Location seen this session, or no other bodies scanned yet)."""
    if ruleset.atmosphere is not None and cond.atmosphere not in ruleset.atmosphere:
        return False
    if ruleset.body_type is not None and cond.planet_class not in ruleset.body_type:
        return False
    if not _in_range(cond.gravity_g, ruleset.min_gravity, ruleset.max_gravity):
        return False
    if not _in_range(cond.temperature_k, ruleset.min_temperature, ruleset.max_temperature):
        return False
    if not _in_range(cond.pressure_atm, ruleset.min_pressure, ruleset.max_pressure):
        return False
    if ruleset.star is not None and cond.star_type not in ruleset.star:
        return False
    if ruleset.system is not None and cond.system_name != ruleset.system:
        return False
    if ruleset.requires_volcanism is True and not cond.volcanism:
        return False
    if ruleset.requires_volcanism is False and cond.volcanism:
        return False
    if ruleset.volcanism is not None:
        if not cond.volcanism:
            return False
        haystack = cond.volcanism.lower()
        if not any(needle.lower() in haystack for needle in ruleset.volcanism):
            return False
    if ruleset.regions is not None:
        region_id = _region_id(cond)
        if region_id is not None and not _region_matches(ruleset.regions, region_id):
            return False
    if ruleset.guardian is True and not _guardian_matches(cond):
        return False
    if ruleset.atmosphere_component is not None:
        components = cond.atmosphere_components or {}
        for gas, min_percent in ruleset.atmosphere_component:
            if components.get(gas, 0.0) < min_percent:
                return False
    if ruleset.tuber is not None and not _tuber_matches(ruleset.tuber, cond):
        return False
    if ruleset.bodies is not None and not _bodies_matches(ruleset.bodies, cond):
        return False
    return True


def predict_species(genus_key: str, cond: BodyConditions) -> List[species_data.SpeciesInfo]:
    """Every species of `genus_key` whose habitability rulesets are
    consistent with `cond` - a body holds at most one species per genus in
    the real game, so this is a candidate *list* (usually narrows to one
    once enough of `cond` is known), not a single answer. Species with no
    documented rulesets at all (e.g. Stratum Aranaemus - a single real
    sample, no derived rules) are never returned, since there's nothing to
    match against - not a "never matches", just "can't predict this one"."""
    matches = []
    for species in species_data.SPECIES.values():
        if species.genus_key != genus_key or not species.rulesets:
            continue
        if any(ruleset_matches(rs, cond) for rs in species.rulesets):
            matches.append(species)
    return matches


def haversine_distance_m(lat1: float, lon1: float, lat2: float, lon2: float, planet_radius_m: float) -> float:
    """Great-circle distance between two lat/lon points on a sphere of the
    given radius - standard formula, not tied to any third-party source."""
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return planet_radius_m * c


@dataclass
class OrganismProgress:
    """One genus's progress on the current body - a body holds at most one
    species per genus, so genus_key alone is the right key within a body."""

    genus_key: str
    species_key: Optional[str] = None  # confirmed once a ScanOrganic event names it
    species_name: Optional[str] = None
    value: Optional[int] = None
    stage: int = 0  # 0=detected only, 1=Log done, 2=Sample done, 3=Analyse done (complete, paid out)
    last_lat: Optional[float] = None
    last_lon: Optional[float] = None

    @property
    def complete(self) -> bool:
        return self.stage >= REQUIRED_SAMPLES

    @property
    def stage_name(self) -> str:
        return STAGE_ORDER[self.stage - 1] if 0 < self.stage <= REQUIRED_SAMPLES else "Detected"


class OrganicTracker:
    """Per-body organism state - reset whenever the commander moves to a
    different body (see organic_scan_panel.py's own Scan-event handling)."""

    def __init__(self) -> None:
        self._organisms: Dict[str, OrganismProgress] = {}

    @property
    def organisms(self) -> List[OrganismProgress]:
        return list(self._organisms.values())

    def reset(self) -> None:
        self._organisms = {}

    def note_genus_detected(self, genus_key: str) -> OrganismProgress:
        """FSSBodySignals/SAASignalsFound told us this genus is present,
        before any sample is taken."""
        return self._organisms.setdefault(genus_key, OrganismProgress(genus_key=genus_key))

    def restore_organism(
        self, genus_key: str, species_key: Optional[str], species_name: Optional[str],
        value: Optional[int], stage: int, last_lat: Optional[float], last_lon: Optional[float],
    ) -> None:
        """Reinstates a genus's progress from persisted state (see
        organic_scan_state.py) - used when returning to a body whose
        earlier progress this session's own record_scan() calls didn't
        produce (a fresh journal file after a relog, or simply having left
        and come back to the body within the same session)."""
        self._organisms[genus_key] = OrganismProgress(
            genus_key=genus_key, species_key=species_key, species_name=species_name,
            value=value, stage=stage, last_lat=last_lat, last_lon=last_lon,
        )

    def record_scan(
        self, genus_key: str, species_key: str, species_name: str, scan_type: str,
        lat: Optional[float], lon: Optional[float],
    ) -> OrganismProgress:
        """A real ScanOrganic event - confirms the exact species (replacing
        any predicted candidate list with certainty) and advances the scan
        stage."""
        organism = self._organisms.setdefault(genus_key, OrganismProgress(genus_key=genus_key))
        organism.species_key = species_key
        organism.species_name = species_name
        composite_key = f"{genus_key}|{species_key}"
        info = species_data.SPECIES.get(composite_key)
        organism.value = info.value if info else None
        if scan_type in STAGE_ORDER:
            organism.stage = max(organism.stage, STAGE_ORDER.index(scan_type) + 1)
        if lat is not None and lon is not None:
            organism.last_lat, organism.last_lon = lat, lon
        return organism

    def next_sample_distance_ok(
        self, genus_key: str, lat: float, lon: float, planet_radius_m: float,
    ) -> Optional[bool]:
        """Whether the commander is far enough from this genus's last
        sample location to take the next one. None if there's no prior
        sample yet to compare against, or the genus/planet radius isn't
        known."""
        organism = self._organisms.get(genus_key)
        if organism is None or organism.last_lat is None or organism.last_lon is None:
            return None
        genus = species_data.GENUS.get(genus_key)
        if genus is None or not planet_radius_m:
            return None
        distance = haversine_distance_m(organism.last_lat, organism.last_lon, lat, lon, planet_radius_m)
        return distance >= genus.min_distance_m
