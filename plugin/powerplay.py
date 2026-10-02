"""Powerplay mode: tracks the commander's pledged Power/merit total, the
current system's PowerPlay context, classifies which activity a batch of
merits most likely came from, and turns that into a session-scoped merit/CP
tally (see session.py/store.py/formulas.py).

The journal has no field that says "these merits came from Acquisition" —
that has to be inferred from where the commander is when they earn them.
FSDJump/Location/Docked report a system's "PowerplayState" and "Powers" (the
controlling power, or the powers contesting it) whenever the system is
powerplay-relevant. Comparing that to the commander's own pledged power tells
us whether being there helps acquire an unclaimed system, reinforce one's own
power's hold on it, or undermine a rival's.

`PowerplayController` (bottom of the tracker section) is this feature's one
entry point for `load.py` — it owns the tracker/session singletons, the
main-panel widgets (`build_panel`), and the Settings tab (`build_settings`/
`save_settings`), per the standard feature-module contract every mode
follows.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict, List, Mapping, Optional, Tuple

import tkinter as tk
from tkinter import ttk

import myNotebook as nb
from config import appname, config
from monitor import monitor

from . import panelkit
from .formulas import (
    ACQUISITION, ACTIVITIES, ACTIVITY_LABELS, DEFAULT_RATIOS, DELIVERY, NO_CP_ACTIVITIES,
    REINFORCEMENT, UNDERMINING, UNKNOWN, merits_to_cp,
)
from .powerplay_clipboard import DEFAULT_TEMPLATE as DEFAULT_CLIPBOARD_TEMPLATE
from .powerplay_clipboard import PLACEHOLDERS as CLIPBOARD_PLACEHOLDERS
from .session import (
    SessionManager, credits_earned, system_merit_total, system_totals, total_merits, visited_systems,
)
from .store import SessionStore

plugin_name = os.path.basename(os.path.dirname(__file__))
logger = logging.getLogger(f"{appname}.{plugin_name}")

# This mode's own main-panel/Settings-tab placement. ui.py builds this
# feature's widgets into the "powerplay" mode frame and calls
# build_settings/save_settings generically; it never reaches into this
# module's internals beyond that.
PANEL_PLACEMENT = "powerplay"

_INFO_COLOR = "#1565c0"

# PowerplayState values that mean "a single power has already secured this
# system" — under one of these, whether it's *our* power or a rival's Powers
# entry is what separates Reinforcement from Undermining. Anything else means
# nobody has it secured yet, so effort there is Acquisition. The exact set of
# state names Frontier uses isn't documented (the last official journal
# manual predates Powerplay 2.0); this list covers both the legacy and
# current names seen in the wild and is deliberately conservative — an
# unrecognised state falls through to Acquisition rather than guessing wrong.
_CONTROLLED_STATES = {"exploited", "fortified", "stronghold", "controlled", "homesystem"}

# "SearchAndRescue" is shared by several mechanics (Thargoid War salvage,
# regular mission hand-ins, PowerPlay commodity delivery) — Frontier's
# PowerPlay commodity item names ("PowerAgriculture", "PowerComputer", etc.)
# all share this prefix, which is how a PowerPlay hand-in is told apart from
# the others.
_POWER_COMMODITY_PREFIX = "power"

# Pledge status, resolved once per game session (see apply_login_reset /
# confirm_not_pledged_if_unresolved).
PLEDGE_UNKNOWN = "unknown"
PLEDGED = "pledged"
NOT_PLEDGED = "not_pledged"


class PowerplayTracker:
    """Commander's pledged Power/merit total, plus the PowerPlay state of 'here'."""

    def __init__(self) -> None:
        self.my_power: Optional[str] = None
        self.rank: Optional[int] = None
        self.total_merits: Optional[int] = None
        self.system_name: Optional[str] = None
        self.system_state: Optional[str] = None
        self.system_powers: List[str] = []
        self.system_controller: Optional[str] = None
        self.pledge_status: str = PLEDGE_UNKNOWN
        self._delivery_pending: bool = False

    def apply_login_reset(self) -> None:
        """
        "LoadGame": start of a fresh game session.

        The journal only ever tells us "you ARE pledged" (the "Powerplay"
        event, written alongside LoadGame at startup if pledged) — there's no
        "you are NOT pledged" event. So pledge_status goes back to unknown
        here, and confirm_not_pledged_if_unresolved() (called on the next
        always-fires "Location" event) resolves it to NOT_PLEDGED if no
        "Powerplay" event showed up in between.
        """
        self.my_power = None
        self.rank = None
        self.total_merits = None
        self.pledge_status = PLEDGE_UNKNOWN
        self._delivery_pending = False

    def apply_delivery_signal(self, event: str, entry: Mapping[str, Any]) -> None:
        """
        "SearchAndRescue" (PowerPlay commodities only) or
        "DeliverPowerMicroResources" (on-foot PowerPlay data): a hand-in at a
        power contact. Frontier's journal doesn't link this to the
        "PowerplayMerits" event it triggers, so mark the *next* merit gain as
        a delivery rather than guessing an activity from system state — a
        hand-in's target (Acquisition/Reinforcement/Undermining) is chosen
        in-game and isn't reported either, so DELIVERY is tracked by merit
        count only, same as UNKNOWN (see formulas.NO_CP_ACTIVITIES).
        """
        if event == "DeliverPowerMicroResources":
            self._delivery_pending = True
            return
        if event == "SearchAndRescue":
            name = str(entry.get("Name", "")).lower()
            if name.startswith(_POWER_COMMODITY_PREFIX):
                self._delivery_pending = True

    def apply_login_snapshot(self, entry: Mapping[str, Any]) -> None:
        """"Powerplay" event: written at startup if the commander is pledged."""
        power = entry.get("Power")
        self.my_power = str(power) if power else None
        self.pledge_status = PLEDGED if self.my_power else NOT_PLEDGED
        rank = entry.get("Rank")
        if isinstance(rank, int):
            self.rank = rank
        merits = entry.get("Merits")
        if isinstance(merits, int):
            self.total_merits = merits

    def confirm_not_pledged_if_unresolved(self) -> bool:
        """
        Call on "Location" (always fires once at startup, after "Powerplay"
        would have if pledged). Returns True if this call just resolved the
        status to NOT_PLEDGED.
        """
        if self.pledge_status == PLEDGE_UNKNOWN:
            self.pledge_status = NOT_PLEDGED
            return True
        return False

    def apply_join(self, entry: Mapping[str, Any]) -> None:
        power = entry.get("Power")
        self.my_power = str(power) if power else self.my_power
        self.pledge_status = PLEDGED if self.my_power else self.pledge_status
        # A fresh pledge starts at Rank 0; only trust an explicit field though.
        rank = entry.get("Rank")
        self.rank = rank if isinstance(rank, int) else 0

    def apply_leave(self, entry: Mapping[str, Any]) -> None:
        self.my_power = None
        self.rank = None
        self.total_merits = None
        self.pledge_status = NOT_PLEDGED

    def apply_defect(self, entry: Mapping[str, Any]) -> None:
        to_power = entry.get("ToPower")
        self.my_power = str(to_power) if to_power else None
        self.pledge_status = PLEDGED if self.my_power else self.pledge_status
        # Merits and rank don't carry over to the new power; start fresh so
        # the next PowerplayMerits event's TotalMerits diff isn't a huge,
        # wrong number, and so the old power's rank isn't shown against the
        # new one until "PowerplayRank" corrects it.
        self.total_merits = None
        rank = entry.get("Rank")
        self.rank = rank if isinstance(rank, int) else 0

    def apply_rank(self, entry: Mapping[str, Any]) -> None:
        rank = entry.get("Rank")
        if isinstance(rank, int):
            self.rank = rank

    def pledge_summary(self) -> Optional[str]:
        """Human-readable "Power (Rank N)" string, or None if not pledged."""
        if not self.my_power:
            return None
        if self.rank is not None:
            return f"{self.my_power} (Rank {self.rank})"
        return self.my_power

    def apply_system_context(self, system: Optional[str], entry: Mapping[str, Any]) -> None:
        """FSDJump / Location / Docked: refresh PowerplayState/Powers/ControllingPower for 'here'.

        `system` is EDMC's own live-tracked current system name (the `system`
        argument `journal_entry` receives, sourced from monitor.state), not
        parsed from the entry itself — it's the authoritative answer to
        "where are we right now" regardless of which fields this particular
        event happens to carry, and lets classify_current_activity() notice
        when the commander has moved on from the system this context
        describes (see there).
        """
        if "PowerplayState" not in entry and "Powers" not in entry and "ControllingPower" not in entry:
            # Not a powerplay-relevant system right now. Deliberately don't
            # clear the previous context here — a Docked event, for instance,
            # doesn't repeat the fields of the FSDJump that got us here, and
            # that shouldn't erase a still-valid system context.
            return
        self.system_name = system
        self.system_state = entry.get("PowerplayState")
        powers = entry.get("Powers")
        self.system_powers = [str(p) for p in powers] if isinstance(powers, list) else []
        # "Powers" lists *every* Power active in the system — the controller
        # plus any rival actively undermining it — so it can have more than
        # one entry even in a settled Stronghold/Fortified/Exploited system.
        # "ControllingPower" is the one field that actually names who holds
        # it; classify_current_activity() relies on this, not on Powers'
        # length, to tell Reinforcement/Undermining apart in that case.
        controller = entry.get("ControllingPower")
        self.system_controller = str(controller) if controller else None

    def apply_merits(self, entry: Mapping[str, Any]) -> Optional[int]:
        """
        "PowerplayMerits" event: returns the merits gained, or None if there's
        nothing usable to report.

        Prefers the event's own "MeritsGained" (community-confirmed field,
        though undocumented by Frontier); falls back to diffing "TotalMerits"
        against the last known total, which is what EDMC's own state tracking
        relies on, so it's a solid fallback if MeritsGained is ever absent.

        Also resolves pledge status if it wasn't already: earning PowerPlay
        merits is only possible while pledged, so this recovers correctly
        even if EDMC attached to the game mid-session and never saw this
        commander's "Powerplay"/"Location" startup events.
        """
        power = entry.get("Power")
        if power and not self.my_power:
            self.my_power = str(power)
        if self.pledge_status != PLEDGED:
            self.pledge_status = PLEDGED

        total = entry.get("TotalMerits")
        gained = entry.get("MeritsGained")

        if not isinstance(gained, int):
            if isinstance(total, int) and self.total_merits is not None:
                gained = total - self.total_merits
            else:
                gained = None

        if isinstance(total, int):
            self.total_merits = total

        return gained if isinstance(gained, int) and gained > 0 else None

    def classify_current_activity(self, current_system: Optional[str] = None) -> str:
        """Best-guess activity classification for merits earned right now.

        `current_system` is EDMC's live-tracked system name as of the merit
        gain (see apply_system_context). If it doesn't match the system our
        stored PowerplayState/Powers context was captured in, that context is
        stale — the commander has moved on since the last powerplay-relevant
        event — so it's better to admit we don't know than to misattribute
        using a different system's data. Omit it (or pass None) to skip this
        check and classify from the stored context regardless, as before.

        A pending delivery signal (see apply_delivery_signal) takes priority
        over all of that — a commodity/data hand-in's merits aren't a guess
        from system state at all, they're a direct signal of their own, and
        can be turned in at a different system than where the goods were
        collected. This also consumes the pending flag, so it only ever
        applies to the merit gain it actually triggered.
        """
        if self._delivery_pending:
            self._delivery_pending = False
            return DELIVERY

        if not self.my_power:
            return UNKNOWN

        if current_system and self.system_name and current_system != self.system_name:
            return UNKNOWN

        state = (self.system_state or "").lower()
        controller = self.system_controller

        if state in _CONTROLLED_STATES:
            if controller == self.my_power:
                return REINFORCEMENT
            if controller:
                return UNDERMINING
            # A controlled-type state but no ControllingPower reported
            # (shouldn't normally happen): fall back to Acquisition if we're
            # among the Powers listed as active there.
            return ACQUISITION if self.my_power in self.system_powers else UNKNOWN

        if self.system_state:
            # Unoccupied / Contested / Turmoil / etc: nobody holds it yet.
            return ACQUISITION

        return UNKNOWN


