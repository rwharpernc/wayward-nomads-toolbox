"""Tabbed inventory browser popup for Field Ops' Inventory content.

Built on the shared window kit (plugin/uikit: WindowShell, Tabs, DataTable,
ProgressBar - see docs/WINDOW_FRAMEWORK_SPEC.md); the counts, capacities and
wording are unchanged."""

from __future__ import annotations

import logging
import os
import tkinter as tk
from typing import Callable, Dict, Mapping, Optional, Tuple

from config import appname, config

from .inventory import SHIP_LOCKER_CAPACITY, WARNING_THRESHOLD, InventoryTracker, TRACKED_CATEGORIES
from .inventory_names import display_name
from .inventory_suit import SuitState
from .uikit import palette as P
from .uikit import style
from .uikit.shell import WindowShell
from .uikit.table import Column, DataTable
from .uikit.widgets import FlatButton, ProgressBar, Tabs

plugin_name = os.path.basename(os.path.dirname(__file__))
logger = logging.getLogger(f"{appname}.{plugin_name}")

CONFIG_GEOMETRY = "wntb_inventory_window_geometry"

# Journal category -> in-game wording.
CATEGORY_LABELS: Dict[str, str] = {
    "Component": "Assets (Components)",
    "Item": "Goods (Items)",
    "Data": "Data",
}

# Short form, for the Category column.
CATEGORY_SHORT: Dict[str, str] = {
    "Component": "Assets",
    "Item": "Goods",
    "Data": "Data",
}

MIN_WIDTH = 720
MIN_HEIGHT = 420
DEFAULT_SIZE = (900, 650)

# key, tab label, in-window heading
TABS = (
    ("backpack", "Backpack", "Backpack — carried on foot"),
    ("ship_locker", "Ship Locker", "Ship Locker — stored aboard your ship"),
    ("fleet_carrier_locker", "Carrier Locker", "Carrier Locker — from CAPI, may lag 15–30 min"),
)

# Capacity highlight colours: NEAR is the amber "pay attention" cue (also used
# for the baseline note below); FULL escalates once a category is actually capped.
COLOUR_NORMAL = P.INFO
COLOUR_NEAR = P.WARN
COLOUR_FULL = P.DANGER

_COLUMNS = (
    Column("item", "Resource", 420, stretch=True, max_chars=60),
    Column("category", "Category", 140),
    Column("count", "Held", 90, anchor="e"),
)

_window: Optional["InventoryWindow"] = None


# Supplies the Cargo tab: (label, total tonnage, capacity or None, {commodity: count}),
# or None while on foot with no vehicle (a cargo hold doesn't apply).
CargoSource = Callable[[], Optional[Tuple[str, int, Optional[int], Mapping[str, int]]]]

_CARGO_COLUMNS = (
    Column("item", "Commodity", 420, stretch=True, max_chars=60),
    Column("count", "Tonnes", 90, anchor="e"),
)


def show(parent: tk.Misc, tracker: InventoryTracker, suit: SuitState, cargo_source: Optional[CargoSource] = None) -> None:
    """Open the inventory window, or raise it if already open."""
    global _window

    if _window is not None and _window.alive:
        _window.refresh()
        _window.lift()
        return

    _window = InventoryWindow(parent, tracker, suit, cargo_source)


def refresh() -> None:
    """Update the window if it is open."""
    if _window is not None and _window.alive:
        _window.refresh()


def close() -> None:
    if _window is not None and _window.alive:
        _window.close()


