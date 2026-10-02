"""
Opt-in lookup against Spansh's (https://spansh.co.uk) systems typeahead API,
used by Region Sweep to discover which real systems Spansh already knows
about within a given cube — so a queued cube's completion can be tracked
against systems nobody in this session has personally visited yet.

Spansh doesn't publish this endpoint's request/response shape (same
situation mining_spansh_client.py documents for the bodies/stations search
endpoints it wraps). Confirmed empirically via a live call:

    GET https://spansh.co.uk/api/systems?q=<prefix>

returns a plain JSON array of full system-name strings whose name starts
with `<prefix>` (case-sensitive literal prefix match, not a fuzzy search) -
e.g. `?q=Outotz%20LS-K` returned ["Outotz LS-K b50-0", "Outotz LS-K b8-0",
"Outotz LS-K c8-0", ...]. This is the same typeahead endpoint Spansh's own
systems-search page uses. It appears to cap results around 10 - callers
should treat what comes back as "some of what's known", not an exhaustive
catalog of the cube. If Spansh ever changes this endpoint's shape, this is
the one place to fix.

Unlike edsm_client.py's "never raises, degrades to an empty result"
convention, and matching mining_spansh_client.py's own documented choice:
this raises on any network/parse failure - callers must run it off the Tk
main thread and catch exceptions themselves.
"""

from __future__ import annotations

import json
import urllib.parse
import urllib.request

SYSTEMS_SEARCH_URL = "https://spansh.co.uk/api/systems"
REQUEST_TIMEOUT_S = 20
_USER_AGENT = "WNTB-region-sweep-spansh"


def search_boxel_systems(sector: str, cube_id: str, mass_code: str = "") -> list[str]:
    """
    Queries Spansh for known system names starting with "<sector> <cube_id>"
    (optionally narrowed further to "<sector> <cube_id> <mass_code>" when
    `mass_code` is given). Raises on any network/parse failure - synchronous,
    blocking call, same calling convention as mining_spansh_client.py's
    search functions.
    """
    prefix = f"{sector} {cube_id}"
    if mass_code:
        prefix = f"{prefix} {mass_code}"
    query = urllib.parse.urlencode({"q": prefix})
    request = urllib.request.Request(
        f"{SYSTEMS_SEARCH_URL}?{query}",
        headers={"User-Agent": _USER_AGENT},
        method="GET",
    )
    with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT_S) as response:
        data = json.loads(response.read().decode("utf-8"))

    if not isinstance(data, list):
        raise ValueError(f"Unexpected Spansh systems-search response shape: {type(data)!r}")
    return [name for name in data if isinstance(name, str) and name.startswith(prefix)]
