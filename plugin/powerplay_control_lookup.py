"""Live lookup of a system's current Powerplay controlling Power, via
Spansh's public system API (https://spansh.co.uk/api/system/<id64>) - the
only community data source found that tracks current Powerplay control for
arbitrary systems (EDSM's system API does not expose it).

Unlike the rest of the Rare Goods Finder this is a network call at refresh
time rather than baked-in data, since control changes with the weekly
Powerplay cycle while a rare good's origin system never moves. Results are
cached for the life of the process (id64 -> Power name, or None for a
resolved-but-unclaimed system) so a redraw never refetches a system it
already has an answer for. Failed lookups are cached as None too, which
keeps a dead network from being hammered on every refresh; restarting EDMC
retries them.

Lookups run in a background thread pool and never touch Tkinter; callers
marshal results onto the main thread themselves. Uses urllib like the rest
of WNTB.
"""

from __future__ import annotations

import json
import logging
import threading
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable, Dict, Iterable, Optional, Tuple

from . import http_identity

logger = logging.getLogger(__name__)

SYSTEM_URL = "https://spansh.co.uk/api/system/{id64}"
REQUEST_TIMEOUT_S = 8
MAX_WORKERS = 5
_USER_AGENT = http_identity.user_agent("rare-goods")

_cache_lock = threading.Lock()
_cache: Dict[int, Optional[str]] = {}


def cached(id64: int) -> Tuple[bool, Optional[str]]:
    """(True, power) if `id64` has already been resolved this run (`power`
    is None for a resolved-but-unclaimed system), else (False, None)."""
    with _cache_lock:
        if id64 in _cache:
            return True, _cache[id64]
    return False, None


def _fetch_one(id64: int) -> Optional[str]:
    power: Optional[str] = None
    try:
        request = urllib.request.Request(
            SYSTEM_URL.format(id64=id64), headers={"User-Agent": _USER_AGENT},
        )
        with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT_S) as response:
            data = json.loads(response.read().decode("utf-8"))
        power = (data.get("record") or {}).get("controlling_power") or None
    except Exception:
        logger.debug("Spansh controlling-power lookup failed for id64=%s", id64, exc_info=True)

    with _cache_lock:
        _cache[id64] = power
    return power


def fetch_missing(id64s: Iterable[int], on_result: Callable[[int, Optional[str]], None]) -> None:
    """Looks up the controlling Power for each of `id64s` not already
    cached, calling `on_result(id64, power_or_none)` from a background
    thread as each completes - not necessarily in order. Does nothing (no
    thread spawned) if every id64 is already cached. Callers must marshal
    onto the Tk main thread themselves before touching widgets."""
    with _cache_lock:
        pending = [id64 for id64 in id64s if id64 not in _cache]
    if not pending:
        return

    def worker() -> None:
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
            futures = {pool.submit(_fetch_one, id64): id64 for id64 in pending}
            for future in as_completed(futures):
                on_result(futures[future], future.result())

    threading.Thread(target=worker, name="WNTB-rares-power-lookup", daemon=True).start()
