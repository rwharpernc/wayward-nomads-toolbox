"""
Trade: the best back-and-forth pair of stations, loaded both ways.

Spansh's route planner returns the best chain of hops, which is not always a pair that comes back. This module
finds pairs itself: one station search returns the full market of every station near the start, and then it works
out, for each neighbour, what to carry out and what to carry back. A pair only counts when BOTH legs make a profit,
so there is never an empty leg. Pairs are ranked by estimated profit per hour.

The pairing is pure (no network); `fetch_stations` is the one network call (Spansh's /api/stations/search, the same
service Market uses). Prices are only as fresh as the last player who docked there; `max_age_h` limits that.
"""
from __future__ import annotations

import json
import math
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence

from . import http_identity
from . import trade_spansh_client as routes

SEARCH_URL = "https://spansh.co.uk/api/stations/search"
REQUEST_TIMEOUT_S = 30
PAGE_SIZE = 100
MAX_PAGES = 3                 # up to 300 nearest stations
CARRIER_TYPE = "Drake-Class Carrier"
RESULTS_KEPT = 3
_USER_AGENT = http_identity.user_agent("trade-roundtrip")


@dataclass
class Offer:
    """One commodity on a station's market, as Spansh reports it."""
    name: str
    buy_price: int    # what the station charges you
    sell_price: int   # what the station pays you
    supply: int
    demand: int


@dataclass
class Station:
    name: str
    system: str
    x: float
    y: float
    z: float
    arrival_ls: float
    is_planetary: bool
    is_carrier: bool
    pads: Dict[str, int]                       # {"small": n, "medium": n, "large": n}
    market: Dict[str, Offer] = field(default_factory=dict)


@dataclass
class Load:
    """What to carry on one leg."""
    items: List[tuple]   # (commodity, tonnes, profit per tonne)
    tonnes: int
    profit: int


@dataclass
class RoundTrip:
    a: Station
    b: Station
    out: Load            # a -> b
    back: Load           # b -> a
    distance_ly: float
    profit: int          # per full loop
    per_hour: int        # estimate


def _int(value: Any) -> int:
    return int(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else 0


def parse_station(raw: Dict[str, Any]) -> Optional[Station]:
    """One Spansh station record -> Station; None when it has no usable market."""
    try:
        market = {}
        for entry in raw.get("market") or []:
            name = str(entry.get("commodity") or "")
            if name:
                market[name] = Offer(name, _int(entry.get("buy_price")), _int(entry.get("sell_price")),
                                     _int(entry.get("supply")), _int(entry.get("demand")))
        if not market:
            return None
        return Station(
            name=str(raw.get("name") or "?"), system=str(raw.get("system_name") or "?"),
            x=float(raw.get("system_x") or 0), y=float(raw.get("system_y") or 0), z=float(raw.get("system_z") or 0),
            arrival_ls=float(raw.get("distance_to_arrival") or 0), is_planetary=bool(raw.get("is_planetary")),
            is_carrier=str(raw.get("type") or "") == CARRIER_TYPE,
            pads={"small": _int(raw.get("small_pads")), "medium": _int(raw.get("medium_pads")),
                  "large": _int(raw.get("large_pads"))},
            market=market)
    except (TypeError, ValueError):
        return None


def fetch_stations(system: str, radius_ly: float, max_age_h: int) -> List[Station]:
    """The nearest stations with a market updated recently enough, nearest first. Raises on a network or parse
    failure (the caller logs it)."""
    age = f"now-{max(1, int(max_age_h))}h" if max_age_h > 0 else "now-30d"
    found: List[Station] = []
    for page in range(MAX_PAGES):
        body = {"filters": {"distance": {"min": "0", "max": str(max(1, int(radius_ly)))},
                            "market_updated_at": {"comparison": "<=>", "value": [age, "now"]}},
                "sort": [{"distance": {"direction": "asc"}}], "size": PAGE_SIZE, "page": page,
                "reference_system": system}
        request = urllib.request.Request(SEARCH_URL, data=json.dumps(body).encode("utf-8"),
                                         headers={"User-Agent": _USER_AGENT, "Content-Type": "application/json"},
                                         method="POST")
        with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT_S) as response:
            data = json.loads(response.read().decode("utf-8"))
        results = data.get("results") or []
        found.extend(s for s in (parse_station(r) for r in results) if s is not None)
        if len(results) < PAGE_SIZE:
            break
    return found


