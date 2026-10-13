"""Expedition: the commander's planned trips, in Exploration mode's panel.

A collapsible "Expedition" row shows the one being tracked: its name, how many stops are done, the jumps and light-years flown and the time since
it started, the next stop with its distance and note, and the note of the stop just reached. COPY puts the next stop's system name on the
clipboard (to paste into the galaxy map), and a tick copies it automatically on every arrival. The expeditions (`expedition.py`) are kept per
commander and never leave the computer. Progress comes from the journal: `FSDJump`, `CarrierJump` and `Location` (at login) carry the system, and
the first two its position; `FSDJump` also carries the jump distance. The next stop's distance is a straight line from the last position the
game gave, and is left out when either position is unknown."""
from __future__ import annotations

import logging
import os
import tkinter as tk
from typing import Any, Dict, Mapping, Optional, Tuple

from config import appname, config

from . import expedition, expedition_window, panelkit

plugin_name = os.path.basename(os.path.dirname(__file__))
logger = logging.getLogger(f"{appname}.{plugin_name}")

PANEL_PLACEMENT = "exploration"

_CFG_AUTOCOPY = "wntb_expedition_autocopy"
_NAME_SHOWN = 28       # characters of an expedition name shown in the panel
_SYSTEM_SHOWN = 30     # characters of a system name shown in the panel
_NOTE_SHOWN = 110      # characters of a note shown in the panel
_WRAP_PX = 200         # the lines wrap here: what they show comes from the commander and the game, and must not widen EDMC's window

book = expedition.ExpeditionBook()


def autocopy_enabled() -> bool:
    return config.get_bool(_CFG_AUTOCOPY, default=False)


def summary_lines(book_: expedition.ExpeditionBook, position: Optional[expedition.XYZ], arrival: str = "",
                  now_text: Optional[str] = None) -> Tuple[str, str]:
    """(the lines under the title, the note after the title when folded)."""
    if not book_.ready:
        return "Log in to use expeditions.", ""
    e = book_.active()
    if e is None:
        saved = len(book_.expeditions())
        return (f"No expedition running ({saved} saved)." if saved else "No expedition yet."), ""
    total = len(e.stops)
    lines = [f"{expedition.clip(e.name, _NAME_SHOWN)}: {e.visited_count} of {total} stops"]
    stats = f"{e.jumps:,} jumps · {e.light_years:,.0f} ly"
    taken = now_text if now_text is not None else expedition.elapsed_text(e.started)
    lines.append(stats + (f" · {taken}" if taken else ""))
    nxt = e.next_stop()
    if nxt is None:
        lines.append("All stops visited. Finish it in the Expedition window.")
    else:
        place = f"{nxt.system} / {nxt.body}" if nxt.body else nxt.system
        far = book_.distance_to_next(e, position)
        lines.append(f"Next: {expedition.clip(place, _SYSTEM_SHOWN)}" + (f" ({far:,.0f} ly)" if far is not None else ""))
        if nxt.note:
            lines.append(f"Note: {expedition.clip(nxt.note, _NOTE_SHOWN)}")
    if arrival:
        lines.append(expedition.clip(arrival, _NOTE_SHOWN + 30))
    return "\n".join(lines), f"- {e.visited_count}/{total}"


