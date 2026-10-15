"""How far along each mission is, in one place for the Missions window and the Missions overlay card.

Three sources, in this order for each mission:

1. **The game's own cargo count.** The journal's `CargoDepot` event gives collected / delivered / total for haulage and for missions where cargo has been handed in.
2. **Kills.** Massacre and settlement-raid missions: the kill estimate (`kill_missions.estimate_progress`), marked `~` when it is an estimate.
3. **What is in your hold.** A "source and return" mission (Collect) writes nothing to the journal until you hand cargo in, so while you are still buying it there is no
   game count at all. The journal does say what you are carrying, so the progress is the tonnes of that commodity in the hold against the amount the mission asks for
   (`36/60 held`). Several missions for one commodity share the hold, the soonest to expire first, so the same tonne is never counted twice.

`tier` turns a fraction into the colour band both displays use: ready (green), over half (lime), started (blue), not started. Pure logic."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Collection, Dict, Iterable, Mapping, Optional, Tuple

READY, HIGH, LOW, NONE = "ready", "high", "low", "none"
HIGH_AT = 0.5                      # half or more: HIGH; anything started below that: LOW


@dataclass(frozen=True)
class Progress:
    text: str                      # "12/40", "~18/40 kills", "36/60 held" or ""
    fraction: Optional[float]      # 0..1, None when nothing is known
    done: int = 0                  # in the unit of `required`: tonnes or kills
    required: int = 0
    note: str = ""                 # "30/40 collected, 10 delivered"


def live_kills() -> Dict[int, Tuple[int, int, bool]]:
    """(kills done, kills required, is an estimate) for each active massacre or raid, from the Missions mode's kill data."""
    from . import kill_missions
    missions = list((kill_missions.view.missions or {}).values())
    done = kill_missions.estimate_progress(missions) if missions else {}
    return {m.id: (done.get(m.id, 0), m.count, bool(m.is_wing or m.is_ground)) for m in missions}


def commodity_key(raw: Any) -> str:
    """'$AgriculturalMedicines_Name;' -> 'agriculturalmedicines', the form EDMC's cargo map uses."""
    text = str(raw or "").strip().lower().lstrip("$")
    if text.endswith(";"):
        text = text[:-1]
    if text.endswith("_name"):
        text = text[:-5]
    return text


def tier(fraction: Optional[float], ready: bool = False) -> str:
    if ready:
        return READY
    if fraction is None or fraction <= 0:
        return NONE
    return HIGH if fraction >= HIGH_AT else LOW


def compute(missions: Iterable[Any], *, kills: Optional[Mapping[int, Tuple[int, int, bool]]] = None, held: Optional[Mapping[str, int]] = None,
            ready: Collection[int] = ()) -> Dict[int, Progress]:
    """Progress by mission id for `missions` (`all_missions.MissionSummary`s). `kills[id]` is (done, required, estimate); `held` is the hold by commodity key."""
    kills = kills or {}
    pool = {commodity_key(k): int(v) for k, v in (held or {}).items() if isinstance(v, (int, float))}
    result: Dict[int, Progress] = {}
    waiting = []                                         # missions with no game count: they are measured against the hold below
    for summary in missions:
        cargo = summary.cargo
        if cargo is not None and cargo.total:
            first = cargo.delivered if cargo.delivered else cargo.collected
            text = f"{cargo.delivered:,}/{cargo.total:,}" if cargo.delivered or not cargo.collected else f"{cargo.collected:,}/{cargo.total:,} loaded"
            result[summary.id] = Progress(text, min(1.0, first / cargo.total), first, cargo.total,
                                          f"{cargo.collected:,}/{cargo.total:,} collected, {cargo.delivered:,} delivered")
        elif summary.id in kills and kills[summary.id][1]:
            done, required, estimate = kills[summary.id]
            mark = "~" if estimate and summary.id not in ready else ""
            result[summary.id] = Progress(f"{mark}{done}/{required} kills", min(1.0, done / required), done, required)
        elif getattr(summary, "needed_commodity", "") and getattr(summary, "commodity_key", "") and summary.needed_commodity_count > 0:
            waiting.append(summary)
    for summary in sorted(waiting, key=lambda s: (s.expiry == "", s.expiry, s.id)):
        need, key = summary.needed_commodity_count, summary.commodity_key
        have = max(0, min(need, pool.get(key, 0)))
        pool[key] = pool.get(key, 0) - have
        result[summary.id] = Progress(f"{have:,}/{need:,} held", have / need, have, need)
    for mission_id in ready:
        if mission_id in result:
            current = result[mission_id]
            result[mission_id] = Progress(current.text, 1.0, current.required, current.required, current.note)
    return result
