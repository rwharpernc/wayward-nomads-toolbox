"""The catalog of every codex entry that exists (as far as Canonn knows),
used by the Codex Completionist window's "Not found" tab - the found side
comes from codex_completionist.py's journal tally.

Source: Canonn Interstellar Research's public codex reference endpoint, one
unauthenticated GET that
returns every entry keyed by entry id. Confirmed live (2026-10-01): ~1,070
entries / ~650 KB; each carries `entryid`, `name` (the same raw
`$Codex_Ent_..._Name;` string the journal's CodexEntry event uses - that's
what lets the two sides be diffed), `english_name`, `category`,
`sub_category`, `sub_class` (genus/type), `platform` (legacy/odyssey) and
`hud_category`. It covers Biology, Civilisations and Stellar Bodies; it does
NOT list geological or anomaly codex entries, so "not found" is only ever
"not found among those".

Cached next to the plugin (CACHE_FILENAME, listed in update.py's
`_OWN_DATA_FILES`) and re-fetched when older than MAX_AGE_DAYS or on demand,
so the window opens instantly and works offline after the first fetch.

Pure of EDMC imports so it is unit-testable (tests/test_codex_catalog.py).
`fetch_catalog` does network I/O - call it off the Tk thread.
"""

from __future__ import annotations

import json
import os
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any, Iterable, List, Optional, Set

from . import http_identity

CATALOG_URL = "https://us-central1-canonn-api-236217.cloudfunctions.net/query/codex/ref?_limit=5000"
REFERENCE_SEARCH_URL = "https://canonn.science/?s={query}"
CACHE_FILENAME = "codex_catalog.json"
MAX_AGE_DAYS = 14
REQUEST_TIMEOUT_S = 30
_USER_AGENT = http_identity.user_agent("codex-catalog")

_CATEGORY_LABELS = {
    "$codex_category_biology;": "Biological",
    "$codex_category_civilisations;": "Civilisations",
    "$codex_category_stellarbodies;": "Stellar bodies",
}


@dataclass(frozen=True)
class CatalogEntry:
    name: str  # raw journal Name, e.g. "$Codex_Ent_Bacterial_01_Name;"
    entry_id: int
    english_name: str
    category: str  # display label
    sub_class: str  # genus / type, e.g. "Bacterial"
    platform: str  # "Odyssey" / "Legacy"


def category_label(raw: str) -> str:
    return _CATEGORY_LABELS.get(raw.strip().casefold(), raw.strip("$;").replace("Codex_Category_", "") or "Other")


def parse_catalog(raw: Any) -> List[CatalogEntry]:
    """Canonn's `{entryid: {...}}` mapping -> entries. Rows without a
    usable name are skipped rather than failing the whole catalog."""
    if not isinstance(raw, dict):
        raise ValueError(f"Unexpected codex catalog shape: {type(raw).__name__}")
    entries: List[CatalogEntry] = []
    for key, row in raw.items():
        if not isinstance(row, dict):
            continue
        name = row.get("name")
        english = row.get("english_name")
        if not isinstance(name, str) or not name or not isinstance(english, str) or not english:
            continue
        try:
            entry_id = int(row.get("entryid", key))
        except (TypeError, ValueError):
            entry_id = 0
        entries.append(CatalogEntry(
            name=name, entry_id=entry_id, english_name=english,
            category=category_label(str(row.get("category") or "")),
            sub_class=str(row.get("sub_class") or ""),
            platform=str(row.get("platform") or "").capitalize(),
        ))
    return entries


def fetch_catalog() -> List[CatalogEntry]:
    """Raises on any network/parse failure, or if nothing usable came back."""
    request = urllib.request.Request(CATALOG_URL, headers={"User-Agent": _USER_AGENT})
    with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT_S) as response:
        entries = parse_catalog(json.loads(response.read().decode("utf-8")))
    if not entries:
        raise ValueError("Canonn codex catalog came back empty")
    return entries


# --- cache ---------------------------------------------------------------

def load_cache(plugin_dir: str) -> Optional[List[CatalogEntry]]:
    try:
        with open(os.path.join(plugin_dir, CACHE_FILENAME), "r", encoding="utf-8") as fh:
            data = json.load(fh)
        return [CatalogEntry(**row) for row in data["entries"]] or None
    except (OSError, ValueError, KeyError, TypeError):
        return None


def save_cache(plugin_dir: str, entries: List[CatalogEntry]) -> None:
    path = os.path.join(plugin_dir, CACHE_FILENAME)
    tmp_path = f"{path}.tmp"
    payload = {"fetched_at": time.time(), "entries": [e.__dict__ for e in entries]}
    try:
        with open(tmp_path, "w", encoding="utf-8") as fh:
            json.dump(payload, fh)
        os.replace(tmp_path, path)
    except OSError:
        pass  # cache is an optimisation; the in-memory catalog still works


def cache_is_stale(plugin_dir: str, now: Optional[float] = None) -> bool:
    try:
        with open(os.path.join(plugin_dir, CACHE_FILENAME), "r", encoding="utf-8") as fh:
            fetched_at = float(json.load(fh)["fetched_at"])
    except (OSError, ValueError, KeyError, TypeError):
        return True
    return ((now if now is not None else time.time()) - fetched_at) > MAX_AGE_DAYS * 86400


# --- diff + links --------------------------------------------------------

def missing_entries(catalog: Iterable[CatalogEntry], found_names: Iterable[str],
                    found_ids: Iterable[int] = ()) -> List[CatalogEntry]:
    """Catalog entries the commander hasn't found. Matches on the raw name
    (case-insensitively) or on entry id, so either side being unknown is
    fine."""
    names: Set[str] = {n.casefold() for n in found_names}
    ids: Set[int] = {i for i in found_ids if i}
    return [e for e in catalog if e.name.casefold() not in names and not (e.entry_id and e.entry_id in ids)]


def reference_url(display_name: str) -> str:
    """A Canonn site search for the entry's name. Canonn has no stable
    per-entry page URL we can build, so a search is the link that works for
    every entry, found or not."""
    return REFERENCE_SEARCH_URL.format(query=urllib.parse.quote_plus(display_name))
