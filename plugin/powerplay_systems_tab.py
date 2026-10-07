"""The "Systems" tab of the Powerplay Sessions window: one tab per system,
per Powerplay cycle - the Powerplay counterpart of the BGS Report window
(bgs_window.py), with the same pin / close / "Show a system" behaviour.

A drop-down picks the cycle (the live one or an archived week). Below it, one
tab per system: the last `RECENT_SYSTEMS` systems the commander has been in
plus any they pinned (at most `MAX_PINNED`; ★ on the tab). Each tab has two
tables: the system's *standing* (state, controlling Power, control progress,
reinforcement and undermining - baseline against latest, so a gain or loss shows
whoever caused it), and *what the commander did* there (merits and estimated
Control Points per activity).

The data and the pinned/hidden lists belong to powerplay.PowerplayController
(one ledger per commander); this module only draws them. The controller hands
over a `SystemsPane` on every refresh so nothing here goes stale."""

from __future__ import annotations

import tkinter as tk
from dataclasses import dataclass
from tkinter import messagebox
from typing import Callable, Dict, List, Optional, Tuple

from .formulas import ACTIVITY_LABELS, NO_CP_ACTIVITIES, merits_to_cp
from .powerplay import ratio_for
from .powerplay_ledger import (
    MAX_NAME_CHARS, MAX_PINNED, RECENT_SYSTEMS, CycleView, Snapshot, SystemRecord, TabPrefs, activity_rows,
    parse_ts,
)
from .uikit import palette as P
from .uikit import style
from .uikit.table import Column, DataTable
from .uikit.widgets import Combobox, FlatButton, SuggestEntry, Tabs

LEGEND = (
    f"TABS: the last {RECENT_SYSTEMS} systems you've been in, plus up to {MAX_PINNED} you pin (☆ Pin keeps a "
    "system's tab; × Close tab hides it; Show a system - pick from the list or type a name - pins one). "
    "STANDING: Baseline is the system's last reading before this cycle began (or your first reading this "
    "cycle); Latest is the newest. Control progress, Reinforcement and Undermining are whole-system figures "
    "from the journal - everyone's work, not just yours - and only update when you jump in or log in there. "
    "WHAT YOU DID: your merits by activity, with Control Points estimated from your Settings ratios. "
    "Cycles run Thursday 07:00 UTC to Thursday 07:00 UTC."
)

_STANDING_COLUMNS = (
    Column("measure", "Standing", 180, stretch=True),
    Column("before", "Baseline", 190, max_chars=40),
    Column("now", "Latest", 190, max_chars=40),
    Column("change", "Change", 120, anchor="e", max_chars=24),
)
_DID_COLUMNS = (
    Column("activity", "What you did", 180, stretch=True),
    Column("merits", "Merits", 110, anchor="e"),
    Column("events", "Events", 90, anchor="e"),
    Column("cp", "Est. CP", 110, anchor="e"),
)


@dataclass
class TabActions:
    """What the tab buttons do - supplied by the controller, which owns the
    pinned/hidden lists. toggle_pin and add return False when MAX_PINNED stops them."""

    toggle_pin: Callable[[str], bool]
    close: Callable[[str], None]
    add: Callable[[str], bool]


@dataclass
class SystemsPane:
    """Everything the tab reads, as callables so each refresh sees current data."""

    views: Callable[[], List[CycleView]]
    prefs: Callable[[], TabPrefs]
    cmdr: Callable[[], str]
    known_systems: Callable[[], List[str]]
    actions: TabActions


# --- wording -------------------------------------------------------------------


def cycle_label(view: CycleView) -> str:
    start = parse_ts(view.cycle_start)
    begin = start.strftime("%Y-%m-%d %H:%M") if start else "?"
    if view.current:
        return f"Current cycle (since {begin} UTC)"
    end = parse_ts(view.cycle_end)
    return f"{begin} – {end.strftime('%Y-%m-%d %H:%M') if end else '?'} UTC"


def _text(value: Optional[str]) -> str:
    return value or "—"


def _percent(snapshot: Optional[Snapshot]) -> str:
    return f"{snapshot.progress * 100:.1f}%" if snapshot and snapshot.progress is not None else "—"


def _count(snapshot: Optional[Snapshot], name: str) -> str:
    value = getattr(snapshot, name, None) if snapshot else None
    return f"{value:,}" if value is not None else "—"


def _delta(before: Optional[Snapshot], now: Optional[Snapshot], name: str) -> str:
    old, new = (getattr(s, name, None) if s else None for s in (before, now))
    if old is None or new is None or old == new:
        return ""
    return f"{new - old:+,}"


def _changed(before: Optional[str], now: Optional[str]) -> str:
    return "changed" if before and now and before != now else ""


