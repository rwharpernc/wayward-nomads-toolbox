"""A list-style overlay card: lines of text over a two-column list, in one box, every line starting at the card's left padding.

Used by the Route overlay, the System targets card and the Body info card. A `Card` is plain data (header lines, rows of (left text, right
text, color role), an optional footer); a `CardLayout` knows where one card kind is drawn, how wide and tall it must be for its text (the overlay
cannot measure text, so widths come from `overlay_style.Look`'s estimates), and how to send or clear it. The box has a fixed top and width and grows
downward as lines are added, so where it sits on the screen (the global Overlay Placement setting) never changes with what it says. Pure: no Tk, no
EDMC.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional, Tuple

from .overlay_style import CARD_PAD_X, CARD_PAD_Y, LEGACY, Look

Line = Tuple[str, str]            # (text, color role)
Row = Tuple[str, str, str]        # (left text, right text, color role)
LINE_GAP = 4                      # pixels between lines
COLUMN_GAP = 14                   # pixels between the two columns


@dataclass(frozen=True)
class Card:
    header: Tuple[Line, ...] = ()
    rows: Tuple[Row, ...] = ()
    footer: Optional[Line] = None

    def __bool__(self) -> bool:
        return bool(self.header or self.rows)

    def line_count(self) -> int:
        return len(self.header) + len(self.rows) + (1 if self.footer else 0)


def cut(text: str, limit: int) -> str:
    """`text` shortened with an ellipsis to at most `limit` characters."""
    return text if len(text) <= limit else text[:max(1, limit - 1)].rstrip() + "…"


class CardLayout:
    """Where and how one kind of card is drawn. `prefix` starts every overlay id (so one Plugin Group covers the card); `x` and `y` are the
    fixed draw origin of the first line; `name_chars` and `tag_chars` size the two columns; `sample_tag` is the widest right-hand text; and
    `sample_lines` is the height placement assumes."""

    def __init__(self, prefix: str, x: int, y: int, max_header: int, max_rows: int, name_chars: int, tag_chars: int, sample_tag: str,
                 sample_lines: int) -> None:
        self.prefix, self.x, self.y = prefix, x, y
        self.name_chars, self.tag_chars, self.sample_tag, self.sample_lines = name_chars, tag_chars, sample_tag, sample_lines
        self.card_id = f"{prefix}card"
        self.header_ids = tuple(f"{prefix}h{i}" for i in range(max_header))
        self.name_ids = tuple(f"{prefix}n{i}" for i in range(max_rows))
        self.tag_ids = tuple(f"{prefix}t{i}" for i in range(max_rows))
        self.foot_id = f"{prefix}foot"

    # geometry --------------------------------------------------------------------------------------------------------
    def name_width(self, look: Look) -> int:
        return look.measured_width("X" * self.name_chars)

    def inner_width(self, look: Look) -> int:
        return self.name_width(look) + COLUMN_GAP + look.measured_width(self.sample_tag)

    def fit(self, text: str, look: Look, limit_px: int) -> str:
        """`text` cut with an ellipsis until it fits the card's width at the look's size."""
        while len(text) > 1 and look.measured_width(text) > limit_px:
            text = text[:-2].rstrip() + "…"
        return text

    def size(self, look: Look, lines: int) -> Tuple[int, int]:
        pad_x, pad_y = look.pad_x(CARD_PAD_X), look.pad_y(CARD_PAD_Y)
        return self.inner_width(look) + 2 * pad_x, 2 * pad_y + lines * look.line_px("normal") + max(0, lines - 1) * LINE_GAP

    def block_rect(self, look: Look = LEGACY, card: Optional[Card] = None) -> Tuple[int, int, int, int]:
        """(left, top, width, height) of the card as `render` draws it; placement uses a card of `sample_lines` lines when none is given."""
        width, height = self.size(look, self.sample_lines if card is None else card.line_count())
        return self.x - look.pad_x(CARD_PAD_X), self.y - look.pad_y(CARD_PAD_Y), width, height

    # drawing ---------------------------------------------------------------------------------------------------------
    def render(self, card: Card, client: Any, look: Look = LEGACY, ttl: int = 4) -> None:
        """Draws the card, or clears it when it is empty. Raises on an overlay failure; the live path swallows it and a Settings test reports it."""
        if not card:
            self.clear(client)
            return
        width, height = self.size(look, card.line_count())
        left, top = self.x - look.pad_x(CARD_PAD_X), self.y - look.pad_y(CARD_PAD_Y)
        client.send_shape(self.card_id, "rect", look.color("border"), look.color("fill"), left, top, width, height, ttl=ttl, thickness=2)
        step = look.line_px("normal") + LINE_GAP
        size = look.size("normal")
        tag_x = self.x + self.name_width(look) + COLUMN_GAP
        inner = self.inner_width(look)
        row = 0
        for index, msg_id in enumerate(self.header_ids):
            if index < len(card.header):
                text, role = card.header[index]
                client.send_message(msg_id, self.fit(text, look, inner), look.color(role), self.x, self.y + row * step, ttl=ttl, size=size)
                row += 1
            else:
                client.send_message(msg_id, "", "white", self.x, self.y, ttl=1)
        for index, (name_id, tag_id) in enumerate(zip(self.name_ids, self.tag_ids)):
            if index < len(card.rows):
                name, tag, role = card.rows[index]
                y = self.y + row * step
                client.send_message(name_id, name, look.color("text" if role == "muted" else role), self.x, y, ttl=ttl, size=size)
                client.send_message(tag_id, tag, look.color(role), tag_x, y, ttl=ttl, size=size)
                row += 1
            else:
                client.send_message(name_id, "", "white", self.x, self.y, ttl=1)
                client.send_message(tag_id, "", "white", self.x, self.y, ttl=1)
        if card.footer:
            text, role = card.footer
            client.send_message(self.foot_id, self.fit(text, look, inner), look.color(role), self.x, self.y + row * step, ttl=ttl, size=size)
        else:
            client.send_message(self.foot_id, "", "white", self.x, self.y, ttl=1)

    def clear(self, client: Any) -> None:
        left, top, _w, _h = self.block_rect(LEGACY)
        client.send_shape(self.card_id, "rect", "", "", left, top, 0, 0, ttl=1)
        for msg_id in self.header_ids + self.name_ids + self.tag_ids + (self.foot_id,):
            client.send_message(msg_id, "", "white", self.x, self.y, ttl=1)


class LiveCard:
    """Keeps one card on the screen: `refresh` builds the card and draws it when it changed, or every `resend` seconds so it does not expire
    between changes, and clears it when it becomes empty. `build`, `enabled`, `draw` and `now` are injected so the timing is tested without an overlay."""

    def __init__(self, build: Any, enabled: Any, draw: Any, now: Any = None, resend: float = 3.0) -> None:
        import time
        self._build, self._enabled, self._draw = build, enabled, draw
        self._now = now or time.time
        self._resend = resend
        self._last: Optional[Card] = None
        self._last_sent = 0.0

    def refresh(self) -> None:
        if not self._enabled():
            return
        card = self._build()
        now = self._now()
        if card == self._last and now - self._last_sent < self._resend:
            return
        if not card and not self._last:
            self._last = card
            return
        self._last, self._last_sent = card, now
        self._draw(card)

    def showing(self) -> bool:
        return bool(self._enabled() and self._build())


class Ticker:
    """A daemon thread that calls `tick` every `interval` seconds until `stop`, swallowing (and logging) any error so one bad tick never ends it."""

    def __init__(self, name: str, tick: Any, interval: float = 1.0, log: Any = None) -> None:
        import threading
        self._name, self._tick, self._interval, self._log = name, tick, interval, log
        self._stop = threading.Event()
        self._thread: Optional[Any] = None
        self._threading = threading

    def start(self) -> None:
        self._stop.clear()
        if self._thread is None or not self._thread.is_alive():
            self._thread = self._threading.Thread(target=self._run, name=self._name, daemon=True)
            self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    def _run(self) -> None:
        while not self._stop.wait(self._interval):
            try:
                self._tick()
            except Exception:
                if self._log is not None:
                    self._log.debug("%s tick failed", self._name, exc_info=True)
