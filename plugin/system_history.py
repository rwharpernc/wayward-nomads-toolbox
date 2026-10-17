"""Which systems this commander has been in and scanned in, built from their journals, for the System targets card.

The card keeps a survey of each system, but only for visits it saw or could rebuild from the newest journals, and it could not tell a system you have never
been in from one you were in a year ago. This reads every journal once, in the background, and keeps for each system the commander has been in: how many
visits, the first and last, whether they scanned anything there, and which journal files hold those visits (so rebuilding a survey reads those files and not the
whole folder). Only journals that are finished (every one but the newest) are saved; what is happening now is kept in memory and rebuilt from the newest
journal when EDMC starts, so nothing is counted twice. A later start reads only the journals written since.

Saved in `system_history.json` beside the plugin, one record per commander (`commander_data.py`); nothing is sent anywhere. The journals of another
commander are skipped. No Tk, no overlay.
"""

from __future__ import annotations

import logging
import os
import threading
import time
from typing import Any, Dict, List, Optional, Set

try:
    from config import appname
except ImportError:   # unit tests outside EDMC
    appname = "EDMarketConnector"

from . import commander_data, journal_files

plugin_name = os.path.basename(os.path.dirname(__file__))
logger = logging.getLogger(f"{appname}.{plugin_name}")

STATE_FILENAME = "system_history.json"
ARRIVALS = ("FSDJump", "CarrierJump", "Location")
SCAN_EVENTS = ("Scan", "SAAScanComplete", "FSSDiscoveryScan")
EVENTS = ARRIVALS + SCAN_EVENTS + ("LoadGame",)
SAVE_EVERY = 250          # journals read between saves, so a quit part-way through keeps its progress
PAUSE = 0.005             # seconds between journals, so reading years of them never starves EDMC


def _empty() -> Dict[str, Any]:
    return {"files": [], "tail": "", "systems": {}}


def _is_legacy(_raw: Any) -> bool:
    return False


class Visit:
    """What is known about one system: `visits` (all of them, this one included), the first and last timestamps, whether anything was scanned there, and the
    journal files that hold the visits."""

    def __init__(self, name: str = "", visits: int = 0, first: str = "", last: str = "", scanned: bool = False, files: Optional[List[str]] = None) -> None:
        self.name, self.visits, self.first, self.last, self.scanned = name, visits, first, last, scanned
        self.files: List[str] = files or []


class _Walk:
    """Reads journals in order, counting a visit when the commander arrives somewhere other than where the last arrival was (a relog's `Location` in the same
    system is not a new visit)."""

    def __init__(self, systems: Dict[str, Any], tail: str) -> None:
        self.systems, self.tail = systems, tail

    def read(self, entries: List[Dict[str, Any]], basename: str) -> None:
        here = self.tail
        for entry in entries:
            event = entry.get("event")
            if event in ARRIVALS:
                name = str(entry.get("StarSystem") or "").strip()
                if not name:
                    continue
                here, stamp, key = name, str(entry.get("timestamp") or ""), name.casefold()
                record = self.systems.setdefault(key, {"name": name, "visits": 0, "first": stamp, "last": stamp, "scanned": False, "files": []})
                if key != self.tail:
                    record["visits"] += 1
                record["last"] = max(record["last"], stamp) if record["last"] else stamp
                if basename not in record["files"]:
                    record["files"].append(basename)
                self.tail = key
            elif event in SCAN_EVENTS and here:
                self.systems.get(here.casefold(), {}).update({"scanned": True})


def commander_of(entries: List[Dict[str, Any]]) -> str:
    return next((str(e.get("Commander") or "").casefold() for e in entries if e.get("event") == "LoadGame"), "")


