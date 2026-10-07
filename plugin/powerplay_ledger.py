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

The commander's tab choices live in `TabPrefs` (pinned, capped at MAX_PINNED,
and hidden). Persistence is powerplay_state.py's job."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from .formulas import ACTIVITIES

RECENT_SYSTEMS = 6
"""How many recently visited systems get a tab (pinned ones are extra)."""

MAX_PINNED = 5
"""How many systems a commander can pin at once."""

MAX_ARCHIVE = 8
"""How many closed cycles are kept (about two months)."""

MAX_NAME_CHARS = 60
"""Cap on a stored/typed system name (Elite names are far shorter)."""

CYCLE = timedelta(days=7)
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
    return CycleView(
        cycle_start=record.get("cycle_start"), cycle_end=record.get("cycle_end"), current=False,
        records={r.system.casefold(): r for r in parsed if r},
    )


# --- the ledger ----------------------------------------------------------------


class PowerplayLedger:
    """The live cycle for one commander, plus the archive of closed ones."""

    def __init__(self) -> None:
        self.cycle_start: Optional[datetime] = None
        self.records: Dict[str, SystemRecord] = {}
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
            })
            del self.archive[MAX_ARCHIVE:]
        # Each system's newest reading is the next cycle's baseline.
        carried: Dict[str, SystemRecord] = {}
        for key, record in self.records.items():
            latest = record.latest()
            if latest is not None:
                carried[key] = SystemRecord(system=record.system, before=latest, last_at=record.last_at)
        self.records = carried
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

    def record_merits(self, system: str, activity: str, merits: int, timestamp: Optional[str]) -> bool:
        """Merits earned in `system`. False if ignored (no system/merits, no
        usable timestamp, or from before this cycle)."""
        when = parse_ts(timestamp)
        if not system or merits <= 0 or when is None:
            return False
        self._advance(when)
        assert self.cycle_start is not None
        if when < self.cycle_start:
            return False
        record = self._record(system)
        record.merits[activity] = record.merits.get(activity, 0) + merits
        record.events[activity] = record.events.get(activity, 0) + 1
        if timestamp > record.last_at:  # type: ignore[operator]
            record.last_at = timestamp  # type: ignore[assignment]
        return True

    def roll_to(self, moment: datetime) -> None:
        """Roll the cycle forward if `moment` is past its end - used on load, so
        a cycle that ended while EDMC was closed is archived before new data."""
        self._advance(moment)

    # -- views --

    def views(self) -> List[CycleView]:
        """The live cycle first, then archived ones (newest first)."""
        live = CycleView(
            cycle_start=format_ts(self.cycle_start) if self.cycle_start else None, cycle_end=None,
            current=True, records=dict(self.records))
        return [live] + [view_from_archive(r) for r in self.archive]

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
        archive = data.get("archive")
        if isinstance(archive, list):
            ledger.archive = [r for r in archive if isinstance(r, dict)][:MAX_ARCHIVE]
        return ledger


def activity_rows(record: Optional[SystemRecord]) -> List[str]:
    """Activities this record has merits for, in display order."""
    return [a for a in ACTIVITIES if record and record.merits.get(a)]
