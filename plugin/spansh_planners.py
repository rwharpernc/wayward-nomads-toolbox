"""
Opt-in route planners from Spansh that the Expedition window turns into an expedition: Road to Riches (the most valuable bodies to scan, and
optionally map, near a route) and Expressway to Exomastery (the most valuable biological signals near a route). A real outbound network call, so
it is made only after you press the button in the Expedition window, and it sends Spansh the system you start from (and the one you end at, if
you give one) with the numbers you chose, nothing else.

The endpoints are undocumented; the shapes below were taken from Spansh's own web page and checked against real responses (2026-10-13):
- `POST /api/riches/route` and `POST /api/exobiology/route` with form fields `from`, `to` (optional), `range` (jump range in ly), `radius` (ly
  around the route to look for bodies), `max_results`, `max_distance` (ls from the arrival star), `min_value`, `avoid_thargoids` and `loop`
  (0 or 1), and, for riches only, `use_mapping_value` -> `{"job": "<id>", "status": "queued"}`
- the neutron plotter, `POST /api/route` with form fields `from`, `to`, `range` (jump range in ly), `efficiency` (percent, Spansh starts at 60) and
  `supercharge_multiplier` (4 or 6) -> the same `{"job": ...}`; its `result` is a dict whose `system_jumps` lists the systems to jump to in order, each
  with `system`, `jumps` (jumps since the previous entry), `distance_jumped`, `distance_left`, `neutron_star` and `x`, `y`, `z`; the first entry is
  where you start with 0 jumps (checked live 2026-10-17: Sol to Colonia, 169 jumps in 170 entries)
- `GET /api/results/<id>` until `state == "completed"`; `result` is a list of systems in route order, each with `name`, `jumps`, `x`, `y`, `z`
  and `bodies`. A riches body has `name`, `subtype`, `is_terraformable`, `distance_to_arrival`, `estimated_scan_value` and
  `estimated_mapping_value`; an exobiology body has `name`, `subtype`, `distance_to_arrival`, `landmark_value` and `landmarks` (each with
  `subtype`, `type`, `count` and `value`). The first system is where you start and has no bodies.
If Spansh changes it, this is the one place to fix.

The search blocks while Spansh works, so callers run `plan` on a background thread; pass a `threading.Event` as `cancel` to stop waiting.
"""
from __future__ import annotations

import json
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Tuple

from . import http_identity
from .trade_spansh_client import RouteSearchError, describe_state

RICHES = "riches"
EXOBIOLOGY = "exobiology"
NEUTRON = "neutron"
KINDS = (RICHES, EXOBIOLOGY, NEUTRON)
TITLES = {RICHES: "Road to Riches", EXOBIOLOGY: "Expressway to Exomastery", NEUTRON: "Neutron Highway"}
URLS = {RICHES: "https://spansh.co.uk/api/riches/route", EXOBIOLOGY: "https://spansh.co.uk/api/exobiology/route",
        NEUTRON: "https://spansh.co.uk/api/route"}
RESULTS_URL = "https://spansh.co.uk/api/results/"
REQUEST_TIMEOUT_S = 20
POLL_INTERVAL_S = 5.0
MAX_WAIT_S = 300.0
_USER_AGENT = http_identity.user_agent("expedition-planner")

# What Spansh's own page starts with (a value is in credits; a distance in ly or ls).
DEFAULT_MIN_VALUE = {RICHES: 100_000, EXOBIOLOGY: 10_000_000}
DEFAULT_RADIUS_LY = 25
DEFAULT_MAX_RESULTS = 100
DEFAULT_MAX_ARRIVAL_LS = 50_000
DEFAULT_JUMP_RANGE_LY = 30.0
DEFAULT_EFFICIENCY = 60
SUPERCHARGE_CHOICES = (4, 6)

LIMITS = {"efficiency": (1, 100), "range": (1.0, 500.0), "radius": (1, 1000), "max_results": (1, 100), "max_distance": (1, 5_000_000)}
NOTE_CHARS = 480            # an expedition stop's note holds 500
BODIES_PER_NOTE = 3
SPECIES_PER_BODY = 2

XYZ = Tuple[float, float, float]


@dataclass
class PlanQuery:
    kind: str
    start: str
    jump_range: float = DEFAULT_JUMP_RANGE_LY
    destination: str = ""
    radius: int = DEFAULT_RADIUS_LY
    max_results: int = DEFAULT_MAX_RESULTS
    max_distance: int = DEFAULT_MAX_ARRIVAL_LS
    min_value: int = 0                  # 0 = Spansh's own starting value for that planner
    use_mapping_value: bool = False     # riches only: rank by what mapping pays, not only the first scan
    avoid_thargoids: bool = True
    loop: bool = False                  # return to the start; an expedition is usually one way
    efficiency: int = DEFAULT_EFFICIENCY    # neutron plotter only
    supercharge: int = 4                    # neutron plotter only: 4 normal, 6 overcharged


