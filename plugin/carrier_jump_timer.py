"""Fleet carrier jump countdown: the pure part. A `CarrierJumpRequest` journal event names the destination and a
`DepartureTime`; this keeps the planned jump, says how long is left, and says when an alert is due (once each at 10 minutes,
5 minutes, 1 minute and at departure). Nothing here touches Tk, the overlay or the clock except through `now`, so it is
tested without any of them.

What the journal gives, and its limits: the request (system, body and departure time), a cancellation, and, when the commander
is aboard, the `CarrierJump` that completes it. A request is only known if the game wrote it while WNTB could see it, so
`recover` reads it back from the newest journals when WNTB starts. Anything the journal does not say (who scheduled the jump when
it was not this commander, or a jump that was scheduled with the game closed) is simply not shown."""

from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Dict, Iterable, List, Mapping, Optional

EVENTS = ("CarrierJumpRequest", "CarrierJumpCancelled", "CarrierJump")

ALERT_SECONDS = (600, 300, 60, 0)   # alerts fire as the time left falls to each of these
MAX_SYSTEM_CHARS = 24               # a longer system or body name is clipped, so the display's line cannot grow without limit
MAX_BODY_CHARS = 14
AFTER_DEPARTURE_S = 90              # how long "departing" is shown past the departure time before the display clears
STALE_S = AFTER_DEPARTURE_S         # a request whose departure is already this far past is old news (read back from an old journal)


@dataclass(frozen=True)
class PlannedJump:
    system: str
    body: str
    departs: float      # epoch seconds


def parse_departure(text: Any) -> Optional[float]:
    """Epoch seconds from the journal's `2026-10-13T14:30:00Z` form, or None when it is missing or not a time."""
    if not isinstance(text, str) or not text.strip():
        return None
    value = text.strip().replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.timestamp()


def _clip(text: str, limit: int) -> str:
    return text if len(text) <= limit else text[:max(0, limit - 1)].rstrip() + "…"


def format_remaining(seconds: float) -> str:
    """`14:32` for under an hour, `1:02:05` for longer, `0:00` once it has passed."""
    total = max(0, int(seconds + 0.999))   # round up: the display should not say 0:00 while a second is left
    hours, rest = divmod(total, 3600)
    minutes, secs = divmod(rest, 60)
    return f"{hours}:{minutes:02d}:{secs:02d}" if hours else f"{minutes}:{secs:02d}"


class CarrierJumpTimer:
    """The planned jump, and which alerts have already been given for it."""

    def __init__(self, now: Callable[[], float] = time.time) -> None:
        self._now = now
        self.jump: Optional[PlannedJump] = None
        self._fired: set = set()

    def handle_event(self, entry: Mapping[str, Any]) -> bool:
        """Apply one journal event. True when the planned jump changed (set, replaced or cleared)."""
        event = entry.get("event")
        if event == "CarrierJumpRequest":
            departs = parse_departure(entry.get("DepartureTime"))
            system = str(entry.get("SystemName") or "").strip()
            if departs is None or not system or departs < self._now() - STALE_S:
                return False
            new = PlannedJump(system, str(entry.get("Body") or "").strip(), departs)
            if new == self.jump:
                return False
            self.jump, self._fired = new, set()
            return True
        if event in ("CarrierJumpCancelled", "CarrierJump") and self.jump is not None:
            self.jump, self._fired = None, set()
            return True
        return False

    def replay(self, entries: Iterable[Mapping[str, Any]]) -> bool:
        """Apply events read back from the journal, oldest first; True when a jump is planned afterwards."""
        for entry in entries:
            self.handle_event(entry)
        return self.jump is not None

    def remaining(self) -> Optional[float]:
        return None if self.jump is None else self.jump.departs - self._now()

    def active(self) -> bool:
        """A jump is planned and not long past its departure time."""
        left = self.remaining()
        return left is not None and left > -AFTER_DEPARTURE_S

    def expire(self) -> bool:
        """Drop a jump that is long past its departure (nothing was logged to end it). True when it did."""
        if self.jump is not None and not self.active():
            self.jump, self._fired = None, set()
            return True
        return False

    def due_alert(self) -> Optional[int]:
        """The alert threshold (seconds left) to give now, once, or None. Several thresholds crossed at once (the game started
        with 3 minutes left) give only the smallest one that has been crossed."""
        left = self.remaining()
        if left is None:
            return None
        crossed = [t for t in ALERT_SECONDS if left <= t and t not in self._fired]
        if not crossed:
            return None
        self._fired.update(t for t in ALERT_SECONDS if left <= t)
        return min(crossed)

    def line(self) -> Optional[str]:
        """The text for the display, or None when nothing is planned."""
        if self.jump is None or not self.active():
            return None
        left = self.remaining() or 0
        where = _clip(self.jump.system, MAX_SYSTEM_CHARS)
        if self.jump.body and self.jump.body != self.jump.system:
            where += f" ({_clip(self.jump.body, MAX_BODY_CHARS)})"
        if left <= 0:
            return f"Carrier departing for {where}"
        return f"Carrier jumps to {where} in {format_remaining(left)}"


def alert_text(threshold: int) -> str:
    return "Carrier jump departing now" if threshold <= 0 else f"Carrier jump in {threshold // 60} minute{'s' if threshold >= 120 else ''}"


def recover(timer: CarrierJumpTimer, since_epoch: float, folder: Optional[str] = None) -> bool:
    """Read a planned jump back from the journal files modified since `since_epoch` (the game may have been restarted after the
    request). A missing folder or unreadable file gives nothing, never an error."""
    from . import journal_files
    wanted = journal_files.event_pattern(*EVENTS)
    entries: List[Dict[str, Any]] = []
    for path in journal_files.files_modified_since(since_epoch, folder):
        entries.extend(journal_files.read_events(path, wanted))
    return timer.replay(entries)
