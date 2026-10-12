"""Builds the main WNTB panel (ui.create_plugin_app) with stand-ins for EDMC and checks the plugin version line above the
game-mode line: its text for each update state, the orange 'Restart EDMC' colors, and that an update which finished BEFORE the
panel was built still shows once it is. Run by test_version_line_smoke.py in a subprocess so the stand-ins never leak into
other tests. Exits 0 if every check holds, 1 if not, 77 if Tk is unavailable."""
import os
import sys
import types
from unittest import mock

repo = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, repo)
import tkinter as tk
from tkinter import ttk


class Any(types.ModuleType):
    def __getattr__(self, n):
        if n.startswith("__"):
            raise AttributeError(n)
        return mock.MagicMock()


for n in ("monitor", "plug", "EDMCLogging", "l10n", "killswitch", "requests", "win32api", "win32con", "win32gui",
          "win32process", "win32clipboard", "pywintypes", "psutil"):
    sys.modules[n] = Any(n)
theme = Any("theme")
theme.theme = mock.MagicMock()
theme.theme.active = None
theme.theme.THEME_DEFAULT = 0
sys.modules["theme"] = theme


class HL(ttk.Label):
    def __init__(self, parent, text="", url=None, underline=False, background=None, **kw):
        super().__init__(parent, text=text)


mod = types.ModuleType("ttkHyperlinkLabel")
mod.HyperlinkLabel = HL
sys.modules["ttkHyperlinkLabel"] = mod


class Frame(ttk.Frame):
    """EDMC's nb.Frame: a ttk.Frame that puts a gridded spacer child inside itself."""
    def __init__(self, master=None, **kw):
        super().__init__(master, **kw)
        ttk.Frame(self).grid(pady=5)


nbmod = types.ModuleType("myNotebook")
nbmod.Frame = Frame
nbmod.Label = ttk.Label
nbmod.Button = ttk.Button
nbmod.Checkbutton = ttk.Checkbutton
nbmod.Radiobutton = ttk.Radiobutton
nbmod.EntryMenu = ttk.Entry
nbmod.Entry = ttk.Entry
nbmod.OptionMenu = ttk.OptionMenu
nbmod.Notebook = ttk.Notebook
sys.modules["myNotebook"] = nbmod


SAVED = {}


class Cfg:
    default_journal_dir = ""
    def get_str(self, key, default=""): return default or ""
    def get_bool(self, key, default=False): return default
    def get_int(self, key, default=0): return default
    def get(self, key, default=None): return default
    def set(self, key, value): SAVED[key] = value


cfgmod = types.ModuleType("config")
cfgmod.appname = "EDMarketConnector"
cfgmod.config = Cfg()
cfgmod.user_agent = "WNTB-test"
cfgmod.appversion = lambda: "5.13.0"
sys.modules["config"] = cfgmod

try:
    root = tk.Tk()
except tk.TclError:
    print("no display available")
    sys.exit(77)
from plugin import ui

try:
    parent = tk.Frame(root)
    ui.set_update_downloaded("9.9.9")              # the update finished before the panel existed
    frame = ui.create_plugin_app(parent)
    label = ui._version_label
    root.update_idletasks()
    problems = []

    def check(ok, what):
        if not ok:
            problems.append(what)

    check(label["text"] == "v9.9.9 download - Restart EDMC", f"early update text: {label['text']!r}")
    check(str(label.cget("background")).lower() == ui._ATTENTION_BG, "restart line is not orange")
    check(str(label.cget("foreground")).lower() == ui._ATTENTION_FG, "restart line is not black")
    check(label.grid_info()["row"] == 0, "version line is not the first line of the session strip")
    from plugin import game_mode
    check(game_mode.tracker._label.grid_info()["row"] == 1, "game mode is not directly under the version line")
    ui._set_version_state("idle", "")
    check(label["text"] == "Plugin: v" + ui.__version__, f"idle text: {label['text']!r}")
    check(str(label.cget("background")).lower() != ui._ATTENTION_BG, "orange left behind after going idle")
    ui.set_update_downloading("9.9.9")
    check("downloading v9.9.9" in label["text"] and label["text"].startswith("Plugin: v"), f"downloading text: {label['text']!r}")
    ui.set_update_applied(ui.__version__)
    check(label["text"] == f"Plugin: v{ui.__version__} (updated)", f"updated text: {label['text']!r}")
    print("VERSION LINE:", "OK" if not problems else "; ".join(problems))
    code = 0 if not problems else 1
except Exception as exc:  # noqa: BLE001
    import traceback
    tb = traceback.extract_tb(exc.__traceback__)[-1]
    print("VERSION LINE FAILED:", type(exc).__name__, str(exc)[:200], f"(at {tb.filename.split('plugin')[-1]}:{tb.lineno})")
    code = 1
root.destroy()
sys.exit(code)
