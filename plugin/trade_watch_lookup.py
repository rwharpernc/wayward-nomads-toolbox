"""The watch list's Spansh refresh: for each watched commodity, the cheapest stations to buy it at and the dearest to sell it at (up to five of each), near
a system. Nothing here touches Tk, and the search is passed in, so the shaping is tested without a connection.

What is sent to Spansh: the commodity names and the system name the search is measured from (the same station search the Trade
Market page and the Mining Price Finder use). Nothing about the commander. It runs only when the commander presses Refresh, with
Trade's lookups switched on. Fleet carriers are left out: their markets are volatile and they move. A pause between requests keeps a
long list from going out as a burst, and a refresh can be cancelled between requests."""
from __future__ import annotations

import threading
import time
from datetime import datetime, timezone
from typing import Callable, Dict, List, Optional, Sequence, Tuple

from . import trade_prices
from .mining_spansh_client import StationPrice, search_best_price_stations
from .trade_watch_data import SPANSH, Lookup, Quote

DEFAULT_RADIUS_LY = 100
PAUSE_S = 0.4          # between two requests to Spansh
RESULTS = 5            # stations asked for per search, and kept: if one runs short of stock there are others beside it
MAX_AGE_DAYS = 7       # a market Spansh last heard of longer ago than this is probably out of date

SearchFn = Callable[..., List[StationPrice]]


def _quote(item: StationPrice, when: str) -> Quote:
    return Quote(int(item.price), int(item.quantity), item.station, item.system, SPANSH, when, float(item.distance_ly))


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def refresh(commodities: Sequence[str], reference: str, radius_ly: Optional[float] = DEFAULT_RADIUS_LY, *,
            search: SearchFn = search_best_price_stations, sleep: Callable[[float], None] = time.sleep,
            now: Callable[[], str] = _now, cancel: Optional[threading.Event] = None,
            ) -> Tuple[Dict[str, Lookup], List[str]]:
    """({commodity: its best prices}, [messages for the ones that failed]). A failed search leaves that commodity out and goes on to the
    next, so one bad answer does not lose the rest; if every search fails, the messages say so. Cancelled, it returns what it has."""
    found: Dict[str, Lookup] = {}
    problems: List[str] = []
    stations = trade_prices.station_types()
    first = True
    for name in commodities:
        if cancel is not None and cancel.is_set():
            break
        sides: Dict[str, Tuple[Quote, ...]] = {}
        failed = False
        for transaction in ("Buy", "Sell"):
            if not first:
                sleep(PAUSE_S)
            first = False
            try:
                results = search(reference, name, transaction, radius_ly, max_results=RESULTS,
                                 market_days_old=MAX_AGE_DAYS, station_types=stations)
            except Exception as err:   # a network or parse failure; Spansh's answer is not a promise
                problems.append(f"{name}: {err}")
                failed = True
                break
            stamp = now()
            sides[transaction] = tuple(_quote(item, stamp) for item in results[:RESULTS])
        if not failed:
            found[name] = Lookup(sides.get("Buy", ()), sides.get("Sell", ()), reference, now())
    return found, problems
