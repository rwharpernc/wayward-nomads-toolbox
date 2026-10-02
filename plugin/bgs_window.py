"""Detail popup for BGS tracking - the full per-system/per-faction state
and activity breakdown, with the same `show(parent, ...)` entry point and
geometry-persistence convention as the other WNTB windows, built on the shared
window kit (plugin/uikit - see docs/WINDOW_FRAMEWORK_SPEC.md).

Two tabs: "Faction States" (Phase 1's War/Election/Boom/etc.
snapshot per faction) and "Activity Tally" (Phase 2/4's mission/voucher/
trade/exploration tally, split into "This Tick" and "Previous Tick"
sections - see bgs_panel.py's own tick-roll handling for when data moves
from one to the other)."""

from __future__ import annotations

import logging
import os
import tkinter as tk
from typing import Dict, List, Optional

from config import appname, config

from . import panelkit
from .uikit import palette as P
from .uikit import style
from .uikit.shell import WindowShell
from .uikit.table import Column, DataTable
from .uikit.widgets import Tabs
from .bgs_tracker import FactionActivity, FactionSnapshot

plugin_name = os.path.basename(os.path.dirname(__file__))
logger = logging.getLogger(f"{appname}.{plugin_name}")

CONFIG_GEOMETRY = "wntb_bgs_window_geometry"

MIN_WIDTH = 860
MIN_HEIGHT = 420
DEFAULT_SIZE = (900, 560)

_window: Optional["BgsWindow"] = None


def show(
    parent: tk.Misc, snapshots: List[FactionSnapshot], activity: List[FactionActivity],
    previous_activity: List[FactionActivity],
) -> None:
    """Open the BGS report window, or raise/refresh it if already open."""
    global _window
    if _window is not None and _window.alive:
        _window.refresh(snapshots, activity, previous_activity)
        _window.lift()
        return
    _window = BgsWindow(parent, snapshots, activity, previous_activity)


def refresh_if_open(
    snapshots: List[FactionSnapshot], activity: List[FactionActivity], previous_activity: List[FactionActivity],
) -> None:
    """Called from bgs_panel.py whenever fresh data arrives - keeps an
    already-open report window live instead of going stale until the
    commander closes and reopens it."""
    if _window is not None and _window.alive:
        _window.refresh(snapshots, activity, previous_activity)


def _influence_text(snap: FactionSnapshot) -> str:
    return f"{snap.influence * 100:.1f}%" if snap.influence is not None else ""


def _format_activity_line(act: FactionActivity) -> str:
    bits = []
    if act.missions:
        bits.append(f"{act.missions} mission(s), INF +{act.inf_plus}/-{act.inf_minus}")
    if act.bounty_credits:
        bits.append(f"{act.bounty_credits:,}cr bounties")
    if act.combat_bond_credits:
        bits.append(f"{act.combat_bond_credits:,}cr combat bonds")
    if act.trade_profit_credits:
        bits.append(f"{act.trade_profit_credits:,}cr trade profit")
    if act.exploration_credits:
        bits.append(f"{act.exploration_credits:,}cr exploration data")
    return ", ".join(bits) if bits else "no activity"


def _format_summary_text(
    snapshots: List[FactionSnapshot], activity: List[FactionActivity], previous_activity: List[FactionActivity],
) -> str:
    """Plain-text report for the "Copy Summary" button - Discord/forum-
    postable without any Discord-specific formatting (no webhook support,
    per the scoping decision behind this feature)."""
    lines = ["WNTB BGS Report"]

    by_system: Dict[str, List[FactionSnapshot]] = {}
    for snap in snapshots:
        by_system.setdefault(snap.system, []).append(snap)

    lines.append("\n== Faction States ==")
    for system in sorted(by_system, key=str.casefold):
        lines.append(f"\n{system}:")
        for snap in sorted(by_system[system], key=lambda s: s.faction.casefold()):
            marker = "*" if snap.is_controlling else "-"
            influence_text = _influence_text(snap) or "unknown"
            lines.append(
                f"  {marker} {snap.faction} — {snap.faction_state or 'None'}, "
                f"Influence {influence_text}, {snap.happiness or 'unknown happiness'}",
            )
            for label, states in (
                ("Pending", snap.pending_states),
                ("Recovering", snap.recovering_states),
                ("Active", snap.active_states),
            ):
                if states:
                    lines.append(f"      {label}: {', '.join(states)}")

    for label, acts in (("This Tick", activity), ("Previous Tick", previous_activity)):
        active = [a for a in acts if not a.is_empty()]
        lines.append(f"\n== Activity — {label} ==")
        if not active:
            lines.append("  (none)")
            continue
        for act in sorted(active, key=lambda a: (a.system, a.faction.casefold())):
            lines.append(f"  {act.system} / {act.faction}: {_format_activity_line(act)}")

    return "\n".join(lines)


_STATE_COLUMNS = (
    Column("faction", "System / Faction", 190, stretch=True, max_chars=50),
    Column("state", "State", 90),
    Column("influence", "Influence", 85, anchor="e"),
    Column("happiness", "Happiness", 100),
    Column("pending", "Pending", 90, max_chars=40),
    Column("recovering", "Recovering", 100, max_chars=40),
    Column("active", "Active", 90, max_chars=40),
)
_ACTIVITY_COLUMNS = (
    Column("faction", "System / Faction", 170, stretch=True, max_chars=50),
    Column("missions", "Missions", 80, anchor="e"),
    Column("inf", "INF +/-", 80, anchor="e"),
    Column("bounty", "Bounties (cr)", 115, anchor="e"),
    Column("bonds", "Combat Bonds (cr)", 140, anchor="e"),
    Column("trade", "Trade Profit (cr)", 135, anchor="e"),
    Column("exploration", "Exploration (cr)", 130, anchor="e"),
)


