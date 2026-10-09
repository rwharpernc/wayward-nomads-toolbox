"""Field Ops mode: Odyssey on-foot/cargo inventory tracking, alongside
Screenshots in Field Ops.

Tracks backpack/ship-locker/fleet-carrier-locker micro-resource counts, the
worn suit's backpack capacity, and ship/SRV cargo tonnage; fires a
"pillage" notification (status line + overlay text + optional sound)
whenever a tracked pickup is added. The same 4 capacity rows show on the
main panel, the in-game overlay (persistent bars), and the full inventory-
browser popup (`inventory_window.py`).

`PANEL_PLACEMENT = "fieldops"` per the feature-module contract. The overlay
rendering (pillage-line stack + persistent capacity bars) goes through the
shared `overlay.OverlayClient`, and the EDMCModernOverlay Plugin Group this
feature registers (`GROUP_NAME`/`GROUP_PREFIX` below) uses WNTB's own
`overlay.register_modern_overlay_groups()` call. Every one of this
feature's overlay ids shares one prefix
(`wntb_inventory_`) so a single group registration covers both the pillage
stack and the bars — a genuine multi-shape composite (the pillage stack
sits directly above the bars as one HUD panel), unlike every earlier
overlay feature in this project, which deliberately did not register a
group.
"""

from __future__ import annotations

import json
import logging
import os
import threading
import time
from typing import Any, Dict, FrozenSet, List, Optional, Tuple

import tkinter as tk

import myNotebook as nb
from config import appname, config
from theme import theme

from . import inventory_names as names
from . import inventory_suit as suit
from . import overlay, panelkit
from .inventory import CATEGORY_SHORT, InventoryTracker, SHIP_LOCKER_CAPACITY, TRACKED_CATEGORIES
from .inventory_cargo import VehicleState
from . import platform_support
from .inventory_sound import PillageSound
from .inventory_suit import SuitState

plugin_name = os.path.basename(os.path.dirname(__file__))
logger = logging.getLogger(f"{appname}.{plugin_name}")

PANEL_PLACEMENT = "fieldops"

# --- Overlay geometry/ids (drawn through the shared OverlayClient) ---------

# Every one of this feature's overlay ids shares this one prefix, so the
# single Plugin Group registered in load.py covers the pillage stack and
# the capacity bars together (see the module docstring).
ID_PREFIX = "wntb_inventory_"
GROUP_NAME = "wntb_inventory"
GROUP_PREFIX = ID_PREFIX

MAX_LINES = 5
TTL_SECONDS = 8
# Legacy overlay coordinates are on a 1280x960 virtual screen.
MAX_ORIGIN_X = 1280
MAX_ORIGIN_Y = 960
DEFAULT_ORIGIN_X = 900
DEFAULT_ORIGIN_Y = 120
LINE_HEIGHT = 18
COLOUR = "#ffbf00"
TEXT_SIZE = "normal"

# Pillage-line colour per journal category (Component/Item/Data), so the
# stack is scannable by category at a glance rather than one flat colour.
CATEGORY_COLOURS: Dict[str, str] = {
    "Component": "#4fc3f7",  # Assets - blue
    "Item": "#81c784",       # Goods - green
    "Data": "#ba68c8",       # Data - violet
}

# The four inventory bars the main panel and the overlay both show - same
# keys, same colours, same fixed order - each independently togglable on
# the overlay via Settings.
BAR_ORDER: Tuple[str, ...] = ("backpack", "ship_locker", "fleet_carrier_locker", "cargo")
BAR_COLOURS: Dict[str, str] = {
    "backpack": "#4fc3f7",
    "ship_locker": "#81c784",
    "fleet_carrier_locker": "#ba68c8",
    "cargo": "#ff8c0d",
}
BAR_DEFAULT_LABELS: Dict[str, str] = {
    "backpack": "Backpack",
    "ship_locker": "Ship Locker",
    "fleet_carrier_locker": "Carrier Locker",
    "cargo": "Cargo",
}

# Inventory bars: a persistent (long-TTL, refreshed on every relevant
# journal event) row per BAR_ORDER entry, below the pillage stack.
CAPACITY_BAR_GAP = 8            # px between the pillage stack and the bars
CAPACITY_ROW_HEIGHT = 16
CAPACITY_LABEL_WIDTH = 100       # fits "Carrier Locker", the longest label
CAPACITY_BAR_WIDTH = 140
CAPACITY_BAR_HEIGHT = 10
CAPACITY_VALUE_GAP = 8
CAPACITY_TRACK_COLOUR = "#555555"
# Long enough to look persistent between updates; refreshed well before this
# on any further activity.
CAPACITY_TTL = 3600

# Ship locker capacity warning: distinct from pillage lines, so it gets its
# own colour and a longer TTL — missing it can mean being forced to drop
# loot rather than just missing a pickup notification.
LOCKER_WARNING_COLOUR = "#ff3030"
LOCKER_WARNING_TTL = 20

# --- Config keys -----------------------------------------------------------

_CFG_OVERLAY_ENABLED = "wntb_inventory_overlay_enabled"
_CFG_OVERLAY_X = "wntb_inventory_overlay_x"
_CFG_OVERLAY_Y = "wntb_inventory_overlay_y"
_CFG_OVERLAY_BAR_PREFIX = "wntb_inventory_overlay_bar_"
_CFG_SOUND_ENABLED = "wntb_inventory_sound_enabled"
_CFG_MESSAGE_FORMAT = "wntb_inventory_message_format"
_CFG_ANNOUNCE_CATEGORIES = "wntb_inventory_announce_categories"

DEFAULT_MESSAGE_FORMAT = "[{item}] pillaged! New Inventory Total: {total}"

# --- Main-panel bar widget geometry (fixed so a long label/large count can
# never widen EDMC's main window) ------------------------------------------

_BAR_NAME_WIDTH = 13
_BAR_VALUE_WIDTH = 13
_BAR_WIDTH = 80
_BAR_HEIGHT = 8

_BAR_FULL_COLOUR = "#c0392b"
_BAR_DEFAULT_COLOUR = "#9e9e9e"
_BAR_TRACK_LIGHT = "#c0c4c7"

