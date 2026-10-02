"""
Opt-in lookup against Spansh's (https://spansh.co.uk) body-search API to
count how many Earthlike Worlds are already known within a given radius of
a reference system - the rarity signal exploration_value.py's "ELW rarity
comparison" readout uses (fewer known ELWs nearby = a rarer find).

Same endpoint (`POST /api/bodies/search`) and empirical-confirmation
approach as mining_spansh_client.py's search_ring_hotspots(), just filtered
by `subtype` instead of `ring_signals`. Confirmed via a live call:
`{"filters": {"subtype": {"value": ["Earth-like world"]}, "distance":
{"min": "0", "max": "50"}}, ..., "reference_system": "Sol"}` returned a
top-level "count" of 182 (every ELW Spansh knows within 50 ly of Sol) plus
per-body detail - only "count" is used here.

Raises on any network/parse failure - same calling convention as
mining_spansh_client.py/region_sweep_spansh.py, not edsm_client.py's
null-return one.
"""

from __future__ import annotations

import json
import urllib.request

BODIES_SEARCH_URL = "https://spansh.co.uk/api/bodies/search"
REQUEST_TIMEOUT_S = 20
_USER_AGENT = "WNTB-elw-rarity-spansh"

# How far "nearby" means for the rarity comparison. Not user-configurable
# (matches edsm_client.py's own DEFAULT_CUBE_SIZE precedent) - wide enough
# to be a meaningful neighborhood, narrow enough to keep the query fast.
DEFAULT_RADIUS_LY = 250.0


def count_nearby_earthlike_worlds(reference_system: str, radius_ly: float = DEFAULT_RADIUS_LY) -> int:
    """Returns the count of Earthlike Worlds Spansh already knows about
    within `radius_ly` of `reference_system`. Raises on any network/parse
    failure - synchronous, blocking call, callers must run it off the Tk
    main thread and catch exceptions themselves."""
    request_body = {
        "filters": {
            "subtype": {"value": ["Earth-like world"]},
            "distance": {"min": "0", "max": str(radius_ly)},
        },
        "sort": [{"distance": {"direction": "asc"}}],
        "size": 1,
        "page": 0,
        "reference_system": reference_system,
    }
    request = urllib.request.Request(
        BODIES_SEARCH_URL,
        data=json.dumps(request_body).encode("utf8"),
        headers={"User-Agent": _USER_AGENT, "Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT_S) as response:
        data = json.loads(response.read().decode("utf-8"))

    count = data.get("count")
    if not isinstance(count, int):
        raise ValueError(f"Unexpected Spansh bodies-search response shape: {data!r}")
    return count
