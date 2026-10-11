"""Where WNTB's overlay displays go on the screen: one placement model for every overlay in the plugin. Pure logic (no Tk,
no EDMC), so it is tested without a game or an overlay program.

**The problem it solves.** Overlay programs draw on a fixed 1280 x 960 (4:3) canvas and map it onto the game window. How
the canvas fits depends on the window's shape and on the overlay's scale mode:

- **fit**: the whole canvas is shown, centered, with unused bars on the sides (or top and bottom). Every canvas position
  is visible.
- **fill** (EDMCModernOverlay's default): the canvas is scaled up until it covers the window, and what does not fit is
  cut off. On a 16:9 screen only the top 1280 x 720 of the canvas is visible; on a 32:9 ultrawide, only 1280 x 360.

So a bare "y = 600" lands on screen on one monitor and below the bottom edge on another, which is why raw x/y values feel
arbitrary. Placement here is instead **relative to the visible area**, like SRVSurvey's overlays are relative to the game
window: a horizontal anchor (left, center, right), a vertical anchor (top, middle, bottom) and an offset in canvas units
(1/1280 of the canvas width). "Bottom right, 20 in" is the bottom right corner of whatever is visible, on any screen.

**How features use it.** Each feature keeps drawing at its own fixed coordinates, exactly as before, and reports the
rectangle it occupies (its "block"). `shift_for` says how far to move that block to reach the chosen place, and
`ShiftedClient` applies the move to everything drawn through it, so no feature has to be rewritten around a new
coordinate system.
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

# Screen shapes offered when the game's own files can't be read (the common ones), as (label, width, height).
ASPECT_CHOICES: Tuple[Tuple[str, int, int], ...] = (
    ("4:3", 4, 3), ("5:4", 5, 4), ("16:10", 16, 10), ("16:9", 16, 9), ("21:9", 21, 9), ("32:9", 32, 9),
)


# --- the screen --------------------------------------------------------------------------------------------------

@dataclass(frozen=True)
class Screen:
    """The game's picture shape, and how the overlay maps its canvas onto it."""
    width: int = 1920
    height: int = 1080
    mode: str = MODE_FILL
    source: str = "default"            # where the shape came from, for the settings page to say
    full_screen: Optional[int] = None  # the game's FullScreen value: 0 windowed, 1 borderless, 2 full screen

    @property
    def aspect(self) -> float:
        return self.width / self.height

    @property
    def visible(self) -> Tuple[int, int]:
        return visible_area(self.width, self.height, self.mode)


def visible_area(width: int, height: int, mode: str) -> Tuple[int, int]:
    """The part of the 1280 x 960 canvas that shows on a `width` x `height` window, as (w, h) from the canvas's top left.
    Fit shows all of it. Fill shows the part that covers the window: the full width and a shorter height on wide screens
    (16:9 -> 1280 x 720), the full height and a narrower width on tall ones (5:4 -> 1200 x 960)."""
    if width <= 0 or height <= 0 or mode == MODE_FIT:
        return BASE_WIDTH, BASE_HEIGHT
    aspect = width / height
    if aspect >= BASE_WIDTH / BASE_HEIGHT:
        return BASE_WIDTH, max(1, round(BASE_WIDTH / aspect))
    return max(1, round(BASE_HEIGHT * aspect)), BASE_HEIGHT


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


def screen_from_aspect(aspect_width: int, aspect_height: int, mode: str, source: str) -> Screen:
    """A screen of the given shape (the pixel size is a stand-in; only the shape matters to the overlay's mapping)."""
    return Screen(width=aspect_width * 120, height=aspect_height * 120, mode=mode, source=source)


def describe_screen(screen: Screen) -> str:
    """One line for the settings page: what was found and what that means for the overlay."""
    vw, vh = screen.visible
    shape = f"{screen.width} x {screen.height}"
    modes = {0: "windowed", 1: "borderless", 2: "full screen"}
    if screen.full_screen in modes:
        shape += f", {modes[screen.full_screen]}"
    area = "all of the 1280 x 960 canvas" if (vw, vh) == (BASE_WIDTH, BASE_HEIGHT) else f"{vw} x {vh} of the 1280 x 960 canvas"
    return f"{shape} ({screen.source}); overlay mode {screen.mode} shows {area}."


# --- placements --------------------------------------------------------------------------------------------------

@dataclass(frozen=True)
class Placement:
    """Where a display sits: anchors plus an offset, or (for `h == CUSTOM`) an exact canvas position.

    The offset moves the display *inward* from a left/top/right/bottom anchor (toward the middle of the screen), and to
    the right/down from a center/middle anchor."""
    h: str = "left"
    v: str = "top"
    dx: int = 0
    dy: int = 0
    x: int = 0              # used only when h == CUSTOM
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
    """The placement for a menu choice and the two numbers beside it. For a named spot they are the offsets from it; for
    "Exact position" they are the canvas x and y."""
    if label == EXACT_LABEL:
        return custom_placement(first, second)
    for name, h, v in PRESETS:
        if name == label:
            return Placement(h, v, int(first), int(second))
    raise ValueError(f"unknown placement choice: {label!r}")


def block_origin(placement: Placement, block_size: Tuple[int, int], screen: Screen) -> Tuple[int, int]:
    """Canvas position of the top left corner of a `block_size` display placed as `placement` on `screen`. The result is
    kept inside the visible area when the display fits in it; a display bigger than the area is pinned to its top left so
    that the start of it is what shows. A custom placement is returned as given (it is the person's exact choice)."""
    if placement.custom:
        return placement.x, placement.y
    width, height = block_size
    area_w, area_h = screen.visible
    if placement.h == "left":
        x = placement.dx
    elif placement.h == "right":
        x = area_w - width - placement.dx
    else:
        x = (area_w - width) // 2 + placement.dx
    if placement.v == "top":
        y = placement.dy
    elif placement.v == "bottom":
        y = area_h - height - placement.dy
    else:
        y = (area_h - height) // 2 + placement.dy
    x = max(0, min(x, area_w - width)) if width <= area_w else 0
    y = max(0, min(y, area_h - height)) if height <= area_h else 0
    return x, y


def shift_for(placement: Placement, block: Tuple[int, int, int, int], screen: Screen) -> Tuple[int, int]:
    """How far to move a display, given the rectangle `block` = (left, top, width, height) it occupies in its own
    drawing coordinates, to put it where `placement` says."""
    left, top, width, height = block
    x, y = block_origin(placement, (width, height), screen)
    return x - left, y - top


class ShiftedClient:
    """An overlay client that moves everything drawn through it by a fixed (dx, dy). Features keep their own layout; this
    carries them to the chosen place. Anything it doesn't know about passes straight to the real client."""

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
    once so that a position somebody chose by hand is not lost; `size` is the block used to preview it."""
    key: str
    label: str
    default: Placement
    size: Tuple[int, int]
    legacy_x: str = ""
    legacy_y: str = ""
    legacy_default: Tuple[int, int] = (0, 0)


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
