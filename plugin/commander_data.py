"""
Per-commander data files: one JSON file holding a separate payload for every commander, never shared between them.

Several features keep data that belongs to one commander (the hotspots they saved, the ground they drove over, what
they found while surveying). Two commanders on one install must never see or change each other's, so each such file has
the shape

    {"version": 2, "commanders": {"<commander key>": {"name": "<name as seen>", "data": <payload>}},
     "legacy": <payload or null>, "meta": {<small facts about the file, e.g. when legacy data was first seen>}}

`legacy` holds data written before the file was per commander. It cannot be told whose it is, so the **first commander
seen claims it** (`payload_for`), after which it is gone; every later commander starts empty. This is the same rule
`region_sweep_state.py` and `waypoint_route_state.py` already follow.

The commander key is the name trimmed and case-folded (`key_for`): the journal sometimes writes `BOCHEAUX` where EDMC says
`Bocheaux`. A commander name is only ever a JSON key, never part of a file name, so nothing here depends on the file
system's case rules or forbidden characters (they differ on Windows and Linux). Files are UTF-8 and written to a temporary
file then `os.replace`d, which is atomic on both.
"""
from __future__ import annotations

import json
import logging
import os
from typing import Any, Callable, Dict, Optional

logger = logging.getLogger(__name__)

VERSION = 2

Store = Dict[str, Any]


def key_for(cmdr: Any) -> str:
    """The key a commander's data is stored under: name trimmed and case-folded; empty if there is no name."""
    return str(cmdr or "").strip().casefold()


def new_store() -> Store:
    return {"version": VERSION, "commanders": {}, "legacy": None, "meta": {}}


def read(path: str, is_legacy: Callable[[Any], bool]) -> Store:
    """The store in `path`. A file in the old shape (`is_legacy(raw)` is true) becomes the `legacy` payload; a missing,
    unreadable or unrecognised file gives an empty store."""
    try:
        with open(path, "r", encoding="utf-8") as handle:
            raw = json.load(handle)
    except FileNotFoundError:
        return new_store()
    except (OSError, ValueError) as exc:
        logger.warning("Could not read %s: %s", path, exc)
        return new_store()
    if isinstance(raw, dict) and raw.get("version") == VERSION and isinstance(raw.get("commanders"), dict):
        store = new_store()
        for key, entry in raw["commanders"].items():
            if isinstance(entry, dict) and "data" in entry:
                store["commanders"][str(key)] = {"name": str(entry.get("name") or key), "data": entry["data"]}
        store["legacy"] = raw.get("legacy")
        store["meta"] = raw["meta"] if isinstance(raw.get("meta"), dict) else {}
        return store
    if is_legacy(raw):
        store = new_store()
        store["legacy"] = raw
        return store
    return new_store()


def write(path: str, store: Store) -> None:
    """Save atomically; a failure is logged and never raised (a full disk must not stop the plugin)."""
    tmp = f"{path}.tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as handle:
            json.dump(store, handle, indent=2, sort_keys=True)
        os.replace(tmp, path)
    except OSError:
        logger.warning("Could not write %s", path, exc_info=True)


def payload_for(store: Store, cmdr: str, empty: Callable[[], Any]) -> Any:
    """This commander's payload, created if they have none. If the store still holds `legacy` data and this commander
    has nothing yet, they claim it (once). Returns a live reference: change it, then `write` the store."""
    key = key_for(cmdr)
    entry = store["commanders"].get(key)
    if entry is None:
        claimed = store.get("legacy")
        entry = {"name": str(cmdr).strip(), "data": claimed if claimed is not None else empty()}
        if claimed is not None:
            logger.info("Claiming data saved before per-commander storage for %s", cmdr)
            store["legacy"] = None
        store["commanders"][key] = entry
    return entry["data"]


def known(store: Store, cmdr: str) -> bool:
    return key_for(cmdr) in store["commanders"]


def put(store: Store, cmdr: str, payload: Any) -> None:
    """Set this commander's payload (without disturbing anyone else's)."""
    key = key_for(cmdr)
    if not key:
        return
    existing: Optional[Dict[str, Any]] = store["commanders"].get(key)
    store["commanders"][key] = {"name": existing["name"] if existing else str(cmdr).strip(), "data": payload}
