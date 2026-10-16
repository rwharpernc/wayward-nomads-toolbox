"""The Expedition window: plan, run and review the commander's expeditions.

Pick an expedition (or make one with a name and **New**), then **Start** it: from then on, arriving in a stop's system ticks it off and counts the
jump (`expedition.py`, fed by the panel row `expedition_panel.py`). The table lists the stops in order with the next one marked, when each was
reached and how far each is from you. Under it, an editor adds a stop, saves changes to the selected one, or removes it (**Here** fills in the system
you are in); **Up** and **Down** reorder by hand and **Mark visited** ticks a stop off (or takes the tick away) yourself.

Tools: **From plotted route** adds the systems of the route plotted in the game (`NavRoute.json`, with their positions); **Import CSV** reads
system, body and note columns (a one-column list works too); **Locate and reorder** asks EDSM for the positions of the unvisited stops that have none
and puts them in nearest-neighbor order from where you are (this is the one thing here that goes online, and it sends only system names); **Copy list**
and **Export CSV** share the plan; **Copy next** puts the next stop's name on the clipboard.

Built on the shared window kit (plugin/uikit). Module-level show/refresh/close and saved geometry follow notes_window.py. The file dialogs, the EDSM
lookup and the journal folder are module-level names so tests can replace them."""
from __future__ import annotations

import json
import logging
import os
import queue
import threading
import tkinter as tk
from tkinter import filedialog
from typing import Any, Dict, List, Optional, Tuple

from config import appname, config

from . import edsm_client, expedition, expedition_plan_dialog, journal_files, panelkit, spansh_planners, system_autocomplete
from .uikit import palette as P
from .uikit import style
from .uikit.shell import WindowShell
from .uikit.table import Column, DataTable
from .uikit.widgets import Combobox, FlatButton, clip

plugin_name = os.path.basename(os.path.dirname(__file__))
logger = logging.getLogger(f"{appname}.{plugin_name}")

CONFIG_GEOMETRY = "wntb_expedition_window_geometry"
CONFIG_LOOKUP = "wntb_expedition_lookup_names"      # look system names up on EDSM when stops are added (on unless turned off)
LOOKUP_CHUNK = 50      # names asked of EDSM in one request
DEFAULT_SIZE = (1100, 760)
MIN_SIZE = (900, 560)
CONFIRM_MS = 5000     # how long a first press of Reset, Delete or Remove waits for the second
POLL_MS = 200

ask_open_path = filedialog.askopenfilename
ask_save_path = filedialog.asksaveasfilename
lookup_coords = edsm_client.systems_coords
journal_folder = journal_files.journal_folder

_window: Optional["ExpeditionWindow"] = None

_COLUMNS = (
    Column("number", "#", 44, anchor="e"),
    Column("system", "System", 230, stretch=True, max_chars=44),
    Column("body", "Body", 160, max_chars=30),
    Column("note", "Note", 280, stretch=True, max_chars=60),
    Column("reached", "Reached (UTC)", 130),
    Column("survey", "Found here", 190, max_chars=34),
    Column("away", "From you (ly)", 100, anchor="e"),
)


def show(parent: tk.Misc, book: expedition.ExpeditionBook, ctx: Any) -> None:
    """Open the Expedition window, or raise it if it is already open. `ctx` says where the commander is: `system()`, `position()` and `copy_next()`."""
    global _window
    if _window is not None and _window.alive:
        _window.refresh()
        _window.lift()
        return
    _window = ExpeditionWindow(parent, book, ctx)


def refresh() -> None:
    if _window is not None and _window.alive:
        _window.refresh()


def close() -> None:
    if _window is not None and _window.alive:
        _window.close()


def when(stamp: str) -> str:
    """`2026-10-13T12:34:56Z` as `2026-10-13 12:34`."""
    return stamp[:16].replace("T", " ") if stamp else ""


def picker_label(e: expedition.Expedition) -> str:
    return f"{clip(e.name, 50)} ({e.status}, {e.visited_count} of {len(e.stops)})"


