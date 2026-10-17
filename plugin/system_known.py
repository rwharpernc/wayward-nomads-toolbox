"""What other commanders have already found in a system, from Spansh's public system API, for the System targets card.

The card otherwise knows only what you have scanned yourself, so a system others surveyed long ago reads as having nothing in it. This asks Spansh once per
system (`GET https://spansh.co.uk/api/system/<id64>`, which sends the system's number and nothing else) and keeps, for each body, the biology Spansh lists on it
(species, how many, the reward), the points of interest (a wreck, a beacon, a Guardian site, ...) and Spansh's estimated scan and mapping values. The shapes
were checked against real responses (2026-10-17): the record has a `bodies` list; a body has `name`, `type` ("Star" or "Planet"), `subtype`, `distance_to_arrival`,
`terraforming_state`, `estimated_scan_value`, `estimated_mapping_value`, `landmark_value` and `landmarks`, each landmark having `type`, `subtype`, `count` and
`value`. A biological landmark has the genus as its `type`, the species as its `subtype` and a reward as its `value`; a point of interest has a value of 0.
Spansh's body `id` is a 64-bit number, not the journal's BodyID, so bodies are matched to the journal's by name. If Spansh changes it, this is the one place to fix.

Opt-in (Settings → Overlays → System targets), run on a background thread, never raises: a system Spansh does not have, or a failed request, gives no sites.
Nothing is saved: a good answer is kept in memory for the session. No Tk, no overlay.
"""

from __future__ import annotations

import json
import logging
import os
import threading
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

try:
    from config import appname
except ImportError:   # unit tests outside EDMC
    appname = "EDMarketConnector"

from . import http_identity

plugin_name = os.path.basename(os.path.dirname(__file__))
logger = logging.getLogger(f"{appname}.{plugin_name}")

SYSTEM_URL = "https://spansh.co.uk/api/system/{id64}"
REQUEST_TIMEOUT_S = 10
MAX_RESPONSE_BYTES = 16 * 1024 * 1024        # a system with hundreds of bodies is a few MB; anything past this is not a system record
# Landmarks that are scenery or services, not something to go and see (a settlement or a geyser is on almost every world).
SCENERY_TYPES = frozenset({"surface station", "fumarole", "geyser", "gas vent", "lava spout"})
POI_LABELS = {"tourist beacon": "Beacon", "wrecked ship": "Wreck", "crashed ship": "Crash", "guardian ruin": "Guardian ruin",
              "guardian structure": "Guardian structure", "thargoid structure": "Thargoid site", "barnacle": "Barnacle"}


@dataclass
class KnownSite:
    """One body as Spansh knows it: what is on it worth a trip."""
    name: str
    short: str = ""
    subtype: str = ""
    distance_ls: Optional[float] = None
    terraformable: bool = False
    scan_value: int = 0
    map_value: int = 0
    species: List[Tuple[str, int, int]] = field(default_factory=list)      # (species, how many, reward each), best first
    pois: List[Tuple[str, int]] = field(default_factory=list)              # (what, how many)

    @property
    def bio_value(self) -> int:
        """The most the biology here pays: every listed organism at its reward, once each (the first of a species is what a reward pays)."""
        return sum(value for _name, _count, value in self.species)

    @property
    def interesting(self) -> bool:
        return bool(self.species or self.pois)


def _int(value: Any) -> int:
    return int(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else 0


def parse(record: Any, system: str = "") -> List[KnownSite]:
    """The sites in Spansh's system `record` (the API's `record`): every body with biology or a point of interest, plus the planets with a value, best first.
    Anything malformed is skipped rather than failing the whole record."""
    bodies = record.get("bodies") if isinstance(record, dict) else None
    if not isinstance(bodies, list):
        return []
    sites: List[KnownSite] = []
    for body in bodies:
        if not isinstance(body, dict) or body.get("type") != "Planet" or not body.get("name"):
            continue
        name = str(body["name"])
        distance = body.get("distance_to_arrival")
        site = KnownSite(name=name, short=_short(name, system), subtype=str(body.get("subtype") or ""),
                         distance_ls=float(distance) if isinstance(distance, (int, float)) and not isinstance(distance, bool) else None,
                         terraformable=str(body.get("terraforming_state") or "").casefold().startswith("candidate"),
                         scan_value=_int(body.get("estimated_scan_value")), map_value=_int(body.get("estimated_mapping_value")))
        pois: Dict[str, int] = {}
        species: Dict[str, List[int]] = {}
        for landmark in body.get("landmarks") or []:
            if not isinstance(landmark, dict):
                continue
            kind, subtype = str(landmark.get("type") or "").strip(), str(landmark.get("subtype") or "").strip()
            count, value = max(1, _int(landmark.get("count"))), _int(landmark.get("value"))
            if value > 0:
                entry = species.setdefault(subtype or kind, [0, value])
                entry[0] += count
            elif kind.casefold() not in SCENERY_TYPES and kind:
                label = POI_LABELS.get(kind.casefold(), subtype or kind)
                pois[label] = pois.get(label, 0) + count
        site.species = sorted(((n, c, v) for n, (c, v) in species.items()), key=lambda item: -item[2])
        site.pois = sorted(pois.items(), key=lambda item: item[0])
        sites.append(site)
    return sorted(sites, key=lambda s: (-s.bio_value, -s.map_value))


def _short(name: str, system: str) -> str:
    if system and name.casefold().startswith(system.casefold()):
        return name[len(system):].strip() or "Star"
    return name


def fetch(id64: int) -> Optional[Dict[str, Any]]:
    """Spansh's record for the system with this number: {} when Spansh does not have it (404), None when the request failed."""
    try:
        request = urllib.request.Request(SYSTEM_URL.format(id64=int(id64)), headers={"User-Agent": http_identity.user_agent("system-known")})
        with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT_S) as response:
            data = json.loads(response.read(MAX_RESPONSE_BYTES).decode("utf-8"))
    except urllib.error.HTTPError as err:
        if err.code == 404:
            return {}
        logger.debug("Spansh system lookup failed for %s", id64, exc_info=True)
        return None
    except Exception:
        logger.debug("Spansh system lookup failed for %s", id64, exc_info=True)
        return None
    record = data.get("record") if isinstance(data, dict) else None
    return record if isinstance(record, dict) else None


_cache: Dict[int, List[KnownSite]] = {}      # system number -> its sites (empty when Spansh has none), for this session
_cache_lock = threading.Lock()


def cached(id64: int) -> Optional[List[KnownSite]]:
    with _cache_lock:
        return _cache.get(id64)


def lookup(id64: int, system: str) -> Optional[List[KnownSite]]:
    """The sites in a system, asking Spansh once per system per session. [] when Spansh has none; None when the request failed (not remembered, so a later
    event tries again)."""
    have = cached(id64)
    if have is not None:
        return have
    record = fetch(id64)
    if record is None:
        return None
    sites = parse(record, system)
    with _cache_lock:
        _cache[id64] = sites
    return sites
