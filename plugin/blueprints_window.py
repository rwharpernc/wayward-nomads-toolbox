"""The Engineering window: every engineering blueprint to browse, and the commander's wishlist with a combined shopping list.

**Blueprints** tab: search and pick a module type; pick a blueprint to see who offers it, its effects and what ONE craft takes against what you
hold and where each ingredient is found; set a number of crafts and add it to the wishlist (or double-click a row to add one craft).
**Wishlist** tab: each entry with its crafts, whether it can be made now (worked out in list order, so an entry only sees what the ones above it
leave), how many pieces it is short and who can do it (an engineer you have unlocked, or a vendor that needs none), then one shopping list for the
whole wishlist: need, have, short and where to find each ingredient.
**Engineers** tab: where you stand with each engineer (from the journal's `EngineerProgress`), what they offer and what unlocking them takes, with
buttons to list their blueprints or put their unlock on the wishlist.

Built on the shared window kit (plugin/uikit); the lists are `blueprints.py` and `blueprint_wishlist.WishBook`, the arithmetic is
`blueprint_needs.py`, and the counts come in as a `Holdings` from the panel (`materials_panel.py`). Module-level show/refresh/close and saved
geometry follow notes_window.py."""
from __future__ import annotations

import logging
import os
import tkinter as tk
from typing import Callable, List, Optional

from config import appname, config

from . import blueprint_needs as needs_mod
from . import blueprint_wishlist as wishlist_mod
from . import blueprints, engineers
from .uikit import palette as P
from .uikit import style
from .uikit.shell import WindowShell
from .uikit.table import Column, DataTable
from .uikit.widgets import Combobox, FlatButton, Tabs, clip

plugin_name = os.path.basename(os.path.dirname(__file__))
logger = logging.getLogger(f"{appname}.{plugin_name}")

CONFIG_GEOMETRY = "wntb_blueprints_window_geometry"
DEFAULT_SIZE = (1080, 760)
MIN_SIZE = (860, 560)
ALL = "All types"
SHOWN = 150            # blueprints listed at once; a note says when there are more
SEARCH_DELAY_MS = 250  # typing in the search box refills the table once it pauses
CONFIRM_MS = 5000      # how long a first press of Remove or Clear waits for the second
FOUND_CHARS = 80

KIND_LABELS = {blueprints.SHIP: "Ship material", blueprints.ODYSSEY: "On foot", blueprints.COMMODITY: "Commodity"}

_window: Optional["BlueprintsWindow"] = None

_BLUEPRINT_COLUMNS = (
    Column("type", "Module", 170, max_chars=32),
    Column("name", "Blueprint", 230, stretch=True, max_chars=48),
    Column("grade", "Grade", 60, anchor="e"),
    Column("engineers", "Offered by", 260, max_chars=60),
)
_INGREDIENT_COLUMNS = (
    Column("ingredient", "Ingredient", 230, stretch=True, max_chars=44),
    Column("kind", "Kind", 110),
    Column("need", "Need", 60, anchor="e"),
    Column("have", "Have", 60, anchor="e"),
    Column("found", "Where it is found", 360, stretch=True, max_chars=FOUND_CHARS),
)
_WISH_COLUMNS = (
    Column("blueprint", "Blueprint", 330, stretch=True, max_chars=64),
    Column("crafts", "Crafts", 60, anchor="e"),
    Column("ready", "Can be made now", 170, max_chars=44),
    Column("short", "Short", 60, anchor="e"),
    Column("who", "Who can do it", 230, max_chars=48),
)
_ENGINEER_COLUMNS = (
    Column("engineer", "Engineer", 190, max_chars=34),
    Column("standing", "You are", 150, max_chars=30),
    Column("offers", "Offers", 90, anchor="e"),
    Column("unlock", "To unlock", 480, stretch=True, max_chars=90),
)
_SHOPPING_COLUMNS = (
    Column("ingredient", "Ingredient", 230, stretch=True, max_chars=44),
    Column("kind", "Kind", 110),
    Column("need", "Need", 60, anchor="e"),
    Column("have", "Have", 60, anchor="e"),
    Column("short", "Short", 60, anchor="e"),
    Column("found", "Where it is found", 320, stretch=True, max_chars=FOUND_CHARS),
)

