"""The scene WNTB's built-in overlay draws: every text, rectangle, circle and line currently on the screen, each with the moment it runs out.

WNTB's overlay features send the overlay small JSON payloads (`overlay.OverlayClient`): a text message, or a "rect", "circle" or "vect" shape, each with an `id` and a `ttl` in
seconds. Sending the same id again replaces what it drew, and a payload that draws nothing (an empty text, a rectangle of no size, a circle with no color, an empty line) removes it, which is
how a feature clears something before its ttl runs out. This module keeps that state for the built-in overlay, with no drawing and no Windows in it, so it is tested without a game:

- `apply(payload)` takes a payload as the features send it;
- `items()` is what is on the screen now, in drawing order: rectangles first, then circles and lines, then text, each group in the order its ids first appeared. Text is therefore
  always above every panel, whatever order the features sent them in (a panel that expired and came back used to cover the text on top of it);
- `version` goes up whenever the picture would change, so the window repaints only then, and `next_change()` says when something will next run out.

Positions are canvas units (a 1280 x 960 canvas stretched over the window) and sizes are logical pixels, the conventions `overlay_layout.py` describes; turning them into real pixels
is `overlay_raster.py`'s job.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, replace
from typing import Any, Callable, Dict, List, Mapping, Optional, Tuple

TEXT, RECT, CIRCLE, VECT = "text", "rect", "circle", "vect"
_LAYER = {RECT: 0, CIRCLE: 1, VECT: 1, TEXT: 2}
DEFAULT_TTL = 4.0
MAX_ITEMS = 1500


@dataclass(frozen=True)
class Item:
    id: str
    kind: str
    expires: float
    x: float = 0.0
    y: float = 0.0
    w: float = 0.0              # rect: width and height in logical pixels
    h: float = 0.0
    radius: float = 0.0         # circle: radius in logical pixels
    color: str = ""             # "#RRGGBB", "#AARRGGBB" or a color name
    fill: str = ""
    text: str = ""
    size: str = "normal"
    thickness: int = 1
    corner: float = 0.0         # rect: corner radius in logical pixels (0 is square)
    points: Tuple[Tuple[float, float, str, str, str], ...] = ()      # vect: (x, y, color, marker, text) for each point


def _number(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def parse(payload: Mapping[str, Any], now: float) -> Optional[Item]:
    """The item a payload draws, or None when it draws nothing (which removes the id) or cannot be understood."""
    ident = payload.get("id")
    if not isinstance(ident, str) or not ident:
        return None
    ttl = _number(payload.get("ttl"), DEFAULT_TTL)
    expires = now + max(ttl, 0.0)
    common = dict(id=ident, expires=expires, x=_number(payload.get("x")), y=_number(payload.get("y")),
                  color=str(payload.get("color") or ""), fill=str(payload.get("fill") or ""), thickness=int(_number(payload.get("thickness"), 1)) or 1)
    if "text" in payload:
        text = str(payload.get("text") or "")
        return Item(kind=TEXT, text=text, size=str(payload.get("size") or "normal"), **common) if text else None
    shape = payload.get("shape")
    if shape == "rect":
        w, h = _number(payload.get("w")), _number(payload.get("h"))
        if w <= 0 or h <= 0 or not (common["color"] or common["fill"]):
            return None
        return Item(kind=RECT, w=w, h=h, corner=max(0.0, _number(payload.get("radius"))), **common)
    if shape == "circle":
        radius = _number(payload.get("radius"))
        if radius < 1 or not (common["color"] or common["fill"]):
            return None
        return Item(kind=CIRCLE, radius=radius, **common)
    if shape == "vect":
        points = []
        for point in payload.get("vector") or []:
            if isinstance(point, Mapping):
                points.append((_number(point.get("x")), _number(point.get("y")), str(point.get("color") or ""), str(point.get("marker") or ""), str(point.get("text") or "")))
        return Item(kind=VECT, points=tuple(points), **common) if points else None
    return None


class Scene:
    """Thread-safe: features send from their own threads while the window thread reads."""

    def __init__(self, clock: Callable[[], float] = time.monotonic) -> None:
        self._clock = clock
        self._lock = threading.Lock()
        self._items: Dict[str, Item] = {}
        self._order: Dict[str, int] = {}
        self._counter = 0
        self.version = 0

    def apply(self, payload: Mapping[str, Any]) -> None:
        item = parse(payload, self._clock())
        ident = payload.get("id")
        with self._lock:
            if item is None:
                if isinstance(ident, str) and self._items.pop(ident, None) is not None:
                    self.version += 1
                return
            before = self._items.get(ident)
            if before is None or replace(before, expires=item.expires) != item:
                self.version += 1
            if ident not in self._order:
                self._counter += 1
                self._order[ident] = self._counter
            self._items[ident] = item          # a resend with the same content only moves the expiry
            if len(self._items) > MAX_ITEMS:
                self._drop_expired_locked(self._clock())

    def _drop_expired_locked(self, now: float) -> bool:
        gone = [ident for ident, item in self._items.items() if item.expires <= now]
        for ident in gone:
            del self._items[ident]
            self._order.pop(ident, None)
        return bool(gone)

    def items(self) -> List[Item]:
        """What is on the screen now, in drawing order. Items that have run out are dropped, which counts as a change."""
        with self._lock:
            if self._drop_expired_locked(self._clock()):
                self.version += 1
            return sorted(self._items.values(), key=lambda item: (_LAYER[item.kind], self._order.get(item.id, 0)))

    def next_change(self) -> Optional[float]:
        """Seconds until the next item runs out, or None when the scene is empty."""
        with self._lock:
            if not self._items:
                return None
            return max(0.0, min(item.expires for item in self._items.values()) - self._clock())

    def clear(self) -> None:
        with self._lock:
            if self._items:
                self.version += 1
            self._items.clear()
            self._order.clear()

    def __len__(self) -> int:
        with self._lock:
            return len(self._items)
