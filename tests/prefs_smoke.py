"""Builds the WHOLE WNTB Settings tab (ui.create_prefs) with stand-ins that behave like EDMC's
myNotebook: ttk widgets, and every nb.Frame gets a gridded spacer child (read from EDMC's own
myNotebook.Frame.__init__). That spacer is why packing into an nb.Frame always fails in real EDMC, which
once made the entire WNTB Settings tab disappear. Run by test_prefs_smoke.py in a subprocess so the
stand-ins never leak into other tests. Exits 0 if every tab builds, 1 if any raises, 77 if Tk is unavailable."""
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


class Cfg:
    default_journal_dir = ""
    def get_str(self, key, default=""): return default or ""
    def get_bool(self, key, default=False): return default
    def get_int(self, key, default=0): return default
    def get(self, key, default=None): return default
    def set(self, key, value): pass


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
    outer = ui.create_prefs(root)
    tabs = None
    for child in outer.winfo_children():
        for sub in child.winfo_children():
            if isinstance(sub, ttk.Notebook):
                tabs = sub
    names = [tabs.tab(t, "text") for t in tabs.tabs()] if tabs else []
    print("SETTINGS BUILT OK:", len(names), "tabs:", ", ".join(names))
    code = 0 if names else 1
except Exception as exc:  # noqa: BLE001
    import traceback
    tb = traceback.extract_tb(exc.__traceback__)[-1]
    print("SETTINGS FAILED:", type(exc).__name__, str(exc)[:200], f"(at {tb.filename.split('plugin')[-1]}:{tb.lineno})")
    code = 1
root.destroy()
sys.exit(code)
