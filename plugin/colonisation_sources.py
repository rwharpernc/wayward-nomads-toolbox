"""Where to buy a colonisation commodity: the closest stations (and, if asked, fleet carriers) that have it in stock,
found with Spansh's station search (`mining_spansh_client.search_best_price_stations`, shared with the mining Price
Finder and Trade). Nothing here touches Tk, and the network call is passed in, so the shaping, filtering and ordering
are tested without a connection.

The landing-pad choice is deliberate: a commander may swap to a smaller cargo ship when a commodity isn't sold at a
large-pad station, so the default is ANY size. "Medium or larger" and "Large only" ask Spansh for stations with at
least one pad of that size. Fleet carriers are a separate, opt-in search (their stock and prices are volatile and they
can move), and are listed after the stations."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional, Sequence, Tuple

from . import trade_prices
from .mining_spansh_client import StationPrice, search_best_price_stations

PAD_ANY = "any"
PAD_MEDIUM = "medium"
PAD_LARGE = "large"
PAD_CHOICES = ((PAD_ANY, "Any size"), (PAD_MEDIUM, "Medium or larger"), (PAD_LARGE, "Large only"))

SORT_DISTANCE = "distance"
SORT_PRICE = "price"

DEFAULT_RADIUS_LY = 50
RADIUS_CHOICES = (25, 50, 100, 200, 500)   # light years; "no limit" is None
MAX_AGE_DAYS = 7          # market data older than this is ignored: it is probably out of date
STATION_RESULTS = 25
CARRIER_RESULTS = 10

CACHE_SECONDS = 120   # the same search asked again within this long is answered from memory, not Spansh

SearchFn = Callable[..., List[StationPrice]]
_cache: Dict[tuple, Tuple[float, "SearchResult"]] = {}


@dataclass(frozen=True)
class Source:
    station: str
    system: str
    kind: str            # Spansh's station type, e.g. "Coriolis Starport"
    is_carrier: bool
    is_planetary: bool
    pad: str             # the largest pad the station has: "Large" / "Medium" / "Small" / "?" when unknown
    distance_ly: float
    arrival_ls: float
    price: int           # cr per ton
    supply: int          # tons in stock


@dataclass(frozen=True)
class SearchResult:
    stations: List[Source]
    carriers: List[Source]     # empty unless carriers were asked for


def largest_pad(item: StationPrice) -> str:
    """The biggest landing pad the station has, from Spansh's pad counts."""
    if item.large_pads:
        return "Large"
    if item.medium_pads:
        return "Medium"
    if item.small_pads:
        return "Small"
    return "?"


def _fits(item: StationPrice, min_pad: str) -> bool:
    """Whether a station has a pad of the wanted size. A station Spansh gave no pad figures for is kept: leaving a
    possible source out is worse than showing one the commander has to check."""
    if min_pad == PAD_ANY or (item.small_pads is None and item.medium_pads is None and item.large_pads is None):
        return True
    if min_pad == PAD_LARGE:
        return bool(item.large_pads)
    return bool(item.large_pads or item.medium_pads)


def to_source(item: StationPrice) -> Source:
    carrier = trade_prices.is_carrier(item.station_type)
    return Source(
        station=item.station, system=item.system, kind=item.station_type, is_carrier=carrier,
        is_planetary=item.is_planetary, pad=largest_pad(item), distance_ly=item.distance_ly, arrival_ls=item.distance_to_arrival_ls,
        price=item.price, supply=item.quantity)


def order(sources: Sequence[Source], sort: str = SORT_DISTANCE) -> List[Source]:
    """Closest first (then by price), or cheapest first (then by distance)."""
    if sort == SORT_PRICE:
        return sorted(sources, key=lambda s: (s.price, s.distance_ly, s.arrival_ls))
    return sorted(sources, key=lambda s: (s.distance_ly, s.price, s.arrival_ls))


def clear_cache() -> None:
    _cache.clear()


def find(reference_system: str, commodity: str, *, radius_ly: Optional[float] = DEFAULT_RADIUS_LY,
         pad: str = PAD_ANY, include_carriers: bool = False, sort: str = SORT_DISTANCE,
         search: SearchFn = search_best_price_stations, now: Callable[[], float] = time.monotonic) -> SearchResult:
    """Stations (and optionally fleet carriers) near `reference_system` with `commodity` in stock. `search` is the
    Spansh call; it raises on a network or parse failure, which the caller reports. Stations are asked for apart from
    carriers so the volatile carrier prices cannot crowd the real stations out of the first page."""
    if not reference_system.strip():
        raise ValueError("Enter a system to search around.")
    key = (reference_system.strip().casefold(), commodity.casefold(), radius_ly, pad, include_carriers, sort, search)
    cached = _cache.get(key)
    if cached is not None and now() - cached[0] < CACHE_SECONDS:
        return cached[1]
    required = None if pad == PAD_ANY else pad
    spansh_sort = SORT_DISTANCE if sort == SORT_DISTANCE else SORT_PRICE
    stations = search(reference_system.strip(), commodity, "Buy", radius_ly, max_results=STATION_RESULTS,
                      market_days_old=MAX_AGE_DAYS, station_types=trade_prices.station_types(True),
                      sort_by=spansh_sort, required_pad=required)
    carriers: List[StationPrice] = []
    if include_carriers:
        carriers = search(reference_system.strip(), commodity, "Buy", radius_ly, max_results=CARRIER_RESULTS,
                          market_days_old=MAX_AGE_DAYS, station_types=trade_prices.CARRIER_TYPES,
                          sort_by=spansh_sort, required_pad=required)
    result = SearchResult(
        stations=order([to_source(i) for i in stations if _fits(i, pad)], sort),
        carriers=order([to_source(i) for i in carriers if _fits(i, pad)], sort))
    _cache[key] = (now(), result)   # a failed search raised above, so a failure is never remembered
    return result
