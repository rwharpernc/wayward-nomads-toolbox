"""
Unit tests for plugin/powerplay_backfill.py and the scan planning in powerplay_ledger.py.

Pure logic - no EDMC runtime needed. The replay needs powerplay.PowerplayTracker, which lives in a module
that imports EDMC; it is imported here with stand-ins for those modules (removed again afterwards so
nothing leaks into other tests). Run with:
    python -m unittest discover -s tests
"""

from __future__ import annotations

import importlib
import json
import os
import sys
import tempfile
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


_EDMC = ("theme", "myNotebook", "monitor", "ttkHyperlinkLabel", "edmc_data", "plug", "companion", "EDMCLogging",
         "l10n", "timeout_session", "protocol", "prefs", "killswitch", "Tooltips", "ttkDefaults", "requests")
with mock.patch.dict(sys.modules, {name: _Anything(name) for name in _EDMC}):
    powerplay = importlib.import_module("plugin.powerplay")
    backfill = importlib.import_module("plugin.powerplay_backfill")

from plugin import powerplay_ledger as L  # noqa: E402
from plugin.formulas import REINFORCEMENT, UNDERMINING  # noqa: E402

ME = "Pranav Antal"
THU_101 = "2026-10-01T07:00:00Z"


def _ts(day: int, hour: int = 12, minute: int = 0, month: int = 10) -> str:
    return f"2026-{month:02d}-{day:02d}T{hour:02d}:{minute:02d}:00Z"


def _session(cmdr: str = "Bocheaux", *, power: str = ME, controller: str = ME, ts_day: int = 2,
             merits=((12, 100),), jump_hour: int = 10) -> list:
    """One game launch for `cmdr`: pledge, a jump into a system `controller` holds, then merit gains."""
    entries = [
        {"timestamp": _ts(ts_day, 9), "event": "Fileheader"},
        {"timestamp": _ts(ts_day, 9), "event": "Commander", "Name": cmdr},
        {"timestamp": _ts(ts_day, 9), "event": "LoadGame", "Commander": cmdr},
        {"timestamp": _ts(ts_day, 9), "event": "Powerplay", "Power": power, "Rank": 10, "Merits": 5},
        {"timestamp": _ts(ts_day, jump_hour), "event": "FSDJump", "StarSystem": "Ngurii", "PowerplayState": "Fortified",
         "ControllingPower": controller, "Powers": [controller], "PowerplayStateControlProgress": 0.4,
         "PowerplayStateReinforcement": 10, "PowerplayStateUndermining": 5},
    ]
    for hour, gained in merits:
        entries.append({"timestamp": _ts(ts_day, hour), "event": "PowerplayMerits", "Power": power,
                        "MeritsGained": gained, "TotalMerits": 1000 + gained})
    return entries


def _replay(entries, cmdr="Bocheaux", scan_from=None):
    return backfill.replay_entries(entries, cmdr, powerplay.PowerplayTracker, scan_from)


