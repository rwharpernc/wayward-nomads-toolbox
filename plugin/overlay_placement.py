"""Global overlay placement for WNTB: one place to say where every overlay display goes, the same on any screen.

`overlay_layout.py` holds the model (anchors, converting a display's pixel size to canvas units, shifting a display). This
module joins it to the real world:

- **The screen.** The overlay window's size, mode and the operating system's display scaling decide how big a pixel is on the
  overlay's canvas. They are read from, in order: EDMCModernOverlay's own log (its newest "Overlay scaling updated" line is
  exactly what it is using, display scaling included), then Elite's `Options/Graphics/DisplaySettings.xml` for the size
  (found on Windows and inside a Wine/Proton prefix on Linux) with Windows' own display scaling and EDMCModernOverlay's
  `overlay_settings.json` for the mode. The mode and the scaling can be overridden in Settings.
- **The displays.** `SLOTS` lists every display that can be placed, with its default spot. Each display asks `client_for`
  (or `origin_for`) for where it goes right now.
- **The Settings tab** ("Overlay Placement"): one row per display, a menu of nine spots, two offsets in screen pixels, and a
  button that draws a labeled box for every display so a position can be judged on the real screen.

Old per-feature x/y settings are read once, so a position somebody set by hand is kept as an exact position.
"""

from __future__ import annotations

import json
import logging
import os
import sys
import threading
import time
import tkinter as tk
from typing import Any, Dict, List, Optional, Tuple

import myNotebook as nb
from config import appname, config

from . import overlay, overlay_appearance, overlay_layout as layout, overlay_style, platform_support

plugin_name = os.path.basename(os.path.dirname(__file__))
logger = logging.getLogger(f"{appname}.{plugin_name}")

CFG_SCALING = "wntb_overlay_display_scaling"   # "auto" or one of layout.SCALING_CHOICES such as "125%"
CFG_MODE = "wntb_overlay_scale_mode"           # "auto", "fit" or "fill"
CFG_OFFSETS = "wntb_overlay_group_offsets"     # whether right-hand displays are carried past the overlay's clamp (default on)
AUTO = "auto"

DISPLAY_SETTINGS_FILE = "DisplaySettings.xml"
MODERN_OVERLAY_FOLDER = "EDMCModernOverlay"
MODERN_OVERLAY_SETTINGS = "overlay_settings.json"
MODERN_OVERLAY_LOG = os.path.join("logs", MODERN_OVERLAY_FOLDER, "overlay_client.log")
LOG_TAIL_BYTES = 400_000                      # the newest scaling line is near the end of the overlay's log
ASSUMED_SCREEN = (1920, 1080)                 # used only when nothing can be read

SCREEN_CACHE_S = 30.0                         # the files are not re-read more often than this
PREVIEW_SECONDS = 12


# --- the displays that can be placed -------------------------------------------------------------------------------

def _slot(key: str, label: str, h: str, v: str, dx: int, dy: int, size: Tuple[int, int],
          legacy_x: str = "", legacy_y: str = "", legacy_default: Tuple[int, int] = (0, 0),
          group: str = "", group_prefix: str = "") -> layout.Slot:
    return layout.Slot(key, label, layout.Placement(h, v, dx, dy), size, legacy_x, legacy_y, legacy_default, group, group_prefix)


