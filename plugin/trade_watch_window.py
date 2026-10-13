"""The Watch list window: the commander's watched commodities with the best price to buy and to sell each at, where, and how old the
price is; pick one to see every market it was seen at. Add a commodity with the type-ahead box; Remove takes one off (press twice);
Refresh from Spansh asks for the best prices near the system you are in (Trade's lookups must be on). Built on the shared window kit
(plugin/uikit); the list itself is `trade_watch_data.WatchBook`, which saves each change at once. Module-level show/refresh/close and
saved geometry follow notes_window.py."""
from __future__ import annotations

import logging
import os
import tkinter as tk
from typing import Any, List, Optional

from config import appname, config

from . import trade_watch_data as data
from .trade_commodity_entry import CommodityEntry
from .uikit import palette as P
from .uikit.shell import WindowShell
from .uikit.table import Column, DataTable
from .uikit.widgets import FlatButton

plugin_name = os.path.basename(os.path.dirname(__file__))
logger = logging.getLogger(f"{appname}.{plugin_name}")

CONFIG_GEOMETRY = "wntb_trade_watch_window_geometry"
DEFAULT_SIZE = (1080, 640)
MIN_SIZE = (860, 480)
CONFIRM_MS = 5000     # how long a first press of Remove waits for the second

_window: Optional["WatchWindow"] = None

_WATCH_COLUMNS = (
    Column("commodity", "Commodity", 160, max_chars=32),
    Column("buy", "Buy (cr/t)", 90, anchor="e"),
    Column("buy_where", "Buy at", 230, stretch=True, max_chars=60),
    Column("sell", "Sell (cr/t)", 90, anchor="e"),
    Column("sell_where", "Sell at", 230, stretch=True, max_chars=60),
)
_SEEN_COLUMNS = (
    Column("station", "Station", 180, stretch=True, max_chars=40),
    Column("system", "System", 150, max_chars=32),
    Column("buy", "Buy (cr/t)", 90, anchor="e"),
    Column("stock", "Stock", 80, anchor="e"),
    Column("sell", "Sell (cr/t)", 90, anchor="e"),
    Column("demand", "Demand", 80, anchor="e"),
    Column("seen", "Seen", 80, anchor="e"),
)


def show(parent: tk.Misc, book: data.WatchBook, controller: Any) -> None:
    """Open the Watch list window, or raise it if it is already open."""
    global _window
    if _window is not None and _window.alive:
        _window.refresh()
        _window.lift()
        return
    _window = WatchWindow(parent, book, controller)


def refresh() -> None:
    if _window is not None and _window.alive:
        _window.refresh()


def close() -> None:
    if _window is not None and _window.alive:
        _window.close()


def where(quote: Optional[data.Quote], now: Optional[str] = None) -> str:
    """`Station, System (5 min, Spansh)`: where a price is from and how old it is."""
    if quote is None:
        return ""
    how = quote.source if quote.source == data.SPANSH else "seen"
    when = data.age(quote.when, now)
    note = f"{when}, {how}" if when else how
    return f"{data.clip(quote.station, 28)}, {data.clip(quote.system, 24)} ({note})"


def price(quote: Optional[data.Quote]) -> str:
    return f"{quote.price:,}" if quote is not None else "-"


