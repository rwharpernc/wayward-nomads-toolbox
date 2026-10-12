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


@dataclass
class GoalReward:
    """What a finished Community Goal paid this commander (the `CommunityGoalReward` event)."""
    cg_id: int
    title: str
    system: str
    credits: int
    at: str
    """The event's timestamp (ISO, UTC)."""

    def text(self, title_max: int = 60) -> str:
        """One payout as a line: the goal, the credits and the day. The title comes from the game, so it is clipped."""
        title = self.title if len(self.title) <= title_max else self.title[:title_max - 1] + "…"
        day = self.at[:10]
        return f"{title or 'Community Goal'} - {self.credits:,} cr" + (f" ({day})" if day else "")


MAX_REWARDS = 20
"""Payouts kept per commander (newest first when listed); the display shows only the latest few."""

community_goal_listeners: list[Callable[[dict[int, "CommunityGoal"]], None]] = []
"""Notified with the current CMDR's known goals, keyed by CGID."""

current_cmdr: Optional[str] = None
_goals_by_cmdr: dict[str, dict[int, CommunityGoal]] = {}
_rewards_by_cmdr: dict[str, dict[tuple, GoalReward]] = {}


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


def _build_reward(entry: dict) -> Optional[GoalReward]:
    credits = entry.get("Reward")
    if not isinstance(credits, int) or isinstance(credits, bool) or credits <= 0:
        return None
    return GoalReward(
        cg_id=entry.get("CGID") if isinstance(entry.get("CGID"), int) else 0,
        title=str(entry.get("Name") or "").strip(), system=str(entry.get("System") or ""),
        credits=credits, at=str(entry.get("timestamp") or ""))


def initialize(goals_by_cmdr: dict[str, dict[int, dict]], rewards_by_cmdr: Optional[dict[str, list[dict]]] = None):
    """Seed from the journal scan: CMDR -> (CGID -> latest raw CurrentGoals
    sub-entry seen for that CGID), and CMDR -> the CommunityGoalReward events."""
    global _goals_by_cmdr, _rewards_by_cmdr
    _goals_by_cmdr = {
        cmdr: {cg_id: _build_goal(entry) for cg_id, entry in goals.items()}
        for cmdr, goals in goals_by_cmdr.items()
    }
    _rewards_by_cmdr = {}
    for cmdr, events in (rewards_by_cmdr or {}).items():
        for event in events:
            _keep_reward(cmdr, event)


def set_current_cmdr(cmdr: str):
    """Mirrors active_missions.ActiveMissions.switch_to: only re-emits on an
    actual commander switch, so a fresh CMDR immediately sees whatever CG
    data the journal backfill already found for them."""
    global current_cmdr
    if not cmdr or cmdr == current_cmdr:
        return
    current_cmdr = cmdr
    __emit_changed(cmdr)


def _keep_reward(cmdr: str, entry: dict) -> bool:
    reward = _build_reward(entry)
    if reward is None or not cmdr:
        return False
    kept = _rewards_by_cmdr.setdefault(cmdr, {})
    key = (reward.cg_id, reward.at)
    if key in kept:
        return False          # the same payout seen twice (a journal read again after the live event)
    kept[key] = reward
    for old in sorted(kept.values(), key=lambda r: r.at)[:-MAX_REWARDS]:
        kept.pop((old.cg_id, old.at), None)
    return True


def add_reward(cmdr: str, entry: dict):
    """Live CommunityGoalReward event."""
    if _keep_reward(cmdr, entry):
        __emit_changed(cmdr)


def get_rewards(cmdr: Optional[str]) -> list[GoalReward]:
    """The payouts known for `cmdr`, newest first."""
    if cmdr is None:
        return []
    return sorted(_rewards_by_cmdr.get(cmdr, {}).values(), key=lambda r: r.at, reverse=True)


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