# Sizes are the block each display occupies, in the pixels the display is drawn in (used to preview it and to anchor it to
# a right or bottom edge). Offsets are screen pixels in from the edge.
SLOTS: Dict[str, layout.Slot] = {s.key: s for s in (
    _slot("colonisation", "Colonization shopping list", "left", "middle", 40, 0, (360, 300),
          "wntb_colonisation_overlay_x", "wntb_colonisation_overlay_y", (20, 300), "wntb_colonisation", "wntb_colonisation_"),
    _slot("discovery", "Discovery alerts", "center", "top", 0, 100, (460, 234),
          "wntb_discovery_x", "wntb_discovery_y", (700, 60), "wntb_discovery", "wntb_discovery_"),
    _slot("notable", "Notable find card", "center", "top", 0, 360, (460, 84),
          "wntb_notable_x", "wntb_notable_y", (700, 560), "wntb_notable", "wntb_notable_"),
    _slot("interdiction", "Interdiction warning", "center", "top", 0, 120, (600, 116),
          group="wntb_interdiction", group_prefix="wntb_interdiction_"),
    _slot("landing", "Landing assist", "left", "bottom", 40, 40, (466, 324),
          group="wntb_landing", group_prefix="wntb_landing_"),
    _slot("inventory", "Inventory pickups and bars", "right", "top", 40, 200, (420, 226),
          "wntb_inventory_overlay_x", "wntb_inventory_overlay_y", (900, 120), "wntb_inventory", "wntb_inventory_"),
    _slot("mining_stats", "Mining stats", "left", "top", 40, 160, (400, 100)),
    _slot("mining_waypoint", "Mining waypoint", "left", "top", 40, 340, (400, 70)),
    _slot("screenshots", "Screenshot messages", "right", "bottom", 40, 40, (420, 78),
          group="wntb_screenshot", group_prefix="wntb_screenshot_"),
)}


def slot_size(slot_key: str, look: Optional[overlay_style.Look] = None) -> Tuple[int, int]:
    """A display's nominal size at the current look: the slot's size at the default text size, scaled to the chosen text size (its
    width by the estimated character width, its height by the line height) and grown by the padding on every side. It is what
    right- and bottom-anchoring, centering and the overlay group offsets are worked out from, so they stay right when the text
    size or padding changes."""
    look = look or overlay_appearance.current_look()
    width, height = SLOTS[slot_key].size
    char_ratio = look.char_px("normal") / overlay_style.LEGACY.char_px("normal")
    line_ratio = look.line_px("normal") / overlay_style.LEGACY.line_px("normal")
    return int(round(width * char_ratio + 2 * look.pad_extra)), int(round(height * line_ratio + 2 * look.pad_extra))


# --- the screen ----------------------------------------------------------------------------------------------------

_screen_cache: Dict[str, Any] = {"at": 0.0, "screen": None}


def _plugins_dir() -> str:
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _modern_overlay_installed() -> bool:
    return os.path.isdir(os.path.join(_plugins_dir(), MODERN_OVERLAY_FOLDER))


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


def _file_time(path: Optional[str]) -> float:
    try:
        return os.path.getmtime(path) if path else 0.0
    except OSError:
        return 0.0


def read_overlay_scaling() -> Optional[Tuple[int, int, str, float, float]]:
    """(window width, window height, mode, display scaling, log file time) from the newest scaling line in
    EDMCModernOverlay's log, or None when it has none (the overlay never ran, or its log is somewhere else)."""
    path = os.path.join(os.path.dirname(_plugins_dir()), MODERN_OVERLAY_LOG)   # EDMC's data folder holds plugins/ and logs/
    try:
        with open(path, "rb") as handle:
            handle.seek(0, os.SEEK_END)
            handle.seek(max(0, handle.tell() - LOG_TAIL_BYTES))
            tail = handle.read().decode("utf-8", errors="replace")
    except OSError:
        return None
    parsed = layout.parse_scaling_line(tail)
    return (*parsed, _file_time(path)) if parsed else None


def windows_display_scaling() -> Optional[float]:
    """The primary display's scaling on Windows (1.25 for 125%), or None elsewhere or when it can't be read."""
    if sys.platform != "win32":
        return None
    try:
        import ctypes
        percent = ctypes.windll.shcore.GetScaleFactorForDevice(0)   # 0 = the primary display; returns 100, 125, 150 ...
        return percent / 100.0 if percent and percent > 0 else None
    except Exception:
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


def _scaling_choice_value(label: str) -> Optional[float]:
    for text, ratio in layout.SCALING_CHOICES:
        if label == text:
            return ratio
    return None