# ---------------------------------------------------------------------------
# Pledge recovery from the journal file itself.
#
# Frontier only writes a "Powerplay" event once per client launch (at the
# first login) — not on a logout-to-menu-and-back, and EDMC doesn't replay
# journal history when it (re)attaches to an already-running game either. So
# if this tracker starts out not knowing pledge status (a fresh
# EDMC/plugin start, mid-session or right after a relog), there's no new
# live event coming to tell it. The journal file itself still has the
# answer, though: the pledge-lifecycle event(s) from earlier in this same
# client launch are still sitting in it. This reads that file directly to
# recover it — the same approach autohonk.py uses for the binds file.
# ---------------------------------------------------------------------------

_PLEDGE_LIFECYCLE_EVENTS = frozenset({"Powerplay", "PowerplayJoin", "PowerplayLeave", "PowerplayDefect"})
_REVERSE_READ_CHUNK = 65536


def _iter_lines_reverse(path: str, chunk_size: int = _REVERSE_READ_CHUNK):
    """Yields non-blank lines from `path` in reverse order (last line
    first), reading backward in chunks instead of loading the whole file."""
    with open(path, "rb") as fh:
        fh.seek(0, os.SEEK_END)
        remaining = fh.tell()
        tail = b""
        while remaining > 0:
            read_size = min(chunk_size, remaining)
            remaining -= read_size
            fh.seek(remaining)
            tail = fh.read(read_size) + tail
            lines = tail.split(b"\n")
            tail = lines[0]
            for line in reversed(lines[1:]):
                if line.strip():
                    yield line
        if tail.strip():
            yield tail


