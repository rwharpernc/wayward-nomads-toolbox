"""Canonn Nearby POI: an on-demand "find the nearest Thargoid/Guardian site"
lookup against Canonn Interstellar Research's own published site lists -
see canonn_poi_data.py and docs/ATTRIBUTIONS.md.

Same "manual, not automatic-on-jump" design as gec_poi_panel.py (its sibling
feature, edastro.com's GEC catalog) - R.W. Harper asked for button-triggered
lookups, not a live call firing on every FSDJump. Differs from that sibling
in one way: Canonn has no queryable "nearest" REST endpoint of its own, so
this downloads the full Thargoid/Guardian site lists once per session (two
independent third-party Google Sheets/Drive fetches) and caches them in
memory, computing "nearest" client-side on every click rather than
re-downloading - a "Refresh POI Data" button forces a re-download if the
cached lists ever need updating within the same EDMC session.

Lives inside Exploration mode's panel (PANEL_PLACEMENT = "exploration"),
alongside GEC Nearby POI and the rest of Exploration mode's features -
each gets its own dedicated child frame (see
ui.py's create_plugin_app/_stack_features()), separated by a thin
panelkit-drawn rule, so no cross-feature row coordination is needed here.
"""

from __future__ import annotations

import logging
import os
import queue
import threading
from typing import Any, Dict, List, Mapping, Optional, Tuple

import tkinter as tk

import myNotebook as nb
from config import appname, config
from ttkHyperlinkLabel import HyperlinkLabel

from . import canonn_poi_data, codex_completionist_panel, panelkit

plugin_name = os.path.basename(os.path.dirname(__file__))
logger = logging.getLogger(f"{appname}.{plugin_name}")

PANEL_PLACEMENT = "exploration"

_CFG_THARGOID_ENABLED = "wntb_canonn_poi_thargoid_enabled"
_CFG_GUARDIAN_ENABLED = "wntb_canonn_poi_guardian_enabled"
_CFG_SKIP_LOGGED = "wntb_canonn_poi_skip_logged"

_IDLE_TEXT = "Nearest Canonn POI: (jump into a system, then click Find Nearest POI)"
_NO_POSITION_TEXT = "Nearest Canonn POI: current position unknown — jump or reload first"
_NO_CATEGORY_TEXT = "Nearest Canonn POI: no site categories enabled — see Settings"
_DOWNLOADING_TEXT = "Nearest Canonn POI: downloading Canonn site data..."
_SEARCHING_TEXT = "Nearest Canonn POI: searching..."
_ERROR_TEXT = "Nearest Canonn POI: lookup failed — see EDMarketConnector.log"
_NONE_FOUND_TEXT = "Nearest Canonn POI: no sites found in the enabled categories"
_ALL_LOGGED_TEXT = (
    "Nearest Canonn POI: every site in the enabled categories is already logged in "
    "Codex Completionist"
)


def thargoid_enabled() -> bool:
    return config.get_bool(_CFG_THARGOID_ENABLED, default=True)


def guardian_enabled() -> bool:
    return config.get_bool(_CFG_GUARDIAN_ENABLED, default=True)


def skip_logged_enabled() -> bool:
    # On by default: "nearest site I haven't found yet" is what most
    # commanders actually want from a "find nearest POI" button - a site
    # they've already visited isn't useful to route toward.
    return config.get_bool(_CFG_SKIP_LOGGED, default=True)


