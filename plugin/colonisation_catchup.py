"""
Catching colonisation sites up from the journals when EDMC starts.

Deliveries made with EDMC closed are in the journal as `ColonisationContribution`, and every visit to a depot as a
`ColonisationConstructionDepot` snapshot, but EDMC does not replay them. This reads the recent journals once at
start-up and folds in what the saved sites have not seen.

A depot snapshot replaces a site's figures wholesale, so it is safe to apply twice. A contribution is an addition, so
counting one twice would be wrong. Every site therefore carries `journal_at`, the time of the newest journal event
folded in (before that existed, the time the site was last updated), and an event is applied only if it is newer. The
same rule guards the live path, so a catch-up and the live events never overlap.

Sites first met this way (docked at while EDMC was closed) are registered too, named from the `Docked` event for the
same market id when the journal has one.
"""
from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Iterable, List, Optional, Tuple

from . import colonisation, journal_files
from .colonisation_data import SiteRepository

DEFAULT_DAYS = 14   # how far back to read when no site says otherwise
MAX_DAYS = 30       # never read further back than this
_WANTED = journal_files.event_pattern(
    "Commander", "LoadGame", "Docked", colonisation.EVENT_DEPOT, colonisation.EVENT_CONTRIBUTION)

Event = Tuple[str, Dict[str, Any]]   # (commander name, journal entry)


def read_since(since_epoch: float, folder: Optional[str] = None) -> List[Event]:
    """The colonisation-relevant events in journals modified since `since_epoch`, oldest first, each with the
    commander its file says it belongs to (`Commander` / `LoadGame`)."""
    events: List[Event] = []
    for path in journal_files.files_modified_since(since_epoch, folder):
        cmdr = ""
        for entry in journal_files.read_events(path, _WANTED):
            kind = entry.get("event")
            if kind == "Commander" and entry.get("Name"):
                cmdr = str(entry["Name"])
            elif kind == "LoadGame" and entry.get("Commander"):
                cmdr = str(entry["Commander"])
            elif cmdr:
                events.append((cmdr, entry))
    return events


def apply_events(repository: SiteRepository, events: Iterable[Event]) -> int:
    """Fold events into the repository. Returns how many updates were applied (a site refreshed by several events
    counts each)."""
    docked: Dict[int, Tuple[str, str]] = {}
    changed = 0
    for cmdr, entry in events:
        kind = entry.get("event")
        market_id = entry.get("MarketID")
        if kind == "Docked":
            if isinstance(market_id, int) and entry.get("StationName"):
                docked[market_id] = (str(entry["StationName"]), str(entry.get("StarSystem") or ""))
            continue
        if not isinstance(market_id, int):
            continue
        when = colonisation.event_time(entry)
        existing = repository.get(cmdr, market_id)
        if kind == colonisation.EVENT_DEPOT:
            if existing is not None and not colonisation.is_newer(existing, entry, inclusive=True):
                continue
            working = colonisation.Site.from_dict(existing.to_dict()) if existing else None
            name, system = docked.get(market_id, ("", ""))
            site = colonisation.apply_depot_event(entry, working, name=name, system=system)
            if site is not None:
                if when is not None:
                    site.updated = when.isoformat(timespec="seconds")
                repository.upsert(cmdr, site)
                changed += 1
        elif kind == colonisation.EVENT_CONTRIBUTION and existing is not None:
            if not colonisation.is_newer(existing, entry, inclusive=False):
                continue
            working = colonisation.Site.from_dict(existing.to_dict())
            if colonisation.apply_contribution(working, entry):
                if when is not None:
                    working.updated = when.isoformat(timespec="seconds")
                repository.upsert(cmdr, working)
                changed += 1
    return changed


def start_epoch(repository: SiteRepository, cmdrs: Iterable[str], now: Optional[datetime] = None) -> float:
    """Where to start reading: the oldest watermark among the known active sites (a site the journal has not touched
    for longer must be read from there), else DEFAULT_DAYS back; never further than MAX_DAYS."""
    now = now or datetime.now(timezone.utc)
    floor = now - timedelta(days=MAX_DAYS)
    since = now - timedelta(days=DEFAULT_DAYS)
    for cmdr in cmdrs:
        for site in repository.for_cmdr(cmdr):
            mark = colonisation.site_watermark(site)
            if site.active and mark is not None and mark < since:
                since = mark
    return max(since, floor).timestamp()


def catch_up(repository: SiteRepository, cmdrs: Iterable[str], folder: Optional[str] = None) -> int:
    """Read the recent journals and bring `repository` up to date. `cmdrs` are the commanders already known (their
    sites set how far back to read). Returns how many updates were applied."""
    since = start_epoch(repository, cmdrs)
    return apply_events(repository, read_since(since, folder))


def known_commanders(repository: SiteRepository) -> List[str]:
    return list(repository._by_cmdr)   # noqa: SLF001 - same package; the repository keeps no public listing
