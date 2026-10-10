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
    __version__, autohonk, bgs_panel, boxel_survey, canonn_poi_panel, codex_completionist_panel, colonisation_overlay, colonisation_panel, discovery,
    exploration_value, game_mode, gec_poi_panel, interdiction, inventory_panel, landing, mining_overlay, mining_panel,
    missions, notable, organic_scan_panel, overlay, platform_support, powerplay, powerplay_window, rare_goods_window, restore, screenshots, session_credits, ship_builds_panel, trade_panel, ui,
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
    powerplay, missions, autohonk, interdiction, landing, discovery, notable, boxel_survey, exploration_value,
    organic_scan_panel, codex_completionist_panel, gec_poi_panel, canonn_poi_panel, ship_builds_panel, colonisation_panel, screenshots,
    inventory_panel, mining_panel, trade_panel, bgs_panel, game_mode, session_credits,
)

_ui_frame: Optional[tk.Frame] = None
_live_event_seen = False   # any journal event from EDMC (a running game sends StartUp straight away)
RESTORE_DELAY_MS = 4000
_updater: Optional[UpdateManager] = None

# One shared EDMCOverlay connection for every overlay-drawing feature
# (Interdiction/Landing/Discovery) - see overlay.py's own docstring for why
# a persistent, shared connection is required rather than one per feature.
_overlay = overlay.OverlayClient()


# One-time reset: every overlay is off by default, and users who had overlays on from
# earlier versions are switched off once so they opt back in deliberately. The marker
# key makes it run exactly once per install; bump the suffix to force another reset.
_CFG_OVERLAY_RESET_DONE = "wntb_overlay_reset_v1"
_OVERLAY_ENABLE_KEYS = (
    "wntb_discovery_enabled",
    "wntb_interdiction_enabled",
    "wntb_notable_enabled",
    "wntb_landing_overlay_enabled",
    "wntb_inventory_overlay_enabled",
    "wntb_mining_overlay_enabled",
    "wntb_mining_waypoint_overlay_enabled",
    "wntb_screenshot_overlay_enabled",
)


def _reset_overlays_once() -> None:
    if config.get_bool(_CFG_OVERLAY_RESET_DONE, default=False):
        return
    for key in _OVERLAY_ENABLE_KEYS:
        config.set(key, False)
    config.set(_CFG_OVERLAY_RESET_DONE, True)
    logger.info("All WNTB overlays reset to disabled (one-time); re-enable them in Settings")


def plugin_start3(plugin_dir: str) -> str:
    """Load WNTB into EDMarketConnector."""
    global _updater
    logger.info("WNTB v%s starting from %s", __version__, plugin_dir)

    _reset_overlays_once()  # before any feature module reads its settings

    powerplay.controller.start(plugin_dir)
    missions.start(plugin_dir)
    boxel_survey.start(plugin_dir)
    codex_completionist_panel.start(plugin_dir)
    organic_scan_panel.start(plugin_dir)
    bgs_panel.start(plugin_dir)
    session_credits.start(plugin_dir)
    ship_builds_panel.start(plugin_dir)
    colonisation_panel.start(plugin_dir)
    inventory_panel.start(plugin_dir)
    mining_panel.start(plugin_dir)
    trade_panel.start(plugin_dir)
    interdiction.set_overlay_client(_overlay)
    landing.set_overlay_client(_overlay)
    discovery.set_overlay_client(_overlay)
    notable.set_overlay_client(_overlay)
    screenshots.set_overlay_client(_overlay)
    inventory_panel.set_overlay_client(_overlay)
    colonisation_panel.set_overlay_client(_overlay)
    mining_panel.set_overlay_client(_overlay)

    # Every feature with its own background-rect-behind-text overlay card
    # registers an EDMCModernOverlay Plugin Group (see overlay.py's own
    # docstring) - without one, the background can render invisible under
    # EDMCModernOverlay.
    overlay.register_modern_overlay_groups([
        (landing.GROUP_NAME, landing.GROUP_PREFIX),
        (inventory_panel.GROUP_NAME, inventory_panel.GROUP_PREFIX),
        (discovery.GROUP_NAME, discovery.GROUP_PREFIX),
        (notable.GROUP_NAME, notable.GROUP_PREFIX),
        (interdiction.GROUP_NAME, interdiction.GROUP_PREFIX),
        (mining_overlay.GROUP_NAME, mining_overlay.GROUP_PREFIX),
        (screenshots.GROUP_NAME, screenshots.GROUP_PREFIX),
        (colonisation_overlay.GROUP_NAME, colonisation_overlay.GROUP_PREFIX),
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
    session_credits.stop()
    inventory_panel.stop()
    colonisation_panel.stop()
    mining_panel.stop()
    trade_panel.stop()
    powerplay_window.close()
    rare_goods_window.close()
    _overlay.close()
    logger.info("WNTB shutting down")


def plugin_app(parent: tk.Frame) -> tk.Frame:
    """Create WNTB's widgets on the EDMC main window."""
    global _ui_frame
    _ui_frame = ui.create_plugin_app(parent)
    _ui_frame.after(RESTORE_DELAY_MS, _restore_commander_if_idle)
    return _ui_frame


def _restore_commander_if_idle() -> None:
    """EDMC started without the game running, so no event will say who is playing until the next login. Tell every
    feature the last commander from the newest journal so nothing waits for a login (see restore.py)."""
    if _live_event_seen:
        return
    try:
        cmdr = restore.latest_commander()
        if cmdr:
            handled = restore.dispatch(_FEATURES, cmdr)
            logger.info("No game running at start-up; restored commander %s in %d feature(s)", cmdr, handled)
    except Exception:
        logger.exception("Could not restore the last commander")


def plugin_prefs(parent, cmdr: str, is_beta: bool):
    """Create the WNTB settings tab."""
    return ui.create_prefs(parent)


def prefs_changed(cmdr: str, is_beta: bool) -> None:
    """Settings were saved."""
    ui.save_prefs()
    powerplay.controller.flush()
    # A changed overlay host/port applies straight away: drop the old connection
    # and forget any recent "no overlay found" cool-off.
    _overlay.close()
    _overlay.retry_now()


def journal_entry(
    cmdr: str,
    is_beta: bool,
    system: Optional[str],
    station: Optional[str],
    entry: Dict[str, Any],
    state: Dict[str, Any],
) -> None:
    """Dispatches journal events to every feature module's own handle_event."""
    global _live_event_seen
    _live_event_seen = True
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
