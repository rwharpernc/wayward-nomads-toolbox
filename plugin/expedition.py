"""Expedition planner: named expeditions, each an ordered list of stops with notes, and how far along the commander is. Kept per commander in
`expeditions.json` beside the plugin (`commander_data.py`): every commander has a separate set, and nothing is ever sent anywhere. This is the pure
part (no Tk); the Exploration row is `expedition_panel.py` and the window `expedition_window.py`.

An **expedition** has a name, a status and stops. Status: `planned` (being put together), `active` (the one being tracked: at most one at a time),
`paused` (set aside by starting another; its progress is kept) and `done`. A **stop** is a system, an optional body and note, its coordinates when
known, and when it was visited.

**Progress** comes from the journal: on arriving in a system (`FSDJump`, `CarrierJump`, or `Location` at login) the first unvisited stop with that
name in the active expedition is marked visited (wherever it sits in the list, so skipping ahead is recorded), and a jump counts one jump and its
`JumpDist` light-years. The same system can be a stop twice (an outbound and a return leg); each arrival ticks one. When the last stop is visited the
expedition stays active until the commander finishes it. The straight-line distance to the next stop uses coordinates the game gave (`StarPos`, a
plotted route) or EDSM; a stop without them has no distance. Stats count only what happened while the expedition was active.

Importing reuses `waypoint_route.WaypointRoute.parse_navroute` (the route plotted in the game) and a CSV with the columns system, body, note.
Ordering by nearest neighbor works on the unvisited stops that have coordinates and leaves the rest where they are.

Limits keep the file small and the window quick: 30 expeditions, 500 stops each, and 80/100/100/500 characters for a name, a system, a body and a note.
Past them a change is refused with a message, never trimmed quietly."""
from __future__ import annotations

import csv
import io
import logging
import math
import os
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple

from . import commander_data
from .waypoint_route import WaypointRoute

try:
    from config import appname
except ImportError:  # unit tests outside EDMC
    appname = "EDMarketConnector"

plugin_name = os.path.basename(os.path.dirname(__file__))
logger = logging.getLogger(f"{appname}.{plugin_name}")

STATE_FILENAME = "expeditions.json"
PLANNED, ACTIVE, PAUSED, DONE = "planned", "active", "paused", "done"
STATUSES = (PLANNED, ACTIVE, PAUSED, DONE)
MAX_EXPEDITIONS = 30
MAX_STOPS = 500
MAX_NAME, MAX_SYSTEM, MAX_BODY, MAX_NOTE = 80, 100, 100, 500
SAVE_EVERY_S = 5.0
ARRIVAL_EVENTS = ("FSDJump", "CarrierJump", "Location")

XYZ = Tuple[float, float, float]


class ExpeditionError(ValueError):
    """A change that cannot be made; the message says why and is shown to the commander as it is."""


@dataclass
class Stop:
    id: str
    system: str
    body: str = ""
    note: str = ""
    xyz: Optional[XYZ] = None
    visited: str = ""            # UTC time of arrival; empty until visited

    @property
    def is_visited(self) -> bool:
        return bool(self.visited)


@dataclass
class Expedition:
    id: str
    name: str
    status: str = PLANNED
    created: str = ""
    started: str = ""
    finished: str = ""
    jumps: int = 0
    light_years: float = 0.0
    stops: List[Stop] = field(default_factory=list)

    def next_stop(self) -> Optional[Stop]:
        return next((s for s in self.stops if not s.is_visited), None)

    @property
    def visited_count(self) -> int:
        return sum(1 for s in self.stops if s.is_visited)

    @property
    def all_visited(self) -> bool:
        return bool(self.stops) and self.visited_count == len(self.stops)


@dataclass(frozen=True)
class Arrival:
    """What an arrival did to the active expedition: the stop it ticked off (None if the system was not a stop) and whether that was the last."""
    expedition: Expedition
    stop: Optional[Stop]
    completed: bool


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _epoch(stamp: str) -> Optional[float]:
    try:
        return datetime.strptime(stamp, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc).timestamp()
    except (TypeError, ValueError):
        return None


