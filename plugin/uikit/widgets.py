"""Reusable widgets for WNTB windows. All plain tk/ttk, styled from
palette.py. Anything showing external text goes through `clip()` so a long
name can't blow a pane out."""
from __future__ import annotations

import tkinter as tk
from typing import Callable, Optional, Sequence

from . import palette as P
from . import style


def clip(text: object, limit: int = 40) -> str:
    """Hard character cap with an ellipsis (external data is never trusted
    to be short - see the width-bounding rule in docs/TECHNICAL.md section 5)."""
    text = str(text)
    return text if len(text) <= limit else text[:limit - 1] + "…"


class Card(tk.Frame):
    """A raised panel: flat CARD fill, inner padding."""

    def __init__(self, parent: tk.Misc, pad: int = P.PAD, **kwargs) -> None:
        super().__init__(parent, bg=P.CARD, padx=pad, pady=pad, **kwargs)


class Pill(tk.Label):
    """Small status chip. Always has text, so colour is never the only cue."""

    def __init__(self, parent: tk.Misc, text: str, color: str = P.MUTED, limit: int = 18, **kwargs) -> None:
        bg = kwargs.pop("bg", P.CARD)
        super().__init__(parent, text=f" {clip(text, limit)} ", fg=color, bg=bg,
                         font=style.font(P.FONT_SMALL), highlightthickness=1,
                         highlightbackground=color, highlightcolor=color, **kwargs)


class StatTile(tk.Frame):
    """A big number over a small caption."""

    def __init__(self, parent: tk.Misc, value: str, caption: str, color: str = P.TEXT) -> None:
        super().__init__(parent, bg=P.CARD, padx=P.PAD, pady=P.PAD_SM)
        self._value = tk.Label(self, text=value, fg=color, bg=P.CARD, font=style.font(P.FONT_STAT))
        self._value.pack(anchor="w")
        tk.Label(self, text=caption, fg=P.MUTED, bg=P.CARD,
                 font=style.font(P.FONT_SMALL)).pack(anchor="w")

    def set(self, value: str) -> None:
        self._value.configure(text=value)


def section_header(parent: tk.Misc, text: str, bg: str = P.PANE) -> tk.Label:
    return tk.Label(parent, text=text.upper(), fg=P.MUTED, bg=bg, anchor="w",
                    font=style.font(P.FONT_SMALL), padx=P.PAD, pady=P.PAD_SM)


class ScrollFrame(tk.Frame):
    """A vertically scrolling container; put content in `.body`."""

    def __init__(self, parent: tk.Misc, bg: str = P.PANE, height: Optional[int] = None) -> None:
        super().__init__(parent, bg=bg)
        extra = {"height": height} if height else {}
        self._canvas = tk.Canvas(self, bg=bg, highlightthickness=0, bd=0, **extra)
        bar = SlimScrollbar(self, command=self._canvas.yview)
        self._canvas.configure(yscrollcommand=bar.set)
        bar.pack(side="right", fill="y")
        self._canvas.pack(side="left", fill="both", expand=True)
        self.body = tk.Frame(self._canvas, bg=bg)
        self._window = self._canvas.create_window((0, 0), window=self.body, anchor="nw")
        self.body.bind("<Configure>", lambda _e: self._canvas.configure(
            scrollregion=self._canvas.bbox("all")))
        self._canvas.bind("<Configure>", lambda e: self._canvas.itemconfigure(
            self._window, width=e.width))
        self.bind("<Enter>", self._bind_wheel)
        self.bind("<Leave>", self._unbind_wheel)

    def _bind_wheel(self, _e: tk.Event) -> None:
        self._canvas.bind_all("<MouseWheel>", self._on_wheel)
        self._canvas.bind_all("<Button-4>", lambda _e: self._canvas.yview_scroll(-2, "units"))
        self._canvas.bind_all("<Button-5>", lambda _e: self._canvas.yview_scroll(2, "units"))

    def _unbind_wheel(self, _e: tk.Event) -> None:
        for sequence in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
            self._canvas.unbind_all(sequence)

    def _on_wheel(self, event: tk.Event) -> None:
        self._canvas.yview_scroll(-1 if event.delta > 0 else 1, "units")

    def clear(self) -> None:
        for child in self.body.winfo_children():
            child.destroy()
        self._canvas.yview_moveto(0)


