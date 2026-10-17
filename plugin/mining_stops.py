"""
Stops: saved deposits that one Rhino parking spot can reach.

A Rhino's rigs are placed around where it stands, so deposits close together are worked from one place. A stop is the
saved deposit with the most rigs plus every other active one within the stop radius of it; the stops are found greedily, so
no deposit is in two. The best stops are the ones whose lead deposit has BEST_RIGS or more rigs (FALLBACK_RIGS when the
body has none that large), at most MAX_BEST of them, best first.

Only deposits with a position and a rig count are placed in a stop, and a Depleted one is left out, since nobody drives to
it. Distances need the body's radius, so the caller supplies it (the Mining Book has it for the body you are on).

The idea follows RhinoSpotter's golden circles; the rule and the code are WNTB's own. Pure logic, no tkinter: see
tests/test_mining_stops.py.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Sequence

from . import mining_bearing as bearing
from . import mining_deposit
from .mining_hotspots import Hotspot

MIN_RADIUS_M = 500
MAX_RADIUS_M = 2500
STEP_RADIUS_M = 250
DEFAULT_RADIUS_M = 1250

BEST_RIGS = 5
FALLBACK_RIGS = 4
MAX_BEST = 3


@dataclass(frozen=True)
class Stop:
    lead: Hotspot
    members: tuple[Hotspot, ...]
    """Every deposit in the stop, the lead included."""

    @property
    def rigs(self) -> int:
        return self.lead.rigs or 0

    def tons_left(self) -> Optional[tuple[int, int]]:
        """The members' estimated tons left added up, or None when no member has an estimate."""
        spans = [mining_deposit.reserve_range(h.rigs, h.amount, h.density) for h in self.members]
        spans = [s for s in spans if s is not None]
        if not spans:
            return None
        return sum(s[0] for s in spans), sum(s[1] for s in spans)


def clamp_radius(value: object) -> int:
    """A stored radius as a usable one: a multiple of the step inside the range, the default for anything unreadable."""
    try:
        number = int(round(float(value)))   # type: ignore[arg-type]
    except (TypeError, ValueError):
        return DEFAULT_RADIUS_M
    number = min(MAX_RADIUS_M, max(MIN_RADIUS_M, number))
    return MIN_RADIUS_M + round((number - MIN_RADIUS_M) / STEP_RADIUS_M) * STEP_RADIUS_M


def find_stops(spots: Sequence[Hotspot], body_radius_m: Optional[float], radius_m: float) -> list[Stop]:
    """All stops among `spots` (one body's), most rigs first. Empty without a body radius."""
    if not body_radius_m:
        return []
    remaining = [h for h in spots if h.has_position() and h.rigs and h.amount != mining_deposit.AMOUNTS[-1]]

    def near(a: Hotspot, b: Hotspot) -> bool:
        return bearing.distance_m(a.latitude, a.longitude, b.latitude, b.longitude, body_radius_m) <= radius_m

    stops: list[Stop] = []
    while remaining:
        lead = max(remaining, key=lambda h: (h.rigs or 0, sum(1 for o in remaining if near(h, o))))
        members = tuple(o for o in remaining if o is lead or near(lead, o))
        remaining = [o for o in remaining if not any(o is m for m in members)]
        stops.append(Stop(lead, members))
    return sorted(stops, key=lambda s: (-s.rigs, -len(s.members)))


def best_stops(stops: Sequence[Stop]) -> list[Stop]:
    """The stops worth parking at: lead of BEST_RIGS or more (FALLBACK_RIGS when there is none), at most MAX_BEST."""
    threshold = BEST_RIGS if any(s.rigs >= BEST_RIGS for s in stops) else FALLBACK_RIGS
    return [s for s in stops if s.rigs >= threshold][:MAX_BEST]
