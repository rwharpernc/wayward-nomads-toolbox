"""The "Merits this session" line: Powerplay merits earned since logging in, with a per-hour rate, shown under the
"Credits this session" line in every mode (see ui.py's create_plugin_app).

It owns no data. The merits and the session's start come from Powerplay's own session record
(`powerplay.controller.sessions.current`), so the numbers always agree with the Powerplay panel and the Sessions
window. The line stays hidden until the session has earned a merit, so a commander who does not do Powerplay never
sees it. The hourly rate runs from the session's start to now (not to the last merit), so it falls while you stop
earning, the way the credits rate does.

The text is a pure function so it can be unit-tested without EDMC; Tk is only touched when the label is built.
"""

from __future__ import annotations

import calendar
import time
from typing import Any, Dict, Optional

import tkinter as tk

_MIN_HOURS_FOR_RATE = 0.05  # about three minutes


def hours_since(started_at: Optional[str], now: Optional[float] = None) -> float:
    """Hours from an ISO UTC time stamp (`2026-10-12T08:00:00Z`) to `now` (epoch seconds, default: the clock)."""
    if not started_at:
        return 0.0
    try:
        started = float(calendar.timegm(time.strptime(started_at, "%Y-%m-%dT%H:%M:%SZ")))
    except ValueError:
        return 0.0
    return max(0.0, (time.time() if now is None else now) - started) / 3600.0


def summary_text(merits: int, hours: float) -> str:
    """'Merits this session: +1,234 (+567 merits/hr)'. The rate is left out until the session has run long enough to
    mean something."""
    text = f"Merits this session: +{merits:,}"
    if merits > 0 and hours >= _MIN_HOURS_FOR_RATE:
        text += f" ({merits / hours:+,.0f} merits/hr)"
    return text


def _current_session() -> Optional[Dict[str, Any]]:
    from . import powerplay    # imported lazily: powerplay builds on a lot of EDMC

    sessions = powerplay.controller.sessions
    return sessions.current if sessions is not None else None


class SessionMerits:
    def __init__(self) -> None:
        self._label: Optional[tk.Label] = None

    def merits(self) -> int:
        from .session import total_merits

        session = _current_session()
        return total_merits(session) if session else 0

    def text(self) -> str:
        session = _current_session()
        return summary_text(self.merits(), hours_since(session.get("started_at") if session else None))

    def build(self, parent: tk.Frame, row: int) -> tk.Label:
        """Create the line's label in `parent` at `row` (hidden until there is a merit). It wraps to the panel width like
        every label showing live data, so a long number can't widen EDMC's window."""
        from . import panelkit

        self._label = panelkit.wrap_label(parent, text=self.text(), anchor="w")
        self._label.grid(row=row, column=0, columnspan=3, sticky=tk.W)
        self.refresh()
        return self._label

    def refresh(self) -> None:
        if self._label is None:
            return
        if self.merits() > 0:
            self._label["text"] = self.text()
            self._label.grid()
        else:
            self._label.grid_remove()


controller = SessionMerits()


def build(parent: tk.Frame, row: int) -> tk.Label:
    return controller.build(parent, row)


def handle_event(
    entry: Dict[str, Any], cmdr: str, system: Optional[str], station: Optional[str], state: Dict[str, Any],
) -> None:
    """Runs after Powerplay in load.py's feature order, so a merit gained by this event is already in the session."""
    controller.refresh()