Counts = Callable[[], needs_mod.Holdings]


def show(parent: tk.Misc, wishbook: wishlist_mod.WishBook, holdings: Counts, engineer_book: engineers.EngineerBook) -> None:
    """Open the Engineering window, or raise it if it is already open."""
    global _window
    if _window is not None and _window.alive:
        _window.refresh()
        _window.lift()
        return
    _window = BlueprintsWindow(parent, wishbook, holdings, engineer_book)


def refresh() -> None:
    if _window is not None and _window.alive:
        _window.refresh()


def close() -> None:
    if _window is not None and _window.alive:
        _window.close()


def engineers_text(blueprint: blueprints.Blueprint, book: Optional[engineers.EngineerBook] = None) -> str:
    """Who offers a blueprint; with the commander's standings, each engineer is followed by where they stand with them."""
    if not blueprint.engineers:
        return "-"
    parts = []
    for name in blueprint.engineers:
        standing = book.standing(name) if book is not None and name not in blueprints.STAND_IN_NAMES else None
        parts.append(f"{name} ({standing.describe().lower()})" if standing is not None else name)
    return ", ".join(parts)


def who_can(blueprint: blueprints.Blueprint, book: Optional[engineers.EngineerBook]) -> str:
    """Who can do a blueprint for the commander now: a vendor or the synthesis panel (nothing to unlock) and any engineer who is unlocked. When
    the journal has not told WNTB about the engineers yet, it says who offers it instead of guessing."""
    free = [e for e in blueprint.engineers if e in blueprints.STAND_IN_NAMES]
    if book is None or not book.has_data:
        return clip("Offered by " + ", ".join(blueprint.engineers), 48) if blueprint.engineers else "-"
    unlocked = [e for e in blueprints.real_engineers(blueprint) if (s := book.standing(e)) is not None and s.unlocked]
    if free or unlocked:
        return clip(", ".join(free + unlocked), 48)
    return clip("No engineer unlocked yet", 48)


def effects_text(blueprint: blueprints.Blueprint) -> str:
    return ", ".join(f"{e.effect} {e.prop}".strip() for e in blueprint.effects) or "none listed"


def found_text(ingredient: blueprints.Ingredient) -> str:
    return clip("; ".join(ingredient.found) or "-", FOUND_CHARS)


def number(value: Optional[int]) -> str:
    return "-" if value is None else f"{value:,}"


def ingredient_rows(blueprint: blueprints.Blueprint, crafts: int, holdings: needs_mod.Holdings) -> List[tuple]:
    return [(n.ingredient.name, KIND_LABELS[n.ingredient.kind], f"{n.need:,}", number(n.have), found_text(n.ingredient))
            for n in needs_mod.needs_for(blueprint, crafts, holdings)]


def entry_ready_text(entry: needs_mod.EntryStatus) -> str:
    if entry.ready and entry.uncounted:
        return clip("Yes, not counting " + ", ".join(entry.uncounted), 44)
    return "Yes" if entry.ready else "No"


def entry_short(entry: needs_mod.EntryStatus) -> int:
    return sum(max(0, n.need - n.have) for n in entry.needs if n.have is not None)


def shopping_rows(shopping: needs_mod.Shopping) -> List[tuple]:
    return [(n.ingredient.name, KIND_LABELS[n.ingredient.kind], f"{n.need:,}", number(n.have), number(n.short), found_text(n.ingredient))
            for n in shopping.needs]


