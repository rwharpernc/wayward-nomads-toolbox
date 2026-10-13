"""Engineering materials the commander holds: Raw, Manufactured and Encoded, kept per commander. One small JSON file (`materials.json` beside
the plugin, `commander_data.py`): every commander has a separate set of counts, and nothing is ever sent anywhere. This is the pure part (no Tk);
the panel row is `materials_panel.py` and the window `materials_window.py`.

**Where the counts come from.** The game writes a full `Materials` list when a commander logs in, and then one event for every change:
`MaterialCollected`, `MaterialDiscarded`, `MaterialTrade` (one paid, one received), `Synthesis`, `EngineerCraft`, `TechnologyBroker`,
`EngineerContribution` (a material handed to an engineer) and `MissionCompleted` (`MaterialsReward`). The `Materials` list replaces every
count; the others add or take away. If WNTB starts in the middle of a session, it takes EDMC's own running totals once (the `Raw`,
`Manufactured` and `Encoded` entries of the state EDMC passes to plugins) so the counts are right before the next login list arrives.

**Names, types and grades** come from the FDevIDs material table (`materials_data.py`): 137 materials, each with a type and a grade from 1
(very common) to 5 (very rare). The game holds at most 300, 250, 200, 150 and 100 of a grade 1 to 5 material, so a count is never taken above
that, and `full()` lists what is at the limit. A material the table does not know (a new one) is still tracked, under the name and category
the game gave, with no grade and no limit.

The counts are saved when something changes, but not more than once every few seconds (a mining or scanning burst can send many events);
`flush()` writes what is waiting."""
from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass
from typing import Any, Callable, Dict, Iterable, List, Mapping, Optional, Tuple

from . import commander_data
from .materials_data import MATERIAL_ROWS

try:
    from config import appname
except ImportError:  # unit tests outside EDMC
    appname = "EDMarketConnector"

plugin_name = os.path.basename(os.path.dirname(__file__))
logger = logging.getLogger(f"{appname}.{plugin_name}")

STATE_FILENAME = "materials.json"
TYPES = ("Raw", "Manufactured", "Encoded")
OTHER = "Other"
CAPS = {1: 300, 2: 250, 3: 200, 4: 150, 5: 100}    # what the game lets you hold of a grade 1..5 material
SAVE_EVERY_S = 5.0
MAX_NAME = 80          # a material name read from a file or an event is cut to this
MAX_UNKNOWN = 200      # materials the table does not know that are remembered; past it the newest are not tracked


@dataclass(frozen=True)
class Material:
    key: str       # the journal's name, lower case
    name: str      # the display name
    type: str      # Raw, Manufactured, Encoded, or Other for one the table does not know
    grade: int     # 1 very common .. 5 very rare; 0 when not known

    @property
    def cap(self) -> int:
        """The most the game lets you hold; 0 when the grade is not known."""
        return CAPS.get(self.grade, 0)


@dataclass(frozen=True)
class Held:
    material: Material
    count: int

    @property
    def room(self) -> int:
        return max(0, self.material.cap - self.count) if self.material.cap else 0

    @property
    def is_full(self) -> bool:
        return bool(self.material.cap) and self.count >= self.material.cap


@dataclass(frozen=True)
class GradeLine:
    """What is held of one type at one grade: pieces, how many different materials, how many of them are at the limit."""
    grade: int
    pieces: int
    materials: int
    at_limit: int


@dataclass(frozen=True)
class Change:
    """The last single-material change the journal reported, for the panel row."""
    name: str
    delta: int
    total: int


CATALOG: Dict[str, Material] = {
    symbol.lower(): Material(symbol.lower(), name, kind, grade) for symbol, name, kind, grade in MATERIAL_ROWS}


def key_for(name: Any) -> str:
    """The key a journal material name is kept under: lower case, and a `$gold_name;` style token reduced to `gold`."""
    text = str(name or "").strip().lower()
    if text.startswith("$") and text.endswith(";"):
        text = text[1:-1]
        if text.endswith("_name"):
            text = text[:-5]
    return text


def _clip(text: Any) -> str:
    return " ".join(str(text or "").split())[:MAX_NAME]


def _int(value: Any) -> int:
    return int(value) if isinstance(value, (int, float)) and not isinstance(value, bool) and value >= 0 else 0


