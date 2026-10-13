"""Exercises the Surface Compass (plugin/surface_compass.py, plugin/surface_marks_window.py) with EDMC stubbed: the maths, what it points
at, making and cycling marks, when the overlay is drawn or cleared, the carry-over of the old Mining waypoint settings, the panel row's
width and the Marks window. Run by test_surface_compass_smoke.py in a subprocess so the stand-ins never leak into other tests. Exits 0 if
everything holds, 1 if not, 77 if Tk is unavailable."""
import os
import sys
import tempfile
import types
from types import SimpleNamespace
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
        value = saved.get(key, default)
        return "" if value is None else str(value) if not isinstance(value, bool) else ("1" if value else "")

    def get_bool(self, key, default=False):
        return bool(saved.get(key, default))

    def get_int(self, key, default=0):
        return default

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

from plugin import mining_hotspots, mining_live_position as LP, mining_surface, overlay_placement as P  # noqa: E402
from plugin import surface_compass as C, surface_marks as M, surface_marks_window as W  # noqa: E402

problems = []


def check(condition, message):
    if not condition:
        problems.append(message)


def pump():
    root.update_idletasks()
    root.update()


class SyncThread:
    """Runs the overlay worker at once, so the test can see what was drawn."""

    def __init__(self, target=None, name=None, daemon=None, **_):
        self._target = target

    def start(self):
        self._target()


C.threading.Thread = SyncThread


class Rec:
    def __init__(self):
        self.shapes, self.messages, self.vectors, self.calls = {}, {}, {}, 0

    def send_message(self, msg_id, text, color, x, y, ttl=8, size="normal"):
        self.calls += 1
        if text:
            self.messages[msg_id] = text
        else:
            self.messages.pop(msg_id, None)

    def send_shape(self, shape_id, shape, color, fill, x, y, w, h, ttl=8, thickness=None):
        self.calls += 1
        if w and h:
            self.shapes[shape_id] = (x, y, w, h)
        else:
            self.shapes.pop(shape_id, None)

    def send_vector(self, shape_id, points, color, ttl=8):
        self.calls += 1
        if len(points) > 1:
            self.vectors[shape_id] = points
        else:
            self.vectors.pop(shape_id, None)


# --- the maths and the choice of target ------------------------------------------------------------------------------------------------
RADIUS = 1_000_000.0      # a 1,000 km body: one degree is about 17.45 km
north = C.read(C.Target("N", 1.0, 0.0, "mark"), 0.0, 0.0, 0.0, RADIUS)
check(abs(north.bearing) < 0.01 and north.compass == "N" and north.relative == 0.0, f"due north, facing north: {north}")
check(abs(north.distance_m - 17453.3) < 5, f"one degree on a 1,000 km body: {north.distance_m}")
east = C.read(C.Target("E", 0.0, 1.0, "mark"), 0.0, 0.0, 0.0, RADIUS)
check(abs(east.bearing - 90) < 0.01 and east.compass == "E" and abs(east.relative - 90) < 0.01, f"due east, facing north: {east}")
behind = C.read(C.Target("S", -1.0, 0.0, "mark"), 0.0, 0.0, 0.0, RADIUS)
check(abs(behind.relative - 180) < 0.01, f"due south, facing north: behind: {behind.relative}")
turned = C.read(C.Target("E", 0.0, 1.0, "mark"), 0.0, 0.0, 90.0, RADIUS)
check(abs(turned.relative) < 0.01, f"due east, facing east: ahead: {turned.relative}")
check(C.read(C.Target("E", 0.0, 1.0, "mark"), 0.0, 0.0, None, RADIUS).relative is None, "no heading: no relative bearing")
check(east.text().startswith("→ E - 17.45km E"), f"overlay text with a heading: {east.text()!r}")
check(C.read(C.Target("E", 0.0, 1.0, "mark"), 0.0, 0.0, None, RADIUS).text() == "E - 17.45km E", "overlay text without a heading has no arrow")
check(len(C.Reading(C.Target("x" * 100, 0, 0, "mark"), 5.0, 0.0, "N", None).text()) < 60, "a very long name is clipped in the text")