class ReplayTests(unittest.TestCase):
    def test_merits_are_attributed_from_the_system_context(self):
        result = _replay(_session())
        merits = [op for op in result.ops if op.kind == backfill.OP_MERITS]
        self.assertEqual([(m.system, m.activity, m.merits) for m in merits], [("Ngurii", REINFORCEMENT, 100)])
        self.assertEqual([op.kind for op in result.ops].count(backfill.OP_SNAPSHOT), 1)
        self.assertEqual(next(op for op in result.ops if op.kind == backfill.OP_POWER).power, ME)

    def test_a_rival_controlled_system_is_undermining(self):
        merits = [op for op in _replay(_session(controller="Aisling Duval")).ops if op.kind == backfill.OP_MERITS]
        self.assertEqual(merits[0].activity, UNDERMINING)

    def test_other_commanders_are_ignored(self):
        self.assertEqual(_replay(_session("Mactavious")).ops, [])
        both = _session("Mactavious", merits=((12, 7),)) + _session("Bocheaux", merits=((13, 100),), ts_day=3)
        merits = [op for op in _replay(both).ops if op.kind == backfill.OP_MERITS]
        self.assertEqual([m.merits for m in merits], [100])

    def test_commander_switch_inside_one_file(self):
        entries = _session("Mactavious", power="Aisling Duval", controller="Aisling Duval", merits=((12, 7),))
        entries += [
            {"timestamp": _ts(2, 14), "event": "LoadGame", "Commander": "Bocheaux"},
            {"timestamp": _ts(2, 15), "event": "PowerplayMerits", "Power": ME, "MeritsGained": 50, "TotalMerits": 2000},
        ]
        result = _replay(entries, "Bocheaux")
        merits = [op for op in result.ops if op.kind == backfill.OP_MERITS]
        # no system context for this commander yet -> no system, so nothing to record; and nothing of
        # the other commander's leaks in
        self.assertEqual(merits, [])
        self.assertEqual(_replay(entries, "Mactavious").ops[-1].merits, 7)

    def test_events_before_the_window_still_set_the_context_but_make_no_ops(self):
        entries = _session(merits=((8, 40), (20, 60)))
        result = _replay(entries, scan_from=L.parse_ts(_ts(2, 12)))
        merits = [op for op in result.ops if op.kind == backfill.OP_MERITS]
        self.assertEqual([(m.merits, m.activity) for m in merits], [(60, REINFORCEMENT)])  # pledge + system known
        self.assertEqual(result.last_ts, _ts(2, 20))

    def test_not_pledged_commander_gets_standing_but_no_power(self):
        entries = [e for e in _session() if e["event"] not in ("Powerplay", "PowerplayMerits")]
        result = _replay(entries)
        self.assertEqual([op.kind for op in result.ops], [backfill.OP_SNAPSHOT])

    def test_new_file_resets_the_pledge(self):
        entries = _session() + [
            {"timestamp": _ts(3, 9), "event": "Fileheader"},
            {"timestamp": _ts(3, 9), "event": "Commander", "Name": "Bocheaux"},
            {"timestamp": _ts(3, 10), "event": "PowerplayMerits", "Power": ME, "MeritsGained": 5, "TotalMerits": 9},
        ]
        merits = [op for op in _replay(entries).ops if op.kind == backfill.OP_MERITS]
        self.assertEqual(len(merits), 1)   # the second file has no system context: nothing attributable


