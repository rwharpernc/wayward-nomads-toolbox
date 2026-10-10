"""
Tonnes transferred to the fleet carrier (colonisation_carrier.py): only transfers made docked at a fleet carrier count,
a transfer is never counted twice, and each commander's figures are their own.
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

from plugin import colonisation_carrier as cc  # noqa: E402


def docked(station_type: str = "FleetCarrier") -> dict:
    return {"event": "Docked", "StationType": station_type, "MarketID": 3700000001, "timestamp": "2026-10-01T10:00:00Z"}


def transfer(ts: str, *moves) -> dict:
    return {"event": "CargoTransfer", "timestamp": ts,
            "Transfers": [{"Type": t, "Count": n, "Direction": d} for t, n, d in moves]}


class CarrierCargoTests(unittest.TestCase):
    def setUp(self) -> None:
        self.cargo = cc.CarrierCargo()
        self.feed = cc.Feeder(self.cargo, "Alice")

    def test_net_tonnes_per_commodity(self) -> None:
        self.feed.feed(docked())
        self.feed.feed(transfer("2026-10-01T10:01:00Z", ("steel", 100, "tocarrier"), ("titanium", 40, "tocarrier")))
        self.feed.feed(transfer("2026-10-01T10:02:00Z", ("steel", 30, "toship")))
        self.assertEqual(self.cargo.tonnes("Alice"), {"steel": 70, "titanium": 40})
        self.assertTrue(self.cargo.has_carrier("Alice"))

    def test_never_below_zero(self) -> None:
        self.feed.feed(docked())
        self.feed.feed(transfer("2026-10-01T10:01:00Z", ("steel", 10, "tocarrier")))
        self.feed.feed(transfer("2026-10-01T10:02:00Z", ("steel", 50, "toship")))
        self.assertEqual(self.cargo.tonnes("Alice"), {})

    def test_ignored_away_from_a_fleet_carrier(self) -> None:
        self.feed.feed(docked("Orbis"))
        self.assertFalse(self.feed.feed(transfer("2026-10-01T10:01:00Z", ("steel", 10, "tocarrier"))))
        self.feed.feed(docked("SquadronCarrier"))
        self.feed.feed(transfer("2026-10-01T10:02:00Z", ("steel", 10, "tocarrier")))
        self.assertEqual(self.cargo.tonnes("Alice"), {})
        self.assertFalse(self.cargo.has_carrier("Alice"))

    def test_undock_stops_counting(self) -> None:
        self.feed.feed(docked())
        self.feed.feed({"event": "Undocked"})
        self.feed.feed(transfer("2026-10-01T10:01:00Z", ("steel", 10, "tocarrier")))
        self.assertEqual(self.cargo.tonnes("Alice"), {})

    def test_a_transfer_is_not_counted_twice(self) -> None:
        self.feed.feed(docked())
        event = transfer("2026-10-01T10:01:00Z", ("steel", 10, "tocarrier"))
        self.feed.feed(event)
        self.assertFalse(self.feed.feed(event))
        self.assertEqual(self.cargo.tonnes("Alice"), {"steel": 10})

    def test_commanders_are_separate(self) -> None:
        self.feed.feed(docked())
        self.feed.feed(transfer("2026-10-01T10:01:00Z", ("steel", 10, "tocarrier")))
        self.assertEqual(self.cargo.tonnes("Bob"), {})
        self.assertFalse(self.cargo.has_carrier("Bob"))
        self.assertEqual(self.cargo.tonnes("ALICE"), {"steel": 10})

    def test_carrier_stats_marks_a_carrier_without_transfers(self) -> None:
        self.feed.feed({"event": "CarrierStats", "CarrierType": "FleetCarrier"})
        self.feed.feed({"event": "CarrierStats", "CarrierType": "SquadronCarrier"})
        self.assertTrue(self.cargo.has_carrier("Alice"))
        self.assertEqual(self.cargo.tonnes("Alice"), {})

    def test_squadron_stats_alone_is_not_a_fleet_carrier(self) -> None:
        self.feed.feed({"event": "CarrierStats", "CarrierType": "SquadronCarrier"})
        self.assertFalse(self.cargo.has_carrier("Alice"))

    def test_saved_and_reloaded(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            self.cargo.load(folder)
            self.feed.feed(docked())
            self.feed.feed(transfer("2026-10-01T10:01:00Z", ("steel", 10, "tocarrier")))
            self.cargo.commit()
            again = cc.CarrierCargo()
            again.load(folder)
            self.assertEqual(again.tonnes("Alice"), {"steel": 10})
            self.assertTrue(again.has_carrier("Alice"))


class CatchUpTests(unittest.TestCase):
    def test_catch_up_then_live_event_does_not_double_count(self) -> None:
        lines = [
            {"event": "Commander", "Name": "Alice", "timestamp": "2026-10-01T09:59:00Z"},
            docked(),
            transfer("2026-10-01T10:01:00Z", ("steel", 25, "tocarrier")),
        ]
        with tempfile.TemporaryDirectory() as folder:
            with open(os.path.join(folder, "Journal.2026-10-01T090000.01.log"), "w", encoding="utf-8") as handle:
                handle.write("\n".join(json.dumps(line) for line in lines) + "\n")
            cargo = cc.CarrierCargo()
            self.assertEqual(cc.catch_up(cargo, ["Alice"], folder), 1)
            self.assertEqual(cargo.tonnes("Alice"), {"steel": 25})
            self.assertEqual(cc.catch_up(cargo, ["Alice"], folder), 0)   # a second pass over the same file adds nothing
            self.assertEqual(cargo.tonnes("Alice"), {"steel": 25})
            live = cc.Feeder(cargo, "Alice")
            live.feed(docked())
            self.assertFalse(live.feed(lines[2]))


if __name__ == "__main__":
    unittest.main()
