"""Checks that every overlay card that shows a system (or a body named after one) has room to show the whole name: the longest procedural
system names run about 28 characters, so a 32-character one is drawn through each card's real layout and must come out without an ellipsis.
Run by test_system_name_room_smoke.py in a subprocess so the EDMC stand-ins never leak into other tests. Exits 0 if everything holds, 1 if not."""
import os
import sys
import types
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))


class Any(types.ModuleType):
    def __getattr__(self, n):
        if n.startswith("__"):
            raise AttributeError(n)
        return mock.MagicMock()


for n in ("monitor", "plug", "EDMCLogging", "l10n", "killswitch", "requests", "win32api", "win32con", "win32gui",
          "win32process", "win32clipboard", "pywintypes", "psutil", "ttkHyperlinkLabel", "myNotebook"):
    sys.modules[n] = Any(n)
sys.modules["ttkHyperlinkLabel"].HyperlinkLabel = mock.MagicMock()
theme = Any("theme")
theme.theme = mock.MagicMock()
theme.theme.active = None
theme.theme.THEME_DEFAULT = 0
sys.modules["theme"] = theme


class Cfg:
    default_journal_dir = ""

    def get_str(self, key, default=""):
        return default or ""

    def get_bool(self, key, default=False):
        return default

    def get_int(self, key, default=0):
        return default

    def get(self, key, default=None):
        return default

    def set(self, key, value):
        pass


cfgmod = types.ModuleType("config")
cfgmod.appname = "EDMarketConnector"
cfgmod.config = Cfg()
cfgmod.user_agent = "WNTB-test"
cfgmod.appversion = lambda: "5.13.0"
sys.modules["config"] = cfgmod

from plugin import body_info_overlay as BI  # noqa: E402
from plugin import exobiology_overlay as EX  # noqa: E402
from plugin import overlay_card as OC  # noqa: E402
from plugin import route_overlay as RO  # noqa: E402
from plugin import targets_overlay as TG  # noqa: E402
from plugin.overlay_style import LEGACY  # noqa: E402

SYSTEM = "Eorgh Prua XX-X d12-3456 AB"[:32]
BODY = f"{SYSTEM} 3 b a"
failures = []


def check(label, layout, card):
    cut = [t[0] for t in layout.plan(card, LEGACY)[1] if "…" in t[0]]
    if cut:
        failures.append(f"{label}: {cut}")


tracker = RO.RouteTracker(system=SYSTEM, jump_range=60.0)
tracker.route = [RO.Hop(SYSTEM, "N", (float(i), 0.0, 0.0)) for i in range(1, 6)]
check("Route rows", RO.LAYOUT, RO.build_card(tracker, 5))
check("Route expedition lines", RO.LAYOUT, RO.build_card(tracker, 5, expedition_lines=[(f"Next: {SYSTEM} / A 1 a   212 ly", "text"), (f"Reached stop 3: {SYSTEM}.", "ok")]))
check("Body info title", BI.LAYOUT, OC.Card(title=(BODY, "title"), badge="99,999 ls"))
check("System targets title", TG.LAYOUT, OC.Card(title=(SYSTEM, "title"), badge="12 of 20 scanned · 3 online"))
check("Bio signals title", EX.LAYOUT_LIST, OC.Card(title=(f"Bio signals {BODY}", "title"), badge="12 of 12 done"))
check("Bio popup title", EX.LAYOUT_POPUP, OC.Card(title=(f"Bio signals {BODY}", "title"), badge="12 of 12 done"))

if failures:
    print("\n".join(failures))
    sys.exit(1)
print("SYSTEM NAME ROOM OK")
