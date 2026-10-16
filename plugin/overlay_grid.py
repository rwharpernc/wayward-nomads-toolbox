"""A drag-and-drop layout editor for the Overlay Placement tab: a small picture of the screen with a grid, and a box for every display that you drag
where you want it. Dropping a box writes the placement the rest of Overlay Placement already understands (one of the nine spots and an offset in screen pixels).

Why it exists: typing a spot and two offsets means guessing what a pixel offset looks like. Here the box is shown at its real size on a to-scale screen, so
what you drop is what you get, and a box dropped near an edge snaps flush to it (offset 0) and near the middle snaps to the center line, so "0" really is
the edge. The grid (20, 40, 60 or 120 screen pixels) snaps the rest to even steps so cards line up with each other and with the game's own panels.

The conversions between a dropped rectangle and a placement are pure (`placement_from_rect`, `rect_from_placement`, `snap`) and tested without Tk;
`LayoutEditor` is the Tk widget around them. Sizes and offsets are in the screen's logical pixels, the unit Overlay Placement's offsets and sizes are in.
"""

from __future__ import annotations

import math
from typing import Any, Callable, Dict, Optional, Tuple

from . import overlay_layout as layout

GRID_CHOICES = (20, 40, 60, 120)
SIZE_CHOICES = (("Default", 540), ("Large", 760), ("Extra large", 980))     # the picture's width in pixels
DEFAULT_SIZE = "Default"
DEFAULT_GRID = 40
EDGE_SNAP = 14           # logical pixels: a box this close to an edge or the center line snaps to it
THIRD = 1 / 3


def snap(value: float, step: int) -> int:
    """`value` rounded to the nearest multiple of `step`, halves up (a step under 2 just rounds it)."""
    return int(math.floor(value / step + 0.5) * step) if step >= 2 else int(math.floor(value + 0.5))


def placement_from_rect(left: float, top: float, width: float, height: float, screen: Tuple[float, float], grid: int = DEFAULT_GRID,
                        edge: int = EDGE_SNAP) -> layout.Placement:
    """The placement for a box whose top left is (`left`, `top`) and whose size is (`width`, `height`), all in logical pixels on a `screen` of that size.
    The spot (left, center or right; top, middle or bottom) is the third of the screen the box's center is in. The offset is measured from that
    spot as Overlay Placement measures it: inward from an edge, and from the center line for a centered box. A box within `edge` pixels of an edge (or
    of the center line) snaps to it (offset 0); otherwise the offset snaps to `grid`."""
    screen_w, screen_h = screen
    left = max(0.0, min(left, screen_w - width))
    top = max(0.0, min(top, screen_h - height))
    center_x, center_y = left + width / 2, top + height / 2
    h = "left" if center_x < screen_w * THIRD else "right" if center_x > screen_w * (1 - THIRD) else "center"
    v = "top" if center_y < screen_h * THIRD else "bottom" if center_y > screen_h * (1 - THIRD) else "middle"

    def offset(kind: str, near: float, far: float, middle: float) -> int:
        """`near` is the gap to the near edge, `far` to the far edge and `middle` the signed distance of the box's center from the center line."""
        if kind in ("left", "top"):
            value = near
        elif kind in ("right", "bottom"):
            value = far
        else:
            value = middle
        if abs(value) <= edge:
            return 0
        return snap(value, grid) if kind in ("center", "middle") else max(0, snap(value, grid))

    return layout.Placement(h, v, offset(h, left, screen_w - left - width, center_x - screen_w / 2),
                            offset(v, top, screen_h - top - height, center_y - screen_h / 2))


def rect_from_placement(placement: layout.Placement, size: Tuple[float, float], screen: Tuple[float, float],
                        canvas_units_per_px: Tuple[float, float] = (1.0, 1.0)) -> Tuple[float, float]:
    """The top left (logical pixels) of a box of `size` placed as `placement` on a `screen`. A custom (exact) placement is in canvas units and is
    converted with `canvas_units_per_px`. The result is kept on the screen."""
    width, height = size
    screen_w, screen_h = screen
    if placement.custom:
        left, top = placement.x / canvas_units_per_px[0], placement.y / canvas_units_per_px[1]
    else:
        left = {"left": placement.dx, "right": screen_w - width - placement.dx}.get(placement.h, (screen_w - width) / 2 + placement.dx)
        top = {"top": placement.dy, "bottom": screen_h - height - placement.dy}.get(placement.v, (screen_h - height) / 2 + placement.dy)
    return max(0.0, min(left, screen_w - width)), max(0.0, min(top, screen_h - height))


