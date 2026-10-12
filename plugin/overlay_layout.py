"""Where WNTB's overlay displays go on the screen: one placement model for every overlay in the plugin. Pure logic (no Tk,
no EDMC), so it is tested without a game or an overlay program.

**How the overlay draws** (measured on EDMCModernOverlay in its default fill mode, 3840 x 2160 at 125% display scaling):

- A display is drawn at a **position** on a fixed 1280 x 960 canvas, and the canvas is stretched over the *whole* screen, so
  a position is a fraction of the screen: x / 1280 across and y / 960 down. Nothing of the canvas is cut off.
- A display's **size** is not in canvas units. Widths, heights and the offsets between the pieces of one display are in
  *screen pixels* (logical pixels, after the operating system's display scaling), so a 360-wide card is 360 pixels wide
  whether the screen is 1080p or 4K. On a 3072 x 1728 logical screen that is 360 / 3072 = 12% of the width, which is
  360 / 2.4 = 150 canvas units, not 360.

So a display placed "at x = 900" does not end at 900 + 360 on the canvas: it ends at 900 + 150. Anchoring it to the right or
bottom edge, or centering it, needs its size converted from pixels to canvas units, which is what this module does. A bare
x/y number also means a different place on each monitor shape, which is why raw numbers feel arbitrary. Placement here is
instead **relative to the screen**: a horizontal anchor (left, center, right), a vertical anchor
(top, middle, bottom) and an offset in screen pixels.

**The right-hand clamp, and how it is passed.** On the axis the overlay does not stretch (across, on a wide screen) it clamps a
shape's left position plus its pixel width to the canvas width, so a display cannot be drawn past `1280 - its width` without
being squashed. The overlay applies a *group offset* after that clamp (it is how its own Overlay Controller moves things), and
offers it to plugins through `define_plugin_group`. So a display that belongs to a group is drawn at the furthest-right spot
the clamp allows and the group's offset carries it the rest of the way (`plan_origin`); a display with no group stops at the
clamp.

**How features use it.** Each feature keeps drawing at its own fixed coordinates, exactly as before, and reports the
rectangle it occupies (its "block", whose left and top are canvas coordinates and whose width and height are pixels).
`shift_for` says how far to move that block, and `ShiftedClient` applies the move to everything drawn through it, so no
feature has to be rewritten around a new coordinate system.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence, Tuple

BASE_WIDTH = 1280
BASE_HEIGHT = 960

H_ANCHORS = ("left", "center", "right")
V_ANCHORS = ("top", "middle", "bottom")
CUSTOM = "custom"          # an exact canvas position, for people who want one (and how old x/y settings carry over)

MODE_FIT = "fit"
MODE_FILL = "fill"

MIN_ASPECT = 1.0           # screens outside this range are treated as unreadable data, not as real monitors
MAX_ASPECT = 8.0
MIN_RATIO = 0.5            # display scaling outside this range is treated as unreadable data too
MAX_RATIO = 6.0

# Display scaling choices offered when it can't be detected: (label, ratio).
SCALING_CHOICES: Tuple[Tuple[str, float], ...] = (
    ("100%", 1.0), ("125%", 1.25), ("150%", 1.5), ("175%", 1.75), ("200%", 2.0), ("250%", 2.5), ("300%", 3.0),
)


# --- the screen --------------------------------------------------------------------------------------------------

@dataclass(frozen=True)
class Screen:
    """The overlay window and how its canvas is mapped onto it."""
    width: int = 1920                  # the overlay window, in device pixels
    height: int = 1080
    mode: str = MODE_FILL
    source: str = "default"            # where this came from, for the settings page to say
    full_screen: Optional[int] = None  # the game's FullScreen value: 0 windowed, 1 borderless, 2 full screen
    ratio: float = 1.0                 # device pixels per logical pixel: the operating system's display scaling (1.25 = 125%)
    pixel_sizes: bool = True           # sizes are screen pixels (EDMCModernOverlay); False: canvas units (no EDMCModernOverlay found)

    @property
    def aspect(self) -> float:
        return self.width / self.height

    @property
    def logical(self) -> Tuple[float, float]:
        """The window size in logical pixels, the unit display sizes are in."""
        return self.width / self.ratio, self.height / self.ratio

    @property
    def units_per_px(self) -> Tuple[float, float]:
        """Canvas units per pixel, across and down: how big a pixel is on the 1280 x 960 canvas."""
        if not self.pixel_sizes:
            return 1.0, 1.0
        logical_w, logical_h = self.logical
        if self.mode == MODE_FIT:
            scale = min(logical_w / BASE_WIDTH, logical_h / BASE_HEIGHT)    # the canvas keeps its shape: one scale
            return 1.0 / scale, 1.0 / scale
        return BASE_WIDTH / logical_w, BASE_HEIGHT / logical_h             # the canvas is stretched over the window

    @property
    def visible(self) -> Tuple[int, int]:
        """The canvas area that shows: all of it (fill stretches it over the screen; fit shows it with bars)."""
        return BASE_WIDTH, BASE_HEIGHT

    @property
    def clamped(self) -> Tuple[bool, bool]:
        """Which axes the overlay clamps a shape's far edge on. It limits x + width (a pixel width added to a canvas
        position) to the canvas size and squashes the shape if it would pass it, but only on the axis it does not stretch
        (measured: on a wide screen it stretches the canvas down the screen so y is free, and clamps across it, so x is
        clamped; in fit mode both are). A display placed past `canvas size - its pixel size` on a clamped axis loses the
        part beyond, so placement stops it before that. Overlays that draw in canvas units have no such limit."""
        if not self.pixel_sizes:
            return False, False
        if self.mode == MODE_FIT:
            return True, True
        logical_w, logical_h = self.logical
        return (True, False) if logical_w / BASE_WIDTH >= logical_h / BASE_HEIGHT else (False, True)


def block_units(size_px: Tuple[int, int], screen: Screen) -> Tuple[float, float]:
    """A display's size in canvas units, given its size in pixels."""
    ux, uy = screen.units_per_px
    return size_px[0] * ux, size_px[1] * uy