class ApplyTests(unittest.TestCase):
    def test_applying_twice_never_double_counts(self):
        ops = _replay(_session(merits=((12, 100), (13, 50)))).ops
        ledger = L.PowerplayLedger()
        backfill.apply_ops(ledger, ops)
        backfill.apply_ops(ledger, ops)
        self.assertEqual(ledger.records["ngurii"].total_merits(), 150)
        self.assertEqual(ledger.powers, [ME])

    def test_replay_after_live_play_only_adds_what_is_new(self):
        ops = _replay(_session(merits=((12, 100), (13, 50), (14, 25)))).ops
        ledger = L.PowerplayLedger()
        ledger.record_merits("Ngurii", REINFORCEMENT, 100, _ts(2, 12))   # counted live
        ledger.record_merits("Ngurii", REINFORCEMENT, 50, _ts(2, 13))
        backfill.apply_ops(ledger, ops)
        self.assertEqual(ledger.records["ngurii"].total_merits(), 175)

    def test_same_second_merits_are_both_counted_live_and_not_repeated_by_a_replay(self):
        ledger = L.PowerplayLedger()
        stamp = _ts(2, 12)
        self.assertTrue(ledger.record_merits("Ngurii", REINFORCEMENT, 10, stamp))
        self.assertTrue(ledger.record_merits("Ngurii", REINFORCEMENT, 20, stamp))
        replayed = [backfill.Op(backfill.OP_MERITS, stamp, system="Ngurii", activity=REINFORCEMENT, merits=m)
                    for m in (10, 20, 30)]
        backfill.apply_ops(ledger, replayed)
        self.assertEqual(ledger.records["ngurii"].total_merits(), 60)   # 10 + 20 + the new 30

    def test_a_gap_over_a_cycle_boundary_lands_in_the_right_cycles(self):
        # EDMC last saw the journal Wed 7 Oct (cycle 101); the commander then played that evening and
        # on Fri 9 Oct (cycle 102) with EDMC closed.
        ledger = L.PowerplayLedger()
        ledger.record_merits("Ngurii", REINFORCEMENT, 100, _ts(6, 12))
        ledger.touch(_ts(6, 12))
        ops = (_replay(_session(ts_day=7, merits=((20, 40),))).ops + _replay(_session(ts_day=9, merits=((12, 70),))).ops)
        backfill.apply_ops(ledger, ops)
        ledger.roll_to(datetime(2026, 10, 9, 18, tzinfo=timezone.utc))
        self.assertEqual([r["cycle_start"] for r in ledger.archive], ["2026-10-01T07:00:00Z"])
        self.assertEqual(L.view_from_archive(ledger.archive[0]).record_for("Ngurii").total_merits(), 140)
        self.assertEqual(ledger.records["ngurii"].total_merits(), 70)
        self.assertEqual(ledger.views()[0].number, 102)

    def test_rebuild_fills_the_history_in_order_and_adopt_keeps_better_old_data(self):
        ops = []
        for day, gained in ((3, 10), (10, 20), (17, 30)):   # cycles 101, 102, 103
            ops += _replay(_session(ts_day=day, merits=((12, gained),))).ops
        fresh = backfill.rebuild_ledger(ops)
        live = L.PowerplayLedger()
        live.record_merits("Ngurii", REINFORCEMENT, 999, _ts(3, 12))   # cycle 101: richer than the journal's 10
        live.adopt(fresh, L.parse_ts(THU_101), _ts(17, 12))
        live.roll_to(datetime(2026, 10, 23, tzinfo=timezone.utc))
        starts = [r["cycle_start"] for r in live.archive]
        self.assertEqual(starts, sorted(starts, reverse=True))
        self.assertEqual(len(starts), 3)
        self.assertEqual(sum(L.view_from_archive(r).merit_totals().get(REINFORCEMENT, 0) for r in live.archive), 999 + 20 + 30)
        self.assertEqual(live.covered_from, L.parse_ts(THU_101))

    def test_rebuild_with_nothing_found_still_marks_the_cycles_covered(self):
        live = L.PowerplayLedger()
        live.adopt(backfill.rebuild_ledger([]), L.parse_ts(THU_101), None)
        self.assertEqual(live.covered_from, L.parse_ts(THU_101))
        self.assertEqual(live.records, {})


