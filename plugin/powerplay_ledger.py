"""Per-commander, per-system Powerplay ledger: what a commander did in each
system this Powerplay cycle, and how the system itself moved.

The Powerplay counterpart of bgs_ledger.py. Where the BGS ledger is bounded by
the galaxy tick, this one is bounded by the weekly Powerplay cycle (Thursday
07:00 UTC) - the moment control, reinforcement and undermining totals are
settled and reset. Pure logic: no Tk, no EDMC imports, so it is unit-tested
directly (tests/test_powerplay_ledger.py).

Two kinds of data are kept per system:

- **Standing** - a snapshot of the system's Powerplay state taken from
  FSDJump/Location/CarrierJump: state, controlling Power, the Powers in play,
  `PowerplayStateControlProgress` (0-1), `PowerplayStateReinforcement` and
  `PowerplayStateUndermining`. `before` is the baseline (the last reading from
  an earlier cycle, else the first reading this cycle) and `now` the newest, so
  the change between them is the system's gain or loss since the baseline -
  whoever caused it, not only this commander.
- **What the commander did** - merits and event counts per activity (the same
  attribution powerplay.PowerplayTracker already makes), tallied here per
  system and per cycle, rather than per game session.

The ledger also knows how far it can be trusted (`covered_from`, `seen_to`, `last_merit_ts`) so the
journal back-fill (powerplay_backfill.py) scans only what is missing: `plan_scan` says what cycle it is,
which cycles aren't in the history yet and how many days back to read.

The commander's tab choices live in `TabPrefs` (pinned, capped at MAX_PINNED,
and hidden). Persistence is powerplay_state.py's job."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from .formulas import ACTIVITIES

RECENT_SYSTEMS = 6
"""How many recently visited systems get a tab (pinned ones are extra)."""

MAX_PINNED = 5
"""How many systems a commander can pin at once."""

MAX_ARCHIVE = 52
"""How many closed cycles are kept (a year)."""

DEFAULT_BACKFILL_CYCLES = 4
MAX_BACKFILL_CYCLES = 12
"""How many cycles (the current one included) the journal scan covers by default / at most."""

UP_TO_DATE_WINDOW = timedelta(minutes=2)
"""If the ledger has seen the journal this recently there is nothing to scan."""

SCHEMA = 2
"""Saved-ledger layout. 2 added the per-day merit tally; an older ledger is rebuilt from the journals once."""

SCAN_NONE = "none"
SCAN_INCREMENTAL = "incremental"
SCAN_REBUILD = "rebuild"

MAX_NAME_CHARS = 60
"""Cap on a stored/typed system name (Elite names are far shorter)."""

CYCLE = timedelta(days=7)
ANCHOR_CYCLE = 101
ANCHOR_START = datetime(2026, 10, 1, 7, 0, tzinfo=timezone.utc)
"""Powerplay cycle 101 began at this moment; every other cycle number counts weeks from it."""
_CYCLE_WEEKDAY = 3  # Thursday (Monday = 0)
_CYCLE_HOUR_UTC = 7

_TS_FORMAT = "%Y-%m-%dT%H:%M:%SZ"
_SNAPSHOT_FIELDS = ("state", "controller", "powers", "progress", "reinforcement", "undermining", "at")


def parse_ts(value: Any) -> Optional[datetime]:
    """Journal / stored timestamp -> aware UTC datetime, or None."""
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def format_ts(moment: datetime) -> str:
    return moment.astimezone(timezone.utc).strftime(_TS_FORMAT)


def cycle_start_for(moment: datetime) -> datetime:
    """The start (Thursday 07:00 UTC) of the Powerplay cycle `moment` falls in."""
    moment = moment.astimezone(timezone.utc)
    start = moment.replace(hour=_CYCLE_HOUR_UTC, minute=0, second=0, microsecond=0)
    start -= timedelta(days=(moment.weekday() - _CYCLE_WEEKDAY) % 7)
    if start > moment:
        start -= CYCLE
    return start


def cycle_number(start: Optional[datetime]) -> Optional[int]:
    """The Powerplay cycle number for a cycle starting at `start` (101 began 2026-10-01 07:00 UTC)."""
    if start is None:
        return None
    return ANCHOR_CYCLE + (start.astimezone(timezone.utc) - ANCHOR_START) // CYCLE


def _clip(name: str) -> str:
    return " ".join(str(name).split())[:MAX_NAME_CHARS]


def _same(a: str, b: str) -> bool:
    return a.casefold() == b.casefold()


# --- standing snapshot --------------------------------------------------------


@dataclass
class Snapshot:
    """One reading of a system's Powerplay standing."""

    at: str
    state: Optional[str] = None
    controller: Optional[str] = None
    powers: List[str] = field(default_factory=list)
    progress: Optional[float] = None  # control progress, 0-1 as the journal reports it
    reinforcement: Optional[int] = None
    undermining: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        return {name: getattr(self, name) for name in _SNAPSHOT_FIELDS}

    @classmethod
    def from_dict(cls, data: Any) -> Optional["Snapshot"]:
        if not isinstance(data, dict) or not isinstance(data.get("at"), str):
            return None
        powers = data.get("powers")
        return cls(
            at=data["at"],
            state=data["state"] if isinstance(data.get("state"), str) else None,
            controller=data["controller"] if isinstance(data.get("controller"), str) else None,
            powers=[str(p) for p in powers] if isinstance(powers, list) else [],
            progress=_number(data.get("progress"), float),
            reinforcement=_number(data.get("reinforcement"), int),
            undermining=_number(data.get("undermining"), int),
        )


