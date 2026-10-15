"""The four picks (source_picks.py) and the two Spansh search options they need (mining_spansh_client.search_best_price_stations): the closest place in stock, the best
nearby, the cheapest anywhere, and the nearest within 10% of the cheapest. A fake search stands in for Spansh, so no network is used."""
from __future__ import annotations

import os
import sys
import types
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
if "config" not in sys.modules:
    _stub = types.ModuleType("config")
    _stub.appname = "EDMarketConnector"
    _stub.config = types.SimpleNamespace(get_str=lambda key: "", default_journal_dir="")
    sys.modules["config"] = _stub

from plugin import mining_spansh_client as client  # noqa: E402
from plugin import source_picks as P  # noqa: E402
from plugin.mining_spansh_client import StationPrice  # noqa: E402
from plugin.trade_prices import BUY, SELL  # noqa: E402


def station(name, system, distance, price, quantity=500, kind="Coriolis Starport", planetary=False, small=3, medium=2, large=1):
    return StationPrice(name, system, kind, distance, 100.0, planetary, price, quantity, small, medium, large)


def carrier(name, distance, price, quantity=5000):
    return StationPrice(name, "Somewhere", "Drake-Class Carrier", distance, 0.0, False, price, quantity, 0, 0, 0)


class FakeSpansh:
    """Answers like Spansh would: filters by distance, stock, price band and station type, then sorts. Records every call."""

    def __init__(self, stations, carriers=()):
        self.stations, self.carriers = list(stations), list(carriers)
        self.calls = []

    def __call__(self, reference, commodity, transaction, max_distance, max_results=10, market_days_old=30, station_types=None, sort_by="price",
                 required_pad=None, min_quantity=1, price_range=None):
        self.calls.append(dict(max_distance=max_distance, sort_by=sort_by, station_types=station_types, required_pad=required_pad,
                               min_quantity=min_quantity, price_range=price_range, market_days_old=market_days_old, transaction=transaction))
        pool = self.carriers if station_types and "Drake-Class Carrier" in station_types else self.stations
        found = [s for s in pool if (max_distance is None or s.distance_ly <= max_distance) and s.quantity >= min_quantity
                 and (price_range is None or price_range[0] <= s.price <= price_range[1])]
        if required_pad == "large":
            found = [s for s in found if (s.large_pads or 0) > 0]
        if sort_by == "distance":
            found.sort(key=lambda s: s.distance_ly)
        else:
            found.sort(key=lambda s: s.price if transaction == "Buy" else -s.price)
        return found[:max_results]


def find(search, side=BUY, needed=40, radius=50.0, **kw):
    return P.find("Sol", "Gold", side, needed, radius_ly=radius, search=search, pause=lambda _s: None, **kw)


STATIONS = [
    station("Near Dock", "Sol", 4, 2800), station("Mid Port", "Ross 310", 20, 2600), station("Far Cheap", "Lave", 190, 2356),
    station("Band Port", "Wolf 359", 60, 2500), station("Edge Of Band", "Barnard's Star", 56, 2591), station("Just Outside", "Alioth", 25, 2650),
]


