"""Global overlay placement for WNTB: one place to say where every overlay display goes, the same on any screen.

`overlay_layout.py` holds the model (anchors, the visible part of the overlay's canvas, shifting a display). This module
joins it to the real world:

- **The screen.** The shape of the game's picture comes from Elite's own `Options/Graphics/DisplaySettings.xml`
  (`ScreenWidth` / `ScreenHeight`, found on Windows and inside a Wine/Proton prefix on Linux), and whether the overlay
  fits or fills it from EDMCModernOverlay's `overlay_settings.json` (`scale_mode`) sitting next to WNTB in EDMC's plugins
  folder. Either can be overridden in Settings, and when neither can be found the assumption is a 16:9 screen in fill
  mode, the smallest area, so nothing is ever placed out of sight.
- **The displays.** `SLOTS` lists every display that can be placed, with its default spot. Each display asks
  `client_for` (or `origin_for`) for where it goes right now.
- **The Settings tab** ("Overlay Placement"): one row per display, a menu of nine spots, two offsets, and a button that
  draws a labeled box for every display so a position can be judged on the real screen.

Old per-feature x/y settings are read once, so a position somebody set by hand is kept as an exact position.
"""

from __future__ import annotations

import json
import logging
import os
import threading
import time
import tkinter as tk
from typing import Any, Dict, List, Optional, Tuple

import myNotebook as nb
from config import appname, config

from . import overlay, overlay_layout as layout, platform_support

plugin_name = os.path.basename(os.path.dirname(__file__))
logger = logging.getLogger(f"{appname}.{plugin_name}")

CFG_ASPECT = "wntb_overlay_aspect"        # "auto" or one of layout.ASPECT_CHOICES such as "16:9"
CFG_MODE = "wntb_overlay_scale_mode"      # "auto", "fit" or "fill"
AUTO = "auto"

DISPLAY_SETTINGS_FILE = "DisplaySettings.xml"
MODERN_OVERLAY_FOLDER = "EDMCModernOverlay"
MODERN_OVERLAY_SETTINGS = "overlay_settings.json"
ASSUMED_SCREEN = (1920, 1080)             # used only when the game's files cannot be read

SCREEN_CACHE_S = 30.0                     # the game's files are not re-read more often than this
PREVIEW_SECONDS = 12


# --- the displays that can be placed -------------------------------------------------------------------------------

def _slot(key: str, label: str, h: str, v: str, dx: int, dy: int, size: Tuple[int, int],
          legacy_x: str = "", legacy_y: str = "", legacy_default: Tuple[int, int] = (0, 0)) -> layout.Slot:
    return layout.Slot(key, label, layout.Placement(h, v, dx, dy), size, legacy_x, legacy_y, legacy_default)


# Defaults put each display where it used to sit on a 4:3 canvas, as an anchor so it also suits wide screens. Sizes are
# the block each display occupies (used to preview it and to anchor it to a right or bottom edge).
SLOTS: Dict[str, layout.Slot] = {s.key: s for s in (
    _slot("colonisation", "Colonization shopping list", "left", "middle", 20, 0, (360, 300),
          "wntb_colonisation_overlay_x", "wntb_colonisation_overlay_y", (20, 300)),
    _slot("discovery", "Discovery alerts", "center", "top", 0, 44, (460, 234),
          "wntb_discovery_x", "wntb_discovery_y", (700, 60)),
    _slot("notable", "Notable find card", "center", "top", 0, 300, (460, 84),
          "wntb_notable_x", "wntb_notable_y", (700, 560)),
    _slot("interdiction", "Interdiction warning", "center", "top", 0, 74, (600, 116)),
    _slot("landing", "Landing assist", "left", "bottom", 20, 0, (320, 324)),
    _slot("inventory", "Inventory pickups and bars", "right", "top", 20, 120, (420, 226),
          "wntb_inventory_overlay_x", "wntb_inventory_overlay_y", (900, 120)),
    _slot("mining_stats", "Mining stats", "left", "top", 10, 92, (400, 100)),
    _slot("mining_waypoint", "Mining waypoint", "left", "top", 10, 242, (400, 70)),
    _slot("screenshots", "Screenshot messages", "right", "bottom", 20, 20, (420, 78)),
)}


# --- the screen ----------------------------------------------------------------------------------------------------

_screen_cache: Dict[str, Any] = {"at": 0.0, "screen": None}


def _plugins_dir() -> str:
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def read_display_settings() -> Optional[Tuple[int, int, Optional[int]]]:
    """The game's screen size and mode from DisplaySettings.xml, or None when the file can't be found or read."""
    folder = platform_support.elite_graphics_dir(platform_support.get_prefix_override() or None)
    if not folder:
        return None
    try:
        with open(os.path.join(folder, DISPLAY_SETTINGS_FILE), "r", encoding="utf-8") as handle:
            return layout.parse_display_settings(handle.read())
    except OSError:
        return None


