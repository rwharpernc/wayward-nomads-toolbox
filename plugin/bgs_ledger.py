"""BGS per-tick ledger - pure logic (no Tk, no network, no EDMC), so the same
code path handles live journal events and a replay of past journal files.

A `TickLedger` holds everything BGS mode knows about *one tick period* (from
one galaxy tick to the next) for one commander:

- `activity`: what the commander did, per system+faction - missions (done,
  failed, abandoned) with their +/- INF pips, bounties, combat bonds, trade,
  exploration data, crimes. Nothing is gated on a "tracked" list: it records
  wherever the commander actually acts.
- `tracks`: per system+faction, the faction's state/influence as last seen
  *before* the tick (`before`) and as last seen since (`now`), so the report
  can show real increases and decreases.

`roll()` closes the period (returning an archivable dict) and starts the
next one. Events older than `tick_start` still update the "where am I / who
owns this station / which missions are open / what was the pre-tick
influence" state but never count as activity - that is what lets a replay of
the last few journals rebuild the current period exactly.

Schema notes live in bgs_state.py; field semantics in docs/BGS_TECH_SPEC.md.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field, fields
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Iterable, List, Optional, Tuple, Type, TypeVar

from . import bgs_tracker
from .bgs_tracker import FactionActivity, FactionSnapshot, snapshot_key

RECENT_SYSTEMS = 6
"""How many recently visited systems get a report tab (pinned ones are extra)."""

MAX_OPEN_MISSIONS = 400
"""Cap on remembered accepted-but-unfinished missions (oldest dropped first)
so an abandoned save can't grow the state file without bound."""

T = TypeVar("T")


def parse_timestamp(text: Any) -> Optional[datetime]:
    """Journal (`...Z`) and `datetime.isoformat()` (`+00:00`) timestamps ->
    an aware UTC datetime, or None if it isn't one."""
    if not isinstance(text, str) or not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _build(cls: Type[T], data: Any) -> Optional[T]:
    """Dataclass from a saved dict, ignoring fields this version doesn't know
    and defaulting ones it does - saved files survive schema growth."""
    if not isinstance(data, dict):
        return None
    known = {f.name for f in fields(cls)}  # type: ignore[arg-type]
    try:
        return cls(**{k: v for k, v in data.items() if k in known})  # type: ignore[call-arg]
    except TypeError:
        return None


@dataclass
class FactionTrack:
    """One faction in one system: its last pre-tick snapshot and its newest
    snapshot since the tick. `now` is None until the commander has seen the
    system again since the tick."""

    system: str
    faction: str
    before: Optional[FactionSnapshot] = None
    now: Optional[FactionSnapshot] = None

    def latest(self) -> Optional[FactionSnapshot]:
        return self.now or self.before

    def influence_delta(self) -> Optional[float]:
        """Change in influence since before the tick, in percentage points
        (None when either end is unknown)."""
        if self.before is None or self.now is None:
            return None
        if self.before.influence is None or self.now.influence is None:
            return None
        return (self.now.influence - self.before.influence) * 100.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "system": self.system, "faction": self.faction,
            "before": asdict(self.before) if self.before else None,
            "now": asdict(self.now) if self.now else None,
        }

    @classmethod
    def from_dict(cls, data: Any) -> Optional["FactionTrack"]:
        if not isinstance(data, dict) or not data.get("system") or not data.get("faction"):
            return None
        return cls(
            system=data["system"], faction=data["faction"],
            before=_build(FactionSnapshot, data.get("before")),
            now=_build(FactionSnapshot, data.get("now")),
        )


