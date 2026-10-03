"""Platform helpers: where Elite Dangerous keeps its files, and how to send it
keys, on Windows and Linux.

On Windows, Elite's folders are in the user profile and keys go in through
Win32 calls (see autohonk.py / screenshot_automation.py). On Linux, Elite
runs under Steam Proton or Wine, so its "Windows" folders live inside a
Wine prefix, and keys are sent to its (X)Wayland window with `xdotool`.

Pure logic plus thin subprocess wrappers - no Tk, no EDMC imports beyond an
optional config lookup - so it is unit-testable (tests/test_platform_support.py).

Design notes:
- `xdotool` is used through `subprocess`, not a Python binding, so WNTB adds
  no dependency to EDMC's bundled environment. It works on X11 and on
  XWayland, which is where Elite (a Windows game) runs on a Wayland desktop.
- Keys are sent with XTEST (`xdotool keydown`, no `--window`) after
  focusing the game window. Synthetic per-window events (`--window`) are
  ignored by most games, so focusing first is required to reach Elite.
- Every wrapper returns False/None/[] on failure and never raises: input
  simulation is a convenience, not something that should ever break journal
  handling.
"""

from __future__ import annotations

import logging
import os
import re
import shutil
import subprocess
import sys
from typing import Dict, List, Optional, Tuple

try:
    from config import appname, config
except ImportError:  # unit tests outside EDMC
    appname = "EDMarketConnector"
    config = None  # type: ignore

plugin_name = os.path.basename(os.path.dirname(__file__))
logger = logging.getLogger(f"{appname}.{plugin_name}")

IS_WINDOWS = sys.platform == "win32"
IS_LINUX = sys.platform.startswith("linux")

CFG_ELITE_PREFIX = "wntb_elite_prefix"

ELITE_STEAM_APP_ID = "359320"
ELITE_WINDOW_NAME_PATTERN = r"Elite - Dangerous"

_SUBPROCESS_TIMEOUT_S = 5
_WIN_SUBDIR = os.path.join("Frontier Developments", "Elite Dangerous")


def listbox_colors(is_dark: bool) -> Tuple[str, str]:
    """(background, foreground) for a plain tk.Listbox.

    "SystemWindow"/"SystemWindowText" are Windows-only Tk colour names; on
    Linux/macOS Tk raises TclError for them, which used to stop the whole
    Settings tab from building.
    """
    if is_dark:
        return "#1e1e1e", "#e0e0e0"
    if IS_WINDOWS:
        return "SystemWindow", "SystemWindowText"
    return "white", "black"


# ---------------------------------------------------------------------------
# Elite's folders inside a Wine/Proton prefix
# ---------------------------------------------------------------------------

def steam_roots(home: Optional[str] = None) -> List[str]:
    """Steam install folders that exist, most common first (native, the
    ~/.steam symlinks, then Flatpak)."""
    home = home or os.path.expanduser("~")
    candidates = [
        os.path.join(home, ".local", "share", "Steam"),
        os.path.join(home, ".steam", "steam"),
        os.path.join(home, ".steam", "root"),
        os.path.join(home, ".var", "app", "com.valvesoftware.Steam", ".local", "share", "Steam"),
    ]
    seen: List[str] = []
    for path in candidates:
        real = os.path.realpath(path)
        if os.path.isdir(real) and real not in seen:
            seen.append(real)
    return seen


_VDF_PATH_RE = re.compile(r'"path"\s+"([^"]+)"')


def steam_library_folders(steam_root: str) -> List[str]:
    """The Steam root itself plus any extra library folders it lists in
    steamapps/libraryfolders.vdf (games and their compatdata can be on
    another drive)."""
    libraries = [steam_root]
    vdf = os.path.join(steam_root, "steamapps", "libraryfolders.vdf")
    try:
        with open(vdf, "r", encoding="utf-8", errors="replace") as fh:
            text = fh.read()
    except OSError:
        return libraries
    for match in _VDF_PATH_RE.findall(text):
        path = match.replace("\\\\", "\\")
        if path not in libraries:
            libraries.append(path)
    return libraries


def find_elite_prefix(override: str = "", home: Optional[str] = None) -> Optional[str]:
    """The Wine prefix (the folder containing `drive_c`) Elite runs in, or
    None. An explicit `override` wins: it may be the prefix itself, the
    Steam `pfx` folder, or the compatdata/<appid> folder above it."""
    override = (override or "").strip()
    if override:
        return _normalize_prefix(override)

    for root in steam_roots(home):
        for library in steam_library_folders(root):
            found = _normalize_prefix(os.path.join(library, "steamapps", "compatdata", ELITE_STEAM_APP_ID))
            if found:
                return found
    return None


def _normalize_prefix(path: str) -> Optional[str]:
    for candidate in (path, os.path.join(path, "pfx")):
        if os.path.isdir(os.path.join(candidate, "drive_c")):
            return candidate
    return None


