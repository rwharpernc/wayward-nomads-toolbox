"""DataTable: WNTB's replacement for `ttk.Treeview` in tables. A ttk Treeview
can't be restyled on Windows without changing the application-wide ttk
theme (see style.py), so this is built from plain Labels laid out on one
shared grid - which is also what keeps header and body columns aligned.

The API mirrors the small part of Treeview the existing windows use
(`insert`, `set`, `exists`, `clear`, `selection`, double-click) so porting a
window is mostly mechanical. Header click sorts (numbers sort numerically);
rows stripe; hover and selection use the palette. Cell text is clipped to a
per-column character cap (external data is never trusted to be short).

Grouped tables can't use the built-in sort (it would shuffle rows out from
under their group headings), so they pass `on_header` instead: a header click
calls it with the column key, the caller re-inserts its rows in the new order,
and `mark_sorted` draws the arrow.

Grouping: `insert(..., group=True)` makes a collapsible heading row (click
toggles); rows inserted with `parent=<group iid>` sit under it, indented, and
hide when it's collapsed. Use `sortable=False` for grouped tables."""
from __future__ import annotations

import re
import tkinter as tk
from dataclasses import dataclass
from typing import Callable, Optional, Sequence

from . import palette as P
from . import style
from .widgets import ScrollFrame, SlimScrollbar, clip

STRIPE = "#1e232b"
ROW_PX = 40   # generous upper bound on one body row's height (DPI varies), for `visible_rows`
INDENT = "\u2003\u2003"   # two em-spaces
_NUMBER = re.compile(r"^\s*[-+]?\d[\d,]*(\.\d+)?\s*(%|t|ls|ly)?\s*$")


@dataclass(frozen=True)
class Column:
    key: str
    heading: str
    width: int = 100          # minimum pixel width
    anchor: str = "w"         # "w", "e" or "center"
    stretch: bool = False     # takes spare width
    max_chars: int = 48       # hard cap on displayed text


def _sort_value(text: str):
    """Numbers (with thousands separators / small suffixes) sort numerically
    and before text; everything else case-insensitively."""
    if _NUMBER.match(text):
        digits = re.sub(r"[^\d.\-+]", "", text)
        try:
            return (0, float(digits), "")
        except ValueError:
            pass
    return (1, 0.0, text.casefold())


class _TableRow:
    def __init__(self, iid: str, values: list[str], tag: Optional[str],
                 parent: Optional[str], group: bool, opened: bool) -> None:
        self.iid = iid
        self.values = values
        self.tag = tag
        self.parent = parent
        self.group = group
        self.opened = opened
        self.cells: list[tk.Label] = []
        self.index = 0