def screen_for(scaling_choice: str, mode_choice: str) -> layout.Screen:
    """The screen for the given Settings choices ("auto" reads the overlay's log and the game's files)."""
    chosen_ratio = _scaling_choice_value(scaling_choice)
    chosen_mode = mode_choice if mode_choice in (layout.MODE_FIT, layout.MODE_FILL) else None
    modern = _modern_overlay_installed()
    display = read_display_settings()
    display_time = _file_time(os.path.join(
        platform_support.elite_graphics_dir(platform_support.get_prefix_override() or None) or "", DISPLAY_SETTINGS_FILE))

    logged = read_overlay_scaling() if modern else None
    if logged and display and logged[4] < display_time:
        logged = None          # the game's screen settings changed after the overlay last logged: its numbers are old

    if logged:
        width, height, log_mode, log_ratio, _time = logged
        mode = chosen_mode or log_mode
        ratio = chosen_ratio or log_ratio
        source = f"{MODERN_OVERLAY_FOLDER} log" + (", scaling chosen" if chosen_ratio else "") + (", mode chosen" if chosen_mode else "")
        return layout.Screen(width, height, mode, source, display[2] if display else None, ratio, True)

    if display:
        width, height, full_screen = display
        mode, mode_source = (chosen_mode, "chosen") if chosen_mode else detect_scale_mode()
        detected = windows_display_scaling()
        ratio = chosen_ratio or detected or 1.0
        scaling_source = "chosen" if chosen_ratio else "Windows" if detected else "assumed 100%"
        return layout.Screen(width, height, mode, f"{DISPLAY_SETTINGS_FILE}, mode {mode_source}, scaling {scaling_source}",
                             full_screen, ratio, modern)

    mode, _source = (chosen_mode, "chosen") if chosen_mode else detect_scale_mode()
    return layout.Screen(*ASSUMED_SCREEN, mode, "game files not found, assuming 1920 x 1080", None, chosen_ratio or 1.0, modern)


def current_screen() -> layout.Screen:
    """The screen as configured now, re-read from the files at most every SCREEN_CACHE_S seconds. If it changed (a new
    resolution, say) the group offsets are worked out again, since they depend on it."""
    now = time.monotonic()
    cached = _screen_cache["screen"]
    if cached is None or now - _screen_cache["at"] > SCREEN_CACHE_S:
        fresh = screen_for(config.get_str(CFG_SCALING) or AUTO, config.get_str(CFG_MODE) or AUTO)
        changed = cached is not None and fresh != cached
        cached = fresh
        _screen_cache.update(at=now, screen=cached)
        if changed:
            threading.Thread(target=apply_group_offsets, name="WNTB-overlay-offsets", daemon=True).start()
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


def offsets_enabled() -> bool:
    """The Settings switch for carrying displays past the overlay's right-hand clamp (on unless turned off)."""
    return config.get_str(CFG_OFFSETS) != "0"


def can_offset(slot_key: str) -> bool:
    """Whether a display can be carried past the overlay's right-hand clamp by an offset of its overlay group."""
    return bool(SLOTS[slot_key].group) and offsets_enabled() and overlay.group_offsets_available()


def shift_for(slot_key: str, block: Tuple[int, int, int, int]) -> Tuple[int, int]:
    """How far to move a display drawn in the rectangle `block` = (left, top, width, height) to reach its place. For a display
    with an overlay group this is only as far as the clamp allows; the group's offset (apply_group_offsets) does the rest."""
    return layout.shift_for(placement_for(slot_key), block, current_screen(), slot_size(slot_key), can_offset(slot_key))


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
    """Top left corner for a display of `size` that positions itself from an origin rather than being shifted (as far as the
    clamp allows, when its group's offset carries it the rest of the way)."""
    plan = layout.plan_origin(placement_for(slot_key), size, slot_size(slot_key) if SLOTS[slot_key].group else size,
                              current_screen(), can_offset(slot_key))
    return plan.x, plan.y


def group_offsets(placements: Optional[Dict[str, layout.Placement]] = None,
                  screen: Optional[layout.Screen] = None) -> Dict[str, float]:
    """The overlay group offset (canvas units to the right) each display needs for its placement, by group name. Only displays
    with a group are listed; most are 0."""
    screen = screen or current_screen()
    wanted = placements if placements is not None else {key: placement_for(key) for key in SLOTS}
    use = offsets_enabled() if placements is None else _offsets_typed()
    return {slot.group: (layout.plan_origin(wanted[key], slot_size(key), slot_size(key), screen, True).offset_x if use else 0.0)
            for key, slot in SLOTS.items() if slot.group and key in wanted}


