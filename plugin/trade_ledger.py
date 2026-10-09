"""
Trade mode's session ledger: what you bought and sold since logging in, per
commodity, with profit and credits per hour. Pure logic plus a small JSON file
(`trade_ledger.json` beside the plugin) so it can be unit-tested without EDMC and
survives an EDMC restart mid-session.

Profit uses the game's own numbers: a `MarketSell` event carries `TotalSale` and
`AvgPricePaid` (what the sold tonnes cost you), so profit is
`TotalSale - AvgPricePaid * Count`. Stolen or black-market cargo has an
`AvgPricePaid` of 0, so its whole sale counts as profit - the same as the credits
that actually landed in the account.

A session is one game login, tied to the journal file it started in, the same
rule session_credits.py uses (a logout to the menu and back continues it).

Running costs are tracked too, so the headline is a net figure: refuelling (`RefuelAll`,
`RefuelPartial`), repairs (`Repair`, `RepairAll`), Advanced Maintenance (a `Repair` whose `Items` include
"Wear"), rearm (`BuyAmmo`, `RestockVehicle`) and limpets
(`BuyDrones` bought, `SellDrones` sold back). Each carries a credit cost in the journal (field names
checked against a real journal, 2026-10-09). Insurance rebuys (`Resurrect`) and fines are not counted.
Costs only count from when WNTB saw them, like trades, so a refuel before EDMC started isn't included.
The credits-per-hour clock still runs first trade to last trade, so a refuel before the first sale
doesn't stretch it.
"""
from __future__ import annotations

import calendar
import json
import logging
import os
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

try:
    from config import appname
except ImportError:  # unit tests outside EDMC
    appname = "EDMarketConnector"

plugin_name = os.path.basename(os.path.dirname(__file__))
logger = logging.getLogger(f"{appname}.{plugin_name}")

STATE_FILENAME = "trade_ledger.json"
MIN_HOURS_FOR_RATE = 0.05  # about three minutes
TOP_ROWS_SHOWN = 5

_ROW_FIELDS = ("bought", "spent", "sold", "revenue", "cost_basis")

# Running costs: category -> (heading, journal events that add to it).
EXPENSE_LABELS = {"fuel": "Fuel", "repairs": "Repairs", "maintenance": "Advanced maintenance",
                  "rearm": "Rearm", "limpets": "Limpets"}
_EXPENSE_OF_EVENT = {
    "RefuelAll": "fuel", "RefuelPartial": "fuel", "Repair": "repairs", "RepairAll": "repairs",
    "BuyAmmo": "rearm", "RestockVehicle": "rearm", "BuyDrones": "limpets", "SellDrones": "limpets",
}


def _parse_timestamp(value: Any) -> Optional[float]:
    if not isinstance(value, str):
        return None
    try:
        return float(calendar.timegm(time.strptime(value, "%Y-%m-%dT%H:%M:%SZ")))
    except ValueError:
        return None


def new_ledger(cmdr: str, journal_file: Optional[str]) -> Dict[str, Any]:
    return {"cmdr": cmdr, "journal_file": journal_file, "first_trade": None, "last_trade": None, "rows": {},
            "expenses": {}}


def sync_ledger(
    ledger: Optional[Dict[str, Any]], cmdr: str, journal_file: Optional[str],
) -> Tuple[Dict[str, Any], bool]:
    """Same journal file and commander -> the saved ledger carries on; anything
    else starts a fresh one. Returns (ledger, continued)."""
    if ledger and journal_file and ledger.get("journal_file") == journal_file:
        saved = ledger.get("cmdr")
        if not saved or not cmdr or saved == cmdr:
            if cmdr:
                ledger["cmdr"] = cmdr
            return ledger, True
    return new_ledger(cmdr, journal_file), False


def _row(ledger: Dict[str, Any], name: str) -> Dict[str, int]:
    row = ledger["rows"].setdefault(name, {})
    for field in _ROW_FIELDS:
        row.setdefault(field, 0)
    return row