class Spot:
    def __init__(self, material, lat, lon):
        self.material, self.latitude, self.longitude = material, lat, lon

    def has_position(self):
        return self.latitude is not None


tmp = tempfile.mkdtemp()
book = M.MarkBook()
book.load(tmp)
book.set_commander("Bocheaux")
here_mark = book.add("Ship", "Sys A 1", 0.5, 0.0)
other_mark = book.add("Elsewhere", "Sys B 2", 0.2, 0.2)
spots = [Spot("Platinum", 0.1, 0.0), Spot("Osmium", 0.9, 0.0), Spot("Pinned later", None, None)]

check(C.pick_target(M.NONE, None, "Sys A 1", spots, 0, 0, RADIUS) is None, "no target")
t = C.pick_target(M.AUTO, None, "Sys A 1", spots, 0.0, 0.0, RADIUS)
check(t and t.label == "Platinum" and t.kind == "hotspot", f"the nearest hotspot with a position: {t}")
check(C.pick_target(M.AUTO, None, "Sys A 1", [Spot("x", None, None)], 0, 0, RADIUS) is None, "hotspots with no position are skipped")
check(C.pick_target(M.AUTO, None, "Sys A 1", [], 0, 0, RADIUS) is None, "no hotspots, nothing to point at")
t = C.pick_target(here_mark.id, here_mark, " SYS a 1 ", spots, 0, 0, RADIUS)
check(t and t.label == "Ship" and t.kind == "mark", f"a mark on this body (name matched loosely): {t}")
check(C.pick_target(other_mark.id, other_mark, "Sys A 1", spots, 0, 0, RADIUS) is None, "a mark on another body is not pointed at")
check(C.pick_target("gone", None, "Sys A 1", spots, 0, 0, RADIUS) is None, "a missing mark is not pointed at")
check(C.cycle_choices(book, "Sys A 1") == [M.AUTO, here_mark.id, M.NONE], f"cycle order: {C.cycle_choices(book, 'Sys A 1')}")
check(C.cycle_choices(book, "") == [M.AUTO, M.NONE], "no body, no marks to cycle")

# --- the controller ---------------------------------------------------------------------------------------------------------------------
fake_repo = SimpleNamespace(current_system="Sys", current_body="Sys A 1", radius_for_current_body=lambda: None)
fake_spots = SimpleNamespace(for_body=lambda system, body: spots)
mining_surface.surface_mining_repository = fake_repo
C.surface_mining.surface_mining_repository = fake_repo
C.hotspots.hotspot_repository = fake_spots

saved["wntb_compass_migrated_v1"] = True      # the carry-over is tested on its own below
saved.pop("wntb_compass_enabled", None)
C.book.load(tempfile.mkdtemp())
ctl = C.controller
rec = Rec()
ctl.set_overlay_client(rec)
panel_host = tk.Frame(root)
panel_host.pack()
saved["wntb_compass_collapsed"] = False
ctl.build_panel(panel_host)
pump()
check(ctl.summary() == "Log in to use the compass.", f"before a commander: {ctl.summary()}")
ctl.handle_event({"event": "LoadGame"}, "Bocheaux", "Sys", None, {})


def status(lat=0.0, lon=0.0, heading=0.0, body="Sys A 1", radius=RADIUS, flags=1 << 21):
    entry = {"Flags": flags, "Latitude": lat, "Longitude": lon, "Heading": heading, "PlanetRadius": radius, "BodyName": body}
    LP.set_status(entry)
    ctl.dashboard_status(entry)


status(flags=0)
check("Waiting for a surface position" in ctl.summary() and "nearest hotspot" in ctl.summary(), f"in space: {ctl.summary()}")
check(rec.calls == 0, "nothing is drawn while the overlay is off")

status()
check(ctl._reading is not None and ctl._reading.target.label == "Platinum", f"on the surface, aiming at the nearest hotspot: {ctl._reading}")
check(ctl.summary().startswith("↑ Platinum"), f"the panel line is the overlay line: {ctl.summary()}")
check(rec.calls == 0, "the overlay is off by default: nothing drawn")

