"""Where the commander stands with each engineer, kept per commander. One small JSON file (`engineers.json` beside the plugin,
`commander_data.py`): every commander has a separate record, and nothing is ever sent anywhere. This is the pure part (no Tk); the Engineers tab
is in `blueprints_window.py`.

**Where it comes from.** The journal's `EngineerProgress` event: at login a list of every engineer the game shows the commander
(`{"Engineers": [{"Engineer", "EngineerID", "Progress", "Rank", "RankProgress"}, ...]}`), and afterwards one engineer at a time
(`{"Engineer", "EngineerID", "Progress"}`) when a standing changes. `Progress` is `Known` (the commander has heard of them), `Invited` (the
invitation has been earned) or `Unlocked` (they will work for the commander); an unlocked engineer also has a `Rank` (1 to 5) and `RankProgress`
(0 to 100, towards the next rank). A rank-up is sent as `{"Engineer", "EngineerID", "Rank"}` with no `Progress` (71 of them in the journals
checked); an engineer who ranks up is unlocked, so it is read as `Unlocked` at that rank. The shapes were checked against real journals on 2026-10-13. The documentation also lists `Acquainted` and
`Barred`; neither was seen, `Acquainted` is read as `Known` and `Barred` is kept as it is.

**Names.** The journal writes `Tod 'The Blaster' McQuinn` where the blueprint table writes `Tod McQuinn`, so engineers are matched by a key that
drops a nickname in quotes, case and spacing (`name_key`). Three engineers in the journal (Baltanos, Eleanor Bresa, Rosa Dayette) are not in the
blueprint table, which is older than the game; they are listed with their standing and no blueprints."""
from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Mapping, Optional

from . import commander_data

try:
    from config import appname
except ImportError:  # unit tests outside EDMC
    appname = "EDMarketConnector"

plugin_name = os.path.basename(os.path.dirname(__file__))
logger = logging.getLogger(f"{appname}.{plugin_name}")

STATE_FILENAME = "engineers.json"
UNLOCKED, INVITED, KNOWN, BARRED = "Unlocked", "Invited", "Known", "Barred"
PROGRESS = (UNLOCKED, INVITED, KNOWN, BARRED)
MAX_ENGINEERS = 100
MAX_NAME = 80

_NICKNAME = re.compile(r"""\s*(['"“”‘’]).*?\1\s*""")


def name_key(name: Any) -> str:
    """A name reduced for matching: any nickname in quotes dropped, case folded, spaces collapsed."""
    text = _NICKNAME.sub(" ", str(name or ""))
    return " ".join(text.split()).casefold()


@dataclass(frozen=True)
class Standing:
    name: str
    progress: str            # Unlocked, Invited, Known or Barred
    rank: int                # 1 to 5 for an unlocked engineer, 0 otherwise
    rank_progress: int       # percent towards the next rank, 0 to 100

    @property
    def unlocked(self) -> bool:
        return self.progress == UNLOCKED

    def describe(self) -> str:
        if self.unlocked and self.rank:
            return f"Unlocked, rank {self.rank}" + (f" ({self.rank_progress}%)" if self.rank < 5 and self.rank_progress else "")
        return self.progress


def _progress(value: Any) -> Optional[str]:
    text = str(value or "").strip().capitalize()
    if text == "Acquainted":
        return KNOWN
    return text if text in PROGRESS else None


def _clamped(value: Any, high: int) -> int:
    return max(0, min(high, value)) if isinstance(value, int) and not isinstance(value, bool) else 0


def _standing(raw: Any) -> Optional[Standing]:
    if not isinstance(raw, Mapping):
        return None
    name, progress = raw.get("Engineer"), _progress(raw.get("Progress"))
    if not isinstance(name, str) or not name.strip() or progress is None:
        return None
    unlocked = progress == UNLOCKED
    return Standing(" ".join(name.split())[:MAX_NAME], progress, _clamped(raw.get("Rank"), 5) if unlocked else 0,
                    _clamped(raw.get("RankProgress"), 100) if unlocked else 0)


