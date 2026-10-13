"""Opens the real Materials window and Field Ops row (plugin/materials_window.py, plugin/materials_panel.py) with EDMC stubbed, and checks that the
row follows the login list and the events, shows what is at the limit, that the window filters and sorts, follows a commander change, and that
nothing shown can widen the panel. Run by test_materials_smoke.py in a subprocess so the stand-ins never leak into other tests. Exits 0 if
everything holds, 1 if not, 77 if Tk is unavailable."""
import os
import sys
import tempfile
import types
from unittest import mock

repo = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, repo)
import tkinter as tk


class Any(types.ModuleType):
    def __getattr__(self, n):
        if n.startswith("__"):
            raise AttributeError(n)
        return mock.MagicMock()


for n in ("monitor", "plug", "EDMCLogging", "l10n", "killswitch", "requests", "win32api", "win32con", "win32gui",
          "win32process", "win32clipboard", "pywintypes", "psutil", "ttkHyperlinkLabel"):
    sys.modules[n] = Any(n)
nbmod = Any("myNotebook")
nbmod.Frame, nbmod.Label, nbmod.Button, nbmod.Checkbutton = tk.Frame, tk.Label, tk.Button, tk.Checkbutton
sys.modules["myNotebook"] = nbmod
theme = Any("theme")
theme.theme = mock.MagicMock()
theme.theme.active = None
theme.theme.THEME_DEFAULT = 0
sys.modules["theme"] = theme
saved = {}


class Cfg:
    default_journal_dir = ""

    def get_str(self, key, default=""):
        return saved.get(key, default) or ""

    def get_bool(self, key, default=False):
        return saved.get(key, default)

    def get_int(self, key, default=0):
        return saved.get(key, default)

    def get(self, key, default=None):
        return saved.get(key, default)

    def set(self, key, value):
        saved[key] = value


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
root.withdraw()

from plugin import materials, materials_panel, materials_window  # noqa: E402

problems = []


def check(condition, message):
    if not condition:
        problems.append(message)


def pump():
    root.update_idletasks()
    root.update()


folder = tempfile.mkdtemp()
panel = materials_panel.MaterialsController()      # a fresh controller; it listens to the shared book
book = materials_panel.book
book.load(folder)

saved["wntb_materials_collapsed"] = False          # open, so its widgets count towards the panel's width
host = tk.Frame(root)
host.pack()
panel.build_panel(host)
pump()
check(panel.summary()[0] == "Log in to see your materials.", f"before a commander: {panel.summary()}")

panel.handle_event({"event": "LoadGame"}, "Bocheaux", "Sol", None, {})
check(panel.summary()[0].startswith("No materials yet"), f"a commander with nothing: {panel.summary()}")

login = {"event": "Materials",
         "Raw": [{"Name": "iron", "Count": 300}, {"Name": "tin", "Count": 12}, {"Name": "carbon", "Count": 120}],
         "Manufactured": [{"Name": "gridresistors", "Count": 40}], "Encoded": [{"Name": "legacyfirmware", "Count": 7}]}
panel.handle_event(login, "Bocheaux", "Sol", None, {})
text, suffix = panel.summary()
check(text.splitlines()[0] == "Raw 432 · Manufactured 40 · Encoded 7", f"the totals line: {text!r}")
check("At the limit: Iron" in text, f"iron is at its limit: {text!r}")
check(suffix == "- 479 held", f"the folded title says how many: {suffix!r}")
check(panel._summary_var.get() == text, "the label follows the summary")

panel.handle_event({"event": "MaterialCollected", "Category": "Raw", "Name": "carbon", "Count": 3}, "Bocheaux", "Sol", None, {})
check("Last: +3 Carbon (now 123)" in panel.summary()[0], f"the last change: {panel.summary()[0]!r}")
panel.handle_event({"event": "MaterialDiscarded", "Category": "Raw", "Name": "carbon", "Count": 23}, "Bocheaux", "Sol", None, {})
check("Last: -23 Carbon (now 100)" in panel.summary()[0], f"a discard: {panel.summary()[0]!r}")

# The row never gets wider because of what is held or named.
for n in range(8):
    book.apply_event({"event": "MaterialCollected", "Category": "Raw", "Name": f"mat{n}", "Name_Localised": "M" * 60, "Count": 1})
book.apply_event({"event": "Materials", "Raw": [{"Name": k, "Count": 300} for k in ("iron", "carbon", "lead", "nickel", "phosphorus", "rhenium", "sulphur")],
                  "Manufactured": [], "Encoded": []})
pump()
text = panel.summary()[0]
check("and 4 more" in text, f"only a few names, then a count: {text!r}")
check(host.winfo_reqwidth() <= 216, f"the open Materials section asks for {host.winfo_reqwidth()} px, wider than the main panel")

# --- the window ---------------------------------------------------------------------------------------------------------------------------
book.apply_event(login)
materials_window.show(root, book)
win = materials_window._window
pump()
check(win is not None and win.alive, "the window opens")
check(len(win._table) == 5, f"every held material is listed: {len(win._table)}")

win._query.set("grid")
pump()
check(len(win._table) == 1, f"search narrows the table: {len(win._table)}")
win._query.set("")
win._kind.set("Raw")
win._fill()
check(len(win._table) == 3, f"the type filter: {len(win._table)}")
win._kind.set("All")
win._grade.set("1")
win._fill()
check(len(win._table) == 4 and all(r[2] == 1 for r in materials_window.rows_for(book, grade="1")), f"the grade filter: {len(win._table)}")
win._grade.set("All")
win._full_only.set(True)
win._fill()
check(len(win._table) == 1, f"only what is at the limit: {len(win._table)}")
win._full_only.set(False)
win._fill()
win._table.sort_by("held")
check(len(win._table) == 5, "sorting keeps every row")

panel.handle_event({"event": "LoadGame"}, "Other Cmdr", "Sol", None, {})
pump()
check(len(win._table) == 0 and "Other Cmdr" in win._shell._subtitle.cget("text"), "another commander's window starts empty")
listeners = len(book._listeners)
materials_window.close()
pump()
check(not win.alive and len(book._listeners) == listeners - 1, "closing the window removes its listener")
materials_window.show(root, book)
pump()
check(materials_window._window.alive and materials_window._window is not win, "it can be opened again")
materials_window.close()

panel.stop()
check(sorted(os.listdir(folder)) == [materials.STATE_FILENAME], f"one data file, no commander name in a file name: {os.listdir(folder)}")

if problems:
    print("PROBLEMS:", len(problems))
    for line in problems:
        print(" -", line)
    sys.exit(1)
print("MATERIALS OK")
