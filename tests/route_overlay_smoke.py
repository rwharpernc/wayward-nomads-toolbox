"""Exercises the Route overlay (plugin/route_overlay.py) with EDMC stubbed and the overlay, clock and route file injected: what the
card says, when it is redrawn, that every line starts at the card's left padding, and that the card clears off the route. Run by
test_route_overlay_smoke.py in a subprocess so the stand-ins never leak into other tests. Exits 0 if everything holds, 1 if not."""
import os
import sys
import types
from unittest import mock

repo = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, repo)


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

from plugin import fuel_alerts  # noqa: E402
from plugin import overlay_placement as P  # noqa: E402
from plugin import overlay_style as S  # noqa: E402
from plugin import route_overlay as RO  # noqa: E402

problems = []


def check(condition, message):
    if not condition:
        problems.append(message)


def route_file(*stops):
    return {"Route": [{"StarSystem": n, "StarClass": c, "StarPos": [60.0 * i, 0.0, 0.0]} for i, (n, c) in enumerate(stops)]}


ROUTE = route_file(("Sol", "G"), ("Alpha", "M"), ("Beta", "N"), ("Gamma", "K"), ("Delta", "DA"), ("Epsilon", "H"), ("Zeta", "N"))


class World:
    def __init__(self, route=ROUTE, rows=3, enabled=True):
        self.at = 1000.0
        self.drawn = []
        self.file = route
        self.cfg = RO.RouteConfig(enabled=enabled, rows=rows)
        self.state = RO.RouteOverlay(draw=self.drawn.append, now=lambda: self.at, cfg=lambda: self.cfg, read=lambda: self.file)

    def event(self, name, system=None, **fields):
        self.state.handle_event({"event": name, **fields}, system)


# --- a plotted route becomes a card ------------------------------------------------------------------------------------------------------
w = World()
w.event("Loadout", FuelCapacity={"Main": 32.0}, MaxJumpRange=61.4)
w.state.handle_status({"Flags": fuel_alerts.FLAG_IN_MAIN_SHIP, "Fuel": {"FuelMain": 12.2}})
w.event("NavRoute", system="Sol")
card = w.drawn[-1]
check(bool(card), "a plotted route draws a card")
check([r[0] for r in card.rows] == ["1. Alpha", "2. Beta", "3. Gamma"], f"the next three systems: {card.rows}")
check([r[1] for r in card.rows] == ["M", "NEUTRON", "K"], f"the star column: {card.rows}")
check(card.rows[1][2] == "info" and card.rows[0][2] == "muted", "a neutron star is picked out, an ordinary star is not")
texts = [t for t, _r in card.header]
check(texts[0].startswith("Fuel 38%") and "12.2 / 32 t" in texts[0], f"fuel line: {texts}")
check(any("Range 61.4 ly" in t for t in texts), f"range line: {texts}")
check(any(t.startswith("6 jumps left") and "ly" in t for t in texts), f"jumps left: {texts}")
check("Next supercharge: 2 jumps, neutron star" in texts, f"next supercharge: {texts}")
check(card.footer == ("+ 3 more (1 neutron, 1 white dwarf)", "muted"), f"the rest are counted by kind: {card.footer}")

# --- progress along the route, then off it -------------------------------------------------------------------------------------------------
w.event("FSDJump", system="Alpha", StarSystem="Alpha", FuelUsed=3.2)
check(w.drawn[-1].rows[0][0] == "1. Beta", f"the list moves on after a jump: {w.drawn[-1].rows}")
check(any("Last jump 3.2 t" in t for t, _r in w.drawn[-1].header), "the fuel the last jump used")
w.event("FSDJump", system="Beta", StarSystem="Beta", FuelUsed=3.0)
check("Next supercharge: 2 jumps, white dwarf" in [t for t, _r in w.drawn[-1].header], f"{w.drawn[-1].header}")
w.event("FSDJump", system="Somewhere Else", StarSystem="Somewhere Else", FuelUsed=3.0)
check(not w.drawn[-1], "off the route the card clears")
w.event("NavRouteClear", system="Somewhere Else")
check(not w.drawn[-1], "a cleared route stays cleared")

# --- off, redraw rate --------------------------------------------------------------------------------------------------------------------------
off = World(enabled=False)
off.event("NavRoute", system="Sol")
check(off.drawn == [], "nothing is drawn while the overlay is off")
w = World()
w.event("NavRoute", system="Sol")
count = len(w.drawn)
w.state.refresh()
check(len(w.drawn) == count, "an unchanged card is not redrawn at once")
w.at += RO.RESEND_S + 0.1
w.state.refresh()
check(len(w.drawn) == count + 1, "an unchanged card is redrawn now and then so it does not expire")


# --- drawing: left-justified, one padding ------------------------------------------------------------------------------------------------------
class Recorder:
    def __init__(self):
        self.shapes, self.messages = {}, {}

    def send_shape(self, shape_id, shape, color, fill, x, y, w_, h, ttl=8, thickness=None):
        self.shapes[shape_id] = (x, y, w_, h)

    def send_message(self, msg_id, text, color, x, y, ttl=8, size="normal"):
        self.messages[msg_id] = (text, color, x, y, size)


for look in (S.LEGACY, S.DEFAULT, S.look_from_choices("Ice blue", 1, 6, 3)):
    rec = Recorder()
    RO.render(RO.build_card(RO.sample_tracker(), 8), rec, look)
    left, top, width, height = rec.shapes[RO._CARD_ID]
    live = {k: v for k, v in rec.messages.items() if v[0]}
    lefts = {v[2] for k, v in live.items() if not k.startswith("wntb_route_t")}
    check(lefts == {RO._X}, f"every line and system name starts at the same left edge: {lefts}")
    check(RO._X - left == look.pad_x(S.CARD_PAD_X), "the text sits one standard padding in from the card's left border")
    check(min(v[3] for v in live.values()) - top == look.pad_y(S.CARD_PAD_Y), "and one standard padding below its top border")
    bottom = max(v[3] for v in live.values()) + look.line_px("normal")
    check(abs(top + height - bottom - look.pad_y(S.CARD_PAD_Y)) <= 1, f"and one padding above its bottom border ({top + height - bottom})")
    tags = [v for k, v in live.items() if k.startswith("wntb_route_t")]
    check(all(v[2] + look.measured_width(v[0], "normal") <= left + width - look.pad_x(S.CARD_PAD_X) for v in tags),
          "the star column fits inside the card")
    check(all(v[4] == look.size("normal") for v in live.values()), "one text size throughout")

rec = Recorder()
RO.render(RO.Card(), rec, S.LEGACY)
check(rec.shapes[RO._CARD_ID][2:] == (0, 0) and all(v[0] == "" for v in rec.messages.values()), "an empty card clears everything")

# --- placement ----------------------------------------------------------------------------------------------------------------------------------
check("route" in P.SLOTS and P.SLOTS["route"].group == RO.GROUP_NAME, "the slot is registered with the card's group")

if problems:
    print("PROBLEMS:", len(problems))
    for p in problems:
        print(" -", p)
    sys.exit(1)
print("ROUTE OVERLAY OK")
