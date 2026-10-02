"""Auto-Honk: fires the ship's Discovery Scanner on system entry.

Reads the commander's active Elite Dangerous binds file to find which
physical key the configured fire button (Primary/Secondary) is bound to
on the keyboard, then simulates that key being held down for a
configurable duration whenever a jump lands in a new system.

Windows: key-injection calls go in-process via `ctypes` against
`user32.dll`/`kernel32.dll` — no extra process, and no dependency beyond
the Python standard library. Every Windows-only call below is behind an
explicit `sys.platform == "win32"` check.

Linux: Elite runs under Steam Proton/Wine, so its binds file is found inside
the Wine prefix and the key is sent to its window with `xdotool` (X11 and
XWayland) - see platform_support.py for the why.

Lives inside Exploration mode's panel (PANEL_PLACEMENT = "exploration") —
not a Toolbox mode of its own.
"""

from __future__ import annotations

import ctypes
import logging
import os
import re
import subprocess
import sys
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

import tkinter as tk

import myNotebook as nb
from config import appname, config

from . import panelkit, platform_support

if sys.platform == "win32":
    from ctypes import wintypes

plugin_name = os.path.basename(os.path.dirname(__file__))
logger = logging.getLogger(f"{appname}.{plugin_name}")

PANEL_PLACEMENT = "exploration"

FIRE_BUTTONS: Tuple[str, ...] = ("Primary", "Secondary")
_ACTION_BY_FIRE_BUTTON: Dict[str, str] = {"Primary": "PrimaryFire", "Secondary": "SecondaryFire"}

# Other ED companion apps whose own automation could double up with this
# feature — currently just EDCoPilot, since it has its own AutoHonk
# setting that fires the same physical key for the same purpose.
COMPANION_APPS: Tuple[Tuple[str, str], ...] = (("EDCoPilot.exe", "EDCoPilot"),)

# System-entry events that should trigger a honk attempt.
SYSTEM_JUMP_EVENTS: Tuple[str, ...] = ("FSDJump", "CarrierJump")

_CFG_ENABLED = "wntb_autohonk_enabled"
_CFG_FIRE_BUTTON = "wntb_autohonk_firebutton"
_CFG_FOCUS = "wntb_autohonk_focus"
_CFG_SKIP_VISITED = "wntb_autohonk_skipvisited"
_CFG_HOLD_MS = "wntb_autohonk_holdms"

DEFAULT_ENABLED = False
DEFAULT_FIRE_BUTTON = "Secondary"
DEFAULT_FOCUS = True
DEFAULT_SKIP_VISITED = True
# The Discovery Scanner isn't a tap — it charges up while the button stays
# physically depressed and only fires once fully charged, so a keydown+
# keyup tap never actually honks. Charge time depends on the fitted scanner
# module and engineering, so this is a generous default.
DEFAULT_HOLD_MS = 10000


@dataclass
class AutoHonkConfig:
    enabled: bool = DEFAULT_ENABLED
    fire_button: str = DEFAULT_FIRE_BUTTON
    focus_game_window: bool = DEFAULT_FOCUS
    skip_if_visited_this_session: bool = DEFAULT_SKIP_VISITED
    hold_ms: int = DEFAULT_HOLD_MS


def load_config() -> AutoHonkConfig:
    fire_button = config.get_str(_CFG_FIRE_BUTTON)
    if fire_button not in FIRE_BUTTONS:
        fire_button = DEFAULT_FIRE_BUTTON

    hold_raw = config.get_str(_CFG_HOLD_MS)
    try:
        hold_ms = int(hold_raw) if hold_raw else DEFAULT_HOLD_MS
    except ValueError:
        hold_ms = DEFAULT_HOLD_MS
    if hold_ms <= 0:
        hold_ms = DEFAULT_HOLD_MS

    return AutoHonkConfig(
        enabled=config.get_bool(_CFG_ENABLED, default=DEFAULT_ENABLED),
        fire_button=fire_button,
        focus_game_window=config.get_bool(_CFG_FOCUS, default=DEFAULT_FOCUS),
        skip_if_visited_this_session=config.get_bool(_CFG_SKIP_VISITED, default=DEFAULT_SKIP_VISITED),
        hold_ms=hold_ms,
    )


