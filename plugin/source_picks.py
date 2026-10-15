"""The four answers to "where do I buy (or sell) this?": the closest place, the best nearby, the cheapest anywhere, and a recommended one. Pure logic apart from the
Spansh search, which is passed in so the choosing is tested without a connection.

The four picks, for buying (selling is the mirror image, with the highest price as the best):

- **Closest**: the nearest station that has what you need in stock, whatever the price.
- **Best local**: the cheapest station within the radius you set (the "Near me" radius), nearest among equal prices.
- **Cheapest anywhere**: the cheapest station in the galaxy, nearest among equal prices.
- **Recommended**: the nearest station whose price is within `TOLERANCE` (10%) of the cheapest price in the galaxy. This is the one that usually costs the
  least overall: nearly the best price without the long trip.

"In stock" means at least the amount asked for (`needed_t`); when no station has that much, the search is repeated for any stock and the pick says how much the
station has. Stations are asked for apart from fleet carriers (a carrier can move, and carriers are priced so differently that they fill a price-sorted list),
and the best carrier is only mentioned when it beats the cheapest station. Your landing pad size and the ground-facilities setting apply, and market data older
than `MAX_AGE_DAYS` days is ignored. Each pick costs one Spansh search (about four in all, a fifth when carriers are included), asked one after another.

Used by the Trade Market page and by the Missions "Source commodities" window."""
from __future__ import annotations

import math
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from . import trade_prices
from .mining_spansh_client import StationPrice, search_best_price_stations
from .trade_prices import BUY, SELL, Offer

CLOSEST, LOCAL, CHEAPEST, RECOMMENDED = "closest", "local", "cheapest", "recommended"
KINDS = (CLOSEST, LOCAL, CHEAPEST, RECOMMENDED)
LABELS = {CLOSEST: "Closest", LOCAL: "Best local", CHEAPEST: "Cheapest anywhere", RECOMMENDED: "Recommended"}
SELL_LABELS = {CLOSEST: "Closest", LOCAL: "Best local", CHEAPEST: "Highest anywhere", RECOMMENDED: "Recommended"}
TOLERANCE = 0.10
MAX_AGE_DAYS = 7
FETCH = 25                      # stations asked for per search; the first that qualifies is the pick
PAUSE_S = 0.4                   # between two searches, so several are not sent as a burst

SearchFn = Callable[..., List[StationPrice]]


@dataclass(frozen=True)
class Pick:
    kind: str
    offer: Offer
    note: str = ""              # "only 12 t in stock", "also the cheapest anywhere"


@dataclass
class Picks:
    commodity: str
    side: str
    needed_t: int
    picks: Dict[str, Pick] = field(default_factory=dict)
    notes: List[str] = field(default_factory=list)
    reference: str = ""

    def label(self, kind: str) -> str:
        return (SELL_LABELS if self.side == SELL else LABELS)[kind]

    def lines(self) -> List[str]:
        """'Closest: Station (System), 12 ly, 2,356 cr/t' for each pick found, in order."""
        out = []
        for kind in KINDS:
            pick = self.picks.get(kind)
            if pick is not None:
                out.append(f"{self.label(kind)}: {describe(pick)}")
        return out


def describe(pick: Pick) -> str:
    offer = pick.offer
    text = f"{offer.station} ({offer.system}), {offer.distance_ly:.0f} ly, {offer.price:,} cr/t"
    return text + (f" - {pick.note}" if pick.note else "")


def required_pad(ship_pad: Optional[str]) -> Optional[str]:
    """What to ask Spansh for: it filters on medium or large pads only (a small ship fits anywhere)."""
    return ship_pad if ship_pad in ("medium", "large") else None


def _better_price(side: str, offer: Offer) -> tuple:
    """Sort key: best price first (lowest to buy, highest to sell), then nearest."""
    return (offer.price if side == BUY else -offer.price, offer.distance_ly)


def _band(side: str, best_price: int, tolerance: float) -> tuple:
    """(low, high) price limits for 'within the tolerance of the best price'."""
    if side == BUY:
        return best_price, int(math.floor(best_price * (1 + tolerance)))
    return int(math.ceil(best_price * (1 - tolerance))), best_price


def _offers(results: List[StationPrice], needed_t: int, side: str, ship_pad: Optional[str], include_ground: bool, carriers: bool) -> List[Offer]:
    return trade_prices.rank_offers(results, max(1, needed_t), include_carriers=carriers, ship_pad=ship_pad, side=side, include_ground=include_ground)