def detect_scale_mode() -> Tuple[str, str]:
    """(mode, where it came from): EDMCModernOverlay's own scale mode when its settings file is there, otherwise fill."""
    path = os.path.join(_plugins_dir(), MODERN_OVERLAY_FOLDER, MODERN_OVERLAY_SETTINGS)
    try:
        with open(path, "r", encoding="utf-8") as handle:
            mode = str(json.load(handle).get("scale_mode", "")).strip().lower()
        if mode in (layout.MODE_FIT, layout.MODE_FILL):
            return mode, "EDMCModernOverlay settings"
    except (OSError, ValueError, AttributeError):
        pass
    return layout.MODE_FILL, "assumed"


def screen_for(aspect_choice: str, mode_choice: str) -> layout.Screen:
    """The screen for the given Settings choices ("auto" reads the game's and the overlay's own files)."""
    mode, mode_source = (mode_choice, "chosen") if mode_choice in (layout.MODE_FIT, layout.MODE_FILL) else detect_scale_mode()
    for label, aspect_w, aspect_h in layout.ASPECT_CHOICES:
        if aspect_choice == label:
            return layout.screen_from_aspect(aspect_w, aspect_h, mode, f"{label} chosen, mode {mode_source}")
    found = read_display_settings()
    if found:
        width, height, full_screen = found
        return layout.Screen(width, height, mode, f"{DISPLAY_SETTINGS_FILE}, mode {mode_source}", full_screen)
    return layout.Screen(*ASSUMED_SCREEN, mode, "game files not found, assuming 16:9")


def current_screen() -> layout.Screen:
    """The screen as configured now, re-read from the game's files at most every SCREEN_CACHE_S seconds."""
    now = time.monotonic()
    cached = _screen_cache["screen"]
    if cached is None or now - _screen_cache["at"] > SCREEN_CACHE_S:
        cached = screen_for(config.get_str(CFG_ASPECT) or AUTO, config.get_str(CFG_MODE) or AUTO)
        _screen_cache.update(at=now, screen=cached)
    return cached


def refresh() -> None:
    """Forget the cached screen so the next placement re-reads the files (after Settings change)."""
    _screen_cache.update(at=0.0, screen=None)


# --- saved placements ----------------------------------------------------------------------------------------------

def _legacy_int(key: str) -> Optional[int]:
    if not key:
        return None
    try:
        raw = config.get_str(key)
        return int(raw) if raw else None
    except (TypeError, ValueError):
        return None


def placement_for(slot_key: str) -> layout.Placement:
    """Where `slot_key`'s display goes: its saved placement, else the old x/y it used to have, else its default."""
    slot = SLOTS[slot_key]
    default = layout.migrated_placement(slot, _legacy_int(slot.legacy_x), _legacy_int(slot.legacy_y))
    raw = config.get_str(layout.setting_key(slot_key))
    return layout.parse_placement(raw, default) if raw else default


def save_placement(slot_key: str, placement: layout.Placement) -> None:
    config.set(layout.setting_key(slot_key), layout.format_placement(placement))


def shift_for(slot_key: str, block: Tuple[int, int, int, int]) -> Tuple[int, int]:
    """How far to move a display drawn in the rectangle `block` = (left, top, width, height) to reach its place."""
    return layout.shift_for(placement_for(slot_key), block, current_screen())


def client_for(slot_key: str, client: Any, block: Tuple[int, int, int, int]) -> Any:
    """`client` wrapped so everything drawn through it lands where `slot_key` is placed. A failure to work out the
    placement (damaged settings, say) leaves the display where it was drawn rather than hiding it."""
    try:
        dx, dy = shift_for(slot_key, block)
    except Exception:
        logger.exception("Overlay placement for %s failed; drawing it where it is", slot_key)
        return client
    return client if (dx, dy) == (0, 0) else layout.ShiftedClient(client, dx, dy)


def origin_for(slot_key: str, size: Tuple[int, int]) -> Tuple[int, int]:
    """Top left corner for a display of `size` that positions itself from an origin rather than being shifted."""
    return layout.block_origin(placement_for(slot_key), size, current_screen())


# --- Settings tab --------------------------------------------------------------------------------------------------

_ASPECT_AUTO_LABEL = "Automatic (from the game's files)"
_MODE_AUTO_LABEL = "Automatic (from the overlay's settings)"
_MODE_LABELS = {layout.MODE_FIT: "Fit (whole canvas shown)", layout.MODE_FILL: "Fill (screen covered, edges cut off)"}
_PREVIEW_COLORS = ("#f97316", "#22d3ee", "#a3e635", "#f472b6", "#facc15", "#60a5fa", "#fb7185", "#34d399", "#c084fc")

