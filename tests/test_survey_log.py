"""
Unit tests for plugin/survey_log.py.

Pure logic tests — no EDMC runtime needed. Run with:
    python -m unittest discover -s tests
"""

from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from plugin import survey_log  # noqa: E402


class ClassificationTests(unittest.TestCase):
    def test_earthlike_body_tagged_elw(self) -> None:
        log = survey_log.SurveyLog()
        log.record_scan(
            "Outotz LS-K d8",
            "Outotz LS-K d8 1",
            boxel_key="Outotz|LS-K",
            planet_class="Earthlike body",
            terraform_state=None,
            distance_ls=123.4,
        )
        stats = log.boxel_stats("Outotz|LS-K")
        self.assertEqual(stats["elw"], 1)
        self.assertEqual(stats["systems"], 1)
        self.assertEqual(stats["bodies_scanned"], 1)

    def test_water_and_ammonia_worlds_tagged(self) -> None:
        log = survey_log.SurveyLog()
        log.record_scan(
            "Sys", "Sys 1", boxel_key="k", planet_class="Water world",
            terraform_state=None, distance_ls=None,
        )
        log.record_scan(
            "Sys", "Sys 2", boxel_key="k", planet_class="Ammonia world",
            terraform_state=None, distance_ls=None,
        )
        stats = log.boxel_stats("k")
        self.assertEqual(stats["ww"], 1)
        self.assertEqual(stats["aw"], 1)

    def test_terraformable_is_independent_of_planet_class(self) -> None:
        log = survey_log.SurveyLog()
        log.record_scan(
            "Sys", "Sys 1", boxel_key="k", planet_class="High metal content body",
            terraform_state="Terraformable", distance_ls=None,
        )
        stats = log.boxel_stats("k")
        self.assertEqual(stats["terraformable"], 1)
        self.assertEqual(stats["elw"], 0)

    def test_ordinary_body_not_notable_but_counted(self) -> None:
        log = survey_log.SurveyLog()
        log.record_scan(
            "Sys", "Sys 1", boxel_key="k", planet_class="Icy body",
            terraform_state=None, distance_ls=None,
        )
        stats = log.boxel_stats("k")
        self.assertEqual(stats["bodies_scanned"], 1)
        self.assertEqual(sum(v for k2, v in stats.items() if k2 not in ("systems", "bodies_scanned")), 0)
        self.assertEqual(log.export_rows(), [])

    def test_star_scan_counts_but_has_no_planet_class(self) -> None:
        log = survey_log.SurveyLog()
        log.record_scan(
            "Sys", "Sys", boxel_key="k", planet_class=None,
            terraform_state=None, distance_ls=None,
        )
        stats = log.boxel_stats("k")
        self.assertEqual(stats["bodies_scanned"], 1)
        self.assertEqual(log.export_rows(), [])

    def test_bio_signals_tagged_and_counted(self) -> None:
        log = survey_log.SurveyLog()
        log.record_signals("Sys", "Sys 1", boxel_key="k", bio_signal_count=3)
        stats = log.boxel_stats("k")
        self.assertEqual(stats["bio"], 1)
        rows = log.export_rows()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["bio_signal_count"], 3)

    def test_zero_bio_signal_count_not_recorded(self) -> None:
        log = survey_log.SurveyLog()
        log.record_signals("Sys", "Sys 1", boxel_key="k", bio_signal_count=0)
        self.assertEqual(log.export_rows(), [])