def save_config(cfg: AutoHonkConfig) -> None:
    config.set(_CFG_ENABLED, cfg.enabled)
    config.set(_CFG_FIRE_BUTTON, cfg.fire_button)
    config.set(_CFG_HOLD_MS, str(cfg.hold_ms))
    config.set(_CFG_FOCUS, cfg.focus_game_window)
    config.set(_CFG_SKIP_VISITED, cfg.skip_if_visited_this_session)


# ---------------------------------------------------------------------------
# Key map: ED binds-file key tokens (e.g. "Key_Numpad_Divide") -> a Windows
# virtual-key code and a human-readable label.
# ---------------------------------------------------------------------------

KEY_MAP: Dict[str, Tuple[int, str]] = {}


def _map(key: str, vk: int, label: str) -> None:
    KEY_MAP[key] = (vk, label)


for _digit in range(10):
    _map(f"Key_{_digit}", 0x30 + _digit, str(_digit))

for _i, _letter in enumerate("ABCDEFGHIJKLMNOPQRSTUVWXYZ"):
    _map(f"Key_{_letter}", 0x41 + _i, _letter)

for _n in range(1, 25):
    _map(f"Key_F{_n}", 0x70 + (_n - 1), f"F{_n}")

for _digit in range(10):
    _map(f"Key_Numpad_{_digit}", 0x60 + _digit, f"Numpad {_digit}")
_map("Key_Numpad_Decimal", 0x6E, "Numpad .")
_map("Key_Numpad_Divide", 0x6F, "Numpad /")
_map("Key_Numpad_Multiply", 0x6A, "Numpad *")
_map("Key_Numpad_Subtract", 0x6D, "Numpad -")
_map("Key_Numpad_Add", 0x6B, "Numpad +")

_map("Key_UpArrow", 0x26, "Up Arrow")
_map("Key_DownArrow", 0x28, "Down Arrow")
_map("Key_LeftArrow", 0x25, "Left Arrow")
_map("Key_RightArrow", 0x27, "Right Arrow")
_map("Key_Home", 0x24, "Home")
_map("Key_End", 0x23, "End")
_map("Key_PageUp", 0x21, "Page Up")
_map("Key_PageDown", 0x22, "Page Down")
_map("Key_Insert", 0x2D, "Insert")
_map("Key_Delete", 0x2E, "Delete")
_map("Key_Backspace", 0x08, "Backspace")
_map("Key_Tab", 0x09, "Tab")
_map("Key_Space", 0x20, "Space")
_map("Key_Enter", 0x0D, "Enter")
_map("Key_Return", 0x0D, "Enter")
_map("Key_Escape", 0x1B, "Esc")

_map("Key_LeftShift", 0xA0, "Left Shift")
_map("Key_RightShift", 0xA1, "Right Shift")
_map("Key_LeftControl", 0xA2, "Left Ctrl")
_map("Key_RightControl", 0xA3, "Right Ctrl")
_map("Key_LeftAlt", 0xA4, "Left Alt")
_map("Key_RightAlt", 0xA5, "Right Alt")

_map("Key_Apostrophe", 0xDE, "'")
_map("Key_BackSlash", 0xDC, "\\")
_map("Key_Equals", 0xBB, "=")
_map("Key_Minus", 0xBD, "-")
_map("Key_Grave", 0xC0, "`")
_map("Key_LeftBracket", 0xDB, "[")
_map("Key_RightBracket", 0xDD, "]")
_map("Key_Slash", 0xBF, "/")
_map("Key_Semicolon", 0xBA, ";")
_map("Key_Comma", 0xBC, ",")
_map("Key_Period", 0xBE, ".")


# ---------------------------------------------------------------------------
# Binds-file lookup. ED's own bindings folder (Local AppData) is a
# different root from the journal's (Saved Games).
# ---------------------------------------------------------------------------

def _bindings_directory() -> Optional[str]:
    return platform_support.elite_bindings_dir()


