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
from tkinter import messagebox
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
from . import trade_history
from . import trade_history_window
from . import trade_commodities
from . import trade_pages
from . import trade_prices
from . import trade_ship
from . import trade_spansh_client as spansh_routes
from . import trade_stock
from .trade_blocks import Block, Columns, Heading, Item, Note, Pair
from .trade_view import BlockView
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
_CFG_GROUND = "wntb_trade_include_ground"  # ground (planetary) facilities in price results
_CFG_MARKET_SIDE = "wntb_trade_market_side"  # "sell" or "buy": which side of the market the search is for
_CFG_COMMANDERS = "wntb_trade_commanders"  # commanders seen, "|"-separated
_CFG_SHIP_PAD = "wntb_trade_ship_pad_override"  # "" = work it out from the ship

_DEFAULT_MAX_HOPS = 3
_CARRIER_STATION_TYPES = ("FleetCarrier", "SquadronCarrier")  # journal StationType values
_DEFAULT_MAX_ARRIVAL_LS = 5000
_FALLBACK_JUMP_RANGE_LY = 30.0
_DEFAULT_NEAR_RADIUS_LY = 100
_SELL_FETCH = 20   # stations asked for; ranked for your load, then the top few shown
_SELL_FETCH_PAD_FILTERED = 40  # pads are filtered after the search, so ask for more
# Fleet carriers are asked for separately, so they can't crowd stations out, and weighted 75% stations to
# 25% carriers: a third as many carriers are fetched as stations, and one carrier is shown for every three stations.
_CARRIER_FETCH_DIVISOR = 3
_CARRIER_FETCH_MIN = 5
_SELL_SHOWN = 3
_OFFER_COLUMNS = ("cr/t", "Total", "ly")
_CARRIERS_SHOWN = 1   # with _SELL_SHOWN = 3 stations: 75% stations, 25% carriers
_ROUTES_SHOWN = 4  # hops
_CARGO_LINES = 4
_NAME_MAX = 64  # a safety bound on station / system / commodity names; the view wraps anything long
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
        self._book = ledger_mod.LedgerBook()    # each commander's working session; lasts until they press Reset
        self._caught_up: set = set()            # commanders whose session was brought up to date from the journals this run
        self._stock = trade_stock.StockBook()  # bought-not-yet-sold cargo, per commander, across logins
        self._stock_saved = 0.0
        self._history = trade_history.HistoryBook()   # sessions saved on request (Save session)
        self._saved_marks: Dict[str, tuple] = {}      # session id -> how it looked when last saved
        self._save_message: Optional[str] = None      # shown at the top of the Session page for a few seconds
        self._route_label = ""                        # where the route search being run started from
        self._carrier = trade_carrier.CarrierTracker()  # each commander's fleet / squadron carrier cargo space
        self._cmdr = ""
        self._backfill: "queue.Queue[trade_carrier.CarrierTracker]" = queue.Queue()
        self._last_saved = 0.0

        # What the journal has told us.
        self._system: Optional[str] = None
        self._station: Optional[str] = None          # where we are docked now
        self._home_station: Optional[str] = None      # last station we docked at (route start); never a carrier
        self._carrier_names: set = set()              # fleet / squadron carriers docked at (not valid route starts)
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
        self._route_blocks: List[Block] = []
        self._next_system: Optional[str] = None
        self._sell: Dict[str, List[trade_prices.Offer]] = {}   # scope ("near" / "galaxy") -> ranked offers
        self._sell_for: Optional[tuple] = None                  # (commodity, tonnes, pad, side) those offers were ranked for
        side = (config.get_str(_CFG_MARKET_SIDE) or trade_prices.SELL).lower()
        self._side = side if side in (trade_prices.SELL, trade_prices.BUY) else trade_prices.SELL
        self._sell_error: Optional[str] = None
        self._pad_dropped: Dict[str, int] = {}                  # scope -> stations left out for pad size
        self._job: Optional[_Job] = None

        self._page = config.get_str(_CFG_CURRENT_PAGE) or trade_pages.PAGE_ORDER[0]
        if self._page not in trade_pages.PAGE_ORDER:
            self._page = trade_pages.PAGE_ORDER[0]

        # Widgets
        self._parent: Optional[tk.Frame] = None
        self._page_label: Optional[tk.Label] = None
        self._view: Optional[BlockView] = None
        self._button_a: Optional[tk.Button] = None
        self._button_b: Optional[tk.Button] = None
        self._button_c: Optional[tk.Button] = None
        self._button_d: Optional[tk.Button] = None
        self._search_row: Optional[tk.Frame] = None
        self._side_row: Optional[tk.Frame] = None
        self._side_buttons: Dict[str, tk.Button] = {}
        self._side_off_colors: Optional[tuple] = None
        self._commodity_entry: Optional[CommodityEntry] = None

        # Settings variables
        self._lookups_var: Optional[tk.BooleanVar] = None
        self._hops_var: Optional[tk.StringVar] = None
        self._arrival_var: Optional[tk.StringVar] = None
        self._pad_var: Optional[tk.BooleanVar] = None
        self._range_var: Optional[tk.StringVar] = None
        self._near_var: Optional[tk.StringVar] = None
        self._carriers_var: Optional[tk.BooleanVar] = None
        self._ground_var: Optional[tk.BooleanVar] = None
        self._carrier_mode_vars: Dict[str, tk.StringVar] = {}  # commander -> their carrier choice
        self._pad_override_var: Optional[tk.StringVar] = None

    # --- lifecycle -----------------------------------------------------------

    def start(self, plugin_dir: str) -> None:
        self._plugin_dir = plugin_dir
        self._book = ledger_mod.load_book(plugin_dir)
        self._carrier.records = trade_carrier.load_all(plugin_dir)
        self._stock.books = trade_stock.load_all(plugin_dir)
        self._history.sessions = trade_history.load_all(plugin_dir)
        try:
            # Catch up on trades made while EDMC was closed, before any live event can arrive.
            trade_stock.backfill(self._stock, _journal_dir())
        except Exception:
            logger.exception("Could not read trade history from the journal")
        self._save_stock(force=True)
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
        trade_history_window.close()
        self._save(force=True)
        self._save_stock(force=True)

    def _save_stock(self, force: bool = False) -> None:
        if self._plugin_dir is None:
            return
        if force or time.monotonic() - self._stock_saved >= _PERSIST_EVERY_S:
            trade_stock.save_all(self._plugin_dir, self._stock.books)
            self._stock_saved = time.monotonic()

    @property
    def _ledger(self) -> Optional[Dict[str, Any]]:
        """The current commander's working session (None until a commander is known)."""
        return self._book.get(self._cmdr) if self._cmdr else None

    def _save(self, force: bool = False) -> None:
        if self._plugin_dir is None or not self._book.ledgers:
            return
        if force or time.monotonic() - self._last_saved >= _PERSIST_EVERY_S:
            ledger_mod.save_book(self._plugin_dir, self._book)
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
        if cmdr and (event in ("LoadGame", "StartUp") or self._ledger is None):
            # The commander's working session carries on across game logins, journal files and EDMC runs until they
            # press Reset; it is only created here if they have none. LoadGame carries the balance at login.
            opening = entry.get("Credits") if event == "LoadGame" else None
            _ledger, created = self._book.ensure(
                cmdr, _current_logfile(), started=str(entry.get("timestamp") or "") or None,
                credits=opening if isinstance(opening, int) else (self._credits or None))
            new_session = created
        key = trade_carrier.key_for(cmdr)
        if cmdr and event in ("StartUp", "LoadGame") and key not in self._caught_up and self._ledger is not None:
            # First sight of this commander since EDMC started: EDMC doesn't replay old events, and the game may have been
            # played while it was closed, so add whatever the journals hold since the session's last counted event.
            self._caught_up.add(key)
            added = ledger_mod.catch_up(self._ledger, cmdr, _journal_dir())
            if added:
                logger.info("Trade session caught up from the journals: %d event(s) added", added)
                new_session = True
        if self._ledger is None:
            return self._after_event()
        note_credits = entry.get("Credits") if event == "LoadGame" else None
        ledger_mod.note_start(self._ledger, str(entry.get("timestamp") or "") or None,
                              note_credits if isinstance(note_credits, int) else (self._credits or None))

        self._track_carrier(event, entry)

        if event == "Docked":
            if str(entry.get("StationType") or "") in _CARRIER_STATION_TYPES:
                # Spansh's route planner doesn't know fleet carriers ("Could not find station"), so they are
                # never a route start; remember the name so we skip it while we are docked there.
                self._carrier_names.add(str(entry.get("StationName") or ""))
            else:
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
        if event in ("MarketBuy", "MarketSell") and self._stock.feed(entry, self._cmdr):
            self._save_stock()
        counted = not ledger_mod.already_counted(self._ledger, entry)   # a caught-up session already has older events
        changed = ledger_mod.apply_trade_event(self._ledger, entry, (self._system, self._station)) if counted else False
        changed = (ledger_mod.note_jump(self._ledger, entry) if counted else False) or changed
        if new_session:
            self._save(force=True)
        elif changed:
            self._save()
        self._after_event()

    def _after_event(self) -> None:
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

        self._view = BlockView(parent)
        self._view.grid(row=4, column=0, columnspan=3, sticky="ew", pady=(4, 2))

        self._search_row = tk.Frame(parent)
        self._search_row.grid(row=1, column=0, columnspan=3, sticky="w", pady=(2, 2))
        tk.Label(self._search_row, text="Commodity:").pack(side=tk.LEFT, padx=(0, 4))
        self._commodity_entry = CommodityEntry(self._search_row, self._preferred_commodities,
                                               on_submit=lambda: self._find_prices("near"))
        self._commodity_entry.pack(side=tk.LEFT)

        # Which side of the market the search is for. Two toggle buttons (the same on/off look as the mode
        # buttons) rather than radio buttons, which EDMC's theme doesn't colour reliably.
        self._side_row = tk.Frame(parent)
        self._side_row.grid(row=2, column=0, columnspan=3, sticky="w", pady=(0, 2))
        tk.Label(self._side_row, text="I want to:").pack(side=tk.LEFT, padx=(0, 4))
        for value, text in ((trade_prices.SELL, "Sell"), (trade_prices.BUY, "Buy")):
            button = tk.Button(self._side_row, text=text, command=lambda v=value: self._set_side(v))
            button.pack(side=tk.LEFT, padx=(0, 6))
            self._side_buttons[value] = button
        self._side_off_colors = panelkit.capture_toggle_off_colors(self._side_buttons[trade_prices.SELL])
        self._paint_side_buttons()

        buttons = tk.Frame(parent)
        buttons.grid(row=3, column=0, columnspan=3, sticky="w")
        self._button_a = tk.Button(buttons, text="")
        self._button_a.pack(side=tk.LEFT)
        self._button_b = tk.Button(buttons, text="")
        self._button_b.pack(side=tk.LEFT, padx=(6, 0))
        self._button_c = tk.Button(buttons, text="")
        self._button_c.pack(side=tk.LEFT, padx=(6, 0))
        self._button_d = tk.Button(buttons, text="")
        self._button_d.pack(side=tk.LEFT, padx=(6, 0))

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
        if not self._alive() or self._view is None or self._page_label is None:
            return
        index = trade_pages.PAGE_ORDER.index(self._page) + 1
        self._page_label.configure(text=f"{self._page} ({index}/{len(trade_pages.PAGE_ORDER)})")
        busy = self._job is not None and not self._job.done
        if self._page == trade_pages.SESSION:
            blocks = self._session_blocks()
            self._set_buttons(("Reset", self._reset_ledger, True),
                              ("Clear stock", self._clear_stock, bool(self._stock.holdings(self._cmdr))),
                              ("Save session", self._save_session, trade_history.has_content(self._ledger)),
                              ("History", self._open_history, True))
        elif self._page == trade_pages.ROUTES:
            blocks = self._routes_blocks(busy)
            self._set_buttons(
                ("Cancel" if busy else "Find routes", self._cancel_job if busy else self._find_routes,
                 busy or lookups_enabled()),
                ("Copy next system", self._copy_next_system, bool(self._next_system) and not busy), None)
        else:
            blocks = self._market_blocks(busy)
            can_search = lookups_enabled() and not busy
            self._set_buttons(
                ("Cancel" if busy else "Near me", self._cancel_job if busy else lambda: self._find_prices("near"),
                 busy or can_search),
                ("Galaxy", lambda: self._find_prices("galaxy"), can_search),
                ("Price finder", self._open_price_finder, lookups_enabled() and not busy))
        self._view.show(blocks)
        for row in (self._search_row, self._side_row):
            if row is not None:
                if self._page == trade_pages.MARKET and lookups_enabled():
                    row.grid()
                else:
                    row.grid_remove()

    def _set_buttons(self, first, second, third, fourth=None) -> None:
        # Unpack all, then pack in order, so the left-to-right order can never swap.
        for button in (self._button_a, self._button_b, self._button_c, self._button_d):
            if button is not None:
                button.pack_forget()
        for button, spec, padx in ((self._button_a, first, (0, 0)), (self._button_b, second, (6, 0)),
                                   (self._button_c, third, (6, 0)), (self._button_d, fourth, (6, 0))):
            if button is None or spec is None:
                continue
            text, command, enabled = spec
            button.configure(text=text, command=command, state=tk.NORMAL if enabled else tk.DISABLED)
            button.pack(side=tk.LEFT, padx=padx)

    def _session_blocks(self) -> List[Block]:
        in_hold = {market_mod.canonical_name(name): tonnes for name, tonnes in self._cargo.items()}
        blocks: List[Block] = [Heading("This session")]
        if self._save_message:
            blocks.append(Note(self._save_message, strong=True))
        blocks += ledger_mod.summary_blocks(self._ledger)
        blocks += trade_stock.stock_blocks(self._stock.holdings(self._cmdr), in_hold,
                                           name_of=lambda holding: _clip(self._display(holding.key)))
        blocks += self._hold_blocks()
        blocks += trade_carrier.cargo_blocks(self._carrier.records.get(trade_carrier.key_for(self._cmdr)),
                                             self._carrier_mode(self._cmdr))
        return blocks

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

    def _ship_pairs(self) -> List[Block]:
        name = trade_ship.ship_display_name(self._ship) if self._ship else "Unknown"
        pad = self._ship_pad()
        return [Pair("Ship", _clip(name)), Pair("Landing pad", pad.capitalize() if pad else "Unknown")]

    def _hold_blocks(self) -> List[Block]:
        used = sum(self._cargo.values())
        blocks: List[Block] = [Heading("Ship and hold"), *self._ship_pairs()]
        if not self._capacity and not used:
            return blocks + [Pair("Hold", "empty")]
        blocks.append(Pair("Hold", f"{used:,} / {self._capacity:,} t ({max(0, self._capacity - used):,} free)"
                           if self._capacity else f"{used:,} t", bold=True))
        value = market_mod.cargo_value(self._cargo, self._market) if self._market else None
        if value is not None:
            blocks.append(Pair(f"Worth at {_clip(self._market_station or 'this station', 22)}", f"{value:,} cr"))
        if self._cargo:
            blocks.append(Columns(("Held", "Sells here")))
            for name, tonnes in sorted(self._cargo.items(), key=lambda item: -item[1])[:_CARGO_LINES]:
                market_item = self._market.get(market_mod.canonical_name(name))
                price = f"{market_item.sell_price:,} cr" if market_item and market_item.sell_price > 0 else ""
                blocks.append(Item(_clip(self._display(name)), (f"{tonnes:,} t", price)))
            if len(self._cargo) > _CARGO_LINES:
                blocks.append(Note(f"+{len(self._cargo) - _CARGO_LINES} more"))
        return blocks

    @staticmethod
    def _lookups_off_blocks(title: str) -> List[Block]:
        return [Heading(title), Note("Spansh lookups are off.", warn=True),
                Note("Turn them on in Settings > WNTB > Trade.")]

    def _route_start(self) -> Optional[tuple[str, str]]:
        """(system, station) a route starts from: where we are docked, else the last station we docked at.
        Fleet carriers are skipped: Spansh can't plan from one."""
        if self._station and self._system and self._station not in self._carrier_names:
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

    def _routes_blocks(self, busy: bool) -> List[Block]:
        if not lookups_enabled():
            return self._lookups_off_blocks("Routes")
        if busy and self._job is not None:
            return [Heading("Routes"), Note(f"Asking Spansh for routes... {int(time.monotonic() - self._job.started)} s"),
                    Note("This can take a minute or two.")]
        if self._route_blocks:
            return self._route_blocks
        start = self._route_start()
        if start is None:
            return [Heading("Routes"),
                    Note("Dock at a station once so WNTB knows where to start, then press Find routes.")]
        return [Heading("Next route"), Pair("Start", f"{_clip(start[1])} ({_clip(start[0])})"), *self._ship_pairs(),
                Pair("Cargo", f"{self._capacity or '?'} t"), Pair("Jump range", f"{self._jump_range_ly():g} ly"),
                Pair("Budget", f"{self._credits:,} cr" if self._credits else "unknown"),
                Note("Press Find routes.")]

    def _set_side(self, side: str) -> None:
        """Switch between looking for a place to sell and a place to buy. The results shown belong to one side,
        so they are cleared."""
        if side == self._side:
            return
        self._side = side
        config.set(_CFG_MARKET_SIDE, side)
        self._sell, self._sell_for, self._sell_error, self._pad_dropped = {}, None, None, {}
        self._paint_side_buttons()
        self._refresh()

    def _paint_side_buttons(self) -> None:
        if self._side_off_colors is None:
            return
        for value, button in self._side_buttons.items():
            panelkit.apply_toggle_button_state(button, value == self._side, self._side_off_colors)

    def _market_blocks(self, busy: bool) -> List[Block]:
        if not lookups_enabled():
            return self._lookups_off_blocks("Market")
        if busy and self._job is not None:
            return [Heading("Market"), Note(f"Asking Spansh... {int(time.monotonic() - self._job.started)} s")]
        if self._sell_error:
            return [Heading("Market"), Note(self._sell_error, warn=True)]
        if self._sell and self._sell_for:
            return self._price_result_blocks()
        buying = self._side == trade_prices.BUY
        target = self._search_target()
        blocks: List[Block] = [Heading("Market search"), *self._ship_pairs(),
                               Pair("Looking to", "buy" if buying else "sell", bold=True)]
        if target is None:
            blocks.append(Note("Type the commodity you want to buy above (suggestions appear as you type)." if buying else
                               "Type a commodity above (suggestions appear as you type), or load cargo and it is "
                               "searched for you."))
        else:
            name, tonnes, _known = target
            blocks += [Pair("Commodity", _clip(name)),
                       Pair("Amount", f"{tonnes:,} t" + (" (your free hold space)" if buying else ""))]
        return blocks + [Pair("Near me", f"within {self._near_radius()} ly"), Pair("Galaxy", "anywhere")]

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
        """(commodity, tonnes to value the trade for, recognised). Selling: what is typed, else your largest
        load; the tonnes are what you carry of it, or a full hold if you carry none. Buying: only what is
        typed; the tonnes are your free hold space (a full hold's worth if the hold is already full)."""
        typed = self._commodity_entry.get() if self._commodity_entry is not None else ""
        carried = self._carried()
        if self._side == trade_prices.BUY:
            if not typed:
                return None
            name = trade_commodities.resolve(typed)
            free = max(0, self._capacity - sum(self._cargo.values())) if self._capacity else 0
            return name or typed, free or self._capacity or 100, name is not None
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

    def _price_result_blocks(self) -> List[Block]:
        commodity, tonnes, pad, side = self._sell_for  # type: ignore[misc]
        buying = side == trade_prices.BUY
        blocks: List[Block] = [Heading(f"{'Buying' if buying else 'Selling'} {_clip(commodity)}"),
                               Pair("Amount", f"{tonnes:,} t · {pad} pad" if pad else f"{tonnes:,} t")]
        if buying:
            blocks.append(Note("Stations that can supply all of it come first, cheapest first."))
        stations_by_scope: Dict[str, List[trade_prices.Offer]] = {}
        carriers_by_scope: Dict[str, List[trade_prices.Offer]] = {}
        for scope, title in (("near", f"Near me, within {self._near_radius()} ly"), ("galaxy", "Anywhere in the galaxy")):
            if scope not in self._sell:
                continue
            stations, carriers = trade_prices.split_carriers(self._sell[scope])
            stations_by_scope[scope], carriers_by_scope[scope] = stations, carriers
            blocks.append(Heading(title))
            if stations:
                blocks.append(Columns(_OFFER_COLUMNS))
                blocks += [self._offer_item(offer, tonnes) for offer in stations[:_SELL_SHOWN]]
            else:
                dropped = self._pad_dropped.get(scope, 0)
                blocks.append(Note(f"No station {'sells' if buying else 'wants'} it right now"
                                   + (f" that you can dock at ({dropped} too small for a {pad} pad were left out)"
                                      if pad and dropped else "") + "."))
            if carriers:
                blocks.append(Heading("Fleet carriers (they can move)", minor=True))
                blocks.append(Columns(_OFFER_COLUMNS))
                blocks += [self._offer_item(offer, tonnes) for offer in carriers[:_CARRIERS_SHOWN]]
        verdict = trade_prices.verdict(stations_by_scope.get("near", []), stations_by_scope.get("galaxy", []), side)
        if verdict:
            blocks.append(Note(verdict, strong=True))
        rank = (lambda o: o.price) if buying else (lambda o: -o.revenue)
        best_station = sorted((o for v in stations_by_scope.values() for o in v), key=rank)
        best_carrier = sorted((o for v in carriers_by_scope.values() for o in v), key=rank)
        note = trade_prices.carrier_note(best_station, best_carrier, side)
        if note:
            blocks.append(Note(note, warn=True))
        return blocks

    @staticmethod
    def _offer_item(offer: trade_prices.Offer, tonnes: int) -> Item:
        """One result: the station and its three numbers (price per tonne, total, distance), then the system and
        what kind of place it is (orbital or ground, its type, how far from the star), then any shortfall: the
        station has (buying) or wants (selling) less than the amount you asked about."""
        short = ""
        if offer.sellable_t < tonnes:
            short = (f"Only {offer.sellable_t:,} t in stock" if offer.side == trade_prices.BUY
                     else f"Only {offer.sellable_t:,} t wanted")
        return Item(_clip(offer.station), (f"{offer.price:,}", f"{offer.revenue:,}", f"{offer.distance_ly:.1f}"),
                    detail=f"{_clip(offer.system)} · {trade_prices.describe_place(offer)}", warn=short)

    # --- actions ------------------------------------------------------------------------

    def _clear_stock(self) -> None:
        """Forget the unsold stock (for cargo sold some other way, such as by the carrier's own orders)."""
        self._stock.clear(self._cmdr)
        self._save_stock(force=True)
        self._refresh()

    def _now(self) -> str:
        return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    def _session_id(self) -> str:
        """The id this session would be saved under: the same every time it is saved, however many logins it spans."""
        info = ledger_mod.meta(self._ledger) if self._ledger else {}
        started = info.get("started") or (self._ledger or {}).get("first_trade")
        return trade_history.session_id((self._ledger or {}).get("cmdr") or self._cmdr, started)

    def _session_mark(self) -> tuple:
        """How the session looks right now, to tell whether anything has happened since it was last saved."""
        ledger = self._ledger or {}
        return len(ledger.get("log") or []), ledger_mod.totals(ledger).net if ledger else 0

    def _unsaved(self) -> bool:
        return trade_history.has_content(self._ledger) and self._saved_marks.get(self._session_id()) != self._session_mark()

    def _say(self, text: str, seconds: int = 9) -> None:
        """A short message at the top of the Session page that goes away by itself."""
        self._save_message = text
        if self._parent is not None:
            self._parent.after(seconds * 1000, self._clear_message)
        self._refresh()

    def _clear_message(self) -> None:
        self._save_message = None
        if self._alive():
            self._refresh()

    def _stock_snapshot(self) -> List[Dict[str, Any]]:
        return [{"name": self._display(h.key), "tonnes": h.tonnes, "cost": h.cost}
                for h in self._stock.holdings(self._cmdr)]

    def _hold_snapshot(self) -> List[Dict[str, Any]]:
        return [{"name": self._display(name), "tonnes": tonnes}
                for name, tonnes in sorted(self._cargo.items(), key=lambda item: -item[1])]

    def _carrier_snapshot(self) -> List[Dict[str, Any]]:
        records = self._carrier.records.get(trade_carrier.key_for(self._cmdr)) or {}
        return [{"type": trade_carrier.TYPE_LABEL.get(kind, kind), "name": rec.get("name", ""), "callsign": rec.get("callsign", ""),
                 "capacity": rec.get("capacity", 0), "cargo": rec.get("cargo", 0), "reserved": rec.get("reserved", 0),
                 "free": rec.get("free", 0)} for kind, rec in records.items()]

    def _save_session(self) -> bool:
        """Keep this session in Trade History (only ever done on request). Saving again during the same login
        updates its entry. Returns True if it was saved."""
        if not trade_history.has_content(self._ledger):
            self._say("Nothing to save yet: no trades or running costs this session.")
            return False
        name = trade_ship.ship_display_name(self._ship) if self._ship else ""
        record = trade_history.build_record(
            self._ledger, self._ledger.get("cmdr") or self._cmdr, ship=name, pad=self._ship_pad(),
            credits_end=self._credits or None, stock=self._stock_snapshot(), hold=self._hold_snapshot(),
            capacity=self._capacity, carriers=self._carrier_snapshot(), saved_at=self._now())
        replaced = self._history.save(record)
        if self._plugin_dir is not None and not trade_history.save_all(self._plugin_dir, self._history.sessions):
            self._say("Could not write the history file (see the EDMC log). The session is kept until EDMC closes.")
            return False
        self._saved_marks[record["id"]] = self._session_mark()
        trade_history_window.refresh_if_open(self._history, select=record["id"])
        self._say(("Updated this session in Trade History." if replaced else "Saved to Trade History.")
                  + f" ({len(self._history.sessions)} saved)")
        return True

    def _persist_history(self) -> None:
        """The history window deleted something: write the book out."""
        if self._plugin_dir is not None:
            trade_history.save_all(self._plugin_dir, self._history.sessions)

    def _open_history(self) -> None:
        if self._parent is not None:
            trade_history_window.show(self._parent, self._history, self._persist_history)

    def _reset_ledger(self) -> None:
        """Start the tally again. If this session has trades that were never saved, offer to save it first."""
        if not self._cmdr:
            return
        if self._unsaved() and self._parent is not None:
            answer = messagebox.askyesnocancel(
                "Reset trade session",
                "This session has trades that haven't been saved to Trade History.\n\n"
                "Save it before starting again?", parent=self._parent)
            if answer is None:
                return
            if answer and not self._save_session():
                return
        self._book.put(self._cmdr, ledger_mod.new_ledger(self._cmdr, _current_logfile(), started=self._now(),
                                                         credits=self._credits or None))
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
            self._route_blocks = [Heading("Routes"), Note("Dock at a station once so WNTB knows where to start.", warn=True)]
            self._refresh()
            return
        query = spansh_routes.RouteQuery(
            system=start[0], station=start[1], capital=self._credits or 1_000_000,
            cargo_capacity=self._capacity or 100, max_hops=_cfg_int(_CFG_MAX_HOPS, _DEFAULT_MAX_HOPS, 1, 10),
            max_hop_distance_ly=self._jump_range_ly(),
            max_arrival_ls=_cfg_int(_CFG_MAX_ARRIVAL_LS, _DEFAULT_MAX_ARRIVAL_LS, 1, 1_000_000),
            requires_large_pad=config.get_bool(_CFG_LARGE_PAD, default=False) or self._ship_pad() == trade_ship.LARGE,
        )
        self._route_blocks, self._next_system = [], None
        self._route_label = f"{start[1]} ({start[0]})"
        self._start_job("routes", lambda cancel: spansh_routes.search_routes(query, cancel))

    def _find_prices(self, scope: str) -> None:
        if not self._system or (self._job is not None and not self._job.done):
            return
        target = self._search_target()
        buying = self._side == trade_prices.BUY
        if target is None:
            self._sell_error = ("Type the commodity you want to buy." if buying
                                else "Type a commodity to search for, or load some cargo.")
            self._refresh()
            return
        display, tonnes, _known = target
        system = self._system
        radius = float(self._near_radius()) if scope == "near" else None
        carriers = config.get_bool(_CFG_CARRIERS, default=True)
        ground = config.get_bool(_CFG_GROUND, default=True)
        pad = self._ship_pad()
        side = self._side
        fetch = _SELL_FETCH_PAD_FILTERED if pad else _SELL_FETCH

        def work(_cancel: threading.Event) -> Any:
            transaction = "Buy" if side == trade_prices.BUY else "Sell"
            # Stations and carriers are asked for separately: carriers are priced very differently, and in one
            # price-sorted list they filled the whole first page, leaving no real station to show.
            found = spansh_prices.search_best_price_stations(
                system, display, transaction, radius, max_results=fetch, station_types=trade_prices.station_types(ground))
            carrier_found = (spansh_prices.search_best_price_stations(
                system, display, transaction, radius, max_results=max(_CARRIER_FETCH_MIN, fetch // _CARRIER_FETCH_DIVISOR),
                station_types=trade_prices.CARRIER_TYPES) if carriers else [])
            ranked = trade_prices.rank_offers(trade_prices.merge_results(found, carrier_found), tonnes,
                                              include_carriers=carriers, ship_pad=pad, side=side, include_ground=ground)
            unfiltered = trade_prices.rank_offers(found, tonnes, include_carriers=False, side=side,
                                                  include_ground=ground)
            dropped = len(unfiltered) - len(trade_prices.split_carriers(ranked)[0]) if pad else 0
            return scope, (display, tonnes, pad, side), ranked, bool(found or carrier_found), dropped

        self._sell_error = None
        if self._sell_for != (display, tonnes, pad, side):
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
            self._route_blocks = [Heading("Routes"), Note(job.error, warn=True)]
            return
        hops: List[spansh_routes.Hop] = job.result or []
        if not hops:
            self._route_blocks = [Heading("Routes"), Note("No profitable route found."),
                                  Note("Try more hops, a longer range, or a bigger budget.")]
            return
        total = sum(hop.profit for hop in hops)
        blocks: List[Block] = [Heading("Route"), Pair("Total profit", f"{total:+,} cr", bold=True),
                               Pair("Hops", str(len(hops))), Columns(("Profit", "ly"))]
        for number, hop in enumerate(hops[:_ROUTES_SHOWN], start=1):
            detail = f"{_clip(hop.dest_system)} \u00b7 {hop.dest_ls:,.0f} ls"
            if hop.cargo:
                best = max(hop.cargo, key=lambda c: c.total_profit)
                detail += f" \u00b7 {_clip(best.name)} \u00d7 {best.tonnes} t"
            blocks.append(Item(f"{number}. {_clip(hop.source_station)} \u2192 {_clip(hop.dest_station)}",
                               (f"{hop.profit:+,}", f"{hop.distance_ly:.1f}"), detail=detail))
        if len(hops) > _ROUTES_SHOWN:
            blocks.append(Note(f"+{len(hops) - _ROUTES_SHOWN} more hop(s)"))
        self._route_blocks = blocks
        self._next_system = hops[0].dest_system if hops[0].dest_system != "?" else None
        if self._ledger is not None:
            ledger_mod.add_route(self._ledger, {
                "t": self._now(), "start": self._route_label, "total": total,
                "hops": [{"from": hop.source_station, "to": hop.dest_station, "system": hop.dest_system,
                          "ly": round(hop.distance_ly, 1), "profit": hop.profit,
                          "cargo": [{"name": c.name, "tonnes": c.tonnes, "profit": c.total_profit} for c in hop.cargo]}
                         for hop in hops]})

    def _finish_sell(self, job: _Job) -> None:
        if job.error:
            self._sell_error = job.error
            return
        scope, key, offers, any_found, dropped = job.result
        if self._sell_for != key:
            self._sell, self._pad_dropped = {}, {}
        self._sell_for = key
        self._sell[scope] = offers
        self._pad_dropped[scope] = dropped
        if self._ledger is not None:
            stations_only, _carriers = trade_prices.split_carriers(offers)
            top = (stations_only or offers or [None])[0]
            ledger_mod.add_search(self._ledger, {
                "t": self._now(), "side": key[3], "commodity": key[0], "tonnes": key[1], "scope": scope,
                "best": ({"station": top.station, "system": top.system, "price": top.price, "ly": round(top.distance_ly, 1)}
                         if top else None)})
        if not any_found and not offers and not self._sell.get("galaxy" if scope == "near" else "near"):
            verb = "selling" if key[3] == trade_prices.BUY else "buying"
            self._sell_error = (f"Spansh found no market {verb} {_clip(key[0])}. "
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
        self._ground_var = tk.BooleanVar(value=config.get_bool(_CFG_GROUND, default=True))
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
        where = tk.Frame(frame)
        where.grid(row=4, column=0, sticky=tk.W, padx=10, pady=2)
        nb.Checkbutton(where, text="Search fleet carriers (listed apart; they can jump away)",
                       variable=self._carriers_var).grid(row=0, column=0, sticky=tk.W)
        nb.Checkbutton(where, text="Search ground facilities (planetary ports, outposts and settlements)",
                       variable=self._ground_var).grid(row=1, column=0, sticky=tk.W)
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
        config.set(_CFG_GROUND, bool(self._ground_var.get()) if self._ground_var is not None else True)
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
