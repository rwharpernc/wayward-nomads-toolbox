"""Boxel Survey: given a seed procedural system name, walks the ascending/
descending candidate sequence within that boxel, auto-advancing and
copying the next target to the clipboard whenever the commander jumps to
the current target. Locally-visited systems (this session's journal) are
skipped when advancing, and — when enabled in Settings — systems already
known to EDSM (visited by anyone) are skipped too. Also keeps a separate
survey log of notable bodies (Earthlike/water/ammonia worlds,
terraformable, biological signals) found along the way, with CSV export.

The walker's position persists per commander (`boxel_state.py`) - saved on
EDMC exit and whenever the active commander changes, restored the moment
that commander is seen again (including a different commander logging in
on the same install), so nobody has to re-set their seed system every
session. Region Sweep's queue and Waypoint Route's list are each
persisted the same way, in their own per-commander state files.

Part of Exploration mode alongside Auto-Honk and Discovery Alerts
(`PANEL_PLACEMENT = "exploration"`). Not yet implemented: overlay support.

Also hosts a second, selectable sub-mode - Region Sweep
(`region_sweep_panel.py`/`region_sweep_queue.py`/`region_sweep_state.py`/
`region_sweep_spansh.py`) - which tracks completion across a user-curated
queue of cubes rather than one flat sequence within a single boxel. See
`region_sweep_queue.py`'s module docstring for the design rationale.
BoxelSurveyController owns the Sequence/Region Sweep toggle and fans
journal events out to both; only the active sub-mode's controller acts on
them (`RegionSweepController.active` gates its own side effects).
"""

from __future__ import annotations

import csv
import logging
import math
import os
import queue
import random
import threading
from dataclasses import dataclass, replace
from typing import Any, Dict, FrozenSet, List, Optional, Set, Tuple

import tkinter as tk
import tkinter.messagebox as messagebox

import myNotebook as nb
from config import appname, config

from . import (
    boxel, boxel_state, edsm_client, panelkit, region_sweep_panel, survey_log, visited_systems, waypoint_route_panel,
)
from .boxel_walker import BoxelWalker, WalkerSnapshot

plugin_name = os.path.basename(os.path.dirname(__file__))
logger = logging.getLogger(f"{appname}.{plugin_name}")

PANEL_PLACEMENT = "exploration"

_CFG_AUTOCOPY = "wntb_boxel_autocopy"
_CFG_SKIP_VISITED = "wntb_boxel_skip_visited"
_CFG_SKIP_EDSM_VISITED = "wntb_boxel_skip_edsm_visited"
_CFG_SKIP_EDSM_SCANNED = "wntb_boxel_skip_edsm_scanned"
_CFG_CONFIRM_ALIAS_ARRIVAL = "wntb_boxel_confirm_alias_arrival"

# Collapsed by default - this is the largest
# single feature in Exploration mode's panel (three sub-modes' worth of
# widgets), so it starts minimized rather than pushing everything below it
# down the page; same click-the-title-to-toggle convention ui.py's own
# main-panel collapse uses.
_CFG_COLLAPSED = "wntb_boxel_collapsed"

# Which of the two sub-modes (Sequence vs. Region Sweep) is selected -
# persisted separately from either sub-mode's own state, since it's a
# property of the panel/toggle, not of either walker.
_CFG_SUBMODE = "wntb_boxel_submode"
_SUBMODE_SEQUENCE = "sequence"
_SUBMODE_REGION_SWEEP = "region_sweep"
_SUBMODE_WAYPOINTS = "waypoints"
_SUBMODES = (_SUBMODE_SEQUENCE, _SUBMODE_REGION_SWEEP, _SUBMODE_WAYPOINTS)

_NO_TARGET_TEXT = "(no target — set a seed system below)"
_HINT_EMPTY = ""
_HINT_VALID = "looks like a procedural boxel name"
_HINT_INVALID = "not a recognized boxel name shape (hand-named system?)"
_NO_SURVEY_STATS_TEXT = "Surveyed: (not in a boxel yet)"

EXPORT_FILENAME = "boxel_survey_export.csv"

# Real network calls per EDSM-visited skip-check chain — a much smaller cap
# than boxel_walker.MAX_SKIP_STEPS (which is local-only).
MAX_EDSM_SKIP_ATTEMPTS = 20

# How many consecutive manual "Next" clicks (with no confirmed jump in
# between) before auto-suggesting a real EDSM-known system to jump to
# instead. A small mass-code boxel can be sparse enough that the walker's
# blind string-increment sequence (boxel.py has no concept of how many real
# systems a boxel actually contains) runs out of reachable candidates after
# just a couple of hits - the "boxel exhausted" situation, handled by falling
# back to a real spatial EDSM lookup (see edsm_client.py's module docstring)
# rather than continuing to guess.
AUTO_SUGGEST_SKIP_THRESHOLD = 3

# Some resolved candidates display under an alternate "real" name in-game
# (Kickstarter-backer naming rights over the procedural designation — see
# docs/BOXEL_SURVEY_TECH_SPEC.md §6's E3) rather than the procedural string
# generated here — so a genuine arrival at the current target can silently
# fail to advance the walker (on_jump() only matches by exact string). When
# "Confirm alias arrivals (EDSM)" is enabled, an off-sequence jump while a
# target is pending resolves that target's real coordinates via EDSM and
# compares them to the actual arrival StarPos (already in every journal
# event) - a match within this tolerance is treated as "arrived at the
# target under a different name" rather than "jumped somewhere unrelated".
# Real neighboring procedural systems are practically always several ly
# apart, so this comfortably distinguishes "same star" from "a different,
# nearby one" while tolerating minor floating-point/rounding differences
# between EDSM's stored coordinates and the journal's own.
ALIAS_ARRIVAL_COORD_TOLERANCE_LY = 0.5

# "Random" button (above the whole Boxel Survey panel, independent of the
# Sequence/Region Sweep/Waypoints sub-mode): looks for a nearby, real,
# procedural boxel via the same EDSM cube-systems lookup "Find Nearby" uses
# (grounded in the commander's live position, not a guess - see
# docs/BOXEL_SURVEY_TECH_SPEC.md §4.4), then probes random candidate names
# within that boxel via system_known() until it finds one EDSM has no
# record of, and copies that straight to the clipboard. This is still a
# blind string-guess like the rest of Sequence mode (no id64 math - see
# §4.2/4.3), so a returned name isn't guaranteed to resolve on the galaxy
# map; it's just one EDSM has never seen.
RANDOM_CANDIDATE_OFFSET_RANGE = 500
# Real EDSM system_known() calls this may spend across every anchor boxel
# combined before giving up - same order of magnitude as
# MAX_EDSM_SKIP_ATTEMPTS above, so a click never generates unbounded traffic.
RANDOM_MAX_ATTEMPTS = 20
# How many random candidates to try within a single anchor boxel before
# moving on to the next-nearest one - a boxel that's already densely
# EDSM-known needs a few tries before a gap turns up, but a genuinely empty/
# unlisted boxel would waste the whole attempt budget on one anchor.
RANDOM_ATTEMPTS_PER_ANCHOR = 3


