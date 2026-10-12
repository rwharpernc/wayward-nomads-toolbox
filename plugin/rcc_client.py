"""
A thin read-only client for Raven Colonial's public API, for the Colonization window's "Planned Builds" view.

Raven Colonial is a community site where commanders plan the colonization of a system: which buildings go where, and which are
planned, being built or finished. The game's journal never reports a *planned* build, so this is the one place WNTB can show
them. It asks one question per press of the button: the plan for one system (`GET /api/v2/system/<name>`, which needs no key):
its architect, whether it is open, and its build sites. The journal stays the source of truth for your own deliveries; nothing is ever sent to Raven Colonial.

Pure parsing plus one network call (`fetch_sites`) whose opener is passed in, so the shaping and the error handling are tested
without a connection. The request carries WNTB's User-Agent (http_identity), has a timeout, reads a bounded amount, and an answer
is remembered for a minute so pressing the button again does not ask again.
"""
from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Tuple

from . import http_identity

BASE_URL = "https://ravencolonial100-awcbdvabgze4c5cq.canadacentral-01.azurewebsites.net"
SYSTEM_PATH = "/api/v2/system/{system}"
TIMEOUT_S = 15
MAX_BYTES = 2_000_000           # a system's answer is a few tens of kilobytes; anything this large is not one
CACHE_SECONDS = 60              # the same system asked again within this long is answered from memory
MAX_SITES = 500                 # sites kept from one answer
NAME_MAX = 60                   # a site's name is clipped to this (it is text from outside)

STATUS_BUILDING, STATUS_PLANNED, STATUS_COMPLETE, STATUS_DEMOLISH = "build", "plan", "complete", "demolish"
STATUS_ORDER = (STATUS_BUILDING, STATUS_PLANNED, STATUS_COMPLETE, STATUS_DEMOLISH)
STATUS_LABELS = {STATUS_BUILDING: "Building", STATUS_PLANNED: "Planned", STATUS_COMPLETE: "Complete", STATUS_DEMOLISH: "Demolish"}


class RccError(Exception):
    """The lookup failed in a way worth telling the commander about (the message is written to be shown)."""


@dataclass(frozen=True)
class RccSite:
    name: str
    status: str                  # one of STATUS_ORDER, or "" when Raven Colonial gave one we do not know
    build_type: str              # the raw type key, e.g. "dual_truss"
    body_num: Optional[int]
    market_id: Optional[int]     # set once the site exists in the game; None while only planned

    @property
    def type_label(self) -> str:
        return build_type_label(self.build_type)

    @property
    def status_label(self) -> str:
        return STATUS_LABELS.get(self.status, self.status.title() or "Unknown")


def build_type_label(raw: Any) -> str:
    """'dual_truss' -> 'Dual truss'. Empty for nothing."""
    text = str(raw or "").strip().replace("_", " ")
    return (text[:1].upper() + text[1:]) if text else ""


def _int(value: Any) -> Optional[int]:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.strip().lstrip("-").isdigit():
        return int(value)
    return None


def parse_sites(data: Any) -> List[RccSite]:
    """The sites in an answer (a list of `{name, status, buildType, bodyNum, marketId, ...}`), in the order worth showing: building,
    planned, complete, then the rest, each by name. Anything malformed is skipped."""
    if not isinstance(data, list):
        return []
    sites: List[RccSite] = []
    for raw in data[:MAX_SITES]:
        if not isinstance(raw, dict):
            continue
        name = str(raw.get("name") or "").strip()
        if not name:
            continue
        status = str(raw.get("status") or "").strip().lower()
        sites.append(RccSite(
            name=name if len(name) <= NAME_MAX else name[:NAME_MAX - 1] + "…",
            status=status if status in STATUS_ORDER else "",
            build_type=str(raw.get("buildType") or "").strip(),
            body_num=_int(raw.get("bodyNum")),
            market_id=_int(raw.get("marketId"))))
    order = {status: index for index, status in enumerate(STATUS_ORDER)}
    return sorted(sites, key=lambda s: (order.get(s.status, len(order)), s.name.casefold()))


@dataclass(frozen=True)
class RccSystem:
    """What Raven Colonial holds for one system."""
    name: str
    architect: str               # the commander who plans it there ("" when none is given)
    is_open: Optional[bool]      # whether it is open (anyone may edit) or locked to its architect; None when not stated
    sites: List[RccSite]

    @property
    def access_label(self) -> str:
        return {True: "Open", False: "Locked"}.get(self.is_open, "")


def parse_system(data: Any, fallback_name: str = "") -> RccSystem:
    """The system in an answer (`{name, architect, open, sites: [...]}`). Anything missing is left empty."""
    if not isinstance(data, dict):
        return RccSystem(fallback_name, "", None, [])
    is_open = data.get("open")
    return RccSystem(
        name=str(data.get("name") or fallback_name).strip()[:NAME_MAX],
        architect=str(data.get("architect") or "").strip()[:NAME_MAX],
        is_open=is_open if isinstance(is_open, bool) else None,
        sites=parse_sites(data.get("sites")))


def count_by_status(sites: List[RccSite]) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for site in sites:
        counts[site.status] = counts.get(site.status, 0) + 1
    return counts


def summary_text(sites: List[RccSite]) -> str:
    """'2 building · 3 planned · 9 complete' (empty for no sites)."""
    counts = count_by_status(sites)
    parts = [f"{counts[s]:,} {STATUS_LABELS[s].lower()}" for s in STATUS_ORDER if counts.get(s)]
    if counts.get(""):
        parts.append(f"{counts['']:,} other")
    return " · ".join(parts)


_cache: Dict[str, Tuple[float, RccSystem]] = {}


def clear_cache() -> None:
    _cache.clear()


def system_url(system: str) -> str:
    return BASE_URL + SYSTEM_PATH.format(system=urllib.parse.quote(system.strip(), safe=""))


def fetch_system(system: str, opener: Callable[..., Any] = urllib.request.urlopen,
                 now: Callable[[], float] = time.monotonic) -> RccSystem:
    """The plan Raven Colonial holds for `system`. Raises RccError with a message to show; a system it has no record of gives one
    with no sites. Network access is `opener` (urlopen's shape), so tests need no connection."""
    system = (system or "").strip()
    if not system:
        raise RccError("This site has no system name yet; dock at it once so WNTB knows where it is.")
    key = system.casefold()
    cached = _cache.get(key)
    if cached is not None and now() - cached[0] < CACHE_SECONDS:
        return cached[1]
    request = urllib.request.Request(system_url(system), headers={"User-Agent": http_identity.user_agent("rcc-system")})
    try:
        with opener(request, timeout=TIMEOUT_S) as response:
            body = response.read(MAX_BYTES + 1)
    except urllib.error.HTTPError as err:
        if err.code == 404:
            empty = RccSystem(system, "", None, [])
            _cache[key] = (now(), empty)
            return empty
        raise RccError(f"Raven Colonial answered with an error ({err.code}). Try again later.") from err
    except (urllib.error.URLError, OSError, TimeoutError) as err:
        raise RccError("Could not reach Raven Colonial. Check your connection and try again.") from err
    if len(body) > MAX_BYTES:
        raise RccError("Raven Colonial sent more than expected, so it was ignored.")
    try:
        data = json.loads(body.decode("utf-8"))
    except (ValueError, UnicodeDecodeError) as err:
        raise RccError("Raven Colonial sent something WNTB could not read.") from err
    result = parse_system(data, system)
    _cache[key] = (now(), result)     # a failure raised above, so it is never remembered
    return result
