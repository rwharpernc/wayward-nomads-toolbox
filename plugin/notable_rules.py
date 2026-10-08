"""
Notable Bodies: which scanned bodies are worth an on-screen alert.

Pure rule logic (no EDMC or Tk imports, so it is unit-testable the way `boxel.py` and
`survey_log.py` are). `notable.py` is the only place that wires it to real journal events
and the overlay.

Every rule reads one `Scan` event, plus - for the rules that compare a body with its
neighbours - the other `Scan` events already seen in the same system (`bodies`, keyed by
`BodyID`). The journal reports distances in metres, periods in seconds and gravity in m/s^2;
the constants below are in those same units.

The rule definitions and limits follow the default criteria in Elite Observatory's Explorer
plugin (ObservatoryExplorer/DefaultCriteria.cs, MIT licence - see THIRD-PARTY-NOTICES.md); the
constants below say so. The green gas giant temperatures are community research (same notice).
The code is WNTB's own.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, Iterable, List, Mapping, Optional, Set

Scan = Mapping[str, Any]
Bodies = Mapping[int, Scan]

STANDARD_GRAVITY = 9.81  # m/s^2 per "1 g", for display (Observatory uses the same)

# Limits below are Observatory's defaults (DefaultCriteria.cs).
HIGH_GRAVITY_MS2 = 29.4  # landable above 29.4 m/s^2 (about 3 g)
LARGE_LANDABLE_RADIUS_M = 18_000_000.0  # landable above 18,000 km radius
FAST_PERIOD_S = 28_800.0  # rotation or orbit faster than 8 hours
HIGH_ECCENTRICITY = 0.9
GOOD_INJECTION_MIN = 5  # 5 of the 6 premium FSD materials (Observatory flags exactly 5; 6 is better still)
PREMIUM_FSD_MATERIALS = frozenset({"carbon", "germanium", "arsenic", "niobium", "yttrium", "polonium"})
WIDE_RING_WIDTH_FACTOR = 5.0  # ring wider than 5x the body's own radius
CLOSE_ORBIT_RATIO = 3.0  # orbit under 3x the parent's radius
CLOSE_BINARY_MIN_RADIUS_RATIO = 0.4  # radius / semi-major axis above 0.4, for both bodies of the pair

# Green gas giant surface temperatures (K) confirmed by community research - CMDR Arcanic's
# ed-ggg.github.io, compiled for Observatory criteria by DaftMav and CMDR Julian Ford. The journal
# never records a planet's colour, so a match is only ever a lead to check in the system map.
GGG_TEMPERATURE_TOLERANCE_K = 0.001
KNOWN_GGG_TEMPERATURES = {
    "sudarsky class i gas giant": (
        77.450478, 83.943596, 85.945335, 87.11924, 89.193558, 90.14109, 100.046646, 109.874001,
        113.841248, 117.776886, 119.986717, 120.72538, 122.29538, 125.933167, 126.062111,
        128.909407, 129.582138, 130.0, 130.000015, 132.010391, 135.434097, 137.307129),
    "sudarsky class ii gas giant": (
        157.798843, 160.396164, 164.465302, 166.724182, 174.249985, 204.975662, 206.818893,
        213.91156, 217.840744, 217.87532, 225.990601, 228.357773, 238.65065),
    "sudarsky class iii gas giant": (
        276.751648, 299.305664, 370.0, 550.0, 580.0, 610.0, 640.0, 670.0, 700.0),
    "sudarsky class iv gas giant": (1149.999878, 1150.0),
    "water giant": (158.0,),
    "gas giant with water based life": (
        158.0, 176.666641, 176.666656, 176.666672, 176.666687, 176.666702, 217.499985),
    "gas giant with ammonia based life": (
        102.23452, 107.355812, 121.179939, 133.438171, 133.510468),
}


@dataclass(frozen=True)
class Match:
    rule_id: str
    label: str  # short enough for the overlay card's title line
    detail: str  # one line with the measurement, for logs and the Test result


def _number(value: Any) -> Optional[float]:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def _is_star(scan: Scan) -> bool:
    return "StarType" in scan


def _is_planet(scan: Scan) -> bool:
    return "PlanetClass" in scan


def _is_ring(scan: Scan) -> bool:
    return "ring" in str(scan.get("BodyName") or "").casefold()


def _landable(scan: Scan) -> bool:
    return scan.get("Landable") is True


def _rings(scan: Scan) -> List[Mapping[str, Any]]:
    """Real rings only - a star's asteroid belts are named "... Belt"."""
    return [
        ring for ring in scan.get("Rings") or []
        if isinstance(ring, Mapping) and "belt" not in str(ring.get("Name") or "").casefold()
    ]


