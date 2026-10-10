"""
On-demand lookup against edastro.com's (Elite Dangerous Astrometrics) GEC
(Galactic Exploration Catalog) to find the nearest catalogued point of
interest to a given galactic coordinate - see docs/ATTRIBUTIONS.md.

How it works, and why: edastro's `GET /gec/json/nearest/<x>/<y>/<z>` endpoint does not use the position. A live check on
2026-10-10 got the same entry ("The Solar System", the same 42,312 bytes) for every coordinate tried (decimal and integer,
as a path or as query parameters) and for system names. The earlier note that it "worked" had only been checked at Sol's
own coordinates, where Sol is the right answer anyway, so it may never have honoured the position. The Find button
therefore always gave the same answer. `GET /gec/json/all` still works (652 entries, about 2 MB, each with its
`coordinates`), so this downloads that list once and works out the nearest entry itself: straight-line distance in
light years from the query point, matching organic_region_data.py's convention. The list is kept in memory for
CACHE_SECONDS, so pressing Find repeatedly costs one request, and only when the button is pressed.

Same raise-on-failure calling convention as elw_rarity_spansh.py/mining_spansh_client.py, not edsm_client.py's
null-return one - callers run this off the Tk main thread and catch exceptions themselves.
"""

from __future__ import annotations

import json
import math
import threading
import time
import urllib.request
from dataclasses import dataclass
from typing import List, Optional, Tuple

from . import http_identity

ALL_POI_URL = "https://edastro.com/gec/json/all"
REQUEST_TIMEOUT_S = 60   # the list is about 2 MB
CACHE_SECONDS = 6 * 3600
_USER_AGENT = http_identity.user_agent("gec-poi")


@dataclass(frozen=True)
class NearestPoi:
    name: str
    category: str
    region: str
    distance_ly: float
    rating: Optional[float]
    url: Optional[str]
    system: str = ""   # the system to search for in the galaxy map (edastro's galMapSearch)


Entry = Tuple[float, float, float, NearestPoi]   # x, y, z and the POI (its distance is filled in per query)


_cache: Optional[Tuple[float, List[Entry]]] = None
_cache_lock = threading.Lock()


def parse_catalog(raw: str) -> List[Entry]:
    """The entries of edastro's `/gec/json/all` response that have a name and valid coordinates. Raises ValueError if the
    response isn't a non-empty list (so a changed or empty reply is an error, not a silent "nothing nearby")."""
    data = json.loads(raw)
    if not isinstance(data, list) or not data:
        raise ValueError("edastro GEC list is empty or not a list")
    entries: List[Entry] = []
    for item in data:
        if not isinstance(item, dict) or not isinstance(item.get("name"), str):
            continue
        coords = item.get("coordinates")
        if not (isinstance(coords, list) and len(coords) == 3 and all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in coords)):
            continue
        rating = item.get("rating")
        url = item.get("poiUrl")
        search = item.get("galMapSearch")
        poi = NearestPoi(
            name=item["name"], category=item.get("type") or item.get("type2") or "Unknown",
            region=item.get("region") or "Unknown region", distance_ly=0.0,
            rating=float(rating) if isinstance(rating, (int, float)) and not isinstance(rating, bool) else None,
            url=url if isinstance(url, str) and url else None, system=search if isinstance(search, str) else "")
        entries.append((float(coords[0]), float(coords[1]), float(coords[2]), poi))
    if not entries:
        raise ValueError("edastro GEC list has no usable entries")
    return entries


def nearest_in(entries: List[Entry], x: float, y: float, z: float, min_rating: Optional[float] = None) -> NearestPoi:
    """The entry closest to (x, y, z) (optionally only those rated at least `min_rating`), with its distance in light
    years. Raises ValueError when nothing qualifies."""
    best: Optional[Entry] = None
    best_sq = math.inf
    for entry in entries:
        poi = entry[3]
        if min_rating is not None and (poi.rating is None or poi.rating < min_rating):
            continue
        square = (entry[0] - x) ** 2 + (entry[1] - y) ** 2 + (entry[2] - z) ** 2
        if square < best_sq:
            best, best_sq = entry, square
    if best is None:
        raise ValueError("no GEC point of interest matches")
    poi = best[3]
    return NearestPoi(name=poi.name, category=poi.category, region=poi.region, distance_ly=math.sqrt(best_sq),
                      rating=poi.rating, url=poi.url, system=poi.system)


def _catalog() -> List[Entry]:
    """The list of points of interest: downloaded on first use, then kept for CACHE_SECONDS."""
    global _cache
    with _cache_lock:
        if _cache is not None and time.monotonic() - _cache[0] < CACHE_SECONDS:
            return _cache[1]
    request = urllib.request.Request(ALL_POI_URL, headers={"User-Agent": _USER_AGENT})
    with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT_S) as response:
        entries = parse_catalog(response.read().decode("utf-8"))
    with _cache_lock:
        _cache = (time.monotonic(), entries)
    return entries


def find_nearest_poi(x: float, y: float, z: float, min_rating: Optional[float] = None) -> NearestPoi:
    """The nearest GEC point of interest to (x, y, z). Raises on any network/parse failure or when nothing is found -
    synchronous and blocking (the first call downloads the list), so run it off the Tk main thread."""
    return nearest_in(_catalog(), x, y, z, min_rating)
