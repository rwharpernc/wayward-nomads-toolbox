"""
Megaship scans for the Powerplay cycle: the journal tracker (megaship_scans.py), the ledger's per-cycle list, the journal back-fill, the live
controller and the Megaships tab's rows. The sequences below follow real journals (the events and fields are the game's; the names are made up).

Pure logic, but the back-fill and controller need powerplay.py, which imports EDMC, so it is imported with stand-ins that are removed again afterwards.
Run with: python -m unittest discover -s tests
"""
from __future__ import annotations

import importlib
import os
import sys
import types
import unittest
from datetime import datetime, timezone
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

if "config" not in sys.modules:
    _stub = types.ModuleType("config")
    _stub.appname = "EDMarketConnector"  # type: ignore[attr-defined]
    _stub.config = types.SimpleNamespace(get_str=lambda *_a, **_k: "")  # type: ignore[attr-defined]
    sys.modules["config"] = _stub


class _Anything(types.ModuleType):
    def __getattr__(self, name: str):
        if name.startswith("__"):
            raise AttributeError(name)
        return mock.MagicMock(name=f"{self.__name__}.{name}")


import tkinter  # noqa: E402,F401  (imported before the stand-ins so the window code and the test share one tkinter, which the stand-ins
import tkinter.font  # noqa: E402,F401  would otherwise drop from sys.modules again)

_EDMC = ("theme", "myNotebook", "monitor", "ttkHyperlinkLabel", "edmc_data", "plug", "companion", "EDMCLogging",
         "l10n", "timeout_session", "protocol", "prefs", "killswitch", "Tooltips", "ttkDefaults", "requests")
import plugin as _plugin_package  # noqa: E402

_BEFORE = set(sys.modules)
with mock.patch.dict(sys.modules, {name: _Anything(name) for name in _EDMC}):
    powerplay = importlib.import_module("plugin.powerplay")
    backfill = importlib.import_module("plugin.powerplay_backfill")
    T = importlib.import_module("plugin.powerplay_megaships_tab")
    _ADDED = [name for name in sys.modules if name not in _BEFORE and name.startswith("plugin.")]
for _name in _ADDED:                                     # the package keeps an attribute for each submodule imported under the stand-ins; drop them
    _short = _name.split(".", 1)[1]
    if "." not in _short and hasattr(_plugin_package, _short):
        delattr(_plugin_package, _short)

from plugin import megaship_scans as M  # noqa: E402
from plugin import powerplay_ledger as L  # noqa: E402

ADDRESS = 5581410570970
SHIP = "ANU-880 Beckett-class Researcher"


def _ts(day=15, hour=12, minute=0, second=0, month=10):
    return f"2026-{month:02d}-{day:02d}T{hour:02d}:{minute:02d}:{second:02d}Z"


def jump(system="Jarogee", address=ADDRESS, **when):
    return {"timestamp": _ts(**when), "event": "FSDJump", "StarSystem": system, "SystemAddress": address}


def fss(name, kind="Megaship", **when):
    return {"timestamp": _ts(**when), "event": "FSSSignalDiscovered", "SystemAddress": ADDRESS, "SignalName": name, "SignalType": kind}


def drop(name, **when):
    return {"timestamp": _ts(**when), "event": "SupercruiseDestinationDrop", "Type": name, "Threat": 0}


def uplink(**when):
    return {"timestamp": _ts(**when), "event": "DataScanned", "Type": M.UPLINK, "Type_Localised": "Ship Uplink"}


def merits(gained=900, **when):
    return {"timestamp": _ts(**when), "event": "PowerplayMerits", "Power": "Denton Patreus", "MeritsGained": gained, "TotalMerits": 21109}


def run(tracker, entries):
    out = []
    for entry in entries:
        out.extend(tracker.feed(entry))
    return out