def _find_active_binds_file() -> Optional[str]:
    """Finds the currently-active Custom.<major>.<minor>.binds file.

    StartPreset.start names the active preset by base name (near-
    universally "Custom"); ED bumps the version suffix whenever its own
    binding schema changes, leaving old-version files stale but present,
    so picking the most recently *modified* matching file is more robust
    than trying to parse/compare the version numbers.
    """
    directory = _bindings_directory()
    if not directory:
        return None

    preset_name = "Custom"
    try:
        with open(os.path.join(directory, "StartPreset.start"), "r", encoding="utf-8") as fh:
            first_line = fh.readline().strip()
        if first_line:
            preset_name = first_line
    except OSError:
        pass

    try:
        entries = os.listdir(directory)
    except OSError:
        return None

    pattern = re.compile(rf"^{re.escape(preset_name)}\.\d+\.\d+\.binds$", re.IGNORECASE)
    candidates = [name for name in entries if pattern.match(name)]
    if not candidates:
        return None

    def _mtime(name: str) -> float:
        try:
            return os.path.getmtime(os.path.join(directory, name))
        except OSError:
            return 0.0

    candidates.sort(key=_mtime, reverse=True)
    return os.path.join(directory, candidates[0])


_SLOT_PATTERN = re.compile(r'<(?:Primary|Secondary)\s+Device="([^"]*)"\s+Key="([^"]*)"')


def _extract_binding_slots(xml_text: str, action: str) -> List[Tuple[str, str]]:
    """Extracts the <Primary>/<Secondary> input slots for one action block
    (e.g. <SecondaryFire>) from a binds file's raw XML text. Hand-rolled
    rather than a full XML parser — the format is flat and regular."""
    block_match = re.search(rf"<{re.escape(action)}>([\s\S]*?)</{re.escape(action)}>", xml_text)
    if not block_match:
        return []
    return [
        (device, key)
        for device, key in _SLOT_PATTERN.findall(block_match.group(1))
        if device and key
    ]


def _get_fire_button_binding(fire_button: str) -> Tuple[bool, List[Tuple[str, str]]]:
    """Returns (found, slots). `found` is False if the binds file itself
    couldn't be located or read — distinct from "found it but the action
    has no bindings"."""
    if not _input_supported():
        return False, []

    path = _find_active_binds_file()
    if not path:
        return False, []
    try:
        with open(path, "r", encoding="utf-8") as fh:
            xml_text = fh.read()
    except OSError:
        return False, []
    return True, _extract_binding_slots(xml_text, _ACTION_BY_FIRE_BUTTON[fire_button])


def resolve_key_binding(fire_button: str) -> Dict[str, Optional[str]]:
    """Combines the raw binds-file lookup with the key-token-to-VK mapping
    into one status dict the Settings UI can render directly:
    {"status": ..., "label": ..., "raw_key": ...}."""
    found, slots = _get_fire_button_binding(fire_button)
    if not found:
        return {"status": "binds-not-found", "label": None, "raw_key": None}

    keyboard_slot = next((slot for slot in slots if slot[0] == "Keyboard"), None)
    if keyboard_slot is None:
        status = "no-keyboard-binding" if slots else "not-bound"
        return {"status": status, "label": None, "raw_key": None}

    raw_key = keyboard_slot[1]
    mapped = KEY_MAP.get(raw_key)
    if mapped is None:
        return {"status": "unsupported-key", "label": None, "raw_key": raw_key}
    return {"status": "resolved", "label": mapped[1], "raw_key": raw_key}


BINDING_STATUS_TEXT: Dict[str, str] = {
    "no-keyboard-binding": (
        "This fire button is only bound to a joystick/HOTAS button, not a keyboard key — "
        "Auto-Honk can only simulate keyboard input. Rebind it to a keyboard key in-game, "
        "or switch fire buttons above."
    ),
    "not-bound": "This fire button isn't bound to anything in your active control preset.",
    "unsupported-key": "This key isn't supported yet for simulated input — try a different key or fire button.",
    "binds-not-found": "Couldn't find or read your Elite Dangerous keybindings file.",
    "unresolved": "No usable keybind resolved.",
}