def autocopy_enabled() -> bool:
    return config.get_bool(_CFG_AUTOCOPY, default=True)


def skip_visited_enabled() -> bool:
    return config.get_bool(_CFG_SKIP_VISITED, default=True)


def skip_edsm_visited_enabled() -> bool:
    # Opt-in (default off): unlike tier 1, this adds a network call on every
    # advance, so it shouldn't turn on network activity a user didn't ask for.
    return config.get_bool(_CFG_SKIP_EDSM_VISITED, default=False)


def skip_edsm_scanned_enabled() -> bool:
    # Tier 3 - opt-in (default off), same reasoning as tier 2: an extra
    # network call per candidate that shouldn't turn itself on.
    return config.get_bool(_CFG_SKIP_EDSM_SCANNED, default=False)


def confirm_alias_arrival_enabled() -> bool:
    # Opt-in (default off): fires an EDSM lookup on every off-sequence jump
    # while a target is pending, not just on boxel-survey candidates - a
    # commander doing unrelated travel with Sequence mode still selected
    # would otherwise generate background EDSM traffic they didn't ask for.
    return config.get_bool(_CFG_CONFIRM_ALIAS_ARRIVAL, default=False)


@dataclass
class _EdsmSkipResult:
    """Outcome of one chained Tier 2/Tier 3 skip-check run, off the main
    thread."""

    generation: int
    candidate: str
    attempts: int
    gave_up: bool
    lookup_failed: bool
    """True if the check that stopped the chain (kept `candidate`) did so
    because a lookup itself failed/was inconclusive (EDSM down, no data)
    rather than because the candidate was confirmed not-known/not-fully-
    scanned. Distinguishes "EDSM check unavailable" from "found an
    actually-new candidate" in the status line."""
    is_from_jump: bool
    arrival_system: Optional[str]


