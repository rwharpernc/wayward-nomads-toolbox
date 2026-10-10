"""Codex Completionist — a new Exploration feature: a personal "how many
of each scannable thing have I ever found" tally (see codex_completionist.py's
own docstring for the full "sit alongside EDMC-Canonn, don't duplicate it"
rationale and scope boundaries — no galaxy-wide completion percentage,
that's Canonn's own job).

Lives inside Exploration mode's panel (PANEL_PLACEMENT = "exploration"),
alongside Auto-Honk/Discovery/Boxel Survey/Exploration Value/Organic
Scanning - each gets its own dedicated
child frame (see ui.py's create_plugin_app/_stack_features()), separated
by a thin panelkit-drawn rule, so no cross-feature row coordination is
needed here.

Unlike most of this project's other Exploration features, this one
persists across restarts (see codex_completionist_state.py) - it needs
start()/stop() calls from load.py, same lifecycle pattern as
boxel_survey.py.
"""

from __future__ import annotations

import logging
import os
import queue
import threading
import time
from typing import Any, Dict, List, Optional, Tuple

import tkinter as tk

import myNotebook as nb
from config import appname, config
from ttkHyperlinkLabel import HyperlinkLabel

from . import codex_backfill, codex_completionist_state, codex_completionist_window, commander_data, panelkit
from .codex_completionist import CodexTally

plugin_name = os.path.basename(os.path.dirname(__file__))
logger = logging.getLogger(f"{appname}.{plugin_name}")

PANEL_PLACEMENT = "exploration"

_CFG_ENABLED = "wntb_codex_completionist_enabled"

CANONN_CODEX_URL = "https://canonn.science/codex/"

_DISABLED_TEXT = "Codex Completionist is disabled — see Settings."
_EMPTY_TEXT = "No codex entries recorded yet for this commander — fly, scan, and discover things."
_NO_CMDR_TEXT = "Codex Completionist: (waiting for commander login)"


def enabled() -> bool:
    # On by default - pure local journal tracking, no network calls.
    return config.get_bool(_CFG_ENABLED, default=True)


def _summary_text(tally: CodexTally, rebuilding: bool = False) -> str:
    if not tally.owner:
        return _NO_CMDR_TEXT
    if rebuilding:
        return f"Rebuilding {tally.owner}'s tally from your journals (one time, this can take a minute)..."
    if tally.total_distinct == 0:
        return _EMPTY_TEXT
    counts = tally.category_counts()
    top = sorted(counts.items(), key=lambda pair: pair[1], reverse=True)[:3]
    top_text = ", ".join(f"{name} ({count})" for name, count in top)
    return f"{tally.total_distinct:,} distinct entries, {tally.total_finds:,} total finds — {top_text}"


