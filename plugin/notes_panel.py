"""Notes: the commander's own notes on a system or body, in Exploration mode's panel.

A collapsible "Notes" row says how many notes there are for the system you are in (and shows the newest), takes a quick one-line
note about it, and opens the Notes window (`notes_window.py`) to read, search, change or delete them all. The notes are kept per
commander (`notes_data.py`) and never leave the computer. The system comes from the journal (`FSDJump`, `Location`, `CarrierJump` and
EDMC's own current system); the body, offered when you add a note, from `Status.json`'s `BodyName` while you are near one."""
from __future__ import annotations

import logging
import os
import tkinter as tk
from typing import Any, Dict, Mapping, Optional, Tuple

from config import appname

from . import notes_data, notes_window, panelkit

plugin_name = os.path.basename(os.path.dirname(__file__))
logger = logging.getLogger(f"{appname}.{plugin_name}")

PANEL_PLACEMENT = "exploration"

_LOCATION_EVENTS = ("FSDJump", "Location", "CarrierJump")
_NAME_SHOWN = 40       # characters of a system name shown in the panel
_PREVIEW_SHOWN = 60    # characters of the newest note shown in the panel
_ENTRY_WIDTH = 26      # the quick-add box has a fixed width, whatever is typed in it (about 190 px: inside the panel's own width)
_WRAP_PX = 200         # the summary wraps here: what it shows comes from the commander and the game, and must not widen EDMC's window

book = notes_data.NoteBook()


class NotesController:
    def __init__(self) -> None:
        self._system = ""
        self._body = ""
        self._summary_var: Optional[tk.StringVar] = None
        self._entry_var: Optional[tk.StringVar] = None
        self._section: Optional[tk.Frame] = None
        self._parent: Optional[tk.Frame] = None
        book.add_listener(self._update_summary)

    # --- what the game tells us -----------------------------------------------------------------------------------------

    def start(self, plugin_dir: str) -> None:
        book.load(plugin_dir)

    def stop(self) -> None:
        notes_window.close()

    def handle_event(self, entry: Mapping[str, Any], cmdr: str, system: Optional[str], station: Optional[str],
                     state: Dict[str, Any]) -> None:
        place = str(entry.get("StarSystem") or "") if entry.get("event") in _LOCATION_EVENTS else ""
        place = (place or system or self._system or "").strip()
        moved = place != self._system
        if moved:
            self._system, self._body = place, ""
        changed = book.set_commander(cmdr)   # a new commander tells the book's listeners (this row, an open window) itself
        if moved and not changed:
            self._update_summary()
            notes_window.refresh()

    def dashboard_status(self, entry: Mapping[str, Any]) -> None:
        body = entry.get("BodyName")
        self._body = body.strip() if isinstance(body, str) else ""

    def context(self) -> Tuple[str, str]:
        """(the system you are in, the body you are near), either may be empty."""
        return self._system, self._body

    # --- the panel row ---------------------------------------------------------------------------------------------------

    def summary(self) -> Tuple[str, str]:
        """(the line under the title, the note after the title when folded)."""
        if not book.ready:
            return "Log in to use notes.", ""
        if not self._system:
            return "Notes: your system is not known yet.", ""
        here = notes_data.clip(self._system, _NAME_SHOWN)
        notes = book.for_system(self._system)
        if not notes:
            return f"No notes for {here}.", ""
        newest = notes_data.clip(notes[0].text, _PREVIEW_SHOWN)
        count = f"{len(notes)} note{'s' if len(notes) != 1 else ''}"
        return f"{count} for {here}. Newest: {newest}", f"- {len(notes)} here"

    def _update_summary(self) -> None:
        if self._summary_var is None:
            return
        try:
            text, suffix = self.summary()
            self._summary_var.set(text)
            if self._section is not None:
                self._section.set_title_suffix(suffix)   # type: ignore[attr-defined]
        except tk.TclError:
            pass   # the panel is being torn down

    def build_panel(self, parent: tk.Frame) -> None:
        self._parent = parent
        self._summary_var = tk.StringVar()
        self._entry_var = tk.StringVar()

        body = panelkit.collapsible_section(parent, "Notes", "wntb_notes_collapsed")
        self._section = body
        # A plain label with a hard wrap, not panelkit.wrap_label: that one never wraps narrower than 300 px, and a long system name or
        # note would then make this the widest row in the panel (and so widen the whole EDMC window).
        tk.Label(body, textvariable=self._summary_var, anchor="w", justify=tk.LEFT, wraplength=_WRAP_PX).grid(
            row=1, column=0, columnspan=3, sticky=tk.W, pady=(2, 0))
        entry = tk.Entry(body, textvariable=self._entry_var, width=_ENTRY_WIDTH)
        entry.grid(row=2, column=0, columnspan=3, sticky=tk.W, pady=(4, 0))
        entry.bind("<Return>", lambda _e: self._add_quick())
        add = tk.Button(body, text="ADD", command=self._add_quick)
        add.grid(row=3, column=0, sticky=tk.W, pady=(4, 0))
        panelkit.add_tooltip(add, "Save this line as a note about the system you are in")
        notes = tk.Button(body, text="NOTES", command=self._open_window)
        notes.grid(row=3, column=1, sticky=tk.W, padx=(4, 0), pady=(4, 0))
        panelkit.add_tooltip(notes, "Open the Notes window: read, search, change or delete every note")
        self._update_summary()

    def _add_quick(self) -> None:
        if self._entry_var is None or self._summary_var is None:
            return
        try:
            book.add(self._system, self._body, self._entry_var.get())
        except notes_data.NoteError as err:
            self._summary_var.set(str(err))
            return
        self._entry_var.set("")   # the book's listener has refreshed the summary

    def _open_window(self) -> None:
        if self._parent is not None:
            notes_window.show(self._parent, book, self.context)


controller = NotesController()


def start(plugin_dir: str) -> None:
    controller.start(plugin_dir)


def stop() -> None:
    controller.stop()


def handle_event(entry: Dict[str, Any], cmdr: str, system: Optional[str], station: Optional[str], state: Dict[str, Any]) -> None:
    controller.handle_event(entry, cmdr, system, station, state)


def dashboard_status(entry: Dict[str, Any]) -> None:
    controller.dashboard_status(entry)


def build_panel(parent: tk.Frame) -> None:
    controller.build_panel(parent)
