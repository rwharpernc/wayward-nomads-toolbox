"""JSON persistence for Powerplay session history, stored alongside the
plugin itself."""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict, List, Optional, Tuple

from config import appname

plugin_name = os.path.basename(os.path.dirname(__file__))
logger = logging.getLogger(f"{appname}.{plugin_name}")

FILENAME = "sessions.json"
# Keep history bounded so the file can't grow forever across years of play. The limit is **per commander**, so one
# commander's heavy use never pushes another's sessions out.
MAX_HISTORY = 200


def commander_of(session: Dict[str, Any]) -> str:
    """A session's commander as a comparison key (trimmed, case-folded; "" if it has none)."""
    return str(session.get("cmdr") or "").strip().casefold()


def sessions_of(history: List[Dict[str, Any]], cmdr: Any) -> List[Dict[str, Any]]:
    """The sessions in `history` that belong to `cmdr`, oldest first. With no commander named there is nobody to show
    them to, so none are returned (sessions saved before commanders were recorded can't be given to anyone)."""
    key = str(cmdr or "").strip().casefold()
    return [s for s in history if key and commander_of(s) == key]


def trim(history: List[Dict[str, Any]], limit: int = MAX_HISTORY) -> List[Dict[str, Any]]:
    """Keep each commander's newest `limit` sessions, in the original order."""
    seen: Dict[str, int] = {}
    keep = []
    for session in reversed(history):
        key = commander_of(session)
        seen[key] = seen.get(key, 0) + 1
        if seen[key] <= limit:
            keep.append(session)
    keep.reverse()
    return keep


class SessionStore:
    def __init__(self, plugin_dir: str) -> None:
        self._path = os.path.join(plugin_dir, FILENAME)

    def load(self) -> Tuple[List[Dict[str, Any]], Optional[Dict[str, Any]]]:
        """Returns (history, current). current is None if there's nothing to resume."""
        if not os.path.exists(self._path):
            return [], None
        try:
            with open(self._path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
        except (OSError, ValueError):
            logger.warning("Could not read %s; starting with empty history", self._path, exc_info=True)
            return [], None

        if isinstance(data, dict):
            history = data.get("history")
            current = data.get("current")
            return (
                history if isinstance(history, list) else [],
                current if isinstance(current, dict) else None,
            )
        return [], None

    def save(self, history: List[Dict[str, Any]], current: Dict[str, Any]) -> None:
        trimmed = trim(history)
        payload = {"history": trimmed, "current": current}
        try:
            with open(self._path, "w", encoding="utf-8") as fh:
                json.dump(payload, fh, indent=2)
        except OSError:
            logger.warning("Could not write %s", self._path, exc_info=True)
