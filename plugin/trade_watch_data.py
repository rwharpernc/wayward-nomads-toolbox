"""Market watch list: the commodities a commander wants to see prices for at a glance, kept per commander. One small JSON file
(`trade_watch.json` beside the plugin, `commander_data.py`): every commander has a separate list, and nothing is ever sent anywhere
from here (the optional Spansh refresh is `trade_watch_lookup.py`, run only on a button press).

Two kinds of price are held for a watched commodity:

- **Seen**: whenever the commander opens a station's commodity market, `Market.json` is read and, for each watched commodity the
  station trades, its buy price (what the station charges), sell price (what it pays), stock, demand and the time are kept, one
  entry per station, newest 12 stations. These are saved, so they survive a restart, and each says how old it is: a price is only
  true when it was seen.
- **Spansh**: the best buy and sell near the commander, from the lookup. These are held in memory only (they go stale in minutes and
  are one button press away), and are replaced by the next refresh.

`best_buy` / `best_sell` pick the cheapest to buy and the dearest to sell across both. Limits keep the file small and the panel
quick: 30 watched commodities. Past it an add is refused with a message, never dropped quietly. This is the pure part (no Tk); the
window is `trade_watch_window.py` and the Trade row is `trade_watch_panel.py`."""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Mapping, Optional, Tuple

from . import commander_data, trade_commodities
from .trade_market import MarketItem, canonical_name

try:
    from config import appname
except ImportError:  # unit tests outside EDMC
    appname = "EDMarketConnector"

plugin_name = os.path.basename(os.path.dirname(__file__))
logger = logging.getLogger(f"{appname}.{plugin_name}")

STATE_FILENAME = "trade_watch.json"
MAX_WATCHED = 30
MAX_SIGHTINGS = 12     # stations kept per commodity
MAX_NAME = 100         # a station or system name read from a file is cut to this

SEEN = "seen"
SPANSH = "Spansh"


class WatchError(ValueError):
    """A change that cannot be made; the message says why and is shown to the commander as it is."""


@dataclass(frozen=True)
class Quote:
    """One price for one commodity at one station: `price` in cr per tonne, `quantity` the stock (to buy) or demand (to sell)."""
    price: int
    quantity: int
    station: str
    system: str
    source: str            # SEEN or SPANSH
    when: str = ""         # UTC time the price was seen or fetched
    distance_ly: float = 0.0   # from the system the Spansh lookup was made for; 0 for a price seen at a market


@dataclass(frozen=True)
class Sighting:
    commodity: str
    station: str
    system: str
    buy_price: int
    sell_price: int
    stock: int
    demand: int
    seen: str


@dataclass(frozen=True)
class Lookup:
    """What Spansh knew near `reference` when asked: the stations to buy at (cheapest first) and to sell at (dearest first), each side
    possibly empty (nothing in stock / wanted). Several are kept so a station that runs short of stock has others beside it."""
    buys: Tuple[Quote, ...]
    sells: Tuple[Quote, ...]
    reference: str
    when: str

    @property
    def buy(self) -> Optional[Quote]:
        return self.buys[0] if self.buys else None

    @property
    def sell(self) -> Optional[Quote]:
        return self.sells[0] if self.sells else None


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _epoch(stamp: str) -> Optional[float]:
    try:
        return datetime.strptime(stamp, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc).timestamp()
    except (TypeError, ValueError):
        return None


def age(stamp: str, now: Optional[str] = None) -> str:
    """How long ago `stamp` was, in the largest whole unit: `just now`, `5 min`, `3 h`, `2 d`; empty when it is unknown."""
    then, current = _epoch(stamp), _epoch(now or _now())
    if then is None or current is None:
        return ""
    seconds = max(0.0, current - then)
    if seconds < 60:
        return "just now"
    if seconds < 3600:
        return f"{int(seconds // 60)} min"
    if seconds < 86400:
        return f"{int(seconds // 3600)} h"
    return f"{int(seconds // 86400)} d"


def clip(text: Any, limit: int) -> str:
    """`text` on one line, shortened with an ellipsis to at most `limit` characters (for tables and the panel)."""
    one_line = " ".join(str(text or "").split())
    return one_line if len(one_line) <= limit else one_line[:max(0, limit - 1)].rstrip() + "…"


def _int(value: Any) -> int:
    return int(value) if isinstance(value, (int, float)) and not isinstance(value, bool) and value >= 0 else 0


