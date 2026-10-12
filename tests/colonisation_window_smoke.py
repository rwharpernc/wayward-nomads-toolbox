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

market_state = [None]   # what the docked station sells: None until a market is opened
W.show(root, repo, "Bocheaux", {"water": 50}, carrier, lambda: 100, None, lambda: market_state[0])
window = W._window
check(window is not None and window.alive, "the window did not open")
window._group_by_category.set(False)    # the checks below count plain rows; grouping is checked at the end
window._refresh_detail()
top = window._toplevel
top.geometry(f"{W.MIN_WIDTH}x{W.MIN_HEIGHT}+20+20")
for _ in range(4):
    root.update()

check(window._selected == 1, f"the first active site should be picked, got {window._selected}")
check(len(window._site_table) == 2, "both of the commander's sites should be listed (not the other commander's)")
check(len(window._commodity_table) == 3, "three commodities are outstanding")
check(window._tile_get.winfo_exists(), "the totals tiles should exist")
check(window._tile_haul._value.cget("text") == "6", f"haul trips: {window._tile_haul._value.cget('text')}")  # 530 t left / 100
window._refresh()   # (the tiles' text is set whether or not they are shown)
check(window._tile_buy.winfo_manager() == "" and window._tile_carrier.winfo_manager() == "",
      "without a carrier there is no carrier figure and no separate buy figure")
check(window._tile_haul._caption.cget("text") == "trips to finish", "one trips figure without a carrier")
check(window._tile_ship._value.cget("text") == "100", f"ship hold: {window._tile_ship._value.cget('text')}")

# Trips Left: each commodity's remaining tons over the ship's 100 t capacity, two decimals at most.
window._on_sort("label")
for _ in range(4):
    root.update()
trips = {row.values[0]: row.values[-1] for row in window._commodity_table._rows.values()}
check(trips == {"Aluminium": "0.8", "Steel": "4", "Water": "0.5"},
      f"the single Trips column without a carrier: {trips}")   # 100 t ships carrying the whole remaining need
check(len(window._commodity_table._rows[next(iter(window._commodity_table._rows))].values) == 6, "no FC, no Buy Trips")

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

# The search choices are remembered: the two searches above used "Large only" and carriers on.
saved_prefs = S.load_prefs(saved.get(W.CONFIG_SEARCH))
check(saved_prefs.pad == "large" and saved_prefs.carriers is True and saved_prefs.radius_ly == 50.0,
      f"the search choices should be saved when a search starts, got {saved_prefs}")
saved[W.CONFIG_SEARCH] = S.dump_prefs(S.SearchPrefs(radius_ly=None, pad="medium", carriers=True, sort="price"))
reopened = W.ColonisationWindow(root, repo, "Bocheaux", {}, None, lambda: 100)
check(reopened._radius.get() == "No limit" and reopened._pad.get() == "Medium or larger"
      and reopened._sort.get() == "Cheapest first" and reopened._carriers_var.get() is True,
      "a new window should start from the remembered choices")
reopened.close()
saved[W.CONFIG_SEARCH] = S.dump_prefs(S.SearchPrefs())

# Only what this station sells: greyed out until a market is known, then narrows the list to what it has for sale.
window._refresh_detail()
check(str(window._station_check.cget("state")) == "disabled", "the station filter needs a market first")
market_state[0] = ("Jameson Memorial", frozenset({"steel"}))
W.refresh_market()
check(str(window._station_check.cget("state")) == "normal"
      and "Jameson Memorial" in window._station_check.cget("text"), "the filter should name the docked station")
check(len(window._commodity_table) == 3, "the filter is off until it is ticked")
window._station_only.set(True)
window._refresh_detail()
check([row.values[0] for row in window._commodity_table._rows.values()] == ["Steel"],
      "only Steel is for sale at the station")
market_state[0] = None
W.refresh_market()
check(not window._station_only.get() and len(window._commodity_table) == 3,
      "leaving the station should switch the filter off and bring every row back")

# Find all: every commodity still to buy (Water is covered by the hold), one heading each with its closest stations.
whole_calls = []


def fake_whole(system, commodities, **kwargs):
    whole_calls.append((system, list(commodities), kwargs))
    kwargs["progress"](0, len(commodities), commodities[0])
    near = S.Source("Near Port", "Sol", "Coriolis Starport", False, False, "Large", 4.0, 300.0, 410, 900)
    found = [(commodities[0], S.SearchResult([near], [])), (commodities[1], S.SearchResult([], []))]
    return S.WholeListResult(found=found, failed=[])