def first_parent(scan: Scan) -> tuple:
    """(kind, id) of the body this one orbits - kind is "Planet", "Star" or "Null" - or (None, None)."""
    parents = scan.get("Parents")
    if not isinstance(parents, list) or not parents or not isinstance(parents[0], Mapping):
        return None, None
    for kind in ("Planet", "Star", "Null"):
        value = parents[0].get(kind)
        if isinstance(value, int) and not isinstance(value, bool):
            return kind, value
    return None, None


def _parent_scan(scan: Scan, bodies: Bodies, kind: str) -> Optional[Scan]:
    parent_kind, parent_id = first_parent(scan)
    if parent_kind != kind or parent_id is None:
        return None
    return bodies.get(parent_id)


# --- the rules: each returns a one-line detail when it matches, else None ----------------

def _terraformable_landable(scan: Scan, bodies: Bodies) -> Optional[str]:
    state = scan.get("TerraformState")  # "Terraformable", "Terraforming" or "Terraformed"
    if _landable(scan) and isinstance(state, str) and state:
        return f"{scan.get('PlanetClass') or 'Landable'}, {state.lower()}"
    return None


HIGH_VALUE_CLASSES = frozenset({"earthlike body", "ammonia world", "water world"})


def _high_value_body(scan: Scan, bodies: Bodies) -> Optional[str]:
    """Any terraformable, plus every Earth-like, ammonia and water world (landable or not)."""
    planet_class = str(scan.get("PlanetClass") or "")
    terraform = scan.get("TerraformState")
    terraformable = isinstance(terraform, str) and bool(terraform)
    if planet_class.casefold() not in HIGH_VALUE_CLASSES and not terraformable:
        return None
    status = ""
    if scan.get("WasMapped") is False:
        status = "undiscovered " if scan.get("WasDiscovered") is False else "unmapped "
    if terraformable:
        status += "terraformable "
    distance = _number(scan.get("DistanceFromArrivalLS"))
    where = f", {distance:,.0f} Ls" if distance is not None else ""
    text = f"{status}{planet_class.lower()}{where}".strip()
    return text[:1].upper() + text[1:]


def _high_gravity(scan: Scan, bodies: Bodies) -> Optional[str]:
    gravity = _number(scan.get("SurfaceGravity"))
    if _landable(scan) and gravity is not None and gravity > HIGH_GRAVITY_MS2:
        return f"{gravity / STANDARD_GRAVITY:.2f} g"
    return None


def _large_landable(scan: Scan, bodies: Bodies) -> Optional[str]:
    radius = _number(scan.get("Radius"))
    if _landable(scan) and radius is not None and radius > LARGE_LANDABLE_RADIUS_M:
        return f"radius {radius / 1000:,.0f} km"
    return None


def _fast_rotation(scan: Scan, bodies: Bodies) -> Optional[str]:
    # Planets only (a neutron star spins in milliseconds), and not tidally locked (a locked
    # body's day is its orbit, which "Fast orbit" already covers).
    period = _number(scan.get("RotationPeriod"))
    if _is_planet(scan) and not _is_ring(scan) and scan.get("TidalLock") is not True and period is not None and period != 0 \
            and abs(period) < FAST_PERIOD_S:
        return f"day {abs(period) / 3600:.1f} h"
    return None


def _fast_orbit(scan: Scan, bodies: Bodies) -> Optional[str]:
    period = _number(scan.get("OrbitalPeriod"))
    if _is_planet(scan) and not _is_ring(scan) and period is not None and period != 0 \
            and abs(period) < FAST_PERIOD_S:
        return f"orbit {abs(period) / 3600:.1f} h"
    return None


def _high_eccentricity(scan: Scan, bodies: Bodies) -> Optional[str]:
    eccentricity = _number(scan.get("Eccentricity"))
    if eccentricity is not None and eccentricity > HIGH_ECCENTRICITY:
        return f"eccentricity {eccentricity:.3f}"
    return None


def _wide_ring(scan: Scan, bodies: Bodies) -> Optional[str]:
    radius = _number(scan.get("Radius"))
    if radius is None or radius <= 0:
        return None
    for ring in _rings(scan):
        inner, outer = _number(ring.get("InnerRad")), _number(ring.get("OuterRad"))
        if inner is not None and outer is not None and (outer - inner) > WIDE_RING_WIDTH_FACTOR * radius:
            return f"ring {(outer - inner) / 1000:,.0f} km wide"
    return None


