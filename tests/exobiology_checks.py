"""Run by test_exobiology_overlay.py in its own process, so its stub config does not reach other test files. Exobiology overlay cards (exobiology_overlay.py, exo_radar.py) and the per-body view that feeds them (organic_scan_panel.overlay_view): what each card says,
where the radar draws things, and that samples, variants, first footfall, the ship and the commander's position come through from journal events and Status.json."""
from __future__ import annotations

import dataclasses
import math
import os
import sys
import types
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
for name in ("myNotebook", "ttkHyperlinkLabel", "theme", "monitor", "plug", "l10n", "requests"):
    sys.modules.setdefault(name, mock.MagicMock())
if "config" not in sys.modules:
    config_stub = types.ModuleType("config")
    config_stub.appname = "EDMarketConnector"
    config_stub.config = mock.MagicMock()
    sys.modules["config"] = config_stub

from plugin import exo_radar as XR  # noqa: E402
from plugin import exobiology_overlay as EX  # noqa: E402
from plugin import organic_scan, organic_scan_panel  # noqa: E402
from plugin import overlay_style as S  # noqa: E402

TUSSOCK, BACTERIUM = "$Codex_Ent_Tussocks_Genus_Name;", "$Codex_Ent_Bacterial_Genus_Name;"


class Recorder:
    def __init__(self):
        self.shapes, self.circles, self.messages, self.vectors = {}, {}, {}, {}

    def send_shape(self, shape_id, shape, color, fill, x, y, w, h, ttl=8, thickness=None):
        self.shapes[shape_id] = (x, y, w, h, color)

    def send_circle(self, shape_id, color, fill, x, y, radius, ttl=8, thickness=None):
        self.circles[shape_id] = (x, y, radius, color, fill)

    def send_vector(self, shape_id, points, color, ttl=8):
        self.vectors[shape_id] = list(points)

    def send_message(self, msg_id, text, color, x, y, ttl=8, size="normal"):
        self.messages[msg_id] = (text, color, x, y, size)

    def texts(self):
        return [v[0] for v in self.messages.values() if v[0]]