def _entries(entry: Mapping[str, Any]) -> List[Tuple[str, str, str, int]]:
    """What a journal event adds (+) or takes away (-): [(name, category, localised name, change)], in the order given. Empty for any
    event that does not change materials, and for entries that are damaged."""
    event = entry.get("event")
    out: List[Tuple[str, str, str, int]] = []

    def add(name: Any, category: Any, localised: Any, change: int) -> None:
        if name and change:
            out.append((str(name), str(category or ""), str(localised or ""), change))

    def listed(items: Any, sign: int, default_category: str = "") -> None:
        for item in items if isinstance(items, list) else []:
            if isinstance(item, Mapping):
                add(item.get("Name"), item.get("Category") or default_category, item.get("Name_Localised"), sign * _int(item.get("Count")))

    if event == "MaterialCollected":
        add(entry.get("Name"), entry.get("Category"), entry.get("Name_Localised"), _int(entry.get("Count")))
    elif event == "MaterialDiscarded":
        add(entry.get("Name"), entry.get("Category"), entry.get("Name_Localised"), -_int(entry.get("Count")))
    elif event == "MaterialTrade":
        for side, sign in (("Paid", -1), ("Received", 1)):
            part = entry.get(side)
            if isinstance(part, Mapping):
                add(part.get("Material"), part.get("Category"), part.get("Material_Localised"), sign * _int(part.get("Quantity")))
    elif event == "Synthesis":
        listed(entry.get("Materials"), -1)
    elif event == "EngineerCraft":
        ingredients = entry.get("Ingredients")
        if isinstance(ingredients, Mapping):      # the older shape: {"iron": 3}
            for name, count in ingredients.items():
                add(name, "", "", -_int(count))
        else:
            listed(ingredients, -1)
    elif event == "TechnologyBroker":
        listed(entry.get("Materials"), -1)
    elif event == "MissionCompleted":
        listed(entry.get("MaterialsReward"), 1)
    elif event == "EngineerContribution" and entry.get("Type") == "Material":
        add(entry.get("Material"), entry.get("Category"), entry.get("Material_Localised"), -_int(entry.get("Quantity")))
    return out


def _empty() -> Dict[str, Any]:
    return {"counts": {}, "unknown": {}}


def _is_legacy(_raw: Any) -> bool:
    return False   # the file is new; nothing older to claim