# (key, label, total, capacity_or_None) for one main-panel/overlay bar row.
BarRow = Tuple[str, str, int, Optional[int]]

_THEME_DEBUG_LOG_LIMIT = 60


def overlay_enabled() -> bool:
    return config.get_bool(_CFG_OVERLAY_ENABLED, default=False)


def sound_enabled() -> bool:
    return config.get_bool(_CFG_SOUND_ENABLED, default=False)


def message_format() -> str:
    return config.get_str(_CFG_MESSAGE_FORMAT) or DEFAULT_MESSAGE_FORMAT


def format_pillage_message(item: str, total: int) -> str:
    """Render the configured pillage message, falling back to the default on a bad template."""
    template = message_format()
    try:
        return template.format(item=item, total=total)
    except (KeyError, IndexError, ValueError):
        logger.warning("Invalid pillage message format %r; using the default", template)
        return DEFAULT_MESSAGE_FORMAT.format(item=item, total=total)


def _get_int(key: str, default: int) -> int:
    raw = config.get_str(key)
    try:
        return int(raw) if raw else default
    except ValueError:
        return default


def overlay_position() -> Tuple[int, int]:
    """The in-game overlay's on-screen origin, clamped to its virtual screen."""
    x = _get_int(_CFG_OVERLAY_X, DEFAULT_ORIGIN_X)
    y = _get_int(_CFG_OVERLAY_Y, DEFAULT_ORIGIN_Y)
    return max(0, min(MAX_ORIGIN_X, x)), max(0, min(MAX_ORIGIN_Y, y))


def overlay_enabled_bars() -> FrozenSet[str]:
    """Which of BAR_ORDER should draw on the in-game overlay, each
    independently toggled in Settings. Defaults to off for every bar (no
    legacy-key migration needed — WNTB starts clean)."""
    return frozenset(key for key in BAR_ORDER if config.get_bool(f"{_CFG_OVERLAY_BAR_PREFIX}{key}", default=False))


def announced_categories() -> FrozenSet[str]:
    """Categories whose pickups get a pillage notification (log line,
    overlay, panel status). Counts are always tracked regardless of this
    setting — it only gates the notification."""
    raw = config.get_str(_CFG_ANNOUNCE_CATEGORIES)
    if not raw:
        return frozenset(TRACKED_CATEGORIES)
    try:
        selected = json.loads(raw)
    except (TypeError, ValueError):
        return frozenset(TRACKED_CATEGORIES)
    if not isinstance(selected, list):
        return frozenset(TRACKED_CATEGORIES)
    return frozenset(category for category in selected if category in TRACKED_CATEGORIES)