def stats_text(e: Optional[expedition.Expedition]) -> str:
    if e is None:
        return "No expedition selected. Type a name and press New."
    parts = [e.status.capitalize(), f"{e.visited_count} of {len(e.stops)} stops", f"{e.jumps:,} jumps", f"{e.light_years:,.0f} ly"]
    taken = expedition.elapsed_text(e.started, e.finished) if e.started else ""
    if taken:
        parts.append(taken)
    if e.survey_text():
        parts.append(e.survey_text())
    return " · ".join(parts)


class ExpeditionWindow:
    def __init__(self, parent: tk.Misc, book: expedition.ExpeditionBook, ctx: Any) -> None:
        self._book = book
        self._ctx = ctx
        self._picked: Optional[str] = None          # the expedition shown
        self._stop_id: Optional[str] = None         # the stop selected in the table
        self._labels: Dict[str, str] = {}           # picker label -> expedition id
        self._confirming: Optional[str] = None
        self._results: "queue.Queue[Tuple[str, Dict[str, expedition.XYZ], int, expedition.XYZ]]" = queue.Queue()
        self._busy = False
        self._planner: Optional[expedition_plan_dialog.PlanDialog] = None
        self._lookups: "queue.Queue[Tuple[str, List[str], Dict[str, expedition.XYZ]]]" = queue.Queue()
        self._lookups_waiting = 0

        self._shell = WindowShell(
            parent, "Expedition", "", size=DEFAULT_SIZE, min_size=MIN_SIZE,
            load_geometry=lambda: config.get_str(CONFIG_GEOMETRY) or "",
            save_geometry=lambda geometry: config.set(CONFIG_GEOMETRY, geometry))
        self._shell.window.protocol("WM_DELETE_WINDOW", self.close)
        self._shell.add_action("Start", self._start, accent=True)
        self._shell.add_action("Pause", self._pause)
        self._shell.add_action("Finish", self._finish)

        body = self._shell.body
        picker = tk.Frame(body, bg=P.BG)
        picker.pack(fill="x", pady=(0, P.PAD_SM))
        tk.Label(picker, text="Expedition", fg=P.MUTED, bg=P.BG).pack(side="left")
        self._choice = tk.StringVar()
        self._box = Combobox(picker, textvariable=self._choice, state="readonly", width=46)
        self._box.pack(side="left", padx=(P.PAD_SM, P.PAD))
        self._box.bind("<<ComboboxSelected>>", lambda _e: self._on_pick())
        tk.Label(picker, text="Name", fg=P.MUTED, bg=P.BG).pack(side="left")
        self._name = tk.StringVar()
        entry = tk.Entry(picker, textvariable=self._name, width=26)
        self._name_entry = entry
        entry.pack(side="left", padx=(P.PAD_SM, P.PAD_SM))
        entry.bind("<Return>", lambda _e: self._new())
        FlatButton(picker, "New", self._new).pack(side="left")
        FlatButton(picker, "Rename", self._rename).pack(side="left", padx=(6, 0))
        FlatButton(picker, "Reset", self._reset, kind="danger").pack(side="left", padx=(P.PAD, 0))
        FlatButton(picker, "Delete", self._delete, kind="danger").pack(side="left", padx=(6, 0))

        self._stats = tk.Label(body, text="", fg=P.TEXT, bg=P.BG, anchor="w", font=style.font(P.FONT_BOLD))
        self._stats.pack(fill="x", pady=(0, P.PAD_SM))

        self._table = DataTable(body, _COLUMNS, on_select=self._pick_stop, sortable=False, visible_rows=11,
                                empty_text="No stops yet. Add some below, or import a plotted route or a CSV.")
        self._table.pack(fill="x", pady=(0, P.PAD_SM))

        editor = tk.Frame(body, bg=P.PANE, padx=P.PAD, pady=P.PAD)
        editor.pack(fill="x", pady=(0, P.PAD_SM))
        editor.columnconfigure(1, weight=1)
        self._system, self._body_var, self._note = tk.StringVar(), tk.StringVar(), tk.StringVar()
        tk.Label(editor, text="System", fg=P.MUTED, bg=P.PANE).grid(row=0, column=0, sticky="w", pady=2)
        system_entry = tk.Entry(editor, textvariable=self._system, width=40)
        system_entry.grid(row=0, column=1, sticky="w", padx=P.PAD_SM, pady=2)
        system_autocomplete.attach(system_entry, self._system)
        system_entry.bind("<Return>", lambda _e: self._add_stop())
        FlatButton(editor, "Here", self._fill_here).grid(row=0, column=2, sticky="w", pady=2)
        tk.Label(editor, text="Body (optional)", fg=P.MUTED, bg=P.PANE).grid(row=1, column=0, sticky="w", pady=2)
        tk.Entry(editor, textvariable=self._body_var, width=40).grid(row=1, column=1, sticky="w", padx=P.PAD_SM, pady=2)
        tk.Label(editor, text="Note (optional)", fg=P.MUTED, bg=P.PANE).grid(row=2, column=0, sticky="w", pady=2)
        tk.Entry(editor, textvariable=self._note, width=80).grid(row=2, column=1, columnspan=2, sticky="w", padx=P.PAD_SM, pady=2)
        stop_buttons = tk.Frame(editor, bg=P.PANE)
        stop_buttons.grid(row=3, column=0, columnspan=3, sticky="w", pady=(P.PAD_SM, 0))
        for text, command, kind in (("Add stop", self._add_stop, "accent"), ("Save changes", self._save_stop, "normal"),
                                    ("Mark visited", self._toggle_visited, "normal"), ("Up", lambda: self._move(-1), "normal"),
                                    ("Down", lambda: self._move(1), "normal"), ("Remove", self._remove_stop, "danger")):
            FlatButton(stop_buttons, text, command, kind=kind).pack(side="left", padx=(0, 6))
        self._lookup_var = tk.BooleanVar(value=config.get_bool(CONFIG_LOOKUP, default=True))
        tk.Checkbutton(editor, text="Check system names on EDSM when adding (fixes capitals, finds the position)", variable=self._lookup_var,
                       command=lambda: config.set(CONFIG_LOOKUP, self._lookup_var.get()), fg=P.TEXT, bg=P.PANE, selectcolor=P.BG,
                       activebackground=P.PANE, activeforeground=P.TEXT, anchor="w").grid(row=4, column=0, columnspan=3, sticky="w", pady=(P.PAD_SM, 0))

        planners = tk.Frame(body, bg=P.BG)
        planners.pack(fill="x", pady=(0, P.PAD_SM))
        tk.Label(planners, text="Make an expedition with Spansh", fg=P.MUTED, bg=P.BG).pack(side="left", padx=(0, P.PAD))
        for text, kind in (("Road to Riches", spansh_planners.RICHES), ("Exomastery", spansh_planners.EXOBIOLOGY)):
            FlatButton(planners, text, lambda k=kind: self._plan(k)).pack(side="left", padx=(0, 6))
        tools = tk.Frame(body, bg=P.BG)
        tools.pack(fill="x")
        for text, command in (("From plotted route", self._from_route), ("Import CSV", self._import_csv),
                              ("Locate and reorder (EDSM)", self._locate), ("Copy list", self._copy_list),
                              ("Export CSV", self._export_csv), ("Copy next", self._copy_next)):
            FlatButton(tools, text, command).pack(side="left", padx=(0, 6))

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

    def _on_book_changed(self) -> None:
        try:
            if self.alive:
                self.refresh()
        except tk.TclError:
            pass   # the window went away between the check and the redraw

    def current(self) -> Optional[expedition.Expedition]:
        return self._book.get(self._picked) if self._picked else None

    def refresh(self) -> None:
        if not self.alive:
            return
        who = self._book.commander
        count = len(self._book.expeditions())
        self._shell.set_subtitle(f"{who}: {count} expedition{'s' if count != 1 else ''}" if who else "Waiting for a commander (log in)")
        everything = self._book.expeditions()
        self._labels = {picker_label(e): e.id for e in everything}
        self._box.configure(values=list(self._labels))
        if self.current() is None:
            active = self._book.active()
            self._picked = active.id if active is not None else (everything[0].id if everything else None)
        e = self.current()
        self._choice.set(picker_label(e) if e is not None else "")
        self._stats.configure(text=stats_text(e))
        self._fill_table()
        if not self._shell._status.cget("text"):
            self._shell.set_status("Stops are ticked off when you arrive in their system while the expedition is active (Start). Positions come "
                                   "from the game or EDSM.")

    def _fill_table(self) -> None:
        e = self.current()
        keep = self._stop_id
        self._table.clear()
        if e is None:
            return
        position = self._ctx.position()
        nxt = e.next_stop()
        for number, stop in enumerate(e.stops, 1):
            far = expedition.distance(position, stop.xyz)
            reached = when(stop.visited) or ("next" if stop is nxt and e.status == expedition.ACTIVE else "")
            self._table.insert(stop.id, (number, clip(stop.system, 44), clip(stop.body, 30), clip(stop.note, 60), reached,
                                         clip(stop.survey_text(), 34), f"{far:,.0f}" if far is not None else "-"))
        if keep and any(s.id == keep for s in e.stops):
            self._table.select(keep)
        else:
            self._stop_id = None

    def _say(self, text: str) -> None:
        self._shell.set_status(text)

    def _confirm(self, what: str, message: str) -> bool:
        """A first press asks and a second press (within a few seconds) goes ahead."""
        if self._confirming != what:
            self._confirming = what
            self._say(message)
            self._shell.window.after(CONFIRM_MS, self._stop_confirming)
            return False
        self._confirming = None
        return True

    def _stop_confirming(self) -> None:
        self._confirming = None

    def _need_expedition(self) -> Optional[expedition.Expedition]:
        e = self.current()
        if e is None:
            self._say("Pick or create an expedition first.")
        return e

    def _expedition_to_add_to(self) -> Optional[expedition.Expedition]:
        """The picked expedition, or a new one when there is none yet, so the first stop never needs a separate step. It is named from the Name box
        if something is typed there, else "My expedition" (numbered if that name is taken)."""
        e = self.current()
        if e is not None:
            return e
        typed = " ".join(self._name.get().split())
        taken = {x.name.casefold() for x in self._book.expeditions()}
        name = typed
        if not name:
            name, number = "My expedition", 1
            while name.casefold() in taken:
                number += 1
                name = f"My expedition {number}"
        e = self._attempt(self._book.create, name)
        if e is not None:
            self._picked, self._stop_id = e.id, None
            self._name.set("")
            self.refresh()
        return e

    def _attempt(self, action: Any, *args: Any) -> Any:
        """Run a change on the book; a refusal is shown as it is and None returned."""
        try:
            return action(*args)
        except expedition.ExpeditionError as err:
            self._say(str(err))
            return None

    # --- the expeditions ----------------------------------------------------------------------------------------------

    def _on_pick(self) -> None:
        self._picked = self._labels.get(self._choice.get())
        self._stop_id = None
        self._confirming = None
        self.refresh()

    def _new(self) -> None:
        e = self._attempt(self._book.create, self._name.get())
        if e is not None:
            self._picked, self._stop_id = e.id, None
            self._name.set("")
            self.refresh()
            self._say(f"Created '{e.name}'. Add stops, then press Start.")

    def _rename(self) -> None:
        """First press with an empty Name box puts the current name there to edit; a press with a name typed renames."""
        e = self._need_expedition()
        if e is None:
            return
        typed = " ".join(self._name.get().split())
        if not typed or typed == e.name:
            self._name.set(e.name)
            self._name_entry.focus_set()
            self._name_entry.icursor("end")
            self._say(f"Change the name in the Name box, then press Rename again (now '{e.name}').")
            return
        if self._attempt(self._book.rename, e.id, typed) is not None:
            self._name.set("")
            self.refresh()
            self._say("Renamed.")

    def _start(self) -> None:
        e = self._need_expedition()
        if e is not None and self._attempt(self._book.start, e.id) is not None:
            self._say(f"'{e.name}' is running: arrivals now count.")

    def _pause(self) -> None:
        e = self._need_expedition()
        if e is not None and self._attempt(self._book.pause, e.id) is not None:
            self._say("Paused. Its progress is kept.")

    def _finish(self) -> None:
        e = self._need_expedition()
        if e is not None and self._attempt(self._book.finish, e.id) is not None:
            self._say(f"'{e.name}' is finished.")

    def _reset(self) -> None:
        e = self._need_expedition()
        if e is not None and self._confirm("reset", "Press Reset again to forget this expedition's progress (visits, jumps, distance, times). The stops stay."):
            self._attempt(self._book.reset, e.id)
            self._say("Reset: it is a plan again.")

    def _delete(self) -> None:
        e = self._need_expedition()
        if e is not None and self._confirm("delete", f"Press Delete again to delete '{e.name}' and all its stops for good."):
            self._book.delete(e.id)
            self._picked = None
            self.refresh()
            self._say("Deleted.")

    # --- the stops ------------------------------------------------------------------------------------------------------

    def _pick_stop(self, stop_id: str) -> None:
        e = self.current()
        stop = next((s for s in e.stops if s.id == stop_id), None) if e is not None else None
        if stop is None:
            return
        self._stop_id = stop.id
        self._confirming = None
        self._system.set(stop.system)
        self._body_var.set(stop.body)
        self._note.set(stop.note)

    def _fill_here(self) -> None:
        self._system.set(self._ctx.system())

    def _add_stop(self) -> None:
        if not self._system.get().strip():
            self._say("A stop needs a system name: type one, or press Here for the system you are in. The body and the note are optional.")
            return
        e = self._expedition_to_add_to()
        if e is None:
            return
        stop = self._attempt(self._book.add_stop, e.id, self._spelling(self._system.get()), self._body_var.get(), self._note.get())
        if stop is not None:
            self._stop_id = stop.id
            self._system.set("")
            self._body_var.set("")
            self._note.set("")
            self._say(f"Added {stop.system} as stop {len(e.stops)}.")
            self._look_up(e.id, [stop.system])

    def _selected(self) -> Optional[Tuple[expedition.Expedition, expedition.Stop]]:
        e = self._need_expedition()
        if e is None:
            return None
        stop = next((s for s in e.stops if s.id == self._stop_id), None)
        if stop is None:
            self._say("Select a stop first.")
            return None
        return e, stop

    def _save_stop(self) -> None:
        picked = self._selected()
        if picked is not None:
            changed = self._attempt(self._book.update_stop, picked[0].id, picked[1].id, self._spelling(self._system.get()), self._body_var.get(),
                                    self._note.get())
            if changed is not None:
                self._say("Saved.")
                self._look_up(picked[0].id, [changed.system])

    def _remove_stop(self) -> None:
        picked = self._selected()
        if picked is not None and self._confirm("remove", "Press Remove again to take this stop off the expedition."):
            self._book.remove_stop(picked[0].id, picked[1].id)
            self._stop_id = None
            self._say("Removed.")

    def _move(self, delta: int) -> None:
        picked = self._selected()
        if picked is not None and not self._book.move_stop(picked[0].id, picked[1].id, delta):
            self._say("It is at the end of the list already.")

    def _toggle_visited(self) -> None:
        picked = self._selected()
        if picked is not None:
            stop = self._attempt(self._book.set_visited, picked[0].id, picked[1].id, not picked[1].is_visited)
            if stop is not None:
                self._say("Marked as visited." if stop.is_visited else "Visit cleared.")

    # --- import, locate and share ------------------------------------------------------------------------------------------

    def _from_route(self) -> None:
        e = self._expedition_to_add_to()
        if e is None:
            return
        folder = journal_folder()
        if not folder:
            self._say("Set EDMC's Journal directory first.")
            return
        try:
            with open(os.path.join(folder, "NavRoute.json"), encoding="utf-8") as handle:
                data = json.load(handle)
        except FileNotFoundError:
            self._say("No plotted route found.")
            return
        except (OSError, ValueError) as exc:
            logger.debug("Could not read NavRoute.json: %s", exc)
            self._say("Could not read the plotted route; try again in a moment.")
            return
        systems = self._book.parse_navroute(data, skip_system=self._ctx.system())
        if not systems:
            self._say("No route is plotted in the game.")
            return
        added = self._book.add_systems(e.id, systems)
        self._say(f"Added {added} stop(s) from the plotted route ({len(systems)} systems).")

    def _import_csv(self) -> None:
        e = self._expedition_to_add_to()
        if e is None:
            return
        path = ask_open_path(filetypes=[("CSV files", "*.csv"), ("All files", "*.*")])
        if not path:
            return
        try:
            with open(path, encoding="utf-8-sig", newline="") as handle:
                rows = self._book.parse_csv_stops(handle.read())
        except (OSError, ValueError) as exc:
            logger.debug("Could not read %s: %s", path, exc)
            self._say(f"Could not read {os.path.basename(path)}: {exc}")
            return
        before = len(e.stops)
        added, skipped = self._book.add_rows(e.id, rows)
        self._look_up(e.id, [s.system for s in e.stops[before:] if s.xyz is None])
        self._say(f"Added {added} stop(s) from {os.path.basename(path)}" + (f"; skipped {skipped} (empty, too long or over the limit)." if skipped else "."))

    # --- system names ---------------------------------------------------------------------------------------------------

    def _spelling(self, typed: str) -> str:
        """A system typed in any case, spelled as the game or another stop already spells it (the system you are in, then any stop); the
        typed text, spaces tidied, when nothing here knows it. No network."""
        typed = " ".join(str(typed or "").split())
        here = self._ctx.system()
        if typed and here and expedition.name_key(here) == expedition.name_key(typed):
            return here
        return self._book.known_spelling(typed) or typed

    def _look_up(self, expedition_id: str, names: List[str]) -> None:
        """Ask EDSM, in the background, how it spells these systems and where they are: it fixes the capitals and gives the stop a position.
        Only when the box under the editor is ticked, and only the names go."""
        names = [n for n in dict.fromkeys(names) if n]
        if not names or not self._lookup_var.get():
            return
        self._lookups_waiting += 1
        threading.Thread(target=self._look_up_worker, args=(expedition_id, names), daemon=True).start()
        self._shell.window.after(POLL_MS, self._poll_lookups)

    def _look_up_worker(self, expedition_id: str, names: List[str]) -> None:
        """Runs off the main thread: it must not touch any Tk widget."""
        found: Dict[str, expedition.XYZ] = {}
        try:
            for start in range(0, len(names), LOOKUP_CHUNK):
                found.update(lookup_coords(names[start:start + LOOKUP_CHUNK]))
        except Exception:
            logger.exception("Expedition system name lookup failed")
        self._lookups.put((expedition_id, names, found))

    def _poll_lookups(self) -> None:
        """Runs on the main thread via after(): safe to touch widgets."""
        try:
            expedition_id, names, found = self._lookups.get_nowait()
        except queue.Empty:
            if self.alive and self._lookups_waiting:
                self._shell.window.after(POLL_MS, self._poll_lookups)
            return
        self._lookups_waiting = max(0, self._lookups_waiting - 1)
        if not self.alive or self._book.get(expedition_id) is None:
            return
        respelled = self._book.canonical_names(expedition_id, found.keys())
        self._book.set_coords(expedition_id, found)
        known = {expedition.name_key(k) for k in found}
        unknown = [n for n in names if expedition.name_key(n) not in known]
        if not found and unknown:
            what = unknown[0] if len(unknown) == 1 else f"{len(unknown)} of these systems"
            self._say(f"EDSM could not be reached or does not know {what}. The name is kept as typed.")
        elif unknown:
            more = " and more" if len(unknown) > 3 else ""
            self._say(f"EDSM knows {len(known)}; it does not know {', '.join(unknown[:3])}{more}. Those names are kept as typed.")
        elif respelled:
            self._say(f"EDSM respelled {respelled} system name(s), for example {next(iter(found))}.")
        if self._lookups_waiting:
            self._shell.window.after(POLL_MS, self._poll_lookups)

    def _plan(self, kind: str) -> None:
        """Open the Spansh planner for `kind`; its answer becomes a new expedition (see `_planned`)."""
        if self._planner is not None and self._planner.alive:
            self._planner.lift()
            return
        if not self._book.ready:
            self._say("Expeditions are kept per commander and no commander is known yet. Log in first.")
            return
        reach = getattr(self._ctx, "jump_range", lambda: None)()
        self._planner = expedition_plan_dialog.open_dialog(self._shell.window, kind, self._ctx.system(), reach, self._planned)

    def _planned(self, query: spansh_planners.PlanQuery, stops: List[spansh_planners.PlannedStop]) -> None:
        if not stops:
            self._say(f"{spansh_planners.TITLES[query.kind]} found nothing worth stopping for. Lower the least worth, or look further from the route.")
            return
        name, taken, number = spansh_planners.default_name(query), {x.name.casefold() for x in self._book.expeditions()}, 1
        base = name
        while name.casefold() in taken:
            number += 1
            name = f"{base[:70]} ({number})"
        made = self._attempt(self._book.create, name)
        if made is None:
            return
        added = self._book.add_planned(made.id, [(s.system, s.body, s.note, s.xyz) for s in stops])
        self._picked, self._stop_id = made.id, None
        self.refresh()
        self._say(f"Made '{made.name}' with {added} stop(s) from Spansh. Check the order, then press Start.")

    def _locate(self) -> None:
        e = self._need_expedition()
        if e is None or self._busy:
            return
        position = self._ctx.position()
        if position is None:
            self._say("Your position is not known yet. Make a jump, then try again.")
            return
        names = [s.system for s in e.stops if not s.is_visited and s.xyz is None]
        if not names and not any(not s.is_visited and s.xyz is not None for s in e.stops):
            self._say("No unvisited stops to order.")
            return
        self._busy = True
        self._say(f"Asking EDSM for the positions of {len(names)} system(s)..." if names else "Ordering by distance...")
        threading.Thread(target=self._worker, args=(e.id, names, position), daemon=True).start()
        self._shell.window.after(POLL_MS, self._poll)

    def _worker(self, expedition_id: str, names: List[str], position: expedition.XYZ) -> None:
        """Runs off the main thread: it must not touch any Tk widget."""
        try:
            resolved = lookup_coords(names) if names else {}
        except Exception:
            logger.exception("Expedition position lookup failed")
            resolved = {}
        self._results.put((expedition_id, resolved, len(names), position))

    def _poll(self) -> None:
        """Runs on the main thread via after(): safe to touch widgets."""
        try:
            expedition_id, resolved, asked, position = self._results.get_nowait()
        except queue.Empty:
            if self.alive and self._busy:
                self._shell.window.after(POLL_MS, self._poll)
            return
        self._busy = False
        if not self.alive or self._book.get(expedition_id) is None:
            return
        self._book.set_coords(expedition_id, resolved)
        moved = self._book.reorder_nearest_neighbor(expedition_id, position)
        self._say((f"EDSM located {len(resolved)} of {asked}. " if asked else "") + f"Reordered {moved} unvisited stop(s) by distance"
                  + (" (the rest have no position and stay where they are)." if moved < self._unvisited_count(expedition_id) else "."))

    def _unvisited_count(self, expedition_id: str) -> int:
        e = self._book.get(expedition_id)
        return sum(1 for s in e.stops if not s.is_visited) if e is not None else 0

    def _copy_list(self) -> None:
        e = self._need_expedition()
        if e is not None:
            self._say("Copied the list." if panelkit.copy_to_clipboard(self._shell.window, self._book.to_text(e)) else "Could not reach the clipboard.")

    def _copy_next(self) -> None:
        self._say("Copied the next stop." if self._ctx.copy_next() else "There is no next stop to copy.")

    def _export_csv(self) -> None:
        e = self._need_expedition()
        if e is None:
            return
        path = ask_save_path(defaultextension=".csv", initialfile=f"{e.name}.csv", filetypes=[("CSV files", "*.csv"), ("All files", "*.*")])
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8", newline="") as handle:
                handle.write(self._book.to_csv(e))
        except OSError as exc:
            self._say(f"Could not write {os.path.basename(path)}: {exc}")
            return
        self._say(f"Saved {len(e.stops)} stop(s) to {os.path.basename(path)}.")
