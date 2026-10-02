"""
Refinements-per-minute: a sliding window over the last RPM_WINDOW_SECONDS
of refinement timestamps, scaled to a per-minute rate. Shared by
mining_space.py and mining_surface.py (both track a `refined_timestamps`
list the same way) so the rate reads the same on both pages.

Recomputed both on every MiningRefined (via record_tick()) and on a
periodic UI timer (mining_render.py's re-render tick) that just re-reads
current_rate() against the same list - that's what makes the displayed
rate decay back toward zero during a lull instead of freezing at its
last value once refining stops.
"""
import time

RPM_WINDOW_SECONDS = 10.0
"""How far back a refinement still counts toward the displayed rate -
short enough that the rate visibly decays toward zero within ~10s of a
mining lull, rather than staying stuck at whatever it last read."""


def record_tick(timestamps: list[float]) -> None:
    """Call once per unit refined, appending the current time."""
    timestamps.append(time.time())


def current_rate(timestamps: list[float]) -> float:
    """Prunes entries older than RPM_WINDOW_SECONDS from `timestamps` in
    place, then returns units-per-minute for what's left (0.0 once the
    window empties out). The fixed window means the result is always a
    multiple of 60/RPM_WINDOW_SECONDS - a coarse but simple rate, not a
    smoothed average."""
    cutoff = time.time() - RPM_WINDOW_SECONDS
    while timestamps and timestamps[0] < cutoff:
        timestamps.pop(0)
    if not timestamps:
        return 0.0
    return len(timestamps) * 60.0 / RPM_WINDOW_SECONDS
