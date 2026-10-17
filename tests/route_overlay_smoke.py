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
from plugin import route_edsm as RE  # noqa: E402
from plugin import route_overlay as RO  # noqa: E402

problems = []


def check(condition, message):
    if not condition:
        problems.append(message)


def route_file(*stops):
    return {"Route": [{"StarSystem": n, "StarClass": c, "StarPos": [60.0 * i, 0.0, 0.0]} for i, (n, c) in enumerate(stops)]}


ROUTE = route_file(("Sol", "G"), ("Alpha", "M"), ("Beta", "N"), ("Gamma", "K"), ("Delta", "DA"), ("Epsilon", "H"), ("Zeta", "N"))


TRIP = [("Expedition: Colonia   2 of 5", "title"), ("Next: Sol / Earth   212 ly", "text"), ("Note: say hello", "muted")]


class World:
    def __init__(self, route=ROUTE, rows=3, enabled=True, trip=(), show_trip=True, edsm=False, lookup=None):
        self.at = 1000.0
        self.drawn = []
        self.file = route
        self.cfg = RO.RouteConfig(enabled=enabled, rows=rows, expedition=show_trip, edsm=edsm)
        self.trip = list(trip)
        self.asked = []

        def ask(names):
            self.asked.append(list(names))
            return lookup(names)
        checker = RE.EdsmChecker(lookup=ask, now=lambda: self.at, background=False) if lookup else None
        self.state = RO.RouteOverlay(draw=self.drawn.append, now=lambda: self.at, cfg=lambda: self.cfg, read=lambda: self.file,
                                     expedition=lambda: self.trip, edsm=checker)

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

# --- the active expedition on the card -----------------------------------------------------------------------------------------------------
w = World(trip=TRIP)
w.event("NavRoute", system="Sol")
card = w.drawn[-1]
check(list(card.header[-3:]) == TRIP, f"the expedition lines follow the status lines: {card.header}")
check([r[0] for r in card.rows][:1] == ["1. Alpha"], "and the route is still listed under them")
w.cfg.expedition = False
w.state.refresh()
check(all(t not in [x for x, _r in w.drawn[-1].header] for t, _r in TRIP), "the setting hides the expedition")
solo = World(route={"Route": []}, trip=TRIP)
solo.event("NavRoute", system="Sol")
check(bool(solo.drawn[-1]) and list(solo.drawn[-1].header[-3:]) == TRIP and not solo.drawn[-1].rows, f"an expedition with no route still draws a card: {solo.drawn[-1]}")
check(solo.state.showing(), "and keeps the tick running")
none = World(route={"Route": []})
none.event("NavRoute", system="Sol")
check(not none.state.showing() and not none.drawn, "no route and no expedition: nothing to show")

# a card with the most header lines still fits the card's ids
full = RO.Card(header=tuple(("line %d" % i, "text") for i in range(RO.MAX_HEADER)))
rec_full = None


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
    texts = {k: v for k, v in live.items() if k.startswith("wntb_route_x")}
    check(RO._X in {v[2] for v in texts.values()} and min(v[2] for v in texts.values()) == RO._X, "lines start at the card's left edge")
    check(RO._X - left == look.pad_x(S.CARD_PAD_X), "the text sits one standard padding in from the card's left border")
    check(min(v[3] for v in live.values()) - top == look.pad_y(S.CARD_PAD_Y), "and one standard padding below its top border")
    bottom = max(v[3] for v in live.values()) + look.line_px("normal")
    check(abs(top + height - bottom - look.pad_y(S.CARD_PAD_Y)) <= 1, f"and one padding above its bottom border ({top + height - bottom})")
    bad = [(v[0], v[2] + look.measured_width(v[0], "normal" if v[4] == look.size("normal") else "large"), left + width - look.pad_x(S.CARD_PAD_X)) for v in texts.values() if v[2] + look.measured_width(v[0], "normal" if v[4] == look.size("normal") else "large") > left + width - look.pad_x(S.CARD_PAD_X) + 1]
    check(not bad, f"every text, the right-aligned star column included, fits inside the card: {bad}")
    check({v[4] for v in texts.values()} <= {look.size("normal"), look.size("large")}, "only the normal and title sizes are used")