def _empty() -> Dict[str, Any]:
    return {"watched": [], "sightings": []}


def _is_legacy(_raw: Any) -> bool:
    return False   # the file is new; nothing older to claim


def _sighting_from_raw(raw: Any) -> Optional[Sighting]:
    """A sighting read from the file, or None for a damaged entry (dropped rather than stopping the load)."""
    if not isinstance(raw, dict):
        return None
    commodity, station, system = raw.get("commodity"), raw.get("station"), raw.get("system")
    if not all(isinstance(v, str) and v.strip() for v in (commodity, station, system)):
        return None
    return Sighting(commodity.strip(), station.strip()[:MAX_NAME], system.strip()[:MAX_NAME], _int(raw.get("buy_price")),
                    _int(raw.get("sell_price")), _int(raw.get("stock")), _int(raw.get("demand")), str(raw.get("seen") or ""))


def _sighting_to_raw(s: Sighting) -> Dict[str, Any]:
    return {"commodity": s.commodity, "station": s.station, "system": s.system, "buy_price": s.buy_price,
            "sell_price": s.sell_price, "stock": s.stock, "demand": s.demand, "seen": s.seen}


def _place_key(station: str, system: str) -> str:
    return f"{station.strip().casefold()}|{system.strip().casefold()}"


class WatchBook:
    """The commander's watch list. Constructed empty; `load(plugin_dir)` once at start-up and `set_commander(cmdr)` whenever the
    commander is known or changes. Every change to the list or the sightings is written straight away."""

    def __init__(self, now: Callable[[], str] = _now) -> None:
        self._store = commander_data.new_store()
        self._plugin_dir: Optional[str] = None
        self._cmdr = ""
        self._now = now
        self._watched: List[str] = []
        self._sightings: List[Sighting] = []
        self._lookups: Dict[str, Lookup] = {}     # canonical commodity name -> the last Spansh answer (memory only)
        self._listeners: List[Callable[[], None]] = []

    # --- loading and saving --------------------------------------------------------------------------------------

    def load(self, plugin_dir: str) -> None:
        self._plugin_dir = plugin_dir
        self._store = commander_data.read(os.path.join(plugin_dir, STATE_FILENAME), _is_legacy)
        self._reload()

    def set_commander(self, cmdr: str) -> bool:
        """True when this changed whose list is showing."""
        cmdr = str(cmdr or "").strip()
        if not cmdr or commander_data.key_for(cmdr) == commander_data.key_for(self._cmdr):
            return False
        self._cmdr = cmdr
        self._lookups = {}
        self._reload()
        return True

    def _reload(self) -> None:
        self._watched, self._sightings = [], []
        if self._cmdr:
            payload = commander_data.payload_for(self._store, self._cmdr, _empty)
            if isinstance(payload, dict):
                for raw in payload.get("watched") if isinstance(payload.get("watched"), list) else []:
                    name = trade_commodities.resolve(raw) if isinstance(raw, str) else None
                    if name and name not in self._watched and len(self._watched) < MAX_WATCHED:
                        self._watched.append(name)
                raw_seen = payload.get("sightings") if isinstance(payload.get("sightings"), list) else []
                self._sightings = [s for s in (_sighting_from_raw(r) for r in raw_seen)
                                   if s is not None and s.commodity in self._watched]
        self._changed()

    def _save(self) -> None:
        if not self._cmdr or self._plugin_dir is None:
            return
        commander_data.put(self._store, self._cmdr, {"watched": list(self._watched),
                                                     "sightings": [_sighting_to_raw(s) for s in self._sightings]})
        commander_data.write(os.path.join(self._plugin_dir, STATE_FILENAME), self._store)

    def add_listener(self, callback: Callable[[], None]) -> None:
        self._listeners.append(callback)

    def remove_listener(self, callback: Callable[[], None]) -> None:
        if callback in self._listeners:
            self._listeners.remove(callback)

    def _changed(self) -> None:
        for callback in list(self._listeners):
            try:
                callback()
            except Exception:   # a listener (a window that has gone) must never stop a save
                logger.debug("Watch list listener failed", exc_info=True)

    # --- reading ---------------------------------------------------------------------------------------------------

    @property
    def commander(self) -> str:
        return self._cmdr

    @property
    def ready(self) -> bool:
        """Commodities can be watched: a commander is known."""
        return bool(self._cmdr)

    def watched(self) -> List[str]:
        """The watched commodities (the game's names), in the order they were added."""
        return list(self._watched)

    def count(self) -> int:
        return len(self._watched)

    def sightings(self, commodity: str) -> List[Sighting]:
        """Where `commodity` was seen at a market, newest first."""
        return sorted((s for s in self._sightings if s.commodity == commodity), key=lambda s: s.seen, reverse=True)

    def lookup(self, commodity: str) -> Optional[Lookup]:
        return self._lookups.get(canonical_name(commodity))

    def best_buy(self, commodity: str) -> Optional[Quote]:
        """The cheapest price to buy `commodity` at, among the markets seen and the last Spansh answer; None if nothing is in stock."""
        quotes = [Quote(s.buy_price, s.stock, s.station, s.system, SEEN, s.seen)
                  for s in self._sightings if s.commodity == commodity and s.buy_price > 0 and s.stock > 0]
        found = self.lookup(commodity)
        if found is not None:
            quotes.extend(found.buys)
        return min(quotes, key=lambda q: (q.price, -_epoch_or_zero(q.when)), default=None)

    def best_sell(self, commodity: str) -> Optional[Quote]:
        """The dearest price to sell `commodity` at, among the markets seen and the last Spansh answer; None if nobody wants it."""
        quotes = [Quote(s.sell_price, s.demand, s.station, s.system, SEEN, s.seen)
                  for s in self._sightings if s.commodity == commodity and s.sell_price > 0 and s.demand > 0]
        found = self.lookup(commodity)
        if found is not None:
            quotes.extend(found.sells)
        return max(quotes, key=lambda q: (q.price, _epoch_or_zero(q.when)), default=None)

    # --- changing --------------------------------------------------------------------------------------------------

    def add(self, text: Any) -> str:
        """Start watching a commodity, typed as the game or Spansh names it (or its journal symbol). Returns the game's name."""
        if not self.ready:
            raise WatchError("The watch list is kept per commander and no commander is known yet. Log in first.")
        name = trade_commodities.resolve(str(text or ""))
        if not name:
            raise WatchError(f"'{clip(text, 40)}' is not a commodity I know. Pick one from the suggestions.")
        if name in self._watched:
            raise WatchError(f"{name} is already on the list.")
        if len(self._watched) >= MAX_WATCHED:
            raise WatchError(f"There is room for {MAX_WATCHED} commodities. Remove one before adding another.")
        self._watched.append(name)
        self._save()
        self._changed()
        return name

    def remove(self, commodity: str) -> bool:
        if commodity not in self._watched:
            return False
        self._watched.remove(commodity)
        self._sightings = [s for s in self._sightings if s.commodity != commodity]
        self._lookups.pop(canonical_name(commodity), None)
        self._save()
        self._changed()
        return True

    def record_market(self, station: str, system: str, market: Mapping[str, MarketItem]) -> int:
        """Keep the prices of every watched commodity this market trades (what `Market.json` said just now). Returns how many were
        kept; a market that trades none of them changes nothing."""
        station, system = str(station or "").strip()[:MAX_NAME], str(system or "").strip()[:MAX_NAME]
        if not (self.ready and station and system and self._watched):
            return 0
        kept, stamp = 0, self._now()
        for name in self._watched:
            item = market.get(canonical_name(name))
            if item is None or not (item.buy_price > 0 or item.sell_price > 0):
                continue
            place = _place_key(station, system)
            self._sightings = [s for s in self._sightings if not (s.commodity == name and _place_key(s.station, s.system) == place)]
            self._sightings.append(Sighting(name, station, system, item.buy_price, item.sell_price, item.stock, item.demand, stamp))
            self._trim(name)
            kept += 1
        if kept:
            self._save()
            self._changed()
        return kept

    def _trim(self, commodity: str) -> None:
        mine = self.sightings(commodity)
        for old in mine[MAX_SIGHTINGS:]:
            self._sightings.remove(old)

    def set_lookups(self, found: Mapping[str, Lookup]) -> None:
        """Replace the Spansh answers for these commodities (keyed by the game's name)."""
        for name, result in found.items():
            if name in self._watched:
                self._lookups[canonical_name(name)] = result
        self._changed()


def _epoch_or_zero(stamp: str) -> float:
    return _epoch(stamp) or 0.0