def parse_display_settings(text: str) -> Optional[Tuple[int, int, Optional[int]]]:
    """(width, height, full_screen) from the game's `DisplaySettings.xml`, or None when it can't be used. A missing
    FullScreen is None; a size outside a believable range is rejected rather than trusted."""
    try:
        root = ET.fromstring(text)
    except ET.ParseError:
        return None

    def number(tag: str) -> Optional[int]:
        node = root.find(tag)
        try:
            return int(str(node.text).strip()) if node is not None and node.text is not None else None
        except ValueError:
            return None

    width, height = number("ScreenWidth"), number("ScreenHeight")
    if not width or not height or width <= 0 or height <= 0:
        return None
    if not MIN_ASPECT <= width / height <= MAX_ASPECT:
        return None
    return width, height, number("FullScreen")


# What EDMCModernOverlay's client writes whenever its window or scale changes, e.g.
# "Overlay scaling updated: window=3840x2160 px mode=fill base_scale=2.4000 scale_x=3.000 scale_y=3.000 ..."
_SCALING_LINE = re.compile(
    r"Overlay scaling updated: window=(\d+)x(\d+) px mode=(\w+) base_scale=([0-9.]+) scale_x=([0-9.]+)")


def parse_scaling_line(text: str) -> Optional[Tuple[int, int, str, float]]:
    """(window width, window height, mode, display scaling ratio) from the newest 'Overlay scaling updated' line in the
    overlay's own log, or None. The ratio is scale_x / base_scale: the overlay's device-pixel scale over its logical one."""
    found = None
    for match in _SCALING_LINE.finditer(text):
        found = match
    if found is None:
        return None
    width, height, mode = int(found.group(1)), int(found.group(2)), found.group(3).lower()
    try:
        base, scale_x = float(found.group(4)), float(found.group(5))
    except ValueError:
        return None
    if base <= 0 or scale_x <= 0 or mode not in (MODE_FIT, MODE_FILL):
        return None
    ratio = scale_x / base
    if not (MIN_ASPECT <= width / max(height, 1) <= MAX_ASPECT) or not (MIN_RATIO <= ratio <= MAX_RATIO):
        return None
    return width, height, mode, ratio


