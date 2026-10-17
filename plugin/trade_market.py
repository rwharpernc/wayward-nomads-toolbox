"""
Reading the docked station's market (`Market.json`, which the game rewrites when
you open the commodities screen) so Trade mode can value the cargo you carry.
The parsing is pure; only `read_market_file` touches the disk.

Names: Market.json items are `$gold_name;` and the cargo in EDMC's state is the
lowercase internal name (`gold`), so both are reduced to the same key by
`canonical_name`.
"""
from __future__ import annotations

import json
import os
import re
import time
from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional

_TOKEN = re.compile(r"^\$(.+?)_name;$", re.IGNORECASE)


def canonical_name(name: str) -> str:
    """'$Gold_Name;' / 'Gold' / 'gold' -> 'gold'; spaces dropped."""
    text = str(name or "").strip()
    match = _TOKEN.match(text)
    if match:
        text = match.group(1)
    return text.lower().replace(" ", "")


@dataclass
class MarketItem:
    name: str          # display name
    sell_price: int    # what the station pays you per tonne
    buy_price: int     # what the station charges you per tonne
    demand: int
    stock: int


def _int(value: Any) -> int:
    return int(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else 0


def parse_market(data: Any) -> Dict[str, MarketItem]:
    """Market.json -> {canonical name: MarketItem}. Anything malformed is skipped."""
    items: Dict[str, MarketItem] = {}
    if not isinstance(data, dict):
        return items
    for raw in data.get("Items") or []:
        if not isinstance(raw, dict) or not raw.get("Name"):
            continue
        key = canonical_name(raw["Name"])
        display = str(raw.get("Name_Localised") or key).strip()
        items[key] = MarketItem(
            name=display, sell_price=_int(raw.get("SellPrice")), buy_price=_int(raw.get("BuyPrice")),
            demand=_int(raw.get("Demand")), stock=_int(raw.get("Stock")),
        )
    return items


READ_ATTEMPTS = 5
READ_DELAY_S = 0.1
"""The game sometimes writes Market.json a moment after the journal's `Market` event, so a read made on the event can find the
file missing, half written, or still the previous station's. Up to READ_ATTEMPTS reads, READ_DELAY_S apart (at most 0.4 s of
waiting, and only when the first read was not good), before giving up."""


def _load(path: str) -> Optional[dict]:
    try:
        with open(path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) and isinstance(data.get("Items"), list) else None


def read_market_file(journal_dir: str, market_id: Any = None,
                     sleep: Callable[[float], None] = time.sleep) -> Dict[str, MarketItem]:
    """The market in Market.json, or {} when it cannot be read.

    With `market_id` (the journal `Market` event's MarketID) the file must be that market's; a file for another station,
    which is what is on disk until the game catches up, is waited out rather than returned. Without it any readable file
    counts, and an unreadable one is not waited for unless it exists but cannot be parsed yet."""
    path = os.path.join(journal_dir, "Market.json")
    for attempt in range(READ_ATTEMPTS):
        data = _load(path)
        if data is not None and (market_id is None or data.get("MarketID") == market_id):
            return parse_market(data)
        if market_id is None and data is None and not os.path.exists(path):
            return {}
        if attempt < READ_ATTEMPTS - 1:
            sleep(READ_DELAY_S)
    return {}


def cargo_value(cargo: Dict[str, int], market: Dict[str, MarketItem]) -> Optional[int]:
    """What this station would pay for the whole hold, counting only commodities
    it actually buys (a sell price above 0). None if it buys none of them."""
    total = 0
    matched = False
    for name, tonnes in cargo.items():
        item = market.get(canonical_name(name))
        if item and item.sell_price > 0 and tonnes > 0:
            total += item.sell_price * tonnes
            matched = True
    return total if matched else None


def sold_keys(market: Dict[str, MarketItem]) -> frozenset:
    """The commodities this station has for sale (some in stock and a price to buy at), by canonical name."""
    return frozenset(key for key, item in market.items() if item.stock > 0 and item.buy_price > 0)
