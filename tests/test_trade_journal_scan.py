"""Journal scan: files copied over from the other computer are found, read once, folded in, and remembered."""
from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from plugin import trade_journal_scan as scan  # noqa: E402
from plugin import trade_carrier as carrier  # noqa: E402
from plugin import trade_ledger as ledger_mod  # noqa: E402
from plugin import trade_stock  # noqa: E402

CARRIER_ID = 3707024384


def write(folder: str, name: str, events: list) -> str:
    path = os.path.join(folder, name)
    with open(path, "w", encoding="utf-8") as handle:
        for event in events:
            handle.write(json.dumps(event, separators=(",", ":")) + "\n")
            handle.write(json.dumps({"timestamp": event["timestamp"], "event": "Music"}) + "\n")
    return path


def header(stamp: str) -> list:
    return [{"timestamp": stamp, "event": "Fileheader"},
            {"timestamp": stamp, "event": "Commander", "Name": "BOCHEAUX"},
            {"timestamp": stamp, "event": "LoadGame", "Commander": "BOCHEAUX", "Credits": 1_000}]


def windows_file() -> list:
    """A Windows play session: dock at a carrier, a baseline, one load in, a purchase and a sale."""
    return header("2026-10-09T10:00:00Z") + [
        {"timestamp": "2026-10-09T10:01:00Z", "event": "Docked", "StarSystem": "Sol", "StationName": "Daedalus",
         "MarketID": 5, "StationType": "Orbis"},
        {"timestamp": "2026-10-09T10:02:00Z", "event": "MarketBuy", "Type": "gold", "Count": 10, "TotalCost": 1000},
        {"timestamp": "2026-10-09T10:03:00Z", "event": "MarketSell", "Type": "gold", "Count": 4, "TotalSale": 800,
         "AvgPricePaid": 100, "SellPrice": 200},
        {"timestamp": "2026-10-09T10:04:00Z", "event": "Docked", "StarSystem": "Sol", "StationName": "WLF-LXW",
         "MarketID": CARRIER_ID, "StationType": "FleetCarrier"},
        {"timestamp": "2026-10-09T10:05:00Z", "event": "CarrierStats", "CarrierID": CARRIER_ID, "CarrierType": "FleetCarrier",
         "SpaceUsage": {"TotalCapacity": 25_000, "Crew": 1_280, "Cargo": 5_060, "CargoSpaceReserved": 0, "ShipPacks": 0,
                        "ModulePacks": 0, "FreeSpace": 18_660}},
        {"timestamp": "2026-10-09T10:06:00Z", "event": "CargoTransfer",
         "Transfers": [{"Type": "gold", "Count": 100, "Direction": "tocarrier"}]},
    ]


