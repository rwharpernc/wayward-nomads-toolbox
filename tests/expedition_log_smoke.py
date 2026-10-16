"""Opens the real Expedition Log row and window (plugin/expedition_log_panel.py, expedition_log_window.py) with EDMC stubbed and feeds them journal-shaped events: the row's
lines before and during an expedition, START and STOP, the totals counted from events, the window's table, facts and editor (name, dates, locations, ships, notes, a bad date),
Reset and Delete asking twice, Rescan from journals on disk, Copy summary, Export CSV, a commander change, and the overlay card. Run by test_expedition_log_smoke.py in a
subprocess so the stand-ins never leak into other tests. Exits 0 if everything holds, 1 if not, 77 if Tk is unavailable."""
import csv
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

from plugin import expedition_log as L, expedition_log_overlay as OV, expedition_log_panel as PA, expedition_log_window as WIN  # noqa: E402

problems = []


def check(condition, message):
    if not condition:
        problems.append(message)


def pump(times=3):
    for _ in range(times):
        root.update()


def ev(entry, cmdr="CMDR A", system=None):
    PA.handle_event(entry, cmdr, system, None, {})


tmp = tempfile.mkdtemp()
journals = tempfile.mkdtemp()
PA.start(tmp)

# --- the row, before anything is running -----------------------------------------------------------------------------------------
frame = tk.Frame(root)
frame.pack()
PA.build_panel(frame)
pump()
check("Log in" in PA.summary_text(PA.book), "before a commander is known the row says to log in")
ev({"event": "LoadGame", "Commander": "CMDR A"})
check("No expedition yet" in PA.summary_text(PA.book), f"with a commander but no expedition: {PA.summary_text(PA.book)}")

# --- START: from where the commander is, in the ship they are in -----------------------------------------------------------------------------
ev({"event": "Loadout", "Ship": "explorer_nx", "Ship_Localised": "Caspian Explorer", "ShipName": "Far Horizon", "ShipIdent": "WN-01"})
ev({"event": "Location", "StarSystem": "Sol", "SystemAddress": 1}, system="Sol")
run = PA.controller.start_expedition("Core Run")
pump()
check(run is not None and run.start_system == "Sol" and run.ships == ["Caspian Explorer 'Far Horizon' WN-01"], f"the expedition starts here in this ship: {run}")
check(PA.book.running() is run, "and it is the one running")

# --- journal events are counted while it runs -----------------------------------------------------------------------------------------
stamp0 = time.time()
events = [
    {"event": "FSDJump", "StarSystem": "Alpha", "SystemAddress": 2, "JumpDist": 12.5},
    {"event": "FSSDiscoveryScan", "Progress": 0.5, "BodyCount": 3},
    {"event": "Scan", "BodyID": 1, "BodyName": "Alpha 1", "SystemAddress": 2, "PlanetClass": "Earthlike body", "MassEM": 1.0, "WasDiscovered": False, "WasMapped": False,
     "WasFootfalled": False, "Landable": True, "TerraformState": "Terraformable"},
    {"event": "SAAScanComplete", "BodyID": 1, "BodyName": "Alpha 1", "SystemAddress": 2},
    {"event": "ScanOrganic", "ScanType": "Analyse", "Genus": "$Codex_Ent_Tussocks_Genus_Name;", "Genus_Localised": "Tussock",
     "Species": "$Codex_Ent_Tussocks_06_Name;", "Body": 1, "SystemAddress": 2},
    {"event": "MultiSellExplorationData", "TotalEarnings": 1_500_000},
    {"event": "SellOrganicData", "BioData": [{"Value": 1_000_000, "Bonus": 4_000_000}]},
]
for entry in events:
    ev(entry, system="Alpha")