class Row(tk.Frame):
    """One selectable list row: title, optional sub line, right-aligned
    detail, optional pill. Hover/selected colours come from the palette."""

    def __init__(self, parent: tk.Misc, title: str, detail: str = "", sub: str = "",
                 pill: Optional[tuple[str, str]] = None, indent: int = 0,
                 on_click: Optional[Callable[[], None]] = None) -> None:
        super().__init__(parent, bg=P.PANE, padx=P.PAD, pady=4, cursor="hand2")
        self._selected = False
        left = tk.Frame(self, bg=P.PANE)
        left.pack(side="left", fill="x", expand=True, padx=(indent, 0))
        self._title = tk.Label(left, text=clip(title, 34), fg=P.TEXT, bg=P.PANE, anchor="w")
        self._title.pack(anchor="w")
        self._sub: Optional[tk.Label] = None
        if sub:
            self._sub = tk.Label(left, text=clip(sub, 46), fg=P.MUTED, bg=P.PANE, anchor="w",
                                 font=style.font(P.FONT_SMALL))
            self._sub.pack(anchor="w")
        self._detail = tk.Label(self, text=clip(detail, 16), fg=P.MUTED, bg=P.PANE,
                                font=style.font(P.FONT_SMALL))
        self._detail.pack(side="right")
        self._pill: Optional[Pill] = None
        if pill:
            self._pill = Pill(self, pill[0], pill[1], bg=P.PANE)
            self._pill.pack(side="right", padx=(0, 6))
        self._bg_widgets: list[tk.Misc] = [self, left, self._title, self._detail]
        if self._sub:
            self._bg_widgets.append(self._sub)
        if self._pill:
            self._bg_widgets.append(self._pill)
        for widget in self._bg_widgets:
            widget.bind("<Enter>", lambda _e: self._paint(P.HOVER))
            widget.bind("<Leave>", lambda _e: self._paint(P.SELECT if self._selected else P.PANE))
            if on_click:
                widget.bind("<Button-1>", lambda _e: on_click())

    def _paint(self, color: str) -> None:
        for widget in self._bg_widgets:
            widget.configure(bg=color)

    def set_selected(self, selected: bool) -> None:
        self._selected = selected
        self._paint(P.SELECT if selected else P.PANE)


class FoldList(ScrollFrame):
    """Collapsible groups of selectable rows - body types and hotspot
    locations. One row selected at a time; `open_group()` unfolds one."""

    def __init__(self, parent: tk.Misc, on_select: Callable[[str], None],
                 single_open: bool = True) -> None:
        super().__init__(parent)
        self._on_select = on_select
        self._single_open = single_open
        self._groups: dict[str, tuple[tk.Label, tk.Frame, str]] = {}
        self._rows: dict[str, Row] = {}
        self._selected: Optional[str] = None

    def populate(self, groups: Sequence[tuple[str, str, Sequence[dict]]],
                 keep_scroll: bool = False) -> None:
        """groups: (key, heading, rows), each row a dict of Row kwargs
        plus a unique "key". `keep_scroll` restores the scroll position
        after rebuilding (live refreshes shouldn't jump the list)."""
        top = self._canvas.yview()[0] if keep_scroll else 0.0
        self.clear()
        self._groups.clear()
        self._rows.clear()
        self._selected = None
        for key, heading, rows in groups:
            header = tk.Label(self.body, text="", fg=P.MUTED, bg=P.BG, anchor="w",
                              font=style.font(P.FONT_BOLD), padx=P.PAD, pady=6, cursor="hand2")
            header.pack(fill="x", pady=(1, 0))
            container = tk.Frame(self.body, bg=P.PANE)
            self._groups[key] = (header, container, heading)
            header.bind("<Button-1>", lambda _e, k=key: self.toggle(k))
            for spec in rows:
                spec = dict(spec)
                row_key = spec.pop("key")
                row = Row(container, on_click=lambda k=row_key: self.select(k), **spec)
                row.pack(fill="x")
                self._rows[row_key] = row
            self._set_open(key, False)
        if keep_scroll:
            self.after_idle(lambda: self._canvas.yview_moveto(top))

    def _set_open(self, key: str, opened: bool) -> None:
        header, container, heading = self._groups[key]
        header.configure(text=f"{'▾' if opened else '▸'}  {clip(heading, 40)}")
        if opened:
            container.pack(fill="x", after=header)
        else:
            container.pack_forget()

    def open_keys(self) -> list[str]:
        return [key for key in self._groups if self.is_open(key)]

    def is_open(self, key: str) -> bool:
        return self._groups[key][1].winfo_manager() != ""

    def toggle(self, key: str) -> None:
        self.open_group(key, not self.is_open(key))

    def open_group(self, key: str, opened: bool = True) -> None:
        if key not in self._groups:
            return
        if opened and self._single_open:
            for other in self._groups:
                if other != key:
                    self._set_open(other, False)
        self._set_open(key, opened)

    def select(self, key: str, notify: bool = True) -> None:
        if self._selected in self._rows:
            self._rows[self._selected].set_selected(False)
        self._selected = key
        if key in self._rows:
            self._rows[key].set_selected(True)
            if notify:
                self._on_select(key)


