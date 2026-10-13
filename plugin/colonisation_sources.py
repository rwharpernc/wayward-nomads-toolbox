"""Where to buy a colonisation commodity: the closest stations (and, if asked, fleet carriers) that have it in stock,
found with Spansh's station search (`mining_spansh_client.search_best_price_stations`, shared with the mining Price
Finder and Trade). Nothing here touches Tk, and the network call is passed in, so the shaping, filtering and ordering
are tested without a connection.

The landing-pad choice is deliberate: a commander may swap to a smaller cargo ship when a commodity isn't sold at a
large-pad station, so the default is ANY size. "Medium or larger" and "Large only" ask Spansh for stations with at
least one pad of that size. Fleet carriers are a separate, opt-in search (their stock and prices are volatile and they
can move), and are listed after the stations."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

from . import trade_prices
from .mining_spansh_client import StationPrice, search_best_price_stations, search_stations_selling_all

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

WHOLE_LIST_STATIONS = 5     # stations shown per commodity when the whole list is searched at once
WHOLE_LIST_CARRIERS = 2     # fleet carriers shown per commodity then (only when carriers were asked for)
ONE_STOP_RESULTS = 5        # stations asked for that sell the whole list in one place
WHOLE_LIST_PAUSE = 0.4      # seconds between two requests to Spansh, so a long list is not sent as a burst

CACHE_SECONDS = 120   # the same search asked again within this long is answered from memory, not Spansh

SearchFn = Callable[..., List[StationPrice]]
OneStopFn = Callable[..., List[Tuple[StationPrice, Dict[str, Tuple[int, int]]]]]
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


def _cache_key(reference_system: str, commodity: str, radius_ly: Optional[float], pad: str, include_carriers: bool,
               sort: str, search: SearchFn) -> tuple:
    return (reference_system.strip().casefold(), commodity.casefold(), radius_ly, pad, include_carriers, sort, search)


def is_cached(reference_system: str, commodity: str, *, radius_ly: Optional[float] = DEFAULT_RADIUS_LY,
              pad: str = PAD_ANY, include_carriers: bool = False, sort: str = SORT_DISTANCE,
              search: SearchFn = search_best_price_stations, now: Callable[[], float] = time.monotonic) -> bool:
    """Whether `find` with these arguments would be answered from memory (so it sends no request)."""
    cached = _cache.get(_cache_key(reference_system, commodity, radius_ly, pad, include_carriers, sort, search))
    return cached is not None and now() - cached[0] < CACHE_SECONDS


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
    key = _cache_key(reference_system, commodity, radius_ly, pad, include_carriers, sort, search)
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


# --- the whole list at once ----------------------------------------------------------------------------------------


@dataclass
class WholeListResult:
    """What searching every outstanding commodity found: per commodity, in the order asked, plus the ones that failed."""
    found: List[Tuple[str, SearchResult]] = field(default_factory=list)   # (commodity label, its sources)
    failed: List[Tuple[str, str]] = field(default_factory=list)           # (commodity label, why)
    stopped: bool = False                                                 # the commander stopped it part-way

    def without_sources(self) -> List[str]:
        """Commodities the search ran for but found no station (or carrier) for."""
        return [label for label, result in self.found if not result.stations and not result.carriers]


def find_whole_list(reference_system: str, commodities: Sequence[str], *, radius_ly: Optional[float] = DEFAULT_RADIUS_LY,
                    pad: str = PAD_ANY, include_carriers: bool = False, sort: str = SORT_DISTANCE,
                    search: SearchFn = search_best_price_stations, now: Callable[[], float] = time.monotonic,
                    sleep: Callable[[float], None] = time.sleep, pause: float = WHOLE_LIST_PAUSE,
                    progress: Optional[Callable[[int, int, str], None]] = None,
                    cancelled: Optional[Callable[[], bool]] = None, one_stop: Optional[OneStopFn] = None) -> WholeListResult:
    """`find` for each commodity in turn, one request each (Spansh has no multi-commodity search), pausing between
    requests that really went out. A commodity whose search fails is recorded and the rest carry on, so one bad answer
    does not lose the others; a blank system is refused outright. `progress(done, total, label)` is called before each
    commodity, and `cancelled()` is checked between them. With `one_stop` (Spansh's "has all of these" search) one more request
    asks for stations that sell every commodity in the list; any it finds are added to each commodity's sources, so the
    route can use a station that is not among the nearest few for any one commodity. That request is a bonus: if it fails,
    nothing is lost."""
    if not reference_system.strip():
        raise ValueError("Enter a system to search around.")
    out = WholeListResult()
    options = dict(radius_ly=radius_ly, pad=pad, include_carriers=include_carriers, sort=sort, search=search, now=now)
    sent_any = False
    for index, label in enumerate(commodities):
        if cancelled is not None and cancelled():
            out.stopped = True
            break
        if progress is not None:
            progress(index, len(commodities), label)
        cached = is_cached(reference_system, label, **options)
        if sent_any and not cached and pause > 0:
            sleep(pause)
        try:
            out.found.append((label, find(reference_system, label, **options)))
            sent_any = sent_any or not cached
        except Exception as exc:   # a network or parse failure for this commodity only
            out.failed.append((label, str(exc) or exc.__class__.__name__))
            sent_any = True
    if one_stop is not None and not out.stopped and len(out.found) >= 2 and not out.failed:
        try:
            _add_one_stop(out, reference_system, one_stop, radius_ly, pad, include_carriers, sort)
        except Exception:   # an extra; the per-commodity answers stand without it
            pass
    return out


def _add_one_stop(out: WholeListResult, reference_system: str, one_stop: OneStopFn, radius_ly: Optional[float],
                  pad: str, include_carriers: bool, sort: str) -> None:
    """Add the stations that sell every commodity searched to each commodity's sources (see `find_whole_list`)."""
    labels = [label for label, _ in out.found]
    types = trade_prices.station_types(True) + (trade_prices.CARRIER_TYPES if include_carriers else [])
    hits = one_stop(reference_system.strip(), labels, radius_ly, max_results=ONE_STOP_RESULTS, market_days_old=MAX_AGE_DAYS,
                    station_types=types, required_pad=None if pad == PAD_ANY else pad)
    for index, (label, result) in enumerate(out.found):
        have = {(s.station, s.system) for s in [*result.stations, *result.carriers]}
        stations, carriers = list(result.stations), list(result.carriers)
        for item, offers in hits:
            if (item.station, item.system) in have or label not in offers or not _fits(item, pad):
                continue
            price, supply = offers[label]
            source = to_source(StationPrice(
                station=item.station, system=item.system, station_type=item.station_type, distance_ly=item.distance_ly,
                distance_to_arrival_ls=item.distance_to_arrival_ls, is_planetary=item.is_planetary, price=price,
                quantity=supply, small_pads=item.small_pads, medium_pads=item.medium_pads, large_pads=item.large_pads))
            (carriers if source.is_carrier else stations).append(source)
        out.found[index] = (label, SearchResult(stations=order(stations, sort), carriers=order(carriers, sort)))


# --- a shopping route from the whole-list answer ----------------------------------------------------------------------

ROUTE_MAX_STOPS = 6   # a suggested route never has more stops than this: past that it is a different trip


@dataclass(frozen=True)
class Purchase:
    commodity: str
    tonnes: int
    price: int           # cr per ton at this stop


@dataclass(frozen=True)
class Stop:
    station: str
    system: str
    kind: str
    is_carrier: bool
    distance_ly: float
    buys: Tuple[Purchase, ...]

    @property
    def tonnes(self) -> int:
        return sum(b.tonnes for b in self.buys)


@dataclass(frozen=True)
class RoutePlan:
    stops: Tuple[Stop, ...]
    needed: int                       # tons the commodities searched for still need in all
    covered: int                      # of that, how many tons the stops can supply
    uncovered: Tuple[Tuple[str, int], ...]   # (commodity, tons) the stops cannot supply (not in range, or too little stock)

    def lines(self) -> List[str]:
        """The plan as plain lines: a summary, one line per stop, and what is left over."""
        if not self.stops:
            return []
        out = [f"Suggested shopping route: {len(self.stops)} stop{'s' if len(self.stops) != 1 else ''}, "
               f"{self.covered:,} of {self.needed:,} t covered"]
        for number, stop in enumerate(self.stops, 1):
            buys = ", ".join(f"{b.commodity} {b.tonnes:,} t" for b in stop.buys)
            tag = " (fleet carrier)" if stop.is_carrier else ""
            out.append(f"{number}. {stop.station} ({stop.system}){tag}, {stop.distance_ly:,.1f} ly: {buys}")
        if self.uncovered:
            out.append("Not covered: " + ", ".join(f"{label} {tons:,} t" for label, tons in self.uncovered))
        return out


def plan_route(found: Sequence[Tuple[str, "SearchResult"]], needs: Dict[str, int], max_stops: int = ROUTE_MAX_STOPS) -> RoutePlan:
    """Pick the few stops that between them supply the most of what is still needed, from the per-commodity answers of a
    whole-list search. `needs` is the tons still to get for each commodity (by label).

    It is greedy: take the station that can supply the most tons of what is still outstanding (a station is offered once per
    commodity it sells, so one that sells several wins), take that off the needs, and repeat until nothing is left, nothing more
    can be covered, or `max_stops` is reached. Ties go to the nearer station, then the cheaper one. The stops are then put in
    order of distance from the search's reference system (the nearest first), which is the order to fly them. Only the stations
    the searches returned are considered, so a commodity with none in range is reported as not covered rather than guessed."""
    remaining = {label: int(tons) for label, tons in needs.items() if tons and tons > 0}
    needed = sum(remaining.values())
    # (station, system) -> {commodity: (supply, price)} plus the details of the station
    offers: Dict[Tuple[str, str], Dict[str, Tuple[int, int]]] = {}
    details: Dict[Tuple[str, str], Source] = {}
    for label, result in found:
        if label not in remaining:
            continue
        for source in [*result.stations, *result.carriers]:
            if source.supply <= 0:
                continue
            key = (source.station, source.system)
            offers.setdefault(key, {})[label] = (source.supply, source.price)
            details.setdefault(key, source)

    chosen: List[Stop] = []
    left = dict(remaining)
    candidates = dict(offers)
    while left and candidates and len(chosen) < max_stops:
        def coverage(key: Tuple[str, str]) -> int:
            return sum(min(supply, left.get(label, 0)) for label, (supply, _price) in candidates[key].items())
        best = max(candidates, key=lambda k: (coverage(k), -details[k].distance_ly, -sum(p for _s, p in candidates[k].values())))
        if coverage(best) <= 0:
            break
        buys = []
        for label, (supply, price) in sorted(candidates[best].items(), key=lambda kv: kv[0].casefold()):
            take = min(supply, left.get(label, 0))
            if take > 0:
                buys.append(Purchase(label, take, price))
                left[label] -= take
                if left[label] <= 0:
                    del left[label]
        source = details[best]
        chosen.append(Stop(source.station, source.system, source.kind, source.is_carrier, source.distance_ly, tuple(buys)))
        del candidates[best]
    chosen.sort(key=lambda stop: (stop.distance_ly, stop.station.casefold()))
    uncovered = tuple(sorted(left.items(), key=lambda kv: kv[0].casefold()))
    return RoutePlan(stops=tuple(chosen), needed=needed, covered=needed - sum(left.values()), uncovered=uncovered)


# --- remembered choices --------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class SearchPrefs:
    """The where-to-buy options the commander last used, kept between sessions. These are window preferences, not
    anything about their play, so they are shared by every commander like the window's size."""
    radius_ly: Optional[float] = DEFAULT_RADIUS_LY   # None = no limit
    pad: str = PAD_ANY
    carriers: bool = False
    sort: str = SORT_DISTANCE


def dump_prefs(prefs: SearchPrefs) -> str:
    return json.dumps({"radius": prefs.radius_ly, "pad": prefs.pad, "carriers": prefs.carriers, "sort": prefs.sort})


def load_prefs(raw: Any) -> SearchPrefs:
    """The saved choices, with anything missing, unreadable or out of range replaced by its default."""
    try:
        data = json.loads(raw) if isinstance(raw, str) and raw.strip() else {}
    except ValueError:
        data = {}
    if not isinstance(data, dict):
        data = {}
    default = SearchPrefs()
    radius = data.get("radius", default.radius_ly)
    if radius is not None and (isinstance(radius, bool) or radius not in RADIUS_CHOICES):
        radius = default.radius_ly
    pad = data.get("pad")
    sort = data.get("sort")
    carriers = data.get("carriers")
    return SearchPrefs(
        radius_ly=float(radius) if radius is not None else None,
        pad=pad if pad in {key for key, _ in PAD_CHOICES} else default.pad,
        carriers=carriers if isinstance(carriers, bool) else default.carriers,
        sort=sort if sort in (SORT_DISTANCE, SORT_PRICE) else default.sort)
