"""Marks: named spots on a planet's surface that the Surface Compass can point at, kept per commander. One small JSON file
(`surface_marks.json` beside the plugin, `commander_data.py`): every commander has a separate list and a separate choice of target,
and nothing is ever sent anywhere.

A mark is a name, the body it is on (the game's own body name, which already includes the system) and a latitude and longitude in
degrees. A mark belongs to one body: the compass only offers the marks on the body the commander is on, matched by name trimmed
and case-folded. The compass target is one of `AUTO` (the nearest recorded mining hotspot with a position, the way the old Mining
waypoint arrow worked), `NONE` (point at nothing), or the id of a mark. Deleting the marked target returns to `AUTO`. This is the
pure part (no Tk); the compass is `surface_compass.py` and the window `surface_marks_window.py`."""
from __future__ import annotations

import logging
import math
import os
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

from . import commander_data

try:
    from config import appname
except ImportError:  # unit tests outside EDMC
    appname = "EDMarketConnector"

plugin_name = os.path.basename(os.path.dirname(__file__))
logger = logging.getLogger(f"{appname}.{plugin_name}")

STATE_FILENAME = "surface_marks.json"
MAX_MARKS = 500
MAX_NAME = 60
MAX_BODY = 100

AUTO = "auto"      # the nearest recorded hotspot on this body
NONE = "none"      # no target


class MarkError(ValueError):
    """A mark that cannot be saved; the message says why and is shown to the commander as it is."""


@dataclass(frozen=True)
class Mark:
    id: str
    name: str
    body: str
    latitude: float
    longitude: float
    created: str


@dataclass(frozen=True)
class Here:
    """Where the commander is now, for a mark made on the spot and for distances in the window: the body (from the game's
    `Status.json`), the position on it and the body's radius. Everything is None or empty when there is no surface position."""
    body: str = ""
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    radius: Optional[float] = None

    @property
    def on_surface(self) -> bool:
        return self.latitude is not None and self.longitude is not None


def body_key(body: Any) -> str:
    return str(body or "").strip().casefold()


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _empty() -> Dict[str, Any]:
    return {"marks": [], "target": AUTO}


def _is_legacy(_raw: Any) -> bool:
    return False   # the file is new; nothing older to claim


def _number(value: Any, what: str, low: float, high: float) -> float:
    try:
        number = float(str(value).strip().replace(",", ".")) if isinstance(value, str) else float(value)
    except (TypeError, ValueError):
        raise MarkError(f"{what} must be a number.") from None
    if not math.isfinite(number) or not low <= number <= high:
        raise MarkError(f"{what} must be between {low:g} and {high:g}.")
    return number


def _from_raw(raw: Any) -> Optional[Mark]:
    """A mark read from the file, or None for a damaged entry (dropped, so one bad entry cannot stop the load)."""
    if not isinstance(raw, dict):
        return None
    mark_id, name, body = raw.get("id"), raw.get("name"), raw.get("body")
    if not all(isinstance(v, str) and v.strip() for v in (mark_id, name, body)):
        return None
    try:
        latitude, longitude = _number(raw.get("latitude"), "latitude", -90, 90), _number(raw.get("longitude"), "longitude", -180, 180)
    except MarkError:
        return None
    return Mark(mark_id, name.strip()[:MAX_NAME], body.strip()[:MAX_BODY], latitude, longitude, str(raw.get("created") or ""))


def _to_raw(mark: Mark) -> Dict[str, Any]:
    return {"id": mark.id, "name": mark.name, "body": mark.body, "latitude": mark.latitude, "longitude": mark.longitude,
            "created": mark.created}


