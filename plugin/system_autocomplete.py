"""
Type-ahead for any box that takes a system name: `attach(entry, var)` adds a short list of suggestions under the box as you type. Down and Up move
through it, Enter (or a click) takes the highlighted one, Escape closes it. Enter with nothing highlighted goes on to whatever the box already did,
so a box that adds or searches on Enter still does. The box itself is not changed, so it keeps its place and its look: the list takes its colors from
the box.

The suggestions are the systems you have been in and the names WNTB already holds, from two letters on, and, when **Suggest system names from Spansh
while typing** is ticked (Settings → Window), systems from Spansh's search, from three letters on, after a short pause (see `system_names.py`). The
Spansh call runs on a worker thread, so typing never waits for it.
"""
from __future__ import annotations

import logging
import os
import queue
import threading
import tkinter as tk
from typing import Callable, List, Optional, Tuple

from config import appname

from . import system_names
from .uikit.widgets import suggestions

plugin_name = os.path.basename(os.path.dirname(__file__))
logger = logging.getLogger(f"{appname}.{plugin_name}")

MAX_ROWS = 8
DEBOUNCE_MS = 350
POLL_MS = 150
_IGNORED_KEYS = {"Return", "Escape", "Up", "Down", "Tab", "Shift_L", "Shift_R", "Control_L", "Control_R", "Alt_L", "Alt_R", "Left", "Right",
                 "Home", "End", "Caps_Lock", "ISO_Left_Tab"}


def attach(entry: tk.Entry, var: Optional[tk.StringVar] = None, on_pick: Optional[Callable[[], None]] = None) -> "Autocomplete":
    """Give `entry` system-name suggestions. `var` is its text variable if it has one; `on_pick()` is called after a suggestion is taken."""
    return Autocomplete(entry, var, on_pick)


