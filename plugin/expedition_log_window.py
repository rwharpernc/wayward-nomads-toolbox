"""The Expedition Log window: the archive of the commander's exploration expeditions.

A table lists every expedition (newest first) with its dates and its headline totals. Select one to read everything it recorded and to edit its details: the name, when
it started and ended (UTC), where it started and ended, the ships used, and notes. **Start** begins a new expedition now (in the ship and system you are in; the one
running is stopped), **Stop** ends the running one, **Resume** carries on counting one that was stopped, **Reset** clears an expedition's totals and starts it counting
again from now, **Rescan** works its totals out again from your own journals between its start and its end (which fills in an expedition that missed events, or one given
an earlier start), **Delete** removes it from the archive, **Copy summary** puts what it recorded on the clipboard and **Export CSV** writes the whole archive for a
spreadsheet. Reset and Delete ask for a second press.

Built on the shared window kit (plugin/uikit). Module-level show/refresh/close and saved geometry follow expedition_window.py. The file dialog and the journal folder are
module-level names so tests can replace them.
"""
from __future__ import annotations

import csv
import logging
import os
import queue
import threading
import tkinter as tk
from tkinter import filedialog
from typing import Any, List, Optional

from config import appname, config

from . import expedition_log, journal_files
from .uikit import palette as P
from .uikit import style
from .uikit.shell import WindowShell
from .uikit.table import Column, DataTable
from .uikit.widgets import FlatButton, clip

plugin_name = os.path.basename(os.path.dirname(__file__))
logger = logging.getLogger(f"{appname}.{plugin_name}")

CONFIG_GEOMETRY = "wntb_expedition_log_window_geometry"
DEFAULT_SIZE = (1240, 820)
MIN_SIZE = (1080, 600)
CONFIRM_MS = 5000
POLL_MS = 200

ask_save_path = filedialog.asksaveasfilename
journal_folder = journal_files.journal_folder

_window: Optional["LogWindow"] = None

_COLUMNS = (
    Column("name", "Name", 160, stretch=True, max_chars=40),
    Column("status", "Status", 70),
    Column("started", "Started (UTC)", 120),
    Column("ended", "Ended (UTC)", 120),
    Column("systems", "Systems", 64, anchor="e"),
    Column("jumps", "Jumps", 56, anchor="e"),
    Column("bodies", "Bodies", 64, anchor="e"),
    Column("species", "Species", 64, anchor="e"),
    Column("explo", "Exploration cr", 104, anchor="e"),
    Column("bio", "Exobiology cr", 104, anchor="e"),
    Column("total", "Total cr", 104, anchor="e"),
)


def show(parent: tk.Misc, book: expedition_log.LogBook, ctx: Any) -> None:
    """Open the window, or raise it if it is already open. `ctx` is the controller: `system()`, `ship()`, `commander()`, `start_expedition(name)`, `stop_expedition()`,
    `rescan_totals(run_id, folder)`, `plan_since_last_sale(folder)` and `begin_since_last_sale(plan, name)`."""
    global _window
    if _window is not None and _window.alive:
        _window.refresh()
        _window.lift()
        return
    _window = LogWindow(parent, book, ctx)


def refresh() -> None:
    if _window is not None and _window.alive:
        _window.refresh()


def close() -> None:
    if _window is not None and _window.alive:
        _window.close()


def table_row(run: expedition_log.Run) -> tuple:
    t = run.totals
    return (clip(run.name, 40), "running" if run.status == expedition_log.RUNNING else "stopped", expedition_log.display_time(run.started),
            expedition_log.display_time(run.ended) or "-", f"{len(run.systems):,}", f"{t.jumps:,}", f"{t.bodies_scanned:,}", f"{t.bio_species:,}",
            f"{t.explore_earned:,}", f"{t.bio_earned:,}", f"{t.earned:,}")


