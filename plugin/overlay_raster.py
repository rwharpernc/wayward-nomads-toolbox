"""Draws the built-in overlay's scene as one picture: the scene's items (`overlay_scene.py`) onto a transparent image the size of the game window.

It uses Pillow, which EDMC ships with, and nothing from Windows, so it is tested anywhere Pillow is. Where things go follows the conventions the overlay features already use
(`overlay_layout.py` has the full account): a position is in canvas units, a 1280 x 960 canvas stretched over the whole window, and a size (a rectangle's width and height, a circle's radius,
the size of text) is in logical pixels, the unit after the operating system's display scaling. So with `ratio` the display scaling (1.25 for 125%), a size becomes `size * ratio` device pixels
and a position becomes `x * width / 1280` across and `y * height / 960` down.

Colors are "#RRGGBB", "#AARRGGBB" (alpha first, as the overlay's payloads write them) or a color name; an empty color means none. Text is drawn from the top left of its line.
"""

from __future__ import annotations

import os
from typing import Dict, Iterable, Optional, Tuple

from PIL import Image, ImageColor, ImageDraw, ImageFont

from .overlay_scene import CIRCLE, RECT, TEXT, VECT, Item

BASE_WIDTH = 1280
BASE_HEIGHT = 960

# The pixel height of the font at each text size, in logical pixels. The card layouts size their lines from `overlay_style.LINE_PX`
# (16, 20, 26, 34 at small to huge); text a little under the line height leaves the gap between lines.
FONT_PX: Dict[str, float] = {"small": 13.0, "normal": 16.0, "large": 21.0, "huge": 27.0}
DEFAULT_FONT_PX = FONT_PX["normal"]
MARKER_RADIUS = 4.0
LINE_WIDTH = 2.0

RGBA = Tuple[int, int, int, int]


def parse_color(text: str) -> Optional[RGBA]:
    """(r, g, b, a) for a color string, or None for no color (empty, or not understood)."""
    value = (text or "").strip()
    if not value:
        return None
    try:
        if value.startswith("#") and len(value) == 9:
            a, r, g, b = (int(value[i:i + 2], 16) for i in (1, 3, 5, 7))
            return r, g, b, a
        r, g, b, *rest = ImageColor.getcolor(value, "RGBA")
        return r, g, b, rest[0] if rest else 255
    except (ValueError, IndexError):
        return None


def default_font_path() -> str:
    """A font to draw with when none is chosen: EDMCModernOverlay's bundled lower-case font if it is installed beside WNTB, else Windows' Segoe UI, else "" (Pillow's own)."""
    plugins = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    candidates = [
        os.path.join(plugins, "EDMCModernOverlay", "overlay_client", "fonts", "SourceSans3-Regular.ttf"),
        os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts", "segoeui.ttf"),
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    return next((path for path in candidates if os.path.isfile(path)), "")


class Fonts:
    """Fonts of one file at the pixel sizes asked for, kept so a frame does not load them again."""

    def __init__(self, path: str = "") -> None:
        self.path = path
        self._cache: Dict[int, ImageFont.ImageFont] = {}

    def get(self, px: float):
        size = max(8, int(round(px)))
        if size not in self._cache:
            try:
                self._cache[size] = ImageFont.truetype(self.path, size) if self.path else ImageFont.load_default(size)
            except OSError:
                self._cache[size] = ImageFont.load_default(size)
        return self._cache[size]


def render(items: Iterable[Item], width: int, height: int, ratio: float = 1.0, fonts: Optional[Fonts] = None) -> Image.Image:
    """The items, already in drawing order, as a transparent RGBA picture `width` x `height` device pixels."""
    fonts = fonts or Fonts(default_font_path())
    image = Image.new("RGBA", (max(1, width), max(1, height)), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    ux, uy = width / BASE_WIDTH, height / BASE_HEIGHT
    for item in items:
        x, y = item.x * ux, item.y * uy
        if item.kind == RECT:
            _rect(draw, item, x, y, ratio)
        elif item.kind == CIRCLE:
            _circle(draw, item, x, y, ratio)
        elif item.kind == VECT:
            _vect(draw, item, ux, uy, ratio, fonts)
        elif item.kind == TEXT:
            color = parse_color(item.color) or (255, 255, 255, 255)
            draw.text((x, y), item.text, font=fonts.get(FONT_PX.get(item.size, DEFAULT_FONT_PX) * ratio), fill=color)
    return image


def _rect(draw: ImageDraw.ImageDraw, item: Item, x: float, y: float, ratio: float) -> None:
    box = (x, y, x + item.w * ratio, y + item.h * ratio)
    fill, border = parse_color(item.fill), parse_color(item.color)
    width = max(1, int(round(item.thickness * ratio)))
    if fill is not None and fill[3]:
        draw.rectangle(box, fill=fill)
    if border is not None and border[3] and border != fill:
        draw.rectangle(box, outline=border, width=width)


def _circle(draw: ImageDraw.ImageDraw, item: Item, x: float, y: float, ratio: float) -> None:
    r = item.radius * ratio
    fill, border = parse_color(item.fill), parse_color(item.color)
    draw.ellipse((x - r, y - r, x + r, y + r), fill=fill if fill is not None and fill[3] else None,
                 outline=border if border is not None and border[3] else None, width=max(1, int(round(item.thickness * ratio))))


def _vect(draw: ImageDraw.ImageDraw, item: Item, ux: float, uy: float, ratio: float, fonts: Fonts) -> None:
    base = parse_color(item.color) or (255, 255, 255, 255)
    points = [(px * ux, py * uy) for px, py, _c, _m, _t in item.points]
    if len(points) > 1:
        draw.line(points, fill=base, width=max(1, int(round(LINE_WIDTH * ratio))))
    r = MARKER_RADIUS * ratio
    for (px, py), (_x, _y, color, marker, label) in zip(points, item.points):
        tint = parse_color(color) or base
        if marker == "cross":
            draw.line((px - r, py, px + r, py), fill=tint, width=max(1, int(ratio)))
            draw.line((px, py - r, px, py + r), fill=tint, width=max(1, int(ratio)))
        elif marker == "circle":
            draw.ellipse((px - r, py - r, px + r, py + r), outline=tint, width=max(1, int(ratio)))
        if label:
            draw.text((px + r * 1.5, py - r), label, font=fonts.get(FONT_PX["small"] * ratio), fill=tint)
