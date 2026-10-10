"""
Colonisation catches up from the journals without counting a delivery twice.

Uses the repository with no plugin folder (nothing is written) and journal files in a temporary folder.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import time
import types
import unittest
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
if "config" not in sys.modules:
    _stub = types.ModuleType("config")
    _stub.appname = "EDMarketConnector"
    _stub.config = types.SimpleNamespace(get_str=lambda key: "", default_journal_dir="")
    sys.modules["config"] = _stub

from plugin import colonisation, colonisation_catchup as catchup  # noqa: E402
from plugin.colonisation_data import SiteRepository  # noqa: E402

MARKET = 3700000001


def depot(ts: str, steel_provided: int = 0) -> dict:
    return {"timestamp": ts, "event": "ColonisationConstructionDepot", "MarketID": MARKET, "ConstructionProgress": 0.1,
            "ResourcesRequired": [{"Name": "$steel_name;", "Name_Localised": "Steel", "RequiredAmount": 1000,
                                   "ProvidedAmount": steel_provided, "Payment": 1}]}


def give(ts: str, amount: int) -> dict:
    return {"timestamp": ts, "event": "ColonisationContribution", "MarketID": MARKET,
            "Contributions": [{"Name": "$steel_name;", "Amount": amount}]}


def docked(ts: str) -> dict:
    return {"timestamp": ts, "event": "Docked", "MarketID": MARKET, "StationName": "Orbital Construction Site: X",
            "StarSystem": "Sol"}


def provided(repo: SiteRepository, cmdr: str = "Alice") -> int:
    return repo.get(cmdr, MARKET).resources[0].provided


class ApplyEventsTests(unittest.TestCase):
    def test_a_snapshot_then_contributions_after_it_are_added(self) -> None:
        repo = SiteRepository()
        events = [("Alice", e) for e in (docked("2026-10-01T10:00:00Z"), depot("2026-10-01T10:01:00Z", 100),
                                          give("2026-10-01T10:05:00Z", 200), give("2026-10-01T10:06:00Z", 50))]
        catchup.apply_events(repo, events)
        self.assertEqual(provided(repo), 350)
        self.assertEqual(repo.get("Alice", MARKET).name, "Orbital Construction Site: X")

    def test_replaying_the_same_events_never_counts_a_delivery_twice(self) -> None:
        repo = SiteRepository()
        events = [("Alice", e) for e in (depot("2026-10-01T10:01:00Z", 100), give("2026-10-01T10:05:00Z", 200))]
        catchup.apply_events(repo, events)
        catchup.apply_events(repo, events)
        catchup.apply_events(repo, events[1:])
        self.assertEqual(provided(repo), 300)

    def test_contributions_older_than_a_newer_snapshot_are_not_added_on_top_of_it(self) -> None:
        repo = SiteRepository()
        catchup.apply_events(repo, [("Alice", depot("2026-10-01T12:00:00Z", 500))])
        catchup.apply_events(repo, [("Alice", give("2026-10-01T10:05:00Z", 200))])   # already inside that snapshot
        self.assertEqual(provided(repo), 500)

    def test_a_site_saved_before_journal_at_existed_uses_its_updated_time(self) -> None:
        repo = SiteRepository()
        site = colonisation.apply_depot_event(depot("2026-10-01T10:00:00Z", 300), None)
        site.journal_at = ""
        site.updated = "2026-10-01T12:00:00+00:00"
        repo.upsert("Alice", site)
        catchup.apply_events(repo, [("Alice", give("2026-10-01T11:00:00Z", 999)),     # before it: already counted
                                    ("Alice", give("2026-10-01T13:00:00Z", 50))])     # after it: new
        self.assertEqual(provided(repo), 350)

    def test_a_contribution_for_an_unknown_site_is_ignored_and_commanders_are_kept_apart(self) -> None:
        repo = SiteRepository()
        catchup.apply_events(repo, [("Alice", give("2026-10-01T10:05:00Z", 200))])
        self.assertIsNone(repo.get("Alice", MARKET))
        catchup.apply_events(repo, [("Alice", depot("2026-10-01T10:00:00Z", 10)), ("Bob", depot("2026-10-01T10:00:00Z", 20))])
        self.assertEqual((provided(repo, "Alice"), provided(repo, "Bob")), (10, 20))


class ReadJournalsTests(unittest.TestCase):
    def write(self, folder: str, name: str, events: list, age_hours: float = 0) -> None:
        path = os.path.join(folder, name)
        with open(path, "w", encoding="utf-8") as handle:
            for event in events:
                handle.write(json.dumps(event) + "\n")
        stamp = time.time() - age_hours * 3600
        os.utime(path, (stamp, stamp))

    def test_reads_the_commander_each_file_belongs_to_and_skips_old_files(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            self.write(folder, "Journal.1.log", [{"event": "Commander", "Name": "Alice"}, depot("2026-10-01T10:00:00Z", 1)],
                       age_hours=1)
            self.write(folder, "Journal.2.log", [{"event": "LoadGame", "Commander": "Bob"}, give("2026-10-02T10:00:00Z", 5)],
                       age_hours=0.5)
            self.write(folder, "Journal.old.log", [{"event": "Commander", "Name": "Carol"}, depot("2026-01-01T00:00:00Z")],
                       age_hours=24 * 90)
            events = catchup.read_since(time.time() - 24 * 3600 * 7, folder)
        self.assertEqual([(cmdr, e["event"]) for cmdr, e in events],
                         [("Alice", colonisation.EVENT_DEPOT), ("Bob", colonisation.EVENT_CONTRIBUTION)])

    def test_the_start_reaches_back_to_the_oldest_active_site_but_not_past_the_cap(self) -> None:
        repo = SiteRepository()
        now = datetime(2026, 10, 10, tzinfo=timezone.utc)
        site = colonisation.apply_depot_event(depot("2026-10-03T00:00:00Z"), None)
        repo.upsert("Alice", site)
        # A recent site does not shorten the default reach.
        self.assertEqual(catchup.start_epoch(repo, ["Alice"], now), (now - timedelta(days=catchup.DEFAULT_DAYS)).timestamp())
        quiet = colonisation.apply_depot_event(depot("2026-09-20T00:00:00Z"), None)   # untouched for 20 days: read from there
        quiet.market_id = 3
        repo.upsert("Alice", quiet)
        self.assertEqual(catchup.start_epoch(repo, ["Alice"], now), datetime(2026, 9, 20, tzinfo=timezone.utc).timestamp())
        old = colonisation.apply_depot_event(depot("2026-06-01T00:00:00Z"), None)
        old.market_id = 2
        repo.upsert("Alice", old)
        self.assertEqual(catchup.start_epoch(repo, ["Alice"], now), (now - timedelta(days=catchup.MAX_DAYS)).timestamp())


if __name__ == "__main__":
    unittest.main()
