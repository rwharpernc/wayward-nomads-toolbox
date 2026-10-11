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


class CoverageStateTests(unittest.TestCase):
    """The row color: green when the hold plus the carrier covers the need, orange when it is more, else unchanged."""

    def state_of(self, label, cargo, carrier=None):
        rows = {r.label: r for r in view.commodity_rows(site(), cargo, carrier)}
        return rows[label].state

    def test_short_enough_and_over_by_the_hold_alone(self):
        self.assertEqual(self.state_of("Steel", {"steel": 399}), view.STATE_SHORT)
        self.assertEqual(self.state_of("Steel", {"steel": 400}), view.STATE_ENOUGH)   # exactly equal is green
        self.assertEqual(self.state_of("Steel", {"steel": 401}), view.STATE_OVER)

    def test_the_carrier_counts_toward_the_need(self):
        self.assertEqual(self.state_of("Steel", {"steel": 100}, {"steel": 299}), view.STATE_SHORT)
        self.assertEqual(self.state_of("Steel", {"steel": 100}, {"steel": 300}), view.STATE_ENOUGH)
        self.assertEqual(self.state_of("Steel", {"steel": 100}, {"steel": 301}), view.STATE_OVER)

    def test_the_carrier_alone_can_cover_it(self):
        self.assertEqual(self.state_of("Water", {}, {"water": 50}), view.STATE_ENOUGH)
        self.assertEqual(self.state_of("Water", {}, {"water": 60}), view.STATE_OVER)

    def test_nothing_held_is_short(self):
        self.assertEqual(self.state_of("Steel", {}), view.STATE_SHORT)

    def test_covered_follows_the_state_and_hide_covered_uses_it(self):
        rows = view.commodity_rows(site(), {"water": 10}, {"water": 40}, hide_covered=True)
        self.assertEqual([r.label for r in rows], ["Aluminium", "Steel"])   # Water: 10 + 40 = 50 needed

    def test_totals_count_carrier_coverage_when_given_it(self):
        self.assertEqual(view.totals(site(), {}).covered, 0)
        self.assertEqual(view.totals(site(), {}, carrier={"water": 50, "aluminium": 90}).covered, 2)


class TotalsTests(unittest.TestCase):
    def test_totals_ignore_the_filters_and_count_trips(self):
        totals = view.totals(site(), {"steel": 100}, capacity=100)
        self.assertEqual(totals.remaining, 400 + 50 + 80)
        self.assertEqual(totals.to_source, 300 + 50 + 80)
        self.assertEqual(totals.in_hold, 100)
        self.assertEqual(totals.lines, 3)
        self.assertEqual(totals.covered, 0)
        self.assertEqual(totals.trips, 6)   # all 530 t still to deliver in 100 t trips; the hold is the first load

    def test_surplus_in_the_hold_is_not_counted_as_needed(self):
        totals = view.totals(site(), {"water": 500})
        self.assertEqual(totals.in_hold, 50)
        self.assertEqual(totals.covered, 1)

    def test_unknown_capacity_gives_no_trips(self):
        self.assertEqual(view.totals(site(), {}, capacity=0).trips, 0)

    def test_a_full_hold_still_has_to_be_delivered(self):
        everything = {"steel": 400, "water": 50, "aluminium": 80}
        totals = view.totals(site(), everything, capacity=100)
        self.assertEqual((totals.to_source, totals.trips), (0, 6))   # nothing to buy, 530 t to deliver

    def test_a_finished_site_needs_no_trips(self):
        done = site()
        for resource in done.resources:
            resource.provided = resource.required
        self.assertEqual(view.totals(done, {}, capacity=100).trips, 0)


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
