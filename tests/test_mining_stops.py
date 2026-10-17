"""
Unit tests for plugin/mining_stops.py and mining_ledger_data.deposit_here().

Pure logic - no EDMC runtime needed (EDMC's `config` module is stubbed). Run with:
    python -m unittest discover -s tests
"""

from __future__ import annotations

import os
import sys
import types
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.modules.setdefault("config", types.SimpleNamespace(appname="EDMarketConnector"))

from plugin import mining_hotspots as hotspots  # noqa: E402
from plugin import mining_ledger_data as data  # noqa: E402
from plugin import mining_stops as stops  # noqa: E402

RADIUS_M = 1_000_000.0
M_PER_DEG = RADIUS_M * 3.141592653589793 / 180.0


def _spot(north_m: float, rigs=4, **kwargs) -> hotspots.Hotspot:
    fields = dict(system="Sol", body="Mars 1", material="Monazite", rigs=rigs,
                  latitude=north_m / M_PER_DEG, longitude=0.0)
    fields.update(kwargs)
    return hotspots.Hotspot(**fields)


class ClampRadiusTests(unittest.TestCase):
    def test_in_range_steps_are_kept(self) -> None:
        self.assertEqual(stops.clamp_radius(1250), 1250)

    def test_out_of_range_is_pulled_in(self) -> None:
        self.assertEqual(stops.clamp_radius(100), 500)
        self.assertEqual(stops.clamp_radius(9000), 2500)

    def test_snaps_to_the_step(self) -> None:
        self.assertEqual(stops.clamp_radius("1300"), 1250)

    def test_unreadable_is_the_default(self) -> None:
        self.assertEqual(stops.clamp_radius("abc"), stops.DEFAULT_RADIUS_M)
        self.assertEqual(stops.clamp_radius(None), stops.DEFAULT_RADIUS_M)


class FindStopsTests(unittest.TestCase):
    def test_nearby_deposits_share_a_stop_led_by_the_most_rigs(self) -> None:
        small, big = _spot(0, rigs=3), _spot(800, rigs=6)
        (stop,) = stops.find_stops([small, big], RADIUS_M, 1250)
        self.assertIs(stop.lead, big)
        self.assertEqual(len(stop.members), 2)

    def test_far_deposits_are_separate_stops_best_first(self) -> None:
        near, far = _spot(0, rigs=4), _spot(5000, rigs=6)
        found = stops.find_stops([near, far], RADIUS_M, 1250)
        self.assertEqual([s.rigs for s in found], [6, 4])

    def test_no_deposit_is_in_two_stops(self) -> None:
        spots = [_spot(0, rigs=5), _spot(1000, rigs=4), _spot(2000, rigs=6)]
        found = stops.find_stops(spots, RADIUS_M, 1250)
        members = [m for s in found for m in s.members]
        self.assertEqual(len(members), len({id(m) for m in members}))

    def test_depleted_unpositioned_and_unrigged_are_left_out(self) -> None:
        spots = [_spot(0, amount="Depleted"), _spot(10, rigs=None),
                 hotspots.Hotspot(system="Sol", body="Mars 1", material="X", rigs=5)]
        self.assertEqual(stops.find_stops(spots, RADIUS_M, 1250), [])

    def test_no_body_radius_means_no_stops(self) -> None:
        self.assertEqual(stops.find_stops([_spot(0)], None, 1250), [])

    def test_radius_is_inclusive_and_bounded(self) -> None:
        spots = [_spot(0, rigs=5), _spot(1500, rigs=4)]
        self.assertEqual(len(stops.find_stops(spots, RADIUS_M, 1250)), 2)
        self.assertEqual(len(stops.find_stops(spots, RADIUS_M, 2000)), 1)


class BestStopsTests(unittest.TestCase):
    def _found(self, *rigs: int):
        return stops.find_stops([_spot(i * 10_000, rigs=r) for i, r in enumerate(rigs)], RADIUS_M, 1250)

    def test_five_rigs_or_more_when_the_body_has_them(self) -> None:
        self.assertEqual([s.rigs for s in stops.best_stops(self._found(6, 5, 4))], [6, 5])

    def test_falls_back_to_four(self) -> None:
        self.assertEqual([s.rigs for s in stops.best_stops(self._found(4, 3, 4))], [4, 4])

    def test_at_most_three(self) -> None:
        self.assertEqual(len(stops.best_stops(self._found(7, 7, 6, 5, 5))), 3)

    def test_none_when_all_small(self) -> None:
        self.assertEqual(stops.best_stops(self._found(3, 2)), [])


class TonsLeftTests(unittest.TestCase):
    def test_adds_the_members_estimates(self) -> None:
        a = _spot(0, rigs=2, amount="High", density="High")
        b = _spot(100, rigs=2, amount="High", density="High")
        (stop,) = stops.find_stops([a, b], RADIUS_M, 1250)
        one = stops.mining_deposit.reserve_range(2, "High", "High")
        self.assertEqual(stop.tons_left(), (one[0] * 2, one[1] * 2))

    def test_none_without_any_estimate(self) -> None:
        (stop,) = stops.find_stops([_spot(0)], RADIUS_M, 1250)
        self.assertIsNone(stop.tons_left())


class DepositHereTests(unittest.TestCase):
    def test_nearest_within_reach(self) -> None:
        a, b = _spot(0), _spot(120)
        self.assertIs(data.deposit_here([a, b], 100 / M_PER_DEG, 0.0, RADIUS_M), b)

    def test_none_when_too_far(self) -> None:
        self.assertIsNone(data.deposit_here([_spot(0)], 400 / M_PER_DEG, 0.0, RADIUS_M))

    def test_depleted_still_counts(self) -> None:
        spot = _spot(0, amount="Depleted")
        self.assertIs(data.deposit_here([spot], 0.0, 0.0, RADIUS_M), spot)

    def test_unpositioned_is_ignored(self) -> None:
        self.assertIsNone(data.deposit_here(
            [hotspots.Hotspot(system="Sol", body="Mars 1", material="X")], 0.0, 0.0, RADIUS_M))


if __name__ == "__main__":
    unittest.main()
