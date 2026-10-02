"""
WNTB — Wayward Nomads Toolbox — plugin entry point.

Copyright (c) 2026 R.W. Harper. Licensed under the GNU General Public
License v3.0 - see LICENSE and THIRD-PARTY-NOTICES.md at the repository
root.

Wires up the standard EDMC lifecycle hooks and the shared mode-switching
panel/overlay/updater, then forwards every journal event unconditionally to
each registered feature module's own `handle_event` — each feature decides
internally what it cares about and whether it's currently enabled (see
each feature's own docstring for why "forward unconditionally, gate
inside" is the established pattern: it's cheap, and it means load.py
never needs per-event-type knowledge of any feature).
"""

from __future__ import annotations

import logging
import os
import tkinter as tk
from typing import Any, Dict, Optional

from config import appname, config

from . import (
    __version__, autohonk, bgs_panel, boxel_survey, canonn_poi_panel, codex_completionist_panel, colonisation_panel, discovery,
    exploration_value, gec_poi_panel, interdiction, inventory_panel, landing, mining_overlay, mining_panel,
    missions, organic_scan_panel, overlay, platform_support, powerplay, powerplay_window, rare_goods_window, screenshots, ship_builds_panel, ui,
)
from .update import UpdateManager, check_applied_update

plugin_name = os.path.basename(os.path.dirname(__file__))
logger = logging.getLogger(f"{appname}.{plugin_name}")

if not logger.hasHandlers():
    level = logging.INFO
    logger.setLevel(level)
    logger_channel = logging.StreamHandler()
    logger_formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - "
        "%(module)s:%(lineno)d:%(funcName)s: %(message)s",
    )
    logger_formatter.default_time_format = "%Y-%m-%d %H:%M:%S"
    logger_formatter.default_msec_format = "%s.%03d"
    logger_channel.setFormatter(logger_formatter)
    logger.addHandler(logger_channel)

# Every feature module that consumes journal events. Order doesn't matter -
# each one only ever reads `entry`/`state`, never mutates them.
_FEATURES = (
    powerplay, missions, autohonk, interdiction, landing, discovery, boxel_survey, exploration_value,
    organic_scan_panel, codex_completionist_panel, gec_poi_panel, canonn_poi_panel, ship_builds_panel, colonisation_panel, screenshots,
    inventory_panel, mining_panel, bgs_panel,
)

_ui_frame: Optional[tk.Frame] = None
_updater: Optional[UpdateManager] = None

# One shared EDMCOverlay connection for every overlay-drawing feature
# (Interdiction/Landing/Discovery) - see overlay.py's own docstring for why
# a persistent, shared connection is required rather than one per feature.
_overlay = overlay.OverlayClient()


def plugin_start3(plugin_dir: str) -> str:
    """Load WNTB into EDMarketConnector."""
    global _updater
    logger.info("WNTB v%s starting from %s", __version__, plugin_dir)

    powerplay.controller.start(plugin_dir)
    missions.start(plugin_dir)
    boxel_survey.start(plugin_dir)
    codex_completionist_panel.start(plugin_dir)
    organic_scan_panel.start(plugin_dir)
    bgs_panel.start(plugin_dir)
    ship_builds_panel.start(plugin_dir)
    colonisation_panel.start(plugin_dir)
    inventory_panel.start(plugin_dir)
    mining_panel.start(plugin_dir)
    interdiction.set_overlay_client(_overlay)
    landing.set_overlay_client(_overlay)
    discovery.set_overlay_client(_overlay)
    screenshots.set_overlay_client(_overlay)
    inventory_panel.set_overlay_client(_overlay)
    mining_panel.set_overlay_client(_overlay)

    # Every feature with its own background-rect-behind-text overlay card
    # registers an EDMCModernOverlay Plugin Group (see overlay.py's own
    # docstring) - a live report (2026-09) found the background invisible
    # under EDMCModernOverlay specifically *without* one, so this now
    # matches Landing's approach across the board rather than being the
    # exception.
    overlay.register_modern_overlay_groups([
        (landing.GROUP_NAME, landing.GROUP_PREFIX),
        (inventory_panel.GROUP_NAME, inventory_panel.GROUP_PREFIX),
        (discovery.GROUP_NAME, discovery.GROUP_PREFIX),
        (interdiction.GROUP_NAME, interdiction.GROUP_PREFIX),
        (mining_overlay.GROUP_NAME, mining_overlay.GROUP_PREFIX),
        (screenshots.GROUP_NAME, screenshots.GROUP_PREFIX),
    ])

    if platform_support.IS_LINUX:
        advice = platform_support.journal_dir_advice(config.get_str("journaldir") or "")
        if advice:
            logger.warning("Linux journal folder: %s", advice)

    applied_version = check_applied_update()
    if applied_version is not None:
        logger.info("WNTB updated to v%s", applied_version)
        ui.set_update_applied(applied_version)

    _updater = UpdateManager(plugin_dir, on_ready=_on_update_ready, on_downloading=_on_update_downloading)
    _updater.check_async()
    return "WNTB"


def _on_update_downloading(version: str) -> None:
    if _ui_frame is not None:
        _ui_frame.after(0, lambda: ui.set_update_downloading(version))


def _on_update_ready(version: str) -> None:
    if _ui_frame is not None:
        _ui_frame.after(0, lambda: ui.set_update_downloaded(version))


def plugin_stop() -> None:
    """EDMarketConnector is closing."""
    powerplay.controller.flush()
    boxel_survey.stop()
    codex_completionist_panel.stop()
    organic_scan_panel.stop()
    bgs_panel.stop()
    inventory_panel.stop()
    mining_panel.stop()
    powerplay_window.close()
    rare_goods_window.close()
    _overlay.close()
    logger.info("WNTB shutting down")


def plugin_app(parent: tk.Frame) -> tk.Frame:
    """Create WNTB's widgets on the EDMC main window."""
    global _ui_frame
    _ui_frame = ui.create_plugin_app(parent)
    return _ui_frame


def plugin_prefs(parent, cmdr: str, is_beta: bool):
    """Create the WNTB settings tab."""
    return ui.create_prefs(parent)


def prefs_changed(cmdr: str, is_beta: bool) -> None:
    """Settings were saved."""
    ui.save_prefs()
    powerplay.controller.flush()


def journal_entry(
    cmdr: str,
    is_beta: bool,
    system: Optional[str],
    station: Optional[str],
    entry: Dict[str, Any],
    state: Dict[str, Any],
) -> None:
    """Dispatches journal events to every feature module's own handle_event."""
    for feature in _FEATURES:
        feature.handle_event(entry, cmdr, system, station, state)


def capi_fleetcarrier(data: Any) -> None:
    """EDMC calls this when fresh CAPI `/fleetcarrier` data arrives
    (requires Frontier auth; fetched on CarrierBuy/CarrierStats, ~15min
    throttle) - a separate hook from journal_entry, not a journal event.
    Only Inventory's fleet-carrier-locker tracking currently needs this."""
    inventory_panel.capi_fleetcarrier(data)


def dashboard_entry(cmdr: str, is_beta: bool, entry: Dict[str, Any]) -> None:
    """EDMC calls this on every Status.json change (roughly once a second in
    flight) - entry is the parsed file directly. The only thing WNTB reads
    from it is the Flags bitmask, for Interdiction's "Being Interdicted" bit
    (the earliest interdiction signal, before any resolving journal event -
    see interdiction.py)."""
    flags = entry.get("Flags")
    if isinstance(flags, int):
        interdiction.handle_dashboard_flags(flags)
    mining_panel.dashboard_status(entry)
    organic_scan_panel.dashboard_status(entry)