def find_last_pledge_event(journal_file: Optional[str]) -> Optional[Dict[str, Any]]:
    """Scans `journal_file` backward for the most recent pledge-lifecycle
    event already written to it. Returns None if the file can't be read or
    contains no pledge-lifecycle event before its start."""
    if not journal_file:
        return None
    try:
        for raw_line in _iter_lines_reverse(journal_file):
            try:
                entry = json.loads(raw_line)
            except ValueError:
                continue
            event = entry.get("event")
            if event in _PLEDGE_LIFECYCLE_EVENTS:
                return entry
            if event == "Fileheader":
                break
    except OSError:
        logger.warning("Could not read %s for pledge recovery", journal_file, exc_info=True)
    return None


_PLEDGE_EVENT_APPLIERS = {
    "Powerplay": lambda pp, entry: pp.apply_login_snapshot(entry),
    "PowerplayJoin": lambda pp, entry: pp.apply_join(entry),
    "PowerplayLeave": lambda pp, entry: pp.apply_leave(entry),
    "PowerplayDefect": lambda pp, entry: pp.apply_defect(entry),
}

# Events that carry PowerplayState/Powers for the current system when it's
# powerplay-relevant. "Location" is handled separately (it also doubles as
# the not-pledged checkpoint).
_SYSTEM_CONTEXT_EVENTS = ("FSDJump", "Docked")

