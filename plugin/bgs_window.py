"""BGS Report window - the per-system breakdown for one tick period, with the
same `show(parent, ...)` entry point and geometry-persistence convention as
the other WNTB windows, built on the shared window kit (plugin/uikit - see
docs/WINDOW_FRAMEWORK_SPEC.md).

A drop-down at the top picks the tick period: the current one, or any
archived earlier tick (the archive length is a Settings option). Below it,
one tab per system the commander has acted in during that period (the
system they're in now always has a tab in the current period). Each tab has
two tables: where every faction there stands (state, influence and how far
each moved since before the tick), and what the commander did to each
(missions done/failed/abandoned with +/- INF, vouchers, trade, exploration,
crimes). "Copy Summary" puts every period and system on the clipboard as
plain text."""

from __future__ import annotations

import logging
import os
import tkinter as tk
from typing import Dict, List, Optional, Tuple

from config import appname, config

from . import bgs_format, panelkit
from .bgs_ledger import FactionTrack, PeriodView
from .bgs_tracker import FactionActivity
from .uikit import palette as P
from .uikit import style
from .uikit.shell import WindowShell
from .uikit.table import Column, DataTable
from .uikit.widgets import Combobox, Tabs, clip

plugin_name = os.path.basename(os.path.dirname(__file__))
logger = logging.getLogger(f"{appname}.{plugin_name}")

CONFIG_GEOMETRY = "wntb_bgs_window_geometry"

MIN_WIDTH = 900
MIN_HEIGHT = 420
DEFAULT_SIZE = (960, 600)
MAX_TABS = 8
"""Most system tabs shown at once (the tab bar doesn't wrap). The newest
systems win; Copy Summary always includes every system."""

_window: Optional["BgsWindow"] = None


def show(parent: tk.Misc, views: List[PeriodView], current_system: Optional[str]) -> None:
    """Open the BGS report window, or raise/refresh it if already open."""
    global _window
    if _window is not None and _window.alive:
        _window.refresh(views, current_system)
        _window.lift()
        return
    _window = BgsWindow(parent, views, current_system)


def refresh_if_open(views: List[PeriodView], current_system: Optional[str]) -> None:
    """Called from bgs_panel.py whenever fresh data arrives - keeps an
    already-open report window live instead of going stale until the
    commander closes and reopens it."""
    if _window is not None and _window.alive:
        _window.refresh(views, current_system)


_FACTION_COLUMNS = (
    Column("faction", "Faction", 190, stretch=True, max_chars=40),
    Column("state", "State", 130, max_chars=28),
    Column("influence", "Influence (change)", 140, anchor="e"),
    Column("pending", "Pending", 110, max_chars=40),
    Column("recovering", "Recovering", 110, max_chars=40),
    Column("active", "Active", 110, max_chars=40),
)
_ACTIVITY_COLUMNS = (
    Column("faction", "Faction", 160, stretch=True, max_chars=40),
    Column("done", "Done", 55, anchor="e"),
    Column("inf", "INF +/-", 75, anchor="e"),
    Column("failed", "Failed", 55, anchor="e"),
    Column("abandoned", "Aband.", 60, anchor="e"),
    Column("bounty", "Bounties", 95, anchor="e"),
    Column("bonds", "Bonds", 90, anchor="e"),
    Column("trade", "Trade", 95, anchor="e"),
    Column("exploration", "Explor.", 95, anchor="e"),
    Column("crimes", "Crimes", 60, anchor="e"),
)


def _count(value: int) -> str:
    return str(value) if value else ""


def _credits(value: int, signed: bool = False) -> str:
    if not value:
        return ""
    return f"{value:+,}" if signed else f"{value:,}"


