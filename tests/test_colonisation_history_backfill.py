"""
The one-time rebuild of a commander's colonization delivery history from every journal they have
(colonisation_catchup.read_all_events, colonisation_history.DeliveryLedger.rebuild).

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


def claim(ts, system="Hyades Sector NE-W a3-1"):
    return {"timestamp": ts, "event": "ColonisationSystemClaim", "StarSystem": system, "SystemAddress": 22949620763280}


def release(ts):
    return {"timestamp": ts, "event": "ColonisationSystemClaimRelease", "StarSystem": "Synuefe DO-L b55-8", "SystemAddress": 18267435247065}


def beacon(ts):
    return {"timestamp": ts, "event": "ColonisationBeaconDeployed"}


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
        found = catchup.read_all_events("Alice", self.dir)
        self.assertEqual([e["timestamp"] for e in found], ["2025-06-01T10:00:00Z", "2026-03-01T10:00:00Z"])

    def test_other_commanders_deliveries_are_left_out_even_in_the_same_file(self):
        path = write_journal(self.dir, "Journal.2026-03-01T000000.01.log", "Alice", [give("2026-03-01T10:00:00Z", 200)])
        with open(path, "a", encoding="utf-8") as handle:
            handle.write(json.dumps({"timestamp": "2026-03-01T11:00:00Z", "event": "LoadGame", "Commander": "Bob"}) + "\n")
            handle.write(json.dumps(give("2026-03-01T12:00:00Z", 999)) + "\n")
        alice = catchup.read_all_events("Alice", self.dir)
        bob = catchup.read_all_events("bob", self.dir)          # the name's case does not matter
        self.assertEqual([e["Contributions"][0]["Amount"] for e in alice], [200])
        self.assertEqual([e["Contributions"][0]["Amount"] for e in bob], [999])

    def test_files_without_a_delivery_are_skipped_and_damaged_lines_do_not_stop_the_read(self):
        write_journal(self.dir, "Journal.2026-01-01T000000.01.log", "Alice", [])
        path = write_journal(self.dir, "Journal.2026-02-01T000000.01.log", "Alice", [give("2026-02-01T10:00:00Z", 50)])
        with open(path, "a", encoding="utf-8") as handle:
            handle.write('{ "event":"ColonisationContribution", broken\n')
        self.assertEqual(len(catchup.read_all_events("Alice", self.dir)), 1)

    def test_a_missing_or_unset_folder_gives_nothing(self):
        self.assertEqual(catchup.read_all_events("Alice", os.path.join(self.dir, "nope")), [])
        self.assertEqual(catchup.read_all_events("Alice", ""), [])


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

    def test_claims_releases_and_beacons_are_counted_with_the_deliveries(self):
        ledger = DeliveryLedger()
        entries = [claim("2025-06-23T14:00:53Z"), beacon("2025-06-23T14:10:48Z"), claim("2025-07-01T09:00:00Z", "Sol"),
                   release("2025-07-27T09:50:54Z"), give("2025-07-28T10:00:00Z", 100)]
        ledger.rebuild("Alice", entries)
        record = ledger.record("Alice")
        self.assertEqual({k: record["claims"][k] for k in ("made", "released", "beacons")}, {"made": 2, "released": 1, "beacons": 1})
        self.assertEqual((record["deliveries"], record["tonnes"]), (1, 100))

    def test_a_claim_seen_live_after_the_rebuild_counts_once(self):
        ledger = DeliveryLedger()
        ledger.rebuild("Alice", [claim("2025-06-23T14:00:53Z")])
        self.assertTrue(ledger.apply_event("Alice", claim("2025-08-01T00:00:00Z")))
        self.assertFalse(ledger.apply_event("Alice", claim("2025-08-01T00:00:00Z")))        # the same event again
        self.assertFalse(ledger.apply_event("Alice", claim("2025-06-23T14:00:53Z")))        # an older one the rebuild already had
        self.assertEqual(ledger.record("Alice")["claims"]["made"], 2)

    def test_claims_and_deliveries_keep_their_own_newest_marks(self):
        ledger = DeliveryLedger()
        ledger.apply_event("Alice", give("2026-03-01T10:00:00Z", 50))
        self.assertTrue(ledger.apply_event("Alice", claim("2026-01-01T00:00:00Z")))          # older than the delivery, still new to claims
        self.assertEqual(ledger.record("Alice")["claims"]["made"], 1)

    def test_a_record_saved_before_claims_existed_gains_the_counters(self):
        ledger = DeliveryLedger()
        ledger.apply_contribution("Alice", give("2026-03-01T10:00:00Z", 50))
        record = ledger.record("Alice")
        del record["claims"]                                           # the shape version 1 wrote
        self.assertTrue(ledger.apply_event("Alice", claim("2026-03-02T00:00:00Z")))
        self.assertEqual(ledger.record("Alice")["claims"]["made"], 1)

    def test_a_rebuild_from_the_first_version_is_done_again_so_claims_are_found(self):
        ledger = DeliveryLedger()
        ledger.rebuild("Alice", [give("2026-03-01T10:00:00Z", 50)])
        ledger.record("Alice")["backfilled"] = True                    # what version 1 stored
        self.assertFalse(ledger.backfilled("Alice"))
        self.assertTrue(ledger.rebuild("Alice", [give("2026-03-01T10:00:00Z", 50), claim("2026-03-02T00:00:00Z")]))
        self.assertTrue(ledger.backfilled("Alice"))
        self.assertEqual(ledger.record("Alice")["claims"]["made"], 1)
        self.assertEqual(ledger.record("Alice")["tonnes"], 50)         # not doubled

    def test_the_reader_finds_claim_events_in_files_with_no_deliveries(self):
        with tempfile.TemporaryDirectory() as folder:
            write_journal(folder, "Journal.2025-06-23T000000.01.log", "Alice", [claim("2025-06-23T14:00:53Z"), beacon("2025-06-23T14:10:48Z")])
            found = catchup.read_all_events("Alice", folder)
            self.assertEqual([e["event"] for e in found], ["ColonisationSystemClaim", "ColonisationBeaconDeployed"])

    def test_the_start_up_catch_up_counts_claims_too_once(self):
        from plugin.colonisation_data import SiteRepository
        ledger = DeliveryLedger()
        events = [("Alice", claim("2026-03-01T00:00:00Z")), ("Alice", beacon("2026-03-02T00:00:00Z"))]
        catchup.apply_events(SiteRepository(), events, ledger)
        catchup.apply_events(SiteRepository(), events, ledger)
        claims = ledger.record("Alice")["claims"]
        self.assertEqual((claims["made"], claims["beacons"]), (1, 1))

    def test_the_whole_path_from_files_to_figures(self):
        with tempfile.TemporaryDirectory() as folder:
            write_journal(folder, "Journal.2025-06-01T000000.01.log", "Alice", [give("2025-06-01T10:00:00Z", 100)])
            write_journal(folder, "Journal.2026-03-01T000000.01.log", "Alice", [give("2026-03-01T10:00:00Z", 200)], as_loadgame=True)
            ledger = DeliveryLedger()
            ledger.rebuild("Alice", catchup.read_all_events("Alice", folder))
            self.assertEqual(ledger.record("Alice")["tonnes"], 300)


if __name__ == "__main__":
    unittest.main()


class SiteNameTests(unittest.TestCase):
    """A delivery names only a MarketID; the history takes the site's name from the Docked at it."""

    @staticmethod
    def dock(ts, market=SITE_A, name="$EXT_PANEL_ColonisationShip; Froude Reach", system="Pegasi Sector GR-V b2-0"):
        return {"timestamp": ts, "event": "Docked", "StationName": name, "StationType": "SurfaceStation",
                "StarSystem": system, "MarketID": market}

    def test_rebuild_names_the_busiest_site(self):
        from plugin import colonisation_stats as stats
        ledger = DeliveryLedger()
        ledger.rebuild("Silas Kade", [self.dock("2025-10-16T10:00:00Z"), give("2025-10-17T10:00:00Z", 500)])
        h = stats.history_for([], ledger.record("Silas Kade"))
        self.assertEqual(h.top_site, ("Froude Reach (Pegasi Sector GR-V b2-0)", 500))

    def test_unnamed_site_still_shows_its_number(self):
        from plugin import colonisation_stats as stats
        ledger = DeliveryLedger()
        ledger.rebuild("Silas Kade", [give("2025-10-17T10:00:00Z", 500)])
        self.assertEqual(stats.history_for([], ledger.record("Silas Kade")).top_site, (f"Construction site {SITE_A}", 500))

    def test_ordinary_station_is_not_kept(self):
        ledger = DeliveryLedger()
        self.assertFalse(ledger.note_station("Silas Kade", {"event": "Docked", "StationName": "Port Trident",
                                                             "StationType": "Coriolis", "MarketID": 1, "StarSystem": "Sol"}))

    def test_read_all_events_finds_the_dock_for_the_right_commander_only(self):
        with tempfile.TemporaryDirectory() as folder:
            lines = [{"timestamp": "2025-10-16T09:00:00Z", "event": "Commander", "Name": "Silas Kade"},
                     self.dock("2025-10-16T10:00:00Z"),
                     {"timestamp": "2025-10-17T09:00:00Z", "event": "Commander", "Name": "Other"},
                     self.dock("2025-10-17T10:00:00Z", market=SITE_B, name="Elsewhere Depot Construction Site")]
            with open(os.path.join(folder, "Journal.2025-10-16T090000.01.log"), "w", encoding="utf-8") as handle:
                handle.write("\n".join(json.dumps(line) for line in lines))
            found = catchup.read_all_events("Silas Kade", folder)
        self.assertEqual([e["MarketID"] for e in found], [SITE_A])
