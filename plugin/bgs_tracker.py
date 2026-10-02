"""BGS (Background Simulation) tracking — pure logic (no Tk, no network),
same split as organic_scan.py. Covers all four phases from
docs/BGS_TECH_SPEC.md:

- Phase 1: faction-state *snapshots* (`FactionSnapshot`) from the
  `Factions[]` array every FSDJump/Location/CarrierJump event carries.
- Phase 2: mission INF (`parse_mission_faction_effects`) and bounty/combat-
  bond voucher redemption (`parse_bounty_voucher`/`parse_combat_bond`),
  accumulated into `FactionActivity`.
- Phase 4: trade and exploration-data-sale credit extraction
  (`market_buy_cost`/`market_sell_proceeds`/`exploration_sale_value`) - bare
  field reads only; station-faction attribution happens in bgs_panel.py
  since it spans two separate events (`Docked` then `MarketBuy`/etc).

Field semantics (Trend → +INF/-INF, `Factions[]` vs. single `Faction` on
`RedeemVoucher`, station-faction attribution for trade/exploration) were
checked against real journal entries - see docs/BGS_TECH_SPEC.md. Phase 3 (tick detection) is the one piece with a real network
call, and lives entirely in bgs_tick_client.py/bgs_panel.py instead of
here - this module stays pure.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class FactionSnapshot:
    """One faction's state in one system, as last reported by a journal
    event's own `Factions[]` array entry - a point-in-time snapshot, not
    accumulated/tallied data. Overwritten wholesale on every fresh sighting
    of that faction in that system (never merged field-by-field), since the
    journal always sends the complete current picture, not a delta."""

    system: str
    faction: str
    faction_state: str = ""
    government: str = ""
    allegiance: str = ""
    influence: Optional[float] = None
    happiness: str = ""
    is_controlling: bool = False
    pending_states: List[str] = field(default_factory=list)
    recovering_states: List[str] = field(default_factory=list)
    active_states: List[str] = field(default_factory=list)
    updated_at: str = ""  # the source journal entry's own ISO `timestamp`


def snapshot_key(system: str, faction: str) -> str:
    """Case-insensitive composite key - EDMC/Frontier aren't perfectly
    consistent about case across journal entries for the same real system/
    faction name, same reasoning as ship_builds_data.py's own cmdr-key
    matching."""
    return f"{system.strip().casefold()}|{faction.strip().casefold()}"


def is_tracked(system: str, faction: str, tracked_systems: List[str], tracked_factions: List[str]) -> bool:
    """A faction is tracked if either its home system or its own name is on
    the commander's configured list (case-insensitive) - covers both a
    commander who tracks "everything happening in my system(s)" and one who
    tracks "this faction wherever it operates". Returns False if nothing is
    configured at all - Phase 1 shows nothing until the commander sets up
    at least one tracked system or faction, deliberately (no "everything,
    everywhere" default - see the scoping decision behind this feature)."""
    if not tracked_systems and not tracked_factions:
        return False
    system_key = system.strip().casefold()
    faction_key = faction.strip().casefold()
    if any(system_key == s.strip().casefold() for s in tracked_systems if s.strip()):
        return True
    return any(faction_key == f.strip().casefold() for f in tracked_factions if f.strip())


def _state_names(states: Any) -> List[str]:
    if not isinstance(states, list):
        return []
    return [s.get("State") for s in states if isinstance(s, dict) and s.get("State")]


def parse_faction_entry(
    system: str, entry: Dict[str, Any], is_controlling: bool, timestamp: str,
) -> Optional[FactionSnapshot]:
    """Builds a FactionSnapshot from one element of a journal event's
    `Factions[]` array. Returns None if `entry` doesn't even name a faction
    (defensive only - every real journal entry does)."""
    name = entry.get("Name")
    if not name:
        return None
    influence = entry.get("Influence")
    return FactionSnapshot(
        system=system,
        faction=name,
        faction_state=entry.get("FactionState", ""),
        government=entry.get("Government", ""),
        allegiance=entry.get("Allegiance", ""),
        influence=float(influence) if isinstance(influence, (int, float)) else None,
        happiness=entry.get("Happiness_Localised") or entry.get("Happiness", ""),
        is_controlling=is_controlling,
        pending_states=_state_names(entry.get("PendingStates")),
        recovering_states=_state_names(entry.get("RecoveringStates")),
        active_states=_state_names(entry.get("ActiveStates")),
        updated_at=timestamp,
    )


# --- Phase 2/4: activity tally ---------------------------------------------


@dataclass
class FactionActivity:
    """Accumulated BGS-needle-moving activity for one faction in one system,
    since the last detected tick (see bgs_panel.py's own tick-roll logic).
    All credit fields are net-of-broker-cut as reported by the journal
    event itself (no separate broker-percentage math here)."""

    system: str
    faction: str
    missions: int = 0
    inf_plus: int = 0
    """Sum of Influence-marker pip counts across every UpGood/DownGood
    mission effect - not a percentage (Frontier never exposes one)."""
    inf_minus: int = 0
    bounty_credits: int = 0
    combat_bond_credits: int = 0
    trade_buy_credits: int = 0
    trade_sell_credits: int = 0
    trade_profit_credits: int = 0  # trade_sell_credits - trade_buy_credits; can be negative
    exploration_credits: int = 0

    def is_empty(self) -> bool:
        return not any((
            self.missions, self.inf_plus, self.inf_minus, self.bounty_credits,
            self.combat_bond_credits, self.trade_buy_credits, self.trade_sell_credits,
            self.exploration_credits,
        ))


def parse_mission_faction_effects(entry: Dict[str, Any]) -> List[Tuple[str, int, int]]:
    """`MissionCompleted`'s own `FactionEffects[]` array -> one
    `(faction, inf_plus_pips, inf_minus_pips)` tuple per faction affected.
    `Trend` -> direction mapping (`UpGood`/`DownGood` => +INF, `UpBad`/
    `DownBad` => -INF) and pip-count-from-string-length are both observed
    from real journal entries - Frontier itself only ever exposes a `+`/`-`
    pip string, never an exact number."""
    results: List[Tuple[str, int, int]] = []
    effects = entry.get("FactionEffects")
    if not isinstance(effects, list):
        return results
    for fx in effects:
        if not isinstance(fx, dict):
            continue
        faction = fx.get("Faction")
        if not faction:
            continue
        plus = 0
        minus = 0
        for inf in fx.get("Influence") or []:
            if not isinstance(inf, dict):
                continue
            trend = inf.get("Trend", "")
            pips = len(inf.get("Influence") or "")
            if trend in ("UpGood", "DownGood"):
                plus += pips
            elif trend in ("UpBad", "DownBad"):
                minus += pips
        results.append((faction, plus, minus))
    return results


def parse_bounty_voucher(entry: Dict[str, Any]) -> List[Tuple[str, int]]:
    """`RedeemVoucher` with `Type == "bounty"` -> one `(faction, amount)`
    tuple per faction in its own `Factions[]` array - a single bounty-
    voucher redemption can cover several factions' bounties earned in the
    same system at once, unlike a combat bond (see `parse_combat_bond`)."""
    if entry.get("Type") != "bounty":
        return []
    results: List[Tuple[str, int]] = []
    for fx in entry.get("Factions") or []:
        if isinstance(fx, dict) and fx.get("Faction") and isinstance(fx.get("Amount"), (int, float)):
            results.append((fx["Faction"], int(fx["Amount"])))
    return results


def parse_combat_bond(entry: Dict[str, Any]) -> Optional[Tuple[str, int]]:
    """`RedeemVoucher` with `Type == "CombatBond"` -> `(faction, amount)`.
    Unlike a bounty voucher, this event carries a single top-level `Faction`/
    `Amount` pair, not a `Factions[]` array (a combat bond is always earned
    fighting for one faction's side in one conflict zone)."""
    if entry.get("Type") != "CombatBond":
        return None
    faction = entry.get("Faction")
    amount = entry.get("Amount")
    if not faction or not isinstance(amount, (int, float)):
        return None
    return (faction, int(amount))


def market_buy_cost(entry: Dict[str, Any]) -> Optional[int]:
    cost = entry.get("TotalCost")
    return int(cost) if isinstance(cost, (int, float)) else None


def market_sell_proceeds(entry: Dict[str, Any]) -> Optional[int]:
    proceeds = entry.get("TotalSale")
    return int(proceeds) if isinstance(proceeds, (int, float)) else None


def exploration_sale_value(entry: Dict[str, Any]) -> Optional[int]:
    """Covers both `MultiSellExplorationData` (current) - which reports
    `TotalEarnings` directly - and the legacy `SellExplorationData` event,
    which instead reports `BaseValue` + `Bonus` separately with no
    `TotalEarnings` field at all; falls back to summing those two when
    `TotalEarnings` isn't present."""
    value = entry.get("TotalEarnings")
    if isinstance(value, (int, float)):
        return int(value)
    base = entry.get("BaseValue")
    bonus = entry.get("Bonus")
    if isinstance(base, (int, float)) or isinstance(bonus, (int, float)):
        return int((base or 0) + (bonus or 0))
    return None
