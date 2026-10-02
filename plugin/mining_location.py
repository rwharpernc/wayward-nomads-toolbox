"""
The commander's current system name - nothing more. EDMC's own
`journal_entry` hook already resolves this for every event (the `system`
parameter, forwarded through the feature-module contract), so there's no
journal-event parsing needed here, unlike mining_surface.py's current-body
tracking (which genuinely needs `ApproachBody`/`LeaveBody` since no such
parameter exists for that).

Kept separate from mining_surface.py's location tracking rather than
merged into it: that module's `current_system`/`current_body` are
Rhino/Surface-Mining-scoped (body-clearing on LeaveBody, feeding the
hotspot quick-add's prefill), while this is a plain "where am I right
now" used by anything that just needs a reference system - currently
mining_spansh_client.py's nearby-hotspot search (Space Mining page).
"""
from typing import Optional

_current_system: Optional[str] = None


def set_current_system(system: Optional[str]) -> None:
    global _current_system
    if system:
        _current_system = system


def current_system() -> Optional[str]:
    return _current_system
