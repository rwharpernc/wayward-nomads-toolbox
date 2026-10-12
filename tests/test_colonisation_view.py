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


class GroupingAndAvailabilityTests(unittest.TestCase):
    def test_rows_group_under_market_categories_alphabetically(self):
        groups = view.group_rows(view.commodity_rows(site(), {}))
        self.assertEqual([(c, [r.label for r in rows]) for c, rows in groups],
                         [("Chemicals", ["Water"]), ("Metals", ["Aluminium", "Steel"])])

    def test_the_market_marks_rows_available_without_filtering_any(self):
        rows = {r.label: r for r in view.commodity_rows(site(), {}, market_keys={"steel", "water"})}
        self.assertEqual({k: r.available for k, r in rows.items()}, {"Aluminium": False, "Steel": True, "Water": True})
        for keys in (None, set()):
            self.assertTrue(all(r.available for r in view.commodity_rows(site(), {}, market_keys=keys)))


class CommodityRowsTests(unittest.TestCase):
    def test_lists_only_what_is_outstanding_alphabetically(self):
        labels = [r.label for r in view.commodity_rows(site(), {})]
        self.assertEqual(labels, ["Aluminium", "Steel", "Water"])   # Copper is fully delivered

    def test_to_get_takes_the_ship_off(self):
        rows = {r.label: r for r in view.commodity_rows(site(), {"steel": 150, "water": 80})}
        self.assertEqual(rows["Steel"].to_get, 250)
        self.assertEqual(rows["Steel"].in_cargo, 150)
        self.assertEqual(rows["Water"].to_get, 0)
        self.assertTrue(rows["Water"].covered)
        self.assertFalse(rows["Steel"].covered)

    def test_hide_covered_drops_only_covered_rows(self):
        rows = view.commodity_rows(site(), {"water": 50}, hide_covered=True)
        self.assertEqual([r.label for r in rows], ["Aluminium", "Steel"])

    def test_text_filter_is_a_case_insensitive_substring(self):
        self.assertEqual([r.label for r in view.commodity_rows(site(), {}, text="  ALU ")], ["Aluminium"])
        self.assertEqual(view.commodity_rows(site(), {}, text="nothing like this"), [])

    def test_carrier_tons_are_attached(self):
        rows = {r.label: r for r in view.commodity_rows(site(), {}, {"steel": 120})}
        self.assertEqual(rows["Steel"].on_carrier, 120)
        self.assertEqual(rows["Water"].on_carrier, 0)


class TripsTests(unittest.TestCase):
    def test_whole_and_fractional_trips(self):
        self.assertEqual(view.format_trips(view.trips_for(400, 100)), "4")
        self.assertEqual(view.format_trips(view.trips_for(150, 100)), "1.5")
        self.assertEqual(view.format_trips(view.trips_for(125, 100)), "1.25")
        self.assertEqual(view.format_trips(view.trips_for(50, 100)), "0.5")

    def test_never_more_than_two_decimals_and_rounds_half_up(self):
        self.assertEqual(view.format_trips(view.trips_for(100, 300)), "0.33")
        self.assertEqual(view.format_trips(view.trips_for(200, 300)), "0.67")
        self.assertEqual(view.format_trips(view.trips_for(1, 8)), "0.13")      # 0.125 rounds up
        self.assertEqual(view.format_trips(view.trips_for(2675, 1000)), "2.68")  # exact, not a float surprise

    def test_a_small_remainder_never_reads_as_zero(self):
        self.assertEqual(view.format_trips(view.trips_for(1, 784)), "0.01")

    def test_thousands_are_separated(self):
        self.assertEqual(view.format_trips(view.trips_for(1_000_000, 784)), "1,275.51")

    def test_unknown_capacity_is_a_dash_and_nothing_left_is_zero(self):
        self.assertEqual(view.format_trips(view.trips_for(400, 0)), "–")
        self.assertEqual(view.format_trips(None), "–")
        self.assertEqual(view.format_trips(view.trips_for(0, 100)), "0")

    def test_rows_carry_their_trips_from_what_remains(self):
        rows = {r.label: r for r in view.commodity_rows(site(), {"steel": 100}, {"steel": 150}, capacity=100)}
        self.assertEqual(view.format_trips(rows["Steel"].haul_trips), "4")        # 400 t remaining, whatever is already held
        self.assertEqual(view.format_trips(rows["Aluminium"].haul_trips), "0.8")  # 80 t
        self.assertIsNone({r.label: r for r in view.commodity_rows(site(), {})}["Steel"].haul_trips)
        self.assertIsNone({r.label: r for r in view.commodity_rows(site(), {})}["Steel"].buy_trips)


