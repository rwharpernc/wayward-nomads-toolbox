"""Opens the real Expedition row (plugin/expedition_panel.py) with EDMC stubbed and feeds it journal-shaped events: the row's lines before and during
an expedition, ticking stops off from jumps, the distance and notes, COPY and copy-on-arrival, a commander change, and that nothing shown can widen
the panel. Run by test_expedition_smoke.py in a subprocess so the stand-ins never leak into other tests. Exits 0 if everything holds, 1 if not, 77
if Tk is unavailable."""
import json
import os
import sys
import tempfile
import time
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

from plugin import expedition, expedition_panel, expedition_window  # noqa: E402

problems = []


def check(condition, message):
    if not condition:
        problems.append(message)


def pump():
    root.update_idletasks()
    root.update()


def wait_for(condition, seconds=5.0):
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        pump()
        if condition():
            return True
        time.sleep(0.02)
    return False


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

# --- the window ---------------------------------------------------------------------------------------------------------------------------
book.pause(e.id)
scratch = tempfile.mkdtemp()
csv_path = os.path.join(scratch, "in.csv")
out_path = os.path.join(scratch, "out.csv")
with open(csv_path, "w", encoding="utf-8") as handle:
    handle.write("System,Body,Note\nDelta,Moon,hi\n\nEpsilon\n")
with open(os.path.join(scratch, "NavRoute.json"), "w", encoding="utf-8") as handle:
    json.dump({"Route": [{"StarSystem": "Sol", "StarPos": [0, 0, 0]}, {"StarSystem": "Alpha", "StarPos": [10, 0, 0]},
                         {"StarSystem": "Beta", "StarPos": [1, 0, 0]}, {"StarSystem": "Gamma"}]}, handle)
asked = []


def fake_lookup(names):
    asked.append(list(names))
    return {"Gamma": (5.0, 0.0, 0.0), "Delta": (2.0, 0.0, 0.0)}


expedition_window.ask_open_path = lambda **kw: csv_path
expedition_window.ask_save_path = lambda **kw: out_path
expedition_window.lookup_coords = fake_lookup
expedition_window.journal_folder = lambda: scratch

expedition_window.show(root, book, panel)
win = expedition_window._window
pump()
check(win is not None and win.alive, "the window opens")
check(win._choice.get().startswith("EEEE") and win._picked == e.id, f"the picker shows the running expedition: {win._choice.get()!r}")
status = lambda: win._shell._status.cget("text")   # noqa: E731

win._name.set("   ")
win._new()
check("needs a name" in status(), f"an empty name is refused: {status()!r}")
win._name.set("Trip")
win._new()
trip = book.get(win._picked)
check(trip is not None and trip.name == "Trip" and trip.status == expedition.PLANNED, "New makes an expedition and picks it")
win._name.set("trip")
win._new()
check("already" in status(), f"a repeated name is refused: {status()!r}")
win._start()
check("at least one stop" in status() and book.active() is None, f"starting with no stops is refused: {status()!r}")

win._system.set("")
win._add_stop()
check("needs a system" in status(), f"a stop needs a system: {status()!r}")
win._system.set("Sol")
win._body_var.set("Earth")
win._note.set("start")
win._add_stop()
check([x.system for x in trip.stops] == ["Sol"] and (trip.stops[0].body, trip.stops[0].note) == ("Earth", "start"), "Add stop")
check(win._system.get() == "" and win._note.get() == "", "and the editor is cleared")
win._fill_here()
check(win._system.get() == panel.system() != "", f"Here fills in the system you are in: {win._system.get()!r}")
win._add_stop()
check(len(trip.stops) == 2 and trip.stops[1].system == panel.system(), "a second stop")

win._start()
check(book.active() is trip and "running" in status(), f"Start: {status()!r}")
check("0 of 2 stops" in win._stats.cget("text") and "Active" in win._stats.cget("text"), f"the stats line: {win._stats.cget('text')!r}")
panel.handle_event(jump("Sol", (0.0, 0.0, 0.0), 5.0), "Bocheaux", "Sol", None, {})
pump()
check(trip.stops[0].is_visited and "1 of 2 stops" in win._stats.cget("text"), "an arrival ticks the stop in the open window")
check(len(win._table) == 2, f"the table lists the stops: {len(win._table)}")