class MaterialBook:
    """The commander's materials. Constructed empty; `load(plugin_dir)` once at start-up and `set_commander(cmdr)` whenever the commander is
    known or changes."""

    def __init__(self, clock: Callable[[], float] = time.monotonic) -> None:
        self._store = commander_data.new_store()
        self._plugin_dir: Optional[str] = None
        self._cmdr = ""
        self._clock = clock
        self._counts: Dict[str, int] = {}
        self._unknown: Dict[str, Material] = {}    # materials the table does not know, by key
        self._last: Optional[Change] = None
        self._listed = False          # the login list (or EDMC's totals) has been taken for this commander in this run
        self._dirty = False
        self._saved_at = -SAVE_EVERY_S
        self._listeners: List[Callable[[], None]] = []

    # --- loading and saving --------------------------------------------------------------------------------------

    def load(self, plugin_dir: str) -> None:
        self._plugin_dir = plugin_dir
        self._store = commander_data.read(os.path.join(plugin_dir, STATE_FILENAME), _is_legacy)
        self._reload()

    def set_commander(self, cmdr: str) -> bool:
        """True when this changed whose materials are showing."""
        cmdr = str(cmdr or "").strip()
        if not cmdr or commander_data.key_for(cmdr) == commander_data.key_for(self._cmdr):
            return False
        self.flush()
        self._cmdr = cmdr
        self._reload()
        return True

    def _reload(self) -> None:
        self._counts, self._unknown, self._last, self._listed = {}, {}, None, False
        if self._cmdr:
            payload = commander_data.payload_for(self._store, self._cmdr, _empty)
            if isinstance(payload, dict):
                raw_unknown = payload.get("unknown") if isinstance(payload.get("unknown"), dict) else {}
                for key, info in raw_unknown.items():
                    if isinstance(key, str) and isinstance(info, list) and len(info) == 2 and key not in CATALOG:
                        kind = info[1] if info[1] in TYPES else OTHER
                        self._unknown[key] = Material(key, _clip(info[0]) or key, kind, 0)
                raw_counts = payload.get("counts") if isinstance(payload.get("counts"), dict) else {}
                for key, count in raw_counts.items():
                    if isinstance(key, str) and (key in CATALOG or key in self._unknown) and _int(count):
                        self._counts[key] = self._limited(key, _int(count))
        self._dirty = False
        self._changed()

    def _payload(self) -> Dict[str, Any]:
        used = {key: [m.name, m.type] for key, m in self._unknown.items() if key in self._counts}
        return {"counts": dict(self._counts), "unknown": used}

    def _save(self, force: bool = False) -> None:
        if not self._dirty or not self._cmdr or self._plugin_dir is None:
            return
        if not force and self._clock() - self._saved_at < SAVE_EVERY_S:
            return
        commander_data.put(self._store, self._cmdr, self._payload())
        commander_data.write(os.path.join(self._plugin_dir, STATE_FILENAME), self._store)
        self._dirty = False
        self._saved_at = self._clock()

    def flush(self) -> None:
        """Write any change still waiting (call when EDMC closes or the commander changes)."""
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
                logger.debug("Materials listener failed", exc_info=True)

    # --- reading ---------------------------------------------------------------------------------------------------

    @property
    def commander(self) -> str:
        return self._cmdr

    @property
    def ready(self) -> bool:
        return bool(self._cmdr)

    @property
    def has_counts(self) -> bool:
        """The login list (or EDMC's totals) has been taken, so the counts can be trusted rather than being only what was saved."""
        return self._listed

    @property
    def last(self) -> Optional[Change]:
        return self._last

    def _material(self, key: str) -> Material:
        return CATALOG.get(key) or self._unknown.get(key) or Material(key, key, OTHER, 0)

    def held(self) -> List[Held]:
        """Every material with a count above 0: Raw, Manufactured, Encoded, then others; grade 1 first within a type, then by name."""
        order = {kind: i for i, kind in enumerate((*TYPES, OTHER))}
        rows = [Held(self._material(key), count) for key, count in self._counts.items() if count > 0]
        return sorted(rows, key=lambda h: (order.get(h.material.type, 9), h.material.grade, h.material.name.lower()))

    def count_of(self, name: Any) -> int:
        return self._counts.get(key_for(name), 0)

    def totals(self) -> Dict[str, int]:
        """Pieces held of each type (Raw, Manufactured, Encoded) and of the unknown ones under Other."""
        out = {kind: 0 for kind in TYPES}
        for held in self.held():
            out[held.material.type] = out.get(held.material.type, 0) + held.count
        return out

    def grade_summary(self, kind: str) -> List[GradeLine]:
        """What is held of `kind` (Raw, Manufactured or Encoded) at grades 1 to 5, a line for each grade that has anything, lowest first. Materials
        with no known grade are left out."""
        out = []
        for grade in sorted(CAPS):
            mine = [h for h in self.held() if h.material.type == kind and h.material.grade == grade]
            if mine:
                out.append(GradeLine(grade, sum(h.count for h in mine), len(mine), sum(1 for h in mine if h.is_full)))
        return out

    def full(self) -> List[Held]:
        """Materials at the most the game lets you hold: collecting more of them is wasted."""
        return [h for h in self.held() if h.is_full]

    # --- changing --------------------------------------------------------------------------------------------------

    def _limited(self, key: str, count: int) -> int:
        cap = self._material(key).cap
        return min(count, cap) if cap else count

    def _know(self, name: str, category: str, localised: str) -> Optional[str]:
        """The key a name is kept under, remembering a material the table does not know; None if there is no room to track one more."""
        key = key_for(name)
        if not key or key in CATALOG or key in self._unknown:
            return key or None
        if len(self._unknown) >= MAX_UNKNOWN:
            return None
        kind = next((t for t in TYPES if t.lower() == str(category).strip().lower()), OTHER)
        self._unknown[key] = Material(key, _clip(localised) or _clip(name) or key, kind, 0)
        return key

    def _replace(self, counts: Mapping[str, int]) -> None:
        self._counts = {key: n for key, n in counts.items() if n > 0}
        self._listed = True

    def apply_event(self, entry: Mapping[str, Any], state: Optional[Mapping[str, Any]] = None) -> bool:
        """Take one journal event; True when the counts changed. `state` is EDMC's running state, used once, when no login list has been
        taken yet this run (WNTB started in the middle of a session)."""
        if not self.ready:
            return False
        event = entry.get("event")
        changed = False
        if event == "Materials":
            counts: Dict[str, int] = {}
            for kind in TYPES:
                for item in entry.get(kind) if isinstance(entry.get(kind), list) else []:
                    if not isinstance(item, Mapping):
                        continue
                    key = self._know(item.get("Name"), kind, item.get("Name_Localised"))
                    if key:
                        counts[key] = self._limited(key, _int(item.get("Count")))
            self._replace(counts)
            self._last = None
            changed = True
        else:
            if not self._listed and state is not None and self._take_state(state):
                changed = True   # EDMC has already counted this event in its totals, so it is not applied again
            else:
                for name, category, localised, delta in _entries(entry):
                    key = self._know(name, category, localised)
                    if key is None:
                        continue
                    total = self._limited(key, max(0, self._counts.get(key, 0) + delta))
                    if total != self._counts.get(key, 0):
                        changed = True
                    if total > 0:
                        self._counts[key] = total
                    else:
                        self._counts.pop(key, None)
                    if event in ("MaterialCollected", "MaterialDiscarded"):
                        self._last = Change(self._material(key).name, delta, total)
        if changed:
            self._dirty = True
            self._save(force=event == "Materials")
            self._changed()
        return changed

    def _take_state(self, state: Mapping[str, Any]) -> bool:
        """EDMC's running totals (its state's Raw, Manufactured and Encoded: {name: count}); True when they held anything."""
        counts: Dict[str, int] = {}
        seen = False
        for kind in TYPES:
            part = state.get(kind)
            if not isinstance(part, Mapping):
                continue
            for name, count in part.items():
                key = self._know(name, kind, "")
                if key:
                    seen = True
                    counts[key] = self._limited(key, _int(count))
        if seen:
            self._replace(counts)
        return seen
