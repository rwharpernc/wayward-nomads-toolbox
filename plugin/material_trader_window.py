"""The Material trader window: find the closest station that trades Raw, Manufactured or Encoded materials, and see what you hold of that type.

Pick a type (a trader swaps materials within one category), how far to look and the smallest landing pad you need, check the system to search
from (it starts as the one you are in; type another to plan ahead) and press **Find**. The results list the closest stations first with whether they
are in space or on a surface, how far from the arrival star and the largest pad; double-click a row to copy its system name for the galaxy map.
Above them, the materials you hold of that type by grade, with how many are at the game's limit, so you can see what is worth swapping.

The only thing that goes online is the search: the system name and the type, to Spansh, when you press Find (`material_traders.py`). Built on the
shared window kit (plugin/uikit); the lookup runs on a worker thread and the result is picked up by an after() poll, so no widget is touched off
the main thread. Module-level show/refresh/close and saved geometry follow notes_window.py; `find_traders` is a module-level name so tests can
replace it."""
from __future__ import annotations

import logging
import os
import queue
import threading
import tkinter as tk
from typing import Any, Dict, List, Optional, Tuple

from config import appname, config

from . import material_traders, materials, panelkit
from .uikit import palette as P
from .uikit import style
from .uikit.shell import WindowShell
from .uikit.table import Column, DataTable
from .uikit.widgets import Combobox, FlatButton, clip

plugin_name = os.path.basename(os.path.dirname(__file__))
logger = logging.getLogger(f"{appname}.{plugin_name}")

CONFIG_GEOMETRY = "wntb_material_trader_window_geometry"
DEFAULT_SIZE = (980, 640)
MIN_SIZE = (780, 480)
POLL_MS = 200
ANY_DISTANCE = "Any distance"

find_traders = material_traders.find

_window: Optional["MaterialTraderWindow"] = None

_COLUMNS = (
    Column("station", "Station", 220, stretch=True, max_chars=44),
    Column("system", "System", 200, max_chars=36),
    Column("place", "Where", 260, stretch=True, max_chars=56),
    Column("distance", "Distance (ly)", 110, anchor="e"),
    Column("pad", "Largest pad", 100),
)


def show(parent: tk.Misc, book: materials.MaterialBook, ctx: Any) -> None:
    """Open the Material trader window, or raise it if it is already open. `ctx.system()` says which system the commander is in."""
    global _window
    if _window is not None and _window.alive:
        _window.refresh()
        _window.lift()
        return
    _window = MaterialTraderWindow(parent, book, ctx)


def refresh() -> None:
    if _window is not None and _window.alive:
        _window.refresh()


def close() -> None:
    if _window is not None and _window.alive:
        _window.close()


def radius_choices() -> List[Tuple[str, Optional[float]]]:
    return [(f"{r:,} ly", float(r)) for r in material_traders.RADIUS_CHOICES] + [(ANY_DISTANCE, None)]


def default_type(book: materials.MaterialBook) -> str:
    """The type most worth a trip: the one with the most materials at the game's limit, else the one with the most pieces, else Raw."""
    best, best_score = "Raw", (0, 0)
    for kind in materials.TYPES:
        score = (len([h for h in book.full() if h.material.type == kind]), sum(g.pieces for g in book.grade_summary(kind)))
        if score > best_score:
            best, best_score = kind, score
    return best


def holdings_text(book: materials.MaterialBook, kind: str) -> str:
    """What is held of `kind` by grade, one grade per line, or a line saying nothing is held."""
    lines = book.grade_summary(kind)
    if not lines:
        return f"You hold no {kind} materials with a known grade."
    out = []
    for g in lines:
        limit = f" ({g.at_limit} at the limit)" if g.at_limit else ""
        out.append(f"Grade {g.grade}: {g.pieces:,} pieces in {g.materials} material{'s' if g.materials != 1 else ''}{limit}")
    return "\n".join(out)