@dataclass
class PeriodView:
    """Read-only view of one tick period for the report window: the live
    one (`current=True`) or an archived one."""

    tick_start: Optional[str]
    tick_end: Optional[str]
    current: bool
    activity: List[FactionActivity] = field(default_factory=list)
    tracks: List[FactionTrack] = field(default_factory=list)

    def systems(
        self, current_system: Optional[str] = None, pinned: Iterable[str] = (),
        hidden: Iterable[str] = (), limit: Optional[int] = None,
    ) -> List[str]:
        """Systems to give a tab: pinned ones first (always shown, even with
        no data), then the `limit` most recently visited others - for the
        live period the system the commander is in leads them - skipping any
        the commander has hidden. `limit=None` returns every known system."""
        newest: Dict[str, Tuple[str, str]] = {}

        def note(name: str, stamp: str) -> None:
            key = name.casefold()
            if key not in newest or stamp > newest[key][0]:
                newest[key] = (stamp, name)

        for act in self.activity:
            if not act.is_empty():
                note(act.system, act.last_at)
        for track in self.tracks:
            latest = track.latest()
            note(track.system, latest.updated_at if latest else "")
        ordered = [name for _stamp, name in sorted(newest.values(), reverse=True)]
        if self.current and current_system:
            ordered = [s for s in ordered if s.casefold() != current_system.casefold()]
            ordered.insert(0, current_system)

        pin_list = sorted({p.strip() for p in pinned if p and p.strip()}, key=str.casefold)
        pin_keys = {p.casefold() for p in pin_list}
        hide_keys = {h.casefold() for h in hidden if h}
        known = {name.casefold(): name for name in ordered}  # keep the spelling the data uses
        starred = [known.get(p.casefold(), p) for p in pin_list]
        rest = [n for n in ordered if n.casefold() not in pin_keys and n.casefold() not in hide_keys]
        return starred + (rest if limit is None else rest[:limit])

    def activity_for(self, system: str) -> List[FactionActivity]:
        key = system.casefold()
        return [a for a in self.activity if a.system.casefold() == key and not a.is_empty()]

    def tracks_for(self, system: str) -> List[FactionTrack]:
        key = system.casefold()
        return [t for t in self.tracks if t.system.casefold() == key]


