"""Finding a material trader: the closest stations that trade Raw, Manufactured or Encoded materials, found with Spansh's station search
(`mining_spansh_client.search_material_traders`, the same search family the Trade and Mining finders use). Nothing here touches Tk, and the search is
passed in, so the shaping, the cache and the ordering are tested without a connection.

What is sent to Spansh: the system the search is measured from and the trader type, once per press of the button. Nothing about the commander.
The same search asked again within two minutes is answered from memory. A material trader trades within one category (a Raw trader trades Raw
materials), so the type asked for is the category of the materials to trade.

Pads: the stations are listed with the largest landing pad Spansh reports, and the pad filter asks Spansh for stations with at least a medium or a
large pad. Fleet carriers do not host material traders, so none are listed."""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional, Tuple

from .mining_spansh_client import TRADER_TYPES, MaterialTrader, search_material_traders

PAD_ANY, PAD_MEDIUM, PAD_LARGE = "any", "medium", "large"
PAD_CHOICES = ((PAD_ANY, "Any size"), (PAD_MEDIUM, "Medium or larger"), (PAD_LARGE, "Large only"))
DEFAULT_RADIUS_LY = 100
RADIUS_CHOICES = (50, 100, 250, 500)    # light years; "no limit" is None
RESULTS = 10
CACHE_SECONDS = 120

SearchFn = Callable[..., List[MaterialTrader]]
_cache: Dict[tuple, Tuple[float, "Result"]] = {}


@dataclass(frozen=True)
class Trader:
    station: str
    system: str
    station_type: str        # Spansh's own name, e.g. "Coriolis Starport"
    is_planetary: bool
    distance_ly: float
    arrival_ls: float
    pad: str                 # the largest pad the station has: "Large", "Medium", "Small" or "?" when not given


@dataclass(frozen=True)
class Result:
    reference: str
    trader_type: str
    radius_ly: Optional[float]
    traders: Tuple[Trader, ...]


def largest_pad(item: MaterialTrader) -> str:
    if item.large_pads:
        return "Large"
    if item.medium_pads:
        return "Medium"
    if item.small_pads:
        return "Small"
    return "?"


def to_trader(item: MaterialTrader) -> Trader:
    return Trader(item.station, item.system, item.station_type, item.is_planetary, item.distance_ly, item.distance_to_arrival_ls, largest_pad(item))


def describe_place(trader: Trader) -> str:
    """`orbital Coriolis Starport, 1,234 ls` / `ground Planetary Outpost, 80 ls`: whether it is in space or on a surface, what it is and how far
    from the arrival star."""
    kind = (trader.station_type or "station").strip()
    return f"{'ground' if trader.is_planetary else 'orbital'} {kind}, {trader.arrival_ls:,.0f} ls"


def _key(reference: str, trader_type: str, radius_ly: Optional[float], pad: str) -> tuple:
    return (" ".join(reference.split()).casefold(), trader_type, radius_ly, pad)


def is_cached(reference: str, trader_type: str, radius_ly: Optional[float] = DEFAULT_RADIUS_LY, pad: str = PAD_ANY,
              now: Callable[[], float] = time.monotonic) -> bool:
    held = _cache.get(_key(reference, trader_type, radius_ly, pad))
    return held is not None and now() - held[0] < CACHE_SECONDS


def clear_cache() -> None:
    _cache.clear()


def find(reference: str, trader_type: str, radius_ly: Optional[float] = DEFAULT_RADIUS_LY, pad: str = PAD_ANY, *,
         search: SearchFn = search_material_traders, now: Callable[[], float] = time.monotonic) -> Result:
    """The closest traders of `trader_type` to `reference`, nearest first. Raises on a network failure (the caller shows it) and ValueError for
    a type or pad it does not know. An answer, never a failure, is remembered for two minutes."""
    reference = " ".join(str(reference or "").split())
    if not reference:
        raise ValueError("A system to search from is needed.")
    if trader_type not in TRADER_TYPES:
        raise ValueError("Pick Raw, Manufactured or Encoded.")
    if pad not in (PAD_ANY, PAD_MEDIUM, PAD_LARGE):
        raise ValueError("Unknown landing pad size.")
    key = _key(reference, trader_type, radius_ly, pad)
    held = _cache.get(key)
    if held is not None and now() - held[0] < CACHE_SECONDS:
        return held[1]
    found = search(reference, trader_type, radius_ly, RESULTS, None if pad == PAD_ANY else pad)
    result = Result(reference, trader_type, radius_ly, tuple(sorted((to_trader(i) for i in found), key=lambda t: t.distance_ly)))
    _cache[key] = (now(), result)
    return result
