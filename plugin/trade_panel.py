"""
Trade mode's feature-module entry point (`PANEL_PLACEMENT = "trade"`): the panel
chrome (page nav, one text body, a small button row), the Settings tab, and the
journal dispatch. Three pages, in trade_pages.PAGE_ORDER:

- Session: what you bought and sold since logging in (trade_ledger.py), the hold,
  and what the docked station would pay for it (trade_market.py). Works offline.
- Routes: the most profitable routes from where you are, from Spansh's trade-route
  planner (trade_spansh_client.py). Needs the lookups turned on in Settings.
- Market: where to sell what you are carrying, and a button for the best-price
  finder Mining mode already has (it works for any commodity).

Network calls are opt-in (off by default, like Mining's Spansh finders) and only
happen when you press a button. They run on a background thread; the panel polls
the finished job from the Tk thread, so no widget is touched off-thread.

Sizing (EDMC's window follows the widest row of every plugin): the body is a single
panelkit.wrap_label with every station/system/commodity name clipped, and the button
row is fixed small buttons - nothing here can widen the window.
"""
from __future__ import annotations

import logging
import os
import queue
import re
import threading
import time
import tkinter as tk
from typing import Any, Callable, Dict, List, Optional

import myNotebook as nb
from config import appname, config

from . import inventory_names
from . import mining_price_finder_dialog as price_finder_dialog
from . import mining_spansh_client as spansh_prices
from . import panelkit
from . import trade_ledger as ledger_mod
from . import trade_market as market_mod
from . import trade_carrier
from . import trade_commodities
from . import trade_pages
from . import trade_prices
from . import trade_ship
from . import trade_spansh_client as spansh_routes
from .trade_commodity_entry import CommodityEntry

plugin_name = os.path.basename(os.path.dirname(__file__))
logger = logging.getLogger(f"{appname}.{plugin_name}")

PANEL_PLACEMENT = "trade"

_CFG_LOOKUPS_ENABLED = "wntb_trade_lookups_enabled"
_CFG_MAX_HOPS = "wntb_trade_max_hops"
_CFG_MAX_ARRIVAL_LS = "wntb_trade_max_arrival_ls"
_CFG_LARGE_PAD = "wntb_trade_large_pad"
_CFG_JUMP_RANGE = "wntb_trade_jump_range_override"
_CFG_CURRENT_PAGE = "wntb_trade_current_page"
_CFG_NEAR_RADIUS = "wntb_trade_near_radius_ly"
_CFG_CARRIERS = "wntb_trade_include_carriers"
_CFG_COMMANDERS = "wntb_trade_commanders"  # commanders seen, "|"-separated
_CFG_SHIP_PAD = "wntb_trade_ship_pad_override"  # "" = work it out from the ship

_DEFAULT_MAX_HOPS = 3
_DEFAULT_MAX_ARRIVAL_LS = 5000
_FALLBACK_JUMP_RANGE_LY = 30.0
_DEFAULT_NEAR_RADIUS_LY = 100
_SELL_FETCH = 20   # stations asked for; ranked for your load, then the top few shown
_SELL_FETCH_PAD_FILTERED = 40  # pads are filtered after the search, so ask for more
_SELL_SHOWN = 3
_CARRIERS_SHOWN = 2
_ROUTES_SHOWN = 4  # hops
_CARGO_LINES = 4
_NAME_MAX = 34  # clip station / system / commodity names; the body also wraps to the panel width
_PERSIST_EVERY_S = 30.0
_POLL_MS = 500


def _clip(text: Any, limit: int = _NAME_MAX) -> str:
    value = str(text)
    return value if len(value) <= limit else value[: limit - 1] + "…"


def _cfg_int(key: str, default: int, low: int, high: int) -> int:
    try:
        return max(low, min(high, int(config.get_int(key, default=default))))
    except (TypeError, ValueError):
        return default


def lookups_enabled() -> bool:
    return config.get_bool(_CFG_LOOKUPS_ENABLED, default=False)


def _current_logfile() -> Optional[str]:
    try:
        from monitor import monitor  # EDMC's own module; absent in unit tests
    except ImportError:
        return None
    logfile = getattr(monitor, "logfile", None)
    return str(logfile) if logfile else None


def _journal_dir() -> str:
    getter = getattr(config, "get_str", None) or config.get  # type: ignore[attr-defined]
    return getter("journaldir") or getattr(config, "default_journal_dir", "") or ""


class _Job:
    """One background lookup. The worker only fills in `result`/`error` and sets
    `done`; the Tk thread reads them."""

    def __init__(self, kind: str, work: Callable[[threading.Event], Any]) -> None:
        self.kind = kind
        self.started = time.monotonic()
        self.cancel = threading.Event()
        self.done = False
        self.result: Any = None
        self.error: Optional[str] = None
        self._work = work
        threading.Thread(target=self._run, name=f"WNTB-trade-{kind}", daemon=True).start()

    def _run(self) -> None:
        try:
            self.result = self._work(self.cancel)
        except spansh_routes.RouteSearchError as err:
            self.error = str(err)
        except Exception:
            logger.exception("Trade %s lookup failed", self.kind)
            self.error = "Lookup failed - check your connection and try again (see the EDMC log)."
        self.done = True


