"""Nearest place to land: the closest stations that can take your ship and give you what you need (repairs, fuel, rearming), and the closest fleet carriers that let anyone dock.

It is for deep space and for emergencies, so it asks from the position the journal last gave (`StarPos`), not from a system name: a system you have only just discovered is not in
any database yet, but its coordinates still work. The lookup is Spansh's station search (the same one the material trader finder uses), asked **only when the player presses Find**, and what
it sends is the position, the pad size, the services wanted and the carrier freshness; nothing about the commander. This module is pure logic plus that one request, passed in so the shaping,
the pad rules and the cache are tested without a connection.

- **Pads.** The pad class of the ship comes from `trade_ship` (Coriolis's ship data, from the journal's `Loadout.Ship`). A ship fits a pad of its own size or bigger, so a Python is never sent to an outpost
  with only small pads. A ship that is not known asks for no pad restriction and says so.
- **Stations** are every kind a ship can dock at (starports, outposts, planetary ports and outposts, megaships, construction depots), nearest first. Their records change rarely.
- **Fleet carriers** are listed only when Spansh's record says docking is open to everyone (`carrier_docking_access` is "All"; a carrier whose access Spansh does not know is left out, since
  you could fly there and be refused) and the record was updated within the freshness chosen (carriers jump about weekly and change access, so an old record is a guess). The age of each record is shown.
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence, Tuple

from . import http_identity, mining_spansh_client, trade_ship

CARRIER_TYPE = "Drake-Class Carrier"
STATION_TYPES = ("Coriolis Starport", "Orbis Starport", "Ocellus Starport", "Outpost", "Planetary Outpost", "Planetary Port", "Mega ship",
                 "Space Construction Depot", "Planetary Construction Depot")
SERVICES = ("Refuel", "Repair", "Restock", "Outfitting")
SERVICE_LABELS = {"Refuel": "Refuel", "Repair": "Repair", "Restock": "Rearm (restock)", "Outfitting": "Outfitting"}
DEFAULT_SERVICES = ("Refuel", "Repair")
PAD_AUTO, PAD_ANY, PAD_MEDIUM, PAD_LARGE = "auto", "any", "medium", "large"
FRESH_CHOICES = (7, 14, 30, 90)         # days a carrier's record may be old
DEFAULT_FRESH_DAYS = 14
RESULTS = 8
CACHE_SECONDS = 120
_AGENT = http_identity.user_agent("landing-finder")
Position = Tuple[float, float, float]
SearchFn = Callable[[dict], dict]


@dataclass(frozen=True)
class Place:
    name: str
    system: str
    kind: str                    # Spansh's own type name, e.g. "Ocellus Starport"
    is_carrier: bool
    is_planetary: bool
    distance_ly: float
    arrival_ls: float
    small: Optional[int]
    medium: Optional[int]
    large: Optional[int]
    services: Tuple[str, ...]
    updated: str                 # when Spansh last had a report of it ("" when not given)
    access: str = ""             # a carrier's docking access as Spansh has it


@dataclass(frozen=True)
class Result:
    position: Position
    pad: Optional[str]           # the pad the ship needs: "small", "medium", "large", or None when it was not known / not asked for
    services: Tuple[str, ...]
    fresh_days: int
    stations: Tuple[Place, ...]
    carriers: Tuple[Place, ...]      # empty when carriers were not asked for
    carriers_asked: bool = True


_cache: Dict[tuple, Tuple[float, Result]] = {}


# --- the ship ------------------------------------------------------------------------------------------------------

def ship_pad(ship: Optional[str]) -> Optional[str]:
    """The pad a journal ship name (`Loadout.Ship`) needs, or None when the ship is not known."""
    return trade_ship.pad_size(ship)


def pad_for(choice: str, ship: Optional[str]) -> Optional[str]:
    """The pad to ask for: the ship's own for "auto" (None, meaning no restriction, when the ship is not known), or the one chosen."""
    if choice == PAD_AUTO:
        pad = ship_pad(ship)
        return pad if pad in (PAD_MEDIUM, PAD_LARGE) else None          # a small ship fits everywhere
    return choice if choice in (PAD_MEDIUM, PAD_LARGE) else None