HONK_OUTCOME_TEXT: Dict[str, str] = {
    "sent": "sent",
    "window-not-found": "Elite Dangerous window not found",
    "unresolved": "no usable keybind resolved",
    "unsupported-platform": "unsupported on this OS (Windows and Linux only)",
    "input-tool-missing": "xdotool isn't installed (Linux) — install it, e.g. `sudo apt install xdotool`",
    "error": "error — see the EDMC log",
}


# ---------------------------------------------------------------------------
# Win32 key injection via direct ctypes calls against
# user32.dll/kernel32.dll — no subprocess needed for a same-process
# Python call.
# ---------------------------------------------------------------------------

_ELITE_WINDOW_TITLE = "Elite - Dangerous (CLIENT)"
_ELITE_WINDOW_CLASS = "FrontierDevelopmentsAppWinClass"

_KEYEVENTF_EXTENDEDKEY = 0x0001
_KEYEVENTF_KEYUP = 0x0002
_MAPVK_VK_TO_VSC = 0
_SW_RESTORE = 9
_VK_MENU = 0x12

_EXTENDED_VKS = {0x21, 0x22, 0x23, 0x24, 0x25, 0x26, 0x27, 0x28, 0x2D, 0x2E, 0x6F, 0xA3, 0xA5}

if sys.platform == "win32":
    _user32 = ctypes.WinDLL("user32", use_last_error=True)
    _kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

    _user32.FindWindowW.restype = wintypes.HWND
    _user32.FindWindowW.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR]
    _user32.GetForegroundWindow.restype = wintypes.HWND
    _user32.SetForegroundWindow.restype = wintypes.BOOL
    _user32.SetForegroundWindow.argtypes = [wintypes.HWND]
    _user32.ShowWindow.restype = wintypes.BOOL
    _user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
    _user32.GetWindowThreadProcessId.restype = wintypes.DWORD
    _user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
    _user32.AttachThreadInput.restype = wintypes.BOOL
    _user32.AttachThreadInput.argtypes = [wintypes.DWORD, wintypes.DWORD, wintypes.BOOL]
    _user32.keybd_event.restype = None
    _user32.keybd_event.argtypes = [wintypes.BYTE, wintypes.BYTE, wintypes.DWORD, ctypes.c_size_t]
    _user32.MapVirtualKeyW.restype = wintypes.UINT
    _user32.MapVirtualKeyW.argtypes = [wintypes.UINT, wintypes.UINT]
    _kernel32.GetCurrentThreadId.restype = wintypes.DWORD
else:
    _user32 = None
    _kernel32 = None


def _find_elite_window() -> int:
    return _user32.FindWindowW(_ELITE_WINDOW_CLASS, _ELITE_WINDOW_TITLE)


def _send_key_event(vk: int, key_up: bool) -> None:
    scan = _user32.MapVirtualKeyW(vk, _MAPVK_VK_TO_VSC)
    flags = 0
    if vk in _EXTENDED_VKS:
        flags |= _KEYEVENTF_EXTENDEDKEY
    if key_up:
        flags |= _KEYEVENTF_KEYUP
    _user32.keybd_event(vk, scan, flags, 0)


def _bring_to_foreground(hwnd: int) -> bool:
    fg = _user32.GetForegroundWindow()
    if fg == hwnd:
        return True

    # Windows' foreground-lock heuristic silently ignores
    # SetForegroundWindow from a background process unless it just
    # observed a genuine Alt keypress — simulate one to unlock it.
    _user32.keybd_event(_VK_MENU, 0, 0, 0)
    _user32.keybd_event(_VK_MENU, 0, _KEYEVENTF_KEYUP, 0)

    fg_pid = wintypes.DWORD()
    fg_thread = _user32.GetWindowThreadProcessId(fg, ctypes.byref(fg_pid))
    cur_thread = _kernel32.GetCurrentThreadId()
    attached = False
    if fg_thread and fg_thread != cur_thread:
        attached = bool(_user32.AttachThreadInput(cur_thread, fg_thread, True))

    _user32.ShowWindow(hwnd, _SW_RESTORE)
    result = bool(_user32.SetForegroundWindow(hwnd))

    if attached:
        _user32.AttachThreadInput(cur_thread, fg_thread, False)
    return result


