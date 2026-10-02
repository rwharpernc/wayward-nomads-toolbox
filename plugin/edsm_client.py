"""
EDSM API client for spatial nearby-system queries.

Boxel Survey has no way to compute which boxel is actually spatially
adjacent to the current one without Frontier's id64 coordinate math, which
isn't derived. This module sidesteps that problem: it queries EDSM's
public `cube-systems` endpoint centered on the current system's real
StarPos (already present in every FSDJump/Location journal event) rather
than deriving anything from the procedural name string itself.

Deliberately minimal — this is a "nice to have" lookup used from a UI
button, not core walker logic, so every failure mode (no network, EDSM
down, bad response shape) degrades to an empty result rather than raising.

Shared across modes (Boxel Survey uses it for the "Find Nearby"/EDSM-
visited-skip flows; Mining mode reuses it too) rather than each mode
carrying its own copy.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional, Tuple

import requests

from config import appname, user_agent

plugin_name = os.path.basename(os.path.dirname(__file__))
logger = logging.getLogger(f"{appname}.{plugin_name}")

CUBE_SYSTEMS_URL = "https://www.edsm.net/api-v1/cube-systems"
SYSTEM_URL = "https://www.edsm.net/api-v1/system"
SYSTEMS_URL = "https://www.edsm.net/api-v1/systems"
BODIES_URL = "https://www.edsm.net/api-system-v1/bodies"
# EDSM rejects requests without a recognizable User-Agent (requests' default
# "python-requests/X.Y" gets a 403) — confirmed by hitting this exact 403
# during field testing, and by EDMC's own bundled edsm.py plugin setting
# this same config.user_agent on its session for the same reason.
REQUEST_HEADERS = {"User-Agent": user_agent}
# EDSM caps this endpoint's cube edge length at 200 ly. 100 is a middle
# ground: wide enough to usually catch a few procedural systems, narrow
# enough to keep the response small and the query fast.
DEFAULT_CUBE_SIZE = 100
REQUEST_TIMEOUT = 10  # seconds


def nearby_systems(x: float, y: float, z: float, size: int = DEFAULT_CUBE_SIZE) -> List[Dict[str, Any]]:
    """
    Query EDSM for known systems within a cube of the given edge length (ly)
    centered on (x, y, z). Returns [] on any network/parsing failure instead
    of raising — this must never be able to hang or crash the plugin.

    Each returned dict has at least "name", "distance" (ly from the query
    center), and "coords" ({"x", "y", "z"}), per EDSM's cube-systems shape.
    """
    params = {"x": x, "y": y, "z": z, "size": size, "showId": 1, "showCoordinates": 1}
    try:
        response = requests.get(
            CUBE_SYSTEMS_URL, params=params, headers=REQUEST_HEADERS, timeout=REQUEST_TIMEOUT
        )
        response.raise_for_status()
        data = response.json()
    except Exception:
        logger.exception("EDSM cube-systems lookup failed")
        return []
    if not isinstance(data, list):
        logger.warning("EDSM cube-systems returned unexpected shape: %r", type(data))
        return []
    return data


def system_known(name: str) -> Optional[bool]:
    """
    Query EDSM for whether `name` is a known system — i.e. visited/submitted
    by anyone, the "Tier 2" skip-filtering check.

    Returns True if EDSM has a record for it, False if EDSM's response is the
    empty shape it uses for "not found", or None if the lookup itself
    failed (network error, bad response, EDSM down). Callers must treat None
    as "couldn't determine" and NOT as "not visited" — a temporary EDSM
    outage must never cause a valid candidate to be silently withheld.

    EDSM's "not found" shape for this endpoint is an empty list (`[]`),
    confirmed via a live call — not the empty dict (`{}`) this function
    originally assumed, which meant every genuinely-unknown system used to
    fall through to the "couldn't determine" (`None`) branch below with a
    spurious logged warning. Fixed to recognize either empty shape as
    "not found" instead.
    """
    params = {"systemName": name, "showId": 1}
    try:
        response = requests.get(
            SYSTEM_URL, params=params, headers=REQUEST_HEADERS, timeout=REQUEST_TIMEOUT
        )
        response.raise_for_status()
        data = response.json()
    except Exception:
        logger.exception("EDSM system lookup failed for %r", name)
        return None
    if isinstance(data, (dict, list)) and not data:
        return False
    if isinstance(data, dict):
        return True
    logger.warning("EDSM system lookup returned unexpected shape: %r", type(data))
    return None


def system_bodies(system: str) -> Optional[List[Dict[str, Any]]]:
    """Queries EDSM's `api-system-v1/bodies` endpoint for `system` -
    Mining mode's ring reserve-level/composition lookup ("is this ring
    worth laser-mining, and how rich is it" without needing a DSS scan
    first). Confirmed directly against a live call to
    `.../bodies?systemName=Sol`: each ringed body carries `reserveLevel`
    (Pristine/Major/Common/Low/Depleted) and a `rings` list of
    {name, type} - `type` being the ring composition (Metallic/Metal
    Rich/Rocky/Icy), both attributes of the *body*, not each individual
    ring, since in-game reserve level and composition apply to a body's
    whole ring system. No API key needed - EDSM's system/body data is
    public.

    Returns the raw `bodies` list (a list of raw dicts, unfiltered - the
    caller decides which bodies actually have rings) on success, or
    `None` on any network/parsing failure - same "never raises, `None`
    means couldn't determine" convention as `system_known()`. Mining
    mode's own `mining_reserve_lookup_dialog.py` parses this raw shape
    into its own `BodyInfo`/`RingInfo` dataclasses; this function stays
    generic (no Mining-specific types) since it's shared infrastructure,
    not Mining-only API surface."""
    params = {"systemName": system}
    try:
        response = requests.get(
            BODIES_URL, params=params, headers=REQUEST_HEADERS, timeout=REQUEST_TIMEOUT
        )
        response.raise_for_status()
        data = response.json()
    except Exception:
        logger.exception("EDSM system-bodies lookup failed for %r", system)
        return None
    if not isinstance(data, dict):
        logger.warning("EDSM system-bodies lookup returned unexpected shape: %r", type(data))
        return None
    bodies = data.get("bodies")
    if not isinstance(bodies, list):
        return []
    return bodies


def system_fully_scanned(system: str) -> Optional[bool]:
    """Whether every body EDSM knows `system` to have has already been
    discovered/submitted by *someone* — Boxel Survey's "Tier 3" skip
    check (see `boxel_survey.py`'s module docstring): stronger than
    `system_known()`'s plain "visited by anyone", since a system can be
    visited (has a record) without every body in it having been found
    yet.

    Reuses the same `api-system-v1/bodies` endpoint as `system_bodies()`
    (kept as a separate function rather than built on top of that one,
    since the two have different failure semantics — this needs the
    response's own `bodyCount` field too, which `system_bodies()`
    deliberately discards). EDSM's own bodies response carries
    `bodyCount` (the system's total known body count) alongside the
    `bodies` list (bodies actually discovered/submitted so far) - "fully
    scanned" means the list is already as long as that count.

    Returns `True`/`False` once determined, or `None` when it can't be
    (network/parse failure, or EDSM has no `bodyCount` on file for this
    system yet) - same "`None` means couldn't determine, never treat as
    a confident answer" convention as `system_known()`. Callers must
    treat `None` as "keep the candidate", not "not fully scanned" - a
    temporary EDSM outage or a system EDSM hasn't indexed a body count
    for must never cause a valid candidate to be silently skipped."""
    params = {"systemName": system}
    try:
        response = requests.get(
            BODIES_URL, params=params, headers=REQUEST_HEADERS, timeout=REQUEST_TIMEOUT
        )
        response.raise_for_status()
        data = response.json()
    except Exception:
        logger.exception("EDSM fully-scanned lookup failed for %r", system)
        return None
    if not isinstance(data, dict):
        logger.warning("EDSM fully-scanned lookup returned unexpected shape: %r", type(data))
        return None
    body_count = data.get("bodyCount")
    if not isinstance(body_count, int) or body_count <= 0:
        return None
    bodies = data.get("bodies")
    if not isinstance(bodies, list):
        return None
    return len(bodies) >= body_count


def systems_coords(names: List[str]) -> Dict[str, Tuple[float, float, float]]:
    """Bulk-resolve real galactic (x, y, z) coordinates for `names` — used
    by Waypoint Route mode's nearest-neighbor reordering, which (unlike
    Sequence/Region Sweep) genuinely needs real distances between named
    systems and has no other source for them.

    One request for the whole list via EDSM's bulk `systems` endpoint
    (`?systemName[]=A&systemName[]=B&...&showCoordinates=1`), confirmed via
    a live call to return `[{"name": ..., "coords": {"x", "y", "z"}, ...}, ...]`
    - not one request per name. Same "never raises, returns whatever it
    could resolve" convention as `nearby_systems()`: on any network/parse
    failure, or for any name EDSM couldn't find, that name is simply absent
    from the returned dict rather than raising or returning a partial/
    placeholder value."""
    if not names:
        return {}
    params = [("systemName[]", name) for name in names]
    params.append(("showCoordinates", 1))
    try:
        response = requests.get(
            SYSTEMS_URL, params=params, headers=REQUEST_HEADERS, timeout=REQUEST_TIMEOUT
        )
        response.raise_for_status()
        data = response.json()
    except Exception:
        logger.exception("EDSM bulk systems-coords lookup failed for %d name(s)", len(names))
        return {}
    if not isinstance(data, list):
        logger.warning("EDSM systems lookup returned unexpected shape: %r", type(data))
        return {}

    resolved: Dict[str, Tuple[float, float, float]] = {}
    for entry in data:
        if not isinstance(entry, dict):
            continue
        name = entry.get("name")
        coords = entry.get("coords")
        if not name or not isinstance(coords, dict):
            continue
        try:
            resolved[name] = (float(coords["x"]), float(coords["y"]), float(coords["z"]))
        except (KeyError, TypeError, ValueError):
            continue
    return resolved
