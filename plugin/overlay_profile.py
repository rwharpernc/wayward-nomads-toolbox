"""
Each commander's overlay settings, kept in `overlay_settings.json` (one entry per commander, never shared: commander_data.py).

Which cards a commander runs, where they sit, and how they look are choices about that commander's play and screen, so two
commanders on one install do not share them. EDMC keeps WNTB's settings in one place (its own config), and every overlay module
reads them from there, so this module does not change where they are read. Instead the config always holds the *active*
commander's choices:

- `activate(cmdr)` runs when a commander is first seen (a journal event, or the last commander restored at start-up). It files
  the previous commander's current choices away, then loads this commander's into the config. A commander seen for the first
  time starts with a copy of what the config holds then, so an upgrade changes nothing on screen.
- `save_current(cmdr)` files the active commander's choices away after Settings are saved and when EDMC closes.

Only the keys listed here (`profile_keys`) are swapped. The overlay's connection (which overlay draws, host and port), the hide
hotkey and window preferences describe the machine, not the commander, and stay shared. A key a commander never set is removed
from the config on a switch, so another commander's choice does not leak through as theirs.
"""
from __future__ import annotations

import logging
import os
import threading
from typing import Any, Callable, Dict, Iterable, Optional, Tuple, Union

from . import commander_data

logger = logging.getLogger(__name__)

STATE_FILENAME = "overlay_settings.json"

Value = Union[str, int]

_ABSENT_INT = -(2 ** 31)       # a sentinel get_int hands back for a key that was never saved

# What a commander can choose about the overlay. Placement, Show ticks and the slot keys are added by overlay_placement.
_FIXED: Tuple[str, ...] = (
    # which cards run, and each card's own choices
    "wntb_discovery_enabled", "wntb_interdiction_enabled", "wntb_notable_enabled", "wntb_notable_rules",
    "wntb_landing_enabled", "wntb_landing_overlay_enabled", "wntb_landing_in_app_enabled",
    "wntb_inventory_overlay_enabled", "wntb_inventory_sound_enabled", "wntb_inventory_message_format",
    "wntb_inventory_announce_categories", "wntb_mining_overlay_enabled", "wntb_compass_enabled",
    "wntb_screenshot_overlay_enabled",
    "wntb_colonisation_overlay_enabled", "wntb_colonisation_overlay_row_limit", "wntb_colonisation_overlay_right_panel",
    "wntb_colonisation_overlay_forced",
    "wntb_flight_enabled", "wntb_flight_carrier", "wntb_flight_fuel", "wntb_flight_low_percent",
    "wntb_flight_unscoopable_percent", "wntb_flight_sound",
    "wntb_route_enabled", "wntb_route_rows", "wntb_route_expedition", "wntb_route_edsm",
    "wntb_targets_enabled", "wntb_targets_threshold", "wntb_targets_rows", "wntb_targets_life", "wntb_targets_online",
    "wntb_targets_done", "wntb_targets_basis",
    "wntb_body_info_enabled", "wntb_body_info_targeted", "wntb_body_info_near", "wntb_chemistry_style",
    "wntb_missions_overlay_enabled", "wntb_missions_overlay_rows", "wntb_missions_overlay_next",
    "wntb_missions_overlay_urgent_minutes",
    "wntb_expedition_log_overlay", "wntb_expedition_log_overlay_after_stop",
    "wntb_exo_status_enabled", "wntb_exo_list_enabled", "wntb_exo_radar_enabled", "wntb_exo_popup_enabled",
    "wntb_exo_radar_size", "wntb_exo_radar_fill", "wntb_exo_radar_line",
    # how the overlay looks
    "wntb_overlay_scheme", "wntb_overlay_panel_opacity", "wntb_overlay_text_size",
    "wntb_overlay_builtin_font", "wntb_overlay_corners", "wntb_overlay_keep_showing",
) + tuple(f"wntb_inventory_overlay_bar_{name}" for name in ("backpack", "ship_locker", "fleet_carrier_locker", "cargo"))

_registered: set = set()


def register(keys: Iterable[str]) -> None:
    """Adds keys other modules own (overlay_placement's per-display placement and Show ticks)."""
    _registered.update(keys)


def profile_keys() -> Tuple[str, ...]:
    return tuple(sorted(set(_FIXED) | _registered))


def _read(cfg: Any, key: str) -> Optional[Value]:
    """The setting as saved: text, a number, or None when it was never saved. EDMC refuses to read a number as text (and the
    other way round), so the text read is tried first and a refusal means it is a number."""
    try:
        text = cfg.get_str(key, default=None)
    except (ValueError, TypeError):
        text = None
    if text is not None:
        return str(text)
    try:
        number = cfg.get_int(key, default=_ABSENT_INT)
    except (ValueError, TypeError, AttributeError):
        return None
    return None if number == _ABSENT_INT else int(number)