# --- the request -------------------------------------------------------------------------------------------------

def _services_filter(services: Sequence[str]) -> list:
    return [{"name": name} for name in services if name in SERVICES]


def _pad_filter(pad: Optional[str]) -> dict:
    return {f"{pad}_pads": {"comparison": "<=>", "value": [1, 999]}} if pad in (PAD_MEDIUM, PAD_LARGE) else {}


def build_request(position: Position, pad: Optional[str], services: Sequence[str], carriers: bool, fresh_days: int, size: int = RESULTS) -> dict:
    """The Spansh station search for the stations (carriers False) or the open fleet carriers (carriers True) nearest `position`."""
    filters: dict = {**_pad_filter(pad)}
    if services:
        filters["services"] = _services_filter(services)
    if carriers:
        filters["type"] = {"value": [CARRIER_TYPE]}
        filters["carrier_docking_access"] = {"value": ["All"]}
        filters["updated_at"] = {"comparison": "<=>", "value": [f"now-{int(fresh_days)}d", "now"]}
    else:
        filters["type"] = {"value": list(STATION_TYPES)}
    x, y, z = position
    return {"filters": filters, "sort": [{"distance": {"direction": "asc"}}], "size": size, "page": 0, "reference_coords": {"x": x, "y": y, "z": z}}


def _count(value: Any) -> Optional[int]:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def to_place(record: Mapping[str, Any]) -> Place:
    kind = str(record.get("type") or "?")
    return Place(
        name=str(record.get("name") or "?"), system=str(record.get("system_name") or "?"), kind=kind, is_carrier=kind == CARRIER_TYPE,
        is_planetary=bool(record.get("is_planetary", False)), distance_ly=float(record.get("distance") or 0.0),
        arrival_ls=float(record.get("distance_to_arrival") or 0.0), small=_count(record.get("small_pads")), medium=_count(record.get("medium_pads")),
        large=_count(record.get("large_pads")), services=tuple(str(s.get("name")) for s in record.get("services") or [] if isinstance(s, Mapping)),
        updated=str(record.get("updated_at") or ""), access=str(record.get("carrier_docking_access") or ""))


def _usable(place: Place, pad: Optional[str], services: Sequence[str]) -> bool:
    """The search should only return stations that fit; a record that does not is not shown rather than trusted."""
    return trade_ship.fits(pad, place.small, place.medium, place.large) and all(name in place.services for name in services)


def _shape(data: Mapping[str, Any], pad: Optional[str], services: Sequence[str], carriers: bool) -> Tuple[Place, ...]:
    found = []
    for record in data.get("results") or []:
        if not isinstance(record, Mapping):
            continue
        place = to_place(record)
        if place.is_carrier != carriers or not _usable(place, pad, services):
            continue
        if carriers and place.access != "All":
            continue
        found.append(place)
    return tuple(sorted(found, key=lambda p: p.distance_ly))


def _key(position: Position, pad: Optional[str], services: Sequence[str], carriers: bool, fresh_days: int) -> tuple:
    return (tuple(round(c, 1) for c in position), pad, tuple(sorted(services)), carriers, fresh_days)


def find(position: Position, pad: Optional[str], services: Sequence[str] = DEFAULT_SERVICES, carriers: bool = True, fresh_days: int = DEFAULT_FRESH_DAYS, *,
         search: Optional[SearchFn] = None, now: Callable[[], float] = time.monotonic) -> Result:
    """The closest places to land from `position`. Raises on a network failure (the caller shows it) and ValueError for a position that is not three numbers. An answer is remembered for two minutes."""
    try:
        x, y, z = (float(c) for c in position)
    except (TypeError, ValueError):
        raise ValueError("Your position is not known yet. Jump or log in first.")
    position = (x, y, z)
    services = tuple(s for s in services if s in SERVICES)
    key = _key(position, pad, services, carriers, fresh_days)
    held = _cache.get(key)
    if held is not None and now() - held[0] < CACHE_SECONDS:
        return held[1]
    ask = search or (lambda body: mining_spansh_client._post_station_search(body, _AGENT))
    stations = _shape(ask(build_request(position, pad, services, False, fresh_days)), pad, services, False)
    open_carriers = _shape(ask(build_request(position, pad, services, True, fresh_days)), pad, services, True) if carriers else ()
    result = Result(position, pad, services, fresh_days, stations, open_carriers, carriers)
    _cache[key] = (now(), result)
    return result


