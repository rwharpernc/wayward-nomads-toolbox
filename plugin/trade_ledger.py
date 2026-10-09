"""
Trade mode's session ledger: what you bought and sold since the last Reset (it
spans logins), per commodity, with profit and credits per hour. Pure logic plus a small JSON file
(`trade_ledger.json` beside the plugin) so it can be unit-tested without EDMC and
survives an EDMC restart mid-session.

Profit uses the game's own numbers: a `MarketSell` event carries `TotalSale` and
`AvgPricePaid` (what the sold tonnes cost you), so profit is
`TotalSale - AvgPricePaid * Count`. Stolen or black-market cargo has an
`AvgPricePaid` of 0, so its whole sale counts as profit - the same as the credits
that actually landed in the account.

A session belongs to a **commander** and lasts until the commander presses Reset. It is deliberately *not* tied to a game
login: loading a carrier for a bulk sale can take several play sessions, and so several journal files and several EDMC
runs, for one commander. Each commander has their own working session (`LedgerBook`).

Running costs are tracked too, so the headline is a net figure: refuelling (`RefuelAll`,
`RefuelPartial`), repairs (`Repair`, `RepairAll`), Advanced Maintenance (a `Repair` whose `Items` include
"Wear"), rearm (`BuyAmmo`, `RestockVehicle`) and limpets
(`BuyDrones` bought, `SellDrones` sold back). Each carries a credit cost in the journal (field names
checked against a real journal, 2026-10-09). Insurance rebuys (`Resurrect`) and fines are not counted.
Costs only count from when WNTB saw them, like trades, so a refuel before EDMC started isn't included.
The credits-per-hour clock still runs first trade to last trade, so a refuel before the first sale
doesn't stretch it.

Beyond the totals the ledger keeps what a saved session needs to be looked at later (docs/TRADE_TECH_SPEC.md, "Trade
history"): `log`, one entry per trade or cost with the station and system it happened at (so routes can be worked
out), `meta` (when the session started, the balance at login, jumps and light years travelled), and the `routes` and
`searches` done during it. It is all bounded, and an older saved ledger without any of it still loads.

EDMC doesn't replay old events when it starts, and the game can be played while EDMC is closed, so a session would be
missing whatever happened in between. `catch_up` fixes it: the ledger remembers the last event it counted
(`meta["seen_ts"]`, plus fingerprints of the events at that exact second), and when EDMC next sees the commander it
replays the journal files written since then, through the *same* functions the live events use, adding only what is
new. Nothing is ever replaced or discarded, and `already_counted` makes any event idempotent, so replaying twice, or
EDMC delivering live an event the replay already read, never counts it twice.
"""
from __future__ import annotations

import calendar
import hashlib
import json
import logging
import os
import re
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from . import trade_commodities
from .trade_blocks import Block, Heading, Note, Pair, to_text

try:
    from config import appname
except ImportError:  # unit tests outside EDMC
    appname = "EDMarketConnector"

plugin_name = os.path.basename(os.path.dirname(__file__))
logger = logging.getLogger(f"{appname}.{plugin_name}")

STATE_FILENAME = "trade_ledger.json"
LOG_LIMIT = 5000       # trade and cost entries kept per session; the oldest are dropped past this
ROUTES_KEPT = 5        # Spansh route searches remembered for a saved session
SEARCHES_KEPT = 10     # market searches remembered for a saved session
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


def new_ledger(cmdr: str, journal_file: Optional[str], started: Optional[str] = None,
               credits: Optional[int] = None) -> Dict[str, Any]:
    """A fresh session. `started` (an ISO timestamp) and `credits` (the balance at that moment) are what the
    saved history shows as the start; both are optional."""
    return {"cmdr": cmdr, "journal_file": journal_file, "first_trade": None, "last_trade": None, "rows": {},
            "expenses": {}, "log": [], "routes": [], "searches": [],
            "meta": {"started": started, "credits_start": credits, "jumps": 0, "jump_ly": 0.0}}


