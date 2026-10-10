"""Region Sweep — Boxel Survey's second, selectable sub-mode.

Where Sequence mode (boxel_survey.py's own BoxelSurveyController) walks one
flat ascending/descending sequence within a single boxel, Region Sweep
manages a *queue* of cubes and tracks completion across all of them,
discovering known systems from EDSM's nearby-systems lookup, a live Spansh
boxel query, and the commander's own visits — see region_sweep_queue.py's
module docstring for the full rationale (in particular: why there's no
auto-descending nested-boxel tree here, unlike the third-party tool that
inspired this feature).

This module owns its own widgets (built into a frame boxel_survey.py hands
it via build_panel()) and its own Settings-tab section, but does NOT
register its own PANEL_PLACEMENT/FEATURES entry — boxel_survey.py is the one
feature module EDMC's ui.py/load.py dispatch to for Boxel Survey as a
whole; it fans out to this controller only when Region Sweep is the
selected sub-mode. `active` gates every side effect (advancing the queue,
autocopy, status updates) so this controller is inert while Sequence mode
is the one showing - state tracking (current system/position) still runs
regardless, cheaply, so switching sub-modes mid-session doesn't start from
nothing.
"""

from __future__ import annotations

import logging
import os
import queue
import threading
from typing import Any, Dict, List, Optional, Tuple

import tkinter as tk

import myNotebook as nb
from config import appname, config

from . import boxel, edsm_client, panelkit, region_sweep_spansh, region_sweep_state
from .region_sweep_queue import CubeEntry, RegionSweepQueue, RegionSweepSnapshot

plugin_name = os.path.basename(os.path.dirname(__file__))
logger = logging.getLogger(f"{appname}.{plugin_name}")

_CFG_AUTOCOPY = "wntb_boxel_sweep_autocopy"
_CFG_SKIP_VISITED = "wntb_boxel_sweep_skip_visited"
_CFG_SKIP_EDSM_VISITED = "wntb_boxel_sweep_skip_edsm_visited"
_CFG_COMPLETE_ON_FSS = "wntb_boxel_sweep_complete_on_fss"
_CFG_AUTO_DISCOVER = "wntb_boxel_sweep_auto_discover"

# When 1 or fewer queued cubes still have work left, proactively kick off the
# same EDSM cube-systems lookup "Discover Nearby Cubes" does — the buildable,
# EDSM-backed way to keep the queue stocked (see
# docs/BOXEL_SURVEY_TECH_SPEC.md §4.5/§6): WNTB has no id64 math to
# precompute neighboring boxels, but RegionSweepQueue.advance_cube() already auto-continues into whatever's
# queued once a cube completes — so keeping the queue topped up from real
# EDSM data achieves the same practical effect (never running dry) without
# needing the still-unconfirmed mass-code stride table. 1, not 0, so the
# lookup's network latency has a head start before the last cube actually
# runs out.
_AUTO_DISCOVER_LOW_WATER_MARK = 1

_NO_TARGET_TEXT = "(no target — add a cube below)"
_HINT_EMPTY = ""
_HINT_VALID = "looks like a procedural boxel name"
_HINT_INVALID = "not a recognized boxel name shape (hand-named system?)"

# Bounds the queue Listbox's own footprint - see the global EDMC-plugin
# instruction on bounding anything that can size the main window. Sector
# names are externally-sourced/unbounded text, so each displayed line is
# truncated to this many characters rather than trusting them to be short.
_LIST_WIDTH_CHARS = 48
_LIST_HEIGHT_ROWS = 6
_MAX_LIST_ITEM_CHARS = _LIST_WIDTH_CHARS


def autocopy_enabled() -> bool:
    return config.get_bool(_CFG_AUTOCOPY, default=True)


def skip_visited_enabled() -> bool:
    return config.get_bool(_CFG_SKIP_VISITED, default=True)


def skip_edsm_visited_enabled() -> bool:
    return config.get_bool(_CFG_SKIP_EDSM_VISITED, default=False)


