"""GEC Nearby POI: an on-demand "find the nearest catalogued point of
interest" lookup against edastro.com's (Elite Dangerous Astrometrics) GEC
API - see gec_poi_edastro.py and docs/ATTRIBUTIONS.md.

Deliberately **manual, not automatic-on-jump**: a button-triggered lookup
rather than a live call firing on every FSDJump, so
this never fires on its own and stays well clear of edastro's published
rate limit (100 requests/15 min) even on long multi-jump exploration runs.
No opt-in/opt-out setting is needed as a result - there's no passive
network activity to gate, unlike exploration_value.py's ELW-rarity/EDSM-
upload readouts.

Lives inside Exploration mode's panel (PANEL_PLACEMENT = "exploration"),
alongside Auto-Honk/Discovery/Boxel Survey/Exploration Value/Organic
Scanning/Codex Completionist - each gets
its own dedicated child frame (see ui.py's create_plugin_app/
_stack_features()), separated by a thin panelkit-drawn rule, so no
cross-feature row coordination is needed here.
"""

from __future__ import annotations

import logging
import os
import queue
import threading
from typing import Any, Dict, Mapping, Optional, Tuple

import tkinter as tk

import myNotebook as nb
from config import appname
from ttkHyperlinkLabel import HyperlinkLabel

from . import gec_poi_edastro, panelkit

plugin_name = os.path.basename(os.path.dirname(__file__))
logger = logging.getLogger(f"{appname}.{plugin_name}")

PANEL_PLACEMENT = "exploration"

_IDLE_TEXT = "Nearby POI: (jump into a system, then click Find Nearest POI)"
_NO_POSITION_TEXT = "Nearby POI: current position unknown — jump or reload first"
_CHECKING_TEXT = "Nearby POI: checking edastro.com..."
_ERROR_TEXT = "Nearby POI: lookup failed — see EDMarketConnector.log"


class GecPoiController:
    def __init__(self) -> None:
        self._star_pos: Optional[Tuple[float, float, float]] = None

        self._result_var: Optional[tk.StringVar] = None
        self._find_button: Optional[tk.Button] = None
        self._link_label: Optional[HyperlinkLabel] = None
        self._parent: Optional[tk.Frame] = None

        # Worker-thread + queue.Queue + after()-polling plumbing, same
        # pattern as exploration_value.py's own opt-in network lookups.
        # Generation counter lets a later click supersede an in-flight one.
        self._generation = 0
        self._result_queue: "queue.Queue[Tuple[int, Optional[gec_poi_edastro.NearestPoi], Optional[str]]]" = queue.Queue()

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

    def _on_find_clicked(self) -> None:
        if self._star_pos is None:
            if self._result_var is not None:
                self._result_var.set(_NO_POSITION_TEXT)
            return

        self._generation += 1
        generation = self._generation
        if self._result_var is not None:
            self._result_var.set(_CHECKING_TEXT)
        if self._link_label is not None:
            self._link_label.grid_remove()
        if self._find_button is not None:
            self._find_button.config(state=tk.DISABLED)

        x, y, z = self._star_pos
        threading.Thread(target=self._worker, args=(generation, x, y, z), daemon=True).start()

    def _worker(self, generation: int, x: float, y: float, z: float) -> None:
        """Runs off the main thread — must not touch any Tk widget directly."""
        result: Optional[gec_poi_edastro.NearestPoi] = None
        error: Optional[str] = None
        try:
            result = gec_poi_edastro.find_nearest_poi(x, y, z)
        except Exception:
            logger.exception("gec_poi_panel lookup failed for (%s, %s, %s)", x, y, z)
            error = "lookup failed"
        self._result_queue.put((generation, result, error))

    def _poll_queue(self) -> None:
        """Runs on the main thread via after() — safe to touch widgets here."""
        try:
            generation, result, error = self._result_queue.get_nowait()
        except queue.Empty:
            pass
        else:
            if generation == self._generation:
                if self._find_button is not None:
                    self._find_button.config(state=tk.NORMAL)
                if error:
                    if self._result_var is not None:
                        self._result_var.set(_ERROR_TEXT)
                elif result is not None and self._result_var is not None:
                    rating = f", rating {result.rating:.1f}" if result.rating is not None else ""
                    self._result_var.set(
                        f"Nearby POI: {result.name} ({result.category}) — "
                        f"{result.distance_ly:,.1f} ly, {result.region}{rating}"
                    )
                    if result.url and self._link_label is not None:
                        self._link_label.configure(url=result.url)
                        self._link_label.grid()
        if self._parent is not None:
            self._parent.after(200, self._poll_queue)

    # --- main-panel widgets -----------------------------------------------

    def build_panel(self, parent: tk.Frame) -> None:
        self._parent = parent
        self._result_var = tk.StringVar(value=_IDLE_TEXT)

        body = panelkit.collapsible_section(parent, "GEC Nearby POI", "wntb_gec_poi_collapsed")
        panelkit.wrap_label(body, textvariable=self._result_var, anchor="w").grid(
            row=1, column=0, columnspan=3, sticky=tk.W, pady=(2, 0),
        )
        self._find_button = tk.Button(body, text="Find Nearest POI", command=self._on_find_clicked)
        self._find_button.grid(row=2, column=0, sticky=tk.W, pady=(4, 0))
        self._link_label = HyperlinkLabel(
            body, text="View on edastro.com", background=nb.Label().cget("background"), underline=True,
        )
        self._link_label.grid(row=3, column=0, columnspan=3, sticky=tk.W, pady=(2, 0))
        self._link_label.grid_remove()

        parent.after(200, self._poll_queue)

    # --- Settings tab --------------------------------------------------

    def build_settings(self, notebook: nb.Notebook) -> None:
        frame = nb.Frame(notebook)
        frame.columnconfigure(0, weight=1)
        notebook.add(frame, text="GEC Nearby POI")

        nb.Label(frame, text="GEC Nearby POI", font=("TkDefaultFont", 9, "bold")).grid(
            row=0, column=0, sticky=tk.W, padx=10, pady=(10, 4),
        )
        nb.Label(
            frame,
            text=(
                "Adds a \"Find Nearest POI\" button to the Exploration panel that looks up the "
                "nearest catalogued point of interest to your current position, via edastro.com's "
                "(Elite Dangerous Astrometrics) Galactic Exploration Catalog. Manual only — this "
                "never makes a network call on its own, only when you click the button."
            ),
            wraplength=440, justify=tk.LEFT,
        ).grid(row=1, column=0, sticky=tk.W, padx=10, pady=(0, 4))

        HyperlinkLabel(
            frame, text="edastro.com GEC", background=nb.Label().cget("background"),
            url="https://edastro.com/gec/", underline=True,
        ).grid(row=2, column=0, sticky=tk.W, padx=10, pady=(0, 10))

    def save_settings(self) -> None:
        pass


controller = GecPoiController()


def handle_event(entry: Dict[str, Any], cmdr: str, system: Optional[str], station: Optional[str], state: Dict[str, Any]) -> None:
    controller.handle_event(entry, cmdr, system, station, state)


def build_panel(parent: tk.Frame) -> None:
    controller.build_panel(parent)


def build_settings(notebook: nb.Notebook) -> None:
    controller.build_settings(notebook)


def save_settings() -> None:
    controller.save_settings()
