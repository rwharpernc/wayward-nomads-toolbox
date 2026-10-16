"""Exercises the System targets card, the Body info card and the shared card layout (plugin/targets_overlay.py, body_info_overlay.py, overlay_card.py)
with EDMC stubbed and the overlay and clock injected: what the cards say, that every line starts at the card's left padding, how the redraw timing works,
which body the Body info card picks, and that the cards clear. Run by test_system_cards_smoke.py in a subprocess so the stand-ins never leak into other
tests. Exits 0 if everything holds, 1 if not."""
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

from plugin import body_info_overlay as BI  # noqa: E402
from plugin import overlay_card as OC  # noqa: E402
from plugin import overlay_placement as P  # noqa: E402
from plugin import overlay_style as S  # noqa: E402
from plugin import system_survey as SS  # noqa: E402
from plugin import targets_overlay as TO  # noqa: E402

problems = []


def check(condition, message):
    if not condition:
        problems.append(message)


SYSTEM = "Test Sector AB-C d1"


def build_survey():
    survey = SS.SystemSurvey()
    survey.handle_event({"event": "FSDJump", "StarSystem": SYSTEM, "SystemAddress": 99})
    survey.handle_event({"event": "FSSDiscoveryScan", "Progress": 0.5, "BodyCount": 8, "SystemName": SYSTEM})
    rows = [(1, "A 1", "Earthlike body", 1.0, "Terraformable", False), (2, "A 2", "Water world", 1.0, "", True), (3, "A 3", "Icy body", 0.1, "", True),
            (4, "B 1", "Rocky body", 0.05, "", True)]
    for number, short, planet_class, mass, terraform, discovered in rows:
        survey.handle_event({"event": "Scan", "BodyName": f"{SYSTEM} {short}", "BodyID": number, "StarSystem": SYSTEM, "PlanetClass": planet_class, "MassEM": mass,
                             "TerraformState": terraform, "WasDiscovered": discovered, "WasMapped": False, "SurfaceGravity": 4.9, "SurfaceTemperature": 150.0,
                             "SurfacePressure": 600.0, "Landable": True, "DistanceFromArrivalLS": 1200.0, "Atmosphere": "thin carbon dioxide atmosphere",
                             "Materials": [{"Name": "iron", "Percent": 20.0}, {"Name": "sulphur", "Percent": 15.0}]})
    survey.handle_event({"event": "FSSBodySignals", "BodyName": f"{SYSTEM} B 1", "BodyID": 4, "Signals": [{"Type": SS.BIO_TYPE, "Count": 2}]})
    return survey


# --- System targets: what the card says -----------------------------------------------------------------------------------------
survey = build_survey()
card = TO.build_card(survey, 100_000, 6, True)
texts = [r[0] for r in card.rows]
check(card.title and card.title[0] == SYSTEM and card.badge == "4 of 8 scanned" and card.progress == 0.5, f"the title, scan count and progress: {card.title} {card.badge} {card.progress}")
check(texts[0] == "To map (1)" or texts[0].startswith("To map ("), f"a To map section comes first: {texts}")
check(any(t.startswith("A 1") and "ELW" in t for t in texts), f"the Earthlike world is listed with its tag: {texts}")
check(any(r[0] == "B 1" and r[1] == "0/2 life" for r in card.rows), f"the body with life is listed with its progress: {card.rows}")
check(not any(r[0].startswith("A 3") for r in card.rows), "a body under the threshold is not listed")
first = next(r for r in card.rows if r[0].startswith("A 1"))
check(first[1].endswith("first") and first[2] == "title", f"an undiscovered body is marked and picked out: {first}")

no_life = TO.build_card(survey, 100_000, 6, False)
check(not any("life" in r[1] for r in no_life.rows), "the life list can be turned off")

survey.handle_event({"event": "SAAScanComplete", "BodyName": f"{SYSTEM} A 1", "BodyID": 1})
check(not any(r[0].startswith("A 1") for r in TO.build_card(survey, 100_000, 6, True).rows), "mapping a body removes it from the list")
survey.handle_event({"event": "ScanOrganic", "ScanType": "Analyse", "Genus_Localised": "Bacterium", "Body": 4})
survey.handle_event({"event": "ScanOrganic", "ScanType": "Analyse", "Genus_Localised": "Osseus", "Body": 4})
check(not any(r[0] == "B 1" for r in TO.build_card(survey, 100_000, 6, True).rows), "analysing every organism removes the body")
done = TO.build_card(survey, 10_000_000, 6, True)
check(done.header[-1][0] == "Nothing over 10.0M to map yet" and not done.rows, f"nothing above the threshold, and it names the threshold: {done.header}")
survey.handle_event({"event": "FSSAllBodiesFound", "SystemName": SYSTEM, "Count": 4})
check(TO.build_card(survey, 10_000_000, 6, True).header[-1][0] == "Nothing over 10.0M left to map or sample", "and with the scan complete it says so")

survey = build_survey()
small = TO.build_card(survey, 0, 3, True)
check(len(small.rows) <= 3 and small.footer is not None and small.footer[0].startswith("+ "), f"rows are capped and the rest counted: {small.rows} {small.footer}")

