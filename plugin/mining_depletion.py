"""
When a hotspot marked Depleted is assumed to carry material again, and what the Mining Book says while it waits.

A deposit that has been mined out refills over time in the game, but no journal event or Status.json field says when, and
the HUD's Amount readout is the only proof. So WNTB works from an assumption, not a measurement: a Depleted mark is taken
off REGEN_DAYS after it was set, which leaves the hotspot with no Amount until the commander reads it again. Pressing
Mark depleted on such a hotspot when no ton has been refined there since means the deposit was looked at and is still
empty: the first depletion date is kept, the look is recorded, and the mark comes off again RECHECK_DAYS after that look.
Refined tons since the regrowth make it a fresh depletion instead.

Pure logic with no tkinter and no file access; mining_hotspots.py calls it whenever a hotspot is added or changed and when a
commander's list is loaded. See tests/test_mining_depletion.py.
"""
from __future__ import annotations

import dataclasses
import math
from datetime import datetime, timedelta, timezone
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from .mining_hotspots import Hotspot

DEPLETED = "Depleted"

REGEN_DAYS = 14
"""Days after a Depleted mark before it is assumed to have refilled. Assumed, not measured."""

RECHECK_DAYS = 7
"""Days after a recheck (Mark depleted pressed with no ton refined since the regrowth) before the mark comes off again."""


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def stamp(moment: datetime) -> str:
    return moment.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse(text: Optional[str]) -> Optional[datetime]:
    """A stored stamp back into a datetime, or None for a missing or damaged one (a damaged stamp must never stop a list loading)."""
    if not text:
        return None
    try:
        return datetime.strptime(text, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return None


def _tons(spot: "Hotspot") -> int:
    return spot.mined_tons or 0


def apply(old: Optional["Hotspot"], new: "Hotspot", moment: datetime) -> "Hotspot":
    """`new` (an edit, a re-save or a fresh hotspot) with its depletion bookkeeping brought in line with `old`, what it replaces.

    The dialogs build a new Hotspot without knowing about the bookkeeping, so it is always taken from `old` and then changed
    only by what the edit did to the Amount."""
    base = old if old is not None else new
    depleted_at, regrown_at = base.depleted_at, base.regrown_at
    tons_at_regrow, rechecks = base.tons_at_regrow, list(base.rechecks)
    was = old is not None and old.amount == DEPLETED
    now = new.amount == DEPLETED
    if now and not was:
        looked_again = (old is not None and old.regrown_at is not None and old.depleted_at is not None
                        and _tons(old) == (old.tons_at_regrow or 0))
        if looked_again:
            rechecks.append(stamp(moment))
            regrown_at = tons_at_regrow = None
        else:
            depleted_at, regrown_at, tons_at_regrow, rechecks = stamp(moment), None, None, []
    elif now and depleted_at is None:
        depleted_at = stamp(moment)   # marked before dates were kept: counts from now
    elif not now and (was or new.amount):
        depleted_at = regrown_at = tons_at_regrow = None   # set active by hand, or a fresh Amount reading
        rechecks = []
    return dataclasses.replace(new, depleted_at=depleted_at, regrown_at=regrown_at,
                               tons_at_regrow=tons_at_regrow, rechecks=rechecks)


def due_at(spot: "Hotspot") -> Optional[datetime]:
    """When a Depleted mark comes off: RECHECK_DAYS after the last look, else REGEN_DAYS after it was set."""
    if spot.amount != DEPLETED:
        return None
    if spot.rechecks:
        last = parse(spot.rechecks[-1])
        if last is not None:
            return last + timedelta(days=RECHECK_DAYS)
    started = parse(spot.depleted_at)
    return started + timedelta(days=REGEN_DAYS) if started is not None else None


def settle(spot: "Hotspot", moment: datetime) -> "Hotspot":
    """`spot` unchanged, or with a legacy Depleted mark dated now, or with a due mark taken off (the same object when nothing changed)."""
    if spot.amount != DEPLETED:
        return spot
    if parse(spot.depleted_at) is None:
        return dataclasses.replace(spot, depleted_at=stamp(moment))
    due = due_at(spot)
    if due is not None and moment >= due:
        return dataclasses.replace(spot, amount=None, regrown_at=stamp(moment), tons_at_regrow=_tons(spot))
    return spot


def _days(delta: timedelta) -> int:
    return max(0, math.ceil(delta.total_seconds() / 86400))


def status_text(spot: "Hotspot", moment: datetime) -> str:
    """One line on where a hotspot stands in the depletion cycle, or "" when it is not in it."""
    if spot.amount == DEPLETED:
        due = due_at(spot)
        started = parse(spot.depleted_at)
        if due is None or started is None:
            return ""
        left = _days(due - moment)
        if spot.rechecks:
            looked = parse(spot.rechecks[-1]) or moment
            return f"Still depleted at {(looked - started).days} d; look again in {left} d"
        return f"Assumed to refill in {left} d (the game gives no date)"
    if spot.regrown_at and not spot.amount:
        return "Assumed refilled: read its Amount again, or Mark depleted if it is still empty"
    return ""