class Cards(unittest.TestCase):
    def setUp(self):
        self.view = EX.sample_view()

    def test_status_card_while_sampling_shows_the_variant_dots_reward_and_distance(self):
        card = EX.build_status_card(self.view, "Sample System")
        self.assertEqual(card.headline[0], "Tussock pennatis - Lime")
        self.assertEqual(card.dots, (True, True, False))
        self.assertEqual(card.badge, "1 of 4 analysed")
        self.assertAlmostEqual(card.progress, (2 / 3 + 1) / 4)     # the Tussock is two samples in and the Osseus is analysed
        self.assertEqual(card.header[0][0], "5.0M CR  ·  FF 5x")                # the reward and the reason share one line
        self.assertTrue(card.header[1][0].startswith("Move 122 m further"))
        self.assertEqual(card.header[1][1], "warn")

    def test_status_card_says_clear_once_far_enough_and_with_nothing_active_lists_the_genera(self):
        genera = tuple(dataclasses.replace(g, distance_m=250.0) if g.key == "t" else g for g in self.view.genera)
        clear = EX.build_status_card(dataclasses.replace(self.view, genera=genera), "Sample System")
        self.assertEqual(clear.header[1][1], "ok")
        idle = EX.build_status_card(dataclasses.replace(self.view, active=None), "Sample System")
        self.assertEqual([r[0] for r in idle.rows], ["Bacterium", "Frutexa", "Tussock pennatis - Lime", "Osseus fractus - Red"])
        self.assertEqual([r[1] for r in idle.rows], ["500 m apart", "150 m apart", "200 m apart", "Done"])
        self.assertIn("five times", idle.footer[0])

    def test_status_card_for_an_unmapped_body_says_to_map_it_and_everything_done_says_so(self):
        unmapped = organic_scan.BodyView("Sample 3", (), signal_count=3)
        card = EX.build_status_card(unmapped)
        self.assertIn("Map this body", card.header[0][0])
        self.assertEqual(card.badge, "3 signals")
        done = organic_scan.BodyView("Sample 3", (organic_scan.GenusView("t", "Tussock", 200.0, species="Tussock Pennatis", value=1, stage=3),), signal_count=1)
        self.assertIn("All samples analysed", EX.build_status_card(done).footer[0])
        self.assertFalse(EX.build_status_card(None))

    def test_a_scanned_plant_is_named_in_the_footer_until_it_is_sampled(self):
        idle = dataclasses.replace(self.view, active=None)
        card = EX.build_status_card(idle, "Sample System", ("Tussock Pennatis - Lime", 1_000_000))
        self.assertEqual(card.footer, ("Scanned: Tussock Pennatis - Lime  5.0M CR (first footfall bonus)", "info"))
        EX._note_codex({"SubCategory": "$Codex_SubCategory_Organic_Structures;", "Name_Localised": "Tussock Pennatis - Lime"})
        self.assertEqual(EX._codex_scan(), ("Tussock pennatis - Lime", 1_000_000))
        EX._codex.clear()
        EX._note_codex({"SubCategory": "$Codex_SubCategory_Geology;", "Name_Localised": "Something"})
        self.assertIsNone(EX._codex_scan())

    def test_list_card_shows_candidates_confirmed_species_and_the_rewards(self):
        card = EX.build_list_card(self.view, "Sample System")
        names = [r[0] for r in card.rows]
        self.assertTrue(names[0].startswith("Bacterium\nBacterium nebulus  5.3M CR  ~50%\nBacterium aurasus  1.0M CR  ~50%"))
        self.assertEqual(card.rows[0][1], "1.0M - 5.3M CR")                         # the range the genus could pay
        self.assertEqual(card.rows[1], ("Frutexa fera", "~1.6M CR", "info"))
        self.assertEqual(card.rows[2][0], "Tussock pennatis - Lime")
        self.assertEqual(card.rows[3][2], "ok")                       # analysed
        self.assertEqual(card.footer[0], "Rewards: 7.6M - 11.9M CR\nFirst footfall (5x): 38.2M - 59.6M CR")      # the range, and the bonus on its own line
        self.assertFalse(EX.build_list_card(organic_scan.BodyView("x", ())))

    def test_popup_card_and_its_first_footfall_value(self):
        card = EX.build_popup_card(EX.sample_popup())
        self.assertEqual(card.title[0], "Tussock pennatis - Lime")
        self.assertEqual(card.rows[0], ("Estimated value", "5,000,000 cr (FF bonus)", "title"))
        self.assertEqual(card.rows[1], ("Colony range", "200 m", "text"))
        self.assertEqual(card.footer[0], "Sampled")
        self.assertFalse(EX.build_popup_card(None))

    def test_the_cards_draw_with_every_text_inside_the_card_at_both_looks(self):
        for look in (S.LEGACY, S.DEFAULT):
            for layout, card in ((EX.LAYOUT_STATUS, EX.build_status_card(self.view)), (EX.LAYOUT_LIST, EX.build_list_card(self.view)),
                                 (EX.LAYOUT_POPUP, EX.build_popup_card(EX.sample_popup()))):
                rec = Recorder()
                layout.render(card, rec, look)
                left, top, width, height, _color = rec.shapes[layout.card_id]
                for key, (text, _c, x, y, size) in rec.messages.items():
                    if not text:
                        continue
                    base = "normal" if size == look.size("normal") else "large"
                    self.assertLessEqual(x + look.measured_width(text, base), left + width - look.pad_x(S.CARD_PAD_X) + 1, f"{layout.prefix}: {text}")
                    self.assertLessEqual(y + look.line_px(base), top + height, f"{layout.prefix}: {text}")
            if look is S.DEFAULT:
                self.assertEqual(len(rec.circles), 0)


