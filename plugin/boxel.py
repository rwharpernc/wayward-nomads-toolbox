"""
Procedural system name parsing and sequence-walking for boxel surveys.

Elite Dangerous procedurally-generated system names follow the shape:

    <sector words> <LL-L> <mass-code><N1>[-<N2>]

e.g. "Outotz LS-K d8-0" or "Nyeajaae ZE-A d106" (both illustrative examples
of the *shape*, not claims about specific real systems). <LL-L> is a
three-letter cube identifier within the sector; <mass-code> is a single
letter a-h denoting the size of the boxel (sub-cube) the system belongs to;
the trailing number is the system's sequence index within that boxel,
either a plain integer or an <N1>-<N2> pair.

This module only understands the *string* structure of that trailing
sequence well enough to walk it forward/backward and reconstruct a
candidate name — it does not decode names into galactic x/y/z coordinates.
That's a separate, much harder problem and isn't needed for a boxel
*survey walker*: we generate the next candidate name and let the in-game
galaxy map confirm whether it exists.

<N1> and <N2> are NOT a fixed-width counter pair — <N2> does not "carry"
into <N1> at any small boundary. Secondary values like "d3-5660" and
"c13-670" occur in practice, so walking <N2> and moving to a different <N1>
cube are unrelated actions, not stages of one counter. So next/
previous here only ever move <N2> when it's present (or <N1> when the name
has no <N2> at all); nothing auto-carries between them.

An explicit "next boxel" action (<N1>+1) was tried and reverted after field testing showed it
doesn't correspond to spatial reality: incrementing <N1> while holding the
cube_id fixed produced candidates nowhere near the commander's actual
position, while genuinely neighboring boxels had entirely different cube
IDs. Moving to a real spatially-adjacent boxel needs actual coordinate/id64
math, not a string increment.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, replace
from typing import Optional

_NAME_RE = re.compile(
    r"^(?P<sector>.+?)\s+"
    r"(?P<cube>[A-Za-z]{2}-[A-Za-z])\s+"
    r"(?P<mass>[a-hA-H])(?P<n1>\d+)(?:-(?P<n2>\d+))?$"
)


@dataclass(frozen=True)
class ProcSystemName:
    """A parsed procedural system name."""

    sector: str
    cube_id: str
    mass_code: str
    primary: int
    secondary: Optional[int] = None

    def format(self) -> str:
        """Reconstruct the full system name string."""
        suffix = str(self.primary) if self.secondary is None else f"{self.primary}-{self.secondary}"
        return f"{self.sector} {self.cube_id} {self.mass_code}{suffix}"


def parse_system_name(name: str) -> Optional[ProcSystemName]:
    """
    Parse a procedural system name into its components.

    Returns None for names that don't match the procedural shape — hand-named
    systems like "Sol" or "Colonia" aren't boxel-walkable.
    """
    match = _NAME_RE.match(name.strip())
    if match is None:
        return None
    n2 = match.group("n2")
    return ProcSystemName(
        sector=match.group("sector"),
        cube_id=match.group("cube").upper(),
        mass_code=match.group("mass").lower(),
        primary=int(match.group("n1")),
        secondary=int(n2) if n2 is not None else None,
    )


def is_procedural_name(name: str) -> bool:
    """Whether name matches the procedural system name shape."""
    return parse_system_name(name) is not None


def next_in_sequence(name: ProcSystemName) -> ProcSystemName:
    """
    Return the next candidate name in the boxel's sequence.

    Only ever advances <N2> (when present) or <N1> (when the name has no
    <N2>) — see the module docstring for why there's no carry between them.
    """
    if name.secondary is None:
        return replace(name, primary=name.primary + 1)
    return replace(name, secondary=name.secondary + 1)


def previous_in_sequence(name: ProcSystemName) -> ProcSystemName:
    """
    Return the previous candidate name in the boxel's sequence.

    Raises ValueError at the start of the sequence (<N1> or <N2> would go
    negative) rather than returning a nonsensical name.
    """
    if name.secondary is None:
        if name.primary == 0:
            raise ValueError("already at the start of the sequence")
        return replace(name, primary=name.primary - 1)
    if name.secondary == 0:
        raise ValueError("already at the start of the sequence")
    return replace(name, secondary=name.secondary - 1)
