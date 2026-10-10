"""
Trade History: sessions the commander chose to save, kept in `trade_history.json` beside the plugin (pure logic plus
a small JSON file, so it is unit-tested without EDMC or a window).

Nothing is saved automatically: the live session ledger (trade_ledger.py) is a working tally, and a session only goes
into history when the commander presses **Save session**. Saving again *updates* that session's record instead of adding a
second one (the id is made from the commander and the moment the session began), and **Reset** starts a new session
with a new id. A session belongs to a commander and lasts until Reset, however many game logins, journal files and EDMC
runs it spans, so it becomes at most one history entry.

A record is a snapshot, so it still reads right after the live ledger has moved on:

    id, cmdr, saved_at, started, ended, first_trade, last_trade
    credits_start, credits_end            the balance at login and at save
    ship, pad                              what was flown, and the landing pad it needs
    jumps, jump_ly                         FSD jumps and light years covered
    rows, expenses                         the totals per commodity and per kind of running cost (exact)
    log                                    every trade and cost with its station and system (bounded)
    routes, searches                       the Spansh routes and market searches made during the session
    stock, hold, capacity, carriers        what was unsold, in the hold and on the carrier at save time

The numbers shown from a record are worked out in trade_stats.py.
"""
from __future__ import annotations

import copy
import hashlib
import json
import logging
import os
import time
from typing import Any, Dict, List, Optional

try:
    from config import appname
except ImportError:  # unit tests outside EDMC
    appname = "EDMarketConnector"

from . import trade_ledger
from .trade_carrier import key_for

plugin_name = os.path.basename(os.path.dirname(__file__))
logger = logging.getLogger(f"{appname}.{plugin_name}")

STATE_FILENAME = "trade_history.json"
MAX_SESSIONS = 500   # the commander saves these by hand, so the cap is generous; the oldest go first past it

Record = Dict[str, Any]


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def session_id(cmdr: str, started: Optional[str]) -> str:
    """Stable for one session, however many logins and journal files it spans: saving it again updates the same record.
    (The commander and the moment the session began; Reset begins a new one.)"""
    raw = f"{key_for(cmdr)}|{started or ''}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:12]


def has_content(ledger: Optional[Dict[str, Any]]) -> bool:
    """Is there anything worth saving: a trade or a running cost?"""
    return bool(ledger and (ledger.get("rows") or ledger.get("expenses")))


def build_record(
    ledger: Dict[str, Any], cmdr: str, ship: str = "", pad: Optional[str] = None, credits_end: Optional[int] = None,
    stock: Optional[List[Dict[str, Any]]] = None, hold: Optional[List[Dict[str, Any]]] = None, capacity: int = 0,
    carriers: Optional[List[Dict[str, Any]]] = None, saved_at: Optional[str] = None,
) -> Record:
    """A snapshot of the live ledger plus what was true at the moment of saving. Everything is copied, so later
    changes to the live ledger don't alter it."""
    info = trade_ledger.meta(ledger)
    log = ledger.get("log") or []
    started = info.get("started") or ledger.get("first_trade")
    stamp = saved_at or _now()
    last_entry = next((item.get("t") for item in reversed(log) if item.get("t")), None)
    record: Record = {
        "id": session_id(cmdr, started),
        "cmdr": cmdr, "saved_at": stamp, "started": started, "ended": last_entry or ledger.get("last_trade") or stamp,
        "first_trade": ledger.get("first_trade"), "last_trade": ledger.get("last_trade"),
        "credits_start": info.get("credits_start"), "credits_end": credits_end,
        "ship": ship, "pad": pad, "jumps": info.get("jumps", 0), "jump_ly": info.get("jump_ly", 0.0),
        "rows": ledger.get("rows") or {}, "expenses": ledger.get("expenses") or {}, "log": log,
        "routes": ledger.get("routes") or [], "searches": ledger.get("searches") or [],
        "stock": stock or [], "hold": hold or [], "capacity": capacity, "carriers": carriers or [],
    }
    return copy.deepcopy(record)


class HistoryBook:
    def __init__(self, sessions: Optional[List[Record]] = None) -> None:
        self.sessions: List[Record] = sessions if sessions is not None else []

    def save(self, record: Record) -> bool:
        """Add the session, or replace the saved one with the same id. Returns True if it replaced one."""
        for index, existing in enumerate(self.sessions):
            if existing.get("id") == record.get("id"):
                self.sessions[index] = record
                return True
        self.sessions.append(record)
        del self.sessions[: max(0, len(self.sessions) - MAX_SESSIONS)]
        return False

    def delete(self, session: str) -> bool:
        before = len(self.sessions)
        self.sessions = [s for s in self.sessions if s.get("id") != session]
        return len(self.sessions) != before

    def is_saved(self, session: str) -> bool:
        return any(s.get("id") == session for s in self.sessions)

    def newest_first(self, cmdr: Optional[str] = None) -> List[Record]:
        """Saved sessions, the most recently started first; optionally only one commander's."""
        chosen = [s for s in self.sessions if cmdr is None or key_for(s.get("cmdr", "")) == key_for(cmdr)]
        return sorted(chosen, key=lambda s: str(s.get("started") or s.get("saved_at") or ""), reverse=True)

    def commanders(self) -> List[str]:
        seen: Dict[str, str] = {}
        for session in self.sessions:
            seen.setdefault(key_for(session.get("cmdr", "")), str(session.get("cmdr") or ""))
        return sorted(seen.values(), key=str.casefold)


# --- persistence --------------------------------------------------------------------------------------

def load_all(plugin_dir: str) -> List[Record]:
    try:
        with open(os.path.join(plugin_dir, STATE_FILENAME), "r", encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, ValueError):
        return []
    sessions = data.get("sessions") if isinstance(data, dict) else None
    return [s for s in sessions if isinstance(s, dict) and s.get("id")] if isinstance(sessions, list) else []


def save_all(plugin_dir: str, sessions: List[Record]) -> bool:
    """Temp file then replace, so a crash can't leave a half-written history. Returns False if it couldn't write."""
    path = os.path.join(plugin_dir, STATE_FILENAME)
    tmp = f"{path}.tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as handle:
            json.dump({"sessions": sessions}, handle, indent=1, sort_keys=True)
        os.replace(tmp, path)
        return True
    except OSError:
        logger.warning("Could not write %s", path, exc_info=True)
        return False
