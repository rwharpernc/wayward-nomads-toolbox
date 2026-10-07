"""Session details window for Powerplay mode: live breakdown + history.

Built on the shared window kit (plugin/uikit: WindowShell, Tabs, DataTable - see
docs/WINDOW_FRAMEWORK_SPEC.md); the numbers and wording are unchanged."""

from __future__ import annotations

import logging
import os
import tkinter as tk
from tkinter import messagebox
from typing import Any, Dict, List, Optional

from config import appname, config

from . import panelkit
from .formulas import ACTIVITIES, ACTIVITY_LABELS, NO_CP_ACTIVITIES, merits_to_cp
from .powerplay import PowerplayTracker, clipboard_template, ratio_for
from .powerplay_clipboard import format_system_line
from .session import (
    SessionManager,
    duration_hours,
    per_hour,
    system_merit_total,
    system_totals,
    total_merits,
    visited_systems,
)
from .powerplay_systems_tab import CyclesTab, SystemsPane, SystemsTab
from .uikit import palette as P
from .uikit import style
from .uikit.shell import WindowShell
from .uikit.table import Column, DataTable
from .uikit.widgets import ScrollFrame, Tabs, field_grid, section_header

plugin_name = os.path.basename(os.path.dirname(__file__))
logger = logging.getLogger(f"{appname}.{plugin_name}")

CONFIG_GEOMETRY = "wntb_powerplay_window_geometry"

MIN_WIDTH = 820
MIN_HEIGHT = 560
DEFAULT_SIZE = (1040, 720)

# Marks the row for whatever system the commander is in right now in the "By
# System" table, so it doesn't get lost among other rows once a session has
# touched several systems.
_CURRENT_SYSTEM_MARK = "▶ "

_SYSTEM_COLUMNS = (
    Column("system", "System", 200),
    Column("merits", "Merits", 90, anchor="e"),
    Column("cp", "Est. CP", 90, anchor="e"),
    Column("breakdown", "Activity breakdown", 320, stretch=True, max_chars=90),
)
_ACTIVITY_COLUMNS = (
    Column("activity", "Activity", 180, stretch=True),
    Column("merits", "Merits", 110, anchor="e"),
    Column("ratio", "Merits/CP", 110, anchor="e"),
    Column("cp", "Est. CP", 110, anchor="e"),
    Column("cp_hr", "CP/hr", 110, anchor="e"),
)
_HISTORY_COLUMNS = (
    Column("started", "Started", 190),
    Column("cmdr", "Commander", 130),
    Column("power", "Power", 170, stretch=True),
    Column("duration", "Duration", 90, anchor="e"),
    Column("merits", "Merits", 100, anchor="e"),
    Column("cp", "Est. CP", 100, anchor="e"),
)

_window: Optional["SessionWindow"] = None


def show(
    parent: tk.Misc, sessions: SessionManager, pp: PowerplayTracker, current_system: Optional[str],
    systems: Optional[SystemsPane] = None,
) -> None:
    """Open the sessions window, or raise it if already open."""
    global _window

    if _window is not None and _window.alive:
        _window.refresh(current_system, systems)
        _window.lift()
        return

    _window = SessionWindow(parent, sessions, pp, current_system, systems)


def refresh(current_system: Optional[str], systems: Optional[SystemsPane] = None) -> None:
    if _window is not None and _window.alive:
        _window.refresh(current_system, systems)


def close() -> None:
    if _window is not None and _window.alive:
        _window.close()


