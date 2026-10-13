"""Material traders: the Spansh search's request and parsing (mining_spansh_client.search_material_traders, the network call replaced), the finder's
shaping and cache (material_traders.py), and the holdings-by-grade summary (materials.MaterialBook.grade_summary)."""
from __future__ import annotations

import os
import sys
import tempfile
import types
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
if "config" not in sys.modules:
    _stub = types.ModuleType("config")
    _stub.appname = "EDMarketConnector"
    _stub.config = types.SimpleNamespace(get_str=lambda key: "", default_journal_dir="")
    sys.modules["config"] = _stub

from plugin import material_traders as T  # noqa: E402
from plugin import materials as M  # noqa: E402
from plugin import mining_spansh_client as C  # noqa: E402


def station(name="Broglie Terminal", system="61 Cygni", kind="Ocellus Starport", distance=11.4, trader="Raw", **extra):
    base = {"name": name, "system_name": system, "type": kind, "distance": distance, "distance_to_arrival": 520.0, "is_planetary": False,
            "material_trader": trader, "small_pads": 0, "medium_pads": 4, "large_pads": 6}
    base.update(extra)
    return base


class ClientTests(unittest.TestCase):
    def search(self, results, *args, **kwargs):
        with mock.patch.object(C, "_post_station_search", return_value={"results": results}) as post:
            found = C.search_material_traders(*args, **kwargs)
        return found, post

    def test_the_request_asks_for_the_trader_type_nearest_first(self):
        _, post = self.search([], "Sol", "Encoded", 120, 7, "large")
        body, agent = post.call_args[0]
        self.assertEqual(body["filters"]["material_trader"], {"value": ["Encoded"]})
        self.assertEqual(body["filters"]["distance"], {"min": "0", "max": "120"})
        self.assertEqual(body["filters"]["large_pads"], {"comparison": "<=>", "value": [1, 999]})
        self.assertEqual((body["sort"], body["size"], body["reference_system"]), ([{"distance": {"direction": "asc"}}], 7, "Sol"))
        self.assertIn("material-trader", agent)

    def test_no_distance_and_no_pad_send_no_such_filters(self):
        _, post = self.search([], "Sol", "Raw", None)
        self.assertEqual(set(post.call_args[0][0]["filters"]), {"material_trader"})

    def test_results_are_read(self):
        found, _ = self.search([station(), station("Bresnik Port", "82 Eridani", "Coriolis Starport", 19.7, small_pads=None)], "Sol", "Raw", 50)
        self.assertEqual([(t.station, t.system, t.station_type, round(t.distance_ly, 1), t.trader_type) for t in found],
                         [("Broglie Terminal", "61 Cygni", "Ocellus Starport", 11.4, "Raw"), ("Bresnik Port", "82 Eridani", "Coriolis Starport", 19.7, "Raw")])
        self.assertEqual((found[0].small_pads, found[0].medium_pads, found[0].large_pads), (0, 4, 6))
        self.assertIsNone(found[1].small_pads)

    def test_a_result_that_does_not_carry_the_trader_or_is_damaged_is_not_shown(self):
        found, _ = self.search([station(trader="Encoded"), station(trader=None), "junk", None, station("Good")], "Sol", "Raw", 50)
        self.assertEqual([t.station for t in found], ["Good"])

    def test_missing_fields_get_safe_values(self):
        found, _ = self.search([{"material_trader": "Raw"}], "Sol", "Raw", 50)
        self.assertEqual((found[0].station, found[0].system, found[0].distance_ly, found[0].is_planetary), ("?", "?", 0.0, False))

    def test_unknown_values_are_refused_before_anything_is_sent(self):
        with mock.patch.object(C, "_post_station_search") as post:
            for args in (("Sol", "Gold", 50), ("Sol", "raw", 50)):
                with self.assertRaises(ValueError):
                    C.search_material_traders(*args)
            with self.assertRaises(ValueError):
                C.search_material_traders("Sol", "Raw", 50, 10, "small")
        post.assert_not_called()