class ExpeditionController:
    def __init__(self) -> None:
        self._system = ""
        self._position: Optional[expedition.XYZ] = None
        self._arrival = ""
        self._summary_var: Optional[tk.StringVar] = None
        self._autocopy_var: Optional[tk.BooleanVar] = None
        self._section: Optional[tk.Frame] = None
        self._parent: Optional[tk.Frame] = None
        book.add_listener(self._update_summary)

    # --- what the game tells us -----------------------------------------------------------------------------------------

    def start(self, plugin_dir: str) -> None:
        book.load(plugin_dir)

    def stop(self) -> None:
        book.flush()
        expedition_window.close()

    def handle_event(self, entry: Mapping[str, Any], cmdr: str, system: Optional[str], station: Optional[str],
                     state: Dict[str, Any]) -> None:
        changed = book.set_commander(cmdr)       # a new commander tells the book's listeners (this row) itself
        event = entry.get("event")
        if changed:
            self._arrival = ""
        if event in expedition.ARRIVAL_EVENTS and isinstance(entry.get("StarSystem"), str) and entry["StarSystem"].strip():
            self._arrive(entry)
        elif not self._system and system:
            self._system = system.strip()

    def _arrive(self, entry: Mapping[str, Any]) -> None:
        name = " ".join(entry["StarSystem"].split())
        self._system = name
        self._position = expedition.parse_xyz(entry.get("StarPos"))      # unknown if the game did not give it: we have moved
        done = book.on_arrival(name, str(entry.get("timestamp") or ""), entry.get("JumpDist"), is_jump=entry.get("event") == "FSDJump")
        self._arrival = ""
        if done is not None and done.stop is not None:
            number = done.expedition.stops.index(done.stop) + 1
            self._arrival = f"Reached stop {number}: {done.stop.system}." + (f" {done.stop.note}" if done.stop.note else "")
            if done.completed:
                self._arrival += " That was the last stop."
        if done is not None and autocopy_enabled():
            self.copy_next()
        self._update_summary()

    # --- the panel row ---------------------------------------------------------------------------------------------------

    def summary(self) -> Tuple[str, str]:
        return summary_lines(book, self._position, self._arrival)

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
        self._autocopy_var = tk.BooleanVar(value=autocopy_enabled())
        body = panelkit.collapsible_section(parent, "Expedition", "wntb_expedition_collapsed")
        self._section = body
        # A plain label with a hard wrap, not panelkit.wrap_label: that one never wraps narrower than 300 px, and a long system name or note
        # would then make this the widest row in the panel (and so widen the whole EDMC window).
        tk.Label(body, textvariable=self._summary_var, anchor="w", justify=tk.LEFT, wraplength=_WRAP_PX).grid(
            row=1, column=0, columnspan=3, sticky=tk.W, pady=(2, 0))
        copy = tk.Button(body, text="COPY", command=self.copy_next)
        copy.grid(row=2, column=0, sticky=tk.W, pady=(4, 0))
        panelkit.add_tooltip(copy, "Copy the next stop's system name to the clipboard, to paste into the galaxy map")
        tick = tk.Checkbutton(body, text="Copy on arrival", variable=self._autocopy_var, command=self._save_autocopy)
        tick.grid(row=2, column=1, sticky=tk.W, padx=(6, 0), pady=(4, 0))
        panelkit.add_tooltip(tick, "Copy the next stop's system name to the clipboard every time you arrive anywhere")
        window = tk.Button(body, text="EXPEDITION", command=self._open_window)
        window.grid(row=3, column=0, sticky=tk.W, pady=(4, 0))
        panelkit.add_tooltip(window, "Open the Expedition window: plan, start and review expeditions")
        self._update_summary()

    def _save_autocopy(self) -> None:
        if self._autocopy_var is not None:
            config.set(_CFG_AUTOCOPY, self._autocopy_var.get())

    def system(self) -> str:
        """The system the commander is in, or an empty string when it is not known yet."""
        return self._system

    def position(self) -> Optional[expedition.XYZ]:
        """The galactic position the game last gave, or None."""
        return self._position

    def _open_window(self) -> None:
        if self._parent is not None:
            expedition_window.show(self._parent, book, self)

    def next_system(self) -> str:
        e = book.active()
        nxt = e.next_stop() if e is not None else None
        return nxt.system if nxt is not None else ""

    def copy_next(self) -> bool:
        """Copy the next stop's system name; False when there is none or the clipboard could not be reached."""
        name = self.next_system()
        if not name or self._parent is None:
            return False
        return panelkit.copy_to_clipboard(self._parent, name)


controller = ExpeditionController()


def start(plugin_dir: str) -> None:
    controller.start(plugin_dir)


def stop() -> None:
    controller.stop()


def handle_event(entry: Dict[str, Any], cmdr: str, system: Optional[str], station: Optional[str], state: Dict[str, Any]) -> None:
    controller.handle_event(entry, cmdr, system, station, state)


def build_panel(parent: tk.Frame) -> None:
    controller.build_panel(parent)
