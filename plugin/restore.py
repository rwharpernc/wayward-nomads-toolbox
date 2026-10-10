"""
Knowing who is playing when EDMC starts without the game running.

EDMC tells plugins the commander only through journal events. When it starts with the game already running it sends a
synthetic `StartUp` event, and every feature picks the commander up from that. When it starts first (the game is not
running yet, or was closed), nothing arrives until the next login, and every per-commander feature sits waiting.

So a short time after start-up, if no live event has arrived, `load.py` calls `dispatch`: it names the commander from the
newest journal (`latest_commander`) and sends every feature one neutral event, `RESTORE_EVENT`. It is deliberately **not**
`StartUp` or `LoadGame`: those say a game is running (Game Mode would read a dead game's journal, Powerplay would try to
recover a pledge, a credits session would start). Features treat the new event as any other unknown event, so the only
effect is the one they all share, learning `cmdr` and loading that commander's saved data. A real `LoadGame` or
`StartUp` later, for the same or another commander, then behaves exactly as before.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, Optional

from . import journal_files

try:
    from config import appname
except ImportError:  # unit tests outside EDMC
    appname = "EDMarketConnector"

plugin_name = os.path.basename(os.path.dirname(__file__))
logger = logging.getLogger(f"{appname}.{plugin_name}")

RESTORE_EVENT = "WNTBRestoreCommander"
NEWEST_FILES = 3   # the newest journal may be empty (the game just started), so look back a few
_LOGIN_EVENTS = journal_files.event_pattern("Commander", "LoadGame")


def latest_commander(folder: Optional[str] = None) -> str:
    """The commander named in the newest journal (its last `LoadGame` / `Commander`), else EDMC's own idea of it, else
    "". A missing folder or unreadable file gives ""."""
    try:
        files = journal_files.files_modified_since(0.0, folder)
        for path in reversed(files[-NEWEST_FILES:]):
            found = ""
            for entry in journal_files.read_events(path, _LOGIN_EVENTS):
                name = entry.get("Name") if entry.get("event") == "Commander" else entry.get("Commander")
                if name:
                    found = str(name)
            if found:
                return found
    except Exception:
        logger.debug("Could not read the commander from the journals", exc_info=True)
    try:
        from monitor import monitor  # EDMC's own module; absent in unit tests
        return str(getattr(monitor, "cmdr", "") or "")
    except ImportError:
        return ""


def restore_entry() -> Dict[str, Any]:
    return {"event": RESTORE_EVENT, "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}


def dispatch(features: Iterable[Any], cmdr: str) -> int:
    """Send `cmdr`'s restore event to every feature's `handle_event`. One feature failing never stops the others.
    Returns how many handled it without error."""
    ok = 0
    entry = restore_entry()
    for feature in features:
        try:
            feature.handle_event(dict(entry), cmdr, None, None, {})
            ok += 1
        except Exception:
            logger.exception("%s failed to restore the commander %s", getattr(feature, "__name__", feature), cmdr)
    return ok