class TickLedger:
    def __init__(self, tick_start: Optional[str] = None) -> None:
        self.tick_start: Optional[str] = tick_start
        self._tick_start_dt = parse_timestamp(tick_start)
        self.activity: Dict[str, FactionActivity] = {}
        self.tracks: Dict[str, FactionTrack] = {}
        self.open_missions: Dict[str, Tuple[str, str]] = {}
        """MissionID -> (issuing faction, system accepted in), for scoring a
        later MissionFailed/MissionAbandoned (neither names a faction)."""

        # Where the commander is - transient, rebuilt by events.
        self.current_system: Optional[str] = None
        self.current_system_factions: Optional[List[FactionSnapshot]] = None
        """None = no faction data yet; [] = confirmed uninhabited."""
        self.station_faction: Optional[str] = None

    # --- period bookkeeping --------------------------------------------------

    def set_tick_start(self, tick_start: Optional[str]) -> None:
        self.tick_start = tick_start
        self._tick_start_dt = parse_timestamp(tick_start)

    def _in_period(self, timestamp: str) -> bool:
        """Does an event at `timestamp` belong to the current period? With no
        known tick start, everything does."""
        if self._tick_start_dt is None:
            return True
        when = parse_timestamp(timestamp)
        return when is None or when >= self._tick_start_dt

    def has_activity(self) -> bool:
        return any(not a.is_empty() for a in self.activity.values())

    def view(self, tick_end: Optional[str] = None, current: bool = True) -> PeriodView:
        return PeriodView(
            tick_start=self.tick_start, tick_end=tick_end, current=current,
            activity=[a for a in self.activity.values() if not a.is_empty()],
            tracks=list(self.tracks.values()),
        )

    def roll(self, new_tick_start: str) -> Optional[Dict[str, Any]]:
        """Close this period at `new_tick_start` and begin the next. Returns
        the closed period as an archive record, or None if nothing happened
        in it (nothing worth keeping). Every faction's newest known snapshot
        becomes the next period's `before` baseline."""
        archived = self.archive_record(new_tick_start) if self.has_activity() else None
        for track in self.tracks.values():
            track.before = track.latest()
            track.now = None
        self.activity = {}
        self.set_tick_start(new_tick_start)
        return archived

    def archive_record(self, tick_end: str) -> Dict[str, Any]:
        """Serializable record of this period. Only systems with activity
        keep their faction tracks - the rest is just galaxy background."""
        active_systems = {a.system.casefold() for a in self.activity.values() if not a.is_empty()}
        return {
            "tick_start": self.tick_start,
            "tick_end": tick_end,
            "activity": {k: asdict(a) for k, a in self.activity.items() if not a.is_empty()},
            "tracks": {
                k: t.to_dict() for k, t in self.tracks.items() if t.system.casefold() in active_systems
            },
        }

    def prune_tracks(self, now: datetime, keep_days: int) -> None:
        """Forget factions not seen for `keep_days` (bounds the state file)."""
        cutoff = now - timedelta(days=max(1, keep_days))
        for key in list(self.tracks):
            latest = self.tracks[key].latest()
            seen = parse_timestamp(latest.updated_at) if latest else None
            if seen is not None and seen < cutoff:
                del self.tracks[key]

    # --- persistence -------------------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        return {
            "tick_start": self.tick_start,
            "activity": {k: asdict(a) for k, a in self.activity.items()},
            "tracks": {k: t.to_dict() for k, t in self.tracks.items()},
            "open_missions": {k: list(v) for k, v in self.open_missions.items()},
        }

    @classmethod
    def from_dict(cls, data: Any) -> "TickLedger":
        ledger = cls()
        if not isinstance(data, dict):
            return ledger
        ledger.set_tick_start(data.get("tick_start"))
        for key, raw in (data.get("activity") or {}).items():
            act = _build(FactionActivity, raw)
            if act is not None:
                ledger.activity[key] = act
        for key, raw in (data.get("tracks") or {}).items():
            track = FactionTrack.from_dict(raw)
            if track is not None:
                ledger.tracks[key] = track
        for key, raw in (data.get("open_missions") or {}).items():
            if isinstance(raw, (list, tuple)) and len(raw) == 2:
                ledger.open_missions[str(key)] = (str(raw[0]), str(raw[1]))
        return ledger

    # --- events --------------------------------------------------------------

    def _act(self, system: str, faction: str, timestamp: str) -> FactionActivity:
        key = snapshot_key(system, faction)
        act = self.activity.setdefault(key, FactionActivity(system=system, faction=faction))
        if timestamp > act.last_at:  # ISO strings of one format sort chronologically
            act.last_at = timestamp
        return act

    def process(self, entry: Dict[str, Any], fallback_system: Optional[str] = None) -> bool:
        """Feed one journal entry (live or replayed). Returns True if anything
        worth persisting/redrawing changed."""
        event = entry.get("event", "")
        timestamp = entry.get("timestamp", "")
        if event in ("FSDJump", "Location", "CarrierJump"):
            return self._on_location(entry, event, fallback_system)
        if event == "Docked":
            self.station_faction = (entry.get("StationFaction") or {}).get("Name")
            if entry.get("StarSystem") and entry["StarSystem"] != self.current_system:
                self.current_system = entry["StarSystem"]
                self.current_system_factions = None
            return False
        if event == "Undocked":
            self.station_faction = None
            return False
        if event == "MissionAccepted":
            return self._on_mission_accepted(entry, fallback_system)

        counted = self._in_period(timestamp)
        system = self.current_system or fallback_system
        if event == "MissionCompleted":
            self.open_missions.pop(str(entry.get("MissionID")), None)
            return counted and self._on_mission_completed(entry, system, timestamp)
        if event in ("MissionFailed", "MissionAbandoned"):
            return self._on_mission_ended(entry, event, timestamp, counted)
        if not counted or not system:
            return False
        if event == "RedeemVoucher":
            return self._on_voucher(entry, system, timestamp)
        if event == "CommitCrime":
            return self._on_crime(entry, system, timestamp)
        if event in ("MarketBuy", "MarketSell"):
            return self._on_market(entry, event, system, timestamp)
        if event in ("SellExplorationData", "MultiSellExplorationData"):
            return self._on_exploration(entry, system, timestamp)
        return False

    def _on_location(self, entry: Dict[str, Any], event: str, fallback_system: Optional[str]) -> bool:
        star = entry.get("StarSystem") or fallback_system
        if star and star != self.current_system:
            self.current_system = star
            self.current_system_factions = None
        if event == "FSDJump":
            self.station_faction = None
        elif "Docked" in entry:
            self.station_faction = (
                (entry.get("StationFaction") or {}).get("Name") if entry.get("Docked") else None
            )
        factions = entry.get("Factions")
        if not star or not isinstance(factions, list):
            return False

        controlling = (entry.get("SystemFaction") or {}).get("Name")
        timestamp = entry.get("timestamp", "")
        pre_tick = not self._in_period(timestamp)
        present: List[FactionSnapshot] = []
        for raw in factions:
            if not isinstance(raw, dict):
                continue
            snap = bgs_tracker.parse_faction_entry(star, raw, raw.get("Name") == controlling, timestamp)
            if snap is None:
                continue
            present.append(snap)
            key = snapshot_key(star, snap.faction)
            track = self.tracks.setdefault(key, FactionTrack(system=star, faction=snap.faction))
            if pre_tick:
                track.before = snap
            else:
                track.now = snap
        self.current_system_factions = present
        return True

    def _on_mission_accepted(self, entry: Dict[str, Any], fallback_system: Optional[str]) -> bool:
        mission_id = entry.get("MissionID")
        faction = entry.get("Faction")
        system = self.current_system or fallback_system
        if mission_id is None or not faction or not system:
            return False
        self.open_missions[str(mission_id)] = (faction, system)
        while len(self.open_missions) > MAX_OPEN_MISSIONS:
            self.open_missions.pop(next(iter(self.open_missions)))
        return True

    def _on_mission_completed(self, entry: Dict[str, Any], system: Optional[str], timestamp: str) -> bool:
        if not system:
            return False
        changed = False
        for faction, plus, minus in bgs_tracker.parse_mission_faction_effects(entry):
            act = self._act(system, faction, timestamp)
            act.missions += 1
            act.inf_plus += plus
            act.inf_minus += minus
            changed = True
        return changed

    def _on_mission_ended(self, entry: Dict[str, Any], event: str, timestamp: str, counted: bool) -> bool:
        issuer = self.open_missions.pop(str(entry.get("MissionID")), None)
        if issuer is None or not counted:
            return issuer is not None
        faction, system = issuer
        act = self._act(system, faction, timestamp)
        if event == "MissionFailed":
            act.missions_failed += 1
        else:
            act.missions_abandoned += 1
        return True

    def _on_voucher(self, entry: Dict[str, Any], system: str, timestamp: str) -> bool:
        changed = False
        for faction, amount in bgs_tracker.parse_bounty_voucher(entry):
            self._act(system, faction, timestamp).bounty_credits += amount
            changed = True
        bond = bgs_tracker.parse_combat_bond(entry)
        if bond is not None:
            self._act(system, bond[0], timestamp).combat_bond_credits += bond[1]
            changed = True
        return changed

    def _on_crime(self, entry: Dict[str, Any], system: str, timestamp: str) -> bool:
        crime = bgs_tracker.parse_crime(entry)
        if crime is None:
            return False
        act = self._act(system, crime[0], timestamp)
        act.crimes += 1
        act.crime_credits += crime[1]
        return True

    def _on_market(self, entry: Dict[str, Any], event: str, system: str, timestamp: str) -> bool:
        if not self.station_faction:
            return False
        if event == "MarketBuy":
            cost = bgs_tracker.market_buy_cost(entry)
            if cost is None:
                return False
            act = self._act(system, self.station_faction, timestamp)
            act.trade_buy_credits += cost
            act.trade_profit_credits -= cost
        else:
            proceeds = bgs_tracker.market_sell_proceeds(entry)
            if proceeds is None:
                return False
            act = self._act(system, self.station_faction, timestamp)
            act.trade_sell_credits += proceeds
            act.trade_profit_credits += proceeds
        return True

    def _on_exploration(self, entry: Dict[str, Any], system: str, timestamp: str) -> bool:
        value = bgs_tracker.exploration_sale_value(entry)
        if value is None or not self.station_faction:
            return False
        self._act(system, self.station_faction, timestamp).exploration_credits += value
        return True


