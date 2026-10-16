"""Remembers each system's survey between sessions, per commander, so leaving a system and coming back (or logging out and back in) shows where you left off.

The journal only holds the scans of the visits it covers, and a relog starts a new journal, so a system surveyed over several visits cannot always be rebuilt from
the journals alone. This keeps what `system_survey.SystemSurvey` knows about each system (the bodies with everything their scans said, the honk and how far the
system scan got, what is mapped and which organisms are analysed) in `system_surveys.json` beside the plugin, one payload per commander
(`commander_data.py`), and merges it back when the commander arrives in, or is restored to, the system.

A save is debounced (a burst of scans is one write) and the file keeps only the most recently visited systems (`MAX_SYSTEMS`). Nothing is sent anywhere. Pure
apart from the file: no Tk, no EDMC beyond the logger.
"""

from __future__ import annotations

import dataclasses
import logging
import os
import threading
import time
from typing import Any, Dict, List, Optional

from . import commander_data

try:
    from config import appname
except ImportError:   # unit tests outside EDMC
    appname = "EDMarketConnector"

plugin_name = os.path.basename(os.path.dirname(__file__))
logger = logging.getLogger(f"{appname}.{plugin_name}")

STATE_FILENAME = "system_surveys.json"
MAX_SYSTEMS = 60
SAVE_DELAY = 2.0          # seconds a burst of events is allowed to settle before the file is written


def _empty() -> Dict[str, Any]:
    return {"systems": {}}


def _is_legacy(_raw: Any) -> bool:
    return False


def system_key(name: str, address: Optional[int]) -> str:
    return str(address) if isinstance(address, int) else name.casefold()


def body_to_raw(body: Any) -> Dict[str, Any]:
    """A `system_survey.Body` as plain JSON data (its fields, tuples as lists)."""
    return dataclasses.asdict(body)


def body_from_raw(raw: Any, body_class: Any) -> Optional[Any]:
    """A `Body` from `body_to_raw`'s data, ignoring unknown fields and anything damaged; None when it cannot be made."""
    if not isinstance(raw, dict) or not isinstance(raw.get("body_id"), int):
        return None
    names = {f.name for f in dataclasses.fields(body_class)}
    try:
        body = body_class(**{k: v for k, v in raw.items() if k in names})
        body.materials = [(str(m[0]), float(m[1])) for m in raw.get("materials", []) if isinstance(m, (list, tuple)) and len(m) == 2]
        body.atmosphere_parts = [(str(m[0]), float(m[1])) for m in raw.get("atmosphere_parts", []) if isinstance(m, (list, tuple)) and len(m) == 2]
        body.genuses = [str(g) for g in raw.get("genuses", [])]
        body.analysed = [str(g) for g in raw.get("analysed", [])]
        return body
    except (TypeError, ValueError):
        return None


class SurveyStore:
    """The saved surveys of the current commander. `start(plugin_dir)` once, `set_commander(cmdr)` when the commander is known, `remember(survey)` after the
    survey changes (debounced), and `merge_into(survey)` when a system is entered or restored."""

    def __init__(self) -> None:
        self._store = commander_data.new_store()
        self._plugin_dir: Optional[str] = None
        self._cmdr = ""
        self._lock = threading.RLock()
        self._timer: Optional[threading.Timer] = None
        self._pending: Optional[Dict[str, Any]] = None       # the survey's raw data waiting to be written
        self.delay = SAVE_DELAY

    # --- loading and saving --------------------------------------------------------------------------------------
    def start(self, plugin_dir: str) -> None:
        with self._lock:
            self._plugin_dir = plugin_dir
            self._store = commander_data.read(os.path.join(plugin_dir, STATE_FILENAME), _is_legacy)

    @property
    def commander(self) -> str:
        return self._cmdr

    def has_saved(self, name: str, address: Optional[int]) -> bool:
        return self.saved(name, address) is not None

    def set_commander(self, cmdr: str) -> None:
        cmdr = str(cmdr or "").strip()
        if not cmdr or commander_data.key_for(cmdr) == commander_data.key_for(self._cmdr):
            return
        self.flush()
        with self._lock:
            self._cmdr = cmdr

    def _systems(self) -> Optional[Dict[str, Any]]:
        if not self._cmdr:
            return None
        payload = commander_data.payload_for(self._store, self._cmdr, _empty)
        if not isinstance(payload, dict) or not isinstance(payload.get("systems"), dict):
            payload = _empty()
            commander_data.put(self._store, self._cmdr, payload)
        return payload["systems"]

    def remember(self, survey: Any) -> None:
        """Notes the survey's current state and writes it soon. A system with no scanned body and no honk is not worth keeping."""
        if not survey.name or not (survey.honked or survey.bodies):
            return
        raw = {"name": survey.name, "address": survey.address, "honked": survey.honked, "body_count": survey.body_count, "progress": survey.progress,
               "fss_complete": survey.fss_complete, "last": time.time(), "bodies": [body_to_raw(b) for b in survey.bodies.values()]}
        with self._lock:
            self._pending = raw
            if self._timer is not None:
                self._timer.cancel()
            self._timer = threading.Timer(self.delay, self.flush)
            self._timer.daemon = True
            self._timer.start()

    def flush(self) -> None:
        """Writes any waiting change now."""
        with self._lock:
            timer, self._timer = self._timer, None
            if timer is not None:
                timer.cancel()
            raw, self._pending = self._pending, None
            systems = self._systems()
            if raw is None or systems is None or self._plugin_dir is None:
                return
            systems[system_key(raw["name"], raw["address"])] = raw
            if len(systems) > MAX_SYSTEMS:
                for key in sorted(systems, key=lambda k: systems[k].get("last", 0.0))[:len(systems) - MAX_SYSTEMS]:
                    del systems[key]
            commander_data.write(os.path.join(self._plugin_dir, STATE_FILENAME), self._store)

    # --- merging back --------------------------------------------------------------------------------------------
    def saved(self, name: str, address: Optional[int]) -> Optional[Dict[str, Any]]:
        with self._lock:
            systems = self._systems()
            if systems is None:
                return None
            raw = systems.get(system_key(name, address)) or systems.get(system_key(name, None))
            return raw if isinstance(raw, dict) else None

    def merge_into(self, survey: Any, body_class: Any) -> int:
        """Adds what was saved about the survey's system to it: bodies the survey does not have, and for those it has, what the saved copy knew that the live one
        does not (the scan, mapped, analysed organisms, signals). The live data wins wherever it has a value. Returns how many bodies were added or filled in."""
        if not survey.name:
            return 0
        raw = self.saved(survey.name, survey.address)
        if raw is None:
            return 0
        changed = 0
        if not survey.honked and raw.get("honked"):
            survey.honked, survey.body_count, survey.progress = True, int(raw.get("body_count") or 0), float(raw.get("progress") or 0.0)
        survey.fss_complete = survey.fss_complete or bool(raw.get("fss_complete"))
        for item in raw.get("bodies", []):
            saved = body_from_raw(item, body_class)
            if saved is None:
                continue
            live = survey.bodies.get(saved.body_id)
            if live is None:
                survey.bodies[saved.body_id] = saved
                changed += 1
                continue
            if _fill(live, saved):
                changed += 1
        return changed


