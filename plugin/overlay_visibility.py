"""Hide every WNTB overlay for a while, and show them again: a click on the line in the WNTB panel, a keyboard shortcut (Windows), or the button in Settings.

The switch itself is in `overlay.py` (`set_all_hidden`): it clears what is on screen and stops everything being drawn until shown again, then puts back what was up. Nothing
is saved; overlays are shown whenever EDMC starts. This module adds the ways to flip it. The keyboard shortcut is a system-wide hotkey, so it works while Elite has the
focus; it exists only on Windows (a Linux desktop gives a program no portable way to listen for keys it does not have the focus for, and Wayland gives none), where the
panel line and the Settings button do the same.
"""

from __future__ import annotations

import ctypes
import logging
import os
import sys
import threading
from typing import Dict, List, Optional, Tuple

import tkinter as tk

import myNotebook as nb
from config import appname, config

from . import overlay

plugin_name = os.path.basename(os.path.dirname(__file__))
logger = logging.getLogger(f"{appname}.{plugin_name}")

PANEL_PLACEMENT = None   # Settings-tab-only, no main-panel widget (the panel line is built by `build_panel_line`)

_CFG_HOTKEY = "wntb_overlay_hide_hotkey"
OFF = "Off"
DEFAULT_HOTKEY = "Ctrl+Alt+H"
CHOICES = (OFF, "Ctrl+Alt+H", "Ctrl+Alt+O", "Ctrl+Shift+H", "Ctrl+Shift+O", "Ctrl+Alt+F10", "Ctrl+Alt+F11")

MOD_ALT, MOD_CONTROL, MOD_SHIFT, MOD_NOREPEAT = 0x1, 0x2, 0x4, 0x4000
WM_HOTKEY, WM_QUIT = 0x0312, 0x0012
_MODS = {"ctrl": MOD_CONTROL, "alt": MOD_ALT, "shift": MOD_SHIFT}


def hotkey_supported() -> bool:
    return sys.platform == "win32"


def parse_combo(text: str) -> Optional[Tuple[int, int]]:
    """(modifiers, virtual key) for a choice such as "Ctrl+Alt+H" or "Ctrl+Alt+F10"; None for Off or anything not recognized."""
    parts = [part.strip() for part in (text or "").split("+") if part.strip()]
    if len(parts) < 2 or text == OFF:
        return None
    mods = 0
    for part in parts[:-1]:
        mod = _MODS.get(part.lower())
        if mod is None:
            return None
        mods |= mod
    key = parts[-1].upper()
    if len(key) == 1 and key.isalnum():
        return mods, ord(key)
    if key.startswith("F") and key[1:].isdigit() and 1 <= int(key[1:]) <= 24:
        return mods, 0x6F + int(key[1:])                 # VK_F1 is 0x70
    return None


def saved_hotkey() -> str:
    raw = config.get_str(_CFG_HOTKEY)
    return raw if raw in CHOICES else (DEFAULT_HOTKEY if raw in (None, "") else OFF)


# --- the global hotkey (Windows) ---------------------------------------------------------------------------------------

_thread: Optional[threading.Thread] = None
_thread_id = 0
_registered = ""          # the combination the thread holds, or ""


def _listen(combo: Tuple[int, int], ready: threading.Event, outcome: Dict[str, object]) -> None:
    user32, kernel32 = ctypes.windll.user32, ctypes.windll.kernel32
    outcome["thread_id"] = kernel32.GetCurrentThreadId()
    outcome["ok"] = bool(user32.RegisterHotKey(None, 1, combo[0] | MOD_NOREPEAT, combo[1]))
    ready.set()
    if not outcome["ok"]:
        return
    msg = ctypes.wintypes.MSG()
    try:
        while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
            if msg.message == WM_HOTKEY:
                try:
                    overlay.toggle_all_hidden()
                except Exception:
                    logger.debug("Hiding the overlays from the hotkey failed", exc_info=True)
    finally:
        user32.UnregisterHotKey(None, 1)


def stop_hotkey() -> None:
    global _thread, _thread_id, _registered
    if _thread is not None and _thread_id:
        try:
            ctypes.windll.user32.PostThreadMessageW(_thread_id, WM_QUIT, 0, 0)
        except Exception:
            logger.debug("Could not stop the hotkey thread", exc_info=True)
        _thread.join(timeout=1.0)
    _thread, _thread_id, _registered = None, 0, ""


