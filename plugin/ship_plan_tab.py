"""The Ship planner tab of the Engineering window: paste a ship loadout (a SLEF export from EDSY or Coriolis, or a `Loadout` line from a journal),
see what engineering it holds module by module, and put the whole plan on the wishlist.

Nothing here goes online: the text comes from the clipboard or the box, `ship_plan.py` does the reading, and **Add plan to wishlist** hands the result
to `blueprint_wishlist.WishBook.add_many`, all or nothing. How many crafts each grade takes depends on the game's dice, so **Rolls per grade** says how
many to plan for (an experimental effect is one craft). The tab is built into a frame the window gives it; it owns no window of its own.
"""
from __future__ import annotations

import tkinter as tk
from typing import Callable, List, Optional

from . import blueprint_wishlist as wishlist_mod
from . import ship_plan
from .uikit import palette as P
from .uikit.table import Column, DataTable
from .uikit.widgets import Combobox, FlatButton, clip

_COLUMNS = (
    Column("slot", "Slot", 150, max_chars=28),
    Column("module", "Module", 190, max_chars=34),
    Column("blueprint", "Engineering", 220, stretch=True, max_chars=48),
    Column("grades", "Level", 50, anchor="e"),
    Column("effect", "Experimental", 170, max_chars=34),
    Column("status", "Counted?", 150, max_chars=34),
)
_HELP = ("Paste a ship loadout (a SLEF export from EDSY or Coriolis, or a Loadout line from your journal) and press Read loadout. "
         "Nothing is sent anywhere.")


