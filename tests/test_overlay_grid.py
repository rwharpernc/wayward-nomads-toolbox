"""The layout editor's conversions (overlay_grid.py): a dropped box becomes a placement and a placement becomes a box, so "0" is the edge and what you
drop is what you get. Pure: no Tk."""
from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from plugin import overlay_grid as G  # noqa: E402
from plugin import overlay_layout as L  # noqa: E402

SCREEN = (1920.0, 1080.0)


class Snap(unittest.TestCase):
    def test_snap_rounds_to_the_step(self):
        self.assertEqual((G.snap(57, 40), G.snap(61, 40), G.snap(20, 40), G.snap(100, 40), G.snap(13.4, 1)), (40, 80, 40, 120, 13))


class DropToPlacement(unittest.TestCase):
    def test_a_box_near_the_top_left_corner_snaps_flush(self):
        placement = G.placement_from_rect(6, 9, 300, 200, SCREEN)
        self.assertEqual(placement, L.Placement("left", "top", 0, 0))

    def test_a_box_near_the_bottom_right_snaps_flush_to_both_edges(self):
        placement = G.placement_from_rect(1920 - 300 - 5, 1080 - 200 - 11, 300, 200, SCREEN)
        self.assertEqual((placement.h, placement.v, placement.dx, placement.dy), ("right", "bottom", 0, 0))

    def test_the_spot_is_the_third_the_center_is_in_and_the_offset_is_inward_from_that_edge(self):
        placement = G.placement_from_rect(240, 400, 300, 200, SCREEN, grid=40)
        self.assertEqual((placement.h, placement.v, placement.dx), ("left", "middle", 240))
        placement = G.placement_from_rect(1920 - 300 - 160, 100, 300, 200, SCREEN, grid=40)
        self.assertEqual((placement.h, placement.v, placement.dx, placement.dy), ("right", "top", 160, 120))

    def test_a_box_near_the_middle_snaps_to_the_center_line(self):
        placement = G.placement_from_rect(960 - 150 + 8, 100, 300, 200, SCREEN)
        self.assertEqual((placement.h, placement.dx), ("center", 0))
        placement = G.placement_from_rect(960 - 150 + 200, 100, 300, 200, SCREEN, grid=40)
        self.assertEqual((placement.h, placement.dx), ("center", 200))
        placement = G.placement_from_rect(960 - 150 - 200, 100, 300, 200, SCREEN, grid=40)
        self.assertEqual((placement.h, placement.dx), ("center", -200))

    def test_a_box_dragged_off_the_screen_is_kept_on_it(self):
        placement = G.placement_from_rect(-50, -50, 300, 200, SCREEN)
        self.assertEqual((placement.h, placement.v, placement.dx, placement.dy), ("left", "top", 0, 0))

    def test_no_snapping_keeps_the_exact_offset(self):
        placement = G.placement_from_rect(37, 29, 300, 200, SCREEN, grid=1, edge=0)
        self.assertEqual((placement.dx, placement.dy), (37, 29))


class PlacementToBox(unittest.TestCase):
    def test_every_spot_puts_the_box_where_overlay_placement_does(self):
        size = (300.0, 200.0)
        self.assertEqual(G.rect_from_placement(L.Placement("left", "top", 40, 20), size, SCREEN), (40, 20))
        self.assertEqual(G.rect_from_placement(L.Placement("right", "bottom", 40, 20), size, SCREEN), (1920 - 300 - 40, 1080 - 200 - 20))
        self.assertEqual(G.rect_from_placement(L.Placement("center", "middle", 0, 0), size, SCREEN), (810, 440))
        self.assertEqual(G.rect_from_placement(L.Placement("center", "bottom", -230, 0), size, SCREEN), (810 - 230, 880))

    def test_a_drop_and_a_read_back_agree(self):
        size = (300.0, 200.0)
        for left, top in ((0, 0), (240, 400), (1000, 700), (1620, 880), (810, 0)):
            placement = G.placement_from_rect(left, top, *size, SCREEN, grid=1, edge=0)
            self.assertEqual(G.rect_from_placement(placement, size, SCREEN), (left, top), placement)

    def test_an_exact_placement_is_converted_from_canvas_units(self):
        left, top = G.rect_from_placement(L.custom_placement(640, 480), (100.0, 100.0), SCREEN, (1280 / 1920, 960 / 1080))
        self.assertEqual((left, top), (960, 540))

    def test_a_box_bigger_than_the_screen_is_pinned_to_the_corner(self):
        self.assertEqual(G.rect_from_placement(L.Placement("right", "bottom", 0, 0), (3000.0, 2000.0), SCREEN), (0.0, 0.0))


class Sizes(unittest.TestCase):
    def test_the_picture_sizes_grow_and_the_default_is_the_smallest(self):
        widths = [w for _label, w in G.SIZE_CHOICES]
        self.assertEqual(widths, sorted(widths))
        self.assertEqual(dict(G.SIZE_CHOICES)[G.DEFAULT_SIZE], widths[0])


class Clients(unittest.TestCase):
    """Circles must be moved with everything else drawn through a placed client, or they land away from their card."""

    class Recorder:
        def __init__(self):
            self.circles = []

        def send_circle(self, shape_id, color, fill, x, y, radius, ttl=8, thickness=None):
            self.circles.append((shape_id, color, x, y, radius, ttl))

    def test_a_shifted_client_moves_circles(self):
        recorder = self.Recorder()
        L.ShiftedClient(recorder, 100, -20).send_circle("c", "#fff", "#000", 10, 50, 7, ttl=4)
        self.assertEqual(recorder.circles, [("c", "#fff", 110, 30, 7, 4)])

    def test_a_hidden_client_clears_circles(self):
        recorder = self.Recorder()
        L.HiddenClient(recorder).send_circle("c", "#fff", "#000", 10, 50, 7, ttl=4)
        self.assertEqual(recorder.circles[0][1], "")
        self.assertEqual(recorder.circles[0][5], 1)


class Description(unittest.TestCase):
    def test_describe_reads_plainly(self):
        self.assertEqual(G.describe(L.Placement("left", "top", 0, 120)), "Top left: 0 px from the left, 120 px from the top")
        self.assertEqual(G.describe(L.Placement("center", "bottom", -230, 0)), "Bottom center: -230 px from the middle, 0 px from the bottom")


if __name__ == "__main__":
    unittest.main()
