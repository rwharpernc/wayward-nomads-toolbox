"""Opens the real Materials window and Field Ops row (plugin/materials_window.py, plugin/materials_panel.py) with EDMC stubbed, and checks that the
row follows the login list and the events, shows what is at the limit, that the window filters and sorts, follows a commander change, and that
nothing shown can widen the panel. Run by test_materials_smoke.py in a subprocess so the stand-ins never leak into other tests. Exits 0 if
everything holds, 1 if not, 77 if Tk is unavailable."""
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

from plugin import blueprints, blueprints_window, material_trader_window, material_traders, materials, materials_panel, materials_window  # noqa: E402

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


folder = tempfile.mkdtemp()
panel = materials_panel.MaterialsController()      # a fresh controller; it listens to the shared book
book = materials_panel.book
book.load(folder)
materials_panel.wishlist.load(folder)
materials_panel.engineer_book.load(folder)

saved["wntb_materials_collapsed"] = False          # open, so its widgets count towards the panel's width
host = tk.Frame(root)
host.pack()
panel.build_panel(host)
pump()
check(panel.summary()[0] == "Log in to see your materials.", f"before a commander: {panel.summary()}")

panel.handle_event({"event": "LoadGame"}, "Bocheaux", "Sol", None, {})
check(panel.summary()[0].startswith("No materials yet"), f"a commander with nothing: {panel.summary()}")

login = {"event": "Materials",
         "Raw": [{"Name": "iron", "Count": 300}, {"Name": "tin", "Count": 12}, {"Name": "carbon", "Count": 120}],
         "Manufactured": [{"Name": "gridresistors", "Count": 40}], "Encoded": [{"Name": "legacyfirmware", "Count": 7}]}
panel.handle_event(login, "Bocheaux", "Sol", None, {})
text, suffix = panel.summary()
check(text.splitlines()[0] == "Raw 432 · Manufactured 40 · Encoded 7", f"the totals line: {text!r}")
check("At the limit: Iron" in text, f"iron is at its limit: {text!r}")
check(suffix == "- 479 held", f"the folded title says how many: {suffix!r}")
check(panel._summary_var.get() == text, "the label follows the summary")

panel.handle_event({"event": "MaterialCollected", "Category": "Raw", "Name": "carbon", "Count": 3}, "Bocheaux", "Sol", None, {})
check("Last: +3 Carbon (now 123)" in panel.summary()[0], f"the last change: {panel.summary()[0]!r}")
panel.handle_event({"event": "MaterialDiscarded", "Category": "Raw", "Name": "carbon", "Count": 23}, "Bocheaux", "Sol", None, {})
check("Last: -23 Carbon (now 100)" in panel.summary()[0], f"a discard: {panel.summary()[0]!r}")

# The row never gets wider because of what is held or named.
for n in range(8):
    book.apply_event({"event": "MaterialCollected", "Category": "Raw", "Name": f"mat{n}", "Name_Localised": "M" * 60, "Count": 1})
book.apply_event({"event": "Materials", "Raw": [{"Name": k, "Count": 300} for k in ("iron", "carbon", "lead", "nickel", "phosphorus", "rhenium", "sulphur")],
                  "Manufactured": [], "Encoded": []})
pump()
text = panel.summary()[0]
check("and 4 more" in text, f"only a few names, then a count: {text!r}")
check(host.winfo_reqwidth() <= 216, f"the open Materials section asks for {host.winfo_reqwidth()} px, wider than the main panel")

# --- the window ---------------------------------------------------------------------------------------------------------------------------
book.apply_event(login)
materials_window.show(root, book)
win = materials_window._window
pump()
check(win is not None and win.alive, "the window opens")
check(len(win._table) == 5, f"every held material is listed: {len(win._table)}")

