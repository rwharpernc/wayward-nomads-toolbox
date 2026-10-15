"""The Missions window's data: one `Row` per active mission with everything the window shows, the totals line, and the missions grouped by place.

Pure logic. The Missions mode's data (`all_missions.MissionSummary`, the kill progress estimate, the redirected missions and the pinned ids) is passed in, so
the window and the tests use the same code. Nothing is stored or sent."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Collection, Dict, Iterable, List, Mapping, Optional, Tuple

from . import mission_progress, mission_types
from .missions_overlay import parse_expiry, time_left

SOON_MINUTES = 60                 # "expiring soon" in the totals


@dataclass(frozen=True)
class Row:
    id: int
    title: str
    kind: str                     # "Massacre (space)", "Trade & Mining" ...
    faction: str
    system: str                   # where to go now: the hand-in place once the objective is done, else the destination
    station: str
    progress: str                 # "80/200", "~18/40 kills", "36/60 held" or ""
    fraction: Optional[float]     # 0..1 when there is progress to show
    reward: int
    expiry: Optional[datetime]
    ready: bool
    wing: bool
    illegal: bool
    pinned: bool
    accepted: str                 # ISO timestamp
    expiry_text: str              # ISO timestamp as the game wrote it
    commodity: str                # what is mined or collected, if any
    needed: int                   # tonnes still to find, 0 if none
    cargo_note: str               # "120/200 collected, 80 delivered" or ""

    @property
    def tier(self) -> str:
        """The colour band of its progress: ready, high (half or more), low (started) or none."""
        return mission_progress.tier(self.fraction, self.ready)

    def where(self) -> str:
        if self.system and self.station:
            return f"{self.system} / {self.station}"
        return self.station or self.system or "-"


def rows_from(missions: Mapping[int, Any], *, redirected: Collection[int] = (), redirects: Optional[Mapping[int, Mapping[str, str]]] = None,
              kills: Optional[Mapping[int, Tuple[int, int, bool]]] = None, held: Optional[Mapping[str, int]] = None,
              pinned: Collection[int] = ()) -> List[Row]:
    """A row for each of `missions` (`MissionSummary`s). `redirected` are the missions whose objective is done (the game redirected them to a hand-in
    place, named in `redirects[id]` when it said). `kills[id]` is (kills done, kills required, is an estimate) for a massacre or raid."""
    redirects = redirects or {}
    progress_by_id = mission_progress.compute(list(missions.values()), kills=kills, held=held, ready=redirected)
    rows: List[Row] = []
    for summary in missions.values():
        ready = summary.id in redirected
        system, station = summary.destination_system, summary.destination_station
        if ready:
            place = redirects.get(summary.id) or {}
            if place.get("system") or place.get("station"):
                system, station = place.get("system") or system, place.get("station") or station
        found = progress_by_id.get(summary.id)
        progress, fraction, note = (found.text, found.fraction, found.note) if found else ("", None, "")
        if ready:
            fraction = 1.0
        rows.append(Row(
            summary.id, summary.name, mission_types.CATEGORY_LABELS.get(summary.category, summary.category), summary.source_faction, system, station,
            progress, fraction, summary.reward, parse_expiry(summary.expiry), ready, summary.is_wing, summary.is_illegal, summary.id in pinned,
            summary.accepted_at, summary.expiry, summary.commodity or summary.needed_commodity, summary.needed_commodity_count, note))
    return sorted(rows, key=order)


def order(row: Row) -> Tuple[Any, ...]:
    """Ready first, then soonest to expire (no expiry last), then by title."""
    return (not row.ready, row.expiry is None, row.expiry.timestamp() if row.expiry else 0.0, row.title.casefold())


@dataclass(frozen=True)
class Totals:
    count: int
    ready: int
    soon: int                     # not ready and under SOON_MINUTES left
    reward: int
    ready_reward: int
    pinned: int

    def text(self) -> str:
        parts = [f"{self.count} mission{'s' if self.count != 1 else ''}"]
        if self.ready:
            parts.append(f"{self.ready} ready")
        if self.soon:
            parts.append(f"{self.soon} under {SOON_MINUTES // 60}h")
        if self.pinned:
            parts.append(f"{self.pinned} pinned")
        text = " · ".join(parts)
        if self.reward:
            text += f" · {money(self.reward)} cr held" + (f" ({money(self.ready_reward)} ready)" if self.ready_reward else "")
        return text


def totals(rows: Iterable[Row], now: datetime) -> Totals:
    rows = list(rows)
    soon = sum(1 for r in rows if not r.ready and r.expiry is not None and (r.expiry - now).total_seconds() < SOON_MINUTES * 60)
    return Totals(len(rows), sum(r.ready for r in rows), soon, sum(r.reward for r in rows), sum(r.reward for r in rows if r.ready),
                  sum(r.pinned for r in rows))


def money(credits: int) -> str:
    """12,400,000 -> '12.4M'; 850,000 -> '850K'."""
    if credits >= 1_000_000:
        return f"{credits / 1_000_000:.1f}".rstrip("0").rstrip(".") + "M"
    if credits >= 1_000:
        return f"{credits / 1_000:.0f}K"
    return str(credits)


@dataclass(frozen=True)
class Place:
    system: str
    rows: List[Row]
    here: bool = False
    next_jump: bool = False


def by_place(rows: Iterable[Row], here: str = "", next_system: str = "") -> List[Place]:
    """The rows grouped by the system to go to: where you are first, then the next jump, then the places with something ready, then the soonest to expire."""
    groups: Dict[str, List[Row]] = {}
    for row in rows:
        groups.setdefault((row.system or "?").casefold(), []).append(row)
    places = []
    for members in groups.values():
        members.sort(key=order)
        name = members[0].system or "No destination"
        places.append(Place(name, members, bool(here) and name.casefold() == here.casefold(), bool(next_system) and name.casefold() == next_system.casefold()))
    return sorted(places, key=lambda p: (not p.here, not p.next_jump, order(p.rows[0])))


def detail(row: Row, now: datetime) -> List[Tuple[str, str]]:
    """The label and value pairs shown for the selected mission."""
    pairs = [("Mission", row.title), ("Kind", row.kind + ("  ⚠ Illegal" if row.illegal else "")), ("Faction", row.faction),
             ("Status", "✓ Ready to hand in" if row.ready else "In progress"), ("Go to", row.where())]
    if row.progress:
        pairs.append(("Progress", row.progress))
    if row.cargo_note:
        pairs.append(("Cargo", row.cargo_note))
    if row.commodity:
        pairs.append(("Commodity", row.commodity + (f" ({row.needed:,} t still needed)" if row.needed else "")))
    pairs.append(("Reward", f"{row.reward:,} cr" if row.reward else "-"))
    pairs.append(("Wing mission", "Yes" if row.wing else "No"))
    pairs.append(("Accepted", _stamp(row.accepted)))
    left = time_left(row.expiry, now)
    pairs.append(("Expires", f"{_stamp(row.expiry_text)}" + (f"  ({left} left)" if left else "")))
    pairs.append(("Pinned", "Yes - on the overlay" if row.pinned else "No"))
    return pairs


def _stamp(iso: str) -> str:
    parsed = parse_expiry(iso)
    return parsed.strftime("%Y-%m-%d %H:%M UTC") if parsed else "-"