class SessionWindow:
    def __init__(
        self, parent: tk.Misc, sessions: SessionManager, pp: PowerplayTracker, current_system: Optional[str],
        systems: Optional[SystemsPane] = None,
    ) -> None:
        self._sessions = sessions
        self._pp = pp
        self._current_system = current_system
        self._systems = systems

        self._shell = WindowShell(
            parent, "Powerplay Sessions", "", size=DEFAULT_SIZE, min_size=(MIN_WIDTH, MIN_HEIGHT),
            load_geometry=lambda: config.get_str(CONFIG_GEOMETRY) or "",
            save_geometry=lambda geometry: config.set(CONFIG_GEOMETRY, geometry))
        self._shell.window.protocol("WM_DELETE_WINDOW", self.close)
        self._toplevel = self._shell.window

        self._shell.add_action("Refresh", lambda: self.refresh(self._current_system))
        self._copy_button = self._shell.add_action("Copy Progress", self._copy_progress)
        self._shell.add_action("Reset Current System", self._reset_current_system)
        self._shell.add_action("Reset Session", self._reset_session)

        tabs = Tabs(self._shell.body)
        tabs.pack(fill="both", expand=True, pady=(0, P.PAD_SM))
        self._current_tab = _CurrentTab(tabs.add("Current session"))
        self._systems_tab = SystemsTab(tabs.add("Systems"), self._toplevel)
        self._cycles_tab = CyclesTab(tabs.add("Cycles"))
        self._history_tab = _HistoryTab(tabs.add("History"))

        self.refresh(current_system)

    @property
    def alive(self) -> bool:
        return self._shell.alive

    def lift(self) -> None:
        self._toplevel.deiconify()
        self._toplevel.lift()

    def refresh(self, current_system: Optional[str], systems: Optional[SystemsPane] = None) -> None:
        if not self.alive:
            return
        self._current_system = current_system
        if systems is not None:
            self._systems = systems
        self._current_tab.update(self._sessions.current, self._pp, current_system)
        self._systems_tab.update(self._systems, current_system)
        self._cycles_tab.update(self._systems)
        self._history_tab.update(self._sessions.history, self._sessions.current)

    def _reset_session(self) -> None:
        """Zeroes this session's merit counts entirely (session identity untouched) — mainly for correcting a bad count, e.g.
        the donation-mission duplicate-merit journal bug. Confirms first
        since it destroys in-memory/persisted counters."""
        if not messagebox.askyesno(
            "Reset Session",
            "Zero this session's merit totals (by system and by activity)?\n\n"
            "This does not end the session, and can't be undone.",
            parent=self._toplevel,
        ):
            return
        self._sessions.reset_session()
        self.refresh(self._current_system)

    def _reset_current_system(self) -> None:
        if not self._current_system:
            messagebox.showinfo("Reset Current System", "No current system to reset.", parent=self._toplevel)
            return
        if not messagebox.askyesno(
            "Reset Current System",
            f"Zero merits earned in {self._current_system} this session (subtracted from the "
            "session totals too)?\n\nThis can't be undone.",
            parent=self._toplevel,
        ):
            return
        self._sessions.reset_system(self._current_system)
        self.refresh(self._current_system)

    def _copy_progress(self) -> None:
        """Copies one formatted line per system in the By System table to
        the clipboard, using the user's configured template (Settings ->
        Powerplay -> Clipboard)."""
        session = self._sessions.current
        systems = visited_systems(session)
        if self._current_system and self._current_system not in systems:
            systems = [self._current_system] + systems
        elif self._current_system in systems:
            systems = [self._current_system] + [s for s in systems if s != self._current_system]

        template = clipboard_template()
        lines = []
        for name in systems:
            merits = system_merit_total(session, name)
            cp = sum(
                merits_to_cp(system_totals(session, name).get(activity, 0), ratio_for(activity))
                for activity in ACTIVITIES
                if activity not in NO_CP_ACTIVITIES
            )
            state = self._pp.system_state if name == self._current_system and self._pp.system_state else "—"
            lines.append(format_system_line(template, system=name, merits=f"{merits:,}", cp=f"{cp:,.1f}", state=state))

        panelkit.copy_to_clipboard(self._toplevel, "\n".join(lines))

        original_text = self._copy_button.cget("text")
        self._copy_button.configure(text="Copied!")
        self._copy_button.after(1500, lambda: self._copy_button.configure(text=original_text))

    def close(self) -> None:
        self._shell.close()


