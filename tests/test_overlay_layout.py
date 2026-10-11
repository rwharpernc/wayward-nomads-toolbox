"""Overlay placement: how big a pixel is on the canvas, anchors and offsets, and the shifted client (overlay_layout.py)."""
from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from plugin import overlay_layout as L  # noqa: E402


def screen(w, h, mode=L.MODE_FILL, ratio=1.0, pixel_sizes=True):
    return L.Screen(width=w, height=h, mode=mode, source="test", ratio=ratio, pixel_sizes=pixel_sizes)


# The measured case: 3840 x 2160 at 125% display scaling, EDMCModernOverlay in fill mode (3072 x 1728 logical pixels).
MEASURED = screen(3840, 2160, ratio=1.25)


class ScaleTests(unittest.TestCase):
    def test_the_measured_screen_has_the_pixel_size_the_overlay_really_uses(self):
        self.assertEqual(MEASURED.logical, (3072.0, 1728.0))
        ux, uy = MEASURED.units_per_px
        self.assertAlmostEqual(ux, 1280 / 3072)          # a 1280-wide outline covers 41.7% of the width, as photographed
        self.assertAlmostEqual(uy, 960 / 1728)

    def test_a_display_is_its_pixel_size_in_canvas_units(self):
        width, height = L.block_units((360, 300), MEASURED)
        self.assertAlmostEqual(width, 150.0)             # 360 px of 3072 is 150 of 1280 canvas units
        self.assertAlmostEqual(height, 300 * 960 / 1728)

    def test_the_whole_canvas_always_shows(self):
        self.assertEqual(MEASURED.visible, (1280, 960))
        self.assertEqual(screen(5120, 1440).visible, (1280, 960))

    def test_without_scaling_a_4k_screen_is_a_pixel_size_of_one_third(self):
        ux, uy = screen(3840, 2160).units_per_px
        self.assertAlmostEqual(ux, 1280 / 3840)
        self.assertAlmostEqual(uy, 960 / 2160)

    def test_fit_mode_uses_one_scale_for_both_directions(self):
        fit = screen(1920, 1080, mode=L.MODE_FIT)
        ux, uy = fit.units_per_px
        self.assertAlmostEqual(ux, uy)
        self.assertAlmostEqual(ux, 1 / min(1920 / 1280, 1080 / 960))

    def test_an_overlay_that_draws_in_canvas_units_is_not_rescaled(self):
        self.assertEqual(screen(3840, 2160, ratio=1.25, pixel_sizes=False).units_per_px, (1.0, 1.0))