def absorb(self_store: "SurveyStore", found: Any, body_class: Any) -> None:
    """Adds a survey rebuilt from the journals (`found`, a SystemSurvey) to the saved record of its system, keeping what was saved and filling in what it did not
    know, and writes it. Used for the visits that happened before this was saved."""
    with self_store._lock:
        systems = self_store._systems()
        if systems is None or self_store._plugin_dir is None or not found.name:
            return
        key = system_key(found.name, found.address)
        record = systems.get(key) or systems.get(system_key(found.name, None))
        bodies: Dict[int, Any] = {}
        if isinstance(record, dict):
            for item in record.get("bodies", []):
                body = body_from_raw(item, body_class)
                if body is not None:
                    bodies[body.body_id] = body
        for body in found.bodies.values():
            if body.body_id in bodies:
                _fill(bodies[body.body_id], body)
            else:
                bodies[body.body_id] = body
        honked = bool(record.get("honked")) if isinstance(record, dict) else False
        systems[key] = {"name": found.name, "address": found.address, "honked": honked or found.honked,
                        "body_count": max(int(record.get("body_count") or 0) if isinstance(record, dict) else 0, found.body_count),
                        "progress": max(float(record.get("progress") or 0.0) if isinstance(record, dict) else 0.0, found.progress),
                        "fss_complete": bool(record.get("fss_complete")) if isinstance(record, dict) and record.get("fss_complete") else found.fss_complete,
                        "last": time.time(), "bodies": [body_to_raw(b) for b in bodies.values()]}
        commander_data.write(os.path.join(self_store._plugin_dir, STATE_FILENAME), self_store._store)


def _fill(live: Any, saved: Any) -> bool:
    """Fills `live` from `saved` where the live one is missing something. True when anything changed."""
    changed = False
    if saved.scanned and not live.scanned:
        for field in dataclasses.fields(live):
            if field.name in ("body_id", "name", "short", "mapped", "bio", "geo", "genuses", "analysed", "sampling", "known"):
                continue
            setattr(live, field.name, getattr(saved, field.name))
        changed = True
    if saved.was_footfalled is False and live.was_footfalled is not False:
        live.was_footfalled, changed = False, True
    for field in ("mapped",):
        if getattr(saved, field) and not getattr(live, field):
            setattr(live, field, True)
            changed = True
    for field in ("bio", "geo"):
        if getattr(saved, field) > getattr(live, field):
            setattr(live, field, getattr(saved, field))
            changed = True
    for field in ("genuses", "analysed"):
        merged: List[str] = list(getattr(live, field))
        for item in getattr(saved, field):
            if item not in merged:
                merged.append(item)
        if merged != getattr(live, field):
            setattr(live, field, merged)
            changed = True
    if not live.name and saved.name:
        live.name, live.short = saved.name, saved.short
    return changed


SurveyStore.absorb = absorb       # type: ignore[attr-defined]
store = SurveyStore()