class Autocomplete:
    def __init__(self, entry: tk.Entry, var: Optional[tk.StringVar], on_pick: Optional[Callable[[], None]]) -> None:
        self._entry = entry
        self._var = var
        self._on_pick = on_pick
        self._popup: Optional[tk.Toplevel] = None
        self._listbox: Optional[tk.Listbox] = None
        self._answers: "queue.Queue[Tuple[str, List[str]]]" = queue.Queue()
        self._timer: Optional[str] = None
        self._waiting = 0
        # A bindtag ahead of the box's own, so Enter, Up, Down and Escape are seen first and can be taken ("break") when a suggestion is
        # highlighted, while the box's own bindings still run when it is not.
        self._tag = f"WntbSystemSuggest{id(self)}"
        entry.bindtags((self._tag,) + entry.bindtags())
        for sequence, handler in (("<KeyRelease>", self._on_key), ("<Return>", self._on_return), ("<Down>", lambda e: self._move(1)),
                                  ("<Up>", lambda e: self._move(-1)), ("<Escape>", self._on_escape), ("<FocusOut>", self._on_focus_out)):
            entry.bind_class(self._tag, sequence, handler)
        entry.bind("<Destroy>", lambda _e: self.close(), add="+")

    # --- the text --------------------------------------------------------------------------------------------------------

    def _text(self) -> str:
        return " ".join((self._var.get() if self._var is not None else self._entry.get()).split())

    def _set_text(self, text: str) -> None:
        if self._var is not None:
            self._var.set(text)
        else:
            self._entry.delete(0, "end")
            self._entry.insert(0, text)
        self._entry.icursor("end")

    def matches(self) -> List[str]:
        """The suggestions for what is typed now: known names first, then Spansh's, no repeats, none identical to the text."""
        text = self._text()
        if len(text) < system_names.MIN_LOCAL_CHARS:
            return []
        pool = system_names.local()
        if system_names.remote_enabled():
            pool = pool + system_names.cached(text)
        out: List[str] = []
        seen = set()
        for name in suggestions(pool, text, limit=60):
            if system_names.key(name) not in seen:
                seen.add(system_names.key(name))
                out.append(name)
        if len(out) == 1 and system_names.key(out[0]) == system_names.key(text) and out[0] == text:
            return []
        return out[:MAX_ROWS * 2]

    # --- typing and the Spansh call ----------------------------------------------------------------------------------------

    def _on_key(self, event: tk.Event) -> None:
        if event.keysym in _IGNORED_KEYS:
            return
        self.refresh()
        text = self._text()
        if system_names.remote_enabled() and len(text) >= system_names.MIN_REMOTE_CHARS and not system_names.is_cached(text):
            if self._timer is not None:
                self._entry.after_cancel(self._timer)
            self._timer = self._entry.after(DEBOUNCE_MS, lambda t=text: self._ask(t))

    def _ask(self, text: str) -> None:
        self._timer = None
        if self._text() != text or system_names.is_cached(text):
            return
        self._waiting += 1
        threading.Thread(target=self._worker, args=(text,), daemon=True).start()
        self._entry.after(POLL_MS, self._poll)

    def _worker(self, text: str) -> None:
        """Runs off the main thread: it must not touch any Tk widget."""
        self._answers.put((text, system_names.fetch(text)))

    def _poll(self) -> None:
        """Runs on the main thread via after(): safe to touch widgets."""
        try:
            self._answers.get_nowait()
        except queue.Empty:
            if self._waiting:
                try:
                    self._entry.after(POLL_MS, self._poll)
                except tk.TclError:
                    pass
            return
        self._waiting = max(0, self._waiting - 1)
        try:
            if self._entry.focus_get() is self._entry:
                self.refresh()
        except (KeyError, tk.TclError):
            pass

    # --- the list --------------------------------------------------------------------------------------------------------

    def refresh(self) -> None:
        items = self.matches()
        if items:
            self._show(items)
        else:
            self.close()

    def _colors(self) -> Tuple[str, str, str, str]:
        def pick(option: str, fallback: str) -> str:
            try:
                return str(self._entry.cget(option)) or fallback
            except tk.TclError:
                return fallback
        return pick("bg", "white"), pick("fg", "black"), pick("selectbackground", "#3399ff"), pick("selectforeground", "white")

    def _show(self, items: List[str]) -> None:
        bg, fg, select_bg, select_fg = self._colors()
        if self._popup is None:
            popup = tk.Toplevel(self._entry)
            popup.overrideredirect(True)
            popup.configure(bg=fg)
            listbox = tk.Listbox(popup, exportselection=False, bg=bg, fg=fg, selectbackground=select_bg, selectforeground=select_fg,
                                 activestyle="none", relief="flat", highlightthickness=0, bd=0)
            listbox.pack(padx=1, pady=1, fill="both", expand=True)
            listbox.bind("<ButtonRelease-1>", lambda _e: self._take(self._highlighted()))
            self._popup, self._listbox = popup, listbox
        listbox = self._listbox
        assert listbox is not None and self._popup is not None
        listbox.delete(0, "end")
        for item in items:
            listbox.insert("end", item)
        listbox.configure(height=min(len(items), MAX_ROWS))
        self._popup.update_idletasks()
        entry = self._entry
        self._popup.geometry(f"{max(entry.winfo_width(), 160)}x{listbox.winfo_reqheight() + 2}"
                             f"+{entry.winfo_rootx()}+{entry.winfo_rooty() + entry.winfo_height()}")
        self._popup.lift()

    def close(self) -> None:
        popup, self._popup, self._listbox = self._popup, None, None
        if popup is not None:
            try:
                popup.destroy()
            except tk.TclError:
                pass

    def _highlighted(self) -> Optional[str]:
        if self._listbox is None:
            return None
        selection = self._listbox.curselection()
        return self._listbox.get(selection[0]) if selection else None

    def _take(self, name: Optional[str]) -> None:
        if not name:
            return
        self._set_text(name)
        self.close()
        self._entry.focus_set()
        if self._on_pick is not None:
            self._on_pick()

    # --- keys ----------------------------------------------------------------------------------------------------------------

    def _move(self, step: int) -> Optional[str]:
        if self._listbox is None:
            self.refresh()
        listbox = self._listbox
        if listbox is None or not listbox.size():
            return None
        current = listbox.curselection()
        index = (current[0] + step) if current else (0 if step > 0 else listbox.size() - 1)
        index = max(0, min(listbox.size() - 1, index))
        listbox.selection_clear(0, "end")
        listbox.selection_set(index)
        listbox.see(index)
        return "break"

    def _on_return(self, _event: tk.Event) -> Optional[str]:
        picked = self._highlighted()
        if picked is None:
            self.close()
            return None          # nothing chosen: the box's own Enter handling goes ahead
        self._take(picked)
        return "break"

    def _on_escape(self, _event: tk.Event) -> Optional[str]:
        if self._popup is None:
            return None
        self.close()
        return "break"

    def _on_focus_out(self, _event: tk.Event) -> None:
        self._entry.after(150, self._close_if_unfocused)

    def _close_if_unfocused(self) -> None:
        try:
            focused = self._entry.focus_get()
        except (KeyError, tk.TclError):
            focused = None
        if focused is not self._entry:
            self.close()
