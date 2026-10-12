"""Tests for trade_roundtrip: the best back-and-forth pair of stations, loaded both ways."""
from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from plugin import trade_roundtrip as rt  # noqa: E402


def station(name, market, x=0.0, system=None, ls=100.0, planetary=False, carrier=False, pads=None):
    """market: {commodity: (buy_price, sell_price, supply, demand)}."""
    return rt.Station(name, system or name, x, 0.0, 0.0, ls, planetary, carrier,
                      pads or {"small": 1, "medium": 1, "large": 1},
                      {c: rt.Offer(c, *v) for c, v in market.items()})


class BestLoadTests(unittest.TestCase):
    def test_best_commodity_first_then_the_rest_of_the_hold(self) -> None:
        a = station("A", {"Gold": (100, 90, 50, 0), "Tea": (10, 5, 1000, 0)})
        b = station("B", {"Gold": (0, 200, 0, 40), "Tea": (0, 30, 0, 1000)})
        load = rt.best_load(a, b, cargo=100, capital=10_000_000)
        # Gold earns 100/t but only 40 t are wanted; the rest of the hold goes to tea (20/t).
        self.assertEqual([(n, t) for n, t, _ in load.items], [("Gold", 40), ("Tea", 60)])
        self.assertEqual(load.profit, 40 * 100 + 60 * 20)

    def test_limited_by_what_you_can_afford(self) -> None:
        a = station("A", {"Gold": (100, 90, 500, 0)})
        b = station("B", {"Gold": (0, 200, 0, 500)})
        self.assertEqual(rt.best_load(a, b, 100, capital=1000).tonnes, 10)
        self.assertIsNone(rt.best_load(a, b, 100, capital=50))

    def test_thin_markets_are_left_out(self) -> None:
        a = station("A", {"Gold": (100, 90, 50, 0)})
        b = station("B", {"Gold": (0, 200, 0, 500)})
        self.assertIsNotNone(rt.best_load(a, b, 100, 10**9))
        self.assertIsNone(rt.best_load(a, b, 100, 10**9, min_supply=100))
        self.assertIsNone(rt.best_load(a, b, 100, 10**9, min_demand=1000))

    def test_no_profit_gives_none(self) -> None:
        a = station("A", {"Gold": (200, 190, 50, 0)})
        b = station("B", {"Gold": (0, 150, 0, 50)})
        self.assertIsNone(rt.best_load(a, b, 100, 10**9))


class FindRoundTripsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.start = station("Start", {"Gold": (100, 90, 500, 0), "Tea": (0, 50, 0, 500)})

    def test_both_legs_must_be_loaded(self) -> None:
        loaded = station("Loaded", {"Gold": (0, 200, 0, 500), "Tea": (20, 15, 500, 0)}, x=10)
        one_way = station("OneWay", {"Gold": (0, 200, 0, 500)}, x=10)   # nothing to carry back
        trips = rt.find_round_trips(self.start, [self.start, loaded, one_way], 100, 10**9, 30.0)
        self.assertEqual([t.b.name for t in trips], ["Loaded"])
        self.assertGreater(trips[0].out.profit, 0)
        self.assertGreater(trips[0].back.profit, 0)
        self.assertEqual(trips[0].profit, trips[0].out.profit + trips[0].back.profit)

    def test_ranked_by_profit_per_hour_not_per_loop(self) -> None:
        near = station("Near", {"Gold": (0, 150, 0, 500), "Tea": (20, 15, 500, 0)}, x=5)
        far = station("Far", {"Gold": (0, 400, 0, 500), "Tea": (20, 15, 500, 0)}, x=600, ls=20000)
        trips = rt.find_round_trips(self.start, [near, far], 100, 10**9, 30.0, limit=2)
        self.assertEqual(trips[0].b.name, "Near")             # the far pair pays more per loop but takes far longer
        self.assertGreater(trips[1].profit, trips[0].profit)

    def test_carriers_ground_pads_and_arrival_distance_are_respected(self) -> None:
        market = {"Gold": (0, 200, 0, 500), "Tea": (20, 15, 500, 0)}
        carrier = station("Carrier", market, carrier=True)
        ground = station("Ground", market, planetary=True)
        small = station("Small", market, pads={"small": 1, "medium": 0, "large": 0})
        distant = station("Distant", market, ls=9000)
        others = [carrier, ground, small, distant]
        self.assertEqual(rt.find_round_trips(self.start, others, 100, 10**9, 30.0, ship_pad="large",
                                             include_ground=False, include_carriers=False, max_arrival_ls=5000), [])
        names = lambda **kw: {t.b.name for t in rt.find_round_trips(  # noqa: E731
            self.start, others, 100, 10**9, 30.0, limit=10, **kw)}
        self.assertEqual(names(include_ground=True, include_carriers=True), {"Carrier", "Ground", "Small", "Distant"})
        self.assertEqual(names(ship_pad="large", include_ground=True, include_carriers=True),
                         {"Carrier", "Ground", "Distant"})

    def test_the_start_is_never_its_own_partner(self) -> None:
        self.assertEqual(rt.find_round_trips(self.start, [self.start], 100, 10**9, 30.0), [])

    def test_find_start_ignores_case(self) -> None:
        self.assertIs(rt.find_start([self.start], "start", "START"), self.start)
        self.assertIsNone(rt.find_start([self.start], "Elsewhere", "Start"))


