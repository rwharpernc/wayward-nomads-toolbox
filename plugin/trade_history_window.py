"""Trade History window: every trading session the commander chose to save, one at a time, with all of its numbers.

Built on the shared window kit (plugin/uikit: WindowShell, Tabs, DataTable - see docs/WINDOW_FRAMEWORK_SPEC.md) with
the same `show(parent, ...)` entry point and geometry-persistence convention as the BGS Report and Powerplay
Sessions windows. A drop-down at the top picks the session (newest first, optionally one commander's); below it:

- **Overview**: the headline numbers (net and trade profit, running costs, per hour, tonnes, time), balance, jumps,
  per-tonne and per-jump figures, and the running costs with their share of sales.
- **Commodities**: bought / sold / averages / profit / margin for each.
- **Stations**: the same added up for each station traded at.
- **Route**: the stations visited in order with what was bought and sold at each and a running net.
- **Trades**: every buy, sale and cost, newest page first, paged (a long session has thousands).
- **Stock & carrier**: what was unsold, in the hold and on the carrier when it was saved.
- **Lookups**: the Spansh routes and market searches made during the session.

The numbers are worked out in trade_stats.py from the saved record; this module only lays them out. **Copy summary**
puts a plain-text version on the clipboard, **Export log** writes the trade log as CSV, **Delete session** removes it
from the history (after asking). Only the tab on screen is filled in; the others fill when selected, so a session
with thousands of trades doesn't build every table at once."""

from __future__ import annotations

import logging
import os
import tkinter as tk
from tkinter import filedialog, messagebox
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

from config import appname, config

from . import panelkit, trade_stats as stats
from .trade_history import HistoryBook
from .uikit import palette as P
from .uikit import style
from .uikit.shell import WindowShell
from .uikit.table import Column, DataTable
from .uikit.widgets import Card, Combobox, FlatButton, NoteLabel, ScrollFrame, StatTile, Tabs, field_grid, section_header

plugin_name = os.path.basename(os.path.dirname(__file__))
logger = logging.getLogger(f"{appname}.{plugin_name}")

CONFIG_GEOMETRY = "wntb_trade_history_window_geometry"

MIN_WIDTH = 1080
MIN_HEIGHT = 520
DEFAULT_SIZE = (1180, 700)
PAGE_SIZE = 200          # rows of the trade log shown at once
ALL_COMMANDERS = "All commanders"

LEGEND = (
    "Only sessions you saved (Trade > Session > Save session) are here; saving again during the same login updates "
    "its entry. NET PROFIT = trade profit (sales minus what the sold tonnes cost) minus running costs. PER HOUR uses "
    "trading time, first trade to last. BALANCE CHANGE is the real credits difference between login and save, so it "
    "also includes anything else you earned. Times are UTC, as the journal writes them. Money is in credits; Bought / Sold are tonnes."
)