class TrackerTests(unittest.TestCase):
    def test_a_scan_at_a_megaship_is_named_from_the_destination_just_dropped_to(self):
        found = run(M.MegaShipTracker(), [jump(minute=0), drop(SHIP, minute=7), uplink(minute=9, second=5), merits(minute=9, second=6)])
        self.assertEqual([f[0] for f in found], ["scan", "merits"])
        scan = found[0][1]
        self.assertEqual((scan.name, scan.system, scan.address, scan.at, scan.merits), (SHIP, "Jarogee", ADDRESS, _ts(minute=9, second=5), 0))
        self.assertEqual(found[1][1:], (scan.key, 900, _ts(minute=9, second=6)))

    def test_what_is_not_a_megaship_is_not_counted(self):
        for destination in ("The Orion", "Newcomb Orbital", "Conflict Zone [High Intensity]", ""):
            found = run(M.MegaShipTracker(), [jump(), drop(destination), uplink(minute=5)])
            self.assertEqual(found, [], destination)

    def test_a_megaship_the_fss_listed_counts_without_the_word_class(self):
        found = run(M.MegaShipTracker(), [jump(), fss("Tour des Fiers"), drop("Tour des Fiers"), uplink(minute=5)])
        self.assertEqual(found[0][1].name, "Tour des Fiers")
        self.assertEqual(run(M.MegaShipTracker(), [jump(), fss("Newcomb Orbital", "StationONeilCylinder"), drop("Newcomb Orbital"), uplink()]), [])

    def test_spacing_and_case_in_the_name_do_not_matter(self):
        found = run(M.MegaShipTracker(), [jump(), fss("LHS 1110 I  Aquarius-class Tanker"), drop("LHS 1110 I Aquarius-class Tanker"), uplink()])
        self.assertEqual(found[0][1].name, "LHS 1110 I Aquarius-class Tanker")

    def test_no_destination_no_system_or_a_bad_timestamp_gives_nothing(self):
        self.assertEqual(run(M.MegaShipTracker(), [uplink()]), [])
        self.assertEqual(run(M.MegaShipTracker(), [drop(SHIP), uplink()]), [])           # no jump seen: the system is unknown
        self.assertEqual(run(M.MegaShipTracker(), [jump(), drop(SHIP), dict(uplink(), timestamp="soon")]), [])

    def test_leaving_supercruise_or_the_system_forgets_the_destination(self):
        after_entry = run(M.MegaShipTracker(), [jump(), drop(SHIP), {"timestamp": _ts(minute=2), "event": "SupercruiseEntry"}, uplink(minute=3)])
        self.assertEqual(after_entry, [])
        after_jump = run(M.MegaShipTracker(), [jump(), drop(SHIP), jump("Sol", 10477373803, minute=2), uplink(minute=3)])
        self.assertEqual(after_jump, [])

    def test_a_location_event_in_the_same_system_keeps_what_the_fss_found(self):
        tracker = M.MegaShipTracker()
        run(tracker, [jump(), fss("Tour des Fiers")])
        run(tracker, [dict(jump(minute=1), event="Location")])
        self.assertEqual(len(run(tracker, [drop("Tour des Fiers", minute=2), uplink(minute=3)])), 1)
        other = M.MegaShipTracker()
        run(other, [jump(), fss("Tour des Fiers"), jump("Sol", 10477373803, minute=1)])
        self.assertEqual(run(other, [drop("Tour des Fiers", minute=2), uplink(minute=3)]), [])

    def test_merits_count_only_within_a_few_seconds_of_the_scan(self):
        in_time = run(M.MegaShipTracker(), [jump(), drop(SHIP), uplink(minute=5), merits(minute=5, second=1), merits(300, minute=5, second=3)])
        self.assertEqual([f[2] for f in in_time if f[0] == "merits"], [900, 300])
        late = run(M.MegaShipTracker(), [jump(), drop(SHIP), uplink(minute=5), merits(minute=5, second=30)])
        self.assertEqual([f[0] for f in late], ["scan"])
        stray = run(M.MegaShipTracker(), [jump(), merits(minute=5)])
        self.assertEqual(stray, [])

    def test_a_zero_or_malformed_merit_event_is_ignored(self):
        for gained in (0, -5, "900", None, True):
            found = run(M.MegaShipTracker(), [jump(), drop(SHIP), uplink(minute=5), dict(merits(minute=5, second=1), MeritsGained=gained)])
            self.assertEqual([f[0] for f in found], ["scan"], gained)

    def test_junk_entries_never_raise(self):
        tracker = M.MegaShipTracker()
        for entry in ({}, {"event": 5}, {"event": "FSDJump"}, {"event": "FSDJump", "SystemAddress": "x", "StarSystem": None},
                      {"event": "SupercruiseDestinationDrop"}, {"event": "FSSSignalDiscovered"}, {"event": "PowerplayMerits"}):
            tracker.feed(entry)