class LegDetailTests(unittest.TestCase):
    def _load(self):
        a = station("A", {"Gold": (100, 90, 50, 0), "Tea": (10, 5, 1000, 0)})
        b = station("B", {"Gold": (0, 200, 0, 40), "Tea": (0, 30, 0, 1000)})
        return rt.best_load(a, b, cargo=100, capital=10_000_000)

    def test_each_commodity_keeps_its_prices_supply_and_demand(self) -> None:
        gold, tea = self._load().lines
        self.assertEqual((gold.name, gold.tonnes, gold.buy_price, gold.sell_price, gold.supply, gold.demand),
                         ("Gold", 40, 100, 200, 50, 40))
        self.assertEqual((gold.per_tonne, gold.profit), (100, 4000))
        self.assertEqual((tea.per_tonne, tea.profit), (20, 1200))

    def test_the_lines_agree_with_the_items_and_the_total(self) -> None:
        load = self._load()
        self.assertEqual([(l.name, l.tonnes, l.per_tonne) for l in load.lines], load.items)
        self.assertEqual(sum(l.profit for l in load.lines), load.profit)

    def test_a_load_built_without_lines_still_works(self) -> None:
        load = rt.Load([("Gold", 1, 5)], 1, 5)
        self.assertEqual(load.lines, [])
        self.assertEqual(len(rt.leg_blocks("Out", load, "B")), 1)

    def test_the_leg_reads_as_a_summary_then_a_line_per_commodity(self) -> None:
        from plugin.trade_blocks import to_text
        text = to_text(rt.leg_blocks("Out", self._load(), "Station B"))
        self.assertEqual(text[0], "Out to Station B: 100 t, +5,200 cr")
        self.assertIn("Gold × 40 t  +4,000", text[1])
        self.assertIn("buy 100 → sell 200 (+100/t) · supply 50 / demand 40", text[2])

    def test_only_the_first_few_commodities_are_listed_and_the_rest_counted(self) -> None:
        market_a = {f"C{i}": (10, 5, 100, 0) for i in range(6)}
        market_b = {f"C{i}": (0, 20 + i, 0, 100) for i in range(6)}
        load = rt.best_load(station("A", market_a), station("B", market_b), cargo=600, capital=10**9)
        blocks = rt.leg_blocks("Back", load, "A")
        self.assertEqual(len(blocks), 1 + rt.LEG_COMMODITIES_SHOWN + 1)
        from plugin.trade_blocks import to_text
        self.assertEqual(to_text(blocks)[-1], "+3 more commodities")

    def test_a_name_from_outside_goes_through_the_clip(self) -> None:
        from plugin.trade_blocks import to_text
        text = to_text(rt.leg_blocks("Out", self._load(), "S" * 100, clip=lambda t: t[:10]))
        self.assertTrue(text[0].startswith("Out to " + "S" * 10 + ":"))


class SearchRadiusTests(unittest.TestCase):
    def test_with_nothing_chosen_it_follows_the_jump_range_within_limits(self):
        self.assertEqual(rt.search_radius(0, 30.0), 60.0)
        self.assertEqual(rt.search_radius(0, 5.0), rt.AUTO_RADIUS_MIN)      # a short-range ship still looks 20 ly
        self.assertEqual(rt.search_radius(0, 80.0), rt.AUTO_RADIUS_MAX)     # and a long-range one stops at 100 ly
        self.assertEqual(rt.search_radius(0, 0.0), rt.AUTO_RADIUS_MIN)      # an unknown range
        self.assertEqual(rt.search_radius(0, None), rt.AUTO_RADIUS_MIN)

    def test_a_chosen_radius_is_used_as_given(self):
        self.assertEqual(rt.search_radius(150, 30.0), 150.0)
        self.assertEqual(rt.search_radius(25, 80.0), 25.0)               # smaller than the automatic one, if that is what was asked

    def test_a_chosen_radius_is_held_to_sensible_limits(self):
        self.assertEqual(rt.search_radius(1, 30.0), float(rt.CHOSEN_RADIUS_MIN))
        self.assertEqual(rt.search_radius(100_000, 30.0), float(rt.CHOSEN_RADIUS_MAX))

    def test_a_negative_choice_means_automatic(self):
        self.assertEqual(rt.search_radius(-5, 30.0), 60.0)


class ParseTests(unittest.TestCase):
    def test_a_spansh_record_becomes_a_station(self) -> None:
        raw = {"name": "Lloyd Dock", "system_name": "Candiaei", "system_x": 1.0, "system_y": 2.0, "system_z": 3.0,
               "distance_to_arrival": 12.5, "is_planetary": False, "type": "Orbis Starport",
               "small_pads": 2, "medium_pads": 3, "large_pads": 1,
               "market": [{"commodity": "Gold", "buy_price": 9, "sell_price": 8, "supply": 5, "demand": 0}]}
        s = rt.parse_station(raw)
        self.assertEqual((s.name, s.system, s.pads["large"], s.is_carrier), ("Lloyd Dock", "Candiaei", 1, False))
        self.assertEqual(s.market["Gold"].supply, 5)
        self.assertTrue(rt.parse_station({**raw, "type": rt.CARRIER_TYPE}).is_carrier)

    def test_a_station_without_a_market_is_skipped(self) -> None:
        self.assertIsNone(rt.parse_station({"name": "X", "market": []}))
        self.assertIsNone(rt.parse_station({"name": "X"}))


if __name__ == "__main__":
    unittest.main()
