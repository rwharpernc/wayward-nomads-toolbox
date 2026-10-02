"""Rare-goods locator for Powerplay mode: nearest rare commodities to the
current system.

Rare-good origins never move, so the dataset (`rare_goods.json`: 141 rare
goods with origin system, station, pad size, cost, legality restrictions,
Powerplay eligibility, and baked-in EDSM coordinates / Inara id / Spansh
id64 - see docs/ATTRIBUTIONS.md) ships as a static file rather than being
queried live. Only the origin system's *controlling Power* is looked up
live (`powerplay_control_lookup.py`), because that changes weekly.

Deliberately has no EDMC imports so it can be unit-tested outside EDMC.
"""

from __future__ import annotations

import json
import logging
import math
import os
from typing import Any, Dict, List, Optional, Sequence, Tuple

logger = logging.getLogger(__name__)

_DATA_PATH = os.path.join(os.path.dirname(__file__), "rare_goods.json")

_cache: Optional[List[Dict[str, Any]]] = None


def _load() -> List[Dict[str, Any]]:
    global _cache
    if _cache is not None:
        return _cache
    try:
        with open(_DATA_PATH, "r", encoding="utf-8") as fh:
            _cache = json.load(fh)
    except (OSError, ValueError):
        logger.warning("Could not read %s", _DATA_PATH, exc_info=True)
        _cache = []
    return _cache


def dataset_size() -> int:
    return len(_load())


def _distance_ly(a: Sequence[float], b: Dict[str, float]) -> float:
    return math.sqrt((a[0] - b["x"]) ** 2 + (a[1] - b["y"]) ** 2 + (a[2] - b["z"]) ** 2)


def nearest(current_coords: Tuple[float, float, float], limit: int = 10) -> List[Dict[str, Any]]:
    """The `limit` nearest rare goods to `current_coords` (a StarPos-shaped
    (x, y, z) tuple), each entry annotated with `distance_ly`, nearest first."""
    annotated = [
        {**entry, "distance_ly": _distance_ly(current_coords, entry["coords"])} for entry in _load()
    ]
    annotated.sort(key=lambda e: e["distance_ly"])
    return annotated[:max(0, limit)]


def inara_commodity_url(inara_id: int) -> str:
    """Inara.cz page for the commodity with this numeric id. Inara's own
    name-search for commodities doesn't resolve to a specific item, so the
    ids baked into rare_goods.json (looked up once at authoring time) are
    used to link directly."""
    return f"https://inara.cz/elite/commodity/{inara_id}/"
