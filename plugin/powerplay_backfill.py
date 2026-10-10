"""Journal back-fill for the per-system Powerplay ledger: reads a commander's
Journal*.log files and turns what happened into ledger operations, so cycles
played while EDMC was closed (or before this feature existed) are still counted.

Run once per commander at start-up, and only as far as needed - see
powerplay_ledger.PowerplayLedger.plan_scan, which says which cycle it is, which
cycles aren't in the history yet and how many days back to read. The slow part
(reading files) is meant for a worker thread; it never touches the live ledger.
It returns a list of `Op`s which the main thread applies, in time order, with
`apply_ops` - so a cycle that ended during the gap is archived in its right
place and the numbers are the same however the events arrived.

The activity of each merit gain is decided by a fresh `PowerplayTracker` (passed
in as `tracker_factory`, so this module needs no EDMC import and is testable),
fed every event of the commander's session - including those before the scan
window, because the pledge and the system context come from them. A new tracker
starts at each journal file and whenever the commander changes within one.

A missing folder, unreadable file or malformed line never raises: you get what
could be read."""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, Iterable, List, Optional

from config import appname

from .powerplay_ledger import PowerplayLedger, Snapshot, parse_snapshot, parse_ts

plugin_name = os.path.basename(os.path.dirname(__file__))
logger = logging.getLogger(f"{appname}.{plugin_name}")

OP_SNAPSHOT = "snapshot"
OP_MERITS = "merits"
OP_POWER = "power"

_PLEDGE_EVENTS = ("Powerplay", "PowerplayJoin", "PowerplayLeave", "PowerplayDefect")
_CONTEXT_EVENTS = ("Location", "FSDJump", "Docked")
_SNAPSHOT_EVENTS = ("Location", "FSDJump", "CarrierJump")
_DELIVERY_EVENTS = ("PowerplayDeliver", "SearchAndRescue", "DeliverPowerMicroResources")
_RELEVANT = (
    "Fileheader", "Commander", "LoadGame", "Location", "FSDJump", "CarrierJump", "Docked", "PowerplayMerits",
    "PowerplayRank", "PowerplayDeliver", "SearchAndRescue", "DeliverPowerMicroResources", *_PLEDGE_EVENTS,
)
_NEEDLES = tuple(f'"{name}"' for name in _RELEVANT)


@dataclass
class Op:
    """One thing to record in the ledger."""

    kind: str
    ts: str
    system: str = ""
    activity: str = ""
    merits: int = 0
    snapshot: Optional[Snapshot] = None
    power: str = ""


@dataclass
class ScanResult:
    ok: bool
    """False when the journals couldn't be read at all (no folder): nothing was learned."""
    ops: List[Op] = field(default_factory=list)
    last_ts: Optional[str] = None
    """Newest timestamp seen for this commander - the ledger is up to date with the journal to here."""
    files: int = 0


def apply_ops(ledger: PowerplayLedger, ops: Iterable[Op]) -> None:
    """Record replayed `ops` (oldest first) into `ledger`. Safe to repeat: merits
    already counted and older standing readings are ignored by the ledger."""
    ledger.begin_replay()
    for op in ops:
        if op.kind == OP_SNAPSHOT and op.snapshot is not None:
            ledger.record_snapshot(op.system, op.snapshot)
        elif op.kind == OP_MERITS:
            ledger.record_merits(op.system, op.activity, op.merits, op.ts, replay=True)
        elif op.kind == OP_POWER:
            ledger.record_power(op.power, op.ts)


# --- replaying journal entries ----------------------------------------------------