def _landable_ring(scan: Scan, bodies: Bodies) -> Optional[str]:
    if _landable(scan) and _rings(scan):
        return "landable body with rings"
    return None


def _good_fsd_injection(scan: Scan, bodies: Bodies) -> Optional[str]:
    if not _landable(scan):
        return None
    names = {
        str(item.get("Name") or "").casefold()
        for item in scan.get("Materials") or [] if isinstance(item, Mapping)
    }
    found = len(names & PREMIUM_FSD_MATERIALS)
    if found >= GOOD_INJECTION_MIN:
        return f"{found} of {len(PREMIUM_FSD_MATERIALS)} premium FSD materials"
    return None


def _parent_body(scan: Scan, bodies: Bodies) -> Optional[Scan]:
    """The planet or star this body orbits (not a barycentre), if it has been scanned."""
    kind, parent_id = first_parent(scan)
    if kind not in ("Planet", "Star") or parent_id is None:
        return None
    return bodies.get(parent_id)


def _close_orbit(scan: Scan, bodies: Bodies) -> Optional[str]:
    parent = _parent_body(scan, bodies)
    axis = _number(scan.get("SemiMajorAxis"))
    parent_radius = _number(parent.get("Radius")) if parent else None
    if axis and parent_radius and not _is_ring(scan) and parent_radius * CLOSE_ORBIT_RATIO > axis:
        return f"orbit {axis / 1000:,.0f} km, parent radius {parent_radius / 1000:,.0f} km"
    return None


def _shepherd_moon(scan: Scan, bodies: Bodies) -> Optional[str]:
    parent = _parent_body(scan, bodies)
    axis = _number(scan.get("SemiMajorAxis"))
    rings = parent.get("Rings") if parent else None
    if not axis or not rings or _is_ring(scan):
        return None
    last = rings[-1]  # Observatory judges against the outermost ring only
    if not isinstance(last, Mapping) or "belt" in str(last.get("Name") or "").casefold():
        return None
    outer = _number(last.get("OuterRad"))
    if outer is not None and outer > axis:
        return f"orbit {axis / 1000:,.0f} km, ring edge {outer / 1000:,.0f} km"
    return None


def _binary_partner(scan: Scan, bodies: Bodies) -> Optional[Scan]:
    """The one other body sharing this body's barycentre, when both are close enough to their
    common centre for the pair to count (radius over semi-major axis above 0.4)."""
    kind, barycentre = first_parent(scan)
    axis, radius = _number(scan.get("SemiMajorAxis")), _number(scan.get("Radius"))
    if kind != "Null" or not axis or radius is None or radius / axis <= CLOSE_BINARY_MIN_RADIUS_RATIO:
        return None
    partners = [
        other for other in bodies.values()
        if other.get("BodyID") != scan.get("BodyID") and first_parent(other) == ("Null", barycentre)
    ]
    if len(partners) != 1:
        return None
    other_axis, other_radius = _number(partners[0].get("SemiMajorAxis")), _number(partners[0].get("Radius"))
    if not other_axis or other_radius is None or other_radius / other_axis <= CLOSE_BINARY_MIN_RADIUS_RATIO:
        return None
    return partners[0]


def _is_colliding(scan: Scan, partner: Scan) -> bool:
    """Their closest approaches (periapsis) are less than their radii apart."""
    def periapsis(body: Scan) -> float:
        return (_number(body.get("SemiMajorAxis")) or 0.0) * (1 - (_number(body.get("Eccentricity")) or 0.0))
    return (_number(partner.get("Radius")) or 0.0) + (_number(scan.get("Radius")) or 0.0) \
        >= periapsis(partner) + periapsis(scan)


def _binary_detail(scan: Scan, partner: Scan) -> str:
    return f"orbit {(_number(scan.get('SemiMajorAxis')) or 0) / 1000:,.0f} km, partner {partner.get('BodyName')}"


def _close_binary(scan: Scan, bodies: Bodies) -> Optional[str]:
    partner = _binary_partner(scan, bodies)
    if partner is not None and not _is_colliding(scan, partner):
        return _binary_detail(scan, partner)
    return None


def _colliding_binary(scan: Scan, bodies: Bodies) -> Optional[str]:
    partner = _binary_partner(scan, bodies)
    if partner is not None and _is_colliding(scan, partner):
        return _binary_detail(scan, partner)
    return None


