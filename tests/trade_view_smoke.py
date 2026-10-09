"""Draws Trade mode's page (plugin/trade_view.py) with EDMC stubbed, in a real Tk window, and checks the layout
rules that matter on EDMC's narrow main window. Run by test_trade_view_smoke.py in a subprocess so the stand-ins
never leak into other tests. Exits 0 if everything holds, 1 if not, 77 if Tk is unavailable."""
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


class Cfg:
    default_journal_dir = ""
    def get_str(self, key, default=""): return default or ""
    def get_bool(self, key, default=False): return default
    def get_int(self, key, default=0): return default
    def get(self, key, default=None): return default
    def set(self, key, value): pass


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

from plugin.trade_blocks import Columns, Heading, Item, Note, Pair
from plugin.trade_view import BlockView

problems = []


def check(condition, message):
    if not condition:
        problems.append(message)


def labels_of(widget):
    found = []
    for child in widget.winfo_children():
        if isinstance(child, tk.Label):
            found.append(child)
        found += labels_of(child)
    return found


WIDTH = 330
holder = tk.Frame(root, width=WIDTH)
holder.pack()
holder.pack_propagate(False)
holder.configure(height=600)
view = BlockView(holder)
view.pack(fill="x")
root.update()

LONG = "A very long station name that must wrap instead of widening the window " * 2
blocks = [
    Heading("Buying Superconductors"),
    Pair("Amount", "1,265 t · large pad", bold=True),
    Heading("Near me, within 100 ly"),
    Columns(("cr/t", "Total", "ly")),
    Item(LONG, ("5,312", "6,719,680,000", "148.3"), detail=LONG + " · orbital Coriolis Starport, 292 ls", warn="Only 6 t in stock"),
    Heading("Fleet carriers (they can move)", minor=True),
    Item("XBF-94W", ("6,551", "8,287,015", "293.6"), detail="carrier"),
    Pair("A label that is quite long and has to wrap too", "+18,096,412 cr (+19,093,518 cr/hr)", bold=True),
    Pair("Best", "+400,000 cr on 20 t", indent=1),
    Note("Best overall is nearby: Velidhu Dream (Zeta Tucanae).", strong=True),
    Note("A fleet carrier is 100 cr/t cheaper than the best station (it can move).", warn=True),
]
view.show(blocks)
root.update()
root.update_idletasks()

check(len(labels_of(view)) > 15, "the page drew no labels")
widest = max(label.winfo_reqwidth() for label in labels_of(view))
check(widest <= WIDTH, f"a label asks for {widest}px, wider than the {WIDTH}px available")
check(view.winfo_reqwidth() <= WIDTH + 4, f"the page asks for {view.winfo_reqwidth()}px, wider than the {WIDTH}px available")
for label in labels_of(view):
    check(int(label.cget("wraplength")) <= WIDTH, f"{label.cget('text')[:30]!r} wraps at {label.cget('wraplength')}px")

# Unchanged blocks are not redrawn; changed ones are.
before = list(view.winfo_children())
view.show(list(blocks))
check(list(view.winfo_children()) == before, "identical blocks were redrawn")
view.show(blocks[:3])
check(list(view.winfo_children()) != before, "changed blocks were not redrawn")

# Every block type on its own, and an empty page.
for block in blocks:
    view.show([block])
view.show([])
check(not view.winfo_children(), "an empty page left widgets behind")

# The number columns line up: the 3 cells of two rows sit at the same x.
view.show([Columns(("cr/t", "Total", "ly")), Item("One", ("1", "22", "3.0")), Item("Two", ("4,444", "55,555,555", "66.6"))])
root.update()
rows = {}
for label in labels_of(view):
    rows.setdefault(label.cget("text"), label)
for a, b in (("1", "4,444"), ("22", "55,555,555"), ("3.0", "66.6")):
    check(rows[a].winfo_x() + rows[a].winfo_width() == rows[b].winfo_x() + rows[b].winfo_width(),
          f"column of {a!r} and {b!r} do not end at the same place")

root.destroy()
if problems:
    print("PROBLEMS:\n  " + "\n  ".join(problems))
    sys.exit(1)
print("TRADE VIEW OK")