class WatchWindow:
    def __init__(self, parent: tk.Misc, book: data.WatchBook, controller: Any) -> None:
        self._book = book
        self._controller = controller
        self._picked: Optional[str] = None        # the commodity whose markets are shown below
        self._shown: List[str] = []
        self._confirming = False                  # Remove has been pressed once

        self._shell = WindowShell(
            parent, "Watch list", "", size=DEFAULT_SIZE, min_size=MIN_SIZE,
            load_geometry=lambda: config.get_str(CONFIG_GEOMETRY) or "",
            save_geometry=lambda geometry: config.set(CONFIG_GEOMETRY, geometry))
        self._shell.window.protocol("WM_DELETE_WINDOW", self.close)
        self._refresh_action = self._shell.add_action("Refresh from Spansh", self._refresh_spansh, accent=True)

        adding = tk.Frame(self._shell.body, bg=P.BG)
        adding.pack(fill="x", pady=(0, P.PAD_SM))
        tk.Label(adding, text="Add a commodity", fg=P.MUTED, bg=P.BG).pack(side="left")
        self._entry = CommodityEntry(adding, preferred=lambda: [], on_submit=self._add)
        self._entry.pack(side="left", padx=(P.PAD_SM, P.PAD_SM))
        FlatButton(adding, "Add", self._add).pack(side="left")
        self._remove_button = FlatButton(adding, "Remove", self._remove, kind="danger")
        self._remove_button.pack(side="left", padx=(P.PAD, 0))
        self._remove_button.set_enabled(False)

        self._table = DataTable(self._shell.body, _WATCH_COLUMNS, on_select=self._pick,
                                empty_text="Nothing watched yet. Add a commodity above.", visible_rows=8)
        self._table.pack(fill="x", pady=(0, P.PAD_SM))

        self._seen_title = tk.Label(self._shell.body, text="", fg=P.MUTED, bg=P.BG, anchor="w")
        self._seen_title.pack(fill="x")
        self._seen = DataTable(self._shell.body, _SEEN_COLUMNS, sortable=False, visible_rows=6,
                               empty_text="Select a commodity to see the markets it was seen at.")
        self._seen.pack(fill="x", pady=(0, P.PAD_SM))

        book.add_listener(self._on_book_changed)
        self.refresh()

    # --- the window ---------------------------------------------------------------------------------------------------

    @property
    def alive(self) -> bool:
        return self._shell.alive

    def lift(self) -> None:
        self._shell.window.deiconify()
        self._shell.window.lift()

    def close(self) -> None:
        self._book.remove_listener(self._on_book_changed)
        self._shell.close()

    def refresh(self) -> None:
        if not self.alive:
            return
        who = self._book.commander
        count = self._book.count()
        self._shell.set_subtitle(f"{who}: {count} commodit{'y' if count == 1 else 'ies'} watched" if who
                                 else "Waiting for a commander (log in)")
        self._fill()

    def _on_book_changed(self) -> None:
        try:
            if self.alive:
                self.refresh()
        except tk.TclError:
            pass   # the window went away between the check and the redraw

    def _fill(self) -> None:
        if not self.alive:
            return
        keep = self._picked
        self._table.clear()
        self._shown = self._book.watched()
        for name in self._shown:
            buy, sell = self._book.best_buy(name), self._book.best_sell(name)
            self._table.insert(name, (name, price(buy), where(buy), price(sell), where(sell)))
        if keep and keep in self._shown:
            self._table.select(keep)
        else:
            self._picked = None
        self._fill_seen()
        self._remove_button.set_enabled(self._picked is not None)
        note = self._controller.status or (
            "Prices are the best among the markets you opened and, after Refresh, Spansh's. A price is only true when it was seen: "
            "check the age. Nothing leaves this computer unless you press Refresh.")
        self._shell.set_status(note)

    def _fill_seen(self) -> None:
        self._seen.clear()
        if self._picked is None:
            self._seen_title.configure(text="")
            return
        sightings = self._book.sightings(self._picked)
        self._seen_title.configure(text=f"{self._picked}: markets you opened")
        for s in sightings:
            self._seen.append((s.station, s.system, f"{s.buy_price:,}" if s.buy_price else "-", f"{s.stock:,}" if s.stock else "-",
                               f"{s.sell_price:,}" if s.sell_price else "-", f"{s.demand:,}" if s.demand else "-", data.age(s.seen)))

    # --- the buttons --------------------------------------------------------------------------------------------------

    def _pick(self, name: str) -> None:
        self._picked = name if name in self._shown else None
        self._confirming = False
        self._remove_button.set_enabled(self._picked is not None)
        self._fill_seen()

    def _add(self) -> None:
        try:
            name = self._book.add(self._entry.get())
        except data.WatchError as err:
            self._shell.set_status(str(err))
            return
        self._entry.set("")
        self._picked = name
        self._fill()
        self._table.select(name)
        self._shell.set_status(f"Watching {name}. Open a market that trades it, or press Refresh from Spansh, to see a price.")

    def _remove(self) -> None:
        """Removing forgets the prices seen for it, so the first press asks and a second press (within a few seconds) removes."""
        if self._picked is None:
            return
        if not self._confirming:
            self._confirming = True
            self._shell.set_status(f"Press Remove again to stop watching {self._picked} and forget its prices.")
            self._shell.window.after(CONFIRM_MS, self._stop_confirming)
            return
        self._confirming = False
        name, self._picked = self._picked, None
        if self._book.remove(name):
            self._shell.set_status(f"Stopped watching {name}.")

    def _stop_confirming(self) -> None:
        self._confirming = False

    def _refresh_spansh(self) -> None:
        self._controller.refresh()
        self._shell.set_status(self._controller.status)
