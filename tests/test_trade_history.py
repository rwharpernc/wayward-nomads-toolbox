"""
Unit tests for Trade History: the ledger's log, the saved-session records and store (plugin/trade_history.py) and the
numbers shown from a record (plugin/trade_stats.py). No EDMC runtime or display needed.

Run with: python -m unittest discover -s tests
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from plugin import trade_history as history  # noqa: E402
from plugin import trade_ledger as ledger_mod  # noqa: E402
from plugin import trade_stats as stats  # noqa: E402

A = ("Sol", "Daedalus")
B = ("Alpha Centauri", "Hutton Orbital")


def buy(name: str, count: int, price: int, stamp: str) -> dict:
    return {"event": "MarketBuy", "Type": name.lower(), "Type_Localised": name, "Count": count, "BuyPrice": price,
            "TotalCost": count * price, "timestamp": stamp}


def sell(name: str, count: int, price: int, paid: int, stamp: str) -> dict:
    return {"event": "MarketSell", "Type": name.lower(), "Type_Localised": name, "Count": count, "SellPrice": price,
            "TotalSale": count * price, "AvgPricePaid": paid, "timestamp": stamp}


def session() -> dict:
    """Buy Gold and Tea at A, refuel; sell them at B, repair; back to A for more Gold. Two jumps."""
    ledger = ledger_mod.new_ledger("Bocheaux", "Journal.1.log", started="2026-10-09T10:00:00Z", credits=5_000_000)
    ev = ledger_mod.apply_trade_event
    ev(ledger, buy("Gold", 100, 10_000, "2026-10-09T10:05:00Z"), A)
    ev(ledger, buy("Tea", 50, 1_000, "2026-10-09T10:06:00Z"), A)
    ev(ledger, {"event": "RefuelAll", "Cost": 200, "timestamp": "2026-10-09T10:07:00Z"}, A)
    ledger_mod.note_jump(ledger, {"event": "FSDJump", "JumpDist": 4.38})
    ev(ledger, sell("Gold", 100, 13_000, 10_000, "2026-10-09T10:30:00Z"), B)
    ev(ledger, sell("Tea", 20, 1_500, 1_000, "2026-10-09T10:31:00Z"), B)
    ev(ledger, {"event": "RepairAll", "Cost": 1_000, "timestamp": "2026-10-09T10:32:00Z"}, B)
    ledger_mod.note_jump(ledger, {"event": "FSDJump", "JumpDist": 4.38})
    ev(ledger, buy("Gold", 50, 10_400, "2026-10-09T11:00:00Z"), A)
    return ledger


def record(**extra) -> dict:
    return history.build_record(session(), "Bocheaux", ship="Type-9 Heavy", pad="large", credits_end=5_307_800,
                                saved_at="2026-10-09T11:05:00Z", **extra)


class LedgerLogTests(unittest.TestCase):
    def test_each_trade_and_cost_is_logged_with_where_it_happened(self) -> None:
        log = session()["log"]
        self.assertEqual([item["e"] for item in log], ["buy", "buy", "cost", "sell", "sell", "cost", "buy"])
        self.assertEqual((log[0]["c"], log[0]["n"], log[0]["u"], log[0]["tot"], log[0]["sys"], log[0]["stn"]),
                         ("Gold", 100, 10_000, 1_000_000, "Sol", "Daedalus"))
        self.assertEqual((log[3]["paid"], log[3]["stn"]), (10_000, "Hutton Orbital"))
        self.assertEqual((log[2]["c"], log[2]["tot"]), ("fuel", 200))

    def test_the_log_is_bounded(self) -> None:
        ledger = ledger_mod.new_ledger("B", "J")
        for index in range(ledger_mod.LOG_LIMIT + 25):
            ledger_mod.apply_trade_event(ledger, buy("Gold", 1, 10, f"2026-10-09T10:{index // 60 % 60:02d}:{index % 60:02d}Z"), A)
        self.assertEqual(len(ledger["log"]), ledger_mod.LOG_LIMIT)
        self.assertEqual(ledger["rows"]["Gold"]["bought"], ledger_mod.LOG_LIMIT + 25)   # the totals are never trimmed

    def test_black_market_sales_are_marked(self) -> None:
        ledger = ledger_mod.new_ledger("B", "J")
        entry = sell("Gold", 1, 10, 0, "2026-10-09T10:00:00Z")
        entry["BlackMarket"] = True
        ledger_mod.apply_trade_event(ledger, entry, A)
        self.assertTrue(ledger["log"][0]["bm"])

    def test_jumps_and_distance_are_counted(self) -> None:
        info = ledger_mod.meta(session())
        self.assertEqual((info["jumps"], info["jump_ly"]), (2, 8.76))
        self.assertFalse(ledger_mod.note_jump(session(), {"event": "Docked"}))

    def test_start_is_recorded_once(self) -> None:
        ledger = ledger_mod.new_ledger("B", "J")
        ledger_mod.note_start(ledger, "2026-10-09T10:00:00Z", 100)
        ledger_mod.note_start(ledger, "2026-10-09T12:00:00Z", 999)
        self.assertEqual(ledger_mod.meta(ledger)["started"], "2026-10-09T10:00:00Z")
        self.assertEqual(ledger_mod.meta(ledger)["credits_start"], 100)

    def test_an_older_ledger_without_a_log_still_works(self) -> None:
        old = {"cmdr": "B", "journal_file": "J", "first_trade": None, "last_trade": None, "rows": {}, "expenses": {}}
        self.assertTrue(ledger_mod.apply_trade_event(old, buy("Gold", 1, 10, "2026-10-09T10:00:00Z"), A))
        self.assertEqual(len(old["log"]), 1)
        self.assertEqual(ledger_mod.meta(old)["jumps"], 0)

    def test_routes_and_searches_are_remembered_a_few_at_a_time(self) -> None:
        ledger = ledger_mod.new_ledger("B", "J")
        for index in range(ledger_mod.ROUTES_KEPT + 3):
            ledger_mod.add_route(ledger, {"n": index})
        for index in range(ledger_mod.SEARCHES_KEPT + 3):
            ledger_mod.add_search(ledger, {"n": index})
        self.assertEqual([r["n"] for r in ledger["routes"]], list(range(3, 3 + ledger_mod.ROUTES_KEPT)))
        self.assertEqual(len(ledger["searches"]), ledger_mod.SEARCHES_KEPT)


class OverviewTests(unittest.TestCase):
    def test_the_headline_numbers(self) -> None:
        o = stats.overview(record())
        self.assertEqual(o.bought_t, 200)                         # 100 Gold + 50 Tea + 50 Gold
        self.assertEqual(o.sold_t, 120)
        self.assertEqual(o.spent, 1_000_000 + 50_000 + 520_000)
        self.assertEqual(o.revenue, 1_300_000 + 30_000)
        self.assertEqual(o.trade_profit, 300_000 + 10_000)       # sales minus what those tonnes cost
        self.assertEqual(o.expenses, 1_200)
        self.assertEqual(o.net, 308_800)

    def test_time_and_rates(self) -> None:
        o = stats.overview(record())
        self.assertAlmostEqual(o.trading_hours, 55 / 60, places=4)   # first trade 10:05 to last trade 11:00
        self.assertAlmostEqual(o.net_per_hour, 308_800 / o.trading_hours, places=2)
        self.assertEqual((o.started, o.ended), ("2026-10-09T10:00:00Z", "2026-10-09T11:00:00Z"))
        self.assertAlmostEqual(o.session_hours, 1.0, places=3)

    def test_the_rate_waits_for_enough_trading_time(self) -> None:
        ledger = ledger_mod.new_ledger("B", "J", started="2026-10-09T10:00:00Z")
        ledger_mod.apply_trade_event(ledger, sell("Gold", 1, 100, 0, "2026-10-09T10:00:00Z"), A)
        ledger_mod.apply_trade_event(ledger, sell("Gold", 1, 100, 0, "2026-10-09T10:01:00Z"), A)
        self.assertIsNone(stats.overview(history.build_record(ledger, "B")).net_per_hour)

    def test_balance_change_and_jump_metrics(self) -> None:
        o = stats.overview(record())
        self.assertEqual((o.credits_start, o.credits_end, o.balance_change), (5_000_000, 5_307_800, 307_800))
        self.assertEqual((o.jumps, o.jump_ly), (2, 8.76))
        self.assertAlmostEqual(o.profit_per_jump, 308_800 / 2)
        self.assertAlmostEqual(o.profit_per_ly, 308_800 / 8.76)

    def test_per_tonne_and_margin(self) -> None:
        o = stats.overview(record())
        self.assertAlmostEqual(o.profit_per_tonne, 310_000 / 120)
        self.assertAlmostEqual(o.margin_pct, 310_000 / (1_000_000 + 20_000) * 100)

    def test_counts_of_trades_and_places(self) -> None:
        o = stats.overview(record())
        self.assertEqual((o.trades, o.stations, o.visits), (5, 2, 3))

    def test_an_empty_record_does_not_divide_by_zero(self) -> None:
        o = stats.overview({})
        self.assertEqual((o.net, o.trades, o.visits), (0, 0, 0))
        self.assertIsNone(o.profit_per_tonne)
        self.assertIsNone(o.margin_pct)
        self.assertIsNone(o.balance_change)


class BreakdownTests(unittest.TestCase):
    def test_commodities_best_profit_first_with_averages(self) -> None:
        rows = stats.commodity_stats(record())
        self.assertEqual([r.name for r in rows], ["Gold", "Tea"])
        gold = rows[0]
        self.assertEqual((gold.bought_t, gold.sold_t, gold.left_t, gold.profit), (150, 100, 50, 300_000))
        self.assertEqual((gold.avg_buy, gold.avg_sell, gold.per_tonne), (round(1_520_000 / 150), 13_000, 3_000))
        self.assertAlmostEqual(gold.margin_pct, 30.0)
        tea = rows[1]
        self.assertEqual((tea.sold_t, tea.left_t, tea.profit), (20, 30, 10_000))

    def test_costs_in_the_usual_order(self) -> None:
        self.assertEqual(stats.cost_breakdown(record()), [("Fuel", 200), ("Repairs", 1_000)])

    def test_the_route_is_the_visits_in_order(self) -> None:
        route = stats.visits(record())
        self.assertEqual([(v.station, v.bought_t, v.sold_t) for v in route],
                         [("Daedalus", 150, 0), ("Hutton Orbital", 0, 120), ("Daedalus", 50, 0)])
        self.assertEqual((route[0].spent, route[0].costs, route[0].net), (1_050_000, 200, -200))
        self.assertEqual((route[1].revenue, route[1].profit, route[1].costs, route[1].net), (1_330_000, 310_000, 1_000, 309_000))

    def test_stations_added_up_best_net_first(self) -> None:
        by_station = stats.station_stats(record())
        self.assertEqual([s.station for s in by_station], ["Hutton Orbital", "Daedalus"])
        daedalus = by_station[1]
        self.assertEqual((daedalus.visits, daedalus.bought_t, daedalus.spent, daedalus.costs), (2, 200, 1_570_000, 200))

    def test_route_text_reads_naturally(self) -> None:
        route = stats.visits(record())
        self.assertEqual(stats.route_text(route[0]), "bought 100 t Gold, 50 t Tea")
        self.assertEqual(stats.route_text(route[1]), "sold 100 t Gold, 20 t Tea")

    def test_a_log_shorter_than_the_totals_does_not_change_the_totals(self) -> None:
        trimmed = record()
        trimmed["log"] = trimmed["log"][4:]
        self.assertEqual(stats.overview(trimmed).net, 308_800)


class LogAndTextTests(unittest.TestCase):
    def test_log_rows(self) -> None:
        rows = stats.log_rows(record())
        self.assertEqual(len(rows), 7)
        self.assertEqual(rows[0], ("2026-10-09 10:05:00", "Buy", "Gold", "100", "10,000", "-1,000,000", "", "Daedalus", "Sol"))
        self.assertEqual(rows[3][1:7], ("Sell", "Gold", "100", "13,000", "1,300,000", "+300,000"))
        self.assertEqual(rows[2][1:3], ("Cost", "Fuel"))

    def test_csv_has_a_header_and_one_line_per_entry(self) -> None:
        lines = stats.csv_text(record()).strip().splitlines()
        self.assertEqual(lines[0], ",".join(stats.LOG_HEADERS))
        self.assertEqual(len(lines), 1 + 7)

    def test_summary_text_has_the_key_figures(self) -> None:
        text = "\n".join(stats.summary_text(record()))
        for expected in ("Net profit: +308,800 cr", "Trade profit: +310,000 cr", "Running costs: -1,200 cr",
                         "Jumps: 2 (8.8 ly)", "Balance: 5,000,000 -> 5,307,800 cr (+307,800)", "Costs: Fuel 200, Repairs 1,000",
                         "Gold: bought 150 t, sold 100 t, profit +300,000 cr", "1. Daedalus (Sol)", "2. Hutton Orbital (Alpha Centauri)"):
            self.assertIn(expected, text)

    def test_the_picker_label(self) -> None:
        self.assertEqual(stats.label(record()), "2026-10-09 10:00 · Bocheaux · net +308,800 cr · 55 m")

    def test_duration_text(self) -> None:
        self.assertEqual(stats.fmt_duration(0), "—")
        self.assertEqual(stats.fmt_duration(23 / 60), "23 m")
        self.assertEqual(stats.fmt_duration(65 / 60), "1 h 05 m")


class HistoryStoreTests(unittest.TestCase):
    def test_a_record_is_a_snapshot(self) -> None:
        ledger = session()
        saved = history.build_record(ledger, "Bocheaux")
        ledger_mod.apply_trade_event(ledger, buy("Gold", 1, 1, "2026-10-09T12:00:00Z"), A)
        self.assertEqual(len(saved["log"]), 7)
        self.assertEqual(saved["rows"]["Gold"]["bought"], 150)

    def test_saving_the_same_session_again_replaces_it(self) -> None:
        book = history.HistoryBook()
        ledger = session()
        self.assertFalse(book.save(history.build_record(ledger, "Bocheaux")))
        ledger_mod.apply_trade_event(ledger, buy("Gold", 1, 1, "2026-10-09T12:00:00Z"), A)
        self.assertTrue(book.save(history.build_record(ledger, "Bocheaux")))
        self.assertEqual(len(book.sessions), 1)
        self.assertEqual(len(book.sessions[0]["log"]), 8)

    def test_a_reset_session_is_a_different_one(self) -> None:
        book = history.HistoryBook()
        book.save(history.build_record(session(), "Bocheaux"))
        other = ledger_mod.new_ledger("Bocheaux", "Journal.1.log", started="2026-10-09T13:00:00Z")
        ledger_mod.apply_trade_event(other, buy("Gold", 1, 1, "2026-10-09T13:05:00Z"), A)
        book.save(history.build_record(other, "Bocheaux"))
        self.assertEqual(len(book.sessions), 2)

    def test_newest_first_and_per_commander(self) -> None:
        book = history.HistoryBook()
        first = session()
        later = ledger_mod.new_ledger("Mactavious", "Journal.2.log", started="2026-10-10T09:00:00Z")
        ledger_mod.apply_trade_event(later, buy("Tea", 1, 1, "2026-10-10T09:05:00Z"), A)
        book.save(history.build_record(first, "Bocheaux"))
        book.save(history.build_record(later, "Mactavious"))
        self.assertEqual([s["cmdr"] for s in book.newest_first()], ["Mactavious", "Bocheaux"])
        self.assertEqual([s["cmdr"] for s in book.newest_first("BOCHEAUX")], ["Bocheaux"])
        self.assertEqual(book.commanders(), ["Bocheaux", "Mactavious"])

    def test_delete(self) -> None:
        book = history.HistoryBook()
        saved = history.build_record(session(), "Bocheaux")
        book.save(saved)
        self.assertTrue(book.is_saved(saved["id"]))
        self.assertTrue(book.delete(saved["id"]))
        self.assertFalse(book.delete(saved["id"]))
        self.assertEqual(book.sessions, [])

    def test_nothing_to_save_is_detected(self) -> None:
        self.assertFalse(history.has_content(None))
        self.assertFalse(history.has_content(ledger_mod.new_ledger("B", "J")))
        self.assertTrue(history.has_content(session()))
        costs_only = ledger_mod.new_ledger("B", "J")
        ledger_mod.apply_trade_event(costs_only, {"event": "RefuelAll", "Cost": 5, "timestamp": "2026-10-09T10:00:00Z"})
        self.assertTrue(history.has_content(costs_only))

    def test_the_book_is_capped(self) -> None:
        book = history.HistoryBook()
        for index in range(history.MAX_SESSIONS + 3):
            book.save({"id": str(index), "cmdr": "B"})
        self.assertEqual(len(book.sessions), history.MAX_SESSIONS)
        self.assertFalse(book.is_saved("0"))

    def test_save_and_load_round_trip(self) -> None:
        book = history.HistoryBook()
        book.save(record(stock=[{"name": "Gold", "tonnes": 50, "cost": 520_000}]))
        with tempfile.TemporaryDirectory() as folder:
            self.assertEqual(history.load_all(folder), [])
            self.assertTrue(history.save_all(folder, book.sessions))
            loaded = history.load_all(folder)
        self.assertEqual(loaded, book.sessions)
        self.assertEqual(stats.overview(loaded[0]).net, 308_800)

    def test_a_damaged_file_loads_as_nothing(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            with open(os.path.join(folder, history.STATE_FILENAME), "w", encoding="utf-8") as handle:
                handle.write("{not json")
            self.assertEqual(history.load_all(folder), [])
            with open(os.path.join(folder, history.STATE_FILENAME), "w", encoding="utf-8") as handle:
                json.dump({"sessions": ["x", {"no": "id"}, {"id": "ok"}]}, handle)
            self.assertEqual(history.load_all(folder), [{"id": "ok"}])


if __name__ == "__main__":
    unittest.main()