class DataTable(tk.Frame):
    def __init__(self, parent: tk.Misc, columns: Sequence[Column],
                 on_activate: Optional[Callable[[str], None]] = None,
                 on_select: Optional[Callable[[str], None]] = None,
                 sortable: bool = True, empty_text: str = "", visible_rows: Optional[int] = None,
                 on_header: Optional[Callable[[str], None]] = None) -> None:
        """`visible_rows`: fit the table to its content up to this many rows
        (then scroll), instead of expanding to fill the space available."""
        super().__init__(parent, bg=P.PANE)
        self._columns = list(columns)
        self._on_activate = on_activate
        self._on_select = on_select
        self._sortable = sortable
        self._rows: dict[str, _TableRow] = {}
        self._order: list[str] = []
        self._selected: Optional[str] = None
        self._sort_key: Optional[str] = None
        self._sort_desc = False
        self._tags: dict[str, str] = {}
        self._empty_text = empty_text
        self._max_rows = visible_rows
        self._on_header = on_header
        self._layout_pending = False
        self._signature: Optional[list] = None  # rows last given to set_rows()

        self._header = tk.Frame(self, bg=P.CARD)
        self._header.pack(fill="x", padx=(0, SlimScrollbar.WIDTH))
        self._scroll = ScrollFrame(self, height=visible_rows * ROW_PX if visible_rows else None)
        self._scroll.pack(fill="both", expand=not visible_rows)
        self._empty = tk.Label(self._scroll.body, text=empty_text, fg=P.MUTED, bg=P.PANE, pady=P.PAD)
        self._header_labels: list[tk.Label] = []
        for index, column in enumerate(self._columns):
            for grid in (self._header, self._scroll.body):
                grid.columnconfigure(index, minsize=column.width, weight=1 if column.stretch else 0)
            label = tk.Label(self._header, text=column.heading, fg=P.MUTED, bg=P.CARD, anchor=column.anchor,
                             padx=8, pady=6, font=style.font(P.FONT_BOLD),
                             cursor="hand2" if sortable or on_header else "")
            label.grid(row=0, column=index, sticky="ew")
            if on_header:
                label.bind("<Button-1>", lambda _e, k=column.key: on_header(k))
            elif sortable:
                label.bind("<Button-1>", lambda _e, k=column.key: self.sort_by(k))
            self._header_labels.append(label)

    # --- Treeview-like API ---------------------------------------------------
    def tag_configure(self, tag: str, foreground: str) -> None:
        """Foreground colour for rows inserted with this tag."""
        self._tags[tag] = foreground

    def set_rows(self, rows: Sequence[Sequence[object]]) -> None:
        """Replace the table's rows with `rows`, doing nothing at all when they are the
        same as last time. For a table that is re-filled often (a live window) this
        avoids destroying and rebuilding every cell on each refresh."""
        signature = [tuple(str(v) for v in row) for row in rows]
        if signature == self._signature:
            return
        self.clear()
        for row in rows:
            self.append(row)
        self._signature = signature

    def clear(self) -> None:
        self._signature = None
        for row in self._rows.values():
            for cell in row.cells:
                cell.destroy()
        self._rows.clear()
        self._order.clear()
        self._selected = None
        self._schedule_layout()

    def insert(self, iid: str, values: Sequence[object], tag: Optional[str] = None,
               parent: Optional[str] = None, group: bool = False, open: bool = True) -> None:
        self._signature = None
        row = _TableRow(iid, [str(v) for v in values], tag, parent, group, open)
        self._rows[iid] = row
        self._order.append(iid)
        self._build_cells(row)
        self._schedule_layout()

    def append(self, values: Sequence[object], tag: Optional[str] = None,
               parent: Optional[str] = None, group: bool = False, open: bool = True) -> str:
        """insert() with a generated row id, for rows nothing looks up by id."""
        iid = f"row{len(self._rows)}-{id(values) & 0xFFFF}"
        while iid in self._rows:
            iid += "x"
        self.insert(iid, values, tag, parent, group, open)
        return iid

    def exists(self, iid: str) -> bool:
        return iid in self._rows

    def set(self, iid: str, column_key: str, value: object) -> None:
        row = self._rows.get(iid)
        if row is None:
            return
        index = self._column_index(column_key)
        row.values[index] = str(value)
        row.cells[index].configure(text=self._cell_text(row, index))

    def selection(self) -> list[str]:
        return [self._selected] if self._selected else []

    def select(self, iid: Optional[str], notify: bool = False) -> None:
        if self._selected in self._rows:
            self._paint(self._rows[self._selected], False)
        self._selected = iid if iid in self._rows else None
        if self._selected:
            self._paint(self._rows[self._selected], True)
            if notify and self._on_select:
                self._on_select(self._selected)

    def toggle(self, iid: str) -> None:
        row = self._rows.get(iid)
        if row is not None and row.group:
            row.opened = not row.opened
            row.cells[0].configure(text=self._cell_text(row, 0))
            self._schedule_layout()

    def __len__(self) -> int:
        return len(self._rows)

    # --- sorting -------------------------------------------------------------
    def sort_by(self, key: str) -> None:
        index = self._column_index(key)
        self._sort_desc = (self._sort_key == key) and not self._sort_desc
        self._sort_key = key
        self._order.sort(key=lambda iid: _sort_value(self._rows[iid].values[index]),
                         reverse=self._sort_desc)
        for i, column in enumerate(self._columns):
            arrow = (" ▼" if self._sort_desc else " ▲") if column.key == key else ""
            self._header_labels[i].configure(text=column.heading + arrow)
        self._schedule_layout()

    def mark_sorted(self, key: Optional[str], descending: bool = False) -> None:
        """Draw the sort arrow on one header (None clears them all) - for
        callers that sort their own rows via `on_header`."""
        for i, column in enumerate(self._columns):
            arrow = (" ▼" if descending else " ▲") if column.key == key else ""
            self._header_labels[i].configure(text=column.heading + arrow)

    # --- internals -----------------------------------------------------------
    def _column_index(self, key: str) -> int:
        for index, column in enumerate(self._columns):
            if column.key == key:
                return index
        raise KeyError(key)

    def _cell_text(self, row: _TableRow, index: int) -> str:
        text = row.values[index] if index < len(row.values) else ""
        if row.group and index == 0:
            text = f"{'▾' if row.opened else '▸'}  {text}"
        elif row.parent is not None and index == 0:
            text = INDENT + text   # tk.Label can't take an asymmetric padx, so indent with spaces
        return clip(text, self._columns[index].max_chars)

    def _build_cells(self, row: _TableRow) -> None:
        for index, column in enumerate(self._columns):
            cell = tk.Label(self._scroll.body, text=self._cell_text(row, index), anchor=column.anchor,
                            padx=8, pady=5, bg=P.PANE,
                            fg=P.TEXT if row.group else self._tags.get(row.tag or "", P.TEXT),
                            font=style.font(P.FONT_BOLD if row.group else P.FONT_BODY),
                            cursor="hand2" if row.group else "")
            cell.bind("<Enter>", lambda _e, r=row: self._hover(r, True))
            cell.bind("<Leave>", lambda _e, r=row: self._hover(r, False))
            if row.group:
                cell.bind("<Button-1>", lambda _e, r=row: self.toggle(r.iid))
            else:
                cell.bind("<Button-1>", lambda _e, r=row: self.select(r.iid, notify=True))
                cell.bind("<Double-1>", lambda _e, r=row: self._activate(r))
            row.cells.append(cell)

    def _schedule_layout(self) -> None:
        """Rows are inserted one at a time; lay the grid out once afterwards
        rather than once per insert (which would be quadratic)."""
        if not self._layout_pending:
            self._layout_pending = True
            self.after_idle(self._layout)

    def _is_visible(self, row: _TableRow) -> bool:
        parent = self._rows.get(row.parent) if row.parent else None
        return parent is None or (parent.opened and self._is_visible(parent))

    def _layout(self) -> None:
        self._layout_pending = False
        if not self.winfo_exists():
            return
        self._empty.grid_forget()
        if not self._rows:
            if self._empty_text:
                self._empty.grid(row=0, column=0, columnspan=max(len(self._columns), 1), sticky="w", padx=P.PAD)
            return
        position = 0
        for iid in self._order:
            row = self._rows[iid]
            if not self._is_visible(row):
                for cell in row.cells:
                    cell.grid_forget()
                continue
            row.index = position
            for column_index, cell in enumerate(row.cells):
                cell.grid(row=position, column=column_index, sticky="nsew")
            self._paint(row, iid == self._selected)
            position += 1
        self._sync_widths()

    def _sync_widths(self) -> None:
        """Header and body are separate grids, so a body cell wider than its
        column's minimum would push the body out of step with the header.
        Give both grids every column's widest requirement."""
        self.update_idletasks()
        for index, column in enumerate(self._columns):
            widest = max([column.width, self._header_labels[index].winfo_reqwidth()]
                         + [row.cells[index].winfo_reqwidth() for row in self._rows.values()
                            if index < len(row.cells)])
            for grid in (self._header, self._scroll.body):
                grid.columnconfigure(index, minsize=widest)
        if self._max_rows:
            # Fit the content, up to `visible_rows` rows; beyond that it scrolls.
            natural = self._scroll.body.winfo_reqheight()
            self._scroll._canvas.configure(height=max(1, min(natural, self._max_rows * ROW_PX)))

    def _row_background(self, row: _TableRow, selected: bool, hover: bool = False) -> str:
        if selected:
            return P.SELECT
        if hover:
            return P.HOVER
        if row.group:
            return P.CARD
        return STRIPE if row.index % 2 else P.PANE

    def _paint(self, row: _TableRow, selected: bool, hover: bool = False) -> None:
        colour = self._row_background(row, selected, hover)
        for cell in row.cells:
            cell.configure(bg=colour)

    def _hover(self, row: _TableRow, inside: bool) -> None:
        self._paint(row, row.iid == self._selected, hover=inside)

    def _activate(self, row: _TableRow) -> None:
        self.select(row.iid)
        if self._on_activate:
            self._on_activate(row.iid)
