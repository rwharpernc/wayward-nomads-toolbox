"""The missions a commander has pinned: kept for the Missions window and drawn first, under PINNED, on the Missions overlay card.

Stored per commander in `mission_pins.json` beside the plugin (`commander_data.py`): only mission ids, nothing else, and nothing is ever sent anywhere. A pin
goes when its mission does (handed in, failed, abandoned or expired): `prune` drops the ids that are no longer active, and is only called once the
roster of active missions is known, so a roster that has not loaded yet cannot wipe the pins."""
from __future__ import annotations

import logging
import os
import threading
from typing import Any, Collection, Dict, Iterable, List, Optional, Set

from . import commander_data

logger = logging.getLogger(__name__)

STATE_FILENAME = "mission_pins.json"


def _is_legacy(raw: Any) -> bool:
    return False          # the file has always been per commander


def _empty() -> Dict[str, Any]:
    return {"ids": []}


class PinBook:
    """The pinned mission ids of each commander. `load(plugin_dir)` once at start-up; every change is written at once (a handful of numbers)."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._store = commander_data.new_store()
        self._plugin_dir: Optional[str] = None

    def load(self, plugin_dir: str) -> None:
        with self._lock:
            self._plugin_dir = plugin_dir
            self._store = commander_data.read(os.path.join(plugin_dir, STATE_FILENAME), _is_legacy)

    def pinned(self, cmdr: Optional[str]) -> Set[int]:
        if not cmdr:
            return set()
        with self._lock:
            entry = self._store["commanders"].get(commander_data.key_for(cmdr))
            ids = entry["data"].get("ids", []) if entry and isinstance(entry.get("data"), dict) else []
            return {int(i) for i in ids if isinstance(i, int)}

    def is_pinned(self, cmdr: Optional[str], mission_id: int) -> bool:
        return mission_id in self.pinned(cmdr)

    def _set(self, cmdr: str, ids: Iterable[int]) -> None:
        commander_data.put(self._store, cmdr, {"ids": sorted(set(ids))})
        if self._plugin_dir is None:
            return
        try:
            commander_data.write(os.path.join(self._plugin_dir, STATE_FILENAME), self._store)
        except OSError:
            logger.warning("Could not save the pinned missions", exc_info=True)

    def toggle(self, cmdr: Optional[str], mission_id: int) -> bool:
        """Pin the mission if it is not pinned, else unpin it. Returns whether it is pinned now."""
        if not cmdr:
            return False
        with self._lock:
            ids = self.pinned(cmdr)
            now = mission_id not in ids
            ids.add(mission_id) if now else ids.discard(mission_id)
            self._set(cmdr, ids)
            return now

    def pin_many(self, cmdr: Optional[str], mission_ids: Collection[int]) -> None:
        if cmdr and mission_ids:
            with self._lock:
                self._set(cmdr, self.pinned(cmdr) | set(mission_ids))

    def clear(self, cmdr: Optional[str]) -> None:
        if cmdr and self.pinned(cmdr):
            with self._lock:
                self._set(cmdr, ())

    def prune(self, cmdr: Optional[str], active_ids: Collection[int]) -> List[int]:
        """Drop the pins of missions that are no longer active; returns the ids dropped."""
        if not cmdr:
            return []
        with self._lock:
            ids = self.pinned(cmdr)
            gone = sorted(ids - set(active_ids))
            if gone:
                self._set(cmdr, ids - set(gone))
            return gone


book = PinBook()