class ScalingLineTests(unittest.TestCase):
    LINE = ("2026-10-03 12:01:59.003 UTC - DEBUG - Overlay scaling updated: window=3840x2160 px mode=fill base_scale=2.4000 "
            "scale_x=3.000 scale_y=3.000 diag=3.00 scaled=3072.0x2304.0 offset=(0.0,0.0) overflow_x=0 overflow_y=1")

    def test_the_window_mode_and_display_scaling_are_read(self):
        width, height, mode, ratio = L.parse_scaling_line("noise\n" + self.LINE + "\nmore noise")
        self.assertEqual((width, height, mode), (3840, 2160, "fill"))
        self.assertAlmostEqual(ratio, 1.25)

    def test_the_newest_line_wins(self):
        older = self.LINE.replace("3840x2160", "800x600").replace("mode=fill", "mode=fit").replace("base_scale=2.4000", "base_scale=0.5000").replace("scale_x=3.000", "scale_x=0.625")
        self.assertEqual(L.parse_scaling_line(older + "\n" + self.LINE)[:3], (3840, 2160, "fill"))
        self.assertEqual(L.parse_scaling_line(self.LINE + "\n" + older)[:3], (800, 600, "fit"))

    def test_nothing_usable_gives_none(self):
        self.assertIsNone(L.parse_scaling_line("no scaling here"))
        self.assertIsNone(L.parse_scaling_line(self.LINE.replace("mode=fill", "mode=stretch")))
        self.assertIsNone(L.parse_scaling_line(self.LINE.replace("base_scale=2.4000", "base_scale=0.0")))
        self.assertIsNone(L.parse_scaling_line(self.LINE.replace("scale_x=3.000", "scale_x=90.0")))   # a 37x ratio is not a monitor


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
        text = L.describe_screen(L.Screen(3840, 2160, L.MODE_FILL, "EDMCModernOverlay log", 2, 1.25))
        for expected in ("3840 x 2160", "full screen", "125%", "3072 x 1728", "whole screen"):
            self.assertIn(expected, text)

    def test_the_description_for_an_overlay_that_uses_canvas_units(self):
        self.assertIn("canvas units", L.describe_screen(L.Screen(1920, 1080, pixel_sizes=False)))


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
    """On the measured screen a pixel is 0.4167 canvas units across and 0.5556 down."""

    def origin(self, h, v, dx, dy, size=(360, 300), scr=MEASURED):
        return L.block_origin(L.Placement(h, v, dx, dy), size, scr)

    def test_a_right_aligned_display_stops_where_the_overlay_would_squash_it(self):
        # Ideally a 360 px display (150 canvas units) would start at 1130 to end on the screen's right edge. But across the
        # screen the overlay clamps x + width (a pixel width) to 1280, so past 1280 - 360 = 920 it would be squashed.
        x, y = self.origin("right", "top", 0, 0)
        self.assertEqual(x, 1280 - 360)
        self.assertEqual(y, 0)

    def test_the_clamp_is_only_on_the_axis_the_overlay_does_not_stretch(self):
        self.assertEqual(MEASURED.clamped, (True, False))                      # wide screen: across is clamped, down is free
        self.assertEqual(screen(1280, 1024).clamped, (False, True))             # taller than 4:3: the other way round
        self.assertEqual(screen(1920, 1080, mode=L.MODE_FIT).clamped, (True, True))
        self.assertEqual(screen(1920, 1080, pixel_sizes=False).clamped, (False, False))

    def test_on_a_free_axis_a_display_does_reach_the_edge(self):
        _x, y = self.origin("left", "bottom", 0, 0)
        self.assertEqual(y, round(960 - 300 * 960 / 1728))                      # down the wide screen: flush with the bottom
        tall = screen(1280, 1024)                                               # across is free, down is clamped
        self.assertEqual(self.origin("right", "top", 0, 0, scr=tall)[0], 1280 - 360)   # 1 px = 1 unit here, so same as clamp
        wide_tall = screen(2560, 2048, ratio=1.0)                                # 1 px = 0.5 units across
        x, _y = self.origin("right", "top", 0, 0, scr=wide_tall)
        self.assertEqual(x, 1280 - 180)                                         # 360 px is 180 units, ends on the edge
        self.assertEqual(wide_tall.clamped, (False, True))

    def test_offsets_are_screen_pixels_not_canvas_units(self):
        x, y = self.origin("left", "top", 100, 100)
        self.assertEqual((x, y), (round(100 * 1280 / 3072), round(100 * 960 / 1728)))   # 100 px is 42 across and 56 down
        _x, y = self.origin("left", "bottom", 100, 100)
        self.assertEqual(y, round(960 - 300 * 960 / 1728 - 100 * 960 / 1728))

    def test_centers(self):
        x, y = self.origin("center", "middle", 0, 0)
        self.assertEqual(x, round((1280 - 150) / 2))
        self.assertEqual(y, round((960 - 300 * 960 / 1728) / 2))

    def test_the_same_placement_follows_the_screen(self):
        # Down the screen the canvas is stretched, so "bottom" is the bottom whatever the monitor shape.
        full_hd = screen(1920, 1080)
        self.assertEqual(self.origin("left", "bottom", 0, 0, scr=full_hd)[1], round(960 - 300 * 960 / 1080))
        ultrawide = screen(5120, 1440)
        self.assertEqual(self.origin("left", "bottom", 0, 0, scr=ultrawide)[1], round(960 - 300 * 960 / 1440))
        # A fit overlay keeps one scale for both directions, and clamps both, so the bottom stops at 960 - 300 px.
        fit = screen(1920, 1080, mode=L.MODE_FIT)
        self.assertEqual(self.origin("left", "bottom", 0, 0, scr=fit)[1], 960 - 300)

    def test_a_display_is_kept_on_the_canvas(self):
        self.assertEqual(self.origin("left", "top", 99999, 99999), (1280 - 360, round(960 - 300 * 960 / 1728)))
        self.assertEqual(self.origin("right", "bottom", 99999, 99999), (0, 0))
        self.assertEqual(self.origin("left", "top", -500, -500), (0, 0))

    def test_a_display_bigger_than_the_canvas_starts_at_the_top_left(self):
        self.assertEqual(L.block_origin(L.Placement("center", "middle", 0, 0), (5000, 4000), MEASURED), (0, 0))

    def test_custom_is_taken_exactly_in_canvas_units(self):
        self.assertEqual(L.block_origin(L.custom_placement(700, 900), (300, 100), MEASURED), (700, 900))

    def test_canvas_unit_overlays_anchor_directly(self):
        classic = screen(1920, 1080, pixel_sizes=False)
        self.assertEqual(self.origin("right", "top", 0, 0, scr=classic)[0], 1280 - 360)


