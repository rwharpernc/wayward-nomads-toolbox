"""
The suggested shopping route (colonisation_sources.plan_route): from the per-commodity answers of a whole-list search, the few
stops that between them supply the most of what is still needed. Pure; no network.
"""
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

from plugin import colonisation_sources as S  # noqa: E402


def src(station, ly, price, supply, carrier=False, system=None):
    return S.Source(station, system or "Sys " + station, "Drake-Class Carrier" if carrier else "Coriolis Starport", carrier,
                    False, "Large", ly, 500.0, price, supply)


def result(*stations, carriers=()):
    return S.SearchResult(list(stations), list(carriers))


class PlanTests(unittest.TestCase):
    def test_one_station_that_sells_everything_is_one_stop(self):
        found = [("Steel", result(src("Hub", 10, 400, 900))), ("Water", result(src("Hub", 10, 90, 500)))]
        plan = S.plan_route(found, {"Steel": 300, "Water": 100})
        self.assertEqual(len(plan.stops), 1)
        self.assertEqual({b.commodity: b.tonnes for b in plan.stops[0].buys}, {"Steel": 300, "Water": 100})
        self.assertEqual((plan.needed, plan.covered, plan.uncovered), (400, 400, ()))

    def test_a_station_selling_several_beats_the_nearest_seller_of_one(self):
        found = [("Steel", result(src("Near", 2, 400, 900), src("Hub", 20, 410, 900))),
                 ("Water", result(src("Hub", 20, 90, 500))),
                 ("Copper", result(src("Hub", 20, 300, 500)))]
        plan = S.plan_route(found, {"Steel": 300, "Water": 100, "Copper": 100})
        self.assertEqual([s.station for s in plan.stops], ["Hub"])

    def test_stock_that_is_too_small_is_topped_up_at_a_second_stop(self):
        # The station with the most stock is taken first, the nearer one only tops up what is left, and they fly nearest first.
        found = [("Steel", result(src("A", 5, 400, 200), src("B", 15, 410, 500)))]
        plan = S.plan_route(found, {"Steel": 600})
        self.assertEqual([(s.station, s.buys[0].tonnes) for s in plan.stops], [("A", 100), ("B", 500)])
        self.assertEqual((plan.covered, plan.uncovered), (600, ()))

    def test_stops_are_ordered_nearest_first_whatever_order_they_were_chosen_in(self):
        found = [("Steel", result(src("Far", 40, 400, 1000))), ("Water", result(src("Near", 3, 90, 100)))]
        plan = S.plan_route(found, {"Steel": 500, "Water": 50})
        self.assertEqual([s.station for s in plan.stops], ["Near", "Far"])

    def test_what_nobody_in_range_sells_is_reported_not_guessed(self):
        found = [("Steel", result(src("A", 5, 400, 900))), ("Titanium", result())]
        plan = S.plan_route(found, {"Steel": 100, "Titanium": 80})
        self.assertEqual(plan.uncovered, (("Titanium", 80),))
        self.assertEqual((plan.needed, plan.covered), (180, 100))

    def test_a_commodity_with_not_enough_total_stock_shows_what_is_missing(self):
        found = [("Steel", result(src("A", 5, 400, 120)))]
        plan = S.plan_route(found, {"Steel": 500})
        self.assertEqual(plan.uncovered, (("Steel", 380),))

    def test_it_never_plans_more_stops_than_the_limit(self):
        found = [("Steel", result(*[src(f"S{i}", i + 1, 400, 10) for i in range(20)]))]
        plan = S.plan_route(found, {"Steel": 1000}, max_stops=3)
        self.assertEqual(len(plan.stops), 3)
        self.assertEqual(plan.covered, 30)

    def test_ties_go_to_the_nearer_then_the_cheaper_station(self):
        found = [("Steel", result(src("Far", 30, 400, 500), src("Near", 4, 450, 500)))]
        self.assertEqual(S.plan_route(found, {"Steel": 100}).stops[0].station, "Near")
        found = [("Steel", result(src("Dear", 4, 450, 500), src("Cheap", 4, 400, 500)))]
        self.assertEqual(S.plan_route(found, {"Steel": 100}).stops[0].station, "Cheap")

    def test_carriers_are_used_when_the_search_included_them_and_are_marked(self):
        found = [("Steel", result(carriers=[src("K7X-LLL", 6, 300, 900, carrier=True)]))]
        plan = S.plan_route(found, {"Steel": 100})
        self.assertTrue(plan.stops[0].is_carrier)
        self.assertIn("(fleet carrier)", plan.lines()[1])

    def test_empty_stock_and_unwanted_commodities_are_ignored(self):
        found = [("Steel", result(src("A", 5, 400, 0))), ("Gold", result(src("B", 1, 9000, 99)))]
        plan = S.plan_route(found, {"Steel": 100})
        self.assertEqual(plan.stops, ())
        self.assertEqual(plan.uncovered, (("Steel", 100),))

    def test_nothing_needed_means_no_plan(self):
        plan = S.plan_route([("Steel", result(src("A", 5, 400, 900)))], {})
        self.assertEqual((plan.stops, plan.needed, plan.lines()), ((), 0, []))
        self.assertEqual(S.plan_route([], {"Steel": 5}).uncovered, (("Steel", 5),))

    def test_a_station_name_shared_by_two_systems_is_two_stations(self):
        found = [("Steel", result(src("Port", 3, 400, 100, system="Alpha"), src("Port", 9, 400, 100, system="Beta")))]
        plan = S.plan_route(found, {"Steel": 200})
        self.assertEqual(sorted(s.system for s in plan.stops), ["Alpha", "Beta"])

    def test_the_lines_read_as_a_route(self):
        found = [("Steel", result(src("Hub", 12.34, 400, 900))), ("Water", result(src("Hub", 12.34, 90, 500)))]
        lines = S.plan_route(found, {"Steel": 300, "Water": 100}).lines()
        self.assertEqual(lines[0], "Suggested shopping route: 1 stop, 400 of 400 t covered")
        self.assertEqual(lines[1], "1. Hub (Sys Hub), 12.3 ly: Steel 300 t, Water 100 t")


if __name__ == "__main__":
    unittest.main()
