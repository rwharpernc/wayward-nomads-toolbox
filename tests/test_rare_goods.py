"""
Unit tests for plugin/rare_goods.py and plugin/powerplay_control_lookup.py.

No EDMC runtime or network needed - the Spansh call is mocked. Run with:
    python -m unittest discover -s tests
"""

from __future__ import annotations

import json
import os
import sys
import threading
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from plugin import powerplay_control_lookup as lookup  # noqa: E402
from plugin import rare_goods  # noqa: E402


class DatasetTests(unittest.TestCase):
    def test_dataset_loads_with_expected_shape(self) -> None:
        self.assertEqual(rare_goods.dataset_size(), 141)
        for entry in rare_goods._load():
            for key in ("rare", "inaraId", "system", "station", "pad", "coords"):
                self.assertIn(key, entry, entry.get("rare"))
            for axis in ("x", "y", "z"):
                self.assertIsInstance(entry["coords"][axis], (int, float))

    def test_inara_ids_are_unique(self) -> None:
        # The window uses the Inara id as the tree row id, so a duplicate
        # would raise on insert.
        ids = [e["inaraId"] for e in rare_goods._load()]
        self.assertEqual(len(ids), len(set(ids)))


class NearestTests(unittest.TestCase):
    def test_sorted_nearest_first_and_limited(self) -> None:
        results = rare_goods.nearest((75.75, 48.75, 70.75), limit=5)  # Lave's own coords
        self.assertEqual(len(results), 5)
        self.assertEqual(results[0]["rare"], "Lavian Brandy")
        self.assertAlmostEqual(results[0]["distance_ly"], 0.0)
        distances = [r["distance_ly"] for r in results]
        self.assertEqual(distances, sorted(distances))

    def test_limit_larger_than_dataset_and_zero(self) -> None:
        self.assertEqual(len(rare_goods.nearest((0, 0, 0), limit=10_000)), rare_goods.dataset_size())
        self.assertEqual(rare_goods.nearest((0, 0, 0), limit=0), [])

    def test_does_not_mutate_cached_dataset(self) -> None:
        rare_goods.nearest((0, 0, 0), limit=3)
        self.assertNotIn("distance_ly", rare_goods._load()[0])

    def test_inara_url(self) -> None:
        self.assertEqual(rare_goods.inara_commodity_url(10006), "https://inara.cz/elite/commodity/10006/")


def _fake_response(payload: dict):
    resp = mock.MagicMock()
    resp.read.return_value = json.dumps(payload).encode("utf-8")
    resp.__enter__.return_value = resp
    return resp


class ControlLookupTests(unittest.TestCase):
    def setUp(self) -> None:
        lookup._cache.clear()

    def test_fetch_one_caches_power_and_unclaimed(self) -> None:
        with mock.patch.object(
            lookup.urllib.request, "urlopen",
            side_effect=[_fake_response({"record": {"controlling_power": "Aisling Duval"}}),
                         _fake_response({"record": {}})],
        ):
            self.assertEqual(lookup._fetch_one(1), "Aisling Duval")
            self.assertIsNone(lookup._fetch_one(2))
        self.assertEqual(lookup.cached(1), (True, "Aisling Duval"))
        self.assertEqual(lookup.cached(2), (True, None))
        self.assertEqual(lookup.cached(3), (False, None))

    def test_failed_lookup_is_cached_as_unresolved_power(self) -> None:
        with mock.patch.object(lookup.urllib.request, "urlopen", side_effect=OSError("down")):
            self.assertIsNone(lookup._fetch_one(9))
        self.assertEqual(lookup.cached(9), (True, None))

    def test_fetch_missing_skips_cached_and_reports_results(self) -> None:
        lookup._cache[1] = "Zachary Hudson"
        got: dict = {}
        done = threading.Event()

        def on_result(id64: int, power) -> None:
            got[id64] = power
            done.set()

        with mock.patch.object(
            lookup.urllib.request, "urlopen",
            return_value=_fake_response({"record": {"controlling_power": "Nakato Kaine"}}),
        ) as urlopen:
            lookup.fetch_missing([1, 2], on_result)
            self.assertTrue(done.wait(5))
        self.assertEqual(got, {2: "Nakato Kaine"})
        self.assertEqual(urlopen.call_count, 1)

    def test_fetch_missing_spawns_nothing_when_all_cached(self) -> None:
        lookup._cache[1] = None
        with mock.patch.object(lookup.threading, "Thread") as thread:
            lookup.fetch_missing([1], lambda *_: None)
        thread.assert_not_called()


if __name__ == "__main__":
    unittest.main()
