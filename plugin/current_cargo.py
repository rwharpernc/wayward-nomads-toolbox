"""What is in the commander's hold right now, by commodity, for mission progress ("36/60 held" for a source-and-return mission).

EDMC keeps the live hold in its state (`state["Cargo"]`, commodity name in lower case to tonnes) and hands that state to every journal event, so the Missions
feature passes it here on each event. `changed` is told when the hold differs from last time, so the Missions window and overlay card can redraw as you buy.
Nothing is stored or sent."""
from __future__ import annotations

from typing import Any, Dict, Mapping

from .notifier import Notifier

changed = Notifier()
_held: Dict[str, int] = {}


def update(state: Any) -> None:
    """Take the hold from EDMC's state (ignored when it has none)."""
    global _held
    cargo = state.get("Cargo") if isinstance(state, Mapping) else None
    if not isinstance(cargo, Mapping):
        return
    now = {str(name).lower(): int(count) for name, count in cargo.items() if isinstance(count, (int, float)) and count > 0}
    if now != _held:
        _held = now
        changed.notify()


def held() -> Dict[str, int]:
    return dict(_held)