class Ranges(unittest.TestCase):
    def test_a_genus_pays_a_range_until_a_sample_names_the_species(self):
        genus = organic_scan.GenusView("b", "Bacterium", 500.0, candidates=(("A", 1_000_000), ("B", 5_000_000), ("C", 3_000_000)))
        self.assertEqual(genus.value_range, (1_000_000, 5_000_000))
        named = organic_scan.GenusView("b", "Bacterium", 500.0, species="A", value=1_000_000, candidates=genus.candidates)
        self.assertEqual(named.value_range, (1_000_000, 1_000_000))
        self.assertIsNone(organic_scan.GenusView("x", "X", 100.0).value_range)

    def test_the_odds_are_an_even_share_and_only_while_the_species_is_open(self):
        genus = organic_scan.GenusView("b", "Bacterium", 500.0, candidates=(("A", 1), ("B", 2), ("C", 3)))
        self.assertEqual([p for _n, _v, p in genus.odds()], [33, 33, 33])
        self.assertEqual([p for _n, _v, p in organic_scan.GenusView("b", "B", 1.0, candidates=(("A", 1),)).odds()], [100])
        self.assertEqual(organic_scan.GenusView("b", "B", 1.0, species="A", candidates=(("A", 1), ("B", 2))).odds(), ())

    def test_a_body_adds_its_genera_up_and_says_nothing_when_no_value_is_known(self):
        view = EX.sample_view()
        self.assertEqual(view.reward_range, (7_632_500, 11_922_400))
        self.assertIsNone(organic_scan.BodyView("x", (organic_scan.GenusView("t", "T", 1.0),)).reward_range)

    def test_the_footer_without_a_first_footfall_is_a_single_line(self):
        view = dataclasses.replace(EX.sample_view(), first_footfall=False)
        self.assertEqual(EX.build_list_card(view).footer[0], "Rewards: 7.6M - 11.9M CR")

    def test_a_footer_of_two_lines_is_drawn_as_two_lines(self):
        rec = Recorder()
        EX.LAYOUT_LIST.render(EX.build_list_card(EX.sample_view()), rec, S.DEFAULT)
        texts = [t for t in rec.texts()]
        self.assertIn("Rewards: 7.6M - 11.9M CR", texts)
        self.assertIn("First footfall (5x): 38.2M - 59.6M CR", texts)


class MultiTrack(unittest.TestCase):
    """One pointer for each genus identified, each the latest plant of its genus, each in its own color."""

    def view(self):
        base = EX.sample_view()
        way = organic_scan.Waypoint
        return dataclasses.replace(base, waypoints=(
            way("t", "Tussock Pennatis - Lime", 0.0, 0.0250), way("b", "Bacterium Aurasus - Emerald", 0.0, 0.0300),
            way("f", "Frutexa Fera - Green", 0.0, 0.0280), way("t", "Tussock Pennatis - Lime", 0.0, 0.0290)))

    def test_three_genera_give_three_tracked_plants_the_latest_of_each(self):
        followed = XR.tracked(self.view())
        self.assertEqual(len(followed), 3)
        by = {t.waypoint.genus_key: t for t in followed}
        self.assertEqual(round(by["t"].waypoint.lon, 4), 0.0290)                      # the newer Tussock, not the first
        self.assertEqual(sorted(t.color for t in followed), [0, 1, 2])

    def test_the_radar_has_a_pointer_a_ring_and_a_row_for_each(self):
        plan = XR.build_plan(self.view())
        self.assertEqual((len(plan.pointers), len(plan.targets), len(plan.track)), (3, 3, 3))
        tracked_rows = [row[0] for row in plan.rows if row and row[0].text.split(" ")[0] in ("Tussock", "Bacterium", "Frutexa")]
        self.assertEqual(len(tracked_rows), 3)
        self.assertTrue(all(item.angle is not None for item in tracked_rows))
        self.assertEqual({item.role for item in tracked_rows}, {"series0", "series1", "series2"})

    def test_the_radar_grows_a_row_for_each_plant_tracked(self):
        one = dataclasses.replace(self.view(), waypoints=self.view().waypoints[:1])
        layout = XR.RadarLayout("t_", 100, 100)
        self.assertGreater(layout.block_rect(S.DEFAULT, XR.build_plan(self.view()))[3], layout.block_rect(S.DEFAULT, XR.build_plan(one))[3])

    def test_drawing_sends_one_pointer_each_and_clears_the_ones_no_longer_needed(self):
        rec = Recorder()
        layout = XR.RadarLayout("t_", 100, 100)
        layout.render(XR.build_plan(self.view()), rec, S.DEFAULT)
        self.assertEqual(sorted(k for k, v in rec.vectors.items() if v and k.startswith("t_point")), ["t_point0", "t_point1", "t_point2"])
        one = dataclasses.replace(self.view(), waypoints=self.view().waypoints[:1])
        layout.render(XR.build_plan(one), rec, S.DEFAULT)
        self.assertEqual(sorted(k for k, v in rec.vectors.items() if v and k.startswith("t_point")), ["t_point0"])

    def test_bio_status_has_a_line_for_each_in_the_radar_s_color(self):
        card = EX.build_status_card(self.view(), "Sample System")
        lines = [h for h in card.side if h[0].startswith(("Tussock", "Bacterium", "Frutexa", "Osseus"))]
        self.assertEqual(len(lines), 3)
        self.assertEqual({h[1] for h in lines}, {"series0", "series1", "series2"})
        rec = Recorder()
        EX.LAYOUT_STATUS.render(card, rec, S.DEFAULT)           # series roles are drawn like any other color
        self.assertTrue(any(t.startswith("Tussock: ") for t in rec.texts()))


