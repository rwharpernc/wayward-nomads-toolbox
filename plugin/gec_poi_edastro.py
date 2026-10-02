"""
On-demand lookup against edastro.com's (Elite Dangerous Astrometrics) GEC
(Galactic Exploration Catalog) API to find the nearest catalogued point of
interest to a given galactic coordinate - see docs/ATTRIBUTIONS.md.

Confirmed via a live call: `GET /gec/json/nearest/0/0/0` (Sol's own StarPos)
returned a single JSON object (not a list) with `name`, `type`/`type2`,
`region`, `coordinates` ([x, y, z]), `summary`, `rating`, `poiUrl`, and a
`distance` field that came back `null` for a coordinate-based query (only
populated for edastro's own name-based queries) - so this module computes
straight-line distance itself from `coordinates` vs. the query point,
matching organic_region_data.py's own straight-line-distance convention.

Same raise-on-failure calling convention as elw_rarity_spansh.py/
mining_spansh_client.py, not edsm_client.py's null-return one - callers run
this off the Tk main thread and catch exceptions themselves.
"""

from __future__ import annotations

import json
import math
import urllib.request
from dataclasses import dataclass
from typing import Optional

NEAREST_POI_URL = "https://edastro.com/gec/json/nearest/{x}/{y}/{z}"
NEAREST_POI_URL_RATED = "https://edastro.com/gec/json/nearest/{x}/{y}/{z}/{min_rating}"
REQUEST_TIMEOUT_S = 20
_USER_AGENT = "WNTB-gec-poi-edastro"


@dataclass(frozen=True)
class NearestPoi:
    name: str
    category: str
    region: str
    distance_ly: float
    rating: Optional[float]
    url: Optional[str]


def find_nearest_poi(x: float, y: float, z: float, min_rating: Optional[float] = None) -> NearestPoi:
    """Returns the nearest GEC point of interest to (x, y, z). Raises on any
    network/parse failure or when nothing is found (edastro returns an empty
    body in that case) - synchronous, blocking call."""
    if min_rating is not None:
        url = NEAREST_POI_URL_RATED.format(x=x, y=y, z=z, min_rating=min_rating)
    else:
        url = NEAREST_POI_URL.format(x=x, y=y, z=z)

    request = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
    with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT_S) as response:
        raw = response.read().decode("utf-8").strip()

    if not raw:
        raise ValueError("edastro GEC nearest-POI lookup returned no results")

    data = json.loads(raw)
    if isinstance(data, list):
        if not data:
            raise ValueError("edastro GEC nearest-POI lookup returned no results")
        data = data[0]
    if not isinstance(data, dict):
        raise ValueError(f"Unexpected edastro GEC nearest-POI response shape: {data!r}")

    name = data.get("name")
    coordinates = data.get("coordinates")
    if not isinstance(name, str) or not (isinstance(coordinates, list) and len(coordinates) == 3):
        raise ValueError(f"Unexpected edastro GEC nearest-POI response shape: {data!r}")

    poi_x, poi_y, poi_z = coordinates
    distance_ly = math.sqrt((poi_x - x) ** 2 + (poi_y - y) ** 2 + (poi_z - z) ** 2)

    category = data.get("type") or data.get("type2") or "Unknown"
    region = data.get("region") or "Unknown region"
    rating = data.get("rating")
    rating_value = rating if isinstance(rating, (int, float)) else None
    url_value = data.get("poiUrl")

    return NearestPoi(
        name=name, category=category, region=region, distance_ly=distance_ly,
        rating=rating_value, url=url_value if isinstance(url_value, str) else None,
    )