class PlanTests(unittest.TestCase):
    NOW = datetime(2026, 10, 7, 18, 30, tzinfo=timezone.utc)   # Wed of cycle 101, day 7

    def test_never_scanned_rebuilds_the_last_cycles(self):
        plan = L.PowerplayLedger().plan_scan(self.NOW, 4)
        self.assertEqual((plan.mode, plan.current_cycle, plan.day_of_cycle), (L.SCAN_REBUILD, 101, 7))
        self.assertEqual(plan.missing_cycles, [98, 99, 100, 101])
        self.assertEqual(plan.scan_from, datetime(2026, 9, 10, 7, tzinfo=timezone.utc))
        self.assertEqual(plan.days_back, 28)
        self.assertIn("Not in history yet: cycles 98, 99, 100, 101", plan.describe())

    def test_depth_one_reads_only_the_days_since_this_cycle_started(self):
        plan = L.PowerplayLedger().plan_scan(self.NOW, 1)
        self.assertEqual((plan.missing_cycles, plan.days_back), ([101], 7))   # ceil(6.46 days)

    def test_depth_is_clamped(self):
        self.assertEqual(len(L.PowerplayLedger().plan_scan(self.NOW, 99).missing_cycles), L.MAX_BACKFILL_CYCLES)
        self.assertEqual(len(L.PowerplayLedger().plan_scan(self.NOW, 0).missing_cycles), 1)

    def _covered(self, seen_to: str) -> L.PowerplayLedger:
        ledger = L.PowerplayLedger()
        ledger.covered_from = datetime(2026, 9, 10, 7, tzinfo=timezone.utc)
        ledger.seen_to = seen_to
        return ledger

    def test_up_to_date_needs_no_scan(self):
        plan = self._covered("2026-10-07T18:29:00Z").plan_scan(self.NOW, 4)
        self.assertEqual((plan.mode, plan.missing_cycles, plan.scan_from), (L.SCAN_NONE, [], None))
        self.assertIn("up to date", plan.describe())

    def test_a_gap_is_scanned_incrementally_from_where_the_journal_was_last_seen(self):
        plan = self._covered("2026-10-05T20:00:00Z").plan_scan(self.NOW, 4)
        self.assertEqual((plan.mode, plan.missing_cycles), (L.SCAN_INCREMENTAL, []))
        self.assertEqual(plan.scan_from, datetime(2026, 10, 5, 20, tzinfo=timezone.utc))
        self.assertEqual(plan.days_back, 2)

    def test_a_long_gap_is_limited_to_the_depth(self):
        plan = self._covered("2026-05-01T00:00:00Z").plan_scan(self.NOW, 4)
        self.assertEqual(plan.scan_from, datetime(2026, 9, 10, 7, tzinfo=timezone.utc))

    def test_a_bigger_depth_than_before_rebuilds_only_the_new_cycles_range(self):
        ledger = self._covered("2026-10-07T18:29:00Z")
        plan = ledger.plan_scan(self.NOW, 6)
        self.assertEqual(plan.mode, L.SCAN_REBUILD)
        self.assertEqual(plan.missing_cycles, [96, 97])
        self.assertEqual(plan.scan_from, datetime(2026, 8, 27, 7, tzinfo=timezone.utc))

    def test_plan_round_trips_through_the_saved_state(self):
        ledger = self._covered("2026-10-05T20:00:00Z")
        ledger.record_merits("Ngurii", REINFORCEMENT, 5, _ts(5, 20))
        again = L.PowerplayLedger.from_dict(json.loads(json.dumps(ledger.to_dict())))
        self.assertEqual((again.covered_from, again.seen_to, again.last_merit_ts, again.last_merit_n),
                         (ledger.covered_from, ledger.seen_to, ledger.last_merit_ts, 1))


class ViewGapTests(unittest.TestCase):
    def test_covered_cycles_with_no_activity_still_appear_in_order(self):
        ops = _replay(_session(ts_day=3, merits=((12, 10),))).ops + _replay(_session(ts_day=17, merits=((12, 30),))).ops
        ledger = L.PowerplayLedger()
        ledger.adopt(backfill.rebuild_ledger(ops), L.parse_ts(THU_101), _ts(17, 12))
        ledger.roll_to(datetime(2026, 10, 18, tzinfo=timezone.utc))   # live = 103
        views = ledger.views()
        self.assertEqual([v.number for v in views], [103, 102, 101])
        self.assertEqual([bool(v.records) for v in views], [True, False, True])   # 102 was empty
        self.assertFalse(views[1].current)

    def test_an_uncovered_ledger_shows_only_what_it_has(self):
        ledger = L.PowerplayLedger()
        ledger.record_merits("Ngurii", REINFORCEMENT, 5, _ts(3, 12))
        self.assertEqual([v.number for v in ledger.views()], [101])


