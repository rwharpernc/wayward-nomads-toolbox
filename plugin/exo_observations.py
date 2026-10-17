"""
A record of what lived where, kept so the species prediction can be checked against real finds over time. Pure logic plus a small JSON file
(`exo_observations.json` beside the plugin); nothing here is sent anywhere.

One record per body that has been sampled on: the body's conditions (type, atmosphere and its trace gases, gravity, temperature, pressure,
volcanism, the star, surface materials, the other body types in the system, and where in the galaxy), which genera the body's signals named, and
for each genus the species the sample confirmed, its color variant and which species the prediction listed at that moment. With that, the
questions worth asking later are answerable: how often the confirmed species was on the list, which finds the rules would not have predicted
(and under what conditions), which species turn up together on a body, and how wide a species' observed temperature and gravity are against
the range the data gives it. `scripts/analyze_exo_observations.py` prints those.

Unlike the rest of what WNTB saves about play, this file is deliberately **global, not per commander**: it holds facts about bodies (their
conditions and what grows on them), pools every commander's finds on the install so the prediction is checked against more data, and stores no
commander name, journal path or anything else that says who found what. A body two commanders both sampled is one record. A body sampled before
this file existed is filled in from each commander's saved per-body state as that commander is seen (`backfill`, safe to repeat: it never
replaces a live record); its prediction list is then what today's rules give for its saved conditions, and the record says so
(`"source": "backfill"`).
"""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence

from . import organic_scan
from .organic_scan import BodyConditions

try:
    from config import appname
except ImportError:  # unit tests outside EDMC
    appname = "EDMarketConnector"

plugin_name = os.path.basename(os.path.dirname(__file__))
logger = logging.getLogger(f"{appname}.{plugin_name}")

FILENAME = "exo_observations.json"
VERSION = 1
SOURCE_LIVE, SOURCE_BACKFILL = "live", "backfill"

Record = Dict[str, Any]
Predict = Callable[[str, BodyConditions], Sequence[str]]    # genus key, conditions -> the species keys the prediction lists


def body_key(system: Optional[str], body: str) -> str:
    return f"{system or ''}|{body}"


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def predicted_keys(genus_key: str, cond: BodyConditions) -> List[str]:
    """The species keys the prediction lists for `genus_key` on a body with `cond`, as the Biology card would."""
    return [species.species_key for species in organic_scan.predict_species(genus_key, cond)]


def _body_record(cond: BodyConditions, genera: Iterable[str], source: str, when: str) -> Record:
    return {
        "system": cond.system_name, "body": cond.body_name, "planet_class": cond.planet_class, "atmosphere": cond.atmosphere,
        "atmosphere_components": cond.atmosphere_components, "gravity_g": cond.gravity_g, "temperature_k": cond.temperature_k,
        "pressure_atm": cond.pressure_atm, "volcanism": cond.volcanism, "star_type": cond.star_type,
        "materials": list(cond.materials) if cond.materials is not None else None,
        "system_body_types": sorted(set(cond.system_body_types)) if cond.system_body_types else None,
        "galactic_position": list(cond.galactic_position) if cond.galactic_position else None,
        "genera": sorted(set(genera)), "species": {}, "first_seen": when, "source": source,
    }


