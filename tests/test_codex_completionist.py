"""
Unit tests for plugin/codex_completionist.py.

Pure logic tests — no EDMC runtime needed. Run with:
    python -m unittest discover -s tests
"""

from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from plugin.codex_completionist import CodexTally  # noqa: E402

_BACTERIUM_ENTRY = {
    "timestamp": "2026-01-01T00:00:00Z",
    "event": "CodexEntry",
    "EntryID": 2101202,
    "Name": "$Codex_Ent_Bacterial_01_Name;",
    "Name_Localised": "Bacterium Aurasus",
    "SubCategory": "$Codex_SubCategory_Organic_Structures;",
    "SubCategory_Localised": "Organic structures",
    "Category": "$Codex_Category_Biology;",
    "Category_Localised": "Biological and Geological",
    "Region": "$Codex_RegionName_22;",
    "Region_Localised": "Inner Orion Spur",
    "System": "Outotz LS-K d8",
    "SystemAddress": 12345,
    "IsNewEntry": True,
}


class RecordTests(unittest.TestCase):
    def test_first_sighting_creates_a_record(self) -> None:
        tally = CodexTally()
        record = tally.record(_BACTERIUM_ENTRY, "Outotz LS-K d8")
        self.assertIsNotNone(record)
        self.assertEqual(record.name, "$Codex_Ent_Bacterial_01_Name;")
        self.assertEqual(record.name_localised, "Bacterium Aurasus")
        self.assertEqual(record.category_localised, "Biological and Geological")
        self.assertEqual(record.first_system, "Outotz LS-K d8")
        self.assertEqual(record.times_found, 1)
        self.assertTrue(record.was_first_discovery)
        self.assertEqual(tally.total_distinct, 1)
        self.assertEqual(tally.total_finds, 1)

    def test_repeat_sighting_increments_times_found_not_a_new_record(self) -> None:
        tally = CodexTally()
        tally.record(_BACTERIUM_ENTRY, "Outotz LS-K d8")
        repeat = dict(_BACTERIUM_ENTRY, IsNewEntry=False, System="Sol")
        tally.record(repeat, "Sol")

        self.assertEqual(tally.total_distinct, 1)  # still one distinct entry
        self.assertEqual(tally.total_finds, 2)
        record = tally.records[0]
        self.assertEqual(record.times_found, 2)
        self.assertEqual(record.first_system, "Outotz LS-K d8")  # unchanged by the repeat
        self.assertTrue(record.was_first_discovery)  # stays True once ever set

    def test_missing_name_is_ignored(self) -> None:
        tally = CodexTally()
        result = tally.record({"event": "CodexEntry"}, "Sol")
        self.assertIsNone(result)
        self.assertEqual(tally.total_distinct, 0)

    def test_second_entry_never_marked_first_discovery_by_a_later_repeat(self) -> None:
        tally = CodexTally()
        not_first = dict(_BACTERIUM_ENTRY, IsNewEntry=False)
        record = tally.record(not_first, "Sol")
        self.assertFalse(record.was_first_discovery)
        # A later repeat that WAS a first discovery (unusual, but shouldn't crash) sets it True.
        tally.record(dict(_BACTERIUM_ENTRY, IsNewEntry=True), "Sol")
        self.assertTrue(tally.records[0].was_first_discovery)


class GroupingTests(unittest.TestCase):
    def test_by_category_groups_and_sorts(self) -> None:
        tally = CodexTally()
        tally.record(_BACTERIUM_ENTRY, "Sol")
        other = dict(
            _BACTERIUM_ENTRY, Name="$Codex_Ent_Bacterial_02_Name;", Name_Localised="Bacterium Nebulus",
        )
        tally.record(other, "Sol")

        grouped = tally.by_category()
        self.assertIn("Biological and Geological", grouped)
        names = [r.name_localised for r in grouped["Biological and Geological"]]
        self.assertEqual(names, ["Bacterium Aurasus", "Bacterium Nebulus"])  # alphabetical

    def test_category_counts(self) -> None:
        tally = CodexTally()
        tally.record(_BACTERIUM_ENTRY, "Sol")
        counts = tally.category_counts()
        self.assertEqual(counts["Biological and Geological"], 1)