def meta(ledger: Dict[str, Any]) -> Dict[str, Any]:
    """The session's meta record, created (with defaults) on a ledger saved before it existed."""
    record = ledger.setdefault("meta", {})
    record.setdefault("started", None)
    record.setdefault("credits_start", None)
    record.setdefault("jumps", 0)
    record.setdefault("jump_ly", 0.0)
    return record


def note_start(ledger: Dict[str, Any], started: Optional[str], credits: Optional[int]) -> None:
    """Record when the session began and the balance then, if they aren't known yet."""
    record = meta(ledger)
    if not record["started"] and started:
        record["started"] = started
    if record["credits_start"] is None and credits is not None:
        record["credits_start"] = credits


def note_jump(ledger: Dict[str, Any], entry: Dict[str, Any]) -> bool:
    """Count an `FSDJump` and the light years it covered."""
    if entry.get("event") != "FSDJump":
        return False
    record = meta(ledger)
    record["jumps"] += 1
    distance = entry.get("JumpDist")
    if isinstance(distance, (int, float)) and not isinstance(distance, bool) and distance > 0:
        record["jump_ly"] = round(record["jump_ly"] + float(distance), 2)
    _mark_seen(ledger, entry)
    return True


def _fingerprint(entry: Dict[str, Any]) -> str:
    return hashlib.sha1(json.dumps(entry, sort_keys=True, default=str).encode("utf-8")).hexdigest()[:12]


def _key(cmdr: str) -> str:
    return str(cmdr or "").strip().casefold()


def _mark_seen(ledger: Dict[str, Any], entry: Dict[str, Any]) -> None:
    """Remember the latest event counted (its time, and fingerprints of the events at that exact second) so it can be
    recognised, and skipped, if it ever comes round again."""
    stamp = str(entry.get("timestamp") or "")
    if not stamp:
        return
    record = meta(ledger)
    last = record.get("seen_ts") or ""
    if stamp > last:
        record["seen_ts"], record["seen_fp"] = stamp, [_fingerprint(entry)]
    elif stamp == last:
        seen = record.setdefault("seen_fp", [])
        fingerprint = _fingerprint(entry)
        if fingerprint not in seen:
            seen.append(fingerprint)
            del seen[: max(0, len(seen) - 50)]


def watermark(ledger: Dict[str, Any]) -> str:
    """The time of the last event this session has counted (or, failing that, when it started): where a catch-up
    from the journals begins."""
    record = meta(ledger)
    if record.get("seen_ts"):
        return str(record["seen_ts"])
    stamps = [str(item.get("t") or "") for item in (ledger.get("log") or [])[-1:]]
    stamps += [str(ledger.get("last_trade") or ""), str(record.get("started") or "")]
    return max(stamps)


def already_counted(ledger: Optional[Dict[str, Any]], entry: Dict[str, Any]) -> bool:
    """Has this session already counted this event? True for anything before the last event counted, and, for events in
    that same second, for those whose fingerprint was recorded. A ledger from before this was recorded falls back on the
    time of its last logged event."""
    if not ledger:
        return False
    stamp = str(entry.get("timestamp") or "")
    record = meta(ledger)
    last = record.get("seen_ts") or ""
    seen = record.get("seen_fp") or []
    if not last:
        entries = ledger.get("log") or []
        last = str(entries[-1].get("t") or "") if entries else str(ledger.get("last_trade") or "")
        seen = []
    if not stamp or not last or stamp > last:
        return False
    return True if stamp < last else _fingerprint(entry) in seen


def _log(ledger: Dict[str, Any], item: Dict[str, Any], entry: Dict[str, Any],
         where: Optional[Tuple[Optional[str], Optional[str]]]) -> None:
    item["t"] = str(entry.get("timestamp") or "")
    if where:
        if where[0]:
            item["sys"] = str(where[0])
        if where[1]:
            item["stn"] = str(where[1])
    log = ledger.setdefault("log", [])
    log.append(item)
    if len(log) > LOG_LIMIT:
        del log[: len(log) - LOG_LIMIT]


# --- catching a session up from the journals -----------------------------------------------------------------------

