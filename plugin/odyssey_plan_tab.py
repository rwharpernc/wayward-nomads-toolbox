"""The Upgrade planner tab of the Engineering window: take an Odyssey suit or weapon from one class to another, fit up to four modifications, see what it
costs and put the lot on the wishlist.

Nothing here goes online or reads the journal: the choices are made on the tab, `odyssey_upgrade_plan.py` works the cost out from the blueprint table, and
**Add to wishlist** hands the result to `blueprint_wishlist.WishBook.add_many`, all or nothing. The credits are shown only where they have been recorded for
the item (see odyssey_upgrade_plan.CREDIT_UNIT); a modification's engineer fee is not in the table. The tab is built into a frame the window gives it."""
from __future__ import annotations

import tkinter as tk
from typing import Callable, List, Optional, Tuple

from . import blueprint_wishlist as wishlist_mod
from . import odyssey_upgrade_plan as plan_mod
from .uikit import palette as P
from .uikit.table import Column, DataTable
from .uikit.widgets import Combobox, FlatButton, clip

NONE = "(none)"
_COLUMNS = (
    Column("step", "Step", 230, max_chars=44),
    Column("takes", "Takes", 560, stretch=True, max_chars=140),
    Column("credits", "Credits", 120, anchor="e"),
)
_HELP = ("Pick a suit or a weapon, the class it is now and the class you want, and up to four modifications. The materials of each step are shown, "
         "and Add to wishlist puts them on the Wishlist tab with the rest of your list.")


def materials_text(blueprint) -> str:
    return ", ".join(f"{i.count} {i.name}" for i in blueprint.ingredients)


def rows(plan: plan_mod.Plan) -> List[Tuple[str, str, str]]:
    """The table: one row per class step and per modification."""
    out: List[Tuple[str, str, str]] = []
    previous = plan.current
    for step in plan.steps:
        credit = plan_mod.CLASS_FACTOR[step.grade] * plan.item.credit_unit if plan.item.credit_unit else None
        out.append((f"Class {previous} to {step.grade}", materials_text(step), f"{credit:,}" if credit else "not recorded"))
        previous = step.grade
    for mod in plan.mods:
        out.append((f"Modification: {mod.name}", materials_text(mod), "engineer's fee"))
    return out


def summary(plan: plan_mod.Plan) -> str:
    parts = []
    if plan.steps:
        parts.append(f"{plan.item.label}, class {plan.current} to {plan.target}"
                     + (f": {plan.credits:,} credits" if plan.credits is not None else ": credits not recorded"))
    if plan.mods:
        parts.append(f"{len(plan.mods)} modification{'s' if len(plan.mods) != 1 else ''}")
    return "; ".join(parts) if parts else "Nothing to plan: pick a higher class or a modification."