# Column widths are chosen so each table's minimum widths add up to less than the window's minimum width (MIN_WIDTH
# less the window's padding), with the wide text column stretching to take any spare room. Anything wider is clipped.
_COMMODITY_COLUMNS = (
    Column("name", "Commodity", 130, stretch=True, max_chars=40),
    Column("bought", "Bought t", 62, anchor="e"), Column("spent", "Spent", 92, anchor="e"),
    Column("avg_buy", "Avg buy", 62, anchor="e"), Column("sold", "Sold t", 52, anchor="e"),
    Column("revenue", "Revenue", 92, anchor="e"), Column("avg_sell", "Avg sell", 62, anchor="e"),
    Column("profit", "Profit", 92, anchor="e"), Column("margin", "Margin", 58, anchor="e"),
    Column("per_t", "Profit/t", 60, anchor="e"), Column("left", "Unsold t", 62, anchor="e"),
)
_STATION_COLUMNS = (
    Column("station", "Station", 150, stretch=True, max_chars=44), Column("system", "System", 120, max_chars=36),
    Column("visits", "Visits", 48, anchor="e"), Column("bought", "Bought t", 62, anchor="e"),
    Column("spent", "Spent", 90, anchor="e"), Column("sold", "Sold t", 52, anchor="e"),
    Column("revenue", "Revenue", 92, anchor="e"), Column("profit", "Profit", 92, anchor="e"),
    Column("costs", "Costs", 60, anchor="e"), Column("net", "Net", 90, anchor="e"),
)
_ROUTE_COLUMNS = (
    Column("n", "#", 30, anchor="e"), Column("time", "Time", 118), Column("station", "Station", 150, max_chars=40),
    Column("system", "System", 125, max_chars=34), Column("what", "What happened", 220, stretch=True, max_chars=120),
    Column("net", "Net", 90, anchor="e"), Column("running", "Running", 95, anchor="e"),
)
# The table's headings are shorter than the CSV's (trade_stats.LOG_HEADERS) so the nine columns fit.
_TRADE_COLUMNS = (
    Column("time", "Time", 125), Column("type", "Type", 60), Column("commodity", "Commodity", 120, stretch=True, max_chars=40),
    Column("tonnes", "t", 55, anchor="e"), Column("unit", "Unit", 70, anchor="e"), Column("total", "Total", 95, anchor="e"),
    Column("profit", "Profit", 85, anchor="e"), Column("station", "Station", 140, max_chars=40),
    Column("system", "System", 120, max_chars=36),
)
_COST_COLUMNS = (
    Column("kind", "Running cost", 200, stretch=True), Column("amount", "Credits", 120, anchor="e"),
    Column("share", "Share of sales", 120, anchor="e"),
)
_STOCK_COLUMNS = (
    Column("name", "Bought, not sold (estimate)", 220, stretch=True, max_chars=40), Column("tonnes", "Tonnes", 90, anchor="e"),
    Column("cost", "Cost (cr)", 130, anchor="e"), Column("avg", "Avg cost / t", 110, anchor="e"),
)
_HOLD_COLUMNS = (Column("name", "In the ship hold when saved", 220, stretch=True, max_chars=40), Column("tonnes", "Tonnes", 90, anchor="e"))
_CARRIER_COLUMNS = (
    Column("type", "Carrier", 140), Column("name", "Name", 200, stretch=True, max_chars=40),
    Column("used", "Carrier cargo used / capacity (t)", 190, anchor="e"), Column("free", "Free (t)", 90, anchor="e"),
    Column("reserved", "Reserved (t)", 100, anchor="e"),
)
_ROUTE_SEARCH_COLUMNS = (
    Column("time", "Time (UTC)", 125), Column("start", "Started from", 190, max_chars=50),
    Column("hops", "Hops", 50, anchor="e"), Column("total", "Total profit (cr)", 130, anchor="e"),
    Column("chain", "Route", 360, stretch=True, max_chars=160),
)
_MARKET_SEARCH_COLUMNS = (
    Column("time", "Time (UTC)", 125), Column("side", "Side", 50), Column("commodity", "Commodity", 130, max_chars=34),
    Column("tonnes", "Tonnes", 65, anchor="e"), Column("scope", "Scope", 70),
    Column("station", "Best result", 190, stretch=True, max_chars=44), Column("system", "System", 150, max_chars=34),
    Column("price", "cr/t", 70, anchor="e"), Column("ly", "ly", 60, anchor="e"),
)

_window: Optional["HistoryWindow"] = None


def show(parent: tk.Misc, book: HistoryBook, on_change: Callable[[], None], select: Optional[str] = None) -> None:
    """Open the history window, or refresh and raise it if already open. `select` is a session id to show."""
    global _window
    if _window is not None and _window.alive:
        _window.refresh(book, select)
        _window.lift()
        return
    _window = HistoryWindow(parent, book, on_change, select)


def refresh_if_open(book: HistoryBook, select: Optional[str] = None) -> None:
    """Called when a session is saved: keep an open window current."""
    if _window is not None and _window.alive:
        _window.refresh(book, select)


def close() -> None:
    if _window is not None and _window.alive:
        _window.close()


def _table(parent: tk.Misc, columns: Sequence[Column], empty: str, rows: Optional[int] = None, sortable: bool = True) -> DataTable:
    table = DataTable(parent, columns, sortable=sortable, visible_rows=rows, empty_text=empty)
    return table


