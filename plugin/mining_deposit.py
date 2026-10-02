"""
Estimates how many tons a recorded Hotspot's deposit still holds, from its
Rigs count and the HUD's own Amount/Density readout.

Neither Amount nor Density is a journal field - they're read off the in-game
mining scanner display and recorded on a Hotspot on trust, same as
`material`/`notes` (see mining_hotspots.py's Hotspot docstring). This module
turns those two readings plus Rigs into a range rather than a single number,
because nothing here is exact: the working assumption is that a deposit's
total reserve is built from a fixed number of tons per rig position, and that
number depends on Density.

The bands below reproduce empirically-measured game behavior (real depletion
traces, not derived from any formula the game documents), credited in
THIRD-PARTY-NOTICES.md. The model is a base of 125-175 t per rig position
times a Density factor (High x1, Medium x2, Low x3), fitted to six deposits
mined from High Amount to Depleted
(e.g. High Density 134 and 153 t/position, Medium 384, Low 288-473). Note the
direction: a *lower* Density label means a *larger* total reserve per
position. A missing Density reading takes High's low end to Low's high end.
Share-of-deposit-remaining by Amount comes from where the same traces changed
label as they were mined down. This replaces an earlier two-point model
(Low 287.5 / Medium 384 t/position, High unmeasured).

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

# Tons a single rig position holds in a full (Amount=High, freshly found)
# deposit: a base range scaled by Density (lower Density label = more tons).
_TONS_BASE: tuple[float, float] = (125.0, 175.0)
_DENSITY_FACTOR: dict[str, int] = {"High": 1, "Medium": 2, "Low": 3}
_TONS_PER_RIG: dict[str, tuple[float, float]] = {
    density: (_TONS_BASE[0] * factor, _TONS_BASE[1] * factor)
    for density, factor in _DENSITY_FACTOR.items()
}
# No Density reading at all: span High's low end to Low's high end rather
# than guessing a narrower band.
_TONS_PER_RIG_UNKNOWN: tuple[float, float] = (_TONS_PER_RIG["High"][0], _TONS_PER_RIG["Low"][1])

# Share of the deposit's total tons still left, by Amount - from where real
# depletion traces changed label as they were mined down.
_SHARE_LEFT: dict[str, tuple[float, float]] = {
    "High": (0.566, 1.0),
    "Medium": (0.267, 0.665),
    "Low": (0.0, 0.342),
    "Depleted": (0.0, 0.0),
}


def tons_left(rigs: Optional[int], amount: Optional[str],
              density: Optional[str] = None) -> Optional[tuple[int, int]]:
    """(low, high) tons estimated still in the deposit, rounded to the
    nearest 10, or None when `rigs` or `amount` is missing/unrecognized. A
    missing or High Density widens the range rather than refusing one -
    see the module docstring."""
    share = _SHARE_LEFT.get(amount) if amount else None
    if share is None or not isinstance(rigs, int) or isinstance(rigs, bool) or rigs <= 0:
        return None
    per_rig = _TONS_PER_RIG.get(density, _TONS_PER_RIG_UNKNOWN)
    return (_round10(rigs * per_rig[0] * share[0]),
            _round10(rigs * per_rig[1] * share[1]))


def describe(rigs: Optional[int], amount: Optional[str],
             density: Optional[str] = None, mined_tons: Optional[int] = None) -> str:
    """"~620-1,200 t left", "depleted", "depleted (612 t)" (when
    `mined_tons` - what Hotspot.mined_tons counted off the journal - is
    known), or "" when there's nothing to say (missing Rigs or Amount)."""
    if amount == "Depleted":
        return f"depleted ({mined_tons:,} t)" if mined_tons else "depleted"
    span = tons_left(rigs, amount, density)
    if span is None:
        return ""
    low, high = span
    if low == 0:
        return f"~up to {high:,} t left"
    return f"~{low:,}-{high:,} t left"


def _round10(value: float) -> int:
    return int(round(value / 10.0)) * 10
