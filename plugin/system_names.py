"""
Where the suggestions for a system-name box come from.

- **Local** (always on, no network): the systems you have been in this session (most recent first) and the names other parts of WNTB register
  with `add_source`: expedition stops, system notes. Nothing leaves the computer.
- **Spansh** (only when **Suggest system names from Spansh while typing** is ticked in Settings → Window, off until you tick it): the part of the
  name typed so far goes to Spansh's system-name search, which returns up to 20 systems that match. It is a real outbound call made as you type
  (after a short pause, from the third character), so it is opt-in and listed on the internet page. The answers are kept in memory for the
  session, so typing the same start again asks nothing.

The endpoint is undocumented; the shape was taken from Spansh's own web page and a live answer (2026-10-13):
`GET /api/systems/field_values/system_names?q=<text>` -> `{"min_max": [{"id64", "name", "x", "y", "z"}, ...], "values": ["<name>", ...]}`,
at most 20 names. `values` is used; a damaged answer gives no suggestions rather than an error.
"""
from __future__ import annotations

import json
import logging
import os
import threading
import urllib.error
import urllib.parse
import urllib.request
from collections import OrderedDict
from typing import Callable, Dict, Iterable, List, Optional

from config import appname, config

from . import http_identity

plugin_name = os.path.basename(os.path.dirname(__file__))
logger = logging.getLogger(f"{appname}.{plugin_name}")

CFG_REMOTE = "wntb_system_suggest_spansh"
URL = "https://spansh.co.uk/api/systems/field_values/system_names"
REQUEST_TIMEOUT_S = 6
MIN_LOCAL_CHARS = 2
MIN_REMOTE_CHARS = 3
MAX_REMEMBERED = 300     # systems kept from this session
MAX_CACHED = 400         # typed starts kept with their answers
MAX_NAME = 100
_USER_AGENT = http_identity.user_agent("system-name-suggestions")

_recent: "OrderedDict[str, str]" = OrderedDict()      # name_key -> name, most recent last
_sources: List[Callable[[], Iterable[str]]] = []
_cache: "OrderedDict[str, List[str]]" = OrderedDict()  # typed start (case-folded) -> names Spansh gave
_lock = threading.Lock()


def key(name: str) -> str:
    return " ".join(str(name or "").split()).casefold()


def remote_enabled() -> bool:
    return bool(config.get_bool(CFG_REMOTE, default=False))


def remember(name: str) -> None:
    """Note a system the commander has been in (called from the journal handler)."""
    clean = " ".join(str(name or "").split())[:MAX_NAME]
    if not clean:
        return
    with _lock:
        _recent.pop(key(clean), None)
        _recent[key(clean)] = clean
        while len(_recent) > MAX_REMEMBERED:
            _recent.popitem(last=False)


def add_source(source: Callable[[], Iterable[str]]) -> None:
    """Register a function that returns system names WNTB already holds (called each time suggestions are built, so it can change)."""
    if source not in _sources:
        _sources.append(source)


def local() -> List[str]:
    """Known system names, the ones from this session first (most recent first), then the registered sources', without repeats."""
    seen: Dict[str, str] = {}
    with _lock:
        recent = list(reversed(_recent.values()))
    for name in recent:
        seen.setdefault(key(name), name)
    for source in list(_sources):
        try:
            for name in source():
                clean = " ".join(str(name or "").split())
                if clean:
                    seen.setdefault(key(clean), clean[:MAX_NAME])
        except Exception:
            logger.debug("A system-name source failed", exc_info=True)
    return list(seen.values())


def cached(typed: str) -> List[str]:
    """What Spansh gave for the longest start of `typed` already asked about (so letters added since still have suggestions to filter)."""
    text = key(typed)
    with _lock:
        for length in range(len(text), MIN_REMOTE_CHARS - 1, -1):
            hit = _cache.get(text[:length])
            if hit is not None:
                return list(hit)
    return []


def is_cached(typed: str) -> bool:
    with _lock:
        return key(typed) in _cache


def parse(data: object) -> List[str]:
    """Spansh's answer -> names. Anything that is not the expected shape gives an empty list."""
    values = data.get("values") if isinstance(data, dict) else None
    out: List[str] = []
    for name in values if isinstance(values, list) else []:
        if isinstance(name, str) and name.strip():
            out.append(" ".join(name.split())[:MAX_NAME])
    return out


def fetch(typed: str) -> List[str]:
    """Ask Spansh for systems matching `typed` and keep the answer. Blocks, so callers run it off the main thread. Never raises: a failure
    (no network, Spansh down, a bad answer) is logged and gives no suggestions, and is not cached so a later try can succeed."""
    text = " ".join(str(typed or "").split())
    if len(text) < MIN_REMOTE_CHARS or not remote_enabled():
        return []
    request = urllib.request.Request(f"{URL}?{urllib.parse.urlencode({'q': text})}", headers={"User-Agent": _USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT_S) as response:
            names = parse(json.loads(response.read().decode("utf-8")))
    except (OSError, ValueError, urllib.error.URLError):
        logger.debug("Spansh system-name suggestions failed for %r", text, exc_info=True)
        return []
    with _lock:
        _cache[key(text)] = names
        while len(_cache) > MAX_CACHED:
            _cache.popitem(last=False)
    return names


def clear() -> None:
    """Forget everything remembered and cached (used by tests)."""
    with _lock:
        _recent.clear()
        _cache.clear()
    del _sources[:]
