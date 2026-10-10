"""
Unit tests for Trade mode's stock book (plugin/trade_stock.py): cargo bought but not yet sold, kept across
logins. No EDMC runtime needed.

Run with: python -m unittest discover -s tests
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import time
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from plugin import trade_stock as stock  # noqa: E402
from plugin.trade_blocks import Columns, Heading, Item, Note, Pair  # noqa: E402


def buy(name: str, count: int, total: int, stamp: str = "2026-10-09T10:00:00Z", raw: str = "") -> dict:
    return {"event": "MarketBuy", "Type": raw or name.lower().replace(" ", ""), "Type_Localised": name,
            "Count": count, "TotalCost": total, "timestamp": stamp}


def sell(name: str, count: int, total: int, stamp: str = "2026-10-09T11:00:00Z", raw: str = "") -> dict:
    return {"event": "MarketSell", "Type": raw or name.lower().replace(" ", ""), "Type_Localised": name,
            "Count": count, "TotalSale": total, "AvgPricePaid": 1, "timestamp": stamp}


class StockBookTests(unittest.TestCase):
    def test_a_purchase_adds_stock_at_cost(self) -> None:
        book = stock.StockBook()
        book.feed(buy("Superconductors", 100, 565_500), "Bocheaux")
        (holding,) = book.holdings("Bocheaux")
        self.assertEqual((holding.tonnes, holding.cost, holding.average), (100, 565_500, 5_655))

    def test_a_sale_removes_stock_at_average_cost(self) -> None:
        book = stock.StockBook()
        book.feed(buy("Gold", 10, 90_000, "2026-10-09T10:00:00Z"), "B")
        book.feed(buy("Gold", 10, 110_000, "2026-10-09T10:05:00Z"), "B")      # 20 t for 200,000: average 10,000
        book.feed(sell("Gold", 5, 70_000, "2026-10-09T10:10:00Z"), "B")
        (holding,) = book.holdings("B")
        self.assertEqual((holding.tonnes, holding.cost), (15, 150_000))

    def test_selling_everything_clears_the_line_and_overselling_never_goes_negative(self) -> None:
        book = stock.StockBook()
        book.feed(buy("Gold", 10, 90_000), "B")
        book.feed(sell("Gold", 999, 1, "2026-10-09T11:00:00Z"), "B")
        self.assertEqual(book.holdings("B"), [])

    def test_a_sale_of_cargo_the_book_never_saw_is_ignored(self) -> None:
        book = stock.StockBook()
        book.feed(buy("Tea", 5, 5_000), "B")
        book.feed(sell("Gold", 10, 100_000, "2026-10-09T11:00:00Z"), "B")
        self.assertEqual([h.name for h in book.holdings("B")], ["Tea"])

    def test_commanders_are_kept_apart_and_matched_ignoring_case(self) -> None:
        book = stock.StockBook()
        book.feed(buy("Gold", 10, 90_000), "BOCHEAUX")
        self.assertEqual(len(book.holdings("Bocheaux")), 1)
        self.assertEqual(book.holdings("Mactavious"), [])

    def test_largest_spend_is_listed_first(self) -> None:
        book = stock.StockBook()
        book.feed(buy("Tea", 5, 5_000, "2026-10-09T10:00:00Z"), "B")
        book.feed(buy("Gold", 5, 50_000, "2026-10-09T10:01:00Z"), "B")
        self.assertEqual([h.name for h in book.holdings("B")], ["Gold", "Tea"])

    def test_other_events_zero_counts_and_unknown_commanders_change_nothing(self) -> None:
        book = stock.StockBook()
        self.assertFalse(book.feed({"event": "Docked"}, "B"))
        self.assertFalse(book.feed(buy("Gold", 0, 0), "B"))
        self.assertFalse(book.feed(buy("Gold", 5, 5), ""))
        self.assertEqual(book.books, {})


class ApplyOnceTests(unittest.TestCase):
    def test_two_sales_in_the_same_second_are_both_counted(self) -> None:
        book = stock.StockBook()
        book.feed(buy("Gold", 10, 100_000, "2026-10-09T10:00:00Z"), "B")
        book.feed(buy("Tea", 10, 10_000, "2026-10-09T10:00:00Z"), "B")
        book.feed(sell("Gold", 4, 1, "2026-10-09T11:00:00Z"), "B")
        book.feed(sell("Tea", 4, 1, "2026-10-09T11:00:00Z"), "B")
        self.assertEqual({h.name: h.tonnes for h in book.holdings("B")}, {"Gold": 6, "Tea": 6})

    def test_the_same_event_replayed_is_not_counted_twice(self) -> None:
        book = stock.StockBook()
        event = buy("Gold", 10, 100_000)
        self.assertTrue(book.feed(event, "B"))
        self.assertFalse(book.feed(dict(event), "B"))   # same second, same content
        self.assertEqual(book.holdings("B")[0].tonnes, 10)

    def test_an_older_event_than_the_last_seen_is_skipped(self) -> None:
        book = stock.StockBook()
        book.feed(buy("Gold", 10, 100_000, "2026-10-09T12:00:00Z"), "B")
        self.assertFalse(book.feed(buy("Gold", 99, 1, "2026-10-09T09:00:00Z"), "B"))
        self.assertEqual(book.holdings("B")[0].tonnes, 10)

    def test_clearing_keeps_the_position_so_a_replay_does_not_bring_it_back(self) -> None:
        book = stock.StockBook()
        event = buy("Gold", 10, 100_000)
        book.feed(event, "B")
        book.clear("B")
        self.assertEqual(book.holdings("B"), [])
        self.assertFalse(book.feed(dict(event), "B"))
        self.assertEqual(book.holdings("B"), [])
        self.assertTrue(book.feed(buy("Gold", 3, 30, "2026-10-09T13:00:00Z"), "B"))


class StockLinesTests(unittest.TestCase):
    def test_nothing_unsold_means_no_lines(self) -> None:
        self.assertEqual(stock.stock_lines([], {}), [])

    def test_rows_say_how_much_is_in_the_hold_and_how_much_is_not(self) -> None:
        holding = stock.Holding("superconductors", "Superconductors", 6_325, 35_767_875)
        blocks = stock.stock_blocks([holding], {"superconductors": 1_265})
        self.assertEqual(blocks[0], Heading("Stock bought, not yet sold"))
        self.assertEqual(blocks[1], Pair("Total", "6,325 t, 35,767,875 cr", bold=True))
        self.assertEqual(blocks[2], Columns(("Held", "Avg cost")))
        self.assertEqual(blocks[3], Item("Superconductors", ("6,325 t", "5,655"),
                                         detail="1,265 t in ship hold, 5,060 t not in ship hold"))
        self.assertIn("usually moved to your carrier", blocks[-1].text)

    def test_all_aboard_or_all_elsewhere(self) -> None:
        holding = stock.Holding("gold", "Gold", 10, 100)
        aboard = stock.stock_blocks([holding], {"gold": 50})
        self.assertEqual(aboard[-1].detail, "10 t in ship hold")   # nothing is away, so no explanation note
        away = stock.stock_blocks([holding], {})
        self.assertEqual(away[-2].detail, "10 t not in ship hold")
        self.assertIn("Not in ship hold", away[-1].text)

    def test_the_list_is_capped_and_names_can_be_replaced(self) -> None:
        many = [stock.Holding(f"c{i}", f"C{i}", 1, 100 - i) for i in range(6)]
        blocks = stock.stock_blocks(many, {}, name_of=lambda h: h.name.lower())
        items = [b for b in blocks if isinstance(b, Item)]
        self.assertEqual(len(items), stock.SHOWN)
        self.assertEqual(items[0].title, "c0")
        self.assertEqual(blocks[-2], Note("+2 more"))   # the last note explains "not in ship hold"



class BackfillAndSaveTests(unittest.TestCase):
    def _journal(self, folder: str, name: str, lines: list, age_days: float = 0.0) -> str:
        path = os.path.join(folder, name)
        with open(path, "w", encoding="utf-8") as handle:
            handle.writelines(json.dumps(line) + "\n" for line in lines)
        moment = time.time() - age_days * 86400
        os.utime(path, (moment, moment))
        return path

    def test_trades_made_while_edmc_was_closed_are_caught_up(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            self._journal(folder, "Journal.2026-10-09T100000.01.log", [
                {"event": "Commander", "Name": "BOCHEAUX"},
                buy("Superconductors", 6_325, 35_767_875), sell("Superconductors", 1_265, 9, "2026-10-09T12:00:00Z")])
            book = stock.StockBook()
            self.assertTrue(stock.backfill(book, folder, now=time.time()))
        (holding,) = book.holdings("Bocheaux")
        self.assertEqual(holding.tonnes, 5_060)

    def test_a_second_backfill_adds_nothing(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            self._journal(folder, "Journal.2026-10-09T100000.01.log", [
                {"event": "LoadGame", "Commander": "BOCHEAUX"}, buy("Gold", 10, 100)])
            book = stock.StockBook()
            stock.backfill(book, folder, now=time.time())
            self.assertFalse(stock.backfill(book, folder, now=time.time()))
        self.assertEqual(book.holdings("Bocheaux")[0].tonnes, 10)

    def test_a_first_run_ignores_trades_older_than_the_window(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            self._journal(folder, "Journal.2026-01-01T100000.01.log", [
                {"event": "LoadGame", "Commander": "BOCHEAUX"}, buy("Gold", 10, 100, "2026-01-01T10:00:00Z")],
                age_days=100)
            book = stock.StockBook()
            self.assertFalse(stock.backfill(book, folder, now=time.time()))
        self.assertEqual(book.holdings("Bocheaux"), [])

    def test_newest_files_are_chosen_by_modified_time_not_by_name(self) -> None:
        # The game has used two naming styles that don't sort chronologically together.
        with tempfile.TemporaryDirectory() as folder:
            self._journal(folder, "Journal.260228162446.01.log", [
                {"event": "LoadGame", "Commander": "B"}, buy("Old", 1, 1, "2026-02-28T16:24:46Z")], age_days=200)
            self._journal(folder, "Journal.2026-10-09T100000.01.log", [
                {"event": "LoadGame", "Commander": "B"}, buy("New", 1, 1, "2026-10-09T10:00:00Z")])
            from plugin import trade_carrier
            paths = trade_carrier.journal_files(folder, 1)
        self.assertEqual([os.path.basename(p) for p in paths], ["Journal.2026-10-09T100000.01.log"])

    def test_save_and_load_round_trip(self) -> None:
        book = stock.StockBook()
        book.feed(buy("Gold", 10, 100), "BOCHEAUX")
        with tempfile.TemporaryDirectory() as folder:
            self.assertEqual(stock.load_all(folder), {})
            stock.save_all(folder, book.books)
            loaded = stock.StockBook(stock.load_all(folder))
        self.assertEqual(loaded.holdings("bocheaux")[0].tonnes, 10)
        self.assertFalse(loaded.feed(buy("Gold", 10, 100), "BOCHEAUX"))   # remembers what it has applied


if __name__ == "__main__":
    unittest.main()
