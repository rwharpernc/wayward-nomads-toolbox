"""
The game's lifetime totals on Trade's Session page (trade_lifetime.py): reading the `Statistics` event, the section it makes,
and finding each commander's newest event in the journals. Event shapes copied from a real journal (2026-10-12). Temporary
folders only, so it behaves the same on Windows and Linux.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import time
import types
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
if "config" not in sys.modules:
    _stub = types.ModuleType("config")
    _stub.appname = "EDMarketConnector"
    _stub.config = types.SimpleNamespace(get_str=lambda key: "", default_journal_dir="")
    sys.modules["config"] = _stub

from plugin import trade_lifetime as L  # noqa: E402
from plugin.trade_blocks import to_text  # noqa: E402


def stats(at="2026-10-12T10:55:56Z", **sections):
    base = {"timestamp": at, "event": "Statistics",
            "Trading": {"Markets_Traded_With": 87, "Market_Profits": 388105754, "Resources_Traded": 24336,
                        "Average_Profit": 1884008.5145631, "Highest_Single_Transaction": 66857175, "Data_Sold": 0, "Goods_Sold": 0,
                        "Assets_Sold": 682},
            "Mining": {"Mining_Profits": 68753202, "Quantity_Mined": 539, "Materials_Collected": 2404},
            "Exobiology": {"Organic_Data_Profits": 1639644300, "Organic_Species_Encountered": 36}}
    base.update(sections)
    return base


FLEETCARRIER = {"FLEETCARRIER_EXPORT_TOTAL": 456, "FLEETCARRIER_IMPORT_TOTAL": 0, "FLEETCARRIER_TRADEPROFIT_TOTAL": 43320,
                "FLEETCARRIER_DISTANCE_TRAVELLED": 29719.052553451, "FLEETCARRIER_TOTAL_JUMPS": 99}


class ParseTests(unittest.TestCase):
    def test_the_figures_worth_a_glance_are_kept(self):
        life = L.parse(stats())
        self.assertEqual(life.at, "2026-10-12T10:55:56Z")
        self.assertEqual(life.trading["market_profits"], 388105754)
        self.assertEqual(life.trading["tonnes"], 24336)
        self.assertEqual(life.mining, {"profits": 68753202, "tonnes": 539})
        self.assertEqual(life.exobiology["profits"], 1639644300)
        self.assertEqual(life.carrier, {})

    def test_a_carrier_owner_has_the_carrier_figures(self):
        life = L.parse(stats(FLEETCARRIER=FLEETCARRIER))
        self.assertEqual((life.carrier["jumps"], life.carrier["exported_t"], life.carrier["trade_profit"]), (99, 456, 43320))

    def test_other_events_and_junk_give_nothing(self):
        for junk in (None, [], {}, {"event": "Cargo"}, "Statistics", {"event": "Statistics"}, {"event": "Statistics", "Trading": "x"}):
            self.assertIsNone(L.parse(junk))

    def test_missing_or_odd_values_are_left_out_not_guessed(self):
        life = L.parse({"event": "Statistics", "Trading": {"Market_Profits": "lots", "Resources_Traded": True, "Markets_Traded_With": 5}})
        self.assertEqual(life.trading, {"markets": 5})


class BlockTests(unittest.TestCase):
    def test_nothing_without_an_event(self):
        self.assertEqual(L.blocks(None), [])

    def test_the_section_names_each_group_and_says_when_the_game_took_the_figures(self):
        text = to_text(L.blocks(L.parse(stats())))
        self.assertEqual(text[0], "Lifetime (the game's own totals)")
        for line in ("Trading", "Market profits: 388,105,754 cr", "Traded: 24,336 t", "Markets traded with: 87",
                     "Best single deal: 66,857,175 cr", "Average profit: 1,884,009 cr", "Mining", "Mining profits: 68,753,202 cr",
                     "Mined: 539 t", "Exobiology", "Data sold: 1,639,644,300 cr", "Species found: 36"):
            self.assertIn(line, text)
        self.assertNotIn("Fleet carrier", text)
        self.assertIn("2026-10-12", text[-1])

    def test_a_carrier_owner_also_gets_the_carrier_group(self):
        text = to_text(L.blocks(L.parse(stats(FLEETCARRIER=FLEETCARRIER))))
        self.assertIn("Fleet carrier", text)
        self.assertIn("Jumps: 99", text)
        self.assertIn("Distance: 29,719 ly", text)
        self.assertIn("Exported / imported: 456 t / 0 t", text)
        self.assertIn("Trade profit: 43,320 cr", text)

    def test_a_group_with_nothing_in_it_is_left_out(self):
        life = L.parse({"event": "Statistics", "timestamp": "2026-10-12T10:00:00Z", "Mining": {"Mining_Profits": 5}})
        text = to_text(L.blocks(life))
        self.assertNotIn("Trading", text)
        self.assertNotIn("Exobiology", text)
        self.assertIn("Mining profits: 5 cr", text)


class JournalTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.dir = self._tmp.name

    def journal(self, name, who, events, age=0.0, as_loadgame=False):
        path = os.path.join(self.dir, name)
        header = {"event": "LoadGame", "Commander": who} if as_loadgame else {"event": "Commander", "Name": who}
        with open(path, "w", encoding="utf-8") as handle:
            for entry in [{"event": "Fileheader"}, header, *events]:
                handle.write(json.dumps(entry) + "\n")
        stamp = time.time() - age
        os.utime(path, (stamp, stamp))

    def test_the_newest_event_for_each_commander_is_found(self):
        self.journal("Journal.1.log", "Alice", [stats("2026-10-01T00:00:00Z")], age=5000)
        self.journal("Journal.2.log", "Alice", [stats("2026-10-10T00:00:00Z"), stats("2026-10-11T00:00:00Z")], age=1000)
        self.journal("Journal.3.log", "Bob", [stats("2026-10-09T00:00:00Z", Trading={"Market_Profits": 7})], age=3000)
        found = L.latest_in_journals(["Alice", "bob"], self.dir)
        self.assertEqual(found["alice"].at, "2026-10-11T00:00:00Z")
        self.assertEqual(found["bob"].trading["market_profits"], 7)

    def test_a_commander_with_no_event_is_simply_missing(self):
        self.journal("Journal.1.log", "Alice", [stats()])
        found = L.latest_in_journals(["Alice", "Nobody"], self.dir)
        self.assertEqual(list(found), ["alice"])

    def test_events_in_another_commanders_part_of_a_shared_file_are_not_taken(self):
        path = os.path.join(self.dir, "Journal.1.log")
        with open(path, "w", encoding="utf-8") as handle:
            for entry in ({"event": "Commander", "Name": "Alice"}, stats("2026-10-01T00:00:00Z"),
                          {"event": "LoadGame", "Commander": "Bob"}, stats("2026-10-02T00:00:00Z", Trading={"Market_Profits": 9})):
                handle.write(json.dumps(entry) + "\n")
        found = L.latest_in_journals(["Alice", "Bob"], self.dir)
        self.assertEqual(found["alice"].at, "2026-10-01T00:00:00Z")
        self.assertEqual(found["bob"].trading["market_profits"], 9)

    def test_it_stops_at_the_files_limit_and_copes_with_a_missing_folder(self):
        for i in range(5):
            self.journal(f"Journal.{i}.log", "Alice", [], age=100 - i)
        self.journal("Journal.old.log", "Alice", [stats()], age=99999)
        self.assertEqual(L.latest_in_journals(["Alice"], self.dir, max_files=3), {})
        self.assertEqual(L.latest_in_journals(["Alice"], os.path.join(self.dir, "nope")), {})
        self.assertEqual(L.latest_in_journals([], self.dir), {})


if __name__ == "__main__":
    unittest.main()
