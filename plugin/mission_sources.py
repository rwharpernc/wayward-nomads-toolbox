"""Where to get what your Collect and Mining missions still need: the list of needs, and the four source picks (source_picks.py) for each.

Pure logic apart from the Spansh search, which is passed in. The window that shows it is `mission_sources_window.py`.

A need is one commodity summed over every active mission that still has to source it (`MissionSummary.needed_commodity` and `needed_commodity_count`: units
still needed, less what a cargo depot already holds). Its **turn-in system** is where most of those missions are handed in. Looking up is one Spansh round of
about four searches per commodity, so it only happens when the commander presses the button, one commodity after another with a pause between."""
from __future__ import annotations

import time
from collections import Counter
from dataclasses import dataclass
from typing import Any, Callable, Dict, Iterable, List, Optional

from . import source_picks
from .trade_prices import BUY

TURN_IN, HERE = "turn-in", "here"      # which system the picks are measured from
MAX_NEEDS = 12                         # a full board of 20 missions rarely has more kinds of cargo; a hard cap on the searches one press can start


@dataclass(frozen=True)
class Need:
    commodity: str
    tonnes: int                 # still to find, summed over the missions
    missions: int
    turn_in: str                # the system most of those missions are handed in at ("" if none says)


@dataclass(frozen=True)
class Options:
    radius_ly: float
    ship_pad: Optional[str]
    include_carriers: bool
    include_ground: bool


def needs_from(missions: Iterable[Any]) -> List[Need]:
    """The commodities still to source, biggest need first, at most `MAX_NEEDS`. Works on `all_missions.MissionSummary` objects."""
    totals: Dict[str, List[int]] = {}
    places: Dict[str, Counter] = {}
    for mission in missions:
        name = getattr(mission, "needed_commodity", "")
        count = int(getattr(mission, "needed_commodity_count", 0) or 0)
        if not name or count <= 0:
            continue
        entry = totals.setdefault(name, [0, 0])
        entry[0] += count
        entry[1] += 1
        place = getattr(mission, "destination_system", "") or ""
        if place:
            places.setdefault(name, Counter())[place] += 1
    ranked = sorted(totals.items(), key=lambda item: (-item[1][0], item[0].casefold()))
    return [Need(name, tonnes, count, places[name].most_common(1)[0][0] if name in places else "") for name, (tonnes, count) in ranked[:MAX_NEEDS]]


def reference_for(need: Need, mode: str, here: str) -> str:
    """The system to measure from: where you are, or the need's turn-in system (falling back to where you are if no mission names one)."""
    if mode == TURN_IN and need.turn_in:
        return need.turn_in
    return here


def lookup(needs: List[Need], mode: str, here: str, options: Options, *, search: Optional[Callable[..., Any]] = None,
           pause: Callable[[float], None] = time.sleep, cancelled: Callable[[], bool] = lambda: False,
           on_done: Callable[[Need, source_picks.Picks], None] = lambda need, picks: None) -> Dict[str, source_picks.Picks]:
    """The picks for each need (by commodity name), one after another with a pause between. `on_done` is told as each finishes, so a window can show the
    first while the rest are still being found. A failed search is raised; the commodities done before it have already been passed to `on_done`."""
    results: Dict[str, source_picks.Picks] = {}
    extra = {} if search is None else {"search": search}
    started = False
    for need in needs:
        if cancelled():
            break
        reference = reference_for(need, mode, here)
        if not reference:
            continue
        if started:
            pause(source_picks.PAUSE_S)
        started = True
        picks = source_picks.find(reference, need.commodity, BUY, need.tonnes, radius_ly=options.radius_ly, ship_pad=options.ship_pad,
                                  include_carriers=options.include_carriers, include_ground=options.include_ground,
                                  pause=pause, cancelled=cancelled, **extra)
        results[need.commodity] = picks
        on_done(need, picks)
    return results
