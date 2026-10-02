"""
Unit tests for plugin/colonisation.py.

Pure logic tests — no EDMC runtime needed. Run with:
    python -m unittest discover -s tests
"""

from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from plugin.colonisation import (  # noqa: E402
    Site, apply_contribution, apply_depot_event, cargo_by_key, commodity_key, shopping_list, still_to_source,
)

_DEPOT = {
    "timestamp": "2026-10-01T00:00:00Z",
    "event": "ColonisationConstructionDepot",
    "MarketID": 3700000001,
    "ConstructionProgress": 0.25,
    "ConstructionComplete": False,
    "ConstructionFailed": False,
    "ResourcesRequired": [
        {"Name": "$steel_name;", "Name_Localised": "Steel", "RequiredAmount": 1000, "ProvidedAmount": 400, "Payment": 5000},
        {"Name": "$aluminium_name;", "Name_Localised": "Aluminium", "RequiredAmount": 300, "ProvidedAmount": 300, "Payment": 4000},
        {"Name": "$titanium_name;", "Name_Localised": "Titanium", "RequiredAmount": 200, "ProvidedAmount": 0, "Payment": 6000},
    ],
}


class CommodityKeyTests(unittest.TestCase):
    def test_journal_and_cargo_names_agree(self) -> None:
        self.assertEqual(commodity_key("$steel_name;"), "steel")
        self.assertEqual(commodity_key("steel"), "steel")
        self.assertEqual(commodity_key("$Steel_Name;"), "steel")

    def test_non_string_is_empty(self) -> None:
        self.assertEqual(commodity_key(None), "")


class DepotEventTests(unittest.TestCase):
    def test_builds_a_site_from_the_snapshot(self) -> None:
        site = apply_depot_event(_DEPOT, None, name="Orbital Construction Site", system="Sol")
        assert site is not None
        self.assertEqual(site.market_id, 3700000001)
        self.assertEqual(site.name, "Orbital Construction Site")
        self.assertAlmostEqual(site.progress, 0.25)
        self.assertEqual(site.remaining_total, 600 + 0 + 200)
        self.assertTrue(site.active)

    def test_no_market_id_is_ignored(self) -> None:
        self.assertIsNone(apply_depot_event({"event": "ColonisationConstructionDepot"}, None))

    def test_known_name_is_not_overwritten(self) -> None:
        site = apply_depot_event(_DEPOT, None, name="First")
        site = apply_depot_event(_DEPOT, site, name="Second")
        assert site is not None
        self.assertEqual(site.name, "First")

    def test_snapshot_replaces_resources_wholesale(self) -> None:
        site = apply_depot_event(_DEPOT, None)
        trimmed = dict(_DEPOT, ResourcesRequired=_DEPOT["ResourcesRequired"][:1])
        site = apply_depot_event(trimmed, site)
        assert site is not None
        self.assertEqual([r.key for r in site.resources], ["steel"])

    def test_provided_never_exceeds_required(self) -> None:
        odd = dict(_DEPOT, ResourcesRequired=[
            {"Name": "$steel_name;", "RequiredAmount": 10, "ProvidedAmount": 50}])
        site = apply_depot_event(odd, None)
        assert site is not None
        self.assertEqual(site.resources[0].remaining, 0)

    def test_complete_site_is_not_active(self) -> None:
        site = apply_depot_event(dict(_DEPOT, ConstructionComplete=True), None)
        assert site is not None
        self.assertFalse(site.active)


class ContributionTests(unittest.TestCase):
    def test_contribution_advances_provided(self) -> None:
        site = apply_depot_event(_DEPOT, None)
        assert site is not None
        changed = apply_contribution(site, {"Contributions": [{"Name": "$steel_name;", "Amount": 250}]})
        self.assertTrue(changed)
        steel = next(r for r in site.resources if r.key == "steel")
        self.assertEqual(steel.provided, 650)

    def test_contribution_is_clamped_and_unknown_ignored(self) -> None:
        site = apply_depot_event(_DEPOT, None)
        assert site is not None
        apply_contribution(site, {"Contributions": [{"Name": "$titanium_name;", "Amount": 9999}]})
        titanium = next(r for r in site.resources if r.key == "titanium")
        self.assertEqual(titanium.remaining, 0)
        self.assertFalse(apply_contribution(site, {"Contributions": [{"Name": "$gold_name;", "Amount": 5}]}))


class CargoTests(unittest.TestCase):
    def test_still_to_source_subtracts_the_hold(self) -> None:
        site = apply_depot_event(_DEPOT, None)
        assert site is not None
        cargo = cargo_by_key({"steel": 100, "titanium": 500})
        steel, _alu, titanium = site.resources
        self.assertEqual(still_to_source(steel, cargo), 500)
        self.assertEqual(still_to_source(titanium, cargo), 0)

    def test_shopping_list_is_largest_first_and_skips_done(self) -> None:
        site = apply_depot_event(_DEPOT, None)
        assert site is not None
        self.assertEqual(shopping_list(site), [("Steel", 600), ("Titanium", 200)])
        self.assertEqual(shopping_list(site, {"steel": 600}), [("Titanium", 200)])


class RoundTripTests(unittest.TestCase):
    def test_serialisation_round_trip(self) -> None:
        site = apply_depot_event(_DEPOT, None, name="X", system="Sol")
        assert site is not None
        again = Site.from_dict(site.to_dict())
        self.assertEqual(again.to_dict(), site.to_dict())


if __name__ == "__main__":
    unittest.main()