class TwoLegTests(unittest.TestCase):
    """Stock stored on the carrier while it fills: nothing left to buy, but all of it still has to be hauled."""

    def test_a_commodity_fully_on_the_carrier_needs_no_buying_but_still_needs_hauling(self):
        row = {r.label: r for r in view.commodity_rows(site(), {}, {"steel": 400}, capacity=100)}["Steel"]
        self.assertEqual(view.format_trips(row.buy_trips), "0")
        self.assertEqual(view.format_trips(row.haul_trips), "4")
        self.assertEqual(row.state, view.STATE_ENOUGH)

    def test_the_carrier_lowers_the_buying_trips_but_not_the_hauling_ones(self):
        row = {r.label: r for r in view.commodity_rows(site(), {}, {"steel": 150}, capacity=100)}["Steel"]
        self.assertEqual(view.format_trips(row.buy_trips), "2.5")      # 250 t still to buy
        self.assertEqual(view.format_trips(row.haul_trips), "4")        # all 400 t still go to the site

    def test_the_totals_show_the_carrier_and_both_legs(self):
        totals = view.totals(site(), {}, capacity=100, carrier={"steel": 400, "water": 999})
        self.assertEqual(totals.on_carrier, 400 + 50)              # capped at what the site needs
        self.assertEqual(totals.buy_trips, 1)                      # only the 80 t of aluminium is missing
        self.assertEqual(totals.haul_trips, 6)                     # 530 t to carry over


class StillToGetTests(unittest.TestCase):
    def test_the_carrier_is_taken_off_as_well(self):
        rows = {r.label: r for r in view.commodity_rows(site(), {"steel": 100}, {"steel": 150})}
        self.assertEqual(rows["Steel"].to_get, 150)   # 400 needed, 100 on the ship, 150 on the carrier

    def test_it_never_goes_below_zero(self):
        rows = {r.label: r for r in view.commodity_rows(site(), {"steel": 300}, {"steel": 300})}
        self.assertEqual(rows["Steel"].to_get, 0)

    def test_it_is_zero_exactly_when_the_row_is_covered(self):
        for cargo, carrier in (({}, {}), ({"steel": 400}, {}), ({"steel": 100}, {"steel": 300}), ({}, {"steel": 500})):
            row = {r.label: r for r in view.commodity_rows(site(), cargo, carrier)}["Steel"]
            self.assertEqual(row.to_get == 0, row.covered, (cargo, carrier))

    def test_the_total_counts_the_carrier(self):
        self.assertEqual(view.totals(site(), {}, carrier={"steel": 400}).to_get, 50 + 80)


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
        self.assertEqual(totals.to_get, 300 + 50 + 80)
        self.assertEqual(totals.in_hold, 100)
        self.assertEqual(totals.lines, 3)
        self.assertEqual(totals.covered, 0)
        self.assertEqual(totals.haul_trips, 6)   # all 530 t still to haul in 100 t trips; the ship is the first load
        self.assertEqual(totals.buy_trips, 5)    # 430 t still to buy

    def test_surplus_in_the_hold_is_not_counted_as_needed(self):
        totals = view.totals(site(), {"water": 500})
        self.assertEqual(totals.in_hold, 50)
        self.assertEqual(totals.covered, 1)

    def test_unknown_capacity_gives_no_trips(self):
        self.assertEqual((view.totals(site(), {}, capacity=0).buy_trips, view.totals(site(), {}, capacity=0).haul_trips), (0, 0))

    def test_a_full_hold_still_has_to_be_delivered(self):
        everything = {"steel": 400, "water": 50, "aluminium": 80}
        totals = view.totals(site(), everything, capacity=100)
        self.assertEqual((totals.to_get, totals.buy_trips, totals.haul_trips), (0, 0, 6))   # nothing to buy, 530 t to haul

    def test_a_finished_site_needs_no_trips(self):
        done = site()
        for resource in done.resources:
            resource.provided = resource.required
        self.assertEqual(view.totals(done, {}, capacity=100).haul_trips, 0)


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
