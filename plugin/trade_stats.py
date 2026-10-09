"""
The numbers behind Trade History (pure logic, no Tk): everything the history window and "Copy summary" show, worked
out from one saved session record (see trade_history.py for the record's shape).

Totals come from the record's `rows` and `expenses` (kept exactly), not from the trade `log`, which is bounded and
could be shorter on a very long session. The log supplies the detail: which station each trade happened at, in order,
which is what makes a route.

- Trade profit = sales minus what the sold tonnes cost (the game's `AvgPricePaid`); net profit = trade profit minus
  running costs (fuel, repairs, advanced maintenance, rearm, limpets). The balance change is separate: it is the
  actual credits difference between login and save, and includes everything else you did (missions, selling data...).
- Per hour uses the *trading* time, first to last trade, so a long wait before the first sale doesn't dilute it.
- A *visit* is a run of consecutive trades and costs at one station; the route is the visits in order.
"""
from __future__ import annotations

import calendar
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple

MIN_HOURS_FOR_RATE = 0.05   # about three minutes, as in the live ledger

COST_LABELS = {"fuel": "Fuel", "repairs": "Repairs", "maintenance": "Advanced maintenance", "rearm": "Rearm",
               "limpets": "Limpets"}


def parse_time(value: Any) -> Optional[float]:
    if not isinstance(value, str):
        return None
    try:
        return float(calendar.timegm(time.strptime(value, "%Y-%m-%dT%H:%M:%SZ")))
    except ValueError:
        return None


def hours_between(start: Any, end: Any) -> float:
    a, b = parse_time(start), parse_time(end)
    return 0.0 if a is None or b is None else max(0.0, b - a) / 3600.0


def fmt_duration(hours: float) -> str:
    """'1 h 05 m', '23 m', or '—' when there is nothing to show."""
    minutes = int(round(hours * 60))
    if minutes <= 0:
        return "—"
    return f"{minutes // 60} h {minutes % 60:02d} m" if minutes >= 60 else f"{minutes} m"


def fmt_time(value: Any, with_seconds: bool = False) -> str:
    """'2026-10-09 10:07' (UTC, as the journal writes it); blank when unknown."""
    moment = parse_time(value)
    if moment is None:
        return ""
    return time.strftime("%Y-%m-%d %H:%M:%S" if with_seconds else "%Y-%m-%d %H:%M", time.gmtime(moment))