def fingerprint(entry: Dict[str, Any]) -> str:
    """Stable identity of a journal entry, to avoid counting one twice when a
    replay and the live feed overlap."""
    return json.dumps(entry, sort_keys=True, separators=(",", ":"))


def rebuild(
    events: Iterable[Dict[str, Any]], tick_start: Optional[str],
    open_missions: Optional[Dict[str, Tuple[str, str]]] = None,
) -> TickLedger:
    """A fresh ledger for the period starting at `tick_start`, built by
    replaying `events` (journal order). `open_missions` seeds missions
    accepted before the replayed window."""
    ledger = TickLedger(tick_start)
    if open_missions:
        ledger.open_missions.update(open_missions)
    for entry in events:
        ledger.process(entry)
    return ledger


def prune_archive(archive: List[Dict[str, Any]], now: datetime, keep_days: int) -> List[Dict[str, Any]]:
    """Drop archived periods that ended more than `keep_days` ago (newest
    first order is preserved)."""
    cutoff = now - timedelta(days=max(1, keep_days))
    kept = []
    for record in archive:
        ended = parse_timestamp(record.get("tick_end")) if isinstance(record, dict) else None
        if ended is None or ended >= cutoff:
            kept.append(record)
    return kept


def view_from_archive(record: Dict[str, Any]) -> PeriodView:
    activity = [a for a in (_build(FactionActivity, v) for v in (record.get("activity") or {}).values()) if a]
    tracks = [t for t in (FactionTrack.from_dict(v) for v in (record.get("tracks") or {}).values()) if t]
    return PeriodView(
        tick_start=record.get("tick_start"), tick_end=record.get("tick_end"), current=False,
        activity=activity, tracks=tracks,
    )