def describe_screen(screen: Screen) -> str:
    """One line for the settings page: what was found and what that means for the overlay."""
    modes = {0: "windowed", 1: "borderless", 2: "full screen"}
    shape = f"{screen.width} x {screen.height}"
    if screen.full_screen in modes:
        shape += f", {modes[screen.full_screen]}"
    if abs(screen.ratio - 1.0) > 0.01:
        shape += f", display scaling {round(screen.ratio * 100)}%"
    if not screen.pixel_sizes:
        return f"{shape} ({screen.source}); this overlay draws sizes in canvas units, so displays are anchored directly."
    logical_w, logical_h = screen.logical
    how = ("the canvas is stretched over your whole screen" if screen.mode == MODE_FILL
           else "the canvas keeps its shape, with bars on the sides or top and bottom")
    return (f"{shape} ({screen.source}); overlay mode {screen.mode}: {how}. Displays are drawn at pixel size on a "
            f"{round(logical_w)} x {round(logical_h)} pixel screen.")


# --- placements --------------------------------------------------------------------------------------------------

@dataclass(frozen=True)
class Placement:
    """Where a display sits: anchors plus an offset in screen pixels, or (for `h == CUSTOM`) an exact canvas position.

    The offset moves the display *inward* from a left/top/right/bottom anchor (toward the middle of the screen), and to
    the right/down from a center/middle anchor."""
    h: str = "left"
    v: str = "top"
    dx: int = 0
    dy: int = 0
    x: int = 0              # used only when h == CUSTOM (canvas units)
    y: int = 0

    @property
    def custom(self) -> bool:
        return self.h == CUSTOM


def custom_placement(x: int, y: int) -> Placement:
    return Placement(h=CUSTOM, v=CUSTOM, x=int(x), y=int(y))


def format_placement(placement: Placement) -> str:
    """The text saved in settings: 'right,bottom,20,40' or 'custom,700,60'."""
    if placement.custom:
        return f"{CUSTOM},{placement.x},{placement.y}"
    return f"{placement.h},{placement.v},{placement.dx},{placement.dy}"


def parse_placement(text: Optional[str], default: Placement) -> Placement:
    """Reads what `format_placement` wrote. Anything else (empty, damaged, an unknown anchor) gives `default`."""
    parts = [p.strip().lower() for p in str(text or "").split(",")]
    try:
        if len(parts) == 3 and parts[0] == CUSTOM:
            return custom_placement(int(parts[1]), int(parts[2]))
        if len(parts) == 4 and parts[0] in H_ANCHORS and parts[1] in V_ANCHORS:
            return Placement(parts[0], parts[1], int(parts[2]), int(parts[3]))
    except ValueError:
        pass
    return default


# The choices in the Settings menu: a name for each of the nine spots, and "Exact position" for a canvas x/y.
PRESETS: Tuple[Tuple[str, str, str], ...] = (
    ("Top left", "left", "top"), ("Top center", "center", "top"), ("Top right", "right", "top"),
    ("Middle left", "left", "middle"), ("Center", "center", "middle"), ("Middle right", "right", "middle"),
    ("Bottom left", "left", "bottom"), ("Bottom center", "center", "bottom"), ("Bottom right", "right", "bottom"),
)
EXACT_LABEL = "Exact position"
PRESET_LABELS: Tuple[str, ...] = tuple(label for label, _h, _v in PRESETS) + (EXACT_LABEL,)


def preset_label(placement: Placement) -> str:
    """The menu text for a placement."""
    if placement.custom:
        return EXACT_LABEL
    return next((label for label, h, v in PRESETS if (h, v) == (placement.h, placement.v)), PRESETS[0][0])


def placement_from_choice(label: str, first: int, second: int) -> Placement:
    """The placement for a menu choice and the two numbers beside it. For a named spot they are the offsets from it, in
    screen pixels; for "Exact position" they are the canvas x and y."""
    if label == EXACT_LABEL:
        return custom_placement(first, second)
    for name, h, v in PRESETS:
        if name == label:
            return Placement(h, v, int(first), int(second))
    raise ValueError(f"unknown placement choice: {label!r}")