class BgsWindow:
    def __init__(
        self, parent: tk.Misc, snapshots: List[FactionSnapshot], activity: List[FactionActivity],
        previous_activity: List[FactionActivity],
    ) -> None:
        self._shell = WindowShell(
            parent, "BGS Report", "", size=DEFAULT_SIZE, min_size=(MIN_WIDTH, MIN_HEIGHT),
            load_geometry=lambda: config.get_str(CONFIG_GEOMETRY) or "",
            save_geometry=lambda geometry: config.set(CONFIG_GEOMETRY, geometry))
        self._shell.window.protocol("WM_DELETE_WINDOW", self.close)
        self._toplevel = self._shell.window
        self._copy_button = self._shell.add_action("Copy Summary", self._on_copy)

        tabs = Tabs(self._shell.body)
        tabs.pack(fill="both", expand=True, pady=(0, P.PAD_SM))

        states_tab = tabs.add("Faction States")
        self._states_table = DataTable(states_tab, _STATE_COLUMNS, sortable=False)
        self._states_table.pack(fill="both", expand=True, padx=P.PAD, pady=P.PAD)

        activity_tab = tabs.add("Activity Tally")
        tk.Label(activity_tab, text="THIS TICK", fg=P.MUTED, bg=P.PANE, anchor="w", padx=P.PAD,
                 font=style.font(P.FONT_SMALL)).pack(fill="x", pady=(P.PAD_SM, 0))
        self._current_activity_table = DataTable(activity_tab, _ACTIVITY_COLUMNS, sortable=False)
        self._current_activity_table.pack(fill="both", expand=True, padx=P.PAD, pady=(2, P.PAD_SM))
        tk.Label(activity_tab, text="PREVIOUS TICK", fg=P.MUTED, bg=P.PANE, anchor="w", padx=P.PAD,
                 font=style.font(P.FONT_SMALL)).pack(fill="x", pady=(P.PAD_SM, 0))
        self._previous_activity_table = DataTable(activity_tab, _ACTIVITY_COLUMNS, sortable=False)
        self._previous_activity_table.pack(fill="both", expand=True, padx=P.PAD, pady=(2, P.PAD))

        self._snapshots: List[FactionSnapshot] = []
        self._activity: List[FactionActivity] = []
        self._previous_activity: List[FactionActivity] = []
        self.refresh(snapshots, activity, previous_activity)

    @property
    def alive(self) -> bool:
        return self._shell.alive

    def lift(self) -> None:
        self._toplevel.deiconify()
        self._toplevel.lift()

    def refresh(
        self, snapshots: List[FactionSnapshot], activity: List[FactionActivity],
        previous_activity: List[FactionActivity],
    ) -> None:
        if not self.alive:
            return
        self._snapshots = list(snapshots)
        self._activity = list(activity)
        self._previous_activity = list(previous_activity)
        self._shell.set_subtitle(f"{len(self._snapshots)} faction(s) tracked")

        self._refresh_states_table()
        self._refresh_activity_table(self._current_activity_table, self._activity)
        self._refresh_activity_table(self._previous_activity_table, self._previous_activity)

    def _refresh_states_table(self) -> None:
        table = self._states_table
        table.clear()

        by_system: Dict[str, List[FactionSnapshot]] = {}
        for snap in self._snapshots:
            by_system.setdefault(snap.system, []).append(snap)

        for system in sorted(by_system, key=str.casefold):
            system_id = table.append((system,) + ("",) * 6, group=True)
            for snap in sorted(by_system[system], key=lambda s: s.faction.casefold()):
                label = f"★ {snap.faction}" if snap.is_controlling else snap.faction
                table.append(
                    (
                        label, snap.faction_state or "None", _influence_text(snap), snap.happiness,
                        ", ".join(snap.pending_states), ", ".join(snap.recovering_states),
                        ", ".join(snap.active_states),
                    ),
                    parent=system_id,
                )

    def _refresh_activity_table(self, table: DataTable, activities: List[FactionActivity]) -> None:
        table.clear()

        by_system: Dict[str, List[FactionActivity]] = {}
        for act in activities:
            if act.is_empty():
                continue
            by_system.setdefault(act.system, []).append(act)

        for system in sorted(by_system, key=str.casefold):
            system_id = table.append((system,) + ("",) * 6, group=True)
            for act in sorted(by_system[system], key=lambda a: a.faction.casefold()):
                table.append(
                    (
                        act.faction,
                        act.missions, f"+{act.inf_plus}/-{act.inf_minus}" if act.missions else "",
                        f"{act.bounty_credits:,}" if act.bounty_credits else "",
                        f"{act.combat_bond_credits:,}" if act.combat_bond_credits else "",
                        f"{act.trade_profit_credits:,}" if act.trade_profit_credits else "",
                        f"{act.exploration_credits:,}" if act.exploration_credits else "",
                    ),
                    parent=system_id,
                )

    def _on_copy(self) -> None:
        text = _format_summary_text(self._snapshots, self._activity, self._previous_activity)
        if panelkit.copy_to_clipboard(self._toplevel, text):
            original = self._copy_button.cget("text")
            self._copy_button.configure(text="Copied!")
            self._copy_button.after(1500, lambda: self._copy_button.configure(text=original))

    def close(self) -> None:
        self._shell.close()