class DailyTests(unittest.TestCase):
    def test_merits_are_tallied_by_cycle_day_with_day_one_starting_at_the_cycle(self):
        ledger = L.PowerplayLedger()
        ledger.record_merits("A", REINFORCEMENT, 10, "2026-10-01T07:00:00Z")   # day 1, first second
        ledger.record_merits("A", REINFORCEMENT, 20, "2026-10-02T06:59:59Z")   # still day 1
        ledger.record_merits("A", UNDERMINING, 5, "2026-10-02T07:00:00Z")      # day 2
        ledger.record_merits("B", REINFORCEMENT, 7, "2026-10-07T23:00:00Z")    # day 7
        view = ledger.views()[0]
        self.assertEqual(view.day_merits(1), {REINFORCEMENT: 30})
        self.assertEqual(view.day_merits(2), {UNDERMINING: 5})
        self.assertEqual(view.day_merits(7), {REINFORCEMENT: 7})
        self.assertEqual(view.day_merits(3), {})
        self.assertEqual(sum(sum(m.values()) for m in view.daily.values()), 42)

    def test_days_are_archived_with_their_cycle_and_reset_for_the_next(self):
        ledger = L.PowerplayLedger()
        ledger.record_merits("A", REINFORCEMENT, 10, _ts(2, 12))
        ledger.record_merits("A", REINFORCEMENT, 4, _ts(8, 12))   # cycle 102, day 1
        self.assertEqual(L.view_from_archive(ledger.archive[0]).day_merits(2), {REINFORCEMENT: 10})
        self.assertEqual(ledger.views()[0].day_merits(1), {REINFORCEMENT: 4})
        self.assertEqual(ledger.views()[0].day_merits(2), {})

    def test_daily_survives_saving_and_junk(self):
        ledger = L.PowerplayLedger()
        ledger.record_merits("A", REINFORCEMENT, 10, _ts(2, 12))
        again = L.PowerplayLedger.from_dict(json.loads(json.dumps(ledger.to_dict())))
        self.assertEqual(again.daily, ledger.daily)
        bad = L.PowerplayLedger.from_dict({"daily": {"1": {"x": "y", "z": 3}, "2": 5}, "schema": "no"})
        self.assertEqual(bad.daily, {"1": {"z": 3}})
        self.assertEqual(bad.schema, 1)

    def test_a_ledger_saved_before_days_existed_is_rebuilt_once(self):
        old = L.PowerplayLedger()
        old.covered_from = datetime(2026, 9, 10, 7, tzinfo=timezone.utc)
        old.seen_to = "2026-10-07T18:29:00Z"
        old.schema = 1
        now = datetime(2026, 10, 7, 18, 30, tzinfo=timezone.utc)
        self.assertEqual(old.plan_scan(now, 4).mode, L.SCAN_REBUILD)
        old.adopt(backfill.rebuild_ledger([]), L.parse_ts("2026-09-10T07:00:00Z"), None)
        self.assertEqual(old.schema, L.SCHEMA)
        self.assertEqual(old.plan_scan(now, 4).mode, L.SCAN_NONE)

    def test_rebuild_from_journals_fills_the_days(self):
        ops = _replay(_session(ts_day=2, merits=((12, 100),))).ops + _replay(_session(ts_day=4, merits=((12, 40),))).ops
        view = backfill.rebuild_ledger(ops).views()[0]
        self.assertEqual((sum(view.day_merits(2).values()), sum(view.day_merits(4).values())), (100, 40))


class ScanFilesTests(unittest.TestCase):
    def _write(self, folder: str, name: str, entries: list, age_days: float = 0.0) -> str:
        path = os.path.join(folder, name)
        with open(path, "w", encoding="utf-8") as fh:
            for entry in entries:
                fh.write(json.dumps(entry) + "\n")
        if age_days:
            stamp = datetime.now().timestamp() - age_days * 86400
            os.utime(path, (stamp, stamp))
        return path

    def test_reads_only_recent_files_for_the_commander_in_order(self):
        with tempfile.TemporaryDirectory() as folder:
            self._write(folder, "Journal.2026-10-02T090000.01.log", _session(ts_day=2, merits=((12, 100),)), 1)
            self._write(folder, "Journal.2026-10-03T090000.01.log", _session("Mactavious", ts_day=3), 1)
            self._write(folder, "Journal.2026-08-01T090000.01.log", _session(ts_day=2, merits=((12, 5000),)), 90)
            self._write(folder, "Status.json", [{"event": "Nope"}], 1)
            result = backfill.scan_journals("bocheaux", datetime.fromtimestamp(
                datetime.now().timestamp() - 10 * 86400, timezone.utc), powerplay.PowerplayTracker, folder)
        self.assertTrue(result.ok)
        self.assertEqual(result.files, 2)   # the old file and Status.json are skipped; the other commander is read, then ignored
        merits = [op.merits for op in result.ops if op.kind == backfill.OP_MERITS]
        self.assertEqual(merits, [100])

    def test_missing_folder_is_not_ok(self):
        result = backfill.scan_journals("Bocheaux", datetime.now(timezone.utc), powerplay.PowerplayTracker,
                                        os.path.join(tempfile.gettempdir(), "no-such-wntb-folder"))
        self.assertFalse(result.ok)

    def test_junk_lines_are_skipped(self):
        with tempfile.TemporaryDirectory() as folder:
            path = self._write(folder, "Journal.2026-10-02T090000.01.log", _session(), 0)
            with open(path, "a", encoding="utf-8") as fh:
                fh.write('{"event":"PowerplayMerits", broken\n')
            result = backfill.scan_journals("Bocheaux", datetime(2026, 1, 1, tzinfo=timezone.utc),
                                            powerplay.PowerplayTracker, folder)
        self.assertEqual([op.merits for op in result.ops if op.kind == backfill.OP_MERITS], [100])


