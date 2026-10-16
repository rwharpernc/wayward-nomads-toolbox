"""Route status (plugin/route_plan.py): star kinds, reading a plotted route, and where the ship is on it."""

from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from plugin import route_plan as R  # noqa: E402


def hop(name, star="", x=0.0):
    return {"StarSystem": name, "StarClass": star, "StarPos": [x, 0.0, 0.0]}


class StarKindTests(unittest.TestCase):
    def test_neutron_stars_and_every_white_dwarf_class_are_supercharges(self):
        self.assertEqual(R.star_kind("N"), R.KIND_NEUTRON)
        for star in ("D", "DA", "DAB", "DB", "DC", "DQ", "DX"):
            self.assertEqual(R.star_kind(star), R.KIND_WHITE_DWARF, star)

    def test_scoopable_and_unscoopable_stars(self):
        for star in "OBAFGKM":
            self.assertEqual(R.star_kind(star), R.KIND_SCOOPABLE, star)
        for star in ("H", "WN", "CJ", "S", "MS", "TTS", "AeBe", "T", "L", "Y"):
            self.assertEqual(R.star_kind(star), R.KIND_NO_SCOOP, star)
        self.assertEqual(R.star_kind(""), R.KIND_UNKNOWN)

    def test_the_star_column_text(self):
        self.assertEqual(R.star_tag("N")[0], "NEUTRON")
        self.assertEqual(R.star_tag("DAB")[0], "WHITE DWARF")
        self.assertEqual(R.star_tag("H")[0], "BLACK HOLE")
        self.assertEqual(R.star_tag("K")[0], "K")
        self.assertEqual(R.star_tag("")[0], "")


class ParseRouteTests(unittest.TestCase):
    def test_a_route_keeps_its_order_classes_and_positions(self):
        hops = R.parse_route({"Route": [hop("A", "G", 0), hop("B", "N", 60)]})
        self.assertEqual([(h.name, h.star_class, h.pos) for h in hops], [("A", "G", (0.0, 0.0, 0.0)), ("B", "N", (60.0, 0.0, 0.0))])

    def test_malformed_input_is_skipped_not_raised(self):
        self.assertEqual(R.parse_route(None), [])
        self.assertEqual(R.parse_route({"Route": "x"}), [])
        hops = R.parse_route({"Route": [None, {"StarSystem": ""}, {"StarSystem": "B", "StarClass": 3, "StarPos": [1, 2]}]})
        self.assertEqual([(h.name, h.star_class, h.pos) for h in hops], [("B", "", None)])

    def test_the_length_needs_every_position(self):
        hops = R.parse_route({"Route": [hop("A", x=0), hop("B", x=30), hop("C", x=100)]})
        self.assertEqual(R.route_length(hops), 100.0)
        self.assertIsNone(R.route_length(hops + [R.Hop("D")]))


class TrackerTests(unittest.TestCase):
    def tracker(self, system="A"):
        t = R.RouteTracker(system=system)
        t.set_route(R.parse_route({"Route": [hop("A", "G", 0), hop("B", "N", 50), hop("C", "K", 100), hop("D", "DA", 150)]}))
        return t

    def test_what_is_left_follows_the_ship(self):
        t = self.tracker("A")
        self.assertEqual([h.name for h in t.remaining()], ["B", "C", "D"])
        t.handle_event({"event": "FSDJump", "StarSystem": "C", "FuelUsed": 2.5})
        self.assertEqual([h.name for h in t.remaining()], ["D"])
        self.assertEqual(t.last_fuel_used, 2.5)
        self.assertEqual(t.distance_left(), 50.0)

    def test_the_next_supercharge_and_the_counts(self):
        t = self.tracker("A")
        number, found = t.next_supercharge()
        self.assertEqual((number, found.name), (1, "B"))
        self.assertEqual(t.special_counts(t.remaining()), (1, 1))
        t.handle_event({"event": "FSDJump", "StarSystem": "B"})
        number, found = t.next_supercharge()
        self.assertEqual((number, found.name), (2, "D"))

    def test_off_the_route_nothing_applies_until_a_new_one_is_plotted(self):
        t = self.tracker("A")
        t.handle_event({"event": "FSDJump", "StarSystem": "Elsewhere"})
        self.assertFalse(t.on_route())
        self.assertEqual(t.remaining(), [])

    def test_the_route_is_shown_before_the_ships_place_is_known(self):
        t = self.tracker("")
        self.assertEqual([h.name for h in t.remaining()], ["B", "C", "D"])

    def test_clearing_and_the_navroute_event(self):
        t = self.tracker("A")
        self.assertTrue(t.handle_event({"event": "NavRoute"}))
        self.assertFalse(t.handle_event({"event": "FSDJump", "StarSystem": "B"}))
        t.handle_event({"event": "NavRouteClear"})
        self.assertEqual(t.remaining(), [])

    def test_loadout_gives_the_jump_range_and_the_tank(self):
        t = R.RouteTracker()
        t.handle_event({"event": "Loadout", "MaxJumpRange": 61.4, "FuelCapacity": {"Main": 32.0}})
        self.assertEqual((t.jump_range, t.fuel.capacity), (61.4, 32.0))
        t.handle_event({"event": "Loadout", "MaxJumpRange": 0})
        self.assertIsNone(t.jump_range)


if __name__ == "__main__":
    unittest.main()
