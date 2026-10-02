"""
Unit tests for plugin/mining_body_survey.py.

Pure logic tests - no EDMC runtime needed. Run with:
    python -m unittest discover -s tests
"""

from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from plugin import mining_body_survey as survey  # noqa: E402


class SystemBodySurveyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.survey = survey.SystemBodySurvey()
        self.survey.on_system_changed("Sol")

    def test_landable_body_is_recorded(self) -> None:
        self.survey.record_scan("Sol", "Sol 1", "High metal content body", "", True)
        bodies = self.survey.landable_bodies()
        self.assertEqual(len(bodies), 1)
        self.assertEqual(bodies[0].name, "Sol 1")
        self.assertEqual(bodies[0].planet_class, "High metal content body")

    def test_non_landable_body_is_ignored(self) -> None:
        self.survey.record_scan("Sol", "Sol", "K (Yellow-Orange) Star", "", False)
        self.assertEqual(self.survey.landable_bodies(), [])

    def test_scan_from_a_different_system_is_ignored(self) -> None:
        self.survey.record_scan("Alioth", "Alioth 1", "Rocky body", "", True)
        self.assertEqual(self.survey.landable_bodies(), [])

    def test_system_change_clears_previous_bodies(self) -> None:
        self.survey.record_scan("Sol", "Sol 1", "Rocky body", "", True)
        self.survey.on_system_changed("Alioth")
        self.assertEqual(self.survey.landable_bodies(), [])
        self.assertEqual(self.survey.current_system, "Alioth")

    def test_same_system_reconfirmation_does_not_clear(self) -> None:
        self.survey.record_scan("Sol", "Sol 1", "Rocky body", "", True)
        self.survey.on_system_changed("Sol")
        self.assertEqual(len(self.survey.landable_bodies()), 1)

    def test_signal_before_scan_is_applied_once_scan_arrives(self) -> None:
        self.survey.record_signal("Sol", "Sol 1", 3)
        self.survey.record_scan("Sol", "Sol 1", "Rocky body", "", True)
        self.assertEqual(self.survey.landable_bodies()[0].mining_signal_count, 3)

    def test_signal_after_scan_updates_existing_body(self) -> None:
        self.survey.record_scan("Sol", "Sol 1", "Rocky body", "", True)
        self.survey.record_signal("Sol", "Sol 1", 5)
        self.assertEqual(self.survey.landable_bodies()[0].mining_signal_count, 5)

    def test_bodies_with_signals_sort_before_bodies_without(self) -> None:
        self.survey.record_scan("Sol", "A", "Rocky body", "", True)
        self.survey.record_scan("Sol", "B", "Icy body", "", True)
        self.survey.record_signal("Sol", "B", 2)
        names = [b.name for b in self.survey.landable_bodies()]
        self.assertEqual(names, ["B", "A"])

    def test_higher_signal_count_sorts_first(self) -> None:
        self.survey.record_scan("Sol", "A", "Rocky body", "", True)
        self.survey.record_scan("Sol", "B", "Icy body", "", True)
        self.survey.record_signal("Sol", "A", 1)
        self.survey.record_signal("Sol", "B", 4)
        names = [b.name for b in self.survey.landable_bodies()]
        self.assertEqual(names, ["B", "A"])

    def test_grouped_by_class(self) -> None:
        self.survey.record_scan("Sol", "A", "Rocky body", "", True)
        self.survey.record_scan("Sol", "B", "Icy body", "", True)
        self.survey.record_scan("Sol", "C", "Rocky body", "", True)
        groups = self.survey.grouped_by_class()
        self.assertEqual({b.name for b in groups["Rocky body"]}, {"A", "C"})
        self.assertEqual({b.name for b in groups["Icy body"]}, {"B"})

    def test_missing_planet_class_groups_as_unknown(self) -> None:
        self.survey.record_scan("Sol", "A", None, "", True)
        groups = self.survey.grouped_by_class()
        self.assertIn("Unknown", groups)


if __name__ == "__main__":
    unittest.main()
