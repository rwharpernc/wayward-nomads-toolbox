"""
The data side of the Mining Book window (mining_ledger.py): which
bodies to list and how to group them, how to group a body's hotspots, and
the metre-offset projection the Canvas map needs. Pure logic, no tkinter -
see tests/test_mining_ledger_data.py.

Bodies come from two places: this session's landable-body survey
(mining_body_survey.py - what the journal has shown us in the current
system) and the commander's saved hotspots (mining_hotspots.py - possibly
in other systems entirely). The browser merges them so one window replaces
both the "System Bodies" and "Search Known Hotspots" dialogs.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional, Sequence

from . import mining_bearing as bearing
from . import mining_body_survey as body_survey
from . import mining_coverage as coverage
from . import mining_hotspots as hotspots
from . import mining_ground

ALL_MATERIALS = "All materials"
ANY_RIGS = "Any rigs"
UNNUMBERED = "Unnumbered"
GROUP_SAVED_HERE = "Saved, not scanned this session"
GROUP_OTHER_SYSTEMS = "Other systems"


@dataclass(frozen=True)
class BodyEntry:
    system: str
    body: str
    planet_class: Optional[str]
    mining_signal_count: Optional[int]
    saved_count: int
    ground: Optional[str] = None
    """The ground key for this kind of body (mining_ground.classify), None
    when the body is only known from a saved hotspot."""
    rate_pct: Optional[float] = None
    """With a material filter: the share of the commander's own recorded
    deposits on this kind of body that were that material."""

    @property
    def key(self) -> str:
        return f"{self.system}|{self.body}"

    @property
    def short_name(self) -> str:
        return short_body_name(self.system, self.body)


def short_body_name(system: str, body: str) -> str:
    """"Col 285 Sector XT-Q c5-21 6 a" in "Col 285 Sector XT-Q c5-21" -> "6 a".
    Journal body names are the system name plus a suffix; the suffix is all
    that's useful inside a list already headed by the system."""
    if system and body.casefold().startswith(system.casefold()):
        rest = body[len(system):].strip()
        if rest:
            return rest
    return body


def _norm(text: str) -> str:
    return text.strip().casefold()


def _matches(spots: Sequence[hotspots.Hotspot], material: str, rigs: Optional[int]) -> bool:
    """Whether any one hotspot satisfies both filters (material substring,
    exact rig count) - the same hotspot, not one per filter."""
    wanted = _norm(material) if material and material != ALL_MATERIALS else ""
    return any((not wanted or wanted in _norm(h.material)) and (rigs is None or h.rigs == rigs)
               for h in spots)


def rigs_from_label(label: str) -> Optional[int]:
    """"3 rigs" -> 3; "Any rigs" (or anything unparseable) -> None."""
    head = label.split(" ", 1)[0]
    return int(head) if head.isdigit() else None


def rig_labels(saved: Sequence[hotspots.Hotspot]) -> list[str]:
    counts = sorted({h.rigs for h in saved if h.rigs is not None})
    return [ANY_RIGS] + [f"{n} rigs" for n in counts]


def build_body_groups(current_system: Optional[str],
                      surveyed: Sequence[body_survey.SurveyedBody],
                      saved: Sequence[hotspots.Hotspot],
                      material: str = ALL_MATERIALS,
                      rigs: Optional[int] = None,
                      rates: Optional[mining_ground.OwnRates] = None) -> list[tuple[str, str, list[BodyEntry]]]:
    """(group key, heading, entries) in display order: one group per
    planet class for bodies scanned in the current system, then saved
    hotspot bodies in the current system the survey hasn't seen, then one
    group listing bodies in other systems that have saved hotspots. With a
    material and/or rigs filter, only bodies that have a saved hotspot
    matching it remain - except that, for a material filter alone, a scanned
    body also stays when the commander's own records (`rates`) show deposits
    of that material on its kind of body, and those bodies are listed
    highest-share first (a rigs filter needs a saved hotspot: the rates
    know nothing of rigs)."""
    material_filter = material if material and material != ALL_MATERIALS else ""
    filtering = (bool(material) and material != ALL_MATERIALS) or rigs is not None
    system = current_system or ""

    by_body: dict[tuple[str, str], list[hotspots.Hotspot]] = {}
    for spot in saved:
        by_body.setdefault((_norm(spot.system), _norm(spot.body)), []).append(spot)

    def keep(spots: list[hotspots.Hotspot]) -> bool:
        return not filtering or _matches(spots, material, rigs)

    groups: list[tuple[str, str, list[BodyEntry]]] = []
    seen: set[tuple[str, str]] = set()

    classes: dict[str, list[BodyEntry]] = {}
    for body in surveyed:
        ident = (_norm(system), _norm(body.name))
        seen.add(ident)
        spots = by_body.get(ident, [])
        ground = mining_ground.classify(body.planet_class, body.volcanism)
        rate = rates.rate_of(ground, material_filter) if rates and material_filter else None
        if keep(spots) or (rate is not None and rigs is None):
            classes.setdefault(body.planet_class or "Unknown", []).append(
                BodyEntry(system, body.name, body.planet_class, body.mining_signal_count, len(spots),
                          ground, rate.pct if rate else None))
    for planet_class, entries in classes.items():
        if material_filter and rates:
            entries.sort(key=lambda e: (-(e.rate_pct or 0.0), e.body.casefold()))
        groups.append((f"class:{planet_class}", planet_class, entries))

    here_unscanned: list[BodyEntry] = []
    elsewhere: list[BodyEntry] = []
    for (spot_system, spot_body), spots in sorted(by_body.items()):
        if (spot_system, spot_body) in seen or not keep(spots):
            continue
        first = spots[0]
        entry = BodyEntry(first.system, first.body, None, None, len(spots))
        (here_unscanned if system and spot_system == _norm(system) else elsewhere).append(entry)
    if here_unscanned:
        groups.append(("saved-here", GROUP_SAVED_HERE, here_unscanned))
    if elsewhere:
        groups.append(("other-systems", GROUP_OTHER_SYSTEMS, elsewhere))
    return groups