pump()
t = run.totals
check((t.jumps, t.light_years, t.bodies_scanned, t.first_discoveries, t.mapped, t.first_mapped) == (1, 12.5, 1, 1, 1, 1), f"exploration is counted: {t}")
check((t.bio_species, t.bio_first_footfalls, t.explore_earned, t.bio_earned) == (1, 1, 1_500_000, 5_000_000), f"exobiology and what was sold are counted: {t}")
text = PA.summary_text(PA.book)
check("Core Run" in text and "Earned 6.5M" in text, f"the row shows the running expedition and what it earned: {text}")
check(frame.winfo_reqwidth() < 420, f"the row does not widen the panel: {frame.winfo_reqwidth()}")

# --- the overlay card ----------------------------------------------------------------------------------------------------------------
card = OV.build_card(run, stamp0 + 7_500)
check(card.title[0] == "Core Run" and "2h" in card.badge, f"the card is titled with the name and how long it has run: {card.title} {card.badge}")
labels = {r[0] + str(i): r for i, r in enumerate(card.rows)}
check(any(r[0] == "Earned" and r[1].startswith("1.5M") for r in card.rows) and any(r[0] == "Earned" and r[1].startswith("5.0M") for r in card.rows), f"the card shows both earnings: {card.rows}")
check("Total earned 6.5M" in card.footer[0], f"and the total: {card.footer}")
check(not OV.build_card(None), "no expedition, no card")
check(OV.build_card(OV.sample_run()), "the sample card builds")

# --- STOP ----------------------------------------------------------------------------------------------------------------------------
PA.controller.stop_expedition()
pump()
check(PA.book.running() is None and run.ended, "STOP ends it")
ev({"event": "FSDJump", "StarSystem": "Beta", "SystemAddress": 3, "JumpDist": 99.0})
check(run.totals.jumps == 1, "nothing is counted while no expedition is running")
check("No expedition running (1 in the archive)" in PA.summary_text(PA.book), PA.summary_text(PA.book))

# --- the window -------------------------------------------------------------------------------------------------------------------------
WIN.journal_folder = lambda: journals
WIN.show(root, PA.book, PA.controller)
pump()
win = WIN._window
check(win is not None and win.alive, "the window opens")
check(len(win._table) == 1, f"the table lists the expedition: {len(win._table)}")
check("Core Run" in win._facts.cget("text") and "TOTAL EARNED 6,500,000 cr" in win._facts.cget("text"), f"the facts show what it recorded: {win._facts.cget('text')[:200]}")
check(win._fields["name"].get() == "Core Run" and win._fields["start_system"].get() == "Sol", "the editor holds its details")

# edit the details
win._fields["name"].set("Colonia Run")
win._fields["started"].set("2026-10-10 08:00")
win._fields["ended"].set("2026-10-12 20:30")
win._fields["end_system"].set("Colonia")
win._ships.delete("1.0", "end")
win._ships.insert("1.0", "Caspian Explorer 'Far Horizon' WN-01\nPython 'B'")
win._notes.delete("1.0", "end")
win._notes.insert("1.0", "Went the long way.")
win._save()
pump()
check((run.name, run.started, run.ended, run.end_system, run.ships, run.notes) == (
    "Colonia Run", "2026-10-10T08:00:00Z", "2026-10-12T20:30:00Z", "Colonia", ["Caspian Explorer 'Far Horizon' WN-01", "Python 'B'"], "Went the long way."), f"the edits are saved: {run}")
win._fields["started"].set("next week")
win._save()
check("not a date" in win._shell._status.cget("text") and run.started == "2026-10-10T08:00:00Z", "a bad date is refused and nothing is lost")
win._fields["started"].set("2026-10-10 08:00")

# rescan from journals on disk
lines = [{"event": "LoadGame", "Commander": "CMDR A", "timestamp": "2026-10-10T07:00:00Z"},
         {"event": "FSDJump", "StarSystem": "Out", "SystemAddress": 7, "JumpDist": 40.0, "timestamp": "2026-10-10T09:00:00Z"},
         {"event": "FSDJump", "StarSystem": "Farther", "SystemAddress": 8, "JumpDist": 60.0, "timestamp": "2026-10-11T09:00:00Z"},
         {"event": "FSDJump", "StarSystem": "Late", "SystemAddress": 9, "JumpDist": 500.0, "timestamp": "2026-10-25T09:00:00Z"}]