@dataclass(frozen=True)
class PlannedStop:
    system: str
    body: str = ""
    note: str = ""
    xyz: Optional[XYZ] = None


def _clamp(value: Any, name: str, default: float) -> float:
    low, high = LIMITS[name]
    try:
        number = float(value)
    except (TypeError, ValueError):
        number = default
    return max(low, min(high, number))


def build_form(query: PlanQuery) -> Dict[str, str]:
    """The form fields Spansh expects. Numbers are clamped to sensible limits and sent as the whole values it accepts."""
    if query.kind not in KINDS:
        raise RouteSearchError("Unknown planner.")
    start = " ".join(str(query.start or "").split())
    if not start:
        raise RouteSearchError("Give the system to start from.")
    if query.kind == NEUTRON:
        destination = " ".join(str(query.destination or "").split())
        if not destination:
            raise RouteSearchError("Give the system to end at.")
        return {"from": start, "to": destination,
                "range": f"{_clamp(query.jump_range, 'range', DEFAULT_JUMP_RANGE_LY):g}",
                "efficiency": str(int(_clamp(query.efficiency, "efficiency", DEFAULT_EFFICIENCY))),
                "supercharge_multiplier": str(query.supercharge if query.supercharge in SUPERCHARGE_CHOICES else 4)}
    form = {
        "from": start,
        "range": f"{_clamp(query.jump_range, 'range', DEFAULT_JUMP_RANGE_LY):g}",
        "radius": str(int(_clamp(query.radius, "radius", DEFAULT_RADIUS_LY))),
        "max_results": str(int(_clamp(query.max_results, "max_results", DEFAULT_MAX_RESULTS))),
        "max_distance": str(int(_clamp(query.max_distance, "max_distance", DEFAULT_MAX_ARRIVAL_LS))),
        "min_value": str(max(1, int(query.min_value or DEFAULT_MIN_VALUE[query.kind]))),
        "avoid_thargoids": "1" if query.avoid_thargoids else "0",
        "loop": "1" if query.loop else "0",
    }
    destination = " ".join(str(query.destination or "").split())
    if destination:
        form["to"] = destination
    if query.kind == RICHES:
        form["use_mapping_value"] = "1" if query.use_mapping_value else "0"
    return form


def default_name(query: PlanQuery) -> str:
    """A name for the expedition made from a plan, e.g. "Road to Riches from Sol"."""
    return f"{TITLES[query.kind]} from {' '.join(str(query.start).split())}"[:80]


def credits(value: Any) -> str:
    """12345678 -> '12.3M cr', 45600 -> '45.6k cr', 900 -> '900 cr'."""
    try:
        number = float(value)
    except (TypeError, ValueError):
        return ""
    if number >= 1_000_000:
        return f"{number / 1_000_000:.1f}M cr"
    if number >= 10_000:
        return f"{number / 1_000:.1f}k cr"
    return f"{int(number):,} cr"


def _num(value: Any) -> float:
    return float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else 0.0


def _xyz(raw: Dict[str, Any]) -> Optional[XYZ]:
    try:
        x, y, z = (float(raw[k]) for k in ("x", "y", "z"))
    except (KeyError, TypeError, ValueError):
        return None
    return (x, y, z)


def _riches_line(body: Dict[str, Any]) -> Tuple[float, str]:
    scan, mapped = _num(body.get("estimated_scan_value")), _num(body.get("estimated_mapping_value"))
    kind = str(body.get("subtype") or "").strip()
    if body.get("is_terraformable"):
        kind = f"{kind}, terraformable" if kind else "terraformable"
    parts = [f"scan {credits(scan)}"] if scan else []
    if mapped:
        parts.append(f"map {credits(mapped)}")
    label = str(body.get("name") or "?")
    detail = ", ".join(x for x in (kind, " / ".join(parts)) if x)
    return scan + mapped, f"{label} ({detail})" if detail else label


def _exobiology_line(body: Dict[str, Any]) -> Tuple[float, str]:
    species: Dict[str, List[float]] = {}
    for landmark in body.get("landmarks") or []:
        if not isinstance(landmark, dict):
            continue
        name = str(landmark.get("subtype") or landmark.get("type") or "").strip()
        if not name:
            continue
        count = max(1, int(_num(landmark.get("count")) or 1))
        entry = species.setdefault(name, [0, _num(landmark.get("value"))])
        entry[0] += count
    ranked = sorted(species.items(), key=lambda item: item[1][1], reverse=True)
    shown = ", ".join(f"{name} x{int(entry[0])} ({credits(entry[1])})" if entry[0] > 1 else f"{name} ({credits(entry[1])})"
                      for name, entry in ranked[:SPECIES_PER_BODY])
    if len(ranked) > SPECIES_PER_BODY:
        shown += f", +{len(ranked) - SPECIES_PER_BODY} more"
    value = _num(body.get("landmark_value")) or sum(entry[1] for entry in species.values())
    label = str(body.get("name") or "?")
    kind = str(body.get("subtype") or "").strip()
    head = f"{label} ({kind})" if kind else label
    return value, f"{head}: {shown}" if shown else head