class InventoryWindow:
    """Toplevel with a tab per storage location."""

    def __init__(
        self, parent: tk.Misc, tracker: InventoryTracker, suit: SuitState,
        cargo_source: Optional[CargoSource] = None,
    ) -> None:
        self._tracker = tracker
        self._suit = suit
        self._cargo_source = cargo_source

        self._shell = WindowShell(
            parent, "Inventory", "", size=DEFAULT_SIZE, min_size=(MIN_WIDTH, MIN_HEIGHT),
            load_geometry=lambda: config.get_str(CONFIG_GEOMETRY) or "",
            save_geometry=lambda geometry: config.set(CONFIG_GEOMETRY, geometry))
        self._shell.window.protocol("WM_DELETE_WINDOW", self.close)
        self._toplevel = self._shell.window
        self._shell.add_action("Refresh", self.refresh)

        filter_bar = tk.Frame(self._shell.body, bg=P.BG)
        filter_bar.pack(fill="x", pady=(0, P.PAD_SM))
        tk.Label(filter_bar, text="Filter:", fg=P.MUTED, bg=P.BG).pack(side="left", padx=(0, 6))
        self._filter_var = tk.StringVar()
        self._filter_var.trace_add("write", lambda *_args: self.refresh())
        tk.Entry(filter_bar, textvariable=self._filter_var).pack(side="left", fill="x", expand=True)
        FlatButton(filter_bar, "Clear", self._clear_filter).pack(side="left", padx=(6, 0))

        self._tab_bar = Tabs(self._shell.body)
        self._tab_bar.pack(fill="both", expand=True, pady=(0, P.PAD_SM))

        self._tabs: Dict[str, _LocationTab] = {}
        self._tab_index: Dict[str, int] = {}
        for index, (key, tab_label, tab_heading) in enumerate(TABS):
            self._tabs[key] = _LocationTab(self._tab_bar.add(tab_label), tab_heading)
            self._tab_index[key] = index
        self._carrier_tab_shown = True

        # Cargo is a different game system from the microresource stores above
        # (tonnage, not item counts), so it gets its own tab type, last in order.
        self._cargo_tab = _CargoTab(self._tab_bar.add("Cargo"))

        self.refresh()

    @property
    def alive(self) -> bool:
        return self._shell.alive

    def lift(self) -> None:
        self._toplevel.deiconify()
        self._toplevel.lift()

    def refresh(self) -> None:
        if not self.alive:
            return

        snapshot = self._tracker.snapshot()
        self._shell.set_subtitle(f"Suit: {self._suit.display_name}")

        capacities = {
            "backpack": self._suit.capacities(cmdr=self._tracker.commander),
            "ship_locker": SHIP_LOCKER_CAPACITY,
            "fleet_carrier_locker": {},
        }

        # No fresh Backpack/Resupply event yet this session — commonly hit when
        # logging in already on foot. The counts below may be stale or zero
        # rather than a confirmed empty backpack; say so instead of guessing.
        backpack_note = (
            None
            if self._tracker.backpack_baseline_seen
            else "Not yet synced this session — loot, resupply, or disembark to refresh."
        )
        notes = {"backpack": backpack_note, "ship_locker": None, "fleet_carrier_locker": None}
        filter_text = self._filter_var.get().strip()

        for key, tab in self._tabs.items():
            tab.update(snapshot.get(key, {}), capacities[key], note=notes[key], filter_text=filter_text)

        cargo = self._cargo_source() if self._cargo_source is not None else None
        self._cargo_tab.update(cargo, filter_text=filter_text)

        self._update_carrier_tab_visibility()

    def _update_carrier_tab_visibility(self) -> None:
        """
        Show the Carrier Locker tab only once a fleet carrier is actually
        confirmed for this commander (fleet_carrier_callsign only ever gets
        set from real CAPI locker data - see InventoryTracker.
        apply_fleet_carrier_locker) - same gating as the main panel's
        Carrier Locker bar, so a commander with no carrier never sees a tab
        for one here either.
        """
        has_carrier = bool(self._tracker.fleet_carrier_callsign)
        if has_carrier == self._carrier_tab_shown:
            return
        self._tab_bar.set_tab_visible(self._tab_index["fleet_carrier_locker"], has_carrier)
        self._carrier_tab_shown = has_carrier

    def _clear_filter(self) -> None:
        self._filter_var.set("")

    def close(self) -> None:
        self._shell.close()


class _CargoTab:
    """Cargo-hold tonnage bar plus a commodity listing for the current vehicle."""

    def __init__(self, parent: tk.Frame) -> None:
        self._heading = tk.Label(parent, text="Cargo", anchor="w", bg=P.PANE, fg=P.TEXT,
                                 font=style.font(P.FONT_SECTION), padx=P.PAD)
        self._heading.pack(fill="x", pady=(P.PAD, 8))

        summary = tk.Frame(parent, bg=P.PANE)
        summary.pack(fill="x", padx=P.PAD, pady=(0, P.PAD))
        self._bar = ProgressBar(summary, width=220, height=10)
        self._bar.grid(row=0, column=0, padx=(0, 10), sticky="w")
        self._total = tk.Label(summary, text="0", anchor="w", bg=P.PANE, fg=P.TEXT)
        self._total.grid(row=0, column=1, sticky="w")

        tk.Frame(parent, bg=P.LINE, height=1).pack(fill="x", padx=P.PAD)

        self._table = DataTable(parent, _CARGO_COLUMNS)
        self._table.pack(fill="both", expand=True, padx=P.PAD, pady=P.PAD)

    def update(self, cargo, *, filter_text: str = "") -> None:
        self._table.clear()

        if cargo is None:
            self._heading.configure(text="Cargo — not applicable on foot")
            self._total.configure(text="", fg=P.TEXT)
            self._bar.set(0, COLOUR_NORMAL)
            self._table.append(("(no cargo hold while on foot)", ""))
            return

        label, total, capacity, items = cargo
        self._heading.configure(text=f"{label} — tonnes carried")

        if capacity:
            self._total.configure(text=f"{total} / {capacity}")
            percent = min(100, round(total * 100 / capacity))
        else:
            self._total.configure(text=f"{total}  (capacity unknown)")
            percent = 0
        colour, text_colour = _LocationTab._capacity_colours(total, capacity)
        self._bar.set(percent, colour)
        self._total.configure(fg=text_colour)

        needle = filter_text.strip().lower()
        rows = 0
        for name, count in sorted(items.items(), key=lambda kv: (-kv[1], kv[0])):
            if count <= 0:
                continue
            commodity = display_name(name)
            if needle and needle not in commodity.lower():
                continue
            self._table.append((commodity, count))
            rows += 1

        if rows == 0:
            self._table.append((f'(no matches for "{filter_text.strip()}")' if needle and items else "(hold is empty)", ""))


