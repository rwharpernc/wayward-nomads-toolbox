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


class WholeListTests(unittest.TestCase):
    def setUp(self):
        src.clear_cache()
        self.slept = []

    def run_list(self, commodities, fake, **kwargs):
        return src.find_whole_list("Sol", commodities, search=fake, sleep=self.slept.append, **kwargs)

    def test_each_commodity_is_searched_once_in_the_order_given(self):
        fake = FakeSpansh([item("Near", 5)])
        result = self.run_list(["Steel", "Water", "Copper"], fake)
        self.assertEqual([label for label, _ in result.found], ["Steel", "Water", "Copper"])
        self.assertEqual([call[1] for call in fake.calls], ["Steel", "Water", "Copper"])
        self.assertEqual(result.failed, [])
        self.assertFalse(result.stopped)

    def test_it_pauses_between_requests_but_not_before_the_first(self):
        self.run_list(["Steel", "Water", "Copper"], FakeSpansh([item("Near", 5)]), pause=0.4)
        self.assertEqual(self.slept, [0.4, 0.4])

    def test_answers_from_memory_send_nothing_and_cost_no_pause(self):
        fake = FakeSpansh([item("Near", 5)])
        self.run_list(["Steel", "Water"], fake)
        self.slept.clear()
        self.run_list(["Steel", "Water"], fake)
        self.assertEqual(len(fake.calls), 2)   # the second run was all cache hits
        self.assertEqual(self.slept, [])

    def test_one_failure_does_not_lose_the_others(self):
        def flaky(system, commodity, transaction, radius, **kwargs):
            if commodity == "Water":
                raise RuntimeError("Spansh timed out")
            return [item("Near", 5)]
        result = self.run_list(["Steel", "Water", "Copper"], flaky)
        self.assertEqual([label for label, _ in result.found], ["Steel", "Copper"])
        self.assertEqual(result.failed, [("Water", "Spansh timed out")])

    def test_stopping_keeps_what_was_found_so_far(self):
        calls = []
        result = self.run_list(["Steel", "Water", "Copper"], FakeSpansh([item("Near", 5)]),
                               cancelled=lambda: len(calls) >= 1, progress=lambda i, n, label: calls.append(label))
        self.assertEqual([label for label, _ in result.found], ["Steel"])
        self.assertTrue(result.stopped)

    def test_progress_reports_position_total_and_name(self):
        seen = []
        self.run_list(["Steel", "Water"], FakeSpansh([item("Near", 5)]), progress=lambda i, n, label: seen.append((i, n, label)))
        self.assertEqual(seen, [(0, 2, "Steel"), (1, 2, "Water")])

    def test_commodities_with_no_source_are_listed(self):
        fake = FakeSpansh([])
        result = self.run_list(["Steel", "Water"], fake)
        self.assertEqual(result.without_sources(), ["Steel", "Water"])

    def test_a_blank_system_is_refused_before_any_request(self):
        fake = FakeSpansh([item("Near", 5)])
        with self.assertRaises(ValueError):
            src.find_whole_list("  ", ["Steel"], search=fake)
        self.assertEqual(fake.calls, [])

    def test_options_reach_every_request(self):
        fake = FakeSpansh([item("Near", 5)])
        self.run_list(["Steel", "Water"], fake, radius_ly=100, pad=src.PAD_LARGE)
        self.assertEqual({call[3] for call in fake.calls}, {100})
        self.assertEqual({call[4]["required_pad"] for call in fake.calls}, {"large"})


class PrefsTests(unittest.TestCase):
    def test_defaults_when_nothing_is_saved(self):
        self.assertEqual(src.load_prefs(""), src.SearchPrefs())
        self.assertEqual(src.load_prefs(None), src.SearchPrefs())

    def test_a_round_trip_keeps_every_choice(self):
        prefs = src.SearchPrefs(radius_ly=100.0, pad=src.PAD_LARGE, carriers=True, sort=src.SORT_PRICE)
        self.assertEqual(src.load_prefs(src.dump_prefs(prefs)), prefs)

    def test_no_limit_survives_a_round_trip(self):
        prefs = src.SearchPrefs(radius_ly=None)
        self.assertIsNone(src.load_prefs(src.dump_prefs(prefs)).radius_ly)

    def test_junk_falls_back_to_the_defaults_field_by_field(self):
        self.assertEqual(src.load_prefs("not json"), src.SearchPrefs())
        self.assertEqual(src.load_prefs("[1, 2]"), src.SearchPrefs())
        loaded = src.load_prefs('{"radius": 7, "pad": "huge", "carriers": "yes", "sort": "newest"}')
        self.assertEqual(loaded, src.SearchPrefs())
        self.assertEqual(src.load_prefs('{"radius": 25, "pad": "medium"}'),
                         src.SearchPrefs(radius_ly=25.0, pad=src.PAD_MEDIUM))
        self.assertEqual(src.load_prefs('{"radius": true}').radius_ly, src.DEFAULT_RADIUS_LY)


