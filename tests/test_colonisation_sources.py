"""Where-to-buy search for colonisation commodities (colonisation_sources.py), with Spansh replaced by a stand-in."""
from __future__ import annotations

import os
import sys
import types
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
if "config" not in sys.modules:
    _stub = types.ModuleType("config")
    _stub.appname = "EDMarketConnector"
    _stub.config = types.SimpleNamespace(get_str=lambda key: "", default_journal_dir="")
    sys.modules["config"] = _stub

from plugin import colonisation_sources as src  # noqa: E402
from plugin.mining_spansh_client import StationPrice  # noqa: E402


def item(name, ly, price=400, kind="Coriolis Starport", pads=(4, 4, 4), ls=500.0, qty=1000, planetary=False):
    small, medium, large = pads
    return StationPrice(station=name, system="Sys " + name, station_type=kind, distance_ly=ly,
                        distance_to_arrival_ls=ls, is_planetary=planetary, price=price, quantity=qty,
                        small_pads=small, medium_pads=medium, large_pads=large)


class FakeSpansh:
    """Records each call and answers from a table keyed by whether it asked for carriers."""

    def __init__(self, stations, carriers=()):
        self.stations, self.carriers, self.calls = list(stations), list(carriers), []

    def __call__(self, system, commodity, transaction, radius, **kwargs):
        self.calls.append((system, commodity, transaction, radius, kwargs))
        return list(self.carriers if kwargs.get("station_types") == ["Drake-Class Carrier"] else self.stations)


class CacheTests(unittest.TestCase):
    def setUp(self):
        src.clear_cache()

    def test_the_same_search_is_answered_from_memory_for_a_short_while(self):
        fake, clock = FakeSpansh([item("Port", 4)]), [0.0]
        first = src.find("Sol", "Steel", search=fake, now=lambda: clock[0])
        clock[0] = src.CACHE_SECONDS - 1
        again = src.find(" sol ", "STEEL", search=fake, now=lambda: clock[0])
        self.assertEqual(len(fake.calls), 1)
        self.assertIs(first, again)
        clock[0] = src.CACHE_SECONDS + 1
        src.find("Sol", "Steel", search=fake, now=lambda: clock[0])
        self.assertEqual(len(fake.calls), 2)

    def test_changed_options_search_again(self):
        fake = FakeSpansh([item("Port", 4)])
        src.find("Sol", "Steel", search=fake)
        src.find("Sol", "Steel", pad=src.PAD_LARGE, search=fake)
        src.find("Sol", "Steel", include_carriers=True, search=fake)
        self.assertEqual(len(fake.calls), 4)   # the carrier search is two requests

    def test_a_failure_is_not_remembered(self):
        def failing(*args, **kwargs):
            raise OSError("down")
        with self.assertRaises(OSError):
            src.find("Sol", "Steel", search=failing)
        fake = FakeSpansh([item("Port", 4)])
        self.assertEqual(len(src.find("Sol", "Steel", search=fake).stations), 1)


class PadTests(unittest.TestCase):
    def setUp(self):
        src.clear_cache()

    def test_largest_pad(self):
        self.assertEqual(src.largest_pad(item("a", 1, pads=(4, 2, 1))), "Large")
        self.assertEqual(src.largest_pad(item("a", 1, pads=(4, 2, 0))), "Medium")
        self.assertEqual(src.largest_pad(item("a", 1, pads=(4, 0, 0))), "Small")
        self.assertEqual(src.largest_pad(item("a", 1, pads=(0, 0, 0))), "?")

    def test_any_size_is_the_default_and_asks_spansh_for_no_pad_filter(self):
        fake = FakeSpansh([item("Outpost", 5, pads=(4, 1, 0), kind="Outpost")])
        result = src.find("Sol", "Steel", search=fake)
        self.assertEqual([s.station for s in result.stations], ["Outpost"])
        self.assertIsNone(fake.calls[0][4]["required_pad"])

    def test_medium_and_large_are_passed_to_spansh_and_checked_again(self):
        stations = [item("Big", 9, pads=(4, 4, 4)), item("Mid", 3, pads=(4, 2, 0)), item("Tiny", 1, pads=(4, 0, 0))]
        fake = FakeSpansh(stations)
        medium = src.find("Sol", "Steel", pad=src.PAD_MEDIUM, search=fake)
        self.assertEqual(fake.calls[0][4]["required_pad"], "medium")
        self.assertEqual([s.station for s in medium.stations], ["Mid", "Big"])
        large = src.find("Sol", "Steel", pad=src.PAD_LARGE, search=fake)
        self.assertEqual(fake.calls[1][4]["required_pad"], "large")
        self.assertEqual([s.station for s in large.stations], ["Big"])

    def test_a_station_with_no_pad_figures_is_kept(self):
        unknown = StationPrice("Mystery", "X", "Outpost", 2.0, 100.0, False, 300, 10)
        result = src.find("Sol", "Steel", pad=src.PAD_LARGE, search=FakeSpansh([unknown]))
        self.assertEqual([s.station for s in result.stations], ["Mystery"])
        self.assertEqual(result.stations[0].pad, "?")