def elapsed_text(start: str, end: str = "") -> str:
    """`3 d 4 h`, `5 h 12 min`, `40 min`; empty when the start is unknown. `end` defaults to now."""
    a, b = _epoch(start), _epoch(end) if end else time.time()
    if a is None or b is None:
        return ""
    seconds = max(0, int(b - a))
    days, rest = divmod(seconds, 86400)
    hours, rest = divmod(rest, 3600)
    minutes = rest // 60
    if days:
        return f"{days} d {hours} h"
    if hours:
        return f"{hours} h {minutes} min"
    return f"{minutes} min"


def clip(text: Any, limit: int) -> str:
    """`text` on one line, shortened with an ellipsis to at most `limit` characters (for tables and the panel)."""
    one_line = " ".join(str(text or "").split())
    return one_line if len(one_line) <= limit else one_line[:max(0, limit - 1)].rstrip() + "…"


def name_key(name: Any) -> str:
    return " ".join(str(name or "").split()).casefold()


def distance(a: Optional[XYZ], b: Optional[XYZ]) -> Optional[float]:
    return math.dist(a, b) if a is not None and b is not None else None


def _xyz(raw: Any) -> Optional[XYZ]:
    if isinstance(raw, (list, tuple)) and len(raw) == 3 and all(isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) for v in raw):
        return (float(raw[0]), float(raw[1]), float(raw[2]))
    return None


parse_xyz = _xyz
"""A position from the journal's `StarPos` (three finite numbers), or None."""


def _empty() -> Dict[str, Any]:
    return {"expeditions": []}


def _is_legacy(_raw: Any) -> bool:
    return False   # the file is new; nothing older to claim


def _stop_from_raw(raw: Any) -> Optional[Stop]:
    if not isinstance(raw, dict) or not isinstance(raw.get("system"), str) or not raw["system"].strip():
        return None
    return Stop(str(raw.get("id") or uuid.uuid4().hex[:8]), " ".join(raw["system"].split())[:MAX_SYSTEM],
                " ".join(str(raw.get("body") or "").split())[:MAX_BODY], str(raw.get("note") or "").strip()[:MAX_NOTE],
                _xyz(raw.get("xyz")), str(raw.get("visited") or ""))


def _expedition_from_raw(raw: Any) -> Optional[Expedition]:
    if not isinstance(raw, dict) or not isinstance(raw.get("id"), str) or not isinstance(raw.get("name"), str) or not raw["name"].strip():
        return None
    status = raw.get("status") if raw.get("status") in STATUSES else PLANNED
    jumps, ly = raw.get("jumps"), raw.get("light_years")
    stops: List[Stop] = []
    for item in raw.get("stops") if isinstance(raw.get("stops"), list) else []:
        stop = _stop_from_raw(item)
        if stop is not None and len(stops) < MAX_STOPS:
            stops.append(stop)
    return Expedition(raw["id"], " ".join(raw["name"].split())[:MAX_NAME], status, str(raw.get("created") or ""), str(raw.get("started") or ""),
                      str(raw.get("finished") or ""), jumps if isinstance(jumps, int) and not isinstance(jumps, bool) and jumps >= 0 else 0,
                      float(ly) if isinstance(ly, (int, float)) and not isinstance(ly, bool) and math.isfinite(ly) and ly >= 0 else 0.0, stops)


def _expedition_to_raw(e: Expedition) -> Dict[str, Any]:
    return {"id": e.id, "name": e.name, "status": e.status, "created": e.created, "started": e.started, "finished": e.finished,
            "jumps": e.jumps, "light_years": round(e.light_years, 2),
            "stops": [{"id": s.id, "system": s.system, "body": s.body, "note": s.note, "xyz": list(s.xyz) if s.xyz else None,
                       "visited": s.visited} for s in e.stops]}