def start_hotkey(choice: Optional[str] = None) -> str:
    """Registers the saved (or given) shortcut; returns "" when it is on, or why it is not (Off, not Windows, or another program holds that combination)."""
    global _thread, _thread_id, _registered
    choice = saved_hotkey() if choice is None else choice
    if not hotkey_supported():
        return "The keyboard shortcut is available on Windows only."
    combo = parse_combo(choice)
    stop_hotkey()
    if combo is None:
        return ""
    import ctypes.wintypes  # noqa: F401  (the MSG type)
    ready, outcome = threading.Event(), {}
    thread = threading.Thread(target=_listen, args=(combo, ready, outcome), name="WNTB-hide-hotkey", daemon=True)
    thread.start()
    ready.wait(2.0)
    if not outcome.get("ok"):
        return f"{choice} could not be taken: another program is using that combination."
    _thread, _thread_id, _registered = thread, int(outcome.get("thread_id", 0)), choice
    return ""


# --- the panel line ----------------------------------------------------------------------------------------------------

def panel_text(hidden: bool) -> str:
    return "Overlays are hidden (click to show)" if hidden else "Overlays shown (click to hide)"


_labels: List[tk.Label] = []


def build_panel_line(parent: tk.Misc, row: int) -> tk.Label:
    """A line in the WNTB panel that says whether the overlays are hidden and flips it when clicked."""
    from . import panelkit
    label = panelkit.wrap_label(parent, anchor="w", cursor="hand2")
    label.grid(row=row, column=0, columnspan=3, sticky=tk.W)
    label.configure(text=panel_text(overlay.all_hidden()))
    label.bind("<Button-1>", lambda _e: overlay.toggle_all_hidden())
    panelkit.add_tooltip(label, "Hides every WNTB overlay until you click again (Settings → Overlays → Hide overlays has a keyboard shortcut)")
    _labels.append(label)
    return label


def _on_change(hidden: bool) -> None:
    for label in list(_labels):
        try:
            label.after(0, lambda lab=label: lab.configure(text=panel_text(hidden)))
        except (tk.TclError, RuntimeError):
            _labels.remove(label)


overlay.on_visibility_change(_on_change)


# --- Settings tab ------------------------------------------------------------------------------------------------------

_hotkey_var: Optional[tk.StringVar] = None
_result_var: Optional[tk.StringVar] = None


def build_settings(notebook: tk.Misc) -> None:
    global _hotkey_var, _result_var
    frame = nb.Frame(notebook)
    frame.columnconfigure(0, weight=1)
    notebook.add(frame, text="Hide overlays")
    nb.Label(
        frame,
        text=("Hides every WNTB overlay at once, for example to take a clean screenshot or to look at the game without cards over it, and shows them again where they "
              "were. Click the Overlays line in the WNTB panel, press the keyboard shortcut below, or use the button. The overlays are always shown when EDMC "
              "starts. This hides WNTB's overlays only; another plugin's overlay is unaffected."),
        wraplength=440, justify=tk.LEFT,
    ).grid(row=0, column=0, sticky=tk.W, padx=10, pady=(10, 8))

    row = tk.Frame(frame)
    row.grid(row=1, column=0, sticky=tk.W, padx=10, pady=2)
    nb.Label(row, text="Keyboard shortcut:").pack(side=tk.LEFT, padx=(0, 8))
    _hotkey_var = tk.StringVar(value=saved_hotkey())
    menu = tk.OptionMenu(row, _hotkey_var, *CHOICES)
    menu.pack(side=tk.LEFT)
    if not hotkey_supported():
        menu.configure(state=tk.DISABLED)
        nb.Label(frame, text=("The shortcut works on Windows only: a Linux desktop gives a program no portable way to hear keys while another window has the focus. On "
                              "Linux use the line in the WNTB panel or the button below."),
                 wraplength=440, justify=tk.LEFT).grid(row=2, column=0, sticky=tk.W, padx=10, pady=(2, 4))
    else:
        nb.Label(frame, text=("The shortcut works while Elite has the focus. Pick one Elite and your other programs do not use; if another program already holds it, "
                              "WNTB says so after you press OK."),
                 wraplength=440, justify=tk.LEFT).grid(row=2, column=0, sticky=tk.W, padx=10, pady=(2, 4))
    buttons = tk.Frame(frame)
    buttons.grid(row=3, column=0, sticky=tk.W, padx=10, pady=(6, 2))
    tk.Button(buttons, text="Hide / show now", command=overlay.toggle_all_hidden).pack(side=tk.LEFT)
    _result_var = tk.StringVar(value="")
    nb.Label(frame, textvariable=_result_var, wraplength=440, justify=tk.LEFT).grid(row=4, column=0, sticky=tk.W, padx=10, pady=(2, 10))


def save_settings() -> None:
    if _hotkey_var is None:
        return
    choice = _hotkey_var.get()
    config.set(_CFG_HOTKEY, choice)
    problem = start_hotkey(choice) if hotkey_supported() else ""
    if _result_var is not None:
        _result_var.set(problem)
    if problem:
        logger.warning(problem)


def start(plugin_dir: str) -> None:
    problem = start_hotkey()
    if problem:
        logger.info(problem)


def stop() -> None:
    stop_hotkey()