class ScanTests(unittest.TestCase):
    def test_a_scan_round_trips_and_bad_data_is_refused(self):
        scan = M.MegaShipScan(SHIP, "Jarogee", ADDRESS, _ts(), 900, _ts(second=1))
        self.assertEqual(M.MegaShipScan.from_dict(scan.to_dict()), scan)
        for bad in (None, {}, {"name": "", "system": "x", "at": _ts()}, {"name": "x", "system": "y", "at": "never"}, {"name": 1, "system": "y", "at": _ts()}):
            self.assertIsNone(M.MegaShipScan.from_dict(bad))
        clean = M.MegaShipScan.from_dict({"name": "x", "system": "y", "at": _ts(), "address": True, "merits": -3, "merit_at": "?"})
        self.assertEqual((clean.address, clean.merits, clean.merit_at), (0, 0, ""))

    def test_the_key_is_one_megaship_in_one_system(self):
        a = M.MegaShipScan("Tour  des Fiers", "Laguz", 1, _ts())
        b = M.MegaShipScan("tour des fiers", "Laguz", 1, _ts(day=16))
        self.assertEqual(a.key, b.key)
        self.assertNotEqual(a.key, M.MegaShipScan("tour des fiers", "Laguz", 2, _ts()).key)


def scan(name=SHIP, system="Jarogee", at=None, merits_=0, address=ADDRESS):
    return M.MegaShipScan(name, system, address, at or _ts(day=15), merits_)