class UpgradePlanTab:
    def __init__(self, tab: tk.Frame, wishbook: wishlist_mod.WishBook, set_status: Callable[[str], None]) -> None:
        self._wishbook = wishbook
        self._set_status = set_status
        self._plan: Optional[plan_mod.Plan] = None

        pad = tk.Frame(tab, bg=P.PANE)
        pad.pack(fill="both", expand=True, padx=P.PAD, pady=P.PAD)
        tk.Label(pad, text=_HELP, fg=P.MUTED, bg=P.PANE, anchor="w", justify="left", wraplength=980).pack(fill="x")

        top = tk.Frame(pad, bg=P.PANE)
        top.pack(fill="x", pady=(P.PAD_SM, P.PAD_SM))
        tk.Label(top, text="Item", fg=P.MUTED, bg=P.PANE).pack(side="left")
        self._gear = tk.StringVar(value=plan_mod.labels()[0])
        gear_box = Combobox(top, textvariable=self._gear, values=plan_mod.labels(), state="readonly", width=26)
        gear_box.pack(side="left", padx=(P.PAD_SM, P.PAD))
        gear_box.bind("<<ComboboxSelected>>", lambda _e: self._gear_changed())
        classes = [str(c) for c in plan_mod.CLASSES]
        tk.Label(top, text="Class now", fg=P.MUTED, bg=P.PANE).pack(side="left")
        self._current = tk.StringVar(value="1")
        current_box = Combobox(top, textvariable=self._current, values=classes, state="readonly", width=3)
        current_box.pack(side="left", padx=(P.PAD_SM, P.PAD))
        current_box.bind("<<ComboboxSelected>>", lambda _e: self._class_changed())
        tk.Label(top, text="Wanted", fg=P.MUTED, bg=P.PANE).pack(side="left")
        self._target = tk.StringVar(value="5")
        target_box = Combobox(top, textvariable=self._target, values=classes, state="readonly", width=3)
        target_box.pack(side="left", padx=(P.PAD_SM, 0))
        target_box.bind("<<ComboboxSelected>>", lambda _e: self._class_changed(target_chosen=True))

        mods = tk.Frame(pad, bg=P.PANE)
        mods.pack(fill="x", pady=(0, P.PAD_SM))
        tk.Label(mods, text="Modifications", fg=P.MUTED, bg=P.PANE).pack(side="left")
        self._mod_vars: List[tk.StringVar] = []
        self._mod_boxes: List[Combobox] = []
        for _ in range(plan_mod.MAX_MODS):
            var = tk.StringVar(value=NONE)
            box = Combobox(mods, textvariable=var, values=[NONE], state="readonly", width=24)
            box.pack(side="left", padx=(P.PAD_SM, 0))
            box.bind("<<ComboboxSelected>>", lambda _e: self.refresh())
            self._mod_vars.append(var)
            self._mod_boxes.append(box)

        self._table = DataTable(pad, _COLUMNS, sortable=False, visible_rows=8, empty_text="Nothing to plan yet.")
        self._table.pack(fill="x", pady=(0, P.PAD_SM))
        controls = tk.Frame(pad, bg=P.PANE)
        controls.pack(fill="x")
        FlatButton(controls, "Add to wishlist", self.add_to_wishlist, kind="accent").pack(side="left")
        self._summary = tk.Label(pad, text="", fg=P.TEXT, bg=P.PANE, anchor="w", justify="left", wraplength=980)
        self._summary.pack(fill="x", pady=(P.PAD_SM, 0))
        self._notes = tk.Label(pad, text="", fg=P.MUTED, bg=P.PANE, anchor="w", justify="left", wraplength=980)
        self._notes.pack(fill="x", pady=(P.PAD_SM, 0))
        self._gear_changed()

    # --- choices -----------------------------------------------------------------------------------------------------------

    def _item(self) -> Optional[plan_mod.Gear]:
        return plan_mod.gear(self._gear.get())

    def _gear_changed(self) -> None:
        item = self._item()
        options = [NONE, *(plan_mod.modifications_for(item) if item else [])]
        for box, var in zip(self._mod_boxes, self._mod_vars):
            box.configure(values=options)
            if var.get() not in options:
                var.set(NONE)
        self.refresh()

    def _class_changed(self, target_chosen: bool = False) -> None:
        """Keep the two classes in order: moving one past the other drags the other with it."""
        current, target = int(self._current.get()), int(self._target.get())
        if target < current:
            (self._current if target_chosen else self._target).set(str(target if target_chosen else current))
        self.refresh()

    def chosen_mods(self) -> List[str]:
        return [v.get() for v in self._mod_vars if v.get() and v.get() != NONE]

    def refresh(self) -> None:
        """Work the plan out from the choices and show it; a choice that cannot be planned says why."""
        item = self._item()
        self._table.clear()
        self._plan = None
        if item is None:
            return
        try:
            self._plan = plan_mod.plan(item, int(self._current.get()), int(self._target.get()), self.chosen_mods())
        except plan_mod.OdysseyPlanError as err:
            self._summary.configure(text=str(err))
            self._notes.configure(text="")
            return
        for index, row in enumerate(rows(self._plan)):
            self._table.insert(str(index), row)
        self._summary.configure(text=summary(self._plan))
        self._notes.configure(text=clip(" ".join(self._plan.notes()), 600))

    # --- the wishlist ------------------------------------------------------------------------------------------------------

    def add_to_wishlist(self) -> None:
        if self._plan is None or not self._plan.entries():
            self._set_status("Nothing to add: pick a higher class or a modification.")
            return
        try:
            changed = self._wishbook.add_many(self._plan.entries())
        except wishlist_mod.WishError as err:
            self._set_status(str(err))
            return
        self._set_status(f"Put {changed} entr{'ies' if changed != 1 else 'y'} for {self._plan.item.label} on the wishlist. See the Wishlist tab.")