class FlatButton(tk.Label):
    """A flat label-button (classic tk buttons and ttk buttons both draw
    native chrome on Windows that ignores our colours). kind: "normal",
    "accent" (primary action) or "danger"."""

    _KINDS = {
        "normal": (P.BUTTON, P.HOVER, P.TEXT),
        "accent": (P.ACCENT, "#ffb957", "#1a1306"),
        "danger": (P.BUTTON, P.HOVER, P.DANGER),
    }

    def __init__(self, parent: tk.Misc, text: str, command: Callable[[], None],
                 kind: str = "normal", **kwargs) -> None:
        self._bg, self._hover, fg = self._KINDS[kind]
        weight = P.FONT_BOLD if kind == "accent" else P.FONT_BODY
        super().__init__(parent, text=text, fg=fg, bg=self._bg, padx=14, pady=6,
                         cursor="hand2", font=style.font(weight), **kwargs)
        self._command = command
        self._enabled = True
        self.bind("<Enter>", lambda _e: self._enabled and self.configure(bg=self._hover))
        self.bind("<Leave>", lambda _e: self.configure(bg=self._bg))
        self.bind("<ButtonRelease-1>", self._on_release)

    def _on_release(self, event: tk.Event) -> None:
        inside = 0 <= event.x < self.winfo_width() and 0 <= event.y < self.winfo_height()
        if self._enabled and inside:
            self._command()

    def set_enabled(self, enabled: bool) -> None:
        self._enabled = enabled
        self.configure(fg=self._KINDS["normal"][2] if enabled else P.FAINT,
                       cursor="hand2" if enabled else "")


class SlimScrollbar(tk.Canvas):
    """A thin dark vertical scrollbar - same `set`/`command` protocol as
    tk.Scrollbar, which on Windows can't be recoloured."""

    WIDTH = 10

    def __init__(self, parent: tk.Misc, command: Callable[..., object]) -> None:
        # height=1: a Canvas defaults to 7 cm tall, which would prop up every container.
        super().__init__(parent, width=self.WIDTH, height=1, bg=P.PANE, highlightthickness=0, bd=0)
        self._command = command
        self._first, self._last = 0.0, 1.0
        self._grab: Optional[float] = None
        self.bind("<Configure>", lambda _e: self._draw())
        self.bind("<Button-1>", self._press)
        self.bind("<B1-Motion>", self._drag)
        self.bind("<ButtonRelease-1>", lambda _e: setattr(self, "_grab", None))

    def set(self, first: object, last: object) -> None:
        self._first, self._last = float(first), float(last)
        self._draw()

    def _draw(self) -> None:
        self.delete("all")
        if self._first <= 0.0 and self._last >= 1.0:
            return  # everything visible: no thumb
        height = max(self.winfo_height(), 1)
        top = self._first * height
        bottom = max(self._last * height, top + 24)
        self.create_rectangle(2, top, self.WIDTH - 2, bottom, fill=P.LINE, outline="")

    def _press(self, event: tk.Event) -> None:
        fraction = event.y / max(self.winfo_height(), 1)
        if self._first <= fraction <= self._last:
            self._grab = fraction - self._first
        else:  # click in the trough: centre the thumb there
            self._grab = (self._last - self._first) / 2
            self._command("moveto", max(0.0, fraction - self._grab))

    def _drag(self, event: tk.Event) -> None:
        if self._grab is not None:
            self._command("moveto", max(0.0, event.y / max(self.winfo_height(), 1) - self._grab))