class Radar(unittest.TestCase):
    def test_offset_is_right_and_ahead_for_the_heading(self):
        here, there = (0.0, 0.0), (0.0, 0.001)               # a point due east
        right, ahead = XR.offset_m(here, there, 600_000.0, 90.0)   # facing east: it is straight ahead
        self.assertAlmostEqual(right, 0.0, places=3)
        self.assertGreater(ahead, 10.0)
        right, ahead = XR.offset_m(here, there, 600_000.0, 0.0)    # facing north: it is to the right
        self.assertGreater(right, 10.0)
        self.assertAlmostEqual(ahead, 0.0, places=3)

    def test_the_plan_has_a_circle_per_sample_red_when_inside_and_the_distances(self):
        plan = XR.build_plan(EX.sample_view())
        self.assertTrue(plan.visible)
        self.assertEqual(len(plan.circles), 2)
        inside = {c.inside for c in plan.circles}
        self.assertEqual(inside, {True, False})                 # 209 m from the first sample (clear), 78 m from the second (inside)
        self.assertEqual(plan.markers[0][0], "S")
        self.assertEqual(plan.top, "Ship: 16 m")
        self.assertEqual(plan.bottom, "Scan 1: 209 m   Scan 2: 79 m")
        for circle in plan.circles:                              # every circle is inside the plot
            self.assertLessEqual(math.hypot(circle.x, circle.y) + circle.radius, XR.SIZE / 2)

    def test_nothing_to_plot_without_a_position_samples_or_a_vehicle(self):
        view = EX.sample_view()
        self.assertFalse(XR.build_plan(None).visible)
        self.assertFalse(XR.build_plan(dataclasses.replace(view, here=None)).visible)
        bare = dataclasses.replace(view, ship=None, waypoints=(), genera=tuple(dataclasses.replace(g, positions=()) for g in view.genera))
        self.assertFalse(XR.build_plan(bare).visible)

    def test_rendering_draws_and_then_clears(self):
        rec = Recorder()
        XR.RadarLayout("t_", 100, 100).render(XR.build_plan(EX.sample_view()), rec, S.DEFAULT)
        self.assertIn("t_c0", rec.circles)
        self.assertIn("t_panel", rec.shapes)
        layout = XR.RadarLayout("t_", 100, 100)
        layout.render(XR.build_plan(EX.sample_view()), rec, S.DEFAULT)
        layout.render(XR.Plan(), rec, S.DEFAULT)
        self.assertEqual(rec.shapes["t_panel"][2:4], (0, 0))
        self.assertTrue(all(v[0] == "" for v in rec.messages.values()))


