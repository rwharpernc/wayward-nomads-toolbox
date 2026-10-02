"""Waypoint Route — Boxel Survey's third, selectable sub-mode.

Where Sequence mode walks one flat boxel sequence and Region Sweep tracks
completion across a queue of cubes, Waypoint Route is a general
point-to-point route tool: add arbitrary systems (hand-named or
procedural), optionally import a list from CSV, and visit them in order -
manually curated, or auto-ordered by nearest-neighbor distance via a live
EDSM coordinate lookup (edsm_client.systems_coords()).

Owns its own widgets (built into a frame boxel_survey.py hands it via
build_panel()) and its own Settings-tab section, same pattern as
region_sweep_panel.py's RegionSweepController - see that module's own
docstring for the shared "does NOT register its own PANEL_PLACEMENT"
reasoning, which applies here identically. `active` gates every side
effect the same way.
"""

from __future__ import annotations

import logging
import os
import queue
import threading
from tkinter import filedialog
from typing import Any, Dict, List, Optional, Tuple

import tkinter as tk

import myNotebook as nb
from config import appname, config

from . import edsm_client, panelkit, waypoint_route_state
from .waypoint_route import WaypointRoute

plugin_name = os.path.basename(os.path.dirname(__file__))
logger = logging.getLogger(f"{appname}.{plugin_name}")

_CFG_AUTOCOPY = "wntb_boxel_waypoint_autocopy"

_NO_TARGET_TEXT = "(no target — add a waypoint below)"
_HINT_EMPTY = ""

# Bounds the waypoint Listbox's own footprint - see the global EDMC-plugin
# instruction on bounding anything that can size the main window. System
# names are externally-sourced/unbounded text, so each displayed line is
# truncated to this many characters rather than trusting them to be short.
_LIST_WIDTH_CHARS = 48
_LIST_HEIGHT_ROWS = 6
_MAX_LIST_ITEM_CHARS = _LIST_WIDTH_CHARS


def autocopy_enabled() -> bool:
    return config.get_bool(_CFG_AUTOCOPY, default=True)


def _truncate(text: str, limit: int = _MAX_LIST_ITEM_CHARS) -> str:
    return text if len(text) <= limit else text[: limit - 1] + "…"