class TradePanelController:
    def __init__(self) -> None:
        self._plugin_dir: Optional[str] = None
        self._ledger: Optional[Dict[str, Any]] = None
        self._carrier = trade_carrier.CarrierTracker()  # each commander's fleet / squadron carrier cargo space
        self._cmdr = ""
        self._backfill: "queue.Queue[trade_carrier.CarrierTracker]" = queue.Queue()
        self._last_saved = 0.0

        # What the journal has told us.
        self._system: Optional[str] = None
        self._station: Optional[str] = None          # where we are docked now
        self._home_station: Optional[str] = None      # last station we docked at (route start)
        self._home_system: Optional[str] = None
        self._cargo: Dict[str, int] = {}
        self._capacity = 0
        self._ship: Optional[str] = None  # journal ship name from Loadout, e.g. 'cobramkiii'
        self._credits = 0
        self._jump_range = 0.0
        self._market: Dict[str, market_mod.MarketItem] = {}
        self._market_station: Optional[str] = None
        self._names: Dict[str, str] = {}  # canonical commodity name -> the game's display name

        # Lookup results (text lines kept until the next search) and the running job.
        self._route_lines: List[str] = []
        self._next_system: Optional[str] = None
        self._sell: Dict[str, List[trade_prices.Offer]] = {}   # scope ("near" / "galaxy") -> ranked offers
        self._sell_for: Optional[tuple] = None                  # (commodity, tonnes) those offers were ranked for
        self._sell_error: Optional[str] = None
        self._job: Optional[_Job] = None

        self._page = config.get_str(_CFG_CURRENT_PAGE) or trade_pages.PAGE_ORDER[0]
        if self._page not in trade_pages.PAGE_ORDER:
            self._page = trade_pages.PAGE_ORDER[0]

        # Widgets
        self._parent: Optional[tk.Frame] = None
        self._page_label: Optional[tk.Label] = None
        self._body: Optional[tk.Label] = None
        self._button_a: Optional[tk.Button] = None
        self._button_b: Optional[tk.Button] = None
        self._button_c: Optional[tk.Button] = None
        self._search_row: Optional[tk.Frame] = None
        self._commodity_entry: Optional[CommodityEntry] = None

        # Settings variables
        self._lookups_var: Optional[tk.BooleanVar] = None
        self._hops_var: Optional[tk.StringVar] = None
        self._arrival_var: Optional[tk.StringVar] = None
        self._pad_var: Optional[tk.BooleanVar] = None
        self._range_var: Optional[tk.StringVar] = None
        self._near_var: Optional[tk.StringVar] = None
        self._carriers_var: Optional[tk.BooleanVar] = None
        self._carrier_mode_vars: Dict[str, tk.StringVar] = {}  # commander -> their carrier choice
        self._pad_override_var: Optional[tk.StringVar] = None

    # --- lifecycle -----------------------------------------------------------

    def start(self, plugin_dir: str) -> None:
        self._plugin_dir = plugin_dir
        self._ledger = ledger_mod.load_ledger(plugin_dir)
        self._carrier.records = trade_carrier.load_all(plugin_dir)
        threading.Thread(target=self._read_carrier_history, name="WNTB-trade-carrier", daemon=True).start()

    def _read_carrier_history(self) -> None:
        """Worker thread: find each commander's last carrier baseline in the recent journals. Hands the
        result over through a queue; the Tk thread merges it (`_merge_carrier_history`)."""
        try:
            self._backfill.put(trade_carrier.backfill_tracker(_journal_dir()))
        except Exception:
            logger.exception("Could not read fleet carrier history from the journal")

    def _merge_carrier_history(self) -> None:
        try:
            found = self._backfill.get_nowait()
        except queue.Empty:
            return
        if not self._carrier.dock_state()[0]:
            self._carrier.set_dock(*found.dock_state())  # started while docked: carry on from where the journal left off
        if trade_carrier.merge(self._carrier.records, found.records):
            if self._plugin_dir is not None:
                trade_carrier.save_all(self._plugin_dir, self._carrier.records)
            self._refresh()

    def stop(self) -> None:
        if self._job is not None:
            self._job.cancel.set()
        self._save(force=True)

    def _save(self, force: bool = False) -> None:
        if self._plugin_dir is None or self._ledger is None:
            return
        if force or time.monotonic() - self._last_saved >= _PERSIST_EVERY_S:
            ledger_mod.save_ledger(self._plugin_dir, self._ledger)
            self._last_saved = time.monotonic()

    # --- journal -------------------------------------------------------------

    def handle_event(
        self, entry: Dict[str, Any], cmdr: str, system: Optional[str], station: Optional[str], state: Dict[str, Any],
    ) -> None:
        event = entry.get("event")
        if cmdr:
            self._cmdr = cmdr
            self._carrier.set_cmdr(cmdr)
            self._remember_commander(cmdr)
        self._merge_carrier_history()
        if system:
            self._system = system
        self._station = station or None
        if isinstance(state, dict):
            cargo = state.get("Cargo")
            if isinstance(cargo, dict):
                self._cargo = {str(k): int(v) for k, v in cargo.items() if isinstance(v, (int, float)) and v > 0}
            capacity = state.get("CargoCapacity")
            if isinstance(capacity, (int, float)):
                self._capacity = int(capacity)
            if not self._ship and state.get("ShipType"):
                self._ship = str(state["ShipType"])
            credits = state.get("Credits")
            if isinstance(credits, (int, float)):
                self._credits = int(credits)

        new_session = False
        if event in ("LoadGame", "StartUp"):
            self._ledger, continued = ledger_mod.sync_ledger(self._ledger, cmdr, _current_logfile())
            new_session = not continued
        if self._ledger is None:
            self._ledger = ledger_mod.new_ledger(cmdr, _current_logfile())

        self._track_carrier(event, entry)

        if event == "Docked":
            self._home_station = entry.get("StationName") or self._home_station
            self._home_system = entry.get("StarSystem") or self._home_system
        elif event == "Loadout":
            if entry.get("Ship"):
                self._ship = str(entry["Ship"])
            jump = entry.get("MaxJumpRange")
            if isinstance(jump, (int, float)) and jump > 0:
                self._jump_range = float(jump)
        elif event == "Market":
            self._market = market_mod.read_market_file(_journal_dir())
            self._names.update({key: item.name for key, item in self._market.items()})
            self._market_station = entry.get("StationName") or self._station
        elif event in ("Undocked", "Location") and not self._station:
            self._market, self._market_station = {}, None

        if event in ("MarketBuy", "MarketSell") and entry.get("Type") and entry.get("Type_Localised"):
            self._names[market_mod.canonical_name(entry["Type"])] = str(entry["Type_Localised"])
        changed = ledger_mod.apply_trade_event(self._ledger, entry)
        if new_session:
            self._save(force=True)
        elif changed:
            self._save()
        if self._parent is not None:
            self._refresh()

    def _track_carrier(self, event: Optional[str], entry: Dict[str, Any]) -> None:
        """Keep each carrier's cargo space up to date. A commander without a carrier never produces a
        record, and what is shown follows their Settings choice."""
        if self._carrier.feed(entry) and self._plugin_dir is not None:
            trade_carrier.save_all(self._plugin_dir, self._carrier.records)

    # --- which carriers each commander has (Settings) ----------------------------------------------------

    @staticmethod
    def _carrier_cfg_key(cmdr: str) -> str:
        return "wntb_trade_carriers_" + re.sub(r"[^a-z0-9]", "", trade_carrier.key_for(cmdr))

    def _carrier_mode(self, cmdr: str) -> str:
        mode = (config.get_str(self._carrier_cfg_key(cmdr)) or trade_carrier.AUTO).lower()
        return mode if mode in trade_carrier.MODES else trade_carrier.AUTO

    @staticmethod
    def _known_commanders() -> List[str]:
        return [name for name in (config.get_str(_CFG_COMMANDERS) or "").split("|") if name]

    def _remember_commander(self, cmdr: str) -> None:
        """Keep the list of commanders seen, so Settings can offer a carrier choice for each (you can
        only be asked about commanders WNTB has met)."""
        known = self._known_commanders()
        if trade_carrier.key_for(cmdr) not in {trade_carrier.key_for(n) for n in known}:
            config.set(_CFG_COMMANDERS, "|".join(known + [cmdr.replace("|", "")]))

    # --- panel chrome ----------------------------------------------------------

    def build_panel(self, parent: tk.Frame) -> None:
        parent.columnconfigure(0, weight=1)
        self._parent = parent

        nav = tk.Frame(parent)
        nav.grid(row=0, column=0, columnspan=3, sticky="ew")
        panelkit.nav_arrow(nav, -1, lambda: self._step_page(-1)).pack(side=tk.LEFT)
        panelkit.nav_arrow(nav, 1, lambda: self._step_page(1)).pack(side=tk.RIGHT)
        self._page_label = tk.Label(nav, anchor=tk.CENTER)
        self._page_label.pack(side=tk.LEFT, fill=tk.X, expand=True)

        self._body = panelkit.wrap_label(parent, text="", anchor="w")
        self._body.grid(row=1, column=0, columnspan=3, sticky="w", pady=(2, 2))

        self._search_row = tk.Frame(parent)
        self._search_row.grid(row=2, column=0, columnspan=3, sticky="w", pady=(0, 2))
        tk.Label(self._search_row, text="Commodity:").pack(side=tk.LEFT, padx=(0, 4))
        self._commodity_entry = CommodityEntry(self._search_row, self._preferred_commodities,
                                               on_submit=lambda: self._find_sell_prices("near"))
        self._commodity_entry.pack(side=tk.LEFT)

        buttons = tk.Frame(parent)
        buttons.grid(row=3, column=0, columnspan=3, sticky="w")
        self._button_a = tk.Button(buttons, text="")
        self._button_a.pack(side=tk.LEFT)
        self._button_b = tk.Button(buttons, text="")
        self._button_b.pack(side=tk.LEFT, padx=(6, 0))
        self._button_c = tk.Button(buttons, text="")
        self._button_c.pack(side=tk.LEFT, padx=(6, 0))

        self._refresh()
        parent.after(2000, self._poll_carrier_history)

    def _poll_carrier_history(self) -> None:
        """The journal read takes a moment at startup; pick its result up once it is ready."""
        if not self._alive():
            return
        self._merge_carrier_history()
        if self._backfill.empty() and self._backfill_thread_done():
            return
        self._parent.after(2000, self._poll_carrier_history)  # type: ignore[union-attr]

    def _backfill_thread_done(self) -> bool:
        return not any(t.name == "WNTB-trade-carrier" and t.is_alive() for t in threading.enumerate())

    def _step_page(self, direction: int) -> None:
        order = trade_pages.PAGE_ORDER
        self._page = order[(order.index(self._page) + direction) % len(order)]
        config.set(_CFG_CURRENT_PAGE, self._page)
        self._refresh()

    def _alive(self) -> bool:
        return self._parent is not None and bool(self._parent.winfo_exists())

    # --- rendering ----------------------------------------------------------------

    def _refresh(self) -> None:
        if not self._alive() or self._body is None or self._page_label is None:
            return
        index = trade_pages.PAGE_ORDER.index(self._page) + 1
        self._page_label.configure(text=f"{self._page} ({index}/{len(trade_pages.PAGE_ORDER)})")
        busy = self._job is not None and not self._job.done
        if self._page == trade_pages.SESSION:
            lines = self._session_lines()
            self._set_buttons(("Reset", self._reset_ledger, True), None, None)
        elif self._page == trade_pages.ROUTES:
            lines = self._routes_lines(busy)
            self._set_buttons(
                ("Cancel" if busy else "Find routes", self._cancel_job if busy else self._find_routes,
                 busy or lookups_enabled()),
                ("Copy next system", self._copy_next_system, bool(self._next_system) and not busy), None)
        else:
            lines = self._market_lines(busy)
            can_search = lookups_enabled() and not busy
            self._set_buttons(
                ("Cancel" if busy else "Near me", self._cancel_job if busy else lambda: self._find_sell_prices("near"),
                 busy or can_search),
                ("Galaxy", lambda: self._find_sell_prices("galaxy"), can_search),
                ("Price…", self._open_price_finder, lookups_enabled() and not busy))
        self._body.configure(text="\n".join(lines))
        if self._search_row is not None:
            if self._page == trade_pages.MARKET and lookups_enabled():
                self._search_row.grid()
            else:
                self._search_row.grid_remove()

    def _set_buttons(self, first, second, third) -> None:
        # Unpack all, then pack in order, so the left-to-right order can never swap.
        for button in (self._button_a, self._button_b, self._button_c):
            if button is not None:
                button.pack_forget()
        for button, spec, padx in ((self._button_a, first, (0, 0)), (self._button_b, second, (6, 0)),
                                   (self._button_c, third, (6, 0))):
            if button is None or spec is None:
                continue
            text, command, enabled = spec
            button.configure(text=text, command=command, state=tk.NORMAL if enabled else tk.DISABLED)
            button.pack(side=tk.LEFT, padx=padx)

    def _session_lines(self) -> List[str]:
        lines = ledger_mod.summary_lines(self._ledger)
        lines.append("")
        lines.extend(self._hold_lines())
        carrier = trade_carrier.cargo_lines(self._carrier.records.get(trade_carrier.key_for(self._cmdr)),
                                          self._carrier_mode(self._cmdr))
        if carrier:
            lines.append("")
            lines.extend(carrier)
        return lines

    def _display(self, name: str) -> str:
        """The game's name for a cargo item: learned from market events, else the shared name table."""
        return (self._names.get(market_mod.canonical_name(name)) or trade_commodities.resolve(name)
                or inventory_names.display_name(name))

    def _ship_pad(self) -> Optional[str]:
        """The pad size to plan for: the Settings override if set, else worked out from the ship."""
        override = (config.get_str(_CFG_SHIP_PAD) or "").strip().lower()
        if override in (trade_ship.SMALL, trade_ship.MEDIUM, trade_ship.LARGE):
            return override
        return trade_ship.pad_size(self._ship)

    def _ship_line(self) -> str:
        name = trade_ship.ship_display_name(self._ship) if self._ship else "Ship unknown"
        return f"Ship: {_clip(name)} ({trade_ship.label(self._ship_pad())})"

    def _hold_lines(self) -> List[str]:
        used = sum(self._cargo.values())
        if not self._capacity and not used:
            return [self._ship_line(), "Hold: empty"]
        head = (f"Hold: {used:,}/{self._capacity:,} t ({max(0, self._capacity - used):,} free)"
                if self._capacity else f"Hold: {used:,} t")
        value = market_mod.cargo_value(self._cargo, self._market) if self._market else None
        if value is not None:
            head += f" - worth {value:,} cr at {_clip(self._market_station or 'this station')}"
        lines = [self._ship_line(), head]
        for name, tonnes in sorted(self._cargo.items(), key=lambda item: -item[1])[:_CARGO_LINES]:
            item = self._market.get(market_mod.canonical_name(name))
            price = f" @ {item.sell_price:,} cr" if item and item.sell_price > 0 else ""
            lines.append(f"  {_clip(self._display(name))}: {tonnes:,} t{price}")
        if len(self._cargo) > _CARGO_LINES:
            lines.append(f"  +{len(self._cargo) - _CARGO_LINES} more")
        return lines

    def _lookups_off_lines(self) -> List[str]:
        return ["Spansh lookups are off.", "Turn them on in Settings > WNTB > Trade."]

    def _route_start(self) -> Optional[tuple[str, str]]:
        """(system, station) a route starts from: where we are docked, else the last place we docked."""
        if self._station and self._system:
            return self._system, self._station
        if self._home_station and self._home_system:
            return self._home_system, self._home_station
        return None

    def _jump_range_ly(self) -> float:
        override = config.get_str(_CFG_JUMP_RANGE) or ""
        try:
            if override and float(override) > 0:
                return float(override)
        except ValueError:
            pass
        return self._jump_range or _FALLBACK_JUMP_RANGE_LY

    def _routes_lines(self, busy: bool) -> List[str]:
        if not lookups_enabled():
            return self._lookups_off_lines()
        if busy and self._job is not None:
            return [f"Asking Spansh for routes... {int(time.monotonic() - self._job.started)} s",
                    "This can take a minute or two."]
        if self._route_lines:
            return self._route_lines
        start = self._route_start()
        if start is None:
            return ["Dock at a station once so WNTB knows where to start,", "then press Find routes."]
        return [f"Start: {_clip(start[1])} ({_clip(start[0])})", self._ship_line(),
                f"Cargo {self._capacity or '?'} t, jump range {self._jump_range_ly():g} ly",
                f"Budget {self._credits:,} cr" if self._credits else "Budget: unknown",
                "Press Find routes."]

    def _market_lines(self, busy: bool) -> List[str]:
        if not lookups_enabled():
            return self._lookups_off_lines()
        if busy and self._job is not None:
            return [f"Asking Spansh... {int(time.monotonic() - self._job.started)} s"]
        if self._sell_error:
            return [self._sell_error]
        if self._sell and self._sell_for:
            return self._sell_result_lines()
        target = self._search_target()
        lines = [self._ship_line()]
        if target is None:
            lines += ["Type a commodity above (suggestions appear as you type),",
                      "or load cargo and it is searched for you."]
        else:
            name, tonnes, _known = target
            lines.append(f"Will search: {_clip(name)} ({tonnes:,} t)")
        lines += [f"Near me: best sale within {self._near_radius()} ly.", "Galaxy: best sale anywhere."]
        return lines

    def _carried(self) -> Dict[str, int]:
        """Cargo by the name Spansh knows (falls back to the game's name for anything unlisted)."""
        carried: Dict[str, int] = {}
        for raw, tonnes in self._cargo.items():
            name = trade_commodities.resolve(raw) or self._display(raw)
            carried[name] = carried.get(name, 0) + tonnes
        return carried

    def _preferred_commodities(self) -> List[str]:
        """What to list first in the search box: what you carry, then what this station buys."""
        names = [name for name, _t in sorted(self._carried().items(), key=lambda item: -item[1])]
        names += [item.name for item in self._market.values() if item.sell_price > 0]
        return names

    def _search_target(self) -> Optional[tuple]:
        """(commodity, tonnes to value the sale for, recognised) from the search box, else your largest
        load. Tonnes is what you carry of it, or a full hold when you carry none."""
        typed = self._commodity_entry.get() if self._commodity_entry is not None else ""
        carried = self._carried()
        if typed:
            name = trade_commodities.resolve(typed)
            shown = name or typed
            return shown, carried.get(shown) or self._capacity or 100, name is not None
        if carried:
            name, tonnes = max(carried.items(), key=lambda item: item[1])
            return name, tonnes, trade_commodities.resolve(name) is not None
        return None

    def _near_radius(self) -> int:
        return _cfg_int(_CFG_NEAR_RADIUS, _DEFAULT_NEAR_RADIUS_LY, 1, 100_000)

    def _sell_result_lines(self) -> List[str]:
        commodity, tonnes, pad = self._sell_for  # type: ignore[misc]
        lines = [f"Selling {tonnes:,} t {_clip(commodity)} ({trade_ship.label(pad)}):"]
        stations_by_scope: Dict[str, List[trade_prices.Offer]] = {}
        carriers_by_scope: Dict[str, List[trade_prices.Offer]] = {}
        for scope, title in (("near", f"Near me (within {self._near_radius()} ly)"), ("galaxy", "Anywhere in the galaxy")):
            if scope not in self._sell:
                continue
            stations, carriers = trade_prices.split_carriers(self._sell[scope])
            stations_by_scope[scope], carriers_by_scope[scope] = stations, carriers
            lines.append(title + ":")
            if not stations:
                lines.append("    no station wants it right now" + (" that you can dock at" if pad else ""))
            for offer in stations[:_SELL_SHOWN]:
                lines += self._offer_lines(offer, tonnes)
            if carriers:
                lines.append("  Fleet carriers (they can move):")
                for offer in carriers[:_CARRIERS_SHOWN]:
                    lines += self._offer_lines(offer, tonnes, indent="  ")
        verdict = trade_prices.verdict(stations_by_scope.get("near", []), stations_by_scope.get("galaxy", []))
        if verdict:
            lines.append(verdict)
        best_station = sorted((o for v in stations_by_scope.values() for o in v), key=lambda o: -o.revenue)
        best_carrier = sorted((o for v in carriers_by_scope.values() for o in v), key=lambda o: -o.revenue)
        note = trade_prices.carrier_note(best_station, best_carrier)
        if note:
            lines.append(note)
        return lines

    @staticmethod
    def _offer_lines(offer: trade_prices.Offer, tonnes: int, indent: str = "") -> List[str]:
        partial = f", only {offer.sellable_t:,} t wanted" if offer.sellable_t < tonnes else ""
        return [f"{indent}  {_clip(offer.station)} ({_clip(offer.system)})",
                f"{indent}    {offer.price:,} cr/t = {offer.revenue:,} cr, {offer.distance_ly:.1f} ly{partial}"]

    # --- actions ------------------------------------------------------------------------

    def _reset_ledger(self) -> None:
        self._ledger = ledger_mod.new_ledger("", _current_logfile())
        self._save(force=True)
        self._refresh()

    def _copy_next_system(self) -> None:
        if self._next_system and self._parent is not None:
            panelkit.copy_to_clipboard(self._parent, self._next_system)

    def _cancel_job(self) -> None:
        if self._job is not None:
            self._job.cancel.set()

    def _open_price_finder(self) -> None:
        if self._parent is None:
            return
        suggested = list(dict.fromkeys(self._preferred_commodities() + trade_commodities.SUGGESTIBLE))
        price_finder_dialog.open_price_finder_dialog(self._parent, suggested_commodities=suggested)

    def _find_routes(self) -> None:
        if self._job is not None and not self._job.done:
            return
        start = self._route_start()
        if start is None:
            self._route_lines = ["Dock at a station once so WNTB knows where to start."]
            self._refresh()
            return
        query = spansh_routes.RouteQuery(
            system=start[0], station=start[1], capital=self._credits or 1_000_000,
            cargo_capacity=self._capacity or 100, max_hops=_cfg_int(_CFG_MAX_HOPS, _DEFAULT_MAX_HOPS, 1, 10),
            max_hop_distance_ly=self._jump_range_ly(),
            max_arrival_ls=_cfg_int(_CFG_MAX_ARRIVAL_LS, _DEFAULT_MAX_ARRIVAL_LS, 1, 1_000_000),
            requires_large_pad=config.get_bool(_CFG_LARGE_PAD, default=False) or self._ship_pad() == trade_ship.LARGE,
        )
        self._route_lines, self._next_system = [], None
        self._start_job("routes", lambda cancel: spansh_routes.search_routes(query, cancel))

    def _find_sell_prices(self, scope: str) -> None:
        if not self._system or (self._job is not None and not self._job.done):
            return
        target = self._search_target()
        if target is None:
            self._sell_error = "Type a commodity to search for, or load some cargo."
            self._refresh()
            return
        display, tonnes, _known = target
        system = self._system
        radius = float(self._near_radius()) if scope == "near" else None
        carriers = config.get_bool(_CFG_CARRIERS, default=True)
        pad = self._ship_pad()
        fetch = _SELL_FETCH_PAD_FILTERED if pad else _SELL_FETCH

        def work(_cancel: threading.Event) -> Any:
            found = spansh_prices.search_best_price_stations(system, display, "Sell", radius, max_results=fetch)
            ranked = trade_prices.rank_offers(found, tonnes, include_carriers=carriers, ship_pad=pad)
            return scope, (display, tonnes, pad), ranked, bool(found)

        self._sell_error = None
        if self._sell_for != (display, tonnes, pad):
            self._sell = {}  # a different search: the other scope's answer no longer applies
        self._start_job("sell", work)

    def _start_job(self, kind: str, work: Callable[[threading.Event], Any]) -> None:
        self._job = _Job(kind, work)
        self._refresh()
        if self._parent is not None:
            self._parent.after(_POLL_MS, self._poll_job)

    def _poll_job(self) -> None:
        job = self._job
        if job is None or not self._alive():
            return
        if not job.done:
            self._refresh()  # keeps the elapsed-seconds counter moving
            self._parent.after(_POLL_MS, self._poll_job)  # type: ignore[union-attr]
            return
        if job.kind == "routes":
            self._finish_routes(job)
        else:
            self._finish_sell(job)
        self._job = None
        self._refresh()

    def _finish_routes(self, job: _Job) -> None:
        if job.error:
            self._route_lines = [job.error]
            return
        hops: List[spansh_routes.Hop] = job.result or []
        if not hops:
            self._route_lines = ["No profitable route found.", "Try more hops, a longer range, or a bigger budget."]
            return
        total = sum(hop.profit for hop in hops)
        lines = [f"Route profit: {total:,} cr over {len(hops)} hop(s)"]
        for number, hop in enumerate(hops[:_ROUTES_SHOWN], start=1):
            lines.append(f"{number}. {_clip(hop.source_station)} > {_clip(hop.dest_station)}")
            lines.append(f"    {_clip(hop.dest_system)}, {hop.distance_ly:.1f} ly, {hop.dest_ls:,.0f} ls")
            if hop.cargo:
                best = max(hop.cargo, key=lambda c: c.total_profit)
                lines.append(f"    {_clip(best.name)} x{best.tonnes} t: +{hop.profit:,} cr")
        if len(hops) > _ROUTES_SHOWN:
            lines.append(f"  +{len(hops) - _ROUTES_SHOWN} more hop(s)")
        self._route_lines = lines
        self._next_system = hops[0].dest_system if hops[0].dest_system != "?" else None

    def _finish_sell(self, job: _Job) -> None:
        if job.error:
            self._sell_error = job.error
            return
        scope, key, offers, any_found = job.result
        if self._sell_for != key:
            self._sell = {}
        self._sell_for = key
        self._sell[scope] = offers
        if not any_found and not offers and not self._sell.get("galaxy" if scope == "near" else "near"):
            self._sell_error = (f"Spansh found no market buying {_clip(key[0])}. "
                                "Check the spelling, or pick a name from the suggestions.")

    # --- settings -----------------------------------------------------------------------------

    def build_settings(self, notebook: nb.Notebook) -> None:
        frame = nb.Frame(notebook)
        frame.columnconfigure(0, weight=1)
        notebook.add(frame, text="Trade")

        nb.Label(
            frame,
            text=(
                "Trade mode's Session page works offline from your journal. The Routes and Market pages ask "
                "Spansh (spansh.co.uk) for trade routes and prices when you press their buttons - a real "
                "outbound network call, so they are off until you turn them on here."
            ),
            wraplength=440, justify=tk.LEFT,
        ).grid(row=0, column=0, sticky=tk.W, padx=10, pady=(10, 6))

        self._lookups_var = tk.BooleanVar(value=lookups_enabled())
        nb.Checkbutton(frame, text="Enable Spansh trade lookups", variable=self._lookups_var).grid(
            row=1, column=0, sticky=tk.W, padx=10, pady=2)

        self._hops_var = tk.StringVar(value=str(_cfg_int(_CFG_MAX_HOPS, _DEFAULT_MAX_HOPS, 1, 10)))
        self._arrival_var = tk.StringVar(value=str(_cfg_int(_CFG_MAX_ARRIVAL_LS, _DEFAULT_MAX_ARRIVAL_LS, 1, 1_000_000)))
        self._range_var = tk.StringVar(value=config.get_str(_CFG_JUMP_RANGE) or "")
        self._pad_var = tk.BooleanVar(value=config.get_bool(_CFG_LARGE_PAD, default=False))
        self._near_var = tk.StringVar(value=str(self._near_radius()))
        self._carriers_var = tk.BooleanVar(value=config.get_bool(_CFG_CARRIERS, default=True))
        self._pad_override_var = tk.StringVar(value=(config.get_str(_CFG_SHIP_PAD) or "auto").lower())

        form = tk.Frame(frame)
        form.grid(row=2, column=0, sticky=tk.W, padx=10, pady=(6, 2))
        for row, (label, var) in enumerate((
                ("Route hops (1-10)", self._hops_var),
                ("Max distance from the star (ls)", self._arrival_var),
                ("Jump range override (ly, blank = use my ship's)", self._range_var),
                ("'Near me' price search radius (ly)", self._near_var))):
            nb.Label(form, text=label).grid(row=row, column=0, sticky=tk.W, pady=2)
            tk.Entry(form, textvariable=var, width=8).grid(row=row, column=1, sticky=tk.W, padx=(8, 0), pady=2)
        nb.Checkbutton(frame, text="Only stations with a large landing pad", variable=self._pad_var).grid(
            row=3, column=0, sticky=tk.W, padx=10, pady=2)
        nb.Checkbutton(frame, text="Show fleet carriers in price results (listed apart; they can jump away)",
                       variable=self._carriers_var).grid(row=4, column=0, sticky=tk.W, padx=10, pady=2)
        pad_row = tk.Frame(frame)
        pad_row.grid(row=6, column=0, sticky=tk.W, padx=10, pady=(6, 2))
        nb.Label(pad_row, text="Ship size (landing pad):").pack(side=tk.LEFT, padx=(0, 6))
        for value, text in (("auto", "From my ship"), ("small", "Small"), ("medium", "Medium"), ("large", "Large")):
            nb.Radiobutton(pad_row, text=text, variable=self._pad_override_var, value=value).pack(side=tk.LEFT, padx=(0, 6))
        nb.Label(
            frame,
            text=("Prices and routes leave out stations without a pad your ship fits. 'From my ship' reads your "
                  "ship from the game; pick a size only if it guesses wrong."),
            wraplength=440, justify=tk.LEFT,
        ).grid(row=7, column=0, sticky=tk.W, padx=10, pady=(0, 10))
        nb.Label(
            frame,
            text=("The ship's unladen jump range is used unless you override it; a full hold jumps shorter, so "
                  "lower the override if routes are too long for you. Budget and cargo size come from the game."),
            wraplength=440, justify=tk.LEFT,
        ).grid(row=5, column=0, sticky=tk.W, padx=10, pady=(4, 10))

        self._build_carrier_settings(frame, first_row=8)

    def _build_carrier_settings(self, frame: tk.Misc, first_row: int) -> None:
        """One choice per commander WNTB has met: which carriers they own. Auto shows whatever the journal
        has revealed; the rest show exactly what you pick (and nothing for None)."""
        nb.Label(
            frame,
            text=("Carriers: not every commander has a fleet carrier, and some have a squadron carrier too. "
                  "Pick what each commander owns and Trade > Session shows only those (Auto shows whatever WNTB "
                  "has seen in your journal)."),
            wraplength=440, justify=tk.LEFT,
        ).grid(row=first_row, column=0, sticky=tk.W, padx=10, pady=(6, 4))
        commanders = self._known_commanders()
        if self._cmdr and trade_carrier.key_for(self._cmdr) not in {trade_carrier.key_for(n) for n in commanders}:
            commanders.append(self._cmdr)
        self._carrier_mode_vars = {}
        if not commanders:
            nb.Label(frame, text="No commander seen yet - start the game and this will list them.",
                     wraplength=440, justify=tk.LEFT).grid(row=first_row + 1, column=0, sticky=tk.W, padx=10)
            return
        choices = ((trade_carrier.AUTO, "Auto"), (trade_carrier.NONE, "None"), (trade_carrier.FLEET_ONLY, "Fleet"),
                   (trade_carrier.SQUADRON_ONLY, "Squadron"), (trade_carrier.BOTH, "Both"))
        for offset, name in enumerate(commanders, start=1):
            row = tk.Frame(frame)
            row.grid(row=first_row + offset, column=0, sticky=tk.W, padx=10, pady=1)
            nb.Label(row, text=f"{_clip(name, 20)}:", width=22, anchor=tk.W).pack(side=tk.LEFT)
            var = tk.StringVar(value=self._carrier_mode(name))
            self._carrier_mode_vars[name] = var
            for value, text in choices:
                nb.Radiobutton(row, text=text, variable=var, value=value).pack(side=tk.LEFT, padx=(0, 4))

    def save_settings(self) -> None:
        if self._lookups_var is None:
            return
        config.set(_CFG_LOOKUPS_ENABLED, bool(self._lookups_var.get()))
        for name, var in self._carrier_mode_vars.items():
            config.set(self._carrier_cfg_key(name), var.get() if var.get() in trade_carrier.MODES else trade_carrier.AUTO)
        config.set(_CFG_LARGE_PAD, bool(self._pad_var.get()) if self._pad_var is not None else False)
        config.set(_CFG_CARRIERS, bool(self._carriers_var.get()) if self._carriers_var is not None else True)
        pad_choice = (self._pad_override_var.get() if self._pad_override_var is not None else "auto").lower()
        config.set(_CFG_SHIP_PAD, pad_choice if pad_choice in (trade_ship.SMALL, trade_ship.MEDIUM, trade_ship.LARGE) else "")
        for key, var, default, low, high in (
                (_CFG_MAX_HOPS, self._hops_var, _DEFAULT_MAX_HOPS, 1, 10),
                (_CFG_MAX_ARRIVAL_LS, self._arrival_var, _DEFAULT_MAX_ARRIVAL_LS, 1, 1_000_000),
                (_CFG_NEAR_RADIUS, self._near_var, _DEFAULT_NEAR_RADIUS_LY, 1, 100_000)):
            try:
                value = int((var.get() if var is not None else "").strip())
            except ValueError:
                value = default
            config.set(key, max(low, min(high, value)))
        jump = (self._range_var.get() if self._range_var is not None else "").strip()
        try:
            config.set(_CFG_JUMP_RANGE, jump if jump and float(jump) > 0 else "")
        except ValueError:
            config.set(_CFG_JUMP_RANGE, "")
        self._refresh()


controller = TradePanelController()


def start(plugin_dir: str) -> None:
    controller.start(plugin_dir)


def stop() -> None:
    controller.stop()


def build_panel(parent: tk.Frame) -> None:
    controller.build_panel(parent)


def build_settings(notebook: nb.Notebook) -> None:
    controller.build_settings(notebook)


def save_settings() -> None:
    controller.save_settings()


def handle_event(
    entry: Dict[str, Any], cmdr: str, system: Optional[str], station: Optional[str], state: Dict[str, Any],
) -> None:
    controller.handle_event(entry, cmdr, system, station, state)