# Commodity/data hand-ins at a power contact — see apply_delivery_signal.
_DELIVERY_EVENTS = ("SearchAndRescue", "DeliverPowerMicroResources")

_LOADGAME_SCAN_LIMIT = 50  # "LoadGame" is always one of the first few lines in a journal file


def _mode_text(game_mode: Optional[str], group: Optional[str]) -> str:
    if game_mode == "Open":
        return "Mode: Open"
    if game_mode == "Solo":
        return "Mode: Solo"
    if game_mode == "Group":
        return f"Mode: Private ({group})" if group else "Mode: Private"
    return "Mode: unknown"


# --- CP-ratio / clipboard-template settings (this mode's own Settings-tab
# state, kept here rather than in ui.py so the feature owns its own config) -

CONFIG_RATIO_PREFIX = "wntb_powerplay_ratio_"
CONFIG_CLIPBOARD_FORMAT = "wntb_powerplay_clipboard_format"


def ratio_for(activity: str) -> float:
    """Current merits-per-CP ratio for an activity, from Settings or the default."""
    default = DEFAULT_RATIOS.get(activity)
    if default is None:
        return 0.0
    raw = config.get_str(f"{CONFIG_RATIO_PREFIX}{activity}")
    if not raw:
        return default
    try:
        value = float(raw)
    except ValueError:
        return default
    return value if value > 0 else default


def clipboard_template() -> str:
    """Current "Copy Progress" line format, from Settings or the default."""
    return config.get_str(CONFIG_CLIPBOARD_FORMAT) or DEFAULT_CLIPBOARD_TEMPLATE


def _format_ratio(value: float) -> str:
    return f"{value:g}"


def _cp_by_activity(totals: Dict[str, int]) -> Dict[str, float]:
    return {
        activity: merits_to_cp(totals.get(activity, 0), ratio_for(activity))
        for activity in ACTIVITIES
        if activity not in NO_CP_ACTIVITIES and totals.get(activity, 0)
    }


_SHORT_ACTIVITY_LABELS = {
    ACQUISITION: "Acq", REINFORCEMENT: "Reinf", UNDERMINING: "UM", DELIVERY: "Del", UNKNOWN: "Unk",
}


def _cp_bits(cp_by_activity: Dict[str, float]) -> str:
    return " · ".join(
        f"{_SHORT_ACTIVITY_LABELS[activity]} {cp_by_activity[activity]:.0f}"
        for activity in ACTIVITIES if activity in cp_by_activity
    )


def _full_cp_bits(totals: Dict[str, int]) -> str:
    return " · ".join(
        f"{_SHORT_ACTIVITY_LABELS[activity]} {merits_to_cp(totals.get(activity, 0), ratio_for(activity)):.0f}"
        for activity in ACTIVITIES
        if activity not in NO_CP_ACTIVITIES
    )


def _here_lines(session: dict, current_system: Optional[str]) -> tuple:
    if not current_system:
        return "Here: awaiting system data…", ""
    merits = system_merit_total(session, current_system)
    cp_bits = _full_cp_bits(system_totals(session, current_system))
    return f"Here: {merits:,} merits", f"CP: {cp_bits}"


def _system_summary(pp: PowerplayTracker) -> str:
    """'Nervi — Exploited (Zachary Hudson)' for the main panel. Deliberately
    just the controller, not the full rival/contested-Powers list — the
    Sessions window's Current Session tab is the better home for that full
    detail, and keeping it off the main panel keeps this row's width
    predictable."""
    if not pp.system_name:
        return "Awaiting system data…"
    state = pp.system_state or "no PP data"
    if pp.system_controller:
        detail = pp.system_controller
    elif pp.system_powers:
        detail = "contested"
    else:
        detail = "uncontested"
    return f"{pp.system_name} — {state} ({detail})"


