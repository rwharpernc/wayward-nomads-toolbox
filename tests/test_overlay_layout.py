"""Overlay placement: the visible part of the canvas, anchors and offsets, and the shifted client (overlay_layout.py)."""
from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from plugin import overlay_layout as L  # noqa: E402


def screen(w, h, mode=L.MODE_FILL):
    return L.Screen(width=w, height=h, mode=mode, source="test")


class VisibleAreaTests(unittest.TestCase):
    def test_fit_always_shows_the_whole_canvas(self):
        for w, h in ((3840, 2160), (1024, 768), (5120, 1440)):
            self.assertEqual(L.visible_area(w, h, L.MODE_FIT), (1280, 960))

    def test_fill_on_the_common_shapes(self):
        self.assertEqual(L.visible_area(3840, 2160, L.MODE_FILL), (1280, 720))     # 16:9
        self.assertEqual(L.visible_area(2560, 1600, L.MODE_FILL), (1280, 800))     # 16:10
        self.assertEqual(L.visible_area(3440, 1440, L.MODE_FILL), (1280, 536))     # 21:9
        self.assertEqual(L.visible_area(5120, 1440, L.MODE_FILL), (1280, 360))     # 32:9
        self.assertEqual(L.visible_area(1024, 768, L.MODE_FILL), (1280, 960))      # 4:3 is the canvas
        self.assertEqual(L.visible_area(1280, 1024, L.MODE_FILL), (1200, 960))     # 5:4 is narrower

    def test_nonsense_sizes_show_the_whole_canvas(self):
        self.assertEqual(L.visible_area(0, 1080, L.MODE_FILL), (1280, 960))


class DisplaySettingsTests(unittest.TestCase):
    XML = ('<?xml version="1.0" encoding="UTF-8" ?><DisplayConfig><ScreenWidth>3840</ScreenWidth>'
           "<ScreenHeight>2160</ScreenHeight><FullScreen>2</FullScreen><Monitor>0</Monitor></DisplayConfig>")

    def test_reads_the_size_and_mode(self):
        self.assertEqual(L.parse_display_settings(self.XML), (3840, 2160, 2))

    def test_a_missing_mode_is_none_not_a_failure(self):
        xml = "<DisplayConfig><ScreenWidth>1920</ScreenWidth><ScreenHeight>1080</ScreenHeight></DisplayConfig>"
        self.assertEqual(L.parse_display_settings(xml), (1920, 1080, None))

    def test_unusable_files_give_none(self):
        self.assertIsNone(L.parse_display_settings("not xml"))
        self.assertIsNone(L.parse_display_settings("<DisplayConfig/>"))
        self.assertIsNone(L.parse_display_settings(
            "<DisplayConfig><ScreenWidth>abc</ScreenWidth><ScreenHeight>1080</ScreenHeight></DisplayConfig>"))
        self.assertIsNone(L.parse_display_settings(     # a believable monitor, not 100:1
            "<DisplayConfig><ScreenWidth>10000</ScreenWidth><ScreenHeight>100</ScreenHeight></DisplayConfig>"))

    def test_the_description_says_what_it_means(self):
        text = L.describe_screen(L.Screen(3840, 2160, L.MODE_FILL, "DisplaySettings.xml", 2))
        self.assertIn("3840 x 2160", text)
        self.assertIn("full screen", text)
        self.assertIn("1280 x 720", text)


class PlacementTextTests(unittest.TestCase):
    def test_round_trip(self):
        p = L.Placement("right", "bottom", 20, 40)
        self.assertEqual(L.format_placement(p), "right,bottom,20,40")
        self.assertEqual(L.parse_placement("right,bottom,20,40", L.Placement()), p)
        c = L.custom_placement(700, 60)
        self.assertEqual(L.format_placement(c), "custom,700,60")
        self.assertEqual(L.parse_placement("custom,700,60", L.Placement()), c)

    def test_damaged_text_gives_the_default(self):
        default = L.Placement("center", "top", 0, 60)
        for text in ("", None, "nonsense", "left,top,x,y", "up,top,1,1", "left,top,1", "custom,1"):
            self.assertEqual(L.parse_placement(text, default), default, text)

    def test_negative_offsets_are_allowed(self):
        self.assertEqual(L.parse_placement("center,middle,-30,15", L.Placement()), L.Placement("center", "middle", -30, 15))


class PresetTests(unittest.TestCase):
    def test_every_spot_round_trips_through_its_menu_text(self):
        for label, h, v in L.PRESETS:
            placement = L.placement_from_choice(label, 12, 34)
            self.assertEqual((placement.h, placement.v, placement.dx, placement.dy), (h, v, 12, 34))
            self.assertEqual(L.preset_label(placement), label)

    def test_exact_position_takes_the_numbers_as_canvas_coordinates(self):
        placement = L.placement_from_choice(L.EXACT_LABEL, 700, 60)
        self.assertTrue(placement.custom)
        self.assertEqual((placement.x, placement.y), (700, 60))
        self.assertEqual(L.preset_label(placement), L.EXACT_LABEL)

    def test_there_are_nine_spots_and_the_exact_choice(self):
        self.assertEqual(len(L.PRESET_LABELS), 10)
        self.assertEqual(len(set(L.PRESET_LABELS)), 10)

    def test_an_unknown_choice_is_refused(self):
        with self.assertRaises(ValueError):
            L.placement_from_choice("Somewhere", 0, 0)


