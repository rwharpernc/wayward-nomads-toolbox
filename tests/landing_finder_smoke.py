"""Opens the real Nearest place to land window and its Exploration panel row (plugin/landing_finder_window.py, plugin/landing_finder_panel.py) with EDMC stubbed: the row follows the
journal, the window refuses to look until the box is ticked, passes the choices on, lists stations and carriers, copies a system name and explains an empty answer and a failure. Run
by test_landing_finder_smoke.py in a subprocess so the stand-ins never leak into other tests. Exits 0 if everything holds, 1 if not, 77 if Tk is unavailable."""
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

from plugin import landing_finder as LF, landing_finder_panel as panel_mod, landing_finder_window as win  # noqa: E402

problems = []


def check(condition, message):
    if not condition:
        problems.append(message)


def wait_for(condition, seconds=5.0):
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        root.update_idletasks()
        root.update()
        if condition():
            return True
        time.sleep(0.02)
    return False


def pump():
    root.update_idletasks()
    root.update()


saved["wntb_landing_finder_collapsed"] = False
host = tk.Frame(root)
host.pack()
controller = panel_mod.FinderController()
controller.build_panel(host)
pump()
check("Needs your position" in controller._summary.get(), f"before a position: {controller._summary.get()!r}")
controller.handle_event({"event": "Loadout", "Ship": "python"}, "CMDR", "Sol", None, {})
controller.handle_event({"event": "FSDJump", "StarSystem": "Deep A", "StarPos": [1.5, 2.5, 3.5]}, "CMDR", "Deep A", None, {})
check(controller.position() == (1.5, 2.5, 3.5) and controller.system() == "Deep A" and controller.ship() == "python", "the controller follows the journal")
check("Deep A" in controller._summary.get() and "medium pad" in controller._summary.get(), f"the row says where and what pad: {controller._summary.get()!r}")

asked = []
outcome = {"mode": "ok"}


def fake_find(position, pad, services, carriers, days):
    asked.append((position, pad, tuple(services), carriers, days))
    if outcome["mode"] == "fail":
        raise OSError("no network")
    if outcome["mode"] == "refuse":
        raise ValueError("Your position is not known yet. Jump or log in first.")
    stations = () if outcome["mode"] == "empty" else (
        LF.Place("Anchorage", "Far Sys", "Ocellus Starport", False, False, 2707.0, 5012.0, 13, 14, 7, ("Refuel", "Repair"), "2026-10-16T00:00:00Z"),)
    carriers_ = () if outcome["mode"] == "empty" or not carriers else (
        LF.Place("T5M-BVZ", "Carrier Sys", LF.CARRIER_TYPE, True, False, 913.0, 0.0, 4, 4, 8, ("Refuel", "Repair"), "2026-10-15T00:00:00Z", "All"),)
    return LF.Result(position, pad, tuple(services), days, stations, carriers_, carriers)


win.find_places = fake_find
win.show(root, controller)
pump()
w = win._window
check(w is not None and w.alive, "the window opens")
check("Deep A" in w._from.cget("text") and "(1.5, 2.5, 3.5)" in w._from.cget("text"), f"it says where it searches from: {w._from.cget('text')!r}")
check("medium pad" in w._shell._subtitle.cget("text") if hasattr(w._shell, "_subtitle") else True, "it says the pad the ship needs")

w._find()
pump()
check(asked == [] and "Tick the box" in w._shell._status.cget("text"), f"nothing is sent until the box is ticked: {asked} {w._shell._status.cget('text')!r}")
w._allowed.set(True)
w._find()
check(wait_for(lambda: not w._busy), "the lookup finishes")
pump()
check(asked == [((1.5, 2.5, 3.5), "medium", ("Refuel", "Repair"), True, 14)], f"the position, the ship's pad and the defaults are sent: {asked}")
check(len(w._stations) == 1 and len(w._carrier_table) == 1, f"stations and carriers are listed: {len(w._stations)} {len(w._carrier_table)}")
check("medium pad or larger" in w._station_heading.cget("text"), f"the heading names the pad: {w._station_heading.cget('text')!r}")
check("1 station(s) and 1 carrier(s)" in w._shell._status.cget("text") and "2,707" in w._shell._status.cget("text"), f"the status: {w._shell._status.cget('text')!r}")
w._copy_system("s0")
check(root.clipboard_get() == "Far Sys", f"double-click copies a station's system: {root.clipboard_get()!r}")
w._copy_system("c0")
check(root.clipboard_get() == "Carrier Sys", "and a carrier's")
check(saved.get("wntb_landing_finder_allowed") is True, "ticking the box is remembered")

w._service_vars["Refuel"].set(False)
w._service_vars["Outfitting"].set(True)
w._pad.set("Large only")
w._carriers.set(False)
w._fresh.set("30 days")
w._find()
check(wait_for(lambda: not w._busy), "a second lookup finishes")
check(asked[-1] == ((1.5, 2.5, 3.5), "large", ("Repair", "Outfitting"), False, 30), f"the choices are passed on: {asked[-1]}")
check(len(w._carrier_table) == 0 and "not asked for" in w._carrier_heading.cget("text"), "carriers left out say so")

outcome["mode"] = "empty"
w._find()
check(wait_for(lambda: not w._busy) and "Nothing found" in w._shell._status.cget("text") and len(w._stations) == 0, f"an empty answer says so: {w._shell._status.cget('text')!r}")
outcome["mode"] = "fail"
w._find()
check(wait_for(lambda: not w._busy) and "could not be reached" in w._shell._status.cget("text"), f"a failure is explained: {w._shell._status.cget('text')!r}")
outcome["mode"] = "refuse"
w._find()
check(wait_for(lambda: not w._busy) and "position is not known" in w._shell._status.cget("text"), "a refusal shows its message")
outcome["mode"] = "ok"

controller.tracker.reset()
before = len(asked)
w._find()
pump()
check(len(asked) == before and "position is not known" in w._shell._status.cget("text"), "without a position nothing is sent")

win.close()
pump()
check(not w.alive, "the window closes")

if problems:
    print("PROBLEMS:" + chr(10) + chr(10).join(problems))
    sys.exit(1)
print("LANDING FINDER OK")