def green_gas_giant_candidate(scan: Scan) -> bool:
    """A gas giant whose class and surface temperature match a confirmed green gas giant."""
    temperatures = KNOWN_GGG_TEMPERATURES.get(str(scan.get("PlanetClass") or "").strip().casefold())
    temperature = _number(scan.get("SurfaceTemperature"))
    return bool(temperatures) and temperature is not None and any(
        abs(temperature - known) <= GGG_TEMPERATURE_TOLERANCE_K for known in temperatures
    )


def _green_gas_giant(scan: Scan, bodies: Bodies) -> Optional[str]:
    if green_gas_giant_candidate(scan):
        return f"{scan.get('SurfaceTemperature')} K matches a known green gas giant - check the system map"
    return None


def green_gas_giant_codex(entry: Mapping[str, Any]) -> bool:
    """A CodexEntry that explicitly names a Green Gas Giant (matches the internal id too, so it
    does not depend on the game language)."""
    text = " ".join(
        str(entry.get(key) or "")
        for key in ("Name", "Name_Localised", "SubCategory", "SubCategory_Localised")
    ).casefold()
    compact = "".join(ch for ch in text if ch.isalnum())
    return "green gas giant" in text or "greengasgiant" in compact or "codexentgreensudarsky" in compact


@dataclass(frozen=True)
class Rule:
    id: str
    label: str  # overlay title; keep it short (notable.TITLE_MAX_CHARS)
    description: str  # one line for the Settings page
    default_on: bool
    check: Callable[[Scan, Bodies], Optional[str]]


# Order is the Settings page order.
RULES = (
    Rule("terraformable_landable", "Terraformable landable", "A landable body that is terraformable, or being or already terraformed.",
         True, _terraformable_landable),
    Rule("high_value", "High-value body",
         "Any terraformable, Earth-like, water or ammonia world, landable or not.", True, _high_value_body),
    Rule("high_g", "High-g landable", "A landable body above about 3 g (29.4 m/s²).", True, _high_gravity),
    Rule("shepherd_moon", "Shepherd moon", "A moon orbiting inside the outer edge of its parent's outermost ring.",
         True, _shepherd_moon),
    Rule("good_fsd", "Good FSD injection", "A body with 5 or 6 of the premium FSD boost materials.",
         True, _good_fsd_injection),
    Rule("green_gas_giant", "Green gas giant", "A Codex entry for one, or a gas giant at a confirmed green temperature.",
         True, _green_gas_giant),
    Rule("large_landable", "Large landable", "A landable body over 18,000 km in radius.", False, _large_landable),
    Rule("landable_ring", "Landable ringed", "A landable body that also has rings.", False, _landable_ring),
    Rule("close_orbit", "Close orbit", "A moon orbiting very close to its parent planet.", False, _close_orbit),
    Rule("close_binary", "Close binary", "Two bodies orbiting so close to their shared centre that they nearly touch.", False, _close_binary),
    Rule("colliding_binary", "Colliding binary", "Two bodies whose orbits overlap, so they will collide.", True,
         _colliding_binary),
    Rule("high_eccentricity", "High eccentricity", "An orbit with eccentricity above 0.9.", False,
         _high_eccentricity),
    Rule("fast_orbit", "Fast orbit", "A planet orbiting in under 8 hours.", False, _fast_orbit),
    Rule("fast_rotation", "Fast rotation", "A planet with a day under 8 hours (not tidally locked).",
         False, _fast_rotation),
    Rule("wide_ring", "Wide ring", "A ring far wider than the body it circles.", False, _wide_ring),
)

RULES_BY_ID: Dict[str, Rule] = {rule.id: rule for rule in RULES}


def default_enabled() -> Set[str]:
    return {rule.id for rule in RULES if rule.default_on}


def evaluate(scan: Scan, bodies: Bodies, enabled: Iterable[str]) -> List[Match]:
    """Every enabled rule that matches `scan`, in Settings order. `bodies` should already hold
    the neighbours this scan is compared with (it may or may not include `scan` itself).
    A malformed event never raises - it just matches nothing."""
    enabled = set(enabled)
    matches: List[Match] = []
    for rule in RULES:
        if rule.id not in enabled:
            continue
        try:
            detail = rule.check(scan, bodies)
        except (TypeError, ValueError, ArithmeticError):
            detail = None
        if detail:
            matches.append(Match(rule.id, rule.label, detail))
    return matches