class MaterialTraderWindow:
    def __init__(self, parent: tk.Misc, book: materials.MaterialBook, ctx: Any) -> None:
        self._book = book
        self._ctx = ctx
        self._busy = False
        self._results: "queue.Queue[Tuple[str, Any]]" = queue.Queue()
        self._shown: Dict[str, material_traders.Trader] = {}

        self._shell = WindowShell(
            parent, "Material trader", "", size=DEFAULT_SIZE, min_size=MIN_SIZE,
            load_geometry=lambda: config.get_str(CONFIG_GEOMETRY) or "",
            save_geometry=lambda geometry: config.set(CONFIG_GEOMETRY, geometry))
        self._shell.window.protocol("WM_DELETE_WINDOW", self.close)

        body = self._shell.body
        row = tk.Frame(body, bg=P.BG)
        row.pack(fill="x", pady=(0, P.PAD_SM))
        self._kind = tk.StringVar(value=default_type(book))
        self._radius_choices = radius_choices()
        self._radius = tk.StringVar(value=f"{material_traders.DEFAULT_RADIUS_LY:,} ly")
        self._pad = tk.StringVar(value=material_traders.PAD_CHOICES[0][1])
        for label, variable, values, width in (("Type", self._kind, list(materials.TYPES), 14),
                                               ("Within", self._radius, [name for name, _ in self._radius_choices], 14),
                                               ("Pad", self._pad, [name for _, name in material_traders.PAD_CHOICES], 18)):
            tk.Label(row, text=label, fg=P.MUTED, bg=P.BG).pack(side="left")
            box = Combobox(row, textvariable=variable, values=values, state="readonly", width=width)
            box.pack(side="left", padx=(P.PAD_SM, P.PAD))
            if variable is self._kind:
                box.bind("<<ComboboxSelected>>", lambda _e: self._show_holdings())

        origin = tk.Frame(body, bg=P.BG)
        origin.pack(fill="x", pady=(0, P.PAD_SM))
        tk.Label(origin, text="Search from", fg=P.MUTED, bg=P.BG).pack(side="left")
        self._origin = tk.StringVar(value=ctx.system())
        entry = tk.Entry(origin, textvariable=self._origin, width=34)
        entry.pack(side="left", padx=(P.PAD_SM, P.PAD_SM))
        entry.bind("<Return>", lambda _e: self._find())
        FlatButton(origin, "Here", self._fill_here).pack(side="left")
        self._find_button = FlatButton(origin, "Find", self._find, kind="accent")
        self._find_button.pack(side="left", padx=(P.PAD, 0))

        self._holdings = tk.Label(body, text="", fg=P.TEXT, bg=P.BG, anchor="w", justify="left")
        self._holdings.pack(fill="x", pady=(0, P.PAD_SM))

        self._heading = tk.Label(body, text="", fg=P.MUTED, bg=P.BG, anchor="w", font=style.font(P.FONT_BOLD))
        self._heading.pack(fill="x")
        self._table = DataTable(body, _COLUMNS, on_activate=self._copy_system, sortable=False, visible_rows=10,
                                empty_text="Press Find to look for the closest material trader.")
        self._table.pack(fill="x", pady=(0, P.PAD_SM))

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

    def _on_book_changed(self) -> None:
        try:
            if self.alive:
                self._show_holdings()
        except tk.TclError:
            pass   # the window went away between the check and the redraw

    def refresh(self) -> None:
        if not self.alive:
            return
        who = self._book.commander
        self._shell.set_subtitle(who or "Waiting for a commander (log in)")
        self._show_holdings()
        if not self._shell._status.cget("text"):
            self._shell.set_status("A material trader swaps materials within one category. Pressing Find sends Spansh the system name and the "
                                   "type, nothing else.")

    def _show_holdings(self) -> None:
        self._holdings.configure(text=holdings_text(self._book, self._kind.get()))

    def _say(self, text: str) -> None:
        self._shell.set_status(text)

    def _fill_here(self) -> None:
        self._origin.set(self._ctx.system())

    # --- the lookup ---------------------------------------------------------------------------------------------------

    def _find(self) -> None:
        if self._busy:
            return
        origin = " ".join(self._origin.get().split())
        if not origin:
            self._say("Type the system to search from, or press Here (your system is not known yet).")
            return
        radius = dict(self._radius_choices).get(self._radius.get(), float(material_traders.DEFAULT_RADIUS_LY))
        pad = next((key for key, name in material_traders.PAD_CHOICES if name == self._pad.get()), material_traders.PAD_ANY)
        kind = self._kind.get()
        self._busy = True
        self._find_button.set_enabled(False)
        self._say(f"Asking Spansh for the closest {kind} material trader near {clip(origin, 40)}...")
        threading.Thread(target=self._worker, args=(origin, kind, radius, pad), daemon=True).start()
        self._shell.window.after(POLL_MS, self._poll)

    def _worker(self, origin: str, kind: str, radius: Optional[float], pad: str) -> None:
        """Runs off the main thread: it must not touch any Tk widget."""
        try:
            self._results.put(("ok", find_traders(origin, kind, radius, pad)))
        except ValueError as err:
            self._results.put(("refused", str(err)))
        except Exception:
            logger.exception("Material trader lookup failed")
            self._results.put(("failed", "Spansh could not be reached. Check your connection and try again (see the EDMC log)."))

    def _poll(self) -> None:
        """Runs on the main thread via after(): safe to touch widgets."""
        try:
            outcome, payload = self._results.get_nowait()
        except queue.Empty:
            if self.alive and self._busy:
                self._shell.window.after(POLL_MS, self._poll)
            return
        self._busy = False
        if not self.alive:
            return
        self._find_button.set_enabled(True)
        if outcome != "ok":
            self._say(str(payload))
            return
        self._fill_results(payload)

    def _fill_results(self, result: material_traders.Result) -> None:
        self._table.clear()
        self._shown = {}
        limit = f"within {result.radius_ly:,.0f} ly" if result.radius_ly is not None else "at any distance"
        for number, trader in enumerate(result.traders):
            iid = f"t{number}"
            self._shown[iid] = trader
            self._table.insert(iid, (clip(trader.station, 44), clip(trader.system, 36), clip(material_traders.describe_place(trader), 56),
                                     f"{trader.distance_ly:,.1f}", trader.pad))
        self._heading.configure(text=f"{result.trader_type} material traders {limit} of {clip(result.reference, 40)}")
        if result.traders:
            self._say(f"{len(result.traders)} found, closest first. Double-click a row to copy its system name.")
        else:
            self._say(f"No {result.trader_type} material trader {limit}. Try a longer distance or a smaller pad.")

    def _copy_system(self, iid: str) -> None:
        trader = self._shown.get(iid)
        if trader is not None:
            ok = panelkit.copy_to_clipboard(self._shell.window, trader.system)
            self._say(f"Copied {trader.system}." if ok else "Could not reach the clipboard.")
