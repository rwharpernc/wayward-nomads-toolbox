"""Draws every WNTB overlay display with EDMC stubbed, at a grid of looks (color scheme x text size x padding x line spacing), and checks
that each display's text sits inside its card: the property that makes a larger text size safe. Text is measured with the same estimates
the cards are sized from (overlay_style.CHAR_PX / LINE_PX at the size the display actually asked for), so a failure means a display's
card and its text disagree about the size, not that the estimate is wrong. Run by test_overlay_look_smoke.py in a subprocess so the
stand-ins never leak into other tests. Exits 0 if everything holds, 1 if not."""
import itertools
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

from plugin import colonisation, colonisation_overlay as C, discovery as D, interdiction as I, landing as L  # noqa: E402
from plugin import flight_alerts as FA  # noqa: E402
from plugin import mining_overlay as M, notable as N, overlay_style as S, screenshots as SC  # noqa: E402

problems = []


class Rec:
    """An overlay client that records what is drawn."""

    def __init__(self):
        self.shapes, self.messages, self.vectors = {}, {}, {}

    def send_message(self, msg_id, text, color, x, y, ttl=8, size="normal"):
        if text:
            self.messages[msg_id] = (text, x, y, size, color)
        else:
            self.messages.pop(msg_id, None)

    def send_shape(self, shape_id, shape, color, fill, x, y, w, h, ttl=8, thickness=None):
        if w and h:
            self.shapes[shape_id] = (x, y, w, h, color, fill)
        else:
            self.shapes.pop(shape_id, None)

    def send_vector(self, shape_id, points, color, ttl=8):
        if len(points) > 1:
            self.vectors[shape_id] = points


def check(condition, message):
    if not condition:
        problems.append(message)


def fits(rec, card_id, label, centered=False, slack=2):
    """Every message lies inside the card rectangle `card_id`, horizontally (the text's start to its estimated end) and vertically."""
    if card_id not in rec.shapes:
        problems.append(f"{label}: no card was drawn")
        return
    left, top, width, height, _color, _fill = rec.shapes[card_id]
    for msg_id, (text, x, y, size, _c) in rec.messages.items():
        text_w = len(text) * S.CHAR_PX[size]
        text_h = S.LINE_PX[size]
        check(x >= left - slack, f"{label}: {msg_id} starts left of the card ({x} < {left})")
        check(x + text_w <= left + width + slack, f"{label}: {msg_id} {text!r} runs past the card's right edge "
              f"({x + text_w:.0f} > {left + width})")
        check(y >= top - slack, f"{label}: {msg_id} starts above the card ({y} < {top})")
        check(y + text_h <= top + height + slack, f"{label}: {msg_id} runs past the card's bottom ({y + text_h} > {top + height})")


def looks():
    names = list(S.SCHEMES)
    for scheme, level, pad, gap in itertools.product(names, (-1, 0, 1, 2), (0, 6, 14), (0, 7)):
        yield S.look_from_choices(scheme, level, pad, gap)


def describe(look):
    return f"{look.palette.name}/text{look.text_level:+d}/pad{look.pad_extra}/gap{look.line_extra}"


# --- the legacy look reproduces the geometry these displays always had ---------------------------------------------------------
check(S.LEGACY.size("large") == "large" and S.LEGACY.char_px("normal") == 8 and S.LEGACY.line_px("normal") == 20, "LEGACY basics")
geometry = D.card_geometry(S.LEGACY, [("NEW SYSTEM DISCOVERY", "Some system")])
check((geometry.width, geometry.height, geometry.name_offset, geometry.body_offset, geometry.pad_x, geometry.pad_top) ==
      (460, 84, 38, 150, 22, 16), f"discovery legacy geometry: {geometry}")
interdiction = I._geometry(S.LEGACY, I._SAMPLE_WHO)
check((interdiction.width, interdiction.height, interdiction.y_who, interdiction.y_resolution) == (600, 116, 130, 160),
      f"interdiction legacy geometry: {interdiction}")
landing = L._geometry(S.LEGACY, None, False)
check((landing.card_w, landing.card_h, landing.y_title, landing.y_status, landing.y_station, landing.y_pad, landing.y_denied,
       landing.shift_x, landing.shift_y) == (320, 324, 650, 675, 698, 721, 744, 0, 0), f"landing legacy geometry: {landing}")
check(M._stat_pitch(S.LEGACY) == 22 and M._waypoint_geometry(S.LEGACY) == (26, 290, 32), "mining legacy geometry")

