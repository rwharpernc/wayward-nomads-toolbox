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
check(window._tile_get.winfo_exists(), "the totals tiles should exist")
check(window._tile_haul._value.cget("text") == "6", f"haul trips: {window._tile_haul._value.cget('text')}")  # 530 t left / 100
check(window._tile_buy._value.cget("text") == "5", f"buy trips: {window._tile_buy._value.cget('text')}")    # 430 t still to buy
check(window._tile_ship._value.cget("text") == "100", f"ship hold: {window._tile_ship._value.cget('text')}")

# Trips Left: each commodity's remaining tons over the ship's 100 t capacity, two decimals at most.
window._on_sort("label")
for _ in range(4):
    root.update()
trips = {row.values[0]: (row.values[-2], row.values[-1]) for row in window._commodity_table._rows.values()}
check(trips == {"Aluminium": ("0.8", "0.8"), "Steel": ("4", "4"), "Water": ("0", "0.5")},
      f"Buy and Haul Trips columns: {trips}")   # 100 t ships; the ship carries 50 t of water, which is all the water needs

# Picking the other site switches the detail.
for _ in range(4):
    root.update()
window._site_table._rows["2"].cells[0].event_generate("<Button-1>")
root.update()
check(window._selected == 2, "clicking a site should select it")
window._site_table._rows["1"].cells[0].event_generate("<Button-1>")
root.update()
check(window._selected == 1, "clicking the first site should select it again")

# Filters.
window._hide_covered.set(True)
window._refresh_detail()
check(len(window._commodity_table) == 2, "hide-covered should drop Water")
window._hide_covered.set(False)
window._filter_text.set("ste")
check(len(window._commodity_table) == 1, "the text filter should keep only Steel")
window._filter_text.set("")

# Sorting by Haul Trips, twice (descending).
window._on_sort("haul")
check(window._sort_key == "haul" and not window._sort_desc, "first header click sorts ascending")
window._on_sort("haul")
check(window._sort_desc, "second header click sorts descending")

# Row tints: green when the hold covers the need exactly, orange when it is more, none while short.
def tag_of(key):
    return window._commodity_table._rows[f"1:{key}"].tag


window.set_cargo({"steel": 400, "water": 60})
check(tag_of("steel") == "enough", f"steel exactly covered should be green, got {tag_of('steel')}")
check(tag_of("water") == "over", f"water over should be orange, got {tag_of('water')}")
check(tag_of("aluminium") is None, "aluminium is still short and must keep the normal colors")
for _ in range(4):
    root.update()
steel_cell = window._commodity_table._rows["1:steel"].cells[0]
check(steel_cell.cget("bg").lower() == W.P.ROW_OK, f"the whole row should be tinted, got {steel_cell.cget('bg')}")
window.set_cargo({"water": 50})

# Where to buy: the search runs on a thread; Spansh is replaced by a stand-in that records what was asked.
import time
from plugin import colonisation_sources as S

asked = []


def fake_find(system, commodity, **kwargs):
    asked.append((system, commodity, kwargs))
    near = S.Source("Near Port", "Sol", "Coriolis Starport", False, False, "Large", 4.0, 300.0, 410, 900)
    outpost = S.Source("Small Post", "Alpha", "Planetary Outpost", False, True, "Medium", 9.5, 1200.0, 380, 50)
    fc = S.Source("K7X-LLL", "Beta", "Drake-Class Carrier", True, False, "Large", 12.0, 0.0, 300, 20)
    return S.SearchResult([near, outpost], [fc] if kwargs.get("include_carriers") else [])


def wait_for_search():
    for _ in range(100):
        root.update()
        if window._find_button._enabled:
            return
        time.sleep(0.02)


S_find = W.sources.find
W.sources.find = fake_find
window._on_find()
check(not asked, "Find nearest with no commodity picked must not search")
# A real single click on the row (not a direct call), the way the commander picks a commodity.
for _ in range(4):
    root.update()
steel_row = window._commodity_table._rows["1:steel"]
steel_row.cells[0].event_generate("<Button-1>")
root.update()
check(window._wanted == "Steel", f"picking a commodity row should set the wanted commodity, got {window._wanted}")
check(window._system_var.get() == "Sol", "the search should default to the site's system")
window._on_find()
wait_for_search()
check(len(asked) == 1 and asked[0][1] == "Steel", "the search should ask for Steel")
check(asked[0][2]["pad"] == "any", "the pad size must default to ANY")
check(asked[0][2]["include_carriers"] is False, "fleet carriers must be off by default")
check(len(window._source_table) == 2, "two stations should be listed")
planetary = {row.values[0]: row.values[3] for row in window._source_table._rows.values()}
check(planetary == {"Near Port": "No", "Small Post": "Yes"},
      f"the Planetary column should say whether landing on a surface is needed, got {planetary}")

window._pad.set("Large only")
window._carriers_var.set(True)
window._on_find()
wait_for_search()
check(asked[1][2]["pad"] == "large" and asked[1][2]["include_carriers"] is True, "the options should reach the search")
check(len(window._source_table) == 4, "two stations, the carrier group row and one carrier should be listed")
window._source_table.select("s0")
window._on_copy_system()
check("Copied" in window._sources_note.cget("text"), "Copy System should confirm")

def failing_find(*args, **kwargs):
    raise OSError("boom")


W.sources.find = failing_find
window._on_find()
wait_for_search()
check("failed" in window._sources_note.cget("text"), "a failed search should say so")
check(window._find_button._enabled, "the button must come back after a failure")
W.sources.find = S_find

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