class MarkBook:
    """The commander's marks and compass target. Constructed empty; `load(plugin_dir)` once at start-up and `set_commander(cmdr)`
    whenever the commander is known or changes. Every change is written straight away."""

    def __init__(self, now: Callable[[], str] = _now, new_id: Callable[[], str] = lambda: uuid.uuid4().hex[:12]) -> None:
        self._store = commander_data.new_store()
        self._plugin_dir: Optional[str] = None
        self._cmdr = ""
        self._now = now
        self._new_id = new_id
        self._marks: List[Mark] = []
        self._target = AUTO
        self._listeners: List[Callable[[], None]] = []

    # --- loading and saving --------------------------------------------------------------------------------------

    def load(self, plugin_dir: str) -> None:
        self._plugin_dir = plugin_dir
        self._store = commander_data.read(os.path.join(plugin_dir, STATE_FILENAME), _is_legacy)
        self._reload()

    def set_commander(self, cmdr: str) -> bool:
        """True when this changed whose marks are showing."""
        cmdr = str(cmdr or "").strip()
        if not cmdr or commander_data.key_for(cmdr) == commander_data.key_for(self._cmdr):
            return False
        self._cmdr = cmdr
        self._reload()
        return True

    def _reload(self) -> None:
        self._marks, self._target = [], AUTO
        if self._cmdr:
            payload = commander_data.payload_for(self._store, self._cmdr, _empty)
            payload = payload if isinstance(payload, dict) else {}
            raw = payload.get("marks")
            self._marks = [m for m in (_from_raw(r) for r in (raw if isinstance(raw, list) else [])) if m is not None]
            target = payload.get("target")
            self._target = target if target in (AUTO, NONE) or self.get(str(target)) is not None else AUTO
        self._changed()

    def _save(self) -> None:
        if not self._cmdr or self._plugin_dir is None:
            return
        commander_data.put(self._store, self._cmdr, {"marks": [_to_raw(m) for m in self._marks], "target": self._target})
        commander_data.write(os.path.join(self._plugin_dir, STATE_FILENAME), self._store)

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
                logger.debug("Marks listener failed", exc_info=True)

    # --- reading ---------------------------------------------------------------------------------------------------

    @property
    def commander(self) -> str:
        return self._cmdr

    @property
    def ready(self) -> bool:
        """Marks can be added: a commander is known."""
        return bool(self._cmdr)

    @property
    def target(self) -> str:
        return self._target

    def all(self) -> List[Mark]:
        """By name, then oldest first."""
        return sorted(self._marks, key=lambda m: (m.name.casefold(), m.created))

    def get(self, mark_id: str) -> Optional[Mark]:
        return next((m for m in self._marks if m.id == mark_id), None)

    def for_body(self, body: Any) -> List[Mark]:
        key = body_key(body)
        return [m for m in self.all() if key and body_key(m.body) == key]

    def target_mark(self) -> Optional[Mark]:
        """The mark the compass is set to point at, or None (the target is AUTO or NONE)."""
        return self.get(self._target)

    def count(self) -> int:
        return len(self._marks)

    def next_name(self) -> str:
        """`Mark 1`, `Mark 2`, ... the first one not already used (for a mark made with no name typed)."""
        used = {m.name.casefold() for m in self._marks}
        number = 1
        while f"mark {number}" in used:
            number += 1
        return f"Mark {number}"

    # --- changing --------------------------------------------------------------------------------------------------

    @staticmethod
    def _checked(name: Any, body: Any, latitude: Any, longitude: Any) -> tuple:
        name, body = str(name or "").strip(), str(body or "").strip()
        if not name:
            raise MarkError("A mark needs a name.")
        if not body:
            raise MarkError("A mark needs the name of the body it is on.")
        if len(name) > MAX_NAME:
            raise MarkError(f"A mark's name can be at most {MAX_NAME} characters.")
        if len(body) > MAX_BODY:
            raise MarkError(f"A body name can be at most {MAX_BODY} characters.")
        return name, body, _number(latitude, "Latitude", -90, 90), _number(longitude, "Longitude", -180, 180)

    def add(self, name: Any, body: Any, latitude: Any, longitude: Any) -> Mark:
        if not self.ready:
            raise MarkError("Marks are kept per commander and no commander is known yet. Log in first.")
        name, body, latitude, longitude = self._checked(name, body, latitude, longitude)
        if len(self._marks) >= MAX_MARKS:
            raise MarkError(f"There is room for {MAX_MARKS} marks. Delete some before adding more.")
        mark = Mark(self._new_id(), name, body, latitude, longitude, self._now())
        self._marks.append(mark)
        self._save()
        self._changed()
        return mark

    def update(self, mark_id: str, name: Any, body: Any, latitude: Any, longitude: Any) -> Mark:
        old = self.get(mark_id)
        if old is None:
            raise MarkError("That mark no longer exists.")
        name, body, latitude, longitude = self._checked(name, body, latitude, longitude)
        new = Mark(old.id, name, body, latitude, longitude, old.created)
        self._marks[self._marks.index(old)] = new
        self._save()
        self._changed()
        return new

    def delete(self, mark_id: str) -> bool:
        old = self.get(mark_id)
        if old is None:
            return False
        self._marks.remove(old)
        if self._target == old.id:
            self._target = AUTO
        self._save()
        self._changed()
        return True

    def set_target(self, target: str) -> None:
        """`AUTO`, `NONE` or the id of an existing mark."""
        if target not in (AUTO, NONE) and self.get(target) is None:
            raise MarkError("That mark no longer exists.")
        if not self.ready:
            raise MarkError("Marks are kept per commander and no commander is known yet. Log in first.")
        if target != self._target:
            self._target = target
            self._save()
            self._changed()