class LedgerTests(unittest.TestCase):
    THURSDAY = "2026-10-15T07:00:00Z"            # cycle 103 began here

    def test_a_scan_is_kept_once_per_megaship_per_cycle(self):
        ledger = L.PowerplayLedger()
        self.assertTrue(ledger.record_megaship(scan()))
        self.assertFalse(ledger.record_megaship(scan(at=_ts(day=16))))              # the same megaship again
        self.assertTrue(ledger.record_megaship(scan("Other-class Hauler")))
        self.assertTrue(ledger.record_megaship(scan(system="Sol", address=1)))      # the same name in another system
        self.assertEqual(len(ledger.megaships), 3)
        self.assertEqual(ledger.live_view().megaships[0].name, SHIP)

    def test_unusable_scans_are_ignored(self):
        ledger = L.PowerplayLedger()
        self.assertFalse(ledger.record_megaship(M.MegaShipScan("", "Sol", 1, _ts())))
        self.assertFalse(ledger.record_megaship(M.MegaShipScan("x", "", 1, _ts())))
        self.assertFalse(ledger.record_megaship(M.MegaShipScan("x", "Sol", 1, "never")))
        ledger.record_megaship(scan())
        self.assertFalse(ledger.record_megaship(scan("Earlier-class Hauler", at=_ts(day=14))))     # before this cycle began
        self.assertEqual(len(ledger.megaships), 1)

    def test_merits_are_added_to_their_scan_and_a_replay_adds_nothing(self):
        ledger = L.PowerplayLedger()
        first = scan()
        ledger.record_megaship(first)
        self.assertTrue(ledger.add_megaship_merits(first.key, 900, _ts(second=1)))
        self.assertFalse(ledger.add_megaship_merits(first.key, 900, _ts(second=1)))            # the same event seen again
        self.assertTrue(ledger.add_megaship_merits(first.key, 100, _ts(second=3)))
        self.assertEqual(ledger.megaships[0].merits, 1000)
        for bad in (0, -1, True, "9"):
            self.assertFalse(ledger.add_megaship_merits(first.key, bad, _ts(second=9)))
        self.assertFalse(ledger.add_megaship_merits(("nobody", 1), 50, _ts(second=9)))
        self.assertEqual(ledger.live_view().megaship_merits(), 1000)

    def test_a_new_cycle_archives_the_old_scans_and_starts_empty(self):
        ledger = L.PowerplayLedger()
        ledger.record_megaship(scan(at="2026-10-15T08:00:00Z"))
        self.assertTrue(ledger.record_megaship(scan(at="2026-10-22T08:00:00Z")))               # the next Thursday 07:00 started cycle 104
        self.assertEqual(len(ledger.megaships), 1)
        self.assertEqual(len(ledger.archive), 1)
        archived = L.view_from_archive(ledger.archive[0])
        self.assertEqual([s.name for s in archived.megaships], [SHIP])
        self.assertEqual([v.current for v in ledger.views()][0], True)

    def test_scans_survive_saving_and_loading(self):
        ledger = L.PowerplayLedger()
        ledger.record_megaship(scan(merits_=0))
        ledger.add_megaship_merits(ledger.megaships[0].key, 900, _ts(second=1))
        again = L.PowerplayLedger.from_dict(ledger.to_dict())
        self.assertEqual([s.to_dict() for s in again.megaships], [s.to_dict() for s in ledger.megaships])
        self.assertEqual(L.PowerplayLedger.from_dict({"megaships": "junk"}).megaships, [])
        self.assertEqual(L.PowerplayLedger.from_dict({"megaships": [None, 5, {"name": "x"}]}).megaships, [])

    def test_a_ledger_from_before_megaships_is_rebuilt_from_the_journals(self):
        ledger = L.PowerplayLedger()
        ledger.schema = 2
        ledger.covered_from = datetime(2026, 9, 1, tzinfo=timezone.utc)
        ledger.seen_to = _ts()
        plan = ledger.plan_scan(datetime(2026, 10, 15, 12, tzinfo=timezone.utc))
        self.assertEqual(plan.mode, L.SCAN_REBUILD)

    def test_adopting_a_rebuild_never_loses_a_live_scan_or_its_merits(self):
        live = L.PowerplayLedger()
        live.record_megaship(scan(at="2026-10-15T09:00:00Z"))
        live.add_megaship_merits(live.megaships[0].key, 900, "2026-10-15T09:00:01Z")
        fresh = L.PowerplayLedger()
        fresh.record_megaship(scan(at="2026-10-15T09:00:00Z"))
        fresh.record_megaship(scan("Other-class Hauler", at="2026-10-15T10:00:00Z"))
        live.adopt(fresh, datetime(2026, 9, 17, 7, tzinfo=timezone.utc), "2026-10-15T10:00:00Z")
        self.assertEqual({s.name: s.merits for s in live.megaships}, {SHIP: 900, "Other-class Hauler": 0})

    def test_the_cycle_holds_at_most_so_many_scans(self):
        ledger = L.PowerplayLedger()
        for number in range(L.MAX_MEGASHIPS + 5):
            ledger.record_megaship(scan(f"S{number}-class Hauler", at=_ts(day=15, hour=8) ))
        self.assertEqual(len(ledger.megaships), L.MAX_MEGASHIPS)


