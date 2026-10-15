"""The list of commodities your missions still need, and looking up the four source picks for each (mission_sources.py, mission_sources_window.rows_for).
A fake search stands in for Spansh, so no network is used."""
from __future__ import annotations

import os
import sys
import types
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
if "config" not in sys.modules:
    _stub = types.ModuleType("config")
    _stub.appname = "EDMarketConnector"
    _stub.config = types.SimpleNamespace(get_str=lambda key: "", default_journal_dir="")
    sys.modules["config"] = _stub

from plugin import mission_sources as M  # noqa: E402
from plugin import source_picks  # noqa: E402
from plugin.mining_spansh_client import StationPrice  # noqa: E402
from plugin.trade_prices import BUY  # noqa: E402


def mission(commodity, count, destination="Sol"):
    return types.SimpleNamespace(needed_commodity=commodity, needed_commodity_count=count, destination_system=destination)


OPTIONS = M.Options(radius_ly=50.0, ship_pad=None, include_carriers=False, include_ground=True)


class NeedsTests(unittest.TestCase):
    def test_commodities_are_summed_and_the_biggest_comes_first(self):
        needs = M.needs_from([mission("Gold", 10), mission("Silver", 50), mission("Gold", 15, "Lave"), mission("Gold", 5, "Lave")])
        self.assertEqual([(n.commodity, n.tonnes, n.missions) for n in needs], [("Silver", 50, 1), ("Gold", 30, 3)])

    def test_the_turn_in_system_is_where_most_missions_are_handed_in(self):
        needs = M.needs_from([mission("Gold", 10, "Lave"), mission("Gold", 10, "Lave"), mission("Gold", 10, "Sol")])
        self.assertEqual(needs[0].turn_in, "Lave")

    def test_missions_with_nothing_to_source_are_ignored(self):
        self.assertEqual(M.needs_from([mission("", 0), mission("Gold", 0), types.SimpleNamespace()]), [])

    def test_the_number_of_needs_is_capped(self):
        many = [mission(f"Item {i:02d}", 5) for i in range(M.MAX_NEEDS + 8)]
        self.assertEqual(len(M.needs_from(many)), M.MAX_NEEDS)

    def test_the_reference_system(self):
        need = M.Need("Gold", 10, 1, "Lave")
        self.assertEqual(M.reference_for(need, M.HERE, "Sol"), "Sol")
        self.assertEqual(M.reference_for(need, M.TURN_IN, "Sol"), "Lave")
        self.assertEqual(M.reference_for(M.Need("Gold", 10, 1, ""), M.TURN_IN, "Sol"), "Sol")


class LookupTests(unittest.TestCase):
    def setUp(self):
        self.calls = []

        def search(reference, commodity, transaction, max_distance, **kw):
            self.calls.append((reference, commodity, transaction))
            return [StationPrice("Dock", "Sol", "Coriolis Starport", 4.0, 100.0, False, 1000, 900, 3, 2, 1)]

        self.search = search

    def run_lookup(self, needs, mode=M.HERE, here="Sol", **kw):
        return M.lookup(needs, mode, here, OPTIONS, search=self.search, pause=lambda _s: None, **kw)

    def test_each_commodity_is_looked_up_for_buying_from_the_chosen_system(self):
        needs = [M.Need("Gold", 10, 1, "Lave"), M.Need("Silver", 5, 1, "")]
        results = self.run_lookup(needs, M.TURN_IN)
        self.assertEqual(set(results), {"Gold", "Silver"})
        self.assertEqual({c[0] for c in self.calls if c[1] == "Gold"}, {"Lave"})
        self.assertEqual({c[0] for c in self.calls if c[1] == "Silver"}, {"Sol"})       # no turn-in system known: where you are
        self.assertTrue(all(c[2] == "Buy" for c in self.calls))

    def test_each_result_is_reported_as_it_finishes(self):
        seen = []
        self.run_lookup([M.Need("Gold", 10, 1, ""), M.Need("Silver", 5, 1, "")], on_done=lambda need, picks: seen.append(need.commodity))
        self.assertEqual(seen, ["Gold", "Silver"])

    def test_cancelling_stops_before_the_next_commodity(self):
        state = {"done": 0}
        results = self.run_lookup([M.Need("Gold", 10, 1, ""), M.Need("Silver", 5, 1, "")], cancelled=lambda: state["done"] >= 1,
                                  on_done=lambda need, picks: state.__setitem__("done", state["done"] + 1))
        self.assertEqual(set(results), {"Gold"})

    def test_a_pause_separates_commodities(self):
        pauses = []
        M.lookup([M.Need("Gold", 10, 1, ""), M.Need("Silver", 5, 1, "")], M.HERE, "Sol", OPTIONS, search=self.search, pause=pauses.append)
        self.assertGreaterEqual(len(pauses), 1)

    def test_nowhere_to_measure_from_skips_the_commodity(self):
        self.assertEqual(self.run_lookup([M.Need("Gold", 10, 1, "")], here=""), {})
        self.assertEqual(self.calls, [])


class RowsTests(unittest.TestCase):
    def setUp(self):
        stubs = {name: mock.MagicMock() for name in ("theme", "myNotebook", "monitor", "ttkHyperlinkLabel", "plug", "EDMCLogging", "l10n")}
        with mock.patch.dict(sys.modules, stubs):
            from plugin import mission_sources_window as W
        self.W = W

    def picks(self):
        station = StationPrice("Dock", "Sol", "Coriolis Starport", 4.0, 100.0, False, 1000, 900, 3, 2, 1)
        result = source_picks.find("Sol", "Gold", BUY, 10, radius_ly=50, search=lambda *a, **k: [station], pause=lambda _s: None, include_carriers=False)
        return result

    def test_the_first_row_names_the_commodity_and_the_rest_do_not(self):
        rows = self.W.rows_for(M.Need("Gold", 1200, 3, ""), self.picks())
        self.assertEqual(rows[0][:2], ["Gold", "1,200 t"])
        self.assertTrue(all(row[:2] == ["", ""] for row in rows[1:]))
        self.assertEqual([row[2] for row in rows], ["Closest", "Best local", "Cheapest anywhere", "Recommended"])
        self.assertEqual(rows[0][8], "Sol")                                # the system to copy

    def test_before_a_search_there_is_just_the_need(self):
        rows = self.W.rows_for(M.Need("Gold", 10, 1, ""), None)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0][0], "Gold")

    def test_nothing_found_says_so(self):
        empty = source_picks.find("Sol", "Gold", BUY, 10, radius_ly=50, search=lambda *a, **k: [], pause=lambda _s: None, include_carriers=False)
        rows = self.W.rows_for(M.Need("Gold", 10, 1, ""), empty)
        self.assertIn("no station", rows[0][3].lower())


if __name__ == "__main__":
    unittest.main()