class _Overview:
    """The headline numbers. Small, so it is simply rebuilt each time a session is shown."""

    def __init__(self, parent: tk.Frame) -> None:
        scroll = ScrollFrame(parent)
        scroll.pack(fill="both", expand=True)
        self._body = scroll.body

    def fill(self, record: Dict[str, Any]) -> None:
        for child in self._body.winfo_children():
            child.destroy()
        o = stats.overview(record)
        card = Card(self._body)
        card.pack(fill="x", padx=P.PAD, pady=(P.PAD, P.PAD_SM))
        tiles = (
            (f"{o.net:+,} cr", "NET PROFIT", P.OK if o.net >= 0 else P.DANGER),
            (f"{o.trade_profit:+,} cr", "TRADE PROFIT", P.TEXT),
            (f"-{o.expenses:,} cr" if o.expenses else "0 cr", "RUNNING COSTS", P.WARN if o.expenses else P.TEXT),
            ("—" if o.net_per_hour is None else f"{o.net_per_hour:+,.0f} cr", "NET PER HOUR", P.TEXT),
            (f"{o.sold_t:,} t", "TONNES SOLD", P.TEXT),
            (stats.fmt_duration(o.trading_hours), "TRADING TIME", P.TEXT),
        )
        for index, (value, caption, colour) in enumerate(tiles):
            card.columnconfigure(index, weight=1)
            StatTile(card, value, caption, colour).grid(row=0, column=index, sticky="w", padx=(0, P.PAD))

        facts = tk.Frame(self._body, bg=P.PANE)
        facts.pack(fill="x", padx=P.PAD, pady=(P.PAD_SM, P.PAD))
        ship = str(record.get("ship") or "?") + (f" ({record['pad']} pad)" if record.get("pad") else "")
        balance = ("—" if o.balance_change is None else
                   f"{o.credits_start:,} → {o.credits_end:,} cr  ({o.balance_change:+,})")
        rows = (
            (("Commander:", str(record.get("cmdr") or "?")), ("Ship:", ship)),
            (("Started:", stats.fmt_time(o.started) or "?"), ("Ended:", stats.fmt_time(o.ended) or "?")),
            (("Session length:", stats.fmt_duration(o.session_hours)), ("Saved:", stats.fmt_time(record.get("saved_at")) or "?")),
            (("Balance change:", balance), ("Trades:", f"{o.trades:,} at {o.stations} station(s), {o.visits} visit(s)")),
            (("Bought:", f"{o.bought_t:,} t for {o.spent:,} cr"), ("Sold:", f"{o.sold_t:,} t for {o.revenue:,} cr")),
            (("Profit per tonne sold:", "—" if o.profit_per_tonne is None else f"{o.profit_per_tonne:+,.0f} cr"),
             ("Margin on cost:", "—" if o.margin_pct is None else f"{o.margin_pct:+.1f}%")),
            (("Jumps:", f"{o.jumps:,}  ({o.jump_ly:,.1f} ly)"),
             ("Net per jump:", "—" if o.profit_per_jump is None else f"{o.profit_per_jump:+,.0f} cr")),
            (("Net per light year:", "—" if o.profit_per_ly is None else f"{o.profit_per_ly:+,.0f} cr"), ("", "")),
        )
        for number, pairs in enumerate(rows):
            field_grid(facts, number, tuple(pair for pair in pairs if pair[0]))

        section_header(self._body, "Running costs").pack(fill="x")
        costs = _table(self._body, _COST_COLUMNS, "No running costs recorded.", rows=6, sortable=False)
        costs.pack(fill="x", padx=P.PAD, pady=(0, P.PAD))
        sales = o.revenue or 0
        costs.set_rows([(label, f"-{amount:,}" if amount > 0 else f"+{-amount:,}",
                         f"{amount / sales * 100:.1f}%" if sales else "") for label, amount in stats.cost_breakdown(record)])

        ranked = [c for c in stats.commodity_stats(record) if c.sold_t > 0]   # best and weakest among those sold
        if ranked:
            best, worst = ranked[0], ranked[-1]
            line = f"Best commodity: {best.name} ({best.profit:+,} cr)"
            if len(ranked) > 1:
                line += f"      Weakest: {worst.name} ({worst.profit:+,} cr)"
            NoteLabel(self._body, text=line, fg=P.TEXT).pack(fill="x", pady=(0, P.PAD))


class _TableTab:
    """A tab that is one table (plus an optional note)."""

    def __init__(self, parent: tk.Frame, columns: Sequence[Column], empty: str, rows_for: Callable[[Dict[str, Any]], List[Tuple[str, ...]]],
                 note: str = "") -> None:
        if note:
            NoteLabel(parent, text=note).pack(side="bottom", fill="x", pady=(P.PAD_SM, P.PAD_SM))
        self._table = _table(parent, columns, empty)
        self._table.pack(fill="both", expand=True, padx=P.PAD, pady=P.PAD)
        self._rows_for = rows_for

    def fill(self, record: Dict[str, Any]) -> None:
        self._table.set_rows(self._rows_for(record))


