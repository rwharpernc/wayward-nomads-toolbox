"""
Static reference list of known surface material-deposit locations
("hotspots"): system, body, what's there, and (usually) exact lat/lon.

Unlike mining_surface.py's MiningLocationSignal (a DSS scan telling you
*some* Planetary Mining Location exists on a body, found from orbit, not
tied to any specific spot), a Hotspot is entered by the commander from
knowledge they already have - a location they've found and want to
remember, or one shared by someone else - and doesn't change once
recorded, since the underlying surface deposit is static. So this is a
small, rarely-edited list rather than session state: persisted as a
single JSON file next to mining_sessions/ (see mining_session_archive.py
for the same "next to the plugin" pattern), loaded once via `load()` and
rewritten in full on every change.

Per commander, like mining_session_archive.py and the run repositories:
each commander has their own list (their notes, mined tons and depleted
marks are theirs), kept in one file by `commander_data`. A file written
before that was a single shared list; the first commander seen claims it.
Until a commander is known the list is empty, and anything added in that
moment is kept for the first commander seen.
"""
import json
import logging
import os
import time
from dataclasses import asdict, dataclass
from typing import Callable, Optional

from config import appname

from . import commander_data
from . import mining_bearing as bearing

plugin_name = os.path.basename(os.path.dirname(__file__))
logger = logging.getLogger(f"{appname}.{plugin_name}")

SAME_SPOT_M = 100.0
"""A new hotspot saved within this distance of an existing one on the same
body is treated as the same deposit and updates it rather than adding a
second entry."""

MINED_ATTRIBUTION_M = 200.0
"""Refined tons are credited to the nearest positioned hotspot within this
distance of the Rhino - rigs sit up to a deposit-radius from its centre."""

_MINED_SAVE_INTERVAL_S = 5.0
"""Tons arrive roughly once a second per rig; the file is rewritten at
most this often while counting (and on flush())."""

HOTSPOTS_FILENAME = "mining_hotspots.json"
"""Prefixed `mining_` for the same collision-clarity reasoning as
mining_session_archive.py's directory name. Not committed to
git and not part of any release build - the commander's own data, not
something to ship empty-but-present to every install, or to overwrite on
update."""


@dataclass
class Hotspot:
    """One recorded surface deposit. `system`/`body` are matched
    case-insensitively against journal StarSystem/Body fields (see
    mining_surface.py's current_system/current_body) to decide what's
    "known here". `latitude`/`longitude` are optional since a commander
    may want to note a body has something worth mining before they've
    pinned down the exact spot. `folder` is a free-text grouping label
    ("" = unfiled) - there's no separate folder-management concept, a
    folder exists as long as some hotspot references it and disappears
    once the last one is renamed or deleted, same as a tag. `rigs` is the
    optional rig capacity of the deposit (how many mining rigs can be
    placed there) - a commander may not know or care to record this, so
    it's optional like position rather than required like `material`.
    `signal_number` is the "Planetary Mining Location Signal N" number
    the system/planet map shows for this specific signal among the
    others on the same body - purely a manual, commander-entered note,
    not derived from anything: `SAASignalsFound` only gives a body-wide
    total Count for the whole `$PlanetaryMiningLocation_Name;` signal
    type, no per-signal index at all, so there's no way to look this
    number up or verify whether it stays fixed for a given body across
    sessions - it's recorded on trust, same as `material`/`notes`.
    `amount`/`density` are the HUD mining scanner's own readout for the
    deposit (mining_deposit.AMOUNTS/DENSITIES) at the time it was last
    recorded - neither is a journal field, so like `signal_number` these
    are commander-entered on trust, not derived. Feeds
    mining_deposit.reserve_text() for an estimated tons-remaining range.
    `mined_tons` is the one derived field: refined tons the journal
    credited to this deposit (see HotspotRepository.add_mined_tons) -
    shown once it is marked Depleted, as what the deposit actually gave."""
    system: str
    body: str
    material: str
    notes: str = ""
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    folder: str = ""
    rigs: Optional[int] = None
    signal_number: Optional[int] = None
    amount: Optional[str] = None
    density: Optional[str] = None
    mined_tons: Optional[int] = None
    ground: Optional[str] = None
    """The kind of ground the body is (mining_ground.classify), stamped when
    the hotspot is saved on a body this session's scan has shown. Feeds the
    Mining Book's "your own rates"; None for hotspots saved or imported
    without it, which still count while their body is in the current
    survey."""

    def matches_body(self, system: str, body: str) -> bool:
        return (self.system.strip().casefold() == system.strip().casefold()
                and self.body.strip().casefold() == body.strip().casefold())

    def has_position(self) -> bool:
        return self.latitude is not None and self.longitude is not None


