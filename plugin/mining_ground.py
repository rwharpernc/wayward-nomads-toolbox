"""
Which kind of ground a landable body is, and "your own base rates": of the
surface deposits *you* have recorded on bodies of a given kind of ground,
what share carried each material.

All of it comes from the commander's own saved hotspots (mining_hotspots.py)
and the journal's `Scan` PlanetClass/Volcanism - there is deliberately no
bundled or downloaded third-party dataset behind it. The journal never
reports what a deposit holds, so with no records the rates are simply empty
and the Mining Book hides the section; they fill in as hotspots are saved.

Read the numbers as *what you have found so far*, not what a body holds: they
only count deposits you chose to record, and a small sample says little (the
Mining Book always shows the sample size next to them).

Pure logic, no tkinter - see tests/test_mining_ground.py.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Optional, Sequence

from . import mining_body_survey as body_survey
from . import mining_hotspots as hotspots

# Ground key -> display name.
GROUND_LABELS: dict[str, str] = {
    "metal_rich": "Metal-rich body",
    "high_metal": "High metal content body",
    "rocky": "Rocky body",
    "rocky_metallic_magma": "Rocky body, metallic magma",
    "rocky_rocky_magma": "Rocky body, rocky magma",
    "rocky_silicate_vapour": "Rocky body, silicate vapour",
    "rocky_silicate_magma": "Rocky body, silicate magma",
    "rocky_other_volcanism": "Rocky body, other volcanism",
    "rocky_ice": "Rocky ice body",
    "icy": "Icy body",
}

_CLASS_PREFIXES: tuple[tuple[str, str], ...] = (
    ("metal rich", "metal_rich"),
    ("metal-rich", "metal_rich"),
    ("high metal", "high_metal"),
    ("rocky ice", "rocky_ice"),
    ("icy", "icy"),
)
"""PlanetClass prefix (lower case) -> ground. Anything else landable is a
plain rocky body, which is then split by volcanism."""

_VOLCANISM_WORDS: tuple[tuple[str, str], ...] = (
    ("silicate magma", "rocky_silicate_magma"),
    ("silicate", "rocky_silicate_vapour"),
    ("metallic", "rocky_metallic_magma"),
    ("rocky", "rocky_rocky_magma"),
)
"""Words in the Volcanism text -> ground, first match wins. The order matters:
"silicate magma" contains "silicate"."""


def classify(planet_class: Optional[str], volcanism: Optional[str]) -> Optional[str]:
    """Journal Scan `PlanetClass` + `Volcanism` -> a ground key, or None when
    there is no class. The caller has already established the body is
    landable (mining_body_survey only keeps landable bodies)."""
    planet = (planet_class or "").strip().lower()
    if not planet:
        return None
    for prefix, ground in _CLASS_PREFIXES:
        if planet.startswith(prefix):
            return ground

    text = " ".join((volcanism or "").lower().split())
    if not text:
        return "rocky"
    for word, ground in _VOLCANISM_WORDS:
        if word in text:
            return ground
    return "rocky_other_volcanism"


def label(ground: Optional[str]) -> str:
    return GROUND_LABELS.get(ground or "", ground or "Unknown ground")


def survey_grounds(surveyed: Sequence[body_survey.SurveyedBody],
                   system: Optional[str]) -> dict[tuple[str, str], str]:
    """(system, body) -> ground for this session's scanned bodies, keyed the
    way OwnRates looks them up (case-folded). Lets deposits saved before they
    carried a ground still count, while their body is in the current survey."""
    grounds: dict[tuple[str, str], str] = {}
    for body in surveyed:
        ground = classify(body.planet_class, body.volcanism)
        if ground:
            grounds[((system or "").strip().casefold(), body.name.strip().casefold())] = ground
    return grounds


def ground_in_survey(survey: body_survey.SystemBodySurvey, system: Optional[str],
                     body: Optional[str]) -> Optional[str]:
    """The ground of a body in the current system's survey, or None (not the
    current system, not scanned, or not landable). Used to stamp a newly
    saved hotspot."""
    if not system or not body or system != survey.current_system:
        return None
    return survey_grounds(survey.landable_bodies(), system).get(
        (system.strip().casefold(), body.strip().casefold()))


@dataclass(frozen=True)
class Rate:
    material: str
    pct: float     # share of this ground's recorded deposits that were this material
    count: int     # how many recorded deposits that is


class OwnRates:
    """Built from a snapshot of the commander's saved hotspots; rebuild after
    the repository changes (it is cheap - one pass over the list).

    A hotspot counts toward the ground it was stamped with
    (`Hotspot.ground`), else the one `extra_grounds` knows for its body (see
    survey_grounds); one with neither is skipped, as is one with no material.
    Each hotspot is one recorded deposit, so the percentages are shares of
    recorded deposits - not of measured locations."""

    def __init__(self, saved: Sequence[hotspots.Hotspot],
                 extra_grounds: Optional[Mapping[tuple[str, str], str]] = None) -> None:
        counts: dict[str, dict[str, int]] = {}
        names: dict[str, str] = {}
        for spot in saved:
            material = spot.material.strip()
            if not material:
                continue
            ground = spot.ground
            if not ground and extra_grounds:
                ground = extra_grounds.get((spot.system.strip().casefold(), spot.body.strip().casefold()))
            if not ground:
                continue
            key = material.casefold()
            names.setdefault(key, material)
            per_ground = counts.setdefault(ground, {})
            per_ground[key] = per_ground.get(key, 0) + 1

        self._samples = {g: sum(per.values()) for g, per in counts.items()}
        self._rates = {
            g: sorted((Rate(names[k], n * 100.0 / self._samples[g], n) for k, n in per.items()),
                      key=lambda r: (-r.count, r.material.casefold()))
            for g, per in counts.items()}

    @property
    def has_data(self) -> bool:
        return bool(self._rates)

    def rates(self, ground: Optional[str]) -> list[Rate]:
        """Materials recorded on this ground, most common first. Empty when
        the ground is None or nothing has been recorded on it."""
        return list(self._rates.get(ground or "", []))

    def rate_of(self, ground: Optional[str], material: str) -> Optional[Rate]:
        wanted = material.strip().casefold()
        return next((r for r in self._rates.get(ground or "", []) if r.material.casefold() == wanted), None)

    def sample_size(self, ground: Optional[str]) -> int:
        """How many recorded deposits this ground's percentages are over."""
        return self._samples.get(ground or "", 0)