def _number(value: Any, kind: type) -> Optional[Any]:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return kind(value)


def parse_snapshot(entry: Dict[str, Any]) -> Optional[Snapshot]:
    """Standing snapshot from an FSDJump/Location/CarrierJump entry, or None
    when the system isn't Powerplay-relevant (the entry carries none of the
    Powerplay fields)."""
    if not any(key in entry for key in ("PowerplayState", "Powers", "ControllingPower")):
        return None
    at = entry.get("timestamp")
    if parse_ts(at) is None:
        return None
    state = entry.get("PowerplayState")
    controller = entry.get("ControllingPower")
    powers = entry.get("Powers")
    return Snapshot(
        at=at,
        state=str(state) if state else None,
        controller=str(controller) if controller else None,
        powers=[str(p) for p in powers] if isinstance(powers, list) else [],
        progress=_number(entry.get("PowerplayStateControlProgress"), float),
        reinforcement=_number(entry.get("PowerplayStateReinforcement"), int),
        undermining=_number(entry.get("PowerplayStateUndermining"), int),
    )


# --- per-system record ---------------------------------------------------------


@dataclass
class SystemRecord:
    system: str
    before: Optional[Snapshot] = None
    now: Optional[Snapshot] = None
    merits: Dict[str, int] = field(default_factory=dict)
    events: Dict[str, int] = field(default_factory=dict)
    last_at: str = ""

    def latest(self) -> Optional[Snapshot]:
        return self.now or self.before

    def total_merits(self) -> int:
        return sum(self.merits.values())

    def has_data(self) -> bool:
        return self.before is not None or self.total_merits() > 0

    def progress_change(self) -> Optional[float]:
        """Control-progress movement in percentage points (negative = lost), or None."""
        now = self.latest()
        if self.before is None or now is None or self.before.progress is None or now.progress is None:
            return None
        return (now.progress - self.before.progress) * 100.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "system": self.system,
            "before": self.before.to_dict() if self.before else None,
            "now": self.now.to_dict() if self.now else None,
            "merits": dict(self.merits),
            "events": dict(self.events),
            "last_at": self.last_at,
        }

    @classmethod
    def from_dict(cls, data: Any) -> Optional["SystemRecord"]:
        if not isinstance(data, dict) or not data.get("system"):
            return None

        def counts(raw: Any) -> Dict[str, int]:
            return {str(k): int(v) for k, v in raw.items() if isinstance(v, int) and not isinstance(v, bool)} \
                if isinstance(raw, dict) else {}

        return cls(
            system=_clip(data["system"]),
            before=Snapshot.from_dict(data.get("before")),
            now=Snapshot.from_dict(data.get("now")),
            merits=counts(data.get("merits")), events=counts(data.get("events")),
            last_at=data["last_at"] if isinstance(data.get("last_at"), str) else "",
        )


