"""
Per-system/per-boxel survey findings: notable bodies and boxel-level rollups.

Boxel Survey's walker state (`boxel_state.py`) only ever tracked bare
system-name strings — enough to skip re-visiting, not enough to answer "what
did I actually find out there" or "have I surveyed this boxel before." This
module is a separate, optional log for that: which bodies turned out to be
Earthlike/water/ammonia worlds, terraformable, or carrying biological
signals, grouped by system and by boxel (`sector`+`cube_id`).

Deliberately logs *notable* bodies only, not every scanned body — the goal is
a highlights log a human can actually read (directly, or via the CSV export),
not a full personal exploration database. `bodies_scanned` is still counted
for every body regardless of notability, so "how much of this boxel have I
actually looked at" stays answerable.

Kept pure (no EDMC/Tk imports) so it's unit-testable the same way `boxel.py`
is — `boxel_survey.py` is the only place that wires this up to real journal
events.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

try:
    from config import appname
except ImportError:
    # EDMC's `config` module isn't on sys.path outside a running EDMC
    # instance (e.g. under `python -m unittest`) — this module's actual
    # logic has no other EDMC dependency, so fall back to a plain name
    # rather than make the whole module require the EDMC runtime to import.
    appname = "EDMarketConnector"

plugin_name = os.path.basename(os.path.dirname(__file__))
logger = logging.getLogger(f"{appname}.{plugin_name}")

LOG_FILENAME = "survey_log.json"

# PlanetClass (from the Scan journal event) -> notable tag.
NOTABLE_PLANET_CLASSES = {
    "Earthlike body": "elw",
    "Water world": "ww",
    "Ammonia world": "aw",
}

# The Type string FSSBodySignals/SAASignalsFound use for biological signals.
# Unlocalized and stable across game languages, unlike Type_Localised.
BIO_SIGNAL_TYPE = "$SAA_SignalType_Biological;"

EXPORT_FIELDNAMES = [
    "system",
    "boxel",
    "body",
    "tags",
    "planet_class",
    "distance_ls",
    "bio_signal_count",
    "first_seen",
]


def boxel_key(sector: str, cube_id: str) -> str:
    """Build the boxel-grouping key from a parsed procedural name's parts."""
    return f"{sector}|{cube_id}"


@dataclass
class NotableBody:
    """A single body worth remembering, and why."""

    body: str
    tags: List[str] = field(default_factory=list)
    planet_class: Optional[str] = None
    distance_ls: Optional[float] = None
    bio_signal_count: int = 0

    def add_tag(self, tag: str) -> None:
        if tag not in self.tags:
            self.tags.append(tag)


@dataclass
class SystemEntry:
    """Everything recorded for one system: scan progress and notable finds."""

    boxel_key: Optional[str] = None
    bodies_scanned: int = 0
    first_seen: str = ""
    notable_bodies: Dict[str, NotableBody] = field(default_factory=dict)