win._query.set("grid")
pump()
check(len(win._table) == 1, f"search narrows the table: {len(win._table)}")
win._query.set("")
win._kind.set("Raw")
win._fill()
check(len(win._table) == 3, f"the type filter: {len(win._table)}")
win._kind.set("All")
win._grade.set("1")
win._fill()
check(len(win._table) == 4 and all(r[2] == 1 for r in materials_window.rows_for(book, grade="1")), f"the grade filter: {len(win._table)}")
win._grade.set("All")
win._full_only.set(True)
win._fill()
check(len(win._table) == 1, f"only what is at the limit: {len(win._table)}")
win._full_only.set(False)
win._fill()
win._table.sort_by("held")
check(len(win._table) == 5, "sorting keeps every row")

panel.handle_event({"event": "LoadGame"}, "Other Cmdr", "Sol", None, {})
pump()
check(len(win._table) == 0 and "Other Cmdr" in win._shell._subtitle.cget("text"), "another commander's window starts empty")
listeners = len(book._listeners)
materials_window.close()
pump()
check(not win.alive and len(book._listeners) == listeners - 1, "closing the window removes its listener")
materials_window.show(root, book)
pump()
check(materials_window._window.alive and materials_window._window is not win, "it can be opened again")
materials_window.close()


# --- the wishlist line and the Engineering window ----------------------------------------------------------------------------------------
panel.handle_event({"event": "LoadGame"}, "Bocheaux", "Sol", None, {})
wish = materials_panel.wishlist
book.apply_event(login)
check("Wishlist" not in panel.summary()[0], "no wishlist line while the wishlist is empty")

fsd5 = next(b for b in blueprints.grades_for("Frame Shift Drive", "Increased FSD Range") if b.grade == 5)
wish.add(fsd5.id, 2)
need = sum(i.count for i in fsd5.ingredients) * 2
check(f"Wishlist: 1 blueprint, 0 can be made, {need:,} pieces short" in panel.summary()[0], f"the line counts what is short: {panel.summary()[0]!r}")
book.apply_event({"event": "Materials", "Raw": [], "Manufactured": [], "Encoded": [
    {"Name": i.key, "Count": i.count * 2} for i in fsd5.ingredients]})
check("Wishlist: 1 blueprint, 1 can be made" in panel.summary()[0] and "short" not in panel.summary()[0].splitlines()[-1],
      f"covered, the line says it can be made: {panel.summary()[0]!r}")
check(host.winfo_reqwidth() <= 216, f"with the wishlist line and both buttons the section asks for {host.winfo_reqwidth()} px")
book.apply_event(login)

blueprints_window.show(root, wish, materials_panel.holdings, materials_panel.engineer_book)
bwin = blueprints_window._window
pump()
check(bwin is not None and bwin.alive, "the Engineering window opens")
check(1 <= len(bwin._table) <= blueprints_window.SHOWN, f"blueprints are listed, capped: {len(bwin._table)}")
bwin._query.set("increased fsd range")
bwin._fill_blueprints()
check(len(bwin._table) == 5, f"search narrows to the five grades: {len(bwin._table)}")
bwin._type.set("Suit")
bwin._query.set("")
bwin._fill_blueprints()
check(len(bwin._table) > 0 and all(b.type == "Suit" for b in blueprints.search("", "Suit", limit=500)), "the module filter")
bwin._type.set(blueprints_window.ALL)
bwin._query.set("increased fsd range")
bwin._fill_blueprints()

bwin._pick(fsd5.id)
check(len(bwin._ingredients) == len(fsd5.ingredients), f"the detail lists the ingredients: {len(bwin._ingredients)}")
check("Increased FSD Range" in bwin._title.cget("text"), "the detail names the blueprint")
before = wish.count()
bwin._crafts.set("3")
bwin._add()
check(wish.get(fsd5.id).crafts == 5, f"adding again adds crafts: {wish.get(fsd5.id).crafts}")
bwin._crafts.set("abc")
bwin._add()
check(wish.get(fsd5.id).crafts == 6, "a crafts box that is not a number counts as one")
bwin._add_one(blueprints.grades_for("Frame Shift Drive", "Increased FSD Range")[0].id)
check(wish.count() == before + 1, "double-clicking a row adds one craft")