def distance_ly(a: Station, b: Station) -> float:
    return math.sqrt((a.x - b.x) ** 2 + (a.y - b.y) ** 2 + (a.z - b.z) ** 2)


def best_load(source: Station, dest: Station, cargo: int, capital: int, min_supply: int = 0,
              min_demand: int = 0) -> Optional[Load]:
    """The most profitable hold from `source` to `dest`: commodities in order of profit per tonne, each limited by
    the supply there, the demand here and what you can afford, until the hold is full. None when nothing profits."""
    candidates = []
    for name, buy in source.market.items():
        sell = dest.market.get(name)
        if sell is None or buy.buy_price <= 0 or sell.sell_price <= buy.buy_price:
            continue
        if buy.supply <= 0 or sell.demand <= 0 or buy.supply < min_supply or sell.demand < min_demand:
            continue
        candidates.append((sell.sell_price - buy.buy_price, name, buy, sell))
    candidates.sort(key=lambda c: -c[0])
    room, money, items, profit = max(0, int(cargo)), max(0, int(capital)), [], 0
    for per_t, name, buy, sell in candidates:
        if room <= 0 or money < buy.buy_price:
            break
        tonnes = min(room, buy.supply, sell.demand, money // buy.buy_price)
        if tonnes <= 0:
            continue
        items.append((name, tonnes, per_t))
        room -= tonnes
        money -= tonnes * buy.buy_price
        profit += tonnes * per_t
    if not items:
        return None
    return Load(items, sum(i[1] for i in items), profit)


def _fits(station: Station, ship_pad: Optional[str]) -> bool:
    if ship_pad is None:
        return True
    order = ("small", "medium", "large")
    if sum(station.pads.values()) == 0:
        return True    # no pad data: don't hold it against the station
    return any(station.pads.get(size, 0) > 0 for size in order[order.index(ship_pad):])


def find_round_trips(start: Station, others: Sequence[Station], cargo: int, capital: int, jump_range_ly: float,
                     ship_pad: Optional[str] = None, min_supply: int = 0, min_demand: int = 0,
                     include_ground: bool = True, include_carriers: bool = False,
                     max_arrival_ls: float = 0, limit: int = RESULTS_KEPT) -> List[RoundTrip]:
    """The best pairs with `start`, each leg loaded and profitable, best estimated profit per hour first."""
    trips: List[RoundTrip] = []
    for other in others:
        if other is start or (other.name == start.name and other.system == start.system):
            continue
        if (other.is_planetary and not include_ground) or (other.is_carrier and not include_carriers):
            continue
        if max_arrival_ls and other.arrival_ls > max_arrival_ls:
            continue
        if not _fits(other, ship_pad):
            continue
        out = best_load(start, other, cargo, capital, min_supply, min_demand)
        back = best_load(other, start, cargo, capital + out.profit if out else capital, min_supply, min_demand) \
            if out else None
        if out is None or back is None:
            continue    # one leg would be empty: not a round trip
        gap = distance_ly(start, other)
        leg_out = routes.Hop(start.system, start.name, start.arrival_ls, other.system, other.name, other.arrival_ls,
                             gap, profit=out.profit)
        leg_back = routes.Hop(other.system, other.name, other.arrival_ls, start.system, start.name,
                              start.arrival_ls, gap, profit=back.profit)
        seconds = routes.estimate_hop_seconds(leg_out, jump_range_ly) + routes.estimate_hop_seconds(leg_back, jump_range_ly)
        profit = out.profit + back.profit
        trips.append(RoundTrip(start, other, out, back, gap, profit, int(profit * 3600 / seconds) if seconds else 0))
    trips.sort(key=lambda t: -t.per_hour)
    return trips[:max(1, limit)]


def find_start(stations: Sequence[Station], system: str, name: str) -> Optional[Station]:
    """The start station among the search results (matched ignoring case)."""
    for station in stations:
        if station.name.casefold() == name.casefold() and station.system.casefold() == system.casefold():
            return station
    return None
