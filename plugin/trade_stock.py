"""
Stock bought but not yet sold: what you have spent on commodities that are still waiting to be sold, for
Trade mode. One persistent book per commander, in `trade_stock.json` beside the plugin.

Why a book of its own, and not part of the session ledger: the ledger is one login. Buying a bulk load
for a fleet carrier, or a station-to-station run, often spans several logins, and the money is out of
your account the whole time. This book follows the cargo, not the session.

It is deliberately the *same* mechanism for both ways of trading, so there is nothing to keep in step:
- station to station: buy at A (stock goes up), sell at B (stock comes down);
- load the carrier: every purchase adds to the stock; moving cargo to or from the carrier changes where it
  is, not what you paid, so it is neither added nor removed. It comes out only when it is sold.

Method: average cost per commodity. `MarketBuy` adds `Count` tonnes and `TotalCost`; `MarketSell` removes
`Count` tonnes at the commodity's average cost so far (never below zero; a sale of cargo this book never saw
is ignored). The session ledger's profit still uses the game's own `AvgPricePaid`, so the two can differ a
little when cargo came from outside what this book saw; the ledger is the profit figure, this is "what is
tied up".

Where the cargo is now (in the hold, or elsewhere such as a carrier) is not tracked here: the panel works
it out as held tonnes minus what the ship's hold currently contains.

Catching up: EDMC doesn't replay events, and trades made while EDMC was closed would be missed. So at start
the recent journals are replayed (`backfill`): events newer than what the book last saw, or, for a commander
with no book yet, the last `FIRST_RUN_DAYS` days. Each event is applied once: the book remembers the time of
the last event and fingerprints of the events at that exact second, so two sales in the same second are both
counted and a replay never doubles one.

What it can't know: cargo sold by the carrier's own trade orders, or lost, stays on the books until you
clear it (Trade > Session > Clear stock).
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
from typing import Any, Callable, Dict, List, Optional

try:
    from config import appname
except ImportError:  # unit tests outside EDMC
    appname = "EDMarketConnector"

from .trade_carrier import journal_files, key_for
from .trade_market import canonical_name

plugin_name = os.path.basename(os.path.dirname(__file__))
logger = logging.getLogger(f"{appname}.{plugin_name}")

STATE_FILENAME = "trade_stock.json"
FIRST_RUN_DAYS = 14
BACKFILL_FILES = 60
# Cheap test for "could this journal line matter?" before paying to parse it; tolerant of spacing.
_WANTED = re.compile(r'"event"\s*:\s*"(?:MarketBuy|MarketSell|LoadGame|Commander)"')
SHOWN = 4

CommanderBook = Dict[str, Any]   # {"as_of": str | None, "seen": [fingerprint...], "items": {key: item}}


@dataclass
class Holding:
    key: str
    name: str
    tonnes: int
    cost: int

    @property
    def average(self) -> int:
        return round(self.cost / self.tonnes) if self.tonnes else 0


def _int(value: Any) -> int:
    return int(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else 0


def _epoch(stamp: Any) -> Optional[float]:
    if not isinstance(stamp, str):
        return None
    try:
        return float(calendar.timegm(time.strptime(stamp, "%Y-%m-%dT%H:%M:%SZ")))
    except ValueError:
        return None


def _fingerprint(entry: Dict[str, Any]) -> str:
    return hashlib.sha1(json.dumps(entry, sort_keys=True, default=str).encode("utf-8")).hexdigest()[:12]


class StockBook:
    def __init__(self, books: Optional[Dict[str, CommanderBook]] = None) -> None:
        self.books: Dict[str, CommanderBook] = books if books is not None else {}

    # --- feeding events ------------------------------------------------------

    def feed(self, entry: Dict[str, Any], cmdr: str, not_before: Optional[float] = None) -> bool:
        """Apply one `MarketBuy` / `MarketSell` for `cmdr`. Returns True if the stock changed.
        `not_before` (epoch seconds) is the first-run cut-off for a commander with no book yet."""
        event = entry.get("event")
        if event not in ("MarketBuy", "MarketSell") or not key_for(cmdr):
            return False
        count = _int(entry.get("Count"))
        name = str(entry.get("Type_Localised") or entry.get("Type") or "").strip()
        if count <= 0 or not name:
            return False
        key = key_for(cmdr)
        existing = self.books.get(key)
        stamp = str(entry.get("timestamp") or "")
        if existing is None:
            moment = _epoch(stamp)
            if not_before is not None and moment is not None and moment < not_before:
                return False
            existing = self.books[key] = {"as_of": None, "seen": [], "items": {}}
        if not self._is_new(existing, stamp, _fingerprint(entry)):
            return False
        item_key = canonical_name(entry.get("Type") or name)
        item = existing["items"].setdefault(item_key, {"name": name, "tonnes": 0, "cost": 0})
        item["name"] = name or item["name"]
        if event == "MarketBuy":
            item["tonnes"] += count
            item["cost"] += _int(entry.get("TotalCost"))
        else:
            sold = min(count, item["tonnes"])
            if sold > 0:
                average = item["cost"] / item["tonnes"]
                item["cost"] = max(0, item["cost"] - round(average * sold))
                item["tonnes"] -= sold
        if item["tonnes"] <= 0:
            del existing["items"][item_key]
        return True

    @staticmethod
    def _is_new(book: CommanderBook, stamp: str, fingerprint: str) -> bool:
        """Has this event not been applied yet? Compares against the last event's time, and, for events in
        that same second, against fingerprints, so same-second events are each counted exactly once."""
        as_of = book.get("as_of")
        if as_of and stamp and stamp < as_of:
            return False
        if as_of and stamp == as_of:
            if fingerprint in book.get("seen", []):
                return False
            book["seen"].append(fingerprint)
            return True
        if stamp:
            book["as_of"], book["seen"] = stamp, [fingerprint]
        return True

    # --- reading -------------------------------------------------------------

    def holdings(self, cmdr: str) -> List[Holding]:
        items = (self.books.get(key_for(cmdr)) or {}).get("items", {})
        found = [Holding(k, v.get("name", k), v.get("tonnes", 0), v.get("cost", 0)) for k, v in items.items()]
        return sorted((h for h in found if h.tonnes > 0), key=lambda h: -h.cost)

    def clear(self, cmdr: str) -> None:
        """Forget the stock but keep the position in the journal, so a replay doesn't bring it back."""
        book = self.books.get(key_for(cmdr))
        if book is not None:
            book["items"] = {}


