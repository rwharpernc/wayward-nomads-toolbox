"""
Ranking station offers for the load you are actually moving (pure logic, no network), for selling and for
buying.

Selling. Spansh sorts stations by price per tonne, but the best *price* is not always the best *sale*: a
station paying 95,000 cr/t that wants only 40 t is worth less to a 200 t hold than one paying 90,000 that
wants 5,000 t. So each offer is valued for your tonnage, `price * min(tonnes, demand)`, and ranked by that.

Buying. The goal is the lowest price, but a cheap station with 40 t in stock can't fill a 200 t hold. So
stations that can supply the whole amount come first (cheapest first), then those that can only supply part
(cheapest first), each marked with how many tonnes it has.

Fleet carriers often top the lists but can jump away, so they are kept apart from stations
(`split_carriers`) rather than mixed in, and can be left out in Settings.

Pads: stations your ship cannot dock at are dropped (trade_ship.fits). Spansh does not say which pads a fleet
carrier has, and carriers have all three sizes, so they always fit.

Where: each offer says whether the station is orbital or on the ground (Spansh's `is_planetary`), its type,
and its distance from the arrival star, so you can tell a Coriolis from a planetary outpost.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from . import trade_ship
from .mining_spansh_client import StationPrice

SELL = "sell"
BUY = "buy"


@dataclass
class Offer:
    station: str
    system: str
    station_type: str
    distance_ly: float
    arrival_ls: float
    price: int           # cr per tonne
    demand: int          # sell: tonnes the station still wants. buy: tonnes it has in stock
    sellable_t: int      # min(your tonnes, demand): what could actually change hands
    revenue: int         # price * sellable_t: what you would be paid (sell) or pay (buy)
    is_carrier: bool
    is_planetary: bool = False
    side: str = SELL


def is_carrier(station_type: str) -> bool:
    return "carrier" in (station_type or "").lower()


def describe_place(offer: Offer) -> str:
    """'orbital Coriolis Starport, 1,234 ls' / 'ground Planetary Outpost, 80 ls' / 'carrier'. Tells a station in
    space from one on a planet's surface, which matters for the trip and for what can land."""
    if offer.is_carrier:
        return "carrier"
    kind = (offer.station_type or "station").strip()
    return f"{'ground' if offer.is_planetary else 'orbital'} {kind}, {offer.arrival_ls:,.0f} ls"


def rank_offers(results: List[StationPrice], tonnes: int, include_carriers: bool = True,
                ship_pad: Optional[str] = None, side: str = SELL) -> List[Offer]:
    """Value each station for `tonnes` and rank them. Selling: best total sale first. Buying: stations that
    can supply all of it first, cheapest first, then partial ones, cheapest first. Ties: nearer first.
    Stations with none to buy/sell, or with no pad your ship fits, are dropped."""
    offers: List[Offer] = []
    for item in results:
        carrier = is_carrier(item.station_type)
        if carrier and not include_carriers:
            continue
        if not carrier and not trade_ship.fits(ship_pad, item.small_pads, item.medium_pads, item.large_pads):
            continue
        movable = min(max(0, tonnes), max(0, item.quantity))
        if movable <= 0 or item.price <= 0:
            continue
        offers.append(Offer(
            station=item.station, system=item.system, station_type=item.station_type,
            distance_ly=item.distance_ly, arrival_ls=item.distance_to_arrival_ls,
            price=item.price, demand=item.quantity, sellable_t=movable,
            revenue=item.price * movable, is_carrier=carrier, is_planetary=bool(item.is_planetary), side=side,
        ))
    if side == BUY:
        offers.sort(key=lambda o: (o.sellable_t < tonnes, o.price, o.distance_ly))
    else:
        offers.sort(key=lambda o: (-o.revenue, o.distance_ly))
    return offers


def split_carriers(offers: List[Offer]) -> tuple[List[Offer], List[Offer]]:
    """(stations, fleet carriers), each keeping the ranking order."""
    return [o for o in offers if not o.is_carrier], [o for o in offers if o.is_carrier]


def _better(side: str, candidate: Offer, reference: Offer) -> int:
    """How much better `candidate` is than `reference`, in credits for the amount involved (positive = better)."""
    if side == BUY:
        return (reference.price - candidate.price) * candidate.sellable_t
    return candidate.revenue - reference.revenue


def carrier_note(stations: List[Offer], carriers: List[Offer], side: str = SELL) -> Optional[str]:
    """Says so when a fleet carrier would beat the best station (pay more when selling, charge less when
    buying), since that is the case where ignoring carriers costs you something. None otherwise."""
    if not carriers:
        return None
    if not stations:
        return "Only fleet carriers have it (they can move)." if side == BUY else "Only fleet carriers want it (they can move)."
    extra = _better(side, carriers[0], stations[0])
    if extra <= 0:
        return None
    if side == BUY:
        return f"A fleet carrier is {stations[0].price - carriers[0].price:,} cr/t cheaper than the best station (it can move)."
    return f"A fleet carrier pays {extra:,} cr more than the best station (it can move)."


def verdict(near: List[Offer], galaxy: List[Offer], side: str = SELL) -> Optional[str]:
    """One line comparing the best nearby offer with the best anywhere (stations only; pass each list through
    split_carriers first). None until both searches have run."""
    if not near or not galaxy:
        return None
    best_near, best_galaxy = near[0], galaxy[0]
    extra = _better(side, best_galaxy, best_near)
    if extra <= 0:
        return f"Best overall is nearby: {best_near.station} ({best_near.system})."
    detour = max(0.0, best_galaxy.distance_ly - best_near.distance_ly)
    if side == BUY:
        saved = best_near.price - best_galaxy.price
        percent = saved / best_near.price * 100
        return (f"Best overall: {best_galaxy.station} ({best_galaxy.system}), {saved:,} cr/t cheaper "
                f"(-{percent:.0f}%), about {extra:,} cr saved on {best_galaxy.sellable_t:,} t, {detour:.0f} ly further.")
    percent = extra / best_near.revenue * 100
    return (f"Best overall: {best_galaxy.station} ({best_galaxy.system}), {extra:,} cr "
            f"(+{percent:.0f}%) more than the best nearby, {detour:.0f} ly further.")
