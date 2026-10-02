"""Missions mode: active mission tracking across every category (massacre/
settlement-raid kill-stacking, generic Trade/Passenger/Covert/Combat/Other
missions, and Community Goals).

This module is the feature-module contract entry point (mirrors
`powerplay.py`'s role) — `ui.py`/`load.py` only ever call the functions
below, never reach into `missions_ui.py` or the data-layer modules
directly. The data/logic layer is split across several files:

- `mission_types.py` — classification rules (zero deps)
- `mining_methods.py` — shared mining-method lookup (also used by Mining
  mode)
- `kill_tracker.py`, `active_missions.py`, `community_goal_state.py` —
  per-CMDR state, each with its own `*_listeners` list
- `kill_missions.py`, `all_missions.py` — derived views that subscribe
  to `active_missions`' and `kill_tracker`'s change notifications
  as a side effect of being imported
- `journal_scan.py` — historic journal-backlog scan (this module's `start`
  calls it once, on plugin_start3)
- `missions_ui.py` — the main-panel content (Canvas+Scrollbar category
  pages) and the "All Missions"/mission-detail popups, which self-registers
  onto `kill_missions`'/`all_missions`'/`community_goal_state`'s
  listener lists the same way

Python's own import caching handles the self-registration ordering
correctly regardless of the order imported below — each module declares its
own dependencies, so importing `missions_ui` (which imports `kill_missions`
and `all_missions`) is sufficient to bring in the whole chain exactly once.
"""

from __future__ import annotations

import datetime as dt
import logging
import os
from dataclasses import dataclass
from typing import Any, Dict, Optional

import tkinter as tk

import myNotebook as nb
from config import appname, config

from . import active_missions, community_goal_state, kill_tracker, missions_ui
from .journal_scan import read_backlog

plugin_name = os.path.basename(os.path.dirname(__file__))
logger = logging.getLogger(f"{appname}.{plugin_name}")

PANEL_PLACEMENT = "missions"

_CFG_DELTA = "wntb_missions_display_delta_column"
_CFG_PROGRESS = "wntb_missions_display_progress"
_CFG_SUM = "wntb_missions_display_sum_row"
_CFG_MISSION_COUNT = "wntb_missions_display_mission_count"
_CFG_SETTLEMENT = "wntb_missions_display_settlement"
_CFG_COMMODITIES_NEEDED = "wntb_missions_display_commodities_needed"

_JOURNAL_SCAN_LOOKBACK = dt.timedelta(weeks=2)


@dataclass
class MissionsConfig:
    display_delta_column: bool = True
    display_progress: bool = True
    display_sum_row: bool = True
    display_mission_count: bool = True
    display_settlement: bool = True
    display_commodities_needed: bool = True


def load_config() -> MissionsConfig:
    return MissionsConfig(
        display_delta_column=config.get_bool(_CFG_DELTA, default=True),
        display_progress=config.get_bool(_CFG_PROGRESS, default=True),
        display_sum_row=config.get_bool(_CFG_SUM, default=True),
        display_mission_count=config.get_bool(_CFG_MISSION_COUNT, default=True),
        display_settlement=config.get_bool(_CFG_SETTLEMENT, default=True),
        display_commodities_needed=config.get_bool(_CFG_COMMODITIES_NEEDED, default=True),
    )


def save_config(cfg: MissionsConfig) -> None:
    config.set(_CFG_DELTA, cfg.display_delta_column)
    config.set(_CFG_PROGRESS, cfg.display_progress)
    config.set(_CFG_SUM, cfg.display_sum_row)
    config.set(_CFG_MISSION_COUNT, cfg.display_mission_count)
    config.set(_CFG_SETTLEMENT, cfg.display_settlement)
    config.set(_CFG_COMMODITIES_NEEDED, cfg.display_commodities_needed)


def _to_display_settings(cfg: MissionsConfig) -> missions_ui.DisplaySettings:
    return missions_ui.DisplaySettings(
        delta=cfg.display_delta_column,
        progress=cfg.display_progress,
        sum=cfg.display_sum_row,
        mission_count=cfg.display_mission_count,
        settlement=cfg.display_settlement,
        commodities_needed=cfg.display_commodities_needed,
    )


