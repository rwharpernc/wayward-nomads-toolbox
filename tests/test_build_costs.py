"""
The bundled build cost table (build_costs.py, plugin/colonisation_costs.json): what each kind of building needs in tons, looked up
by a site's layout name. Reads the real bundled file, so a bad table fails here. Pure; no network.
"""
from __future__ import annotations

import json
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

from plugin import build_costs as B  # noqa: E402


class BundledTableTests(unittest.TestCase):
    def test_the_bundled_file_is_there_and_every_entry_is_usable(self):
        path = os.path.join(os.path.dirname(B.__file__), B.TABLE_FILE)
        with open(path, encoding="utf-8") as handle:
            raw = json.load(handle)
        self.assertGreater(len(raw), 40)
        for entry in raw:
            self.assertTrue(entry["buildType"] and entry["displayName"], entry)
            self.assertTrue(entry["cargo"], entry["buildType"])
            for commodity, tons in entry["cargo"].items():
                self.assertIsInstance(tons, int, (entry["buildType"], commodity))
                self.assertGreater(tons, 0, (entry["buildType"], commodity))

    def test_every_commodity_in_the_table_has_a_game_name(self):
        from plugin import trade_commodities
        unknown = sorted({key for cost in B.table().values() for key in cost.cargo if not trade_commodities.resolve(key)})
        self.assertEqual(unknown, [])

    def test_a_coriolis_matches_the_total_a_project_reports(self):
        # Raven Colonial reported maxNeed 53,723 for a no_truss Coriolis (2026-10-12), the same as this table.
        self.assertEqual(B.cost_for("no_truss").total, 53_723)

    def test_every_layout_of_a_kind_shares_that_kinds_cost(self):
        self.assertIs(B.cost_for("dual_truss"), B.cost_for("no_truss"))
        self.assertIs(B.cost_for("quad_truss"), B.cost_for("no_truss"))
        self.assertEqual(B.cost_for("hermes").name, "Satellite Installation")


class LookupTests(unittest.TestCase):
    def test_case_and_spaces_do_not_matter(self):
        self.assertIs(B.cost_for("TELLUS"), B.cost_for("tellus"))
        self.assertIs(B.cost_for(" Quad Truss "), B.cost_for("quad_truss"))

    def test_an_unknown_or_missing_type_is_none(self):
        for value in (None, "", "   ", "nonsense", 5):
            self.assertIsNone(B.cost_for(value))

    def test_an_entrys_own_type_wins_over_another_entry_that_lists_it_as_a_layout(self):
        # "tellus" is the Exploration Hub's own type but also one of the Industrial Hub's layouts.
        self.assertEqual(B.cost_for("tellus").name, "Exploration Hub")
        self.assertEqual(B.cost_for("molae").name, "Industrial Hub")

    def test_the_biggest_commodities_come_with_their_game_names(self):
        cost = B.cost_for("no_truss")
        self.assertEqual(cost.biggest(2), [("Steel", 14076), ("CMM Composite", 11261)])
        self.assertEqual(len(cost.biggest(50)), len(cost.cargo))
        from plugin import trade_commodities
        self.assertEqual(B.commodity_label("liquidoxygen"), trade_commodities.resolve("liquidoxygen"))
        self.assertEqual(B.commodity_label("not_a_commodity"), "Not A Commodity")


class ParseTests(unittest.TestCase):
    def test_junk_gives_an_empty_table(self):
        for data in (None, {}, "x", 3, [None, "x", 3, {}, {"buildType": ""}, {"buildType": "a"}, {"buildType": "a", "cargo": "x"},
                                       {"buildType": "a", "cargo": {"steel": 0, "gold": -3, "tin": True}}]):
            self.assertEqual(B.parse(data), {})

    def test_zero_and_odd_amounts_are_dropped_but_good_ones_kept(self):
        table = B.parse([{"buildType": "a", "displayName": "A", "tier": 2, "location": "Orbital",
                          "cargo": {"steel": 10, "gold": 0, "tin": "5", "lead": 7}, "layouts": ["A", "b_two", None]}])
        self.assertEqual(dict(table["a"].cargo), {"steel": 10, "lead": 7})
        self.assertEqual((table["a"].total, table["a"].tier, table["a"].location), (17, 2, "orbital"))
        self.assertIs(table["b_two"], table["a"])

    def test_a_damaged_file_leaves_an_empty_table_rather_than_raising(self):
        from unittest import mock
        with mock.patch.object(B, "_table", None), mock.patch("builtins.open", side_effect=OSError("gone")):
            with self.assertLogs(level="WARNING"):
                self.assertEqual(B.table(), {})
            self.assertIsNone(B.cost_for("no_truss"))
        B._table = None            # the next real lookup reads the real file again
        self.assertIsNotNone(B.cost_for("no_truss"))


if __name__ == "__main__":
    unittest.main()