class LogWindow:
    def __init__(self, parent: tk.Misc, book: expedition_log.LogBook, ctx: Any) -> None:
        self._book = book
        self._ctx = ctx
        self._picked: Optional[str] = None
        self._confirming: Optional[str] = None
        self._results: "queue.Queue[tuple]" = queue.Queue()
        self._busy = False

        self._shell = WindowShell(
            parent, "Expedition Log", "", size=DEFAULT_SIZE, min_size=MIN_SIZE,
            load_geometry=lambda: config.get_str(CONFIG_GEOMETRY) or "",
            save_geometry=lambda geometry: config.set(CONFIG_GEOMETRY, geometry))
        self._shell.window.protocol("WM_DELETE_WINDOW", self.close)
        self._shell.add_action("Start", self._start, accent=True)
        self._shell.add_action("Stop", self._stop)

        body = self._shell.body
        starter = tk.Frame(body, bg=P.BG)
        starter.pack(fill="x", pady=(0, P.PAD_SM))
        tk.Label(starter, text="New expedition name", fg=P.MUTED, bg=P.BG).pack(side="left")
        self._new_name = tk.StringVar()
        entry = tk.Entry(starter, textvariable=self._new_name, width=36)
        entry.pack(side="left", padx=(P.PAD_SM, P.PAD_SM))
        entry.bind("<Return>", lambda _e: self._start())
        tk.Label(starter, text="(optional; Start begins it now, from where you are)", fg=P.FAINT, bg=P.BG).pack(side="left", padx=(0, P.PAD))
        FlatButton(starter, "Start since my last sale", self._start_since_sale).pack(side="left")

        self._table = DataTable(body, _COLUMNS, on_select=self._pick, sortable=False, visible_rows=8,
                                empty_text="No expeditions yet. Press Start when you set off.")
        self._table.pack(fill="x", pady=(0, P.PAD_SM))

        lower = tk.Frame(body, bg=P.BG)
        lower.pack(fill="both", expand=True)
        lower.columnconfigure(0, weight=3)
        lower.columnconfigure(1, weight=2)
        facts = tk.Frame(lower, bg=P.PANE, padx=P.PAD, pady=P.PAD)
        facts.grid(row=0, column=0, sticky="nsew", padx=(0, P.PAD_SM))
        tk.Label(facts, text="What it recorded", fg=P.MUTED, bg=P.PANE, anchor="w").pack(fill="x")
        self._facts = tk.Label(facts, text="", fg=P.TEXT, bg=P.PANE, anchor="nw", justify="left", wraplength=640, font=style.font(P.FONT_BODY))
        self._facts.pack(fill="both", expand=True, anchor="nw")

        editor = tk.Frame(lower, bg=P.PANE, padx=P.PAD, pady=P.PAD)
        editor.grid(row=0, column=1, sticky="nsew")
        editor.columnconfigure(1, weight=1)
        self._fields = {key: tk.StringVar() for key in ("name", "started", "ended", "start_system", "end_system")}
        for row, (key, label) in enumerate((("name", "Name"), ("started", "Started (UTC)"), ("ended", "Ended (UTC)"),
                                            ("start_system", "Start location"), ("end_system", "End location"))):
            tk.Label(editor, text=label, fg=P.MUTED, bg=P.PANE).grid(row=row, column=0, sticky="w", pady=2)
            tk.Entry(editor, textvariable=self._fields[key], width=34).grid(row=row, column=1, sticky="we", padx=P.PAD_SM, pady=2)
        tk.Label(editor, text="Ships used (one per line)", fg=P.MUTED, bg=P.PANE).grid(row=5, column=0, columnspan=2, sticky="w", pady=(P.PAD_SM, 0))
        self._ships = tk.Text(editor, width=34, height=3, wrap="word")
        self._ships.grid(row=6, column=0, columnspan=2, sticky="we", pady=2)
        tk.Label(editor, text="Notes", fg=P.MUTED, bg=P.PANE).grid(row=7, column=0, columnspan=2, sticky="w", pady=(P.PAD_SM, 0))
        self._notes = tk.Text(editor, width=34, height=5, wrap="word")
        self._notes.grid(row=8, column=0, columnspan=2, sticky="we", pady=2)
        tk.Label(editor, text="Dates: 2026-10-16 or 2026-10-16 18:30 (UTC). Leave Ended empty while it runs.", fg=P.FAINT, bg=P.PANE, anchor="w",
                 wraplength=330, justify="left").grid(row=9, column=0, columnspan=2, sticky="w", pady=(2, 0))

        buttons = tk.Frame(body, bg=P.BG)
        buttons.pack(fill="x", pady=(P.PAD_SM, 0))
        for text, command, kind in (("Save changes", self._save, "accent"), ("Resume", self._resume, "normal"), ("Rescan", self._rescan, "normal"),
                                    ("Reset", self._reset, "danger"), ("Delete", self._delete, "danger"), ("Copy summary", self._copy, "normal"),
                                    ("Export CSV", self._export, "normal")):
            FlatButton(buttons, text, command, kind=kind).pack(side="left", padx=(0, 6))

        book.add_listener(self._on_book_changed)
        self.refresh()
        self._poll()

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
            pass

    def current(self) -> Optional[expedition_log.Run]:
        return self._book.get(self._picked) if self._picked else None

    def refresh(self) -> None:
        if not self.alive:
            return
        who = self._book.commander
        runs = self._book.runs()
        self._shell.set_subtitle(f"{who}: {len(runs)} expedition{'s' if len(runs) != 1 else ''}" if who else "Waiting for a commander (log in)")
        keep = self._picked
        self._table.clear()
        for run in runs:
            self._table.insert(run.id, table_row(run))
        if keep and self._book.get(keep) is not None:
            self._table.select(keep)
        else:
            running = self._book.running()
            self._picked = running.id if running is not None else (runs[0].id if runs else None)
            if self._picked:
                self._table.select(self._picked)
        self._show_selected(refill_fields=self._picked != keep)
        if not self._shell._status.cget("text"):
            self._shell.set_status("Start an expedition when you set off. Totals come from the journal while it runs; Rescan works them out again from your journals.")

    def _show_selected(self, refill_fields: bool = True) -> None:
        run = self.current()
        self._facts.configure(text="\n".join(expedition_log.facts_lines(run)) if run is not None else "Select an expedition, or press Start.")
        if refill_fields:
            self._fill_fields(run)

    def _fill_fields(self, run: Optional[expedition_log.Run]) -> None:
        values = {"name": run.name, "started": expedition_log.display_time(run.started), "ended": expedition_log.display_time(run.ended),
                  "start_system": run.start_system, "end_system": run.end_system} if run is not None else {k: "" for k in self._fields}
        for key, var in self._fields.items():
            var.set(values[key])
        for widget, text in ((self._ships, "\n".join(run.ships) if run else ""), (self._notes, run.notes if run else "")):
            widget.delete("1.0", "end")
            widget.insert("1.0", text)

    def _pick(self, run_id: str) -> None:
        self._picked = run_id
        self._confirming = None
        self._show_selected()

    def _say(self, text: str) -> None:
        self._shell.set_status(text)

    def _confirm(self, what: str, message: str) -> bool:
        """A first press asks and a second press (within a few seconds) goes ahead."""
        if self._confirming == what:
            self._confirming = None
            return True
        self._confirming = what
        self._say(message)
        self._shell.window.after(CONFIRM_MS, lambda: setattr(self, "_confirming", None) if self._confirming == what else None)
        return False

    def _need_run(self) -> Optional[expedition_log.Run]:
        run = self.current()
        if run is None:
            self._say("Select an expedition first.")
        return run

    # --- the actions ---------------------------------------------------------------------------------------------------
    def _start(self) -> None:
        run = self._ctx.start_expedition(self._new_name.get())
        if run is None:
            self._say("Log in first: an expedition belongs to a commander.")
            return
        self._new_name.set("")
        self._picked = run.id
        self.refresh()
        self._say(f"Started {run.name} from {run.start_system or 'where you are'}.")

    def _start_since_sale(self) -> None:
        """Starts an expedition that carries on from the data you are still holding: it begins just after your last sale and takes the totals your journals give since."""
        if self._busy:
            return
        if not self._book.ready:
            self._say("Log in first: an expedition belongs to a commander.")
            return
        self._busy = True
        self._say("Reading your journals for your last sale...")
        folder, name = journal_folder(), self._new_name.get()

        def worker() -> None:
            try:
                self._results.put(("sale", name, self._ctx.plan_since_last_sale(folder)))
            except Exception as problem:   # reading journals must never leave the window stuck
                logger.exception("Expedition Log: could not plan an expedition since the last sale")
                self._results.put(("error", name, problem))

        threading.Thread(target=worker, name="WNTB-expedition-log-since-sale", daemon=True).start()

    def _stop(self) -> None:
        run = self._ctx.stop_expedition()
        self._say(f"Stopped {run.name}." if run is not None else "No expedition is running.")

    def _resume(self) -> None:
        run = self._need_run()
        if run is not None and self._book.resume(run.id) is not None:
            self._say(f"{run.name} is counting again.")

    def _save(self) -> None:
        run = self._need_run()
        if run is None:
            return
        try:
            self._book.update(run.id, name=self._fields["name"].get(), started=self._fields["started"].get(), ended=self._fields["ended"].get(),
                              start_system=self._fields["start_system"].get(), end_system=self._fields["end_system"].get(),
                              ships=self._ships.get("1.0", "end").strip().replace("\n", ";"), notes=self._notes.get("1.0", "end").strip())
        except ValueError as problem:
            self._say(str(problem))
            return
        self._fill_fields(self._book.get(run.id))
        self._say("Saved.")

    def _reset(self) -> None:
        run = self._need_run()
        if run is None or not self._confirm("reset", f"Press Reset again to clear {run.name}'s totals and start counting from now."):
            return
        fresh = self._book.reset(run.id)
        self._say(f"{fresh.name} was reset and is counting from now." if fresh is not None else "Nothing to reset.")

    def _delete(self) -> None:
        run = self._need_run()
        if run is None or not self._confirm("delete", f"Press Delete again to remove {run.name} from the archive."):
            return
        self._book.delete(run.id)
        self._picked = None
        self.refresh()
        self._say(f"Deleted {run.name}.")

    def _rescan(self) -> None:
        run = self._need_run()
        if run is None or self._busy:
            return
        if not run.started:
            self._say("Give it a start date first.")
            return
        self._busy = True
        self._say(f"Reading your journals for {run.name}...")
        run_id, folder = run.id, journal_folder()

        def worker() -> None:
            try:
                rebuilt = self._ctx.rescan_totals(run_id, folder)          # reads the journals only; the log is changed on the main thread, in _poll
                self._results.put(("ok", run_id, rebuilt))
            except Exception as problem:   # reading journals must never leave the window stuck
                logger.exception("Expedition Log rescan failed")
                self._results.put(("error", run_id, problem))

        threading.Thread(target=worker, name="WNTB-expedition-log-rescan", daemon=True).start()

    def _poll(self) -> None:
        if not self.alive:
            return
        try:
            while True:
                kind, run_id, payload = self._results.get_nowait()
                self._busy = False
                if kind == "sale":
                    if payload is None:
                        self._say("Your journals show no sale, so there is no last sale to start from. Use Start instead.")
                    else:
                        run = self._ctx.begin_since_last_sale(payload, run_id)
                        if run is not None:
                            self._new_name.set("")
                            self._picked = run.id
                            self.refresh()
                            t = run.totals
                            self._say(f"Started {run.name} from {expedition_log.display_time(run.started)} UTC: {len(run.systems):,} systems, {t.jumps:,} jumps, "
                                      f"{t.bodies_scanned:,} bodies and {t.bio_species:,} species so far, and it carries on counting.")
                elif kind == "ok" and payload is not None:
                    done = self._book.replace_totals(run_id, payload)
                    if done is not None:
                        self._say(f"{done.name}: totals worked out again from your journals ({len(done.systems):,} systems, {done.totals.jumps:,} jumps).")
                    self.refresh()
                else:
                    self._say("Could not read the journals for that expedition." if kind == "error" else "Nothing to rescan.")
        except queue.Empty:
            pass
        self._shell.window.after(POLL_MS, self._poll)

    def _copy(self) -> None:
        run = self._need_run()
        if run is None:
            return
        self._shell.window.clipboard_clear()
        self._shell.window.clipboard_append("\n".join(expedition_log.facts_lines(run)))
        self._say(f"Copied {run.name}'s summary.")

    def _export(self) -> None:
        runs = self._book.runs()
        if not runs:
            self._say("The archive is empty.")
            return
        path = ask_save_path(parent=self._shell.window, defaultextension=".csv", initialfile="expedition-log.csv", filetypes=[("CSV", "*.csv")])
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8", newline="") as handle:
                csv.writer(handle).writerows(expedition_log.csv_rows(runs))
        except OSError as problem:
            self._say(f"Could not write the file: {problem}")
            return
        self._say(f"Wrote {len(runs)} expedition{'s' if len(runs) != 1 else ''} to {path}.")