# --- a sample of everything each display can show ---------------------------------------------------------------------------------
site = colonisation.apply_depot_event({"MarketID": 7, "ConstructionProgress": 0.4, "ResourcesRequired": [
    {"Name": "$ceramiccomposites_name;", "Name_Localised": "Ceramic Composites", "RequiredAmount": 12345, "ProvidedAmount": 100},
    {"Name": "$semiconductors_name;", "Name_Localised": "Semiconductors", "RequiredAmount": 50, "ProvidedAmount": 0}]},
    None, name="Orbital Construction Site: A Fairly Long Name", system="Sol")
colonisation_card = C.build_card(site, {"ceramiccomposites": 99999}, {"ceramiccomposites": 12345, "semiconductors": 50}, True, 784)
discovery_snapshot = D.DiscoverySnapshot(system_visible=True, system_name="Pegasi Sector KO-E a13-2 Long Name 12345",
                                         body_visible=True, body_action="scanned", body_name="Pegasi Sector KO-E a13-2 A 5 a")
notable_snapshot = N.NotableSnapshot(visible=True, title="HIGH GRAVITY LANDABLE BODY", name="Pegasi Sector KO-E a13-2 A 5 a", more=3)
interdiction_snapshot = I.InterdictionSnapshot(active=True, interdictor_name="CMDR A Very Long Commander Name", is_player=True,
                                               is_thargoid=False, power="Archon Delaine", resolution="submitted")
landing_info = L.LandingDisplayInfo(status_label="Docking Approved", station="ELDER WARDEN WLF-LXW (Fleet Carrier)", pad=24,
                                    diagram_type="starport", show_diagram=True)
landing_placeholder = L.LandingDisplayInfo(status_label="Docking Approved", station="Some Outpost", pad=3,
                                           diagram_type=None, show_diagram=False)
landing_denied = L.LandingDisplayInfo(status_label="Docking Denied", station="Some Station With A Rather Long Name", pad=None,
                                      denied_reason="No fire zone 12345678901234567890", diagram_type=None, show_diagram=False)

