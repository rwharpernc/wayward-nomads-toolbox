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
saved["wntb_expedition_lookup_names"] = False        # the EDSM name check is tested on its own below
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
# adding a stop with only a system, before any expedition exists, makes one rather than asking for a separate step
expedition_window.show(root, book, panel)
pump()
fresh = expedition_window._window
fresh._system.set("Colonia")
fresh._add_stop()
pump()
made = book.expeditions()
check(len(made) == 1 and made[0].name == "My expedition" and [x.system for x in made[0].stops] == ["Colonia"],
      f"a system alone adds a stop, and makes the expedition: {[(x.name, [y.system for y in x.stops]) for x in made]}")
check(fresh._picked == made[0].id and fresh._system.get() == "", "the new expedition is picked and the editor cleared")
fresh._system.set("Sol")
fresh._add_stop()
check(len(book.expeditions()) == 1 and len(made[0].stops) == 2, "the second stop goes into the same expedition")
fresh._rename()
check(fresh._name.get() == "My expedition" and "Rename again" in fresh._shell._status.cget("text"), "Rename with an empty Name box offers the current name to edit")
fresh._name.set("Colonia run")
fresh._rename()
check(made[0].name == "Colonia run" and fresh._name.get() == "", f"Rename changes it: {made[0].name!r}")
check("Colonia run" in fresh._choice.get(), f"and the picker shows the new name: {fresh._choice.get()!r}")
fresh._system.set("   ")
fresh._add_stop()
check("needs a system" in fresh._shell._status.cget("text") and len(made[0].stops) == 2, "an empty system is still refused, with a hint")
expedition_window.close()
pump()

# system names are normalized when a stop is added
here = panel.system()
saved["wntb_expedition_lookup_names"] = False
expedition_window.show(root, book, panel)
pump()
names_window = expedition_window._window
names_window._name.set("Names")
names_window._new()
names_window._system.set("  " + here.lower() + "  ")
names_window._add_stop()
named = book.get(names_window._picked)
check(named.stops[-1].system == here, f"the system you are in is spelled the way the game spells it: {named.stops[-1].system!r} for {here!r}")
names_window._system.set("gamma")
names_window._add_stop()
check(named.stops[-1].system == "gamma", "a name nothing knows is kept as typed when the EDSM check is off")
names_window._system.set("GAMMA")
names_window._add_stop()
check(named.stops[-1].system == "gamma" or named.stops[-1].system == "GAMMA", "a repeat is not turned into a different system")
expedition_window.close()
pump()

saved["wntb_expedition_lookup_names"] = True
looked_up = []


def edsm_names(names):
    looked_up.append(list(names))
    return {"Sesuang": (45.7, -3.2, 22.1)} if any(n.casefold() == "sesuang" for n in names) else {}


expedition_window.lookup_coords = edsm_names
expedition_window.show(root, book, panel)
pump()
names_window = expedition_window._window
check(names_window._lookup_var.get(), "the EDSM name check is ticked unless turned off")
names_window._name.set("Names two")
names_window._new()
names_window._system.set("sesuang")
names_window._add_stop()
for _ in range(60):
    pump()
    if book.get(names_window._picked).stops[-1].xyz is not None:
        break
    time.sleep(0.02)
two = book.get(names_window._picked)
check(two.stops[-1].system == "Sesuang" and two.stops[-1].xyz == (45.7, -3.2, 22.1) and looked_up == [["sesuang"]],
      f"EDSM fixes the capitals and gives the position: {two.stops[-1].system!r} {two.stops[-1].xyz} {looked_up}")
check("respelled 1" in names_window._shell._status.cget("text"), f"and says so: {names_window._shell._status.cget('text')!r}")
names_window._system.set("nowhere zz-z a0")
names_window._add_stop()
for _ in range(60):
    pump()
    if "does not know" in names_window._shell._status.cget("text"):
        break
    time.sleep(0.02)
check(two.stops[-1].system == "nowhere zz-z a0" and "does not know nowhere zz-z a0" in names_window._shell._status.cget("text"),
      f"a system EDSM does not know is kept as typed, with a note: {names_window._shell._status.cget('text')!r}")
names_window._lookup_var.set(False)
names_window._system.set("kushen")
names_window._add_stop()
pump()
check(looked_up[-1] != ["kushen"] and two.stops[-1].system == "kushen", "with the box unticked nothing is sent")
expedition_window.lookup_coords = fake_lookup
saved["wntb_expedition_lookup_names"] = False
expedition_window.close()
pump()

# the Spansh planners: the dialog's answer becomes a new expedition
from plugin import expedition_plan_dialog, spansh_planners  # noqa: E402