def prefix_user_dir(prefix: str) -> Optional[str]:
    """`drive_c/users/<name>` inside the prefix. Proton uses `steamuser`;
    Lutris and plain Wine use the real username."""
    users = os.path.join(prefix, "drive_c", "users")
    try:
        names = [n for n in os.listdir(users) if n.lower() not in ("public", "default")]
    except OSError:
        return None
    for preferred in ("steamuser", os.environ.get("USER", "")):
        if preferred and preferred in names:
            return os.path.join(users, preferred)
    return os.path.join(users, sorted(names)[0]) if names else None


def get_prefix_override() -> str:
    """The user's configured prefix path, or ''."""
    if config is None:
        return ""
    try:
        return config.get_str(CFG_ELITE_PREFIX) or ""
    except Exception:
        return ""


def elite_bindings_dir(override: Optional[str] = None) -> Optional[str]:
    """Folder holding Elite's `*.binds` files, or None if it can't be found
    (Linux with no detectable prefix)."""
    if IS_WINDOWS:
        local_appdata = os.environ.get("LOCALAPPDATA") or os.path.join(os.path.expanduser("~"), "AppData", "Local")
        return os.path.join(local_appdata, _WIN_SUBDIR, "Options", "Bindings")
    user_dir = _linux_user_dir(override)
    if user_dir is None:
        return None
    return os.path.join(user_dir, "AppData", "Local", _WIN_SUBDIR, "Options", "Bindings")


def elite_pictures_dir(override: Optional[str] = None) -> Optional[str]:
    """Folder Elite writes screenshots to on Linux (inside the prefix's
    Pictures folder), or None. Windows resolves this via the shell instead
    (screenshots.py)."""
    if IS_WINDOWS:
        return None
    user_dir = _linux_user_dir(override)
    if user_dir is None:
        return None
    return os.path.join(user_dir, "Pictures", _WIN_SUBDIR)


def elite_journal_dir(override: Optional[str] = None) -> Optional[str]:
    """Where Elite writes journals and Status.json on Linux (the prefix's
    Saved Games folder), or None. On Windows EDMC finds this itself."""
    if IS_WINDOWS:
        return None
    user_dir = _linux_user_dir(override)
    if user_dir is None:
        return None
    return os.path.join(user_dir, "Saved Games", _WIN_SUBDIR)


def journal_dir_advice(configured: str, override: Optional[str] = None) -> Optional[str]:
    """A one-line hint when EDMC's Journal directory setting doesn't point at
    the journals Elite is writing inside the Wine/Proton prefix, or None if
    it looks right (or this isn't Linux). Comparison follows symlinks, since
    people often link the prefix's Saved Games folder somewhere convenient."""
    if not IS_LINUX:
        return None
    expected = elite_journal_dir(override)
    if expected is None:
        return "Couldn't find Elite's Wine/Proton prefix, so the journal folder can't be checked."
    configured = (configured or "").strip()
    if not configured:
        return f"EDMC's Journal directory is empty. Set it to: {expected}"
    if os.path.realpath(os.path.expanduser(configured)) == os.path.realpath(expected):
        return None
    return (
        f"EDMC's Journal directory is {configured}, but Elite writes to {expected}. "
        "If WNTB isn't seeing your game, set EDMC's Journal directory to that folder."
    )


def _linux_user_dir(override: Optional[str]) -> Optional[str]:
    prefix = find_elite_prefix(get_prefix_override() if override is None else override)
    return prefix_user_dir(prefix) if prefix else None


# ---------------------------------------------------------------------------
# Elite key tokens -> X11 keysym names
# ---------------------------------------------------------------------------

_X11_FIXED: Dict[str, str] = {
    "Key_Numpad_Decimal": "KP_Decimal", "Key_Numpad_Divide": "KP_Divide",
    "Key_Numpad_Multiply": "KP_Multiply", "Key_Numpad_Subtract": "KP_Subtract",
    "Key_Numpad_Add": "KP_Add",
    "Key_UpArrow": "Up", "Key_DownArrow": "Down", "Key_LeftArrow": "Left", "Key_RightArrow": "Right",
    "Key_Home": "Home", "Key_End": "End", "Key_PageUp": "Prior", "Key_PageDown": "Next",
    "Key_Insert": "Insert", "Key_Delete": "Delete", "Key_Backspace": "BackSpace", "Key_Tab": "Tab",
    "Key_Space": "space", "Key_Enter": "Return", "Key_Return": "Return", "Key_Escape": "Escape",
    "Key_LeftShift": "Shift_L", "Key_RightShift": "Shift_R",
    "Key_LeftControl": "Control_L", "Key_RightControl": "Control_R",
    "Key_LeftAlt": "Alt_L", "Key_RightAlt": "Alt_R",
    "Key_Apostrophe": "apostrophe", "Key_BackSlash": "backslash", "Key_Equals": "equal",
    "Key_Minus": "minus", "Key_Grave": "grave", "Key_LeftBracket": "bracketleft",
    "Key_RightBracket": "bracketright", "Key_Slash": "slash", "Key_Semicolon": "semicolon",
    "Key_Comma": "comma", "Key_Period": "period",
}