class FirstSystemsMatchingTests(unittest.TestCase):
    def test_matches_on_localised_category(self) -> None:
        tally = CodexTally()
        guardian_entry = dict(
            _BACTERIUM_ENTRY, Name="$Codex_Ent_Guardian_Relic;", Name_Localised="Guardian Relic",
            Category="$Codex_Category_Guardian;", Category_Localised="Guardian",
        )
        tally.record(guardian_entry, "HIP 12345")
        self.assertEqual(tally.first_systems_matching("guardian"), {"HIP 12345"})
        self.assertEqual(tally.first_systems_matching("thargoid"), set())

    def test_matches_on_raw_category_case_insensitive(self) -> None:
        tally = CodexTally()
        entry = dict(_BACTERIUM_ENTRY, Category="$Codex_Category_Xeno;", Category_Localised="Thargoid")
        tally.record(entry, "Sol")
        self.assertEqual(tally.first_systems_matching("XENO"), {"Sol"})

    def test_multiple_keywords_are_or_matched(self) -> None:
        tally = CodexTally()
        tally.record(dict(_BACTERIUM_ENTRY, Category_Localised="Thargoid"), "Sol")
        self.assertEqual(tally.first_systems_matching("guardian", "thargoid"), {"Sol"})

    def test_unknown_first_system_is_excluded(self) -> None:
        tally = CodexTally()
        entry = dict(_BACTERIUM_ENTRY, Category_Localised="Guardian")
        tally.record(entry, None)  # falls back to entry's own "System", "Outotz LS-K d8"
        # sanity: this one DOES have a real first_system, so it should show up
        self.assertEqual(tally.first_systems_matching("guardian"), {"Outotz LS-K d8"})

    def test_no_matching_records_returns_empty_set(self) -> None:
        tally = CodexTally()
        tally.record(_BACTERIUM_ENTRY, "Sol")
        self.assertEqual(tally.first_systems_matching("guardian"), set())


class PersistenceTests(unittest.TestCase):
    def test_snapshot_restore_round_trip(self) -> None:
        tally = CodexTally()
        tally.record(_BACTERIUM_ENTRY, "Outotz LS-K d8")
        tally.record(dict(_BACTERIUM_ENTRY, IsNewEntry=False), "Sol")  # second find

        snap = tally.snapshot()
        restored = CodexTally()
        restored.restore(snap)

        self.assertEqual(restored.total_distinct, 1)
        self.assertEqual(restored.total_finds, 2)
        record = restored.records[0]
        self.assertEqual(record.name_localised, "Bacterium Aurasus")
        self.assertTrue(record.was_first_discovery)

    def test_restore_skips_malformed_entries(self) -> None:
        tally = CodexTally()
        tally.restore([{"name": "$Codex_Ent_Bacterial_01_Name;", "name_localised": "Bacterium Aurasus"},
                        {"no_name_field": True}])
        self.assertEqual(tally.total_distinct, 1)


class MergeHistoryTests(unittest.TestCase):
    @staticmethod
    def _event(stamp: str, system: str = "Outotz LS-K d8", new: bool = False) -> dict:
        return {**_BACTERIUM_ENTRY, "timestamp": stamp, "System": system, "IsNewEntry": new}

    def test_backfill_into_an_empty_tally_counts_each_event_once(self) -> None:
        tally = CodexTally()
        tally.merge_history([self._event("2026-01-01T00:00:00Z", new=True), self._event("2026-01-02T00:00:00Z")])
        self.assertEqual(tally.total_distinct, 1)
        self.assertEqual(tally.total_finds, 2)
        self.assertTrue(tally.records[0].was_first_discovery)

    def test_backfill_twice_changes_nothing(self) -> None:
        events = [self._event("2026-01-01T00:00:00Z"), self._event("2026-01-02T00:00:00Z")]
        tally = CodexTally()
        tally.merge_history(events)
        tally.merge_history(events)
        self.assertEqual(tally.total_finds, 2)

    def test_events_already_counted_live_are_not_added_again(self) -> None:
        events = [self._event("2026-01-01T00:00:00Z"), self._event("2026-01-02T00:00:00Z")]
        tally = CodexTally()
        for event in events:
            tally.record(event, event["System"])
        tally.merge_history(events)
        self.assertEqual(tally.total_finds, 2)

    def test_finds_from_deleted_journals_are_kept(self) -> None:
        tally = CodexTally()
        for stamp in ("2026-01-01T00:00:00Z", "2026-01-02T00:00:00Z", "2026-01-03T00:00:00Z"):
            tally.record(self._event(stamp), "Outotz LS-K d8")
        tally.merge_history([self._event("2026-01-03T00:00:00Z")])
        self.assertEqual(tally.total_finds, 3)

    def test_live_events_missing_from_history_are_still_counted_by_history_max(self) -> None:
        tally = CodexTally()
        tally.record(self._event("2026-01-03T00:00:00Z"), "Outotz LS-K d8")
        tally.merge_history([self._event("2026-01-01T00:00:00Z"), self._event("2026-01-02T00:00:00Z"),
                             self._event("2026-01-03T00:00:00Z")])
        self.assertEqual(tally.total_finds, 3)

    def test_earlier_first_sighting_and_first_discovery_flag_come_from_history(self) -> None:
        tally = CodexTally()
        tally.record(self._event("2026-02-01T00:00:00Z", system="Later System"), "Later System")
        tally.merge_history([self._event("2026-01-01T00:00:00Z", system="Earlier System", new=True),
                             self._event("2026-02-01T00:00:00Z", system="Later System")])
        record = tally.records[0]
        self.assertEqual(record.first_system, "Earlier System")
        self.assertEqual(record.first_seen, "2026-01-01T00:00:00Z")
        self.assertTrue(record.was_first_discovery)

    def test_events_without_a_name_are_ignored(self) -> None:
        tally = CodexTally()
        tally.merge_history([{"event": "CodexEntry"}])
        self.assertEqual(tally.total_distinct, 0)