def _rank_up(raw: Mapping[str, Any]) -> Optional[Standing]:
    """A rank-up event (a rank and no progress): the engineer is unlocked at that rank, with no progress towards the next."""
    rank = raw.get("Rank")
    if not isinstance(raw.get("Engineer"), str) or isinstance(rank, bool) or not isinstance(rank, int) or not 1 <= rank <= 5:
        return None
    return _standing({"Engineer": raw["Engineer"], "Progress": UNLOCKED, "Rank": rank, "RankProgress": 0})


def _empty() -> Dict[str, Any]:
    return {"engineers": []}


def _is_legacy(_raw: Any) -> bool:
    return False   # the file is new; nothing older to claim


class EngineerBook:
    """The commander's standing with each engineer. Constructed empty; `load(plugin_dir)` once at start-up and `set_commander(cmdr)` whenever
    the commander is known or changes. A change is written straight away (they are rare)."""

    def __init__(self) -> None:
        self._store = commander_data.new_store()
        self._plugin_dir: Optional[str] = None
        self._cmdr = ""
        self._standing: Dict[str, Standing] = {}      # name_key -> standing
        self._listeners: List[Callable[[], None]] = []

    # --- loading and saving --------------------------------------------------------------------------------------

    def load(self, plugin_dir: str) -> None:
        self._plugin_dir = plugin_dir
        self._store = commander_data.read(os.path.join(plugin_dir, STATE_FILENAME), _is_legacy)
        self._reload()

    def set_commander(self, cmdr: str) -> bool:
        """True when this changed whose standings are showing."""
        cmdr = str(cmdr or "").strip()
        if not cmdr or commander_data.key_for(cmdr) == commander_data.key_for(self._cmdr):
            return False
        self._cmdr = cmdr
        self._reload()
        return True

    def _reload(self) -> None:
        self._standing = {}
        if self._cmdr:
            payload = commander_data.payload_for(self._store, self._cmdr, _empty)
            raw = payload.get("engineers") if isinstance(payload, dict) else None
            for item in raw if isinstance(raw, list) else []:
                standing = _standing({"Engineer": item.get("name"), "Progress": item.get("progress"), "Rank": item.get("rank"),
                                      "RankProgress": item.get("rank_progress")}) if isinstance(item, dict) else None
                if standing is not None and len(self._standing) < MAX_ENGINEERS:
                    self._standing[name_key(standing.name)] = standing
        self._changed()

    def _save(self) -> None:
        if not self._cmdr or self._plugin_dir is None:
            return
        commander_data.put(self._store, self._cmdr, {"engineers": [
            {"name": s.name, "progress": s.progress, "rank": s.rank, "rank_progress": s.rank_progress}
            for s in self._standing.values()]})
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
                logger.debug("Engineers listener failed", exc_info=True)

    # --- reading ---------------------------------------------------------------------------------------------------

    @property
    def commander(self) -> str:
        return self._cmdr

    @property
    def has_data(self) -> bool:
        """The game has told WNTB about at least one engineer for this commander (an empty list means it has not)."""
        return bool(self._standing)

    def standing(self, name: Any) -> Optional[Standing]:
        return self._standing.get(name_key(name))

    def all(self) -> List[Standing]:
        return sorted(self._standing.values(), key=lambda s: s.name.casefold())

    def unlocked(self) -> List[Standing]:
        return [s for s in self.all() if s.unlocked]

    # --- changing --------------------------------------------------------------------------------------------------

    def apply_event(self, entry: Mapping[str, Any]) -> bool:
        """Take one journal event; True when the standings changed. The login list replaces everything (unless it is empty); a single-engineer event updates one."""
        if entry.get("event") != "EngineerProgress" or not self._cmdr:
            return False
        listed = entry.get("Engineers")
        if isinstance(listed, list):
            if not listed:
                return False       # an empty list (a new commander, or the game not ready) never wipes what was known: progress is not lost
            new: Dict[str, Standing] = {}
            for raw in listed:
                standing = _standing(raw)
                if standing is not None and len(new) < MAX_ENGINEERS:
                    new[name_key(standing.name)] = standing
            if new == self._standing:
                return False
            self._standing = new
        else:
            standing = _standing(entry) if "Progress" in entry else _rank_up(entry)
            if standing is None:
                return False
            key = name_key(standing.name)
            if self._standing.get(key) == standing or (key not in self._standing and len(self._standing) >= MAX_ENGINEERS):
                return False
            self._standing[key] = standing
        self._save()
        self._changed()
        return True