class Combobox(tk.Frame):
    """Dark dropdown with the parts of ttk.Combobox the dialogs use:
    textvariable, values, state ("readonly" or editable), width, get/set/
    current, configure(values=...), and a <<ComboboxSelected>> event. ttk's
    own combobox can't be recoloured without changing the global ttk theme."""

    _MAX_ROWS = 10

    def __init__(self, parent: tk.Misc, textvariable: Optional[tk.StringVar] = None,
                 values: Sequence[str] = (), state: str = "normal", width: int = 20,
                 **_ignored) -> None:
        super().__init__(parent, bg=P.CARD, highlightthickness=1, highlightbackground=P.LINE,
                         highlightcolor=P.ACCENT)
        self._var = textvariable if textvariable is not None else tk.StringVar()
        self._values = list(values)
        self._readonly = state == "readonly"
        self._popup: Optional[tk.Toplevel] = None
        self._entry = tk.Entry(self, textvariable=self._var, width=width, relief="flat", bd=0,
                               highlightthickness=0, bg=P.CARD, fg=P.TEXT, insertbackground=P.TEXT,
                               readonlybackground=P.CARD, selectbackground=P.SELECT,
                               selectforeground=P.TEXT,
                               state="readonly" if self._readonly else "normal")
        self._entry.pack(side="left", fill="x", expand=True, padx=(6, 0), pady=3)
        self._arrow = tk.Label(self, text="▾", fg=P.MUTED, bg=P.CARD, padx=7, cursor="hand2")
        self._arrow.pack(side="right", fill="y")
        self._arrow.bind("<Button-1>", lambda _e: self._toggle())
        if self._readonly:
            self._entry.bind("<Button-1>", lambda _e: self._toggle())
            self._entry.configure(cursor="hand2")
        self._entry.bind("<Down>", lambda _e: self._open())
        self.bind("<Destroy>", lambda _e: self._close(), add="+")

    # --- ttk.Combobox-compatible surface -------------------------------------
    def get(self) -> str:
        return self._var.get()

    def set(self, value: str) -> None:
        self._var.set(value)

    def current(self, index: Optional[int] = None) -> Optional[int]:
        if index is None:
            try:
                return self._values.index(self._var.get())
            except ValueError:
                return -1
        self._var.set(self._values[index])
        return None

    def configure(self, cnf: Optional[dict] = None, **kwargs) -> object:  # type: ignore[override]
        options = dict(cnf or {}, **kwargs)
        if "values" in options:
            self._values = list(options.pop("values"))
        if "state" in options:
            state = options.pop("state")
            self._readonly = state == "readonly"
            self._entry.configure(state=state)
        return super().configure(**options) if options else None

    config = configure

    def __setitem__(self, key: str, value: object) -> None:
        self.configure(**{key: value})

    # --- popup -----------------------------------------------------------------
    def _toggle(self) -> None:
        if self._popup:
            self._close()
        else:
            self._open()

    def _open(self) -> None:
        if self._popup or not self._values:
            return
        popup = tk.Toplevel(self)
        popup.overrideredirect(True)
        popup.configure(bg=P.LINE)
        listbox = tk.Listbox(popup, height=min(len(self._values), self._MAX_ROWS),
                             exportselection=False, bg=P.CARD, fg=P.TEXT,
                             selectbackground=P.SELECT, selectforeground=P.TEXT,
                             activestyle="none", relief="flat", highlightthickness=0, bd=0,
                             width=max(int(self._entry.cget("width")), 10))
        listbox.pack(padx=1, pady=1)
        for value in self._values:
            listbox.insert("end", value)
        current = self.current()
        if current is not None and current >= 0:
            listbox.selection_set(current)
            listbox.see(current)
        listbox.bind("<ButtonRelease-1>", lambda _e: self._pick(listbox))
        listbox.bind("<Return>", lambda _e: self._pick(listbox))
        popup.bind("<Escape>", lambda _e: self._close())
        popup.geometry(f"+{self.winfo_rootx()}+{self.winfo_rooty() + self.winfo_height()}")
        popup.lift()
        self._popup = popup
        self._outside_binding = self.winfo_toplevel().bind("<Button-1>", self._outside_click, add="+")
        listbox.focus_set()

    def _outside_click(self, event: tk.Event) -> None:
        if self._popup and not str(event.widget).startswith(str(self._popup)) \
                and event.widget not in (self._arrow, self._entry):
            self._close()

    def _pick(self, listbox: tk.Listbox) -> None:
        selection = listbox.curselection()
        if selection:
            self._var.set(self._values[selection[0]])
            self._close()
            self.event_generate("<<ComboboxSelected>>")

    def _close(self) -> None:
        popup, self._popup = self._popup, None
        if popup is not None:
            try:
                popup.destroy()
            except tk.TclError:
                pass


