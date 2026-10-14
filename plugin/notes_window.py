"""The Notes window: every note the active commander has written about a system or body, with a search box, an editor, and a
"Here" button on each name field that fills in where the commander is now. Built on the shared window kit (plugin/uikit); the notes
themselves are `notes_data.NoteBook`, which saves each change at once. Module-level show/refresh/close and saved geometry follow
rare_goods_window.py."""
from __future__ import annotations

import logging
import os
import tkinter as tk
from typing import Callable, List, Optional, Tuple

from config import appname, config

from . import notes_data, system_autocomplete
from .uikit import palette as P
from .uikit.shell import WindowShell
from .uikit.table import Column, DataTable
from .uikit.widgets import FlatButton

plugin_name = os.path.basename(os.path.dirname(__file__))
logger = logging.getLogger(f"{appname}.{plugin_name}")

CONFIG_GEOMETRY = "wntb_notes_window_geometry"
DEFAULT_SIZE = (980, 640)
MIN_SIZE = (760, 480)
PREVIEW_CHARS = 90
CONFIRM_MS = 5000     # how long a first press of Delete waits for the second

Context = Callable[[], Tuple[str, str]]   # () -> (current system, current body), either may be ""

_window: Optional["NotesWindow"] = None

_COLUMNS = (
    Column("system", "System", 170, max_chars=40),
    Column("body", "Body", 130, max_chars=30),
    Column("note", "Note", 280, stretch=True, max_chars=PREVIEW_CHARS),
    Column("changed", "Changed (UTC)", 130),
)


def show(parent: tk.Misc, book: notes_data.NoteBook, context: Context) -> None:
    """Open the Notes window, or raise it if it is already open."""
    global _window
    if _window is not None and _window.alive:
        _window.refresh()
        _window.lift()
        return
    _window = NotesWindow(parent, book, context)


def refresh() -> None:
    if _window is not None and _window.alive:
        _window.refresh()


def close() -> None:
    if _window is not None and _window.alive:
        _window.close()


def when(stamp: str) -> str:
    """`2026-10-13T12:34:56Z` as `2026-10-13 12:34`."""
    return stamp[:16].replace("T", " ") if stamp else ""


