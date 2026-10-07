"""
On-demand lookup against Spansh's (https://spansh.co.uk) body-search API to
find the nearest neutron star that is its system's *primary* (main) star -
the "Neutron" button in Exploration mode's panel, next to Discovery Alerts.
Useful for neutron-boost plotting: a neutron star that is only a secondary
companion isn't what you want to jump to, so the search is restricted to
`is_main_star`.

Spansh doesn't publish this endpoint's request shape. The shape below was
worked out from live `POST /api/bodies/search` calls and checked against
real responses (same approach as mining_spansh_client.py): `subtype`
"Neutron Star" plus `is_main_star` true, sorted by distance ascending, with
the search origin given as `reference_coords` (the journal's StarPos) -
confirmed to return the same distances as a `reference_system` of "Sol" for
(0, 0, 0). Coordinates rather than a system name so this works from a
system Spansh has never seen. If Spansh changes this endpoint, this is the
one place to fix.

Same raise-on-failure calling convention as mining_spansh_client.py and
gec_poi_edastro.py: a synchronous, blocking network call that callers must
run off the Tk main thread, catching exceptions themselves.
"""

from __future__ import annotations

import json
import urllib.request
from dataclasses import dataclass
from typing import Optional

from . import http_identity

BODIES_SEARCH_URL = "https://spansh.co.uk/api/bodies/search"
REQUEST_TIMEOUT_S = 20
_USER_AGENT = http_identity.user_agent("neutron-finder")

_RESULT_COUNT = 2
"""Asked for two so the commander's own system can be skipped when they are
already sitting in a neutron system - the useful answer is then the next one."""

MAX_NAME_CHARS = 40
"""Hard cap on a system name shown in the main panel (see
`display_name`) - names come from an external API, and an EDMC main window
sizes itself to its widest row across every loaded plugin."""


@dataclass(frozen=True)
class NearestNeutron:
    system: str
    distance_ly: float
    region: str


def display_name(name: str) -> str:
    """`name` truncated to MAX_NAME_CHARS for the main panel."""
    if len(name) <= MAX_NAME_CHARS:
        return name
    return name[:MAX_NAME_CHARS - 1] + "…"


def find_nearest_neutron(x: float, y: float, z: float, current_system: Optional[str] = None) -> NearestNeutron:
    """The nearest system whose primary star is a neutron star, measured from
    galactic (x, y, z) in light years, skipping `current_system` (if given).
    Raises on any network/parse failure or when nothing is found."""
    request_body = {
        "filters": {
            "subtype": {"value": ["Neutron Star"]},
            "is_main_star": {"value": True},
        },
        "sort": [{"distance": {"direction": "asc"}}],
        "size": _RESULT_COUNT,
        "page": 0,
        "reference_coords": {"x": x, "y": y, "z": z},
    }
    request = urllib.request.Request(
        BODIES_SEARCH_URL,
        data=json.dumps(request_body).encode("utf8"),
        headers={"User-Agent": _USER_AGENT, "Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT_S) as response:
        data = json.loads(response.read().decode("utf-8"))

    return pick_nearest(data, current_system)


def pick_nearest(data: object, current_system: Optional[str]) -> NearestNeutron:
    """Picks the answer out of a bodies/search response; split from the network
    call so it can be tested against a canned response."""
    results = data.get("results") if isinstance(data, dict) else None
    if not isinstance(results, list):
        raise ValueError(f"Unexpected Spansh bodies/search response shape: {data!r}")

    skip = current_system.casefold() if current_system else None
    for body in results:
        if not isinstance(body, dict):
            continue
        system = body.get("system_name")
        distance = body.get("distance")
        if not isinstance(system, str) or not isinstance(distance, (int, float)):
            continue
        if skip is not None and system.casefold() == skip:
            continue
        region = body.get("system_region")
        return NearestNeutron(system, float(distance), region if isinstance(region, str) else "")
    raise ValueError("Spansh returned no neutron-star primary systems")
