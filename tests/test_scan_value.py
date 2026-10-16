"""The exploration value formula (scan_value.py): the base value, the first-discovery multiplier, the mapping values and the Odyssey and efficiency bonuses,
as in EDDiscovery's table (which OD Explorer's figures agree with)."""
from __future__ import annotations

import math
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from plugin import scan_value as V  # noqa: E402

Q = 0.56591828


def base(k, mass):
    return max(k + k * math.pow(mass, 0.2) * Q, 500)


class Scan(unittest.TestCase):
    def test_the_base_is_k_plus_k_times_q_times_mass_to_the_point_two(self):
        self.assertEqual(V.estimate_planet_scan_value("High metal content body", 2.0, False, True), int(base(9654, 2.0)))
        self.assertEqual(V.estimate_planet_scan_value("Water world", 0.8, True, True), int(base(64831 + 116295, 0.8)))

    def test_an_earthlike_world_is_always_counted_as_terraformable(self):
        self.assertEqual(V.estimate_planet_scan_value("Earthlike body", 1.0, False, True), int(base(64831 + 116295, 1.0)))
        self.assertEqual(V.estimate_planet_scan_value("Earthlike body", 1.0, True, True), V.estimate_planet_scan_value("Earthlike body", 1.0, False, True))

    def test_a_small_rocky_body_is_worth_at_least_500(self):
        self.assertEqual(V.estimate_planet_scan_value("Rocky body", 0.01, False, True), 500)

    def test_a_first_discovery_pays_2_6_times(self):
        found = V.estimate_planet_scan_value("Icy body", 1.0, True, False)
        known = V.estimate_planet_scan_value("Icy body", 1.0, True, True)
        self.assertAlmostEqual(found / known, 2.6, places=2)
        self.assertEqual(V.estimate_planet_scan_value("Icy body", 1.0, True, None), known)

    def test_a_missing_mass_counts_as_one(self):
        self.assertEqual(V.estimate_planet_scan_value("Icy body", None, False, True), V.estimate_planet_scan_value("Icy body", 1.0, False, True))

    def test_stars_by_type(self):
        self.assertEqual(V.estimate_star_scan_value(1.0, True, "G"), int(1200 + 1.0 * 1200 / 66.25))
        self.assertEqual(V.estimate_star_scan_value(1.0, True, "N"), int(22628 + 22628 / 66.25))
        self.assertEqual(V.estimate_star_scan_value(0.6, False, "DA"), int((14057 + 0.6 * 14057 / 66.25) * 2.6))


class Mapped(unittest.TestCase):
    def value(self, discovered, mapped, efficient=True, odyssey=True):
        return V.estimate_planet_mapped_value("Water world", 1.0, False, discovered, mapped, efficient, odyssey)

    def test_the_three_cases_use_their_own_multipliers(self):
        b = base(64831, 1.0)
        def ody(v):
            return v + max(v * 0.3, 555)
        self.assertEqual(self.value(False, False, False), int(ody(b * 3.699622554) * 2.6))        # first to discover and to map
        self.assertEqual(self.value(True, False, False), int(ody(b * 8.0956)))                   # discovered before, never mapped
        self.assertEqual(self.value(True, True, False), int(ody(b * 3.3333333)))                 # already mapped

    def test_a_good_probe_run_pays_a_quarter_more_and_odyssey_adds_to_the_mapping(self):
        self.assertAlmostEqual(self.value(True, True, True) / self.value(True, True, False), 1.25, places=3)
        self.assertGreater(self.value(True, True, False, True), self.value(True, True, False, False) * 1.29)

    def test_mapping_pays_far_more_than_the_scan_alone(self):
        scan = V.estimate_planet_scan_value("Water world", 1.0, False, False)
        self.assertGreater(self.value(False, False), scan * 3)


if __name__ == "__main__":
    unittest.main()