class SystemHistory:
    def __init__(self) -> None:
        self._store = commander_data.new_store()
        self._plugin_dir: Optional[str] = None
        self._cmdr = ""
        self._lock = threading.RLock()
        self._live: Dict[str, Any] = {}           # this session, not saved: casefolded system -> record, as `_Walk` makes them
        self._live_tail = ""
        self._stamps: Set[str] = set()            # arrival timestamps already counted, so the journal read at start and the live events never count one twice
        self.reading = ""                          # "" idle, else a line saying how far the first read has got
        self._thread: Optional[threading.Thread] = None
        self.pause = PAUSE
        self._rebuild: Optional[tuple] = None
        self.ready = False                         # the history has been read at least once this run

    # --- state --------------------------------------------------------------------------------------------------
    def start(self, plugin_dir: str) -> None:
        with self._lock:
            self._plugin_dir = plugin_dir
            self._store = commander_data.read(os.path.join(plugin_dir, STATE_FILENAME), _is_legacy)

    def set_commander(self, cmdr: str) -> None:
        cmdr = str(cmdr or "").strip()
        if not cmdr or commander_data.key_for(cmdr) == commander_data.key_for(self._cmdr):
            return
        with self._lock:
            self._cmdr, self._live, self._live_tail = cmdr, {}, ""
            self._stamps = set()
            self.ready = False
        self.build(cmdr)

    def _payload(self) -> Optional[Dict[str, Any]]:
        if not self._cmdr:
            return None
        payload = commander_data.payload_for(self._store, self._cmdr, _empty)
        if not isinstance(payload, dict) or not isinstance(payload.get("systems"), dict) or not isinstance(payload.get("files"), list):
            payload = _empty()
            commander_data.put(self._store, self._cmdr, payload)
        return payload

    def _save(self) -> None:
        if self._plugin_dir:
            commander_data.write(os.path.join(self._plugin_dir, STATE_FILENAME), self._store)

    # --- live ----------------------------------------------------------------------------------------------------
    def record(self, entry: Dict[str, Any]) -> None:
        """Takes one journal event as it happens (an arrival or a scan)."""
        event = entry.get("event")
        if event not in ARRIVALS and event not in SCAN_EVENTS:
            return
        with self._lock:
            if event in ARRIVALS:
                stamp = str(entry.get("timestamp") or "")
                if stamp and stamp in self._stamps:
                    return
                self._stamps.add(stamp)
                walk = _Walk(self._live, self._live_tail)
                walk.read([entry], "")
                self._live_tail = walk.tail
            elif self._live_tail:
                self._live.get(self._live_tail, {}).update({"scanned": True})

    # --- asking --------------------------------------------------------------------------------------------------
    def lookup(self, name: str) -> Optional[Visit]:
        """The commander's history in `name`: saved visits plus this session's. None when they have never been recorded there."""
        key = str(name or "").casefold()
        with self._lock:
            payload = self._payload()
            saved = payload["systems"].get(key) if payload else None
            live = self._live.get(key)
        if not saved and not live:
            return None
        saved, live = saved or {}, live or {}
        stamps = [s for s in (saved.get("first"), live.get("first")) if s]
        lasts = [s for s in (saved.get("last"), live.get("last")) if s]
        return Visit(str(saved.get("name") or live.get("name") or name), int(saved.get("visits") or 0) + int(live.get("visits") or 0),
                     min(stamps) if stamps else "", max(lasts) if lasts else "", bool(saved.get("scanned") or live.get("scanned")), list(saved.get("files") or []))

    def unindexed_files(self, folder: Optional[str] = None) -> List[str]:
        """The journals not yet in the saved history (at least the newest), full paths, oldest first: what a rebuild must read besides a system's own files."""
        with self._lock:
            payload = self._payload()
            done = set(payload["files"]) if payload else set()
        return [p for p in journal_files.files_modified_since(0.0, folder) if os.path.basename(p) not in done]

    # --- building ------------------------------------------------------------------------------------------------
    def build(self, cmdr: str, folder: Optional[str] = None, wait: bool = False) -> None:
        """Reads the journals not yet in the history (background, once per run), then the newest one into this session's record."""
        if self._thread is not None and self._thread.is_alive():
            self._rebuild = (cmdr, folder)                  # a read for another commander is under way: start this one when it stops
            return
        self._thread = threading.Thread(target=self._build, args=(cmdr, folder), name="WNTB-history", daemon=True)
        self._thread.start()
        if wait:
            self._thread.join()

    def _build(self, cmdr: str, folder: Optional[str]) -> None:
        try:
            self._read_all(cmdr, folder)
        except Exception:
            logger.debug("Could not build the system history", exc_info=True)
        finally:
            self.reading = ""
            again, self._rebuild = self._rebuild, None
            if again is not None and commander_data.key_for(again[0]) == commander_data.key_for(self._cmdr):
                self._thread = threading.Thread(target=self._build, args=again, name="WNTB-history", daemon=True)
                self._thread.start()
            elif commander_data.key_for(cmdr) == commander_data.key_for(self._cmdr):
                self.ready = True

    def _read_all(self, cmdr: str, folder: Optional[str]) -> None:
        paths = journal_files.files_modified_since(0.0, folder)
        if not paths:
            return
        wanted, pattern = commander_data.key_for(cmdr), journal_files.event_pattern(*EVENTS)
        with self._lock:
            payload = self._payload()
            if payload is None:
                return
            done = set(payload["files"])
        closed, active = paths[:-1], paths[-1]
        todo = [p for p in closed if os.path.basename(p) not in done]
        for count, path in enumerate(todo, 1):
            if commander_data.key_for(self._cmdr) != wanted:
                return                                        # another commander loaded in: this read is no longer wanted
            if len(todo) > 20:
                self.reading = f"Reading your journals for a visit history ({count * 100 // len(todo)}%)"
            entries = list(journal_files.read_events(path, pattern))
            owner = commander_of(entries)
            with self._lock:
                payload = self._payload()
                if payload is None:
                    return
                if not owner or owner == wanted:
                    walk = _Walk(payload["systems"], payload["tail"])
                    walk.read(entries, os.path.basename(path))
                    payload["tail"] = walk.tail
                payload["files"].append(os.path.basename(path))
                if count % SAVE_EVERY == 0:
                    self._save()
            time.sleep(self.pause)
        with self._lock:
            self._save()
        entries = list(journal_files.read_events(active, pattern))
        owner = commander_of(entries)
        if owner and owner != wanted:
            return
        with self._lock:
            # the newest journal holds the current session, which the live events also report: start this session's record from it, and remember its arrivals
            # so an event that arrives later is not counted twice
            payload = self._payload()
            walk = _Walk({}, payload["tail"] if payload else "")
            walk.read(entries, "")
            self._live, self._live_tail = walk.systems, walk.tail
            self._stamps = {str(e.get("timestamp") or "") for e in entries if e.get("event") in ARRIVALS}


history = SystemHistory()


def visit_line(name: str, now_counted: bool = True) -> str:
    """One line for the card: `First visit here`, or `Been here 3 times before · last 10 Oct 2026 · you scanned here`. Empty when nothing is known (the history is
    still being read, or no commander yet)."""
    found = history.lookup(name)
    if found is None:
        return "" if history.reading or not history.ready else "First visit here"
    before = max(0, found.visits - (1 if now_counted else 0))
    if before == 0:
        return "First visit here"
    parts = [f"Been here {before} time{'s' if before != 1 else ''} before"]
    if found.last:
        parts.append(f"last {_date(found.last)}")
    if found.scanned:
        parts.append("you scanned here")
    return " · ".join(parts)


def _date(stamp: str) -> str:
    """`2026-10-10T08:15:00Z` as `10 Oct 2026`; the text unchanged when it cannot be read."""
    try:
        year, month, day = int(stamp[0:4]), int(stamp[5:7]), int(stamp[8:10])
        return f"{day} {('Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec').split()[month - 1]} {year}"
    except (ValueError, IndexError):
        return stamp
