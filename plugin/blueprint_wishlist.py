"""The blueprint wishlist: the engineering blueprints a commander wants to craft and how many crafts of each, kept per commander. One small JSON
file (`blueprint_wishlist.json` beside the plugin, `commander_data.py`): every commander has a separate list, and nothing is ever sent anywhere.
This is the pure part (no Tk); what the list needs and how much of it the commander already holds is `blueprint_needs.py`, and the window is
`blueprints_window.py`.

An entry is a blueprint (`blueprints.Blueprint.id`) and a number of crafts. One craft takes the blueprint's ingredients once; how many crafts it
takes to reach a result depends on the game's rolls, which WNTB cannot know, so the commander sets it. Adding a blueprint that is already on the
list adds to its crafts. Limits: 100 entries, 99 crafts each; past them a change is refused with a message, never trimmed quietly. An entry whose
blueprint is no longer in the table (the table was replaced) is dropped when the file is read."""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional

from . import blueprints, commander_data

try:
    from config import appname
except ImportError:  # unit tests outside EDMC
    appname = "EDMarketConnector"

plugin_name = os.path.basename(os.path.dirname(__file__))
logger = logging.getLogger(f"{appname}.{plugin_name}")

STATE_FILENAME = "blueprint_wishlist.json"
MAX_ITEMS = 100
MAX_CRAFTS = 99


class WishError(ValueError):
    """A change that cannot be made; the message says why and is shown to the commander as it is."""


@dataclass(frozen=True)
class WishItem:
    blueprint_id: str
    crafts: int

    @property
    def blueprint(self) -> Optional[blueprints.Blueprint]:
        return blueprints.get(self.blueprint_id)


def _empty() -> Dict[str, Any]:
    return {"items": []}


def _is_legacy(_raw: Any) -> bool:
    return False   # the file is new; nothing older to claim


class WishBook:
    """The commander's wishlist. Constructed empty; `load(plugin_dir)` once at start-up and `set_commander(cmdr)` whenever the commander is
    known or changes. Every change is written straight away."""

    def __init__(self) -> None:
        self._store = commander_data.new_store()
        self._plugin_dir: Optional[str] = None
        self._cmdr = ""
        self._items: List[WishItem] = []
        self._listeners: List[Callable[[], None]] = []

    # --- loading and saving --------------------------------------------------------------------------------------

    def load(self, plugin_dir: str) -> None:
        self._plugin_dir = plugin_dir
        self._store = commander_data.read(os.path.join(plugin_dir, STATE_FILENAME), _is_legacy)
        self._reload()

    def set_commander(self, cmdr: str) -> bool:
        """True when this changed whose list is showing."""
        cmdr = str(cmdr or "").strip()
        if not cmdr or commander_data.key_for(cmdr) == commander_data.key_for(self._cmdr):
            return False
        self._cmdr = cmdr
        self._reload()
        return True

    def _reload(self) -> None:
        self._items = []
        if self._cmdr:
            payload = commander_data.payload_for(self._store, self._cmdr, _empty)
            raw = payload.get("items") if isinstance(payload, dict) else None
            seen = set()
            for entry in raw if isinstance(raw, list) else []:
                if not isinstance(entry, dict) or not isinstance(entry.get("id"), str):
                    continue
                crafts = entry.get("crafts")
                if entry["id"] in seen or blueprints.get(entry["id"]) is None or isinstance(crafts, bool) or not isinstance(crafts, int):
                    continue
                if len(self._items) < MAX_ITEMS:
                    seen.add(entry["id"])
                    self._items.append(WishItem(entry["id"], max(1, min(MAX_CRAFTS, crafts))))
        self._changed()

    def _save(self) -> None:
        if not self._cmdr or self._plugin_dir is None:
            return
        commander_data.put(self._store, self._cmdr, {"items": [{"id": i.blueprint_id, "crafts": i.crafts} for i in self._items]})
        commander_data.write(os.path.join(self._plugin_dir, STATE_FILENAME), self._store)

    def add_listener(self, callback: Callable[[], None]) -> None:
        self._listeners.append(callback)

    def remove_listener(self, callback: Callable[[], None]) -> None:
        if callback in self._listeners:
            self._listeners.remove(callback)

    def _changed(self) -> None:
        for callback in list(self._listeners):
            try:
                callback()
            except Exception:   # a listener (a window that has gone) must never stop a save
                logger.debug("Wishlist listener failed", exc_info=True)

    # --- reading ---------------------------------------------------------------------------------------------------

    @property
    def commander(self) -> str:
        return self._cmdr

    @property
    def ready(self) -> bool:
        """Blueprints can be listed: a commander is known."""
        return bool(self._cmdr)

    def items(self) -> List[WishItem]:
        """In the order they were added."""
        return list(self._items)

    def count(self) -> int:
        return len(self._items)

    def get(self, blueprint_id: str) -> Optional[WishItem]:
        return next((i for i in self._items if i.blueprint_id == blueprint_id), None)

    # --- changing --------------------------------------------------------------------------------------------------

    def add(self, blueprint_id: str, crafts: int = 1) -> WishItem:
        """Put a blueprint on the list, or add to its crafts if it is there already. Returns the entry."""
        if not self.ready:
            raise WishError("The wishlist is kept per commander and no commander is known yet. Log in first.")
        if blueprints.get(blueprint_id) is None:
            raise WishError("That blueprint is not in the table.")
        crafts = self._checked_crafts(crafts)
        old = self.get(blueprint_id)
        if old is None:
            if len(self._items) >= MAX_ITEMS:
                raise WishError(f"There is room for {MAX_ITEMS} blueprints. Remove some before adding more.")
            item = WishItem(blueprint_id, crafts)
            self._items.append(item)
        else:
            if old.crafts + crafts > MAX_CRAFTS:
                raise WishError(f"A blueprint can be crafted at most {MAX_CRAFTS} times on the list; it is at {old.crafts} already.")
            item = WishItem(blueprint_id, old.crafts + crafts)
            self._items[self._items.index(old)] = item
        self._save()
        self._changed()
        return item

    def set_crafts(self, blueprint_id: str, crafts: int) -> WishItem:
        old = self.get(blueprint_id)
        if old is None:
            raise WishError("That blueprint is not on the list.")
        item = WishItem(blueprint_id, self._checked_crafts(crafts))
        self._items[self._items.index(old)] = item
        self._save()
        self._changed()
        return item

    def remove(self, blueprint_id: str) -> bool:
        old = self.get(blueprint_id)
        if old is None:
            return False
        self._items.remove(old)
        self._save()
        self._changed()
        return True

    def clear(self) -> int:
        """Empty the list; returns how many entries went."""
        gone = len(self._items)
        if gone:
            self._items = []
            self._save()
            self._changed()
        return gone

    @staticmethod
    def _checked_crafts(crafts: Any) -> int:
        if isinstance(crafts, bool) or not isinstance(crafts, int) or not 1 <= crafts <= MAX_CRAFTS:
            raise WishError(f"The number of crafts must be a whole number from 1 to {MAX_CRAFTS}.")
        return crafts