def complete_on_fss_enabled() -> bool:
    # Stricter completion criterion (every body FSS-scanned) - opt-in, since
    # it changes what "done" means
    # for a cube and shouldn't silently change behavior for existing users.
    return config.get_bool(_CFG_COMPLETE_ON_FSS, default=False)


def auto_discover_enabled() -> bool:
    # Opt-in (default off): unlike the manual "Discover Nearby Cubes"
    # button, this fires a network call without an explicit click, so it
    # shouldn't turn on background EDSM traffic a user didn't ask for.
    return config.get_bool(_CFG_AUTO_DISCOVER, default=False)


def _truncate(text: str, limit: int = _MAX_LIST_ITEM_CHARS) -> str:
    return text if len(text) <= limit else text[: limit - 1] + "…"


class RegionSweepController:
    def __init__(self) -> None:
        self.active = False
        self._queue = RegionSweepQueue()
        self._plugin_dir: Optional[str] = None
        self._current_system: Optional[str] = None
        self._current_pos: Optional[Tuple[float, float, float]] = None
        self._current_cmdr: Optional[str] = None
        self._parent: Optional[tk.Frame] = None

        # Worker-thread + queue.Queue + after()-polling plumbing, same
        # pattern as boxel_survey.py's own EDSM lookups - workers must
        # never touch a Tk widget directly.
        self._edsm_result_queue: "queue.Queue[Dict[str, List[str]]]" = queue.Queue()
        self._spansh_result_queue: "queue.Queue[Tuple[str, List[str], Optional[str]]]" = queue.Queue()
        self._fss_result_queue: "queue.Queue[Tuple[str, bool]]" = queue.Queue()

        # Guards against firing a second auto-discover lookup while one is
        # already in flight (e.g. two jumps landing before the first
        # response comes back) — the manual button has no such guard since
        # a human clicking it twice in a row is deliberate, but an automatic
        # trigger firing repeatedly on every subsequent jump while the
        # queue is still low would be a silent EDSM-traffic multiplier.
        self._auto_discover_inflight = False

        # Main-panel widgets/vars.
        self._add_seed_var: Optional[tk.StringVar] = None
        self._add_seed_hint_var: Optional[tk.StringVar] = None
        self._target_var: Optional[tk.StringVar] = None
        self._status_var: Optional[tk.StringVar] = None
        self._stats_var: Optional[tk.StringVar] = None
        self._listbox: Optional[tk.Listbox] = None
        self._list_index_to_cube: List[CubeEntry] = []

        # Settings-tab vars.
        self._autocopy_var: Optional[tk.BooleanVar] = None
        self._skip_visited_var: Optional[tk.BooleanVar] = None
        self._skip_edsm_visited_var: Optional[tk.BooleanVar] = None
        self._complete_on_fss_var: Optional[tk.BooleanVar] = None
        self._auto_discover_var: Optional[tk.BooleanVar] = None

    # --- lifecycle -----------------------------------------------------

    def start(self, plugin_dir: str) -> None:
        self._plugin_dir = plugin_dir
        # Queue state is per-commander (region_sweep_state.py) and EDMC
        # doesn't know which commander is active until the first journal
        # event - actual restore happens in _switch_cmdr(), called from
        # handle_event() below.

    def stop(self) -> None:
        self._save_queue_state()

    def _save_queue_state(self) -> None:
        if self._plugin_dir is None or self._current_cmdr is None:
            return
        snap = self._queue.snapshot()
        region_sweep_state.save_state(
            self._plugin_dir, self._current_cmdr, {"cubes": snap.cubes, "current_index": snap.current_index},
        )

    def _switch_cmdr(self, cmdr: str) -> None:
        """Called whenever the active commander changes, including the
        first journal event of a session - saves the previous commander's
        queue (if one was loaded) and loads this commander's own, so two
        commanders on the same install never share or overwrite one
        queue."""
        self._save_queue_state()
        self._current_cmdr = cmdr
        saved = region_sweep_state.load_state(self._plugin_dir, cmdr) if self._plugin_dir else None
        self._queue = RegionSweepQueue()
        if saved:
            try:
                self._queue.restore(RegionSweepSnapshot(
                    cubes=saved.get("cubes", []), current_index=saved.get("current_index", -1),
                ))
                logger.info("Restored Region Sweep queue for %s: %d cube(s)", cmdr, len(self._queue.cubes))
            except Exception:
                logger.exception("Failed to restore saved Region Sweep state for %s; starting fresh", cmdr)
        self._refresh_list()
        if self.active:
            self._refresh_target()

    def set_active(self, active: bool) -> None:
        self.active = active
        if active:
            self._refresh_target()

    # --- journal dispatch ------------------------------------------------

    def handle_event(self, entry: Dict[str, Any], cmdr: str, system: Optional[str], station: Optional[str], state: Dict[str, Any]) -> None:
        if cmdr and cmdr != self._current_cmdr:
            self._switch_cmdr(cmdr)

        if system:
            self._current_system = system
        star_pos = entry.get("StarPos")
        if isinstance(star_pos, (list, tuple)) and len(star_pos) == 3:
            self._current_pos = (star_pos[0], star_pos[1], star_pos[2])

        event = entry.get("event", "")

        if event == "FSSAllBodiesFound":
            # The game writes this when the FSS has found every body in the system, so "require a full FSS scan"
            # is decided from the journal itself: no network call, and it works while offline.
            name = entry.get("SystemName") or system
            if complete_on_fss_enabled() and name:
                self._fss_result_queue.put((str(name), True))
            return

        if event in ("FSSBodySignals", "SAASignalsFound", "Scan"):
            # Notable-finds recording already happens unconditionally in
            # boxel_survey.py's own handler (survey_log.py is keyed by
            # sector/cube_id, not by which sub-mode is active) - nothing to do here.
            return

        if event not in ("FSDJump", "Location"):
            return
        star_system = entry.get("StarSystem")
        if not star_system:
            return

        # Visited-tracking always runs (cheap, keeps state current even
        # while Sequence mode is the one on screen); advancing the queue
        # and touching the UI only happens while Region Sweep is active,
        # so switching sub-modes never causes a surprise jump in state.
        if not self.active:
            self._queue.mark_visited(star_system)
            return

        complete_now = not complete_on_fss_enabled()
        next_target = self._queue.on_jump(
            star_system, skip_visited=skip_visited_enabled(), complete=complete_now,
        )
        self._refresh_list()
        self._maybe_auto_discover()
        if next_target is None:
            self._set_status(f"Arrived {star_system}")
            return
        self._set_target(next_target)
        if autocopy_enabled():
            self._copy_current()
            self._set_status(f"Arrived {star_system} — copied next target")
        else:
            self._set_status(f"Arrived {star_system} — next target ready")

    # --- main-panel widgets -----------------------------------------------

    def build_panel(self, parent: tk.Frame) -> None:
        self._parent = parent

        self._add_seed_var = tk.StringVar(value="")
        self._add_seed_hint_var = tk.StringVar(value=_HINT_EMPTY)
        self._target_var = tk.StringVar(value=_NO_TARGET_TEXT)
        self._status_var = tk.StringVar(value="")
        self._stats_var = tk.StringVar(value="")

        tk.Label(parent, text="Add cube — seed system:").grid(row=0, column=0, sticky=tk.W)
        tk.Entry(parent, textvariable=self._add_seed_var, width=28).grid(row=0, column=1, sticky=tk.W)
        add_button_row = tk.Frame(parent)
        add_button_row.grid(row=0, column=2, sticky=tk.W)
        tk.Button(add_button_row, text="Use Current", command=self._on_use_current).pack(side=tk.LEFT)
        tk.Button(add_button_row, text="Add", command=self._on_add_cube).pack(side=tk.LEFT, padx=(4, 0))

        add_hint_label = panelkit.wrap_label(parent, textvariable=self._add_seed_hint_var, fg="grey")
        add_hint_label.grid(row=1, column=0, columnspan=3, sticky=tk.W)
        self._add_seed_var.trace_add("write", lambda *_args: self._update_add_hint())

        discover_row = tk.Frame(parent)
        discover_row.grid(row=2, column=0, columnspan=3, sticky=tk.W, pady=(2, 0))
        tk.Button(discover_row, text="Discover Nearby Cubes (EDSM)", command=self._on_discover_nearby).pack(
            side=tk.LEFT,
        )
        tk.Button(discover_row, text="Discover Known Systems (Spansh)", command=self._on_discover_spansh).pack(
            side=tk.LEFT, padx=(4, 0),
        )

        list_frame = tk.Frame(parent)
        list_frame.grid(row=3, column=0, columnspan=3, sticky=tk.W, pady=(4, 0))
        self._listbox = tk.Listbox(
            list_frame, width=_LIST_WIDTH_CHARS, height=_LIST_HEIGHT_ROWS, exportselection=False,
        )
        self._listbox.pack(side=tk.LEFT)
        list_scroll = tk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self._listbox.yview)
        list_scroll.pack(side=tk.LEFT, fill=tk.Y)
        self._listbox.configure(yscrollcommand=list_scroll.set)

        queue_button_row = tk.Frame(parent)
        queue_button_row.grid(row=4, column=0, columnspan=3, sticky=tk.W)
        tk.Button(queue_button_row, text="Set Current", command=self._on_set_current).pack(side=tk.LEFT)
        tk.Button(queue_button_row, text="Remove", command=self._on_remove_selected).pack(side=tk.LEFT, padx=(4, 0))
        tk.Button(queue_button_row, text="Mark Empty", command=self._on_mark_empty).pack(side=tk.LEFT, padx=(4, 0))
        tk.Button(queue_button_row, text="Unmark Empty", command=self._on_unmark_empty).pack(
            side=tk.LEFT, padx=(4, 0),
        )

        tk.Label(parent, text="Target:").grid(row=5, column=0, sticky=tk.W, pady=(4, 0))
        panelkit.wrap_label(parent, textvariable=self._target_var, anchor="w").grid(
            row=5, column=1, columnspan=2, sticky=tk.W, pady=(4, 0),
        )

        target_button_row = tk.Frame(parent)
        target_button_row.grid(row=6, column=0, columnspan=3, sticky=tk.W)
        tk.Button(target_button_row, text="< Prev", command=self._on_prev).pack(side=tk.LEFT)
        tk.Button(target_button_row, text="Next >", command=self._on_next).pack(side=tk.LEFT, padx=(4, 0))
        tk.Button(target_button_row, text="Copy", command=self._copy_current).pack(side=tk.LEFT, padx=(4, 0))

        panelkit.wrap_label(parent, textvariable=self._stats_var, anchor="w").grid(
            row=7, column=0, columnspan=3, sticky=tk.W,
        )
        panelkit.wrap_label(parent, textvariable=self._status_var, fg="grey").grid(
            row=8, column=0, columnspan=3, sticky=tk.W,
        )

        panelkit.apply_theme_deep(parent)

        self._refresh_list()
        self._refresh_target()
        parent.after(200, self._poll_edsm_queue)
        parent.after(200, self._poll_spansh_queue)
        parent.after(200, self._poll_fss_queue)

    # --- widget helpers --------------------------------------------------

    def _set_target(self, name: Optional[str]) -> None:
        if self._target_var is not None:
            self._target_var.set(name or _NO_TARGET_TEXT)

    def _set_status(self, message: str) -> None:
        if self._status_var is not None:
            self._status_var.set(message)

    def _refresh_target(self) -> None:
        cube = self._queue.current
        self._set_target(cube.walker.current if cube else None)
        self._refresh_stats()

    def _refresh_stats(self) -> None:
        if self._stats_var is None:
            return
        cube = self._queue.current
        cubes_total = len(self._queue.cubes)
        if cube is None:
            self._stats_var.set(f"Cubes: 0/{cubes_total} complete")
            return
        self._stats_var.set(
            f"Current cube: {cube.prefix} ({cube.complete_count}/{cube.known_count} known systems) | "
            f"Cubes: {self._queue.cubes_complete}/{cubes_total} complete"
        )

    def _refresh_list(self) -> None:
        if self._listbox is None:
            return
        selected = self._listbox.curselection()
        selected_cube = self._list_index_to_cube[selected[0]] if selected else None
        self._listbox.delete(0, tk.END)
        self._list_index_to_cube = list(self._queue.cubes)
        current = self._queue.current
        for i, cube in enumerate(self._list_index_to_cube):
            marker = "> " if cube is current else "  "
            state = "empty" if cube.empty else f"{cube.complete_count}/{cube.known_count}"
            self._listbox.insert(tk.END, _truncate(f"{marker}{cube.prefix} [{state}]"))
            if cube is selected_cube:
                self._listbox.selection_set(i)
        self._refresh_stats()

    def _selected_cube(self) -> Optional[CubeEntry]:
        if self._listbox is None:
            return None
        selected = self._listbox.curselection()
        if not selected or selected[0] >= len(self._list_index_to_cube):
            return None
        return self._list_index_to_cube[selected[0]]

    def _update_add_hint(self) -> None:
        try:
            if self._add_seed_var is None or self._add_seed_hint_var is None:
                return
            text = self._add_seed_var.get().strip()
            if not text:
                self._add_seed_hint_var.set(_HINT_EMPTY)
                return
            self._add_seed_hint_var.set(_HINT_VALID if boxel.is_procedural_name(text) else _HINT_INVALID)
        except Exception:
            # trace_add callbacks run inside Tk's event loop, which silently
            # swallows exceptions when running windowed - log explicitly.
            logger.exception("_update_add_hint failed")

    def _copy_current(self) -> None:
        if self._parent is None or self._target_var is None:
            return
        text = self._target_var.get()
        if not text or text == _NO_TARGET_TEXT:
            self._set_status("Nothing to copy yet")
            return
        if panelkit.copy_to_clipboard(self._parent, text):
            self._set_status(f"Copied: {text}")

    # --- button handlers ---------------------------------------------------

    def _on_use_current(self) -> None:
        if not self._current_system:
            self._set_status("Current system not known yet")
            return
        if self._add_seed_var is not None:
            self._add_seed_var.set(self._current_system)

    def _on_add_cube(self) -> None:
        if self._add_seed_var is None:
            return
        name = self._add_seed_var.get().strip()
        if not name:
            self._set_status("Enter a system name first")
            return
        entry = self._queue.add_cube_from_system(name)
        if entry is None:
            self._set_status(f"{name!r} is not a recognized boxel name shape")
            return
        self._refresh_list()
        self._refresh_target()
        self._set_status(f"Added cube {entry.prefix}")

    def _on_set_current(self) -> None:
        cube = self._selected_cube()
        if cube is None:
            self._set_status("Select a cube in the list first")
            return
        self._queue.set_current(cube.sector, cube.cube_id, cube.mass_code)
        self._refresh_list()
        self._refresh_target()
        self._set_status(f"Current cube: {cube.prefix}")

    def _on_remove_selected(self) -> None:
        cube = self._selected_cube()
        if cube is None:
            self._set_status("Select a cube in the list first")
            return
        self._queue.remove_cube(cube.sector, cube.cube_id, cube.mass_code)
        self._refresh_list()
        self._refresh_target()
        self._set_status(f"Removed cube {cube.prefix}")

    def _on_mark_empty(self) -> None:
        cube = self._selected_cube()
        if cube is not None:
            self._queue.set_current(cube.sector, cube.cube_id, cube.mass_code)
        self._queue.mark_current_empty()
        self._refresh_list()
        self._refresh_target()
        self._set_status("Marked current cube empty")

    def _on_unmark_empty(self) -> None:
        cube = self._selected_cube()
        if cube is not None:
            self._queue.set_current(cube.sector, cube.cube_id, cube.mass_code)
        self._queue.unmark_current_empty()
        self._refresh_list()
        self._refresh_target()
        self._set_status("Unmarked current cube as empty")

    def _on_next(self) -> None:
        cube = self._queue.current
        if cube is None:
            self._set_status("Add a cube first")
            return
        try:
            target = cube.walker.advance(skip_visited=skip_visited_enabled())
        except Exception:
            logger.exception("_on_next failed")
            return
        self._set_target(target)
        self._refresh_list()
        self._set_status("Manual advance" if target else "Add a cube first")

    def _on_prev(self) -> None:
        cube = self._queue.current
        if cube is None:
            self._set_status("Add a cube first")
            return
        try:
            target = cube.walker.retreat()
        except ValueError:
            self._set_status("Already at the start of the sequence")
            return
        except Exception:
            logger.exception("_on_prev failed")
            return
        self._set_target(target)
        self._set_status("Manual retreat" if target else "Add a cube first")

    def _on_discover_nearby(self) -> None:
        self._start_discover_nearby(auto=False)

    def _maybe_auto_discover(self) -> None:
        """Called after every jump while Region Sweep is active - if
        "Auto-discover" is enabled and the queue is down to
        _AUTO_DISCOVER_LOW_WATER_MARK or fewer cubes still needing work,
        proactively runs the same EDSM lookup "Discover Nearby Cubes" does,
        so RegionSweepQueue.advance_cube() has somewhere to go once the
        current cube actually completes - see this module's own
        _CFG_AUTO_DISCOVER comment for the full rationale."""
        if not auto_discover_enabled() or self._auto_discover_inflight:
            return
        incomplete = sum(1 for cube in self._queue.cubes if not cube.complete)
        if incomplete > _AUTO_DISCOVER_LOW_WATER_MARK:
            return
        self._start_discover_nearby(auto=True)

    def _start_discover_nearby(self, *, auto: bool) -> None:
        if self._current_pos is None:
            if not auto:
                self._set_status("Current position not known yet")
            return
        if auto:
            self._auto_discover_inflight = True
        else:
            self._set_status("Looking up nearby systems on EDSM...")
        x, y, z = self._current_pos
        threading.Thread(target=self._edsm_discover_worker, args=(x, y, z, auto), daemon=True).start()

    def _edsm_discover_worker(self, x: float, y: float, z: float, auto: bool) -> None:
        """Runs off the main thread — must not touch any Tk widget directly.
        Groups every discovered system by its own (sector, cube_id,
        mass_code), so one EDSM lookup can seed/merge several cubes at
        once - unlike Sequence mode's single-nearest-candidate use of this
        same endpoint."""
        grouped: Dict[str, List[str]] = {}
        try:
            for entry in edsm_client.nearby_systems(x, y, z):
                name = entry.get("name")
                if not name:
                    continue
                parsed = boxel.parse_system_name(name)
                if parsed is None:
                    continue
                key = f"{parsed.sector}|{parsed.cube_id}|{parsed.mass_code}"
                grouped.setdefault(key, []).append(name)
        except Exception:
            logger.exception("_edsm_discover_worker failed")
            grouped = {}
        self._edsm_result_queue.put((grouped, auto))

    def _poll_edsm_queue(self) -> None:
        """Runs on the main thread via after() — safe to touch widgets here."""
        try:
            grouped, auto = self._edsm_result_queue.get_nowait()
        except queue.Empty:
            pass
        else:
            if auto:
                self._auto_discover_inflight = False
            if not grouped:
                if not auto:
                    self._set_status("No nearby procedural systems found via EDSM")
            else:
                cubes_touched = 0
                for key, names in grouped.items():
                    sector, cube_id, mass_code = key.split("|", 2)
                    self._queue.merge_known_systems(sector, cube_id, mass_code, names)
                    cubes_touched += 1
                self._refresh_list()
                self._refresh_target()
                if auto:
                    self._set_status(f"Auto-discovered {cubes_touched} more cube(s) nearby via EDSM")
                else:
                    self._set_status(f"EDSM: merged systems into {cubes_touched} cube(s)")
        if self._parent is not None:
            self._parent.after(200, self._poll_edsm_queue)

    def _on_discover_spansh(self) -> None:
        cube = self._selected_cube() or self._queue.current
        if cube is None:
            self._set_status("Add a cube first")
            return
        self._set_status(f"Looking up known systems in {cube.prefix} on Spansh...")
        threading.Thread(
            target=self._spansh_discover_worker, args=(cube.sector, cube.cube_id, cube.mass_code), daemon=True,
        ).start()

    def _spansh_discover_worker(self, sector: str, cube_id: str, mass_code: str) -> None:
        """Runs off the main thread — must not touch any Tk widget directly."""
        error: Optional[str] = None
        names: List[str] = []
        try:
            names = region_sweep_spansh.search_boxel_systems(sector, cube_id, mass_code)
        except Exception as exc:
            logger.exception("_spansh_discover_worker failed for %s %s %s", sector, cube_id, mass_code)
            error = str(exc)
        self._spansh_result_queue.put((f"{sector}|{cube_id}|{mass_code}", names, error))

    def _poll_spansh_queue(self) -> None:
        """Runs on the main thread via after() — safe to touch widgets here."""
        try:
            key, names, error = self._spansh_result_queue.get_nowait()
        except queue.Empty:
            pass
        else:
            sector, cube_id, mass_code = key.split("|", 2)
            if error:
                self._set_status("Spansh lookup failed — see EDMarketConnector.log")
            else:
                self._queue.merge_known_systems(sector, cube_id, mass_code, names)
                self._refresh_list()
                self._refresh_target()
                self._set_status(f"Spansh: found {len(names)} known system(s) in {sector} {cube_id} {mass_code}")
        if self._parent is not None:
            self._parent.after(200, self._poll_spansh_queue)

    def _poll_fss_queue(self) -> None:
        """Runs on the main thread via after() — safe to touch widgets here."""
        try:
            system, still_current = self._fss_result_queue.get_nowait()
        except queue.Empty:
            pass
        else:
            self._queue.mark_system_complete(system)
            self._refresh_list()
            self._refresh_target()
            if still_current and self.active:
                self._set_status(f"{system}: fully scanned — marked complete")
        if self._parent is not None:
            self._parent.after(200, self._poll_fss_queue)

    # --- Settings tab --------------------------------------------------

    def build_settings(self, notebook: nb.Notebook) -> None:
        frame = nb.Frame(notebook)
        frame.columnconfigure(0, weight=1)
        notebook.add(frame, text="Region Sweep")

        self._autocopy_var = tk.BooleanVar(value=autocopy_enabled())
        self._skip_visited_var = tk.BooleanVar(value=skip_visited_enabled())
        self._skip_edsm_visited_var = tk.BooleanVar(value=skip_edsm_visited_enabled())
        self._complete_on_fss_var = tk.BooleanVar(value=complete_on_fss_enabled())
        self._auto_discover_var = tk.BooleanVar(value=auto_discover_enabled())

        nb.Label(frame, text="Region Sweep", font=("TkDefaultFont", 9, "bold")).grid(
            row=0, column=0, sticky=tk.W, padx=10, pady=(10, 4),
        )
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
            frame, text="Require a full FSS scan (not just arrival) to mark a system complete",
            variable=self._complete_on_fss_var,
        ).grid(row=4, column=0, sticky=tk.W, padx=10)
        nb.Checkbutton(
            frame,
            text="Auto-discover more nearby cubes (EDSM) when the queue is running low",
            variable=self._auto_discover_var,
        ).grid(row=5, column=0, sticky=tk.W, padx=10, pady=(0, 10))

    def save_settings(self) -> None:
        if self._autocopy_var is None:
            return
        config.set(_CFG_AUTOCOPY, self._autocopy_var.get())
        config.set(_CFG_SKIP_VISITED, self._skip_visited_var.get())
        config.set(_CFG_SKIP_EDSM_VISITED, self._skip_edsm_visited_var.get())
        config.set(_CFG_COMPLETE_ON_FSS, self._complete_on_fss_var.get())
        config.set(_CFG_AUTO_DISCOVER, self._auto_discover_var.get())