def _int(value: Any) -> int:
    return int(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else 0


# --- the headline numbers ----------------------------------------------------------------------------

@dataclass
class Overview:
    started: str
    ended: str
    session_hours: float
    trading_hours: float
    bought_t: int
    sold_t: int
    spent: int
    revenue: int
    cost_basis: int
    trade_profit: int
    expenses: int
    net: int
    net_per_hour: Optional[float]      # None until there is enough trading time to mean something
    profit_per_tonne: Optional[float]  # trade profit per tonne sold
    margin_pct: Optional[float]        # trade profit as a percentage of what the sold tonnes cost
    credits_start: Optional[int]
    credits_end: Optional[int]
    balance_change: Optional[int]
    jumps: int
    jump_ly: float
    profit_per_jump: Optional[float]
    profit_per_ly: Optional[float]
    trades: int                        # individual buys and sales in the log
    stations: int                      # distinct stations traded at
    visits: int


def overview(record: Dict[str, Any]) -> Overview:
    rows = (record.get("rows") or {}).values()
    bought = sum(_int(r.get("bought")) for r in rows)
    sold = sum(_int(r.get("sold")) for r in rows)
    spent = sum(_int(r.get("spent")) for r in rows)
    revenue = sum(_int(r.get("revenue")) for r in rows)
    basis = sum(_int(r.get("cost_basis")) for r in rows)
    expenses = sum(_int(v) for v in (record.get("expenses") or {}).values())
    profit = revenue - basis
    net = profit - expenses
    trading = hours_between(record.get("first_trade"), record.get("last_trade"))
    started = str(record.get("started") or record.get("first_trade") or "")
    ended = str(record.get("ended") or record.get("last_trade") or record.get("saved_at") or "")
    start_credits, end_credits = record.get("credits_start"), record.get("credits_end")
    jumps, ly = _int(record.get("jumps")), float(record.get("jump_ly") or 0.0)
    log = record.get("log") or []
    trade_visits = visits(record)
    return Overview(
        started=started, ended=ended, session_hours=hours_between(started, ended), trading_hours=trading,
        bought_t=bought, sold_t=sold, spent=spent, revenue=revenue, cost_basis=basis, trade_profit=profit,
        expenses=expenses, net=net,
        net_per_hour=net / trading if trading >= MIN_HOURS_FOR_RATE else None,
        profit_per_tonne=profit / sold if sold else None,
        margin_pct=profit / basis * 100 if basis else None,
        credits_start=start_credits if isinstance(start_credits, int) else None,
        credits_end=end_credits if isinstance(end_credits, int) else None,
        balance_change=(end_credits - start_credits) if isinstance(start_credits, int) and isinstance(end_credits, int) else None,
        jumps=jumps, jump_ly=ly, profit_per_jump=net / jumps if jumps else None, profit_per_ly=net / ly if ly > 0 else None,
        trades=sum(1 for item in log if item.get("e") in ("buy", "sell")),
        stations=len({(v.system, v.station) for v in trade_visits if v.station}), visits=len(trade_visits),
    )


# --- by commodity -------------------------------------------------------------------------------------

@dataclass
class CommodityStat:
    name: str
    bought_t: int
    spent: int
    sold_t: int
    revenue: int
    cost_basis: int
    avg_buy: Optional[int]
    avg_sell: Optional[int]
    profit: int
    margin_pct: Optional[float]
    per_tonne: Optional[int]
    left_t: int            # bought but not sold in this session (still held, or on a carrier)


def commodity_stats(record: Dict[str, Any]) -> List[CommodityStat]:
    """Every commodity traded, best trade profit first."""
    stats = []
    for name, row in (record.get("rows") or {}).items():
        bought, spent = _int(row.get("bought")), _int(row.get("spent"))
        sold, revenue, basis = _int(row.get("sold")), _int(row.get("revenue")), _int(row.get("cost_basis"))
        profit = revenue - basis
        stats.append(CommodityStat(
            name=name, bought_t=bought, spent=spent, sold_t=sold, revenue=revenue, cost_basis=basis,
            avg_buy=round(spent / bought) if bought else None, avg_sell=round(revenue / sold) if sold else None,
            profit=profit, margin_pct=profit / basis * 100 if basis else None,
            per_tonne=round(profit / sold) if sold else None, left_t=max(0, bought - sold)))
    stats.sort(key=lambda s: (-s.profit, s.name.casefold()))
    return stats


def cost_breakdown(record: Dict[str, Any]) -> List[Tuple[str, int]]:
    """(label, credits) for each running cost that is not zero, in the usual order."""
    costs = record.get("expenses") or {}
    return [(COST_LABELS[key], _int(costs[key])) for key in COST_LABELS if _int(costs.get(key))]


# --- the route: stations visited in order -------------------------------------------------------------------

@dataclass
class Visit:
    system: str
    station: str
    first: str
    last: str
    bought: Dict[str, int] = field(default_factory=dict)      # commodity -> tonnes bought here
    sold: Dict[str, int] = field(default_factory=dict)        # commodity -> tonnes sold here
    spent: int = 0
    revenue: int = 0
    profit: int = 0                                           # sales here minus what those tonnes cost
    costs: int = 0                                            # fuel, repairs... paid here

    @property
    def bought_t(self) -> int:
        return sum(self.bought.values())

    @property
    def sold_t(self) -> int:
        return sum(self.sold.values())

    @property
    def net(self) -> int:
        return self.profit - self.costs


def visits(record: Dict[str, Any]) -> List[Visit]:
    """The stations traded at, in order. A run of consecutive entries at one station is one visit; going back to
    a station later is a new visit, so the list reads as the route that was flown."""
    found: List[Visit] = []
    for item in record.get("log") or []:
        kind = item.get("e")
        if kind not in ("buy", "sell", "cost"):
            continue
        system, station = str(item.get("sys") or ""), str(item.get("stn") or "")
        if not found or (found[-1].system, found[-1].station) != (system, station):
            found.append(Visit(system=system, station=station, first=str(item.get("t") or ""), last=str(item.get("t") or "")))
        visit = found[-1]
        visit.last = str(item.get("t") or visit.last)
        name, count, total = str(item.get("c") or "?"), _int(item.get("n")), _int(item.get("tot"))
        if kind == "buy":
            visit.bought[name] = visit.bought.get(name, 0) + count
            visit.spent += total
        elif kind == "sell":
            visit.sold[name] = visit.sold.get(name, 0) + count
            visit.revenue += total
            visit.profit += total - _int(item.get("paid")) * count
        else:
            visit.costs += total
    return found


@dataclass
class StationStat:
    system: str
    station: str
    visits: int
    bought_t: int
    spent: int
    sold_t: int
    revenue: int
    profit: int
    costs: int

    @property
    def net(self) -> int:
        return self.profit - self.costs


def station_stats(record: Dict[str, Any]) -> List[StationStat]:
    """The visits added up per station, best net first."""
    totals: Dict[Tuple[str, str], StationStat] = {}
    for visit in visits(record):
        key = (visit.system.casefold(), visit.station.casefold())
        stat = totals.setdefault(key, StationStat(visit.system, visit.station, 0, 0, 0, 0, 0, 0, 0))
        stat.visits += 1
        stat.bought_t += visit.bought_t
        stat.spent += visit.spent
        stat.sold_t += visit.sold_t
        stat.revenue += visit.revenue
        stat.profit += visit.profit
        stat.costs += visit.costs
    return sorted(totals.values(), key=lambda s: (-s.net, s.station.casefold()))


def route_text(visit: Visit) -> str:
    """'bought 100 t Gold; sold 40 t Tea' for one visit."""
    parts = []
    if visit.bought:
        parts.append("bought " + ", ".join(f"{n:,} t {name}" for name, n in visit.bought.items()))
    if visit.sold:
        parts.append("sold " + ", ".join(f"{n:,} t {name}" for name, n in visit.sold.items()))
    if visit.costs and not parts:
        parts.append("refuel / repair")
    return "; ".join(parts)


# --- the log, for the table and the CSV --------------------------------------------------------------------

LOG_HEADERS = ("Time (UTC)", "Type", "Commodity", "Tonnes", "Unit price", "Total", "Profit", "Station", "System")


def log_rows(record: Dict[str, Any]) -> List[Tuple[str, ...]]:
    """One row per logged trade or cost, oldest first, as plain strings."""
    rows: List[Tuple[str, ...]] = []
    for item in record.get("log") or []:
        kind = item.get("e")
        total = _int(item.get("tot"))
        if kind == "buy":
            rows.append((fmt_time(item.get("t"), True), "Buy", str(item.get("c") or ""), f"{_int(item.get('n')):,}",
                         f"{_int(item.get('u')):,}", f"{-total:,}", "", str(item.get("stn") or ""), str(item.get("sys") or "")))
        elif kind == "sell":
            profit = total - _int(item.get("paid")) * _int(item.get("n"))
            tag = "Sell (black market)" if item.get("bm") else "Sell"
            rows.append((fmt_time(item.get("t"), True), tag, str(item.get("c") or ""), f"{_int(item.get('n')):,}",
                         f"{_int(item.get('u')):,}", f"{total:,}", f"{profit:+,}", str(item.get("stn") or ""),
                         str(item.get("sys") or "")))
        elif kind == "cost":
            rows.append((fmt_time(item.get("t"), True), "Cost", COST_LABELS.get(str(item.get("c")), str(item.get("c") or "")),
                         "", "", f"{-total:,}", "", str(item.get("stn") or ""), str(item.get("sys") or "")))
    return rows


def csv_text(record: Dict[str, Any]) -> str:
    """The log as CSV (UTF-8 text)."""
    import csv
    import io
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(LOG_HEADERS)
    writer.writerows(log_rows(record))
    return buffer.getvalue()


# --- a one-line label, and the clipboard summary ---------------------------------------------------------------

def label(record: Dict[str, Any]) -> str:
    """For the session picker: '2026-10-09 10:12 · Bocheaux · net +344,827 cr · 1 h 02 m'."""
    o = overview(record)
    when = fmt_time(o.started or record.get("saved_at")) or "?"
    return f"{when} · {record.get('cmdr') or '?'} · net {o.net:+,} cr · {fmt_duration(o.trading_hours)}"


def _rate(value: Optional[float], unit: str) -> str:
    return "—" if value is None else f"{value:+,.0f} {unit}"


def summary_text(record: Dict[str, Any]) -> List[str]:
    """Plain text for the clipboard: the headline numbers, costs, commodities, stations and the route."""
    o = overview(record)
    lines = [
        f"Trade session - {record.get('cmdr') or '?'} - {fmt_time(o.started) or '?'} to {fmt_time(o.ended) or '?'} UTC",
        f"Ship: {record.get('ship') or '?'}" + (f" ({record['pad']} pad)" if record.get("pad") else ""),
        f"Net profit: {o.net:+,} cr   Trade profit: {o.trade_profit:+,} cr   Running costs: -{o.expenses:,} cr",
        f"Per hour: {_rate(o.net_per_hour, 'cr/hr')}   Trading time: {fmt_duration(o.trading_hours)}   "
        f"Session length: {fmt_duration(o.session_hours)}",
        f"Bought {o.bought_t:,} t for {o.spent:,} cr; sold {o.sold_t:,} t for {o.revenue:,} cr",
        f"Per tonne sold: {_rate(o.profit_per_tonne, 'cr/t')}   Margin: "
        + ("—" if o.margin_pct is None else f"{o.margin_pct:+.1f}%"),
        f"Jumps: {o.jumps} ({o.jump_ly:,.1f} ly)   Per jump: {_rate(o.profit_per_jump, 'cr')}",
    ]
    if o.balance_change is not None:
        lines.append(f"Balance: {o.credits_start:,} -> {o.credits_end:,} cr ({o.balance_change:+,})")
    costs = cost_breakdown(record)
    if costs:
        lines.append("Costs: " + ", ".join(f"{name} {amount:,}" for name, amount in costs))
    stats = commodity_stats(record)
    if stats:
        lines.append("")
        lines.append("Commodities (best first):")
        for s in stats:
            lines.append(f"  {s.name}: bought {s.bought_t:,} t, sold {s.sold_t:,} t, profit {s.profit:+,} cr"
                         + (f" ({s.per_tonne:+,} cr/t)" if s.per_tonne is not None else ""))
    route = visits(record)
    if route:
        lines.append("")
        lines.append("Route:")
        for number, visit in enumerate(route, start=1):
            lines.append(f"  {number}. {visit.station or '?'} ({visit.system or '?'}) - {route_text(visit)} - net {visit.net:+,} cr")
    return lines


# --- table rows for the history window ---------------------------------------------------------------------
# Each returns plain strings, one tuple per row, matching a *_HEADERS tuple in the window's columns.

def _n(value: Optional[int]) -> str:
    return "" if value is None else f"{value:,}"


def _pct(value: Optional[float]) -> str:
    return "" if value is None else f"{value:+.1f}%"


def commodity_rows(record: Dict[str, Any]) -> List[Tuple[str, ...]]:
    return [(s.name, _n(s.bought_t), _n(s.spent), _n(s.avg_buy), _n(s.sold_t), _n(s.revenue), _n(s.avg_sell),
             f"{s.profit:+,}" if s.sold_t else "", _pct(s.margin_pct), "" if s.per_tonne is None else f"{s.per_tonne:+,}",
             _n(s.left_t))
            for s in commodity_stats(record)]


def station_rows(record: Dict[str, Any]) -> List[Tuple[str, ...]]:
    return [(s.station or "?", s.system or "?", str(s.visits), _n(s.bought_t), _n(s.spent), _n(s.sold_t), _n(s.revenue),
             f"{s.profit:+,}", f"{-s.costs:,}" if s.costs else "", f"{s.net:+,}") for s in station_stats(record)]


def route_rows(record: Dict[str, Any]) -> List[Tuple[str, ...]]:
    """The visits in order, with a running net so the route reads as the session's progress."""
    rows = []
    running = 0
    for number, visit in enumerate(visits(record), start=1):
        running += visit.net
        rows.append((str(number), fmt_time(visit.first), visit.station or "?", visit.system or "?", route_text(visit),
                     f"{visit.net:+,}", f"{running:+,}"))
    return rows


def lookup_route_rows(record: Dict[str, Any]) -> List[Tuple[str, ...]]:
    """The Spansh route searches made during the session: when, from where, how many hops, the total, and the chain."""
    rows = []
    for route in record.get("routes") or []:
        hops = route.get("hops") or []
        chain = " → ".join([str(hops[0].get("from", "?"))] + [str(h.get("to", "?")) for h in hops]) if hops else ""
        rows.append((fmt_time(route.get("t")), str(route.get("start") or ""), str(len(hops)),
                     f"{_int(route.get('total')):+,}", chain))
    return rows


def search_rows(record: Dict[str, Any]) -> List[Tuple[str, ...]]:
    """The market searches made during the session and the best result each found."""
    rows = []
    for item in record.get("searches") or []:
        best = item.get("best") or {}
        rows.append((fmt_time(item.get("t")), "Buy" if item.get("side") == "buy" else "Sell", str(item.get("commodity") or ""),
                     _n(_int(item.get("tonnes"))), "Near me" if item.get("scope") == "near" else "Galaxy",
                     str(best.get("station") or "(none found)"), str(best.get("system") or ""),
                     _n(_int(best.get("price"))) if best else "", f"{float(best.get('ly') or 0):.1f}" if best else ""))
    return rows


def stock_rows(record: Dict[str, Any]) -> List[Tuple[str, ...]]:
    """Stock bought but not yet sold, as it stood when the session was saved."""
    rows = []
    for item in record.get("stock") or []:
        tonnes, cost = _int(item.get("tonnes")), _int(item.get("cost"))
        rows.append((str(item.get("name") or "?"), _n(tonnes), _n(cost), _n(round(cost / tonnes)) if tonnes else ""))
    return rows


def hold_rows(record: Dict[str, Any]) -> List[Tuple[str, ...]]:
    return [(str(item.get("name") or "?"), _n(_int(item.get("tonnes")))) for item in record.get("hold") or []]


def carrier_rows(record: Dict[str, Any]) -> List[Tuple[str, ...]]:
    rows = []
    for item in record.get("carriers") or []:
        capacity = _int(item.get("capacity"))
        rows.append((str(item.get("type") or ""), str(item.get("name") or item.get("callsign") or ""),
                     f"{_int(item.get('cargo')):,} / {capacity:,}" if capacity else "unknown",
                     _n(_int(item.get("free"))) if capacity else "", _n(_int(item.get("reserved"))) if capacity else ""))
    return rows
