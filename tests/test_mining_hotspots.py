"""
Unit tests for plugin/mining_hotspots.py's same-spot merge and mined-ton
counting, plus mining_deposit.describe()'s depleted-tons text.

Pure logic tests - no EDMC runtime needed (EDMC's `config` module is
stubbed). Run with:
    python -m unittest discover -s tests
"""

from __future__ import annotations

import os
import sys
import types
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.modules.setdefault("config", types.SimpleNamespace(appname="EDMarketConnector"))

from plugin import mining_deposit as deposit  # noqa: E402
from plugin import mining_hotspots as hotspots  # noqa: E402

_RADIUS_M = 1_000_000.0
_M_PER_DEG = _RADIUS_M * 3.141592653589793 / 180.0  # metres per degree of latitude


def _spot(north_m: float = 0.0, **kwargs) -> hotspots.Hotspot:
    fields = dict(system="Sol", body="Mars 1", material="Monazite",
                  latitude=north_m / _M_PER_DEG, longitude=0.0)
    fields.update(kwargs)
    return hotspots.Hotspot(**fields)


class AddOrMergeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.repo = hotspots.HotspotRepository()

    def test_far_apart_adds_a_second_hotspot(self) -> None:
        self.repo.add(_spot(0))
        self.assertFalse(self.repo.add_or_merge(_spot(500), _RADIUS_M))
        self.assertEqual(len(self.repo.all()), 2)

    def test_nearby_updates_existing_whatever_the_material(self) -> None:
        self.repo.add(_spot(0, notes="loc 8", mined_tons=40))
        merged = self.repo.add_or_merge(
            _spot(30, material="Alexandrite", rigs=4, amount="High", density="Low"), _RADIUS_M)
        self.assertTrue(merged)
        (only,) = self.repo.all()
        self.assertEqual(only.material, "Alexandrite")
        self.assertEqual(only.rigs, 4)
        self.assertEqual(only.notes, "loc 8")         # kept: new one had none
        self.assertEqual(only.mined_tons, 40)         # never overwritten by a save
        self.assertEqual(only.latitude, 0.0)          # existing position stays

    def test_other_body_is_never_merged(self) -> None:
        self.repo.add(_spot(0))
        self.assertFalse(self.repo.add_or_merge(_spot(10, body="Mars 2"), _RADIUS_M))
        self.assertEqual(len(self.repo.all()), 2)

    def test_without_radius_or_position_is_a_plain_add(self) -> None:
        self.repo.add(_spot(0))
        self.assertFalse(self.repo.add_or_merge(_spot(10), None))
        self.assertFalse(self.repo.add_or_merge(
            hotspots.Hotspot(system="Sol", body="Mars 1", material="X"), _RADIUS_M))
        self.assertEqual(len(self.repo.all()), 3)


class MinedTonsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.repo = hotspots.HotspotRepository()
        self.repo.add(_spot(0))
        self.repo.add(_spot(150, material="Painite"))

    def test_credits_nearest_within_range(self) -> None:
        near_second = 140 / _M_PER_DEG
        self.assertTrue(self.repo.add_mined_tons("Sol", "Mars 1", near_second, 0.0, _RADIUS_M))
        first, second = self.repo.all()
        self.assertIsNone(first.mined_tons)
        self.assertEqual(second.mined_tons, 1)

    def test_nothing_in_range_credits_nobody(self) -> None:
        self.assertFalse(self.repo.add_mined_tons("Sol", "Mars 1", 1000 / _M_PER_DEG, 0.0, _RADIUS_M))
        self.assertTrue(all(h.mined_tons is None for h in self.repo.all()))

    def test_other_body_credits_nobody(self) -> None:
        self.assertFalse(self.repo.add_mined_tons("Sol", "Mars 2", 0.0, 0.0, _RADIUS_M))

    def test_counts_accumulate_and_flush_notifies_once(self) -> None:
        notified = []
        self.repo.add_listener(lambda: notified.append(1))
        for _ in range(3):
            self.repo.add_mined_tons("Sol", "Mars 1", 0.0, 0.0, _RADIUS_M)
        self.repo.flush()
        self.assertEqual(self.repo.all()[0].mined_tons, 3)
        self.assertLessEqual(len(notified), 2)  # first ton may flush on its own; never one per ton
        self.repo.flush()                      # nothing dirty: no further write
        self.assertLessEqual(len(notified), 2)


class DescribeMinedTests(unittest.TestCase):
    def test_depleted_shows_tons_given(self) -> None:
        self.assertEqual(deposit.describe(4, "Depleted", "High", 612), "depleted (612 t)")

    def test_depleted_without_tons_is_plain(self) -> None:
        self.assertEqual(deposit.describe(4, "Depleted", "High", None), "depleted")
        self.assertEqual(deposit.describe(4, "Depleted", "High", 0), "depleted")

    def test_mined_tons_ignored_while_not_depleted(self) -> None:
        self.assertEqual(deposit.describe(4, "High", "High", 50),
                         deposit.describe(4, "High", "High"))


if __name__ == "__main__":
    unittest.main()
