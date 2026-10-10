"""
Running the carrier, for Trade mode: tritium, where the carrier is, a planned jump, its trade orders and its balance.

The journal records these as separate events, each of which names the carrier (`CarrierID`, usually `CarrierType`):

- `CarrierStats` (Carrier Management opened): `FuelLevel` (tritium, tonnes), `PendingDecommission`, and a `Finance`
  block holding `CarrierBalance`. Handled in `trade_carrier.parse_stats`, which calls `stats_facts` here.
- `CarrierDepositFuel`: `Amount` added and the new `Total`. Names only `CarrierID`.
- `CarrierLocation`: `StarSystem`, written at login and after a jump.
- `CarrierJumpRequest`: `SystemName` and `DepartureTime`; `CarrierJumpCancelled` withdraws it.
- `CarrierTradeOrder`: an order placed or cancelled (`Commodity`, `PurchaseOrder` or `SaleOrder` tonnes, `Price`,
  `BlackMarket`, `CancelTrade`). This records the order, not each tonne it later moves: a sale order names a commodity
  that is in the bay, a purchase order one that will arrive, but the amounts left on them are only known to the game.
- `CarrierFinance`: `CarrierBalance`.

Every fact carries the time of the event it came from (`<name>_at`) and only a newer event replaces it, so journals
read late or twice, in any order, give the right answer (the same rule `trade_route_start` uses). `merge_facts` applies
the rule between two records of the same carrier.
"""
from __future__ import annotations

import calendar
import time
from typing import Any, Dict, List, Optional

from .trade_blocks import Block, Note, Pair

OPS_EVENTS = ("CarrierDepositFuel", "CarrierLocation", "CarrierJumpRequest", "CarrierJumpCancelled",
              "CarrierTradeOrder", "CarrierFinance")
# These name their carrier by type as well as id, so they may start a record for a carrier first met through them.
# CarrierDepositFuel names only the id, so it can only update a carrier already on record.
CREATES_RECORD = ("CarrierLocation", "CarrierJumpRequest", "CarrierTradeOrder", "CarrierFinance")

_SCALARS = (("fuel", "fuel_at"), ("system", "system_at"), ("balance", "balance_at"))
ORDERS_SHOWN = 6
_NAME_MAX = 28
JUMP_GRACE_S = 20 * 60   # a carrier jump takes about this long after its departure time; after it, stop showing the plan