_WANTED = re.compile(
    r'"event"\s*:\s*"(?:MarketBuy|MarketSell|RefuelAll|RefuelPartial|Repair|RepairAll|BuyAmmo|RestockVehicle|BuyDrones|'
    r'SellDrones|FSDJump|CarrierJump|Docked|Undocked|Location|LoadGame|Commander)"')
CATCH_UP_FILES = 80   # at most this many journal files are read in one catch-up


def replay_journal(ledger: Dict[str, Any], path: str, cmdr: str) -> int:
    """Count into `ledger` the events of one journal file that it hasn't counted yet (`already_counted`), oldest first,
    through the same functions the live events use. Tracks the system and the station the commander was docked at as EDMC
    would have reported them; only `cmdr`'s own events count (a journal can hold more than one). Returns how many events
    were added."""
    wanted = _key(cmdr)
    if not wanted:
        return 0
    system: Optional[str] = None
    station: Optional[str] = None
    current = ""
    added = 0
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as handle:
            for line in handle:
                if not _WANTED.search(line):
                    continue
                try:
                    entry = json.loads(line)
                except ValueError:
                    continue
                if not isinstance(entry, dict):
                    continue
                event = entry.get("event")
                if event == "Commander" and entry.get("Name"):
                    current = _key(entry["Name"])
                    continue
                if event == "LoadGame":
                    current = _key(entry.get("Commander") or current)
                    station = None
                    if current == wanted:
                        credits = entry.get("Credits")
                        note_start(ledger, str(entry.get("timestamp") or "") or None,
                                   credits if isinstance(credits, int) and not isinstance(credits, bool) else None)
                    continue
                if current != wanted:
                    continue
                if event in ("Location", "FSDJump", "CarrierJump", "Docked") and entry.get("StarSystem"):
                    system = str(entry["StarSystem"])
                if event == "Docked" or (event == "Location" and entry.get("Docked")):
                    station = str(entry.get("StationName") or "") or None
                elif event == "Undocked" or (event == "Location" and not entry.get("Docked")):
                    station = None
                if already_counted(ledger, entry):
                    continue
                changed = apply_trade_event(ledger, entry, (system, station))
                changed = note_jump(ledger, entry) or changed
                added += 1 if changed else 0
    except OSError:
        return 0
    return added


def catch_up(ledger: Dict[str, Any], cmdr: str, journal_dir: str, max_files: int = CATCH_UP_FILES) -> int:
    """Bring the commander's session up to date from the journal files written since its last counted event, which
    covers play with EDMC closed and several logins in between. Adds only what is new, so it is safe to run any number
    of times. Returns how many events were added."""
    since = _parse_timestamp(watermark(ledger))
    if since is None:
        return 0     # a session with nothing counted and no start time has nothing to catch up from
    try:
        found = []
        for name in os.listdir(journal_dir):
            if name.startswith("Journal.") and name.endswith(".log"):
                full = os.path.join(journal_dir, name)
                modified = os.path.getmtime(full)
                if modified >= since - 120:       # a file last written before the session's last event holds nothing newer
                    found.append((modified, name, full))
    except OSError:
        return 0
    found.sort()
    added = 0
    for _modified, _name, full in found[-max_files:]:
        added += replay_journal(ledger, full, cmdr)
    return added


