"""Exercises the Flight Alerts controller (plugin/flight_alerts.py) with EDMC stubbed and the overlay, clock and sound injected: what
the card says, when it is redrawn, when a sound plays, and that the card's top stays put as its lines change. Run by
test_flight_alerts_smoke.py in a subprocess so the stand-ins never leak into other tests. Exits 0 if everything holds, 1 if not."""
import os
import sys
import types
from datetime import datetime, timezone
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

from plugin import flight_alerts as FA  # noqa: E402
from plugin import overlay_placement as P  # noqa: E402
from plugin import overlay_style as S  # noqa: E402

problems = []


def check(condition, message):
    if not condition:
        problems.append(message)


NOW = datetime(2026, 10, 13, 12, 0, 0, tzinfo=timezone.utc).timestamp()


class World:
    """The injected clock, overlay and sound."""

    def __init__(self, **cfg):
        self.at = NOW
        self.drawn = []
        self.beeps = 0
        self.cfg = FA.FlightConfig(enabled=True, sound=False, **cfg)
        self.alerts = FA.FlightAlerts(draw=self.drawn.append, beep=self.beep, now=lambda: self.at, cfg=lambda: self.cfg)

    def beep(self):
        self.beeps += 1

    def request(self, minutes):
        stamp = datetime.fromtimestamp(NOW + minutes * 60, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        self.alerts.handle_event({"event": "CarrierJumpRequest", "SystemName": "Sol", "Body": "Earth", "DepartureTime": stamp})

    def status(self, fuel, flags=FA.fuel_alerts.FLAG_IN_MAIN_SHIP):
        self.alerts.handle_status({"Flags": flags, "Fuel": {"FuelMain": fuel}})

    def loadout(self, capacity=32.0):
        self.alerts.handle_event({"event": "Loadout", "FuelCapacity": {"Main": capacity}})


# --- the card says what the watchers say ------------------------------------------------------------------------------------------------
w = World()
w.request(15)
check(w.drawn and w.drawn[-1] == [("Carrier jumps to Sol (Earth) in 15:00", FA.COLOR_AMBER)], f"countdown line: {w.drawn}")
w.at = NOW + 15 * 60 - 45
w.alerts.refresh()
check(w.drawn[-1][0][1] == FA.COLOR_RED and "0:45" in w.drawn[-1][0][0], f"the last minute is red: {w.drawn[-1]}")
check(w.alerts.ticking(), "a planned jump is ticking")
w.alerts.handle_event({"event": "CarrierJumpCancelled"})
check(w.drawn[-1] == [], f"a cancel clears the card: {w.drawn[-1]}")
check(not w.alerts.ticking(), "nothing planned, nothing to tick")

w = World()
w.loadout()
w.status(8.0)
w.alerts.handle_event({"event": "FSDTarget", "Name": "Col 70 Sector", "StarClass": "N"})
texts = [t for t, _c in w.drawn[-1]]
check(len(texts) == 2 and texts[0].startswith("Low fuel: 25%") and "neutron star" in texts[1], f"fuel lines: {texts}")
colors = [c for _t, c in w.drawn[-1]]
check(colors == [FA.COLOR_RED, FA.COLOR_AMBER], f"fuel colors: {colors}")

# --- off means off; the options pick what shows ------------------------------------------------------------------------------------------
w = World()
w.cfg.enabled = False
w.request(5)
w.loadout()
w.status(2.0)
check(w.drawn == [], f"nothing is drawn while disabled: {w.drawn}")

w = World(carrier=False)
w.request(5)
check(w.drawn == [], "carrier countdown off: nothing drawn")
w = World(fuel=False)
w.loadout()
w.status(2.0)
check(w.drawn == [], "fuel warnings off: nothing drawn")

# --- redrawing: only on a change, or now and then so the card does not expire ---------------------------------------------------------------
w = World()
w.loadout()
w.status(8.0)
count = len(w.drawn)
w.status(8.0)
check(len(w.drawn) == count, "an unchanged card is not redrawn at once")
w.at += FA.RESEND_S + 0.1
w.status(8.0)
check(len(w.drawn) == count + 1, "an unchanged card is redrawn after a few seconds")
w.status(40.0)    # a full tank: the alert ends
check(w.drawn[-1] == [], "the card clears when the alert ends")
count = len(w.drawn)
w.status(40.0)
check(len(w.drawn) == count, "an empty card is not redrawn while nothing is shown")

# --- sound: once per alert, and fuel alerts can sound again after they have ended ------------------------------------------------------
w = World()
w.cfg.sound = True
w.loadout()
w.status(8.0)
check(w.beeps == 1, f"low fuel sounds once: {w.beeps}")
w.status(7.5)
check(w.beeps == 1, f"still low, no second sound: {w.beeps}")
w.status(40.0)
w.status(8.0)
check(w.beeps == 2, f"after a refuel it sounds again: {w.beeps}")

w = World()
w.cfg.sound = True
w.request(15)
check(w.beeps == 0, "a fresh 15-minute jump has no alert yet")
for seconds_in, expected in ((300, 1), (301, 1), (840, 2), (900, 3), (905, 3)):
    w.at = NOW + seconds_in
    w.alerts.refresh()
    check(w.beeps == expected, f"carrier sound at +{seconds_in}s: {w.beeps} (want {expected})")

w = World()
w.request(5)
w.at = NOW + 200
w.alerts.refresh()
check(w.beeps == 0, "no sound when sound is off")

# --- the card is sized from its text and its top does not move as lines change ------------------------------------------------------------------
look = S.LEGACY
one = FA.block_rect(look, FA.SAMPLE_LINES[:1])
three = FA.block_rect(look, FA.SAMPLE_LINES[:3])
check(one[:2] == three[:2], "the card's top left is the same whatever the number of lines")
check(three[3] > one[3], "more lines make a taller card")
check(FA.block_rect(look)[:2] == three[:2] and FA.block_rect(look)[2:] == three[2:], "placement uses a three-line card")
check("flight_alerts" in P.SLOTS and P.SLOTS["flight_alerts"].group == FA.GROUP_NAME, "the slot is registered with the card's group")


class Rec:
    def __init__(self):
        self.shapes, self.messages = {}, {}

    def send_message(self, msg_id, text, color, x, y, ttl=8, size="normal"):
        self.messages[msg_id] = text

    def send_shape(self, shape_id, shape, color, fill, x, y, w, h, ttl=8, thickness=None):
        self.shapes[shape_id] = (color, w, h)


rec = Rec()
FA.render(FA.SAMPLE_LINES[:2], rec, look)
check(rec.shapes[FA._CARD_ID][0] == FA.BORDER_AMBER, "no red line: amber border")
check([rec.messages[i] for i in FA._LINE_IDS[:2]] == [t for t, _c in FA.SAMPLE_LINES[:2]], f"two lines drawn: {rec.messages}")
check(rec.messages[FA._LINE_IDS[2]] == "" and rec.messages[FA._LINE_IDS[3]] == "", "unused lines are blanked")
rec = Rec()
FA.render(FA.SAMPLE_LINES, rec, look)
check(rec.shapes[FA._CARD_ID][0] == FA.BORDER_RED, "a red line makes the border red")
rec = Rec()
FA.render([], rec, look)
check(rec.shapes[FA._CARD_ID][1:] == (0, 0) and all(rec.messages[i] == "" for i in FA._LINE_IDS), "no lines clears the card")
check(len(FA.SAMPLE_LINES) <= FA.MAX_LINES, "the sample fits the card")

# --- start-up: a jump planned before WNTB started is read back ------------------------------------------------------------------------------------
w = World()
with mock.patch.object(FA.jump_timer, "recover", side_effect=lambda timer, since, folder=None: timer.handle_event(
        {"event": "CarrierJumpRequest", "SystemName": "Colonia", "DepartureTime": "2026-10-13T12:09:00Z"})) as recover:
    w.alerts.handle_event({"event": "LoadGame"})
    w.alerts.handle_event({"event": "LoadGame"})
check(recover.call_count == 1, f"the journals are read once per session: {recover.call_count}")
check(w.drawn and "Colonia" in w.drawn[-1][0][0], f"the recovered jump shows: {w.drawn[-1:]}")

if problems:
    print("PROBLEMS:", len(problems))
    for line in problems:
        print(" -", line)
    sys.exit(1)
print("FLIGHT ALERTS OK")
