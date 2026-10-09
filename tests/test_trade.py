"""
Unit tests for Trade mode's pure logic (trade_ledger, trade_market, trade_spansh_client).
No EDMC runtime and no network needed.

Run with: python -m unittest discover -s tests
"""

from __future__ import annotations

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from plugin import trade_ledger as ledger_mod  # noqa: E402
from plugin import trade_market as market  # noqa: E402
from plugin import trade_spansh_client as client  # noqa: E402


def buy(name: str, count: int, total: int, stamp: str = "2026-10-09T10:00:00Z") -> dict:
    return {"event": "MarketBuy", "Type": name.lower(), "Type_Localised": name, "Count": count,
            "TotalCost": total, "timestamp": stamp}


def sell(name: str, count: int, total: int, paid: int, stamp: str = "2026-10-09T11:00:00Z") -> dict:
    return {"event": "MarketSell", "Type": name.lower(), "Type_Localised": name, "Count": count,
            "TotalSale": total, "AvgPricePaid": paid, "timestamp": stamp}


class LedgerTests(unittest.TestCase):
    def _ledger(self) -> dict:
        return ledger_mod.new_ledger("Bocheaux", "Journal.1.log")

    def test_profit_is_sale_minus_what_the_sold_tonnes_cost(self) -> None:
        ledger = self._ledger()
        ledger_mod.apply_trade_event(ledger, buy("Gold", 10, 90_000))
        ledger_mod.apply_trade_event(ledger, sell("Gold", 10, 120_000, 9_000))
        totals = ledger_mod.totals(ledger)
        self.assertEqual((totals.bought_t, totals.sold_t, totals.spent, totals.revenue), (10, 10, 90_000, 120_000))
        self.assertEqual(totals.profit, 30_000)

    def test_stolen_goods_count_the_whole_sale_as_profit(self) -> None:
        ledger = self._ledger()
        ledger_mod.apply_trade_event(ledger, sell("Gold", 4, 40_000, 0))
        self.assertEqual(ledger_mod.totals(ledger).profit, 40_000)

    def test_a_loss_is_negative(self) -> None:
        ledger = self._ledger()
        ledger_mod.apply_trade_event(ledger, sell("Tea", 5, 20_000, 5_000))
        self.assertEqual(ledger_mod.totals(ledger).profit, -5_000)

    def test_other_events_and_bad_counts_are_ignored(self) -> None:
        ledger = self._ledger()
        self.assertFalse(ledger_mod.apply_trade_event(ledger, {"event": "Docked"}))
        self.assertFalse(ledger_mod.apply_trade_event(ledger, buy("Gold", 0, 0)))
        self.assertFalse(ledger_mod.apply_trade_event(ledger, {"event": "MarketBuy", "Count": "x"}))
        self.assertEqual(ledger["rows"], {})

    def test_rate_needs_enough_time_to_mean_something(self) -> None:
        ledger = self._ledger()
        ledger_mod.apply_trade_event(ledger, sell("Gold", 1, 1_000, 0, "2026-10-09T10:00:00Z"))
        self.assertNotIn("cr/hr", ledger_mod.summary_lines(ledger)[0])
        ledger_mod.apply_trade_event(ledger, sell("Gold", 1, 1_000, 0, "2026-10-09T11:00:00Z"))
        self.assertIn("+2,000 cr (+2,000 cr/hr)", ledger_mod.summary_lines(ledger)[0])

    def test_best_sales_are_ranked_and_limited(self) -> None:
        ledger = self._ledger()
        for index in range(8):
            ledger_mod.apply_trade_event(ledger, sell(f"Item{index}", 1, 1_000 * (index + 1), 0))
        lines = ledger_mod.summary_lines(ledger)
        ranked = [line for line in lines if line.startswith("  ")]
        self.assertEqual(len(ranked), ledger_mod.TOP_ROWS_SHOWN)
        self.assertIn("Item7", ranked[0])

    def test_empty_ledger_text(self) -> None:
        self.assertIn("No trades yet", ledger_mod.summary_lines(None)[0])
        self.assertIn("No trades yet", ledger_mod.summary_lines(self._ledger())[0])

    def test_same_journal_and_commander_continues(self) -> None:
        ledger = self._ledger()
        ledger_mod.apply_trade_event(ledger, buy("Gold", 1, 10))
        same, continued = ledger_mod.sync_ledger(ledger, "Bocheaux", "Journal.1.log")
        self.assertTrue(continued)
        self.assertIn("Gold", same["rows"])

    def test_new_journal_or_commander_starts_over(self) -> None:
        ledger = self._ledger()
        ledger_mod.apply_trade_event(ledger, buy("Gold", 1, 10))
        for cmdr, journal in (("Bocheaux", "Journal.2.log"), ("Mactavious", "Journal.1.log")):
            fresh, continued = ledger_mod.sync_ledger(ledger, cmdr, journal)
            self.assertFalse(continued)
            self.assertEqual(fresh["rows"], {})

    def test_save_and_load_round_trip(self) -> None:
        ledger = self._ledger()
        ledger_mod.apply_trade_event(ledger, buy("Gold", 3, 30))
        with tempfile.TemporaryDirectory() as folder:
            self.assertIsNone(ledger_mod.load_ledger(folder))
            ledger_mod.save_ledger(folder, ledger)
            self.assertEqual(ledger_mod.load_ledger(folder), ledger)