class BoxelSurveyController:
    def __init__(self) -> None:
        self._walker = BoxelWalker()
        # BoxelWalker isn't internally thread-safe. It's mutated from the Tk
        # main thread (button handlers, handle_event) and from the Tier 2
        # skip-check worker thread below — every _walker.* call must hold this.
        self._walker_lock = threading.Lock()
        self._plugin_dir: Optional[str] = None
        self._current_system: Optional[str] = None
        self._current_pos: Optional[Tuple[float, float, float]] = None
        self._current_cmdr: Optional[str] = None
        self._parent: Optional[tk.Frame] = None

        self._collapsed = True
        self._title_label: Optional[tk.Label] = None
        self._body_frame: Optional[tk.Frame] = None

        # Worker threads doing the EDSM lookup put their (possibly empty)
        # result here; _poll_nearby_queue (main thread, via after()) picks
        # it up. Never touch Tk widgets from the worker thread itself.
        self._nearby_result_queue: "queue.Queue[List[Tuple[float, str]]]" = queue.Queue()

        # Tier 2 (EDSM visited-by-anyone) skip-check plumbing — same
        # worker-thread + queue + after() pattern as "Find Nearby" above.
        self._edsm_skip_generation = 0
        self._edsm_skip_result_queue: "queue.Queue[_EdsmSkipResult]" = queue.Queue()

        # Notable-finds/survey-stats log.
        self._survey_log = survey_log.SurveyLog()
        self._survey_log_lock = threading.Lock()

        # Consecutive manual "Next" clicks since the last confirmed jump —
        # see AUTO_SUGGEST_SKIP_THRESHOLD above.
        self._consecutive_skips = 0

        # Alias-arrival confirmation plumbing (E4/E3 fix) — same
        # worker-thread + queue + after() pattern as everywhere else. Only
        # one field needed (no generation counter): the poll re-checks
        # `_walker.current == candidate` before applying a result, which
        # already discards a stale check (the target moved on for any
        # reason) without needing to track generations explicitly.
        self._alias_result_queue: "queue.Queue[Tuple[str, str]]" = queue.Queue()

        # Region Sweep — the second sub-mode. Owns its own state/widgets;
        # this controller only toggles which sub-frame is visible and fans
        # journal events out to it (see handle_event()).
        self._region_sweep = region_sweep_panel.RegionSweepController()
        self._waypoint_route = waypoint_route_panel.WaypointRouteController()
        self._submode = _SUBMODE_SEQUENCE
        self._sequence_frame: Optional[tk.Frame] = None
        self._region_sweep_frame: Optional[tk.Frame] = None
        self._waypoint_route_frame: Optional[tk.Frame] = None
        self._sequence_button: Optional[tk.Button] = None
        self._region_sweep_button: Optional[tk.Button] = None
        self._waypoint_route_button: Optional[tk.Button] = None
        self._submode_off_colors: Optional[Tuple[str, str]] = None

        # "Random" button plumbing (above the whole panel, sub-mode-
        # independent) — same worker-thread + queue + after() pattern as
        # everywhere else.
        self._random_result_queue: "queue.Queue[Tuple[Optional[str], int, bool]]" = queue.Queue()
        self._random_status_var: Optional[tk.StringVar] = None

        # Per-commander "visited systems" log (visited_systems.py) — every
        # system genuinely arrived at (FSDJump/Location), regardless of
        # which sub-mode is active, kept so "Random" never re-offers a
        # system the commander has already been to just because EDSM
        # hasn't caught up yet. Mutated only from the Tk main thread
        # (handle_event); the Random lookup worker thread only ever reads
        # an immutable frozenset snapshot taken under this lock.
        self._visited_lock = threading.Lock()
        self._visited_systems: Set[str] = set()
        self._visited_count_var: Optional[tk.StringVar] = None

        # Main-panel widgets/vars.
        self._target_var: Optional[tk.StringVar] = None
        self._status_var: Optional[tk.StringVar] = None
        self._seed_var: Optional[tk.StringVar] = None
        self._seed_hint_var: Optional[tk.StringVar] = None
        self._survey_stats_var: Optional[tk.StringVar] = None

        # Settings-tab vars.
        self._autocopy_var: Optional[tk.BooleanVar] = None
        self._skip_visited_var: Optional[tk.BooleanVar] = None
        self._skip_edsm_visited_var: Optional[tk.BooleanVar] = None
        self._skip_edsm_scanned_var: Optional[tk.BooleanVar] = None
        self._confirm_alias_arrival_var: Optional[tk.BooleanVar] = None
        self._export_status_var: Optional[tk.StringVar] = None

    # --- lifecycle ----------------------------------------------------------

    def start(self, plugin_dir: str) -> None:
        self._plugin_dir = plugin_dir
        # Walker state is per-commander (boxel_state.py) and EDMC doesn't
        # know which commander is active until the first journal event -
        # actual restore happens in _switch_cmdr(), called from
        # handle_event() below.

        with self._survey_log_lock:
            self._survey_log = survey_log.load_log(plugin_dir)

        self._region_sweep.start(plugin_dir)
        self._waypoint_route.start(plugin_dir)

    def stop(self) -> None:
        self._region_sweep.stop()
        self._waypoint_route.stop()
        self._save_walker_state()
        self._save_visited_systems()

    def _save_visited_systems(self) -> None:
        if self._plugin_dir is None or self._current_cmdr is None:
            return
        with self._visited_lock:
            snapshot = set(self._visited_systems)
        visited_systems.save_visited(self._plugin_dir, self._current_cmdr, snapshot)

    def _record_visited(self, system_name: str) -> None:
        with self._visited_lock:
            if system_name in self._visited_systems:
                return
            self._visited_systems.add(system_name)
        self._save_visited_systems()
        self._update_visited_count_label()

    def _save_walker_state(self) -> None:
        if self._plugin_dir is None or self._current_cmdr is None:
            return
        with self._walker_lock:
            snap = self._walker.snapshot()
        boxel_state.save_state(
            self._plugin_dir, self._current_cmdr,
            {"seed": snap.seed, "current": snap.current, "visited": snap.visited},
        )

    def _switch_cmdr(self, cmdr: str) -> None:
        """Called whenever the active commander changes, including the
        first journal event of a session - saves the previous commander's
        walker position and visited-systems log (if one was loaded) and
        loads this commander's own, so two commanders on the same install
        never share or overwrite one boxel position or visited log."""
        self._save_walker_state()
        self._save_visited_systems()
        self._current_cmdr = cmdr
        with self._visited_lock:
            self._visited_systems = visited_systems.load_visited(self._plugin_dir, cmdr) if self._plugin_dir else set()
        self._update_visited_count_label()
        saved = boxel_state.load_state(self._plugin_dir, cmdr) if self._plugin_dir else None
        with self._walker_lock:
            self._walker = BoxelWalker()
            if saved:
                try:
                    self._walker.restore(WalkerSnapshot(
                        seed=saved.get("seed"), current=saved.get("current"), visited=saved.get("visited", []),
                    ))
                    logger.info(
                        "Restored boxel walker state for %s: target=%s, %d visited",
                        cmdr, self._walker.current, len(saved.get("visited", [])),
                    )
                except Exception:
                    # Never let a corrupt/old-format state file stop the plugin from loading.
                    logger.exception("Failed to restore saved boxel walker state for %s; starting fresh", cmdr)
            current = self._walker.current
        self._consecutive_skips = 0
        self._set_target(current)
        self._refresh_survey_stats(current)

    # --- journal dispatch -----------------------------------------------------

    def handle_event(self, entry: Dict[str, Any], cmdr: str, system: Optional[str], station: Optional[str], state: Dict[str, Any]) -> None:
        if cmdr and cmdr != self._current_cmdr:
            self._switch_cmdr(cmdr)

        # EDMC keeps `system` current on every call, not just jump events -
        # this is the cheapest reliable source for the "Use Current System" button.
        if system:
            self._current_system = system

        # FSDJump/Location events carry the real galactic [x, y, z] StarPos -
        # this is what lets "Find Nearby" query EDSM without any coordinate
        # decode of our own.
        star_pos = entry.get("StarPos")
        if isinstance(star_pos, (list, tuple)) and len(star_pos) == 3:
            self._current_pos = (star_pos[0], star_pos[1], star_pos[2])

        event = entry.get("event", "")

        # Visited-systems log (visited_systems.py) — recorded on every real
        # arrival regardless of which sub-mode is selected, unlike
        # BoxelWalker's own internal visited set (Sequence-only, driven by
        # on_jump() below). This is what lets "Random" recognize a system
        # the commander has already been to even when EDSM itself doesn't
        # know about it yet.
        if event in ("FSDJump", "Location"):
            arrived_system = entry.get("StarSystem")
            if arrived_system:
                self._record_visited(arrived_system)

        if event == "Scan":
            self._record_scan_event(system, entry)
        elif event in ("FSSBodySignals", "SAASignalsFound"):
            self._record_signals_event(system, entry)

        # Region Sweep and Waypoint Route each track their own current
        # system/position and handle FSDJump/Location, Scan and signal
        # events on their own terms (gated internally by their own
        # `.active` flag) - always dispatched regardless of which sub-mode
        # this panel currently shows, so switching sub-modes mid-session
        # never starts either one from nothing.
        self._region_sweep.handle_event(entry, cmdr, system, station, state)
        self._waypoint_route.handle_event(entry, cmdr, system, station, state)

        if self._submode != _SUBMODE_SEQUENCE:
            return
        if event in ("Scan", "FSSBodySignals", "SAASignalsFound"):
            return
        if event not in ("FSDJump", "Location"):
            return

        star_system = entry.get("StarSystem")
        if not star_system:
            return

        with self._walker_lock:
            next_target = self._walker.on_jump(star_system, skip_visited=skip_visited_enabled())
        if next_target is None:
            # Arrived somewhere that doesn't string-match the pending
            # target - normally means the commander jumped off-sequence on
            # purpose, but could also be a genuine arrival at the target
            # under an alternate display name (E3/E4, see
            # docs/BOXEL_SURVEY_TECH_SPEC.md §6). Opt-in EDSM confirmation
            # only, since this fires on every off-sequence jump, not just
            # boxel candidates.
            with self._walker_lock:
                pending_target = self._walker.current
            if confirm_alias_arrival_enabled() and pending_target is not None and self._current_pos is not None:
                self._maybe_confirm_alias_arrival(pending_target, star_system, self._current_pos)
            return

        # A confirmed jump means the previous target was a real, reachable
        # system - reset the "stuck" streak that drives the auto-suggest below.
        self._consecutive_skips = 0
        self._set_target(next_target)
        if skip_edsm_visited_enabled() or skip_edsm_scanned_enabled():
            self._set_status(f"Arrived {star_system} — checking EDSM for already-known systems...")
            self._maybe_skip_edsm(next_target, is_from_jump=True, arrival_system=star_system)
        elif autocopy_enabled():
            self._copy_current()
            self._set_status(f"Arrived {star_system} — copied next target")
        else:
            self._set_status(f"Arrived {star_system} — next target ready")

    def _boxel_key_for(self, system: str) -> Optional[str]:
        parsed = boxel.parse_system_name(system)
        if parsed is None:
            return None
        return survey_log.boxel_key(parsed.sector, parsed.cube_id)

    def _record_scan_event(self, system: Optional[str], entry: Dict[str, Any]) -> None:
        body_name = entry.get("BodyName")
        if not system or not body_name:
            return
        with self._survey_log_lock:
            self._survey_log.record_scan(
                system, body_name, boxel_key=self._boxel_key_for(system),
                planet_class=entry.get("PlanetClass"), terraform_state=entry.get("TerraformState") or None,
                distance_ls=entry.get("DistanceFromArrivalLS"),
            )
        self._persist_survey_log_and_refresh(system)

    def _record_signals_event(self, system: Optional[str], entry: Dict[str, Any]) -> None:
        body_name = entry.get("BodyName")
        signals = entry.get("Signals")
        if not system or not body_name or not isinstance(signals, list):
            return
        bio_signal_count = 0
        for signal in signals:
            if isinstance(signal, dict) and signal.get("Type") == survey_log.BIO_SIGNAL_TYPE:
                bio_signal_count += signal.get("Count", 0) or 0
        if bio_signal_count <= 0:
            return
        with self._survey_log_lock:
            self._survey_log.record_signals(
                system, body_name, boxel_key=self._boxel_key_for(system), bio_signal_count=bio_signal_count,
            )
        self._persist_survey_log_and_refresh(system)

    def _persist_survey_log_and_refresh(self, system: str) -> None:
        if self._plugin_dir is not None:
            with self._survey_log_lock:
                survey_log.save_log(self._plugin_dir, self._survey_log)
        self._refresh_survey_stats(system)

    def _refresh_survey_stats(self, system: Optional[str]) -> None:
        """Recompute and display the current boxel's stats line, if `system`
        is procedural-shaped. If not (or `system` is None), leave whatever
        stats are already showing rather than clear them - e.g. while
        docked at a hand-named hub between boxel-survey legs."""
        if not system:
            return
        key = self._boxel_key_for(system)
        if key is None:
            return
        with self._survey_log_lock:
            stats = self._survey_log.boxel_stats(key)
        self._set_survey_stats(stats)

    # --- main-panel widgets -------------------------------------------------

    def build_panel(self, parent: tk.Frame) -> None:
        self._parent = parent

        self._submode = config.get_str(_CFG_SUBMODE) or _SUBMODE_SEQUENCE
        if self._submode not in _SUBMODES:
            self._submode = _SUBMODE_SEQUENCE
        self._region_sweep.set_active(self._submode == _SUBMODE_REGION_SWEEP)
        self._waypoint_route.set_active(self._submode == _SUBMODE_WAYPOINTS)
        self._collapsed = config.get_bool(_CFG_COLLAPSED, default=True)

        # ui.py's create_plugin_app() gives every PANEL_PLACEMENT feature its
        # own dedicated child frame (see _stack_features()), separated from
        # its siblings by panelkit.add_separator() - so this can just start
        # at row 0 of its own frame, no cross-feature row coordination needed.

        # "Random" sits above the collapsible title itself (stays visible and
        # usable even when the section is collapsed, and works regardless of
        # which sub-mode is selected - it doesn't touch the walker at all).
        random_row = tk.Frame(parent)
        random_row.grid(row=0, column=0, columnspan=3, sticky=tk.W, pady=(0, 4))
        self._random_status_var = tk.StringVar(value="")
        tk.Button(random_row, text="Random", command=self._on_random).pack(side=tk.LEFT)
        panelkit.wrap_label(random_row, textvariable=self._random_status_var, fg="grey").pack(
            side=tk.LEFT, padx=(6, 0),
        )

        self._title_label = tk.Label(parent, text=self._title_text(), font=panelkit.bold_font(parent), cursor="hand2")
        self._title_label.grid(row=1, column=0, columnspan=3, sticky=tk.W)
        self._title_label.bind("<Button-1>", self._toggle_collapsed)

        self._body_frame = tk.Frame(parent)
        self._body_frame.grid(row=2, column=0, columnspan=3, sticky=tk.W)

        mode_row = tk.Frame(self._body_frame)
        mode_row.grid(row=0, column=0, columnspan=3, sticky=tk.W, pady=(2, 4))
        self._sequence_button = tk.Button(
            mode_row, text="Sequence", command=lambda: self._on_submode_click(_SUBMODE_SEQUENCE),
        )
        self._sequence_button.pack(side=tk.LEFT)
        self._region_sweep_button = tk.Button(
            mode_row, text="Region Sweep", command=lambda: self._on_submode_click(_SUBMODE_REGION_SWEEP),
        )
        self._region_sweep_button.pack(side=tk.LEFT, padx=(4, 0))
        self._waypoint_route_button = tk.Button(
            mode_row, text="Waypoints", command=lambda: self._on_submode_click(_SUBMODE_WAYPOINTS),
        )
        self._waypoint_route_button.pack(side=tk.LEFT, padx=(4, 0))
        # Same button-row-plus-grid_remove toggle pattern ui.py itself uses
        # for the Powerplay/Exploration/Mining/... mode select - there's no
        # notebook/tab widget at this level anywhere in WNTB to reuse instead.
        self._submode_off_colors = panelkit.capture_toggle_off_colors(self._sequence_button)

        self._sequence_frame = tk.Frame(self._body_frame)
        self._sequence_frame.grid(row=1, column=0, columnspan=3, sticky=tk.W)
        self._build_sequence_panel(self._sequence_frame)

        self._region_sweep_frame = tk.Frame(self._body_frame)
        self._region_sweep_frame.grid(row=1, column=0, columnspan=3, sticky=tk.W)
        self._region_sweep.build_panel(self._region_sweep_frame)

        self._waypoint_route_frame = tk.Frame(self._body_frame)
        self._waypoint_route_frame.grid(row=1, column=0, columnspan=3, sticky=tk.W)
        self._waypoint_route.build_panel(self._waypoint_route_frame)

        self._apply_submode_visibility()
        self._apply_collapsed_visibility()
        panelkit.apply_theme_deep(parent)
        parent.after(200, self._poll_random_queue)

    def _title_text(self) -> str:
        return f"{'▸' if self._collapsed else '▾'} Boxel Survey"

    def _apply_collapsed_visibility(self) -> None:
        if self._body_frame is not None:
            (self._body_frame.grid_remove if self._collapsed else self._body_frame.grid)()
        if self._title_label is not None:
            self._title_label.config(text=self._title_text())

    def _toggle_collapsed(self, _event: Optional[tk.Event] = None) -> None:
        self._collapsed = not self._collapsed
        config.set(_CFG_COLLAPSED, self._collapsed)
        self._apply_collapsed_visibility()

    def _apply_submode_visibility(self) -> None:
        frames_by_submode = {
            _SUBMODE_SEQUENCE: self._sequence_frame,
            _SUBMODE_REGION_SWEEP: self._region_sweep_frame,
            _SUBMODE_WAYPOINTS: self._waypoint_route_frame,
        }
        for submode, frame in frames_by_submode.items():
            if frame is not None:
                (frame.grid if self._submode == submode else frame.grid_remove)()

        buttons_by_submode = {
            _SUBMODE_SEQUENCE: self._sequence_button,
            _SUBMODE_REGION_SWEEP: self._region_sweep_button,
            _SUBMODE_WAYPOINTS: self._waypoint_route_button,
        }
        if self._submode_off_colors is not None:
            for submode, button in buttons_by_submode.items():
                if button is not None:
                    panelkit.apply_toggle_button_state(button, self._submode == submode, self._submode_off_colors)

    def _on_submode_click(self, submode: str) -> None:
        self._submode = submode
        config.set(_CFG_SUBMODE, submode)
        self._region_sweep.set_active(submode == _SUBMODE_REGION_SWEEP)
        self._waypoint_route.set_active(submode == _SUBMODE_WAYPOINTS)
        self._apply_submode_visibility()

    def _build_sequence_panel(self, parent: tk.Frame) -> None:
        self._target_var = tk.StringVar(value=_NO_TARGET_TEXT)
        self._status_var = tk.StringVar(value="")
        self._seed_var = tk.StringVar(value="")
        self._seed_hint_var = tk.StringVar(value=_HINT_EMPTY)
        self._survey_stats_var = tk.StringVar(value=_NO_SURVEY_STATS_TEXT)

        tk.Label(parent, text="Target:").grid(row=3, column=0, sticky=tk.W)
        panelkit.wrap_label(parent, textvariable=self._target_var, anchor="w").grid(
            row=3, column=1, columnspan=2, sticky=tk.W,
        )

        button_row = tk.Frame(parent)
        button_row.grid(row=4, column=0, columnspan=3, sticky=tk.W)
        tk.Button(button_row, text="< Prev", command=self._on_prev).pack(side=tk.LEFT)
        tk.Button(button_row, text="Next >", command=self._on_next).pack(side=tk.LEFT, padx=(4, 0))
        tk.Button(button_row, text="Copy", command=self._copy_current).pack(side=tk.LEFT, padx=(4, 0))

        tk.Label(parent, text="Seed system:").grid(row=5, column=0, sticky=tk.W)
        tk.Entry(parent, textvariable=self._seed_var, width=28).grid(row=5, column=1, sticky=tk.W)

        seed_button_row = tk.Frame(parent)
        seed_button_row.grid(row=5, column=2, sticky=tk.W)
        tk.Button(seed_button_row, text="Use Current", command=self._on_use_current).pack(side=tk.LEFT)
        tk.Button(seed_button_row, text="Set", command=lambda: self._on_set_seed(self._seed_var.get())).pack(
            side=tk.LEFT, padx=(4, 0),
        )

        tk.Button(parent, text="Find Nearby (EDSM)", command=self._on_find_nearby).grid(
            row=6, column=0, columnspan=3, sticky=tk.W,
        )

        seed_hint_label = panelkit.wrap_label(parent, textvariable=self._seed_hint_var, fg="grey")
        seed_hint_label.grid(row=7, column=0, columnspan=3, sticky=tk.W)
        # trace_add (not a static grid label) since this needs to re-validate
        # on every keystroke, before the user commits to clicking Set.
        self._seed_var.trace_add("write", lambda *_args: self._update_seed_hint())

        # Export Survey Log lives in Settings (see build_settings) - it's an
        # occasional action, not something that needs a button taking up
        # space in the main panel on every load.
        panelkit.wrap_label(parent, textvariable=self._survey_stats_var, anchor="w").grid(
            row=8, column=0, columnspan=3, sticky=tk.W,
        )

        panelkit.wrap_label(parent, textvariable=self._status_var, fg="grey").grid(
            row=9, column=0, columnspan=3, sticky=tk.W,
        )

        # theme.update() (called once, on the mode frame, from ui.py) only
        # recolors direct children - not enough for button_row/seed_button_row/
        # survey_row's own nested buttons. Walk the whole subtree instead.
        panelkit.apply_theme_deep(parent)

        with self._walker_lock:
            current_target = self._walker.current
        self._set_target(current_target)
        self._refresh_survey_stats(current_target)

        parent.after(200, self._poll_nearby_queue)
        parent.after(200, self._poll_edsm_skip_queue)
        parent.after(200, self._poll_alias_queue)

    def _set_target(self, name: Optional[str]) -> None:
        if self._target_var is not None:
            self._target_var.set(name or _NO_TARGET_TEXT)

    def _set_status(self, message: str) -> None:
        if self._status_var is not None:
            self._status_var.set(message)

    def _set_survey_stats(self, stats: dict) -> None:
        if self._survey_stats_var is None:
            return
        self._survey_stats_var.set(
            f"Surveyed: {stats.get('systems', 0)} systems | {stats.get('elw', 0)} ELW | "
            f"{stats.get('ww', 0)} WW | {stats.get('aw', 0)} AW | {stats.get('terraformable', 0)} "
            f"terraformable | {stats.get('bio', 0)} bio"
        )

    def _update_seed_hint(self) -> None:
        try:
            if self._seed_var is None or self._seed_hint_var is None:
                return
            text = self._seed_var.get().strip()
            if not text:
                self._seed_hint_var.set(_HINT_EMPTY)
                return
            self._seed_hint_var.set(_HINT_VALID if boxel.is_procedural_name(text) else _HINT_INVALID)
        except Exception:
            # trace_add callbacks run inside Tk's event loop, which silently
            # swallows exceptions when running windowed (no stderr) instead
            # of surfacing them anywhere, so log explicitly.
            logger.exception("_update_seed_hint failed")

    def _copy_current(self) -> None:
        """Copy the currently displayed target to the clipboard, if there is one."""
        if self._parent is None or self._target_var is None:
            return
        text = self._target_var.get()
        if not text or text == _NO_TARGET_TEXT:
            self._set_status("Nothing to copy yet")
            return
        if panelkit.copy_to_clipboard(self._parent, text):
            self._set_status(f"Copied: {text}")

    def _set_export_status(self, message: str) -> None:
        if self._export_status_var is not None:
            self._export_status_var.set(message)

    def _on_export_survey_log(self) -> None:
        if self._plugin_dir is None:
            self._set_export_status("Plugin not fully started yet")
            return
        with self._survey_log_lock:
            rows = self._survey_log.export_rows()
        if not rows:
            self._set_export_status("No notable finds recorded yet")
            return
        path = os.path.join(self._plugin_dir, EXPORT_FILENAME)
        try:
            with open(path, "w", newline="", encoding="utf-8") as fh:
                writer = csv.DictWriter(fh, fieldnames=survey_log.EXPORT_FIELDNAMES)
                writer.writeheader()
                writer.writerows(rows)
        except OSError:
            logger.exception("_on_export_survey_log failed")
            self._set_export_status("Failed to export survey log — see EDMarketConnector.log")
            return
        self._set_export_status(f"Exported {len(rows)} notable finds to {path}")

    def _on_set_seed(self, name: str) -> None:
        name = name.strip()
        if not name:
            self._set_status("Enter a system name first")
            return
        try:
            with self._walker_lock:
                self._walker.set_seed(name)
                current = self._walker.current
        except ValueError as exc:
            self._set_status(str(exc))
            return
        self._consecutive_skips = 0
        self._set_target(current)
        self._set_status(f"Survey started at {name}")

    def _on_use_current(self) -> None:
        if not self._current_system:
            self._set_status("Current system not known yet")
            return
        if self._seed_var is not None:
            self._seed_var.set(self._current_system)
        self._on_set_seed(self._current_system)

    def _on_next(self) -> None:
        try:
            with self._walker_lock:
                target = self._walker.advance(skip_visited=skip_visited_enabled())
            self._set_target(target)
            # Manual Next is how a commander skips past a candidate that
            # doesn't actually exist in-game (there's no journal signal for
            # "galaxy map couldn't plot this" to detect it any other way).
            # AUTO_SUGGEST_SKIP_THRESHOLD in a row without a confirmed jump
            # (reset in handle_event) means this mass-code boxel is likely
            # exhausted - fall back to a real EDSM lookup instead of
            # continuing to guess blindly.
            self._consecutive_skips += 1
            if self._consecutive_skips >= AUTO_SUGGEST_SKIP_THRESHOLD:
                self._consecutive_skips = 0
                self._start_nearby_lookup(auto=True)
            if target and (skip_edsm_visited_enabled() or skip_edsm_scanned_enabled()):
                self._set_status("Checking EDSM for already-known systems...")
                self._maybe_skip_edsm(target, is_from_jump=False)
            else:
                self._set_status("Manual advance" if target else "Set a seed system first")
        except Exception:
            # Tkinter swallows exceptions raised from widget commands when
            # running windowed (no console/stderr), so log explicitly.
            logger.exception("_on_next failed")

    def _on_prev(self) -> None:
        try:
            with self._walker_lock:
                target = self._walker.retreat()
        except ValueError:
            self._set_status("Already at the start of the sequence")
            return
        except Exception:
            logger.exception("_on_prev failed")
            return
        self._consecutive_skips = 0
        self._set_target(target)
        self._set_status("Manual retreat" if target else "Set a seed system first")

    def _on_find_nearby(self) -> None:
        """Ask EDSM which real, known systems exist near the commander's
        current position, and fill the seed entry with the nearest
        procedural-shaped one that isn't in the current boxel - a
        substitute for the spatial-adjacency math this feature doesn't have."""
        self._start_nearby_lookup(auto=False)

    def _start_nearby_lookup(self, *, auto: bool) -> None:
        """Shared by the manual "Find Nearby (EDSM)" button and the
        automatic exhausted-boxel fallback in _on_next() - `auto` only
        changes status-line wording (and silences the "nothing found"/
        "position unknown" messages, so an automatic background check that
        comes up empty doesn't overwrite whatever the manual-advance status
        already said)."""
        if self._current_pos is None:
            if not auto:
                self._set_status("Current position not known yet")
            return
        exclude_cube = None
        with self._walker_lock:
            current = self._walker.current
        if current:
            parsed = boxel.parse_system_name(current)
            if parsed is not None:
                exclude_cube = parsed.cube_id
        if not auto:
            self._set_status("Looking up nearby systems on EDSM...")
        x, y, z = self._current_pos
        threading.Thread(
            target=self._nearby_lookup_worker, args=(x, y, z, exclude_cube, auto), daemon=True,
        ).start()

    def _nearby_lookup_worker(
        self, x: float, y: float, z: float, exclude_cube: Optional[str], auto: bool,
    ) -> None:
        """Runs off the main thread — must not touch any Tk widget directly."""
        candidates: List[Tuple[float, str]] = []
        try:
            for entry in edsm_client.nearby_systems(x, y, z):
                name = entry.get("name")
                if not name:
                    continue
                parsed = boxel.parse_system_name(name)
                if parsed is None:
                    continue
                if exclude_cube is not None and parsed.cube_id == exclude_cube:
                    continue
                candidates.append((entry.get("distance", 0.0), name))
            candidates.sort(key=lambda pair: pair[0])
        except Exception:
            logger.exception("_nearby_lookup_worker failed")
            candidates = []
        self._nearby_result_queue.put((candidates, auto))

    def _poll_nearby_queue(self) -> None:
        """Runs on the main thread via after() — safe to touch widgets here."""
        try:
            candidates, auto = self._nearby_result_queue.get_nowait()
        except queue.Empty:
            pass
        else:
            if not candidates:
                if not auto:
                    self._set_status("No nearby procedural systems found via EDSM")
            else:
                _, nearest = candidates[0]
                if self._seed_var is not None:
                    self._seed_var.set(nearest)
                if auto:
                    self._set_status(
                        f"{AUTO_SUGGEST_SKIP_THRESHOLD} candidates in a row weren't reachable — "
                        f"nearest real system via EDSM: {nearest} ({len(candidates)} found) — "
                        f"click Set to jump the survey there"
                    )
                else:
                    self._set_status(f"Nearest boxel via EDSM: {nearest} ({len(candidates)} found) — set in seed entry")
        if self._parent is not None:
            self._parent.after(200, self._poll_nearby_queue)

    def _on_random(self) -> None:
        """Look up a real, EDSM-known boxel near the commander's live
        position, then probe random candidate names inside it until one
        turns up that's neither EDSM-known nor already in this commander's
        own visited-systems log — and copy that name straight to the
        clipboard. Independent of Sequence mode's seed/target/walker - this
        never touches `_walker`."""
        if self._current_pos is None:
            self._set_random_status("Current position not known yet")
            return
        self._set_random_status("Looking for an undiscovered system nearby...")
        x, y, z = self._current_pos
        with self._visited_lock:
            visited_snapshot = frozenset(self._visited_systems)
        threading.Thread(
            target=self._random_lookup_worker, args=(x, y, z, visited_snapshot), daemon=True,
        ).start()

    @staticmethod
    def _random_candidate_near(anchor: "boxel.ProcSystemName") -> str:
        """One random candidate name in the same (sector, cube, mass code)
        boxel as `anchor`, offset from its own primary/secondary index by a
        random amount in either direction (clamped at 0 - these indices
        never go negative)."""
        new_primary = max(0, anchor.primary + random.randint(-RANDOM_CANDIDATE_OFFSET_RANGE, RANDOM_CANDIDATE_OFFSET_RANGE))
        if anchor.secondary is None:
            candidate = replace(anchor, primary=new_primary)
        else:
            new_secondary = max(
                0, anchor.secondary + random.randint(-RANDOM_CANDIDATE_OFFSET_RANGE, RANDOM_CANDIDATE_OFFSET_RANGE),
            )
            candidate = replace(anchor, primary=new_primary, secondary=new_secondary)
        return candidate.format()

    def _random_lookup_worker(self, x: float, y: float, z: float, visited: FrozenSet[str]) -> None:
        """Runs off the main thread — must not touch any Tk widget or
        `_visited_systems` directly; `visited` is an immutable snapshot
        taken on the main thread before this thread started."""
        result: Optional[str] = None
        attempts = 0
        lookup_failed = False
        try:
            anchors: List[Tuple[float, "boxel.ProcSystemName"]] = []
            for entry in edsm_client.nearby_systems(x, y, z):
                name = entry.get("name")
                if not name:
                    continue
                parsed = boxel.parse_system_name(name)
                if parsed is None:
                    continue
                anchors.append((entry.get("distance", 0.0), parsed))
            anchors.sort(key=lambda pair: pair[0])

            for _, anchor in anchors:
                if attempts >= RANDOM_MAX_ATTEMPTS or result is not None:
                    break
                for _ in range(RANDOM_ATTEMPTS_PER_ANCHOR):
                    if attempts >= RANDOM_MAX_ATTEMPTS:
                        break
                    candidate = self._random_candidate_near(anchor)
                    attempts += 1
                    if candidate in visited:
                        # Already been there ourselves - skip without
                        # spending an EDSM call on it at all.
                        continue
                    known = edsm_client.system_known(candidate)
                    if known is False:
                        result = candidate
                        break
                    if known is None:
                        lookup_failed = True
        except Exception:
            logger.exception("_random_lookup_worker failed")
        self._random_result_queue.put((result, attempts, lookup_failed))

    def _poll_random_queue(self) -> None:
        """Runs on the main thread via after() — safe to touch widgets here."""
        try:
            result, attempts, lookup_failed = self._random_result_queue.get_nowait()
        except queue.Empty:
            pass
        else:
            if result is not None:
                if self._parent is not None and panelkit.copy_to_clipboard(self._parent, result):
                    self._set_random_status(f"Copied: {result} (not listed in EDSM)")
                else:
                    self._set_random_status(f"Found (not listed in EDSM) but couldn't copy: {result}")
            elif attempts == 0:
                self._set_random_status("No known systems near current position to search from")
            elif lookup_failed:
                self._set_random_status("EDSM check unavailable — try again")
            else:
                self._set_random_status(f"No undiscovered candidate found after {attempts} tries — try again")
        if self._parent is not None:
            self._parent.after(200, self._poll_random_queue)

    def _set_random_status(self, message: str) -> None:
        if self._random_status_var is not None:
            self._random_status_var.set(message)

    def _update_visited_count_label(self) -> None:
        if self._visited_count_var is None:
            return
        with self._visited_lock:
            count = len(self._visited_systems)
        self._visited_count_var.set(f"{count} system{'s' if count != 1 else ''} logged as visited")

    def _on_clear_visited(self) -> None:
        with self._visited_lock:
            count = len(self._visited_systems)
        if count == 0:
            self._set_random_status("Visited systems log is already empty")
            return
        if not messagebox.askyesno(
            "Clear Visited Systems Log",
            f"Clear all {count} system(s) from this commander's visited-systems log?\n\n"
            "This only affects which systems \"Random\" treats as already-visited - it doesn't undo "
            "any actual exploration progress.",
        ):
            return
        with self._visited_lock:
            self._visited_systems = set()
        self._save_visited_systems()
        self._update_visited_count_label()
        self._set_random_status("Visited systems log cleared")

    def _maybe_skip_edsm(
        self, target: str, *, is_from_jump: bool, arrival_system: Optional[str] = None,
    ) -> None:
        """Kicks a background thread that checks `target` (and, chained,
        however many further candidates follow) against whichever of
        Tier 2 ("visited by anyone")/Tier 3 ("fully scanned by anyone")
        skip filtering is currently enabled, skipping past any candidate
        either one confirms. Tagged with a generation counter so a later
        call (a fresher Next click or jump) can invalidate this one
        before it's applied."""
        self._edsm_skip_generation += 1
        generation = self._edsm_skip_generation
        threading.Thread(
            target=self._edsm_skip_worker, args=(target, generation, is_from_jump, arrival_system), daemon=True,
        ).start()

    @staticmethod
    def _edsm_skip_check(candidate: str, *, tier2: bool, tier3: bool) -> Tuple[bool, bool]:
        """Returns `(should_skip, lookup_failed)` for one candidate.
        `tier2`/`tier3` gate which check(s) actually run - a tier that's
        off is never called, so a commander with only Tier 3 enabled
        doesn't pay for a Tier 2 lookup they didn't ask for. Tier 2 is
        checked first (cheaper - a single small `system` lookup) and
        short-circuits Tier 3 (a heavier `bodies` fetch) once it already
        confirms a skip. `lookup_failed` is only set by whichever check
        actually ran and returned `None` (couldn't determine) - never by
        a tier that's disabled."""
        if tier2:
            known = edsm_client.system_known(candidate)
            if known is True:
                return True, False
            if known is None:
                return False, True
        if tier3:
            fully_scanned = edsm_client.system_fully_scanned(candidate)
            if fully_scanned is True:
                return True, False
            if fully_scanned is None:
                return False, True
        return False, False

    def _edsm_skip_worker(
        self, candidate: str, generation: int, is_from_jump: bool, arrival_system: Optional[str],
    ) -> None:
        """Runs off the main thread — must not touch any Tk widget directly."""
        attempts = 0
        gave_up = False
        lookup_failed = False
        skip_visited = skip_visited_enabled()
        tier2 = skip_edsm_visited_enabled()
        tier3 = skip_edsm_scanned_enabled()
        try:
            for _ in range(MAX_EDSM_SKIP_ATTEMPTS):
                should_skip, lookup_failed = self._edsm_skip_check(candidate, tier2=tier2, tier3=tier3)
                if not should_skip:
                    # Confirmed not-known/not-fully-scanned, or the
                    # relevant lookup(s) failed - either way, keep this
                    # candidate rather than risk skipping a valid one on
                    # a flaky/down EDSM.
                    break
                with self._walker_lock:
                    next_candidate = self._walker.advance(skip_visited=skip_visited)
                if next_candidate is None:
                    break
                candidate = next_candidate
                attempts += 1
            else:
                gave_up = True
        except Exception:
            logger.exception("_edsm_skip_worker failed")
        self._edsm_skip_result_queue.put(
            _EdsmSkipResult(generation, candidate, attempts, gave_up, lookup_failed, is_from_jump, arrival_system),
        )

    def _poll_edsm_skip_queue(self) -> None:
        """Runs on the main thread via after() — safe to touch widgets here."""
        try:
            result = self._edsm_skip_result_queue.get_nowait()
        except queue.Empty:
            pass
        else:
            if result.generation != self._edsm_skip_generation:
                pass  # superseded by a newer Next click or jump — discard
            else:
                self._set_target(result.candidate)
                if result.gave_up:
                    self._set_status(
                        f"EDSM check capped after {result.attempts} already-known systems "
                        f"— showing {result.candidate} anyway"
                    )
                elif result.lookup_failed:
                    self._set_status("EDSM check unavailable — showing candidate anyway")
                elif result.attempts:
                    plural = "s" if result.attempts != 1 else ""
                    self._set_status(
                        f"Skipped {result.attempts} already-known/fully-scanned system{plural} "
                        f"— next: {result.candidate}"
                    )
                elif result.is_from_jump:
                    self._set_status(f"Arrived {result.arrival_system} — next target ready")
                else:
                    self._set_status("Manual advance")
                if result.is_from_jump and autocopy_enabled():
                    self._copy_current()
        if self._parent is not None:
            self._parent.after(200, self._poll_edsm_skip_queue)

    def _maybe_confirm_alias_arrival(
        self, candidate: str, arrived_name: str, pos: Tuple[float, float, float],
    ) -> None:
        """Kicks a background thread that resolves `candidate`'s real
        coordinates via EDSM and compares them against `pos` (the arrival's
        actual StarPos) - see ALIAS_ARRIVAL_COORD_TOLERANCE_LY above for the
        full rationale (E3/E4)."""
        threading.Thread(
            target=self._alias_check_worker, args=(candidate, arrived_name, pos), daemon=True,
        ).start()

    def _alias_check_worker(self, candidate: str, arrived_name: str, pos: Tuple[float, float, float]) -> None:
        """Runs off the main thread — must not touch any Tk widget directly."""
        try:
            resolved = edsm_client.systems_coords([candidate])
        except Exception:
            logger.exception("_alias_check_worker failed for %r", candidate)
            return
        candidate_pos = resolved.get(candidate)
        if candidate_pos is None:
            return
        distance = math.sqrt(sum((a - b) ** 2 for a, b in zip(candidate_pos, pos)))
        if distance <= ALIAS_ARRIVAL_COORD_TOLERANCE_LY:
            self._alias_result_queue.put((candidate, arrived_name))

    def _poll_alias_queue(self) -> None:
        """Runs on the main thread via after() — safe to touch widgets here."""
        try:
            candidate, arrived_name = self._alias_result_queue.get_nowait()
        except queue.Empty:
            pass
        else:
            with self._walker_lock:
                still_pending = self._walker.current == candidate
                if still_pending:
                    next_target = self._walker.advance(skip_visited=skip_visited_enabled())
            if still_pending:
                self._consecutive_skips = 0
                self._set_target(next_target)
                self._set_status(
                    f"Arrived {arrived_name} — confirmed via EDSM as {candidate} under a different "
                    f"display name — next target ready"
                )
                if autocopy_enabled():
                    self._copy_current()
        if self._parent is not None:
            self._parent.after(200, self._poll_alias_queue)

    # --- Settings tab --------------------------------------------------------

    def build_settings(self, notebook: nb.Notebook) -> None:
        frame = nb.Frame(notebook)
        frame.columnconfigure(0, weight=1)
        notebook.add(frame, text="Boxel Survey")

        self._autocopy_var = tk.BooleanVar(value=autocopy_enabled())
        self._skip_visited_var = tk.BooleanVar(value=skip_visited_enabled())
        self._skip_edsm_visited_var = tk.BooleanVar(value=skip_edsm_visited_enabled())
        self._skip_edsm_scanned_var = tk.BooleanVar(value=skip_edsm_scanned_enabled())
        self._confirm_alias_arrival_var = tk.BooleanVar(value=confirm_alias_arrival_enabled())

        nb.Label(frame, text="Boxel Survey", font=("TkDefaultFont", 9, "bold")).grid(
            row=0, column=0, sticky=tk.W, padx=10, pady=(10, 4),
        )
        nb.Label(
            frame, text=panelkit.WORK_IN_PROGRESS_NOTE, wraplength=440, justify=tk.LEFT, foreground="#c07000",
        ).grid(row=99, column=0, sticky=tk.W, padx=10, pady=(14, 10))
        nb.Checkbutton(
            frame, text="Auto-copy next target to clipboard on jump", variable=self._autocopy_var,
        ).grid(row=1, column=0, sticky=tk.W, padx=10)
        nb.Checkbutton(
            frame, text="Skip systems already visited this session", variable=self._skip_visited_var,
        ).grid(row=2, column=0, sticky=tk.W, padx=10)
        nb.Checkbutton(
            frame, text="Skip systems already visited by anyone (EDSM)", variable=self._skip_edsm_visited_var,
        ).grid(row=3, column=0, sticky=tk.W, padx=10)
        nb.Checkbutton(
            frame, text="Skip systems already fully scanned in EDSM (adds another network call per candidate)",
            variable=self._skip_edsm_scanned_var,
        ).grid(row=4, column=0, sticky=tk.W, padx=10)
        nb.Checkbutton(
            frame,
            text="Confirm off-sequence arrivals against EDSM (catches a target that resolved under a"
                 " different display name)",
            variable=self._confirm_alias_arrival_var,
        ).grid(row=5, column=0, sticky=tk.W, padx=10, pady=(0, 10))

        # Export Survey Log - moved off the main panel (2026-09-19, R.W.
        # Harper) since it's an occasional action, not something that needs
        # a button taking up space there on every load. The stats line
        # itself (surveyed system/ELW/WW/AW/terraformable/bio counts) stays
        # on the main panel - only the export action moved.
        self._export_status_var = tk.StringVar(value="")
        nb.Button(frame, text="Export Survey Log", command=self._on_export_survey_log).grid(
            row=6, column=0, sticky=tk.W, padx=10,
        )
        nb.Label(frame, textvariable=self._export_status_var).grid(
            row=7, column=0, sticky=tk.W, padx=10, pady=(0, 10),
        )

        # "Random" button's visited-systems log (visited_systems.py) - a
        # per-commander history of every system actually arrived at, kept so
        # Random never re-offers a system the commander has already been to
        # just because EDSM hasn't caught up yet. Clearing it only affects
        # what Random treats as "already been there" - it's not tied to any
        # sub-mode's own progress.
        nb.Label(frame, text="Random button", font=("TkDefaultFont", 9, "bold")).grid(
            row=8, column=0, sticky=tk.W, padx=10, pady=(0, 4),
        )
        self._visited_count_var = tk.StringVar(value="")
        self._update_visited_count_label()
        nb.Label(frame, textvariable=self._visited_count_var).grid(
            row=9, column=0, sticky=tk.W, padx=10,
        )
        nb.Button(frame, text="Clear Visited Systems Log", command=self._on_clear_visited).grid(
            row=10, column=0, sticky=tk.W, padx=10, pady=(0, 10),
        )

        # Region Sweep/Waypoint Route each get their own Settings tab, built
        # by their own controller.
        self._region_sweep.build_settings(notebook)
        self._waypoint_route.build_settings(notebook)

    def save_settings(self) -> None:
        self._region_sweep.save_settings()
        self._waypoint_route.save_settings()
        if self._autocopy_var is None:
            return
        config.set(_CFG_AUTOCOPY, self._autocopy_var.get())
        config.set(_CFG_SKIP_VISITED, self._skip_visited_var.get())
        config.set(_CFG_SKIP_EDSM_VISITED, self._skip_edsm_visited_var.get())
        config.set(_CFG_SKIP_EDSM_SCANNED, self._skip_edsm_scanned_var.get())
        config.set(_CFG_CONFIRM_ALIAS_ARRIVAL, self._confirm_alias_arrival_var.get())


controller = BoxelSurveyController()


def start(plugin_dir: str) -> None:
    controller.start(plugin_dir)


def stop() -> None:
    controller.stop()


def handle_event(entry: Dict[str, Any], cmdr: str, system: Optional[str], station: Optional[str], state: Dict[str, Any]) -> None:
    controller.handle_event(entry, cmdr, system, station, state)


def build_panel(parent: tk.Frame) -> None:
    controller.build_panel(parent)


def build_settings(notebook: nb.Notebook) -> None:
    controller.build_settings(notebook)


def save_settings() -> None:
    controller.save_settings()
