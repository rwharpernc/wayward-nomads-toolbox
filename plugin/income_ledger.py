"""
The Credits Ledger's data: what the commander earned, by activity and by day (per commander, pure logic plus a small JSON file).

Each activity is kept apart so the ledger never blurs them: Trade is only market trading, Exploration is only exploration data
sold, Exobiology is only organic data sold, and so on. Nothing here is shown on a mode's panel; the Credits Ledger window
(ledger_window.py) is its only reader.

What is counted, from the journal:

    trade        `MarketSell`: the sale minus what the sold tonnes cost (the profit, which can be negative)
    exploration  `SellExplorationData` / `MultiSellExplorationData`: the payout (base value plus bonus)
    exobiology   `SellOrganicData`: the value of each species sold, with its first-discovery bonus
    missions     `MissionCompleted`: the credit reward
    vouchers     `RedeemVoucher`: bounty, combat bond and similar vouchers cashed in

Limits, stated plainly: the journal does not say which commodity sold was mined, so Mining has no per-day income here (the game's
own lifetime Mining profits are on the ledger's Lifetime tab); a mission's commodity or other rewards are not credits and are left
out; nothing is counted for credits spent.

An amount is an addition, so counting an event twice would be wrong. Each commander's record keeps `at`, the time of the newest
event folded in, and `at_seen`, the events counted at exactly that second (several sales share one), so a journal read twice, or
caught up after the live event, adds nothing the second time. `rebuild` fills in the past once per commander from every journal.
"""
from __future__ import annotations

import logging
import os
from datetime import date, datetime, timedelta, timezone
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple

from . import commander_data

try:
    from config import appname
except ImportError:  # unit tests outside EDMC
    appname = "EDMarketConnector"

plugin_name = os.path.basename(os.path.dirname(__file__))
logger = logging.getLogger(f"{appname}.{plugin_name}")

STATE_FILENAME = "income_ledger.json"
BACKFILL_VERSION = 1

TRADE, EXPLORATION, EXOBIOLOGY, MISSIONS, VOUCHERS = "trade", "exploration", "exobiology", "missions", "vouchers"
ACTIVITIES: Tuple[str, ...] = (TRADE, EXPLORATION, EXOBIOLOGY, MISSIONS, VOUCHERS)
LABELS = {TRADE: "Trade", EXPLORATION: "Exploration data", EXOBIOLOGY: "Exobiology data", MISSIONS: "Mission rewards",
          VOUCHERS: "Bounties and bonds"}
EVENTS = frozenset({"MarketSell", "SellExplorationData", "MultiSellExplorationData", "SellOrganicData", "MissionCompleted",
                    "RedeemVoucher"})

Record = Dict[str, Any]


def _empty() -> Record:
    return {"at": "", "at_seen": [], "backfilled": 0, "by_day": {}}


def _is_legacy(_raw: Any) -> bool:
    return False   # the file is new; nothing older to claim