class _SystemTab:
    """The two tables on one system's tab."""

    def __init__(self, content: tk.Frame) -> None:
        tk.Label(content, text="FACTIONS", fg=P.MUTED, bg=P.PANE, anchor="w", padx=P.PAD,
                 font=style.font(P.FONT_SMALL)).pack(fill="x", pady=(P.PAD_SM, 0))
        self.factions = DataTable(content, _FACTION_COLUMNS, sortable=False, visible_rows=8,
                                  empty_text="No faction data recorded for this system.")
        self.factions.pack(fill="x", padx=P.PAD, pady=(2, P.PAD_SM))
        tk.Label(content, text="WHAT YOU DID", fg=P.MUTED, bg=P.PANE, anchor="w", padx=P.PAD,
                 font=style.font(P.FONT_SMALL)).pack(fill="x", pady=(P.PAD_SM, 0))
        self.activity = DataTable(content, _ACTIVITY_COLUMNS, sortable=False,
                                  empty_text="Nothing done here this tick.")
        self.activity.pack(fill="both", expand=True, padx=P.PAD, pady=(2, P.PAD))

    def fill(self, view: PeriodView, system: str) -> None:
        self.factions.clear()
        tracks = sorted(view.tracks_for(system), key=lambda t: (
            not (t.latest() and t.latest().is_controlling), t.faction.casefold()))
        activity = {a.faction.casefold(): a for a in view.activity_for(system)}
        shown = set()
        for track in tracks:
            shown.add(track.faction.casefold())
            self.factions.append(self._faction_row(track))
        for key, act in sorted(activity.items()):  # acted on a faction we have no snapshot of
            if key not in shown:
                self.factions.append((act.faction, "", "", "", "", ""))

        self.activity.clear()
        for act in sorted(activity.values(), key=lambda a: a.faction.casefold()):
            self.activity.append(self._activity_row(act))

    @staticmethod
    def _faction_row(track: FactionTrack) -> Tuple[str, ...]:
        now = track.latest()
        label = f"★ {track.faction}" if now and now.is_controlling else track.faction
        return (
            label, bgs_format.state_change_text(track), bgs_format.influence_change_text(track),
            ", ".join(now.pending_states) if now else "",
            ", ".join(now.recovering_states) if now else "",
            ", ".join(now.active_states) if now else "",
        )

    @staticmethod
    def _activity_row(act: FactionActivity) -> Tuple[str, ...]:
        return (
            act.faction, _count(act.missions),
            f"+{act.inf_plus}/-{act.inf_minus}" if act.missions else "",
            _count(act.missions_failed), _count(act.missions_abandoned),
            _credits(act.bounty_credits), _credits(act.combat_bond_credits),
            _credits(act.trade_profit_credits, signed=True), _credits(act.exploration_credits),
            _count(act.crimes),
        )