class PowerplayController:
    """This mode's one entry point for `load.py`/`ui.py` — owns the tracker
    + session singletons, the main-panel widgets, and the Settings tab."""

    def __init__(self) -> None:
        self.tracker = PowerplayTracker()
        self.sessions: Optional[SessionManager] = None
        self._current_system: Optional[str] = None
        # Galactic (x, y, z) from the latest StarPos-carrying event - only
        # the Rare Goods Finder needs it.
        self._current_coords: Optional[Tuple[float, float, float]] = None

        # Main-panel widgets (built in build_panel).
        self._status_label: Optional[tk.Label] = None
        self._mode_label: Optional[tk.Label] = None
        self._system_label: Optional[tk.Label] = None
        self._here_merits_label: Optional[tk.Label] = None
        self._here_cp_label: Optional[tk.Label] = None
        self._merits_label: Optional[tk.Label] = None
        self._cp_label: Optional[tk.Label] = None
        self._credits_label: Optional[tk.Label] = None
        self._last_event_label: Optional[tk.Label] = None
        self._panel_parent: Optional[tk.Frame] = None

        # Settings-tab state.
        self._ratio_vars: Dict[str, tk.StringVar] = {}
        self._clipboard_format_var: Optional[tk.StringVar] = None

    # --- lifecycle --------------------------------------------------------

    def start(self, plugin_dir: str) -> None:
        self.sessions = SessionManager(SessionStore(plugin_dir))

    def flush(self) -> None:
        if self.sessions is not None:
            self.sessions.flush()

    # --- journal dispatch ---------------------------------------------------

    def handle_event(self, entry: Dict[str, Any], cmdr: str, system: Optional[str], station: Optional[str], state: Dict[str, Any]) -> None:
        if self.sessions is None:
            return

        if system:
            self._current_system = system

        star_pos = entry.get("StarPos")
        if (
            isinstance(star_pos, (list, tuple)) and len(star_pos) == 3
            and all(isinstance(v, (int, float)) for v in star_pos)
        ):
            self._current_coords = (float(star_pos[0]), float(star_pos[1]), float(star_pos[2]))
            from . import rare_goods_window
            rare_goods_window.refresh(self._current_system, self._current_coords)

        credits_now = state.get("Credits") if isinstance(state, dict) else None
        if isinstance(credits_now, (int, float)):
            self.sessions.record_credits(int(credits_now))

        try:
            self._dispatch(cmdr, system, entry)
        finally:
            self._refresh_panel()

    def _dispatch(self, cmdr: str, system: Optional[str], entry: Dict[str, Any]) -> None:
        assert self.sessions is not None
        event = entry.get("event", "")

        if event == "LoadGame":
            self._set_mode(_mode_text(entry.get("GameMode"), entry.get("Group")))
            credits_start = entry.get("Credits")
            continued = self.sessions.sync_session(
                cmdr, None, credits_start if isinstance(credits_start, int) else None, monitor.logfile,
            )
            logger.info("LoadGame for %s (%s)", cmdr, "continuing session" if continued else "new session")
            if continued:
                # Same journal file as before — a logout to the main menu and
                # back in, not a fresh game launch. Frontier only re-sends
                # "Powerplay" on the *first* login of a client launch, so
                # recover pledge state from the journal file if this tracker
                # is a fresh instance that never saw it live.
                self._recover_pledge_state()
                self._set_status(
                    f"Pledged to {self.tracker.pledge_summary()}" if self.tracker.my_power
                    else f"CMDR {cmdr}: not a PP Pledge"
                )
            else:
                self.tracker.apply_login_reset()
                self._set_status(f"{cmdr}: checking PowerPlay pledge…")
            return

        if event == "StartUp":
            # EDMC (re)started with the game already running — no journal
            # replay, so recover both pledge and game-mode state directly.
            self.sessions.sync_session(cmdr, None, None, monitor.logfile)
            logger.info("StartUp (EDMC attached to a running game) for %s", cmdr)
            self._recover_pledge_state()
            self._recover_game_mode()
            self._set_status(
                f"Pledged to {self.tracker.pledge_summary()}" if self.tracker.my_power
                else f"CMDR {cmdr}: not a PP Pledge"
            )
            return

        if event == "Powerplay":
            self.tracker.apply_login_snapshot(entry)
            self.sessions.record_power(self.tracker.my_power)
            self._set_status(
                f"Pledged to {self.tracker.pledge_summary()}" if self.tracker.my_power
                else f"CMDR {cmdr}: not a PP Pledge"
            )
            return

        if event == "PowerplayJoin":
            self.tracker.apply_join(entry)
            self.sessions.record_power(self.tracker.my_power)
            self._set_status(f"Pledged to {self.tracker.pledge_summary()}")
            return

        if event == "PowerplayLeave":
            self.tracker.apply_leave(entry)
            self._set_status("Left PowerPlay")
            return

        if event == "PowerplayDefect":
            self.tracker.apply_defect(entry)
            self.sessions.record_power(self.tracker.my_power)
            self._set_status(f"Defected to {self.tracker.pledge_summary()}")
            return

        if event == "PowerplayRank":
            self.tracker.apply_rank(entry)
            if self.tracker.my_power:
                self._set_status(f"Pledged to {self.tracker.pledge_summary()}")
            return

        if event == "Location":
            # "Location" always fires once at startup, after "Powerplay"
            # would have if the commander is pledged — so if pledge status
            # is still unresolved by now, there was no "Powerplay" event.
            if self.tracker.confirm_not_pledged_if_unresolved():
                logger.info("CMDR %s is not pledged to a Power", cmdr)
                self._set_status(f"CMDR {cmdr}: not a PP Pledge")
            self.tracker.apply_system_context(system, entry)
            return

        if event in _SYSTEM_CONTEXT_EVENTS:
            self.tracker.apply_system_context(system, entry)
            return

        if event in _DELIVERY_EVENTS:
            self.tracker.apply_delivery_signal(event, entry)
            return

        if event == "PowerplayMerits":
            self._handle_merits(system, entry)
            return

    def _handle_merits(self, system: Optional[str], entry: Dict[str, Any]) -> None:
        assert self.sessions is not None

        gained = self.tracker.apply_merits(entry)
        self.sessions.record_power(self.tracker.my_power)
        if gained is None:
            return

        activity = self.tracker.classify_current_activity(system)
        ts = entry.get("timestamp")
        self.sessions.record_merits(activity, gained, system, ts if isinstance(ts, str) else None)

        ratio = ratio_for(activity)
        cp = 0.0 if not ratio else gained / ratio
        label = ACTIVITY_LABELS.get(activity, "Unattributed")
        message = f"+{gained} merits ({label}, ~{cp:.1f} CP)"
        logger.info(message)
        self._set_last_event(message)

    def _recover_game_mode(self) -> None:
        """Reads the current journal file directly for its "LoadGame"
        event's GameMode/Group fields — needed for the "StartUp" handler,
        where EDMC synthesizes the entry itself (no journal replay)."""
        if not monitor.logfile:
            return
        try:
            with open(monitor.logfile, "r", encoding="utf-8") as fh:
                for _ in range(_LOADGAME_SCAN_LIMIT):
                    line = fh.readline()
                    if not line:
                        break
                    try:
                        entry = json.loads(line)
                    except ValueError:
                        continue
                    if entry.get("event") == "LoadGame":
                        self._set_mode(_mode_text(entry.get("GameMode"), entry.get("Group")))
                        return
        except OSError:
            logger.warning("Could not read %s for game-mode recovery", monitor.logfile, exc_info=True)

    def _recover_pledge_state(self) -> None:
        """Falls back to reading the current journal file directly for the
        last pledge-lifecycle event when the tracker doesn't already know
        pledge status in memory. No-op if it already has an answer."""
        if self.tracker.pledge_status != PLEDGE_UNKNOWN:
            return
        entry = find_last_pledge_event(monitor.logfile)
        if entry is not None:
            _PLEDGE_EVENT_APPLIERS[entry["event"]](self.tracker, entry)
            logger.info("Recovered pledge state from journal file: %s", self.tracker.pledge_summary() or "not pledged")

    def rescan_journal(self) -> None:
        """"Rescan" button handler: re-reads the current journal file from
        the start and replays its PowerPlay-relevant events, to recover
        merits earned in the gap between an EDMC restart (while the game
        keeps running) and the synthesized "StartUp" event that follows it.

        PowerplayMerits events are only actually recorded if their
        "timestamp" is newer than the last one already recorded this session
        — re-adding an already-counted gain would double it. A genuinely new
        merit event sharing the exact same (whole-second-precision) timestamp
        as the last recorded one is the one edge case this can still miss —
        silently under-counting is the safer failure mode than double-counting.
        """
        if self.sessions is None:
            return
        journal_file = monitor.logfile
        if not journal_file or self.sessions.current.get("journal_file") != journal_file:
            self._set_last_event("Rescan: no active session for the current journal file")
            return

        baseline_ts = self.sessions.current.get("last_merit_ts")
        replay_system: Optional[str] = None
        recovered_events = 0
        recovered_merits = 0

        try:
            with open(journal_file, "r", encoding="utf-8") as fh:
                for line in fh:
                    try:
                        entry = json.loads(line)
                    except ValueError:
                        continue
                    event = entry.get("event", "")
                    star_system = entry.get("StarSystem")
                    if star_system:
                        replay_system = star_system

                    applier = _PLEDGE_EVENT_APPLIERS.get(event)
                    if applier is not None:
                        applier(self.tracker, entry)
                    elif event == "PowerplayRank":
                        self.tracker.apply_rank(entry)
                    elif event == "Location" or event in _SYSTEM_CONTEXT_EVENTS:
                        self.tracker.apply_system_context(replay_system, entry)
                    elif event in _DELIVERY_EVENTS:
                        self.tracker.apply_delivery_signal(event, entry)
                    elif event == "PowerplayMerits":
                        gained = self.tracker.apply_merits(entry)
                        activity = self.tracker.classify_current_activity(replay_system)
                        ts = entry.get("timestamp")
                        is_new = (
                            gained is not None
                            and isinstance(ts, str)
                            and (baseline_ts is None or ts > baseline_ts)
                        )
                        if is_new:
                            self.sessions.record_merits(activity, gained, replay_system, ts)
                            baseline_ts = ts
                            recovered_events += 1
                            recovered_merits += gained
        except OSError:
            logger.warning("Could not read %s for rescan", journal_file, exc_info=True)
            self._set_last_event("Rescan failed: could not read journal file")
            return

        self.sessions.record_power(self.tracker.my_power)
        logger.info("Rescanned journal: recovered %d merits across %d events", recovered_merits, recovered_events)
        if recovered_events:
            self._set_last_event(f"Rescan: recovered {recovered_merits} merits ({recovered_events} events)")
        else:
            self._set_last_event("Rescan: no missed merits found")
        self._refresh_panel()

    # --- main-panel widgets -------------------------------------------------

    def build_panel(self, parent: tk.Frame) -> None:
        self._panel_parent = parent

        self._status_label = panelkit.wrap_label(parent, text="Awaiting PowerPlay activity…")
        self._status_label.grid(row=0, column=0, sticky=tk.W)

        self._mode_label = panelkit.wrap_label(parent, text="Mode: awaiting login…")
        self._mode_label.grid(row=1, column=0, sticky=tk.W)

        self._system_label = panelkit.wrap_label(parent, text="Awaiting system data…")
        self._system_label.grid(row=2, column=0, sticky=tk.W, pady=(4, 0))

        self._here_merits_label = panelkit.wrap_label(parent, text="Here: awaiting system data…")
        self._here_merits_label.grid(row=3, column=0, sticky=tk.W)

        self._here_cp_label = panelkit.wrap_label(parent, text="")
        self._here_cp_label.grid(row=4, column=0, sticky=tk.W)

        self._merits_label = panelkit.wrap_label(parent, text="Session merits: 0")
        self._merits_label.grid(row=5, column=0, sticky=tk.W, pady=(4, 0))

        self._cp_label = panelkit.wrap_label(parent, text="Session CP: —")
        self._cp_label.grid(row=6, column=0, sticky=tk.W)

        self._credits_label = panelkit.wrap_label(parent, text="")
        self._credits_label.grid(row=7, column=0, sticky=tk.W)

        self._last_event_label = panelkit.wrap_label(parent, text="No merit events yet this session.")
        self._last_event_label.grid(row=8, column=0, sticky=tk.W, pady=(4, 0))

        windows_row = tk.Frame(parent)
        windows_row.grid(row=9, column=0, sticky=tk.W, pady=(4, 0))
        tk.Button(windows_row, text="Sessions", command=self._show_sessions).pack(side=tk.LEFT, padx=(0, 6))
        tk.Button(windows_row, text="Rares", command=self._show_rares).pack(side=tk.LEFT, padx=(0, 6))
        tk.Button(windows_row, text="Rescan", command=self.rescan_journal).pack(side=tk.LEFT)

        self._refresh_panel()

    def _show_sessions(self) -> None:
        if self._panel_parent is not None and self.sessions is not None:
            from . import powerplay_window
            powerplay_window.show(self._panel_parent, self.sessions, self.tracker, self._current_system)

    def _show_rares(self) -> None:
        if self._panel_parent is not None:
            from . import rare_goods_window
            rare_goods_window.show(self._panel_parent, self._current_system, self._current_coords)

    def _set_status(self, message: str) -> None:
        if self._status_label is not None:
            self._status_label["text"] = message

    def _set_mode(self, message: str) -> None:
        if self._mode_label is not None:
            self._mode_label["text"] = message

    def _set_last_event(self, message: str) -> None:
        if self._last_event_label is not None:
            self._last_event_label["text"] = message
            self._last_event_label["foreground"] = "green"

    def _refresh_panel(self) -> None:
        if self.sessions is None or self._merits_label is None:
            return

        if self._system_label is not None:
            self._system_label["text"] = _system_summary(self.tracker)

        session = self.sessions.current

        if self._here_merits_label is not None and self._here_cp_label is not None:
            here_merits_text, here_cp_text = _here_lines(session, self._current_system)
            self._here_merits_label["text"] = here_merits_text
            self._here_cp_label["text"] = here_cp_text

        merits = total_merits(session)
        cp_by_activity = _cp_by_activity(session.get("totals", {}))
        earned = credits_earned(session)

        self._merits_label["text"] = f"Session merits: {merits:,}"
        if self._cp_label is not None:
            self._cp_label["text"] = f"Session CP: {_cp_bits(cp_by_activity)}"

        if self._credits_label is not None:
            if earned is None:
                self._credits_label.grid_remove()
            else:
                self._credits_label["text"] = f"Credits: {earned:+,}"
                self._credits_label.grid()

        from . import powerplay_window
        powerplay_window.refresh(self._current_system)

    # --- Settings tab --------------------------------------------------------

    def build_settings(self, notebook: nb.Notebook) -> None:
        tab = nb.Frame(notebook)
        tab.columnconfigure(0, weight=1)
        notebook.add(tab, text="Powerplay")

        nb.Label(tab, text="CP Ratios", font=("TkDefaultFont", 9, "bold")).grid(
            row=0, column=0, sticky=tk.W, padx=10, pady=(10, 2),
        )
        ratios_section = nb.Frame(tab)
        ratios_section.grid(row=1, column=0, sticky=tk.NSEW)
        self._build_ratios_section(ratios_section)

        ttk.Separator(tab, orient=tk.HORIZONTAL).grid(row=2, column=0, sticky=tk.EW, padx=10, pady=(8, 0))
        nb.Label(tab, text="Clipboard", font=("TkDefaultFont", 9, "bold")).grid(
            row=3, column=0, sticky=tk.W, padx=10, pady=(10, 2),
        )
        clipboard_section = nb.Frame(tab)
        clipboard_section.grid(row=4, column=0, sticky=tk.NSEW)
        self._build_clipboard_section(clipboard_section)

    def _build_ratios_section(self, frame: nb.Frame) -> None:
        nb.Label(
            frame,
            text=(
                "Frontier doesn't publish these in the journal — the defaults are "
                "community-sourced best estimates. If your in-game CP totals don't "
                "line up, correct the ratio here (merits required for 1 CP)."
            ),
            wraplength=440, justify=tk.LEFT,
        ).grid(row=0, column=0, columnspan=2, sticky=tk.W, padx=10, pady=(10, 8))

        nb.Label(
            frame,
            text=(
                "Note: system strength/frontline penalties, ethos bonuses, and your "
                "Squadron's PP bonus are already baked into the merit amount the "
                "journal reports — these ratios only convert that final merit total "
                "into CP, so there's no separate bonus to account for here."
            ),
            wraplength=440, justify=tk.LEFT, foreground="#c07000",
        ).grid(row=1, column=0, columnspan=2, sticky=tk.W, padx=10, pady=(0, 10))

        self._ratio_vars = {}
        row = 2
        for activity in ACTIVITIES:
            default = DEFAULT_RATIOS.get(activity)
            if default is None:
                continue
            nb.Label(frame, text=f"{ACTIVITY_LABELS[activity]}:").grid(
                row=row, column=0, sticky=tk.W, padx=10, pady=2,
            )
            var = tk.StringVar(value=_format_ratio(ratio_for(activity)))
            self._ratio_vars[activity] = var
            nb.EntryMenu(frame, textvariable=var, width=8).grid(
                row=row, column=1, sticky=tk.W, padx=(0, 10), pady=2,
            )
            row += 1

    def _build_clipboard_section(self, frame: nb.Frame) -> None:
        nb.Label(
            frame,
            text='Format for each system\'s line when "Copy Progress" (Sessions window) copies to the clipboard.',
            wraplength=440, justify=tk.LEFT,
        ).grid(row=0, column=0, columnspan=2, sticky=tk.W, padx=10, pady=(10, 6))

        nb.Label(
            frame, text="Placeholders: " + "  ".join(CLIPBOARD_PLACEHOLDERS),
            wraplength=440, justify=tk.LEFT, foreground=_INFO_COLOR,
        ).grid(row=1, column=0, columnspan=2, sticky=tk.W, padx=10, pady=(0, 8))

        self._clipboard_format_var = tk.StringVar(value=clipboard_template())
        nb.EntryMenu(frame, textvariable=self._clipboard_format_var, width=60).grid(
            row=2, column=0, sticky=tk.W, padx=10, pady=2,
        )

        def _reset_default() -> None:
            if self._clipboard_format_var is not None:
                self._clipboard_format_var.set(DEFAULT_CLIPBOARD_TEMPLATE)

        tk.Button(frame, text="Reset to default", command=_reset_default).grid(
            row=2, column=1, sticky=tk.W, padx=(6, 10), pady=2,
        )

    def save_settings(self) -> None:
        for activity, var in self._ratio_vars.items():
            text = var.get().strip()
            try:
                value = float(text)
            except ValueError:
                continue
            if value <= 0:
                continue
            config.set(f"{CONFIG_RATIO_PREFIX}{activity}", str(value))

        if self._clipboard_format_var is not None:
            text = self._clipboard_format_var.get()
            config.set(CONFIG_CLIPBOARD_FORMAT, text if text.strip() else DEFAULT_CLIPBOARD_TEMPLATE)


controller = PowerplayController()


def handle_event(entry: Dict[str, Any], cmdr: str, system: Optional[str], station: Optional[str], state: Dict[str, Any]) -> None:
    controller.handle_event(entry, cmdr, system, station, state)


def build_panel(parent: tk.Frame) -> None:
    controller.build_panel(parent)


def build_settings(notebook: nb.Notebook) -> None:
    controller.build_settings(notebook)


def save_settings() -> None:
    controller.save_settings()