def _int(value: Any) -> int:
    return int(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else 0


def _day(stamp: str) -> str:
    return stamp[:10]    # "2026-10-15T09:30:00Z" -> "2026-10-15"


def amount_of(entry: Dict[str, Any]) -> Optional[Tuple[str, int]]:
    """`(activity, credits)` for a journal event worth counting, or None for any other event or one with no credits in it."""
    event = entry.get("event")
    if event == "MarketSell":
        count = _int(entry.get("Count"))
        if count <= 0:
            return None
        return TRADE, _int(entry.get("TotalSale")) - _int(entry.get("AvgPricePaid")) * count
    if event in ("SellExplorationData", "MultiSellExplorationData"):
        total = _int(entry.get("TotalEarnings")) or _int(entry.get("BaseValue")) + _int(entry.get("Bonus"))
        return (EXPLORATION, total) if total > 0 else None
    if event == "SellOrganicData":
        total = sum(_int(item.get("Value")) + _int(item.get("Bonus")) for item in entry.get("BioData") or []
                    if isinstance(item, dict))
        return (EXOBIOLOGY, total) if total > 0 else None
    if event == "MissionCompleted":
        reward = _int(entry.get("Reward"))
        return (MISSIONS, reward) if reward > 0 else None
    if event == "RedeemVoucher":
        total = _int(entry.get("Amount"))
        return (VOUCHERS, total) if total > 0 else None
    return None


def _signature(entry: Dict[str, Any], amount: int) -> str:
    """Tells apart the events that share one second of the journal."""
    return "|".join(str(part) for part in (entry.get("event"), amount, entry.get("Type"), entry.get("MarketID"),
                                           entry.get("MissionID"), entry.get("Faction"), entry.get("Count")))


def fold(record: Record, entry: Dict[str, Any]) -> bool:
    """Add one event to `record`, unless it was counted already. True if the record changed."""
    found = amount_of(entry)
    stamp = str(entry.get("timestamp") or "")
    if found is None or len(stamp) < 10:
        return False
    activity, amount = found
    sig = _signature(entry, amount)
    seen = record["at_seen"]
    if record["at"]:
        if stamp < record["at"] or (stamp == record["at"] and sig in seen):
            return False
    if stamp != record["at"]:
        record["at"], record["at_seen"] = stamp, []
    record["at_seen"].append(sig)
    slot = record["by_day"].setdefault(_day(stamp), {})
    slot[activity] = slot.get(activity, 0) + amount
    return True


class IncomeBook:
    """Per-commander income by day. Constructed empty; `load(plugin_dir)` is called when the ledger starts."""

    def __init__(self) -> None:
        self._store = commander_data.new_store()
        self._plugin_dir: Optional[str] = None
        self._listeners: List[Callable[[], None]] = []

    def load(self, plugin_dir: str) -> None:
        self._plugin_dir = plugin_dir
        self._store = commander_data.read(os.path.join(plugin_dir, STATE_FILENAME), _is_legacy)

    def add_listener(self, callback: Callable[[], None]) -> None:
        self._listeners.append(callback)

    def commit(self) -> None:
        if self._plugin_dir is not None:
            commander_data.write(os.path.join(self._plugin_dir, STATE_FILENAME), self._store)
        for listener in self._listeners:
            listener()

    def record(self, cmdr: str) -> Record:
        """This commander's record (an empty one for a commander with none; nothing is created by asking)."""
        if not cmdr or not commander_data.known(self._store, cmdr):
            return _empty()
        return commander_data.payload_for(self._store, cmdr, _empty)

    def apply(self, cmdr: str, entry: Dict[str, Any]) -> bool:
        """Fold a live event in. True if anything changed (the caller then `commit`s)."""
        if not commander_data.key_for(cmdr) or entry.get("event") not in EVENTS:
            return False
        return fold(commander_data.payload_for(self._store, cmdr, _empty), entry)

    def backfilled(self, cmdr: str) -> bool:
        if not (cmdr and commander_data.known(self._store, cmdr)):
            return False
        try:
            return int(self.record(cmdr).get("backfilled") or 0) >= BACKFILL_VERSION
        except (TypeError, ValueError):
            return False

    def rebuild(self, cmdr: str, entries: Iterable[Dict[str, Any]], newer: Iterable[Dict[str, Any]] = ()) -> None:
        """Count what is in every journal the commander has (`entries`, any order) plus the live events that arrived while those
        were being read (`newer`). Each day and activity keeps the larger of the saved and the rebuilt figure, so a commander who
        deleted old journals keeps what was counted live and a complete set of journals never undercounts. Marks the record as
        backfilled; the caller then `commit`s."""
        if not commander_data.key_for(cmdr):
            return
        fresh = _empty()
        for entry in sorted(entries, key=lambda e: str(e.get("timestamp") or "")):
            fold(fresh, entry)
        for entry in sorted(newer, key=lambda e: str(e.get("timestamp") or "")):
            fold(fresh, entry)
        current = commander_data.payload_for(self._store, cmdr, _empty)
        for day, activities in fresh["by_day"].items():
            slot = current["by_day"].setdefault(day, {})
            for activity, amount in activities.items():
                slot[activity] = max(slot.get(activity, 0), amount)
        if fresh["at"] >= current["at"]:
            current["at"], current["at_seen"] = fresh["at"], fresh["at_seen"]
        current["backfilled"] = BACKFILL_VERSION


# --- what the window shows ---------------------------------------------------------------------------------------------

def totals(record: Record, since: Optional[str] = None) -> Dict[str, int]:
    """Credits per activity for every day from `since` (an ISO date, inclusive) on; all counted days when None."""
    out = {a: 0 for a in ACTIVITIES}
    for day, activities in (record.get("by_day") or {}).items():
        if since is not None and day < since:
            continue
        for activity, amount in activities.items():
            if activity in out:
                out[activity] += _int(amount)
    return out


def period_starts(today: Optional[date] = None) -> List[Tuple[str, Optional[str]]]:
    """`(label, first day)` for the periods the ledger totals: today, the last 7 days, the last 30 days and everything counted."""
    today = today or datetime.now(timezone.utc).date()
    return [("Today (UTC)", today.isoformat()), ("Last 7 days", (today - timedelta(days=6)).isoformat()),
            ("Last 30 days", (today - timedelta(days=29)).isoformat()), ("All counted", None)]


def day_rows(record: Record) -> List[Tuple[str, ...]]:
    """One row per day, newest first: the date, each activity and the day's total."""
    rows = []
    for day in sorted((record.get("by_day") or {}), reverse=True):
        slot = record["by_day"][day]
        values = [_int(slot.get(a)) for a in ACTIVITIES]
        rows.append((day, *(f"{v:,}" if v else "" for v in values), f"{sum(values):,}"))
    return rows


def first_day(record: Record) -> str:
    days = list((record.get("by_day") or {}))
    return min(days) if days else ""