class CanonnPoiController:
    def __init__(self) -> None:
        self._star_pos: Optional[Tuple[float, float, float]] = None

        # In-memory cache, populated on first click (or "Refresh POI Data")
        # - never re-downloaded automatically, same on-demand-only design as
        # the lookup itself.
        self._thargoid_sites: Optional[List[canonn_poi_data.CanonnPoi]] = None
        self._guardian_sites: Optional[List[canonn_poi_data.CanonnPoi]] = None

        self._result_var: Optional[tk.StringVar] = None
        self._find_button: Optional[tk.Button] = None
        self._refresh_button: Optional[tk.Button] = None
        self._link_label: Optional[HyperlinkLabel] = None
        self._parent: Optional[tk.Frame] = None

        self._thargoid_enabled_var: Optional[tk.BooleanVar] = None
        self._guardian_enabled_var: Optional[tk.BooleanVar] = None
        self._skip_logged_var: Optional[tk.BooleanVar] = None

        # Worker-thread + queue.Queue + after()-polling plumbing, same
        # pattern as gec_poi_panel.py. Generation counter lets a later click
        # supersede an in-flight one.
        self._generation = 0
        self._result_queue: "queue.Queue[Tuple[int, Optional[canonn_poi_data.CanonnPoi], Optional[float], Optional[str], bool]]" = queue.Queue()

    # --- journal dispatch -----------------------------------------------

    def handle_event(self, entry: Mapping[str, Any], cmdr: str, system: Optional[str], station: Optional[str], state: Dict[str, Any]) -> None:
        event = entry.get("event")
        if event not in ("FSDJump", "Location"):
            return
        star_pos = entry.get("StarPos")
        if (isinstance(star_pos, list) and len(star_pos) == 3
                and all(isinstance(v, (int, float)) for v in star_pos)):
            self._star_pos = tuple(star_pos)

    # --- lookup -----------------------------------------------------------

    def _on_find_clicked(self, force_refresh: bool = False) -> None:
        if self._star_pos is None:
            if self._result_var is not None:
                self._result_var.set(_NO_POSITION_TEXT)
            return
        if not thargoid_enabled() and not guardian_enabled():
            if self._result_var is not None:
                self._result_var.set(_NO_CATEGORY_TEXT)
            return

        self._generation += 1
        generation = self._generation
        needs_download = force_refresh or self._thargoid_sites is None or self._guardian_sites is None
        if self._result_var is not None:
            self._result_var.set(_DOWNLOADING_TEXT if needs_download else _SEARCHING_TEXT)
        if self._link_label is not None:
            self._link_label.grid_remove()
        for button in (self._find_button, self._refresh_button):
            if button is not None:
                button.config(state=tk.DISABLED)

        x, y, z = self._star_pos
        threading.Thread(
            target=self._worker, args=(generation, x, y, z, force_refresh), daemon=True,
        ).start()

    def _worker(self, generation: int, x: float, y: float, z: float, force_refresh: bool) -> None:
        """Runs off the main thread — must not touch any Tk widget directly."""
        poi: Optional[canonn_poi_data.CanonnPoi] = None
        distance: Optional[float] = None
        error: Optional[str] = None
        all_logged = False
        try:
            if force_refresh or self._thargoid_sites is None:
                self._thargoid_sites = canonn_poi_data.fetch_thargoid_sites() if thargoid_enabled() else []
            if force_refresh or self._guardian_sites is None:
                self._guardian_sites = canonn_poi_data.fetch_guardian_sites() if guardian_enabled() else []

            candidates: List[canonn_poi_data.CanonnPoi] = []
            if thargoid_enabled():
                candidates.extend(self._thargoid_sites)
            if guardian_enabled():
                candidates.extend(self._guardian_sites)

            exclude_systems: Optional[set] = None
            if skip_logged_enabled() and codex_completionist_panel.enabled():
                tally = codex_completionist_panel.controller.tally
                exclude_systems = set()
                if thargoid_enabled():
                    exclude_systems |= tally.first_systems_matching("thargoid", "xeno")
                if guardian_enabled():
                    exclude_systems |= tally.first_systems_matching("guardian")

            found = canonn_poi_data.find_nearest(candidates, x, y, z, exclude_systems=exclude_systems)
            if found is not None:
                poi, distance = found
            elif exclude_systems and candidates:
                all_logged = True
        except Exception:
            logger.exception("canonn_poi_panel lookup failed for (%s, %s, %s)", x, y, z)
            error = "lookup failed"
        self._result_queue.put((generation, poi, distance, error, all_logged))

    def _poll_queue(self) -> None:
        """Runs on the main thread via after() — safe to touch widgets here."""
        try:
            generation, poi, distance, error, all_logged = self._result_queue.get_nowait()
        except queue.Empty:
            pass
        else:
            if generation == self._generation:
                for button in (self._find_button, self._refresh_button):
                    if button is not None:
                        button.config(state=tk.NORMAL)
                if error:
                    if self._result_var is not None:
                        self._result_var.set(_ERROR_TEXT)
                elif poi is None:
                    if self._result_var is not None:
                        self._result_var.set(_ALL_LOGGED_TEXT if all_logged else _NONE_FOUND_TEXT)
                elif self._result_var is not None and distance is not None:
                    self._result_var.set(
                        f"Nearest Canonn POI: {poi.system} ({poi.category}) — {distance:,.1f} ly"
                        + (f" — {poi.instructions}" if poi.instructions else "")
                    )
                    if poi.url and self._link_label is not None:
                        self._link_label.configure(url=poi.url)
                        self._link_label.grid()
        if self._parent is not None:
            self._parent.after(200, self._poll_queue)

    # --- main-panel widgets -----------------------------------------------

    def build_panel(self, parent: tk.Frame) -> None:
        self._parent = parent
        self._result_var = tk.StringVar(value=_IDLE_TEXT)

        tk.Label(parent, text="Canonn Nearby POI", font=panelkit.bold_font(parent)).grid(
            row=0, column=0, columnspan=3, sticky=tk.W,
        )
        panelkit.wrap_label(parent, textvariable=self._result_var, anchor="w").grid(
            row=1, column=0, columnspan=3, sticky=tk.W, pady=(2, 0),
        )
        button_row = tk.Frame(parent)
        button_row.grid(row=2, column=0, columnspan=3, sticky=tk.W, pady=(4, 0))
        self._find_button = tk.Button(button_row, text="Find Nearest POI", command=self._on_find_clicked)
        self._find_button.pack(side=tk.LEFT)
        self._refresh_button = tk.Button(
            button_row, text="Refresh POI Data", command=lambda: self._on_find_clicked(force_refresh=True),
        )
        self._refresh_button.pack(side=tk.LEFT, padx=(6, 0))

        self._link_label = HyperlinkLabel(
            parent, text="View site details", background=nb.Label().cget("background"), underline=True,
        )
        self._link_label.grid(row=3, column=0, columnspan=3, sticky=tk.W, pady=(2, 0))
        self._link_label.grid_remove()

        parent.after(200, self._poll_queue)

    # --- Settings tab --------------------------------------------------

    def build_settings(self, notebook: nb.Notebook) -> None:
        frame = nb.Frame(notebook)
        frame.columnconfigure(0, weight=1)
        notebook.add(frame, text="Canonn Nearby POI")

        self._thargoid_enabled_var = tk.BooleanVar(value=thargoid_enabled())
        self._guardian_enabled_var = tk.BooleanVar(value=guardian_enabled())
        self._skip_logged_var = tk.BooleanVar(value=skip_logged_enabled())

        nb.Label(frame, text="Canonn Nearby POI", font=("TkDefaultFont", 9, "bold")).grid(
            row=0, column=0, sticky=tk.W, padx=10, pady=(10, 4),
        )
        nb.Label(
            frame,
            text=(
                "Adds a \"Find Nearest POI\" button to the Exploration panel that searches Canonn "
                "Interstellar Research's own published Thargoid/Guardian site lists for the entry "
                "closest to your current position. Manual only — this never downloads or searches "
                "on its own, only when you click a button. The site lists are cached after the "
                "first lookup; use \"Refresh POI Data\" to re-download them."
            ),
            wraplength=440, justify=tk.LEFT,
        ).grid(row=1, column=0, sticky=tk.W, padx=10, pady=(0, 4))
        nb.Checkbutton(
            frame, text="Include Thargoid sites", variable=self._thargoid_enabled_var,
        ).grid(row=2, column=0, sticky=tk.W, padx=10)
        nb.Checkbutton(
            frame, text="Include Guardian sites", variable=self._guardian_enabled_var,
        ).grid(row=3, column=0, sticky=tk.W, padx=10)
        nb.Checkbutton(
            frame, text="Skip sites already logged in Codex Completionist",
            variable=self._skip_logged_var,
        ).grid(row=4, column=0, sticky=tk.W, padx=10, pady=(0, 4))
        nb.Label(
            frame,
            text=(
                "Best-effort only: matches by the system where you first logged a Guardian/"
                "Thargoid codex entry, not a full per-site visit history. Has no effect if "
                "Codex Completionist itself is disabled."
            ),
            wraplength=440, justify=tk.LEFT,
        ).grid(row=5, column=0, sticky=tk.W, padx=10, pady=(0, 10))

        HyperlinkLabel(
            frame, text="Canonn Interstellar Research", background=nb.Label().cget("background"),
            url="https://canonn.science/", underline=True,
        ).grid(row=6, column=0, sticky=tk.W, padx=10, pady=(0, 10))

    def save_settings(self) -> None:
        if (self._thargoid_enabled_var is None or self._guardian_enabled_var is None
                or self._skip_logged_var is None):
            return
        config.set(_CFG_SKIP_LOGGED, self._skip_logged_var.get())
        config.set(_CFG_THARGOID_ENABLED, self._thargoid_enabled_var.get())
        config.set(_CFG_GUARDIAN_ENABLED, self._guardian_enabled_var.get())


controller = CanonnPoiController()


def handle_event(entry: Dict[str, Any], cmdr: str, system: Optional[str], station: Optional[str], state: Dict[str, Any]) -> None:
    controller.handle_event(entry, cmdr, system, station, state)


def build_panel(parent: tk.Frame) -> None:
    controller.build_panel(parent)


def build_settings(notebook: nb.Notebook) -> None:
    controller.build_settings(notebook)


def save_settings() -> None:
    controller.save_settings()