def _write(cfg: Any, key: str, value: Optional[Value]) -> None:
    if value is None:
        try:
            cfg.delete(key, suppress=True)
        except (AttributeError, TypeError):
            logger.debug("Could not forget %s", key)
        return
    cfg.set(key, int(value) if isinstance(value, int) else str(value))


def snapshot(cfg: Any) -> Dict[str, Value]:
    """The overlay choices the config holds now (keys never saved are left out)."""
    values: Dict[str, Value] = {}
    for key in profile_keys():
        try:
            value = _read(cfg, key)
        except Exception:
            logger.debug("Could not read %s", key, exc_info=True)
            continue
        if value is not None:
            values[key] = value
    return values


def apply(cfg: Any, values: Dict[str, Value]) -> None:
    """Makes the config hold exactly `values` for the overlay keys."""
    for key in profile_keys():
        try:
            _write(cfg, key, values.get(key))
        except Exception:
            logger.debug("Could not set %s", key, exc_info=True)


def _empty() -> Dict[str, Any]:
    return {"settings": {}}


def _is_legacy(_raw: Any) -> bool:
    return False


class OverlayProfiles:
    def __init__(self, plugin_dir: Optional[str] = None, cfg: Any = None,
                 on_changed: Optional[Callable[[], None]] = None) -> None:
        self._path = os.path.join(plugin_dir or os.path.dirname(os.path.abspath(__file__)), STATE_FILENAME)
        self._cfg = cfg
        self._on_changed = on_changed
        self._store = commander_data.read(self._path, _is_legacy)
        self._lock = threading.Lock()
        self._active = ""              # the commander key whose choices the config holds
        self._edited_unclaimed = False  # Settings were saved before any commander was known

    def configure(self, plugin_dir: str, cfg: Any, on_changed: Optional[Callable[[], None]]) -> None:
        with self._lock:
            self._path = os.path.join(plugin_dir, STATE_FILENAME)
            self._cfg = cfg
            self._on_changed = on_changed
            self._store = commander_data.read(self._path, _is_legacy)

    @property
    def active(self) -> str:
        return self._active

    @property
    def active_name(self) -> str:
        """The active commander's name as it was seen, or empty before anyone is known."""
        entry = self._store["commanders"].get(self._active)
        return str(entry["name"]) if entry else ""

    def note(self) -> str:
        """The sentence Settings shows on the overlay tabs: whose choices these are."""
        name = self.active_name
        if name:
            return f"These overlay choices are saved for CMDR {name}; every commander has their own."
        return ("No commander is known yet. Choices saved now go to the first commander seen; every commander then has their own.")

    def settings_of(self, cmdr: str) -> Optional[Dict[str, Value]]:
        """What is filed for this commander, or None when they have nothing yet."""
        if not commander_data.known(self._store, cmdr):
            return None
        return dict(commander_data.payload_for(self._store, cmdr, _empty).get("settings") or {})

    def _file(self, cmdr: str, values: Dict[str, Value]) -> None:
        if self.settings_of(cmdr) == values:
            return
        commander_data.put(self._store, cmdr, {"settings": values})
        commander_data.write(self._path, self._store)

    def activate(self, cmdr: Any) -> bool:
        """Makes the config hold this commander's choices. True when it switched (the caller then redraws the overlay)."""
        key = commander_data.key_for(cmdr)
        if not key or self._cfg is None:
            return False
        with self._lock:
            if key == self._active:
                return False
            previous = self._active
            if previous:
                self._file(previous, snapshot(self._cfg))
            filed = self.settings_of(cmdr)
            switched = False
            if filed is None or self._edited_unclaimed:
                # First time seen (or Settings were saved while nobody was known): the config's choices become theirs.
                self._file(cmdr, snapshot(self._cfg))
            else:
                apply(self._cfg, filed)
                switched = True
            self._edited_unclaimed = False
            self._active = key
        logger.info("Overlay settings: %s", f"loaded for {cmdr}" if switched else f"started for {cmdr} from the current choices")
        if switched and self._on_changed is not None:
            try:
                self._on_changed()
            except Exception:
                logger.exception("Could not refresh the overlay after switching commander")
        return switched

    def save_current(self, cmdr: Any = None) -> None:
        """Files the config's choices for the active commander (after Settings are saved, and when EDMC closes). Saved with no
        commander known yet, they are kept for whoever is seen next."""
        if self._cfg is None:
            return
        with self._lock:
            target = self._active
            if not target:
                self._edited_unclaimed = True
                return
            self._file(target, snapshot(self._cfg))


profiles = OverlayProfiles()