def replay_entries(
    entries: Iterable[Dict[str, Any]], cmdr: str, tracker_factory: Callable[[], Any],
    scan_from: Optional[datetime] = None,
) -> ScanResult:
    """Ops for `cmdr` from the entries of ONE journal file, in order. Everything
    still feeds the tracker; only events at or after `scan_from` become ops."""
    wanted = cmdr.strip().casefold()
    result = ScanResult(ok=True)
    tracker = tracker_factory()
    current = ""
    system: Optional[str] = None
    last_power: Optional[str] = None

    def emit(op: Op) -> None:
        nonlocal last_power
        if tracker.my_power and tracker.my_power != last_power:
            result.ops.append(Op(OP_POWER, op.ts, power=tracker.my_power))
            last_power = tracker.my_power
        result.ops.append(op)

    for entry in entries:
        event = entry.get("event")
        if event == "Fileheader":
            tracker, current, system, last_power = tracker_factory(), "", None, None
            continue
        if event in ("Commander", "LoadGame"):
            name = str(entry.get("Name" if event == "Commander" else "Commander", "")).strip().casefold()
            if name and name != current:
                tracker, current, system, last_power = tracker_factory(), name, None, None
            continue
        if current != wanted:
            continue

        ts = entry.get("timestamp")
        when = parse_ts(ts)
        if when is None:
            continue
        if result.last_ts is None or ts > result.last_ts:
            result.last_ts = ts
        in_window = scan_from is None or when >= scan_from

        star_system = entry.get("StarSystem")
        if star_system:
            system = str(star_system)

        if tracker.apply_pledge_event(event, entry):
            pass
        elif event == "PowerplayRank":
            tracker.apply_rank(entry)
        elif event in _DELIVERY_EVENTS:
            tracker.apply_delivery_signal(event, entry)
        elif event == "PowerplayMerits":
            gained = tracker.apply_merits(entry)
            activity = tracker.classify_current_activity(system)
            if gained is not None and in_window and system:
                emit(Op(OP_MERITS, ts, system=system, activity=activity, merits=gained))
        if event in _CONTEXT_EVENTS:
            tracker.apply_system_context(system, entry)
        if event in _SNAPSHOT_EVENTS and in_window and system:
            snapshot = parse_snapshot(entry)
            if snapshot is not None:
                emit(Op(OP_SNAPSHOT, ts, system=system, snapshot=snapshot))
    return result


# --- reading the journal folder -----------------------------------------------------


def _journal_files(folder: str, since: datetime) -> List[str]:
    """Journal files modified since `since`, oldest first (names sort by date)."""
    found: List[str] = []
    cutoff = since.timestamp()
    try:
        with os.scandir(folder) as entries:
            for entry in entries:
                if entry.name.startswith("Journal") and entry.name.endswith(".log") and entry.is_file() \
                        and entry.stat().st_mtime >= cutoff:
                    found.append(entry.path)
    except OSError:
        logger.warning("Powerplay journal scan: could not list %s", folder)
        return []
    return sorted(found)


def _file_entries(path: str) -> Iterable[Dict[str, Any]]:
    try:
        with open(path, encoding="utf8", errors="replace") as handle:
            for line in handle:
                if not any(needle in line for needle in _NEEDLES):
                    continue
                try:
                    entry = json.loads(line)
                except ValueError:
                    continue
                if isinstance(entry, dict):
                    yield entry
    except OSError:
        logger.warning("Powerplay journal scan: could not read %s", path)


def scan_journals(
    cmdr: str, scan_from: datetime, tracker_factory: Callable[[], Any], folder: str = "",
) -> ScanResult:
    """Read `cmdr`'s journals from `scan_from` to now (see module docs). `folder`
    defaults to EDMC's configured journal folder."""
    if not folder:
        from . import journal_scan  # deferred: only needed for EDMC's configured folder
        folder = journal_scan._journal_folder()
    if not folder or not cmdr:
        logger.warning("Powerplay journal scan skipped: no journal folder (set EDMC's Journal directory "
                       "in Settings - Configuration; on Linux there is no default)")
        return ScanResult(ok=False)
    folder = os.path.expanduser(folder)
    if not os.path.isdir(folder):
        return ScanResult(ok=False)

    total = ScanResult(ok=True)
    for path in _journal_files(folder, scan_from):
        try:
            part = replay_entries(_file_entries(path), cmdr, tracker_factory, scan_from)
        except Exception:  # one odd file must not stop the rest
            logger.exception("Powerplay journal scan: skipped %s", path)
            continue
        total.files += 1
        total.ops.extend(part.ops)
        if part.last_ts and (total.last_ts is None or part.last_ts > total.last_ts):
            total.last_ts = part.last_ts
    return total


def rebuild_ledger(ops: Iterable[Op]) -> PowerplayLedger:
    """A fresh ledger holding just what `ops` describe."""
    fresh = PowerplayLedger()
    apply_ops(fresh, ops)
    return fresh