bwin._tabs.select(1)
pump()
check(len(bwin._wish_table) == wish.count(), f"the Wishlist tab lists the entries: {len(bwin._wish_table)}")
check(len(bwin._shopping_table) > 0 and "pieces short" in bwin._shopping_title.cget("text"), f"and a shopping list: {bwin._shopping_title.cget('text')!r}")
bwin._pick_wish(fsd5.id)
check(bwin._wish_crafts.get() == "6", "selecting an entry shows its crafts")
bwin._wish_crafts.set("2")
bwin._set_crafts()
check(wish.get(fsd5.id).crafts == 2, "Set crafts")
bwin._wish_crafts.set("0")
bwin._set_crafts()
check(wish.get(fsd5.id).crafts == 2 and "from 1 to" in bwin._shell._status.cget("text"), "a bad crafts number is refused with a reason")
bwin._remove()
check(wish.get(fsd5.id) is not None and "again" in bwin._shell._status.cget("text"), "the first press of Remove only asks")
bwin._remove()
check(wish.get(fsd5.id) is None, "the second press removes it")
bwin._clear()
check(wish.count() == 1, "the first press of Clear list only asks")
bwin._clear()
check(wish.count() == 0 and len(bwin._wish_table) == 0, "the second press empties the list")


# --- engineers ----------------------------------------------------------------------------------------------------------------------------
eng = materials_panel.engineer_book
check(not eng.has_data and blueprints_window.who_can(fsd5, eng).startswith("Offered by"), f"before the game lists engineers it says who offers: {blueprints_window.who_can(fsd5, eng)!r}")
panel.handle_event({"event": "EngineerProgress", "Engineers": [
    {"Engineer": "Felicity Farseer", "EngineerID": 300100, "Progress": "Unlocked", "RankProgress": 40, "Rank": 3},
    {"Engineer": "Lei Cheung", "EngineerID": 300120, "Progress": "Invited"},
    {"Engineer": "Eleanor Bresa", "EngineerID": 400011, "Progress": "Known"}]}, "Bocheaux", "Sol", None, {})
check(eng.has_data and eng.standing("Felicity Farseer").rank == 3, "the panel feeds EngineerProgress to the engineer book")
check("Felicity Farseer" in blueprints_window.who_can(fsd5, eng), f"an unlocked engineer who offers it: {blueprints_window.who_can(fsd5, eng)!r}")
suit = next(b for b in blueprints.ALL if b.type == "Suit")
check(blueprints_window.who_can(suit, eng) != "", f"a suit upgrade: {blueprints_window.who_can(suit, eng)!r}")
lonely = next(b for b in blueprints.ALL if blueprints.real_engineers(b) and not any(e in blueprints.STAND_IN_NAMES for e in b.engineers)
              and not any((eng.standing(e) is not None and eng.standing(e).unlocked) for e in blueprints.real_engineers(b)))
check(blueprints_window.who_can(lonely, eng) == "No engineer unlocked yet", f"nobody unlocked offers it: {blueprints_window.who_can(lonely, eng)!r}")
check("(unlocked, rank 3" in blueprints_window.engineers_text(fsd5, eng), f"standings beside the names: {blueprints_window.engineers_text(fsd5, eng)!r}")

blueprints_window.show(root, wish, materials_panel.holdings, eng)
bwin = blueprints_window._window
pump()
rows = bwin._engineer_rows()
names = [r[0] for r in rows]
check(names[0] == "Felicity Farseer", f"unlocked engineers come first: {names[:3]}")
check("Eleanor Bresa" in names, "an engineer the journal knows but the table does not is listed")
check(dict(rows)["Eleanor Bresa"][2] == "suit, weapon" and "5 settlements" in dict(rows)["Eleanor Bresa"][3],
      f"a Colonia engineer comes from the hand-added notes: {dict(rows)['Eleanor Bresa']}")
