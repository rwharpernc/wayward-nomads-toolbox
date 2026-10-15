"""The system the commander is in now, for features that must know it on demand (the Missions window's "From where I am", Source commodities).

A feature that follows journal events live only knows the system once it has seen a jump, a login or a carrier jump *since EDMC started*. If EDMC was started
after the game, or the plugin was reloaded, that is nothing until the next jump. So this asks in turn: what the caller has tracked, EDMC's own state (which EDMC
rebuilds from the whole journal at start-up), and the newest journal itself. Nothing is stored or sent."""
from __future__ import annotations

import logging
from typing import Optional

from . import journal_files

logger = logging.getLogger(__name__)

NEWEST_FILES = 3
_PLACE = journal_files.event_pattern("FSDJump", "Location", "CarrierJump")


def from_monitor() -> str:
    """EDMC's idea of the current system, or "" (not running under EDMC, or it does not know yet)."""
    try:
        from monitor import monitor  # EDMC's own module; absent in unit tests
        state = getattr(monitor, "state", None) or {}
        return str(state.get("SystemName") or "").strip()
    except Exception:
        return ""


def from_journal(folder: Optional[str] = None) -> str:
    """The star system of the last jump, login location or carrier jump in the newest journal that has one, or ""."""
    try:
        files = journal_files.files_modified_since(0.0, folder)
        for path in reversed(files[-NEWEST_FILES:]):
            last = ""
            for entry in journal_files.read_events(path, _PLACE):
                name = str(entry.get("StarSystem") or "").strip()
                if name:
                    last = name
            if last:
                return last
    except Exception:
        logger.debug("Could not read the current system from the journals", exc_info=True)
    return ""


def find(tracked: str = "") -> str:
    """The current system: `tracked` if the caller has one, else EDMC's, else the journal's, else ""."""
    return (tracked or "").strip() or from_monitor() or from_journal()