def parse_neutron_stops(result: Any) -> List[PlannedStop]:
    """The neutron plotter's `system_jumps` -> one stop per system to jump to, in order. The first entry (where you start, no jumps) is left out.
    The note says how many jumps it is from the stop before and whether the system is a neutron star to supercharge at."""
    entries = result.get("system_jumps") if isinstance(result, dict) else None
    stops: List[PlannedStop] = []
    for raw in entries if isinstance(entries, list) else []:
        if not isinstance(raw, dict) or not isinstance(raw.get("system"), str) or not raw["system"].strip():
            continue
        jumps = int(_num(raw.get("jumps")))
        if jumps <= 0:
            continue
        note = f"{jumps} jump{'s' if jumps != 1 else ''}" + (", neutron star: supercharge here" if raw.get("neutron_star") else "")
        stops.append(PlannedStop(" ".join(raw["system"].split()), "", note, _xyz(raw)))
    return stops


def parse_stops(kind: str, result: Any, start: str = "") -> List[PlannedStop]:
    """Spansh's `result` list -> stops, in route order. A malformed system is skipped rather than failing the whole plan. The system you start
    in (which has no bodies) is left out, because you are already there."""
    if kind == NEUTRON:
        return parse_neutron_stops(result)
    line = _riches_line if kind == RICHES else _exobiology_line
    started = " ".join(str(start or "").split()).casefold()
    stops: List[PlannedStop] = []
    for raw in result if isinstance(result, list) else []:
        if not isinstance(raw, dict) or not isinstance(raw.get("name"), str) or not raw["name"].strip():
            continue
        name = " ".join(raw["name"].split())
        bodies = [b for b in raw.get("bodies") or [] if isinstance(b, dict)]
        if not bodies and name.casefold() == started:
            continue
        ranked = sorted((line(b) for b in bodies), key=lambda pair: pair[0], reverse=True)
        best = max(bodies, key=lambda b: line(b)[0], default=None)
        note = "; ".join(text for _value, text in ranked[:BODIES_PER_NOTE])
        if len(ranked) > BODIES_PER_NOTE:
            note += f"; +{len(ranked) - BODIES_PER_NOTE} more bodies"
        stops.append(PlannedStop(name, str(best.get("name") or "") if best else "", note[:NOTE_CHARS], _xyz(raw)))
    return stops


def _request(url: str, data: Optional[bytes] = None) -> Dict[str, Any]:
    request = urllib.request.Request(url, data=data, headers={"User-Agent": _USER_AGENT}, method="POST" if data is not None else "GET")
    try:
        with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT_S) as response:
            parsed = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as err:
        reason = ""
        try:
            body = json.loads(err.read().decode("utf-8"))
            reason = str(body.get("error") or "") if isinstance(body, dict) else ""
        except (OSError, ValueError):
            pass
        if err.code in (400, 404, 422) and reason:
            raise RouteSearchError(f"Spansh says: {reason}.") from err
        raise
    return parsed if isinstance(parsed, dict) else {}


def plan(query: PlanQuery, cancel: Optional[threading.Event] = None, on_state: Optional[Callable[[str], None]] = None) -> List[PlannedStop]:
    """Submit the plan, wait for Spansh to finish it, return the stops (empty when nothing near the route is worth the minimum value). Raises
    RouteSearchError, or a network error (OSError / ValueError) for the caller to log. `on_state(text)` hears whether the job is waiting in
    Spansh's queue or being calculated."""
    submitted = _request(URLS[query.kind], urllib.parse.urlencode(build_form(query)).encode("utf-8"))
    job = submitted.get("job")
    if not job:
        raise RouteSearchError(str(submitted.get("error") or "Spansh did not accept the request."))
    if on_state is not None:
        on_state(describe_state(submitted.get("status")))
    deadline = time.monotonic() + MAX_WAIT_S
    while time.monotonic() < deadline:
        if cancel is not None and cancel.wait(POLL_INTERVAL_S):
            raise RouteSearchError("Cancelled.")
        if cancel is None:
            time.sleep(POLL_INTERVAL_S)
        data = _request(RESULTS_URL + urllib.parse.quote(str(job)))
        state = data.get("state")
        if on_state is not None:
            on_state(describe_state(state))
        if state == "completed":
            if data.get("status") not in (None, "ok"):
                raise RouteSearchError(str(data.get("error") or "Spansh could not plan that route."))
            return parse_stops(query.kind, data.get("result"), query.start)
        if state in ("failed", "error"):
            raise RouteSearchError(str(data.get("error") or "Spansh could not plan that route."))
    raise RouteSearchError("Spansh took too long. Try a smaller radius or fewer results.")