class FinderTests(unittest.TestCase):
    def setUp(self):
        T.clear_cache()
        self.calls = []
        self.clock = [1000.0]

    def search(self, reference, trader_type, radius, results, pad):
        self.calls.append((reference, trader_type, radius, results, pad))
        return [C.MaterialTrader("Far", "B", "Outpost", 30.0, 100.0, False, trader_type, 2, 0, 0),
                C.MaterialTrader("Near", "A", "Planetary Port", 5.0, 2500.4, True, trader_type, 0, 1, 3)]

    def find(self, *args, **kwargs):
        return T.find(*args, search=self.search, now=lambda: self.clock[0], **kwargs)

    def test_traders_are_shaped_and_ordered_nearest_first(self):
        result = self.find("  Sol ", "Raw", 100)
        self.assertEqual([t.station for t in result.traders], ["Near", "Far"])
        near, far = result.traders
        self.assertEqual((near.pad, far.pad), ("Large", "Small"))
        self.assertEqual(T.describe_place(near), "ground Planetary Port, 2,500 ls")
        self.assertEqual(T.describe_place(far), "orbital Outpost, 100 ls")
        self.assertEqual(self.calls[0], ("Sol", "Raw", 100, T.RESULTS, None))

    def test_the_pad_choice_is_passed_on(self):
        self.find("Sol", "Raw", 100, T.PAD_LARGE)
        self.assertEqual(self.calls[0][4], "large")

    def test_the_same_search_is_answered_from_memory_for_two_minutes(self):
        first = self.find("Sol", "Raw", 100)
        self.clock[0] += T.CACHE_SECONDS - 1
        self.assertIs(self.find("sol", "Raw", 100), first)
        self.assertTrue(T.is_cached("SOL", "Raw", 100, now=lambda: self.clock[0]))
        self.assertEqual(len(self.calls), 1)
        self.clock[0] += 2
        self.find("Sol", "Raw", 100)
        self.assertEqual(len(self.calls), 2)

    def test_a_different_type_radius_or_pad_is_a_different_search(self):
        for args in (("Sol", "Raw", 100), ("Sol", "Encoded", 100), ("Sol", "Raw", 250), ("Sol", "Raw", 100, T.PAD_MEDIUM), ("Sol", "Raw", None)):
            self.find(*args)
        self.assertEqual(len(self.calls), 5)

    def test_a_failure_is_not_remembered(self):
        def failing(*args):
            raise OSError("no network")
        with self.assertRaises(OSError):
            T.find("Sol", "Raw", 100, search=failing)
        self.find("Sol", "Raw", 100)
        self.assertEqual(len(self.calls), 1)

    def test_bad_input_is_refused(self):
        for args in (("", "Raw"), ("   ", "Raw"), ("Sol", "Gold"), ("Sol", "Raw", 100, "tiny")):
            with self.assertRaises(ValueError, msg=args):
                self.find(*args)
        self.assertEqual(self.calls, [])


class GradeSummaryTests(unittest.TestCase):
    def test_what_is_held_by_grade(self):
        grade4 = next(m for m in M.CATALOG.values() if m.type == "Raw" and m.grade == 4)
        self.assertEqual((M.CATALOG["iron"].grade, M.CATALOG["carbon"].grade, M.CATALOG["tin"].grade, M.CATALOG["tungsten"].grade), (1, 1, 3, 3))
        with tempfile.TemporaryDirectory() as folder:
            book = M.MaterialBook()
            book.load(folder)
            book.set_commander("Bocheaux")
            book.apply_event({"event": "Materials", "Raw": [
                {"Name": "iron", "Count": 300}, {"Name": "carbon", "Count": 100}, {"Name": "tin", "Count": 12}, {"Name": "tungsten", "Count": 3},
                {"Name": grade4.key, "Count": 7}],
                "Manufactured": [{"Name": "gridresistors", "Count": 40}], "Encoded": []})
            raw = book.grade_summary("Raw")
            self.assertEqual([(g.grade, g.pieces, g.materials, g.at_limit) for g in raw], [(1, 400, 2, 1), (3, 15, 2, 0), (4, 7, 1, 0)])
            self.assertEqual([g.grade for g in book.grade_summary("Manufactured")], [1])
            self.assertEqual(book.grade_summary("Encoded"), [])

    def test_a_material_with_no_known_grade_is_left_out(self):
        with tempfile.TemporaryDirectory() as folder:
            book = M.MaterialBook()
            book.load(folder)
            book.set_commander("Bocheaux")
            book.apply_event({"event": "MaterialCollected", "Category": "Raw", "Name": "newthing", "Count": 4})
            self.assertEqual(book.grade_summary("Raw"), [])


if __name__ == "__main__":
    unittest.main()
