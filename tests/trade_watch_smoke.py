"""Opens the real Watch list window and Trade row (plugin/trade_watch_window.py, plugin/trade_watch_panel.py) with EDMC stubbed, and
checks that commodities can be added and removed, that a Market event keeps the prices of what is watched, that a Spansh refresh (stubbed)
fills in the best prices and is refused when Trade's lookups are off, and that the row never gets wider because of what is shown. Run by
test_trade_watch_smoke.py in a subprocess so the stand-ins never leak into other tests. Exits 0 if everything holds, 1 if not, 77 if Tk
is unavailable."""
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

from plugin import trade_watch_data as data, trade_watch_lookup, trade_watch_panel, trade_watch_window  # noqa: E402

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


folder = tempfile.mkdtemp()
journals = tempfile.mkdtemp()
saved["journaldir"] = journals
panel = trade_watch_panel.WatchController()      # a fresh controller; it listens to the shared book
book = trade_watch_panel.book
book.load(folder)

# --- the row ----------------------------------------------------------------------------------------------------------------------------
saved["wntb_trade_watch_collapsed"] = False      # open, so its widgets count towards the panel's width
host = tk.Frame(root)
host.pack()
panel.build_panel(host)
pump()
check(panel.summary()[0] == "Log in to use the watch list.", f"before a commander: {panel.summary()}")

panel.handle_event({"event": "LoadGame"}, "Bocheaux", "Sol", None, {})
check("Nothing watched" in panel.summary()[0], f"a commander with an empty list: {panel.summary()}")
book.add("Gold")
book.add("Tritium")
check(panel.summary() == ("Gold: buy - / sell -\nTritium: buy - / sell -", "- 2 watched"), f"two watched, no prices: {panel.summary()}")
check(panel._summary_var.get().startswith("Gold:"), "the label follows the summary")


def write_market(*items):
    with open(os.path.join(journals, "Market.json"), "w", encoding="utf-8") as handle:
        json.dump({"Items": [{"Name": f"${name.lower()}_name;", "Name_Localised": name, "BuyPrice": buy, "SellPrice": sell,
                              "Stock": stock, "Demand": demand} for name, buy, sell, stock, demand in items]}, handle)


write_market(("Gold", 9100, 9000, 50, 20), ("Silver", 5, 4, 1, 1))
panel.handle_event({"event": "Market", "StationName": "Jameson Memorial", "StarSystem": "Shinrarta Dezhra"}, "Bocheaux", "Sol", None, {})
check(panel.summary()[0].splitlines()[0] == "Gold: buy 9,100 / sell 9,000", f"a Market event keeps the prices: {panel.summary()}")
check(len(book.sightings("Gold")) == 1 and book.sightings("Gold")[0].station == "Jameson Memorial", "the station is recorded")
check(book.sightings("Silver") == [], "a commodity that is not watched is not kept")

# a market event for a station that trades nothing watched changes nothing
write_market(("Silver", 5, 4, 1, 1))
panel.handle_event({"event": "Market", "StationName": "Elsewhere", "StarSystem": "Sol"}, "Bocheaux", "Sol", None, {})
check(len(book.sightings("Gold")) == 1, "a market that trades none of them changes nothing")

# --- the Spansh refresh --------------------------------------------------------------------------------------------------------------------
saved["wntb_trade_lookups_enabled"] = False
check("lookups" in panel.refresh_blocker(), f"a refresh is refused with lookups off: {panel.refresh_blocker()!r}")
panel.refresh()
check(not panel.running and "lookups" in panel.status, f"and it says why: {panel.status!r}")

saved["wntb_trade_lookups_enabled"] = True
asked = []


def fake_refresh(names, reference, radius, **kwargs):
    asked.append((list(names), reference, radius))
    quote = lambda price: data.Quote(price, 300, "Far Away Port", "Sag A*", data.SPANSH, "2026-10-13T12:00:00Z", 55.0)   # noqa: E731
    return {name: data.Lookup((quote(8800), quote(8900)), (quote(9900),), reference, "2026-10-13T12:00:00Z") for name in names}, []


with mock.patch.object(trade_watch_lookup, "refresh", fake_refresh):
    check(panel.refresh_blocker() == "", f"a refresh can start: {panel.refresh_blocker()!r}")
    panel.refresh()
    check(wait_for(lambda: not panel.running), "the refresh finishes")