class DeliveryClassificationTests(unittest.TestCase):
    """PowerplayDeliver claims the merit events it earns; the legacy hand-in events only count without it."""

    def setUp(self) -> None:
        self.tracker = powerplay.PowerplayTracker()
        self.tracker.my_power = ME
        self.tracker.system_name, self.tracker.system_state = "Sol", "Fortified"
        self.tracker.system_controller = ME   # without a delivery this would be Reinforcement

    def merit(self, ts: str, gained: int = 100) -> str:
        self.tracker.apply_merits({"event": "PowerplayMerits", "timestamp": ts, "MeritsGained": gained, "Power": ME})
        return self.tracker.classify_current_activity("Sol")

    def deliver(self, ts: str) -> None:
        self.tracker.apply_delivery_signal("PowerplayDeliver", {"event": "PowerplayDeliver", "timestamp": ts})

    def test_both_merit_events_of_a_hand_in_are_deliveries(self) -> None:
        self.deliver("2026-10-10T20:00:56Z")
        self.assertEqual(self.merit("2026-10-10T20:00:57Z", 3960), "delivery")
        self.assertEqual(self.merit("2026-10-10T20:00:57Z", 238), "delivery")
        self.assertEqual(self.merit("2026-10-10T20:05:00Z"), REINFORCEMENT)   # later, unrelated

    def test_a_delayed_first_merit_is_still_claimed_but_a_very_late_one_is_not(self) -> None:
        self.deliver("2026-10-10T09:57:22Z")
        self.assertEqual(self.merit("2026-10-10T10:04:59Z", 3600), "delivery")   # 7.5 minutes on
        self.deliver("2026-10-10T11:00:00Z")
        self.assertEqual(self.merit("2026-10-10T11:20:00Z"), REINFORCEMENT)      # past the window: not claimed

    def test_the_legacy_signals_are_ignored_once_powerplay_deliver_has_been_seen(self) -> None:
        self.deliver("2026-10-10T20:04:37Z")
        self.assertEqual(self.merit("2026-10-10T20:04:38Z"), "delivery")
        # DeliverPowerMicroResources arrives after the merits in the real journal: it must not claim the next one.
        self.tracker.apply_delivery_signal("DeliverPowerMicroResources", {"event": "DeliverPowerMicroResources"})
        self.assertEqual(self.merit("2026-10-10T20:30:00Z"), REINFORCEMENT)

    def test_the_legacy_signal_still_works_for_journals_without_powerplay_deliver(self) -> None:
        self.tracker.apply_delivery_signal("DeliverPowerMicroResources", {"event": "DeliverPowerMicroResources"})
        self.assertEqual(self.merit("2026-10-10T20:04:38Z"), "delivery")
        self.assertEqual(self.merit("2026-10-10T20:04:50Z"), REINFORCEMENT)


if __name__ == "__main__":
    unittest.main()