class Tabs(tk.Frame):
    """A flat tab bar with an amber underline on the selected tab.
    `add(title)` returns the tab's content frame. With `wrap=True` the bar
    flows onto extra rows when the tabs don't fit the width (for a variable
    number of tabs with long titles); otherwise it's a single row."""

    def __init__(self, parent: tk.Misc, bg: str = P.BG, wrap: bool = False) -> None:
        super().__init__(parent, bg=bg)
        self._wrap = wrap
        self._bar = tk.Frame(self, bg=bg)
        self._bar.pack(fill="x")
        if wrap:
            self._bar.bind("<Configure>", lambda _e: self._reflow())
        tk.Frame(self, bg=P.LINE, height=1).pack(fill="x")
        self._stage = tk.Frame(self, bg=P.PANE)
        self._stage.pack(fill="both", expand=True)
        self._tabs: list[tuple[tk.Label, tk.Frame, tk.Frame]] = []
        self._cells: list[tk.Frame] = []
        self._visible: list[bool] = []
        self._selected = -1

    def add(self, title: str) -> tk.Frame:
        index = len(self._tabs)
        cell = tk.Frame(self._bar, bg=P.BG)
        if self._wrap:
            self.after_idle(self._reflow)
        else:
            cell.pack(side="left")
        label = tk.Label(cell, text=title.upper(), bg=P.BG, fg=P.MUTED, padx=16, pady=8, cursor="hand2",
                         font=style.font(P.FONT_BOLD))
        label.pack()
        underline = tk.Frame(cell, bg=P.BG, height=2)
        underline.pack(fill="x")
        label.bind("<Button-1>", lambda _e, i=index: self.select(i))
        content = tk.Frame(self._stage, bg=P.PANE)
        self._tabs.append((label, underline, content))
        self._cells.append(cell)
        self._visible.append(True)
        if self._selected < 0:
            self.select(0)
        return content

    @property
    def selected(self) -> int:
        return self._selected

    def _reflow(self) -> None:
        """Wrapping bars only: lay the visible tabs out in rows that fit."""
        if not self.winfo_exists():
            return
        width = self._bar.winfo_width()
        if width <= 1:
            return  # not laid out yet; <Configure> calls back once it is
        used = row = column = 0
        for cell, shown in zip(self._cells, self._visible):
            if not shown:
                cell.grid_forget()
                continue
            needed = cell.winfo_reqwidth()
            if column and used + needed > width:
                row, used, column = row + 1, 0, 0
            cell.grid(row=row, column=column, sticky="w")
            used += needed
            column += 1

    def set_tab_visible(self, index: int, visible: bool) -> None:
        """Show or hide a tab (e.g. a Carrier tab only once you own one). Hiding
        the selected tab moves the selection to the first tab still shown."""
        if self._visible[index] == visible:
            return
        self._visible[index] = visible
        if visible:
            if self._wrap:
                self._reflow()
            else:
                self._cells[index].pack(side="left")
        else:
            if self._wrap:
                self._cells[index].grid_forget()
                self._reflow()
            else:
                self._cells[index].pack_forget()
            if self._selected == index:
                self.select(next(i for i, shown in enumerate(self._visible) if shown))

    def select(self, index: int) -> None:
        for i, (label, underline, content) in enumerate(self._tabs):
            active = i == index
            label.configure(fg=P.TEXT if active else P.MUTED)
            underline.configure(bg=P.ACCENT if active else P.BG)
            if active:
                content.pack(fill="both", expand=True)
            else:
                content.pack_forget()
        self._selected = index


