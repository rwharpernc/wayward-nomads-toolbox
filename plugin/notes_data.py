"""Notes on a system or a body: the commander's own words, kept per commander. One small JSON file (`notes.json` beside the
plugin, `commander_data.py`): every commander has a separate list, and nothing is ever sent anywhere.

A note is a system name, an optional body name, some text, and when it was made and last changed. The system and body are free text
(what the game calls them), so a note can be written about a place the commander is not at. Matching a note to the system the
commander is in compares names trimmed and case-folded, as the commander key does. Limits keep the file small and the window quick:
2,000 notes, 2,000 characters of text each, 100 of system or body name. Past them an add is refused with a message, never trimmed
quietly. This is the pure part (no Tk); the window is `notes_window.py` and the panel row is `notes_panel.py`."""
from __future__ import annotations

import logging
import os
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

from . import commander_data

try:
    from config import appname
except ImportError:  # unit tests outside EDMC
    appname = "EDMarketConnector"

plugin_name = os.path.basename(os.path.dirname(__file__))
logger = logging.getLogger(f"{appname}.{plugin_name}")

STATE_FILENAME = "notes.json"
MAX_NOTES = 2000
MAX_TEXT = 2000
MAX_NAME = 100


class NoteError(ValueError):
    """A note that cannot be saved; the message says why and is shown to the commander as it is."""


@dataclass(frozen=True)
class Note:
    id: str
    system: str
    body: str
    text: str
    created: str
    updated: str

    def place(self) -> str:
        return f"{self.system} / {self.body}" if self.body else self.system


def name_key(name: Any) -> str:
    return str(name or "").strip().casefold()


def clip(text: str, limit: int) -> str:
    """`text` on one line, shortened with an ellipsis to at most `limit` characters (for tables and the panel)."""
    one_line = " ".join(str(text or "").split())
    return one_line if len(one_line) <= limit else one_line[:max(0, limit - 1)].rstrip() + "…"


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _empty() -> Dict[str, Any]:
    return {"notes": []}


def _is_legacy(_raw: Any) -> bool:
    return False   # the file is new; nothing older to claim


def _from_raw(raw: Any) -> Optional[Note]:
    """A note read from the file, or None for a damaged entry (which is dropped rather than stopping the load)."""
    if not isinstance(raw, dict):
        return None
    note_id, system, text = raw.get("id"), raw.get("system"), raw.get("text")
    if not all(isinstance(v, str) and v.strip() for v in (note_id, system, text)):
        return None
    body = raw.get("body")
    return Note(note_id, system.strip()[:MAX_NAME], body.strip()[:MAX_NAME] if isinstance(body, str) else "",
                text[:MAX_TEXT], str(raw.get("created") or ""), str(raw.get("updated") or raw.get("created") or ""))


def _to_raw(note: Note) -> Dict[str, str]:
    return {"id": note.id, "system": note.system, "body": note.body, "text": note.text, "created": note.created,
            "updated": note.updated}


class NoteBook:
    """The commander's notes. Constructed empty; `load(plugin_dir)` once at start-up and `set_commander(cmdr)` whenever the
    commander is known or changes. Every change is written straight away."""

    def __init__(self, now: Callable[[], str] = _now, new_id: Callable[[], str] = lambda: uuid.uuid4().hex[:12]) -> None:
        self._store = commander_data.new_store()
        self._plugin_dir: Optional[str] = None
        self._cmdr = ""
        self._now = now
        self._new_id = new_id
        self._notes: List[Note] = []
        self._listeners: List[Callable[[], None]] = []

    # --- loading and saving --------------------------------------------------------------------------------------

    def load(self, plugin_dir: str) -> None:
        self._plugin_dir = plugin_dir
        self._store = commander_data.read(os.path.join(plugin_dir, STATE_FILENAME), _is_legacy)
        self._reload()

    def set_commander(self, cmdr: str) -> bool:
        """True when this changed whose notes are showing."""
        cmdr = str(cmdr or "").strip()
        if not cmdr or commander_data.key_for(cmdr) == commander_data.key_for(self._cmdr):
            return False
        self._cmdr = cmdr
        self._reload()
        return True

    def _reload(self) -> None:
        self._notes = []
        if self._cmdr:
            payload = commander_data.payload_for(self._store, self._cmdr, _empty)
            raw = payload.get("notes") if isinstance(payload, dict) else None
            self._notes = [n for n in (_from_raw(r) for r in (raw if isinstance(raw, list) else [])) if n is not None]
        self._changed()

    def _save(self) -> None:
        if not self._cmdr or self._plugin_dir is None:
            return
        commander_data.put(self._store, self._cmdr, {"notes": [_to_raw(n) for n in self._notes]})
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
                logger.debug("Notes listener failed", exc_info=True)

    # --- reading ---------------------------------------------------------------------------------------------------

    @property
    def commander(self) -> str:
        return self._cmdr

    @property
    def ready(self) -> bool:
        """Notes can be added: a commander is known."""
        return bool(self._cmdr)

    def all(self) -> List[Note]:
        """Newest change first."""
        return sorted(self._notes, key=lambda n: (n.updated, n.created), reverse=True)

    def get(self, note_id: str) -> Optional[Note]:
        return next((n for n in self._notes if n.id == note_id), None)

    def for_system(self, system: Any) -> List[Note]:
        key = name_key(system)
        return [n for n in self.all() if key and name_key(n.system) == key]

    def search(self, query: str = "", system: Any = None) -> List[Note]:
        """Notes whose system, body or text contain every word of `query` (case-folded), newest first; with `system`, only that
        system's."""
        words = [w for w in name_key(query).split() if w]
        found = self.for_system(system) if system else self.all()
        return [n for n in found if all(w in f"{n.system} {n.body} {n.text}".casefold() for w in words)]

    def count(self) -> int:
        return len(self._notes)

    # --- changing --------------------------------------------------------------------------------------------------

    @staticmethod
    def _checked(system: Any, body: Any, text: Any) -> tuple:
        system, body, text = str(system or "").strip(), str(body or "").strip(), str(text or "").strip()
        if not system:
            raise NoteError("A note needs a system name.")
        if not text:
            raise NoteError("A note needs some text.")
        if len(system) > MAX_NAME or len(body) > MAX_NAME:
            raise NoteError(f"System and body names can be at most {MAX_NAME} characters.")
        if len(text) > MAX_TEXT:
            raise NoteError(f"A note can be at most {MAX_TEXT:,} characters; this one is {len(text):,}.")
        return system, body, text

    def add(self, system: Any, body: Any, text: Any) -> Note:
        if not self.ready:
            raise NoteError("Notes are kept per commander and no commander is known yet. Log in first.")
        system, body, text = self._checked(system, body, text)
        if len(self._notes) >= MAX_NOTES:
            raise NoteError(f"There is room for {MAX_NOTES:,} notes. Delete some before adding more.")
        stamp = self._now()
        note = Note(self._new_id(), system, body, text, stamp, stamp)
        self._notes.append(note)
        self._save()
        self._changed()
        return note

    def update(self, note_id: str, system: Any, body: Any, text: Any) -> Note:
        old = self.get(note_id)
        if old is None:
            raise NoteError("That note no longer exists.")
        system, body, text = self._checked(system, body, text)
        new = Note(old.id, system, body, text, old.created, old.updated if (system, body, text) == (old.system, old.body, old.text)
                   else self._now())
        self._notes[self._notes.index(old)] = new
        self._save()
        self._changed()
        return new

    def delete(self, note_id: str) -> bool:
        old = self.get(note_id)
        if old is None:
            return False
        self._notes.remove(old)
        self._save()
        self._changed()
        return True