def standing_rows(record: Optional[SystemRecord]) -> List[Tuple[str, ...]]:
    """Rows for the Standing table; empty when there is no reading for the system."""
    if record is None or record.latest() is None:
        return []
    before, now = record.before, record.latest()
    change = record.progress_change()
    return [
        ("State", _text(before and before.state), _text(now and now.state),
         _changed(before and before.state, now and now.state)),
        ("Controlling Power", _text(before and before.controller), _text(now and now.controller),
         _changed(before and before.controller, now and now.controller)),
        ("Control progress", _percent(before), _percent(now), f"{change:+.1f} pts" if change else ""),
        ("Reinforcement", _count(before, "reinforcement"), _count(now, "reinforcement"),
         _delta(before, now, "reinforcement")),
        ("Undermining", _count(before, "undermining"), _count(now, "undermining"),
         _delta(before, now, "undermining")),
        ("Powers in play", ", ".join(before.powers) if before and before.powers else "—",
         ", ".join(now.powers) if now and now.powers else "—", ""),
    ]


def did_rows(record: Optional[SystemRecord]) -> List[Tuple[str, ...]]:
    """Rows for the What-you-did table: one per activity with merits, then a total."""
    if record is None:
        return []
    rows: List[Tuple[str, ...]] = []
    total_cp = 0.0
    for activity in activity_rows(record):
        merits = record.merits[activity]
        has_cp = activity not in NO_CP_ACTIVITIES
        cp = merits_to_cp(merits, ratio_for(activity)) if has_cp else 0.0
        total_cp += cp
        rows.append((ACTIVITY_LABELS[activity], f"{merits:,}", str(record.events.get(activity, 0)),
                     f"{cp:,.1f}" if has_cp else "—"))
    if rows:
        rows.append(("Total", f"{record.total_merits():,}", str(sum(record.events.values())), f"{total_cp:,.1f}"))
    return rows


# --- widgets -------------------------------------------------------------------


class _SystemTab:
    """The buttons and two tables on one system's tab."""

    def __init__(self, content: tk.Frame, system: str, pinned: bool, actions: Callable[[], TabActions],
                 on_pin: Callable[[str], None]) -> None:
        bar = tk.Frame(content, bg=P.PANE)
        bar.pack(fill="x", padx=P.PAD, pady=(P.PAD_SM, 0))
        FlatButton(bar, "× Close tab", lambda: actions().close(system), kind="normal").pack(side="right")
        FlatButton(bar, "★ Unpin" if pinned else "☆ Pin", lambda: on_pin(system), kind="normal").pack(
            side="right", padx=(0, 6))
        tk.Label(content, text="STANDING", fg=P.MUTED, bg=P.PANE, anchor="w", padx=P.PAD,
                 font=style.font(P.FONT_SMALL)).pack(fill="x", pady=(P.PAD_SM, 0))
        self.standing = DataTable(content, _STANDING_COLUMNS, sortable=False, visible_rows=6,
                                  empty_text="No Powerplay reading for this system yet - jump in or log in there.")
        self.standing.pack(fill="x", padx=P.PAD, pady=(2, P.PAD_SM))
        tk.Label(content, text="WHAT YOU DID", fg=P.MUTED, bg=P.PANE, anchor="w", padx=P.PAD,
                 font=style.font(P.FONT_SMALL)).pack(fill="x", pady=(P.PAD_SM, 0))
        self.did = DataTable(content, _DID_COLUMNS, sortable=False,
                             empty_text="No merits earned here this cycle.")
        self.did.pack(fill="both", expand=True, padx=P.PAD, pady=(2, P.PAD))

    def fill(self, view: CycleView, system: str) -> None:
        record = view.record_for(system)
        self.standing.clear()
        for row in standing_rows(record):
            self.standing.append(row)
        self.did.clear()
        for row in did_rows(record):
            self.did.append(row)


