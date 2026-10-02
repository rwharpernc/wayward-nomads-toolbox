"""
Automation: detects Elite Dangerous and simulates the screenshot hotkey
(F10) on a timer.

Windows uses pywin32, already bundled with EDMC, instead of hand-rolled
ctypes structures. Linux uses `xdotool` (see platform_support.py), so it is
only available there when xdotool is installed. Every entry point is a safe
no-op when unsupported, so the rest of Field Ops' screenshot handling
(conversion, cropping, UI) works unmodified everywhere, including macOS.
"""

from __future__ import annotations

import logging
import os
from sys import platform
from typing import Optional

from config import appname

from . import platform_support

plugin_name = os.path.basename(os.path.dirname(__file__))
logger = logging.getLogger(f"{appname}.{plugin_name}")

_WINDOWS = platform == "win32"
SUPPORTED = _WINDOWS or platform_support.xdotool_available()

if _WINDOWS:
    import win32api
    import win32con
    import win32gui

    VK_F10 = win32con.VK_F10
    VK_LMENU = win32con.VK_LMENU  # Left Alt — held with F10 for a hi-res capture

_ELITE_WINDOW_PREFIX = "Elite - Dangerous"

# Hi-res (Alt+F10) screenshots are only permitted in Solo / no multiplayer.
_HI_RES_ELIGIBLE_MODES = {"Solo"}


def is_elite_foreground() -> bool:
    """True if an Elite Dangerous window currently has OS input focus."""
    if not SUPPORTED:
        return False
    if not _WINDOWS:
        return platform_support.active_window_title().startswith(_ELITE_WINDOW_PREFIX)
    try:
        hwnd = win32gui.GetForegroundWindow()
        title = win32gui.GetWindowText(hwnd)
    except Exception:
        logger.debug("GetForegroundWindow/GetWindowText failed", exc_info=True)
        return False
    return bool(title) and title.startswith(_ELITE_WINDOW_PREFIX)


def press_screenshot_keys(*, hi_res: bool, game_mode: Optional[str]) -> bool:
    """
    Press F10 (optionally with Left Alt, for a hi-res capture in Solo).

    Returns whether Left Alt was pressed, so the caller can pass it back to
    `release_screenshot_keys`. The caller is responsible for scheduling that
    release a short delay later (e.g. via Tk's `after`) — releasing only
    when the *next* journal event happens to arrive would leave the key
    logically "held" for an unbounded time in the meantime.
    """
    if not SUPPORTED:
        return False

    use_alt = hi_res and game_mode in _HI_RES_ELIGIBLE_MODES
    if use_alt:
        _key_down("alt")
    _key_down("f10")
    return use_alt


def release_screenshot_keys(alt_was_pressed: bool) -> None:
    if not SUPPORTED:
        return
    _key_up("f10")
    if alt_was_pressed:
        _key_up("alt")


# "f10" / "alt" are platform-neutral names, resolved to a Win32 virtual key
# or an X11 keysym here so callers don't care which they're on.
_X11_KEYSYMS = {"f10": "F10", "alt": "Alt_L"}


def _key_down(name: str) -> None:
    if _WINDOWS:
        win32api.keybd_event(VK_F10 if name == "f10" else VK_LMENU, 0, 0, 0)
    else:
        platform_support.key_down(_X11_KEYSYMS[name])


def _key_up(name: str) -> None:
    if _WINDOWS:
        win32api.keybd_event(VK_F10 if name == "f10" else VK_LMENU, 0, win32con.KEYEVENTF_KEYUP, 0)
    else:
        platform_support.key_up(_X11_KEYSYMS[name])