def _ideal_origin(placement: Placement, block_size: Tuple[int, int], screen: Screen) -> Tuple[float, float]:
    """Where the top left corner of a display of `block_size` pixels belongs on the canvas, kept on the canvas but not yet
    limited by the overlay's clamp. A custom placement is returned as given."""
    if placement.custom:
        return float(placement.x), float(placement.y)
    width, height = block_units(block_size, screen)
    ux, uy = screen.units_per_px
    offset_x, offset_y = placement.dx * ux, placement.dy * uy
    if placement.h == "left":
        x = offset_x
    elif placement.h == "right":
        x = BASE_WIDTH - width - offset_x
    else:
        x = (BASE_WIDTH - width) / 2 + offset_x
    if placement.v == "top":
        y = offset_y
    elif placement.v == "bottom":
        y = BASE_HEIGHT - height - offset_y
    else:
        y = (BASE_HEIGHT - height) / 2 + offset_y
    x = max(0.0, min(x, BASE_WIDTH - width)) if width <= BASE_WIDTH else 0.0
    y = max(0.0, min(y, BASE_HEIGHT - height)) if height <= BASE_HEIGHT else 0.0
    return x, y


def block_origin(placement: Placement, block_size: Tuple[int, int], screen: Screen) -> Tuple[int, int]:
    """Canvas position of the top left corner of a display whose size is `block_size` (pixels) placed as `placement` on
    `screen`, for a display that cannot be offset: it is stopped where the overlay would squash it. The size is converted to
    canvas units first, so "right" and "bottom" land on the real edge where the overlay allows. The result is kept on the
    canvas when the display fits; a display bigger than the canvas is pinned to its top left so that the start of it shows. A
    custom placement is returned as given (it is the person's exact choice)."""
    if placement.custom:
        return placement.x, placement.y
    x, y = _ideal_origin(placement, block_size, screen)
    clamp_x, clamp_y = screen.clamped
    if clamp_x and block_size[0] <= BASE_WIDTH:
        x = min(x, BASE_WIDTH - block_size[0])       # past this the overlay squashes the display's width
    if clamp_y and block_size[1] <= BASE_HEIGHT:
        y = min(y, BASE_HEIGHT - block_size[1])
    return round(x), round(y)


@dataclass(frozen=True)
class Plan:
    """How to reach a place: draw the display with its top left at (`x`, `y`) on the canvas, and have the overlay move its group
    `offset_x` canvas units to the right afterwards (0 when none is needed)."""
    x: int
    y: int
    offset_x: float = 0.0


def plan_origin(placement: Placement, block_size: Tuple[int, int], slot_size: Tuple[int, int], screen: Screen,
                can_offset: bool) -> Plan:
    """Where to draw a display and how far to have its overlay group moved after. With `can_offset` False this is just
    `block_origin`. With it True, a display that belongs on the far side of the overlay's clamp is drawn at the furthest
    spot the clamp allows for its largest size (`slot_size`, so the position does not move as its content changes) and the
    offset carries it from there to the place wanted. The wanted place is worked out from `slot_size` too, so the offset is a
    fixed number for a given placement and screen, as a group offset has to be."""
    if not can_offset:
        x, y = block_origin(placement, block_size, screen)
        return Plan(x, y)
    clamp_x, _clamp_y = screen.clamped
    ideal_x, _ideal_y = _ideal_origin(placement, slot_size, screen)
    x, y = block_origin(placement, block_size, screen)
    if not clamp_x or slot_size[0] > BASE_WIDTH:
        return Plan(x, y)
    limit = BASE_WIDTH - slot_size[0]
    if ideal_x > limit:
        return Plan(round(limit), y, round(ideal_x - limit, 3))
    return Plan(round(ideal_x), y)


def shift_for(placement: Placement, block: Tuple[int, int, int, int], screen: Screen,
              slot_size: Optional[Tuple[int, int]] = None, can_offset: bool = False) -> Tuple[int, int]:
    """How far to move a display, given the rectangle `block` = (left, top, width, height) it occupies in its own
    drawing coordinates (left and top on the canvas, width and height in pixels), to put it where `placement` says. When the
    display's group can be offset (`can_offset`, with its largest size `slot_size`) the move only goes as far as the overlay's
    clamp allows and the group offset (see `plan_origin`) does the rest."""
    left, top, width, height = block
    plan = plan_origin(placement, (width, height), slot_size or (width, height), screen, can_offset)
    return plan.x - left, plan.y - top


