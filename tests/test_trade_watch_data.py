"""Market watch list (trade_watch_data.py): adding and limits, keeping prices from a market, the best buy and sell across seen and
Spansh prices, ages, saving per commander and loading a damaged file."""
from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from plugin import trade_watch_data as W  # noqa: E402
from plugin.trade_market import MarketItem, parse_market  # noqa: E402


class Clock:
    def __init__(self):
        self.n = 0

    def __call__(self):
        self.n += 1
        return f"2026-10-13T12:{self.n:02d}:00Z"


def make(folder, cmdr="Bocheaux"):
    book = W.WatchBook(now=Clock())
    book.load(folder)
    book.set_commander(cmdr)
    return book


def item(name, buy=0, sell=0, stock=0, demand=0):
    return MarketItem(name, sell, buy, demand, stock)


def quote(price, station="Far", when="2026-10-13T13:00:00Z"):
    return W.Quote(price, 100, station, "Away", W.SPANSH, when, 40.0)


class AddTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.book = make(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_a_commodity_is_added_under_the_game_name(self):
        self.assertEqual(self.book.add("gold"), "Gold")
        self.assertEqual(self.book.watched(), ["Gold"])

    def test_the_journal_symbol_and_a_plural_slip_resolve(self):
        self.assertEqual(self.book.add("lowtemperaturediamond"), "Low Temperature Diamonds")
        self.assertEqual(self.book.add("void opals"), "Void Opal")

    def test_an_unknown_name_is_refused_with_a_message(self):
        with self.assertRaises(W.WatchError) as caught:
            self.book.add("not a commodity")
        self.assertIn("not a commodity I know", str(caught.exception))

    def test_a_long_unknown_name_is_clipped_in_the_message(self):
        with self.assertRaises(W.WatchError) as caught:
            self.book.add("x" * 500)
        self.assertLess(len(str(caught.exception)), 120)

    def test_the_same_commodity_twice_is_refused(self):
        self.book.add("Gold")
        with self.assertRaises(W.WatchError):
            self.book.add("GOLD")

    def test_the_limit_is_enforced_not_trimmed(self):
        from plugin.trade_commodities import SUGGESTIBLE
        for name in SUGGESTIBLE[:W.MAX_WATCHED]:
            self.book.add(name)
        with self.assertRaises(W.WatchError) as caught:
            self.book.add(SUGGESTIBLE[W.MAX_WATCHED])
        self.assertIn(str(W.MAX_WATCHED), str(caught.exception))
        self.assertEqual(self.book.count(), W.MAX_WATCHED)

    def test_nothing_can_be_added_before_a_commander_is_known(self):
        with self.assertRaises(W.WatchError):
            W.WatchBook().add("Gold")


class MarketTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.book = make(self.tmp.name)
        self.book.add("Gold")
        self.book.add("Tritium")

    def tearDown(self):
        self.tmp.cleanup()

    @staticmethod
    def market(**items):
        return {key: item(key, **vals) for key, vals in items.items()}

    def test_only_watched_commodities_are_kept(self):
        kept = self.book.record_market("Jameson", "Shinrarta", self.market(gold=dict(buy=9000, stock=50), silver=dict(buy=5, stock=1)))
        self.assertEqual(kept, 1)
        self.assertEqual([s.commodity for s in self.book.sightings("Gold")], ["Gold"])

    def test_a_market_that_trades_none_changes_nothing(self):
        self.assertEqual(self.book.record_market("A", "B", self.market(silver=dict(buy=5, stock=1))), 0)

    def test_an_item_with_no_prices_is_not_kept(self):
        self.assertEqual(self.book.record_market("A", "B", self.market(gold=dict(buy=0, sell=0, stock=10))), 0)

    def test_the_same_station_updates_one_entry(self):
        self.book.record_market("Jameson", "Shinrarta", self.market(gold=dict(buy=9000, stock=50)))
        self.book.record_market("JAMESON", "shinrarta", self.market(gold=dict(buy=9500, stock=40)))
        seen = self.book.sightings("Gold")
        self.assertEqual(len(seen), 1)
        self.assertEqual(seen[0].buy_price, 9500)

    def test_only_the_newest_stations_are_kept(self):
        for n in range(W.MAX_SIGHTINGS + 5):
            self.book.record_market(f"Station {n}", "Sys", self.market(gold=dict(buy=9000 + n, stock=5)))
        seen = self.book.sightings("Gold")
        self.assertEqual(len(seen), W.MAX_SIGHTINGS)
        self.assertEqual(seen[0].station, f"Station {W.MAX_SIGHTINGS + 4}")

    def test_best_buy_is_the_cheapest_in_stock_and_best_sell_the_dearest_wanted(self):
        self.book.record_market("A", "S", self.market(gold=dict(buy=9500, stock=10, sell=9000, demand=5)))
        self.book.record_market("B", "S", self.market(gold=dict(buy=9100, stock=10, sell=9400, demand=5)))
        self.book.record_market("C", "S", self.market(gold=dict(buy=8000, stock=0, sell=11000, demand=0)))   # nothing to buy or sell
        self.assertEqual((self.book.best_buy("Gold").station, self.book.best_buy("Gold").price), ("B", 9100))
        self.assertEqual((self.book.best_sell("Gold").station, self.book.best_sell("Gold").price), ("B", 9400))

    def test_nothing_seen_gives_no_price(self):
        self.assertIsNone(self.book.best_buy("Gold"))
        self.assertIsNone(self.book.best_sell("Gold"))

    def test_a_spansh_answer_competes_with_what_was_seen(self):
        self.book.record_market("A", "S", self.market(gold=dict(buy=9500, stock=10, sell=9000, demand=5)))
        self.book.set_lookups({"Gold": W.Lookup((quote(9200),), (quote(9900),), "Sol", "2026-10-13T13:00:00Z")})
        self.assertEqual(self.book.best_buy("Gold").source, W.SPANSH)
        self.assertEqual(self.book.best_sell("Gold").price, 9900)

    def test_every_spansh_station_competes_not_only_the_first(self):
        self.book.set_lookups({"Gold": W.Lookup((quote(9300, "First"), quote(9100, "Second")), (quote(9500, "A"), quote(9800, "B")), "Sol",
                                                "2026-10-13T13:00:00Z")})
        self.assertEqual(self.book.best_buy("Gold").station, "Second")
        self.assertEqual(self.book.best_sell("Gold").station, "B")
        self.assertEqual(len(self.book.lookup("Gold").buys), 2)

    def test_a_lookup_for_a_commodity_not_watched_is_ignored(self):
        self.book.set_lookups({"Silver": W.Lookup((quote(5),), (), "Sol", "2026-10-13T13:00:00Z")})
        self.assertIsNone(self.book.best_buy("Silver"))

    def test_removing_forgets_prices_and_lookups(self):
        self.book.record_market("A", "S", self.market(gold=dict(buy=9500, stock=10)))
        self.book.set_lookups({"Gold": W.Lookup((quote(9200),), (), "Sol", "2026-10-13T13:00:00Z")})
        self.assertTrue(self.book.remove("Gold"))
        self.assertEqual(self.book.sightings("Gold"), [])
        self.assertIsNone(self.book.lookup("Gold"))
        self.assertFalse(self.book.remove("Gold"))

    def test_a_market_from_market_json_is_read_through(self):
        raw = {"Items": [{"Name": "$gold_name;", "Name_Localised": "Gold", "BuyPrice": 9000, "SellPrice": 8000,
                          "Stock": 12, "Demand": 3}]}
        self.assertEqual(self.book.record_market("A", "S", parse_market(raw)), 1)
        self.assertEqual(self.book.best_buy("Gold").price, 9000)

    def test_long_names_are_cut_so_a_file_cannot_grow_without_bound(self):
        self.book.record_market("S" * 500, "Y" * 500, self.market(gold=dict(buy=9000, stock=1)))
        seen = self.book.sightings("Gold")[0]
        self.assertEqual((len(seen.station), len(seen.system)), (W.MAX_NAME, W.MAX_NAME))

    def test_listeners_hear_of_a_kept_price_and_a_failing_one_stops_nothing(self):
        heard = []
        self.book.add_listener(lambda: 1 / 0)
        self.book.add_listener(lambda: heard.append(1))
        self.book.record_market("A", "S", self.market(gold=dict(buy=9500, stock=10)))
        self.assertEqual(heard, [1])


class SavingTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.tmp.cleanup()

    def test_a_list_and_its_prices_survive_a_restart(self):
        book = make(self.tmp.name)
        book.add("Gold")
        book.record_market("A", "S", {"gold": item("Gold", buy=9000, stock=5)})
        again = make(self.tmp.name)
        self.assertEqual(again.watched(), ["Gold"])
        self.assertEqual(again.best_buy("Gold").price, 9000)

    def test_spansh_answers_are_not_saved(self):
        book = make(self.tmp.name)
        book.add("Gold")
        book.set_lookups({"Gold": W.Lookup((quote(9000),), (), "Sol", "2026-10-13T13:00:00Z")})
        self.assertIsNone(make(self.tmp.name).best_buy("Gold"))

    def test_commanders_do_not_see_each_others_lists(self):
        make(self.tmp.name, "Bocheaux").add("Gold")
        other = make(self.tmp.name, "Someone Else")
        self.assertEqual(other.watched(), [])
        other.add("Silver")
        self.assertEqual(make(self.tmp.name, "BOCHEAUX").watched(), ["Gold"])

    def test_no_commander_name_is_in_a_file_name(self):
        make(self.tmp.name, "Bocheaux").add("Gold")
        self.assertEqual(os.listdir(self.tmp.name), [W.STATE_FILENAME])

    def test_a_damaged_file_gives_an_empty_list(self):
        with open(os.path.join(self.tmp.name, W.STATE_FILENAME), "w", encoding="utf-8") as handle:
            handle.write("{not json")
        self.assertEqual(make(self.tmp.name).watched(), [])

    def test_damaged_entries_are_dropped_and_the_rest_kept(self):
        book = make(self.tmp.name)
        book.add("Gold")
        path = os.path.join(self.tmp.name, W.STATE_FILENAME)
        with open(path, encoding="utf-8") as handle:
            raw = json.load(handle)
        payload = raw["commanders"]["bocheaux"]["data"]
        payload["watched"] += [5, "nonsense", "Gold"]
        payload["sightings"] += ["junk", {"commodity": "Gold"}, {"commodity": "Silver", "station": "A", "system": "B"}]
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(raw, handle)
        again = make(self.tmp.name)
        self.assertEqual(again.watched(), ["Gold"])
        self.assertEqual(again.sightings("Gold"), [])    # the damaged one was dropped
        self.assertEqual(again.sightings("Silver"), [])  # and Silver is not watched


class AgeTests(unittest.TestCase):
    def test_ages(self):
        now = "2026-10-13T12:00:00Z"
        self.assertEqual(W.age("2026-10-13T11:59:30Z", now), "just now")
        self.assertEqual(W.age("2026-10-13T11:55:00Z", now), "5 min")
        self.assertEqual(W.age("2026-10-13T09:00:00Z", now), "3 h")
        self.assertEqual(W.age("2026-10-11T12:00:00Z", now), "2 d")
        self.assertEqual(W.age("", now), "")
        self.assertEqual(W.age("garbage", now), "")

    def test_clip(self):
        self.assertEqual(W.clip("a  b\nc", 10), "a b c")
        self.assertEqual(len(W.clip("x" * 100, 10)), 10)


if __name__ == "__main__":
    unittest.main()
