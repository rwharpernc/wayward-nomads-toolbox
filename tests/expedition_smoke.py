"""Opens the real Expedition row (plugin/expedition_panel.py) with EDMC stubbed and feeds it journal-shaped events: the row's lines before and during
an expedition, ticking stops off from jumps, the distance and notes, COPY and copy-on-arrival, a commander change, and that nothing shown can widen
the panel. Run by test_expedition_smoke.py in a subprocess so the stand-ins never leak into other tests. Exits 0 if everything holds, 1 if not, 77
if Tk is unavailable."""
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

from plugin import expedition, expedition_panel  # noqa: E402

problems = []


def check(condition, message):
    if not condition:
        problems.append(message)


def pump():
    root.update_idletasks()
    root.update()


def jump(system, pos, dist, stamp="2026-10-14T01:00:00Z"):
    return {"event": "FSDJump", "StarSystem": system, "StarPos": list(pos), "JumpDist": dist, "timestamp": stamp}


folder = tempfile.mkdtemp()
panel = expedition_panel.ExpeditionController()      # a fresh controller; it listens to the shared book
book = expedition_panel.book
book.load(folder)

saved["wntb_expedition_collapsed"] = False           # open, so its widgets count towards the panel's width
host = tk.Frame(root)
host.pack()
panel.build_panel(host)
pump()
check(panel.summary()[0] == "Log in to use expeditions.", f"before a commander: {panel.summary()}")

panel.handle_event({"event": "LoadGame"}, "Bocheaux", "Sol", None, {})
check(panel.summary()[0] == "No expedition yet.", f"a commander with none: {panel.summary()}")

e = book.create("Colonia run")
book.add_stop(e.id, "Sol", "Earth", "Wave goodbye", xyz=(0.0, 0.0, 0.0))
book.add_stop(e.id, "Sagittarius A*", xyz=(25.2, -20.9, 25899.97))
book.add_stop(e.id, "Colonia", note="Say hello to the Council")
check(panel.summary()[0] == "No expedition running (1 saved).", f"saved but not started: {panel.summary()}")

book.start(e.id)
text, suffix = panel.summary()
lines = text.splitlines()
check(lines[0] == "Colonia run: 0 of 3 stops", f"the first line: {lines[0]!r}")
check(lines[1].startswith("0 jumps · 0 ly"), f"the stats line: {lines[1]!r}")
check(lines[2] == "Next: Sol / Earth" and lines[3] == "Note: Wave goodbye", f"the next stop and its note: {lines[2:4]}")
check(suffix == "- 0/3", f"the folded title: {suffix!r}")
check(panel._summary_var.get() == text, "the label follows the summary")

# a jump to a system that is not a stop counts but ticks nothing
panel.handle_event(jump("Elsewhere", (100.0, 0.0, 0.0), 40.5), "Bocheaux", "Elsewhere", None, {})
lines = panel.summary()[0].splitlines()
check("1 jumps · 40 ly" in lines[1] or "1 jumps · 41 ly" in lines[1], f"a jump is counted: {lines[1]!r}")
check(lines[0].endswith("0 of 3 stops"), "and ticks nothing")

# the distance to the next stop comes from the last position
panel.handle_event(jump("Elsewhere 2", (3.0, 4.0, 0.0), 5.0), "Bocheaux", "Elsewhere 2", None, {})
check("Next: Sol / Earth (5 ly)" in panel.summary()[0], f"a straight-line distance: {panel.summary()[0]!r}")

# reaching a stop ticks it and shows its note; the next one has no position, so no distance
panel.handle_event(jump("Sol", (0.0, 0.0, 0.0), 5.0), "Bocheaux", "Sol", None, {})
text = panel.summary()[0]
check(text.splitlines()[0].endswith("1 of 3 stops"), f"a stop is ticked: {text.splitlines()[0]!r}")
check("Reached stop 1: Sol. Wave goodbye" in text, f"and its note shown: {text!r}")
check("Next: Sagittarius A* (25,900 ly)" in text, f"the next stop's distance: {text!r}")

# a Location at login in a stop ticks it without counting a jump
before = e.jumps
panel.handle_event({"event": "Location", "StarSystem": "Colonia", "StarPos": [-9530.5, -910.28, 19808.1], "timestamp": "2026-10-14T02:00:00Z"},
                   "Bocheaux", "Colonia", None, {})
check(e.jumps == before and e.visited_count == 2, f"a login in a stop ticks it, no jump: jumps {e.jumps}, visited {e.visited_count}")

# the last stop
panel.handle_event(jump("Sagittarius A*", (25.2, -20.9, 25899.97), 100.0), "Bocheaux", "Sagittarius A*", None, {})
text = panel.summary()[0]
check("All stops visited" in text and "That was the last stop." in text, f"the last stop says so: {text!r}")

# COPY and copy-on-arrival
book.reset(e.id)
book.start(e.id)
panel.handle_event({"event": "Music"}, "Bocheaux", "Sol", None, {})
check(panel.next_system() == "Sol", f"the next system: {panel.next_system()!r}")
check(panel.copy_next(), "COPY works")
check(root.clipboard_get() == "Sol", f"the clipboard holds the next stop: {root.clipboard_get()!r}")
saved["wntb_expedition_autocopy"] = True
panel.handle_event(jump("Sol", (0.0, 0.0, 0.0), 5.0), "Bocheaux", "Sol", None, {})
check(root.clipboard_get() == "Sagittarius A*", f"copy on arrival puts the next stop on the clipboard: {root.clipboard_get()!r}")
saved["wntb_expedition_autocopy"] = False
panel.handle_event(jump("Elsewhere", (1.0, 1.0, 1.0), 5.0), "Bocheaux", "Elsewhere", None, {})
check(root.clipboard_get() == "Sagittarius A*", "and with it off the clipboard is left alone")
book.pause(e.id)
check(not panel.copy_next(), "COPY with nothing running does nothing")

# a very long name, note and system never widen the row
book.reset(e.id)
book.update_stop(e.id, e.stops[0].id, "S" * 100, "B" * 100, "N" * 500)
book.rename(e.id, "E" * 80)
book.start(e.id)
panel.handle_event(jump("Elsewhere", (1.0, 1.0, 1.0), 5.0), "Bocheaux", "Elsewhere", None, {})
pump()
text = panel.summary()[0]
check(all(len(line) <= 160 for line in text.splitlines()), f"every line stays short: {[len(l) for l in text.splitlines()]}")
check("S" * 50 not in text and "N" * 120 not in text and "E" * 40 not in text, "long names and notes are clipped")
check(host.winfo_reqwidth() <= 216, f"the open Expedition section asks for {host.winfo_reqwidth()} px, wider than the main panel")

# another commander sees none; the first is back after
panel.handle_event({"event": "LoadGame"}, "Other Cmdr", "Sol", None, {})
check(panel.summary()[0] == "No expedition yet.", f"another commander has none: {panel.summary()}")
panel.handle_event({"event": "LoadGame"}, "BOCHEAUX", "Sol", None, {})
check(panel.summary()[0].startswith("EEEE"), f"the first commander's expedition is back: {panel.summary()[0]!r}")

panel.stop()
check(sorted(os.listdir(folder)) == [expedition.STATE_FILENAME], f"one data file, no commander name in a file name: {os.listdir(folder)}")

if problems:
    print("PROBLEMS:", len(problems))
    for line in problems:
        print(" -", line)
    sys.exit(1)
print("EXPEDITION OK")