S_whole = W.sources.find_whole_list
W.sources.find_whole_list = fake_whole
window._on_find_all()
for _ in range(100):
    root.update()
    if window._whole_job is None:
        break
    time.sleep(0.02)
check(len(whole_calls) == 1 and whole_calls[0][1] == ["Aluminium", "Steel"],
      f"Find all should search what is still to buy, got {whole_calls}")
check(whole_calls[0][2]["pad"] == "large", "Find all should use the chosen options")
headings = [row.values[0] for row in window._source_table._rows.values() if row.group]
check(headings == ["Suggested route", "1. Near Port", "Aluminium", "Steel"], f"the route, then one heading per commodity: {headings}")
detail = {row.values[0]: row.values[1:3] for row in window._source_table._rows.values() if row.group}
check(detail["Aluminium"] == ["80 t to get", ""] and detail["Steel"] == ["400 t to get", "no source found"],
      f"the detail sits in later columns so the label is not clipped: {detail}")
check(detail["Suggested route"][0] == "1 stop", f"the route heading counts its stops: {detail['Suggested route']}")
check(len(window._source_table) == 6, f"the route (3 rows), two headings and one station: {len(window._source_table)}")
check(window._plan is not None and [s.station for s in window._plan.stops] == ["Near Port"], "a plan should be kept for Copy Route")
check(window._find_all_button.cget("text") == "Find all" and window._find_button._enabled,
      "the buttons come back when the search is done")
check("No source found for Steel" in window._sources_note.cget("text"), "the note should name what had no source")
check("shopping route of 1 stop" in window._sources_note.cget("text") and "Not covered: Steel 400 t" in window._sources_note.cget("text"),
      f"the note should describe the route and what it leaves out: {window._sources_note.cget('text')}")
window._source_table.select("g0s0")
window._on_copy_system()
check("Copied" in window._sources_note.cget("text"), "Copy System works on a Find all result")
window._on_copy_route()
check("Copied the 1-stop shopping route" in window._sources_note.cget("text"), "Copy Route should confirm")
window._on_source_sort("price")
check(len(window._source_table) == 6, "sorting a Find all result keeps it, route included")
window._plan = None
window._on_copy_route()
check("Press Find all first" in window._sources_note.cget("text"), "Copy Route with no route says what to do")
W.sources.find_whole_list = S_whole

# Planned Builds: what Raven Colonial has for the site's system, in its own window; nothing is asked until the button is pressed.
from plugin import colonisation_builds_window as B, rcc_client
asked_rcc = []


def fake_system(system):
    asked_rcc.append(system)
    return rcc_client.parse_system({"name": system, "architect": "ALICE", "open": False, "sites": [
        {"name": "Victor Xray", "status": "plan", "buildType": "hermes", "bodyNum": 31},
        {"name": "Mystery", "status": "plan", "buildType": "not_in_the_table", "bodyNum": 2},
        {"name": "Depot One", "status": "build", "buildType": "no_truss", "bodyNum": 7, "marketId": 1},
        {"name": "Elsewhere", "status": "complete", "buildType": "dysnomia", "bodyNum": 7, "marketId": 999}]})


rcc_real = rcc_client.fetch_system
rcc_client.fetch_system = fake_system
check(not asked_rcc, "nothing should be asked of Raven Colonial before the button is pressed")
window._on_builds()
for _ in range(60):
    root.update()
    if asked_rcc and B._window is not None and len(B._window._table) == 4:
        break
    time.sleep(0.02)
check(asked_rcc == ["Sol"], f"the selected site's system is the one looked up: {asked_rcc}")
check(B._window is not None and B._window.alive, "the Planned Builds window should open")
rows = [row.values for row in B._window._table._rows.values()]
check([r[0] for r in rows] == ["Depot One", "Mystery", "Victor Xray", "Elsewhere"], f"building, planned, then complete: {[r[0] for r in rows]}")
check([r[5] for r in rows] == ["yes", "", "", ""], f"only the site WNTB tracks (market id 1) is marked: {[r[5] for r in rows]}")
check([r[4] for r in rows] == ["53,723 t", "", "6,721 t", ""],
      f"a planned or building site shows its full cost, an unknown one and a finished one do not: {[r[4] for r in rows]}")
