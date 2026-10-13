"""The Materials window: every material the commander holds, with its type, grade, count, the most the game lets them hold and how much room
is left. A search box, a type filter, a grade filter and "only what is at the limit" narrow the table; the headings sort it. Built on the shared
window kit (plugin/uikit); the counts are `materials.MaterialBook`, which the panel row keeps up to date from the journal. Module-level
show/refresh/close and saved geometry follow notes_window.py."""
from __future__ import annotations

import logging
import os
import tkinter as tk
from typing import List, Optional

from config import appname, config

from . import materials
from .uikit import palette as P
from .uikit.shell import WindowShell
from .uikit.table import Column, DataTable

plugin_name = os.path.basename(os.path.dirname(__file__))
logger = logging.getLogger(f"{appname}.{plugin_name}")

CONFIG_GEOMETRY = "wntb_materials_window_geometry"
DEFAULT_SIZE = (900, 640)
MIN_SIZE = (700, 440)

ALL = "All"

_window: Optional["MaterialsWindow"] = None

_COLUMNS = (
    Column("material", "Material", 240, stretch=True, max_chars=48),
    Column("type", "Type", 110),
    Column("grade", "Grade", 70, anchor="e"),
    Column("held", "Held", 80, anchor="e"),
    Column("limit", "Limit", 80, anchor="e"),
    Column("room", "Room", 80, anchor="e"),
)


def show(parent: tk.Misc, book: materials.MaterialBook) -> None:
    """Open the Materials window, or raise it if it is already open."""
    global _window
    if _window is not None and _window.alive:
        _window.refresh()
        _window.lift()
        return
    _window = MaterialsWindow(parent, book)


def refresh() -> None:
    if _window is not None and _window.alive:
        _window.refresh()


def close() -> None:
    if _window is not None and _window.alive:
        _window.close()


def rows_for(book: materials.MaterialBook, query: str = "", kind: str = ALL, grade: str = ALL, full_only: bool = False) -> List[tuple]:
    """The table rows for what is held: every word of `query` must be in the name (case-folded); `kind` and `grade` are ALL or a value."""
    words = [w for w in query.casefold().split() if w]
    rows = []
    for held in book.held():
        m = held.material
        if kind != ALL and m.type != kind:
            continue
        if grade != ALL and str(m.grade) != grade:
            continue
        if full_only and not held.is_full:
            continue
        if not all(w in m.name.casefold() for w in words):
            continue
        rows.append((m.name, m.type, m.grade or "-", f"{held.count:,}", f"{m.cap:,}" if m.cap else "-", f"{held.room:,}" if m.cap else "-"))
    return rows


class MaterialsWindow:
    def __init__(self, parent: tk.Misc, book: materials.MaterialBook) -> None:
        self._book = book
        self._shell = WindowShell(
            parent, "Materials", "", size=DEFAULT_SIZE, min_size=MIN_SIZE,
            load_geometry=lambda: config.get_str(CONFIG_GEOMETRY) or "",
            save_geometry=lambda geometry: config.set(CONFIG_GEOMETRY, geometry))
        self._shell.window.protocol("WM_DELETE_WINDOW", self.close)

        filters = tk.Frame(self._shell.body, bg=P.BG)
        filters.pack(fill="x", pady=(0, P.PAD_SM))
        tk.Label(filters, text="Search", fg=P.MUTED, bg=P.BG).pack(side="left")
        self._query = tk.StringVar()
        tk.Entry(filters, textvariable=self._query, width=24).pack(side="left", padx=(P.PAD_SM, P.PAD))
        self._kind = tk.StringVar(value=ALL)
        self._grade = tk.StringVar(value=ALL)
        for label, variable, values in (("Type", self._kind, (ALL, *materials.TYPES)),
                                        ("Grade", self._grade, (ALL, "1", "2", "3", "4", "5"))):
            tk.Label(filters, text=label, fg=P.MUTED, bg=P.BG).pack(side="left")
            menu = tk.OptionMenu(filters, variable, *values, command=lambda _v: self._fill())
            menu.configure(bg=P.CARD, fg=P.TEXT, activebackground=P.CARD, activeforeground=P.TEXT, highlightthickness=0, relief="flat")
            menu.pack(side="left", padx=(P.PAD_SM, P.PAD))
        self._full_only = tk.BooleanVar(value=False)
        tk.Checkbutton(filters, text="Only what is at the limit", variable=self._full_only, command=self._fill, fg=P.TEXT, bg=P.BG,
                       selectcolor=P.CARD, activebackground=P.BG, activeforeground=P.TEXT).pack(side="left")
        self._query.trace_add("write", lambda *_: self._fill())

        self._table = DataTable(self._shell.body, _COLUMNS, empty_text="No materials match.")
        self._table.pack(fill="both", expand=True, pady=(0, P.PAD_SM))

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
        totals = self._book.totals()
        self._shell.set_subtitle(
            f"{who}: " + " · ".join(f"{kind} {totals.get(kind, 0):,}" for kind in materials.TYPES) if who else "Waiting for a commander (log in)")
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
        rows = rows_for(self._book, self._query.get(), self._kind.get(), self._grade.get(), self._full_only.get())
        self._table.set_rows(rows)
        note = ("Counts come from the journal: the full list when you log in, then every pick-up, discard, trade, synthesis, engineer "
                "craft and reward. The limit is what the game lets you hold of a grade (300, 250, 200, 150, 100 for grades 1 to 5).")
        if self._book.ready and not self._book.has_counts:
            note = "These are the counts from your last session; they are replaced when you log in to the game. " + note
        self._shell.set_status(f"{len(rows)} shown. {note}")