def _int(value: Any) -> int:
    return int(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else 0


def _is_maintenance(entry: Dict[str, Any]) -> bool:
    """Advanced Maintenance shows up as an ordinary `Repair` event whose `Items` include "Wear" (module wear),
    confirmed on a real journal. The charge covers everything in that event, so it can't be split further."""
    items = entry.get("Items")
    return isinstance(items, list) and any(str(item).strip().lower() == "wear" for item in items)


def _apply_expense(ledger: Dict[str, Any], entry: Dict[str, Any], event: str) -> bool:
    """Add one cost event. `SellDrones` is limpets sold back, so it reduces the limpet cost (the
    category can go negative if you sell more than you bought this session)."""
    if event == "BuyDrones":
        amount = _int(entry.get("TotalCost"))
    elif event == "SellDrones":
        amount = -_int(entry.get("TotalSale"))
    else:
        amount = _int(entry.get("Cost"))
    if amount == 0:
        return False
    category = _EXPENSE_OF_EVENT[event]
    if event == "Repair" and _is_maintenance(entry):
        category = "maintenance"
    expenses = ledger.setdefault("expenses", {})
    expenses[category] = expenses.get(category, 0) + amount
    return True


def apply_trade_event(ledger: Dict[str, Any], entry: Dict[str, Any]) -> bool:
    """Fold one trade (`MarketBuy` / `MarketSell`) or running-cost event into the ledger. Returns True
    if the ledger changed."""
    event = entry.get("event")
    if event in _EXPENSE_OF_EVENT:
        return _apply_expense(ledger, entry, event)
    if event not in ("MarketBuy", "MarketSell"):
        return False
    count = _int(entry.get("Count"))
    if count <= 0:
        return False
    name = str(entry.get("Type_Localised") or entry.get("Type") or "?").strip() or "?"
    row = _row(ledger, name)
    if event == "MarketBuy":
        row["bought"] += count
        row["spent"] += _int(entry.get("TotalCost"))
    else:
        row["sold"] += count
        row["revenue"] += _int(entry.get("TotalSale"))
        row["cost_basis"] += _int(entry.get("AvgPricePaid")) * count
    stamp = entry.get("timestamp")
    if _parse_timestamp(stamp) is not None:
        ledger["first_trade"] = ledger.get("first_trade") or stamp
        ledger["last_trade"] = stamp
    return True


@dataclass
class Totals:
    bought_t: int
    sold_t: int
    spent: int
    revenue: int
    profit: int          # trade profit: sales minus what the sold tonnes cost
    expenses: int = 0    # fuel + repairs + rearm + limpets

    @property
    def net(self) -> int:
        return self.profit - self.expenses


def expenses_by_category(ledger: Optional[Dict[str, Any]]) -> Dict[str, int]:
    """Running costs so far, in display order, leaving out categories that are zero."""
    recorded = (ledger or {}).get("expenses") or {}
    return {c: recorded[c] for c in EXPENSE_LABELS if recorded.get(c)}


def totals(ledger: Dict[str, Any]) -> Totals:
    bought = sold = spent = revenue = basis = 0
    for row in ledger.get("rows", {}).values():
        bought += row.get("bought", 0)
        sold += row.get("sold", 0)
        spent += row.get("spent", 0)
        revenue += row.get("revenue", 0)
        basis += row.get("cost_basis", 0)
    return Totals(bought, sold, spent, revenue, revenue - basis, sum(expenses_by_category(ledger).values()))


def hours_traded(ledger: Dict[str, Any]) -> float:
    first, last = _parse_timestamp(ledger.get("first_trade")), _parse_timestamp(ledger.get("last_trade"))
    if first is None or last is None:
        return 0.0
    return max(0.0, last - first) / 3600.0


def commodity_profits(ledger: Dict[str, Any]) -> List[Tuple[str, int, int]]:
    """(commodity, tonnes sold, profit) for every commodity sold at least once,
    best profit first."""
    rows = []
    for name, row in ledger.get("rows", {}).items():
        if row.get("sold", 0) > 0:
            rows.append((name, row["sold"], row.get("revenue", 0) - row.get("cost_basis", 0)))
    rows.sort(key=lambda item: item[2], reverse=True)
    return rows


def _cost_lines(expenses: Dict[str, int]) -> List[str]:
    """'Fuel: -12,300 cr' (a negative cost, such as limpets sold back, reads '+500 cr')."""
    return [f"{EXPENSE_LABELS[category]}: {-amount:+,} cr" for category, amount in expenses.items()]


def summary_lines(ledger: Optional[Dict[str, Any]]) -> List[str]:
    """The Session page's text, one entry per line. With running costs it leads with the net figure
    and then the trade profit and each cost; without any it is just the profit, as before."""
    expenses = expenses_by_category(ledger)
    has_trades = bool(ledger and ledger.get("rows"))
    if not has_trades and not expenses:
        return ["No trades yet this session.", "Buy or sell at a market and they are counted here."]
    t = totals(ledger)
    if not has_trades:
        return ["No trades yet this session.", *_cost_lines(expenses), f"Net: {t.net:+,} cr"]
    hours = hours_traded(ledger)
    headline = f"Net profit: {t.net:+,} cr" if expenses else f"Profit: {t.profit:+,} cr"
    if hours >= MIN_HOURS_FOR_RATE:
        headline += f" ({t.net / hours:+,.0f} cr/hr)"
    lines = [headline]
    if expenses:
        lines.append(f"Trade profit: {t.profit:+,} cr")
        lines.extend(_cost_lines(expenses))
    lines += [
        f"Bought {t.bought_t:,} t for {t.spent:,} cr",
        f"Sold {t.sold_t:,} t for {t.revenue:,} cr",
    ]
    ranked = commodity_profits(ledger)
    if ranked:
        lines.append("Best sales:")
        for name, tonnes, profit in ranked[:TOP_ROWS_SHOWN]:
            lines.append(f"  {name}: {profit:+,} cr on {tonnes:,} t")
        worst_name, worst_t, worst_profit = ranked[-1]
        if len(ranked) > TOP_ROWS_SHOWN and worst_profit < 0:
            lines.append(f"Worst: {worst_name} {worst_profit:+,} cr on {worst_t:,} t")
    return lines


# --- persistence --------------------------------------------------------------

def load_ledger(plugin_dir: str) -> Optional[Dict[str, Any]]:
    try:
        with open(os.path.join(plugin_dir, STATE_FILENAME), "r", encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) and isinstance(data.get("rows"), dict) else None


def save_ledger(plugin_dir: str, ledger: Dict[str, Any]) -> None:
    """Temp file then replace, so a crash can't leave a half-written file."""
    path = os.path.join(plugin_dir, STATE_FILENAME)
    tmp = f"{path}.tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as handle:
            json.dump(ledger, handle, indent=2, sort_keys=True)
        os.replace(tmp, path)
    except OSError:
        logger.warning("Could not write %s", path, exc_info=True)