class _CurrentTab:
    """Live breakdown of the in-progress session: who/how long, what's been
    earned in each system visited, and the same broken out by activity."""

    def __init__(self, parent: tk.Frame) -> None:
        scroll = ScrollFrame(parent)
        scroll.pack(fill="both", expand=True)
        body = scroll.body

        # --- Session heading: commander/power/started/duration -----------
        self._heading = tk.Frame(body, bg=P.PANE)
        self._heading.pack(fill="x", padx=P.PAD, pady=(P.PAD, 4))

        # --- By system -----------------------------------------------------
        section_header(body, "By System").pack(fill="x")
        tk.Label(
            body, bg=P.PANE, fg=P.MUTED, anchor="w", justify="left", wraplength=900, padx=P.PAD,
            text="What you've earned in each system this session — the current one is marked and stays first.",
        ).pack(fill="x", pady=(0, 6))
        self._system_table = DataTable(body, _SYSTEM_COLUMNS, sortable=False, visible_rows=6)
        self._system_table.pack(fill="x", padx=P.PAD, pady=(0, P.PAD))

        # --- By activity (session-wide) ------------------------------------
        section_header(body, "By Activity (session total)").pack(fill="x")
        self._activity_table = DataTable(body, _ACTIVITY_COLUMNS, sortable=False,
                                         visible_rows=len(ACTIVITIES) + 1)
        self._activity_table.pack(fill="x", padx=P.PAD, pady=(0, P.PAD))

        # --- Live PowerPlay context ------------------------------------------
        section_header(body, "Current PowerPlay Context").pack(fill="x")
        self._context = tk.Frame(body, bg=P.PANE)
        self._context.pack(fill="x", padx=P.PAD, pady=(0, 8))

        tk.Label(
            body, bg=P.PANE, fg=P.WARN, anchor="w", justify="left", wraplength=900, padx=P.PAD,
            text=(
                "The journal doesn't say which activity your merits were for, so WNTB infers it from "
                "who controlled the system when they landed: uncontrolled = Acquisition, your Power = "
                "Reinforcement, a rival Power = Undermining. If a system's breakdown above looks wrong, "
                "compare it against the context shown here."
            ),
        ).pack(fill="x", pady=(0, P.PAD))

    def update(self, session: Dict[str, Any], pp: PowerplayTracker, current_system: Optional[str]) -> None:
        cmdr = session.get("cmdr") or "(unknown)"
        power = pp.pledge_summary() or session.get("power") or "(not pledged)"
        started = session.get("started_at") or "?"
        hours = duration_hours(session)

        for child in self._heading.winfo_children():
            child.destroy()
        field_grid(self._heading, 0, (("Commander:", cmdr), ("Power:", power)))
        field_grid(self._heading, 1, (("Started:", started), ("Duration:", f"{hours:.2f}h")))

        for child in self._context.winfo_children():
            child.destroy()
        name = current_system or pp.system_name or "(none seen yet)"
        state = pp.system_state or "(none seen yet)"
        controller = pp.system_controller or "(none)"
        powers = ", ".join(pp.system_powers) if pp.system_powers else "(none)"
        field_grid(self._context, 0, (("System:", name), ("State:", state)))
        field_grid(self._context, 1, (("Controller:", controller), ("Rival Powers:", powers)))

        self._update_system_table(session, current_system)
        self._update_activity_table(session, hours)

    def _update_system_table(self, session: Dict[str, Any], current_system: Optional[str]) -> None:
        self._system_table.clear()

        systems = visited_systems(session)
        # The current system leads the list even if it hasn't earned any
        # merits yet this visit, so it's never missing from its own table.
        if current_system and current_system not in systems:
            systems = [current_system] + systems
        elif current_system in systems:
            systems = [current_system] + [s for s in systems if s != current_system]

        if not systems:
            self._system_table.append(("(no systems visited yet)", "", "", ""))
            return

        for name in systems:
            totals = system_totals(session, name)
            merits = system_merit_total(session, name)
            cp = sum(
                merits_to_cp(totals.get(activity, 0), ratio_for(activity))
                for activity in ACTIVITIES
                if activity not in NO_CP_ACTIVITIES
            )
            breakdown = " · ".join(
                f"{ACTIVITY_LABELS[activity]} {totals[activity]:,}"
                for activity in ACTIVITIES
                if totals.get(activity)
            ) or "—"

            label = f"{_CURRENT_SYSTEM_MARK}{name} (current)" if name == current_system else name
            self._system_table.append((label, f"{merits:,}", f"{cp:,.1f}" if merits else "—", breakdown))

    def _update_activity_table(self, session: Dict[str, Any], hours: float) -> None:
        self._activity_table.clear()
        totals = session.get("totals", {})

        merits_sum = 0
        cp_sum = 0.0
        for activity in ACTIVITIES:
            merits = totals.get(activity, 0)
            merits_sum += merits
            has_cp = activity not in NO_CP_ACTIVITIES
            ratio = ratio_for(activity) if has_cp else 0.0
            cp = merits_to_cp(merits, ratio) if has_cp else 0.0
            cp_sum += cp
            cp_hr = per_hour(cp, hours)
            self._activity_table.append((
                ACTIVITY_LABELS[activity],
                f"{merits:,}",
                f"{ratio:g}" if ratio else "—",
                f"{cp:,.1f}" if has_cp else "—",
                f"{cp_hr:,.1f}" if has_cp and hours > 0 else "—",
            ))

        self._activity_table.append((
            "Total",
            f"{merits_sum:,}",
            "",
            f"{cp_sum:,.1f}",
            f"{per_hour(cp_sum, hours):,.1f}" if hours > 0 else "—",
        ))