def find(reference_system: str, commodity: str, side: str, needed_t: int, *, radius_ly: float, ship_pad: Optional[str] = None,
         include_carriers: bool = True, include_ground: bool = True, tolerance: float = TOLERANCE,
         search: SearchFn = search_best_price_stations, pause: Callable[[float], None] = time.sleep,
         cancelled: Callable[[], bool] = lambda: False) -> Picks:
    """The four picks for `commodity`, `side` BUY or SELL, from `reference_system`. `needed_t` is the amount (what a mission still needs, or your free
    hold space when buying and your cargo when selling); 0 means any stock will do. Raises whatever the search raises on a network failure, and stops early
    (returning what it has) if `cancelled()` becomes true."""
    transaction = "Buy" if side == BUY else "Sell"
    wanted = max(0, needed_t)
    result = Picks(commodity, side, wanted, reference=reference_system)
    stations = trade_prices.station_types(include_ground)
    pad = required_pad(ship_pad)
    searches = 0

    def run(max_distance: Optional[float], sort_by: str, types: List[str], min_quantity: int, price_range: Optional[tuple] = None) -> List[StationPrice]:
        nonlocal searches
        if searches:
            pause(PAUSE_S)
        searches += 1
        return search(reference_system, commodity, transaction, max_distance, max_results=FETCH, market_days_old=MAX_AGE_DAYS, station_types=types,
                      sort_by=sort_by, required_pad=pad, min_quantity=min_quantity, price_range=price_range)

    def best_of(offers: List[Offer], by_price: bool) -> Optional[Offer]:
        pool = [o for o in offers if not o.is_carrier]
        if not pool:
            return None
        return min(pool, key=(lambda o: _better_price(side, o)) if by_price else (lambda o: (o.distance_ly, _better_price(side, o))))

    def search_for(max_distance: Optional[float], sort_by: str, by_price: bool, price_range: Optional[tuple] = None) -> Optional[Pick]:
        """The qualifying station for one pick: with enough in stock if any has it, else with whatever is there (and the note says how much)."""
        if cancelled():
            return None
        found = run(max_distance, sort_by, stations, max(1, wanted), price_range)
        offer = best_of(_offers(found, wanted, side, ship_pad, include_ground, False), by_price)
        if offer is not None:
            return Pick("", offer)
        if wanted > 1 and not cancelled():
            found = run(max_distance, sort_by, stations, 1, price_range)
            offer = best_of(_offers(found, wanted, side, ship_pad, include_ground, False), by_price)
            if offer is not None:
                held = f"only {offer.demand:,} t in stock" if side == BUY else f"only {offer.demand:,} t wanted"
                return Pick("", offer, held)
        return None

    def keep(kind: str, pick: Optional[Pick]) -> None:
        if pick is not None:
            result.picks[kind] = Pick(kind, pick.offer, pick.note)

    keep(CHEAPEST, search_for(None, "price", True))
    keep(LOCAL, search_for(radius_ly, "price", True))
    keep(CLOSEST, search_for(None, "distance", False))
    cheapest = result.picks.get(CHEAPEST)
    if cheapest is not None:
        low, high = _band(side, cheapest.offer.price, tolerance)
        keep(RECOMMENDED, search_for(None, "distance", False, (low, high)))
        recommended = result.picks.get(RECOMMENDED)
        if recommended is not None and recommended.offer.station == cheapest.offer.station and recommended.offer.system == cheapest.offer.system:
            result.picks[RECOMMENDED] = Pick(RECOMMENDED, recommended.offer, _join(recommended.note, "also the cheapest"))
    if include_carriers and cheapest is not None and not cancelled():
        carrier_found = run(None, "price", trade_prices.CARRIER_TYPES, max(1, wanted))
        carriers = _offers(carrier_found, wanted, side, ship_pad, include_ground, True)
        carriers = [o for o in carriers if o.is_carrier]
        if carriers:
            best_carrier = min(carriers, key=lambda o: _better_price(side, o))
            note = trade_prices.carrier_note([cheapest.offer], [best_carrier], side)
            if note:
                result.notes.append(f"{note} {best_carrier.station} ({best_carrier.system}), {best_carrier.distance_ly:.0f} ly.")
    _mark_same(result)
    if not result.picks:
        result.notes.append("Spansh found no station with it in stock that your ship can dock at." if side == BUY
                            else "Spansh found no station that wants it that your ship can dock at.")
    return result


def _join(first: str, second: str) -> str:
    return f"{first}; {second}" if first else second


def _mark_same(picks: Picks) -> None:
    """Say when one station is two picks, so the list does not read as four different places."""
    owner: Dict[tuple, str] = {}
    for kind in KINDS:
        pick = picks.picks.get(kind)
        if pick is None:
            continue
        key = (pick.offer.station.casefold(), pick.offer.system.casefold())
        if key in owner and "also" not in pick.note:
            picks.picks[kind] = Pick(kind, pick.offer, _join(pick.note, f"same as {picks.label(owner[key])}"))
        else:
            owner.setdefault(key, kind)
