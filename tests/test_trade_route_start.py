"""Trade: the route start (last station docked at) is remembered per commander."""
import importlib
import sys
import unittest
from unittest import mock

# EDMC's own modules are not installed under test, so stand-ins are put in place just for these tests (and
# removed again, with the plugin modules imported against them, so nothing leaks into other tests).
_EDMC_MODULES = ("config", "theme", "myNotebook", "monitor", "ttkHyperlinkLabel", "edmc_data", "plug", "companion",
                 "EDMCLogging", "l10n", "timeout_session", "protocol", "prefs", "killswitch", "Tooltips", "ttkDefaults")


def docked(station: str, system: str, station_type: str = "Coriolis") -> dict:
    return {"event": "Docked", "StationName": station, "StarSystem": system, "StationType": station_type,
            "timestamp": "2026-10-10T10:00:00Z"}


class RouteStartPerCommanderTests(unittest.TestCase):
    def setUp(self) -> None:
        modules = mock.patch.dict(sys.modules, {name: mock.MagicMock(name=name) for name in _EDMC_MODULES})
        modules.start()
        self.addCleanup(modules.stop)
        for name in [m for m in sys.modules if m == "plugin" or m.startswith("plugin.")]:
            if name != "plugin":
                sys.modules.pop(name)   # re-import against the stand-ins; patch.dict restores the originals after
        trade_panel = importlib.import_module("plugin.trade_panel")
        self.panel = trade_panel.TradePanelController()
        patcher = mock.patch.multiple(
            self.panel, _merge_carrier_history=mock.DEFAULT, _remember_commander=mock.DEFAULT,
            _after_event=mock.DEFAULT, _save=mock.DEFAULT)
        patcher.start()
        self.addCleanup(patcher.stop)

    def dock(self, cmdr: str, station: str, system: str, station_type: str = "Coriolis") -> None:
        self.panel.handle_event(docked(station, system, station_type), cmdr, None, None, {})

    def test_each_commander_has_their_own_start(self) -> None:
        self.dock("Alice", "Jameson Memorial", "Shinrarta Dezhra")
        self.dock("Bob", "Abraham Lincoln", "Sol")
        self.panel._cmdr = "Alice"
        self.assertEqual(self.panel._route_start(), ("Shinrarta Dezhra", "Jameson Memorial"))
        self.panel._cmdr = "bob"   # case is ignored
        self.assertEqual(self.panel._route_start(), ("Sol", "Abraham Lincoln"))

    def test_new_commander_with_no_dock_has_no_start(self) -> None:
        self.dock("Alice", "Jameson Memorial", "Shinrarta Dezhra")
        self.panel._cmdr = "Carol"
        self.assertIsNone(self.panel._route_start())

    def test_carriers_never_become_a_start(self) -> None:
        self.dock("Alice", "Jameson Memorial", "Shinrarta Dezhra")
        self.dock("Alice", "ABC-123", "Sol", "FleetCarrier")
        self.panel._cmdr = "Alice"
        self.assertEqual(self.panel._route_start(), ("Shinrarta Dezhra", "Jameson Memorial"))