class _LocationTab:
    """Per-category totals plus an item listing for one storage location."""

    def __init__(self, parent: tk.Frame, heading: str) -> None:
        # Repeat the location inside the tab as well as in the tab strip.
        tk.Label(parent, text=heading, anchor="w", bg=P.PANE, fg=P.TEXT, font=style.font(P.FONT_SECTION),
                 padx=P.PAD).pack(fill="x", pady=(P.PAD, 8))

        self._note = tk.Label(parent, text="", anchor="w", bg=P.PANE, fg=P.WARN, padx=P.PAD)
        self._note.pack(fill="x", pady=(0, 4))

        summary = tk.Frame(parent, bg=P.PANE)
        summary.pack(fill="x", padx=P.PAD, pady=(0, P.PAD))
        summary.columnconfigure(3, weight=1)

        self._bars: Dict[str, ProgressBar] = {}
        self._totals: Dict[str, tk.Label] = {}

        for row, category in enumerate(TRACKED_CATEGORIES):
            tk.Label(summary, text=CATEGORY_LABELS[category], width=22, anchor="w", bg=P.PANE,
                     fg=P.TEXT).grid(row=row, column=0, sticky="w", pady=3)
            bar = ProgressBar(summary, width=220, height=10)
            bar.grid(row=row, column=1, padx=(6, 10), sticky="w")
            total = tk.Label(summary, text="0", width=22, anchor="w", bg=P.PANE, fg=P.TEXT)
            total.grid(row=row, column=2, sticky="w")

            self._bars[category] = bar
            self._totals[category] = total

        tk.Frame(parent, bg=P.LINE, height=1).pack(fill="x", padx=P.PAD)

        self._table = DataTable(parent, _COLUMNS)
        self._table.pack(fill="both", expand=True, padx=P.PAD, pady=P.PAD)

    def update(
        self,
        store: Mapping[str, Mapping[str, int]],
        capacities: Mapping[str, int],
        *,
        note: Optional[str] = None,
        filter_text: str = "",
    ) -> None:
        self._note.configure(text=note or "")

        # Totals/bars always reflect the true category contents - only the
        # item listing below is narrowed by the filter box.
        for category in TRACKED_CATEGORIES:
            items = store.get(category, {})
            total = sum(items.values())
            capacity = capacities.get(category)

            if capacity:
                self._totals[category].configure(text=f"{total} / {capacity}")
                percent = min(100, round(total * 100 / capacity))
            else:
                self._totals[category].configure(text=f"{total}  (capacity unknown)")
                percent = 0

            colour, text_colour = self._capacity_colours(total, capacity)
            self._bars[category].set(percent, colour)
            self._totals[category].configure(fg=text_colour)

        self._table.clear()

        needle = filter_text.strip().lower()
        had_any_items = False
        rows = 0
        for category in TRACKED_CATEGORIES:
            items = store.get(category, {})
            for name, count in sorted(items.items(), key=lambda kv: (-kv[1], kv[0])):
                had_any_items = True
                label = display_name(name)
                if needle and needle not in label.lower():
                    continue
                self._table.append((label, CATEGORY_SHORT[category], count))
                rows += 1

        if rows == 0:
            message = f'(no matches for "{filter_text.strip()}")' if needle and had_any_items else "(nothing stored)"
            self._table.append((message, "", ""))

    @staticmethod
    def _capacity_colours(total: int, capacity: Optional[int]) -> tuple:
        """(bar colour, total-label colour): highlighted once a category nears or hits capacity."""
        if capacity and total >= capacity:
            return COLOUR_FULL, COLOUR_FULL
        if capacity and total >= capacity * WARNING_THRESHOLD:
            return COLOUR_NEAR, COLOUR_NEAR
        return COLOUR_NORMAL, P.TEXT