class CatchUpTests(unittest.TestCase):
    """Finds made while EDMC was closed are counted once, using the watermark."""

    @staticmethod
    def find(stamp: str, name: str = "$Codex_Ent_Bacterial_01_Name;") -> dict:
        return {**_BACTERIUM_ENTRY, "timestamp": stamp, "Name": name, "IsNewEntry": False}

    def test_only_events_after_the_watermark_are_counted_and_it_moves_up(self) -> None:
        tally = CodexTally()
        tally.advance_watermark("2026-01-02T00:00:00Z")
        counted = tally.apply_new([self.find("2026-01-01T00:00:00Z"), self.find("2026-01-03T00:00:00Z"),
                                   self.find("2026-01-04T00:00:00Z")])
        self.assertEqual(counted, 2)
        self.assertEqual(tally.total_finds, 2)
        self.assertEqual(tally.last_event_at, "2026-01-04T00:00:00Z")

    def test_running_it_again_never_counts_anything_twice(self) -> None:
        tally = CodexTally()
        tally.advance_watermark("2026-01-02T00:00:00Z")
        events = [self.find("2026-01-03T00:00:00Z"), self.find("2026-01-04T00:00:00Z", "$Codex_Ent_Other;")]
        tally.apply_new(events)
        self.assertEqual(tally.apply_new(events), 0)
        self.assertEqual(tally.total_finds, 2)

    def test_the_watermark_never_goes_backwards(self) -> None:
        tally = CodexTally()
        tally.advance_watermark("2026-01-04T00:00:00Z")
        tally.advance_watermark("2026-01-01T00:00:00Z")
        tally.advance_watermark(None)
        self.assertEqual(tally.last_event_at, "2026-01-04T00:00:00Z")

    def test_scan_since_reads_only_newer_events_from_recent_files(self) -> None:
        import json
        import tempfile
        import time
        import types
        from unittest import mock
        stub = types.ModuleType("config")
        stub.appname = "EDMarketConnector"
        stub.config = types.SimpleNamespace(get_str=lambda key: "", default_journal_dir="")
        with mock.patch.dict(sys.modules, {"config": stub}):
            import importlib
            sys.modules.pop("plugin.codex_backfill", None)
            backfill = importlib.import_module("plugin.codex_backfill")
            with tempfile.TemporaryDirectory() as folder:
                path = os.path.join(folder, "Journal.1.log")
                with open(path, "w", encoding="utf-8") as handle:
                    for event in (self.find("2026-01-01T00:00:00Z"), self.find("2026-01-05T00:00:00Z"),
                                  {"event": "Scan", "timestamp": "2026-01-06T00:00:00Z"}):
                        handle.write(json.dumps(event) + chr(10))
                found = backfill.scan_since("2026-01-02T00:00:00Z", folder)
            sys.modules.pop("plugin.codex_backfill", None)
        self.assertEqual([e["timestamp"] for e in found], ["2026-01-05T00:00:00Z"])


if __name__ == "__main__":
    unittest.main()