def _input_supported() -> bool:
    return sys.platform == "win32" or platform_support.IS_LINUX


def send_key_press(raw_key: str, focus_window: bool, hold_ms: int) -> str:
    """Simulates the key for the binds-file token `raw_key` (e.g. "Key_G")
    being held down for `hold_ms` against the Elite Dangerous window.
    Blocking for up to ~hold_ms — always call from a background thread,
    never the Tk main thread. Returns a HonkOutcome string (see
    HONK_OUTCOME_TEXT)."""
    if sys.platform == "win32":
        return _send_key_press_windows(KEY_MAP[raw_key][0], focus_window, hold_ms)
    if platform_support.IS_LINUX:
        return _send_key_press_linux(raw_key, focus_window, hold_ms)
    return "unsupported-platform"


def _send_key_press_linux(raw_key: str, focus_window: bool, hold_ms: int) -> str:
    if not platform_support.xdotool_available():
        return "input-tool-missing"
    keysym = platform_support.x11_keysym(raw_key)
    if keysym is None:
        return "unresolved"
    try:
        windows = platform_support.find_elite_windows()
        if not windows:
            return "window-not-found"
        if focus_window:
            platform_support.focus_window(windows[0])
            time.sleep(0.12)
        # XTEST goes to whichever window has focus, like Windows' keybd_event.
        if not platform_support.key_down(keysym):
            return "error"
        try:
            if hold_ms > 0:
                time.sleep(hold_ms / 1000)
        finally:
            platform_support.key_up(keysym)
        return "sent"
    except Exception:
        logger.warning("Auto-Honk: send_key_press failed", exc_info=True)
        return "error"


def _send_key_press_windows(vk: int, focus_window: bool, hold_ms: int) -> str:
    try:
        hwnd = _find_elite_window()
        if not hwnd:
            return "window-not-found"

        if focus_window:
            _bring_to_foreground(hwnd)
            time.sleep(0.12)

        _send_key_event(vk, False)
        if hold_ms > 0:
            time.sleep(hold_ms / 1000)
        _send_key_event(vk, True)
        return "sent"
    except Exception:
        logger.warning("Auto-Honk: send_key_press failed", exc_info=True)
        return "error"


