"""
The Raven Colonial key of each commander, kept in `rcc_keys.json` (one entry per commander, never shared: commander_data.py).

The key is what lets WNTB report a finished build for that commander (rcc_client.complete_project). It is a secret: it is never
logged, never put in a message shown to the commander, and goes only to Raven Colonial. The file sits in the plugin folder
beside the other saved data and is kept by the updater.
"""
from __future__ import annotations

import os
from typing import Any, Dict, Optional

from . import commander_data

STATE_FILENAME = "rcc_keys.json"
KEY_MAX = 200


def _empty() -> Dict[str, Any]:
    return {"key": ""}


def _is_legacy(_raw: Any) -> bool:
    return False


class RccKeys:
    def __init__(self, plugin_dir: Optional[str] = None) -> None:
        self._plugin_dir = plugin_dir or os.path.dirname(os.path.abspath(__file__))
        self._store = commander_data.read(os.path.join(self._plugin_dir, STATE_FILENAME), _is_legacy)

    def get(self, cmdr: str) -> str:
        if not commander_data.known(self._store, cmdr):
            return ""
        return str(commander_data.payload_for(self._store, cmdr, _empty).get("key") or "")

    def set(self, cmdr: str, key: str) -> None:
        """Save (or, given an empty key, forget) this commander's key."""
        if not commander_data.key_for(cmdr):
            return
        commander_data.put(self._store, cmdr, {"key": (key or "").strip()[:KEY_MAX]})
        commander_data.write(os.path.join(self._plugin_dir, STATE_FILENAME), self._store)


keys = RccKeys()