def stock_lines(holdings: List[Holding], in_hold: Dict[str, int],
                name_of: Optional[Callable[[Holding], str]] = None) -> List[str]:
    """Session-page lines. `in_hold` maps a commodity's canonical name to the tonnes in the ship's hold now,
    so each line can say how much of it is still aboard and how much is elsewhere (a carrier, usually).
    `name_of` can supply a nicer display name than the one the journal gave."""
    if not holdings:
        return []
    tonnes = sum(h.tonnes for h in holdings)
    cost = sum(h.cost for h in holdings)
    lines = [f"Stock bought, not yet sold: {tonnes:,} t, {cost:,} cr"]
    for holding in holdings[:SHOWN]:
        aboard = min(holding.tonnes, max(0, in_hold.get(holding.key, 0)))
        elsewhere = holding.tonnes - aboard
        where = []
        if aboard:
            where.append(f"{aboard:,} aboard")
        if elsewhere:
            where.append(f"{elsewhere:,} elsewhere")
        shown = name_of(holding) if name_of else holding.name
        lines.append(f"  {shown}: {holding.tonnes:,} t @ {holding.average:,} avg ({', '.join(where)})")
    if len(holdings) > SHOWN:
        lines.append(f"  +{len(holdings) - SHOWN} more")
    return lines


# --- catching up from the journals ------------------------------------------------------------------

def backfill(book: StockBook, journal_dir: str, now: Optional[float] = None,
             max_files: int = BACKFILL_FILES) -> bool:
    """Replay recent journal files into `book`. Returns True if anything changed."""
    now = time.time() if now is None else now
    cutoff = now - FIRST_RUN_DAYS * 86400
    changed = False
    cmdr = ""
    for path in journal_files(journal_dir, max_files):
        try:
            if os.path.getmtime(path) < cutoff - 86400 and not book.books:
                continue  # nothing in a file this old matters on a first run
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
                        cmdr = str(entry["Name"])
                    elif event == "LoadGame" and entry.get("Commander"):
                        cmdr = str(entry["Commander"])
                    elif cmdr and book.feed(entry, cmdr, not_before=cutoff):
                        changed = True
        except OSError:
            continue
    return changed


# --- persistence ---------------------------------------------------------------------------------------

def load_all(plugin_dir: str) -> Dict[str, CommanderBook]:
    try:
        with open(os.path.join(plugin_dir, STATE_FILENAME), "r", encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, ValueError):
        return {}
    books: Dict[str, CommanderBook] = {}
    for cmdr, book in (data.items() if isinstance(data, dict) else []):
        if isinstance(book, dict) and isinstance(book.get("items"), dict):
            books[key_for(cmdr)] = {"as_of": book.get("as_of"), "seen": list(book.get("seen") or []),
                                    "items": book["items"]}
    return books


def save_all(plugin_dir: str, books: Dict[str, CommanderBook]) -> None:
    path = os.path.join(plugin_dir, STATE_FILENAME)
    tmp = f"{path}.tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as handle:
            json.dump(books, handle, indent=2, sort_keys=True)
        os.replace(tmp, path)
    except OSError:
        logger.warning("Could not write %s", path, exc_info=True)