class BackfillTests(unittest.TestCase):
    def entries(self, cmdr="Bocheaux"):
        return [
            {"timestamp": _ts(hour=9), "event": "Fileheader"},
            {"timestamp": _ts(hour=9), "event": "Commander", "Name": cmdr},
            jump(hour=10),
            fss(SHIP, hour=10),
            drop(SHIP, hour=11),
            uplink(hour=11, minute=2),
            merits(hour=11, minute=2, second=1),
            drop("Other-class Hauler", hour=12),                 # a second megaship, no scan
        ]

    def replay(self, entries, cmdr="Bocheaux", scan_from=None):
        return backfill.replay_entries(entries, cmdr, powerplay.PowerplayTracker, scan_from)

    def test_the_replay_finds_the_scan_and_its_merits(self):
        result = self.replay(self.entries())
        kinds = [op.kind for op in result.ops if op.kind.startswith("megaship")]
        self.assertEqual(kinds, [backfill.OP_MEGASHIP, backfill.OP_MEGASHIP_MERITS])
        ledger = backfill.rebuild_ledger(result.ops)
        self.assertEqual([(s.name, s.system, s.merits) for s in ledger.megaships], [(SHIP, "Jarogee", 900)])

    def test_applying_the_same_ops_twice_counts_once(self):
        ops = self.replay(self.entries()).ops
        ledger = backfill.rebuild_ledger(ops)
        backfill.apply_ops(ledger, ops)
        self.assertEqual([(len(ledger.megaships), ledger.megaships[0].merits)], [(1, 900)])

    def test_only_the_scan_window_becomes_ops_but_the_state_before_it_is_used(self):
        late = datetime(2026, 10, 15, 11, 1, tzinfo=timezone.utc)                       # after the drop's destination was learned? no: before it
        early = datetime(2026, 10, 15, 11, 30, tzinfo=timezone.utc)
        self.assertEqual([op for op in self.replay(self.entries(), scan_from=early).ops if op.kind.startswith("megaship")], [])
        self.assertEqual(len([op for op in self.replay(self.entries(), scan_from=late).ops if op.kind.startswith("megaship")]), 2)

    def test_another_commanders_scans_are_not_taken(self):
        self.assertEqual([op for op in self.replay(self.entries("Mactavious"), cmdr="Bocheaux").ops if op.kind.startswith("megaship")], [])

    def test_a_new_file_does_not_carry_the_last_files_destination(self):
        first = self.entries()[:5]                                           # ends after dropping at the megaship
        second = [{"timestamp": _ts(day=16, hour=9), "event": "Fileheader"}, {"timestamp": _ts(day=16, hour=9), "event": "Commander", "Name": "Bocheaux"},
                  uplink(day=16, hour=9, minute=5)]
        self.assertEqual([op for op in self.replay(first + second).ops if op.kind.startswith("megaship")], [])

    def test_the_scan_reads_only_the_lines_it_needs(self):
        needles = backfill._NEEDLES
        for line in ('{"event":"FSSSignalDiscovered", "SignalType":"Megaship"}', '{"event":"DataScanned", "Type":"$Datascan_ShipUplink;"}',
                     '{"event":"SupercruiseDestinationDrop"}', '{"event":"SupercruiseEntry"}'):
            self.assertTrue(any(n in line for n in needles), line)
        self.assertFalse(any(n in '{"event":"FSSSignalDiscovered", "SignalType":"Combat"}' for n in needles))