def clear_cache() -> None:
    _cache.clear()


# --- how it reads ------------------------------------------------------------------------------------------------

def parse_time(text: str) -> Optional[datetime]:
    try:
        return datetime.strptime(text, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return None


def age_text(updated: str, now: Optional[datetime] = None) -> str:
    """How long ago Spansh last had a report of a place: "today", "3 days ago", "5 months ago", or "unknown"."""
    seen = parse_time(updated)
    if seen is None:
        return "unknown"
    days = max(0, ((now or datetime.now(timezone.utc)) - seen).days)
    if days == 0:
        return "today"
    if days < 60:
        return f"{days} day{'s' if days != 1 else ''} ago"
    months = days // 30
    return f"{months} months ago" if months < 24 else f"{days // 365} years ago"


def describe_place(place: Place) -> str:
    """`orbital Ocellus Starport, 1,234 ls` / `ground Planetary Outpost, 80 ls`; a carrier is `fleet carrier`."""
    if place.is_carrier:
        return "fleet carrier"
    return f"{'ground' if place.is_planetary else 'orbital'} {place.kind}, {place.arrival_ls:,.0f} ls"


def pads_text(place: Place) -> str:
    """`S4 M2 L1`: how many small, medium and large pads Spansh lists (a size it does not give is left out)."""
    parts = [f"{letter}{count}" for letter, count in (("S", place.small), ("M", place.medium), ("L", place.large)) if count]
    return " ".join(parts) or "?"


def services_text(place: Place, wanted: Sequence[str]) -> str:
    """The wanted services the place has, in the player's words."""
    return ", ".join(SERVICE_LABELS.get(name, name) for name in wanted if name in place.services) or "-"



# --- where the ship is -------------------------------------------------------------------------------------------

class Tracker:
    """The last position and ship the journal gave: `StarPos` (from `FSDJump`, `Location` and `CarrierJump`) and `Loadout.Ship`."""

    POSITION_EVENTS = ("FSDJump", "Location", "CarrierJump")

    def __init__(self) -> None:
        self.position: Optional[Position] = None
        self.system = ""
        self.ship = ""

    def apply(self, entry: Mapping[str, Any]) -> bool:
        """Notes what an event says; True when something changed."""
        event = entry.get("event")
        if event in self.POSITION_EVENTS:
            pos = entry.get("StarPos")
            if isinstance(pos, (list, tuple)) and len(pos) == 3:
                try:
                    new = (float(pos[0]), float(pos[1]), float(pos[2]))
                except (TypeError, ValueError):
                    return False
                changed = new != self.position or entry.get("StarSystem") != self.system
                self.position, self.system = new, str(entry.get("StarSystem") or self.system)
                return changed
        elif event == "Loadout" and entry.get("Ship"):
            changed = entry.get("Ship") != self.ship
            self.ship = str(entry["Ship"])
            return changed
        return False

    def reset(self) -> None:
        self.position, self.system, self.ship = None, "", ""


def read_from_journals(folder: Optional[str] = None, newest: int = 3) -> Tracker:
    """The position and ship in the newest journals, for when EDMC starts in the middle of a session and has not seen a jump yet. Reads files only."""
    import re
    from . import journal_files
    wanted = re.compile(r'"event":\s*"(?:FSDJump|Location|CarrierJump|Loadout)"')
    tracker = Tracker()
    try:
        for path in journal_files.files_modified_since(0.0, folder)[-newest:]:
            for entry in journal_files.read_events(path, wanted):
                tracker.apply(entry)
    except Exception:
        pass
    return tracker
