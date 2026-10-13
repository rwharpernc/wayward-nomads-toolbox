"""The watch list's Spansh refresh (trade_watch_lookup.py): shaping, a failure that does not lose the rest, cancelling, pacing."""
from __future__ import annotations

import os
import sys
import threading
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from plugin import trade_watch_lookup as L  # noqa: E402
from plugin.mining_spansh_client import StationPrice  # noqa: E402


def station(name, price, quantity=100, distance=10.0):
    return StationPrice(name, "Sys " + name, "Coriolis Starport", distance, 500.0, False, price, quantity)


class Search:
    """A stand-in for the Spansh search that records what it was asked and answers from a table."""

    def __init__(self, answers, fail_on=()):
        self.answers, self.fail_on, self.calls = answers, set(fail_on), []

    def __call__(self, reference, commodity, transaction, radius, **kwargs):
        self.calls.append((reference, commodity, transaction, radius, kwargs))
        if (commodity, transaction) in self.fail_on:
            raise OSError("no network")
        return self.answers.get((commodity, transaction), [])


def now():
    return "2026-10-13T12:00:00Z"


class RefreshTests(unittest.TestCase):
    @staticmethod
    def run_refresh(names, search, **kwargs):
        sleeps = []
        found, problems = L.refresh(names, "Sol", 100, search=search, sleep=sleeps.append, now=now, **kwargs)
        return found, problems, sleeps

    def test_the_first_station_of_each_side_is_kept(self):
        search = Search({("Gold", "Buy"): [station("A", 9000), station("B", 9500)], ("Gold", "Sell"): [station("C", 11000, 40)]})
        found, problems, _ = self.run_refresh(["Gold"], search)
        self.assertEqual(problems, [])
        lookup = found["Gold"]
        self.assertEqual((lookup.buy.station, lookup.buy.price, lookup.buy.source), ("A", 9000, "Spansh"))
        self.assertEqual((lookup.sell.station, lookup.sell.price, lookup.sell.quantity), ("C", 11000, 40))
        self.assertEqual(lookup.reference, "Sol")

    def test_every_station_asked_for_is_kept_in_the_order_given(self):
        search = Search({("Gold", "Buy"): [station(n, 9000 + i, 10 * i) for i, n in enumerate("ABCDEFG")],
                         ("Gold", "Sell"): [station("S", 11000), station("T", 10900)]})
        found, _, _ = self.run_refresh(["Gold"], search)
        self.assertEqual([q.station for q in found["Gold"].buys], list("ABCDE"))   # at most RESULTS, cheapest first as Spansh sorted
        self.assertEqual([q.station for q in found["Gold"].sells], ["S", "T"])
        self.assertEqual(search.calls[0][4]["max_results"], L.RESULTS)

    def test_a_side_nobody_has_is_empty(self):
        found, _, _ = self.run_refresh(["Gold"], Search({("Gold", "Buy"): [station("A", 9000)]}))
        self.assertEqual(found["Gold"].sells, ())
        self.assertIsNone(found["Gold"].sell)

    def test_only_the_names_and_the_system_are_sent_and_fleet_carriers_are_left_out(self):
        search = Search({})
        self.run_refresh(["Gold"], search)
        reference, commodity, _transaction, radius, kwargs = search.calls[0]
        self.assertEqual((reference, commodity, radius), ("Sol", "Gold", 100))
        self.assertNotIn("Drake-Class Carrier", kwargs["station_types"])
        self.assertEqual(kwargs["market_days_old"], L.MAX_AGE_DAYS)

    def test_one_failure_does_not_lose_the_others(self):
        search = Search({("Silver", "Buy"): [station("A", 100)]}, fail_on={("Gold", "Sell")})
        found, problems, _ = self.run_refresh(["Gold", "Silver"], search)
        self.assertEqual(list(found), ["Silver"])
        self.assertEqual(len(problems), 1)
        self.assertIn("Gold", problems[0])

    def test_every_failure_is_reported(self):
        search = Search({}, fail_on={("Gold", "Buy"), ("Silver", "Buy")})
        found, problems, _ = self.run_refresh(["Gold", "Silver"], search)
        self.assertEqual((found, len(problems)), ({}, 2))

    def test_requests_are_paced(self):
        search = Search({})
        _, _, sleeps = self.run_refresh(["Gold", "Silver"], search)
        self.assertEqual(len(search.calls), 4)
        self.assertEqual(sleeps, [L.PAUSE_S] * 3)   # none before the first request

    def test_cancelling_stops_between_commodities(self):
        cancel = threading.Event()

        class Cancelling(Search):
            def __call__(self, *args, **kwargs):
                cancel.set()
                return super().__call__(*args, **kwargs)

        search = Cancelling({})
        found, _, _ = self.run_refresh(["Gold", "Silver"], search, cancel=cancel)
        self.assertEqual(sorted(found), ["Gold"])
        self.assertEqual(len(search.calls), 2)


if __name__ == "__main__":
    unittest.main()