def materials_in(saved: Sequence[hotspots.Hotspot]) -> list[str]:
    """Material choices: those in the commander's saved hotspots."""
    seen: dict[str, str] = {}
    for spot in saved:
        name = spot.material.strip()
        if name:
            seen.setdefault(name.casefold(), name)
    return [ALL_MATERIALS] + sorted(seen.values(), key=str.casefold)


@dataclass(frozen=True)
class ProspectRow:
    material: str
    pct: float
    count: int
    saved_here: bool


def prospect_rows(rates: mining_ground.OwnRates, ground: Optional[str],
                  spots: Sequence[hotspots.Hotspot]) -> list[ProspectRow]:
    """The commander's own recorded materials for a body's ground, most
    common first, each flagged when a hotspot of that material is already
    saved on this body."""
    have = {_norm(h.material) for h in spots}
    return [ProspectRow(r.material, r.pct, r.count, _norm(r.material) in have)
            for r in rates.rates(ground)]


def spots_on(saved: Sequence[hotspots.Hotspot], system: str, body: str) -> list[hotspots.Hotspot]:
    return [h for h in saved if _norm(h.system) == _norm(system) and _norm(h.body) == _norm(body)]


def location_label(spot: hotspots.Hotspot) -> str:
    return f"Location {spot.signal_number}" if spot.signal_number is not None else UNNUMBERED


def group_by_location(spots: Sequence[hotspots.Hotspot]) -> list[tuple[str, list[hotspots.Hotspot]]]:
    """Hotspots grouped by their Signal/location number, numbered
    locations ascending, unnumbered last."""
    groups: dict[str, list[hotspots.Hotspot]] = {}
    for spot in spots:
        groups.setdefault(location_label(spot), []).append(spot)

    def order(item: tuple[str, list[hotspots.Hotspot]]):
        number = item[1][0].signal_number
        return (number is None, number if number is not None else 0)
    return sorted(groups.items(), key=order)


@dataclass(frozen=True)
class BodySummary:
    saved: int
    mined_tons: int
    still_active: int


def summarize(spots: Sequence[hotspots.Hotspot]) -> BodySummary:
    return BodySummary(
        saved=len(spots),
        mined_tons=sum(h.mined_tons or 0 for h in spots),
        still_active=sum(1 for h in spots if h.amount != "Depleted"))


@dataclass(frozen=True)
class MaterialLine:
    material: str
    hotspots: int
    active: int
    mined_tons: int


def material_summary(spots: Sequence[hotspots.Hotspot]) -> list[MaterialLine]:
    """What a body holds according to the commander's own saved hotspots,
    one line per material: how many hotspots, how many aren't depleted, and
    tons mined so far. Most-mined first, then most hotspots, then name.
    Deliberately only the commander's own records - there is no third-party
    dataset of what a body *could* hold in WNTB (see mining_ground.OwnRates
    for the per-kind-of-body tallies built from the same records)."""
    by_material: dict[str, list[hotspots.Hotspot]] = {}
    names: dict[str, str] = {}
    for spot in spots:
        key = _norm(spot.material) or "?"
        names.setdefault(key, spot.material.strip() or "Unknown")
        by_material.setdefault(key, []).append(spot)
    lines = [MaterialLine(names[k], len(v), sum(1 for h in v if h.amount != "Depleted"),
                          sum(h.mined_tons or 0 for h in v))
             for k, v in by_material.items()]
    return sorted(lines, key=lambda m: (-m.mined_tons, -m.hotspots, m.material.casefold()))


def project_m(center_lat: float, center_lon: float, lat: float, lon: float,
              radius_m: float) -> tuple[float, float]:
    """(east, north) metres of a point from the map centre - the same flat
    projection mining_coverage_render uses, fine at the few-km scale the
    map shows."""
    distance = bearing.distance_m(center_lat, center_lon, lat, lon, radius_m)
    heading = math.radians(bearing.initial_bearing_deg(center_lat, center_lon, lat, lon))
    return distance * math.sin(heading), distance * math.cos(heading)


def map_center(body_coverage: Optional[coverage.BodyCoverage],
               current: Optional[tuple[float, float]],
               spots: Sequence[hotspots.Hotspot]) -> Optional[tuple[float, float]]:
    """Where to centre the map: the body's recorded coverage centre, else
    the live position, else the first positioned hotspot, else None."""
    if body_coverage is not None and body_coverage.center is not None:
        return body_coverage.center.latitude, body_coverage.center.longitude
    if current is not None:
        return current
    for spot in spots:
        if spot.has_position():
            return spot.latitude, spot.longitude
    return None