class ShipPlanTab:
    def __init__(self, tab: tk.Frame, wishbook: wishlist_mod.WishBook, set_status: Callable[[str], None]) -> None:
        self._wishbook = wishbook
        self._set_status = set_status
        self._builds: List[ship_plan.Build] = []
        self._plan: Optional[ship_plan.Plan] = None

        pad = tk.Frame(tab, bg=P.PANE)
        pad.pack(fill="both", expand=True, padx=P.PAD, pady=P.PAD)
        tk.Label(pad, text=_HELP, fg=P.MUTED, bg=P.PANE, anchor="w", justify="left", wraplength=980).pack(fill="x")
        self._text = tk.Text(pad, height=5, wrap="char", bg=P.CARD, fg=P.TEXT, insertbackground=P.TEXT, relief="flat")
        self._text.pack(fill="x", pady=(P.PAD_SM, P.PAD_SM))

        buttons = tk.Frame(pad, bg=P.PANE)
        buttons.pack(fill="x", pady=(0, P.PAD_SM))
        FlatButton(buttons, "Paste from clipboard", self.paste).pack(side="left")
        FlatButton(buttons, "Read loadout", self.read, kind="accent").pack(side="left", padx=(P.PAD, 0))
        FlatButton(buttons, "Clear", self.clear).pack(side="left", padx=(P.PAD, 0))
        tk.Label(buttons, text="Ship", fg=P.MUTED, bg=P.PANE).pack(side="left", padx=(P.PAD, P.PAD_SM))
        self._ship = tk.StringVar()
        self._ship_box = Combobox(buttons, textvariable=self._ship, values=[], state="readonly", width=34)
        self._ship_box.pack(side="left")
        self._ship_box.bind("<<ComboboxSelected>>", lambda _e: self._choose())

        self._table = DataTable(pad, _COLUMNS, on_select=self._pick, sortable=False, visible_rows=9,
                                empty_text="No plan yet. Paste a loadout above and press Read loadout.")
        self._table.pack(fill="x", pady=(0, P.PAD_SM))

        controls = tk.Frame(pad, bg=P.PANE)
        controls.pack(fill="x")
        tk.Label(controls, text="Rolls per grade", fg=P.MUTED, bg=P.PANE).pack(side="left")
        self._rolls = tk.StringVar(value="1")
        rolls = Combobox(controls, textvariable=self._rolls, values=[str(n) for n in range(1, ship_plan.MAX_ROLLS + 1)], state="readonly", width=4)
        rolls.pack(side="left", padx=(P.PAD_SM, P.PAD))
        rolls.bind("<<ComboboxSelected>>", lambda _e: self._summarize())
        FlatButton(controls, "Add plan to wishlist", self.add_to_wishlist, kind="accent").pack(side="left")
        self._summary = tk.Label(pad, text="", fg=P.TEXT, bg=P.PANE, anchor="w", justify="left", wraplength=980)
        self._summary.pack(fill="x", pady=(P.PAD_SM, 0))
        self._note = tk.Label(pad, text="", fg=P.MUTED, bg=P.PANE, anchor="w", justify="left", wraplength=980)
        self._note.pack(fill="x", pady=(P.PAD_SM, 0))
        tk.Label(pad, text=("The journal cannot tell how many rolls a grade takes (the game rolls dice), so the crafts are the number you set, one experimental "
                            "effect each. The Wishlist tab then shows what you can make now and the shopping list."),
                 fg=P.MUTED, bg=P.PANE, anchor="w", justify="left", wraplength=980).pack(fill="x", pady=(P.PAD_SM, 0))

    # --- reading ---------------------------------------------------------------------------------------------------------

    def paste(self) -> None:
        """Put the clipboard's text in the box."""
        try:
            text = self._text.clipboard_get()
        except tk.TclError:
            self._set_status("The clipboard has no text to paste.")
            return
        self._text.delete("1.0", "end")
        self._text.insert("1.0", text[:ship_plan.MAX_TEXT_CHARS])
        self.read()

    def read(self) -> None:
        """Read the loadout in the box."""
        self.load_text(self._text.get("1.0", "end"))

    def load_text(self, text: str) -> bool:
        """Read `text`; True when it holds at least one ship. A problem is shown in the status line and leaves the last plan as it was."""
        try:
            builds = ship_plan.parse(text)
        except ship_plan.PlanError as err:
            self._set_status(str(err))
            return False
        self._builds = builds
        self._ship_box.configure(values=[b.label for b in builds])
        self._ship_box.set(builds[0].label)
        self._choose()
        return True

    def clear(self) -> None:
        self._text.delete("1.0", "end")
        self._builds, self._plan = [], None
        self._ship_box.configure(values=[])
        self._ship.set("")
        self._table.clear()
        self._summary.configure(text="")
        self._note.configure(text="")

    def _choose(self) -> None:
        build = next((b for b in self._builds if b.label == self._ship.get()), None)
        if build is None:
            return
        self._plan = ship_plan.plan(build)
        self._table.clear()
        for index, planned in enumerate(self._plan.modules):
            self._table.insert(str(index), (
                planned.slot, ship_plan.module_type(planned.item) or planned.item, planned.blueprint,
                planned.level or "-", planned.experimental or "-", planned.status))
        self._note.configure(text="")
        self._summarize()
        if not self._plan.modules:
            self._set_status("That ship has no engineered modules.")

    def _pick(self, iid: str) -> None:
        if self._plan is None or not iid.isdigit() or int(iid) >= len(self._plan.modules):
            return
        planned = self._plan.modules[int(iid)]
        parts = [f"{planned.slot}: {planned.item}"]
        if planned.grades:
            parts.append(f"{planned.blueprint}, grades 1 to {planned.grades[-1].grade}")
        if planned.special is not None:
            parts.append(f"experimental effect {planned.special.name}")
        if planned.quality:
            parts.append(f"last roll quality {planned.quality:.0%}")
        if planned.note:
            parts.append(planned.note)
        self._note.configure(text=clip(". ".join(parts) + ".", 600))

    def _rolls_value(self) -> int:
        try:
            return int(self._rolls.get())
        except ValueError:
            return 1

    def _summarize(self) -> None:
        if self._plan is not None:
            self._summary.configure(text=self._plan.summary(self._rolls_value()))

    # --- the wishlist ----------------------------------------------------------------------------------------------------

    def add_to_wishlist(self) -> None:
        if self._plan is None or not self._plan.counted():
            self._set_status("Read a loadout with engineered modules first.")
            return
        try:
            changed = self._wishbook.add_many(self._plan.entries(self._rolls_value()))
        except (wishlist_mod.WishError, ship_plan.PlanError) as err:
            self._set_status(str(err))
            return
        self._set_status(f"Put {changed} blueprint{'s' if changed != 1 else ''} from {clip(self._plan.build.label, 40)} on the wishlist. "
                         "See the Wishlist tab.")