_rows: Dict[str, Tuple[tk.StringVar, tk.StringVar, tk.StringVar]] = {}
_aspect_var: Optional[tk.StringVar] = None
_mode_var: Optional[tk.StringVar] = None
_info_var: Optional[tk.StringVar] = None
_result_var: Optional[tk.StringVar] = None
_frame: Optional[tk.Misc] = None


def _aspect_value(label: str) -> str:
    return AUTO if label == _ASPECT_AUTO_LABEL else label


def _mode_value(label: str) -> str:
    for value, text in _MODE_LABELS.items():
        if label == text:
            return value
    return AUTO


def _number(var: tk.StringVar, default: int = 0) -> int:
    try:
        return int(var.get().strip())
    except ValueError:
        return default


def _typed_placement(slot_key: str) -> layout.Placement:
    """The placement as currently typed into a row (not yet saved)."""
    choice, first, second = _rows[slot_key]
    return layout.placement_from_choice(choice.get(), _number(first), _number(second))


def _typed_screen() -> layout.Screen:
    if _aspect_var is None or _mode_var is None:
        return current_screen()
    return screen_for(_aspect_value(_aspect_var.get()), _mode_value(_mode_var.get()))


def _show_info() -> None:
    if _info_var is not None:
        _info_var.set(layout.describe_screen(_typed_screen()))


def build_settings(notebook: tk.Misc) -> None:
    global _aspect_var, _mode_var, _info_var, _result_var, _frame

    frame = nb.Frame(notebook)
    _frame = frame
    frame.columnconfigure(0, weight=1)
    notebook.add(frame, text="Overlay Placement")

    nb.Label(
        frame,
        text=("Where each on-screen display goes, for every overlay feature in WNTB. Pick one of nine spots and an "
              "offset: the spot is measured on the part of the overlay you can actually see, so \"Bottom right\" is the "
              "bottom right corner on any monitor shape. For the edge spots the offset moves the display inward from "
              "the edge; for Center and Middle it nudges it. \"Exact position\" uses the two numbers as the overlay's "
              "own x and y (a 1280 x 960 canvas) instead."),
        wraplength=460, justify=tk.LEFT,
    ).grid(row=0, column=0, sticky=tk.W, padx=10, pady=(10, 6))

    _info_var = tk.StringVar(value="")
    nb.Label(frame, textvariable=_info_var, wraplength=460, justify=tk.LEFT).grid(
        row=1, column=0, sticky=tk.W, padx=10, pady=(0, 6))

    screen_box = tk.Frame(frame)
    screen_box.grid(row=2, column=0, sticky=tk.W, padx=10, pady=2)
    nb.Label(screen_box, text="Screen shape:").grid(row=0, column=0, sticky=tk.W)
    saved_aspect = config.get_str(CFG_ASPECT) or AUTO
    _aspect_var = tk.StringVar(value=saved_aspect if saved_aspect in [a[0] for a in layout.ASPECT_CHOICES] else _ASPECT_AUTO_LABEL)
    tk.OptionMenu(screen_box, _aspect_var, _ASPECT_AUTO_LABEL, *[a[0] for a in layout.ASPECT_CHOICES],
                  command=lambda _v: _show_info()).grid(row=0, column=1, sticky=tk.W, padx=(6, 0))
    nb.Label(screen_box, text="Overlay mode:").grid(row=1, column=0, sticky=tk.W)
    saved_mode = config.get_str(CFG_MODE) or AUTO
    _mode_var = tk.StringVar(value=_MODE_LABELS.get(saved_mode, _MODE_AUTO_LABEL))
    tk.OptionMenu(screen_box, _mode_var, _MODE_AUTO_LABEL, *_MODE_LABELS.values(),
                  command=lambda _v: _show_info()).grid(row=1, column=1, sticky=tk.W, padx=(6, 0))

    grid = tk.Frame(frame)
    grid.grid(row=3, column=0, sticky=tk.W, padx=10, pady=(10, 4))
    for column, heading in enumerate(("Display", "Spot", "Offset X", "Offset Y")):
        nb.Label(grid, text=heading).grid(row=0, column=column, sticky=tk.W, padx=(0, 8))
    _rows.clear()
    for row_index, (key, slot) in enumerate(SLOTS.items(), start=1):
        placement = placement_for(key)
        first, second = (placement.x, placement.y) if placement.custom else (placement.dx, placement.dy)
        choice, first_var, second_var = (
            tk.StringVar(value=layout.preset_label(placement)), tk.StringVar(value=str(first)), tk.StringVar(value=str(second)))
        _rows[key] = (choice, first_var, second_var)
        nb.Label(grid, text=slot.label).grid(row=row_index, column=0, sticky=tk.W, padx=(0, 8), pady=1)
        tk.OptionMenu(grid, choice, *layout.PRESET_LABELS).grid(row=row_index, column=1, sticky=tk.W, padx=(0, 8), pady=1)
        nb.EntryMenu(grid, textvariable=first_var, width=6).grid(row=row_index, column=2, sticky=tk.W, padx=(0, 8), pady=1)
        nb.EntryMenu(grid, textvariable=second_var, width=6).grid(row=row_index, column=3, sticky=tk.W, pady=1)

    buttons = tk.Frame(frame)
    buttons.grid(row=4, column=0, sticky=tk.W, padx=10, pady=(8, 2))
    tk.Button(buttons, text="Show placement preview", command=_preview).pack(side=tk.LEFT)
    tk.Button(buttons, text="Reset all to defaults", command=_reset_all).pack(side=tk.LEFT, padx=(8, 0))
    tk.Button(buttons, text="Detect screen again", command=_redetect).pack(side=tk.LEFT, padx=(8, 0))
    _result_var = tk.StringVar(value="")
    nb.Label(frame, textvariable=_result_var, wraplength=460, justify=tk.LEFT).grid(
        row=5, column=0, sticky=tk.W, padx=10, pady=(2, 10))
    _show_info()