class Waypoints(unittest.TestCase):
    """Plants identified with the Composition Scanner are remembered and the radar and Bio status lead back to them."""

    def test_the_radar_marks_the_plant_points_to_it_and_says_how_far_and_which_way(self):
        view = EX.sample_view()                      # standing at longitude 0.020, facing 30 degrees; the plant is at 0.029
        plan = XR.build_plan(view)
        self.assertEqual(len(plan.targets), 1)
        self.assertEqual(plan.targets[0][0], "T")
        self.assertEqual(len(plan.pointers), 1)
        self.assertAlmostEqual(math.hypot(plan.pointers[0][0], plan.pointers[0][1]), 1.0)
        self.assertEqual(len(plan.track), 1)
        self.assertRegex(plan.track[0], r"^Tussock: \d+ m, \d+° (right|left)$")

    def test_every_distance_under_the_plot_has_a_little_pointer_turned_toward_it(self):
        plan = XR.build_plan(EX.sample_view())
        items = [item for row in plan.rows for item in row]
        self.assertEqual([i.text for i in items if i.angle is not None], ["Ship: 16 m", "Scan 1: 209 m", "Scan 2: 79 m", "Tussock 94 m"])
        rec = Recorder()
        layout = XR.RadarLayout("t_", 100, 100)
        layout.render(plan, rec, S.DEFAULT)
        self.assertEqual(sorted(k for k, v in rec.vectors.items() if v and k[:3] == "t_a" and k[3:].isdigit()), ["t_a0", "t_a1", "t_a2", "t_a3"])

    def test_an_arrowhead_points_the_way_it_is_turned(self):
        up = XR.arrow_points(0, 0, 0.0)
        self.assertEqual((up[0]["x"], up[0]["y"]), (0.0, -6.0))                  # the tip is straight up
        right = XR.arrow_points(0, 0, 90.0)
        self.assertAlmostEqual(right[0]["x"], 6.0, places=1)                      # turned a quarter clockwise: the tip points right
        self.assertAlmostEqual(right[0]["y"], 0.0, places=1)
        self.assertEqual(up[0], up[-1])                                           # the outline is closed

    def test_bearing_text(self):
        self.assertEqual(XR.bearing_text(0.0, 50.0), "ahead")
        self.assertEqual(XR.bearing_text(0.0, -50.0), "behind")
        self.assertEqual(XR.bearing_text(50.0, 0.0), "90° right")
        self.assertEqual(XR.bearing_text(-50.0, 0.0), "90° left")

    def test_only_a_waypoint_makes_the_radar_show(self):
        view = dataclasses.replace(EX.sample_view(), ship=None, genera=tuple(dataclasses.replace(g, positions=()) for g in EX.sample_view().genera))
        self.assertTrue(XR.build_plan(view).visible)

    def test_bio_status_names_the_plant_being_tracked(self):
        card = EX.build_status_card(EX.sample_view(), "Sample System")
        self.assertTrue(any(h[0].startswith("Tussock: ") for h in card.side))
        idle = EX.build_status_card(dataclasses.replace(EX.sample_view(), active=None), "Sample System")
        self.assertTrue(any(h[0].startswith("Tussock: ") for h in idle.side))

    def test_the_genus_comes_from_the_codex_name(self):
        self.assertEqual(organic_scan.genus_key_for_codex_name("$Codex_Ent_Tussocks_06_G_Name;"), TUSSOCK)
        self.assertEqual(organic_scan.genus_key_for_codex_name("$Codex_Ent_Shrubs_05_F_Name;"), "$Codex_Ent_Shrubs_Genus_Name;")
        self.assertIsNone(organic_scan.genus_key_for_codex_name("$Codex_Ent_Nothing_99_Z_Name;"))
        self.assertIsNone(organic_scan.genus_key_for_codex_name("garbage"))


