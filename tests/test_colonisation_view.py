"""What the Colonization Sites window lists for a site, and the totals under it (colonisation_view.py)."""
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

from plugin import colonisation, colonisation_view as view  # noqa: E402


def site(**flags) -> colonisation.Site:
    entry = {"MarketID": 7, "ConstructionProgress": 0.4, "ResourcesRequired": [
        {"Name": "$steel_name;", "Name_Localised": "Steel", "RequiredAmount": 500, "ProvidedAmount": 100},
        {"Name": "$water_name;", "Name_Localised": "Water", "RequiredAmount": 50, "ProvidedAmount": 0},
        {"Name": "$copper_name;", "Name_Localised": "Copper", "RequiredAmount": 20, "ProvidedAmount": 20},
        {"Name": "$aluminium_name;", "Name_Localised": "Aluminium", "RequiredAmount": 80, "ProvidedAmount": 0}]}
    entry.update(flags)
    return colonisation.apply_depot_event(entry, None, name="Depot One", system="Sol")


class CommodityRowsTests(unittest.TestCase):
    def test_lists_only_what_is_outstanding_alphabetically(self):
        labels = [r.label for r in view.commodity_rows(site(), {})]
        self.assertEqual(labels, ["Aluminium", "Steel", "Water"])   # Copper is fully delivered

    def test_to_source_takes_the_hold_off(self):
        rows = {r.label: r for r in view.commodity_rows(site(), {"steel": 150, "water": 80})}
        self.assertEqual(rows["Steel"].to_source, 250)
        self.assertEqual(rows["Steel"].in_cargo, 150)
        self.assertEqual(rows["Water"].to_source, 0)
        self.assertTrue(rows["Water"].covered)
        self.assertFalse(rows["Steel"].covered)

    def test_hide_covered_drops_only_covered_rows(self):
        rows = view.commodity_rows(site(), {"water": 50}, hide_covered=True)
        self.assertEqual([r.label for r in rows], ["Aluminium", "Steel"])

    def test_text_filter_is_a_case_insensitive_substring(self):
        self.assertEqual([r.label for r in view.commodity_rows(site(), {}, text="  ALU ")], ["Aluminium"])
        self.assertEqual(view.commodity_rows(site(), {}, text="nothing like this"), [])

    def test_carrier_tonnes_are_attached(self):
        rows = {r.label: r for r in view.commodity_rows(site(), {}, {"steel": 120})}
        self.assertEqual(rows["Steel"].on_carrier, 120)
        self.assertEqual(rows["Water"].on_carrier, 0)


class TotalsTests(unittest.TestCase):
    def test_totals_ignore_the_filters_and_count_trips(self):
        totals = view.totals(site(), {"steel": 100}, capacity=200)
        self.assertEqual(totals.remaining, 400 + 50 + 80)
        self.assertEqual(totals.to_source, 300 + 50 + 80)
        self.assertEqual(totals.in_hold, 100)
        self.assertEqual(totals.lines, 3)
        self.assertEqual(totals.covered, 0)
        self.assertEqual(totals.trips, 3)   # 430 t in 200 t trips

    def test_surplus_in_the_hold_is_not_counted_as_needed(self):
        totals = view.totals(site(), {"water": 500})
        self.assertEqual(totals.in_hold, 50)
        self.assertEqual(totals.covered, 1)

    def test_unknown_capacity_gives_no_trips(self):
        self.assertEqual(view.totals(site(), {}, capacity=0).trips, 0)

    def test_nothing_to_source_gives_no_trips(self):
        everything = {"steel": 400, "water": 50, "aluminium": 80}
        self.assertEqual(view.totals(site(), everything, capacity=100).trips, 0)


class StatusTests(unittest.TestCase):
    def test_status_words(self):
        self.assertEqual(view.site_status(site()), "40%")
        done = site()
        done.complete = True
        self.assertEqual(view.site_status(done), "complete")
        broke = site()
        broke.failed = True
        self.assertEqual(view.site_status(broke), "failed")


if __name__ == "__main__":
    unittest.main()