def _int(value: Any) -> int:
    return int(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else 0


def _clip(text: str) -> str:
    return text if len(text) <= _NAME_MAX else text[:_NAME_MAX - 1] + "…"


def _epoch(stamp: str) -> Optional[float]:
    try:
        return calendar.timegm(time.strptime(str(stamp), "%Y-%m-%dT%H:%M:%SZ"))
    except ValueError:
        return None


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


# --- reading events ------------------------------------------------------------------------------

def stats_facts(entry: Dict[str, Any], at: str) -> Dict[str, Any]:
    """The running-the-carrier facts a `CarrierStats` event carries."""
    facts: Dict[str, Any] = {}
    if isinstance(entry.get("FuelLevel"), (int, float)):
        facts["fuel"], facts["fuel_at"] = _int(entry["FuelLevel"]), at
    finance = entry.get("Finance")
    if isinstance(finance, dict) and isinstance(finance.get("CarrierBalance"), (int, float)):
        facts["balance"], facts["balance_at"] = _int(finance["CarrierBalance"]), at
    if "PendingDecommission" in entry:
        facts["decommission"], facts["decommission_at"] = bool(entry.get("PendingDecommission")), at
    return facts


def apply_event(record: Dict[str, Any], entry: Dict[str, Any]) -> bool:
    """Fold one running-the-carrier event into `record`. Returns True if it changed."""
    event = entry.get("event")
    at = str(entry.get("timestamp") or _now())
    changed = False

    def put(value_key: str, value: Any, at_key: str) -> bool:
        if at_key in record and at < str(record[at_key]):
            return False
        if record.get(value_key) == value and record.get(at_key) == at:
            return False
        record[value_key], record[at_key] = value, at
        return True

    if event == "CarrierDepositFuel" and isinstance(entry.get("Total"), (int, float)):
        changed = put("fuel", _int(entry["Total"]), "fuel_at")
    elif event == "CarrierLocation" and entry.get("StarSystem"):
        changed = put("system", str(entry["StarSystem"]), "system_at")
    elif event == "CarrierFinance" and isinstance(entry.get("CarrierBalance"), (int, float)):
        changed = put("balance", _int(entry["CarrierBalance"]), "balance_at")
    elif event == "CarrierJumpRequest" and entry.get("SystemName"):
        jump = {"system": str(entry["SystemName"]), "departs": str(entry.get("DepartureTime") or ""), "at": at}
        if at >= str((record.get("jump") or {}).get("at") or ""):
            changed = record.get("jump") != jump
            record["jump"] = jump
    elif event == "CarrierJumpCancelled":
        if at >= str((record.get("jump") or {}).get("at") or ""):
            changed = record.get("jump") != {"cancelled": True, "at": at}
            record["jump"] = {"cancelled": True, "at": at}
    elif event == "CarrierTradeOrder" and entry.get("Commodity"):
        orders = record.setdefault("orders", {})
        key = str(entry["Commodity"]).lower()
        if at >= str((orders.get(key) or {}).get("at") or ""):
            order = {"at": at, "name": str(entry.get("Commodity_Localised") or entry["Commodity"]),
                     "buy": _int(entry.get("PurchaseOrder")), "sell": _int(entry.get("SaleOrder")),
                     "price": _int(entry.get("Price")), "black": bool(entry.get("BlackMarket")),
                     "cancelled": bool(entry.get("CancelTrade"))}
            changed = orders.get(key) != order
            orders[key] = order
    return changed


def merge_facts(target: Dict[str, Any], other: Dict[str, Any]) -> bool:
    """Bring into `target` every fact in `other` that is newer than the one it holds. Returns True if any changed."""
    changed = False
    for value_key, at_key in (*_SCALARS, ("decommission", "decommission_at")):
        if at_key in other and (at_key not in target or str(other[at_key]) > str(target[at_key])):
            target[value_key], target[at_key] = other.get(value_key), other[at_key]
            changed = True
    mine, theirs = target.get("jump"), other.get("jump")
    if theirs and (not mine or str(theirs.get("at")) > str(mine.get("at"))):
        target["jump"] = dict(theirs)
        changed = True
    for key, order in (other.get("orders") or {}).items():
        held = (target.get("orders") or {}).get(key)
        if held is None or str(order.get("at")) > str(held.get("at")):
            target.setdefault("orders", {})[key] = dict(order)
            changed = True
    return changed


# --- what to show --------------------------------------------------------------------------------

def ops_blocks(record: Dict[str, Any], now: Optional[str] = None) -> List[Block]:
    """Rows for the running-the-carrier facts held for `record`; empty when none are known."""
    blocks: List[Block] = []
    if record.get("decommission"):
        blocks.append(Note("This carrier is being decommissioned.", warn=True))
    if isinstance(record.get("fuel"), int):
        blocks.append(Pair("Carrier tritium", f"{record['fuel']:,} t"))
    if record.get("system"):
        blocks.append(Pair("Carrier is at", _clip(str(record["system"]))))
    jump = record.get("jump") or {}
    if jump and not jump.get("cancelled") and str(jump.get("at", "")) > str(record.get("system_at", "")):
        departs = _epoch(str(jump.get("departs", "")))
        now_s = _epoch(now or _now())
        if departs is None or now_s is None or now_s <= departs + JUMP_GRACE_S:
            when = time.strftime("%d %b %H:%M", time.localtime(departs)) if departs is not None else "time unknown"
            blocks.append(Pair("Carrier jump planned", f"{_clip(str(jump.get('system', '')))}, {when}"))
    if isinstance(record.get("balance"), int):
        blocks.append(Pair("Carrier balance", f"{record['balance']:,} cr"))
    live = sorted((o for o in (record.get("orders") or {}).values() if not o.get("cancelled")
                   and (o.get("buy") or o.get("sell"))), key=lambda o: str(o.get("name", "")).lower())
    for order in live[:ORDERS_SHOWN]:
        selling = bool(order.get("sell"))
        tonnes = order["sell"] if selling else order["buy"]
        price = f" @ {order['price']:,} cr" if order.get("price") else ""
        label = f"Carrier {'selling' if selling else 'buying'} {_clip(str(order.get('name', '')))}"
        blocks.append(Pair(label, f"{tonnes:,} t{price}{' (black market)' if order.get('black') else ''}"))
    if len(live) > ORDERS_SHOWN:
        blocks.append(Note(f"+{len(live) - ORDERS_SHOWN} more carrier orders"))
    return blocks