check(asked == [(["Gold", "Tritium"], "Sol", 100)], f"it asked about both commodities near the system: {asked}")
check(panel.summary()[0].splitlines()[0] == "Gold: buy 8,800 / sell 9,900", f"Spansh's better prices show: {panel.summary()}")
check(panel.summary()[0].splitlines()[1] == "Tritium: buy 8,800 / sell 9,900", "and for the other")
check("Updated from Spansh" in panel.status, f"the status says it worked: {panel.status!r}")


def failing_refresh(names, reference, radius, **kwargs):
    return {}, ["Gold: no network"]


with mock.patch.object(trade_watch_lookup, "refresh", failing_refresh):
    panel.refresh()
    check(wait_for(lambda: not panel.running), "a failing refresh finishes")
check("could not be reached" in panel.status, f"and says so: {panel.status!r}")
check(book.best_buy("Gold").price == 8800, "a failed refresh keeps the last answer")

# --- the row never gets wider ---------------------------------------------------------------------------------------------------------------
from plugin.trade_commodities import SUGGESTIBLE  # noqa: E402

for name in SUGGESTIBLE[:12]:
    if name not in book.watched():
        book.add(name)
panel.handle_event({"event": "Location", "StarSystem": "S" * 90}, "Bocheaux", "S" * 90, None, {})
panel.say("x" * 500)
pump()
lines = panel.summary()[0].splitlines()
check(len(lines) == trade_watch_panel._LINES_SHOWN + 1 and "more in the window" in lines[-1], f"only a few lines, then a count: {lines}")
check(len(panel._status_var.get()) <= 160, "the status is clipped")
# EDMC sizes its window to the widest row of every plugin: the open Watch list section must be no wider than the main panel is by default.
check(host.winfo_reqwidth() <= 216, f"the open Watch list section asks for {host.winfo_reqwidth()} px, wider than the main panel")

# --- the window ---------------------------------------------------------------------------------------------------------------------------
panel.say("")
trade_watch_window.show(root, book, panel)
win = trade_watch_window._window
pump()
check(win is not None and win.alive, "the window opens")
check(len(win._table) == book.count(), f"every watched commodity is listed: {len(win._table)} of {book.count()}")

win._entry.set("silver")
win._add()
check("Silver" in book.watched() and win._entry.get() == "", "adding a commodity from the box")
check(win._picked == "Silver", "the new commodity is picked")
win._entry.set("nonsense")
win._add()
check("not a commodity I know" in win._shell._status.cget("text"), f"an unknown name is refused: {win._shell._status.cget('text')!r}")
win._entry.set("gold")
win._add()
check("already" in win._shell._status.cget("text"), "a repeat is refused")

win._table.select("Gold", notify=True)
check(win._picked == "Gold" and len(win._seen) == 4,
      f"selecting shows the market seen and all three Spansh stations: {len(win._seen)}")
win._remove()
check("Gold" in book.watched() and "again" in win._shell._status.cget("text"), "the first press of Remove only asks")
win._remove()
check("Gold" not in book.watched() and book.sightings("Gold") == [], "the second press removes it and its prices")
win._remove()   # nothing is picked now: must do nothing and not raise

# a commander switch refreshes the open window; closing removes its listener
panel.handle_event({"event": "LoadGame"}, "Other Cmdr", "Sol", None, {})
pump()
check(len(win._table) == 0 and "Other Cmdr" in win._shell._subtitle.cget("text"), "another commander's window starts empty")
listeners = len(book._listeners)
trade_watch_window.close()
pump()
check(not win.alive and len(book._listeners) == listeners - 1, "closing the window removes its listener")
trade_watch_window.show(root, book, panel)
pump()
check(trade_watch_window._window.alive and trade_watch_window._window is not win, "it can be opened again")
trade_watch_window.close()

check(sorted(os.listdir(folder)) == [data.STATE_FILENAME], f"one data file, no commander name in a file name: {os.listdir(folder)}")

if problems:
    print("PROBLEMS:", len(problems))
    for line in problems:
        print(" -", line)
    sys.exit(1)
print("WATCH OK")
