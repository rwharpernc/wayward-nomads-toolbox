"""
Unit tests for plugin/canonn_poi_data.py's find_nearest() - specifically the
exclude_systems filter added for the "Missing Codex Nearby" cross-reference
with codex_completionist.py. No network calls - CanonnPoi objects are built
by hand.

Run with:
    python -m unittest discover -s tests
"""

from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from plugin.canonn_poi_data import CanonnPoi, find_nearest  # noqa: E402


def _poi(system: str, x: float, y: float, z: float) -> CanonnPoi:
    return CanonnPoi(category="Guardian", system=system, x=x, y=y, z=z, instructions="", url=None)


class FindNearestTests(unittest.TestCase):
    def test_returns_closest_with_no_exclusions(self) -> None:
        pois = [_poi("Far", 100, 0, 0), _poi("Near", 1, 0, 0)]
        found = find_nearest(pois, 0, 0, 0)
        self.assertIsNotNone(found)
        poi, distance = found
        self.assertEqual(poi.system, "Near")
        self.assertAlmostEqual(distance, 1.0)

    def test_excludes_matching_system_case_insensitively(self) -> None:
        pois = [_poi("Near", 1, 0, 0), _poi("Far", 100, 0, 0)]
        found = find_nearest(pois, 0, 0, 0, exclude_systems={"near"})
        self.assertIsNotNone(found)
        poi, _distance = found
        self.assertEqual(poi.system, "Far")

    def test_all_excluded_returns_none(self) -> None:
        pois = [_poi("Near", 1, 0, 0)]
        self.assertIsNone(find_nearest(pois, 0, 0, 0, exclude_systems={"Near"}))

    def test_empty_pois_returns_none(self) -> None:
        self.assertIsNone(find_nearest([], 0, 0, 0))

    def test_no_exclude_set_behaves_like_none(self) -> None:
        pois = [_poi("Near", 1, 0, 0)]
        found = find_nearest(pois, 0, 0, 0, exclude_systems=set())
        self.assertIsNotNone(found)


if __name__ == "__main__":
    unittest.main()