class OneStopTests(unittest.TestCase):
    """The extra "stations that sell every commodity" request merged into a whole-list search."""

    def setUp(self):
        src.clear_cache()
        self.calls = []

    def one_stop(self, hits):
        def fake(system, labels, radius, **kwargs):
            self.calls.append((system, list(labels), radius, kwargs))
            return hits
        return fake

    def run_list(self, one_stop, labels=("Steel", "Water"), **kwargs):
        return src.find_whole_list("Sol", list(labels), search=FakeSpansh([item("Near", 5)]), sleep=lambda s: None,
                                   one_stop=one_stop, **kwargs)

    def test_a_station_selling_everything_is_added_to_each_commodity_with_its_own_price(self):
        far = item("Hub", 80)
        result = self.run_list(self.one_stop([(far, {"Steel": (120, 900), "Water": (30, 400)})]))
        steel, water = (r for _, r in result.found)
        self.assertEqual([(s.station, s.price, s.supply) for s in steel.stations], [("Near", 400, 1000), ("Hub", 120, 900)])
        self.assertEqual([(s.station, s.price, s.supply) for s in water.stations], [("Near", 400, 1000), ("Hub", 30, 400)])
        self.assertEqual(len(self.calls), 1)
        self.assertEqual(self.calls[0][1], ["Steel", "Water"])

    def test_a_station_already_listed_is_not_added_twice(self):
        result = self.run_list(self.one_stop([(item("Near", 5), {"Steel": (1, 1), "Water": (1, 1)})]))
        self.assertTrue(all(len(r.stations) == 1 for _, r in result.found))

    def test_the_route_can_use_the_added_station(self):
        result = self.run_list(self.one_stop([(item("Hub", 80), {"Steel": (120, 900), "Water": (30, 400)})]))
        plan = src.plan_route(result.found, {"Steel": 1800, "Water": 1200})   # more than "Near" alone has in stock
        self.assertEqual(sorted(stop.station for stop in plan.stops), ["Hub", "Near"])
        self.assertEqual(plan.uncovered, ())

    def test_pad_size_is_respected(self):
        small_only = item("Hub", 80, pads=(2, 0, 0))
        result = self.run_list(self.one_stop([(small_only, {"Steel": (1, 9), "Water": (1, 9)})]), pad=src.PAD_LARGE)
        self.assertTrue(all(len(r.stations) == 1 for _, r in result.found))

    def test_a_failing_extra_request_loses_nothing(self):
        def broken(*args, **kwargs):
            raise RuntimeError("busy")
        result = self.run_list(broken)
        self.assertEqual([label for label, _ in result.found], ["Steel", "Water"])

    def test_a_single_commodity_or_a_failed_one_skips_the_extra_request(self):
        self.run_list(self.one_stop([]), labels=["Steel"])
        self.assertEqual(self.calls, [])

    def test_it_is_off_unless_given(self):
        result = src.find_whole_list("Sol", ["Steel", "Water"], search=FakeSpansh([item("Near", 5)]), sleep=lambda s: None)
        self.assertTrue(all(len(r.stations) == 1 for _, r in result.found))


class NeedsAwareTests(unittest.TestCase):
    """With `needs`: the one-stop request goes first, satisfied commodities skip their own search, leftovers get one more."""

    def setUp(self):
        src.clear_cache()
        self.calls = []

    def one_stop(self, *answers):
        queue = list(answers)

        def fake(system, labels, radius, **kwargs):
            self.calls.append((list(labels), kwargs.get("also")))
            return queue.pop(0) if queue else []
        return fake

    def run_list(self, fake_stop, search, needs, labels=("Steel", "Water")):
        return src.find_whole_list("Sol", list(labels), search=search, sleep=lambda s: None, one_stop=fake_stop, needs=needs)

    def test_a_commodity_one_stop_can_supply_in_full_is_not_searched(self):
        search = FakeSpansh([item("Near", 5)])
        hub = (item("Hub", 80), {"Steel": (120, 900), "Water": (30, 400)})
        result = self.run_list(self.one_stop([hub]), search, {"Steel": 500, "Water": 1200})
        self.assertEqual([call[1] for call in search.calls], ["Water"])   # Steel came from the hub alone
        steel = dict(result.found)["Steel"]
        self.assertEqual([s.station for s in steel.stations], ["Hub"])

    def test_nothing_is_skipped_when_the_stock_falls_short(self):
        search = FakeSpansh([item("Near", 5)])
        hub = (item("Hub", 80), {"Steel": (120, 100), "Water": (30, 100)})
        self.run_list(self.one_stop([hub]), search, {"Steel": 500, "Water": 500})
        self.assertEqual(sorted(call[1] for call in search.calls), ["Steel", "Water"])

    def test_leftover_commodities_get_one_more_whole_market_request(self):
        search = FakeSpansh([item("Near", 5, qty=10)])   # too little of anything
        market = (item("Depot", 40), {"Water": (30, 900), "Ore": (50, 900), "Steel": (110, 900)})
        fake = self.one_stop([], [market])
        result = self.run_list(fake, search, {"Water": 500, "Ore": 500, "Steel": 500}, labels=("Water", "Ore", "Steel"))
        self.assertEqual(len(self.calls), 2)
        self.assertEqual(sorted(self.calls[1][0]), ["Ore", "Steel", "Water"])   # all three still uncovered
        plan = src.plan_route(result.found, {"Water": 500, "Ore": 500, "Steel": 500})
        self.assertEqual([stop.station for stop in plan.stops][-1], "Depot")
        self.assertEqual(plan.uncovered, ())

    def test_no_leftover_request_when_the_route_covers_everything(self):
        search = FakeSpansh([item("Near", 5)])
        self.run_list(self.one_stop([]), search, {"Steel": 100, "Water": 100})
        self.assertEqual(len(self.calls), 1)

    def test_a_failing_first_request_still_searches_every_commodity(self):
        def broken(*args, **kwargs):
            raise RuntimeError("busy")
        search = FakeSpansh([item("Near", 5)])
        result = self.run_list(broken, search, {"Steel": 100, "Water": 100})
        self.assertEqual(sorted(call[1] for call in search.calls), ["Steel", "Water"])
        self.assertEqual(len(result.found), 2)


if __name__ == "__main__":
    unittest.main()
