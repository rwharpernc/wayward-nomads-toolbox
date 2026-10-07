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
from typing import Any, Dict, List, Optional

import tkinter as tk

import myNotebook as nb
from config import appname, config
from ttkHyperlinkLabel import HyperlinkLabel

from . import codex_backfill, codex_completionist_state, codex_completionist_window, panelkit
from .codex_completionist import CodexTally

plugin_name = os.path.basename(os.path.dirname(__file__))
logger = logging.getLogger(f"{appname}.{plugin_name}")

PANEL_PLACEMENT = "exploration"

_CFG_ENABLED = "wntb_codex_completionist_enabled"

CANONN_CODEX_URL = "https://canonn.science/codex/"

_DISABLED_TEXT = "Codex Completionist is disabled — see Settings."
_EMPTY_TEXT = "No codex entries recorded yet this install — fly, scan, and discover things."


def enabled() -> bool:
    # On by default - pure local journal tracking, no network calls.
    return config.get_bool(_CFG_ENABLED, default=True)


def _summary_text(tally: CodexTally) -> str:
    if tally.total_distinct == 0:
        return _EMPTY_TEXT
    counts = tally.category_counts()
    top = sorted(counts.items(), key=lambda pair: pair[1], reverse=True)[:3]
    top_text = ", ".join(f"{name} ({count})" for name, count in top)
    return f"{tally.total_distinct:,} distinct entries, {tally.total_finds:,} total finds — {top_text}"


class CodexCompletionistController:
    def __init__(self) -> None:
        self._plugin_dir: Optional[str] = None
        self._tally = CodexTally()

        self._backfill_result_queue: "queue.Queue[List[Dict[str, Any]]]" = queue.Queue()

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
        self._plugin_dir = plugin_dir
        saved = codex_completionist_state.load_state(plugin_dir)
        if saved:
            try:
                self._tally.restore(saved)
                logger.info("Restored Codex Completionist tally: %d distinct entries", self._tally.total_distinct)
            except Exception:
                logger.exception("Failed to restore saved Codex Completionist state; starting fresh")

    def stop(self) -> None:
        if self._plugin_dir is None:
            return
        codex_completionist_state.save_state(self._plugin_dir, self._tally.snapshot())

    def _persist(self) -> None:
        if self._plugin_dir is not None:
            codex_completionist_state.save_state(self._plugin_dir, self._tally.snapshot())

    # --- journal dispatch -----------------------------------------------

    def handle_event(self, entry: Dict[str, Any], cmdr: str, system: Optional[str], station: Optional[str], state: Dict[str, Any]) -> None:
        if entry.get("event") != "CodexEntry":
            return
        self._tally.record(entry, system)
        self._persist()
        self._refresh_summary()

    # --- main-panel widgets -----------------------------------------------

    def build_panel(self, parent: tk.Frame) -> None:
        self._parent = parent

        body = panelkit.collapsible_section(parent, "Codex Completionist", "wntb_codex_completionist_collapsed")

        self._summary_var = tk.StringVar(value=_summary_text(self._tally) if enabled() else _DISABLED_TEXT)
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

        parent.after(200, self._poll_backfill_queue)

    def _refresh_summary(self) -> None:
        if self._summary_var is not None and enabled():
            self._summary_var.set(_summary_text(self._tally))

    def _set_status(self, message: str) -> None:
        if self._status_var is not None:
            self._status_var.set(message)

    # --- button handlers ---------------------------------------------------

    def _on_view_details(self) -> None:
        if self._parent is None:
            return
        codex_completionist_window.show(self._parent, self._tally, self._plugin_dir or "")

    def _on_backfill(self) -> None:
        self._set_status("Scanning journal history for codex entries...")
        threading.Thread(target=self._backfill_worker, daemon=True).start()

    def _backfill_worker(self) -> None:
        """Runs off the main thread — must not touch any Tk widget directly."""
        try:
            entries = codex_backfill.scan_all_codex_entries()
        except Exception:
            logger.exception("_backfill_worker failed")
            entries = []
        self._backfill_result_queue.put(entries)

    def _poll_backfill_queue(self) -> None:
        """Runs on the main thread via after() — safe to touch widgets here."""
        try:
            entries = self._backfill_result_queue.get_nowait()
        except queue.Empty:
            pass
        else:
            before = self._tally.total_distinct
            for entry in entries:
                self._tally.record(entry, entry.get("System"))
            self._persist()
            self._refresh_summary()
            added = self._tally.total_distinct - before
            self._set_status(
                f"Backfill scanned {len(entries)} historical codex event(s) — {added} new distinct entr{'y' if added == 1 else 'ies'}"
            )
        if self._parent is not None:
            self._parent.after(200, self._poll_backfill_queue)

    def _refresh_enabled_display(self) -> None:
        if self._summary_var is None:
            return
        self._summary_var.set(_summary_text(self._tally) if enabled() else _DISABLED_TEXT)

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
