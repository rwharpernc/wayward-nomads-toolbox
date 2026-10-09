"""
The commodity list behind Trade mode's search box (pure logic, no UI, no network).

Data is `trade_commodities_data.py`, generated from FDevIDs. Two jobs:

- `resolve(text)`: turn whatever was typed or came from the journal into the name Spansh's
  market search expects. The journal says "Void Opals" and the cargo list says
  `lowtemperaturediamond`; Spansh only knows "Void Opal" and "Low Temperature Diamonds"
  (a plural mismatch finds nothing), so every search goes through here.
- `suggest(text, preferred)`: the type-ahead list. Names you carry or that the station you are
  at buys come first, then names that start with what you typed, then names containing it.

Salvage (black boxes, relics, ...) is sellable but rarely searched for, so it is kept out of the
suggestions; it still resolves if typed or carried.
"""
from __future__ import annotations

import re
from typing import Dict, Iterable, List, Optional

from .trade_commodities_data import COMMODITY_ROWS

SALVAGE = "Salvage"


def _norm(text: str) -> str:
    return re.sub(r"[^a-z0-9]", "", str(text or "").lower())


def _stem(key: str) -> str:
    """Drop a trailing 's' so 'void opals' meets 'void opal' ('glass'-like words keep their s)."""
    return key[:-1] if key.endswith("s") and not key.endswith("ss") else key


_BY_NAME: Dict[str, str] = {}      # normalised display name -> display name
_BY_SYMBOL: Dict[str, str] = {}    # normalised symbol -> display name
_BY_STEM: Dict[str, str] = {}      # stemmed display name -> display name
for _symbol, _name, _category in COMMODITY_ROWS:
    _BY_NAME[_norm(_name)] = _name
    _BY_SYMBOL[_norm(_symbol)] = _name
    _BY_STEM[_stem(_norm(_name))] = _name

SUGGESTIBLE: List[str] = sorted(
    (name for _symbol, name, category in COMMODITY_ROWS if category != SALVAGE), key=str.lower)
"""Every commodity a market can buy, A to Z, without Salvage."""


def resolve(text: Optional[str]) -> Optional[str]:
    """The Spansh/game name for typed or journal text, or None if it is not a known commodity.
    Matches ignoring case, spaces and punctuation, the internal symbol, and a plural/singular slip."""
    key = _norm(text or "")
    if not key:
        return None
    return _BY_NAME.get(key) or _BY_SYMBOL.get(key) or _BY_STEM.get(_stem(key))


def suggest(text: str, preferred: Iterable[str] = (), limit: int = 8) -> List[str]:
    """Names to offer for what has been typed so far, best first, at most `limit`.
    `preferred` (cargo, then what the station buys) leads each group; empty text lists just those."""
    ordered_preferred: List[str] = []
    for item in preferred:
        name = resolve(item) or None
        if name and name not in ordered_preferred:
            ordered_preferred.append(name)
    key = _norm(text)
    if not key:
        return ordered_preferred[:limit]

    def starts(name: str) -> bool:
        return _norm(name).startswith(key) or any(w.lower().startswith(text.strip().lower())
                                                   for w in name.split())

    def contains(name: str) -> bool:
        return key in _norm(name)

    pool = list(dict.fromkeys(ordered_preferred + SUGGESTIBLE))
    first = [n for n in pool if _norm(n).startswith(key)]
    second = [n for n in pool if n not in first and starts(n)]
    third = [n for n in pool if n not in first and n not in second and contains(n)]
    # Within a group, carried / station-buys names keep their place at the front (pool is built that way).
    return (first + second + third)[:limit]