class HiddenClient:
    """An overlay client for a display the commander has hidden (Overlay Placement -> Show). Whatever the display draws becomes a
    clear of the same id, so nothing appears and anything already on screen goes. Anything else passes to the real client."""

    def __init__(self, client: Any) -> None:
        self._client = client

    def send_message(self, msg_id: str, text: str, color: str, x: int, y: int, ttl: int = 8, size: str = "normal") -> None:
        self._client.send_message(msg_id, "", color, x, y, ttl=1, size=size)

    def send_shape(self, shape_id: str, shape: str, color: str, fill: str, x: int, y: int, w: int, h: int, ttl: int = 8,
                   thickness: Optional[int] = None) -> None:
        self._client.send_shape(shape_id, shape, "", "", x, y, 0, 0, ttl=1, thickness=thickness)

    def send_vector(self, shape_id: str, points: Sequence[Dict[str, Any]], color: str, ttl: int = 8) -> None:
        self._client.send_vector(shape_id, [], color, ttl=1)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._client, name)


class ShiftedClient:
    """An overlay client that moves everything drawn through it by a fixed (dx, dy) in canvas units. Features keep their
    own layout; this carries them to the chosen place. Anything it doesn't know about passes straight to the real client."""

    def __init__(self, client: Any, dx: int, dy: int) -> None:
        self._client, self._dx, self._dy = client, int(dx), int(dy)

    def send_message(self, msg_id: str, text: str, color: str, x: int, y: int, ttl: int = 8, size: str = "normal") -> None:
        self._client.send_message(msg_id, text, color, x + self._dx, y + self._dy, ttl=ttl, size=size)

    def send_shape(self, shape_id: str, shape: str, color: str, fill: str, x: int, y: int, w: int, h: int, ttl: int = 8,
                   thickness: Optional[int] = None) -> None:
        # A shape cleared with a zero size stays where it was; the move does not matter for it but is harmless.
        self._client.send_shape(shape_id, shape, color, fill, x + self._dx, y + self._dy, w, h, ttl=ttl, thickness=thickness)

    def send_vector(self, shape_id: str, points: Sequence[Dict[str, Any]], color: str, ttl: int = 8) -> None:
        moved: List[Dict[str, Any]] = [dict(p, x=p["x"] + self._dx, y=p["y"] + self._dy) for p in points]
        self._client.send_vector(shape_id, moved, color, ttl=ttl)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._client, name)


# --- the displays ------------------------------------------------------------------------------------------------

@dataclass(frozen=True)
class Slot:
    """One display that can be placed. `key` names it in settings; `legacy_keys` are the old x/y settings (if any) read
    once so that a position somebody chose by hand is not lost; `size` is the block (in pixels) used to preview it."""
    key: str
    label: str
    default: Placement
    size: Tuple[int, int]
    legacy_x: str = ""
    legacy_y: str = ""
    legacy_default: Tuple[int, int] = (0, 0)
    group: str = ""          # the overlay group this display's ids belong to, whose offset can carry it past the clamp ("" = none)
    group_prefix: str = ""   # that group's id prefix, so the preview can be drawn inside the group


def migrated_placement(slot: Slot, legacy_x: Optional[int], legacy_y: Optional[int]) -> Placement:
    """The placement for a slot whose new setting has never been saved: the slot's default, unless the person had set an
    exact position in the old x/y settings, which is kept as a custom placement."""
    if legacy_x is None or legacy_y is None or (legacy_x, legacy_y) == slot.legacy_default:
        return slot.default
    return custom_placement(legacy_x, legacy_y)


_SAFE_KEY = re.compile(r"^[a-z0-9_]+$")


def setting_key(slot_key: str) -> str:
    """The settings key a slot's placement is saved under."""
    if not _SAFE_KEY.match(slot_key):
        raise ValueError(f"bad overlay slot key: {slot_key!r}")
    return f"wntb_overlay_place_{slot_key}"