class RouteStartFileTests(unittest.TestCase):
    """The pure module has no EDMC dependency, so it is imported directly."""

    def test_round_trip_and_case_insensitive_key(self) -> None:
        import tempfile
        from plugin import trade_route_start as rs
        starts: rs.Starts = {}
        self.assertTrue(rs.remember(starts, "Alice", "Sol", "Abraham Lincoln", "2026-10-10T10:00:00Z"))
        self.assertFalse(rs.remember(starts, "ALICE", "Sol", "Abraham Lincoln", "2026-10-10T10:00:00Z"))   # same: no save
        self.assertTrue(rs.remember(starts, "alice", "Sol", "Galileo", "2026-10-10T11:00:00Z"))
        with tempfile.TemporaryDirectory() as folder:
            rs.save_all(folder, starts)
            loaded = rs.load_all(folder)
        self.assertEqual(rs.lookup(loaded, "Alice"), ("Sol", "Galileo"))
        self.assertIsNone(rs.lookup(loaded, "Bob"))

    def test_blank_values_and_bad_files_are_ignored(self) -> None:
        import json
        import os
        import tempfile
        from plugin import trade_route_start as rs
        starts: rs.Starts = {}
        self.assertFalse(rs.remember(starts, "", "Sol", "Galileo"))
        self.assertFalse(rs.remember(starts, "Alice", "", "Galileo"))
        self.assertFalse(rs.remember(starts, "Alice", "Sol", ""))
        with tempfile.TemporaryDirectory() as folder:
            self.assertEqual(rs.load_all(folder), {})   # no file
            path = os.path.join(folder, rs.STATE_FILENAME)
            with open(path, "w", encoding="utf-8") as handle:
                handle.write("not json")
            self.assertEqual(rs.load_all(folder), {})
            with open(path, "w", encoding="utf-8") as handle:
                json.dump({"alice": {"system": "Sol", "station": "Galileo"}, "bob": {"system": 3}, "carol": "x"}, handle)
            self.assertEqual(rs.lookup(rs.load_all(folder), "alice"), ("Sol", "Galileo"))   # no time saved: oldest
            self.assertEqual(len(rs.load_all(folder)), 1)


class RouteStartScanTests(unittest.TestCase):
    def events(self, *docks, cmdr: str = "Alice") -> list:
        out = [{"event": "Commander", "Name": cmdr}]
        for stamp, system, station, kind in docks:
            out.append({"event": "Docked", "timestamp": stamp, "StarSystem": system, "StationName": station,
                        "StationType": kind})
        return out

    def test_replay_takes_the_latest_real_dock_for_the_commander_in_the_file(self) -> None:
        from plugin import trade_route_start as rs
        starts: rs.Starts = {}
        events = self.events(("2026-10-09T10:00:00Z", "Sol", "Galileo", "Coriolis"),
                             ("2026-10-09T12:00:00Z", "Sol", "ABC-123", "FleetCarrier"),
                             ("2026-10-09T11:00:00Z", "Lave", "Lave Station", "Coriolis"))
        self.assertTrue(rs.replay(starts, events))
        self.assertEqual(rs.lookup(starts, "alice"), ("Lave", "Lave Station"))

    def test_docks_before_a_commander_is_named_are_not_guessed(self) -> None:
        from plugin import trade_route_start as rs
        starts: rs.Starts = {}
        events = [{"event": "Docked", "timestamp": "2026-10-09T10:00:00Z", "StarSystem": "Sol",
                   "StationName": "Galileo", "StationType": "Coriolis"}]
        self.assertFalse(rs.replay(starts, events))
        self.assertEqual(starts, {})

    def test_an_older_file_scanned_late_never_overwrites_a_newer_dock(self) -> None:
        from plugin import trade_route_start as rs
        starts: rs.Starts = {}
        rs.remember(starts, "Alice", "Lave", "Lave Station", "2026-10-10T09:00:00Z")   # live, newest
        old = self.events(("2026-10-08T10:00:00Z", "Sol", "Galileo", "Coriolis"))
        self.assertFalse(rs.replay(starts, old))
        self.assertEqual(rs.lookup(starts, "Alice"), ("Lave", "Lave Station"))
        newer = self.events(("2026-10-10T10:00:00Z", "Sol", "Galileo", "Coriolis"))
        self.assertTrue(rs.replay(starts, newer))
        self.assertEqual(rs.lookup(starts, "Alice"), ("Sol", "Galileo"))

    def test_the_journal_scan_applies_docks_when_given_the_start_book(self) -> None:
        from plugin import trade_journal_scan as scan, trade_stock
        from plugin import trade_route_start as rs
        starts: rs.Starts = {}
        events = self.events(("2026-10-09T10:00:00Z", "Sol", "Galileo", "Coriolis"))
        changed = scan.apply(events, {}, trade_stock.StockBook(), {}, starts)
        self.assertTrue(changed["route"])
        self.assertEqual(rs.lookup(starts, "Alice"), ("Sol", "Galileo"))
        self.assertNotIn("route", scan.apply(events, {}, trade_stock.StockBook(), {}))   # old call shape unchanged


if __name__ == "__main__":
    unittest.main()