class RunningCostTests(unittest.TestCase):
    """Event shapes copied from a real journal (2026-10-09)."""

    def _ledger(self) -> dict:
        return ledger_mod.new_ledger("Bocheaux", "Journal.1.log")

    def test_fuel_repairs_rearm_and_limpets_are_counted(self) -> None:
        ledger = self._ledger()
        for entry in (
            {"event": "RefuelAll", "Cost": 14, "Amount": 0.26972},
            {"event": "RefuelPartial", "Cost": 243, "Amount": 4.85},
            {"event": "Repair", "Items": ["$type8_cockpit_name;", "Hull"], "Cost": 1731},
            {"event": "RepairAll", "Cost": 1621},
            {"event": "BuyAmmo", "Cost": 16},
            {"event": "RestockVehicle", "Type": "testbuggy", "Cost": 5270, "Count": 1},
            {"event": "BuyDrones", "Type": "Drones", "Count": 60, "BuyPrice": 101, "TotalCost": 6060},
            {"event": "SellDrones", "Type": "Drones", "Count": 20, "SellPrice": 100, "TotalSale": 2000},
        ):
            self.assertTrue(ledger_mod.apply_trade_event(ledger, entry), entry["event"])
        self.assertEqual(ledger_mod.expenses_by_category(ledger),
                         {"fuel": 257, "repairs": 3352, "rearm": 5286, "limpets": 4060})

    def test_a_free_or_empty_cost_changes_nothing(self) -> None:
        ledger = self._ledger()
        self.assertFalse(ledger_mod.apply_trade_event(ledger, {"event": "RefuelAll", "Cost": 0}))
        self.assertFalse(ledger_mod.apply_trade_event(ledger, {"event": "RepairAll"}))
        self.assertEqual(ledger_mod.expenses_by_category(ledger), {})

    def test_net_is_trade_profit_less_costs(self) -> None:
        ledger = self._ledger()
        ledger_mod.apply_trade_event(ledger, buy("Gold", 10, 90_000))
        ledger_mod.apply_trade_event(ledger, sell("Gold", 10, 120_000, 9_000))
        ledger_mod.apply_trade_event(ledger, {"event": "RefuelAll", "Cost": 1_000})
        ledger_mod.apply_trade_event(ledger, {"event": "RepairAll", "Cost": 4_000})
        totals = ledger_mod.totals(ledger)
        self.assertEqual((totals.profit, totals.expenses, totals.net), (30_000, 5_000, 25_000))
        lines = ledger_mod.summary_lines(ledger)
        self.assertEqual(lines[0], "Net profit: +25,000 cr (+25,000 cr/hr)")  # buy and sell an hour apart
        self.assertIn("Trade profit: +30,000 cr", lines)
        self.assertIn("Fuel: -1,000 cr", lines)
        self.assertIn("Repairs: -4,000 cr", lines)

    def test_without_costs_the_summary_is_unchanged(self) -> None:
        ledger = self._ledger()
        ledger_mod.apply_trade_event(ledger, sell("Gold", 1, 1_000, 0))
        self.assertEqual(ledger_mod.summary_lines(ledger)[0], "Profit: +1,000 cr")
        self.assertNotIn("Trade profit", "\n".join(ledger_mod.summary_lines(ledger)))

    def test_costs_before_any_trade_still_show(self) -> None:
        ledger = self._ledger()
        ledger_mod.apply_trade_event(ledger, {"event": "RefuelAll", "Cost": 700})
        lines = ledger_mod.summary_lines(ledger)
        self.assertEqual(lines[0], "No trades yet this session.")
        self.assertIn("Fuel: -700 cr", lines)
        self.assertEqual(lines[-1], "Net: -700 cr")

    def test_limpets_sold_back_can_read_as_a_gain(self) -> None:
        ledger = self._ledger()
        ledger_mod.apply_trade_event(ledger, {"event": "SellDrones", "TotalSale": 2_000})
        self.assertIn("Limpets: +2,000 cr", ledger_mod.summary_lines(ledger))

    def test_the_rate_uses_the_net_figure_and_ignores_cost_times(self) -> None:
        ledger = self._ledger()
        ledger_mod.apply_trade_event(ledger, sell("Gold", 1, 3_000, 0, "2026-10-09T10:00:00Z"))
        ledger_mod.apply_trade_event(ledger, {"event": "RepairAll", "Cost": 1_000, "timestamp": "2026-10-09T09:00:00Z"})
        ledger_mod.apply_trade_event(ledger, sell("Gold", 1, 3_000, 0, "2026-10-09T11:00:00Z"))
        self.assertIn("Net profit: +5,000 cr (+5,000 cr/hr)", ledger_mod.summary_lines(ledger)[0])

    def test_an_older_saved_ledger_without_costs_still_works(self) -> None:
        old = {"cmdr": "B", "journal_file": "J", "first_trade": None, "last_trade": None, "rows": {}}
        self.assertTrue(ledger_mod.apply_trade_event(old, {"event": "RefuelAll", "Cost": 5}))
        self.assertEqual(ledger_mod.expenses_by_category(old), {"fuel": 5})

    def test_a_new_session_starts_with_no_costs(self) -> None:
        ledger = self._ledger()
        ledger_mod.apply_trade_event(ledger, {"event": "RefuelAll", "Cost": 5})
        fresh, continued = ledger_mod.sync_ledger(ledger, "Bocheaux", "Journal.2.log")
        self.assertFalse(continued)
        self.assertEqual(ledger_mod.expenses_by_category(fresh), {})