class CodexCompletionistController:
    def __init__(self) -> None:
        self._plugin_dir: Optional[str] = None
        self._tally = CodexTally()   # the active commander's; swapped in place when the commander changes
        self._rebuild_pending = False
        self._rebuilding = False   # a full-history read is running right now
        self._set_title_note = None   # set by build_panel: shows a note next to the section title, even when folded

        # (commander key, that commander's events, manual?) from a full-history scan.
        self._backfill_result_queue: "queue.Queue[Tuple[str, List[Dict[str, Any]], bool]]" = queue.Queue()

        self._parent: Optional[tk.Frame] = None
        self._summary_var: Optional[tk.StringVar] = None
        self._status_var: Optional[tk.StringVar] = None
        self._enabled_var: Optional[tk.BooleanVar] = None

    @property
    def tally(self) -> CodexTally:
        """Read-only access for other features (canonn_poi_panel.py's
        "skip already-logged sites" filter) to cross-reference against this
        commander's own codex finds, without needing their own copy of the
        tally or a direct journal-event subscription."""
        return self._tally

    # --- lifecycle -----------------------------------------------------

    def start(self, plugin_dir: str) -> None:
        # The tally is per commander and EDMC doesn't say who is active until the first journal event - the load
        # happens in _switch_cmdr().
        self._plugin_dir = plugin_dir
        try:
            if codex_completionist_state.tidy_old_tally(plugin_dir):
                logger.info("Removed the old shared Codex tally (every commander has their own now)")
        except Exception:
            logger.exception("Codex Completionist: could not tidy the old shared tally")

    def _switch_cmdr(self, cmdr: str) -> None:
        """Save the previous commander's tally and load this one's. A commander seen for the first time since codex
        tallies became per commander gets a one-time rebuild from their own journals (the old shared tally mixed
        everyone's finds, so it is not handed to anyone); a brand-new install just starts counting from now."""
        self._persist()
        self._tally.clear()
        self._tally.owner = str(cmdr).strip()
        self._rebuild_pending = False
        saved = codex_completionist_state.load_commander(self._plugin_dir, cmdr) if self._plugin_dir else None
        if saved is not None:
            try:
                self._tally.restore(saved.get("entries", []))
                self._tally.advance_watermark(saved.get("last_event_at"))
                self._rebuild_pending = bool(saved.get("rebuild_pending"))
                logger.info("Restored the Codex Completionist tally for %s: %d distinct entries", cmdr, self._tally.total_distinct)
            except Exception:
                logger.exception("Failed to restore the saved Codex Completionist tally for %s; starting fresh", cmdr)
        elif self._plugin_dir and codex_completionist_state.has_old_shared_tally(self._plugin_dir):
            self._rebuild_pending = True
            self._persist()
        if self._rebuild_pending:
            self._set_status(f"Rebuilding {cmdr}'s Codex tally from your journals (one time: Codex is now per commander)...")
            self._start_backfill(manual=False)
        else:
            self._catch_up()
        self._refresh_summary()
        codex_completionist_window.refresh_if_open(self._tally)

    def _catch_up(self) -> None:
        """Count finds made while EDMC was closed. A tally with no starting point (a new install) only sets one now (the
        full history is the BKF button's job); after that, only the journals written since the last counted find are
        read."""
        try:
            if not self._tally.last_event_at:
                self._tally.advance_watermark(time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
                self._persist()
                return
            counted = self._tally.apply_new(codex_backfill.scan_since(self._tally.last_event_at, self._tally.owner))
            if counted:
                logger.info("Codex Completionist counted %d find(s) made while EDMC was closed", counted)
                self._persist()
        except Exception:
            logger.exception("Codex Completionist journal catch-up failed")

    def stop(self) -> None:
        self._persist()

    def _persist(self) -> None:
        if self._plugin_dir is None or not self._tally.owner:
            return
        codex_completionist_state.save_commander(self._plugin_dir, self._tally.owner, {
            "entries": self._tally.snapshot(), "last_event_at": self._tally.last_event_at,
            "rebuild_pending": self._rebuild_pending,
        })

    # --- journal dispatch -----------------------------------------------

    def handle_event(self, entry: Dict[str, Any], cmdr: str, system: Optional[str], station: Optional[str], state: Dict[str, Any]) -> None:
        if cmdr and commander_data.key_for(cmdr) != commander_data.key_for(self._tally.owner):
            self._switch_cmdr(cmdr)
        if entry.get("event") != "CodexEntry" or not self._tally.owner:
            return
        self._tally.record(entry, system)
        self._tally.advance_watermark(entry.get("timestamp"))
        self._persist()
        self._refresh_summary()

    # --- main-panel widgets -----------------------------------------------

    def build_panel(self, parent: tk.Frame) -> None:
        self._parent = parent

        body = panelkit.collapsible_section(parent, "Codex Completionist", "wntb_codex_completionist_collapsed")
        self._set_title_note = getattr(body, "set_title_suffix", None)

        self._summary_var = tk.StringVar(value=_summary_text(self._tally, self._rebuilding) if enabled() else _DISABLED_TEXT)
        panelkit.wrap_label(body, textvariable=self._summary_var, anchor="w").grid(
            row=1, column=0, columnspan=3, sticky=tk.W, pady=(2, 0),
        )

        button_row = tk.Frame(body)
        button_row.grid(row=2, column=0, columnspan=3, sticky=tk.W, pady=(2, 0))
        details_button = tk.Button(button_row, text="DET", command=self._on_view_details)
        details_button.pack(side=tk.LEFT)
        panelkit.add_tooltip(details_button, "View Details - open the full Codex tally")
        backfill_button = tk.Button(button_row, text="BKF", command=self._on_backfill)
        backfill_button.pack(side=tk.LEFT, padx=(4, 0))
        panelkit.add_tooltip(
            backfill_button, "Backfill from Journal History - scan your old journal files for Codex entries you already found")

        self._status_var = tk.StringVar(value="")
        panelkit.wrap_label(body, textvariable=self._status_var, fg="grey").grid(
            row=3, column=0, columnspan=3, sticky=tk.W,
        )

        self._refresh_summary()   # shows the "rebuilding" note if the first commander's rebuild began before this panel was built
        parent.after(200, self._poll_backfill_queue)

    def _refresh_summary(self) -> None:
        if self._summary_var is not None and enabled():
            self._summary_var.set(_summary_text(self._tally, self._rebuilding))
        if self._set_title_note is not None:
            self._set_title_note(" — rebuilding..." if self._rebuilding and enabled() else "")

    def _set_status(self, message: str) -> None:
        if self._status_var is not None:
            self._status_var.set(message)

    # --- button handlers ---------------------------------------------------

    def _on_view_details(self) -> None:
        if self._parent is None:
            return
        codex_completionist_window.show(self._parent, self._tally, self._plugin_dir or "")

    def _on_backfill(self) -> None:
        if not self._tally.owner:
            self._set_status("Waiting for your commander: play or log in first.")
            return
        self._set_status(f"Scanning journal history for {self._tally.owner}'s codex entries...")
        self._start_backfill(manual=True)

    def _start_backfill(self, manual: bool) -> None:
        self._rebuilding = True
        self._refresh_summary()
        threading.Thread(target=self._backfill_worker, args=(self._tally.owner, manual), daemon=True).start()

    def _backfill_worker(self, cmdr: str, manual: bool) -> None:
        """Runs off the main thread — must not touch any Tk widget directly."""
        try:
            entries = codex_backfill.scan_all_codex_entries(cmdr)
        except Exception:
            logger.exception("_backfill_worker failed")
            entries = []
        self._backfill_result_queue.put((commander_data.key_for(cmdr), entries, manual))

    def _poll_backfill_queue(self) -> None:
        """Runs on the main thread via after() — safe to touch widgets here."""
        try:
            key, entries, manual = self._backfill_result_queue.get_nowait()
        except queue.Empty:
            pass
        else:
            self._rebuilding = False
            self._refresh_summary()
            if key != commander_data.key_for(self._tally.owner):
                # The active commander changed while it was reading: these are another commander's finds. Leave the
                # tally alone; a pending rebuild runs again when that commander is next seen, or press BKF again.
                self._set_status("Commander changed during the scan: nothing was added. Press BKF again.")
            else:
                before = self._tally.total_distinct
                self._tally.merge_history(entries)
                self._tally.advance_watermark(max((e.get("timestamp") or "" for e in entries), default=""))
                self._rebuild_pending = False
                self._persist()
                self._refresh_summary()
                codex_completionist_window.refresh_if_open(self._tally)
                added = self._tally.total_distinct - before
                self._set_status(
                    f"Backfill scanned {len(entries)} historical codex event(s) for {self._tally.owner} — "
                    f"{added} new distinct entr{'y' if added == 1 else 'ies'}"
                )
        if self._parent is not None:
            self._parent.after(200, self._poll_backfill_queue)

    def _refresh_enabled_display(self) -> None:
        if self._summary_var is None:
            return
        self._summary_var.set(_summary_text(self._tally, self._rebuilding) if enabled() else _DISABLED_TEXT)

    # --- Settings tab --------------------------------------------------

    def build_settings(self, notebook: nb.Notebook) -> None:
        frame = nb.Frame(notebook)
        frame.columnconfigure(0, weight=1)
        notebook.add(frame, text="Codex Completionist")

        self._enabled_var = tk.BooleanVar(value=enabled())

        nb.Label(frame, text="Codex Completionist", font=("TkDefaultFont", 9, "bold")).grid(
            row=0, column=0, sticky=tk.W, padx=10, pady=(10, 4),
        )
        nb.Label(
            frame,
            text=(
                "Tracks a personal tally of every codex entry you've ever found (biological, "
                "geological, Guardian, human, Thargoid, and more), purely from your own journal "
                "history — local and read-only, no network calls, and no galaxy-wide completion "
                "percentage (that's Canonn's own job, not duplicated here)."
            ),
            wraplength=440, justify=tk.LEFT,
        ).grid(row=1, column=0, sticky=tk.W, padx=10, pady=(0, 4))
        nb.Checkbutton(
            frame, text="Track codex entries", variable=self._enabled_var,
        ).grid(row=2, column=0, sticky=tk.W, padx=10, pady=(0, 4))

        HyperlinkLabel(
            frame, text="View Canonn Codex", background=nb.Label().cget("background"),
            url=CANONN_CODEX_URL, underline=True,
        ).grid(row=3, column=0, sticky=tk.W, padx=10, pady=(0, 10))

    def save_settings(self) -> None:
        if self._enabled_var is None:
            return
        config.set(_CFG_ENABLED, self._enabled_var.get())
        self._refresh_enabled_display()


controller = CodexCompletionistController()


def start(plugin_dir: str) -> None:
    controller.start(plugin_dir)


def stop() -> None:
    controller.stop()


def handle_event(entry: Dict[str, Any], cmdr: str, system: Optional[str], station: Optional[str], state: Dict[str, Any]) -> None:
    controller.handle_event(entry, cmdr, system, station, state)


def build_panel(parent: tk.Frame) -> None:
    controller.build_panel(parent)


def build_settings(notebook: nb.Notebook) -> None:
    controller.build_settings(notebook)


def save_settings() -> None:
    controller.save_settings()
