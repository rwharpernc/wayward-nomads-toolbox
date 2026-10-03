"""Text formatting shared by the BGS main panel and the BGS Report window -
pure functions (no Tk), so the wording lives in one place and is testable.
Every faction/system name that came from the journal is clipped here, so a
long name can't widen EDMC's main window (see docs/TECHNICAL.md section 5)."""

from __future__ import annotations

from typing import List, Optional

from .bgs_ledger import FactionTrack, PeriodView, parse_timestamp
from .bgs_tracker import FactionActivity, FactionSnapshot

NAME_LIMIT = 32


def clip(text: object, limit: int = NAME_LIMIT) -> str:
    text = str(text)
    return text if len(text) <= limit else text[:limit - 1] + "…"


def when_text(iso: Optional[str]) -> str:
    parsed = parse_timestamp(iso)
    return parsed.strftime("%Y-%m-%d %H:%M UTC") if parsed else "unknown"


def influence_text(snap: Optional[FactionSnapshot]) -> str:
    if snap is None or snap.influence is None:
        return ""
    return f"{snap.influence * 100:.1f}%"


def influence_change_text(track: FactionTrack) -> str:
    """`45.2% (+1.3)`: where the faction stands and how far it moved since
    before the tick. The change is left off when either end is unknown."""
    base = influence_text(track.latest())
    delta = track.influence_delta()
    if not base:
        return ""
    return f"{base} ({delta:+.1f})" if delta is not None else base


def state_change_text(track: FactionTrack) -> str:
    """`Boom` or `None → Boom` when the state changed since before the tick."""
    now = track.latest()
    if now is None:
        return ""
    current = now.faction_state or "None"
    if track.before is not None and track.now is not None:
        previous = track.before.faction_state or "None"
        if previous != current:
            return f"{previous} → {current}"
    return current


def activity_bits(act: FactionActivity) -> List[str]:
    """Everything that moved for this faction, increases and decreases both."""
    bits: List[str] = []
    if act.missions:
        bits.append(f"{act.missions} mission(s) done, INF +{act.inf_plus}/-{act.inf_minus}")
    if act.missions_failed:
        bits.append(f"{act.missions_failed} mission(s) failed (INF down)")
    if act.missions_abandoned:
        bits.append(f"{act.missions_abandoned} mission(s) abandoned (INF down)")
    if act.bounty_credits:
        bits.append(f"{act.bounty_credits:,} cr bounties")
    if act.combat_bond_credits:
        bits.append(f"{act.combat_bond_credits:,} cr combat bonds")
    if act.trade_profit_credits:
        bits.append(f"{act.trade_profit_credits:+,} cr trade")
    if act.exploration_credits:
        bits.append(f"{act.exploration_credits:,} cr exploration data")
    if act.crimes:
        fines = f", {act.crime_credits:,} cr in fines" if act.crime_credits else ""
        bits.append(f"{act.crimes} crime(s) against them (INF down){fines}")
    return bits


def period_label(view: PeriodView) -> str:
    if view.current:
        return f"Current tick — since {when_text(view.tick_start)}" if view.tick_start else "Current tick"
    return f"{when_text(view.tick_start)} → {when_text(view.tick_end)}"


def system_lines(view: PeriodView, system: str, pinned: bool = False) -> List[str]:
    """Plain-text block for one system in one period."""
    lines = [f"{'★ ' if pinned else ''}{clip(system, 60)}:"]
    tracks = sorted(view.tracks_for(system), key=lambda t: (
        not (t.latest() and t.latest().is_controlling), t.faction.casefold()))
    activity = {a.faction.casefold(): a for a in view.activity_for(system)}
    if not tracks and not activity:
        lines.append("  (nothing recorded)")
    seen = set()
    for track in tracks:
        seen.add(track.faction.casefold())
        marker = "*" if track.latest() and track.latest().is_controlling else "-"
        parts = [state_change_text(track), influence_change_text(track)]
        lines.append(f"  {marker} {clip(track.faction, 50)} — {', '.join(p for p in parts if p)}")
        now = track.latest()
        if now:
            for label, states in (("Pending", now.pending_states), ("Recovering", now.recovering_states),
                                  ("Active", now.active_states)):
                if states:
                    lines.append(f"      {label}: {', '.join(states)}")
        act = activity.get(track.faction.casefold())
        if act:
            lines.append(f"      You: {'; '.join(activity_bits(act))}")
    for key, act in sorted(activity.items()):
        if key not in seen:
            lines.append(f"  - {clip(act.faction, 50)} — You: {'; '.join(activity_bits(act))}")
    return lines


def is_pinned(system: str, pinned: List[str]) -> bool:
    return any(system.casefold() == p.casefold() for p in pinned)


def summary_text(views: List[PeriodView], current_system: Optional[str], pinned: Optional[List[str]] = None) -> str:
    """Plain-text report (all periods, every system) for Copy Summary -
    Discord/forum-postable without any Discord-specific formatting."""
    pinned = pinned or []
    out = ["WNTB BGS Report"]
    for view in views:
        out.append(f"\n== {period_label(view)} ==")
        systems = view.systems(current_system, pinned)  # every system: no tab limit, nothing hidden
        if not systems:
            out.append("  (no activity)")
        for system in systems:
            out.append("")
            out.extend(system_lines(view, system, is_pinned(system, pinned)))
    return "\n".join(out)