class BgsWindow:
    def __init__(self, parent: tk.Misc, views: List[PeriodView], current_system: Optional[str]) -> None:
        self._shell = WindowShell(
            parent, "BGS Report", "", size=DEFAULT_SIZE, min_size=(MIN_WIDTH, MIN_HEIGHT),
            load_geometry=lambda: config.get_str(CONFIG_GEOMETRY) or "",
            save_geometry=lambda geometry: config.set(CONFIG_GEOMETRY, geometry))
        self._shell.window.protocol("WM_DELETE_WINDOW", self.close)
        self._toplevel = self._shell.window
        self._copy_button = self._shell.add_action("Copy Summary", self._on_copy)

        picker = tk.Frame(self._shell.body, bg=P.BG)
        picker.pack(fill="x", padx=P.PAD, pady=(P.PAD_SM, P.PAD_SM))
        tk.Label(picker, text="TICK", fg=P.MUTED, bg=P.BG, font=style.font(P.FONT_SMALL)).pack(side="left")
        self._period_var = tk.StringVar()
        self._period_box = Combobox(picker, textvariable=self._period_var, state="readonly", width=46)
        self._period_box.pack(side="left", padx=(P.PAD_SM, 0))
        self._period_box.bind("<<ComboboxSelected>>", lambda _e: self._on_period_selected())

        self._stage = tk.Frame(self._shell.body, bg=P.PANE)
        self._stage.pack(fill="both", expand=True, pady=(0, P.PAD_SM))

        self._views: List[PeriodView] = []
        self._current_system: Optional[str] = None
        self._labels: Dict[str, PeriodView] = {}
        self._selected_key: Optional[Tuple] = None
        self._tabs: Optional[Tabs] = None
        self._tab_systems: List[str] = []
        self._tab_widgets: Dict[str, _SystemTab] = {}
        self._tab_period_key: Optional[Tuple] = None
        self._empty_label: Optional[tk.Label] = None
        self.refresh(views, current_system)

    @property
    def alive(self) -> bool:
        return self._shell.alive

    def lift(self) -> None:
        self._toplevel.deiconify()
        self._toplevel.lift()

    @staticmethod
    def _key(view: PeriodView) -> Tuple:
        return (view.tick_start, view.tick_end, view.current)

    def refresh(self, views: List[PeriodView], current_system: Optional[str]) -> None:
        if not self.alive:
            return
        self._views = list(views)
        self._current_system = current_system
        self._labels = {}
        for view in self._views:
            label = bgs_format.period_label(view)
            while label in self._labels:
                label += " "
            self._labels[label] = view
        self._period_box.configure(values=list(self._labels))

        selected = next((v for v in self._views if self._key(v) == self._selected_key), None)
        if selected is None:
            selected = self._views[0] if self._views else None
        if selected is not None:
            self._selected_key = self._key(selected)
            self._period_var.set(next(lbl for lbl, v in self._labels.items() if v is selected))
        self._show_period(selected)

    def _on_period_selected(self) -> None:
        view = self._labels.get(self._period_var.get())
        if view is not None:
            self._selected_key = self._key(view)
            self._show_period(view)

    def _show_period(self, view: Optional[PeriodView]) -> None:
        if view is None:
            self._shell.set_subtitle("")
            return
        systems = view.systems(self._current_system)
        shown = systems[:MAX_TABS]
        extra = len(systems) - len(shown)
        self._shell.set_subtitle(
            f"{len(systems)} system(s)" + (f" — showing the newest {MAX_TABS}; Copy Summary has all" if extra > 0 else ""))

        period_key = self._key(view)
        if self._tabs is None or shown != self._tab_systems or period_key != self._tab_period_key:
            self._rebuild_tabs(shown, period_key)
        for system, tab in self._tab_widgets.items():
            tab.fill(view, system)

    def _rebuild_tabs(self, systems: List[str], period_key: Tuple) -> None:
        previous = self._tab_systems[self._tabs.selected] if self._tabs and self._tab_systems and \
            0 <= self._tabs.selected < len(self._tab_systems) else None
        for child in self._stage.winfo_children():
            child.destroy()
        self._tabs = None
        self._tab_widgets = {}
        self._tab_systems = list(systems)
        self._tab_period_key = period_key

        if not systems:
            tk.Label(self._stage, text="No BGS activity recorded for this tick yet.", fg=P.MUTED, bg=P.PANE,
                     pady=P.PAD).pack(fill="x")
            return
        tabs = Tabs(self._stage)
        tabs.pack(fill="both", expand=True)
        for system in systems:
            self._tab_widgets[system] = _SystemTab(tabs.add(clip(system, 18)))
        if previous in systems:  # stay on the system being looked at across refreshes
            tabs.select(systems.index(previous))
        self._tabs = tabs

    def _on_copy(self) -> None:
        text = bgs_format.summary_text(self._views, self._current_system)
        if panelkit.copy_to_clipboard(self._toplevel, text):
            original = self._copy_button.cget("text")
            self._copy_button.configure(text="Copied!")
            self._copy_button.after(1500, lambda: self._copy_button.configure(text=original))

    def close(self) -> None:
        self._shell.close()
