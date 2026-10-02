"""Canvas map for WNTB windows: coverage discs, hotspot markers, your
position, a metre grid, zoom 1x/2x/4x and click-to-select. Pure geometry
in metres east/north of the map centre - the caller projects lat/lon (see
mining_coverage_render._project) so this module needs no body radius.

Markers carry state by shape, not hue (colour-blind safe): live hotspot =
filled dot, depleted = hollow ring, selected = amber halo, you = blue dot
with a white outline."""
from __future__ import annotations

import tkinter as tk
from dataclasses import dataclass
from typing import Callable, Optional, Sequence

from . import palette as P
from . import style

BASE_VIEW_M = 6000.0     # half-width shown at 1x (matches the in-panel minimap)
ZOOMS = (1, 2, 4)
GRID_M = 1000.0
SCAN_RADIUS_M = 1000.0   # coverage disc radius (mining_coverage.SCAN_RADIUS_M)
HIT_PX = 9


@dataclass
class MapMarker:
    key: str
    east_m: float
    north_m: float
    label: str = ""
    depleted: bool = False


class MapView(tk.Frame):
    def __init__(self, parent: tk.Misc, size: int = 300,
                 on_select: Optional[Callable[[str], None]] = None) -> None:
        super().__init__(parent, bg=P.CARD)
        self._size = size
        self._on_select = on_select
        self._zoom_index = 0
        self._coverage: Sequence[tuple[float, float]] = ()
        self._markers: Sequence[MapMarker] = ()
        self._you: Optional[tuple[float, float]] = None
        self._selected: Optional[str] = None
        self._hits: list[tuple[float, float, str]] = []
        self._cx = self._cy = size / 2
        self._message: Optional[str] = None

        bar = tk.Frame(self, bg=P.CARD)
        bar.pack(fill="x", pady=(0, 4))
        tk.Label(bar, text="MAP", fg=P.MUTED, bg=P.CARD,
                 font=style.font(P.FONT_SMALL)).pack(side="left")
        self._zoom_buttons: list[tk.Label] = []
        for index in reversed(range(len(ZOOMS))):
            button = tk.Label(bar, text=f"{ZOOMS[index]}x", fg=P.MUTED, bg=P.CARD, padx=7,
                              cursor="hand2", font=style.font(P.FONT_SMALL))
            button.pack(side="right")
            button.bind("<Button-1>", lambda _e, i=index: self.set_zoom(i))
            self._zoom_buttons.append(button)
        self._zoom_buttons.reverse()  # index order: 1x, 2x, 4x
        self._canvas = tk.Canvas(self, width=size, height=size, bg=P.MAP_BG,
                                 highlightthickness=1, highlightbackground=P.LINE)
        self._canvas.pack(fill="both", expand=True)
        self._canvas.bind("<Button-1>", self._on_click)
        self._canvas.bind("<Configure>", lambda _e: self.redraw())
        self.set_zoom(0)

    # --- data ------------------------------------------------------------
    def set_data(self, coverage: Sequence[tuple[float, float]], markers: Sequence[MapMarker],
                 you: Optional[tuple[float, float]] = None) -> None:
        self._coverage, self._markers, self._you = coverage, markers, you
        self.redraw()

    def set_message(self, text: Optional[str]) -> None:
        """Replaces the map with a centred note (e.g. "No body radius known")."""
        self._message = text
        self.redraw()

    def select(self, key: Optional[str]) -> None:
        self._selected = key
        self.redraw()

    def set_zoom(self, index: int) -> None:
        self._zoom_index = index
        for i, button in enumerate(self._zoom_buttons):
            button.configure(fg=P.ACCENT if i == index else P.MUTED)
        self.redraw()

    # --- drawing ---------------------------------------------------------
    def _to_px(self, east_m: float, north_m: float, scale: float, _half: float) -> tuple[float, float]:
        return self._cx + east_m * scale, self._cy - north_m * scale

    def redraw(self) -> None:
        canvas = self._canvas
        canvas.delete("all")
        side = min(canvas.winfo_width(), canvas.winfo_height())
        if side < 20:
            side = self._size
        if self._message:
            canvas.create_text(canvas.winfo_width() / 2, canvas.winfo_height() / 2,
                               text=self._message, fill=P.MUTED, width=max(side - 40, 60),
                               justify="center", font=style.font(P.FONT_BODY))
            return
        half = side / 2
        width, height = max(canvas.winfo_width(), side), max(canvas.winfo_height(), side)
        self._cx, self._cy = width / 2, height / 2   # map centre; the view fills the whole canvas
        scale = side / (2 * BASE_VIEW_M / ZOOMS[self._zoom_index])

        step = GRID_M * scale
        if step >= 6:
            offset = 0.0
            while offset <= max(width, height) / 2:
                for coord in {self._cx + offset, self._cx - offset}:
                    canvas.create_line(coord, 0, coord, height, fill=P.MAP_GRID)
                for coord in {self._cy + offset, self._cy - offset}:
                    canvas.create_line(0, coord, width, coord, fill=P.MAP_GRID)
                offset += step

        radius = SCAN_RADIUS_M * scale
        for east, north in self._coverage:
            x, y = self._to_px(east, north, scale, half)
            canvas.create_oval(x - radius, y - radius, x + radius, y + radius,
                               fill=P.MAP_COVERAGE, outline="")

        self._hits = []
        for marker in self._markers:
            x, y = self._to_px(marker.east_m, marker.north_m, scale, half)
            if not (0 <= x <= width and 0 <= y <= height):
                continue
            self._hits.append((x, y, marker.key))
            if marker.key == self._selected:
                canvas.create_oval(x - 9, y - 9, x + 9, y + 9, outline=P.ACCENT, width=2)
            if marker.depleted:
                canvas.create_oval(x - 4, y - 4, x + 4, y + 4, outline=P.MAP_DEPLETED, width=2)
            else:
                canvas.create_oval(x - 4, y - 4, x + 4, y + 4, fill=P.MAP_HOTSPOT, outline="")
            if marker.label:
                canvas.create_text(x + 8, y - 8, text=marker.label, fill=P.TEXT, anchor="w",
                                   font=style.font(P.FONT_SMALL))

        if self._you is not None:
            x, y = self._to_px(self._you[0], self._you[1], scale, half)
            canvas.create_oval(x - 5, y - 5, x + 5, y + 5, fill=P.INFO, outline="#ffffff", width=1)

        canvas.create_text(self._cx, 10, text="N", fill=P.MUTED, font=style.font(P.FONT_SMALL))
        canvas.create_text(8, height - 10, text=f"{int(GRID_M)} m grid", fill=P.FAINT, anchor="w",
                           font=style.font(P.FONT_SMALL))

    def _on_click(self, event: tk.Event) -> None:
        best, best_distance = None, float(HIT_PX)
        for x, y, key in self._hits:
            distance = ((x - event.x) ** 2 + (y - event.y) ** 2) ** 0.5
            if distance <= best_distance:
                best, best_distance = key, distance
        if best is not None and self._on_select:
            self._on_select(best)