count = 0
for look in looks():
    tag = describe(look)
    count += 1

    rec = Rec()
    C.render(rec, colonisation_card, 40, 300, 0, look)
    fits(rec, C.CARD_ID, f"colonisation {tag}")
    left, top, width, height = C.block_rect(colonisation_card, 40, 300, look)
    check(rec.shapes[C.CARD_ID][:4] == (left, top, width, height), f"colonisation {tag}: block_rect disagrees with what is drawn")

    rec = Rec()
    D.render(discovery_snapshot, rec, 100, 100, look)
    for card_id, label in ((D._SYSTEM_CARD_ID, "system"), (D._BODY_CARD_ID, "body")):
        pass
    left, top, width, height, _c, _f = rec.shapes[D._SYSTEM_CARD_ID]
    body = rec.shapes[D._BODY_CARD_ID]
    check(body[2] == width, f"discovery {tag}: the two cards differ in width")
    check(body[1] >= top + height, f"discovery {tag}: the body card overlaps the system card")
    for msg_id, (text, x, y, size, _c2) in rec.messages.items():
        in_system = msg_id.startswith("wntb_discovery_system")
        c_left, c_top, c_w, c_h = (left, top, width, height) if in_system else body[:4]
        check(x >= c_left and x + len(text) * S.CHAR_PX[size] <= c_left + c_w + 2, f"discovery {tag}: {msg_id} {text!r} runs outside its card")
        check(c_top <= y and y + S.LINE_PX[size] <= c_top + c_h + 2, f"discovery {tag}: {msg_id} runs outside its card vertically")

    rec = Rec()
    N.render(notable_snapshot, rec, 100, 300, look)
    fits(rec, N._CARD_ID, f"notable {tag}")

    rec = Rec()
    I.render(interdiction_snapshot, rec, look)
    fits(rec, I._CARD_ID, f"interdiction {tag}")

    for lines_shown in (1, 2, 3, 4):
        rec = Rec()
        FA.render(FA.SAMPLE_LINES[:3] * 2 if lines_shown == 4 else FA.SAMPLE_LINES[:lines_shown], rec, look)
        fits(rec, FA._CARD_ID, f"flight alerts x{lines_shown} {tag}")

    for label, info in (("approved", landing_info), ("placeholder", landing_placeholder), ("denied", landing_denied)):
        rec = Rec()
        L.render(info, None, rec, look)
        fits(rec, L._CARD_ID, f"landing {label} {tag}")
        left, top, width, height, _c, _f = rec.shapes[L._CARD_ID]
        for shape_id, points in rec.vectors.items():
            for point in points:
                check(left - 2 <= point["x"] <= left + width + 2 and top - 2 <= point["y"] <= top + height + 2,
                      f"landing {label} {tag}: the diagram ({shape_id}) is outside the card")
        for shape_id, (x, y, w, h, _c3, _f3) in rec.shapes.items():
            if shape_id != L._CARD_ID:
                check(x >= left - 2 and x + w <= left + width + 2 and y >= top - 2 and y + h <= top + height + 2,
                      f"landing {label} {tag}: {shape_id} is outside the card")

    # the placeholder's box and caption are centered in the card as a pair, the caption in at most three lines
    geo = L._geometry(look, landing_placeholder, True)
    caption, _h = L._caption_lines(look)
    caption_w = max(look.text_width(c, "normal") for c in caption)
    left_margin = geo.box_x - L._CARD_X
    right_margin = geo.card_w - (geo.caption_x - L._CARD_X + caption_w)
    # centered as if the caption were L._CAPTION_CENTRE of its estimate (the estimate errs wide), and never off the card
    expected_right = geo.card_w - (left_margin + L._PLACEHOLDER_W + L._FALLBACK_LABEL_GAP + round(caption_w * L._CAPTION_CENTRE))
    check(abs(left_margin - expected_right) <= 1 or right_margin == look.pad_x(L._BASE_PAD_X) // 2,
          f"landing placeholder {tag}: not centered ({left_margin} left, {expected_right} right)")
    check(right_margin >= look.pad_x(L._BASE_PAD_X) // 2 - 1, f"landing placeholder {tag}: the caption's estimated end is {right_margin}px "
          f"from the card's right edge, nearer than half the padding")
    check(len(caption) <= 3 and " ".join(caption) == L._FALLBACK_LABEL_TEXT, f"landing placeholder {tag}: caption lines {caption}")
    check(left_margin >= look.pad_x(L._BASE_PAD_X) - 1, f"landing placeholder {tag}: the pair is closer to the edge than the padding")

    # mining: the stats panel and the waypoint panel, with the arrow
    lines = ["Cargo: 123/784 t", "Mining rate: 12.3 t/min", "Limpets remaining: ~12 more than you would think"]
    rec = Rec()
    M._send_overlay_panel(rec, "bg", 20, 100, lines, look)
    left, top, width, height, _c, _f = rec.shapes["bg"]
    pitch = M._stat_pitch(look)
    for index, text in enumerate(lines):
        size = look.size("normal")
        check(20 + len(text) * S.CHAR_PX[size] <= left + width + 2, f"mining stats {tag}: line {index} runs past the panel")
        check(100 + index * pitch + S.LINE_PX[size] <= top + height + 2, f"mining stats {tag}: line {index} runs past the panel's bottom")
    line, center_y, extra_h = M._waypoint_geometry(look)
    rec = Rec()
    text = "↑ Platinum - 12.3 km NNE of here"
    M._send_overlay_panel(rec, "wp", 20, M._WAYPOINT_OVERLAY_Y, [text], look, "large", extra_h, line)
    left, top, width, height, _c, _f = rec.shapes["wp"]
    check(20 + len(text) * S.CHAR_PX[look.size("large")] <= left + width + 2, f"mining waypoint {tag}: the text runs past the panel")
    check(center_y + M._WAYPOINT_ARROW_SIZE <= top + height + 2, f"mining waypoint {tag}: the arrow is below the panel")
    check(M._WAYPOINT_OVERLAY_Y + line <= center_y - M._WAYPOINT_ARROW_SIZE + 2 + 14, f"mining waypoint {tag}: the arrow overlaps the text")

    # screenshots: the panel against its lines
    texts = ["Screenshot saved: Some Rather Long Screenshot Name 2026-10-11.png", "Screenshot saved: b.png"]
    left, top, width, height = SC._panel(look, len(texts), max(len(t) for t in texts))
    for index, t in enumerate(texts):
        size = look.size(SC._TEXT_SIZE)
        check(SC._ORIGIN_X + len(t) * S.CHAR_PX[size] <= left + width + 2, f"screenshots {tag}: a line runs past the panel")
        check(SC._ORIGIN_Y + index * SC._line_px(look) + S.LINE_PX[size] <= top + height + 6, f"screenshots {tag}: a line runs past the bottom")

check(count == 144, f"expected 144 looks, drew {count}")
if problems:
    print("PROBLEMS:", len(problems))
    for p in problems[:40]:
        print(" -", p)
    sys.exit(1)
print(f"OVERLAY LOOKS OK: {count} looks")