class ObservationBook:
    """Every observation on this install. `load` at start-up; `record` on each confirmed species; `backfill` as each commander is seen."""

    def __init__(self) -> None:
        self._bodies: Dict[str, Record] = {}
        self._plugin_dir: Optional[str] = None

    # --- persistence ---------------------------------------------------------
    def load(self, plugin_dir: str) -> None:
        self._plugin_dir = plugin_dir
        self._bodies = {}
        try:
            with open(os.path.join(plugin_dir, FILENAME), "r", encoding="utf-8") as handle:
                raw = json.load(handle)
        except FileNotFoundError:
            return
        except (OSError, ValueError) as exc:
            logger.warning("Could not read %s: %s", FILENAME, exc)
            return
        bodies = raw.get("bodies") if isinstance(raw, dict) else None
        if isinstance(bodies, dict):
            self._bodies = {str(k): v for k, v in bodies.items() if isinstance(v, dict)}

    def save(self) -> None:
        """Write atomically; a failure is logged and never raised (a full disk must not stop the plugin)."""
        if not self._plugin_dir:
            return
        path = os.path.join(self._plugin_dir, FILENAME)
        tmp = f"{path}.tmp"
        try:
            with open(tmp, "w", encoding="utf-8") as handle:
                json.dump({"version": VERSION, "bodies": self._bodies}, handle, indent=2, sort_keys=True)
            os.replace(tmp, path)
        except OSError:
            logger.warning("Could not write %s", path, exc_info=True)

    # --- reading -------------------------------------------------------------
    def bodies(self) -> Dict[str, Record]:
        return self._bodies

    def count(self) -> int:
        return sum(len(r.get("species") or {}) for r in self._bodies.values())

    # --- writing -------------------------------------------------------------
    def clear(self) -> int:
        """Forget every recorded find (and every review of one), and save the empty file. Returns how many finds there were."""
        count = self.count()
        self._bodies = {}
        self.save()
        return count

    def record(self, cond: BodyConditions, genera: Iterable[str], genus_key: str, species_key: str, species_name: str,
               variant: Optional[str], predicted: Sequence[str], when: Optional[str] = None, source: str = SOURCE_LIVE,
               save: bool = True) -> bool:
        """Note that `species_key` was confirmed on the body `cond` describes. A live record refreshes the body's conditions (a later Scan can fill in a
        gap) and keeps a species as first seen; a backfilled one never replaces anything already there. Returns True when something was added or changed."""
        if not cond.body_name or not genus_key or not species_key:
            return False
        key = body_key(cond.system_name, cond.body_name)
        stamp = when if when is not None else _now()
        record = self._bodies.get(key)
        before = ((record or {}).get("species") or {}).get(genus_key)
        if source == SOURCE_BACKFILL and before is not None:
            return False
        fresh = _body_record(cond, genera, source, stamp)
        if record is None:
            record = self._bodies[key] = fresh
        else:
            fresh["species"], fresh["first_seen"], fresh["source"] = record.get("species") or {}, record.get("first_seen") or stamp, record.get("source") or source
            record.update(fresh)
        entry = {"species_key": species_key, "species": species_name, "variant": variant, "predicted": list(predicted), "seen": stamp}
        if before is not None:
            entry["seen"] = before.get("seen") or stamp
            entry["variant"] = variant or before.get("variant")
            if before.get("review"):
                entry["review"] = before["review"]          # a manual review survives a later sample of the same species
        record["species"][genus_key] = entry
        if save:
            self.save()
        return before != entry

    def set_review(self, key: str, genus_key: str, status: str, note: str) -> bool:
        """Keep a manual review of one find: `status` (one of exo_analysis.REVIEW_STATUSES, "" to clear) and a short `note`. Returns False when the find is not in
        the book. A review is about the prediction, so like the rest of the file it names no commander."""
        entry = ((self._bodies.get(key) or {}).get("species") or {}).get(genus_key)
        if entry is None:
            return False
        note = " ".join(str(note or "").split())[:500]
        if status or note:
            entry["review"] = {"status": status, "note": note, "at": _now()}
        else:
            entry.pop("review", None)
        self.save()
        return True

    def backfill(self, persisted: Dict[str, Dict[str, Any]], predict: Predict = predicted_keys) -> int:
        """Add what one commander's saved per-body state (`organic_scan_state.json`) holds and the book lacks. Returns the number of species noted.
        Repeating it is harmless: a species already in the book is left as it is."""
        if not persisted:
            return 0
        by_system: Dict[str, List[str]] = {}
        parsed: Dict[str, BodyConditions] = {}
        for key, stored in persisted.items():
            cond = _conditions_from(stored.get("conditions")) if isinstance(stored, dict) else None
            if cond is not None:
                parsed[key] = cond
                if cond.planet_class:
                    by_system.setdefault(cond.system_name or "", []).append(cond.planet_class)
        added = 0
        for key, cond in parsed.items():
            organisms = persisted[key].get("organisms") or {}
            cond.system_body_types = tuple(by_system.get(cond.system_name or "", ()))
            genera = persisted[key].get("genus_hints") or list(organisms)
            for genus_key, organism in organisms.items():
                if not isinstance(organism, dict) or not organism.get("species_key"):
                    continue
                if self.record(cond, genera, genus_key, organism["species_key"], organism.get("species_name") or organism["species_key"],
                               organism.get("variant_name"), predict(genus_key, cond), when="", source=SOURCE_BACKFILL, save=False):
                    added += 1
        if added:
            self.save()
            logger.info("Filled %d exobiology observation(s) from the saved per-body state", added)
        return added


def _conditions_from(raw: Any) -> Optional[BodyConditions]:
    """A BodyConditions from the saved dict, or None when it is missing or from an incompatible version."""
    if not isinstance(raw, dict):
        return None
    data = dict(raw)
    position = data.get("galactic_position")
    if isinstance(position, list) and len(position) == 3:
        data["galactic_position"] = tuple(position)
    for field in ("materials", "system_body_types"):
        if isinstance(data.get(field), list):
            data[field] = tuple(data[field])
    try:
        return BodyConditions(**data)
    except TypeError:
        return None
