"""Materials: the commander's Raw, Manufactured and Encoded engineering materials, in Field Ops mode's panel.

A collapsible "Materials" row shows how many pieces of each type are held, the last change the journal reported and which materials are at the
most the game lets you hold, with a MATERIALS button that opens the window (`materials_window.py`) to search, filter and read every count with
its grade and limit. The counts are kept per commander (`materials.py`) and never leave the computer. They come from the journal's `Materials`
list at login and every event that changes a count; if WNTB starts in the middle of a session it takes EDMC's own totals once."""
from __future__ import annotations

import logging
import os
import tkinter as tk
from typing import Any, Dict, Mapping, Optional, Tuple

from config import appname

from . import materials, materials_window, panelkit

plugin_name = os.path.basename(os.path.dirname(__file__))
logger = logging.getLogger(f"{appname}.{plugin_name}")

PANEL_PLACEMENT = "fieldops"

_FULL_SHOWN = 3        # names listed on the "at the limit" line; the rest are counted
_NAME_SHOWN = 22       # characters of a material name shown in the panel
_WRAP_PX = 200         # the summary wraps here: what it shows comes from the game, and must not widen EDMC's window

book = materials.MaterialBook()


def summary_lines(book_: materials.MaterialBook) -> Tuple[str, str]:
    """(the lines under the title, the note after the title when folded)."""
    if not book_.ready:
        return "Log in to see your materials.", ""
    held = book_.held()
    if not held:
        return "No materials yet. The counts fill in when you are in the game.", ""
    totals = book_.totals()
    lines = [" · ".join(f"{kind} {totals.get(kind, 0):,}" for kind in materials.TYPES)]
    if totals.get(materials.OTHER):
        lines[0] += f" · Other {totals[materials.OTHER]:,}"
    last = book_.last
    if last is not None:
        name = _clip(last.name)
        lines.append(f"Last: {'+' if last.delta > 0 else '-'}{abs(last.delta):,} {name} (now {last.total:,})")
    full = book_.full()
    if full:
        names = ", ".join(_clip(h.material.name) for h in full[:_FULL_SHOWN])
        more = f" and {len(full) - _FULL_SHOWN} more" if len(full) > _FULL_SHOWN else ""
        lines.append(f"At the limit: {names}{more}")
    if not book_.has_counts:
        lines.append("As of your last session.")
    return "\n".join(lines), f"- {sum(totals.values()):,} held"


def _clip(text: str) -> str:
    return text if len(text) <= _NAME_SHOWN else text[:_NAME_SHOWN - 1].rstrip() + "…"


class MaterialsController:
    def __init__(self) -> None:
        self._summary_var: Optional[tk.StringVar] = None
        self._section: Optional[tk.Frame] = None
        self._parent: Optional[tk.Frame] = None
        book.add_listener(self._update_summary)

    # --- what the game tells us -----------------------------------------------------------------------------------------

    def start(self, plugin_dir: str) -> None:
        book.load(plugin_dir)

    def stop(self) -> None:
        book.flush()
        materials_window.close()

    def handle_event(self, entry: Mapping[str, Any], cmdr: str, system: Optional[str], station: Optional[str],
                     state: Dict[str, Any]) -> None:
        book.set_commander(cmdr)       # a new commander tells the book's listeners (this row, an open window) itself
        book.apply_event(entry, state)

    # --- the panel row ---------------------------------------------------------------------------------------------------

    def summary(self) -> Tuple[str, str]:
        return summary_lines(book)

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
        body = panelkit.collapsible_section(parent, "Materials", "wntb_materials_collapsed")
        self._section = body
        # A plain label with a hard wrap, not panelkit.wrap_label: that one never wraps narrower than 300 px, and long names would then make
        # this the widest row in the panel (and so widen the whole EDMC window).
        tk.Label(body, textvariable=self._summary_var, anchor="w", justify=tk.LEFT, wraplength=_WRAP_PX).grid(
            row=1, column=0, columnspan=3, sticky=tk.W, pady=(2, 0))
        button = tk.Button(body, text="MATERIALS", command=self._open_window)
        button.grid(row=2, column=0, sticky=tk.W, pady=(4, 0))
        panelkit.add_tooltip(button, "Open the Materials window: search and filter every material with its grade and limit")
        self._update_summary()

    def _open_window(self) -> None:
        if self._parent is not None:
            materials_window.show(self._parent, book)


controller = MaterialsController()


def start(plugin_dir: str) -> None:
    controller.start(plugin_dir)


def stop() -> None:
    controller.stop()


def handle_event(entry: Dict[str, Any], cmdr: str, system: Optional[str], station: Optional[str], state: Dict[str, Any]) -> None:
    controller.handle_event(entry, cmdr, system, station, state)


def build_panel(parent: tk.Frame) -> None:
    controller.build_panel(parent)