class BlueprintsWindow:
    def __init__(self, parent: tk.Misc, wishbook: wishlist_mod.WishBook, holdings: Counts, engineer_book: engineers.EngineerBook) -> None:
        self._wishbook = wishbook
        self._engineers = engineer_book
        self._holdings = holdings
        self._picked: Optional[str] = None         # the blueprint shown in the detail pane
        self._picked_wish: Optional[str] = None    # the wishlist entry selected
        self._confirming: Optional[str] = None     # "remove" or "clear" after a first press
        self._search_job: Optional[str] = None

        self._shell = WindowShell(
            parent, "Engineering", "", size=DEFAULT_SIZE, min_size=MIN_SIZE,
            load_geometry=lambda: config.get_str(CONFIG_GEOMETRY) or "",
            save_geometry=lambda geometry: config.set(CONFIG_GEOMETRY, geometry))
        self._shell.window.protocol("WM_DELETE_WINDOW", self.close)
        self._shell.add_action("Refresh counts", self.refresh)

        self._tabs = Tabs(self._shell.body)
        self._tabs.pack(fill="both", expand=True)
        self._build_browse(self._tabs.add("Blueprints"))
        self._build_wishlist(self._tabs.add("Wishlist"))
        self._build_engineers(self._tabs.add("Engineers"))
        self._tabs.select(0)

        wishbook.add_listener(self._on_changed)
        engineer_book.add_listener(self._on_changed)
        self._fill_blueprints()
        self.refresh()

    # --- the Blueprints tab --------------------------------------------------------------------------------------------

    def _build_browse(self, tab: tk.Frame) -> None:
        pad = tk.Frame(tab, bg=P.PANE)
        pad.pack(fill="both", expand=True, padx=P.PAD, pady=P.PAD)
        filters = tk.Frame(pad, bg=P.PANE)
        filters.pack(fill="x", pady=(0, P.PAD_SM))
        tk.Label(filters, text="Search", fg=P.MUTED, bg=P.PANE).pack(side="left")
        self._query = tk.StringVar()
        tk.Entry(filters, textvariable=self._query, width=26).pack(side="left", padx=(P.PAD_SM, P.PAD))
        self._query.trace_add("write", lambda *_: self._search_later())
        tk.Label(filters, text="Module", fg=P.MUTED, bg=P.PANE).pack(side="left")
        self._type = tk.StringVar(value=ALL)
        box = Combobox(filters, textvariable=self._type, values=[ALL, *blueprints.types()], state="readonly", width=26)
        box.pack(side="left", padx=(P.PAD_SM, P.PAD))
        box.bind("<<ComboboxSelected>>", lambda _e: self._fill_blueprints())
        self._count_label = tk.Label(filters, text="", fg=P.MUTED, bg=P.PANE)
        self._count_label.pack(side="left")

        self._table = DataTable(pad, _BLUEPRINT_COLUMNS, on_select=self._pick, on_activate=self._add_one,
                                empty_text="No blueprint matches.", visible_rows=9)
        self._table.pack(fill="x", pady=(0, P.PAD_SM))

        self._title = tk.Label(pad, text="Pick a blueprint above.", fg=P.TEXT, bg=P.PANE, anchor="w", font=style.font(P.FONT_BOLD))
        self._title.pack(fill="x")
        self._facts = tk.Label(pad, text="", fg=P.MUTED, bg=P.PANE, anchor="w", justify="left", wraplength=980)
        self._facts.pack(fill="x", pady=(0, P.PAD_SM))
        self._ingredients = DataTable(pad, _INGREDIENT_COLUMNS, sortable=False, visible_rows=6,
                                      empty_text="The ingredients of one craft are listed here.")
        self._ingredients.pack(fill="x", pady=(0, P.PAD_SM))

        adding = tk.Frame(pad, bg=P.PANE)
        adding.pack(fill="x")
        tk.Label(adding, text="Crafts", fg=P.MUTED, bg=P.PANE).pack(side="left")
        self._crafts = tk.StringVar(value="1")
        entry = tk.Entry(adding, textvariable=self._crafts, width=5)
        entry.pack(side="left", padx=(P.PAD_SM, P.PAD))
        entry.bind("<Return>", lambda _e: self._add())
        self._crafts.trace_add("write", lambda *_: self._fill_detail())
        self._add_button = FlatButton(adding, "Add to wishlist", self._add, kind="accent")
        self._add_button.pack(side="left")
        self._add_button.set_enabled(False)

    def _search_later(self) -> None:
        if self._search_job is not None:
            try:
                self._shell.window.after_cancel(self._search_job)
            except tk.TclError:
                pass
        self._search_job = self._shell.window.after(SEARCH_DELAY_MS, self._fill_blueprints)

    def _fill_blueprints(self) -> None:
        self._search_job = None
        if not self.alive:
            return
        kind = None if self._type.get() == ALL else self._type.get()
        found = blueprints.search(self._query.get(), kind, limit=SHOWN + 1)
        shown = found[:SHOWN]
        self._table.clear()
        for b in shown:
            self._table.insert(b.id, (b.type, b.name, b.grade or "-", clip(engineers_text(b), 60)))   # statuses are in the detail below
        if self._picked and any(b.id == self._picked for b in shown):
            self._table.select(self._picked)
        self._count_label.configure(text=f"{len(shown)} shown" + (f", more match: narrow the search" if len(found) > SHOWN else ""))

    def _pick(self, blueprint_id: str) -> None:
        self._picked = blueprint_id
        self._fill_detail()

    def _crafts_value(self) -> int:
        try:
            return max(1, min(wishlist_mod.MAX_CRAFTS, int(self._crafts.get().strip())))
        except ValueError:
            return 1

    def _fill_detail(self) -> None:
        if not self.alive:
            return
        blueprint = blueprints.get(self._picked) if self._picked else None
        self._ingredients.clear()
        self._add_button.set_enabled(blueprint is not None)
        if blueprint is None:
            self._title.configure(text="Pick a blueprint above.")
            self._facts.configure(text="")
            return
        self._title.configure(text=f"{blueprint.type}: {blueprint.title}")
        self._facts.configure(text=clip(f"Offered by: {engineers_text(blueprint, self._engineers)}.   Effects: {effects_text(blueprint)}.", 400))
        for row in ingredient_rows(blueprint, self._crafts_value(), self._holdings()):
            self._ingredients.append(row)

    def _add(self) -> None:
        if self._picked is None:
            return
        self._add_blueprint(self._picked, self._crafts_value())

    def _add_one(self, blueprint_id: str) -> None:
        self._add_blueprint(blueprint_id, 1)

    def _add_blueprint(self, blueprint_id: str, crafts: int) -> None:
        try:
            item = self._wishbook.add(blueprint_id, crafts)
        except wishlist_mod.WishError as err:
            self._shell.set_status(str(err))
            return
        blueprint = item.blueprint
        self._shell.set_status(f"On the wishlist: {blueprint.title if blueprint else blueprint_id} x {item.crafts}.")

    # --- the Wishlist tab ----------------------------------------------------------------------------------------------

    def _build_wishlist(self, tab: tk.Frame) -> None:
        pad = tk.Frame(tab, bg=P.PANE)
        pad.pack(fill="both", expand=True, padx=P.PAD, pady=P.PAD)
        self._wish_table = DataTable(pad, _WISH_COLUMNS, on_select=self._pick_wish, sortable=False, visible_rows=8,
                                     empty_text="The wishlist is empty. Add blueprints on the Blueprints tab.")
        self._wish_table.pack(fill="x", pady=(0, P.PAD_SM))

        controls = tk.Frame(pad, bg=P.PANE)
        controls.pack(fill="x", pady=(0, P.PAD_SM))
        tk.Label(controls, text="Crafts", fg=P.MUTED, bg=P.PANE).pack(side="left")
        self._wish_crafts = tk.StringVar(value="1")
        entry = tk.Entry(controls, textvariable=self._wish_crafts, width=5)
        entry.pack(side="left", padx=(P.PAD_SM, P.PAD))
        entry.bind("<Return>", lambda _e: self._set_crafts())
        FlatButton(controls, "Set crafts", self._set_crafts).pack(side="left")
        FlatButton(controls, "Remove", self._remove, kind="danger").pack(side="left", padx=(P.PAD, 0))
        FlatButton(controls, "Clear list", self._clear, kind="danger").pack(side="left", padx=(6, 0))

        self._shopping_title = tk.Label(pad, text="Shopping list", fg=P.TEXT, bg=P.PANE, anchor="w", font=style.font(P.FONT_BOLD))
        self._shopping_title.pack(fill="x")
        self._shopping_table = DataTable(pad, _SHOPPING_COLUMNS, visible_rows=10, empty_text="Nothing to buy: the wishlist is empty.")
        self._shopping_table.pack(fill="x")

    def _pick_wish(self, blueprint_id: str) -> None:
        self._picked_wish = blueprint_id
        self._confirming = None
        item = self._wishbook.get(blueprint_id)
        if item is not None:
            self._wish_crafts.set(str(item.crafts))

    def _set_crafts(self) -> None:
        if self._picked_wish is None:
            self._shell.set_status("Select a wishlist entry first.")
            return
        try:
            crafts = int(self._wish_crafts.get().strip())
        except ValueError:
            self._shell.set_status(f"The number of crafts must be a whole number from 1 to {wishlist_mod.MAX_CRAFTS}.")
            return
        try:
            self._wishbook.set_crafts(self._picked_wish, crafts)
        except wishlist_mod.WishError as err:
            self._shell.set_status(str(err))
            return
        self._shell.set_status("Crafts changed.")

    def _confirm(self, what: str, message: str) -> bool:
        """A first press asks and a second press (within a few seconds) goes ahead."""
        if self._confirming != what:
            self._confirming = what
            self._shell.set_status(message)
            self._shell.window.after(CONFIRM_MS, self._stop_confirming)
            return False
        self._confirming = None
        return True

    def _stop_confirming(self) -> None:
        self._confirming = None

    def _remove(self) -> None:
        if self._picked_wish is None:
            self._shell.set_status("Select a wishlist entry first.")
            return
        if not self._confirm("remove", "Press Remove again to take this blueprint off the wishlist."):
            return
        gone, self._picked_wish = self._picked_wish, None
        if self._wishbook.remove(gone):
            self._shell.set_status("Removed.")

    def _clear(self) -> None:
        if not self._wishbook.count():
            return
        if not self._confirm("clear", "Press Clear list again to empty the whole wishlist."):
            return
        self._picked_wish = None
        self._shell.set_status(f"Cleared {self._wishbook.clear()} blueprint(s).")

    def _fill_wishlist(self) -> None:
        shopping = needs_mod.shopping_list(self._wishbook.items(), self._holdings())
        keep = self._picked_wish
        self._wish_table.clear()
        for entry in shopping.entries:
            self._wish_table.insert(entry.item.blueprint_id, (clip(f"{entry.blueprint.type}: {entry.blueprint.title}", 64), entry.item.crafts,
                                                              entry_ready_text(entry), f"{entry_short(entry):,}",
                                                              who_can(entry.blueprint, self._engineers)))
        if keep and self._wishbook.get(keep) is not None:
            self._wish_table.select(keep)
        else:
            self._picked_wish = None
        self._shopping_table.set_rows(shopping_rows(shopping))
        if not shopping.entries:
            self._shopping_title.configure(text="Shopping list")
        else:
            self._shopping_title.configure(
                text=f"Shopping list: {shopping.ready_count} of {len(shopping.entries)} can be made now, {shopping.short_pieces:,} pieces short")

    # --- the Engineers tab ---------------------------------------------------------------------------------------------

    def _build_engineers(self, tab: tk.Frame) -> None:
        pad = tk.Frame(tab, bg=P.PANE)
        pad.pack(fill="both", expand=True, padx=P.PAD, pady=P.PAD)
        self._engineer_table = DataTable(pad, _ENGINEER_COLUMNS, on_select=self._pick_engineer, visible_rows=14,
                                         empty_text="No engineers yet. They appear when the game lists them (at login).")
        self._engineer_table.pack(fill="x", pady=(0, P.PAD_SM))
        controls = tk.Frame(pad, bg=P.PANE)
        controls.pack(fill="x")
        FlatButton(controls, "Show their blueprints", self._show_engineer_blueprints).pack(side="left")
        FlatButton(controls, "Put their unlock on the wishlist", self._add_unlock).pack(side="left", padx=(P.PAD, 0))
        self._engineer_note = tk.Label(pad, text="", fg=P.MUTED, bg=P.PANE, anchor="w", justify="left", wraplength=980)
        self._engineer_note.pack(fill="x", pady=(P.PAD_SM, 0))
        self._picked_engineer: Optional[str] = None

    def _engineer_rows(self) -> List[tuple]:
        """(name, row values) for every engineer the table or the journal knows, unlocked ones first, then A to Z."""
        names: dict = {}
        for name in blueprints.engineer_names():
            names[engineers.name_key(name)] = name
        for standing in self._engineers.all():
            names.setdefault(engineers.name_key(standing.name), standing.name)
        offers: dict = {}
        for b in blueprints.ALL:
            for e in blueprints.real_engineers(b):
                offers[engineers.name_key(e)] = offers.get(engineers.name_key(e), 0) + 1
        known = self._engineers.has_data
        rows = []
        for key, name in names.items():
            standing = self._engineers.standing(name)
            unlock = blueprints.unlock_for(name, key=engineers.name_key)
            if standing is not None and standing.unlocked:
                text = "-"
            elif unlock is not None:
                text = clip("; ".join(self._unlock_part(n) for n in needs_mod.needs_for(unlock, 1, self._holdings())), 90)
            else:
                text = "not in the table"
            rows.append((standing is not None and standing.unlocked, name, (name, standing.describe() if standing is not None
                         else ("not known yet" if known else "?"), offers.get(key, 0) or "-", text)))
        rows.sort(key=lambda r: (not r[0], r[1].casefold()))
        return [(name, values) for _unlocked, name, values in rows]

    @staticmethod
    def _unlock_part(need: needs_mod.Need) -> str:
        have = "" if need.have is None else f" (have {need.have:,})"
        return f"{need.need:,} x {need.ingredient.name}{have if need.have is not None else ' (not counted)'}"

    def _fill_engineers(self) -> None:
        keep = self._picked_engineer
        self._engineer_table.clear()
        for name, values in self._engineer_rows():
            self._engineer_table.insert(name, values)
        if keep and self._engineer_table.exists(keep):
            self._engineer_table.select(keep)
        if self._engineers.has_data:
            self._engineer_note.configure(text="Standings come from the journal's engineer list, sent at login and when one changes. Unlock needs are from "
                                               "the blueprint table (March 2024): an invitation may also need something the table does not list.")
        else:
            self._engineer_note.configure(text="The game has not listed your engineers yet. Log in to the game and they appear here.")

    def _pick_engineer(self, name: str) -> None:
        self._picked_engineer = name

    def _show_engineer_blueprints(self) -> None:
        if self._picked_engineer is None:
            self._shell.set_status("Select an engineer first.")
            return
        self._type.set(ALL)
        self._query.set(self._picked_engineer)
        self._fill_blueprints()
        self._tabs.select(0)

    def _add_unlock(self) -> None:
        if self._picked_engineer is None:
            self._shell.set_status("Select an engineer first.")
            return
        unlock = blueprints.unlock_for(self._picked_engineer, key=engineers.name_key)
        if unlock is None:
            self._shell.set_status("The table has no unlock for that engineer.")
            return
        self._add_blueprint(unlock.id, 1)

    # --- the window ----------------------------------------------------------------------------------------------------

    @property
    def alive(self) -> bool:
        return self._shell.alive

    def lift(self) -> None:
        self._shell.window.deiconify()
        self._shell.window.lift()

    def close(self) -> None:
        self._wishbook.remove_listener(self._on_changed)
        self._engineers.remove_listener(self._on_changed)
        self._shell.close()

    def _on_changed(self) -> None:
        try:
            if self.alive:
                self.refresh()
        except tk.TclError:
            pass   # the window went away between the check and the redraw

    def refresh(self) -> None:
        if not self.alive:
            return
        who = self._wishbook.commander
        count = self._wishbook.count()
        self._shell.set_subtitle(f"{who}: {count} blueprint{'s' if count != 1 else ''} on the wishlist" if who
                                 else "Waiting for a commander (log in)")
        self._fill_detail()
        self._fill_wishlist()
        self._fill_engineers()
        if not self._shell._status.cget("text"):
            self._shell.set_status("Counts: ship materials come from your journal, on-foot items from your ship locker only (not the backpack or a "
                                   "carrier's locker). Trade goods are not counted.")