class MultiTagMergeTests(unittest.TestCase):
    def test_scan_then_signals_merge_onto_same_body(self) -> None:
        log = survey_log.SurveyLog()
        log.record_scan(
            "Sys", "Sys 1", boxel_key="k", planet_class="Water world",
            terraform_state="Terraformable", distance_ls=500.0,
        )
        log.record_signals("Sys", "Sys 1", boxel_key="k", bio_signal_count=5)

        rows = log.export_rows()
        self.assertEqual(len(rows), 1)
        tags = set(rows[0]["tags"].split(","))
        self.assertEqual(tags, {"ww", "terraformable", "bio"})
        self.assertEqual(rows[0]["bio_signal_count"], 5)
        self.assertEqual(rows[0]["distance_ls"], 500.0)

    def test_signals_then_scan_merge_onto_same_body(self) -> None:
        # FSS signals can arrive before a detailed Scan of the same body.
        log = survey_log.SurveyLog()
        log.record_signals("Sys", "Sys 1", boxel_key="k", bio_signal_count=2)
        log.record_scan(
            "Sys", "Sys 1", boxel_key="k", planet_class="Earthlike body",
            terraform_state=None, distance_ls=42.0,
        )
        rows = log.export_rows()
        self.assertEqual(len(rows), 1)
        tags = set(rows[0]["tags"].split(","))
        self.assertEqual(tags, {"bio", "elw"})

    def test_repeat_bio_signal_count_takes_max(self) -> None:
        log = survey_log.SurveyLog()
        log.record_signals("Sys", "Sys 1", boxel_key="k", bio_signal_count=2)
        log.record_signals("Sys", "Sys 1", boxel_key="k", bio_signal_count=5)
        log.record_signals("Sys", "Sys 1", boxel_key="k", bio_signal_count=1)
        rows = log.export_rows()
        self.assertEqual(rows[0]["bio_signal_count"], 5)


class BoxelKeyBackfillTests(unittest.TestCase):
    def test_boxel_key_backfilled_when_learned_later(self) -> None:
        log = survey_log.SurveyLog()
        log.record_scan(
            "Sys", "Sys 1", boxel_key=None, planet_class="Earthlike body",
            terraform_state=None, distance_ls=None,
        )
        # boxel_key unknown the first time, learned on a later event for the same system
        log.record_scan(
            "Sys", "Sys 2", boxel_key="k", planet_class="Water world",
            terraform_state=None, distance_ls=None,
        )
        stats = log.boxel_stats("k")
        self.assertEqual(stats["systems"], 1)
        self.assertEqual(stats["elw"], 1)
        self.assertEqual(stats["ww"], 1)

    def test_boxel_stats_only_counts_matching_boxel(self) -> None:
        log = survey_log.SurveyLog()
        log.record_scan(
            "SysA", "SysA 1", boxel_key="k1", planet_class="Earthlike body",
            terraform_state=None, distance_ls=None,
        )
        log.record_scan(
            "SysB", "SysB 1", boxel_key="k2", planet_class="Water world",
            terraform_state=None, distance_ls=None,
        )
        self.assertEqual(survey_log.boxel_key("Outotz", "LS-K"), "Outotz|LS-K")
        self.assertEqual(log.boxel_stats("k1")["elw"], 1)
        self.assertEqual(log.boxel_stats("k1")["ww"], 0)
        self.assertEqual(log.boxel_stats("k2")["ww"], 1)


class RoundTripTests(unittest.TestCase):
    def test_to_dict_from_dict_round_trip(self) -> None:
        log = survey_log.SurveyLog()
        log.record_scan(
            "Sys", "Sys 1", boxel_key="k", planet_class="Ammonia world",
            terraform_state="Terraformable", distance_ls=999.5,
        )
        log.record_signals("Sys", "Sys 1", boxel_key="k", bio_signal_count=7)
        log.record_scan(
            "Sys", "Sys 2", boxel_key="k", planet_class="Icy body",
            terraform_state=None, distance_ls=None,
        )

        restored = survey_log.SurveyLog.from_dict(log.to_dict())

        self.assertEqual(restored.boxel_stats("k"), log.boxel_stats("k"))
        self.assertEqual(
            sorted(restored.export_rows(), key=lambda r: r["body"]),
            sorted(log.export_rows(), key=lambda r: r["body"]),
        )

    def test_from_dict_tolerates_empty_input(self) -> None:
        restored = survey_log.SurveyLog.from_dict({})
        self.assertEqual(restored.export_rows(), [])


if __name__ == "__main__":
    unittest.main()