def save_settings() -> None:
    if _aspect_var is None or _mode_var is None or not _rows:
        return
    config.set(CFG_ASPECT, _aspect_value(_aspect_var.get()))
    config.set(CFG_MODE, _mode_value(_mode_var.get()))
    for key in SLOTS:
        if key in _rows:
            save_placement(key, _typed_placement(key))
    refresh()


def _redetect() -> None:
    refresh()
    _show_info()
    if _result_var is not None:
        _result_var.set("Read the game's files again.")


def _reset_all() -> None:
    """Puts every row back to its default (shown now; kept when Settings is saved)."""
    for key, slot in SLOTS.items():
        if key not in _rows:
            continue
        choice, first, second = _rows[key]
        default = slot.default
        choice.set(layout.preset_label(default))
        first.set(str(default.dx))
        second.set(str(default.dy))
    if _aspect_var is not None:
        _aspect_var.set(_ASPECT_AUTO_LABEL)
    if _mode_var is not None:
        _mode_var.set(_MODE_AUTO_LABEL)
    _show_info()
    if _result_var is not None:
        _result_var.set("Defaults are shown. Press OK in Settings to keep them.")


def preview_shapes(placements: Dict[str, layout.Placement], screen: layout.Screen) -> List[Dict[str, Any]]:
    """What the preview draws: the visible area's edge, then a labeled box for each display at its placed position.
    Plain data so it can be tested without an overlay."""
    area_w, area_h = screen.visible
    items: List[Dict[str, Any]] = [{"id": "wntb_placeprev_edge", "x": 0, "y": 0, "w": area_w, "h": area_h,
                                    "label": f"Visible area {area_w} x {area_h}", "color": "#ffffff"}]
    for index, (key, placement) in enumerate(placements.items()):
        slot = SLOTS[key]
        x, y = layout.block_origin(placement, slot.size, screen)
        items.append({"id": f"wntb_placeprev_{key}", "x": x, "y": y, "w": slot.size[0], "h": slot.size[1],
                      "label": slot.label, "color": _PREVIEW_COLORS[index % len(_PREVIEW_COLORS)]})
    return items


def _preview() -> None:
    """Draws a labeled outline for every display at the positions typed now, for a few seconds."""
    if _result_var is None:
        return
    try:
        items = preview_shapes({key: _typed_placement(key) for key in SLOTS if key in _rows}, _typed_screen())
    except ValueError:
        _result_var.set("One of the offsets is not a number.")
        return
    _result_var.set("Drawing the preview...")

    def worker() -> None:
        try:
            client = overlay.OverlayClient(overlay.load_config())
            for item in items:
                client.send_shape(item["id"], "rect", item["color"], "#33000000", item["x"], item["y"], item["w"], item["h"],
                                  ttl=PREVIEW_SECONDS, thickness=2)
                client.send_message(f"{item['id']}_label", item["label"], item["color"], item["x"] + 8, item["y"] + 6,
                                    ttl=PREVIEW_SECONDS)
            message = f"Preview drawn for {PREVIEW_SECONDS} seconds."
        except OSError as exc:
            message = f"Could not reach the overlay: {exc}"
        try:
            if _frame is not None:
                _frame.after(0, lambda: _result_var.set(message) if _result_var is not None else None)
        except (tk.TclError, RuntimeError):
            pass   # the Settings window was closed while drawing

    threading.Thread(target=worker, name="WNTB-overlay-placement-preview", daemon=True).start()