class BlockOriginTests(unittest.TestCase):
    S = screen(3840, 2160)          # visible 1280 x 720

    def origin(self, h, v, dx, dy, size=(300, 100)):
        return L.block_origin(L.Placement(h, v, dx, dy), size, self.S)

    def test_corners(self):
        self.assertEqual(self.origin("left", "top", 20, 10), (20, 10))
        self.assertEqual(self.origin("right", "top", 20, 10), (1280 - 300 - 20, 10))
        self.assertEqual(self.origin("left", "bottom", 20, 10), (20, 720 - 100 - 10))
        self.assertEqual(self.origin("right", "bottom", 20, 10), (960, 610))

    def test_centers(self):
        self.assertEqual(self.origin("center", "middle", 0, 0), (490, 310))
        self.assertEqual(self.origin("center", "top", 0, 60), (490, 60))
        self.assertEqual(self.origin("center", "middle", 30, -20), (520, 290))

    def test_the_same_placement_follows_the_screen_shape(self):
        bottom_left = L.Placement("left", "bottom", 20, 20)
        wide = L.block_origin(bottom_left, (300, 100), screen(5120, 1440))     # visible height 360
        tall = L.block_origin(bottom_left, (300, 100), screen(3840, 2160))     # 720
        self.assertEqual((wide[1], tall[1]), (360 - 100 - 20, 720 - 100 - 20))
        self.assertEqual(L.block_origin(bottom_left, (300, 100), screen(1024, 768, L.MODE_FIT))[1], 960 - 100 - 20)

    def test_a_display_is_kept_inside_the_visible_area(self):
        self.assertEqual(self.origin("left", "top", 5000, 5000), (980, 620))
        self.assertEqual(self.origin("right", "bottom", 5000, 5000), (0, 0))
        self.assertEqual(self.origin("left", "top", -50, -50), (0, 0))

    def test_a_display_bigger_than_the_area_starts_at_the_top_left(self):
        self.assertEqual(L.block_origin(L.Placement("center", "middle", 0, 0), (400, 900), self.S), (440, 0))
        self.assertEqual(L.block_origin(L.Placement("right", "bottom", 0, 0), (2000, 900), self.S), (0, 0))

    def test_custom_is_taken_exactly(self):
        self.assertEqual(L.block_origin(L.custom_placement(700, 900), (300, 100), self.S), (700, 900))


class ShiftTests(unittest.TestCase):
    def test_shift_is_target_minus_where_it_is_drawn(self):
        s = screen(3840, 2160)
        self.assertEqual(L.shift_for(L.Placement("left", "top", 0, 0), (20, 292, 300, 100), s), (-20, -292))
        self.assertEqual(L.shift_for(L.Placement("right", "top", 0, 0), (20, 292, 300, 100), s), (1280 - 300 - 20, -292))


class Recorder:
    def __init__(self):
        self.calls = []
        self.marker = "kept"

    def send_message(self, *a, **k):
        self.calls.append(("message", a, k))

    def send_shape(self, *a, **k):
        self.calls.append(("shape", a, k))

    def send_vector(self, *a, **k):
        self.calls.append(("vector", a, k))


class ShiftedClientTests(unittest.TestCase):
    def test_everything_drawn_is_moved(self):
        rec = Recorder()
        client = L.ShiftedClient(rec, 100, -10)
        client.send_message("a", "hi", "red", 5, 20, ttl=3, size="large")
        client.send_shape("b", "rect", "c", "f", 1, 2, 30, 40, ttl=9, thickness=2)
        client.send_vector("c", [{"x": 1, "y": 2, "marker": "cross"}, {"x": 3, "y": 4}], "red", ttl=4)
        self.assertEqual(rec.calls[0], ("message", ("a", "hi", "red", 105, 10), {"ttl": 3, "size": "large"}))
        self.assertEqual(rec.calls[1], ("shape", ("b", "rect", "c", "f", 101, -8, 30, 40), {"ttl": 9, "thickness": 2}))
        self.assertEqual(rec.calls[2][1][1], [{"x": 101, "y": -8, "marker": "cross"}, {"x": 103, "y": -6}])

    def test_the_callers_points_are_not_changed(self):
        points = [{"x": 1, "y": 2}]
        L.ShiftedClient(Recorder(), 5, 5).send_vector("c", points, "red")
        self.assertEqual(points, [{"x": 1, "y": 2}])

    def test_other_attributes_reach_the_real_client(self):
        self.assertEqual(L.ShiftedClient(Recorder(), 1, 1).marker, "kept")


class MigrationTests(unittest.TestCase):
    SLOT = L.Slot("demo", "Demo", L.Placement("center", "top", 0, 60), (460, 84), "x_key", "y_key", (700, 60))

    def test_untouched_old_settings_give_the_new_default(self):
        self.assertEqual(L.migrated_placement(self.SLOT, 700, 60), self.SLOT.default)
        self.assertEqual(L.migrated_placement(self.SLOT, None, None), self.SLOT.default)

    def test_a_position_chosen_by_hand_is_kept(self):
        self.assertEqual(L.migrated_placement(self.SLOT, 900, 40), L.custom_placement(900, 40))

    def test_setting_keys(self):
        self.assertEqual(L.setting_key("colonisation"), "wntb_overlay_place_colonisation")
        with self.assertRaises(ValueError):
            L.setting_key("../bad")


if __name__ == "__main__":
    unittest.main()