check(not TO.build_card(SS.SystemSurvey(), 0, 6, True), "an empty survey draws nothing")
unhonked = SS.SystemSurvey()
unhonked.handle_event({"event": "FSDJump", "StarSystem": SYSTEM})
check(not TO.build_card(unhonked, 0, 6, True), "and so does a system with nothing scanned or honked")
survey.handle_event({"event": "StartJump", "JumpType": "Hyperspace"})
check(not TO.build_card(survey, 0, 6, True), "and the card is hidden while jumping")

# --- Body info: which body, and what the card says -----------------------------------------------------------------------------------
survey = build_survey()
cfg = BI.BodyInfoConfig(enabled=True)
check(BI.pick_body(survey, {"Destination": {"System": 99, "Body": 2, "Name": f"{SYSTEM} A 2"}}, cfg).short == "A 2", "the targeted body is picked")
check(BI.pick_body(survey, {"Destination": {"System": 12345, "Body": 2}}, cfg) is None, "a destination in another system is not")
check(BI.pick_body(survey, {"BodyName": f"{SYSTEM} A 3"}, cfg).short == "A 3", "the body the ship is close to is picked")
check(BI.pick_body(survey, {"Destination": {"Body": 2}, "BodyName": f"{SYSTEM} A 3"}, cfg).short == "A 2", "the target wins over the nearby body")
check(BI.pick_body(survey, {"BodyName": f"{SYSTEM} A 3"}, BI.BodyInfoConfig(enabled=True, near=False)) is None, "the nearby body can be turned off")
check(BI.pick_body(survey, {"Destination": {"Body": 2}}, BI.BodyInfoConfig(enabled=True, targeted=False)) is None, "and so can the target")
check(BI.pick_body(survey, {}, cfg) is None, "no target and no body nearby: no card")
unscanned_target = BI.pick_body(survey, {"Destination": {"System": 99, "Body": 77, "Name": f"{SYSTEM} Z 9"}}, cfg)
check(unscanned_target is not None and not unscanned_target.scanned and unscanned_target.short == "Z 9", "a targeted body that has not been scanned is still picked, as one to scan")
check(BI.build_card(unscanned_target).header[0][0] == "Scan required", "and its card says to scan it")

body = survey.bodies[1]
info = BI.build_card(body)
check(info.title[0] == f"{SYSTEM} A 1" and info.header[0][0] == "Earthlike body", f"name and class: {info.header}")
check(any("Terraformable" in t and "Unmapped" in t for t, _r in info.header), f"flags: {info.header}")
rows = {r[0]: r for r in info.rows}
check("Scan value" in rows and rows["Scan value"][1].endswith(" first"), f"the scan value is shown, marked as a first discovery: {rows.get('Scan value')}")
check(rows["Gravity"][1] == "0.50 g" and rows["Gravity"][2] == "text", f"gravity: {rows['Gravity']}")
heavy = SS.Body(9, "Heavy", "H", "planet", "Rocky body", gravity_g=2.5, scanned=True)
check(dict((r[0], r) for r in BI.build_card(heavy).rows)["Gravity"][2] == "warn", "high gravity is in the warning color")
unscanned = BI.build_card(SS.Body(10, "Mystery", "M", bio=2))
check(unscanned.title[0] == "Mystery" and [h[0] for h in unscanned.header] == ["Scan required", "2 life signals"] and not unscanned.rows, f"an unscanned body: {unscanned.header}")
check(not BI.build_card(None), "no body, no card")

online = SS.SystemSurvey()
online.handle_event({"event": "FSDJump", "StarSystem": SYSTEM, "SystemAddress": 99})
online.handle_event({"event": "FSSDiscoveryScan", "Progress": 1.0, "BodyCount": 5})
online.merge_known(SYSTEM, [{"bodyId": 3, "name": f"{SYSTEM} B 2", "type": "Planet", "subType": "Earth-like world", "earthMasses": 1.0,
                             "distanceToArrival": 500.0, "terraformingState": "Not terraformable"}])
known_card = TO.build_card(online, 100_000, 6, True)
check("1 online" in known_card.badge, f"the card says how many bodies came from the lookup: {known_card.badge}")
check(known_card.rows and "EDSM" in known_card.rows[1][0] and "ELW" in known_card.rows[1][0], f"a looked-up body is tagged and marked: {known_card.rows}")
many = SS.SystemSurvey()
many.handle_event({"event": "FSDJump", "StarSystem": SYSTEM, "SystemAddress": 99})
many.handle_event({"event": "Scan", "BodyName": f"{SYSTEM} A 1", "BodyID": 1, "StarSystem": SYSTEM, "PlanetClass": "Rocky body", "MassEM": 0.1})
many.handle_event({"event": "SAASignalsFound", "BodyID": 1, "Signals": [{"Type": SS.BIO_TYPE, "Count": 5}],
                   "Genuses": [{"Genus_Localised": g} for g in ("Bacterium", "Frutexa", "Tussock", "Fungoida", "Osseus")]})
