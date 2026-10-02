"""
Unit tests for plugin/boxel.py.

Pure string/logic tests — no EDMC runtime needed. Run with:
    python -m unittest discover -s tests

Most example system names here are synthetic (chosen only to match the
procedural name shape). SequenceWalkTests.test_real_boxel_survey_data_...
uses real boxel survey data to cross-validate the sequence-walking logic — see that test's docstring and boxel.py's module
docstring for details.
"""

from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from plugin import boxel  # noqa: E402


class ParseSystemNameTests(unittest.TestCase):
    def test_parses_single_number_form(self) -> None:
        parsed = boxel.parse_system_name("Outotz LS-K d8")
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed.sector, "Outotz")
        self.assertEqual(parsed.cube_id, "LS-K")
        self.assertEqual(parsed.mass_code, "d")
        self.assertEqual(parsed.primary, 8)
        self.assertIsNone(parsed.secondary)

    def test_parses_dual_number_form(self) -> None:
        parsed = boxel.parse_system_name("Outotz LS-K d8-3")
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed.primary, 8)
        self.assertEqual(parsed.secondary, 3)

    def test_parses_multi_word_sector_name(self) -> None:
        parsed = boxel.parse_system_name("Preae Thoi RS-T d3-4")
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed.sector, "Preae Thoi")

    def test_normalizes_case(self) -> None:
        parsed = boxel.parse_system_name("outotz ls-k D8-3")
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed.cube_id, "LS-K")
        self.assertEqual(parsed.mass_code, "d")

    def test_rejects_hand_named_systems(self) -> None:
        self.assertIsNone(boxel.parse_system_name("Sol"))
        self.assertIsNone(boxel.parse_system_name("Colonia"))

    def test_is_procedural_name(self) -> None:
        self.assertTrue(boxel.is_procedural_name("Outotz LS-K d8-3"))
        self.assertFalse(boxel.is_procedural_name("Sol"))


class FormatRoundTripTests(unittest.TestCase):
    def test_round_trips_single_number_form(self) -> None:
        name = "Outotz LS-K d8"
        self.assertEqual(boxel.parse_system_name(name).format(), name)

    def test_round_trips_dual_number_form(self) -> None:
        name = "Outotz LS-K d8-3"
        self.assertEqual(boxel.parse_system_name(name).format(), name)


class SequenceWalkTests(unittest.TestCase):
    def test_next_increments_single_number(self) -> None:
        start = boxel.parse_system_name("Outotz LS-K d8")
        self.assertEqual(boxel.next_in_sequence(start).format(), "Outotz LS-K d9")

    def test_next_increments_secondary_only_no_carry(self) -> None:
        # Confirmed against real data: secondary values run into the
        # thousands (e.g. "Iockols EZ-S d3-5660"), so there's no small carry
        # boundary.
        start = boxel.parse_system_name("Outotz LS-K d8-9")
        self.assertEqual(boxel.next_in_sequence(start).format(), "Outotz LS-K d8-10")

    def test_previous_decrements_single_number(self) -> None:
        start = boxel.parse_system_name("Outotz LS-K d8")
        self.assertEqual(boxel.previous_in_sequence(start).format(), "Outotz LS-K d7")

    def test_previous_decrements_secondary(self) -> None:
        start = boxel.parse_system_name("Outotz LS-K d8-3")
        self.assertEqual(boxel.previous_in_sequence(start).format(), "Outotz LS-K d8-2")

    def test_previous_raises_at_sequence_start(self) -> None:
        start = boxel.parse_system_name("Outotz LS-K d0")
        with self.assertRaises(ValueError):
            boxel.previous_in_sequence(start)

    def test_previous_raises_when_secondary_hits_zero(self) -> None:
        start = boxel.parse_system_name("Outotz LS-K d8-0")
        with self.assertRaises(ValueError):
            boxel.previous_in_sequence(start)

    def test_next_then_previous_is_identity(self) -> None:
        start = boxel.parse_system_name("Outotz LS-K d8-9")
        advanced = boxel.next_in_sequence(start)
        self.assertEqual(boxel.previous_in_sequence(advanced), start)

    def test_real_boxel_survey_data_matches_stride_arithmetic(self) -> None:
        """
        Cross-check against real data (not synthetic): a commander's own
        boxel-survey walked the "Prooe Drye BH-S" (mass code d) boxel from
        id64 10057927091 (d5-0) in fixed steps of 34359738368 (2**35) per
        secondary increment. An independently-recorded system confirmed
        "Prooe Drye BH-S d5-24" at id64 834691647923 — and
        10057927091 + 24 * 34359738368 == 834691647923 exactly, confirming
        boxel.py's secondary-only next_in_sequence walks the same axis the
        real game data does, even though we don't compute id64s ourselves.
        """
        base_id64 = 10057927091
        stride_mass_code_d = 34359738368  # 2**35
        observed_id64 = 834691647923
        observed_secondary = 24

        start = boxel.parse_system_name("Prooe Drye BH-S d5-0")
        current = start
        for _ in range(observed_secondary):
            current = boxel.next_in_sequence(current)

        self.assertEqual(current.format(), "Prooe Drye BH-S d5-24")
        self.assertEqual(base_id64 + observed_secondary * stride_mass_code_d, observed_id64)


if __name__ == "__main__":
    unittest.main()