class PlanTests(unittest.TestCase):
    """A display on the far side of the overlay's clamp is drawn where the clamp allows and its group is offset the rest."""
    SIZE = (420, 226)

    def plan(self, placement, scr=MEASURED, can_offset=True, block=None):
        return L.plan_origin(placement, block or self.SIZE, self.SIZE, scr, can_offset)

    def test_a_right_aligned_display_is_drawn_at_the_clamp_and_offset_to_the_edge(self):
        plan = self.plan(L.Placement("right", "top", 0, 0))
        self.assertEqual(plan.x, 1280 - 420)                             # the furthest the clamp allows for 420 px
        self.assertAlmostEqual(plan.offset_x, (1280 - 420 * 1280 / 3072) - (1280 - 420), places=2)
        # Drawn at 860 and moved 245 right, the display's left edge is at 1105 and its right edge (420 px = 175 units) at 1280.
        self.assertAlmostEqual(plan.x + plan.offset_x + 420 * 1280 / 3072, 1280, delta=0.5)

    def test_the_pixel_offset_from_the_edge_is_kept(self):
        plan = self.plan(L.Placement("right", "top", 40, 0))
        self.assertAlmostEqual(plan.x + plan.offset_x + (420 + 40) * 1280 / 3072, 1280, delta=0.5)

    def test_a_display_that_fits_before_the_clamp_needs_no_offset(self):
        for placement in (L.Placement("left", "top", 40, 40), L.Placement("center", "middle", 0, 0), L.Placement("center", "top", 100, 0)):
            plan = self.plan(placement)
            self.assertEqual(plan.offset_x, 0.0, placement)
            self.assertEqual((plan.x, plan.y), L.block_origin(placement, self.SIZE, MEASURED), placement)

    def test_the_offset_is_the_same_whatever_the_displays_current_width(self):
        # A display's content changes width, but its group's offset is one fixed number, so the drawn position must not follow it.
        narrow = self.plan(L.Placement("right", "top", 0, 0), block=(300, 226))
        wide = self.plan(L.Placement("right", "top", 0, 0), block=(420, 226))
        self.assertEqual((narrow.x, narrow.offset_x), (wide.x, wide.offset_x))

    def test_without_an_offset_the_display_just_stops_at_the_clamp(self):
        plan = self.plan(L.Placement("right", "top", 0, 0), can_offset=False)
        self.assertEqual((plan.x, plan.offset_x), (1280 - 420, 0.0))

    def test_no_offset_where_the_overlay_does_not_clamp_across(self):
        classic = screen(1920, 1080, pixel_sizes=False)
        self.assertEqual(self.plan(L.Placement("right", "top", 0, 0), scr=classic).offset_x, 0.0)
        tall = screen(1280, 1024)                       # across is free, down is clamped
        self.assertEqual(self.plan(L.Placement("right", "top", 0, 0), scr=tall).offset_x, 0.0)

    def test_down_the_screen_nothing_is_offset(self):
        plan = self.plan(L.Placement("left", "bottom", 0, 0))
        self.assertEqual(plan.y, round(960 - 226 * 960 / 1728))          # free axis: flush with the bottom, no offset needed

    def test_shift_uses_the_plan(self):
        shift = L.shift_for(L.Placement("right", "top", 0, 0), (20, 100, 420, 226), MEASURED, self.SIZE, True)
        self.assertEqual(shift, (1280 - 420 - 20, 0 - 100))
        plain = L.shift_for(L.Placement("right", "top", 0, 0), (20, 100, 420, 226), MEASURED)
        self.assertEqual(plain, (1280 - 420 - 20, 0 - 100))                # the same raw spot; only the offset differs


class ShiftTests(unittest.TestCase):
    def test_shift_is_target_minus_where_it_is_drawn(self):
        self.assertEqual(L.shift_for(L.Placement("left", "top", 0, 0), (20, 292, 300, 100), MEASURED), (-20, -292))
        self.assertEqual(L.shift_for(L.Placement("right", "top", 0, 0), (20, 292, 300, 100), MEASURED),
                         (1280 - 300 - 20, -292))      # the overlay would squash it past 1280 - 300


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
