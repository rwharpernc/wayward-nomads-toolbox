"""
Opt-in lookup of the most profitable trade routes from where you are, via
Spansh's trade-route planner (https://spansh.co.uk/trade). A real outbound
network call, so Trade mode only makes it after you press the button, and only if
you turned the lookups on in Settings (same rule as Mining's Spansh finders).

The endpoint is undocumented; the shape below was worked out from live calls and
checked against real responses (2026-10-09):
- `POST /api/trade/route` with form fields -> `{"job": "<id>", "status": "queued"}`
- `GET /api/results/<id>` until `state == "completed"` (a small search took about
  80 s), then `result` is a list of hops. Each hop has `source` and `destination`
  (`system`, `station`, `distance_to_arrival`, `market_updated_at`), `distance`
  (ly), `commodities` (`name`, `amount`, `profit` per tonne, `total_profit`),
  `total_profit` and `cumulative_profit`.
If Spansh changes it, this is the one place to fix.

The search blocks while Spansh works, so callers run `search_routes` on a
background thread; pass a `threading.Event` as `cancel` to stop waiting.
"""
from __future__ import annotations

import json
import threading
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from . import http_identity

ROUTE_URL = "https://spansh.co.uk/api/trade/route"
RESULTS_URL = "https://spansh.co.uk/api/results/"
REQUEST_TIMEOUT_S = 20
POLL_INTERVAL_S = 5.0
MAX_WAIT_S = 240.0
_USER_AGENT = http_identity.user_agent("trade-routes")


class RouteSearchError(Exception):
    """Spansh refused the search, failed it, or took too long. The message is shown to the user."""


@dataclass
class Cargo:
    name: str
    tonnes: int
    profit_per_t: int
    total_profit: int


@dataclass
class Hop:
    source_system: str
    source_station: str
    source_ls: float
    dest_system: str
    dest_station: str
    dest_ls: float
    distance_ly: float
    cargo: List[Cargo] = field(default_factory=list)
    profit: int = 0
    market_updated_at: Optional[int] = None  # the older of the two markets, epoch seconds


@dataclass
class RouteQuery:
    system: str
    station: str
    capital: int
    cargo_capacity: int
    max_hops: int = 3
    max_hop_distance_ly: float = 30.0
    max_arrival_ls: int = 5000
    requires_large_pad: bool = False


def build_form(query: RouteQuery) -> Dict[str, str]:
    """The form fields Spansh expects. Numbers are sent as whole values it accepts."""
    return {
        "system": query.system,
        "station": query.station,
        "max_hops": str(max(1, int(query.max_hops))),
        "max_hop_distance": f"{max(1.0, float(query.max_hop_distance_ly)):g}",
        "starting_capital": str(max(0, int(query.capital))),
        "max_cargo": str(max(1, int(query.cargo_capacity))),
        "max_system_distance": str(max(1, int(query.max_arrival_ls))),
        "requires_large_pad": "1" if query.requires_large_pad else "0",
    }


def _num(value: Any, default: float = 0) -> float:
    return float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else default


def parse_hops(result: Any) -> List[Hop]:
    """Spansh's `result` list -> hops. A malformed hop is skipped rather than failing the whole route."""
    hops: List[Hop] = []
    for raw in result if isinstance(result, list) else []:
        try:
            source, dest = raw["source"], raw["destination"]
            cargo = [
                Cargo(str(c.get("name", "?")), int(_num(c.get("amount"))), int(_num(c.get("profit"))),
                      int(_num(c.get("total_profit"))))
                for c in raw.get("commodities") or [] if isinstance(c, dict)
            ]
            updated = [int(t) for t in (source.get("market_updated_at"), dest.get("market_updated_at"))
                       if isinstance(t, (int, float))]
            hops.append(Hop(
                source_system=str(source.get("system", "?")), source_station=str(source.get("station", "?")),
                source_ls=_num(source.get("distance_to_arrival")),
                dest_system=str(dest.get("system", "?")), dest_station=str(dest.get("station", "?")),
                dest_ls=_num(dest.get("distance_to_arrival")),
                distance_ly=_num(raw.get("distance")), cargo=cargo,
                profit=int(_num(raw.get("total_profit"))),
                market_updated_at=min(updated) if updated else None,
            ))
        except (KeyError, TypeError, AttributeError):
            continue
    return hops


def _request(url: str, data: Optional[bytes] = None) -> Dict[str, Any]:
    request = urllib.request.Request(url, data=data, headers={"User-Agent": _USER_AGENT},
                                     method="POST" if data is not None else "GET")
    with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT_S) as response:
        parsed = json.loads(response.read().decode("utf-8"))
    return parsed if isinstance(parsed, dict) else {}


def search_routes(query: RouteQuery, cancel: Optional[threading.Event] = None) -> List[Hop]:
    """Submit the search, wait for Spansh to finish it, return the hops (empty when
    no profitable route exists). Raises RouteSearchError, or a network error
    (OSError / ValueError) for the caller to log."""
    submitted = _request(ROUTE_URL, urllib.parse.urlencode(build_form(query)).encode("ascii"))
    job = submitted.get("job")
    if not job:
        raise RouteSearchError(str(submitted.get("error") or "Spansh did not accept the search."))
    deadline = time.monotonic() + MAX_WAIT_S
    while time.monotonic() < deadline:
        if cancel is not None and cancel.wait(POLL_INTERVAL_S):
            raise RouteSearchError("Search cancelled.")
        if cancel is None:
            time.sleep(POLL_INTERVAL_S)
        data = _request(RESULTS_URL + urllib.parse.quote(str(job)))
        state = data.get("state")
        if state == "completed":
            if data.get("status") not in (None, "ok"):
                raise RouteSearchError(str(data.get("error") or "Spansh could not plan a route."))
            return parse_hops(data.get("result"))
        if state in ("failed", "error"):
            raise RouteSearchError(str(data.get("error") or "Spansh could not plan a route."))
    raise RouteSearchError("Spansh took too long. Try fewer hops or a shorter jump range.")