class CarrierTests(unittest.TestCase):
    def setUp(self):
        src.clear_cache()

    def test_carriers_are_not_searched_unless_asked(self):
        fake = FakeSpansh([item("Port", 4)], [item("FC", 1, kind="Drake-Class Carrier")])
        result = src.find("Sol", "Steel", search=fake)
        self.assertEqual(len(fake.calls), 1)
        self.assertEqual(result.carriers, [])

    def test_carriers_come_back_in_their_own_list(self):
        fake = FakeSpansh([item("Port", 4)], [item("FC", 1, kind="Drake-Class Carrier")])
        result = src.find("Sol", "Steel", include_carriers=True, search=fake)
        self.assertEqual(len(fake.calls), 2)
        self.assertEqual([s.station for s in result.stations], ["Port"])
        self.assertEqual([s.station for s in result.carriers], ["FC"])
        self.assertTrue(result.carriers[0].is_carrier)
        self.assertFalse(result.stations[0].is_carrier)


class OrderingTests(unittest.TestCase):
    def setUp(self):
        src.clear_cache()

    def test_closest_first_by_default_then_price(self):
        stations = [item("Far", 40, price=300), item("Near", 5, price=500), item("Near2", 5, price=450)]
        result = src.find("Sol", "Steel", search=FakeSpansh(stations))
        self.assertEqual([s.station for s in result.stations], ["Near2", "Near", "Far"])

    def test_cheapest_first_when_asked(self):
        stations = [item("Far", 40, price=300), item("Near", 5, price=500)]
        fake = FakeSpansh(stations)
        result = src.find("Sol", "Steel", sort=src.SORT_PRICE, search=fake)
        self.assertEqual([s.station for s in result.stations], ["Far", "Near"])
        self.assertEqual(fake.calls[0][4]["sort_by"], "price")


class RequestTests(unittest.TestCase):
    def setUp(self):
        src.clear_cache()

    def test_buy_search_around_the_given_system_and_radius(self):
        fake = FakeSpansh([])
        src.find("  Sol ", "Steel", radius_ly=100, search=fake)
        system, commodity, transaction, radius, kwargs = fake.calls[0]
        self.assertEqual((system, commodity, transaction, radius), ("Sol", "Steel", "Buy", 100))
        self.assertEqual(kwargs["market_days_old"], src.MAX_AGE_DAYS)

    def test_no_limit_radius_is_passed_as_none(self):
        fake = FakeSpansh([])
        src.find("Sol", "Steel", radius_ly=None, search=fake)
        self.assertIsNone(fake.calls[0][3])

    def test_a_blank_system_is_refused_before_any_request(self):
        fake = FakeSpansh([])
        with self.assertRaises(ValueError):
            src.find("   ", "Steel", search=fake)
        self.assertEqual(fake.calls, [])


class SpanshRequestTests(unittest.TestCase):
    """The request body the shared Spansh search builds for the new sort and pad options."""

    def body_for(self, **kwargs):
        import io
        import json
        from unittest import mock
        from plugin import mining_spansh_client as client
        captured = {}

        def fake_urlopen(request, timeout=0):
            captured["body"] = json.loads(request.data.decode("utf8"))
            return io.BytesIO(b'{"results": []}')

        with mock.patch.object(client.urllib.request, "urlopen", fake_urlopen):
            client.search_best_price_stations("Sol", "Steel", "Buy", 50, **kwargs)
        return captured["body"]

    def test_default_request_is_unchanged(self):
        body = self.body_for()
        self.assertNotIn("medium_pads", body["filters"])
        self.assertNotIn("large_pads", body["filters"])
        self.assertIn("market_buy_price", body["sort"][0])

    def test_distance_sort_and_pad_filter(self):
        body = self.body_for(sort_by="distance", required_pad="large")
        self.assertEqual(body["sort"], [{"distance": {"direction": "asc"}}])
        self.assertEqual(body["filters"]["large_pads"], {"comparison": "<=>", "value": [1, 999]})

    def test_bad_options_are_refused(self):
        with self.assertRaises(ValueError):
            self.body_for(sort_by="newest")
        with self.assertRaises(ValueError):
            self.body_for(required_pad="small")


if __name__ == "__main__":
    unittest.main()
