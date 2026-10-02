"""
Estimates how many tons a recorded Hotspot's deposit still holds, from its
Rigs count and the HUD's own Amount/Density readout.

Neither Amount nor Density is a journal field - they're read off the in-game
mining scanner display and recorded on a Hotspot on trust, same as
`material`/`notes` (see mining_hotspots.py's Hotspot docstring). Nothing here
is exact, so the answer is a (low, high) range, never a single number.

The model, from measured depletion of real deposits (credited in
THIRD-PARTY-NOTICES.md): a full deposit holds a fixed number of tons per rig
position, and how many depends on Density - note the direction, a *lower*
Density label means a *larger* reserve. The Amount label then says what share
of that reserve is left. Rigs x tons-per-position x share-left gives the range.

No tkinter - see tests/test_mining_deposit.py.
"""
from __future__ import annotations

from typing import Optional

MAX_RIGS = 7
"""Rig positions a deposit can hold. Six can be worked at once; a seventh
position can be placed but not run - so 7 is the ceiling for a recorded
count."""

DENSITIES: tuple[str, ...] = ("Low", "Medium", "High")
AMOUNTS: tuple[str, ...] = ("High", "Medium", "Low", "Depleted")

_TONS_PER_POSITION_FULL: dict[str, tuple[int, int]] = {
    "High": (125, 175),
    "Medium": (250, 350),
    "Low": (375, 525),
}
"""(low, high) tons one rig position holds in a full, freshly found deposit."""

_TONS_PER_POSITION_UNKNOWN: tuple[int, int] = (125, 525)
"""No Density reading: span the smallest low end to the largest high end
rather than guessing a narrower band."""

_SHARE_LEFT: dict[str, tuple[float, float]] = {
    "High": (0.566, 1.0),
    "Medium": (0.267, 0.665),
    "Low": (0.0, 0.342),
    "Depleted": (0.0, 0.0),
}
"""(low, high) share of the full reserve still in the deposit, by Amount."""


def _to_nearest_ten(tons: float) -> int:
    return round(tons / 10) * 10


def reserve_range(rigs: Optional[int], amount: Optional[str],
                  density: Optional[str] = None) -> Optional[tuple[int, int]]:
    """(low, high) tons estimated still in the deposit, to the nearest 10, or
    None when `rigs` or `amount` is missing or not usable. A missing or
    unrecognized Density widens the range rather than refusing one."""
    shares = _SHARE_LEFT.get(amount) if amount else None
    if shares is None or isinstance(rigs, bool) or not isinstance(rigs, int) or rigs <= 0:
        return None
    per_position = _TONS_PER_POSITION_FULL.get(density, _TONS_PER_POSITION_UNKNOWN)
    return tuple(_to_nearest_ten(rigs * tons * share)  # type: ignore[return-value]
                 for tons, share in zip(per_position, shares))


def reserve_text(rigs: Optional[int], amount: Optional[str],
                 density: Optional[str] = None, mined_tons: Optional[int] = None) -> str:
    """"~620-1,200 t left", "~up to 700 t left", "depleted", "depleted
    (612 t)" (when `mined_tons` - what Hotspot.mined_tons counted off the
    journal - is known), or "" when there is nothing to say (missing Rigs or
    Amount)."""
    if amount == "Depleted":
        return f"depleted ({mined_tons:,} t)" if mined_tons else "depleted"
    span = reserve_range(rigs, amount, density)
    if span is None:
        return ""
    low, high = span
    return f"~up to {high:,} t left" if low == 0 else f"~{low:,}-{high:,} t left"