class PendingTests(unittest.TestCase):
    def test_new_files_are_found_once_and_a_grown_file_again(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            first = write(folder, "Journal.2026-10-09T100000.01.log", windows_file())
            registry = scan.new_registry()
            found = scan.pending(folder, registry)
            self.assertEqual([p for p, _s in found], [first])
            scan.mark(registry, first, found[0][1])
            self.assertEqual(scan.pending(folder, registry), [])
            os.utime(first, (1, 1))                       # copied again: new modified time, same content
            self.assertEqual(scan.pending(folder, registry), [])
            with open(first, "a", encoding="utf-8") as handle:
                handle.write('{"timestamp":"2026-10-09T11:00:00Z","event":"Music"}\n')
            self.assertEqual([p for p, _s in scan.pending(folder, registry)], [first])

    def test_the_file_being_played_is_left_alone_and_other_files_are_ignored(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            playing = write(folder, "Journal.2026-10-09T100000.01.log", windows_file())
            write(folder, "Status.json", [{"timestamp": "x"}])
            self.assertEqual(scan.pending(folder, scan.new_registry(), skip=playing), [])

    def test_files_are_read_oldest_first_by_their_own_first_timestamp(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            newer = write(folder, "Journal.2026-10-10T000000.01.log", header("2026-10-10T00:00:00Z"))
            older = write(folder, "Journal.2026-10-09T000000.01.log", header("2026-10-09T00:00:00Z"))
            os.utime(older, (2_000_000_000, 2_000_000_000))    # a sync gave the older file the later modified time
            self.assertEqual([p for p, _s in scan.pending(folder, scan.new_registry())], [older, newer])

    def test_a_first_pass_takes_only_the_newest_files(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            for day in range(1, 6):
                path = write(folder, f"Journal.2026-10-0{day}T000000.01.log", header(f"2026-10-0{day}T00:00:00Z"))
                os.utime(path, (day * 1000, day * 1000))
            names = [os.path.basename(p) for p, _s in scan.pending(folder, scan.new_registry(), limit=2)]
            self.assertEqual(names, ["Journal.2026-10-04T000000.01.log", "Journal.2026-10-05T000000.01.log"])

    def test_old_history_is_never_crawled_after_the_first_pass(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            for day in range(1, 6):
                path = write(folder, f"Journal.2026-10-0{day}T000000.01.log", header(f"2026-10-0{day}T00:00:00Z"))
                os.utime(path, (day * 1000, day * 1000))
            registry = scan.new_registry()
            first = scan.pending(folder, registry, limit=2)
            for path, size in first:
                scan.mark(registry, path, size)
            self.assertEqual(scan.pending(folder, registry, limit=2), [])    # days 1-3 are older than the floor
            late = write(folder, "Journal.2026-10-06T000000.01.log", header("2026-10-06T00:00:00Z"))
            self.assertEqual([p for p, _s in scan.pending(folder, registry, limit=2)], [late])

    def test_the_record_round_trips_and_survives_a_bad_file(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            registry = scan.new_registry()
            scan.mark(registry, os.path.join(folder, "Journal.a.log"), 123)
            scan.note_pass(registry, 1)
            scan.save(folder, registry)
            self.assertEqual(scan.load(folder)["files"]["Journal.a.log"]["size"], 123)
            with open(os.path.join(folder, scan.STATE_FILENAME), "w", encoding="utf-8") as handle:
                handle.write("[not json")
            self.assertEqual(scan.load(folder), scan.new_registry())
        self.assertIn("not scanned", scan.summary(scan.new_registry()))
        self.assertIn("1 file(s)", scan.summary(registry))


class ApplyTests(unittest.TestCase):
    def _state(self):
        ledger = ledger_mod.new_ledger("Bocheaux", None, started="2026-10-09T09:00:00Z")
        return {"bocheaux": ledger}, trade_stock.StockBook(), {}

    def test_a_copied_session_reaches_the_ledger_the_stock_and_the_carrier(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            path = write(folder, "Journal.2026-10-09T100000.01.log", windows_file())
            ledgers, stock, records = self._state()
            changed = scan.apply(scan.read_events(path), ledgers, stock, records)
            self.assertEqual(changed, {"ledger": True, "stock": True, "carrier": True})
            self.assertEqual(ledgers["bocheaux"]["rows"]["gold"]["sold"] if "gold" in ledgers["bocheaux"]["rows"]
                             else ledgers["bocheaux"]["rows"]["Gold"]["sold"], 4)
            self.assertEqual(stock.holdings("Bocheaux")[0].tonnes, 6)
            record = records["bocheaux"][carrier.FLEET]
            self.assertEqual((record["cargo"], record["free"]), (5_160, 18_560))   # baseline 5,060 + 100 loaded after it

    def test_applying_the_same_file_twice_counts_nothing_twice(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            path = write(folder, "Journal.2026-10-09T100000.01.log", windows_file())
            ledgers, stock, records = self._state()
            events = scan.read_events(path)
            scan.apply(events, ledgers, stock, records)
            again = scan.apply(events, ledgers, stock, records)
            self.assertEqual(again, {"ledger": False, "stock": False, "carrier": False})
            self.assertEqual(stock.holdings("Bocheaux")[0].tonnes, 6)
            self.assertEqual(records["bocheaux"][carrier.FLEET]["cargo"], 5_160)

    def test_an_older_file_arriving_late_never_overwrites_newer_figures(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            old = write(folder, "Journal.2026-10-09T100000.01.log", windows_file())
            later = header("2026-10-10T08:00:00Z") + [
                {"timestamp": "2026-10-10T08:03:45Z", "event": "CarrierStats", "CarrierID": CARRIER_ID,
                 "CarrierType": "FleetCarrier", "SpaceUsage": {"TotalCapacity": 25_000, "Crew": 1_280, "Cargo": 7_000,
                                                               "CargoSpaceReserved": 0, "ShipPacks": 0, "ModulePacks": 0,
                                                               "FreeSpace": 16_720}}]
            new = write(folder, "Journal.2026-10-10T080000.01.log", later)
            ledgers, stock, records = self._state()
            scan.apply(scan.read_events(new), ledgers, stock, records)
            scan.apply(scan.read_events(old), ledgers, stock, records)
            self.assertEqual(records["bocheaux"][carrier.FLEET]["cargo"], 7_000)

    def test_a_session_with_no_starting_point_is_left_alone(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            path = write(folder, "Journal.2026-10-09T100000.01.log", windows_file())
            ledger = ledger_mod.new_ledger("Bocheaux", None)
            scan.apply(scan.read_events(path), {"bocheaux": ledger}, trade_stock.StockBook(), {})
            self.assertEqual(ledger["rows"], {})


if __name__ == "__main__":
    unittest.main()
