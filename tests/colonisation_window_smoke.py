"""Opens the real Colonization Sites window (plugin/colonisation_window.py) with EDMC stubbed, and checks that
it builds, follows the picked site, filters and sorts, shows the FC column only for a carrier owner, and fits at its
minimum size. Run by test_colonisation_window_smoke.py in a subprocess so the stand-ins never leak
into other tests. Exits 0 if everything holds, 1 if not, 77 if Tk is unavailable."""
import os
import sys
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
          "win32process", "win32clipboard", "pywintypes", "psutil"):
    sys.modules[n] = Any(n)
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
        return default

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

from plugin import colonisation, colonisation_carrier, colonisation_data, colonisation_window as W
from plugin.uikit.table import DataTable

problems = []


def check(condition, message):
    if not condition:
        problems.append(message)


def tables(widget):
    found = []
    for child in widget.winfo_children():
        if isinstance(child, DataTable):
            found.append(child)
        found += tables(child)
    return found


def make(market_id, name, complete=False):
    entry = {"MarketID": market_id, "ConstructionProgress": 0.4, "ConstructionComplete": complete,
             "ResourcesRequired": [
                 {"Name": "$steel_name;", "Name_Localised": "Steel", "RequiredAmount": 500, "ProvidedAmount": 100},
                 {"Name": "$water_name;", "Name_Localised": "Water", "RequiredAmount": 50, "ProvidedAmount": 0},
                 {"Name": "$aluminium_name;", "Name_Localised": "Aluminium", "RequiredAmount": 80, "ProvidedAmount": 0}]}
    return colonisation.apply_depot_event(entry, None, name=name, system="Sol")


repo = colonisation_data.SiteRepository()
repo.upsert("Bocheaux", make(1, "Depot One"))
repo.upsert("Bocheaux", make(2, "Depot Two", complete=True))
repo.upsert("Mactavious", make(3, "Other Depot"))
carrier = colonisation_carrier.CarrierCargo()

W.show(root, repo, "Bocheaux", {"water": 50}, carrier, lambda: 100)
window = W._window
check(window is not None and window.alive, "the window did not open")
top = window._toplevel
top.geometry(f"{W.MIN_WIDTH}x{W.MIN_HEIGHT}+20+20")
for _ in range(4):
    root.update()

check(window._selected == 1, f"the first active site should be picked, got {window._selected}")
check(len(window._site_table) == 2, "both of the commander's sites should be listed (not the other commander's)")
check(len(window._commodity_table) == 3, "three commodities are outstanding")
check(window._tile_source.winfo_exists(), "the totals tiles should exist")
check(window._tile_trips._value.cget("text") == "5", f"trips: {window._tile_trips._value.cget('text')}")  # 480 t to source / 100

# Picking the other site switches the detail.
window._on_pick_site("2")
check(window._selected == 2, "picking a site should select it")
window._on_pick_site("1")

# Filters.
window._hide_covered.set(True)
window._refresh_detail()
check(len(window._commodity_table) == 2, "hide-covered should drop Water")
window._hide_covered.set(False)
window._filter_text.set("ste")
check(len(window._commodity_table) == 1, "the text filter should keep only Steel")
window._filter_text.set("")

# Sorting by To Source, twice (descending).
window._on_sort("source")
check(window._sort_key == "source" and not window._sort_desc, "first header click sorts ascending")
window._on_sort("source")
check(window._sort_desc, "second header click sorts descending")

# No FC column without a carrier; the table never asks for more than the window has.
check(window._with_fc is False, "no FC column for a commander without a carrier")
for _ in range(4):
    root.update()
for table in tables(window._detail):
    check(table.winfo_reqwidth() <= top.winfo_width(), "a table asks for more width than the window has")

# Following the commander and refreshing the hold.
W.refresh_cmdr("Mactavious")
check(window._selected == 3 and len(window._site_table) == 1, "the window should follow the commander")
W.refresh_cmdr("Bocheaux")
W.refresh_cargo({"steel": 400})
check(window._tile_hold._value.cget("text") == "400", "the hold figure should follow the cargo")

# Buttons act on the picked site.
window._on_pick_site("2")
window._on_remove_finished()
check(2 not in window._sites, "Remove Finished should delete the complete site")
check(window._selected == 1, "the selection should fall back to an active site")
window._on_remove()
check(window._selected is None and len(window._site_table) == 0, "Remove Site should delete the picked site")
check(window._title.cget("text") == "No site selected", "an empty window should say so")

window.close()
root.destroy()
if problems:
    print("PROBLEMS:")
    for p in problems:
        print(" -", p)
    sys.exit(1)
print("COLONISATION WINDOW OK")