def apply_group_offsets(placements: Optional[Dict[str, layout.Placement]] = None,
                        screen: Optional[layout.Screen] = None) -> bool:
    """Sends the group offsets for the saved placements (or the given ones) to EDMCModernOverlay. False when it can't be done,
    in which case displays simply stop where the overlay's clamp allows."""
    try:
        return overlay.set_group_offsets(group_offsets(placements, screen))
    except Exception:
        logger.exception("Could not apply the overlay group offsets")
        return False


# --- Settings tab --------------------------------------------------------------------------------------------------

_SCALING_AUTO_LABEL = "Automatic (from the overlay and Windows)"
_MODE_AUTO_LABEL = "Automatic (from the overlay's settings)"
_MODE_LABELS = {layout.MODE_FIT: "Fit (canvas keeps its shape)", layout.MODE_FILL: "Fill (canvas stretched over the screen)"}
_PREVIEW_COLORS = ("#f97316", "#22d3ee", "#a3e635", "#f472b6", "#facc15", "#60a5fa", "#fb7185", "#34d399", "#c084fc")

_rows: Dict[str, Tuple[tk.StringVar, tk.StringVar, tk.StringVar]] = {}
_scaling_var: Optional[tk.StringVar] = None
_mode_var: Optional[tk.StringVar] = None
_info_var: Optional[tk.StringVar] = None
_result_var: Optional[tk.StringVar] = None
_frame: Optional[tk.Misc] = None
_offsets_var: Optional[tk.BooleanVar] = None


def _offsets_typed() -> bool:
    """The offsets switch as currently ticked on the tab (not yet saved), or the saved one when the tab isn't built."""
    return bool(_offsets_var.get()) if _offsets_var is not None else offsets_enabled()


def _scaling_value(label: str) -> str:
    return AUTO if label == _SCALING_AUTO_LABEL else label


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
    if _scaling_var is None or _mode_var is None:
        return current_screen()
    return screen_for(_scaling_value(_scaling_var.get()), _mode_value(_mode_var.get()))


def _show_info() -> None:
    if _info_var is not None:
        _info_var.set(layout.describe_screen(_typed_screen()))


def build_settings(notebook: tk.Misc) -> None:
    global _scaling_var, _mode_var, _info_var, _result_var, _frame, _offsets_var

    frame = nb.Frame(notebook)
    _frame = frame
    frame.columnconfigure(0, weight=1)
    notebook.add(frame, text="Overlay Placement")

    nb.Label(
        frame,
        text=("Where each on-screen display goes, for every overlay feature in WNTB. Pick one of nine spots and an "
              "offset in screen pixels: \"Bottom right\" is the bottom right corner of your screen on any monitor, however "
              "big the display. For the edge spots the offset moves the display inward from the edge; for Center and "
              "Middle it nudges it. \"Exact position\" uses the two numbers as the overlay's own x and y (a 1280 x 960 "
              "canvas stretched over the screen) instead."),
        wraplength=460, justify=tk.LEFT,
    ).grid(row=0, column=0, sticky=tk.W, padx=10, pady=(10, 6))

    _info_var = tk.StringVar(value="")
    nb.Label(frame, textvariable=_info_var, wraplength=460, justify=tk.LEFT).grid(
        row=1, column=0, sticky=tk.W, padx=10, pady=(0, 6))

    screen_box = tk.Frame(frame)
    screen_box.grid(row=2, column=0, sticky=tk.W, padx=10, pady=2)
    nb.Label(screen_box, text="Display scaling:").grid(row=0, column=0, sticky=tk.W)
    saved_scaling = config.get_str(CFG_SCALING) or AUTO
    _scaling_var = tk.StringVar(value=saved_scaling if _scaling_choice_value(saved_scaling) else _SCALING_AUTO_LABEL)
    tk.OptionMenu(screen_box, _scaling_var, _SCALING_AUTO_LABEL, *[label for label, _r in layout.SCALING_CHOICES],
                  command=lambda _v: _show_info()).grid(row=0, column=1, sticky=tk.W, padx=(6, 0))
    nb.Label(screen_box, text="Overlay mode:").grid(row=1, column=0, sticky=tk.W)
    saved_mode = config.get_str(CFG_MODE) or AUTO
    _mode_var = tk.StringVar(value=_MODE_LABELS.get(saved_mode, _MODE_AUTO_LABEL))
    tk.OptionMenu(screen_box, _mode_var, _MODE_AUTO_LABEL, *_MODE_LABELS.values(),
                  command=lambda _v: _show_info()).grid(row=1, column=1, sticky=tk.W, padx=(6, 0))

    _offsets_var = tk.BooleanVar(value=offsets_enabled())
    nb.Checkbutton(
        screen_box, text=("Carry displays on the right to the screen edge (sets an offset on their EDMCModernOverlay group; "
                          "untick if they end up in the wrong place)"),
        variable=_offsets_var, command=_show_info,
    ).grid(row=2, column=0, columnspan=2, sticky=tk.W, pady=(6, 0))

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
    if _scaling_var is None or _mode_var is None or not _rows:
        return
    config.set(CFG_SCALING, _scaling_value(_scaling_var.get()))
    config.set(CFG_MODE, _mode_value(_mode_var.get()))
    if _offsets_var is not None:
        config.set(CFG_OFFSETS, "1" if _offsets_var.get() else "0")
    for key in SLOTS:
        if key in _rows:
            save_placement(key, _typed_placement(key))
    refresh()
    apply_group_offsets()