class WaypointTracking(unittest.TestCase):
    def setUp(self):
        self.controller = organic_scan_panel.OrganicScanController()
        self.system = "Test Sector AB-C d1"
        self.body = f"{self.system} 2 d"
        self.controller.handle_event({"event": "FSDJump", "StarSystem": self.system, "StarPos": [0, 0, 0]}, "CMDR", self.system, None, {})
        self.controller._genus_hints[self.body] = [TUSSOCK, BACTERIUM]
        self.status(0.0, 0.0)

    def status(self, lat, lon):
        self.controller.dashboard_status({"BodyName": self.body, "Latitude": lat, "Longitude": lon, "PlanetRadius": 600_000.0, "Heading": 0.0})

    def codex(self, name, lat, lon, label="Tussock Pennatis - Lime"):
        self.controller.handle_event({"event": "CodexEntry", "SubCategory": "$Codex_SubCategory_Organic_Structures;", "Name": name, "Name_Localised": label,
                                      "Latitude": lat, "Longitude": lon}, "CMDR", self.system, None, {})

    def test_an_identified_plant_becomes_a_waypoint_and_the_genus_is_followed(self):
        self.codex("$Codex_Ent_Tussocks_06_G_Name;", 0.001, 0.0)
        view = self.controller.overlay_view()
        self.assertEqual(view.focus, TUSSOCK)
        self.assertEqual([(w.name, w.lat, w.lon) for w in view.waypoints], [("Tussock Pennatis - Lime", 0.001, 0.0)])

    def test_every_genus_identified_is_kept_and_the_radar_follows_the_latest_of_each(self):
        self.codex("$Codex_Ent_Tussocks_06_G_Name;", 0.001, 0.0)
        self.codex("$Codex_Ent_Tussocks_06_G_Name;", 0.004, 0.0)                              # a later Tussock
        self.codex("$Codex_Ent_Bacterial_01_G_Name;", 0.002, 0.0, "Bacterium Aurasus - Emerald")
        view = self.controller.overlay_view()
        self.assertEqual(len(view.waypoints), 3)
        followed = XR.tracked(view)
        self.assertEqual([t.name for t in followed], ["Tussock", "Bacterium"])               # one per genus, in the order the genera were found
        self.assertEqual([round(t.waypoint.lat, 3) for t in followed], [0.004, 0.002])        # the most recent of each
        self.assertEqual(len({t.color for t in followed}), 2)

    def test_the_same_plant_is_not_listed_twice_and_each_genus_keeps_a_few(self):
        for number in range(6):
            self.codex("$Codex_Ent_Tussocks_06_G_Name;", 0.001 * (number + 1), 0.0)
        self.codex("$Codex_Ent_Tussocks_06_G_Name;", 0.006, 0.0)
        waypoints = self.controller.overlay_view().waypoints
        self.assertEqual(len(waypoints), organic_scan.WAYPOINTS_PER_GENUS)
        self.assertEqual([round(w.lat, 3) for w in waypoints], [0.003, 0.004, 0.005, 0.006])

    def test_sampling_a_plant_drops_its_waypoint_and_analysing_clears_the_genus(self):
        self.codex("$Codex_Ent_Tussocks_06_G_Name;", 0.0, 0.0)           # where we stand
        self.codex("$Codex_Ent_Tussocks_06_G_Name;", 0.05, 0.0)          # far away (about 520 m)
        sample = {"event": "ScanOrganic", "Genus": TUSSOCK, "Species": "$Codex_Ent_Tussocks_06_Name;", "Species_Localised": "Tussock Pennatis"}
        self.controller.handle_event({**sample, "ScanType": "Log"}, "CMDR", self.system, None, {})
        self.assertEqual([w.lat for w in self.controller.overlay_view().waypoints], [0.05])
        self.controller.handle_event({**sample, "ScanType": "Sample"}, "CMDR", self.system, None, {})
        self.controller.handle_event({**sample, "ScanType": "Analyse"}, "CMDR", self.system, None, {})
        self.assertEqual(self.controller.overlay_view().waypoints, ())

    def test_a_plant_sampled_well_away_from_where_the_scanner_recorded_it_is_still_dropped(self):
        self.codex("$Codex_Ent_Tussocks_06_G_Name;", 0.0, 0.0)           # recorded here
        self.status(0.0, 0.007)                                           # sampled about 73 m away
        sample = {"event": "ScanOrganic", "Genus": TUSSOCK, "Species": "$Codex_Ent_Tussocks_06_Name;", "Species_Localised": "Tussock Pennatis"}
        self.controller.handle_event({**sample, "ScanType": "Log"}, "CMDR", self.system, None, {})
        self.assertEqual(self.controller.overlay_view().waypoints, ())

    def test_the_same_color_variant_is_matched_from_further_away(self):
        self.codex("$Codex_Ent_Tussocks_06_G_Name;", 0.0, 0.0, "Tussock Pennatis - Lime")
        self.codex("$Codex_Ent_Tussocks_06_F_Name;", 0.0, 0.002, "Tussock Pennatis - Green")          # about 21 m from the sampler, a different variant
        self.status(0.0, -0.012)                                          # about 125 m from the Lime one, further from the Green one
        sample = {"event": "ScanOrganic", "Genus": TUSSOCK, "Species": "$Codex_Ent_Tussocks_06_Name;", "Species_Localised": "Tussock Pennatis",
                  "Variant_Localised": "Tussock Pennatis - Lime", "ScanType": "Log"}
        self.controller.handle_event(sample, "CMDR", self.system, None, {})
        self.assertEqual([w.name for w in self.controller.overlay_view().waypoints], ["Tussock Pennatis - Green"])

    def test_without_a_position_the_plant_identified_last_is_dropped(self):
        self.codex("$Codex_Ent_Tussocks_06_G_Name;", 0.001, 0.0, "Tussock Pennatis - Lime")
        self.codex("$Codex_Ent_Tussocks_06_F_Name;", 0.003, 0.0, "Tussock Pennatis - Green")
        self.controller._current_planet_radius = None
        sample = {"event": "ScanOrganic", "Genus": TUSSOCK, "Species": "$Codex_Ent_Tussocks_06_Name;", "Species_Localised": "Tussock Pennatis", "ScanType": "Log"}
        self.controller.handle_event(sample, "CMDR", self.system, None, {})
        self.assertEqual([w.name for w in self.controller.overlay_view().waypoints], ["Tussock Pennatis - Lime"])

    def test_waypoints_survive_a_restart(self):
        self.codex("$Codex_Ent_Tussocks_06_G_Name;", 0.001, 0.002)
        saved = self.controller._persisted[self.controller._body_key(self.system, self.body)]["waypoints"]
        fresh = organic_scan_panel.OrganicScanController()
        fresh._persisted = {fresh._body_key(self.system, self.body): {"waypoints": saved}}
        fresh._system_name = self.system
        fresh._restore_body(self.system, self.body)
        self.assertEqual([(w.lat, w.lon) for w in fresh._waypoints[self.body]], [(0.001, 0.002)])

    def test_a_codex_entry_that_is_not_a_plant_or_has_no_position_is_ignored(self):
        self.codex("$Codex_Ent_Tussocks_06_G_Name;", None, None)
        self.controller.handle_event({"event": "CodexEntry", "SubCategory": "$Codex_SubCategory_Geology;", "Name": "$Codex_Ent_Tussocks_06_G_Name;",
                                      "Latitude": 1.0, "Longitude": 1.0}, "CMDR", self.system, None, {})
        self.assertEqual(self.controller.overlay_view().waypoints, ())