def rebuild_from_journal(path: str, cmdr: str, keep: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
    """A fresh session for `cmdr` built entirely from one journal file (used to recover a session whose tally was lost).
    `keep` is an existing ledger whose Spansh routes and market searches (which the journal doesn't record) are carried
    over. Returns None if the file can't be read or holds nothing for this commander."""
    if not _key(cmdr):
        return None
    ledger = new_ledger(cmdr, path)
    if replay_journal(ledger, path, cmdr) == 0 and not meta(ledger).get("started"):
        return None
    if keep:
        ledger["routes"] = list(keep.get("routes") or [])
        ledger["searches"] = list(keep.get("searches") or [])
    return ledger


def add_route(ledger: Dict[str, Any], route: Dict[str, Any]) -> None:
    """Remember a Spansh route search (a dict of start, total and hops) for the saved session."""
    routes = ledger.setdefault("routes", [])
    routes.append(route)
    del routes[: max(0, len(routes) - ROUTES_KEPT)]


def add_search(ledger: Dict[str, Any], search: Dict[str, Any]) -> None:
    """Remember a market search (side, commodity, scope and its best result) for the saved session."""
    searches = ledger.setdefault("searches", [])
    searches.append(search)
    del searches[: max(0, len(searches) - SEARCHES_KEPT)]


class LedgerBook:
    """Each commander's working session. The session is looked up by commander (ignoring case), so switching commanders
    never discards anyone's tally, and it carries on across game logins and EDMC restarts until it is reset."""

    def __init__(self, ledgers: Optional[Dict[str, Dict[str, Any]]] = None) -> None:
        self.ledgers: Dict[str, Dict[str, Any]] = ledgers if ledgers is not None else {}

    def get(self, cmdr: str) -> Optional[Dict[str, Any]]:
        return self.ledgers.get(_key(cmdr))

    def put(self, cmdr: str, ledger: Dict[str, Any]) -> None:
        self.ledgers[_key(cmdr)] = ledger

    def ensure(self, cmdr: str, journal_file: Optional[str], started: Optional[str] = None,
               credits: Optional[int] = None) -> Tuple[Dict[str, Any], bool]:
        """The commander's session, started if they have none. Returns (ledger, created). `journal_file` is only
        a note of the file being played now."""
        existing = self.get(cmdr)
        if existing is not None:
            if journal_file:
                existing["journal_file"] = journal_file
            existing["cmdr"] = existing.get("cmdr") or cmdr
            return existing, False
        ledger = new_ledger(cmdr, journal_file, started=started, credits=credits)
        self.put(cmdr, ledger)
        return ledger, True


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


def _apply_expense(ledger: Dict[str, Any], entry: Dict[str, Any], event: str,
                   where: Optional[Tuple[Optional[str], Optional[str]]] = None) -> bool:
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
    _log(ledger, {"e": "cost", "c": category, "tot": amount}, entry, where)
    _mark_seen(ledger, entry)
    return True


def apply_trade_event(ledger: Dict[str, Any], entry: Dict[str, Any],
                      where: Optional[Tuple[Optional[str], Optional[str]]] = None) -> bool:
    """Fold one trade (`MarketBuy` / `MarketSell`) or running-cost event into the ledger. Returns True
    if the ledger changed. `where` is (system, station) at the time, kept in the log so routes can be worked out."""
    event = entry.get("event")
    if event in _EXPENSE_OF_EVENT:
        return _apply_expense(ledger, entry, event, where)
    if event not in ("MarketBuy", "MarketSell"):
        return False
    count = _int(entry.get("Count"))
    if count <= 0:
        return False
    # The journal only adds Type_Localised when the display name differs from the internal one, so a commodity can arrive as
    # "superconductors"; resolve it to the game's name ("Superconductors") so it reads the same everywhere.
    name = str(entry.get("Type_Localised") or trade_commodities.resolve(entry.get("Type")) or entry.get("Type") or "?").strip() or "?"
    row = _row(ledger, name)
    if event == "MarketBuy":
        row["bought"] += count
        row["spent"] += _int(entry.get("TotalCost"))
        _log(ledger, {"e": "buy", "c": name, "n": count, "u": _int(entry.get("BuyPrice")),
                      "tot": _int(entry.get("TotalCost"))}, entry, where)
    else:
        row["sold"] += count
        row["revenue"] += _int(entry.get("TotalSale"))
        row["cost_basis"] += _int(entry.get("AvgPricePaid")) * count
        item = {"e": "sell", "c": name, "n": count, "u": _int(entry.get("SellPrice")),
                "tot": _int(entry.get("TotalSale")), "paid": _int(entry.get("AvgPricePaid"))}
        if entry.get("BlackMarket") or entry.get("IllegalGoods") or entry.get("StolenGoods"):
            item["bm"] = True
        _log(ledger, item, entry, where)
    stamp = entry.get("timestamp")
    if _parse_timestamp(stamp) is not None:
        ledger["first_trade"] = ledger.get("first_trade") or stamp
        ledger["last_trade"] = stamp
    _mark_seen(ledger, entry)
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


def _cost_pairs(expenses: Dict[str, int]) -> List[Block]:
    """'Fuel: -12,300 cr' (a negative cost, such as limpets sold back, reads '+500 cr')."""
    return [Pair(EXPENSE_LABELS[category], f"{-amount:+,} cr") for category, amount in expenses.items()]


def summary_blocks(ledger: Optional[Dict[str, Any]]) -> List[Block]:
    """The Session page's top section. With running costs it leads with the net figure and then the trade profit
    and each cost; without any it is just the profit."""
    expenses = expenses_by_category(ledger)
    has_trades = bool(ledger and ledger.get("rows"))
    if not has_trades and not expenses:
        return [Note("No trades yet this session."), Note("Buy or sell at a market and they are counted here.")]
    t = totals(ledger)
    if not has_trades:
        return [Note("No trades yet this session."), *_cost_pairs(expenses), Pair("Net", f"{t.net:+,} cr", bold=True)]
    hours = hours_traded(ledger)
    value = f"{t.net:+,} cr" if expenses else f"{t.profit:+,} cr"
    if hours >= MIN_HOURS_FOR_RATE:
        value += f" ({t.net / hours:+,.0f} cr/hr)"
    blocks: List[Block] = [Pair("Net profit" if expenses else "Profit", value, bold=True)]
    if expenses:
        blocks.append(Pair("Trade profit", f"{t.profit:+,} cr"))
        blocks.extend(_cost_pairs(expenses))
    blocks.append(Pair("Bought", f"{t.bought_t:,} t for {t.spent:,} cr"))
    blocks.append(Pair("Sold", f"{t.sold_t:,} t for {t.revenue:,} cr"))
    ranked = commodity_profits(ledger)
    if ranked:
        blocks.append(Heading("Best sales", minor=True))
        for name, tonnes, profit in ranked[:TOP_ROWS_SHOWN]:
            blocks.append(Pair(name, f"{profit:+,} cr on {tonnes:,} t", indent=1))
        worst_name, worst_t, worst_profit = ranked[-1]
        if len(ranked) > TOP_ROWS_SHOWN and worst_profit < 0:
            blocks.append(Pair("Worst", f"{worst_name} {worst_profit:+,} cr on {worst_t:,} t"))
    return blocks


def summary_lines(ledger: Optional[Dict[str, Any]]) -> List[str]:
    """`summary_blocks` as plain lines (for tests and logs)."""
    return to_text(summary_blocks(ledger))


# --- persistence --------------------------------------------------------------

def load_book(plugin_dir: str) -> LedgerBook:
    """The saved working sessions. A file from before sessions were kept per commander held one ledger; it becomes that
    commander's."""
    try:
        with open(os.path.join(plugin_dir, STATE_FILENAME), "r", encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, ValueError):
        return LedgerBook()
    if not isinstance(data, dict):
        return LedgerBook()
    if isinstance(data.get("ledgers"), dict):
        return LedgerBook({_key(k): v for k, v in data["ledgers"].items() if isinstance(v, dict) and isinstance(v.get("rows"), dict)})
    if isinstance(data.get("rows"), dict):                    # the earlier single-ledger file
        return LedgerBook({_key(str(data.get("cmdr") or "")): data}) if _key(str(data.get("cmdr") or "")) else LedgerBook()
    return LedgerBook()


def save_book(plugin_dir: str, book: LedgerBook) -> None:
    """Temp file then replace, so a crash can't leave a half-written file."""
    path = os.path.join(plugin_dir, STATE_FILENAME)
    tmp = f"{path}.tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as handle:
            json.dump({"ledgers": book.ledgers}, handle, indent=2, sort_keys=True)
        os.replace(tmp, path)
    except OSError:
        logger.warning("Could not write %s", path, exc_info=True)