# editing a stop
win._table.select(trip.stops[1].id, notify=True)
check(win._system.get() == trip.stops[1].system, "selecting a stop loads it into the editor")
win._note.set("watch the fuel")
win._save_stop()
check(trip.stops[1].note == "watch the fuel", "Save changes")
win._move(-1)
check(trip.stops[0].note == "watch the fuel", "Up moves it")
win._move(-1)
check("at the end" in status(), "and says so at the top")
win._move(1)
win._toggle_visited()
check(trip.stops[1].is_visited is True, "Mark visited ticks the selected stop (back at second place)")
win._toggle_visited()
check(trip.stops[1].is_visited is False, "and doing it again takes the tick away")
win._remove_stop()
check(len(trip.stops) == 2 and "again" in status(), "the first press of Remove only asks")
win._remove_stop()
check(len(trip.stops) == 1, "the second press removes the stop")
win._add_stop()                                                  # the editor still holds the removed stop's system
check(len(trip.stops) == 2, "a stop can be added back")

# import
win._from_route()
check(len(trip.stops) == 5 and "Added 3" in status(), f"the plotted route adds its systems minus where you are: {status()!r} ({len(trip.stops)})")
check(next(x for x in trip.stops if x.system == "Alpha").xyz == (10.0, 0.0, 0.0), "with their positions")
win._import_csv()
check(len(trip.stops) == 7 and "Added 2" in status(), f"the CSV adds its rows: {status()!r}")
check(next(x for x in trip.stops if x.system == "Delta").body == "Moon", "with the body column")

# locate and reorder
panel.handle_event(jump("Sol", (0.0, 0.0, 0.0), 1.0), "Bocheaux", "Sol", None, {})
win._locate()
check(wait_for(lambda: not win._busy), "the lookup finishes")
pump()
check(len(asked) == 1 and sorted(asked[0]) == ["Delta", "Elsewhere", "Epsilon", "Gamma"], f"EDSM was asked only for the unvisited stops with no position: {asked}")
check([x.system for x in trip.stops] == ["Sol", "Beta", "Delta", "Gamma", "Alpha", "Elsewhere", "Epsilon"],
      f"visited first, then nearest first, then the ones with no position in their old order: {[x.system for x in trip.stops]}")
check("located 2 of" in status() and "Reordered 4" in status(), f"the result is reported: {status()!r}")

# share
win._copy_list()
check(root.clipboard_get().startswith("Trip (active): "), f"Copy list: {root.clipboard_get()[:40]!r}")
win._export_csv()
with open(out_path, encoding="utf-8") as handle:
    exported = handle.read()
check(exported.startswith("system,body,note,visited\n") and "Delta,Moon,hi," in exported, f"Export CSV: {exported[:60]!r}")
win._copy_next()
check(root.clipboard_get() == panel.next_system() != "", f"Copy next: {root.clipboard_get()!r}")

# finish, reset and delete ask twice
win._finish()
check(trip.status == expedition.DONE, "Finish")
win._reset()
check(trip.status == expedition.DONE and "again" in status(), "the first press of Reset only asks")
win._reset()
check(trip.status == expedition.PLANNED and trip.visited_count == 0 and len(trip.stops) == 7, "the second press resets, keeping the stops")
win._delete()
check(book.get(trip.id) is not None, "the first press of Delete only asks")
win._delete()
check(book.get(trip.id) is None, "the second press deletes it")

listeners = len(book._listeners)
expedition_window.close()
pump()
check(not win.alive and len(book._listeners) == listeners - 1, "closing the window removes its listener")
expedition_window.show(root, book, panel)
pump()
check(expedition_window._window.alive and expedition_window._window is not win, "it can be opened again")
expedition_window.close()
book.start(e.id)                                   # the first expedition runs again for the checks below

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
