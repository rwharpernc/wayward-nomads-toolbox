"""A list-style overlay card: lines of text over a two-column list, in one box, every line starting at the card's left padding.

Used by the Route overlay, the System targets card and the Body info card. A `Card` is plain data (header lines, rows of (left text, right
text, color role), an optional footer); a `CardLayout` knows where one card kind is drawn, how wide and tall it must be for its text (the overlay
cannot measure text, so widths come from `overlay_style.Look`'s estimates), and how to send or clear it. The box has a fixed top and width and grows
downward as lines are added, so where it sits on the screen (the global Overlay Placement setting) never changes with what it says. Pure: no Tk, no
EDMC.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, List, Optional, Tuple

from .overlay_style import CARD_PAD_X, CARD_PAD_Y, LEGACY, Look

Line = Tuple[str, str]            # (text, color role)
Row = Tuple[str, str, str]        # (left text, right text, color role)
LINE_GAP = 4                      # pixels between lines
COLUMN_GAP = 14                   # pixels between the two columns


@dataclass(frozen=True)
class Card:
    """What one card says. `title` (with an optional right-hand `badge` and a 0-1 `progress` bar under it) is the heading; `header` lines come
    next, then `rows`, then the `footer`. A row whose right-hand text is empty and whose role is "title" is a section label. A row's left text may
    hold a tab (what follows it is drawn muted in a second column: a class tag, a distance) and newlines (each later line is a detail line drawn
    under the row across the card's width and wrapped, so a long list is shown whole). In "column" align a long right-hand text wraps within its column."""
    header: Tuple[Line, ...] = ()
    rows: Tuple[Row, ...] = ()
    footer: Optional[Line] = None
    title: Optional[Line] = None
    badge: str = ""
    progress: Optional[float] = None
    headline: Optional[Line] = None      # a large line under the title, with `dots` (filled or empty circles) before it
    dots: Tuple[bool, ...] = ()
    align: str = "right"        # "right": a row's right-hand text ends at the card's right edge; "column": it starts in a second column (long values)

    def __bool__(self) -> bool:
        return bool(self.header or self.rows or self.title or self.headline)

    def line_count(self) -> int:
        return len(self.header) + len(self.rows) + (1 if self.footer else 0) + (1 if self.title else 0)


def cut(text: str, limit: int) -> str:
    """`text` shortened with an ellipsis to at most `limit` characters."""
    return text if len(text) <= limit else text[:max(1, limit - 1)].rstrip() + "…"


ACCENT_W = 4                      # the width the colored bar down a card's left edge used to have; cards are plain panels now, and it is cleared when a card is
BAR_H = 4                         # the progress bar
RULE_GAP = 6                      # space above and below a divider
SECTION_GAP = 4                   # extra space above a section label
TAB_CHARS = 7                     # width of the first column of a row that has a second (muted) part
MAX_TEXTS = 64                    # overlay ids reserved for text and for shapes
MAX_SHAPES = 12
CHROME_PX = 22                    # what the title row, bar and divider add to the height placement assumes


class CardLayout:
    """Where and how one kind of card is drawn. `prefix` starts every overlay id (so one Plugin Group covers the card); `x` and `y` are the
    fixed draw origin of the first line; `name_chars` sizes the left column and `sample_tag` is the widest right-hand text (together they fix the
    card's width); `sample_lines` is the height placement assumes; and `accent` is the color role of the bar down the left edge."""

    def __init__(self, prefix: str, x: int, y: int, max_header: int, max_rows: int, name_chars: int, tag_chars: int, sample_tag: str,
                 sample_lines: int, accent: str = "border") -> None:
        self.prefix, self.x, self.y = prefix, x, y
        self.name_chars, self.tag_chars, self.sample_tag, self.sample_lines = name_chars, tag_chars, sample_tag, sample_lines
        self.accent = accent
        self.card_id = f"{prefix}card"
        self._used_texts = 0
        self._used_shapes = 0

    # geometry --------------------------------------------------------------------------------------------------------
    def name_width(self, look: Look) -> int:
        return look.measured_width("X" * self.name_chars)

    def inner_width(self, look: Look) -> int:
        return self.name_width(look) + COLUMN_GAP + look.measured_width(self.sample_tag)

    def fit(self, text: str, look: Look, limit_px: int, base: str = "normal") -> str:
        """`text` cut with an ellipsis until it fits `limit_px` at the look's size."""
        while len(text) > 1 and look.measured_width(text, base) > limit_px:
            text = text[:-2].rstrip() + "…"
        return text

    def wrap(self, text: str, look: Look, limit_px: int) -> List[str]:
        """`text` broken at spaces into lines that each fit `limit_px`, so a long message continues on the next line instead of being cut."""
        lines: List[str] = []
        current = ""
        for word in text.split():
            trial = f"{current} {word}".strip()
            if current and look.measured_width(trial) > limit_px:
                lines.append(current)
                current = word
            else:
                current = trial
        if current:
            lines.append(current)
        return [self.fit(line, look, limit_px) for line in lines] or [""]

    def size(self, look: Look, lines: int) -> Tuple[int, int]:
        pad_x, pad_y = look.pad_x(CARD_PAD_X), look.pad_y(CARD_PAD_Y)
        return self.inner_width(look) + 2 * pad_x, 2 * pad_y + lines * look.line_px("normal") + max(0, lines - 1) * LINE_GAP + CHROME_PX

    def block_rect(self, look: Look = LEGACY, card: Optional[Card] = None) -> Tuple[int, int, int, int]:
        """(left, top, width, height) of the card as `render` draws it; placement uses a card of `sample_lines` lines when none is given."""
        left, top = self.x - look.pad_x(CARD_PAD_X), self.y - look.pad_y(CARD_PAD_Y)
        if card is None:
            width, height = self.size(look, self.sample_lines)
        else:
            width, height = self.plan(card, look)[2:]
        return left, top, width, height

    # the plan: every shape and text, with its place ------------------------------------------------------------------
    def plan(self, card: Card, look: Look = LEGACY) -> Tuple[List[tuple], List[tuple], int, int]:
        """(shapes, texts, width, height). A shape is (kind, color, fill, x, y, w, h) and a text is (text, color role, x, y, size), with y relative to
        the card's first line. Built before anything is sent, so the card's height is known from what it says, wrapped lines included."""
        pad_x, pad_y = look.pad_x(CARD_PAD_X), look.pad_y(CARD_PAD_Y)
        inner = self.inner_width(look)
        step = look.line_px("normal") + LINE_GAP
        size = look.size("normal")
        x = self.x
        y = 0
        shapes: List[tuple] = []
        texts: List[tuple] = []
        rule = look.color("faint")

        def divider(at: int) -> None:
            shapes.append(("rect", rule, rule, x, at, inner, 1))

        if card.title:
            title, role = card.title
            badge = card.badge
            badge_w = look.measured_width(badge) + COLUMN_GAP if badge else 0
            base = "large" if look.measured_width(title, "large") <= inner - badge_w else "normal"
            texts.append((self.fit(title, look, inner - badge_w, base), role, x, y, look.size(base)))
            if badge:
                texts.append((badge, "muted", x + inner - look.measured_width(badge), y + look.line_px(base) - look.line_px("normal"), size))
            y += look.line_px(base) + 2
            if card.progress is not None:
                fraction = max(0.0, min(1.0, card.progress))
                y += 2
                shapes.append(("rect", look.color("faint"), look.color("faint"), x, y, inner, BAR_H))
                if fraction > 0:
                    shapes.append(("rect", look.color(role), look.color(role), x, y, max(2, int(inner * fraction)), BAR_H))
                y += BAR_H + RULE_GAP
            else:
                y += RULE_GAP - 2
            if card.header or card.rows or card.footer:
                divider(y)
                y += 1 + RULE_GAP
        if card.headline:
            text, role = card.headline
            dot = 14
            dots_w = len(card.dots) * (dot + 6) + (4 if card.dots else 0)
            for number, filled in enumerate(card.dots):
                cx = x + number * (dot + 6)
                shapes.append(("circle", look.color(role), look.color(role) if filled else "#00000000", cx, y + 6, dot, dot))
            base = "large" if look.measured_width(text, "large") <= inner - dots_w else "normal"
            for line in ([self.fit(text, look, inner - dots_w, base)] if base == "large" else self.wrap(text, look, inner - dots_w)):
                texts.append((line, role, x + dots_w, y, look.size(base)))
                y += look.line_px(base) + 2
            y += 2
        for text, role in card.header:
            for line in self.wrap(text, look, inner):
                texts.append((line, role, x, y, size))
                y += step
        first = True
        tab_px = look.measured_width("X" * TAB_CHARS)
        for left, right, role in card.rows:
            if not right and role == "title":                    # a section label
                if not first or card.header or card.title:
                    y += SECTION_GAP
                texts.append((left.upper(), "header", x, y, size))
                y += step
                first = False
                continue
            first = False
            head, *details = left.split("\n")
            name, _tab, extra = head.partition("\t")
            texts.append((name, "text", x, y, size))
            if extra:
                texts.append((extra, "muted", x + tab_px, y, size))
            if right and card.align == "right":
                texts.append((right, role, x + inner - look.measured_width(right), y, size))
                y += step
            elif right:
                column_x = x + self.name_width(look) + COLUMN_GAP
                for line in self.wrap(right, look, inner - (column_x - x)):
                    texts.append((line, role, column_x, y, size))
                    y += step
            else:
                y += step
            for detail in details:
                for line in self.wrap(detail, look, inner):
                    texts.append((line, role if role != "text" else "muted", x, y, size))
                    y += step
        if card.footer:
            text, role = card.footer
            divider(y)
            y += 1 + RULE_GAP
            for line in self.wrap(text, look, inner):
                texts.append((line, role, x, y, size))
                y += step
        height = max(y - LINE_GAP, look.line_px("normal")) + 2 * pad_y
        return shapes, texts, inner + 2 * pad_x, height

    # drawing ---------------------------------------------------------------------------------------------------------
    def render(self, card: Card, client: Any, look: Look = LEGACY, ttl: int = 4) -> None:
        """Draws the card, or clears it when it is empty. Raises on an overlay failure; the live path swallows it and a Settings test reports it."""
        if not card:
            self.clear(client)
            return
        shapes, texts, width, height = self.plan(card, look)
        shapes, texts = shapes[:MAX_SHAPES], texts[:MAX_TEXTS]
        left, top = self.x - look.pad_x(CARD_PAD_X), self.y - look.pad_y(CARD_PAD_Y)
        client.send_shape(self.card_id, "rect", look.color("fill"), look.color("fill"), left, top, width, height, ttl=ttl, thickness=1)   # a plain panel: no outline, no edge bar
        for index, (kind, color, fill, sx, sy, sw, sh) in enumerate(shapes):
            if kind == "circle":
                client.send_circle(f"{self.prefix}s{index}", color, fill, sx + sw // 2, self.y + sy + sh // 2, sw // 2, ttl=ttl, thickness=2)
            else:
                client.send_shape(f"{self.prefix}s{index}", kind, color, fill, sx, self.y + sy, sw, sh, ttl=ttl, thickness=1)
        for index in range(len(shapes), self._used_shapes):
            client.send_shape(f"{self.prefix}s{index}", "rect", "", "", left, top, 0, 0, ttl=1)
        self._used_shapes = len(shapes)
        for index, (text, role, tx, ty, tsize) in enumerate(texts):
            client.send_message(f"{self.prefix}x{index}", text, look.color(role), tx, self.y + ty, ttl=ttl, size=tsize)
        for index in range(len(texts), self._used_texts):
            client.send_message(f"{self.prefix}x{index}", "", "white", self.x, self.y, ttl=1)
        self._used_texts = len(texts)

    def clear(self, client: Any) -> None:
        left, top, _w, _h = self.block_rect(LEGACY)
        for msg_id in (self.card_id, f"{self.prefix}bar") + tuple(f"{self.prefix}s{i}" for i in range(self._used_shapes)):
            client.send_shape(msg_id, "rect", "", "", left, top, 0, 0, ttl=1)
        for index in range(self._used_texts):
            client.send_message(f"{self.prefix}x{index}", "", "white", self.x, self.y, ttl=1)
        self._used_texts = self._used_shapes = 0


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
