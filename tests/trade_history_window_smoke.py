"""Opens the real Trade History window (plugin/trade_history_window.py) with EDMC stubbed, visits every tab, and checks
that nothing is clipped at the window's minimum size, that Delete / Copy / commander filtering behave, and that an
empty history shows its message. Run by test_trade_history_window_smoke.py in a subprocess so the stand-ins never leak
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

from plugin import trade_history as H, trade_history_window as W, trade_ledger as L
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


A = ("Col 285 Sector HB-M a37-3", "Goonan Platform")
B = ("Pegasi Sector BL-W b2-4", "Broutsos Industrial Moulding")


def buy(name, count, price, stamp):
    return {"event": "MarketBuy", "Type": name.lower(), "Type_Localised": name, "Count": count, "BuyPrice": price,
            "TotalCost": count * price, "timestamp": stamp}


def sell(name, count, price, paid, stamp):
    return {"event": "MarketSell", "Type": name.lower(), "Type_Localised": name, "Count": count, "SellPrice": price,
            "TotalSale": count * price, "AvgPricePaid": paid, "timestamp": stamp}


def session(cmdr, start, credits_start):
    ledger = L.new_ledger(cmdr, f"Journal.{cmdr}.log", started=start, credits=credits_start)
    L.apply_trade_event(ledger, buy("Superconductors", 1265, 5655, "2026-10-09T10:12:08Z"), A)
    L.apply_trade_event(ledger, {"event": "RefuelAll", "Cost": 10, "timestamp": "2026-10-09T10:15:00Z"}, A)
    L.note_jump(ledger, {"event": "FSDJump", "JumpDist": 31.2})
    L.apply_trade_event(ledger, sell("Superconductors", 1265, 6979, 5655, "2026-10-09T10:40:00Z"), B)
    L.add_route(ledger, {"t": "2026-10-09T10:05:00Z", "start": "Goonan Platform", "total": 5, "hops": [{"from": "X", "to": "Y"}]})
    L.add_search(ledger, {"t": "2026-10-09T10:20:00Z", "side": "buy", "commodity": "Gold", "tonnes": 10, "scope": "galaxy", "best": None})
    return H.build_record(
        ledger, cmdr, ship="Panther Clipper Mk II", pad="large", credits_end=credits_start + 5_000_000,
        stock=[{"name": "Gold", "tonnes": 5, "cost": 500}], hold=[{"name": "Gold", "tonnes": 5}], capacity=1265,
        carriers=[{"type": "Fleet carrier", "name": "ELDER WARDEN", "capacity": 23720, "cargo": 5060, "free": 18660,
                   "reserved": 0}], saved_at="2026-10-09T11:00:00Z")


book = H.HistoryBook()
book.save(session("Bocheaux", "2026-10-09T05:36:05Z", 1_000_000))
book.save(session("Mactavious", "2026-10-08T20:00:00Z", 2_000_000))
changed = []
W.show(root, book, lambda: changed.append(1))
window = W._window
check(window is not None and window.alive, "the window did not open")
top = window._toplevel
top.geometry(f"{W.MIN_WIDTH}x{W.MIN_HEIGHT + 100}+20+20")
root.update()
width = top.winfo_width()

for index in range(7):
    window._tabs.select(index)
    for _ in range(4):
        root.update()
    for table in tables(window._tabs):
        if table.winfo_ismapped():
            # The table sits inside the window's padding, the tab's padding and a scrollbar: allow for them.
            room = width - 80
            check(table.winfo_reqwidth() <= room,
                  f"tab {index}: a table asks for {table.winfo_reqwidth()}px where only {room}px is free")

# The picker lists both sessions, newest first.
check(len(window._session_box._values) == 2, "the picker should list both sessions")
check("Bocheaux" in window._session_box._values[0], "the newest session should be first")
window._tabs.select(1)
root.update()
shown = [t for t in tables(window._tabs) if t.winfo_ismapped()]
check(shown and len(shown[0]) == 1, "the Commodities table should have one row")

# The commander filter narrows the list; it is shown because there are two commanders.
check(window._cmdr_box.winfo_ismapped(), "the commander filter should be visible with two commanders")
window._cmdr_var.set("Mactavious")
window._on_commander_selected()
root.update()
check(len(window._session_box._values) == 1 and "Mactavious" in window._session_box._values[0],
      "the filter did not narrow the list")
window._cmdr_var.set(W.ALL_COMMANDERS)
window._on_commander_selected()

# Copy puts the summary on the clipboard.
window._on_copy()
root.update()
check("Net profit" in root.clipboard_get(), "Copy summary did not put the summary on the clipboard")

# Delete asks first, removes the session, calls back, and shows the next one.
with mock.patch("plugin.trade_history_window.messagebox.askyesno", return_value=False):
    window._on_delete()
check(len(book.sessions) == 2 and not changed, "declining the confirmation must not delete")
with mock.patch("plugin.trade_history_window.messagebox.askyesno", return_value=True):
    window._on_delete()
root.update()
check(len(book.sessions) == 1 and changed, "deleting should remove the session and call back")
with mock.patch("plugin.trade_history_window.messagebox.askyesno", return_value=True):
    window._on_delete()
root.update()
check(not book.sessions, "the last session should delete too")
check(window._empty.winfo_ismapped(), "an empty history should show its message")
check(not window._tabs.winfo_ismapped(), "an empty history should not show the tabs")

# A save while the window is open refreshes it and selects the new session.
book.save(session("Bocheaux", "2026-10-09T05:36:05Z", 1_000_000))
W.refresh_if_open(book, select=book.sessions[0]["id"])
root.update()
check(window._tabs.winfo_ismapped() and not window._empty.winfo_ismapped(), "the window should refresh when a session is saved")

window.close()
root.destroy()
if problems:
    print("PROBLEMS:\n  " + "\n  ".join(problems))
    sys.exit(1)
print("TRADE HISTORY WINDOW OK")