class ExpeditionBook:
    """The commander's expeditions. Constructed empty; `load(plugin_dir)` once at start-up and `set_commander(cmdr)` whenever the commander is known
    or changes. A change to the plan is written at once; the jump counts and distance (which change every jump) are written at most every few
    seconds, and `flush()` writes what is waiting."""

    def __init__(self, now: Callable[[], str] = _now, new_id: Callable[[], str] = lambda: uuid.uuid4().hex[:8],
                 clock: Callable[[], float] = time.monotonic) -> None:
        self._store = commander_data.new_store()
        self._plugin_dir: Optional[str] = None
        self._cmdr = ""
        self._now = now
        self._new_id = new_id
        self._clock = clock
        self._expeditions: List[Expedition] = []
        self._dirty = False
        self._saved_at = -SAVE_EVERY_S
        self._listeners: List[Callable[[], None]] = []

    # --- loading and saving --------------------------------------------------------------------------------------

    def load(self, plugin_dir: str) -> None:
        self._plugin_dir = plugin_dir
        self._store = commander_data.read(os.path.join(plugin_dir, STATE_FILENAME), _is_legacy)
        self._reload()

    def set_commander(self, cmdr: str) -> bool:
        """True when this changed whose expeditions are showing."""
        cmdr = str(cmdr or "").strip()
        if not cmdr or commander_data.key_for(cmdr) == commander_data.key_for(self._cmdr):
            return False
        self.flush()
        self._cmdr = cmdr
        self._reload()
        return True

    def _reload(self) -> None:
        self._expeditions = []
        if self._cmdr:
            payload = commander_data.payload_for(self._store, self._cmdr, _empty)
            raw = payload.get("expeditions") if isinstance(payload, dict) else None
            seen = set()
            for item in raw if isinstance(raw, list) else []:
                e = _expedition_from_raw(item)
                if e is not None and e.id not in seen and len(self._expeditions) < MAX_EXPEDITIONS:
                    seen.add(e.id)
                    self._expeditions.append(e)
            actives = [e for e in self._expeditions if e.status == ACTIVE]
            for extra in actives[1:]:                  # only one is ever active: a damaged file with two keeps the first
                extra.status = PAUSED
        self._dirty = False
        self._changed()

    def _save(self, force: bool = True) -> None:
        self._dirty = True
        if not self._cmdr or self._plugin_dir is None:
            return
        if not force and self._clock() - self._saved_at < SAVE_EVERY_S:
            return
        commander_data.put(self._store, self._cmdr, {"expeditions": [_expedition_to_raw(e) for e in self._expeditions]})
        commander_data.write(os.path.join(self._plugin_dir, STATE_FILENAME), self._store)
        self._dirty = False
        self._saved_at = self._clock()

    def flush(self) -> None:
        """Write any change still waiting (call when EDMC closes or the commander changes)."""
        if self._dirty:
            self._save(force=True)

    def add_listener(self, callback: Callable[[], None]) -> None:
        self._listeners.append(callback)

    def remove_listener(self, callback: Callable[[], None]) -> None:
        if callback in self._listeners:
            self._listeners.remove(callback)

    def _changed(self) -> None:
        for callback in list(self._listeners):
            try:
                callback()
            except Exception:   # a listener (a window that has gone) must never stop a save
                logger.debug("Expedition listener failed", exc_info=True)

    # --- reading ---------------------------------------------------------------------------------------------------

    @property
    def commander(self) -> str:
        return self._cmdr

    @property
    def ready(self) -> bool:
        return bool(self._cmdr)

    def expeditions(self) -> List[Expedition]:
        """Active first, then planned and paused by name, then done (newest first)."""
        order = {ACTIVE: 0, PLANNED: 1, PAUSED: 1, DONE: 2}
        return sorted(self._expeditions, key=lambda e: (order[e.status], -(_epoch(e.finished) or 0) if e.status == DONE else 0, e.name.casefold()))

    def get(self, expedition_id: str) -> Optional[Expedition]:
        return next((e for e in self._expeditions if e.id == expedition_id), None)

    def active(self) -> Optional[Expedition]:
        return next((e for e in self._expeditions if e.status == ACTIVE), None)

    def _need(self, expedition_id: str) -> Expedition:
        e = self.get(expedition_id)
        if e is None:
            raise ExpeditionError("That expedition no longer exists.")
        return e

    @staticmethod
    def _stop(e: Expedition, stop_id: str) -> Stop:
        stop = next((s for s in e.stops if s.id == stop_id), None)
        if stop is None:
            raise ExpeditionError("That stop no longer exists.")
        return stop

    # --- changing the expeditions ------------------------------------------------------------------------------------

    def create(self, name: Any) -> Expedition:
        if not self.ready:
            raise ExpeditionError("Expeditions are kept per commander and no commander is known yet. Log in first.")
        name = " ".join(str(name or "").split())
        if not name:
            raise ExpeditionError("An expedition needs a name.")
        if len(name) > MAX_NAME:
            raise ExpeditionError(f"A name can be at most {MAX_NAME} characters.")
        if any(name_key(e.name) == name_key(name) for e in self._expeditions):
            raise ExpeditionError(f"There is an expedition called '{name}' already.")
        if len(self._expeditions) >= MAX_EXPEDITIONS:
            raise ExpeditionError(f"There is room for {MAX_EXPEDITIONS} expeditions. Delete one before adding another.")
        e = Expedition(self._new_id(), name, PLANNED, self._now())
        self._expeditions.append(e)
        self._save()
        self._changed()
        return e

    def rename(self, expedition_id: str, name: Any) -> Expedition:
        e = self._need(expedition_id)
        name = " ".join(str(name or "").split())
        if not name or len(name) > MAX_NAME:
            raise ExpeditionError(f"A name needs 1 to {MAX_NAME} characters.")
        if any(o.id != e.id and name_key(o.name) == name_key(name) for o in self._expeditions):
            raise ExpeditionError(f"There is an expedition called '{name}' already.")
        e.name = name
        self._save()
        self._changed()
        return e

    def delete(self, expedition_id: str) -> bool:
        e = self.get(expedition_id)
        if e is None:
            return False
        self._expeditions.remove(e)
        self._save()
        self._changed()
        return True

    def start(self, expedition_id: str) -> Expedition:
        """Make this the expedition being tracked. Another active one is paused (its progress is kept). A finished one is reopened."""
        e = self._need(expedition_id)
        if not e.stops:
            raise ExpeditionError("Add at least one stop before starting.")
        for other in self._expeditions:
            if other.status == ACTIVE and other.id != e.id:
                other.status = PAUSED
        e.status = ACTIVE
        e.started = e.started or self._now()
        e.finished = ""
        self._save()
        self._changed()
        return e

    def pause(self, expedition_id: str) -> Expedition:
        e = self._need(expedition_id)
        if e.status == ACTIVE:
            e.status = PAUSED
            self._save()
            self._changed()
        return e

    def finish(self, expedition_id: str) -> Expedition:
        e = self._need(expedition_id)
        e.status = DONE
        e.started = e.started or self._now()
        e.finished = self._now()
        self._save()
        self._changed()
        return e

    def reset(self, expedition_id: str) -> Expedition:
        """Forget the progress (visits, jumps, distance and times) and make it a plan again; the stops stay."""
        e = self._need(expedition_id)
        e.status, e.started, e.finished, e.jumps, e.light_years = PLANNED, "", "", 0, 0.0
        for s in e.stops:
            s.visited = ""
        self._save()
        self._changed()
        return e

    # --- changing the stops --------------------------------------------------------------------------------------------

    @staticmethod
    def _checked(system: Any, body: Any, note: Any) -> Tuple[str, str, str]:
        system, body, note = " ".join(str(system or "").split()), " ".join(str(body or "").split()), str(note or "").strip()
        if not system:
            raise ExpeditionError("A stop needs a system name.")
        if len(system) > MAX_SYSTEM or len(body) > MAX_BODY:
            raise ExpeditionError(f"System and body names can be at most {MAX_SYSTEM} and {MAX_BODY} characters.")
        if len(note) > MAX_NOTE:
            raise ExpeditionError(f"A note can be at most {MAX_NOTE} characters; this one is {len(note)}.")
        return system, body, note

    def add_stop(self, expedition_id: str, system: Any, body: Any = "", note: Any = "", xyz: Optional[XYZ] = None) -> Stop:
        e = self._need(expedition_id)
        system, body, note = self._checked(system, body, note)
        if len(e.stops) >= MAX_STOPS:
            raise ExpeditionError(f"An expedition can have {MAX_STOPS} stops.")
        stop = Stop(self._new_id(), system, body, note, _xyz(xyz))
        e.stops.append(stop)
        self._save()
        self._changed()
        return stop

    def update_stop(self, expedition_id: str, stop_id: str, system: Any, body: Any, note: Any) -> Stop:
        e = self._need(expedition_id)
        stop = self._stop(e, stop_id)
        system, body, note = self._checked(system, body, note)
        if name_key(system) != name_key(stop.system):
            stop.xyz, stop.visited = None, ""          # a different system: its position and visit no longer apply
        stop.system, stop.body, stop.note = system, body, note
        self._save()
        self._changed()
        return stop

    def remove_stop(self, expedition_id: str, stop_id: str) -> bool:
        e = self._need(expedition_id)
        stop = next((s for s in e.stops if s.id == stop_id), None)
        if stop is None:
            return False
        e.stops.remove(stop)
        self._save()
        self._changed()
        return True

    def move_stop(self, expedition_id: str, stop_id: str, delta: int) -> bool:
        """Swap a stop with its neighbor `delta` places away (-1 up, +1 down); False at either end."""
        e = self._need(expedition_id)
        index = next((i for i, s in enumerate(e.stops) if s.id == stop_id), None)
        if index is None or not 0 <= index + delta < len(e.stops):
            return False
        e.stops[index], e.stops[index + delta] = e.stops[index + delta], e.stops[index]
        self._save()
        self._changed()
        return True

    def set_visited(self, expedition_id: str, stop_id: str, visited: bool) -> Stop:
        """Tick a stop off by hand (or take the tick away)."""
        e = self._need(expedition_id)
        stop = self._stop(e, stop_id)
        stop.visited = (self._now() if visited else "")
        self._save()
        self._changed()
        return stop

    def set_coords(self, expedition_id: str, coords: Dict[str, XYZ]) -> int:
        """Give stops without a position the one found for their system ({system name: (x, y, z)}); returns how many were given one."""
        e = self._need(expedition_id)
        by_name = {name_key(k): _xyz(v) for k, v in coords.items()}
        given = 0
        for stop in e.stops:
            found = by_name.get(name_key(stop.system))
            if found is not None and stop.xyz is None:
                stop.xyz = found
                given += 1
        if given:
            self._save()
            self._changed()
        return given

    def add_systems(self, expedition_id: str, systems: Iterable[Tuple[str, Optional[XYZ]]], skip_duplicates_of_last: bool = True) -> int:
        """Append stops for a list of systems, each with its position when the game gave one (a plotted route). A system that is the same as the
        stop before it is skipped. Returns how many stops were added; stops past the limit are not added and the caller is told by the count."""
        e = self._need(expedition_id)
        added = 0
        for name, xyz in systems:
            name = " ".join(str(name or "").split())[:MAX_SYSTEM]
            if not name or len(e.stops) >= MAX_STOPS:
                continue
            if skip_duplicates_of_last and e.stops and name_key(e.stops[-1].system) == name_key(name):
                continue
            e.stops.append(Stop(self._new_id(), name, xyz=_xyz(xyz)))
            added += 1
        if added:
            self._save()
            self._changed()
        return added

    def add_planned(self, expedition_id: str, stops: Iterable[Tuple[str, str, str, Optional[XYZ]]]) -> int:
        """Append stops from a route planner: (system, body, note, position) in route order. A system the same as the stop before it is
        skipped, and anything too long is cut to the limits. Returns how many stops were added."""
        e = self._need(expedition_id)
        added = 0
        for system, body, note, xyz in stops:
            system = " ".join(str(system or "").split())[:MAX_SYSTEM]
            if not system or len(e.stops) >= MAX_STOPS:
                continue
            if e.stops and name_key(e.stops[-1].system) == name_key(system):
                continue
            e.stops.append(Stop(self._new_id(), system, " ".join(str(body or "").split())[:MAX_BODY], str(note or "").strip()[:MAX_NOTE], _xyz(xyz)))
            added += 1
        if added:
            self._save()
            self._changed()
        return added

    def add_rows(self, expedition_id: str, rows: Iterable[Tuple[str, str, str]]) -> Tuple[int, int]:
        """Append stops from (system, body, note) rows (a CSV), saving once. Returns (added, skipped): a row that is empty, too long or past the
        500-stop limit is skipped, never trimmed."""
        e = self._need(expedition_id)
        added = skipped = 0
        for system, body, note in rows:
            try:
                system, body, note = self._checked(system, body, note)
            except ExpeditionError:
                skipped += 1
                continue
            if len(e.stops) >= MAX_STOPS:
                skipped += 1
                continue
            e.stops.append(Stop(self._new_id(), system, body, note))
            added += 1
        if added:
            self._save()
            self._changed()
        return added, skipped

    def reorder_nearest_neighbor(self, expedition_id: str, start: XYZ) -> int:
        """Reorder the unvisited stops that have a position by always going to the nearest next from `start`. Visited stops stay at the front and
        stops without a position keep their order at the end. Returns how many were reordered."""
        e = self._need(expedition_id)
        visited = [s for s in e.stops if s.is_visited]
        pending = [s for s in e.stops if not s.is_visited]
        located = [s for s in pending if s.xyz is not None]
        unlocated = [s for s in pending if s.xyz is None]
        ordered: List[Stop] = []
        here = start
        while located:
            nearest = min(located, key=lambda s: math.dist(here, s.xyz))     # type: ignore[arg-type]
            located.remove(nearest)
            ordered.append(nearest)
            here = nearest.xyz                                              # type: ignore[assignment]
        e.stops = visited + ordered + unlocated
        if ordered:
            self._save()
            self._changed()
        return len(ordered)

    # --- the journal -----------------------------------------------------------------------------------------------

    def on_arrival(self, system: Any, stamp: str = "", jump_distance: Optional[float] = None, is_jump: bool = False) -> Optional[Arrival]:
        """The commander is in `system`. For the active expedition: count a jump and its distance when `is_jump`, and tick off the first unvisited
        stop of that system. None when nothing is active."""
        e = self.active()
        if e is None or not self.ready:
            return None
        stamp = stamp if _epoch(stamp) is not None else self._now()
        changed_plan = False
        if is_jump:
            e.jumps += 1
            if isinstance(jump_distance, (int, float)) and not isinstance(jump_distance, bool) and math.isfinite(jump_distance) and jump_distance > 0:
                e.light_years += float(jump_distance)
        key = name_key(system)
        stop = next((s for s in e.stops if not s.is_visited and name_key(s.system) == key), None) if key else None
        if stop is not None:
            stop.visited = stamp
            changed_plan = True
        if is_jump or stop is not None:
            self._save(force=changed_plan)
            self._changed()
        return Arrival(e, stop, stop is not None and e.all_visited)

    # --- progress and export ---------------------------------------------------------------------------------------------

    def distance_to_next(self, expedition: Expedition, position: Optional[XYZ]) -> Optional[float]:
        nxt = expedition.next_stop()
        return distance(position, nxt.xyz) if nxt is not None else None

    @staticmethod
    def to_csv(expedition: Expedition) -> str:
        """The stops as CSV: system, body, note, visited (the time, or empty). `parse_csv_stops` reads it back."""
        out = io.StringIO()
        writer = csv.writer(out, lineterminator="\n")
        writer.writerow(["system", "body", "note", "visited"])
        for s in expedition.stops:
            writer.writerow([s.system, s.body, s.note, s.visited])
        return out.getvalue()

    @staticmethod
    def to_text(expedition: Expedition) -> str:
        """A plain list to share: the name and status, then `1. [x] System / Body - note` for each stop."""
        lines = [f"{expedition.name} ({expedition.status}): {expedition.visited_count} of {len(expedition.stops)} stops"]
        for number, s in enumerate(expedition.stops, 1):
            place = f"{s.system} / {s.body}" if s.body else s.system
            lines.append(f"{number}. [{'x' if s.is_visited else ' '}] {place}" + (f" - {' '.join(s.note.split())}" if s.note else ""))
        return "\n".join(lines)

    @staticmethod
    def parse_csv_stops(text: str) -> List[Tuple[str, str, str]]:
        """(system, body, note) rows from CSV text: the first column is the system, the optional second the body and third the note. Blank rows and
        a header row (a first cell like `system` or `name`) are skipped. Reads the one-column files Waypoint Route reads and this planner's own export."""
        header_names = {"system", "name", "waypoint", "system name", "systemname"}
        rows: List[Tuple[str, str, str]] = []
        for row in csv.reader(io.StringIO(text.lstrip("﻿"))):
            cells = [c.strip() for c in row]
            if not cells or not cells[0] or cells[0].casefold() in header_names:
                continue
            rows.append((cells[0], cells[1] if len(cells) > 1 else "", cells[2] if len(cells) > 2 else ""))
        return rows

    @staticmethod
    def parse_navroute(data: Any, skip_system: Optional[str] = None) -> List[Tuple[str, Optional[XYZ]]]:
        """The systems of the route plotted in the game (the parsed `NavRoute.json`), each with its position when given."""
        return WaypointRoute.parse_navroute(data, skip_system)