def is_process_running(image_name: str) -> bool:
    """Whether a process with this exact image name is currently running.
    On Linux it matches the name (minus ".exe") against process command lines.
    Elsewhere this reports not-running rather than erroring, since the
    companion-app conflict check is a nice-to-have."""
    if platform_support.IS_LINUX:
        return platform_support.is_process_running(re.sub(r"\.exe$", "", image_name, flags=re.IGNORECASE))
    if sys.platform != "win32":
        return False
    try:
        result = subprocess.run(
            ["tasklist", "/FI", f"IMAGENAME eq {image_name}", "/FO", "CSV", "/NH"],
            capture_output=True,
            text=True,
            timeout=5,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        return image_name.lower() in result.stdout.lower()
    except Exception:
        logger.warning("Auto-Honk: process check failed", exc_info=True)
        return False


# ---------------------------------------------------------------------------
# Controller: this mode's one entry point for load.py/ui.py.
# ---------------------------------------------------------------------------

def _attempt_honk(
    fire_button: str, focus_window: bool, hold_ms: int, label: str, on_done: Callable[[str, str], None],
) -> None:
    binding = resolve_key_binding(fire_button)
    if binding["status"] == "resolved":
        outcome = send_key_press(binding["raw_key"], focus_window, hold_ms)
    else:
        outcome = "unresolved"
    on_done(label, outcome)


class AutoHonkController:
    """Watches for system-entry journal events and, when enabled, simulates
    the keyboard key bound to the configured fire button."""

    def __init__(self) -> None:
        self.config: AutoHonkConfig = load_config()
        self._visited_this_session: Set[int] = set()
        self.last_attempt: Optional[Dict[str, Any]] = None

        self._toggle_btn: Optional[tk.Button] = None
        self._toggle_off_colors: Tuple[str, str] = ("", "")

        self._enabled_var: Optional[tk.BooleanVar] = None
        self._firebutton_var: Optional[tk.StringVar] = None
        self._hold_var: Optional[tk.StringVar] = None
        self._focus_var: Optional[tk.BooleanVar] = None
        self._skipvisited_var: Optional[tk.BooleanVar] = None
        self._prefix_var: Optional[tk.StringVar] = None
        self._dependent_widgets: List[tk.Widget] = []
        self._status_label: Optional[nb.Label] = None
        self._result_label: Optional[nb.Label] = None
        self._frame: Optional[nb.Frame] = None

    def reload_config(self) -> None:
        """Re-reads settings from EDMC's config store — called after the
        Settings tab is saved, so a live-game toggle takes effect
        immediately rather than only on EDMC's next restart."""
        self.config = load_config()

    def reset_session(self) -> None:
        """A fresh login (new journal file, not a same-file relog) clears
        same-session "already visited" memory."""
        self._visited_this_session.clear()

    def handle_event(self, entry: Dict[str, Any], cmdr: str, system: Optional[str], station: Optional[str], state: Dict[str, Any]) -> None:
        if entry.get("event") == "LoadGame":
            self.reset_session()
        if not self.config.enabled or entry.get("event") not in SYSTEM_JUMP_EVENTS:
            return

        system_address = entry.get("SystemAddress")
        system_name = entry.get("StarSystem") or system or "Unknown system"

        if self.config.skip_if_visited_this_session and isinstance(system_address, int):
            if system_address in self._visited_this_session:
                return
        if isinstance(system_address, int):
            self._visited_this_session.add(system_address)

        cfg = self.config
        threading.Thread(
            target=_attempt_honk,
            args=(cfg.fire_button, cfg.focus_game_window, cfg.hold_ms, system_name, self._record_attempt),
            name="WNTB-autohonk",
            daemon=True,
        ).start()

    def _record_attempt(self, system: str, outcome: str) -> None:
        self.last_attempt = {"system": system, "outcome": outcome, "at": datetime.now(timezone.utc).isoformat()}
        logger.info("Auto-Honk: %s — %s", system, outcome)
        if self._result_label is not None:
            try:
                self._result_label.after(0, lambda: self._set_result(system, outcome))
            except tk.TclError:
                pass

    def _set_result(self, system: str, outcome: str) -> None:
        if self._result_label is not None:
            self._result_label["text"] = f"Last test ({system}): {HONK_OUTCOME_TEXT.get(outcome, outcome)}"

    # --- main-panel widgets -------------------------------------------------

    def build_panel(self, parent: tk.Frame) -> None:
        row = tk.Frame(parent)
        row.grid(row=0, column=0, sticky=tk.W, pady=(4, 0))
        self._toggle_btn = tk.Button(row, text="Auto-Honk", command=self._on_toggle_click)
        self._toggle_btn.pack(side=tk.LEFT)

        self._toggle_off_colors = panelkit.capture_toggle_off_colors(self._toggle_btn)
        panelkit.apply_toggle_button_state(self._toggle_btn, self.config.enabled, self._toggle_off_colors)

    def _on_toggle_click(self) -> None:
        cfg = load_config()
        cfg.enabled = not cfg.enabled
        save_config(cfg)
        self.reload_config()
        panelkit.apply_toggle_button_state(self._toggle_btn, cfg.enabled, self._toggle_off_colors)

    # --- Settings tab --------------------------------------------------------

    def build_settings(self, notebook: nb.Notebook) -> None:
        frame = nb.Frame(notebook)
        frame.columnconfigure(0, weight=1)
        notebook.add(frame, text="Auto-Honk")
        self._frame = frame

        cfg = load_config()

        nb.Label(
            frame,
            text=(
                "Automatically fires your ship's Discovery Scanner — the basic system-wide "
                '"honk" that reveals bodies, not the Detailed Surface Scanner — every time you '
                "jump into a new system."
            ),
            wraplength=440, justify=tk.LEFT,
        ).grid(row=0, column=0, columnspan=2, sticky=tk.W, padx=10, pady=(10, 6))

        nb.Label(
            frame,
            text="If EDCoPilot is also running with its own Auto-Honk turned on, turn one of the two off.",
            wraplength=440, justify=tk.LEFT, foreground="#c07000",
        ).grid(row=1, column=0, columnspan=2, sticky=tk.W, padx=10, pady=(0, 8))

        self._enabled_var = tk.BooleanVar(value=cfg.enabled)
        nb.Checkbutton(
            frame, text="Enable Auto-Honk", variable=self._enabled_var, command=self._update_dependent_state,
        ).grid(row=2, column=0, columnspan=2, sticky=tk.W, padx=10, pady=2)

        sub = nb.Frame(frame)
        sub.grid(row=3, column=0, columnspan=2, sticky=tk.W, padx=(28, 10))

        fire_row = tk.Frame(sub)
        fire_row.grid(row=0, column=0, sticky=tk.W, pady=2)
        nb.Label(fire_row, text="Fire button:").pack(side=tk.LEFT)
        self._firebutton_var = tk.StringVar(value=cfg.fire_button)
        firebutton_menu = tk.OptionMenu(fire_row, self._firebutton_var, *FIRE_BUTTONS)
        firebutton_menu.pack(side=tk.LEFT, padx=(4, 0))
        nb.Label(fire_row, text="   Hold (sec):").pack(side=tk.LEFT)
        self._hold_var = tk.StringVar(value=f"{cfg.hold_ms / 1000:g}")
        hold_entry = nb.EntryMenu(fire_row, textvariable=self._hold_var, width=5)
        hold_entry.pack(side=tk.LEFT, padx=(4, 0))

        behavior_row = tk.Frame(sub)
        behavior_row.grid(row=1, column=0, sticky=tk.W, pady=2)
        self._focus_var = tk.BooleanVar(value=cfg.focus_game_window)
        focus_check = nb.Checkbutton(behavior_row, text="Focus game window first", variable=self._focus_var)
        focus_check.pack(side=tk.LEFT)
        self._skipvisited_var = tk.BooleanVar(value=cfg.skip_if_visited_this_session)
        skip_check = nb.Checkbutton(
            behavior_row, text="Skip systems already visited", variable=self._skipvisited_var,
        )
        skip_check.pack(side=tk.LEFT, padx=(16, 0))

        self._dependent_widgets = [firebutton_menu, hold_entry, focus_check, skip_check]

        if platform_support.IS_LINUX:
            prefix_row = tk.Frame(frame)
            prefix_row.grid(row=4, column=0, columnspan=2, sticky=tk.W, padx=10, pady=(6, 0))
            nb.Label(
                prefix_row,
                text="Elite Wine/Proton prefix (blank = auto-detect Steam):",
            ).pack(side=tk.LEFT)
            self._prefix_var = tk.StringVar(value=platform_support.get_prefix_override())
            nb.EntryMenu(prefix_row, textvariable=self._prefix_var, width=28).pack(side=tk.LEFT, padx=(4, 0))
            advice = platform_support.journal_dir_advice(config.get_str("journaldir") or "")
            if advice:
                nb.Label(
                    frame, text=advice, wraplength=440, justify=tk.LEFT, foreground="#c07000",
                ).grid(row=8, column=0, columnspan=2, sticky=tk.W, padx=10, pady=(0, 10))

        self._status_label = nb.Label(frame, text="", wraplength=440, justify=tk.LEFT)
        self._status_label.grid(row=5, column=0, columnspan=2, sticky=tk.W, padx=10, pady=(10, 2))

        action_row = tk.Frame(frame)
        action_row.grid(row=6, column=0, columnspan=2, sticky=tk.W, padx=10, pady=(0, 2))
        tk.Button(action_row, text="Rescan", command=self._rescan).pack(side=tk.LEFT)
        tk.Button(action_row, text="Test Honk Now", command=self._test_honk).pack(side=tk.LEFT, padx=(6, 0))
        self._result_label = nb.Label(action_row, text="", wraplength=280, justify=tk.LEFT)
        self._result_label.pack(side=tk.LEFT, padx=(10, 0))

        nb.Label(
            frame,
            text="(These two work even while Auto-Honk is disabled above, so you can check your setup first.)",
            wraplength=440, justify=tk.LEFT,
        ).grid(row=7, column=0, columnspan=2, sticky=tk.W, padx=10, pady=(0, 10))

        self._update_dependent_state()
        self._rescan()

    def _update_dependent_state(self) -> None:
        if self._enabled_var is None:
            return
        state = tk.NORMAL if self._enabled_var.get() else tk.DISABLED
        for widget in self._dependent_widgets:
            try:
                widget["state"] = state
            except tk.TclError:
                pass

    def _binding_text(self, fire_button: str) -> Tuple[str, str]:
        binding = resolve_key_binding(fire_button)
        status = binding["status"]
        if status == "resolved":
            return f"Will press {binding['label']} when you jump into a system.", "#2e7d32"
        return BINDING_STATUS_TEXT.get(status, status), "#c07000"

    def _rescan(self) -> None:
        if self._firebutton_var is None or self._status_label is None:
            return
        text, color = self._binding_text(self._firebutton_var.get())
        text = f"Status: {text}"
        conflicts = [name for exe, name in COMPANION_APPS if is_process_running(exe)]
        if conflicts:
            text += (
                "\n" + ", ".join(conflicts) + " is running — if its own Auto-Honk is also enabled, "
                "you'll get duplicate honks."
            )
        self._status_label["text"] = text
        self._status_label["foreground"] = color

    def _test_honk(self) -> None:
        if self._firebutton_var is None or self._result_label is None:
            return

        fire_button = self._firebutton_var.get()
        focus_window = bool(self._focus_var.get()) if self._focus_var is not None else DEFAULT_FOCUS
        try:
            hold_ms = max(1, round(float(self._hold_var.get()) * 1000)) if self._hold_var is not None else DEFAULT_HOLD_MS
        except ValueError:
            hold_ms = DEFAULT_HOLD_MS

        self._result_label["text"] = "Testing…"
        frame = self._frame

        def worker() -> None:
            binding = resolve_key_binding(fire_button)
            if binding["status"] == "resolved":
                outcome = send_key_press(binding["raw_key"], focus_window, hold_ms)
            else:
                outcome = "unresolved"
            if frame is not None:
                try:
                    frame.after(0, lambda: self._set_result("Test", outcome))
                except tk.TclError:
                    pass

        threading.Thread(target=worker, name="WNTB-autohonk-test", daemon=True).start()

    def save_settings(self) -> None:
        if self._enabled_var is None:
            return

        fire_button = self._firebutton_var.get() if self._firebutton_var is not None else DEFAULT_FIRE_BUTTON
        if fire_button not in FIRE_BUTTONS:
            fire_button = DEFAULT_FIRE_BUTTON

        try:
            hold_ms = max(1000, round(float(self._hold_var.get()) * 1000)) if self._hold_var is not None else DEFAULT_HOLD_MS
        except ValueError:
            hold_ms = DEFAULT_HOLD_MS

        save_config(AutoHonkConfig(
            enabled=bool(self._enabled_var.get()),
            fire_button=fire_button,
            focus_game_window=bool(self._focus_var.get()) if self._focus_var is not None else DEFAULT_FOCUS,
            skip_if_visited_this_session=(
                bool(self._skipvisited_var.get()) if self._skipvisited_var is not None else DEFAULT_SKIP_VISITED
            ),
            hold_ms=hold_ms,
        ))
        if self._prefix_var is not None:
            config.set(platform_support.CFG_ELITE_PREFIX, self._prefix_var.get().strip())
        self.reload_config()
        if self._toggle_btn is not None:
            panelkit.apply_toggle_button_state(self._toggle_btn, self.config.enabled, self._toggle_off_colors)


controller = AutoHonkController()


def handle_event(entry: Dict[str, Any], cmdr: str, system: Optional[str], station: Optional[str], state: Dict[str, Any]) -> None:
    controller.handle_event(entry, cmdr, system, station, state)


def build_panel(parent: tk.Frame) -> None:
    controller.build_panel(parent)


def build_settings(notebook: nb.Notebook) -> None:
    controller.build_settings(notebook)


def save_settings() -> None:
    controller.save_settings()