def field_grid(parent: tk.Misc, row: int, pairs: Sequence[tuple[str, str]], bg: str = P.PANE) -> None:
    """One row of label: value pairs (muted bold label, plain value) in a
    grid, so values line up instead of being spaced with runs of blanks."""
    column = 0
    for label, value in pairs:
        tk.Label(parent, text=label, fg=P.MUTED, bg=bg, font=style.font(P.FONT_BOLD)).grid(
            row=row, column=column, sticky="w", padx=(0 if column == 0 else 28, 6), pady=2)
        tk.Label(parent, text=clip(value, 60), fg=P.TEXT, bg=bg).grid(row=row, column=column + 1, sticky="w", pady=2)
        column += 2


class ProgressBar(tk.Canvas):
    """A flat capacity bar: `set(percent, colour)`."""

    def __init__(self, parent: tk.Misc, width: int = 220, height: int = 10, bg: str = P.PANE) -> None:
        super().__init__(parent, width=width, height=height, bg=bg, highlightthickness=0, bd=0)
        self._percent = 0.0
        self._colour = P.INFO
        self.bind("<Configure>", lambda _e: self._draw())

    def set(self, percent: float, colour: str = P.INFO) -> None:
        self._percent = max(0.0, min(100.0, percent))
        self._colour = colour
        self._draw()

    def _draw(self) -> None:
        self.delete("all")
        width, height = self.winfo_width(), self.winfo_height()
        self.create_rectangle(0, 0, width, height, fill=P.BG, outline="")
        if self._percent > 0:
            self.create_rectangle(0, 0, width * self._percent / 100, height, fill=self._colour, outline="")


def suggestions(values: Sequence[str], text: str, limit: int = 200) -> list[str]:
    """Entries of `values` matching what has been typed, best first: names
    that start with it, then names that merely contain it (case-insensitive,
    original order kept within each group). Empty text matches everything."""
    needle = text.strip().casefold()
    if not needle:
        return list(values)[:limit]
    starts = [v for v in values if v.casefold().startswith(needle)]
    contains = [v for v in values if needle in v.casefold() and not v.casefold().startswith(needle)]
    return (starts + contains)[:limit]