for look in (S.LEGACY, S.DEFAULT):
    for label, layout, card in (("targets", TO.LAYOUT, TO.build_card(many, 0, 8, True)), ("body info", BI.LAYOUT, BI.build_card(many.bodies[1]))):
        shown = " ".join(t[0] for t in layout.plan(card, look)[1])
        check(all(g in shown for g in ("Bacterium", "Frutexa", "Tussock", "Fungoida", "Osseus")) and "…" not in shown, f"{label}: every genus is shown in full: {shown}")
ff_body = BI.sample_body()
check(any("First footfall" in h[0] for h in BI.build_card(ff_body).header), "the Body info card flags a first footfall")
check(any(r[0] == "Footfall" and "5x" in r[1] for r in BI.build_card(ff_body).rows), "and says exobiology pays five times there")
ff_body.was_footfalled = True
check(not any("First footfall" in h[0] for h in BI.build_card(ff_body).header), "a footfalled body is not flagged")
ff_survey = TO.sample_survey()
check(any(r[1].endswith("FF") for r in TO.build_card(ff_survey, 400_000, 16, True).rows), "System targets marks a body with life where the first footfall is still open")
known_info = BI.build_card(online.bodies[3])
check(known_info.header[0][0] == "Earthlike body" and any("EDSM" in h[0] for h in known_info.header), f"Body info says it came from EDSM: {known_info.header}")

# --- drawing: every line starts at the same left edge, one padding ---------------------------------------------------------------------
class Recorder:
    def __init__(self):
        self.shapes, self.messages = {}, {}

    def send_shape(self, shape_id, shape, color, fill, x, y, w, h, ttl=8, thickness=None):
        self.shapes[shape_id] = (x, y, w, h)

    def send_message(self, msg_id, text, color, x, y, ttl=8, size="normal"):
        self.messages[msg_id] = (text, color, x, y, size)


for label, layout, render, build in (("targets", TO.LAYOUT, TO.render, lambda: TO.build_card(TO.sample_survey(), 0, 8, True)),
                                     ("body info", BI.LAYOUT, BI.render, lambda: BI.build_card(BI.sample_body()))):
    for look in (S.LEGACY, S.DEFAULT):
        rec = Recorder()
        render(build(), rec, look)
        left, top, width, height = rec.shapes[layout.card_id]
        live = {k: v for k, v in rec.messages.items() if v[0]}
        check(live, f"{label}: something was drawn")
        texts = {k: v for k, v in live.items() if k.startswith(layout.prefix + "x")}
        check(min(v[2] for v in texts.values()) == layout.x and all(v[2] >= layout.x for v in texts.values()), f"{label}: lines start at the card's left edge")
        check(sum(1 for v in texts.values() if v[2] == layout.x) >= 2, f"{label}: the first column is left-aligned")
        check(layout.x - left == look.pad_x(S.CARD_PAD_X), f"{label}: one standard padding at the left")
        check(min(v[3] for v in live.values()) - top == look.pad_y(S.CARD_PAD_Y), f"{label}: and at the top")
        bottom = max(v[3] for v in live.values()) + look.line_px("normal")
        check(abs(top + height - bottom - look.pad_y(S.CARD_PAD_Y)) <= 1, f"{label}: and at the bottom ({top + height - bottom})")
        check(all(v[2] + look.measured_width(v[0], "normal" if v[4] == look.size("normal") else "large") <= left + width - look.pad_x(S.CARD_PAD_X) + 1 for v in texts.values()), f"{label}: every text fits inside the card")
    rec = Recorder()
    render(OC.Card(), rec, S.LEGACY)
    check(rec.shapes[layout.card_id][2:] == (0, 0) and all(v[0] == "" for v in rec.messages.values()), f"{label}: an empty card clears everything")

# --- redraw timing (LiveCard) ----------------------------------------------------------------------------------------------------------
clock = [100.0]
drawn = []
current = [OC.Card(header=(("one", "text"),))]
live = OC.LiveCard(lambda: current[0], lambda: True, drawn.append, now=lambda: clock[0], resend=3.0)
live.refresh()
live.refresh()
check(len(drawn) == 1, "an unchanged card is not redrawn at once")
clock[0] += 3.1
live.refresh()
check(len(drawn) == 2, "but is redrawn now and then so it does not expire")
current[0] = OC.Card()
live.refresh()
check(len(drawn) == 3 and not drawn[-1], "an emptied card is sent once so it clears")
live.refresh()
check(len(drawn) == 3, "and an empty card is not sent again")
off = []
OC.LiveCard(lambda: current[0], lambda: False, off.append).refresh()
check(off == [], "nothing is drawn while a card is off")

# --- placement ----------------------------------------------------------------------------------------------------------------------------
for key, group in (("system_targets", TO.GROUP_NAME), ("body_info", BI.GROUP_NAME)):
    check(key in P.SLOTS and P.SLOTS[key].group == group, f"the {key} slot is registered with the card's group")

if problems:
    print("PROBLEMS:", len(problems))
    for p in problems:
        print(" -", p)
    sys.exit(1)
print("SYSTEM CARDS OK")
