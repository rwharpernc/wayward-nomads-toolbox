"""
A small type-ahead box for EDMC's main panel: an Entry with a suggestion list that
fills in as you type (trade_commodities.suggest). Plain tk widgets, so EDMC's theme
colours it like everything else (the dark uikit Combobox is for pop-out dialogs).

Sizing: the Entry has a fixed character width and the suggestion list is a separate
borderless window with a fixed row count, so nothing here can widen EDMC's main window.

Keys: type to filter, Down/Up to move, Enter or a click to pick, Escape to close.
Focusing the empty box lists the preferred names (what you carry, what this station buys).
"""
from __future__ import annotations

import tkinter as tk
from typing import Callable, Iterable, List, Optional

from . import trade_commodities

_ROWS = 8
_WIDTH = 24


class CommodityEntry(tk.Frame):
    def __init__(self, parent: tk.Misc, preferred: Callable[[], Iterable[str]],
                 on_submit: Optional[Callable[[], None]] = None) -> None:
        super().__init__(parent)
        self._preferred = preferred
        self._on_submit = on_submit
        self._var = tk.StringVar()
        self._popup: Optional[tk.Toplevel] = None
        self._list: Optional[tk.Listbox] = None
        self._matches: List[str] = []
        self._entry = tk.Entry(self, textvariable=self._var, width=_WIDTH)
        self._entry.pack(side=tk.LEFT)
        self._entry.bind("<KeyRelease>", self._on_key)
        self._entry.bind("<FocusIn>", lambda _e: self._show())
        self._entry.bind("<Down>", lambda _e: self._move(1))
        self._entry.bind("<Up>", lambda _e: self._move(-1))
        self._entry.bind("<Return>", self._on_return)
        self._entry.bind("<Escape>", lambda _e: self._close())
        self._entry.bind("<FocusOut>", lambda _e: self.after(150, self._close))  # after a list click lands
        self.bind("<Destroy>", lambda _e: self._close(), add="+")

    # --- value ---------------------------------------------------------------

    def get(self) -> str:
        return self._var.get().strip()

    def set(self, value: str) -> None:
        self._var.set(value)

    # --- suggestions -----------------------------------------------------------

    def _on_key(self, event: tk.Event) -> None:
        if event.keysym in ("Return", "Escape", "Up", "Down", "Tab", "Left", "Right", "Shift_L", "Shift_R"):
            return
        self._show()

    def _show(self) -> None:
        self._matches = trade_commodities.suggest(self._var.get(), list(self._preferred()), limit=_ROWS)
        if not self._matches or (len(self._matches) == 1 and self._matches[0].lower() == self.get().lower()):
            self._close()
            return
        if self._popup is None:
            popup = tk.Toplevel(self)
            popup.overrideredirect(True)
            self._list = tk.Listbox(popup, height=_ROWS, width=_WIDTH, exportselection=False, activestyle="none")
            self._list.pack()
            self._list.bind("<ButtonRelease-1>", lambda _e: self._pick())
            self._popup = popup
        assert self._list is not None
        self._list.configure(height=len(self._matches))
        self._list.delete(0, tk.END)
        for name in self._matches:
            self._list.insert(tk.END, name)
        self._popup.geometry(f"+{self._entry.winfo_rootx()}+{self._entry.winfo_rooty() + self._entry.winfo_height()}")
        self._popup.lift()

    def _move(self, step: int) -> str:
        if self._list is None:
            self._show()
        if self._list is None:
            return "break"
        current = self._list.curselection()
        index = (current[0] + step) if current else (0 if step > 0 else len(self._matches) - 1)
        index = max(0, min(len(self._matches) - 1, index))
        self._list.selection_clear(0, tk.END)
        self._list.selection_set(index)
        self._list.see(index)
        return "break"

    def _pick(self) -> None:
        if self._list is None:
            return
        selection = self._list.curselection()
        if selection:
            self._var.set(self._matches[selection[0]])
        self._close()
        self._entry.icursor(tk.END)

    def _on_return(self, _event: tk.Event) -> str:
        if self._list is not None and self._list.curselection():
            self._pick()
        else:
            self._close()
            if self._on_submit is not None:
                self._on_submit()
        return "break"

    def _close(self) -> None:
        popup, self._popup, self._list = self._popup, None, None
        if popup is not None:
            try:
                popup.destroy()
            except tk.TclError:
                pass