def x11_keysym(elite_key: str) -> Optional[str]:
    """X11 keysym name for an Elite binds-file key token (e.g. "Key_G" ->
    "g", "Key_Numpad_5" -> "KP_5"), or None if unsupported. Covers the same
    keys as autohonk.KEY_MAP."""
    if elite_key in _X11_FIXED:
        return _X11_FIXED[elite_key]
    match = re.fullmatch(r"Key_([A-Z])", elite_key)
    if match:
        return match.group(1).lower()
    if re.fullmatch(r"Key_[0-9]", elite_key):
        return elite_key[-1]
    match = re.fullmatch(r"Key_F([0-9]{1,2})", elite_key)
    if match and 1 <= int(match.group(1)) <= 24:
        return f"F{match.group(1)}"
    match = re.fullmatch(r"Key_Numpad_([0-9])", elite_key)
    if match:
        return f"KP_{match.group(1)}"
    return None


# ---------------------------------------------------------------------------
# xdotool wrappers (Linux)
# ---------------------------------------------------------------------------

def xdotool_available() -> bool:
    return IS_LINUX and shutil.which("xdotool") is not None


def _xdotool(*args: str) -> Optional[str]:
    """stdout of `xdotool <args>`, or None on any failure."""
    try:
        result = subprocess.run(
            ["xdotool", *args], capture_output=True, text=True, timeout=_SUBPROCESS_TIMEOUT_S, check=False,
        )
    except (OSError, subprocess.SubprocessError):
        logger.debug("xdotool %s failed", args, exc_info=True)
        return None
    if result.returncode != 0:
        logger.debug("xdotool %s exited %s: %s", args, result.returncode, result.stderr.strip())
        return None
    return result.stdout


def find_elite_windows() -> List[str]:
    """X11 window ids whose title starts with Elite's, newest first."""
    out = _xdotool("search", "--onlyvisible", "--name", f"^{ELITE_WINDOW_NAME_PATTERN}")
    return out.split() if out else []


def focus_window(window_id: str) -> bool:
    return _xdotool("windowactivate", "--sync", window_id) is not None


def active_window_title() -> str:
    return (_xdotool("getactivewindow", "getwindowname") or "").strip()


def key_down(keysym: str) -> bool:
    return _xdotool("keydown", keysym) is not None


def key_up(keysym: str) -> bool:
    return _xdotool("keyup", keysym) is not None


def is_process_running(pattern: str) -> bool:
    """Linux: whether a process whose command line matches `pattern`
    (`pgrep -f`) is running."""
    if not IS_LINUX or shutil.which("pgrep") is None:
        return False
    try:
        return subprocess.run(
            ["pgrep", "-f", pattern], capture_output=True, timeout=_SUBPROCESS_TIMEOUT_S, check=False,
        ).returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


# ---------------------------------------------------------------------------
# Notification sound (Linux)
# ---------------------------------------------------------------------------

def _sound_commands() -> List[List[str]]:
    commands: List[List[str]] = []
    if shutil.which("canberra-gtk-play"):
        commands.append(["canberra-gtk-play", "-i", "message"])
    sound_file = "/usr/share/sounds/freedesktop/stereo/message.oga"
    if shutil.which("paplay") and os.path.exists(sound_file):
        commands.append(["paplay", sound_file])
    return commands


def sound_available() -> bool:
    return IS_LINUX and bool(_sound_commands())


def play_notification_sound() -> bool:
    """Plays the desktop's "message" sound, trying `canberra-gtk-play`, then
    `paplay` with the freedesktop theme file. Returns whether a player ran."""
    if not IS_LINUX:
        return False
    for command in _sound_commands():
        try:
            subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return True
        except OSError:
            continue
    return False


# ---------------------------------------------------------------------------
# Settings-tab notes: which operating systems a feature needs
# ---------------------------------------------------------------------------

def input_support_note() -> Tuple[str, bool]:
    """(text, supported) for features that simulate key presses (Auto-Honk,
    the screenshot auto-timer and Thargoid capture): where they work, and
    whether they can work on *this* machine right now."""
    works_on = ("Works on: Windows; Linux with xdotool installed (X11 or XWayland - not a native Wayland "
                "window). Not on macOS.")
    if IS_WINDOWS:
        return f"{works_on} This system: Windows - supported.", True
    if IS_LINUX:
        if xdotool_available():
            return f"{works_on} This system: Linux, xdotool found - supported.", True
        return (f"{works_on} This system: Linux, xdotool NOT found - unavailable until you install it "
                "(for example: sudo apt install xdotool)."), False
    return f"{works_on} This system is not supported, so this feature is unavailable.", False


def sound_support_note() -> Tuple[str, bool]:
    """(text, supported) for the pickup notification sound."""
    works_on = "Works on: Windows (system beep); Linux with canberra-gtk-play or paplay installed. Not on macOS."
    if IS_WINDOWS:
        return f"{works_on} This system: Windows - supported.", True
    if IS_LINUX:
        if sound_available():
            return f"{works_on} This system: Linux, a sound player was found - supported.", True
        return (f"{works_on} This system: Linux, no sound player found - unavailable until you install one "
                "(canberra-gtk-play or pulseaudio-utils)."), False
    return f"{works_on} This system is not supported, so this option is unavailable.", False
