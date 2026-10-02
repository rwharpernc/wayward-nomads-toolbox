"""
Unit tests for plugin/codex_catalog.py and the Codex Completionist window's
sort helpers.

Run with:
    python -m unittest discover -s tests
"""

from __future__ import annotations

import os
import sys
import tempfile
import time
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from plugin import codex_catalog as cc  # noqa: E402
from plugin.codex_completionist import CodexEntryRecord, CodexTally  # noqa: E402

_RAW = {
    "2100101": {"entryid": 2100101, "name": "$Codex_Ent_Bacterial_01_Name;", "english_name": "Bacterium Aurasus",
                "category": "$Codex_Category_Biology;", "sub_class": "Bacterial", "platform": "odyssey"},
    "2100102": {"entryid": 2100102, "name": "$Codex_Ent_Bacterial_02_Name;", "english_name": "Bacterium Nebulus",
                "category": "$Codex_Category_Biology;", "sub_class": "Bacterial", "platform": "odyssey"},
    "1200102": {"entryid": 1200102, "name": "$Codex_Ent_Green_Water_Giant_Name;", "english_name": "Green Water Giant",
                "category": "$Codex_Category_StellarBodies;", "sub_class": "Planets", "platform": "legacy"},
    "9": {"entryid": 9, "name": "", "english_name": "no name"},
}


class ParseTests(unittest.TestCase):
    def test_parses_and_skips_unusable_rows(self) -> None:
        entries = cc.parse_catalog(_RAW)
        self.assertEqual(len(entries), 3)
        green = next(e for e in entries if e.entry_id == 1200102)
        self.assertEqual((green.category, green.platform, green.sub_class), ("Stellar bodies", "Legacy", "Planets"))

    def test_wrong_shape_raises(self) -> None:
        with self.assertRaises(ValueError):
            cc.parse_catalog([])


class MissingTests(unittest.TestCase):
    def test_matches_on_name_case_insensitively(self) -> None:
        catalog = cc.parse_catalog(_RAW)
        missing = cc.missing_entries(catalog, ["$codex_ent_bacterial_01_name;"])
        self.assertEqual({e.english_name for e in missing}, {"Bacterium Nebulus", "Green Water Giant"})

    def test_matches_on_entry_id_when_name_differs(self) -> None:
        catalog = cc.parse_catalog(_RAW)
        missing = cc.missing_entries(catalog, [], [2100101, 0])
        self.assertNotIn("Bacterium Aurasus", {e.english_name for e in missing})

    def test_tally_records_feed_the_diff(self) -> None:
        tally = CodexTally()
        tally.record({"Name": "$Codex_Ent_Bacterial_02_Name;", "EntryID": 2100102}, "Sol")
        records = tally.records
        missing = cc.missing_entries(cc.parse_catalog(_RAW), (r.name for r in records), (r.entry_id for r in records))
        self.assertEqual(len(missing), 2)
        self.assertEqual(records[0].entry_id, 2100102)


class CacheTests(unittest.TestCase):
    def test_round_trip_and_staleness(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            self.assertIsNone(cc.load_cache(folder))
            self.assertTrue(cc.cache_is_stale(folder))
            entries = cc.parse_catalog(_RAW)
            cc.save_cache(folder, entries)
            self.assertEqual(cc.load_cache(folder), entries)
            self.assertFalse(cc.cache_is_stale(folder))
            self.assertTrue(cc.cache_is_stale(folder, now=time.time() + (cc.MAX_AGE_DAYS + 1) * 86400))


class ReferenceTests(unittest.TestCase):
    def test_reference_url_is_encoded(self) -> None:
        self.assertEqual(cc.reference_url("Bacterium Aurasus"), "https://canonn.science/?s=Bacterium+Aurasus")
        self.assertIn("%26", cc.reference_url("A & B"))


class SortTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        # The window module needs EDMC's `config` and the Tk kit; stand them in.
        from unittest import mock
        import types

        class _Anything(types.ModuleType):
            def __getattr__(self, name):
                if name.startswith("__"):
                    raise AttributeError(name)
                return mock.MagicMock()

        cls._saved = {n: sys.modules.get(n) for n in ("config", "theme", "myNotebook", "ttkHyperlinkLabel")}
        sys.modules["config"] = _Anything("config")
        sys.modules["config"].appname = "EDMarketConnector"
        import importlib
        cls.window = importlib.import_module("plugin.codex_completionist_window")

    @classmethod
    def tearDownClass(cls) -> None:
        sys.modules.pop("plugin.codex_completionist_window", None)
        for name, module in cls._saved.items():
            if module is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = module

    @staticmethod
    def _record(name: str, times: int, system: str = "Sol") -> CodexEntryRecord:
        return CodexEntryRecord(name=name, name_localised=name, category="c", category_localised="c",
                                subcategory="", subcategory_localised="", first_system=system,
                                first_seen="", times_found=times)

    def test_times_found_both_directions_with_alphabetical_ties(self) -> None:
        records = [self._record("b", 2), self._record("a", 2), self._record("c", 9), self._record("d", 1)]
        desc = [r.name for r in self.window.sort_records(records, "found", True)]
        asc = [r.name for r in self.window.sort_records(records, "found", False)]
        self.assertEqual(desc, ["c", "a", "b", "d"])
        self.assertEqual(asc, ["d", "a", "b", "c"])

    def test_entry_name_both_directions_ignores_case(self) -> None:
        records = [self._record("banana", 1), self._record("Apple", 1), self._record("cherry", 1)]
        self.assertEqual([r.name for r in self.window.sort_records(records, "entry", False)],
                         ["Apple", "banana", "cherry"])
        self.assertEqual([r.name for r in self.window.sort_records(records, "entry", True)],
                         ["cherry", "banana", "Apple"])

    def test_missing_sort_by_entry(self) -> None:
        entries = cc.parse_catalog(_RAW)
        names = [e.english_name for e in self.window.sort_missing(entries, "entry", True)]
        self.assertEqual(names, sorted(names, key=str.casefold, reverse=True))


if __name__ == "__main__":
    unittest.main()
