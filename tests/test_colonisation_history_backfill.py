"""
The one-time rebuild of a commander's colonization delivery history from every journal they have
(colonisation_catchup.read_all_contributions, colonisation_history.DeliveryLedger.rebuild).

Journal files in a temporary folder and a ledger with no plugin folder (nothing is written), so it behaves the same on
Windows and Linux.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import types
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
if "config" not in sys.modules:
    _stub = types.ModuleType("config")
    _stub.appname = "EDMarketConnector"
    _stub.config = types.SimpleNamespace(get_str=lambda key: "", default_journal_dir="")
    sys.modules["config"] = _stub

from plugin import colonisation_catchup as catchup  # noqa: E402
from plugin.colonisation_history import DeliveryLedger  # noqa: E402

SITE_A, SITE_B = 3700000001, 3700000002


def give(ts, amount, market=SITE_A, name="steel", label="Steel"):
    return {"timestamp": ts, "event": "ColonisationContribution", "MarketID": market,
            "Contributions": [{"Name": f"${name}_name;", "Name_Localised": label, "Amount": amount}]}


def write_journal(folder, name, who, entries, as_loadgame=False):
    header = {"timestamp": "2026-01-01T00:00:00Z", "event": "LoadGame" if as_loadgame else "Commander",
              ("Commander" if as_loadgame else "Name"): who}
    path = os.path.join(folder, name)
    with open(path, "w", encoding="utf-8") as handle:
        for entry in [{"timestamp": "2026-01-01T00:00:00Z", "event": "Fileheader"}, header, *entries]:
            handle.write(json.dumps(entry) + "\n")
    return path


class ReaderTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.dir = self._tmp.name

    def test_every_delivery_of_the_commander_is_found_oldest_first_across_files(self):
        write_journal(self.dir, "Journal.2026-03-01T000000.01.log", "Alice", [give("2026-03-01T10:00:00Z", 200)])
        write_journal(self.dir, "Journal.2025-06-01T000000.01.log", "Alice", [give("2025-06-01T10:00:00Z", 100)])
        found = catchup.read_all_contributions("Alice", self.dir)
        self.assertEqual([e["timestamp"] for e in found], ["2025-06-01T10:00:00Z", "2026-03-01T10:00:00Z"])

    def test_other_commanders_deliveries_are_left_out_even_in_the_same_file(self):
        path = write_journal(self.dir, "Journal.2026-03-01T000000.01.log", "Alice", [give("2026-03-01T10:00:00Z", 200)])
        with open(path, "a", encoding="utf-8") as handle:
            handle.write(json.dumps({"timestamp": "2026-03-01T11:00:00Z", "event": "LoadGame", "Commander": "Bob"}) + "\n")
            handle.write(json.dumps(give("2026-03-01T12:00:00Z", 999)) + "\n")
        alice = catchup.read_all_contributions("Alice", self.dir)
        bob = catchup.read_all_contributions("bob", self.dir)          # the name's case does not matter
        self.assertEqual([e["Contributions"][0]["Amount"] for e in alice], [200])
        self.assertEqual([e["Contributions"][0]["Amount"] for e in bob], [999])

    def test_files_without_a_delivery_are_skipped_and_damaged_lines_do_not_stop_the_read(self):
        write_journal(self.dir, "Journal.2026-01-01T000000.01.log", "Alice", [])
        path = write_journal(self.dir, "Journal.2026-02-01T000000.01.log", "Alice", [give("2026-02-01T10:00:00Z", 50)])
        with open(path, "a", encoding="utf-8") as handle:
            handle.write('{ "event":"ColonisationContribution", broken\n')
        self.assertEqual(len(catchup.read_all_contributions("Alice", self.dir)), 1)

    def test_a_missing_or_unset_folder_gives_nothing(self):
        self.assertEqual(catchup.read_all_contributions("Alice", os.path.join(self.dir, "nope")), [])
        self.assertEqual(catchup.read_all_contributions("Alice", ""), [])


class RebuildTests(unittest.TestCase):
    def test_a_rebuild_counts_everything_by_commodity_site_and_day(self):
        ledger = DeliveryLedger()
        entries = [give("2025-06-01T10:00:00Z", 100), give("2025-06-01T15:00:00Z", 50, SITE_B, "water", "Water"),
                   give("2026-03-01T10:00:00Z", 200)]
        self.assertTrue(ledger.rebuild("Alice", entries))
        record = ledger.record("Alice")
        self.assertEqual((record["deliveries"], record["tonnes"]), (3, 350))
        self.assertEqual(record["by_commodity"]["steel"]["tonnes"], 300)
        self.assertEqual(record["by_site"], {str(SITE_A): 300, str(SITE_B): 50})
        self.assertEqual(record["by_day"]["2025-06-01"], 150)
        self.assertTrue(record["first"].startswith("2025-06-01"))
        self.assertTrue(record["last"].startswith("2026-03-01"))
        self.assertTrue(ledger.backfilled("Alice"))

    def test_the_order_given_does_not_matter(self):
        entries = [give("2026-03-01T10:00:00Z", 200), give("2025-06-01T10:00:00Z", 100)]
        ledger = DeliveryLedger()
        ledger.rebuild("Alice", entries)
        self.assertEqual(ledger.record("Alice")["tonnes"], 300)

    def test_rebuilding_fills_in_what_the_short_catch_up_never_saw_without_double_counting(self):
        ledger = DeliveryLedger()
        ledger.apply_contribution("Alice", give("2026-03-01T10:00:00Z", 200))    # what the 30-day catch-up found
        self.assertEqual(ledger.record("Alice")["tonnes"], 200)
        ledger.rebuild("Alice", [give("2025-06-01T10:00:00Z", 100), give("2026-03-01T10:00:00Z", 200)])
        self.assertEqual(ledger.record("Alice")["tonnes"], 300)                  # not 500
        self.assertEqual(ledger.record("Alice")["deliveries"], 2)

    def test_live_events_after_the_rebuild_are_still_counted_once(self):
        ledger = DeliveryLedger()
        ledger.rebuild("Alice", [give("2026-03-01T10:00:00Z", 200)])
        self.assertTrue(ledger.apply_contribution("Alice", give("2026-03-02T10:00:00Z", 30)))
        self.assertFalse(ledger.apply_contribution("Alice", give("2026-03-02T10:00:00Z", 30)))   # the same event again
        self.assertEqual(ledger.record("Alice")["tonnes"], 230)

    def test_a_delivery_made_while_the_journals_were_read_is_added_after_unless_the_journals_had_it(self):
        ledger = DeliveryLedger()
        read = [give("2026-03-01T10:00:00Z", 200)]
        during = [give("2026-03-01T10:00:00Z", 200), give("2026-03-01T11:00:00Z", 40)]    # one already read, one new
        ledger.rebuild("Alice", read, newer=during)
        self.assertEqual((ledger.record("Alice")["tonnes"], ledger.record("Alice")["deliveries"]), (240, 2))

    def test_smaller_rebuilt_figures_never_replace_larger_saved_ones(self):
        # The commander deleted their old journals: what was counted live must survive.
        ledger = DeliveryLedger()
        for day, amount in (("2025-06-01", 100), ("2025-07-01", 100), ("2026-03-01", 100)):
            ledger.apply_contribution("Alice", give(f"{day}T10:00:00Z", amount))
        self.assertFalse(ledger.rebuild("Alice", [give("2026-03-01T10:00:00Z", 100)]))
        self.assertEqual(ledger.record("Alice")["tonnes"], 300)
        self.assertTrue(ledger.backfilled("Alice"))                      # still marked done, so it is not repeated

    def test_it_is_marked_done_even_for_a_commander_with_no_deliveries(self):
        ledger = DeliveryLedger()
        self.assertFalse(ledger.backfilled("Alice"))
        ledger.rebuild("Alice", [])
        self.assertTrue(ledger.backfilled("Alice"))
        self.assertEqual(ledger.record("Alice")["deliveries"], 0)

    def test_each_commander_is_rebuilt_apart(self):
        ledger = DeliveryLedger()
        ledger.rebuild("Alice", [give("2026-03-01T10:00:00Z", 200)])
        self.assertFalse(ledger.backfilled("Bob"))
        self.assertEqual(ledger.record("Bob")["tonnes"], 0)
        ledger.rebuild("Bob", [give("2026-03-02T10:00:00Z", 7)])
        self.assertEqual((ledger.record("Alice")["tonnes"], ledger.record("Bob")["tonnes"]), (200, 7))

    def test_no_commander_name_means_nothing_is_rebuilt(self):
        ledger = DeliveryLedger()
        self.assertFalse(ledger.rebuild("", [give("2026-03-01T10:00:00Z", 200)]))
        self.assertFalse(ledger.backfilled(""))

    def test_the_whole_path_from_files_to_figures(self):
        with tempfile.TemporaryDirectory() as folder:
            write_journal(folder, "Journal.2025-06-01T000000.01.log", "Alice", [give("2025-06-01T10:00:00Z", 100)])
            write_journal(folder, "Journal.2026-03-01T000000.01.log", "Alice", [give("2026-03-01T10:00:00Z", 200)], as_loadgame=True)
            ledger = DeliveryLedger()
            ledger.rebuild("Alice", catchup.read_all_contributions("Alice", folder))
            self.assertEqual(ledger.record("Alice")["tonnes"], 300)


if __name__ == "__main__":
    unittest.main()