class HotspotRepository:
    """Constructed empty (no file access at import time, matching
    WNTB's own convention of only touching disk once a `plugin_dir` is
    known) - `load(plugin_dir)` is called once from mining_panel.start()."""

    def __init__(self) -> None:
        self._hotspots: list[Hotspot] = []   # the current commander's (or, before one is known, what was added since)
        self._listeners: list[Callable[[], None]] = []
        self._plugin_dir: Optional[str] = None
        self._mined_dirty = False
        self._last_mined_save = 0.0
        self._store = commander_data.new_store()
        self._cmdr = ""

    def load(self, plugin_dir: str) -> None:
        """Read the file. Nothing is shown until `set_commander` says whose list to use."""
        self._plugin_dir = plugin_dir
        path = os.path.join(plugin_dir, HOTSPOTS_FILENAME)
        try:
            self._store = commander_data.read(path, is_legacy=lambda raw: isinstance(raw, list))
        except Exception:
            logger.exception("Failed to load %s - starting with an empty list", HOTSPOTS_FILENAME)
            self._store = commander_data.new_store()

    def set_commander(self, cmdr: str) -> None:
        """Switch to this commander's list (saving the previous commander's first). The first commander seen claims a
        list saved before hotspots were per commander."""
        key = commander_data.key_for(cmdr)
        if not key or key == commander_data.key_for(self._cmdr):
            return
        pending = [] if self._cmdr else self._hotspots
        if self._cmdr:
            self.flush()
            self._write_current()
        self._cmdr = str(cmdr).strip()
        claimed = commander_data.known(self._store, cmdr) is False and self._store.get("legacy") is not None
        try:
            raw = commander_data.payload_for(self._store, cmdr, list)
            self._hotspots = [Hotspot(**entry) for entry in raw]
        except Exception:
            logger.exception("Failed to read %s's hotspots - starting with an empty list", cmdr)
            self._hotspots = []
        self._hotspots = self._hotspots + pending
        if claimed or pending:
            self._write_current()
        for listener in self._listeners:
            listener()

    def all(self) -> list[Hotspot]:
        return list(self._hotspots)

    def folders(self) -> list[str]:
        """Distinct non-empty folder names currently in use, sorted
        case-insensitively - for populating the dialog's folder picker."""
        seen: dict[str, str] = {}
        for hotspot in self._hotspots:
            name = hotspot.folder.strip()
            if name:
                seen.setdefault(name.casefold(), name)
        return sorted(seen.values(), key=str.casefold)

    def for_body(self, system: Optional[str], body: Optional[str]) -> list[Hotspot]:
        if not system or not body:
            return []
        return [h for h in self._hotspots if h.matches_body(system, body)]

    def materials(self) -> list[str]:
        """Distinct non-empty material names currently in use, sorted
        case-insensitively - for populating a search dialog's material
        picker (see mining_ledger.py)."""
        seen: dict[str, str] = {}
        for hotspot in self._hotspots:
            name = hotspot.material.strip()
            if name:
                seen.setdefault(name.casefold(), name)
        return sorted(seen.values(), key=str.casefold)

    def search(self, material_query: str, rigs: Optional[int] = None) -> list[Hotspot]:
        """Case-insensitive substring match against `material` or
        `notes` - e.g. "diamond" matches "Low Temperature Diamonds".
        Notes is searched too, so a name written only there is still
        found. A
        blank query returns every recorded hotspot rather than none, so
        a search dialog can also serve as a plain "browse everything
        I've recorded" view. `rigs`, if given, further narrows to
        hotspots with that exact recorded rig capacity."""
        query = material_query.strip().casefold()
        matches = self.all() if not query else [
            h for h in self._hotspots
            if query in h.material.casefold() or query in h.notes.casefold()]
        if rigs is not None:
            matches = [h for h in matches if h.rigs == rigs]
        return matches

    def add(self, hotspot: Hotspot) -> None:
        self._hotspots.append(hotspot)
        self._save_and_notify()

    def add_or_merge(self, hotspot: Hotspot, radius_m: Optional[float]) -> bool:
        """add(), except a hotspot with a position that lands within
        SAME_SPOT_M of an existing positioned one on the same body (any
        material - re-saving after correcting the material shouldn't
        leave a second entry at 0 m) updates that one instead. The
        existing position, folder, notes and counted tons stay unless
        the new hotspot supplies its own; the material and any filled-in
        deposit readout (rigs/signal/amount/density) come from the new
        one. Needs `radius_m` (the body's) to measure distance; without
        it, or without a position, this is a plain add. Returns True when
        an existing hotspot was updated."""
        if radius_m and hotspot.has_position():
            for index, existing in enumerate(self._hotspots):
                if not (existing.has_position() and existing.matches_body(hotspot.system, hotspot.body)):
                    continue
                if bearing.distance_m(existing.latitude, existing.longitude,
                                      hotspot.latitude, hotspot.longitude, radius_m) > SAME_SPOT_M:
                    continue
                self.update(index, Hotspot(
                    system=existing.system, body=existing.body, material=hotspot.material,
                    notes=hotspot.notes or existing.notes,
                    latitude=existing.latitude, longitude=existing.longitude,
                    folder=hotspot.folder or existing.folder,
                    rigs=hotspot.rigs if hotspot.rigs is not None else existing.rigs,
                    signal_number=(hotspot.signal_number if hotspot.signal_number is not None
                                   else existing.signal_number),
                    amount=hotspot.amount or existing.amount,
                    density=hotspot.density or existing.density,
                    mined_tons=existing.mined_tons,
                    ground=hotspot.ground or existing.ground))
                return True
        self.add(hotspot)
        return False

    def add_mined_tons(self, system: str, body: str, latitude: float, longitude: float,
                       radius_m: float, tons: int = 1) -> bool:
        """Credits `tons` to the nearest positioned hotspot on this body
        within MINED_ATTRIBUTION_M of the given spot (even after it was
        marked Depleted - leftover fragments still belong to that
        deposit). Returns True when one was found. Counts in memory and
        writes the file at most every _MINED_SAVE_INTERVAL_S rather than
        per ton; listeners aren't notified per ton either - flush() does
        both at the end."""
        best: Optional[Hotspot] = None
        best_distance = MINED_ATTRIBUTION_M
        for candidate in self._hotspots:
            if not (candidate.has_position() and candidate.matches_body(system, body)):
                continue
            distance = bearing.distance_m(candidate.latitude, candidate.longitude,
                                          latitude, longitude, radius_m)
            if distance <= best_distance:
                best, best_distance = candidate, distance
        if best is None:
            return False
        best.mined_tons = (best.mined_tons or 0) + tons
        self._mined_dirty = True
        now = time.monotonic()
        if now - self._last_mined_save >= _MINED_SAVE_INTERVAL_S:
            self.flush()
        return True

    def flush(self) -> None:
        """Writes any counted-but-unsaved mined tons, and tells listeners
        (so the panel's tons-left/depleted text catches up)."""
        if not self._mined_dirty:
            return
        self._mined_dirty = False
        self._last_mined_save = time.monotonic()
        self._save_and_notify()

    def update(self, index: int, hotspot: Hotspot) -> None:
        self._hotspots[index] = hotspot
        self._save_and_notify()

    def remove(self, index: int) -> None:
        del self._hotspots[index]
        self._save_and_notify()

    def import_from_file(self, path: str, *, merge: bool) -> int:
        """Loads hotspots from a JSON file and either appends them to the
        current list (merge=True, for combining lists shared between
        players) or replaces it entirely (merge=False, for restoring a
        backup). Returns how many were imported; raises on a malformed
        file so the caller can show the error rather than silently
        losing data.

        Reads WNTB's own export (same shape as HOTSPOTS_FILENAME - a flat
        list of Hotspot-shaped dicts)."""
        with open(path, "r", encoding="utf8") as fh:
            raw = json.load(fh)
        imported = [Hotspot(**entry) for entry in raw]
        self._hotspots = self._hotspots + imported if merge else imported
        self._save_and_notify()
        return len(imported)

    def export_to_file(self, path: str) -> None:
        with open(path, "w", encoding="utf8") as fh:
            fh.write(self._serialize())

    def add_listener(self, listener: Callable[[], None]) -> None:
        self._listeners.append(listener)

    def remove_listener(self, listener: Callable[[], None]) -> None:
        if listener in self._listeners:
            self._listeners.remove(listener)

    def _serialize(self) -> str:
        """The current commander's list as a plain JSON list (what Export writes, and Import reads back)."""
        return json.dumps([asdict(h) for h in self._hotspots], indent=2)

    def _write_current(self) -> None:
        if self._plugin_dir is None or not self._cmdr:
            return
        commander_data.put(self._store, self._cmdr, [asdict(h) for h in self._hotspots])
        commander_data.write(os.path.join(self._plugin_dir, HOTSPOTS_FILENAME), self._store)

    def _save_and_notify(self) -> None:
        self._save()
        for listener in self._listeners:
            listener()

    def _save(self) -> None:
        # With no commander known yet there is nowhere to save to: the list stays in memory and goes to the first
        # commander seen (set_commander).
        try:
            self._write_current()
        except Exception:
            logger.exception("Failed to save %s", HOTSPOTS_FILENAME)


hotspot_repository = HotspotRepository()
