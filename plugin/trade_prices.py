"""
Ranking sell offers for the load you are actually carrying (pure logic, no network).

Spansh sorts stations by price per tonne, but the best *price* is not always the
best *sale*: a station paying 95,000 cr/t that wants only 40 t is worth less to a
200 t hold than one paying 90,000 that wants 5,000 t. So each offer is valued for
your tonnage, `price * min(tonnes, demand)`, and ranked by that.

Fleet carriers often top the lists but can jump away, so they are kept apart from
stations (`split_carriers`) rather than mixed in, and can be left out in Settings.

Pads: stations your ship cannot dock at are dropped (trade_ship.fits). Spansh does not
say which pads a fleet carrier has, and carriers have all three sizes, so they always fit.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from . import trade_ship
from .mining_spansh_client import StationPrice


@dataclass
class Offer:
    station: str
    system: str
    station_type: str
    distance_ly: float
    arrival_ls: float
    price: int           # cr per tonne
    demand: int          # tonnes the station still wants
    sellable_t: int      # min(your tonnes, demand)
    revenue: int         # price * sellable_t
    is_carrier: bool


def is_carrier(station_type: str) -> bool:
    return "carrier" in (station_type or "").lower()


def rank_offers(results: List[StationPrice], tonnes: int, include_carriers: bool = True,
                ship_pad: Optional[str] = None) -> List[Offer]:
    """Value each station for `tonnes`, best total sale first (ties: nearer first).
    Stations that want none of it, or that have no pad your ship fits, are dropped."""
    offers: List[Offer] = []
    for item in results:
        carrier = is_carrier(item.station_type)
        if carrier and not include_carriers:
            continue
        if not carrier and not trade_ship.fits(ship_pad, item.small_pads, item.medium_pads, item.large_pads):
            continue
        sellable = min(max(0, tonnes), max(0, item.quantity))
        if sellable <= 0 or item.price <= 0:
            continue
        offers.append(Offer(
            station=item.station, system=item.system, station_type=item.station_type,
            distance_ly=item.distance_ly, arrival_ls=item.distance_to_arrival_ls,
            price=item.price, demand=item.quantity, sellable_t=sellable,
            revenue=item.price * sellable, is_carrier=carrier,
        ))
    offers.sort(key=lambda o: (-o.revenue, o.distance_ly))
    return offers


def split_carriers(offers: List[Offer]) -> tuple[List[Offer], List[Offer]]:
    """(stations, fleet carriers), each keeping the ranking order."""
    return [o for o in offers if not o.is_carrier], [o for o in offers if o.is_carrier]


def carrier_note(stations: List[Offer], carriers: List[Offer]) -> Optional[str]:
    """Says so when a fleet carrier would pay more than the best station, since that is the
    case where ignoring carriers costs you something. None otherwise."""
    if not carriers:
        return None
    if not stations:
        return "Only fleet carriers want it (they can move)."
    extra = carriers[0].revenue - stations[0].revenue
    if extra <= 0:
        return None
    return f"A fleet carrier pays {extra:,} cr more than the best station (it can move)."


def verdict(near: List[Offer], galaxy: List[Offer]) -> Optional[str]:
    """One line comparing the best nearby sale with the best anywhere (stations only; pass
    each list through split_carriers first). None until both searches have run."""
    if not near or not galaxy:
        return None
    best_near, best_galaxy = near[0], galaxy[0]
    extra = best_galaxy.revenue - best_near.revenue
    if extra <= 0:
        return f"Best overall is nearby: {best_near.station} ({best_near.system})."
    percent = extra / best_near.revenue * 100
    detour = max(0.0, best_galaxy.distance_ly - best_near.distance_ly)
    return (f"Best overall: {best_galaxy.station} ({best_galaxy.system}), {extra:,} cr "
            f"(+{percent:.0f}%) more than the best nearby, {detour:.0f} ly further.")