check([r[2] for r in rows] == ["Coriolis Starport", "Not in the table", "Satellite Installation", "Pirate Outpost"],
      f"the game's building name is shown where the table knows it: {[r[2] for r in rows]}")
subtitle = B._window._shell._subtitle.cget("text")
check("1 building" in subtitle and "2 planned" in subtitle and "architect ALICE" in subtitle and "locked" in subtitle,
      f"the subtitle should summarize, name the architect and say it is locked: {subtitle}")
check("planned builds need 6,721 t" in subtitle, f"the subtitle should total the planned builds' cost: {subtitle}")
B._window._table.select("s2", notify=True)       # Victor Xray, a Hermes
root.update()
status = B._window._shell._status.cget("text")
check("Satellite Installation" in status and "6,721 t in all" in status and "Steel 2,542" in status,
      f"clicking a costed row names its biggest commodities: {status}")
B._window._table.select("s1", notify=True)       # Mystery: not in the table
root.update()
check("Planned builds come from Raven Colonial" in B._window._shell._status.cget("text"), "an unknown type falls back to the usual note")
B._window.refresh()
for _ in range(40):
    root.update()
    time.sleep(0.01)
check(len(asked_rcc) == 2, "Refresh asks again")
rcc_client.fetch_system = rcc_real
B.close()

# No FC column without a carrier; the table never asks for more than the window has.
check(window._with_fc is False, "no FC column for a commander without a carrier")
for _ in range(4):
    root.update()
for table in tables(window._detail):
    check(table.winfo_reqwidth() <= top.winfo_width(), "a table asks for more width than the window has")

# With a fleet carrier the window has the carrier figure and both trip columns.
carrier.note_carrier("Bocheaux")
carrier.commit()
for _ in range(4):
    root.update()
check(window._with_fc is True, "a carrier owner gets the FC column")
check(window._tile_buy.winfo_manager() == "pack" and window._tile_carrier.winfo_manager() == "pack", "carrier and buy figures shown")
check(window._tile_buy._value.cget("text") == "5", f"buy trips: {window._tile_buy._value.cget('text')}")    # 430 t still to buy
check(window._tile_haul._caption.cget("text") == "trips to haul", "haul wording with a carrier")
trips = {row.values[0]: (row.values[-2], row.values[-1]) for row in window._commodity_table._rows.values()}
check(trips == {"Aluminium": ("0.8", "0.8"), "Steel": ("4", "4"), "Water": ("0", "0.5")}, f"Buy and Haul Trips columns: {trips}")
carrier._store["commanders"].clear()   # and back to no carrier for the rest of the checks
carrier.commit()
for _ in range(4):
    root.update()
check(window._with_fc is False, "back to no carrier")

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
# Grouped by market category, as in SrvSurvey's list; what the docked market does not sell is grayed out with a note.
window._selected = 1
window._sort_key, window._sort_desc = "label", False
market_state[0] = ("Test Port", frozenset({"steel"}))
window._group_by_category.set(True)
window._refresh_detail()
table = window._commodity_table
heads = [(iid, row.values[0]) for iid, row in table._rows.items() if row.group]
check([name for _iid, name in heads] == ["Chemicals", "Metals"], f"category headings, in order: {heads}")
check(table._rows["1:steel"].parent == "1:cat:Metals", "Steel sits under Metals")
check(table._rows["1:water"].tag == "unavailable" or table._rows["1:water"].tag in ("enough", "over"),
      f"Water is not sold at the market: {table._rows['1:water'].tag}")
if table._rows["1:water"].tag == "unavailable":
    check(table._rows["1:water"].values[0].endswith(W.NOT_AVAILABLE.strip()) or "not available" in table._rows["1:water"].values[0],
          "an unavailable commodity says so")
check(table._rows["1:steel"].tag != "unavailable", "Steel is sold at the market")
window._on_sort("remaining")
check(not any(row.group for row in table._rows.values()), "sorting by another column gives a plain list")
window._on_sort("label")
check(any(row.group for row in table._rows.values()) or window._sort_desc, "sorting by commodity again")
market_state[0] = None
window._group_by_category.set(False)
window._refresh_detail()

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