class PicksTests(unittest.TestCase):
    def test_the_four_picks_for_buying(self):
        picks = find(FakeSpansh(STATIONS), radius=50)
        self.assertEqual({k: p.offer.station for k, p in picks.picks.items()},
                         {P.CLOSEST: "Near Dock", P.LOCAL: "Mid Port", P.CHEAPEST: "Far Cheap", P.RECOMMENDED: "Edge Of Band"})

    def test_recommended_is_the_nearest_within_ten_percent_of_the_cheapest_in_the_galaxy(self):
        picks = find(FakeSpansh(STATIONS))
        recommended = picks.picks[P.RECOMMENDED].offer
        self.assertEqual((recommended.station, recommended.price), ("Edge Of Band", 2591))             # 2356 * 1.10 = 2591.6, so 2591 is in the band and 2650 is out
        self.assertEqual(P._band(BUY, 2356, 0.10), (2356, 2591))
        self.assertEqual(P._band(SELL, 1000, 0.10), (900, 1000))

    def test_the_band_is_sent_to_spansh_with_a_distance_sort(self):
        spansh = FakeSpansh(STATIONS)
        find(spansh)
        band = [c for c in spansh.calls if c["price_range"]]
        self.assertEqual(len(band), 1)
        self.assertEqual((band[0]["price_range"], band[0]["sort_by"], band[0]["max_distance"]), ((2356, 2591), "distance", None))

    def test_a_pick_that_is_also_another_says_so(self):
        only = [station("Only Dock", "Sol", 4, 2800)]
        picks = find(FakeSpansh(only))
        self.assertEqual({p.offer.station for p in picks.picks.values()}, {"Only Dock"})
        self.assertIn("also the cheapest", picks.picks[P.RECOMMENDED].note)
        self.assertIn("same as", picks.picks[P.LOCAL].note + picks.picks[P.CLOSEST].note)

    def test_one_search_per_pick_and_a_fifth_for_carriers(self):
        spansh = FakeSpansh(STATIONS, [carrier("ABC-123", 10, 2000)])
        picks = find(spansh)
        self.assertEqual(len(spansh.calls), 5)
        self.assertEqual(sum(1 for c in spansh.calls if c["station_types"] == ["Drake-Class Carrier"]), 1)
        self.assertTrue(any("fleet carrier" in n.lower() and "ABC-123" in n for n in picks.notes))
        spansh = FakeSpansh(STATIONS, [carrier("ABC-123", 10, 2000)])
        picks = find(spansh, include_carriers=False)
        self.assertEqual(len(spansh.calls), 4)
        self.assertEqual(picks.notes, [])

    def test_a_carrier_that_is_dearer_is_not_mentioned_and_never_a_pick(self):
        picks = find(FakeSpansh(STATIONS, [carrier("ABC-123", 1, 9000)]))
        self.assertEqual(picks.notes, [])
        self.assertFalse(any(p.offer.is_carrier for p in picks.picks.values()))

    def test_stock_is_asked_for_and_falls_back_with_a_note(self):
        thin = [station("Thin Dock", "Sol", 4, 2800, quantity=12), station("Fat Dock", "Ross 310", 20, 2900, quantity=900)]
        spansh = FakeSpansh(thin)
        picks = find(spansh, needed=40)
        self.assertEqual(picks.picks[P.CLOSEST].offer.station, "Fat Dock")                       # the nearest with 40 t
        self.assertEqual(picks.picks[P.CLOSEST].note, "")
        picks = find(FakeSpansh(thin), needed=1000)
        self.assertEqual(picks.picks[P.CLOSEST].offer.station, "Thin Dock")                      # nobody has 1,000 t: the nearest with any
        self.assertEqual(picks.picks[P.CLOSEST].note, "only 12 t in stock")

    def test_the_pad_and_the_age_limit_are_passed_on(self):
        spansh = FakeSpansh(STATIONS)
        find(spansh, ship_pad="large")
        self.assertTrue(all(c["required_pad"] == "large" and c["market_days_old"] == P.MAX_AGE_DAYS for c in spansh.calls))
        spansh = FakeSpansh(STATIONS)
        find(spansh, ship_pad="small")
        self.assertTrue(all(c["required_pad"] is None for c in spansh.calls))

    def test_ground_facilities_can_be_left_out(self):
        ground = [station("Surface Port", "Sol", 1, 100, kind="Planetary Port", planetary=True), station("Orbital", "Ross 310", 20, 2600)]
        with_ground = find(FakeSpansh(ground))
        self.assertEqual(with_ground.picks[P.CLOSEST].offer.station, "Surface Port")
        without = find(FakeSpansh([s for s in ground]), include_ground=False)
        self.assertEqual(without.picks[P.CLOSEST].offer.station, "Orbital")

    def test_selling_is_the_mirror_image(self):
        sells = [station("Near Dock", "Sol", 4, 900), station("Mid Port", "Ross 310", 20, 1000), station("Far Rich", "Lave", 190, 1200),
                 station("Band Port", "Wolf 359", 60, 1100), station("Edge Of Band", "Barnard's Star", 56, 1080), station("Just Outside", "Alioth", 25, 950)]
        picks = find(FakeSpansh(sells), side=SELL, radius=50)
        self.assertEqual({k: p.offer.station for k, p in picks.picks.items()},
                         {P.CLOSEST: "Near Dock", P.LOCAL: "Mid Port", P.CHEAPEST: "Far Rich", P.RECOMMENDED: "Edge Of Band"})     # 1200 * 0.9 = 1080
        self.assertEqual(picks.label(P.CHEAPEST), "Highest anywhere")

    def test_a_tie_in_price_goes_to_the_nearer_station(self):
        tie = [station("Far", "A", 90, 2000), station("Near", "B", 30, 2000)]
        picks = find(FakeSpansh(tie))
        self.assertEqual(picks.picks[P.CHEAPEST].offer.station, "Near")

    def test_nothing_found_says_so(self):
        picks = find(FakeSpansh([]))
        self.assertEqual(picks.picks, {})
        self.assertIn("no station", picks.notes[0].lower())

    def test_cancelling_stops_the_searches(self):
        spansh = FakeSpansh(STATIONS)
        state = {"left": 2}

        def cancelled():
            state["left"] -= 1
            return state["left"] < 0

        picks = find(spansh, cancelled=cancelled)
        self.assertLess(len(spansh.calls), 4)
        self.assertIsInstance(picks, P.Picks)

    def test_the_lines_read_in_order(self):
        lines = find(FakeSpansh(STATIONS)).lines()
        self.assertEqual([line.split(":")[0] for line in lines], ["Closest", "Best local", "Cheapest anywhere", "Recommended"])
        self.assertIn("Near Dock (Sol), 4 ly, 2,800 cr/t", lines[0])


class SearchOptionsTests(unittest.TestCase):
    def body(self, **kw):
        captured = {}

        def fake(body, agent=None):
            captured["body"] = body
            return {"results": []}

        with mock.patch.object(client, "_post_station_search", fake):
            client.search_best_price_stations("Sol", "Gold", kw.pop("transaction", "Buy"), None, **kw)
        return captured["body"]

    def test_the_defaults_are_unchanged(self):
        market = self.body()["filters"]["market"][0]
        self.assertEqual(market["supply"]["value"], ["1", "999999999"])
        self.assertNotIn("buy_price", market)

    def test_a_minimum_stock_and_a_price_band_are_sent(self):
        market = self.body(min_quantity=40, price_range=(2591, 2356))["filters"]["market"][0]
        self.assertEqual(market["supply"]["value"], ["40", "999999999"])
        self.assertEqual(market["buy_price"], {"value": ["2356", "2591"], "comparison": "<=>"})          # the bounds are put in order

    def test_selling_uses_demand_and_the_sell_price(self):
        market = self.body(transaction="Sell", min_quantity=10, price_range=(900, 1000))["filters"]["market"][0]
        self.assertEqual(market["demand"]["value"], ["10", "999999999"])
        self.assertEqual(market["sell_price"]["value"], ["900", "1000"])

    def test_a_silly_minimum_is_at_least_one(self):
        self.assertEqual(self.body(min_quantity=0)["filters"]["market"][0]["supply"]["value"][0], "1")


if __name__ == "__main__":
    unittest.main()
