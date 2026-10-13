"""The Marks window: every mark the active commander has made, which one the Surface Compass is aimed at, how far each is from where
you are (when it is on the body you are on), and an editor with a "Here" button that fills in your body and position. Built on the
shared window kit (plugin/uikit); the marks themselves are `surface_marks.MarkBook`, which saves each change at once. Module-level
show/refresh/close and saved geometry follow rare_goods_window.py and notes_window.py."""
from __future__ import annotations

import logging
import os
import tkinter as tk
from typing import Callable, Optional

from config import appname, config

from . import mining_bearing as bearing
from . import surface_marks
from .uikit import palette as P
from .uikit.shell import WindowShell
from .uikit.table import Column, DataTable
from .uikit.widgets import FlatButton

plugin_name = os.path.basename(os.path.dirname(__file__))
logger = logging.getLogger(f"{appname}.{plugin_name}")

CONFIG_GEOMETRY = "wntb_marks_window_geometry"
DEFAULT_SIZE = (940, 640)
MIN_SIZE = (780, 500)
CONFIRM_MS = 5000     # how long a first press of Delete waits for the second

HereFn = Callable[[], surface_marks.Here]

_window: Optional["MarksWindow"] = None

_COLUMNS = (
    Column("name", "Name", 170, stretch=True, max_chars=40),
    Column("body", "Body", 220, max_chars=36),
    Column("lat", "Latitude", 90, anchor="e"),
    Column("lon", "Longitude", 90, anchor="e"),
    Column("away", "From here", 90, anchor="e"),
)


def show(parent: tk.Misc, book: surface_marks.MarkBook, here: HereFn) -> None:
    """Open the Marks window, or raise it if it is already open."""
    global _window
    if _window is not None and _window.alive:
        _window.refresh()
        _window.lift()
        return
    _window = MarksWindow(parent, book, here)


def refresh() -> None:
    if _window is not None and _window.alive:
        _window.refresh()


def close() -> None:
    if _window is not None and _window.alive:
        _window.close()


def degrees(value: float) -> str:
    return f"{value:.4f}"


