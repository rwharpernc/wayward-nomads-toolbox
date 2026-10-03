"""
Unit tests for plugin/bgs_ledger.py, bgs_format.py and bgs_journal.py.

Pure logic — no EDMC runtime needed. Run with:
    python -m unittest discover -s tests
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import types
import unittest
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# bgs_journal imports EDMC's `config`; give it a stand-in only if EDMC isn't there.
if "config" not in sys.modules:
    _stub = types.ModuleType("config")
    _stub.appname = "EDMarketConnector"  # type: ignore[attr-defined]
    _stub.config = types.SimpleNamespace(  # type: ignore[attr-defined]
        get_str=lambda *_a, **_k: "", default_journal_dir="")
    sys.modules["config"] = _stub

from plugin import bgs_format, bgs_journal, bgs_ledger  # noqa: E402

TICK = "2026-10-03T03:00:00.000000+00:00"


def _factions(inf_a: float, state_a: str = "None") -> list:
    return [
        {"Name": "Alpha Party", "FactionState": state_a, "Influence": inf_a, "Happiness_Localised": "Happy"},
        {"Name": "Beta Corp", "FactionState": "Boom", "Influence": 0.3},
    ]


def _jump(ts: str, system: str, inf_a: float, state_a: str = "None") -> dict:
    return {"timestamp": ts, "event": "FSDJump", "StarSystem": system,
            "SystemFaction": {"Name": "Alpha Party"}, "Factions": _factions(inf_a, state_a)}


def _mission(ts: str, faction: str, effect_trend: str = "UpGood", pips: str = "++", mission_id: int = 1) -> dict:
    return {"timestamp": ts, "event": "MissionCompleted", "MissionID": mission_id,
            "FactionEffects": [{"Faction": faction, "Influence": [{"Trend": effect_trend, "Influence": pips}]}]}


class ActivityTests(unittest.TestCase):
    def test_records_increases_and_decreases_in_the_current_system_without_any_tracking(self) -> None:
        ledger = bgs_ledger.TickLedger(TICK)
        ledger.process(_jump("2026-10-03T04:00:00Z", "Sol", 0.4))
        ledger.process(_mission("2026-10-03T04:10:00Z", "Alpha Party", "UpGood", "+++", 1))
        ledger.process(_mission("2026-10-03T04:20:00Z", "Beta Corp", "DownBad", "++", 2))
        alpha = ledger.activity["sol|alpha party"]
        beta = ledger.activity["sol|beta corp"]
        self.assertEqual((alpha.missions, alpha.inf_plus, alpha.inf_minus), (1, 3, 0))
        self.assertEqual((beta.missions, beta.inf_plus, beta.inf_minus), (1, 0, 2))

    def test_events_before_the_tick_do_not_count_but_still_set_context(self) -> None:
        ledger = bgs_ledger.TickLedger(TICK)
        ledger.process(_jump("2026-10-02T22:00:00Z", "Sol", 0.4))
        ledger.process(_mission("2026-10-02T22:10:00Z", "Alpha Party"))
        self.assertEqual(ledger.activity, {})
        self.assertEqual(ledger.current_system, "Sol")
        ledger.process(_mission("2026-10-03T05:00:00Z", "Alpha Party", mission_id=2))
        self.assertEqual(ledger.activity["sol|alpha party"].missions, 1)

    def test_mission_inf_goes_to_the_system_it_was_taken_in_not_where_it_is_handed_in(self) -> None:
        ledger = bgs_ledger.TickLedger(TICK)
        ledger.process({**_jump("2026-10-03T04:00:00Z", "Sol", 0.4), "SystemAddress": 111})
        ledger.process({"timestamp": "2026-10-03T04:01:00Z", "event": "MissionAccepted",
                        "MissionID": 7, "Faction": "Alpha Party"})
        ledger.process({**_jump("2026-10-03T05:00:00Z", "Alpha Centauri", 0.4), "SystemAddress": 222})
        done = _mission("2026-10-03T05:10:00Z", "Alpha Party", "UpGood", "++", 7)
        done["FactionEffects"][0]["Influence"][0]["SystemAddress"] = 111
        ledger.process(done)
        self.assertEqual(ledger.activity["sol|alpha party"].inf_plus, 2)
        self.assertNotIn("alpha centauri|alpha party", ledger.activity)

        # No SystemAddress on the effect: the issuing faction falls back to the accepted system.
        ledger.process({"timestamp": "2026-10-03T05:20:00Z", "event": "MissionAccepted",
                        "MissionID": 8, "Faction": "Beta Corp"})
        ledger.process({**_jump("2026-10-03T05:25:00Z", "Sol", 0.4), "SystemAddress": 111})
        ledger.process(_mission("2026-10-03T05:30:00Z", "Beta Corp", "UpGood", "+", 8))
        self.assertEqual(ledger.activity["alpha centauri|beta corp"].inf_plus, 1)
        self.assertNotIn("sol|beta corp", ledger.activity)

    def test_failed_and_abandoned_missions_score_against_the_issuing_faction(self) -> None:
        ledger = bgs_ledger.TickLedger(TICK)
        ledger.process(_jump("2026-10-03T04:00:00Z", "Sol", 0.4))
        for mission_id in (10, 11):
            ledger.process({"timestamp": "2026-10-03T04:01:00Z", "event": "MissionAccepted",
                            "MissionID": mission_id, "Faction": "Beta Corp"})
        ledger.process({"timestamp": "2026-10-03T06:00:00Z", "event": "MissionFailed", "MissionID": 10})
        ledger.process({"timestamp": "2026-10-03T06:05:00Z", "event": "MissionAbandoned", "MissionID": 11})
        beta = ledger.activity["sol|beta corp"]
        self.assertEqual((beta.missions_failed, beta.missions_abandoned), (1, 1))
        self.assertEqual(ledger.open_missions, {})

    def test_crimes_vouchers_and_trade_attribution(self) -> None:
        ledger = bgs_ledger.TickLedger(TICK)
        ledger.process(_jump("2026-10-03T04:00:00Z", "Sol", 0.4))
        ledger.process({"timestamp": "2026-10-03T04:05:00Z", "event": "CommitCrime", "CrimeType": "assault",
                        "Faction": "Beta Corp", "Fine": 400})
        ledger.process({"timestamp": "2026-10-03T04:06:00Z", "event": "RedeemVoucher", "Type": "bounty",
                        "Factions": [{"Faction": "Alpha Party", "Amount": 5000}]})
        ledger.process({"timestamp": "2026-10-03T04:07:00Z", "event": "Docked", "StarSystem": "Sol",
                        "StationFaction": {"Name": "Alpha Party"}})
        ledger.process({"timestamp": "2026-10-03T04:08:00Z", "event": "MarketBuy", "TotalCost": 1000})
        ledger.process({"timestamp": "2026-10-03T04:09:00Z", "event": "MarketSell", "TotalSale": 400})
        beta = ledger.activity["sol|beta corp"]
        alpha = ledger.activity["sol|alpha party"]
        self.assertEqual((beta.crimes, beta.crime_credits), (1, 400))
        self.assertEqual(alpha.bounty_credits, 5000)
        self.assertEqual(alpha.trade_profit_credits, -600)  # a loss is a decrease, kept negative


class TrackTests(unittest.TestCase):
    def test_influence_and_state_change_since_before_the_tick(self) -> None:
        ledger = bgs_ledger.TickLedger(TICK)
        ledger.process(_jump("2026-10-02T22:00:00Z", "Sol", 0.40, "None"))
        ledger.process(_jump("2026-10-03T05:00:00Z", "Sol", 0.45, "Boom"))
        track = ledger.tracks["sol|alpha party"]
        self.assertAlmostEqual(track.influence_delta() or 0.0, 5.0)
        self.assertEqual(bgs_format.state_change_text(track), "None → Boom")
        self.assertEqual(bgs_format.influence_change_text(track), "45.0% (+5.0)")

    def test_unknown_baseline_shows_no_change(self) -> None:
        ledger = bgs_ledger.TickLedger(TICK)
        ledger.process(_jump("2026-10-03T05:00:00Z", "Sol", 0.45))
        track = ledger.tracks["sol|alpha party"]
        self.assertIsNone(track.influence_delta())
        self.assertEqual(bgs_format.influence_change_text(track), "45.0%")


class RollTests(unittest.TestCase):
    def test_roll_archives_and_resets_but_keeps_baselines(self) -> None:
        ledger = bgs_ledger.TickLedger(TICK)
        ledger.process(_jump("2026-10-03T04:00:00Z", "Sol", 0.45))
        ledger.process(_mission("2026-10-03T04:10:00Z", "Alpha Party"))
        new_tick = "2026-10-04T03:00:00+00:00"
        record = ledger.roll(new_tick)
        self.assertIsNotNone(record)
        self.assertEqual(record["tick_start"], TICK)
        self.assertEqual(record["tick_end"], new_tick)
        self.assertEqual(record["activity"]["sol|alpha party"]["missions"], 1)
        self.assertEqual(ledger.activity, {})
        self.assertEqual(ledger.tick_start, new_tick)
        track = ledger.tracks["sol|alpha party"]
        self.assertAlmostEqual(track.before.influence, 0.45)  # last period's end is this period's start
        self.assertIsNone(track.now)

    def test_roll_of_an_empty_period_archives_nothing(self) -> None:
        self.assertIsNone(bgs_ledger.TickLedger(TICK).roll("2026-10-04T03:00:00+00:00"))

    def test_prune_archive_keeps_only_the_configured_days(self) -> None:
        now = datetime(2026, 10, 10, tzinfo=timezone.utc)
        archive = [{"tick_end": "2026-10-09T03:00:00+00:00"}, {"tick_end": "2026-10-02T03:00:00+00:00"}]
        kept = bgs_ledger.prune_archive(archive, now, 7)
        self.assertEqual([r["tick_end"] for r in kept], ["2026-10-09T03:00:00+00:00"])
        self.assertEqual(len(bgs_ledger.prune_archive(archive, now, 30)), 2)

    def test_state_round_trips_through_json(self) -> None:
        ledger = bgs_ledger.TickLedger(TICK)
        ledger.process(_jump("2026-10-03T04:00:00Z", "Sol", 0.45))
        ledger.process(_mission("2026-10-03T04:10:00Z", "Alpha Party"))
        ledger.process({"timestamp": "2026-10-03T04:11:00Z", "event": "MissionAccepted",
                        "MissionID": 5, "Faction": "Beta Corp"})
        restored = bgs_ledger.TickLedger.from_dict(json.loads(json.dumps(ledger.to_dict())))
        self.assertEqual(restored.tick_start, TICK)
        self.assertEqual(restored.activity["sol|alpha party"].missions, 1)
        self.assertIn("sol|beta corp", restored.tracks)
        self.assertEqual(restored.open_missions, {"5": ("Beta Corp", "Sol")})

    def test_unknown_saved_fields_are_ignored(self) -> None:
        data = {"tick_start": TICK, "activity": {"sol|a": {"system": "Sol", "faction": "A", "missions": 2,
                                                            "field_from_the_future": 1}}}
        self.assertEqual(bgs_ledger.TickLedger.from_dict(data).activity["sol|a"].missions, 2)


class ViewTests(unittest.TestCase):
    def test_visited_systems_are_listed_most_recent_first_current_leading(self) -> None:
        ledger = bgs_ledger.TickLedger(TICK)
        ledger.process(_jump("2026-10-03T04:00:00Z", "Sol", 0.4))
        ledger.process(_mission("2026-10-03T04:10:00Z", "Alpha Party", mission_id=1))
        ledger.process(_jump("2026-10-03T05:00:00Z", "Achenar", 0.4))
        ledger.process(_mission("2026-10-03T05:10:00Z", "Alpha Party", mission_id=2))
        ledger.process(_jump("2026-10-03T06:00:00Z", "Empty Space", 0.4))
        view = ledger.view()
        self.assertEqual(view.systems("Empty Space"), ["Empty Space", "Achenar", "Sol"])
        self.assertEqual(view.systems(None), ["Empty Space", "Achenar", "Sol"])

    def _visit_many(self, names: list) -> bgs_ledger.TickLedger:
        ledger = bgs_ledger.TickLedger(TICK)
        for index, name in enumerate(names):
            ledger.process(_jump(f"2026-10-03T{4 + index:02d}:00:00Z", name, 0.4))
        return ledger

    def test_only_the_most_recent_systems_get_tabs_current_first(self) -> None:
        names = [f"System {n}" for n in range(1, 10)]
        view = self._visit_many(names).view()
        shown = view.systems("System 9", limit=bgs_ledger.RECENT_SYSTEMS)
        self.assertEqual(shown, ["System 9", "System 8", "System 7", "System 6", "System 5", "System 4"])
        self.assertEqual(len(view.systems("System 9")), 9)  # no limit: everything (Copy Summary)

    def test_pinned_systems_always_show_in_addition_to_the_recent_ones(self) -> None:
        view = self._visit_many([f"System {n}" for n in range(1, 10)]).view()
        shown = view.systems("System 9", ["system 1", "Quiet Place"], limit=6)
        self.assertEqual(shown[:2], ["Quiet Place", "System 1"])  # pinned first, data's spelling kept
        self.assertEqual(len(shown), 8)

    def test_hidden_systems_are_skipped_but_pinned_wins_over_nothing(self) -> None:
        view = self._visit_many([f"System {n}" for n in range(1, 10)]).view()
        shown = view.systems("System 9", [], ["system 8"], limit=3)
        self.assertEqual(shown, ["System 9", "System 7", "System 6"])

    def test_summary_marks_pinned_systems_and_includes_all(self) -> None:
        ledger = bgs_ledger.TickLedger(TICK)
        ledger.process(_jump("2026-10-03T04:00:00Z", "Sol", 0.4))
        ledger.process(_mission("2026-10-03T04:10:00Z", "Alpha Party", mission_id=1))
        ledger.process(_jump("2026-10-03T05:00:00Z", "Achenar", 0.4))
        text = bgs_format.summary_text([ledger.view()], "Achenar", ["Sol"])
        self.assertIn("★ Sol:", text)
        self.assertIn("Achenar:", text)
        self.assertNotIn("★ Achenar:", text)

    def test_summary_text_covers_each_period_and_system(self) -> None:
        ledger = bgs_ledger.TickLedger(TICK)
        ledger.process(_jump("2026-10-03T04:00:00Z", "Sol", 0.4))
        ledger.process(_mission("2026-10-03T04:10:00Z", "Alpha Party"))
        archived = bgs_ledger.view_from_archive(ledger.archive_record("2026-10-04T03:00:00+00:00"))
        text = bgs_format.summary_text([ledger.view(), archived], "Sol")
        self.assertIn("Current tick", text)
        self.assertIn("Sol:", text)
        self.assertIn("1 mission(s) done, INF +2/-0", text)
        self.assertIn("2026-10-04 03:00 UTC", text)

    def test_long_names_are_clipped(self) -> None:
        self.assertLessEqual(len(bgs_format.clip("x" * 500)), bgs_format.NAME_LIMIT)


class JournalReplayTests(unittest.TestCase):
    def _write_journal(self, folder: str, name: str, cmdr: str, entries: list) -> None:
        lines = [{"timestamp": "2026-10-03T00:00:00Z", "event": "Commander", "Name": cmdr}] + entries
        with open(os.path.join(folder, name), "w", encoding="utf-8") as handle:
            handle.write("\n".join(json.dumps(e) for e in lines) + "\n")

    def test_replay_rebuilds_the_period_for_the_right_commander(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            self._write_journal(folder, "Journal.2026-10-03T000000.01.log", "Bocheaux", [
                _jump("2026-10-02T22:00:00Z", "Sol", 0.40),
                _jump("2026-10-03T05:00:00Z", "Sol", 0.45, "Boom"),
                _mission("2026-10-03T05:10:00Z", "Alpha Party"),
                {"timestamp": "2026-10-03T05:11:00Z", "event": "FSSDiscoveryScan"},  # irrelevant, filtered
            ])
            self._write_journal(folder, "Journal.2026-10-03T010000.01.log", "Mactavious", [
                _jump("2026-10-03T05:00:00Z", "Sol", 0.10),
                _mission("2026-10-03T05:10:00Z", "Beta Corp", mission_id=9),
            ])
            events = bgs_journal.read_events("bocheaux", TICK, folder)
            ledger = bgs_ledger.rebuild(events, TICK)
        self.assertEqual(list(ledger.activity), ["sol|alpha party"])
        self.assertAlmostEqual(ledger.tracks["sol|alpha party"].influence_delta() or 0.0, 5.0)

    def test_replay_overlapping_live_events_can_be_deduplicated(self) -> None:
        entry = _mission("2026-10-03T05:10:00Z", "Alpha Party")
        self.assertEqual(bgs_ledger.fingerprint(entry), bgs_ledger.fingerprint(dict(entry)))

    def test_missing_folder_or_tick_returns_nothing(self) -> None:
        self.assertEqual(bgs_journal.read_events("Bocheaux", TICK, os.path.join(tempfile.gettempdir(), "nope-bgs")), [])
        self.assertEqual(bgs_journal.read_events("Bocheaux", "not a time", tempfile.gettempdir()), [])


if __name__ == "__main__":
    unittest.main()