class _TradesTab:
    """The trade log, a page at a time (a long session has thousands of rows, and each is a set of widgets)."""

    def __init__(self, parent: tk.Frame) -> None:
        bar = tk.Frame(parent, bg=P.PANE)
        bar.pack(fill="x", padx=P.PAD, pady=(P.PAD_SM, 0))
        self._older = FlatButton(bar, "◀ Earlier", lambda: self._go(-1), kind="normal")
        self._older.pack(side="left")
        self._newer = FlatButton(bar, "Later ▶", lambda: self._go(1), kind="normal")
        self._newer.pack(side="left", padx=(6, 0))
        self._where = tk.Label(bar, text="", fg=P.MUTED, bg=P.PANE)
        self._where.pack(side="left", padx=P.PAD)
        self._table = _table(parent, _TRADE_COLUMNS, "No trades were logged for this session.")
        self._table.pack(fill="both", expand=True, padx=P.PAD, pady=P.PAD)
        self._rows: List[Tuple[str, ...]] = []
        self._page = 0
        self._record_id: Optional[str] = None

    def fill(self, record: Dict[str, Any]) -> None:
        if record.get("id") != self._record_id:
            self._record_id = record.get("id")
            self._rows = stats.log_rows(record)
            self._page = max(0, (len(self._rows) - 1) // PAGE_SIZE)   # open on the newest page
        self._show()

    def _go(self, step: int) -> None:
        last = max(0, (len(self._rows) - 1) // PAGE_SIZE)
        self._page = max(0, min(last, self._page + step))
        self._show()

    def _show(self) -> None:
        start = self._page * PAGE_SIZE
        chunk = self._rows[start:start + PAGE_SIZE]
        self._table.set_rows(chunk)
        total = len(self._rows)
        self._where.configure(text=f"{start + 1:,}–{start + len(chunk):,} of {total:,}" if total else "")
        last = max(0, (total - 1) // PAGE_SIZE)
        self._older.set_enabled(self._page > 0)
        self._newer.set_enabled(self._page < last)


class _StockTab:
    def __init__(self, parent: tk.Frame) -> None:
        scroll = ScrollFrame(parent)
        scroll.pack(fill="both", expand=True)
        body = scroll.body
        self._note = NoteLabel(body, text="")
        self._note.pack(fill="x", pady=(P.PAD_SM, 0))
        section_header(body, "Bought, not yet sold (journal estimate, may include cargo since sold)").pack(fill="x")
        self._stock = _table(body, _STOCK_COLUMNS, "Nothing was waiting to be sold.", rows=6, sortable=False)
        self._stock.pack(fill="x", padx=P.PAD, pady=(0, P.PAD))
        section_header(body, "In the ship hold when saved").pack(fill="x")
        self._hold = _table(body, _HOLD_COLUMNS, "The ship hold was empty.", rows=6, sortable=False)
        self._hold.pack(fill="x", padx=P.PAD, pady=(0, P.PAD))
        section_header(body, "Carriers").pack(fill="x")
        self._carriers = _table(body, _CARRIER_COLUMNS, "No carrier was recorded for this commander.", rows=4, sortable=False)
        self._carriers.pack(fill="x", padx=P.PAD, pady=(0, P.PAD))

    def fill(self, record: Dict[str, Any]) -> None:
        capacity = record.get("capacity")
        self._note.configure(text=f"As it stood when the session was saved ({stats.fmt_time(record.get('saved_at')) or '?'} UTC)."
                             + (f" Hold capacity {capacity:,} t." if isinstance(capacity, int) and capacity else ""))
        self._stock.set_rows(stats.stock_rows(record))
        self._hold.set_rows(stats.hold_rows(record))
        self._carriers.set_rows(stats.carrier_rows(record))


class _LookupsTab:
    def __init__(self, parent: tk.Frame) -> None:
        scroll = ScrollFrame(parent)
        scroll.pack(fill="both", expand=True)
        body = scroll.body
        section_header(body, "Spansh routes searched").pack(fill="x")
        self._routes = _table(body, _ROUTE_SEARCH_COLUMNS, "No route searches during this session.", rows=6, sortable=False)
        self._routes.pack(fill="x", padx=P.PAD, pady=(0, P.PAD))
        section_header(body, "Market searches").pack(fill="x")
        self._searches = _table(body, _MARKET_SEARCH_COLUMNS, "No market searches during this session.", rows=10, sortable=False)
        self._searches.pack(fill="x", padx=P.PAD, pady=(0, P.PAD))

    def fill(self, record: Dict[str, Any]) -> None:
        self._routes.set_rows(stats.lookup_route_rows(record))
        self._searches.set_rows(stats.search_rows(record))


class HistoryWindow:
    def __init__(self, parent: tk.Misc, book: HistoryBook, on_change: Callable[[], None], select: Optional[str]) -> None:
        self._book = book
        self._on_change = on_change
        self._shell = WindowShell(
            parent, "Trade History", "", size=DEFAULT_SIZE, min_size=(MIN_WIDTH, MIN_HEIGHT),
            load_geometry=lambda: config.get_str(CONFIG_GEOMETRY) or "",
            save_geometry=lambda geometry: config.set(CONFIG_GEOMETRY, geometry))
        self._shell.window.protocol("WM_DELETE_WINDOW", self.close)
        self._toplevel = self._shell.window
        self._copy_button = self._shell.add_action("Copy summary", self._on_copy)
        self._shell.add_action("Export log (CSV)", self._on_export)
        self._shell.add_action("Delete session", self._on_delete)
        self._shell.set_status(LEGEND)

        picker = tk.Frame(self._shell.body, bg=P.BG)
        picker.pack(fill="x", padx=P.PAD, pady=(P.PAD_SM, P.PAD_SM))
        tk.Label(picker, text="SESSION", fg=P.MUTED, bg=P.BG, font=style.font(P.FONT_SMALL)).pack(side="left")
        self._session_var = tk.StringVar()
        self._session_box = Combobox(picker, textvariable=self._session_var, state="readonly", width=70)
        self._session_box.pack(side="left", padx=(P.PAD_SM, 0))
        self._session_box.bind("<<ComboboxSelected>>", lambda _e: self._on_session_selected())
        self._cmdr_var = tk.StringVar(value=ALL_COMMANDERS)
        self._cmdr_box = Combobox(picker, textvariable=self._cmdr_var, state="readonly", width=22)
        self._cmdr_box.bind("<<ComboboxSelected>>", lambda _e: self._on_commander_selected())
        self._cmdr_label = tk.Label(picker, text="COMMANDER", fg=P.MUTED, bg=P.BG, font=style.font(P.FONT_SMALL))

        self._stage = tk.Frame(self._shell.body, bg=P.PANE)
        self._stage.pack(fill="both", expand=True, pady=(0, P.PAD_SM))
        self._empty = NoteLabel(self._stage, fg=P.MUTED,
                                text="No saved sessions yet. Press Save session on the Trade > Session page to keep this "
                                     "trading session here; it will then appear in this list with all of its figures.")
        self._tabs = Tabs(self._stage)
        self._overview = _Overview(self._tabs.add("Overview"))
        self._commodities = _TableTab(self._tabs.add("Commodities"), _COMMODITY_COLUMNS, "No commodities traded.", stats.commodity_rows)
        self._stations = _TableTab(self._tabs.add("Stations"), _STATION_COLUMNS, "No stations recorded.", stats.station_rows,
                                   note="Each station's visits added up. Net = trade profit made there minus any fuel or repairs paid there.")
        self._route = _TableTab(self._tabs.add("Route"), _ROUTE_COLUMNS, "No station visits were logged for this session.", stats.route_rows,
                                note="The stations traded at, in the order you flew them (a station you return to is a new visit). "
                                     "Net = trade profit made on that visit minus fuel or repairs paid there; Running net adds them up.")
        self._trades = _TradesTab(self._tabs.add("Trades"))
        self._stock = _StockTab(self._tabs.add("Stock & carrier"))
        self._lookups = _LookupsTab(self._tabs.add("Lookups"))
        self._fillers = [self._overview, self._commodities, self._stations, self._route, self._trades, self._stock, self._lookups]
        self._tabs.on_select = self._draw_tab

        self._sessions: List[Dict[str, Any]] = []
        self._labels: Dict[str, Dict[str, Any]] = {}
        self._selected_id: Optional[str] = None
        self._drawn: Dict[int, Optional[str]] = {}
        self.refresh(book, select)

    @property
    def alive(self) -> bool:
        return self._shell.alive

    def lift(self) -> None:
        self._toplevel.deiconify()
        self._toplevel.lift()

    # --- data ----------------------------------------------------------------------------------

    def refresh(self, book: HistoryBook, select: Optional[str] = None) -> None:
        if not self.alive:
            return
        self._book = book
        commanders = book.commanders()
        self._cmdr_box.configure(values=[ALL_COMMANDERS] + commanders)
        if len(commanders) > 1:
            self._cmdr_label.pack(side="right", padx=(0, P.PAD_SM))
            self._cmdr_box.pack(side="right")
            self._cmdr_label.lift()
        else:
            self._cmdr_label.pack_forget()
            self._cmdr_box.pack_forget()
        if self._cmdr_var.get() not in [ALL_COMMANDERS] + commanders:
            self._cmdr_var.set(ALL_COMMANDERS)
        if select:
            self._selected_id = select
        self._load_sessions()

    def _load_sessions(self) -> None:
        wanted = None if self._cmdr_var.get() == ALL_COMMANDERS else self._cmdr_var.get()
        self._sessions = self._book.newest_first(wanted)
        self._labels = {}
        for record in self._sessions:
            text = stats.label(record)
            while text in self._labels:
                text += " "
            self._labels[text] = record
        self._session_box.configure(values=list(self._labels))
        chosen = next((r for r in self._sessions if r.get("id") == self._selected_id), None) or (self._sessions[0] if self._sessions else None)
        self._drawn = {}
        if chosen is None:
            self._selected_id = None
            self._session_var.set("")
            self._tabs.pack_forget()
            self._empty.pack(fill="x", pady=P.PAD)
            self._shell.set_subtitle("No saved sessions")
            return
        self._selected_id = chosen.get("id")
        self._session_var.set(next(text for text, rec in self._labels.items() if rec is chosen))
        self._empty.pack_forget()
        if not self._tabs.winfo_ismapped():
            self._tabs.pack(fill="both", expand=True)
        self._shell.set_subtitle(f"{len(self._sessions)} saved session(s)")
        self._draw_tab(self._tabs.selected)

    def _current(self) -> Optional[Dict[str, Any]]:
        return next((r for r in self._sessions if r.get("id") == self._selected_id), None)

    def _on_session_selected(self) -> None:
        record = self._labels.get(self._session_var.get())
        if record is not None:
            self._selected_id = record.get("id")
            self._drawn = {}
            self._draw_tab(self._tabs.selected)

    def _on_commander_selected(self) -> None:
        self._selected_id = None
        self._load_sessions()

    def _draw_tab(self, index: int) -> None:
        """Fill the tab being shown, once per session; the others fill when they are selected."""
        record = self._current()
        if record is None or not self.alive or not (0 <= index < len(self._fillers)):
            return
        if self._drawn.get(index) == record.get("id"):
            return
        self._drawn[index] = record.get("id")
        self._fillers[index].fill(record)

    # --- actions -----------------------------------------------------------------------------------

    def _on_copy(self) -> None:
        record = self._current()
        if record is None:
            return
        if panelkit.copy_to_clipboard(self._toplevel, "\n".join(stats.summary_text(record))):
            original = self._copy_button.cget("text")
            self._copy_button.configure(text="Copied!")
            self._copy_button.after(1500, lambda: self._copy_button.configure(text=original) if self.alive else None)

    def _on_export(self) -> None:
        record = self._current()
        if record is None:
            return
        when = (stats.fmt_time(record.get("started")) or "session").replace(":", "").replace(" ", "_")
        path = filedialog.asksaveasfilename(
            parent=self._toplevel, title="Export trade log", defaultextension=".csv",
            initialfile=f"trade-log-{when}.csv", filetypes=[("CSV file", "*.csv"), ("All files", "*.*")])
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8", newline="") as handle:
                handle.write(stats.csv_text(record))
        except OSError as err:
            messagebox.showerror("Export trade log", f"Could not write the file:\n{err}", parent=self._toplevel)

    def _on_delete(self) -> None:
        record = self._current()
        if record is None:
            return
        if not messagebox.askyesno(
                "Delete session",
                f"Delete this saved session?\n\n{stats.label(record)}\n\nThis can't be undone.", parent=self._toplevel):
            return
        self._book.delete(str(record.get("id")))
        self._selected_id = None
        self._on_change()
        self.refresh(self._book)

    def close(self) -> None:
        self._shell.close()