class MarksWindow:
    def __init__(self, parent: tk.Misc, book: surface_marks.MarkBook, here: HereFn) -> None:
        self._book = book
        self._here = here
        self._editing: Optional[str] = None       # the id of the mark in the editor, None for a new one
        self._confirming = False                  # Delete has been pressed once

        self._shell = WindowShell(
            parent, "Marks", "", size=DEFAULT_SIZE, min_size=MIN_SIZE,
            load_geometry=lambda: config.get_str(CONFIG_GEOMETRY) or "",
            save_geometry=lambda geometry: config.set(CONFIG_GEOMETRY, geometry))
        self._shell.window.protocol("WM_DELETE_WINDOW", self.close)
        self._shell.add_action("New mark", self._new, accent=True)

        aim = tk.Frame(self._shell.body, bg=P.BG)
        aim.pack(fill="x", pady=(0, P.PAD_SM))
        tk.Label(aim, text="The compass points at:", fg=P.MUTED, bg=P.BG).pack(side="left")
        self._aim_label = tk.Label(aim, text="", fg=P.ACCENT, bg=P.BG)
        self._aim_label.pack(side="left", padx=(P.PAD_SM, P.PAD))
        FlatButton(aim, "Nearest hotspot", lambda: self._set_target(surface_marks.AUTO)).pack(side="left")
        FlatButton(aim, "Selected mark", self._target_selected).pack(side="left", padx=(6, 0))
        FlatButton(aim, "Nothing", lambda: self._set_target(surface_marks.NONE)).pack(side="left", padx=(6, 0))

        self._table = DataTable(self._shell.body, _COLUMNS, on_select=self._load_into_editor,
                                empty_text="No marks yet. Stand where you want one and press Here, then Save.", visible_rows=8)
        self._table.tag_configure("target", foreground=P.ACCENT)
        self._table.pack(fill="x", pady=(0, P.PAD_SM))

        editor = tk.Frame(self._shell.body, bg=P.PANE, padx=P.PAD, pady=P.PAD)
        editor.pack(fill="x", pady=(0, P.PAD_SM))
        self._name = tk.StringVar()
        self._body = tk.StringVar()
        self._lat = tk.StringVar()
        self._lon = tk.StringVar()
        fields = (("Name", self._name, 30), ("Body", self._body, 44), ("Latitude", self._lat, 14), ("Longitude", self._lon, 14))
        for row, (label, variable, width) in enumerate(fields):
            tk.Label(editor, text=label, fg=P.MUTED, bg=P.PANE).grid(row=row, column=0, sticky="w", pady=2)
            tk.Entry(editor, textvariable=variable, width=width).grid(row=row, column=1, sticky="w", padx=P.PAD_SM, pady=2)
        FlatButton(editor, "Here", self._fill_here).grid(row=1, column=2, rowspan=3, sticky="nw", pady=2)
        tk.Label(editor, text="Here fills in the body and your position now. Latitude and longitude are in degrees "
                              "(north and east positive).", fg=P.FAINT, bg=P.PANE).grid(row=4, column=1, columnspan=2, sticky="w", pady=(2, 0))

        buttons = tk.Frame(editor, bg=P.PANE)
        buttons.grid(row=5, column=1, columnspan=2, sticky="w", pady=(P.PAD_SM, 0))
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
        who = self._book.commander
        count = self._book.count()
        self._shell.set_subtitle(f"{who}: {count} mark{'s' if count != 1 else ''}" if who else "Waiting for a commander (log in)")
        target = self._book.target
        mark = self._book.target_mark()
        self._aim_label.configure(text="nothing" if target == surface_marks.NONE else
                                  f"the mark {mark.name}" if mark else "the nearest recorded hotspot")
        self._fill_table()

    def _on_book_changed(self) -> None:
        try:
            if self.alive:
                self.refresh()
        except tk.TclError:
            pass   # the window went away between the check and the redraw

    def _distance(self, mark: surface_marks.Mark) -> str:
        here = self._here()
        if not here.on_surface or not here.radius or surface_marks.body_key(here.body) != surface_marks.body_key(mark.body):
            return ""
        return bearing.format_distance_m(bearing.distance_m(here.latitude, here.longitude, mark.latitude, mark.longitude, here.radius))

    def _fill_table(self) -> None:
        if not self.alive:
            return
        keep = self._editing
        self._table.clear()
        target = self._book.target
        for mark in self._book.all():
            self._table.insert(mark.id, (mark.name, mark.body, degrees(mark.latitude), degrees(mark.longitude), self._distance(mark)),
                               tag="target" if mark.id == target else None)
        if keep and self._book.get(keep) is not None:
            self._table.select(keep)
        self._shell.set_status("The compass only points at things on the body you are on. Marks are kept on this computer, for this "
                               "commander only, and are never sent anywhere.")

    # --- the target ---------------------------------------------------------------------------------------------------

    def _set_target(self, target: str) -> None:
        try:
            self._book.set_target(target)
        except surface_marks.MarkError as err:
            self._shell.set_status(str(err))
            return
        self._shell.set_status("Saved.")

    def _target_selected(self) -> None:
        if self._editing is None:
            self._shell.set_status("Select a mark in the list first.")
            return
        self._set_target(self._editing)

    # --- the editor ---------------------------------------------------------------------------------------------------

    def _new(self) -> None:
        """Start a new mark, with the name left for you to type (or Mark 1, Mark 2 ... when it is blank) and where you are filled in."""
        self._editing = None
        self._confirming = False
        self._name.set("")
        self._fill_here()
        self._table.select(None)
        self._delete_button.set_enabled(False)

    def _fill_here(self) -> None:
        here = self._here()
        self._body.set(here.body)
        self._lat.set(degrees(here.latitude) if here.latitude is not None else "")
        self._lon.set(degrees(here.longitude) if here.longitude is not None else "")

    def _load_into_editor(self, mark_id: str) -> None:
        mark = self._book.get(mark_id)
        if mark is None:
            return
        self._editing = mark.id
        self._confirming = False
        self._name.set(mark.name)
        self._body.set(mark.body)
        self._lat.set(degrees(mark.latitude))
        self._lon.set(degrees(mark.longitude))
        self._delete_button.set_enabled(True)

    def _save(self) -> None:
        name = self._name.get().strip() or (self._book.get(self._editing).name if self._editing and self._book.get(self._editing)
                                            else self._book.next_name())
        try:
            if self._editing:
                mark = self._book.update(self._editing, name, self._body.get(), self._lat.get(), self._lon.get())
            else:
                mark = self._book.add(name, self._body.get(), self._lat.get(), self._lon.get())
        except surface_marks.MarkError as err:
            self._shell.set_status(str(err))
            return
        self._editing = mark.id
        self._name.set(mark.name)
        self._delete_button.set_enabled(True)
        self._fill_table()
        self._shell.set_status("Saved.")

    def _delete(self) -> None:
        """A mark cannot be got back, so the first press asks and a second press (within a few seconds) deletes."""
        if not self._editing:
            return
        if not self._confirming:
            self._confirming = True
            self._shell.set_status("Press Delete again to remove this mark for good.")
            self._shell.window.after(CONFIRM_MS, self._stop_confirming)
            return
        self._confirming = False
        if self._book.delete(self._editing):
            self._new()
            self._fill_table()
            self._shell.set_status("Deleted.")

    def _stop_confirming(self) -> None:
        self._confirming = False
