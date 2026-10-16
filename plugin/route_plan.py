"""Route status: the pure part of the Route overlay (no Tk, no EDMC, no overlay).

The overlay shows the ship's state as it matters for travel, and the systems of the route plotted in the game, each with its star, so
a neutron star or a white dwarf (a supercharge) can be prepared for before the jump. Everything comes from what the game writes:

- the plotted route is `NavRoute.json` (`Route`: `StarSystem`, `StarPos`, `StarClass` per system, starting with the system the ship
  is in); the `NavRoute` event says it was rewritten and `NavRouteClear` that it was cleared;
- where the ship is on that route comes from the system it is in (`FSDJump`, `Location`, `CarrierJump`);
- the tank size and the jump range come from the `Loadout` event (`FuelCapacity.Main`, `MaxJumpRange`), the fuel on board from
  `Status.json` and the fuel the last jump used from `FSDJump` (`FuelUsed`).

What it cannot know: the journal does not say what the next jump will cost, so the card shows the fuel on board and what the last jump
used rather than "enough fuel". The jump range in `Loadout` is the ship's maximum with its current modules, not the range with the
cargo and fuel it carries now.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, List, Mapping, Optional, Tuple

from . import fuel_alerts

XYZ = Tuple[float, float, float]

KIND_NEUTRON = "neutron"
KIND_WHITE_DWARF = "white_dwarf"
KIND_NO_SCOOP = "no_scoop"       # a star the ship cannot scoop that is not one of the supercharge stars (a black hole, say)
KIND_SCOOPABLE = "scoopable"
KIND_UNKNOWN = "unknown"

# Events after which the ship is in a new system.
_ARRIVALS = ("FSDJump", "Location", "CarrierJump")


@dataclass(frozen=True)
class Hop:
    name: str
    star_class: str = ""
    pos: Optional[XYZ] = None


def star_kind(star_class: str) -> str:
    """What a star means for the trip: a neutron star or a white dwarf (both supercharge the drive), another star that cannot be
    scooped, one that can, or unknown when the route did not give a class."""
    if not star_class:
        return KIND_UNKNOWN
    if star_class == "N":
        return KIND_NEUTRON
    if star_class.startswith("D"):
        return KIND_WHITE_DWARF
    return KIND_SCOOPABLE if fuel_alerts.is_scoopable(star_class) else KIND_NO_SCOOP


_NO_SCOOP_TAGS = (("MS", "S-TYPE"), ("TTS", "PROTOSTAR"), ("AeBe", "PROTOSTAR"), ("H", "BLACK HOLE"), ("W", "WOLF-RAYET"), ("C", "CARBON"),
                  ("S", "S-TYPE"), ("T", "BROWN DWARF"), ("L", "BROWN DWARF"), ("Y", "BROWN DWARF"))


def star_tag(star_class: str) -> Tuple[str, str]:
    """(text, kind) for a route row's star column: NEUTRON or WHITE DWARF for a supercharge, a short name for another star that cannot be
    scooped, and the plain class letters for one that can."""
    kind = star_kind(star_class)
    if kind == KIND_NEUTRON:
        return "NEUTRON", kind
    if kind == KIND_WHITE_DWARF:
        return "WHITE DWARF", kind
    if kind == KIND_NO_SCOOP:
        for prefix, text in _NO_SCOOP_TAGS:
            if star_class == prefix or (len(prefix) == 1 and star_class.startswith(prefix)):
                return text, kind
    return star_class, kind


def _position(raw: Any) -> Optional[XYZ]:
    if isinstance(raw, (list, tuple)) and len(raw) == 3 and all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in raw):
        return float(raw[0]), float(raw[1]), float(raw[2])
    return None


def parse_route(data: Any) -> List[Hop]:
    """The systems of a parsed `NavRoute.json`, in order, starting system included. Anything malformed is skipped."""
    route = data.get("Route") if isinstance(data, Mapping) else None
    hops: List[Hop] = []
    for item in route if isinstance(route, list) else []:
        if not isinstance(item, Mapping):
            continue
        name = str(item.get("StarSystem") or "").strip()
        if name:
            star = item.get("StarClass")
            hops.append(Hop(name, star if isinstance(star, str) else "", _position(item.get("StarPos"))))
    return hops


def distance(a: Optional[XYZ], b: Optional[XYZ]) -> Optional[float]:
    return math.dist(a, b) if a is not None and b is not None else None


def route_length(hops: List[Hop], start: Optional[Hop] = None) -> Optional[float]:
    """Straight-line light years along `hops` (from `start` when given); None when any position is missing."""
    chain = ([start] if start is not None else []) + list(hops)
    total = 0.0
    for first, second in zip(chain, chain[1:]):
        step = distance(first.pos, second.pos)
        if step is None:
            return None
        total += step
    return total


@dataclass
class RouteTracker:
    """The plotted route, where the ship is on it, and the ship numbers the card shows."""
    route: List[Hop] = field(default_factory=list)
    system: str = ""
    jump_range: Optional[float] = None       # ly, `Loadout.MaxJumpRange`
    last_fuel_used: Optional[float] = None   # t, the last `FSDJump`
    fuel: fuel_alerts.FuelWatcher = field(default_factory=fuel_alerts.FuelWatcher)

    # events ----------------------------------------------------------------------------------------------------------
    def handle_event(self, entry: Mapping[str, Any], system: Optional[str] = None) -> bool:
        """Takes one journal event. True when the plotted route has to be read again (a `NavRoute` event)."""
        event = entry.get("event")
        self.fuel.handle_event(entry)
        if event in _ARRIVALS and isinstance(entry.get("StarSystem"), str):
            self.system = entry["StarSystem"]
        elif isinstance(system, str) and system:
            self.system = system
        if event == "FSDJump":
            used = entry.get("FuelUsed")
            self.last_fuel_used = float(used) if isinstance(used, (int, float)) and not isinstance(used, bool) else None
        elif event == "Loadout":
            jump = entry.get("MaxJumpRange")
            self.jump_range = float(jump) if isinstance(jump, (int, float)) and not isinstance(jump, bool) and jump > 0 else None
        elif event in ("NavRouteClear", "Shutdown"):
            self.route = []
        return event == "NavRoute"

    def handle_status(self, entry: Mapping[str, Any]) -> None:
        self.fuel.handle_status(entry)

    def set_route(self, hops: List[Hop]) -> None:
        self.route = list(hops)

    # the route ahead ---------------------------------------------------------------------------------------------------
    def _index(self) -> Optional[int]:
        if not self.system:
            return None
        wanted = self.system.casefold()
        for index, hop in enumerate(self.route):
            if hop.name.casefold() == wanted:
                return index
        return None

    def on_route(self) -> bool:
        """Whether the plotted route applies: the ship is in one of its systems, or its place is not known yet. A ship that has jumped
        off the route (or a route left over from an earlier session) shows nothing until a new route is plotted."""
        return bool(self.route) and (not self.system or self._index() is not None)

    def remaining(self) -> List[Hop]:
        """The systems still to jump to, in order."""
        if not self.on_route():
            return []
        index = self._index()
        return list(self.route[(index + 1) if index is not None else 1:])

    def next_supercharge(self) -> Optional[Tuple[int, Hop]]:
        """(jumps away, the hop) of the next neutron star or white dwarf ahead, or None."""
        for number, hop in enumerate(self.remaining(), 1):
            if star_kind(hop.star_class) in (KIND_NEUTRON, KIND_WHITE_DWARF):
                return number, hop
        return None

    def distance_left(self) -> Optional[float]:
        """Light years from the ship to the end of the route (None when a position is missing)."""
        ahead = self.remaining()
        index = self._index()
        start = self.route[index] if index is not None else (self.route[0] if self.route else None)
        return route_length(ahead, start) if ahead and start is not None else None

    def special_counts(self, hops: List[Hop]) -> Tuple[int, int]:
        """(neutron stars, white dwarfs) among `hops`."""
        kinds = [star_kind(h.star_class) for h in hops]
        return kinds.count(KIND_NEUTRON), kinds.count(KIND_WHITE_DWARF)
