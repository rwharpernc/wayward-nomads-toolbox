"""
Unit tests for plugin/mining_deposit.py.

Pure logic tests - no EDMC runtime needed. Run with:
    python -m unittest discover -s tests
"""

from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from plugin import mining_deposit as deposit  # noqa: E402


class TonsLeftTests(unittest.TestCase):
    def test_missing_rigs_returns_none(self) -> None:
        self.assertIsNone(deposit.reserve_range(None, "High"))

    def test_missing_amount_returns_none(self) -> None:
        self.assertIsNone(deposit.reserve_range(4, None))

    def test_unrecognized_amount_returns_none(self) -> None:
        self.assertIsNone(deposit.reserve_range(4, "Huge"))

    def test_zero_or_negative_rigs_returns_none(self) -> None:
        self.assertIsNone(deposit.reserve_range(0, "High"))
        self.assertIsNone(deposit.reserve_range(-1, "High"))

    def test_bool_rigs_rejected(self) -> None:
        # bool is a subclass of int in Python - True/False must not be
        # accepted as a rig count.
        self.assertIsNone(deposit.reserve_range(True, "High"))

    def test_depleted_is_zero(self) -> None:
        self.assertEqual(deposit.reserve_range(4, "Depleted"), (0, 0))

    def test_low_density_low_amount_is_zero_low_end(self) -> None:
        low, high = deposit.reserve_range(4, "Low", "Low")
        self.assertEqual(low, 0)
        self.assertGreater(high, 0)

    def test_lower_density_label_means_more_tons(self) -> None:
        high = deposit.reserve_range(4, "High", "High")
        medium = deposit.reserve_range(4, "High", "Medium")
        low = deposit.reserve_range(4, "High", "Low")
        self.assertLess(high[1], medium[1])
        self.assertLess(medium[1], low[1])

    def test_known_ranges(self) -> None:
        self.assertEqual(deposit.reserve_range(4, "High", "High"), (280, 700))
        self.assertEqual(deposit.reserve_range(2, "High", "Low"), (420, 1050))

    def test_missing_density_spans_high_low_to_low_high(self) -> None:
        self.assertEqual(deposit.reserve_range(4, "High", None),
                         (round(4 * 125 * 0.566 / 10) * 10, 4 * 175 * 3))

    def test_rounded_to_nearest_ten(self) -> None:
        low, high = deposit.reserve_range(3, "Medium", "Low")
        self.assertEqual(low % 10, 0)
        self.assertEqual(high % 10, 0)


class DescribeTests(unittest.TestCase):
    def test_depleted(self) -> None:
        self.assertEqual(deposit.reserve_text(4, "Depleted"), "depleted")

    def test_missing_data_is_blank(self) -> None:
        self.assertEqual(deposit.reserve_text(None, "High"), "")
        self.assertEqual(deposit.reserve_text(4, None), "")

    def test_zero_low_end_reads_as_up_to(self) -> None:
        text = deposit.reserve_text(4, "Low", "Low")
        self.assertTrue(text.startswith("~up to "))
        self.assertTrue(text.endswith(" t left"))

    def test_nonzero_range_reads_as_a_span(self) -> None:
        text = deposit.reserve_text(4, "High", "Medium")
        self.assertRegex(text, r"^~[\d,]+-[\d,]+ t left$")


if __name__ == "__main__":
    unittest.main()