class View(unittest.TestCase):
    """The controller's per-body view, fed the events and Status.json a real sampling walk produces."""

    def setUp(self):
        self.controller = organic_scan_panel.OrganicScanController()
        self.system = "Test Sector AB-C d1"
        self.body = f"{self.system} 2 d"

    def event(self, entry):
        self.controller.handle_event(entry, "CMDR", self.system, None, {})

    def status(self, lat, lon, heading=0.0):
        self.controller.dashboard_status({"BodyName": self.body, "Latitude": lat, "Longitude": lon, "PlanetRadius": 600_000.0, "Heading": heading})

    def test_a_sampling_walk(self):
        self.event({"event": "FSDJump", "StarSystem": self.system, "StarPos": [0, 0, 0]})
        self.event({"event": "Scan", "BodyName": self.body, "PlanetClass": "Rocky body", "SurfaceGravity": 1.2, "SurfaceTemperature": 178,
                    "SurfacePressure": 2500.0, "AtmosphereType": "Thin Carbon Dioxide", "WasFootfalled": False})
        self.event({"event": "SAASignalsFound", "BodyName": self.body, "Signals": [{"Type": "$SAA_SignalType_Biological;", "Count": 2}],
                    "Genuses": [{"Genus": TUSSOCK}, {"Genus": BACTERIUM}]})
        self.status(0.0, 0.0)
        view = self.controller.overlay_view()
        self.assertEqual((view.signal_count, view.mapped, view.first_footfall, len(view.genera)), (2, True, True, 2))
        self.assertIsNone(view.active)
        self.event({"event": "Touchdown", "Latitude": 0.001, "Longitude": 0.0})
        sample = {"event": "ScanOrganic", "Genus": TUSSOCK, "Species": "$Codex_Ent_Tussocks_06_Name;", "Species_Localised": "Tussock Pennatis",
                  "Variant_Localised": "Tussock Pennatis - Lime"}
        self.event({**sample, "ScanType": "Log"})
        self.status(0.0, 0.01)
        self.event({**sample, "ScanType": "Sample"})
        view = self.controller.overlay_view()
        genus = view.active_genus
        self.assertEqual((genus.name, genus.variant, genus.stage, len(genus.positions)), ("Tussock", "Tussock pennatis - Lime", 2, 2))
        self.assertEqual(view.ship, (0.001, 0.0))
        self.assertEqual(view.here, (0.0, 0.01))
        self.assertAlmostEqual(genus.distance_m, 0.0, places=1)       # the last sample was taken where they stand
        self.status(0.0, 0.03)
        self.assertAlmostEqual(self.controller.overlay_view().active_genus.distance_m, math.radians(0.02) * 600_000.0, delta=1.0)
        self.event({**sample, "ScanType": "Sample"})
        self.event({**sample, "ScanType": "Analyse"})
        view = self.controller.overlay_view()
        self.assertIsNone(view.active)                                # analysed: no longer the one in progress
        self.assertEqual((view.analysed, view.active_genus), (1, None))

    def test_an_unmapped_body_has_a_signal_count_and_no_genera(self):
        self.event({"event": "FSDJump", "StarSystem": self.system, "StarPos": [0, 0, 0]})
        self.event({"event": "FSSBodySignals", "BodyName": self.body, "Signals": [{"Type": "$SAA_SignalType_Biological;", "Count": 3}]})
        self.status(0.0, 0.0)
        view = self.controller.overlay_view()
        self.assertEqual((view.signal_count, view.genera, view.mapped), (3, (), False))

    def test_the_sample_in_progress_is_still_active_after_a_restart_and_the_bar_counts_it(self):
        self.event({"event": "FSDJump", "StarSystem": self.system, "StarPos": [0, 0, 0]})
        self.controller._genus_hints[self.body] = [TUSSOCK, BACTERIUM]
        self.status(0.0, 0.0)
        self.controller._tracker.restore_organism(TUSSOCK, "$Codex_Ent_Tussocks_06_Name;", "Tussock Pennatis", 1_000_000, 2, 0.0, 0.0,
                                                  "Tussock Pennatis - Lime", [(0.0, 0.0), (0.0, 0.0)])
        view = self.controller.overlay_view()
        self.assertEqual(view.active_genus.name, "Tussock")
        self.assertAlmostEqual(view.progress, (2 / 3) / 2)
        self.assertAlmostEqual(EX.build_status_card(view).progress, (2 / 3) / 2)

    def test_leaving_the_planet_resets_the_view_and_returning_brings_the_samples_back(self):
        self.event({"event": "FSDJump", "StarSystem": self.system, "StarPos": [0, 0, 0]})
        self.controller._genus_hints[self.body] = [TUSSOCK]
        self.status(0.0, 0.0)
        sample = {"event": "ScanOrganic", "Genus": TUSSOCK, "Species": "$Codex_Ent_Tussocks_06_Name;", "Species_Localised": "Tussock Pennatis"}
        self.event({**sample, "ScanType": "Log"})
        self.assertIsNotNone(self.controller.overlay_view())
        self.controller.dashboard_status({"Flags": 4})                       # Status.json names no body once the commander is away from the planet
        self.assertIsNone(self.controller.overlay_view())
        self.assertIsNone(self.controller._active_genus)
        self.status(0.0, 0.0)                                                # back at the planet: what was sampled is still there
        self.assertEqual(self.controller.overlay_view().genera[0].stage, 1)

    def test_the_srv_is_where_the_commander_launched_it(self):
        self.event({"event": "FSDJump", "StarSystem": self.system, "StarPos": [0, 0, 0]})
        self.status(0.0, 0.005)
        self.event({"event": "LaunchSRV"})
        self.assertEqual(self.controller._srv_pos, (0.0, 0.005))
        self.event({"event": "DockSRV"})
        self.assertIsNone(self.controller._srv_pos)


if __name__ == "__main__":
    unittest.main()