# --- tab preferences -----------------------------------------------------------


@dataclass
class TabPrefs:
    """A commander's pinned and hidden system tabs. Names match case-insensitively."""

    pinned: List[str] = field(default_factory=list)
    hidden: List[str] = field(default_factory=list)

    def is_pinned(self, system: str) -> bool:
        return any(_same(system, p) for p in self.pinned)

    def is_hidden(self, system: str) -> bool:
        return any(_same(system, h) for h in self.hidden)

    def toggle_pin(self, system: str) -> bool:
        """Pin or unpin. False (nothing changed) when pinning would pass MAX_PINNED."""
        if self.is_pinned(system):
            self.pinned = [p for p in self.pinned if not _same(p, system)]
            return True
        return self.add(system)

    def close(self, system: str) -> None:
        """Hide the system's tab (and unpin it)."""
        self.pinned = [p for p in self.pinned if not _same(p, system)]
        if not self.is_hidden(system):
            self.hidden.append(system)

    def add(self, system: str) -> bool:
        """Pin and un-hide a system. False (nothing changed) when it isn't
        already pinned and MAX_PINNED are."""
        if not self.is_pinned(system):
            if len(self.pinned) >= MAX_PINNED:
                return False
            self.pinned.append(system)
        self.hidden = [h for h in self.hidden if not _same(h, system)]
        return True

    @classmethod
    def from_dict(cls, pinned: Any, hidden: Any) -> "TabPrefs":
        def names(raw: Any) -> List[str]:
            return [_clip(n) for n in raw if n] if isinstance(raw, list) else []

        prefs = cls(hidden=names(hidden))
        for name in names(pinned):  # re-applies the cap to hand-edited / older files
            if not prefs.is_pinned(name) and len(prefs.pinned) < MAX_PINNED:
                prefs.pinned.append(name)
        return prefs


# --- cycle views ---------------------------------------------------------------


@dataclass
class CycleView:
    """Read-only view of one cycle for the window: the live one or an archived one."""

    cycle_start: Optional[str]
    cycle_end: Optional[str]
    current: bool
    records: Dict[str, SystemRecord] = field(default_factory=dict)  # casefolded name -> record
    powers: List[str] = field(default_factory=list)
    """The Power(s) the commander was pledged to during the cycle (empty = none seen / not pledged)."""
    daily: Dict[str, Dict[str, int]] = field(default_factory=dict)
    """Merits per activity for each day of the cycle: "1" (first 24 h from the cycle start) to "7"."""

    @property
    def number(self) -> Optional[int]:
        return cycle_number(parse_ts(self.cycle_start))

    def merit_totals(self) -> Dict[str, int]:
        """Merits per activity across every system this cycle (activities with none are absent)."""
        totals: Dict[str, int] = {}
        for record in self.records.values():
            for activity, merits in record.merits.items():
                if merits:
                    totals[activity] = totals.get(activity, 0) + merits
        return totals

    def day_merits(self, day: int) -> Dict[str, int]:
        """Merits per activity on cycle day `day` (1-7); empty if none."""
        return dict(self.daily.get(str(day), {}))

    def systems_worked(self) -> int:
        """How many systems the commander earned merits in this cycle."""
        return sum(1 for r in self.records.values() if r.total_merits() > 0)

    def record_for(self, system: str) -> Optional[SystemRecord]:
        return self.records.get(system.casefold())

    def systems(
        self, current_system: Optional[str] = None, prefs: Optional[TabPrefs] = None,
        limit: Optional[int] = None,
    ) -> List[str]:
        """Systems to give a tab: pinned ones first (always, even with no data),
        then the `limit` most recently active others - the one the commander is
        in leads, in the live cycle - minus any they hid. `limit=None` = all."""
        prefs = prefs or TabPrefs()
        ordered = [r.system for r in sorted(
            (r for r in self.records.values() if r.has_data()), key=lambda r: r.last_at, reverse=True)]
        if self.current and current_system:
            ordered = [s for s in ordered if not _same(s, current_system)]
            ordered.insert(0, current_system)
        known = {name.casefold(): name for name in ordered}  # keep the spelling the data uses
        starred = [known.get(p.casefold(), p) for p in sorted(prefs.pinned, key=str.casefold)]
        rest = [n for n in ordered if not prefs.is_pinned(n) and not prefs.is_hidden(n)]
        return starred + (rest if limit is None else rest[:limit])