check(panel.jump_range() is None, "no jump range before a Loadout")
panel.handle_event({"event": "Loadout", "MaxJumpRange": 41.25}, "Other Cmdr", "Sol", None, {})
check(panel.jump_range() == 41.25, f"the Loadout's maximum jump range is kept: {panel.jump_range()}")
asked = []


def fake_plan(query, cancel=None, on_state=None):
    asked.append(query)
    on_state("Waiting in Spansh's queue.")
    return [spansh_planners.PlannedStop("Eme", "Eme A 1", "Eme A 1 (Earth-like world, scan 270.0k cr)", (33.7, 26.2, 4.0)),
            spansh_planners.PlannedStop("Jarnae", "Jarnae A 2", "note", None)] if query.kind == spansh_planners.RICHES else []


expedition_plan_dialog.plan_route = fake_plan
expedition_window.show(root, book, panel)
pump()
planner_window = expedition_window._window
before = len(book.expeditions())
planner_window._plan(spansh_planners.RICHES)
pump()
dialog = planner_window._planner
check(dialog is not None and dialog.alive, "Road to Riches opens its dialog")
check(dialog._vars["start"].get() == panel.system() and dialog._vars["jump_range"].get() == "41.25",
      f"filled in with where you are and your jump range: {dialog._vars['start'].get()!r}, {dialog._vars['jump_range'].get()!r}")
dialog._vars["jump_range"].set("abc")
dialog._plot()
check("should be a number" in dialog._shell._status.cget("text") and not asked, f"a bad number is refused before anything is sent: {dialog._shell._status.cget('text')!r}")
dialog._vars["jump_range"].set("40")
dialog._vars["destination"].set("Colonia")
dialog._flags["use_mapping_value"].set(True)
dialog._plot()
for _ in range(60):
    pump()
    if not dialog.alive:
        break
    time.sleep(0.02)
check(len(asked) == 1 and asked[0].kind == spansh_planners.RICHES and asked[0].jump_range == 40.0 and asked[0].destination == "Colonia"
      and asked[0].use_mapping_value and asked[0].start == panel.system(), f"what was asked: {asked}")
check(not dialog.alive, "the dialog closes when Spansh has answered")
made = [x for x in book.expeditions() if x.name.startswith("Road to Riches from")]
check(len(book.expeditions()) == before + 1 and len(made) == 1 and [x.system for x in made[0].stops] == ["Eme", "Jarnae"]
      and made[0].stops[0].body == "Eme A 1" and made[0].stops[0].xyz == (33.7, 26.2, 4.0), f"a new expedition with the stops: {[(x.name, [y.system for y in x.stops]) for x in made]}")
check(planner_window._picked == made[0].id and "2 stop" in planner_window._shell._status.cget("text"), "it is picked, and the window says what was made")
planner_window._plan(spansh_planners.EXOBIOLOGY)
pump()
dialog = planner_window._planner
dialog._plot()
for _ in range(60):
    pump()
    if not dialog.alive:
        break
    time.sleep(0.02)
check(len(book.expeditions()) == before + 1 and "nothing worth stopping for" in planner_window._shell._status.cget("text"),
      f"no results makes no expedition and says so: {planner_window._shell._status.cget('text')!r}")
planner_window._plan(spansh_planners.RICHES)
pump()
dialog = planner_window._planner
import threading as _threading
release = _threading.Event()


def slow_plan(q, cancel=None, on_state=None):
    on_state("Spansh is calculating the route.")
    release.wait(5)
    raise spansh_planners.RouteSearchError("Spansh says: Could not find system.")


expedition_plan_dialog.plan_route = slow_plan
dialog._plot()
for _ in range(15):
    pump()
    time.sleep(0.05)
shown = dialog._activity.cget("text")
check(dialog._busy and shown.startswith("Plotting") and "waited" in shown and "calculating the route" in shown, f"while Spansh works it says so, with the time: {shown!r}")
check(dialog._plot_button.cget("text") == "Plotting..." and not dialog._plot_button._enabled, "the Plot button shows it is working and cannot be pressed again")
check(len(dialog._bar.find_all()) == 1, "and a block moves along the bar")
release.set()
for _ in range(60):
    pump()
    if not dialog._busy:
        break
    time.sleep(0.02)
check(dialog.alive and "Could not find system" in dialog._activity.cget("text"), f"a refusal stays in the dialog with Spansh's words: {dialog._activity.cget('text')!r}")
check(dialog._plot_button.cget("text") == "Plot" and dialog._plot_button._enabled and not dialog._bar.find_all(), "and the button and bar are back to idle")
dialog.close()
expedition_window.close()
pump()

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
