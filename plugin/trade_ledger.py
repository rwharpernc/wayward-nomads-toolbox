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


def _parse_timestamp(value: Any) -> Optional[float]:
    if not isinstance(value, str):
        return None
    try:
        return float(calendar.timegm(time.strptime(value, "%Y-%m-%dT%H:%M:%SZ")))
    except ValueError:
        return None


def new_ledger(cmdr: str, journal_file: Optional[str]) -> Dict[str, Any]:
    return {"cmdr": cmdr, "journal_file": journal_file, "first_trade": None, "last_trade": None, "rows": {}}


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


def apply_trade_event(ledger: Dict[str, Any], entry: Dict[str, Any]) -> bool:
    """Fold one `MarketBuy` / `MarketSell` into the ledger. Returns True if the
    ledger changed."""
    event = entry.get("event")
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
    profit: int


def totals(ledger: Dict[str, Any]) -> Totals:
    bought = sold = spent = revenue = basis = 0
    for row in ledger.get("rows", {}).values():
        bought += row.get("bought", 0)
        sold += row.get("sold", 0)
        spent += row.get("spent", 0)
        revenue += row.get("revenue", 0)
        basis += row.get("cost_basis", 0)
    return Totals(bought, sold, spent, revenue, revenue - basis)


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


def summary_lines(ledger: Optional[Dict[str, Any]]) -> List[str]:
    """The Session page's text, one entry per line."""
    if not ledger or not ledger.get("rows"):
        return ["No trades yet this session.", "Buy or sell at a market and they are counted here."]
    t = totals(ledger)
    hours = hours_traded(ledger)
    profit_line = f"Profit: {t.profit:+,} cr"
    if hours >= MIN_HOURS_FOR_RATE:
        profit_line += f" ({t.profit / hours:+,.0f} cr/hr)"
    lines = [
        profit_line,
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