def view_from_archive(record: Dict[str, Any]) -> CycleView:
    raw = record.get("systems")
    parsed = [SystemRecord.from_dict(v) for v in raw.values()] if isinstance(raw, dict) else []
    powers = record.get("powers")
    return CycleView(
        daily=_clean_daily(record.get("daily")),
        cycle_start=record.get("cycle_start"), cycle_end=record.get("cycle_end"), current=False,
        records={r.system.casefold(): r for r in parsed if r},
        powers=[str(p) for p in powers] if isinstance(powers, list) else [],
    )


# --- the ledger ----------------------------------------------------------------


class PowerplayLedger:
    """The live cycle for one commander, plus the archive of closed ones."""

    def __init__(self) -> None:
        self.cycle_start: Optional[datetime] = None
        self.records: Dict[str, SystemRecord] = {}
        self.powers: List[str] = []
        """Power(s) the commander was pledged to this cycle, in the order seen."""
        self.daily: Dict[str, Dict[str, int]] = {}
        """This cycle's merits per activity per cycle day ("1".."7") - see CycleView.daily."""
        self.schema = SCHEMA
        self.last_merit_ts: Optional[str] = None
        """Timestamp of the newest merit event counted - older ones are never counted again."""
        self.last_merit_n = 0
        """How many merit events counted share `last_merit_ts` (journal timestamps are whole seconds)."""
        self._replay_dups = 0
        self.covered_from: Optional[datetime] = None
        """The ledger is complete (journal-checked or live) from this moment on; None = never scanned."""
        self.seen_to: Optional[str] = None
        """Timestamp of the newest journal event the ledger is known to be up to date with."""
        self.archive: List[Dict[str, Any]] = []
        """Closed cycles, newest first: {"cycle_start", "cycle_end", "systems"}."""

    # -- cycle bookkeeping --

    def _advance(self, when: datetime) -> None:
        """Start (or roll to) the cycle `when` belongs to. Never moves backwards."""
        if self.cycle_start is None:
            self.cycle_start = cycle_start_for(when)
            return
        if when < self.cycle_start + CYCLE:
            return
        kept = {k: r.to_dict() for k, r in self.records.items() if r.has_data()}
        if kept:
            self.archive.insert(0, {
                "cycle_start": format_ts(self.cycle_start),
                "cycle_end": format_ts(self.cycle_start + CYCLE),
                "systems": kept,
                "powers": list(self.powers),
                "daily": {d: dict(m) for d, m in self.daily.items()},
            })
            del self.archive[MAX_ARCHIVE:]
        # Each system's newest reading is the next cycle's baseline.
        carried: Dict[str, SystemRecord] = {}
        for key, record in self.records.items():
            latest = record.latest()
            if latest is not None:
                carried[key] = SystemRecord(system=record.system, before=latest, last_at=record.last_at)
        self.records = carried
        self.daily = {}
        self.powers = self.powers[-1:]  # still pledged to the same Power until told otherwise
        self.cycle_start = cycle_start_for(when)

    def _record(self, system: str) -> SystemRecord:
        name = _clip(system)
        record = self.records.get(name.casefold())
        if record is None:
            record = self.records[name.casefold()] = SystemRecord(system=name)
        return record

    # -- feeding --

    def record_snapshot(self, system: str, snapshot: Snapshot) -> None:
        """A standing reading for `system`. Readings from before the cycle only
        refresh the baseline; out-of-order ones never replace a newer reading."""
        when = parse_ts(snapshot.at)
        if not system or when is None:
            return
        self._advance(when)
        assert self.cycle_start is not None
        record = self._record(system)
        if when < self.cycle_start:
            if record.before is None or snapshot.at > record.before.at:
                record.before = snapshot
            return
        if record.before is None:
            record.before = snapshot
        elif record.now is None or snapshot.at >= record.now.at:
            record.now = snapshot
        if snapshot.at > record.last_at:
            record.last_at = snapshot.at

    def begin_replay(self) -> None:
        """Call before feeding journal-replayed merits (record_merits(replay=True))."""
        self._replay_dups = 0

    def record_merits(
        self, system: str, activity: str, merits: int, timestamp: Optional[str], replay: bool = False,
    ) -> bool:
        """Merits earned in `system`. False if ignored (no system/merits, no
        usable timestamp, from before this cycle, or - for a replay - already counted)."""
        when = parse_ts(timestamp)
        if not system or merits <= 0 or when is None:
            return False
        self._advance(when)
        assert self.cycle_start is not None
        if when < self.cycle_start:
            return False
        if self.last_merit_ts is not None:
            if timestamp < self.last_merit_ts:  # type: ignore[operator]
                return False  # older than what is already counted
            if timestamp == self.last_merit_ts and replay:
                # Same second as the newest counted merit: the first `last_merit_n` replayed
                # events at this stamp are the ones already counted; later ones are new.
                self._replay_dups += 1
                if self._replay_dups <= self.last_merit_n:
                    return False
        if timestamp == self.last_merit_ts:
            self.last_merit_n += 1
        else:
            self.last_merit_ts, self.last_merit_n, self._replay_dups = timestamp, 1, 0
        day = str(max(1, min(7, (when - self.cycle_start) // timedelta(days=1) + 1)))
        by_activity = self.daily.setdefault(day, {})
        by_activity[activity] = by_activity.get(activity, 0) + merits
        record = self._record(system)
        record.merits[activity] = record.merits.get(activity, 0) + merits
        record.events[activity] = record.events.get(activity, 0) + 1
        if timestamp > record.last_at:  # type: ignore[operator]
            record.last_at = timestamp  # type: ignore[assignment]
        return True

    def record_power(self, power: Optional[str], timestamp: Optional[str] = None) -> None:
        """Note the Power the commander is pledged to (None / blank = not pledged: nothing to note).
        A `timestamp` (journal replay) files it under the cycle it belongs to."""
        name = _clip(power) if power else ""
        if not name:
            return
        when = parse_ts(timestamp)
        if when is not None:
            self._advance(when)
            if self.cycle_start is not None and when < self.cycle_start:
                return
        if name not in self.powers:
            self.powers.append(name)

    def touch(self, timestamp: Any) -> None:
        """The journal has been seen up to `timestamp` (any live event)."""
        if isinstance(timestamp, str) and parse_ts(timestamp) is not None \
                and (self.seen_to is None or timestamp > self.seen_to):
            self.seen_to = timestamp

    def roll_to(self, moment: datetime) -> bool:
        """Roll the cycle forward if `moment` is past its end, so a cycle that
        ended is archived on time rather than at the next event. True if it rolled."""
        before = self.cycle_start
        self._advance(moment)
        return before != self.cycle_start

    # -- journal scan planning and adoption --

    def plan_scan(self, now: datetime, depth: int = DEFAULT_BACKFILL_CYCLES) -> "ScanPlan":
        """What the startup journal scan has to do: which cycle it is, which of
        the last `depth` cycles aren't covered yet, and how far back to read.

        - Never scanned, or the history doesn't reach back `depth` cycles:
          **rebuild** from the oldest wanted cycle.
        - Otherwise **incremental**: only what happened since the ledger last saw
          the journal (a gap while EDMC was closed), or **none** if that is moments ago."""
        depth = max(1, min(MAX_BACKFILL_CYCLES, depth))
        now = now.astimezone(timezone.utc)
        current = cycle_start_for(now)
        oldest = current - CYCLE * (depth - 1)
        wanted = [current - CYCLE * n for n in range(depth - 1, -1, -1)]
        missing = [cycle_number(c) for c in wanted
                   if self.covered_from is None or c < self.covered_from or self.schema < SCHEMA]
        scan_from: Optional[datetime] = None
        if self.covered_from is None or self.covered_from > oldest or self.schema < SCHEMA:
            mode, scan_from = SCAN_REBUILD, oldest
        else:
            seen = parse_ts(self.seen_to) or current
            if now - seen < UP_TO_DATE_WINDOW:
                mode = SCAN_NONE
            else:
                mode, scan_from = SCAN_INCREMENTAL, max(seen, oldest)
        days_back = math.ceil((now - scan_from).total_seconds() / 86400) if scan_from else 0
        return ScanPlan(
            mode=mode, current_cycle=cycle_number(current) or 0, cycle_start=current,
            day_of_cycle=(now - current).days + 1, scan_from=scan_from, days_back=days_back,
            missing_cycles=[n for n in missing if n is not None],
        )

    def adopt(self, fresh: "PowerplayLedger", covered_from: datetime, seen_to: Optional[str]) -> None:
        """Take a ledger rebuilt from the journals (the **rebuild** scan) into this one.

        The journals are the truth, but never lose data they no longer hold: for a
        cycle both have, the one with more merits wins (the rebuild on a tie).
        The history stays newest first and capped. Everything from `covered_from`
        on now counts as covered."""
        if fresh.cycle_start is not None:
            if self.cycle_start is None:
                self.cycle_start = fresh.cycle_start
            elif fresh.cycle_start < self.cycle_start:
                fresh.roll_to(self.cycle_start)  # the rebuild's last cycle is already over: into its history
            else:
                self.roll_to(fresh.cycle_start)  # an older live cycle goes to the history first
            merged = {r["cycle_start"]: r for r in self.archive if isinstance(r.get("cycle_start"), str)}
            for record in fresh.archive:
                key = record.get("cycle_start")
                if isinstance(key, str) and (key not in merged or _archived_merits(record) >= _archived_merits(merged[key])):
                    merged[key] = record
            self.archive = sorted(merged.values(), key=lambda r: r["cycle_start"], reverse=True)[:MAX_ARCHIVE]
            if fresh.cycle_start == self.cycle_start:
                if sum(r.total_merits() for r in fresh.records.values()) >= \
                        sum(r.total_merits() for r in self.records.values()):
                    self.records, self.daily = fresh.records, fresh.daily
                self.powers = fresh.powers or self.powers
        if fresh.last_merit_ts and (self.last_merit_ts is None or fresh.last_merit_ts > self.last_merit_ts):
            self.last_merit_ts, self.last_merit_n = fresh.last_merit_ts, fresh.last_merit_n
        for stamp in (seen_to, fresh.seen_to):
            self.touch(stamp)
        if self.covered_from is None or covered_from < self.covered_from:
            self.covered_from = covered_from
        self.schema = SCHEMA

    # -- views --

    def views(self) -> List[CycleView]:
        """The live cycle first, then the closed ones, newest first and in order: a cycle the
        ledger covers but nothing happened in (so it wasn't archived) appears as an empty view."""
        live = CycleView(
            cycle_start=format_ts(self.cycle_start) if self.cycle_start else None, cycle_end=None,
            current=True, records=dict(self.records), powers=list(self.powers),
            daily={d: dict(m) for d, m in self.daily.items()})
        closed = {r["cycle_start"]: view_from_archive(r) for r in self.archive if isinstance(r.get("cycle_start"), str)}
        if self.cycle_start is not None and self.covered_from is not None:
            start = self.cycle_start - CYCLE
            for _ in range(MAX_ARCHIVE):
                if start < self.covered_from:
                    break
                key = format_ts(start)
                closed.setdefault(key, CycleView(cycle_start=key, cycle_end=format_ts(start + CYCLE), current=False))
                start -= CYCLE
        return [live] + [closed[k] for k in sorted(closed, reverse=True)]

    def known_systems(self) -> List[str]:
        """Every system any view has data for, live cycle first."""
        seen: Dict[str, str] = {}
        for view in self.views():
            for name in view.systems():
                seen.setdefault(name.casefold(), name)
        return list(seen.values())

    # -- persistence --

    def to_dict(self) -> Dict[str, Any]:
        return {
            "cycle_start": format_ts(self.cycle_start) if self.cycle_start else None,
            "systems": {k: r.to_dict() for k, r in self.records.items()},
            "powers": list(self.powers),
            "daily": {d: dict(m) for d, m in self.daily.items()},
            "schema": self.schema,
            "last_merit_ts": self.last_merit_ts,
            "last_merit_n": self.last_merit_n,
            "covered_from": format_ts(self.covered_from) if self.covered_from else None,
            "seen_to": self.seen_to,
            "archive": self.archive,
        }

    @classmethod
    def from_dict(cls, data: Any) -> "PowerplayLedger":
        ledger = cls()
        if not isinstance(data, dict):
            return ledger
        ledger.cycle_start = parse_ts(data.get("cycle_start"))
        raw = data.get("systems")
        for value in (raw.values() if isinstance(raw, dict) else ()):
            record = SystemRecord.from_dict(value)
            if record:
                ledger.records[record.system.casefold()] = record
        powers = data.get("powers")
        ledger.powers = [_clip(p) for p in powers if p] if isinstance(powers, list) else []
        ledger.last_merit_ts = data["last_merit_ts"] if parse_ts(data.get("last_merit_ts")) else None
        ledger.daily = _clean_daily(data.get("daily"))
        schema = data.get("schema")
        ledger.schema = schema if isinstance(schema, int) and not isinstance(schema, bool) else 1
        n = data.get("last_merit_n")
        ledger.last_merit_n = n if isinstance(n, int) and not isinstance(n, bool) and n > 0 else \
            (1 if ledger.last_merit_ts else 0)
        ledger.covered_from = parse_ts(data.get("covered_from"))
        ledger.seen_to = data["seen_to"] if parse_ts(data.get("seen_to")) else None
        archive = data.get("archive")
        if isinstance(archive, list):
            ledger.archive = [r for r in archive if isinstance(r, dict)][:MAX_ARCHIVE]
        return ledger


@dataclass
class ScanPlan:
    """What the startup journal scan will do - see PowerplayLedger.plan_scan."""

    mode: str
    current_cycle: int
    cycle_start: datetime
    day_of_cycle: int
    scan_from: Optional[datetime]
    days_back: int
    missing_cycles: List[int]

    def describe(self) -> str:
        where = f"Cycle {self.current_cycle}, day {self.day_of_cycle} of 7"
        if self.mode == SCAN_NONE:
            return f"{where}. Journal scan: up to date."
        gap = ""
        if self.missing_cycles:
            gap = f" Not in history yet: cycle{'s' if len(self.missing_cycles) > 1 else ''} " \
                  f"{', '.join(str(n) for n in self.missing_cycles)}."
        return f"{where}. Journal scan: reading {self.days_back} day{'s' if self.days_back != 1 else ''} back.{gap}"


def _clean_daily(raw: Any) -> Dict[str, Dict[str, int]]:
    """Per-day merit tallies from saved data, dropping anything malformed."""
    out: Dict[str, Dict[str, int]] = {}
    for day, by_activity in (raw.items() if isinstance(raw, dict) else ()):
        if isinstance(by_activity, dict):
            out[str(day)] = {str(a): int(m) for a, m in by_activity.items()
                             if isinstance(m, int) and not isinstance(m, bool)}
    return out


def _archived_merits(record: Dict[str, Any]) -> int:
    """Total merits in an archived cycle record (junk-tolerant)."""
    systems = record.get("systems")
    total = 0
    for system in (systems.values() if isinstance(systems, dict) else ()):
        merits = system.get("merits") if isinstance(system, dict) else None
        total += sum(v for v in merits.values() if isinstance(v, int)) if isinstance(merits, dict) else 0
    return total


def activity_rows(record: Optional[SystemRecord]) -> List[str]:
    """Activities this record has merits for, in display order."""
    return [a for a in ACTIVITIES if record and record.merits.get(a)]