class WaypointRouteController:
    def __init__(self) -> None:
        self.active = False
        self._route = WaypointRoute()
        self._plugin_dir: Optional[str] = None
        self._current_system: Optional[str] = None
        self._current_pos: Optional[Tuple[float, float, float]] = None
        self._current_cmdr: Optional[str] = None
        self._parent: Optional[tk.Frame] = None

        # Worker-thread + queue.Queue + after()-polling plumbing, same
        # pattern as region_sweep_panel.py's own EDSM lookups.
        self._reorder_result_queue: "queue.Queue[Tuple[Dict[str, Tuple[float, float, float]], int]]" = (
            queue.Queue()
        )

        # Main-panel widgets/vars.
        self._add_var: Optional[tk.StringVar] = None
        self._target_var: Optional[tk.StringVar] = None
        self._status_var: Optional[tk.StringVar] = None
        self._listbox: Optional[tk.Listbox] = None
        self._list_index_to_waypoint: List[Any] = []

        # Settings-tab vars.
        self._autocopy_var: Optional[tk.BooleanVar] = None

    # --- lifecycle -----------------------------------------------------

    def start(self, plugin_dir: str) -> None:
        self._plugin_dir = plugin_dir
        # Route state is per-commander (waypoint_route_state.py) and EDMC
        # doesn't know which commander is active until the first journal
        # event - actual restore happens in _switch_cmdr(), called from
        # handle_event() below.

    def stop(self) -> None:
        self._save_route_state()

    def _save_route_state(self) -> None:
        if self._plugin_dir is None or self._current_cmdr is None:
            return
        waypoint_route_state.save_state(self._plugin_dir, self._current_cmdr, self._route.snapshot())

    def _switch_cmdr(self, cmdr: str) -> None:
        """Called whenever the active commander changes, including the
        first journal event of a session - saves the previous commander's
        route (if one was loaded) and loads this commander's own, so two
        commanders on the same install never share or overwrite one
        route."""
        self._save_route_state()
        self._current_cmdr = cmdr
        saved = waypoint_route_state.load_state(self._plugin_dir, cmdr) if self._plugin_dir else None
        self._route = WaypointRoute()
        if saved:
            try:
                self._route.restore(saved)
                logger.info("Restored Waypoint Route for %s: %d waypoint(s)", cmdr, len(self._route.waypoints))
            except Exception:
                logger.exception("Failed to restore saved Waypoint Route state for %s; starting fresh", cmdr)
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
        if event not in ("FSDJump", "Location"):
            return
        star_system = entry.get("StarSystem")
        if not star_system:
            return

        # Visited-tracking always runs (cheap, keeps state current even
        # while another sub-mode is the one on screen); touching the UI
        # only happens while Waypoint Route is active, same reasoning as
        # RegionSweepController's own handle_event.
        if not self.active:
            self._route.mark_visited(star_system)
            return

        next_target = self._route.on_jump(star_system)
        self._refresh_list()
        if next_target is None:
            self._set_target(None)
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

        self._add_var = tk.StringVar(value="")
        self._target_var = tk.StringVar(value=_NO_TARGET_TEXT)
        self._status_var = tk.StringVar(value="")

        tk.Label(parent, text="Add waypoint:").grid(row=0, column=0, sticky=tk.W)
        tk.Entry(parent, textvariable=self._add_var, width=28).grid(row=0, column=1, sticky=tk.W)
        add_button_row = tk.Frame(parent)
        add_button_row.grid(row=0, column=2, sticky=tk.W)
        tk.Button(add_button_row, text="Use Current", command=self._on_use_current).pack(side=tk.LEFT)
        tk.Button(add_button_row, text="Add", command=self._on_add).pack(side=tk.LEFT, padx=(4, 0))

        tk.Button(parent, text="Import CSV…", command=self._on_import_csv).grid(
            row=1, column=0, columnspan=3, sticky=tk.W, pady=(2, 0),
        )

        list_frame = tk.Frame(parent)
        list_frame.grid(row=2, column=0, columnspan=3, sticky=tk.W, pady=(4, 0))
        self._listbox = tk.Listbox(
            list_frame, width=_LIST_WIDTH_CHARS, height=_LIST_HEIGHT_ROWS, exportselection=False,
        )
        self._listbox.pack(side=tk.LEFT)
        list_scroll = tk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self._listbox.yview)
        list_scroll.pack(side=tk.LEFT, fill=tk.Y)
        self._listbox.configure(yscrollcommand=list_scroll.set)

        list_button_row = tk.Frame(parent)
        list_button_row.grid(row=3, column=0, columnspan=3, sticky=tk.W)
        tk.Button(list_button_row, text="Remove", command=self._on_remove_selected).pack(side=tk.LEFT)
        tk.Button(list_button_row, text="Move Up", command=lambda: self._on_move_selected(-1)).pack(
            side=tk.LEFT, padx=(4, 0),
        )
        tk.Button(list_button_row, text="Move Down", command=lambda: self._on_move_selected(1)).pack(
            side=tk.LEFT, padx=(4, 0),
        )
        tk.Button(list_button_row, text="Reorder (Nearest-Neighbor, EDSM)", command=self._on_reorder).pack(
            side=tk.LEFT, padx=(4, 0),
        )

        tk.Label(parent, text="Target:").grid(row=4, column=0, sticky=tk.W, pady=(4, 0))
        panelkit.wrap_label(parent, textvariable=self._target_var, anchor="w").grid(
            row=4, column=1, columnspan=2, sticky=tk.W, pady=(4, 0),
        )
        tk.Button(parent, text="Copy", command=self._copy_current).grid(row=5, column=0, sticky=tk.W)

        panelkit.wrap_label(parent, textvariable=self._status_var, fg="grey").grid(
            row=6, column=0, columnspan=3, sticky=tk.W,
        )

        panelkit.apply_theme_deep(parent)

        self._refresh_list()
        self._refresh_target()
        parent.after(200, self._poll_reorder_queue)

    # --- widget helpers --------------------------------------------------

    def _set_target(self, name: Optional[str]) -> None:
        if self._target_var is not None:
            self._target_var.set(name or _NO_TARGET_TEXT)

    def _set_status(self, message: str) -> None:
        if self._status_var is not None:
            self._status_var.set(message)

    def _refresh_target(self) -> None:
        target = self._route.current_target()
        self._set_target(target.name if target else None)

    def _refresh_list(self) -> None:
        if self._listbox is None:
            return
        selected = self._listbox.curselection()
        selected_wp = self._list_index_to_waypoint[selected[0]] if selected else None
        self._listbox.delete(0, tk.END)
        self._list_index_to_waypoint = list(self._route.waypoints)
        current = self._route.current_target()
        for i, wp in enumerate(self._list_index_to_waypoint):
            marker = "> " if wp is current else "  "
            state = "done" if wp.visited else ("" if wp.has_coords else "no coords")
            suffix = f" [{state}]" if state else ""
            self._listbox.insert(tk.END, _truncate(f"{marker}{wp.name}{suffix}"))
            if wp is selected_wp:
                self._listbox.selection_set(i)

    def _selected_waypoint(self):
        if self._listbox is None:
            return None
        selected = self._listbox.curselection()
        if not selected or selected[0] >= len(self._list_index_to_waypoint):
            return None
        return self._list_index_to_waypoint[selected[0]]

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
        if self._add_var is not None:
            self._add_var.set(self._current_system)

    def _on_add(self) -> None:
        if self._add_var is None:
            return
        name = self._add_var.get().strip()
        if not name:
            self._set_status("Enter a system name first")
            return
        self._route.add(name)
        self._add_var.set("")
        self._refresh_list()
        self._refresh_target()
        self._set_status(f"Added waypoint: {name}")

    def _on_import_csv(self) -> None:
        path = filedialog.askopenfilename(filetypes=[("CSV files", "*.csv"), ("All files", "*.*")])
        if not path:
            return
        try:
            names = WaypointRoute.parse_csv_names(path)
        except OSError as exc:
            logger.exception("_on_import_csv failed to read %s", path)
            self._set_status(f"Could not read {path}: {exc}")
            return
        added = self._route.add_many(names)
        self._refresh_list()
        self._refresh_target()
        self._set_status(f"Imported {added} new waypoint(s) from {os.path.basename(path)}")

    def _on_remove_selected(self) -> None:
        wp = self._selected_waypoint()
        if wp is None:
            self._set_status("Select a waypoint in the list first")
            return
        self._route.remove(wp.name)
        self._refresh_list()
        self._refresh_target()
        self._set_status(f"Removed waypoint: {wp.name}")

    def _on_move_selected(self, delta: int) -> None:
        wp = self._selected_waypoint()
        if wp is None:
            self._set_status("Select a waypoint in the list first")
            return
        if not self._route.move(wp.name, delta):
            self._set_status("Can't move further in that direction")
            return
        self._refresh_list()
        if self._listbox is not None:
            idx = self._list_index_to_waypoint.index(wp)
            self._listbox.selection_clear(0, tk.END)
            self._listbox.selection_set(idx)

    def _on_reorder(self) -> None:
        if self._current_pos is None:
            self._set_status("Current position not known yet")
            return
        names = [wp.name for wp in self._route.waypoints if not wp.visited]
        if not names:
            self._set_status("No unvisited waypoints to reorder")
            return
        self._set_status("Looking up waypoint coordinates on EDSM...")
        threading.Thread(target=self._reorder_worker, args=(names, self._current_pos), daemon=True).start()

    def _reorder_worker(self, names: List[str], start: Tuple[float, float, float]) -> None:
        """Runs off the main thread — must not touch any Tk widget directly."""
        try:
            resolved = edsm_client.systems_coords(names)
        except Exception:
            logger.exception("_reorder_worker failed")
            resolved = {}
        self._reorder_result_queue.put((resolved, len(names)))

    def _poll_reorder_queue(self) -> None:
        """Runs on the main thread via after() — safe to touch widgets here."""
        try:
            resolved, requested = self._reorder_result_queue.get_nowait()
        except queue.Empty:
            pass
        else:
            for name, (x, y, z) in resolved.items():
                self._route.set_coords(name, x, y, z)
            if self._current_pos is not None:
                count = self._route.reorder_nearest_neighbor(self._current_pos)
            else:
                count = 0
            self._refresh_list()
            self._refresh_target()
            self._set_status(
                f"EDSM located {len(resolved)}/{requested} waypoint(s) — reordered {count}"
            )
        if self._parent is not None:
            self._parent.after(200, self._poll_reorder_queue)

    # --- Settings tab --------------------------------------------------

    def build_settings(self, notebook: nb.Notebook) -> None:
        frame = nb.Frame(notebook)
        frame.columnconfigure(0, weight=1)
        notebook.add(frame, text="Waypoint Route")

        self._autocopy_var = tk.BooleanVar(value=autocopy_enabled())

        nb.Label(frame, text="Waypoint Route", font=("TkDefaultFont", 9, "bold")).grid(
            row=0, column=0, sticky=tk.W, padx=10, pady=(10, 4),
        )
        nb.Checkbutton(
            frame, text="Auto-copy next waypoint to clipboard on jump", variable=self._autocopy_var,
        ).grid(row=1, column=0, sticky=tk.W, padx=10, pady=(0, 10))

    def save_settings(self) -> None:
        if self._autocopy_var is None:
            return
        config.set(_CFG_AUTOCOPY, self._autocopy_var.get())