saved["wntb_compass_enabled"] = True
status()
check(C._BG_ID in rec.shapes and "Platinum" in rec.messages.get(C._TEXT_ID, "") and C._ARROW_ID in rec.vectors,
      f"the overlay card is drawn when enabled: {rec.messages}")
status(lat=0.0, lon=0.0, heading=None)
check(C._ARROW_ID not in rec.vectors and "Platinum" in rec.messages[C._TEXT_ID], "no heading: text, no arrow")

# marking
made = ctl.mark_here("")
check(made is not None and C.book.count() == 1, "a mark is made where you stand")
check(C.book.all()[0].name == "Mark 1" and C.book.all()[0].body == "Sys A 1", f"a blank name becomes Mark 1: {C.book.all()}")
mark = ctl.mark_here("  Camp  ")
check(mark and mark.name == "Camp" and abs(mark.latitude) < 1e-9, f"a typed name is used: {mark}")
status(flags=0)
check(ctl.mark_here("Nope") is None and "surface position" in ctl.summary(), f"no position, no mark: {ctl.summary()}")
check(C.book.count() == 2, "nothing was added without a position")
status(body="")
check(ctl.here().body == "Sys A 1", "no BodyName in Status.json falls back to the body the journal named")

# cycling the target: nearest hotspot -> each mark here -> nothing -> nearest hotspot
status()
seen = [C.book.target]
for _ in range(4):
    ctl.cycle_target()
    seen.append(C.book.target)
ids = [m.id for m in C.book.for_body("Sys A 1")]
check(seen == [M.AUTO] + ids + [M.NONE, M.AUTO], f"the target cycles through the marks here: {seen}")
ctl.cycle_target()
status(lat=0.0, lon=0.0)
check(ctl._reading is not None and ctl._reading.target.kind == "mark", f"aiming at a mark: {ctl._reading}")
check("Camp" in rec.messages[C._TEXT_ID] or "Mark 1" in rec.messages[C._TEXT_ID], f"the overlay names the mark: {rec.messages}")
C.book.set_target(M.NONE)
status()
check(ctl._reading is None and C._BG_ID not in rec.shapes and not rec.messages, "no target clears the overlay")
calls = rec.calls
status()
check(rec.calls == calls, "an already clear overlay is not sent to again")
C.book.set_target(M.AUTO)
status(body="Other Body")
check(C.book.target == M.AUTO and ctl._reading is not None, "hotspots follow the repository's body, not Status.json's")
other = C.book.add("Far", "Other Body", 0.3, 0.3)
C.book.set_target(other.id)
status(body="Sys A 1")
ctl._clear_notice()      # the panel shows a message for a few seconds after a mark or a change of target
check(ctl._reading is None and "not here" in ctl.summary(), f"a target mark on another body: {ctl.summary()}")
C.book.set_target(M.AUTO)

# --- carrying over the old Mining waypoint settings -------------------------------------------------------------------------------------------------
for key in list(saved):
    if key.startswith("wntb_compass") or key.startswith("wntb_overlay_"):
        saved.pop(key)
saved["wntb_mining_waypoint_overlay_enabled"] = True
saved["wntb_overlay_place_mining_waypoint"] = "left,top,60,320"
saved["wntb_overlay_hidden_mining_waypoint"] = "1"
C.migrate_old_waypoint_settings()
check(saved.get("wntb_compass_enabled") is True, "someone who had the arrow on has the compass on")
check(saved.get("wntb_overlay_place_surface_compass") == "left,top,60,320", f"its placement carries over: {saved.get('wntb_overlay_place_surface_compass')}")
check(saved.get("wntb_overlay_hidden_surface_compass") == "1", "so does having hidden it")
check(saved.get("wntb_compass_migrated_v1") is True, "it is done once")
saved["wntb_compass_enabled"] = False
saved["wntb_overlay_place_surface_compass"] = "right,bottom,1,1"
C.migrate_old_waypoint_settings()
check(saved["wntb_compass_enabled"] is False and saved["wntb_overlay_place_surface_compass"] == "right,bottom,1,1", "a second run changes nothing")
for key in ("wntb_compass_migrated_v1", "wntb_compass_enabled", "wntb_overlay_hidden_surface_compass"):
    saved.pop(key, None)