class SystemsTab:
    def __init__(self, parent: tk.Frame, toplevel: tk.Misc) -> None:
        self._toplevel = toplevel
        self._pane: Optional[SystemsPane] = None
        self._current_system: Optional[str] = None
        self._views: List[CycleView] = []
        self._labels: Dict[str, CycleView] = {}
        self._selected_key: Optional[Tuple] = None
        self._tabs: Optional[Tabs] = None
        self._tab_systems: List[Tuple[str, bool]] = []
        self._tab_widgets: Dict[str, _SystemTab] = {}
        self._tab_cycle_key: Optional[Tuple] = None
        self._pending_select: Optional[str] = None

        self._heading = tk.Label(parent, bg=P.PANE, fg=P.MUTED, anchor="w", padx=P.PAD, justify="left",
                                 font=style.font(P.FONT_SMALL))
        self._heading.pack(fill="x", pady=(P.PAD_SM, 0))

        picker = tk.Frame(parent, bg=P.PANE)
        picker.pack(fill="x", padx=P.PAD, pady=(P.PAD_SM, P.PAD_SM))
        tk.Label(picker, text="CYCLE", fg=P.MUTED, bg=P.PANE, font=style.font(P.FONT_SMALL)).pack(side="left")
        self._cycle_var = tk.StringVar()
        self._cycle_box = Combobox(picker, textvariable=self._cycle_var, state="readonly", width=40)
        self._cycle_box.pack(side="left", padx=(P.PAD_SM, 0))
        self._cycle_box.bind("<<ComboboxSelected>>", lambda _e: self._on_cycle_selected())

        FlatButton(picker, "Add system", self._on_add, kind="normal").pack(side="right")
        self._add_var = tk.StringVar()
        SuggestEntry(picker, self._add_var, self._known_systems, self._on_add, width=26).pack(
            side="right", padx=(0, 6))
        tk.Label(picker, text="SHOW A SYSTEM", fg=P.MUTED, bg=P.PANE,
                 font=style.font(P.FONT_SMALL)).pack(side="right", padx=(0, 6))

        tk.Label(parent, text=LEGEND, fg=P.MUTED, bg=P.PANE, anchor="w", justify="left", wraplength=900,
                 padx=P.PAD, font=style.font(P.FONT_SMALL)).pack(side="bottom", fill="x", pady=(0, P.PAD_SM))
        self._stage = tk.Frame(parent, bg=P.PANE)
        self._stage.pack(fill="both", expand=True)

    # --- data in -----------------------------------------------------------------

    def _known_systems(self) -> List[str]:
        return self._pane.known_systems() if self._pane else []

    @staticmethod
    def _key(view: CycleView) -> Tuple:
        return (view.cycle_start, view.cycle_end, view.current)

    def update(self, pane: Optional[SystemsPane], current_system: Optional[str]) -> None:
        if pane is None:
            return
        self._pane = pane
        self._current_system = current_system
        self._views = pane.views()
        self._labels = {}
        for view in self._views:
            label = cycle_label(view)
            while label in self._labels:
                label += " "
            self._labels[label] = view
        self._cycle_box.configure(values=list(self._labels))

        selected = next((v for v in self._views if self._key(v) == self._selected_key), None)
        if selected is None:
            selected = self._views[0] if self._views else None
        if selected is not None:
            self._selected_key = self._key(selected)
            self._cycle_var.set(next(lbl for lbl, v in self._labels.items() if v is selected))
        self._show_cycle(selected)

    def _on_cycle_selected(self) -> None:
        view = self._labels.get(self._cycle_var.get())
        if view is not None:
            self._selected_key = self._key(view)
            self._show_cycle(view)

    def _show_cycle(self, view: Optional[CycleView]) -> None:
        if view is None or self._pane is None:
            return
        prefs = self._pane.prefs()
        shown = view.systems(self._current_system, prefs, limit=RECENT_SYSTEMS)
        wanted = [(s, prefs.is_pinned(s)) for s in shown]
        cmdr = self._pane.cmdr()
        self._heading.configure(
            text=f"{'CMDR ' + cmdr + ' — ' if cmdr else ''}{len(shown)} tab(s): last {RECENT_SYSTEMS} systems "
                 f"plus {len(prefs.pinned)}/{MAX_PINNED} pinned")
        key = self._key(view)
        if self._tabs is None or wanted != self._tab_systems or key != self._tab_cycle_key:
            self._rebuild_tabs(wanted, key)
        for system, tab in self._tab_widgets.items():
            tab.fill(view, system)

    def _rebuild_tabs(self, wanted: List[Tuple[str, bool]], key: Tuple) -> None:
        names = [name for name, _pinned in self._tab_systems]
        previous = names[self._tabs.selected] if self._tabs and 0 <= self._tabs.selected < len(names) else None
        for child in self._stage.winfo_children():
            child.destroy()
        self._tabs = None
        self._tab_widgets = {}
        self._tab_systems = list(wanted)
        self._tab_cycle_key = key

        if not wanted:
            tk.Label(self._stage, text="No systems to show yet — Powerplay systems appear here once you jump "
                     "into one or earn merits; or use \"Show a system\" above.",
                     fg=P.MUTED, bg=P.PANE, pady=P.PAD).pack(fill="x")
            return
        assert self._pane is not None
        pane = self._pane
        tabs = Tabs(self._stage, wrap=True)
        tabs.pack(fill="both", expand=True)
        for system, is_pinned in wanted:
            title = ("★ " if is_pinned else "") + system
            self._tab_widgets[system] = _SystemTab(
                tabs.add(title), system, is_pinned, lambda: pane.actions, self._on_pin)
        new_names = [name for name, _pinned in wanted]
        target = previous
        if self._pending_select:
            match = next((n for n in new_names if n.casefold() == self._pending_select.casefold()), None)
            target = match or target
            self._pending_select = None
        if target in new_names:
            tabs.select(new_names.index(target))
        self._tabs = tabs

    # --- user actions -------------------------------------------------------------

    def _limit_reached(self) -> None:
        messagebox.showinfo(
            "Pin limit", f"You can pin up to {MAX_PINNED} systems. Unpin one first.", parent=self._toplevel)

    def _on_pin(self, system: str) -> None:
        if self._pane is not None and not self._pane.actions.toggle_pin(system):
            self._limit_reached()

    def _on_add(self) -> None:
        name = " ".join(self._add_var.get().split())[:MAX_NAME_CHARS]
        if not name or self._pane is None:
            return
        self._add_var.set("")
        self._pending_select = name
        if not self._pane.actions.add(name):
            self._pending_select = None
            self._limit_reached()