def _cumulative_summary(sessions: List[Dict[str, Any]]) -> str:
    """'All sessions — Merits: 12,345   CP: Acquisition 120 / Reinforcement 80 / Undermining 40'."""
    merit_totals: Dict[str, int] = {activity: 0 for activity in ACTIVITIES}
    for s in sessions:
        totals = s.get("totals", {})
        for activity in ACTIVITIES:
            merit_totals[activity] += totals.get(activity, 0)

    cumulative_merits = sum(merit_totals.values())
    cp_bits = " / ".join(
        f"{ACTIVITY_LABELS[activity]} {merits_to_cp(merit_totals[activity], ratio_for(activity)):,.1f}"
        for activity in ACTIVITIES
        if activity not in NO_CP_ACTIVITIES
    )

    return "   ".join([f"All sessions — Merits: {cumulative_merits:,}", f"CP: {cp_bits}"])


class _HistoryTab:
    """Past sessions, most recent first."""

    def __init__(self, parent: tk.Frame) -> None:
        section_header(parent, "All Sessions").pack(fill="x")
        self._summary_label = tk.Label(parent, text="", bg=P.PANE, fg=P.TEXT, anchor="w", justify="left",
                                       padx=P.PAD, pady=P.PAD_SM, font=style.font(P.FONT_BOLD))
        self._summary_label.pack(side="bottom", fill="x")
        self._table = DataTable(parent, _HISTORY_COLUMNS, sortable=False)
        self._table.pack(fill="both", expand=True, padx=P.PAD, pady=(0, P.PAD_SM))

    def update(self, history: List[Dict[str, Any]], current: Dict[str, Any]) -> None:
        self._table.clear()

        sessions = list(history) + [current]
        self._summary_label.configure(text=_cumulative_summary(sessions))
        for session in reversed(sessions):
            hours = duration_hours(session)
            cp_sum = sum(
                merits_to_cp(session.get("totals", {}).get(activity, 0), ratio_for(activity))
                for activity in ACTIVITIES
                if activity not in NO_CP_ACTIVITIES
            )
            is_current = session is current

            self._table.append((
                session.get("started_at", "?") + (" (live)" if is_current else ""),
                session.get("cmdr") or "?",
                session.get("power") or "—",
                f"{hours:.2f}h",
                f"{total_merits(session):,}",
                f"{cp_sum:,.1f}",
            ))

        if not sessions:
            self._table.append(("(no sessions yet)", "", "", "", "", ""))