check("Baltanos" in names and "Yi Shen" in names, "the other Colonia engineers are listed even before the game names them")
check("10 x Faction Associates (have 0)" in dict(rows)["Yi Shen"][3], f"Yi Shen's items are counted: {dict(rows)['Yi Shen'][3]!r}")
check(dict(rows)["Yi Shen"][1] == "not known yet", f"and an unknown standing says so: {dict(rows)['Yi Shen'][1]!r}")
bwin._engineer_table.select("Baltanos", notify=True)
check("Deriso" in bwin._engineer_note.cget("text") and "not confirmed" in bwin._engineer_note.cget("text"),
      f"selecting one shows where and the caveat: {bwin._engineer_note.cget('text')!r}")
bwin._add_unlock()
check("an action" in bwin._shell._status.cget("text"), f"an action-only unlock cannot go on the wishlist: {bwin._shell._status.cget('text')!r}")
bwin._engineer_table.select("Yi Shen", notify=True)
bwin._add_unlock()
check(wish.get("Unlock|Yi Shen|0") is not None, "Yi Shen's items go on the wishlist")
wish.clear()
bwin._picked_engineer = None                      # nothing selected for the check below
check("Colonia" in blueprints_window.who_can(suit, eng), f"an on-foot entry nobody listed can do hints at Colonia: {blueprints_window.who_can(suit, eng)!r}")
check(dict(rows)["Felicity Farseer"][3] == "-", "an unlocked engineer needs nothing")
check("x Gold" in dict(rows)["Lei Cheung"][3] and "not counted" in dict(rows)["Lei Cheung"][3], f"a commodity unlock is shown, not counted: {dict(rows)['Lei Cheung'][3]!r}")
check(len(bwin._engineer_table) == len(rows), "the table lists every row")
bwin._add_unlock()
check("Select an engineer" in bwin._shell._status.cget("text"), "Put their unlock on the wishlist needs a selection")
bwin._engineer_table.select("Lei Cheung", notify=True)
bwin._add_unlock()
check(wish.get("Unlock|Lei Cheung|0") is not None, f"the unlock goes on the wishlist: {[i.blueprint_id for i in wish.items()]}")
bwin._show_engineer_blueprints()
pump()
check(bwin._query.get() == "Lei Cheung" and len(bwin._table) > 0, f"Show their blueprints searches for them: {len(bwin._table)}")
wish.clear()
eng.apply_event({"event": "EngineerProgress", "Engineer": "Lei Cheung", "EngineerID": 300120, "Progress": "Unlocked", "Rank": 1, "RankProgress": 0})
pump()
check(dict(bwin._engineer_rows())["Lei Cheung"][1] == "Unlocked, rank 1", "a change from the journal shows in the open window")
listeners = len(wish._listeners)
blueprints_window.close()
pump()
check(not bwin.alive and len(wish._listeners) == listeners - 1, "closing the Engineering window removes its listener")
check(sorted(os.listdir(folder)) == sorted([materials.STATE_FILENAME, "blueprint_wishlist.json", "engineers.json"]), f"three data files, no commander name in a file name: {os.listdir(folder)}")


# --- the material trader window -------------------------------------------------------------------------------------------------------------
panel.handle_event({"event": "LoadGame"}, "Bocheaux", "Sol", None, {})
panel.handle_event({"event": "FSDJump", "StarSystem": "Sol", "StarPos": [0, 0, 0]}, "Bocheaux", "Sol", None, {})
book.apply_event(login)
check(panel.system() == "Sol", f"the Materials row tracks the system: {panel.system()!r}")
asked = []
outcome = {"mode": "ok"}


