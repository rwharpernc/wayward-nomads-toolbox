"""Tests for neutron_finder.pick_nearest against canned Spansh responses."""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from plugin import neutron_finder  # noqa: E402


def _body(system, distance, region="Inner Orion Spur"):
    return {"system_name": system, "distance": distance, "system_region": region}


class PickNearestTests(unittest.TestCase):
    def test_returns_closest(self):
        found = neutron_finder.pick_nearest({"results": [_body("A", 12.5), _body("B", 20)]}, None)
        self.assertEqual((found.system, found.distance_ly), ("A", 12.5))

    def test_skips_current_system_case_insensitively(self):
        found = neutron_finder.pick_nearest({"results": [_body("PSR J1", 0.0), _body("B", 20)]}, "psr j1")
        self.assertEqual(found.system, "B")

    def test_no_usable_result_raises(self):
        with self.assertRaises(ValueError):
            neutron_finder.pick_nearest({"results": [_body("Here", 0.0)]}, "Here")
        with self.assertRaises(ValueError):
            neutron_finder.pick_nearest({"results": []}, None)
        with self.assertRaises(ValueError):
            neutron_finder.pick_nearest({"error": "x"}, None)

    def test_display_name_is_capped(self):
        long_name = "X" * 200
        self.assertEqual(len(neutron_finder.display_name(long_name)), neutron_finder.MAX_NAME_CHARS)
        self.assertEqual(neutron_finder.display_name("Sol"), "Sol")


if __name__ == "__main__":
    unittest.main()