class MissionsController:
    def __init__(self) -> None:
        self._enabled_vars: Dict[str, tk.BooleanVar] = {}

    # --- lifecycle ----------------------------------------------------------

    def start(self, plugin_dir: str) -> None:
        """Reads the last two weeks of journals so mission state survives
        EDMC restarts. A scan failure must never prevent the rest of the
        plugin from loading — live journal events still work without the
        backlog."""
        try:
            backlog = read_backlog(dt.date.today() - _JOURNAL_SCAN_LOOKBACK)
            logger.info(
                "Journal scan found mission data for %d CMDR(s)", len(backlog.accepted),
            )
            active_missions.tracker.load_history(backlog.accepted)
            kill_tracker.initialize(
                backlog.bounties, backlog.redirected, backlog.redirect_targets,
            )
            community_goal_state.initialize(backlog.goals)
        except Exception:
            logger.exception("Journal scan failed - starting with empty state")
            active_missions.tracker.load_history({})
            kill_tracker.initialize({}, {}, {})
            community_goal_state.initialize({})

        missions_ui.ui.apply_display_settings(_to_display_settings(load_config()))

    # --- journal dispatch -----------------------------------------------------

    def handle_event(self, entry: Dict[str, Any], cmdr: str, system: Optional[str], station: Optional[str], state: Dict[str, Any]) -> None:
        event = entry.get("event")

        if cmdr:
            # Order matters: the kill tracker must know the CMDR before the
            # active-missions tracker announces, because progress is computed for the
            # current CMDR.
            kill_tracker.set_current_cmdr(cmdr)
            community_goal_state.set_current_cmdr(cmdr)
            active_missions.tracker.switch_to(cmdr)

        if event == "Missions":
            # Sent at login: authoritative list of currently active mission IDs.
            active_mission_uuids = [int(m["MissionID"]) for m in entry.get("Active", [])]
            active_missions.tracker.sync_login(cmdr, active_mission_uuids)
            # Also authoritative for which of those are already objective-
            # complete (e.g. right after a relog, before a fresh
            # MissionRedirected fires) - sync_login must run first so
            # the tracker knows about these mission IDs before
            # kill_tracker's own listeners re-derive status/progress.
            complete_mission_uuids = {int(m["MissionID"]) for m in entry.get("Complete", [])}
            kill_tracker.mark_complete(cmdr, complete_mission_uuids)

        elif event == "MissionAccepted":
            active_missions.tracker.accept(cmdr, entry)

        elif event in ("MissionAbandoned", "MissionCompleted", "MissionFailed"):
            active_missions.tracker.finish(cmdr, entry["MissionID"])
            kill_tracker.forget_mission(cmdr, entry["MissionID"])

        elif event == "MissionRedirected":
            # Fired when a mission objective is complete and the game
            # redirects you back to turn it in - possibly at a new
            # station/system.
            kill_tracker.add_redirect(cmdr, entry)

        elif event == "Bounty":
            # Fired for both ship kills and on-foot kills of wanted targets.
            kill_tracker.add_bounty(cmdr, entry)

        elif event == "CommunityGoal":
            # Not scoped to the current station - CurrentGoals can list
            # several Community Goals across different systems at once.
            community_goal_state.update_goals(cmdr, entry)

    # --- main-panel widgets -------------------------------------------------

    def build_panel(self, parent: tk.Frame) -> None:
        missions_ui.ui.build_panel(parent)

    # --- Settings tab --------------------------------------------------------

    def build_settings(self, notebook: nb.Notebook) -> None:
        frame = nb.Frame(notebook)
        frame.columnconfigure(0, weight=1)
        notebook.add(frame, text="Missions")

        cfg = load_config()

        nb.Label(frame, text="UI Settings", font=("TkDefaultFont", 9, "bold")).grid(
            row=0, column=0, sticky=tk.W, padx=10, pady=(10, 2),
        )

        checkboxes = (
            ("display_progress", "Display Kill Progress", cfg.display_progress),
            ("display_delta_column", "Display Delta-Column", cfg.display_delta_column),
            ("display_sum_row", "Display Sum-Row", cfg.display_sum_row),
            ("display_mission_count", "Display Mission Count", cfg.display_mission_count),
            ("display_settlement", "Display Target Settlement (Ground Missions)", cfg.display_settlement),
            (
                "display_commodities_needed", "Display Commodities Needed (Trade & Mining)",
                cfg.display_commodities_needed,
            ),
        )
        self._enabled_vars = {}
        for row, (key, label, default) in enumerate(checkboxes, start=1):
            var = tk.BooleanVar(value=default)
            self._enabled_vars[key] = var
            nb.Checkbutton(frame, text=label, variable=var).grid(
                row=row, column=0, sticky=tk.W, padx=10, pady=2,
            )

    def save_settings(self) -> None:
        if not self._enabled_vars:
            return
        cfg = MissionsConfig(
            display_delta_column=bool(self._enabled_vars["display_delta_column"].get()),
            display_progress=bool(self._enabled_vars["display_progress"].get()),
            display_sum_row=bool(self._enabled_vars["display_sum_row"].get()),
            display_mission_count=bool(self._enabled_vars["display_mission_count"].get()),
            display_settlement=bool(self._enabled_vars["display_settlement"].get()),
            display_commodities_needed=bool(self._enabled_vars["display_commodities_needed"].get()),
        )
        save_config(cfg)
        missions_ui.ui.apply_display_settings(_to_display_settings(cfg))


controller = MissionsController()


def start(plugin_dir: str) -> None:
    controller.start(plugin_dir)


def handle_event(entry: Dict[str, Any], cmdr: str, system: Optional[str], station: Optional[str], state: Dict[str, Any]) -> None:
    controller.handle_event(entry, cmdr, system, station, state)


def build_panel(parent: tk.Frame) -> None:
    controller.build_panel(parent)


def build_settings(notebook: nb.Notebook) -> None:
    controller.build_settings(notebook)


def save_settings() -> None:
    controller.save_settings()
