"""Opens the real Prediction review window (plugin/exo_review_window.py) with EDMC stubbed over a small book of finds, and checks that the tables fill,
the filter narrows the Finds, a find can be picked and reviewed, the review is kept in the book, and the report copies. Run by
test_exo_review_window_smoke.py in a subprocess so the stand-ins never leak into other tests. Exits 0 if everything holds, 1 if not, 77 if Tk is
unavailable."""
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

import json  # noqa: E402

from plugin import exo_analysis as A  # noqa: E402
from plugin import exo_observations as E  # noqa: E402
from plugin import exo_review_window as W  # noqa: E402
from plugin import organic_scan as scan  # noqa: E402

BACTERIUM = "$Codex_Ent_Bacterial_Genus_Name;"
AURASUS = "$Codex_Ent_Bacterial_01_Name;"
failures = []


def check(ok, what):
    if not ok:
        failures.append(what)
        print("FAIL:", what)


def conditions(body, **changes):
    values = dict(body_name=body, planet_class="Rocky body", atmosphere="CarbonDioxide", gravity_g=0.2, temperature_k=180.0, pressure_atm=0.05,
                  volcanism="", star_type="K", system_name="Sol", system_body_types=("Rocky body",))
    values.update(changes)
    return scan.BodyConditions(**values)


folder = tempfile.mkdtemp()
book = E.ObservationBook()
book.load(folder)
hit = conditions("Sol 3")
book.record(hit, [BACTERIUM], BACTERIUM, AURASUS, "Bacterium Aurasus", "Teal", E.predicted_keys(BACTERIUM, hit), when="2026-10-17T10:00:00Z")
cold = conditions("Sol 4", temperature_k=20.0)            # far too cold for Aurasus: the prediction cannot list it
book.record(cold, [BACTERIUM], BACTERIUM, AURASUS, "Bacterium Aurasus", None, E.predicted_keys(BACTERIUM, cold), when="2026-10-17T11:00:00Z")

W.show(root, book)
win = W._window
root.update()
check(win is not None and win.alive, "the window opens")
bar = win._tabs._bar
check(all(c.winfo_x() + c.winfo_width() <= bar.winfo_width() for c in win._tabs._cells), "every tab sits fully inside the tab bar")
check([l.cget("text") for l, _u, _c in win._tabs._tabs] == ["FINDS", "BY GENUS", "RANGES", "TOGETHER"], "the four tabs carry their whole names")
check(len(win._finds_table) == 2, f"two finds listed, got {len(win._finds_table)}")
check(len(win._genus_table) == 1 and len(win._range_table) >= 3, "the genus and range tables fill")
check(any(r.outside for r in A.range_rows(A.finds(book.bodies()))), "the cold find is flagged outside the temperature range")

win._filter.set("Not on the predicted list")
win._fill_finds()
check(len(win._finds_table) == 1, "the filter keeps only the miss")
iid = W.row_id(next(f for f in A.finds(book.bodies()) if not f.hit))
win._finds_table.select(iid, notify=True)
root.update()
check(win._picked == iid, "picking a find selects it")
check("NOT on that list" in win._detail.cget("text"), "the detail says it was missed")

win._status.set("Needs a rule change")
win._note.set("  Aurasus   at 20 K  ")
win._save_review()
root.update()
find = next(f for f in A.finds(book.bodies()) if W.row_id(f) == iid)
check((find.status, find.note) == ("rule", "Aurasus at 20 K"), f"the review is kept: {find.status!r} {find.note!r}")
win._filter.set("Needs a rule change")
win._fill_finds()
check(len(win._finds_table) == 1, "the review filter finds it")
book.record(cold, [BACTERIUM], BACTERIUM, AURASUS, "Bacterium Aurasus", "Later color", [], when="2026-10-18T10:00:00Z")
check(next(f for f in A.finds(book.bodies()) if W.row_id(f) == iid).status == "rule", "a later sample keeps the review")

with open(os.path.join(folder, E.FILENAME), "r", encoding="utf-8") as handle:
    check(json.load(handle)["bodies"]["Sol|Sol 4"]["species"][BACTERIUM]["review"]["status"] == "rule", "the review is saved to the file")
win._copy_report()
root.update()
check("Needs a rule change" in A.report_text(book.bodies()), "the report lists the reviewed find")
W.close()
root.update()
check(not win.alive, "the window closes")
print("EXO REVIEW OK" if not failures else "EXO REVIEW FAILED")
sys.exit(1 if failures else 0)