def fake_find(origin, kind, radius, pad):
    asked.append((origin, kind, radius, pad))
    if outcome["mode"] == "fail":
        raise OSError("no network")
    if outcome["mode"] == "refuse":
        raise ValueError("Pick Raw, Manufactured or Encoded.")
    traders = () if outcome["mode"] == "empty" else (
        material_traders.Trader("Near", "Sol", "Coriolis Starport", False, 5.2, 300.0, "Large"),
        material_traders.Trader("Far", "Alpha", "Planetary Outpost", True, 40.0, 2500.0, "Medium"))
    return material_traders.Result(origin, kind, radius, traders)


material_trader_window.find_traders = fake_find
materials_window.show(root, book, panel)
mwin = materials_window._window
pump()
mwin._find_trader()
pump()
tw = material_trader_window._window
check(tw is not None and tw.alive, "Find a trader opens the Material trader window")
check(tw._origin.get() == "Sol", f"it starts from the system you are in: {tw._origin.get()!r}")
check(tw._kind.get() == "Raw", f"the type with the most at the limit comes first: {tw._kind.get()!r}")
check("Grade 1:" in tw._holdings.cget("text") and "at the limit" in tw._holdings.cget("text"), f"what you hold by grade: {tw._holdings.cget('text')!r}")
tw._kind.set("Encoded")
tw._show_holdings()
check("Grade 1: 7 pieces in 1 material" in tw._holdings.cget("text"), f"the holdings follow the type: {tw._holdings.cget('text')!r}")
tw._kind.set("Raw")

tw._find()
check(wait_for(lambda: not tw._busy), "the lookup finishes")
pump()
check(asked == [("Sol", "Raw", 100.0, "any")], f"it searched from the system, the type and the defaults: {asked}")
check(len(tw._table) == 2, f"the traders are listed: {len(tw._table)}")
check("Raw material traders within 100 ly of Sol" in tw._heading.cget("text"), f"the heading says what was asked: {tw._heading.cget('text')!r}")
check("2 found" in tw._shell._status.cget("text"), f"and the status: {tw._shell._status.cget('text')!r}")
tw._copy_system("t0")
check(root.clipboard_get() == "Sol", f"double-click copies the system name: {root.clipboard_get()!r}")

tw._radius.set(material_trader_window.ANY_DISTANCE)
tw._pad.set("Large only")
tw._kind.set("Encoded")
tw._find()
check(wait_for(lambda: not tw._busy), "a second lookup finishes")
check(asked[-1] == ("Sol", "Encoded", None, "large"), f"any distance and the pad choice are passed on: {asked[-1]}")
check("at any distance" in tw._heading.cget("text"), "and the heading says so")

outcome["mode"] = "empty"
tw._find()
check(wait_for(lambda: not tw._busy), "an empty answer finishes")
check("No Encoded material trader" in tw._shell._status.cget("text") and len(tw._table) == 0, f"an empty answer says so: {tw._shell._status.cget('text')!r}")
outcome["mode"] = "fail"
tw._find()
check(wait_for(lambda: not tw._busy), "a failure finishes")
check("could not be reached" in tw._shell._status.cget("text"), f"a failure is explained: {tw._shell._status.cget('text')!r}")
outcome["mode"] = "refuse"
tw._find()
check(wait_for(lambda: not tw._busy) and "Pick Raw" in tw._shell._status.cget("text"), "a refusal shows its message")
outcome["mode"] = "ok"
tw._origin.set("   ")
before = len(asked)
tw._find()
check(len(asked) == before and "Type the system" in tw._shell._status.cget("text"), "an empty system sends nothing")
tw._fill_here()
check(tw._origin.get() == "Sol", "Here fills in the system you are in")

listeners = len(book._listeners)
material_trader_window.close()
pump()
check(not tw.alive and len(book._listeners) == listeners - 1, "closing the trader window removes its listener")
materials_window.close()
pump()

panel.stop()

if problems:
    print("PROBLEMS:", len(problems))
    for line in problems:
        print(" -", line)
    sys.exit(1)
print("MATERIALS OK")