def describe(placement: layout.Placement) -> str:
    """'Top left, 0 px in, 120 px down' for the line under the picture."""
    spot = layout.preset_label(placement)
    if placement.custom:
        return f"{spot}: x {placement.x}, y {placement.y}"
    horizontal = {"left": f"{placement.dx} px from the left", "right": f"{placement.dx} px from the right"}.get(placement.h, f"{placement.dx:+d} px from the middle")
    vertical = {"top": f"{placement.dy} px from the top", "bottom": f"{placement.dy} px from the bottom"}.get(placement.v, f"{placement.dy:+d} px from the middle")
    return f"{spot}: {horizontal}, {vertical}"


class LayoutEditor:
    """The Tk widget: a canvas drawn to scale, one draggable box per display. `slots` is {key: (label, (width, height))} in logical pixels; `get` returns
    a key's current placement and `put` is called with (key, placement) when a box is dropped; `hidden` says whether a display is hidden. Built with Tk
    imported lazily so the module's pure functions import without it."""

    def __init__(self, parent: Any, screen: Tuple[float, float], slots: Dict[str, Tuple[str, Tuple[int, int]]], get: Callable[[str], Optional[layout.Placement]],
                 put: Callable[[str, layout.Placement], None], hidden: Callable[[str], bool], colors: Tuple[str, ...],
                 size: str = DEFAULT_SIZE, on_size: Optional[Callable[[str], None]] = None) -> None:
        import tkinter as tk
        self._tk = tk
        self.screen, self.slots, self._get, self._put, self._hidden, self._colors = screen, slots, get, put, hidden, colors
        self._on_size = on_size
        self.WIDTH = dict(SIZE_CHOICES).get(size, dict(SIZE_CHOICES)[DEFAULT_SIZE])
        self.scale = self.WIDTH / screen[0]
        self.height = int(round(screen[1] * self.scale))
        self.frame = tk.Frame(parent)
        bar = tk.Frame(self.frame)
        bar.pack(anchor=tk.W)
        tk.Label(bar, text="Picture size:").pack(side=tk.LEFT)
        self.size_var = tk.StringVar(value=size if size in dict(SIZE_CHOICES) else DEFAULT_SIZE)
        tk.OptionMenu(bar, self.size_var, *[label for label, _w in SIZE_CHOICES], command=self._resize).pack(side=tk.LEFT, padx=(4, 10))
        tk.Label(bar, text="Grid:").pack(side=tk.LEFT)
        self.grid_var = tk.StringVar(value=f"{DEFAULT_GRID} px")
        tk.OptionMenu(bar, self.grid_var, *[f"{g} px" for g in GRID_CHOICES], command=lambda _v: self.redraw()).pack(side=tk.LEFT, padx=(4, 10))
        self.snap_var = tk.BooleanVar(value=True)
        tk.Checkbutton(bar, text="Snap to the grid and to edges", variable=self.snap_var).pack(side=tk.LEFT)
        self.canvas = tk.Canvas(self.frame, width=self.WIDTH, height=self.height, background="#101418", highlightthickness=1, highlightbackground="#555555")
        self.canvas.pack(anchor=tk.W, pady=(4, 2))
        self.status = tk.StringVar(value="Drag a box to place that display. A box near an edge snaps to it (offset 0).")
        self._status_label = tk.Label(self.frame, textvariable=self.status, wraplength=self.WIDTH, justify=tk.LEFT)
        self._status_label.pack(anchor=tk.W)
        self._drag: Optional[Tuple[str, float, float]] = None
        self.canvas.bind("<ButtonPress-1>", self._press)
        self.canvas.bind("<B1-Motion>", self._move)
        self.canvas.bind("<ButtonRelease-1>", self._release)
        self.redraw()

    def _resize(self, choice: str) -> None:
        """Changes the picture's size (and remembers it, through `on_size`): the same screen at a different scale."""
        self.WIDTH = dict(SIZE_CHOICES).get(choice, dict(SIZE_CHOICES)[DEFAULT_SIZE])
        self.scale = self.WIDTH / self.screen[0]
        self.height = int(round(self.screen[1] * self.scale))
        self.canvas.configure(width=self.WIDTH, height=self.height)
        self._status_label.configure(wraplength=self.WIDTH)
        if self._on_size is not None:
            self._on_size(choice)
        self.redraw()

    def grid_px(self) -> int:
        try:
            return int(self.grid_var.get().split()[0])
        except (ValueError, IndexError):
            return DEFAULT_GRID

    def _box(self, key: str) -> Tuple[float, float, float, float]:
        """The box's (left, top, width, height) in logical pixels, from its saved placement."""
        placement = self._get(key)
        size = self.slots[key][1]
        if placement is None:
            return 0.0, 0.0, float(size[0]), float(size[1])
        left, top = rect_from_placement(placement, size, self.screen, self._units())
        return left, top, float(size[0]), float(size[1])

    def _units(self) -> Tuple[float, float]:
        return (layout.BASE_WIDTH / self.screen[0], layout.BASE_HEIGHT / self.screen[1])

    def redraw(self) -> None:
        canvas = self.canvas
        canvas.delete("all")
        step = self.grid_px() * self.scale
        x = 0.0
        while x <= self.WIDTH:
            canvas.create_line(x, 0, x, self.height, fill="#1f2933")
            x += step
        y = 0.0
        while y <= self.height:
            canvas.create_line(0, y, self.WIDTH, y, fill="#1f2933")
            y += step
        canvas.create_line(self.WIDTH / 2, 0, self.WIDTH / 2, self.height, fill="#2b3945", dash=(3, 3))
        canvas.create_line(0, self.height / 2, self.WIDTH, self.height / 2, fill="#2b3945", dash=(3, 3))
        for index, key in enumerate(self.slots):
            left, top, width, height = self._box(key)
            color = self._colors[index % len(self._colors)]
            x0, y0 = left * self.scale, top * self.scale
            canvas.create_rectangle(x0, y0, x0 + width * self.scale, y0 + height * self.scale, outline=color, width=2, fill=color if not self._hidden(key) else "",
                                    stipple="gray25" if not self._hidden(key) else "", tags=("box", key))
            canvas.create_text(x0 + 4, y0 + 3, text=self.slots[key][0], anchor=self._tk.NW, fill="#ffffff", font=("TkDefaultFont", 7), width=max(40, width * self.scale - 6),
                               tags=("box", key))

    def _key_at(self, x: float, y: float) -> Optional[str]:
        items = self.canvas.find_overlapping(x, y, x, y)
        for item in reversed(items):
            tags = self.canvas.gettags(item)
            if "box" in tags:
                return next((t for t in tags if t in self.slots), None)
        return None

    def _press(self, event: Any) -> None:
        key = self._key_at(event.x, event.y)
        if key is None:
            return
        left, top, _w, _h = self._box(key)
        self._drag = (key, event.x / self.scale - left, event.y / self.scale - top)
        self.canvas.tag_raise(key)

    def _move(self, event: Any) -> None:
        if self._drag is None:
            return
        key, dx, dy = self._drag
        _l, _t, width, height = self._box(key)
        left = max(0.0, min(event.x / self.scale - dx, self.screen[0] - width))
        top = max(0.0, min(event.y / self.scale - dy, self.screen[1] - height))
        self.canvas.delete(key)
        index = list(self.slots).index(key)
        color = self._colors[index % len(self._colors)]
        x0, y0 = left * self.scale, top * self.scale
        self.canvas.create_rectangle(x0, y0, x0 + width * self.scale, y0 + height * self.scale, outline=color, width=2, fill=color, stipple="gray25", tags=("box", key))
        self.canvas.create_text(x0 + 4, y0 + 3, text=self.slots[key][0], anchor=self._tk.NW, fill="#ffffff", font=("TkDefaultFont", 7),
                                width=max(40, width * self.scale - 6), tags=("box", key))
        self._last = (key, left, top, width, height)

    def _release(self, event: Any) -> None:
        if self._drag is None:
            return
        key, _dx, _dy = self._drag
        self._drag = None
        last = getattr(self, "_last", None)
        if not last or last[0] != key:
            return
        _k, left, top, width, height = last
        edge, grid = (EDGE_SNAP, self.grid_px()) if self.snap_var.get() else (0, 1)
        placement = placement_from_rect(left, top, width, height, self.screen, grid, edge)
        self._put(key, placement)
        self.status.set(f"{self.slots[key][0]}: {describe(placement)}")
        self._last = None
        self.redraw()