class InventoryPanelController:
    def __init__(self) -> None:
        self._tracker = InventoryTracker()
        self._suit = SuitState()
        self._vehicle = VehicleState()
        self._sound = PillageSound()
        self._overlay_client = overlay.OverlayClient()

        self._plugin_dir: Optional[str] = None
        self._last_state: Dict[str, Any] = {}
        self._parent: Optional[tk.Frame] = None

        # Overlay render state.
        self._overlay_x, self._overlay_y = DEFAULT_ORIGIN_X, DEFAULT_ORIGIN_Y
        self._overlay_lines: List[Tuple[str, str, float, str]] = []  # (key, text, expiry, colour)
        self._overlay_rendered_rows = 0
        self._rendered_bar_keys: FrozenSet[str] = frozenset()
        self._bars_broken = False

        # Main-panel widgets.
        self._status_label: Optional[tk.Label] = None
        self._last_event_label: Optional[tk.Label] = None
        self._bar_rows: Dict[str, Dict[str, tk.Widget]] = {}
        self._last_rows: List[BarRow] = []
        self._theme_debug_log_count = 0

        # Settings-tab vars.
        self._overlay_var: Optional[tk.BooleanVar] = None
        self._overlay_x_var: Optional[tk.StringVar] = None
        self._overlay_y_var: Optional[tk.StringVar] = None
        self._overlay_bar_vars: Dict[str, tk.BooleanVar] = {}
        self._sound_var: Optional[tk.BooleanVar] = None
        self._message_format_var: Optional[tk.StringVar] = None
        self._announce_vars: Dict[str, tk.BooleanVar] = {}
        self._override_vars: Dict[Tuple[str, str], tk.StringVar] = {}
        self._override_defaults: Dict[Tuple[str, str], Optional[int]] = {}

    def set_overlay_client(self, client: overlay.OverlayClient) -> None:
        self._overlay_client = client

    # --- lifecycle ----------------------------------------------------------

    def start(self, plugin_dir: str) -> None:
        self._plugin_dir = plugin_dir
        names.load_learned_names()
        suit.load_overrides()
        self._sound.set_enabled(sound_enabled())
        self._overlay_x, self._overlay_y = overlay_position()

    def stop(self) -> None:
        names.save_learned_names()
        suit.save_overrides()
        self._overlay_clear_all_sync()

    # --- journal/CAPI dispatch ------------------------------------------------

    def handle_event(self, entry: Dict[str, Any], cmdr: str, system: Optional[str], station: Optional[str], state: Dict[str, Any]) -> None:
        self._last_state = state
        try:
            self._dispatch(cmdr, entry, state)
        finally:
            from . import inventory_window
            inventory_window.refresh()
            self._refresh_bars(state)

    def _dispatch(self, cmdr: str, entry: Dict[str, Any], state: Dict[str, Any]) -> None:
        event = entry.get("event", "")

        if event in ("LoadGame", "Start"):
            self._on_commander_session(cmdr, state, reason=event)
            return

        if event in ("Backpack", "Resupply"):
            self._tracker.apply_backpack_baseline(entry)
            self._tracker.sync_backpack_from_state(state)
            self._set_status("Backpack synced")
            return

        if event == "ShipLocker":
            self._tracker.apply_ship_locker_baseline(entry)
            self._tracker.sync_ship_locker_from_state(state)
            self._set_status("Ship locker synced")
            self._warn_ship_locker_capacity()
            return

        if event in ("SuitLoadout", "SwitchSuitLoadout"):
            # Disembarking / starting on foot / changing loadout: the suit
            # determines backpack capacity, so record it alongside the
            # backpack contents.
            self._suit.apply_suit_loadout(entry, cmdr=cmdr)
            self._tracker.sync_backpack_from_state(state)
            return

        if event == "BackpackChange":
            self._handle_backpack_change(entry, state)
            return

        if event == "CarrierDecommission":
            self._tracker.clear_fleet_carrier_for_commander(cmdr)
            self._set_status(f"Carrier decommissioned ({cmdr})")
            return

        if event == "Embark":
            self._vehicle.apply_embark(entry)
            return

        if event == "Disembark":
            self._vehicle.apply_disembark(entry)
            return

        if event == "LaunchSRV":
            self._vehicle.apply_launch_srv(entry)
            return

        if event == "DockSRV":
            self._vehicle.apply_dock_srv(entry)
            return

    def capi_fleetcarrier(self, data: Any) -> None:
        """Receive fleet carrier CAPI data from EDMC (requires Frontier
        auth). EDMC fetches /fleetcarrier on CarrierBuy/CarrierStats (15 min
        throttle). Carrier locker data may lag the live game by 15-30
        minutes."""
        request_cmdr = getattr(data, "request_cmdr", None)
        if not request_cmdr:
            return

        callsign = self._carrier_callsign(data)
        carrier_locker = data.get("carrierLocker")

        if not isinstance(carrier_locker, dict):
            self._tracker.clear_fleet_carrier_for_commander(request_cmdr)
            if request_cmdr == self._tracker.commander:
                self._set_status(f"No carrier locker ({request_cmdr})")
                self._refresh_bars(self._last_state)
            return

        stack_count = self._tracker.apply_fleet_carrier_locker(carrier_locker, callsign=callsign, cmdr=request_cmdr)
        label = callsign or "carrier"

        if request_cmdr != self._tracker.commander:
            logger.info(
                "Fleet carrier locker cached for %s (%s, %d stacks); active CMDR is %s",
                request_cmdr, label, stack_count, self._tracker.commander,
            )
            return

        logger.info("Fleet carrier locker synced from CAPI (%s / %s): %d stack(s)", request_cmdr, label, stack_count)
        self._set_status(f"Carrier locker synced ({label}, {stack_count} stacks)")
        self._refresh_bars(self._last_state)

    def _carrier_callsign(self, data: Any) -> Optional[str]:
        name_block = data.get("name")
        if isinstance(name_block, dict):
            callsign = name_block.get("callsign")
            if isinstance(callsign, str) and callsign:
                return callsign
        return None

    def _on_commander_session(self, cmdr: str, state: Dict[str, Any], *, reason: str) -> None:
        self._vehicle.reset()
        switched = self._tracker.set_commander(cmdr)
        self._tracker.sync_all_from_state(state)
        self._warn_ship_locker_capacity()

        # EDMC only (re)populates the backpack from a fresh Backpack/Resupply
        # event, and clears it on LoadGame. A commander already on foot when
        # EDMC attaches may not get one of those for a while, so say so
        # rather than presenting the zeroed-out backpack as confirmed empty.
        pending_note = "" if self._tracker.backpack_baseline_seen else " (backpack pending first sync)"

        if switched:
            if self._tracker.fleet_carrier_callsign:
                self._set_status(
                    f"{cmdr}: inventory synced (carrier {self._tracker.fleet_carrier_callsign} cached){pending_note}",
                )
            else:
                self._set_status(f"{cmdr}: inventory synced (no carrier data yet){pending_note}")
        else:
            self._set_status(f"Inventory synced{pending_note}")

    def _warn_ship_locker_capacity(self) -> None:
        """Warn (log + overlay) for any ship locker category that just
        crossed WARNING_THRESHOLD of its capacity. Ship locker updates the
        same way whether a commander transfers items at their own ship or
        remotely via an Apex shuttle's "Manage Items" screen — both write
        through the same ShipLocker journal event this is called from."""
        announced = announced_categories()
        for category, total, capacity in self._tracker.ship_locker_capacity_warnings():
            if category not in announced:
                continue
            label = CATEGORY_SHORT[category]
            message = f"⚠ Ship Locker {label}: {total}/{capacity} — nearing capacity"
            logger.warning(message)
            self._overlay_notify(
                f"__locker_full_{category}", message, colour=LOCKER_WARNING_COLOUR, ttl=LOCKER_WARNING_TTL,
            )

    def _handle_backpack_change(self, entry: Dict[str, Any], state: Dict[str, Any]) -> None:
        pillage_messages = []
        announced = announced_categories()

        for label, internal_name, category, delta, _backpack_total in self._tracker.apply_backpack_change(entry):
            # Counts are always tracked regardless of the announce-category
            # prefs — only the pillage notification for a muted category is
            # suppressed here.
            if category not in announced:
                continue

            combined_total = self._tracker.get_combined_total(internal_name, category)
            message = format_pillage_message(label, combined_total)
            logger.info(message)
            pillage_messages.append(message)
            self._overlay_notify(
                internal_name, f"+{delta}  {label}: {combined_total}", colour=CATEGORY_COLOURS.get(category, COLOUR),
            )

        # Reconcile with EDMC state after processing journal deltas.
        self._tracker.sync_backpack_from_state(state)

        if pillage_messages:
            self._sound.play()
            self._set_last_event(pillage_messages[-1])
            self._set_status(f"+{len(pillage_messages)} item(s) pillaged")

    def _refresh_bars(self, state: Dict[str, Any]) -> None:
        """Redraw the main-panel inventory bars and, for whichever of them
        are overlay-enabled, the matching in-game overlay bars - both from
        the exact same computed rows, so panel and overlay can never
        disagree. Cheap and called after every journal event (like
        inventory_window.refresh()) rather than only from the handlers that
        changed a given store, so a bar can never go stale after an event
        this function doesn't otherwise know about."""
        snapshot = self._tracker.snapshot()
        backpack_capacities = self._suit.capacities(cmdr=self._tracker.commander)

        rows: List[BarRow] = [
            (
                "backpack", "Backpack",
                sum(sum(items.values()) for items in snapshot["backpack"].values()),
                sum(backpack_capacities.values()) if len(backpack_capacities) == len(TRACKED_CATEGORIES) else None,
            ),
            (
                "ship_locker", "Ship Locker",
                sum(sum(items.values()) for items in snapshot["ship_locker"].values()),
                sum(SHIP_LOCKER_CAPACITY.values()),
            ),
        ]

        # Only show carrier data once we actually know this commander owns a
        # carrier - fleet_carrier_callsign is set from real CAPI locker data
        # and cleared for anyone who doesn't, so its presence is a reliable
        # "carrier confirmed" signal rather than a fresh commander simply not
        # having a carrier at all.
        if self._tracker.fleet_carrier_callsign:
            rows.append((
                "fleet_carrier_locker", "Carrier Locker",
                sum(sum(items.values()) for items in snapshot["fleet_carrier_locker"].values()),
                None,
            ))

        cargo_row = self._vehicle.cargo_bar(state)
        if cargo_row is not None:
            label, total, capacity = cargo_row
            rows.append(("cargo", label, total, capacity))

        self._set_inventory_levels(rows)

        enabled_bars = overlay_enabled_bars()
        self._render_bars([row for row in rows if row[0] in enabled_bars])

    def _set_status(self, message: str) -> None:
        if self._status_label is not None:
            self._status_label["text"] = message

    def _set_last_event(self, message: str) -> None:
        if self._last_event_label is not None:
            self._last_event_label["text"] = message
            self._last_event_label["foreground"] = "green"

    # --- overlay notification (rewired onto the shared OverlayClient) -------

    def _overlay_notify(self, key: str, text: str, *, colour: str = COLOUR, ttl: int = TTL_SECONDS) -> None:
        """Push a line, replacing any live line keyed by the same key.
        Pillage notifications key on the resource's internal name; other
        callers (e.g. ship locker capacity warnings) use their own distinct
        key so they don't collide with or get replaced by item pickups."""
        if not overlay_enabled():
            return

        now = time.monotonic()
        self._overlay_lines = [line for line in self._overlay_lines if line[0] != key]
        self._overlay_lines.insert(0, (key, text, now + ttl, colour))
        self._overlay_lines = [line for line in self._overlay_lines if line[2] > now][:MAX_LINES]

        lines = list(self._overlay_lines)
        previous_rows = self._overlay_rendered_rows
        self._overlay_rendered_rows = len(lines)
        origin_x, origin_y = self._overlay_x, self._overlay_y

        def worker() -> None:
            try:
                for row, (_key, row_text, expiry, row_colour) in enumerate(lines):
                    row_ttl = max(1, int(round(expiry - now)))
                    self._overlay_client.send_message(
                        f"{ID_PREFIX}pillage_{row}", row_text, row_colour, origin_x, origin_y + row * LINE_HEIGHT,
                        ttl=row_ttl, size=TEXT_SIZE,
                    )
                for row in range(len(lines), previous_rows):
                    self._overlay_client.send_message(
                        f"{ID_PREFIX}pillage_{row}", "", "white", origin_x, origin_y + row * LINE_HEIGHT, ttl=1,
                    )
            except OSError:
                logger.debug("Could not reach EDMCOverlay for pillage notification", exc_info=True)

        threading.Thread(target=worker, name="WNTB-inventory-overlay", daemon=True).start()

    def _render_bars(self, rows: List[BarRow]) -> None:
        """Draw (or refresh) the inventory-bars panel below the pillage
        stack: one row per (key, label, total, capacity) tuple - the same
        shape (and, for whichever keys are present, the exact same data) as
        the main panel's bars - coloured via BAR_COLOURS[key].

        Persistent (long TTL) rather than fading like pillage lines — this
        is re-rendered after every journal event to keep it current, so a
        quiet stretch just means a slightly stale (not blank) reading.

        A key from a previous call that's absent from `rows` (the commander
        toggled that bar off in Settings, or it's a conditional bar - no
        longer applicable) is actively cleared rather than left showing a
        stale value."""
        if self._bars_broken or not overlay_enabled():
            return

        base_y = self._overlay_y + MAX_LINES * LINE_HEIGHT + CAPACITY_BAR_GAP
        bar_x = self._overlay_x + CAPACITY_LABEL_WIDTH

        visible = [row for row in rows if row[0] in BAR_ORDER]
        drawn_keys = {row[0] for row in visible}
        stale_keys = self._rendered_bar_keys - drawn_keys
        self._rendered_bar_keys = frozenset(drawn_keys)

        def worker() -> None:
            try:
                for display_row, (key, label, total, capacity) in enumerate(visible):
                    colour = BAR_COLOURS.get(key, COLOUR)
                    row_y = base_y + display_row * CAPACITY_ROW_HEIGHT

                    self._overlay_client.send_message(
                        f"{ID_PREFIX}bar_label_{key}", label, colour, self._overlay_x, row_y,
                        ttl=CAPACITY_TTL, size=TEXT_SIZE,
                    )
                    self._overlay_client.send_shape(
                        f"{ID_PREFIX}bar_track_{key}", "rect", CAPACITY_TRACK_COLOUR, "", bar_x, row_y,
                        CAPACITY_BAR_WIDTH, CAPACITY_BAR_HEIGHT, ttl=CAPACITY_TTL, thickness=1,
                    )

                    fraction = max(0.0, min(1.0, total / capacity)) if capacity else 0.0
                    fill_width = max(1, round(CAPACITY_BAR_WIDTH * fraction)) if total > 0 else 0
                    if fill_width > 0:
                        self._overlay_client.send_shape(
                            f"{ID_PREFIX}bar_fill_{key}", "rect", colour, colour, bar_x, row_y,
                            fill_width, CAPACITY_BAR_HEIGHT, ttl=CAPACITY_TTL,
                        )
                    else:
                        self._overlay_client.send_shape(
                            f"{ID_PREFIX}bar_fill_{key}", "rect", "", "", bar_x, row_y, 0, 0, ttl=1,
                        )

                    value_text = f"{total}/{capacity}" if capacity else str(total)
                    self._overlay_client.send_message(
                        f"{ID_PREFIX}bar_value_{key}", value_text, colour,
                        bar_x + CAPACITY_BAR_WIDTH + CAPACITY_VALUE_GAP, row_y - 3, ttl=CAPACITY_TTL, size=TEXT_SIZE,
                    )

                for key in stale_keys:
                    self._clear_bar_key(key)
            except OSError:
                logger.debug("Could not reach EDMCOverlay for inventory bars", exc_info=True)
                self._bars_broken = True

        threading.Thread(target=worker, name="WNTB-inventory-bars", daemon=True).start()

    def _clear_bar_key(self, key: str) -> None:
        self._overlay_client.send_message(f"{ID_PREFIX}bar_label_{key}", "", "white", self._overlay_x, self._overlay_y, ttl=1)
        self._overlay_client.send_shape(f"{ID_PREFIX}bar_track_{key}", "rect", "", "", self._overlay_x, self._overlay_y, 0, 0, ttl=1)
        self._overlay_client.send_shape(f"{ID_PREFIX}bar_fill_{key}", "rect", "", "", self._overlay_x, self._overlay_y, 0, 0, ttl=1)
        self._overlay_client.send_message(f"{ID_PREFIX}bar_value_{key}", "", "white", self._overlay_x, self._overlay_y, ttl=1)

    def _overlay_clear_all_sync(self) -> None:
        """Synchronous clear for plugin_stop — EDMC doesn't wait around for
        a background thread to finish before the process exits, so shutdown
        cleanup sends directly rather than threading it."""
        try:
            for row in range(self._overlay_rendered_rows):
                self._overlay_client.send_message(
                    f"{ID_PREFIX}pillage_{row}", "", "white", self._overlay_x, self._overlay_y + row * LINE_HEIGHT, ttl=1,
                )
            for key in self._rendered_bar_keys:
                self._clear_bar_key(key)
        except OSError:
            logger.debug("Could not reach EDMCOverlay to clear on shutdown", exc_info=True)
        self._overlay_lines = []
        self._overlay_rendered_rows = 0
        self._rendered_bar_keys = frozenset()

    # --- main-panel widgets -------------------------------------------------

    def build_panel(self, parent: tk.Frame) -> None:
        parent.columnconfigure(0, weight=1)
        self._parent = parent

        self._status_label = panelkit.wrap_label(parent, text="Awaiting Odyssey loot…", anchor=tk.W)
        self._status_label.grid(row=0, column=0, sticky=tk.W)

        bars = tk.Frame(parent)
        bars.grid(row=1, column=0, sticky=tk.W, pady=(2, 2))
        self._bar_rows = {}
        for grid_row, key in enumerate(BAR_ORDER):
            row = tk.Frame(bars)
            row.grid(row=grid_row, column=0, sticky=tk.W, pady=1)

            name_label = tk.Label(
                row, text=BAR_DEFAULT_LABELS.get(key, ""), width=_BAR_NAME_WIDTH, anchor=tk.W, cursor="hand2",
            )
            name_label.pack(side=tk.LEFT)

            bar = tk.Canvas(row, width=_BAR_WIDTH, height=_BAR_HEIGHT, highlightthickness=0, borderwidth=0)
            bar.pack(side=tk.LEFT, padx=(4, 4))

            value_label = tk.Label(row, text="", width=_BAR_VALUE_WIDTH, anchor=tk.W, cursor="hand2")
            value_label.pack(side=tk.LEFT)

            for widget in (row, name_label, bar, value_label):
                widget.bind("<Button-1>", self._open_inventory)

            self._bar_rows[key] = {"row": row, "name": name_label, "bar": bar, "value": value_label}
            self._draw_bar(bar, 0, None, BAR_COLOURS.get(key, _BAR_DEFAULT_COLOUR))

        self._last_event_label = panelkit.wrap_label(parent, text="")
        self._last_event_label.grid(row=2, column=0, sticky=tk.W, pady=(2, 0))

        tk.Label(parent, text="Click Inventory Bar to Open Inventory Panel", anchor=tk.W).grid(
            row=3, column=0, sticky=tk.W, pady=(4, 0),
        )

        # theme.update() (called once, on the mode frame, from ui.py) only
        # recolors direct children - not enough for the bar rows' own
        # nested labels/canvases. Walk the whole subtree instead.
        panelkit.apply_theme_deep(parent)

        # Bars were first drawn above before theme.update() had a chance to
        # colour _status_label - _bar_track_color() reads that label's
        # *current* background, so redraw now that it actually reflects the
        # real theme, rather than leaving the initial paint stuck on the
        # pre-theme guess until the first journal event.
        for key, widgets in self._bar_rows.items():
            self._draw_bar(widgets["bar"], 0, None, BAR_COLOURS.get(key, _BAR_DEFAULT_COLOUR))

        # None of the above is guaranteed to land *after* EDMC has actually
        # applied its own theme (theme.current has been observed still
        # empty a full second after plugin_start3 on a real Dark-theme
        # install) - a bar drawn before that finishes is stuck showing the
        # wrong colour forever, since nothing else would prompt a redraw
        # until the next journal event. Retry a few times over the
        # following seconds so a slow theme-apply can't permanently strand
        # the bars on their pre-theme guess.
        for delay_ms in (500, 1500, 3000, 6000):
            parent.after(delay_ms, self._redraw_bars_only)

        self._refresh_bars({})

    def _open_inventory(self, _event=None) -> None:
        if self._parent is not None:
            from . import inventory_window
            inventory_window.show(self._parent, self._tracker, self._suit, self._cargo_snapshot)

    def _cargo_snapshot(self):
        """(label, total, capacity, {commodity: count}) for the inventory
        window's Cargo tab, from the latest EDMC state; None while on foot."""
        row = self._vehicle.cargo_bar(self._last_state)
        if row is None:
            return None
        label, total, capacity = row
        cargo = self._last_state.get("Cargo")
        items = {str(k): int(v) for k, v in cargo.items()} if isinstance(cargo, dict) else {}
        return label, total, capacity, items

    def _bar_track_color(self) -> str:
        """A shade one step off the panel's actual current background - so
        the track works correctly under Default, Dark, and Transparent
        alike without needing to detect *which* theme is active.

        Reads EDMC's own theme.current['background'] first - the exact
        value its theme.update()/_update_widget() assigns to every
        recoloured widget's background option - rather than inferring it
        by reading a widget back (a Frame's own background is never
        actually touched by theme.update(); a Label's depends on
        theme.apply() having already run against it by the moment we
        happen to read it, which in practice can still be stale under Dark
        theme). Falling back to a Label's background only if theme.current
        isn't populated yet."""
        base = None
        current_snapshot = None
        try:
            current_snapshot = dict(theme.current)
            base = theme.current.get("background")
        except AttributeError:
            base = None

        reference = self._status_label
        used_fallback_label = False
        if not base and reference is not None:
            used_fallback_label = True
            try:
                base = reference.cget("background")
            except tk.TclError:
                base = None

        resolver = reference or self._parent
        if not base or resolver is None:
            if self._theme_debug_log_count < _THEME_DEBUG_LOG_LIMIT:
                self._theme_debug_log_count += 1
                logger.info(
                    "Bar track colour diagnostic [%d/%d]: theme.current=%r, resolved base=%r, "
                    "used_fallback_label=%s, resolver=%r -> falling back to static light",
                    self._theme_debug_log_count, _THEME_DEBUG_LOG_LIMIT,
                    current_snapshot, base, used_fallback_label, resolver,
                )
            return _BAR_TRACK_LIGHT

        try:
            red16, green16, blue16 = resolver.winfo_rgb(base)
        except tk.TclError:
            return _BAR_TRACK_LIGHT

        red, green, blue = red16 // 256, green16 // 256, blue16 // 256
        luminance = 0.2126 * red + 0.7152 * green + 0.0722 * blue
        delta = 24 if luminance < 128 else -20

        def shift(value: int) -> int:
            return max(0, min(255, value + delta))

        result = f"#{shift(red):02x}{shift(green):02x}{shift(blue):02x}"

        if self._theme_debug_log_count < _THEME_DEBUG_LOG_LIMIT:
            self._theme_debug_log_count += 1
            logger.info(
                "Bar track colour diagnostic [%d/%d]: theme.current=%r, resolved base=%r, "
                "used_fallback_label=%s, luminance=%.1f -> track=%s",
                self._theme_debug_log_count, _THEME_DEBUG_LOG_LIMIT,
                current_snapshot, base, used_fallback_label, luminance, result,
            )

        return result

    def _draw_bar(self, canvas: tk.Canvas, total: int, capacity: Optional[int], colour: str) -> None:
        """(Re)draw one bar's track + fill rectangles, fully covering the
        canvas so nothing behind it is ever visible, regardless of the
        active theme. `colour` is this bar's own signature colour - drawn
        as the track's outline even at 0% so every bar reads as distinctly
        "its own colour" rather than a flat gray box, and as the fill
        colour once there's something to show (overridden to red once at
        capacity)."""
        canvas.delete("all")
        track = self._bar_track_color()
        canvas.configure(background=track)
        canvas.create_rectangle(0, 0, _BAR_WIDTH - 1, _BAR_HEIGHT - 1, fill=track, outline=colour)

        if not capacity:
            return

        fraction = max(0.0, min(1.0, total / capacity))
        if fraction <= 0:
            return

        fill_colour = _BAR_FULL_COLOUR if total >= capacity else colour
        canvas.create_rectangle(0, 0, max(1, round(_BAR_WIDTH * fraction)), _BAR_HEIGHT, fill=fill_colour, outline="")

    def _set_inventory_levels(self, rows: List[BarRow]) -> None:
        """Update the main-panel bars from (key, label, total, capacity)
        tuples. A key present in BAR_ORDER but absent from `rows` has its
        row hidden entirely rather than left stale or shown as an empty/
        zero reading."""
        self._last_rows = list(rows)
        self._apply_inventory_levels(rows)

    def _apply_inventory_levels(self, rows: List[BarRow]) -> None:
        if not self._bar_rows:
            return

        present = {key: (label, total, capacity) for key, label, total, capacity in rows}

        for key in BAR_ORDER:
            widgets = self._bar_rows.get(key)
            if widgets is None:
                continue

            row = widgets["row"]
            data = present.get(key)
            if data is None:
                row.grid_remove()
                continue

            label, total, capacity = data
            widgets["name"]["text"] = label
            widgets["value"]["text"] = f"{total}/{capacity}" if capacity else str(total)
            self._draw_bar(widgets["bar"], total, capacity, BAR_COLOURS.get(key, _BAR_DEFAULT_COLOUR))
            row.grid()

    def _redraw_bars_only(self) -> None:
        if self._parent is None or not self._parent.winfo_exists():
            return
        # Confirmed against EDMC's own theme.py: theme.update(widget) is a
        # documented no-op ("No need to call this for widgets created in
        # plugin_app()") whenever theme.current is still empty - it returns
        # *before* ever calling self.register(widget), so a widget built
        # while theme.current is empty (every widget built in build_panel(),
        # since EDMC always constructs every plugin's panel via
        # _config_plugins() before its own first theme.apply() call - see
        # EDMarketConnector.py) is never registered with EDMC's theme system
        # at all, and theme.apply()'s own later re-colour pass only touches
        # *registered* widgets. That silent non-registration - not a delay
        # in theme.current becoming populated - is the mechanism behind the
        # occasional-wrong-colour reports: apply_theme_deep()'s original
        # call in build_panel() ran too early to register anything, so nothing
        # ever re-themes these widgets afterward unless something calls
        # apply_theme_deep() again once theme.current is actually populated.
        # Re-running it here (same retry schedule that already existed for
        # the bar canvases) registers every widget in the panel for the
        # first time under a populated theme.current, fixing both this
        # method's own bar-track colour (whose fallback path reads
        # self._status_label's *applied* background) and every other label
        # in the panel that was silently never themed at all.
        panelkit.apply_theme_deep(self._parent)
        self._apply_inventory_levels(self._last_rows)

    # --- Settings tab --------------------------------------------------------

    def build_settings(self, notebook: nb.Notebook) -> None:
        frame = nb.Frame(notebook)
        frame.columnconfigure(0, weight=1)
        notebook.add(frame, text="Inventory")
        row = 0

        row = self._build_output_format(frame, start_row=row)
        row = self._build_sound_pref(frame, start_row=row)

        self._overlay_var = tk.BooleanVar(value=overlay_enabled())
        nb.Checkbutton(
            frame, text="Show pillage notifications on the in-game overlay", variable=self._overlay_var,
        ).grid(row=row, column=0, sticky=tk.W, padx=10, pady=(10, 0))
        row += 1

        nb.Label(frame, text="Connection settings are on the Overlay Connection tab.").grid(
            row=row, column=0, sticky=tk.W, padx=10, pady=(2, 10),
        )
        row += 1

        row = self._build_overlay_bars(frame, start_row=row)
        row = self._build_overlay_position(frame, start_row=row)
        row = self._build_announce_categories(frame, start_row=row)

        self._override_vars = {}
        self._override_defaults = {}
        self._build_capacity_overrides(frame, start_row=row)

    def _build_output_format(self, frame: nb.Frame, *, start_row: int) -> int:
        row = start_row
        nb.Label(frame, text="Pillage message:").grid(row=row, column=0, sticky=tk.W, padx=10, pady=(0, 2))
        row += 1

        self._message_format_var = tk.StringVar(value=message_format())
        nb.EntryMenu(frame, textvariable=self._message_format_var, width=55).grid(
            row=row, column=0, sticky=tk.W, padx=10,
        )
        row += 1

        nb.Label(
            frame,
            text="Placeholders: {item} (resource name), {total} (new combined total). Leave blank to reset to the default.",
            wraplength=440, justify=tk.LEFT,
        ).grid(row=row, column=0, sticky=tk.W, padx=10, pady=(2, 10))
        return row + 1

    def _build_sound_pref(self, frame: nb.Frame, *, start_row: int) -> int:
        row = start_row
        sound_available = self._sound.available
        self._sound_var = tk.BooleanVar(value=sound_enabled())
        nb.Checkbutton(
            frame, text="Play a sound on pickup", variable=self._sound_var,
            state=tk.NORMAL if sound_available else tk.DISABLED,
        ).grid(row=row, column=0, sticky=tk.W, padx=10, pady=(0, 0))
        row += 1

        note, supported = platform_support.sound_support_note()
        nb.Label(
            frame, text=note, wraplength=440, justify=tk.LEFT, foreground="#2e7d32" if supported else "#c07000",
        ).grid(row=row, column=0, sticky=tk.W, padx=10, pady=(2, 10))
        row += 1
        return row

    def _build_overlay_bars(self, frame: nb.Frame, *, start_row: int) -> int:
        row = start_row
        nb.Label(frame, text="Show these inventory bars on the overlay:").grid(
            row=row, column=0, sticky=tk.W, padx=10, pady=(0, 2),
        )
        row += 1

        enabled = overlay_enabled_bars()
        self._overlay_bar_vars = {}

        bars_row = tk.Frame(frame)
        bars_row.grid(row=row, column=0, sticky=tk.W, padx=10, pady=(0, 2))
        for key in BAR_ORDER:
            var = tk.BooleanVar(value=key in enabled)
            self._overlay_bar_vars[key] = var
            nb.Checkbutton(bars_row, text=BAR_DEFAULT_LABELS.get(key, key), variable=var).pack(
                side=tk.LEFT, padx=(0, 12),
            )
        row += 1

        nb.Label(
            frame,
            text=(
                "Each shown as its own small persistent bar below the pillage stack, "
                "colour-matched to the main panel. Carrier Locker and Cargo only draw "
                "when they'd also show on the main panel."
            ),
            wraplength=440, justify=tk.LEFT,
        ).grid(row=row, column=0, sticky=tk.W, padx=10, pady=(2, 10))
        return row + 1

    def _build_overlay_position(self, frame: nb.Frame, *, start_row: int) -> int:
        row = start_row
        x, y = overlay_position()
        self._overlay_x_var = tk.StringVar(value=str(x))
        self._overlay_y_var = tk.StringVar(value=str(y))

        position = tk.Frame(frame)
        position.grid(row=row, column=0, sticky=tk.W, padx=10, pady=(0, 2))
        nb.Label(position, text="Overlay position — X:").pack(side=tk.LEFT)
        nb.EntryMenu(position, textvariable=self._overlay_x_var, width=6).pack(side=tk.LEFT, padx=(4, 10))
        nb.Label(position, text="Y:").pack(side=tk.LEFT)
        nb.EntryMenu(position, textvariable=self._overlay_y_var, width=6).pack(side=tk.LEFT, padx=(4, 0))
        row += 1

        nb.Label(
            frame,
            text=f"On the legacy overlay's virtual screen (0-{MAX_ORIGIN_X} x 0-{MAX_ORIGIN_Y}). "
            f"Default {DEFAULT_ORIGIN_X}, {DEFAULT_ORIGIN_Y}.",
        ).grid(row=row, column=0, sticky=tk.W, padx=10, pady=(0, 10))
        return row + 1

    def _build_announce_categories(self, frame: nb.Frame, *, start_row: int) -> int:
        row = start_row
        nb.Label(frame, text="Announce pickups for:").grid(row=row, column=0, sticky=tk.W, padx=10, pady=(0, 2))
        row += 1

        enabled = announced_categories()
        self._announce_vars = {}

        categories_row = tk.Frame(frame)
        categories_row.grid(row=row, column=0, sticky=tk.W, padx=10, pady=(0, 10))
        for category in TRACKED_CATEGORIES:
            var = tk.BooleanVar(value=category in enabled)
            self._announce_vars[category] = var
            nb.Checkbutton(categories_row, text=CATEGORY_SHORT[category], variable=var).pack(side=tk.LEFT, padx=(0, 12))
        row += 1

        nb.Label(
            frame,
            text="Unchecked categories are still tracked and counted — only their log/overlay/panel pickup notification is muted.",
            wraplength=440, justify=tk.LEFT,
        ).grid(row=row, column=0, sticky=tk.W, padx=10, pady=(0, 10))
        return row + 1

    def _build_capacity_overrides(self, frame: nb.Frame, *, start_row: int) -> int:
        """Per-loadout backpack capacity override section. Each row is a
        suit loadout the commander has been seen wearing. Fields are pre-
        filled with the unengineered default for that suit; update a field
        only if that specific loadout is engineered (or otherwise holds a
        different amount than the default). Saving a value that matches
        the default is treated the same as leaving it alone — it does not
        fossilize into a stored override."""
        row = start_row
        nb.Label(frame, text="Suit Backpack Capacity").grid(row=row, column=0, sticky=tk.W, padx=10, pady=(14, 2))
        row += 1

        cmdr = self._tracker.commander or ""
        loadouts = suit.known_loadouts_for(cmdr) if cmdr else {}

        if not loadouts:
            nb.Label(
                frame,
                text="No suits recorded yet for this commander — wear a suit in-game, then reopen Settings.",
            ).grid(row=row, column=0, sticky=tk.W, padx=10, pady=(0, 10))
            return row + 1

        nb.Label(
            frame,
            text=(
                "Pre-filled with the unengineered default. If a suit is engineered — or otherwise "
                "holds a different amount — update the number to what you observe in-game."
            ),
            wraplength=440, justify=tk.LEFT,
        ).grid(row=row, column=0, columnspan=2, sticky=tk.W, padx=10, pady=(0, 6))
        row += 1

        for loadout_id, record in sorted(loadouts.items(), key=lambda kv: kv[1].get("name") or kv[0]):
            row = self._add_loadout_row(frame, row, loadout_id, record)

        return row

    def _add_loadout_row(self, frame: nb.Frame, row: int, loadout_id: str, record: dict) -> int:
        suit_key = record.get("suit_key", "")
        suit_name = suit.SUIT_DISPLAY_NAMES.get(suit_key, suit_key or "Unknown suit")
        loadout_name = record.get("name") or ""
        label = f'{suit_name} — "{loadout_name}"' if loadout_name else suit_name

        nb.Label(frame, text=label).grid(row=row, column=0, columnspan=2, sticky=tk.W, padx=10, pady=(6, 0))
        row += 1

        defaults = suit.default_capacity(suit_key, bool(record.get("has_capacity_mod")))
        overrides = record.get("overrides", {})

        fields = tk.Frame(frame)
        fields.grid(row=row, column=0, columnspan=2, sticky=tk.W, padx=20, pady=(0, 6))

        for col, category in enumerate(TRACKED_CATEGORIES):
            nb.Label(fields, text=f"{CATEGORY_SHORT[category]}:").grid(
                row=0, column=col * 3, sticky=tk.W, padx=(0 if col == 0 else 12, 4),
            )

            default_value = defaults.get(category)
            if category in overrides:
                initial = str(overrides[category])
            elif default_value is not None:
                initial = str(default_value)
            else:
                initial = ""

            var = tk.StringVar(value=initial)
            self._override_vars[(loadout_id, category)] = var
            self._override_defaults[(loadout_id, category)] = default_value
            nb.EntryMenu(fields, textvariable=var, width=6).grid(row=0, column=col * 3 + 1, sticky=tk.W)

            if default_value is None:
                nb.Label(fields, text="(no default — enter observed value)").grid(
                    row=0, column=col * 3 + 2, sticky=tk.W, padx=(4, 0),
                )

        return row + 1

    def save_settings(self) -> None:
        if self._overlay_var is None:
            return

        cmdr = self._tracker.commander or ""

        config.set(_CFG_OVERLAY_ENABLED, self._overlay_var.get())
        if self._sound_var is not None:
            config.set(_CFG_SOUND_ENABLED, self._sound_var.get())
        if self._message_format_var is not None:
            config.set(_CFG_MESSAGE_FORMAT, self._message_format_var.get().strip())
        for key, var in self._overlay_bar_vars.items():
            config.set(f"{_CFG_OVERLAY_BAR_PREFIX}{key}", var.get())

        self._save_overlay_position()
        self._save_announce_categories()

        for (loadout_id, category), var in self._override_vars.items():
            text = var.get().strip()
            if not text:
                suit.set_override(cmdr, loadout_id, category, None)
                continue
            try:
                value = int(text)
            except ValueError:
                continue
            if value <= 0:
                continue
            default_value = self._override_defaults.get((loadout_id, category))
            if value == default_value:
                suit.set_override(cmdr, loadout_id, category, None)
            else:
                suit.set_override(cmdr, loadout_id, category, value)

        suit.save_overrides()

        self._sound.set_enabled(sound_enabled())
        self._overlay_x, self._overlay_y = overlay_position()
        self._refresh_bars(self._last_state)

    def _save_overlay_position(self) -> None:
        if self._overlay_x_var is None or self._overlay_y_var is None:
            return
        try:
            x = int(self._overlay_x_var.get().strip())
            y = int(self._overlay_y_var.get().strip())
        except ValueError:
            return
        config.set(_CFG_OVERLAY_X, max(0, min(MAX_ORIGIN_X, x)))
        config.set(_CFG_OVERLAY_Y, max(0, min(MAX_ORIGIN_Y, y)))

    def _save_announce_categories(self) -> None:
        if not self._announce_vars:
            return
        selected = [category for category, var in self._announce_vars.items() if var.get()]
        config.set(_CFG_ANNOUNCE_CATEGORIES, json.dumps(selected))


controller = InventoryPanelController()


def set_overlay_client(client: overlay.OverlayClient) -> None:
    controller.set_overlay_client(client)


def start(plugin_dir: str) -> None:
    controller.start(plugin_dir)


def stop() -> None:
    controller.stop()


def handle_event(entry: Dict[str, Any], cmdr: str, system: Optional[str], station: Optional[str], state: Dict[str, Any]) -> None:
    controller.handle_event(entry, cmdr, system, station, state)


def capi_fleetcarrier(data: Any) -> None:
    controller.capi_fleetcarrier(data)


def build_panel(parent: tk.Frame) -> None:
    controller.build_panel(parent)


def build_settings(notebook: nb.Notebook) -> None:
    controller.build_settings(notebook)


def save_settings() -> None:
    controller.save_settings()
