"""
The Credits Ledger's data (income_ledger.py): which journal events count and as what, not counting an event twice, the rebuild
from the journals, and the rows the window shows. Event shapes follow the journal's documented fields. Pure data and temporary
folders only, so it behaves the same on Windows and Linux.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import types
import unittest
from datetime import date

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
if "config" not in sys.modules:
    _stub = types.ModuleType("config")
    _stub.appname = "EDMarketConnector"
    _stub.config = types.SimpleNamespace(get_str=lambda key: "", default_journal_dir="")
    sys.modules["config"] = _stub

from plugin import income_catchup, income_ledger as L  # noqa: E402


def sell(at, total=1000, paid=400, count=2, market=1):
    return {"timestamp": at, "event": "MarketSell", "MarketID": market, "Type": "gold", "Count": count, "TotalSale": total,
            "AvgPricePaid": paid}


def organic(at, values):
    return {"timestamp": at, "event": "SellOrganicData", "MarketID": 9,
            "BioData": [{"Species": "x", "Value": v, "Bonus": b} for v, b in values]}


class AmountTests(unittest.TestCase):
    def test_a_sale_is_counted_as_trade_profit(self):
        self.assertEqual(L.amount_of(sell("2026-10-15T10:00:00Z")), (L.TRADE, 1000 - 400 * 2))

    def test_a_sale_below_cost_is_a_negative_profit(self):
        self.assertEqual(L.amount_of(sell("2026-10-15T10:00:00Z", total=100, paid=400, count=1)), (L.TRADE, -300))

    def test_exploration_uses_the_total_earnings_else_base_plus_bonus(self):
        self.assertEqual(L.amount_of({"event": "MultiSellExplorationData", "TotalEarnings": 5000}), (L.EXPLORATION, 5000))
        self.assertEqual(L.amount_of({"event": "SellExplorationData", "BaseValue": 300, "Bonus": 20}), (L.EXPLORATION, 320))

    def test_exobiology_adds_each_species_and_its_bonus(self):
        self.assertEqual(L.amount_of(organic("2026-10-15T10:00:00Z", [(100, 10), (50, 0)])), (L.EXOBIOLOGY, 160))

    def test_missions_and_vouchers(self):
        self.assertEqual(L.amount_of({"event": "MissionCompleted", "Reward": 7000, "MissionID": 5}), (L.MISSIONS, 7000))
        self.assertEqual(L.amount_of({"event": "RedeemVoucher", "Amount": 900, "Type": "bounty"}), (L.VOUCHERS, 900))

    def test_nothing_for_other_events_or_empty_payouts(self):
        for junk in ({"event": "Cargo"}, {"event": "MissionCompleted", "Reward": 0}, {"event": "SellOrganicData", "BioData": []},
                     {"event": "MarketSell", "Count": 0, "TotalSale": 5}, {"event": "RedeemVoucher", "Amount": "lots"}):
            self.assertIsNone(L.amount_of(junk))


class FoldTests(unittest.TestCase):
    def test_activities_stay_apart_on_one_day(self):
        record = L._empty()
        L.fold(record, sell("2026-10-15T10:00:00Z"))
        L.fold(record, organic("2026-10-15T11:00:00Z", [(1000, 0)]))
        self.assertEqual(record["by_day"]["2026-10-15"], {L.TRADE: 200, L.EXOBIOLOGY: 1000})

    def test_the_same_event_twice_counts_once(self):
        record = L._empty()
        entry = sell("2026-10-15T10:00:00Z")
        self.assertTrue(L.fold(record, entry))
        self.assertFalse(L.fold(record, dict(entry)))
        self.assertEqual(L.totals(record)[L.TRADE], 200)

    def test_two_different_sales_in_one_second_both_count(self):
        record = L._empty()
        L.fold(record, sell("2026-10-15T10:00:00Z", count=2))
        L.fold(record, {**sell("2026-10-15T10:00:00Z", count=3, total=900, paid=100), "Type": "silver"})
        self.assertEqual(L.totals(record)[L.TRADE], 200 + 600)

    def test_an_older_event_than_the_newest_counted_is_skipped(self):
        record = L._empty()
        L.fold(record, sell("2026-10-15T10:00:00Z"))
        self.assertFalse(L.fold(record, sell("2026-10-14T10:00:00Z")))


class BookTests(unittest.TestCase):
    def test_rebuild_is_not_doubled_by_a_live_event_and_marks_it_done(self):
        book = L.IncomeBook()
        book.apply("Mac", sell("2026-10-15T10:00:00Z"))
        self.assertFalse(book.backfilled("Mac"))
        book.rebuild("Mac", [sell("2026-10-10T10:00:00Z"), sell("2026-10-15T10:00:00Z")])
        self.assertTrue(book.backfilled("Mac"))
        record = book.record("Mac")
        self.assertEqual(record["by_day"]["2026-10-10"][L.TRADE], 200)
        self.assertEqual(record["by_day"]["2026-10-15"][L.TRADE], 200)

    def test_live_events_after_a_rebuild_are_added_and_old_ones_are_not(self):
        book = L.IncomeBook()
        book.rebuild("Mac", [sell("2026-10-15T10:00:00Z")])
        self.assertFalse(book.apply("Mac", sell("2026-10-15T10:00:00Z")))
        self.assertTrue(book.apply("Mac", sell("2026-10-15T12:00:00Z")))
        self.assertEqual(L.totals(book.record("Mac"))[L.TRADE], 400)

    def test_commanders_are_kept_apart(self):
        book = L.IncomeBook()
        book.apply("Mac", sell("2026-10-15T10:00:00Z"))
        self.assertEqual(L.totals(book.record("Other")), {a: 0 for a in L.ACTIVITIES})
        self.assertEqual(book.record("Other")["by_day"], {})

    def test_it_saves_and_loads(self):
        with tempfile.TemporaryDirectory() as folder:
            book = L.IncomeBook()
            book.load(folder)
            book.apply("Mac", sell("2026-10-15T10:00:00Z"))
            book.commit()
            again = L.IncomeBook()
            again.load(folder)
            self.assertEqual(L.totals(again.record("Mac"))[L.TRADE], 200)
            with open(os.path.join(folder, L.STATE_FILENAME), encoding="utf-8") as handle:
                self.assertEqual(list(json.load(handle)["commanders"]), ["mac"])


class ViewTests(unittest.TestCase):
    def test_period_totals(self):
        record = L._empty()
        for stamp in ("2026-10-15T10:00:00Z", "2026-10-12T10:00:00Z", "2026-09-20T10:00:00Z", "2026-08-01T10:00:00Z"):
            record["at"] = ""          # these arrive out of order, as separate journals can
            L.fold(record, sell(stamp, total=1000, paid=0, count=1))
        starts = dict(L.period_starts(date(2026, 10, 15)))
        self.assertEqual(L.totals(record, starts["Today (UTC)"])[L.TRADE], 1000)
        self.assertEqual(L.totals(record, starts["Last 7 days"])[L.TRADE], 2000)
        self.assertEqual(L.totals(record, starts["Last 30 days"])[L.TRADE], 3000)
        self.assertEqual(L.totals(record, None)[L.TRADE], 4000)

    def test_day_rows_are_newest_first_with_a_total(self):
        record = L._empty()
        L.fold(record, sell("2026-10-14T10:00:00Z", total=500, paid=0, count=1))
        L.fold(record, organic("2026-10-15T10:00:00Z", [(700, 0)]))
        rows = L.day_rows(record)
        self.assertEqual([r[0] for r in rows], ["2026-10-15", "2026-10-14"])
        self.assertEqual(rows[0][-1], "700")
        self.assertEqual(L.first_day(record), "2026-10-14")


class CatchupTests(unittest.TestCase):
    def test_only_the_named_commanders_events_are_read(self):
        with tempfile.TemporaryDirectory() as folder:
            lines = [{"timestamp": "2026-10-15T09:00:00Z", "event": "Commander", "Name": "Mac"}, sell("2026-10-15T10:00:00Z"),
                     {"timestamp": "2026-10-15T11:00:00Z", "event": "Commander", "Name": "Other"}, sell("2026-10-15T12:00:00Z"),
                     {"timestamp": "2026-10-15T13:00:00Z", "event": "Cargo"}]
            with open(os.path.join(folder, "Journal.2026-10-15T090000.01.log"), "w", encoding="utf-8", newline="\n") as handle:
                handle.write("\n".join(json.dumps(line) for line in lines) + "\n")
            found = income_catchup.read_all_events("MAC", folder)
            self.assertEqual([e["timestamp"] for e in found], ["2026-10-15T10:00:00Z"])


if __name__ == "__main__":
    unittest.main()