def _redetect() -> None:
    refresh()
    apply_group_offsets()
    _show_info()
    if _result_var is not None:
        _result_var.set("Read the overlay's log and the game's files again.")


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
    if _scaling_var is not None:
        _scaling_var.set(_SCALING_AUTO_LABEL)
    if _mode_var is not None:
        _mode_var.set(_MODE_AUTO_LABEL)
    if _offsets_var is not None:
        _offsets_var.set(True)
    _show_info()
    if _result_var is not None:
        _result_var.set("Defaults are shown. Press OK in Settings to keep them.")


def preview_shapes(placements: Dict[str, layout.Placement], screen: layout.Screen,
                   use_groups: bool = False) -> List[Dict[str, Any]]:
    """What the preview draws: a small marker at the screen's top left corner, then a labeled box for each display at its
    placed position and at its real size. Positions are canvas units and sizes are pixels, as the overlay takes them. (There
    is no full-screen outline: the overlay squashes a box wider than the canvas, so it could not be drawn truthfully.) Plain
    data so it can be tested without an overlay."""
    items: List[Dict[str, Any]] = [{"id": "wntb_placeprev_edge", "x": 0, "y": 0, "w": 150, "h": 36,
                                    "label": "Screen top left", "color": "#ffffff"}]
    for index, (key, placement) in enumerate(placements.items()):
        slot = SLOTS[key]
        grouped = use_groups and bool(slot.group)     # drawn inside its group, so its offset applies, as for the real display
        size = slot_size(key)
        plan = layout.plan_origin(placement, size, size, screen, grouped)
        items.append({"id": f"{slot.group_prefix}placeprev" if grouped else f"wntb_placeprev_{key}",
                      "x": plan.x, "y": plan.y, "w": size[0], "h": size[1], "offset_x": plan.offset_x,
                      "label": slot.label, "color": _PREVIEW_COLORS[index % len(_PREVIEW_COLORS)]})
    return items


def _preview() -> None:
    """Draws a labeled outline for every display at the positions typed now, for a few seconds."""
    if _result_var is None:
        return
    try:
        typed = {key: _typed_placement(key) for key in SLOTS if key in _rows}
        screen = _typed_screen()
        grouped = overlay.group_offsets_available() and screen.pixel_sizes and _offsets_typed()
        items = preview_shapes(typed, screen, use_groups=grouped)
        if grouped:
            apply_group_offsets(typed, screen)    # the typed values, until the preview ends and the saved ones return
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
            if grouped:
                timer = threading.Timer(PREVIEW_SECONDS + 1, apply_group_offsets)   # the saved placements again
                timer.daemon = True
                timer.start()
        except OSError as exc:
            message = f"Could not reach the overlay: {exc}"
        try:
            if _frame is not None:
                _frame.after(0, lambda: _result_var.set(message) if _result_var is not None else None)
        except (tk.TclError, RuntimeError):
            pass   # the Settings window was closed while drawing

    threading.Thread(target=worker, name="WNTB-overlay-placement-preview", daemon=True).start()
