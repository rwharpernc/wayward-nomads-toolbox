"""
GUI focus detection and per-panel crop rectangles for Field Ops screenshot
capture.

Elite Dangerous does not report which HUD panel is open in the Screenshot
journal event itself, so this reads it separately from ``status.json`` (the
same file EDMC's own status overlay uses), written alongside the journal.
"""

from __future__ import annotations

import json
import logging
import os
from os.path import expanduser
from typing import Optional, Tuple

from config import appname, config

plugin_name = os.path.basename(os.path.dirname(__file__))
logger = logging.getLogger(f"{appname}.{plugin_name}")

# GuiFocus values from the Player Journal's status.json (Frontier's own enum).
GUI_FOCUS_NONE = 0
GUI_FOCUS_INTERNAL_PANEL = 1  # Systems / left-hand ship panel
GUI_FOCUS_EXTERNAL_PANEL = 2  # Target panel
GUI_FOCUS_COMMS_PANEL = 3
GUI_FOCUS_ROLE_PANEL = 4
GUI_FOCUS_STATION_SERVICES = 5
GUI_FOCUS_GALAXY_MAP = 6
GUI_FOCUS_SYSTEM_MAP = 7
GUI_FOCUS_ORRERY = 8
GUI_FOCUS_FSS_MODE = 9
GUI_FOCUS_SAA_MODE = 10
GUI_FOCUS_CODEX = 11

# Crop rectangles as fractions of a 1920x1080 reference frame, (left, top,
# right, bottom). Scaled to the screenshot's actual Width/Height at capture
# time (see _scale_rect) so they hold up reasonably well at other
# resolutions and aspect ratios.
_REFERENCE_WIDTH = 1920
_REFERENCE_HEIGHT = 1080

_PANEL_CROPS_REFERENCE = {
    GUI_FOCUS_EXTERNAL_PANEL: (850, 279, 1306, 538),
    GUI_FOCUS_COMMS_PANEL: (406, 123, 919, 832),
    GUI_FOCUS_ROLE_PANEL: (451, 270, 1460, 837),
    GUI_FOCUS_INTERNAL_PANEL: (451, 270, 1460, 837),
}

CropRect = Tuple[int, int, int, int]


def panel_crop_rect(gui_focus: int, width: int, height: int) -> Optional[CropRect]:
    """Return a crop box for the given GuiFocus panel, scaled to (width, height)."""
    reference = _PANEL_CROPS_REFERENCE.get(gui_focus)
    if reference is None:
        return None
    return _scale_rect(reference, width, height)


def thargoid_crop_rect(width: int, height: int) -> CropRect:
    """Bottom-left quadrant, used for the Thargoid-scan auto-crop."""
    return (0, height // 2, width // 2, height)


def _scale_rect(rect: Tuple[int, int, int, int], width: int, height: int) -> CropRect:
    """Scale a reference-frame crop rect to the screenshot's actual
    (width, height), preserving its shape.

    Elite Dangerous's HUD panels don't stretch to fill a wider-than-16:9
    display - they stay the same proportional size and sit centered, with
    unused space (letterboxing) on the sides on ultrawide/Surround setups.
    A single uniform scale factor (the *smaller* of the two axis ratios,
    i.e. whichever axis is the limiting one) reproduces that: on a
    16:9 screenshot sx == sy so this is unchanged from a plain per-axis
    scale; on a wider-than-16:9 frame the height is limiting, so the rect
    scales by height alone and gets centered horizontally via `offset_x`
    (and symmetrically for a taller-than-16:9 frame). Independently
    scaling sx/sy (the previous approach) stretched the crop box itself
    out of proportion on any non-16:9 screenshot."""
    left, top, right, bottom = rect
    scale = min(width / _REFERENCE_WIDTH, height / _REFERENCE_HEIGHT)
    offset_x = (width - _REFERENCE_WIDTH * scale) / 2
    offset_y = (height - _REFERENCE_HEIGHT * scale) / 2
    return (
        int(left * scale + offset_x),
        int(top * scale + offset_y),
        int(right * scale + offset_x),
        int(bottom * scale + offset_y),
    )


def current_gui_focus() -> Optional[int]:
    """Read GuiFocus from status.json; None if unavailable or unreadable."""
    journal_dir = config.get_str("journaldir") or config.default_journal_dir
    if not journal_dir:  # no default on some Linux setups
        return None
    status_path = os.path.join(expanduser(journal_dir), "Status.json")  # exact case: Linux filesystems are case-sensitive
    try:
        with open(status_path, encoding="utf-8") as fh:
            data = json.load(fh)
        return int(data.get("GuiFocus", GUI_FOCUS_NONE))
    except (OSError, ValueError, TypeError) as exc:
        logger.debug("Could not read GuiFocus from status.json: %s", exc)
        return None