class SuggestEntry(tk.Frame):
    """A text box that suggests from a list as you type, with a drop-arrow
    that shows the whole list. Unlike `Combobox` its popup never takes the
    keyboard focus, so you can keep typing while it filters. Down/Up move
    through the suggestions, Enter takes the highlighted one (or the typed
    text when none is highlighted) and calls `on_submit`, Escape closes the
    list. The text isn't restricted to the list: any typed name is allowed.

    `values()` is asked for the list each time the popup opens or the text
    changes, so it can reflect data that changed since the box was built."""

    _MAX_ROWS = 10

    def __init__(self, parent: tk.Misc, textvariable: tk.StringVar, values: Callable[[], Sequence[str]],
                 on_submit: Callable[[], None], width: int = 28) -> None:
        super().__init__(parent, bg=P.CARD, highlightthickness=1, highlightbackground=P.LINE,
                         highlightcolor=P.ACCENT)
        self._var = textvariable
        self._values = values
        self._on_submit = on_submit
        self._popup: Optional[tk.Toplevel] = None
        self._listbox: Optional[tk.Listbox] = None
        self._outside_binding: Optional[str] = None
        self.entry = tk.Entry(self, textvariable=textvariable, width=width, relief="flat", bd=0,
                              highlightthickness=0, bg=P.CARD, fg=P.TEXT, insertbackground=P.TEXT,
                              selectbackground=P.SELECT, selectforeground=P.TEXT)
        self.entry.pack(side="left", fill="x", expand=True, padx=(6, 0), pady=3)
        self._arrow = tk.Label(self, text="▾", fg=P.MUTED, bg=P.CARD, padx=7, cursor="hand2")
        self._arrow.pack(side="right", fill="y")
        self._arrow.bind("<Button-1>", lambda _e: self._toggle_all())
        self.entry.bind("<KeyRelease>", self._on_key)
        self.entry.bind("<Down>", lambda _e: self._move(1))
        self.entry.bind("<Up>", lambda _e: self._move(-1))
        self.entry.bind("<Return>", self._on_return)
        self.entry.bind("<Escape>", lambda _e: self._close())
        self.entry.bind("<FocusOut>", lambda _e: self.after(150, self._close_if_unfocused))
        self.bind("<Destroy>", lambda _e: self._close(), add="+")

    # --- typing ----------------------------------------------------------------
    def _on_key(self, event: tk.Event) -> None:
        if event.keysym in ("Return", "Escape", "Up", "Down", "Tab", "Shift_L", "Shift_R",
                            "Control_L", "Control_R", "Alt_L", "Alt_R"):
            return
        self._show(suggestions(self._values(), self._var.get()))

    def _on_return(self, _event: tk.Event) -> str:
        picked = self._selected()
        if picked is not None:
            self._var.set(picked)
        self._close()
        self._on_submit()
        return "break"

    def _toggle_all(self) -> None:
        if self._popup:
            self._close()
        else:
            self.entry.focus_set()
            self._show(list(self._values()))

    def _move(self, step: int) -> str:
        if not self._popup:
            self._show(suggestions(self._values(), self._var.get()))
        listbox = self._listbox
        if listbox is not None and listbox.size():
            current = listbox.curselection()
            index = (current[0] + step) if current else (0 if step > 0 else listbox.size() - 1)
            index = max(0, min(listbox.size() - 1, index))
            listbox.selection_clear(0, "end")
            listbox.selection_set(index)
            listbox.see(index)
        return "break"

    def _selected(self) -> Optional[str]:
        if self._listbox is None:
            return None
        selection = self._listbox.curselection()
        return self._listbox.get(selection[0]) if selection else None

    # --- popup -----------------------------------------------------------------
    def _show(self, items: Sequence[str]) -> None:
        if not items:
            self._close()
            return
        if not self._popup:
            popup = tk.Toplevel(self)
            popup.overrideredirect(True)
            popup.configure(bg=P.LINE)
            listbox = tk.Listbox(popup, exportselection=False, bg=P.CARD, fg=P.TEXT,
                                 selectbackground=P.SELECT, selectforeground=P.TEXT, activestyle="none",
                                 relief="flat", highlightthickness=0, bd=0)
            listbox.pack(padx=1, pady=1, fill="both", expand=True)
            listbox.bind("<ButtonRelease-1>", lambda _e: self._pick())
            self._popup, self._listbox = popup, listbox
            self._outside_binding = self.winfo_toplevel().bind("<Button-1>", self._outside_click, add="+")
        listbox = self._listbox
        assert listbox is not None and self._popup is not None
        listbox.delete(0, "end")
        for item in items:
            listbox.insert("end", item)
        listbox.configure(height=min(len(items), self._MAX_ROWS))
        self._popup.update_idletasks()  # X11 reports a stale requested height until layout has run
        self._popup.geometry(f"{self.winfo_width()}x{listbox.winfo_reqheight() + 2}"
                             f"+{self.winfo_rootx()}+{self.winfo_rooty() + self.winfo_height()}")
        self._popup.lift()

    def _pick(self) -> None:
        picked = self._selected()
        if picked is not None:
            self._var.set(picked)
            self._close()
            self._on_submit()

    def _outside_click(self, event: tk.Event) -> None:
        if self._popup and not str(event.widget).startswith(str(self._popup)) \
                and event.widget not in (self._arrow, self.entry):
            self._close()

    def _close_if_unfocused(self) -> None:
        """FocusOut can fire spuriously (window managers differ); only close
        when the entry really has lost the keyboard."""
        try:
            focused = self.focus_get()
        except (KeyError, tk.TclError):  # focus_get can raise for popup-menu style windows
            focused = None
        if focused is not self.entry:
            self._close()

    def _close(self) -> None:
        popup, self._popup, self._listbox = self._popup, None, None
        if self._outside_binding is not None:
            try:
                self.winfo_toplevel().unbind("<Button-1>", self._outside_binding)
            except tk.TclError:
                pass
            self._outside_binding = None
        if popup is not None:
            try:
                popup.destroy()
            except tk.TclError:
                pass
