"""
Tracks Community Goal progress and the current CMDR's own contribution,
reported live via the CommunityGoal event's CurrentGoals array. Not a
mission - it never goes through MissionAccepted/active_missions at all.

CurrentGoals isn't scoped to "the CG at your current station": a single
event can list several CGs across different systems at once (confirmed
from a live journal - CGID 852 and 853, in different systems, arrived in
the same event), and an already-expired CG keeps reappearing for a while
after its actual deadline passes (its evaluation/payout period,
presumably - confirmed goals with `Expiry` well in the past still showing
up in `CurrentGoals`). There's also no "this CG is gone" signal - a CGID
simply stops being echoed once it's no longer relevant. So state here is
purely additive (every CGID ever seen is kept, keyed by CGID, most recent
snapshot wins) - missions_ui.py is what filters down to "not yet expired"
for what it actually displays.
"""
from dataclasses import dataclass
from typing import Callable, Optional


@dataclass
class CommunityGoal:
    cg_id: int
    title: str
    system: str
    market: str
    expiry: str
    is_complete: bool
    player_contribution: int
    num_contributors: int
    tier_reached: str
    """The community's overall tier reached so far - not personal; a CMDR
    with zero contribution can still see a high TierReached here."""
    top_tier: str
    bonus: int
    player_in_top_rank: bool


community_goal_listeners: list[Callable[[dict[int, "CommunityGoal"]], None]] = []
"""Notified with the current CMDR's known goals, keyed by CGID."""

current_cmdr: Optional[str] = None
_goals_by_cmdr: dict[str, dict[int, CommunityGoal]] = {}


def _build_goal(entry: dict) -> CommunityGoal:
    top_tier = entry.get("TopTier") or {}
    return CommunityGoal(
        cg_id=entry["CGID"],
        title=entry.get("Title", "").strip(),
        system=entry.get("SystemName", ""),
        market=entry.get("MarketName", ""),
        expiry=entry.get("Expiry", ""),
        is_complete=entry.get("IsComplete", False),
        player_contribution=entry.get("PlayerContribution", 0),
        num_contributors=entry.get("NumContributors", 0),
        tier_reached=entry.get("TierReached", ""),
        top_tier=top_tier.get("Name", ""),
        bonus=entry.get("Bonus", 0),
        player_in_top_rank=entry.get("PlayerInTopRank", False),
    )


def initialize(goals_by_cmdr: dict[str, dict[int, dict]]):
    """Seed from the journal scan: CMDR -> (CGID -> latest raw CurrentGoals
    sub-entry seen for that CGID)."""
    global _goals_by_cmdr
    _goals_by_cmdr = {
        cmdr: {cg_id: _build_goal(entry) for cg_id, entry in goals.items()}
        for cmdr, goals in goals_by_cmdr.items()
    }


def set_current_cmdr(cmdr: str):
    """Mirrors active_missions.ActiveMissions.switch_to: only re-emits on an
    actual commander switch, so a fresh CMDR immediately sees whatever CG
    data the journal backfill already found for them."""
    global current_cmdr
    if not cmdr or cmdr == current_cmdr:
        return
    current_cmdr = cmdr
    __emit_changed(cmdr)


def get_goals(cmdr: Optional[str]) -> dict[int, CommunityGoal]:
    if cmdr is None:
        return {}
    return _goals_by_cmdr.get(cmdr, {})


def update_goals(cmdr: str, entry: dict):
    """Live CommunityGoal event: entry["CurrentGoals"] is a list of goal
    snapshots, possibly spanning several systems at once."""
    if not cmdr:
        return
    goals = _goals_by_cmdr.setdefault(cmdr, {})
    for goal_entry in entry.get("CurrentGoals", []):
        cg_id = goal_entry.get("CGID")
        if cg_id is None:
            continue
        goals[cg_id] = _build_goal(goal_entry)
    __emit_changed(cmdr)


def __emit_changed(cmdr: str):
    if cmdr != current_cmdr:
        return
    for listener in community_goal_listeners:
        listener(_goals_by_cmdr.get(cmdr, {}))
