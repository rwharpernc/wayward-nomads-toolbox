"""Optional notification sound for Field Ops pillage pickups.

Windows uses the stdlib-only `winsound` module. Linux plays the desktop's
message sound through `canberra-gtk-play` or `paplay` when either is
installed (see platform_support.play_notification_sound). Neither adds a pip
dependency; the checkbox is unavailable where no player exists.
"""

from __future__ import annotations

import logging
import os

from config import appname

from . import platform_support

plugin_name = os.path.basename(os.path.dirname(__file__))
logger = logging.getLogger(f"{appname}.{plugin_name}")

try:
    import winsound  # stdlib, Windows-only
except ImportError:
    winsound = None  # type: ignore


class PillageSound:
    """Plays a short system sound on pickup, when enabled and available."""

    def __init__(self) -> None:
        self._enabled = False

    @property
    def available(self) -> bool:
        return winsound is not None or platform_support.sound_available()

    def set_enabled(self, enabled: bool) -> None:
        self._enabled = enabled

    def play(self) -> None:
        if not self._enabled:
            return
        if winsound is None:
            platform_support.play_notification_sound()
            return
        try:
            winsound.MessageBeep(winsound.MB_ICONASTERISK)
        except Exception:
            logger.exception("Notification sound failed; disabling for this session")
            self._enabled = False