with open(os.path.join(journals, "Journal.2026-10-10T070000.01.log"), "w", encoding="utf-8") as handle:
    handle.write("\n".join(json.dumps(line) for line in lines) + "\n")
win._rescan()
for _ in range(60):
    pump(1)
    time.sleep(0.05)
    if not win._busy:
        break
check(run.totals.jumps == 2 and run.totals.light_years == 100.0, f"rescan works the totals out again from the journals within its dates: {run.totals}")
check(run.name == "Colonia Run" and run.notes == "Went the long way.", "and keeps the name and notes")

# copy and export
win._copy()
check("Colonia Run" in root.clipboard_get(), "Copy summary puts the recap on the clipboard")
target = os.path.join(tmp, "out.csv")
WIN.ask_save_path = lambda **kw: target
win._export()
with open(target, encoding="utf-8", newline="") as handle:
    rows = list(csv.reader(handle))
check(rows[0][0] == "Name" and rows[1][0] == "Colonia Run" and rows[1][8] == "2", f"the CSV has headings and a row for the expedition: {rows[:2]}")

# reset and delete ask twice
win._reset()
check(PA.book.get(run.id).totals.jumps == 2, "the first press of Reset only asks")
win._reset()
reset_run = PA.book.get(run.id)
check(reset_run.totals.jumps == 0 and reset_run.name == "Colonia Run" and reset_run.status == L.RUNNING, f"the second press clears the totals and keeps the name: {reset_run}")
win._delete()
check(PA.book.get(run.id) is not None, "the first press of Delete only asks")
win._delete()
check(PA.book.get(run.id) is None and len(win._table) == 0, "the second press removes it")

# start from the last sale: the journals say when you last sold, and the expedition carries on from the data you hold
sale_lines = [{"event": "LoadGame", "Commander": "CMDR A", "timestamp": "2026-10-12T00:00:00Z"},
              {"event": "SellOrganicData", "BioData": [], "timestamp": "2026-10-12T01:00:00Z"},
              {"event": "FSDJump", "StarSystem": "Post", "SystemAddress": 11, "JumpDist": 33.0, "timestamp": "2026-10-12T02:00:00Z"},
              {"event": "FSDJump", "StarSystem": "Post2", "SystemAddress": 12, "JumpDist": 44.0, "timestamp": "2026-10-12T03:00:00Z"}]
with open(os.path.join(journals, "Journal.2026-10-12T000000.01.log"), "w", encoding="utf-8") as handle:
    handle.write("\n".join(json.dumps(line) for line in sale_lines) + "\n")
win._start_since_sale()
for _ in range(80):
    pump(1)
    time.sleep(0.05)
    if not win._busy:
        break
since = PA.book.running()
check(since is not None and since.started == "2026-10-12T01:00:01Z", f"an expedition starts just after the last sale: {since and since.started}")
check(since is not None and since.totals.jumps == 3 and since.totals.light_years == 577.0, f"and takes the totals the journals give since then: {since and since.totals}")
ev({"event": "FSDJump", "StarSystem": "Post3", "SystemAddress": 13, "JumpDist": 3.0})
check(since is not None and since.totals.jumps == 4, "and carries on counting live")
PA.controller.stop_expedition()

# a new expedition from the window, and a commander change
win._new_name.set("Second")
win._start()
pump()
check(PA.book.running() is not None and PA.book.running().name == "Second", "Start in the window begins a new expedition")
ev({"event": "LoadGame", "Commander": "CMDR B"}, cmdr="CMDR B")
check(PA.book.running() is None and PA.book.runs() == [], "another commander sees none of it")
ev({"event": "LoadGame", "Commander": "CMDR A"}, cmdr="CMDR A")
check(PA.book.running() is not None, "and it is back for the first")
win.close()
PA.stop()

if problems:
    print("PROBLEMS:", len(problems))
    for p in problems:
        print(" -", p)
    sys.exit(1)
print("EXPEDITION LOG OK")
