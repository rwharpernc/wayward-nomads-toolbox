"""
Unit tests for plugin/mining_coverage.py.

Pure logic tests - no EDMC runtime needed. Run with:
    python -m unittest discover -s tests
"""

from __future__ import annotations

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from plugin import mining_coverage as coverage  # noqa: E402

_EARTH_RADIUS_M = 6_371_000.0


class BodyCoverageTests(unittest.TestCase):
    def test_first_point_sets_center_and_is_recorded(self) -> None:
        body = coverage.BodyCoverage()
        added = body.record(10.0, 20.0, _EARTH_RADIUS_M)
        self.assertTrue(added)
        self.assertEqual(body.center, coverage.CoveragePoint(10.0, 20.0))
        self.assertEqual(len(body.points), 1)

    def test_point_too_close_to_last_is_rejected(self) -> None:
        body = coverage.BodyCoverage()
        body.record(10.0, 20.0, _EARTH_RADIUS_M)
        # ~11m north - well under STAMP_M (250m).
        added = body.record(10.0001, 20.0, _EARTH_RADIUS_M)
        self.assertFalse(added)
        self.assertEqual(len(body.points), 1)

    def test_point_far_enough_is_recorded(self) -> None:
        body = coverage.BodyCoverage()
        body.record(10.0, 20.0, _EARTH_RADIUS_M)
        # ~1.1km north - comfortably over STAMP_M.
        added = body.record(10.01, 20.0, _EARTH_RADIUS_M)
        self.assertTrue(added)
        self.assertEqual(len(body.points), 2)

    def test_points_capped_at_max(self) -> None:
        body = coverage.BodyCoverage()
        original_max = coverage.MAX_POINTS_PER_BODY
        coverage.MAX_POINTS_PER_BODY = 3
        try:
            lat = 10.0
            for _ in range(5):
                body.record(lat, 20.0, _EARTH_RADIUS_M)
                lat += 0.01  # each step is well over STAMP_M
            self.assertEqual(len(body.points), 3)
            # The oldest points were dropped, not the newest.
            self.assertAlmostEqual(body.points[-1].latitude, lat - 0.01, places=6)
        finally:
            coverage.MAX_POINTS_PER_BODY = original_max


class CoverageRepositoryTests(unittest.TestCase):
    def test_record_and_for_body_round_trip(self) -> None:
        repo = coverage.CoverageRepository()
        with tempfile.TemporaryDirectory() as plugin_dir:
            repo.load(plugin_dir)
            repo.record("Sol", "Earth", 10.0, 20.0, _EARTH_RADIUS_M)
            found = repo.for_body("Sol", "Earth")
            self.assertIsNotNone(found)
            self.assertEqual(len(found.points), 1)

    def test_for_body_is_case_insensitive(self) -> None:
        repo = coverage.CoverageRepository()
        with tempfile.TemporaryDirectory() as plugin_dir:
            repo.load(plugin_dir)
            repo.record("Sol", "Earth", 10.0, 20.0, _EARTH_RADIUS_M)
            self.assertIsNotNone(repo.for_body("sol", "earth"))

    def test_unknown_body_returns_none(self) -> None:
        repo = coverage.CoverageRepository()
        self.assertIsNone(repo.for_body("Sol", "Earth"))
        self.assertIsNone(repo.for_body(None, None))

    def test_persists_across_reload(self) -> None:
        with tempfile.TemporaryDirectory() as plugin_dir:
            repo = coverage.CoverageRepository()
            repo.load(plugin_dir)
            repo.set_commander("Alice")
            repo.record("Sol", "Earth", 10.0, 20.0, _EARTH_RADIUS_M)
            repo.record("Sol", "Earth", 10.01, 20.0, _EARTH_RADIUS_M)

            reloaded = coverage.CoverageRepository()
            reloaded.load(plugin_dir)
            reloaded.set_commander("ALICE")   # the journal may write the name in another case
            found = reloaded.for_body("Sol", "Earth")
            self.assertIsNotNone(found)
            self.assertEqual(len(found.points), 2)
            self.assertEqual(found.center, coverage.CoveragePoint(10.0, 20.0))

    def test_clear_body_removes_it(self) -> None:
        with tempfile.TemporaryDirectory() as plugin_dir:
            repo = coverage.CoverageRepository()
            repo.load(plugin_dir)
            repo.record("Sol", "Earth", 10.0, 20.0, _EARTH_RADIUS_M)
            repo.clear_body("Sol", "Earth")
            self.assertIsNone(repo.for_body("Sol", "Earth"))

    def test_missing_file_loads_as_empty(self) -> None:
        with tempfile.TemporaryDirectory() as plugin_dir:
            repo = coverage.CoverageRepository()
            repo.load(plugin_dir)  # no mining_coverage.json exists yet
            self.assertIsNone(repo.for_body("Sol", "Earth"))


if __name__ == "__main__":
    unittest.main()
