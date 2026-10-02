"""
Unit tests for plugin/mining_ground.py (ground classification and the
commander's own recorded rates).

Pure logic - no EDMC runtime or display needed (EDMC's `config` module is
stubbed). Run with: python -m unittest discover -s tests
"""

from __future__ import annotations

import os
import sys
import types
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.modules.setdefault("config", types.SimpleNamespace(appname="EDMarketConnector"))

from plugin import mining_body_survey as survey  # noqa: E402
from plugin import mining_ground as ground  # noqa: E402
from plugin import mining_hotspots as hotspots  # noqa: E402


def _spot(material: str, body: str = "1", system: str = "Sys", **kwargs) -> hotspots.Hotspot:
    return hotspots.Hotspot(system=system, body=body, material=material, **kwargs)


class ClassifyTests(unittest.TestCase):
    def test_non_rocky_classes(self) -> None:
        self.assertEqual(ground.classify("Metal rich body", ""), "metal_rich")
        self.assertEqual(ground.classify("High metal content body", None), "high_metal")
        self.assertEqual(ground.classify("Rocky ice body", "volcanism ignored"), "rocky_ice")
        self.assertEqual(ground.classify("Icy body", ""), "icy")

    def test_rocky_splits_on_volcanism(self) -> None:
        cases = {
            "": "rocky",
            "Minor Metallic Magma Volcanism": "rocky_metallic_magma",
            "Major Rocky Magma Volcanism": "rocky_rocky_magma",
            "Minor Silicate Vapour Geysers Volcanism": "rocky_silicate_vapour",
            "Major Silicate Magma Volcanism": "rocky_silicate_magma",
            "Minor Carbon Dioxide Geysers Volcanism": "rocky_other_volcanism",
        }
        for volcanism, expected in cases.items():
            self.assertEqual(ground.classify("Rocky body", volcanism), expected, volcanism)

    def test_tolerates_case_and_whitespace(self) -> None:
        self.assertEqual(ground.classify("  METAL RICH BODY ", ""), "metal_rich")
        self.assertEqual(ground.classify("Rocky body", "  Metallic   Magma "), "rocky_metallic_magma")

    def test_no_class_is_none(self) -> None:
        self.assertIsNone(ground.classify(None, "x"))
        self.assertIsNone(ground.classify("", ""))

    def test_every_ground_has_a_label(self) -> None:
        for key in ground.GROUND_LABELS:
            self.assertNotEqual(ground.label(key), key)
        self.assertEqual(ground.label(None), "Unknown ground")


class OwnRatesTests(unittest.TestCase):
    def test_empty_without_records(self) -> None:
        rates = ground.OwnRates([])
        self.assertFalse(rates.has_data)
        self.assertEqual(rates.rates("icy"), [])
        self.assertEqual(rates.rates(None), [])
        self.assertEqual(rates.sample_size("icy"), 0)
        self.assertIsNone(rates.rate_of("icy", "Painite"))

    def test_shares_and_ordering(self) -> None:
        saved = [_spot("Painite", ground="icy"), _spot("painite", ground="icy"), _spot("Painite", ground="icy"),
                 _spot("Bromellite", ground="icy"), _spot("Monazite", ground="rocky_ice")]
        rates = ground.OwnRates(saved)
        self.assertEqual(rates.sample_size("icy"), 4)
        self.assertEqual([(r.material, r.count, r.pct) for r in rates.rates("icy")],
                         [("Painite", 3, 75.0), ("Bromellite", 1, 25.0)])
        self.assertEqual(rates.rate_of("icy", " PAINITE ").count, 3)
        self.assertIsNone(rates.rate_of("icy", "Monazite"))  # recorded on another ground only

    def test_unclassified_and_blank_material_are_skipped(self) -> None:
        rates = ground.OwnRates([_spot("Painite"), _spot("  ", ground="icy")])
        self.assertFalse(rates.has_data)

    def test_extra_grounds_cover_hotspots_saved_without_one(self) -> None:
        saved = [_spot("Painite", body="7 a", system="Sys"), _spot("Monazite", body="7 a", system="Other")]
        rates = ground.OwnRates(saved, {("sys", "7 a"): "icy"})
        self.assertEqual([r.material for r in rates.rates("icy")], ["Painite"])

    def test_a_stamped_ground_wins_over_the_survey(self) -> None:
        saved = [_spot("Painite", body="7 a", ground="rocky_ice")]
        rates = ground.OwnRates(saved, {("sys", "7 a"): "icy"})
        self.assertEqual(rates.sample_size("rocky_ice"), 1)
        self.assertEqual(rates.sample_size("icy"), 0)


class SurveyLookupTests(unittest.TestCase):
    def _survey(self) -> survey.SystemBodySurvey:
        s = survey.SystemBodySurvey()
        s.on_system_changed("Sys")
        s.record_scan("Sys", "Sys 7 a", "Icy body", "", True)
        s.record_scan("Sys", "Sys 8", "Gas giant", "", False)
        return s

    def test_ground_in_survey_for_a_scanned_landable_body(self) -> None:
        self.assertEqual(ground.ground_in_survey(self._survey(), "Sys", "sys 7 A"), "icy")

    def test_unknown_when_other_system_or_unscanned_or_not_landable(self) -> None:
        s = self._survey()
        self.assertIsNone(ground.ground_in_survey(s, "Elsewhere", "Sys 7 a"))
        self.assertIsNone(ground.ground_in_survey(s, "Sys", "Sys 9"))
        self.assertIsNone(ground.ground_in_survey(s, "Sys", "Sys 8"))
        self.assertIsNone(ground.ground_in_survey(s, "Sys", None))

    def test_survey_grounds_keys_are_casefolded(self) -> None:
        s = self._survey()
        self.assertEqual(ground.survey_grounds(s.landable_bodies(), "Sys"), {("sys", "sys 7 a"): "icy"})


if __name__ == "__main__":
    unittest.main()