rec = Recorder()
RO.render(full, rec, S.LEGACY)
rec = Recorder()
RO.render(RO.Card(), rec, S.LEGACY)
check(rec.shapes[RO._CARD_ID][2:] == (0, 0) and all(v[0] == "" for v in rec.messages.values()), "an empty card clears everything")

# --- the EDSM check -------------------------------------------------------------------------------------------------------------------------------
UNKNOWN_TO_EDSM = {"Beta", "Delta"}


def edsm_world(**kwargs):
    world = World(rows=5, edsm=True, lookup=kwargs.pop("lookup", lambda names: {n: n not in UNKNOWN_TO_EDSM for n in names}), **kwargs)
    world.event("NavRoute", system="Sol")
    return world


w = edsm_world()
w.state.refresh()
card = w.state.card()
check(w.asked and "Alpha" in w.asked[0] and "Sol" not in w.asked[0], f"it asks about the systems ahead, not the one you are in: {w.asked}")
check([r[0] for r in card.rows][:4] == ["1. Alpha", "2. Beta *", "3. Gamma", "4. Delta *"], f"unknown systems get a mark: {card.rows}")
check(("* Not in EDSM yet: jumps 2, 4", "warn") in card.header, f"a line says which jumps: {card.header}")
check(len(w.asked) == 1, "it asks once for the whole list, and not again for answers it has")

w = edsm_world(lookup=lambda names: None)
w.state.refresh()
card = w.state.card()
check(not any(r[0].endswith("*") for r in card.rows), "a failed lookup marks nothing (could not tell is not unknown)")
check(("EDSM: could not check these systems", "muted") in card.header, f"it says it could not check: {card.header}")
asked = len(w.asked)
w.state.refresh()
check(len(w.asked) == asked, "it does not hammer EDSM after a failure")
w.at += RE.FAILED_RETRY_S + 1
w.state.refresh()
check(len(w.asked) == asked + 1, "it tries again after the pause")

w = edsm_world()
w.state.refresh()
before = len(w.asked)
w.at += RE.NOT_KNOWN_TTL_S - 1
w.state.refresh()
check(len(w.asked) == before, "an answer is kept until its time is up")
w.at += 2
w.state.refresh()
check(len(w.asked) == before + 1 and w.asked[-1] == ["Beta", "Delta"], f"systems EDSM did not know are asked about again after a while, and only those: {w.asked[-1]}")

w = World(rows=5, edsm=False, lookup=lambda names: {n: False for n in names})
w.event("NavRoute", system="Sol")
check(not w.asked and not any(r[0].endswith("*") for r in w.state.card().rows), "switched off, it asks nothing and marks nothing")

long_name = "Pru Aescs QN-S b" + "9-" * 6 + "1234"
w = World(route=route_file(("Sol", "G"), (long_name, "M")), rows=3, edsm=True, lookup=lambda names: {n: False for n in names})
w.event("NavRoute", system="Sol")
mark = [r[0] for r in w.state.card().rows][0]
check(mark.endswith(RO.NEW_MARK) and len(mark) <= RO.NAME_CHARS, f"a long name is cut so the mark fits: {mark!r}")

sample = RO.build_card(RO.sample_tracker(), 8, edsm=RE.sample_checker())
check([r[0].endswith(" *") for r in sample.rows][:8] == [False, False, True, False, False, False, True, False], f"the Test Card shows the mark on jumps 3 and 7: {sample.rows}")

# --- placement ----------------------------------------------------------------------------------------------------------------------------------
check("route" in P.SLOTS and P.SLOTS["route"].group == RO.GROUP_NAME, "the slot is registered with the card's group")

if problems:
    print("PROBLEMS:", len(problems))
    for p in problems:
        print(" -", p)
    sys.exit(1)
print("ROUTE OVERLAY OK")
