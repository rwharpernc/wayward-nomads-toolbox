"""
On-demand lookup against Canonn Interstellar Research's own published
Thargoid/Guardian site lists - the same public, unauthenticated Google
Sheets/Drive URLs Canonn publishes for those lists. Canonn has no
queryable "nearest POI" REST endpoint (unlike edastro.com's GEC API, see
gec_poi_edastro.py), so this module downloads the full list once, then
computes nearest client-side.

Confirmed via live calls:
- Thargoid sites: TSV, columns `type`, `raw system`, `x`, `y`, `z`,
  `instructions`, `url` (tab-separated, trailing `\r` per row).
- Guardian sites: a JSON array of objects with `system`, `x`, `y`, `z`,
  `instructions`, `url` (no `type` column - every entry is a Guardian
  beacon/site).

Two independent third-party downloads (~84 KB for Guardian sites as of this
writing) - each function below raises on its own failure so a caller can
treat "Thargoid list fetched, Guardian list failed" as a partial success
rather than an all-or-nothing failure.
"""

from __future__ import annotations

import csv
import io
import json
import math
import urllib.request
from dataclasses import dataclass
from typing import List, Optional, Tuple

THARGOID_SITES_URL = (
    "https://docs.google.com/spreadsheets/d/e/2PACX-1vRFRhsa3g0tpYFkqyBR2HrfUjXfjW6gSRnnDhFtVtPlWtpuNAHKujI5fH6Lnh3ctt0SAyNywnesv8H_"
    "/pub?gid=1675294629&single=true&output=tsv"
)
GUARDIAN_SITES_URL = "https://drive.google.com/uc?id=1m8q9lE4_cAI8CotM-oaEm5RWHeeJjoil"

REQUEST_TIMEOUT_S = 30
_USER_AGENT = "WNTB-canonn-poi-data"


@dataclass(frozen=True)
class CanonnPoi:
    category: str
    system: str
    x: float
    y: float
    z: float
    instructions: str
    url: Optional[str]


def _fetch_text(url: str) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
    with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT_S) as response:
        return response.read().decode("utf-8")


def fetch_thargoid_sites() -> List[CanonnPoi]:
    """Raises on any network/parse failure."""
    text = _fetch_text(THARGOID_SITES_URL)
    reader = csv.DictReader(io.StringIO(text), delimiter="\t")
    if reader.fieldnames is None:
        raise ValueError("Canonn Thargoid-sites TSV had no header row")
    # Tolerate either "system" or "raw system" as the column header - the
    # live sheet uses "raw system" as of this writing, but POI_API.md's own
    # generic spec documents plain "system".
    fields = {name.strip().lower(): name for name in reader.fieldnames}
    system_key = fields.get("raw system") or fields.get("system")
    if system_key is None or "x" not in fields or "y" not in fields or "z" not in fields:
        raise ValueError(f"Unexpected Canonn Thargoid-sites TSV columns: {reader.fieldnames!r}")

    pois: List[CanonnPoi] = []
    for row in reader:
        try:
            pois.append(CanonnPoi(
                category=row.get(fields.get("type", ""), "") or "Thargoid",
                system=row[system_key],
                x=float(row[fields["x"]]), y=float(row[fields["y"]]), z=float(row[fields["z"]]),
                instructions=row.get(fields.get("instructions", ""), "") or "",
                url=(row.get(fields.get("url", "")) or None),
            ))
        except (KeyError, ValueError):
            continue  # skip a malformed row rather than fail the whole fetch
    return pois


def fetch_guardian_sites() -> List[CanonnPoi]:
    """Raises on any network/parse failure."""
    text = _fetch_text(GUARDIAN_SITES_URL)
    data = json.loads(text)
    if not isinstance(data, list):
        raise ValueError(f"Unexpected Canonn Guardian-sites response shape: {type(data)!r}")

    pois: List[CanonnPoi] = []
    for row in data:
        if not isinstance(row, dict):
            continue
        try:
            pois.append(CanonnPoi(
                category="Guardian",
                system=row["system"],
                x=float(row["x"]), y=float(row["y"]), z=float(row["z"]),
                instructions=row.get("instructions") or "",
                url=row.get("url") or None,
            ))
        except (KeyError, ValueError, TypeError):
            continue  # skip a malformed row rather than fail the whole fetch
    return pois


def find_nearest(
    pois: List[CanonnPoi], x: float, y: float, z: float,
    exclude_systems: Optional[set] = None,
) -> Optional[Tuple[CanonnPoi, float]]:
    """Returns (poi, distance_ly) for the closest entry in `pois`, or None
    if `pois` is empty (or every entry is excluded).

    `exclude_systems`, if given, is a set of system names (matched
    case-insensitively) to skip - used by canonn_poi_panel.py to answer
    "nearest site I haven't already logged a matching codex entry for"
    rather than just "nearest site, period"."""
    excluded_lower = {s.lower() for s in exclude_systems} if exclude_systems else None
    nearest: Optional[CanonnPoi] = None
    nearest_distance = math.inf
    for poi in pois:
        if excluded_lower is not None and poi.system.lower() in excluded_lower:
            continue
        distance = math.sqrt((poi.x - x) ** 2 + (poi.y - y) ** 2 + (poi.z - z) ** 2)
        if distance < nearest_distance:
            nearest = poi
            nearest_distance = distance
    return (nearest, nearest_distance) if nearest is not None else None