class SurveyLog:
    """In-memory survey log. Persisted via `load_log`/`save_log` below."""

    def __init__(self) -> None:
        self._systems: Dict[str, SystemEntry] = {}

    def record_scan(
        self,
        system: str,
        body: str,
        *,
        boxel_key: Optional[str],
        planet_class: Optional[str],
        terraform_state: Optional[str],
        distance_ls: Optional[float],
    ) -> None:
        """Record one `Scan` journal event."""
        entry = self._get_or_create_system(system, boxel_key)
        entry.bodies_scanned += 1

        tags: List[str] = []
        if planet_class in NOTABLE_PLANET_CLASSES:
            tags.append(NOTABLE_PLANET_CLASSES[planet_class])
        if terraform_state == "Terraformable":
            tags.append("terraformable")
        if not tags:
            return

        notable = entry.notable_bodies.setdefault(body, NotableBody(body=body))
        notable.planet_class = planet_class
        notable.distance_ls = distance_ls
        for tag in tags:
            notable.add_tag(tag)

    def record_signals(
        self, system: str, body: str, *, boxel_key: Optional[str], bio_signal_count: int
    ) -> None:
        """Record one `FSSBodySignals`/`SAASignalsFound` journal event."""
        if bio_signal_count <= 0:
            return
        entry = self._get_or_create_system(system, boxel_key)
        notable = entry.notable_bodies.setdefault(body, NotableBody(body=body))
        notable.add_tag("bio")
        notable.bio_signal_count = max(notable.bio_signal_count, bio_signal_count)

    def _get_or_create_system(self, system: str, boxel_key: Optional[str]) -> SystemEntry:
        entry = self._systems.get(system)
        if entry is None:
            entry = SystemEntry(
                boxel_key=boxel_key, first_seen=datetime.now(timezone.utc).isoformat()
            )
            self._systems[system] = entry
        elif boxel_key is not None and entry.boxel_key is None:
            # E.g. the system was first seen via a Scan before we'd confirmed
            # its procedural shape; backfill once we know it.
            entry.boxel_key = boxel_key
        return entry

    def boxel_stats(self, key: str) -> Dict[str, int]:
        """Aggregate counts for one boxel, computed fresh (nothing stored redundantly)."""
        stats = {"systems": 0, "bodies_scanned": 0, "elw": 0, "ww": 0, "aw": 0, "terraformable": 0, "bio": 0}
        for entry in self._systems.values():
            if entry.boxel_key != key:
                continue
            stats["systems"] += 1
            stats["bodies_scanned"] += entry.bodies_scanned
            for notable in entry.notable_bodies.values():
                for tag in notable.tags:
                    stats[tag] = stats.get(tag, 0) + 1
        return stats

    def export_rows(self) -> List[Dict[str, Any]]:
        """Flatten to one row per notable body, for CSV export."""
        rows: List[Dict[str, Any]] = []
        for system, entry in self._systems.items():
            for notable in entry.notable_bodies.values():
                rows.append(
                    {
                        "system": system,
                        "boxel": entry.boxel_key or "",
                        "body": notable.body,
                        "tags": ",".join(notable.tags),
                        "planet_class": notable.planet_class or "",
                        "distance_ls": notable.distance_ls if notable.distance_ls is not None else "",
                        "bio_signal_count": notable.bio_signal_count,
                        "first_seen": entry.first_seen,
                    }
                )
        return rows

    def to_dict(self) -> Dict[str, Any]:
        return {
            system: {
                "boxel_key": entry.boxel_key,
                "bodies_scanned": entry.bodies_scanned,
                "first_seen": entry.first_seen,
                "notable_bodies": {name: asdict(nb) for name, nb in entry.notable_bodies.items()},
            }
            for system, entry in self._systems.items()
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SurveyLog":
        log = cls()
        for system, raw in data.items():
            entry = SystemEntry(
                boxel_key=raw.get("boxel_key"),
                bodies_scanned=raw.get("bodies_scanned", 0),
                first_seen=raw.get("first_seen", ""),
            )
            for name, nb_raw in raw.get("notable_bodies", {}).items():
                entry.notable_bodies[name] = NotableBody(
                    body=nb_raw.get("body", name),
                    tags=list(nb_raw.get("tags", [])),
                    planet_class=nb_raw.get("planet_class"),
                    distance_ls=nb_raw.get("distance_ls"),
                    bio_signal_count=nb_raw.get("bio_signal_count", 0),
                )
            log._systems[system] = entry
        return log


def load_log(plugin_dir: str) -> SurveyLog:
    """Load the persisted survey log, or an empty one if there's nothing saved / it's unreadable."""
    path = os.path.join(plugin_dir, LOG_FILENAME)
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        return SurveyLog.from_dict(data)
    except FileNotFoundError:
        return SurveyLog()
    except (OSError, json.JSONDecodeError, TypeError, AttributeError) as exc:
        logger.warning("Could not read %s: %s", path, exc)
        return SurveyLog()


def save_log(plugin_dir: str, log: SurveyLog) -> None:
    """Save the log, writing to a temp file and replacing atomically (same as boxel_state.py)."""
    path = os.path.join(plugin_dir, LOG_FILENAME)
    tmp_path = f"{path}.tmp"
    try:
        with open(tmp_path, "w", encoding="utf-8") as fh:
            json.dump(log.to_dict(), fh, indent=2, sort_keys=True)
        os.replace(tmp_path, path)
    except OSError as exc:
        logger.warning("Could not write %s: %s", path, exc)