class MarketTests(unittest.TestCase):
    DATA = {"Items": [
        {"Name": "$gold_name;", "Name_Localised": "Gold", "SellPrice": 50_000, "BuyPrice": 0, "Demand": 80, "Stock": 0},
        {"Name": "$tea_name;", "Name_Localised": "Tea", "SellPrice": 0, "BuyPrice": 1_500, "Demand": 0, "Stock": 90},
        {"bad": "row"}, "junk",
    ]}

    def test_names_reduce_to_one_key(self) -> None:
        self.assertEqual(market.canonical_name("$Gold_Name;"), "gold")
        self.assertEqual(market.canonical_name("Low Temperature Diamonds"), "lowtemperaturediamonds")
        self.assertEqual(market.canonical_name("gold"), "gold")

    def test_parse_skips_malformed_rows(self) -> None:
        parsed = market.parse_market(self.DATA)
        self.assertEqual(set(parsed), {"gold", "tea"})
        self.assertEqual(parsed["gold"].sell_price, 50_000)
        self.assertEqual(market.parse_market(None), {})

    def test_cargo_value_counts_only_what_the_station_buys(self) -> None:
        parsed = market.parse_market(self.DATA)
        self.assertEqual(market.cargo_value({"gold": 10, "tea": 5, "unknown": 3}, parsed), 500_000)
        self.assertIsNone(market.cargo_value({"tea": 5}, parsed))
        self.assertIsNone(market.cargo_value({}, parsed))

    def test_missing_file_gives_empty_market(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            self.assertEqual(market.read_market_file(folder), {})


class SpanshClientTests(unittest.TestCase):
    # Shaped like a real /api/results response (captured 2026-10-09).
    RESULT = [{
        "commodities": [{"amount": 98, "name": "Insulating Membrane", "profit": 7861, "total_profit": 770378}],
        "destination": {"distance_to_arrival": 198, "station": "Ivins City", "system": "Gendalla",
                        "market_updated_at": 1791534202},
        "distance": 16.55,
        "source": {"distance_to_arrival": 232, "station": "Daedalus", "system": "Sol", "market_updated_at": 1791515405},
        "total_profit": 770378,
    }]

    def test_parse_hops(self) -> None:
        hops = client.parse_hops(self.RESULT)
        self.assertEqual(len(hops), 1)
        hop = hops[0]
        self.assertEqual((hop.source_station, hop.dest_system, hop.profit), ("Daedalus", "Gendalla", 770378))
        self.assertEqual(hop.cargo[0].tonnes, 98)
        self.assertEqual(hop.market_updated_at, 1791515405)  # the older market

    def test_malformed_hops_are_skipped(self) -> None:
        self.assertEqual(client.parse_hops([{"nope": 1}, "x", None]), [])
        self.assertEqual(client.parse_hops(None), [])

    def test_form_fields_are_clamped_and_stringified(self) -> None:
        form = client.build_form(client.RouteQuery(
            system="Sol", station="Daedalus", capital=-5, cargo_capacity=0, max_hops=0,
            max_hop_distance_ly=0, max_arrival_ls=0, requires_large_pad=True))
        self.assertEqual(form["starting_capital"], "0")
        self.assertEqual(form["max_cargo"], "1")
        self.assertEqual(form["max_hops"], "1")
        self.assertEqual(form["max_hop_distance"], "1")
        self.assertEqual(form["requires_large_pad"], "1")
        self.assertTrue(all(isinstance(value, str) for value in form.values()))


if __name__ == "__main__":
    unittest.main()
