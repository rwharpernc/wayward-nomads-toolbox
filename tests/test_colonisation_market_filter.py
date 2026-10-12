"""The Colonization window's "only what this station sells" filter: which commodities the docked market has for sale
(trade_market.sold_keys) and how the shopping list narrows to them (colonisation_view.commodity_rows(only_keys=...))."""
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

from plugin import colonisation, colonisation_view as view, trade_market  # noqa: E402

MARKET = {"Items": [
    {"Name": "$steel_name;", "Name_Localised": "Steel", "BuyPrice": 4000, "SellPrice": 3500, "Stock": 900, "Demand": 0},
    {"Name": "$water_name;", "Name_Localised": "Water", "BuyPrice": 0, "SellPrice": 100, "Stock": 0, "Demand": 500},
    {"Name": "$copper_name;", "Name_Localised": "Copper", "BuyPrice": 1200, "SellPrice": 1000, "Stock": 0, "Demand": 0},
    {"Name": "$ceramiccomposites_name;", "Name_Localised": "Ceramic Composites", "BuyPrice": 300, "SellPrice": 200, "Stock": 50, "Demand": 0},
]}


def site() -> colonisation.Site:
    entry = {"MarketID": 7, "ConstructionProgress": 0.4, "ResourcesRequired": [
        {"Name": "$steel_name;", "Name_Localised": "Steel", "RequiredAmount": 500, "ProvidedAmount": 100},
        {"Name": "$water_name;", "Name_Localised": "Water", "RequiredAmount": 50, "ProvidedAmount": 0},
        {"Name": "$ceramiccomposites_name;", "Name_Localised": "Ceramic Composites", "RequiredAmount": 40, "ProvidedAmount": 0},
        {"Name": "$aluminium_name;", "Name_Localised": "Aluminium", "RequiredAmount": 80, "ProvidedAmount": 0}]}
    return colonisation.apply_depot_event(entry, None, name="Depot One", system="Sol")


class SoldKeysTests(unittest.TestCase):
    def test_only_commodities_with_stock_and_a_price_to_buy_at(self):
        keys = trade_market.sold_keys(trade_market.parse_market(MARKET))
        self.assertEqual(keys, frozenset({"steel", "ceramiccomposites"}))   # water is only wanted, copper is out of stock

    def test_an_empty_or_unreadable_market_sells_nothing(self):
        self.assertEqual(trade_market.sold_keys(trade_market.parse_market(None)), frozenset())


class OnlyKeysTests(unittest.TestCase):
    def test_no_filter_keeps_everything_outstanding(self):
        self.assertEqual([r.label for r in view.commodity_rows(site(), {})],
                         ["Aluminium", "Ceramic Composites", "Steel", "Water"])

    def test_only_what_the_station_sells(self):
        keys = trade_market.sold_keys(trade_market.parse_market(MARKET))
        rows = view.commodity_rows(site(), {}, only_keys=keys)
        self.assertEqual([r.label for r in rows], ["Ceramic Composites", "Steel"])

    def test_an_empty_set_hides_every_row_and_none_means_no_filter(self):
        self.assertEqual(view.commodity_rows(site(), {}, only_keys=frozenset()), [])
        self.assertEqual(len(view.commodity_rows(site(), {}, only_keys=None)), 4)

    def test_it_combines_with_the_other_filters(self):
        keys = trade_market.sold_keys(trade_market.parse_market(MARKET))
        rows = view.commodity_rows(site(), {"steel": 400}, hide_covered=True, text="c", only_keys=keys)
        self.assertEqual([r.label for r in rows], ["Ceramic Composites"])   # steel is covered; text "c" drops nothing else


if __name__ == "__main__":
    unittest.main()