saved["wntb_mining_waypoint_overlay_enabled"] = False
C.migrate_old_waypoint_settings()
check(not saved.get("wntb_compass_enabled"), "someone who had the arrow off keeps the compass off")
check(saved["wntb_overlay_place_surface_compass"] == "right,bottom,1,1", "a placement already chosen for the compass is not overwritten")
saved["wntb_compass_migrated_v1"] = True
check("surface_compass" in P.SLOTS and P.SLOTS["surface_compass"].group == C.GROUP_NAME, "the placement slot is the compass's")
check("mining_waypoint" not in P.SLOTS, "the old placement slot is gone")

# --- the panel row never widens the main panel --------------------------------------------------------------------------------------------------------
C.book.add("N" * 60, "B" * 100, 1, 1)
status(body="B" * 100)
pump()
check(panel_host.winfo_reqwidth() <= 216, f"the open Compass section asks for {panel_host.winfo_reqwidth()} px, wider than the main panel")
check(C._PANEL_WRAP_PX <= 216, "the summary wraps narrower than the main panel")

# --- the Marks window --------------------------------------------------------------------------------------------------------------------------
status()
W.show(root, C.book, ctl.here)
win = W._window
pump()
check(win is not None and win.alive and len(win._table) == C.book.count(), f"the window lists every mark: {len(win._table)} of {C.book.count()}")
win._new()
check(win._body.get() == "Sys A 1" and win._lat.get() == "0.0000" and win._lon.get() == "0.0000", "a new mark starts with where you are")
win._name.set("From the window")
win._save()
check(any(m.name == "From the window" for m in C.book.all()), "saving adds a mark")
win._name.set("")
win._editing = None
win._save()
check(any(m.name.startswith("Mark ") for m in C.book.all()), "a blank name becomes the next Mark number")
before = C.book.count()
win._new()
win._name.set("Bad")
win._lat.set("north")
win._save()
check(C.book.count() == before and "Latitude" in win._shell._status.cget("text"), f"a bad latitude is refused with a reason: {win._shell._status.cget('text')!r}")
win._lat.set("95")
win._save()
check(C.book.count() == before, "a latitude out of range is refused")
win._lat.set("0,5")
win._lon.set("0.25")
win._save()
check(C.book.count() == before + 1 and abs(C.book.get(win._editing).latitude - 0.5) < 1e-9, "a comma is accepted as a decimal point")

target = next(m for m in C.book.all() if m.name == "From the window")
win._table.select(target.id, notify=True)
check(win._name.get() == "From the window" and win._editing == target.id, "selecting loads the mark into the editor")
win._target_selected()
check(C.book.target == target.id and "From the window" in win._aim_label.cget("text"), "Selected mark sets the target")
win._set_target(M.AUTO)
check(C.book.target == M.AUTO and "nearest" in win._aim_label.cget("text"), "Nearest hotspot sets it back")
win._set_target(M.NONE)
check(win._aim_label.cget("text") == "nothing", "Nothing sets it to none")
win._new()
win._target_selected()
check("Select a mark" in win._shell._status.cget("text"), "Selected mark with nothing selected says so")

win._table.select(target.id, notify=True)
check(win._distance(target) != "", "a mark on the body you are on shows how far it is")
check(win._distance(other) == "", "a mark on another body shows nothing")
win._delete()
check(C.book.get(target.id) is not None and "again" in win._shell._status.cget("text"), "the first press of Delete only asks")
win._delete()
check(C.book.get(target.id) is None, "the second press deletes")
listeners = len(C.book._listeners)
W.close()
pump()
check(not win.alive and len(C.book._listeners) == listeners - 1, "closing removes the window's listener")

if problems:
    print("PROBLEMS:", len(problems))
    for line in problems:
        print(" -", line)
    sys.exit(1)
print("SURFACE COMPASS OK")