class NotesWindow:
    def __init__(self, parent: tk.Misc, book: notes_data.NoteBook, context: Context) -> None:
        self._book = book
        self._context = context
        self._editing: Optional[str] = None       # the id of the note in the editor, None for a new one
        self._shown: List[str] = []
        self._confirming = False                  # Delete has been pressed once

        self._shell = WindowShell(
            parent, "Notes", "", size=DEFAULT_SIZE, min_size=MIN_SIZE,
            load_geometry=lambda: config.get_str(CONFIG_GEOMETRY) or "",
            save_geometry=lambda geometry: config.set(CONFIG_GEOMETRY, geometry))
        self._shell.window.protocol("WM_DELETE_WINDOW", self.close)
        self._shell.add_action("New note", self._new, accent=True)

        filters = tk.Frame(self._shell.body, bg=P.BG)
        filters.pack(fill="x", pady=(0, P.PAD_SM))
        tk.Label(filters, text="Search", fg=P.MUTED, bg=P.BG).pack(side="left")
        self._query = tk.StringVar()
        tk.Entry(filters, textvariable=self._query, width=28).pack(side="left", padx=(P.PAD_SM, P.PAD))
        self._query.trace_add("write", lambda *_: self._fill_table())
        self._here_only = tk.BooleanVar(value=False)
        self._here_check = tk.Checkbutton(filters, text="Only the system I am in", variable=self._here_only,
                                          command=self._fill_table, fg=P.TEXT, bg=P.BG, selectcolor=P.CARD,
                                          activebackground=P.BG, activeforeground=P.TEXT)
        self._here_check.pack(side="left")

        self._table = DataTable(self._shell.body, _COLUMNS, on_select=self._load_into_editor,
                                empty_text="No notes yet. Write one below.", visible_rows=8)
        self._table.pack(fill="x", pady=(0, P.PAD_SM))

        editor = tk.Frame(self._shell.body, bg=P.PANE, padx=P.PAD, pady=P.PAD)
        editor.pack(fill="both", expand=True, pady=(0, P.PAD_SM))
        editor.columnconfigure(1, weight=1)
        self._system = tk.StringVar()
        self._body = tk.StringVar()
        for row, (label, variable) in enumerate((("System", self._system), ("Body", self._body))):
            tk.Label(editor, text=label, fg=P.MUTED, bg=P.PANE).grid(row=row, column=0, sticky="w", pady=2)
            box = tk.Entry(editor, textvariable=variable, width=36)
            box.grid(row=row, column=1, sticky="w", padx=P.PAD_SM, pady=2)
            if row == 0:
                system_autocomplete.attach(box, variable)
            FlatButton(editor, "Here", lambda r=row: self._fill_here(r)).grid(row=row, column=2, sticky="w", pady=2)
        tk.Label(editor, text="Note", fg=P.MUTED, bg=P.PANE).grid(row=2, column=0, sticky="nw", pady=2)
        self._text = tk.Text(editor, height=6, wrap="word", bg=P.CARD, fg=P.TEXT, insertbackground=P.TEXT, relief="flat")
        self._text.grid(row=2, column=1, columnspan=2, sticky="nsew", padx=P.PAD_SM, pady=2)
        editor.rowconfigure(2, weight=1)

        buttons = tk.Frame(editor, bg=P.PANE)
        buttons.grid(row=3, column=1, columnspan=2, sticky="w", pady=(P.PAD_SM, 0))
        FlatButton(buttons, "Save", self._save, kind="accent").pack(side="left")
        self._delete_button = FlatButton(buttons, "Delete", self._delete, kind="danger")
        self._delete_button.pack(side="left", padx=(6, 0))
        self._delete_button.set_enabled(False)

        book.add_listener(self._on_book_changed)
        self.refresh()
        self._new()

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
        system, _body = self._context()
        self._here_check.configure(state="normal" if system else "disabled")
        if not system:
            self._here_only.set(False)
        who = self._book.commander
        self._shell.set_subtitle(f"{who}: {self._book.count()} note{'s' if self._book.count() != 1 else ''}" if who
                                 else "Waiting for a commander (log in)")
        self._fill_table()

    def _on_book_changed(self) -> None:
        try:
            if self.alive:
                self.refresh()
        except tk.TclError:
            pass   # the window went away between the check and the redraw

    def _fill_table(self) -> None:
        if not self.alive:
            return
        system, _body = self._context()
        notes = self._book.search(self._query.get(), system if self._here_only.get() and system else None)
        keep = self._editing
        self._table.clear()
        self._shown = [n.id for n in notes]
        for note in notes:
            self._table.insert(note.id, (note.system, note.body, notes_data.clip(note.text, PREVIEW_CHARS), when(note.updated)))
        if keep and keep in self._shown:
            self._table.select(keep)
        self._shell.set_status("Select a note to change it, or write a new one below. Notes are kept on this computer, for this "
                               "commander only, and are never sent anywhere.")

    # --- the editor ---------------------------------------------------------------------------------------------------

    def _new(self) -> None:
        """Start a new note, with the system you are in filled in."""
        self._editing = None
        self._confirming = False
        system, body = self._context()
        self._system.set(system)
        self._body.set(body)
        self._text.delete("1.0", "end")
        self._table.select(None)
        self._delete_button.set_enabled(False)

    def _fill_here(self, row: int) -> None:
        system, body = self._context()
        (self._system if row == 0 else self._body).set(system if row == 0 else body)

    def _load_into_editor(self, note_id: str) -> None:
        note = self._book.get(note_id)
        if note is None:
            return
        self._editing = note.id
        self._confirming = False
        self._system.set(note.system)
        self._body.set(note.body)
        self._text.delete("1.0", "end")
        self._text.insert("1.0", note.text)
        self._delete_button.set_enabled(True)

    def _save(self) -> None:
        text = self._text.get("1.0", "end").strip()
        try:
            if self._editing:
                note = self._book.update(self._editing, self._system.get(), self._body.get(), text)
            else:
                note = self._book.add(self._system.get(), self._body.get(), text)
        except notes_data.NoteError as err:
            self._shell.set_status(str(err))
            return
        self._editing = note.id
        self._delete_button.set_enabled(True)
        self._fill_table()
        self._shell.set_status("Saved.")

    def _delete(self) -> None:
        """A note cannot be got back, so the first press asks and a second press (within a few seconds) deletes."""
        if not self._editing:
            return
        if not self._confirming:
            self._confirming = True
            self._shell.set_status("Press Delete again to remove this note for good.")
            self._shell.window.after(CONFIRM_MS, self._stop_confirming)
            return
        self._confirming = False
        if self._book.delete(self._editing):
            self._new()
            self._fill_table()
            self._shell.set_status("Deleted.")

    def _stop_confirming(self) -> None:
        self._confirming = False