class ControllerTests(unittest.TestCase):
    def controller(self):
        c = powerplay.PowerplayController()
        c.sessions = mock.MagicMock()
        c._cmdr = "Bocheaux"
        c._scan_running = False
        c._dispatch = mock.MagicMock()
        c._refresh_panel = mock.MagicMock()
        c._persist_ledger = mock.MagicMock()
        c._tick_cycle = mock.MagicMock()
        c._poll_scan = mock.MagicMock()
        return c

    def test_live_events_fill_the_ledger(self):
        c = self.controller()
        c.ledger.cycle_start = datetime(2026, 10, 15, 7, tzinfo=timezone.utc)
        for entry in (jump(hour=10), drop(SHIP, hour=11), uplink(hour=11, minute=2), merits(hour=11, minute=2, second=1)):
            c.handle_event(entry, "Bocheaux", "Jarogee", None, {})
        self.assertEqual([(s.name, s.merits) for s in c.ledger.megaships], [(SHIP, 900)])
        self.assertEqual(powerplay._megaship_line(c.ledger.live_view()), "Cycle 103 megaships: 1 (900 merits)")

    def test_events_held_during_a_journal_scan_are_applied_after_it(self):
        c = self.controller()
        c._scan_running = True
        for entry in (jump(hour=10), drop(SHIP, hour=11), uplink(hour=11, minute=2)):
            c.handle_event(entry, "Bocheaux", "Jarogee", None, {})
        self.assertEqual(c.ledger.megaships, [])
        self.assertEqual([op.kind for op in c._scan_buffer], [backfill.OP_MEGASHIP])

    def test_the_panel_line_with_no_scans_and_no_merits(self):
        ledger = L.PowerplayLedger()
        ledger.cycle_start = datetime(2026, 10, 15, 7, tzinfo=timezone.utc)
        self.assertEqual(powerplay._megaship_line(ledger.live_view()), "Cycle 103 megaships: 0")
        ledger.record_megaship(scan())
        self.assertEqual(powerplay._megaship_line(ledger.live_view()), "Cycle 103 megaships: 1")


class TabTests(unittest.TestCase):
    def views(self):
        ledger = L.PowerplayLedger()
        ledger.record_megaship(scan(at="2026-10-15T08:00:00Z"))
        ledger.add_megaship_merits(ledger.megaships[0].key, 900, "2026-10-15T08:00:01Z")
        ledger.record_megaship(scan("Other-class Hauler", "Sol", at="2026-10-16T09:30:00Z", address=2))
        ledger.record_megaship(scan("Next-class Tanker", at="2026-10-22T09:00:00Z"))          # cycle 103: the first two go to the archive
        return ledger.views()

    def test_rows_put_the_live_cycle_first_and_the_latest_scan_first(self):
        rows = T.rows(self.views())
        self.assertEqual([r[1] for r in rows], ["Next-class Tanker", "Other-class Hauler", SHIP])
        self.assertEqual(rows[0][0], "Cycle 104 (live)")
        self.assertEqual(rows[2], ("Cycle 103", SHIP, "Jarogee", "2026-10-15 08:00", "900"))
        self.assertEqual(rows[1][4], "")

    def test_summary_names_the_live_cycle_and_counts_the_rest(self):
        self.assertEqual(T.summary(self.views()), "Cycle 104: 1 megaship. Earlier cycles: 2 megaships.")
        self.assertEqual(T.summary([]), "")
        ledger = L.PowerplayLedger()
        ledger.cycle_start = datetime(2026, 10, 15, 7, tzinfo=timezone.utc)
        ledger.record_megaship(scan(at="2026-10-15T08:00:00Z"))
        ledger.add_megaship_merits(ledger.megaships[0].key, 1200, "2026-10-15T08:00:01Z")
        self.assertEqual(T.summary(ledger.views()), "Cycle 103: 1 megaship, 1,200 merits.")


class TabWindowTests(unittest.TestCase):
    def test_the_tab_builds_and_shows_the_rows(self):
        import tkinter as tk
        try:
            root = tk.Tk()
        except tk.TclError:
            self.skipTest("Tk has no display here")
        self.addCleanup(root.destroy)
        tab = T.MegaShipsTab(tk.Frame(root))
        views = TabTests().views()
        tab.update(types.SimpleNamespace(views=lambda: views, status=lambda: "scan status"))
        root.update_idletasks()
        self.assertEqual(len(tab._table), 3)
        self.assertEqual(tab._summary.cget("text"), "Cycle 104: 1 megaship. Earlier cycles: 2 megaships.")
        tab.update(types.SimpleNamespace(views=lambda: [], status=lambda: ""))
        self.assertEqual(len(tab._table), 0)
        tab.update(None)                                           # no data yet: nothing changes, nothing raises


if __name__ == "__main__":
    unittest.main()
