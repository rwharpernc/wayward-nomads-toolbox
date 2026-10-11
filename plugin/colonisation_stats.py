"""
The figures and sentences the Colonization mode shows: the current project and the history. Pure logic, no Tk (so it is
unit-testable; see tests/test_colonisation_stats.py).

Everything adapts to whether the commander has a fleet carrier. Without one there is nothing to stage: the ship's hold is
the only store, a "trip" is one load bought and delivered, and the words carrier and haul never appear. With one the
work has two legs (buy and move it onto the carrier, then haul it to the site) and the figures say so.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, List, Mapping, Optional, Sequence, Tuple

from . import colonisation_view as view
from .colonisation import Site, _parse_time

TOP_GAPS = 4          # biggest outstanding commodities named
TOP_COMMODITIES = 3   # most-delivered commodities named


def _tons(value: int) -> str:
    return f"{value:,} t"


def _plural(count: int, one: str, many: Optional[str] = None) -> str:
    return one if count == 1 else (many or one + "s")


# --- the current project ------------------------------------------------------------------------------------------

@dataclass(frozen=True)
class Project:
    name: str
    system: str
    progress: float          # 0.0 - 1.0
    required: int            # tons the whole build needs
    delivered: int           # tons already handed over (by anyone)
    remaining: int
    lines: int               # commodities still needed
    covered: int             # of those, how many the ship (and carrier) already cover
    in_hold: int
    on_carrier: int
    to_get: int
    capacity: int
    buy_trips: int
    haul_trips: int
    has_carrier: bool
    gaps: Tuple[Tuple[str, int], ...]   # (label, tons still to get), biggest first
    more_active: int                    # other active sites besides this one
    complete: bool = False


def project_for(site: Site, cargo: Mapping[str, int], carrier: Optional[Mapping[str, int]], has_carrier: bool,
                capacity: int, more_active: int = 0) -> Project:
    """The figures for `site`. `carrier` is ignored (treated as empty) for a commander without a fleet carrier."""
    carrier = carrier if has_carrier else {}
    totals = view.totals(site, cargo, capacity, carrier)
    rows = view.commodity_rows(site, cargo, carrier)
    gaps = tuple((r.label, r.to_get) for r in sorted(rows, key=lambda r: (-r.to_get, r.label.casefold())) if r.to_get > 0)
    return Project(
        name=site.display_name(), system=site.system, progress=1.0 if site.complete else site.progress,
        required=sum(r.required for r in site.resources), delivered=sum(r.provided for r in site.resources),
        remaining=totals.remaining, lines=totals.lines, covered=totals.covered, in_hold=totals.in_hold,
        on_carrier=totals.on_carrier, to_get=totals.to_get, capacity=max(0, capacity), buy_trips=totals.buy_trips,
        haul_trips=totals.haul_trips, has_carrier=has_carrier, gaps=gaps[:TOP_GAPS], more_active=more_active,
        complete=site.complete)


def coverage_text(project: Project) -> str:
    """Which commodities are already covered: by the ship alone, or by the ship and the carrier together."""
    if project.lines == 0:
        return "Nothing left to deliver"
    who = "Ship and carrier cover" if project.has_carrier else "Your ship covers"
    return f"{who} {project.covered} of {project.lines} {_plural(project.lines, 'commodity', 'commodities')}"


def trips_text(project: Project) -> str:
    """The trips still to make, in the commander's own terms."""
    if project.remaining <= 0:
        return "None"
    if project.capacity <= 0:
        return "Unknown (ship size not seen yet)"
    if not project.has_carrier:
        n = project.haul_trips
        return f"{n:,} {_plural(n, 'load')} of {project.capacity:,} t"
    return (f"{project.buy_trips:,} to buy · {project.haul_trips:,} to haul "
            f"({project.capacity:,} t ship)")


def next_step(project: Project) -> str:
    """One sentence on what to do next."""
    if project.complete:
        return "This build is complete."
    if project.remaining <= 0:
        return "Everything is delivered. Dock at the site to finish the build."
    if project.to_get <= 0:
        where = "your ship and carrier" if project.has_carrier else "your ship"
        return f"{where.capitalize()} hold everything still needed. Deliver it to the site."
    return f"Get {_tons(project.to_get)} more" + (" (bought or moved onto your carrier)." if project.has_carrier else ".")


# --- history ------------------------------------------------------------------------------------------------------

@dataclass(frozen=True)
class History:
    sites: int
    completed: int
    in_progress: int
    failed: int
    systems: int
    deliveries: int
    tonnes: int              # delivered by this commander (since `since`)
    last_7_days: int
    last_30_days: int
    busiest_day: Optional[Tuple[str, int]]
    top_commodities: Tuple[Tuple[str, int], ...]
    since: str               # date of the first delivery counted ("" when none)
    average_days: Optional[float]   # days from first seen to complete, over the sites for which both are known
    tracked_required: int    # tons the tracked sites need in all
    tracked_delivered: int   # tons delivered to them by anyone


def history_for(sites: Sequence[Site], record: Mapping[str, Any], today: Optional[date] = None) -> History:
    today = today or datetime.now(timezone.utc).date()
    by_day = record.get("by_day") or {}

    def window(days: int) -> int:
        start = (today - timedelta(days=days - 1)).isoformat()
        return sum(int(t) for d, t in by_day.items() if d >= start)

    busiest = max(by_day.items(), key=lambda kv: (kv[1], kv[0]), default=None)
    commodities = sorted(((v.get("label") or k, int(v.get("tonnes") or 0)) for k, v in (record.get("by_commodity") or {}).items()),
                         key=lambda kv: (-kv[1], kv[0].casefold()))
    spans: List[float] = []
    for site in sites:
        start, end = _parse_time(site.first_seen), _parse_time(site.completed_at)
        if site.complete and start and end and end >= start:
            spans.append((end - start).total_seconds() / 86400)
    first = str(record.get("first") or "")
    return History(
        sites=len(sites), completed=sum(1 for s in sites if s.complete), failed=sum(1 for s in sites if s.failed),
        in_progress=sum(1 for s in sites if s.active), systems=len({s.system for s in sites if s.system}),
        deliveries=int(record.get("deliveries") or 0), tonnes=int(record.get("tonnes") or 0),
        last_7_days=window(7), last_30_days=window(30),
        busiest_day=(busiest[0], int(busiest[1])) if busiest and busiest[1] else None,
        top_commodities=tuple((label, tonnes) for label, tonnes in commodities if tonnes > 0)[:TOP_COMMODITIES],
        since=first[:10], average_days=sum(spans) / len(spans) if spans else None,
        tracked_required=sum(r.required for s in sites for r in s.resources),
        tracked_delivered=sum(r.provided for s in sites for r in s.resources))


def sites_text(history: History) -> str:
    if not history.sites:
        return "None tracked yet"
    parts = [f"{history.completed} done", f"{history.in_progress} in progress"]
    if history.failed:
        parts.append(f"{history.failed} failed")
    return " · ".join(parts)


def average_text(days: Optional[float]) -> str:
    if days is None:
        return "–"
    if days < 1:
        return "under a day"
    value = Decimal(str(round(days, 1))).normalize()
    return f"{value:f} days"
