"""
Powerplay's merit-to-CP conversion (formulas.py), session handling (session.py, store.py) and the "Copy Progress" line
(powerplay_clipboard.py). Pure logic with temporary folders only, so it behaves the same on Windows and Linux.

Run with: python -m unittest discover -s tests
"""
from __future__ import annotations

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

from plugin import formulas, powerplay_clipboard as clip, session as S, store  # noqa: E402
from plugin.formulas import ACQUISITION, DELIVERY, REINFORCEMENT, UNDERMINING, UNKNOWN  # noqa: E402


class FormulaTests(unittest.TestCase):
    def test_merits_divide_by_the_ratio(self):
        self.assertAlmostEqual(formulas.merits_to_cp(100, 4.0), 25.0)
        self.assertAlmostEqual(formulas.merits_to_cp(5, 2.5), 2.0)

    def test_no_usable_ratio_gives_zero_rather_than_an_error(self):
        for ratio in (None, 0, 0.0, -1, -4.2):
            self.assertEqual(formulas.merits_to_cp(100, ratio), 0.0)

    def test_zero_merits_is_zero_cp(self):
        self.assertEqual(formulas.merits_to_cp(0, 4.0), 0.0)

    def test_the_defaults_cover_exactly_the_activities_that_have_a_cp_figure(self):
        self.assertEqual(set(formulas.DEFAULT_RATIOS), {ACQUISITION, REINFORCEMENT, UNDERMINING})
        self.assertEqual(formulas.NO_CP_ACTIVITIES, frozenset({DELIVERY, UNKNOWN}))
        self.assertFalse(set(formulas.DEFAULT_RATIOS) & formulas.NO_CP_ACTIVITIES)
        self.assertEqual(set(formulas.ACTIVITIES), set(formulas.DEFAULT_RATIOS) | formulas.NO_CP_ACTIVITIES)

    def test_every_activity_has_a_label(self):
        self.assertEqual(set(formulas.ACTIVITY_LABELS), set(formulas.ACTIVITIES))


class SessionDataTests(unittest.TestCase):
    def test_a_new_session_starts_at_zero_for_every_activity(self):
        s = S.new_session("Alice", "Aisling Duval", "Journal.log")
        self.assertEqual(s["cmdr"], "Alice")
        self.assertEqual(s["totals"], {a: 0 for a in formulas.ACTIVITIES})
        self.assertEqual(s["events"], {a: 0 for a in formulas.ACTIVITIES})
        self.assertEqual(s["by_system"], {})
        self.assertIsNone(s["last_merit_ts"])
        self.assertEqual(S.total_merits(s), 0)

    def test_a_path_like_journal_file_is_stored_as_text(self):
        from pathlib import Path
        s = S.new_session("Alice", None, Path("Journal.log"))
        self.assertEqual(s["journal_file"], "Journal.log")
        self.assertIsNone(S.new_session("Alice", None)["journal_file"])

    def test_merits_add_up_by_activity_session_wide_and_per_system(self):
        s = S.new_session("Alice", None)
        S.add_merits(s, ACQUISITION, 40, "Sol", "2026-10-12T10:00:00Z")
        S.add_merits(s, ACQUISITION, 10, "Sol")
        S.add_merits(s, REINFORCEMENT, 5, "Ngurii")
        self.assertEqual(s["totals"][ACQUISITION], 50)
        self.assertEqual(s["events"][ACQUISITION], 2)
        self.assertEqual(S.total_merits(s), 55)
        self.assertEqual(S.system_totals(s, "Sol")[ACQUISITION], 50)
        self.assertEqual(S.system_merit_total(s, "Sol"), 50)
        self.assertEqual(S.system_merit_total(s, "Ngurii"), 5)
        self.assertEqual(S.system_totals(s, "Nowhere"), {})
        self.assertEqual(S.system_merit_total(s, "Nowhere"), 0)

    def test_the_last_merit_timestamp_follows_the_newest_event_given(self):
        s = S.new_session("Alice", None)
        S.add_merits(s, ACQUISITION, 1, None, "2026-10-12T10:00:00Z")
        S.add_merits(s, ACQUISITION, 1, None)          # no timestamp: the mark stays
        self.assertEqual(s["last_merit_ts"], "2026-10-12T10:00:00Z")

    def test_merits_without_a_system_still_count_session_wide(self):
        s = S.new_session("Alice", None)
        S.add_merits(s, UNKNOWN, 7, None)
        self.assertEqual(S.total_merits(s), 7)
        self.assertEqual(s["by_system"], {})

    def test_visited_systems_lists_the_most_recently_active_first(self):
        s = S.new_session("Alice", None)
        S.add_merits(s, ACQUISITION, 1, "Old")
        S.add_merits(s, ACQUISITION, 1, "New")
        s["by_system"]["Old"]["last_seen_at"] = "2026-10-12T08:00:00Z"
        s["by_system"]["New"]["last_seen_at"] = "2026-10-12T09:00:00Z"
        self.assertEqual(S.visited_systems(s), ["New", "Old"])

    def test_power_only_changes_to_a_real_value(self):
        s = S.new_session("Alice", "Aisling Duval")
        S.update_power(s, None)
        self.assertEqual(s["power"], "Aisling Duval")
        S.update_power(s, "Pranav Antal")
        self.assertEqual(s["power"], "Pranav Antal")

    def test_duration_and_rates(self):
        s = S.new_session("Alice", None)
        s["started_at"], s["updated_at"] = "2026-10-12T08:00:00Z", "2026-10-12T10:00:00Z"
        self.assertAlmostEqual(S.duration_hours(s), 2.0)
        self.assertAlmostEqual(S.per_hour(100, S.duration_hours(s)), 50.0)
        self.assertEqual(S.per_hour(100, 0), 0.0)
        self.assertEqual(S.per_hour(100, -1), 0.0)

    def test_an_unreadable_time_gives_zero_hours_and_never_a_negative_one(self):
        s = S.new_session("Alice", None)
        s["started_at"] = "not a time"
        self.assertEqual(S.duration_hours(s), 0.0)
        s["started_at"], s["updated_at"] = "2026-10-12T10:00:00Z", "2026-10-12T08:00:00Z"
        self.assertEqual(S.duration_hours(s), 0.0)


class ManagerTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.dir = self._tmp.name

    def manager(self):
        return S.SessionManager(store.SessionStore(self.dir))

    def test_the_same_journal_and_commander_continue_the_session(self):
        m = self.manager()
        m.start_session("Alice", None, "J1.log")
        m.record_merits(ACQUISITION, 10, "Sol")
        self.assertTrue(m.sync_session("Alice", None, "J1.log"))
        self.assertEqual(S.total_merits(m.current), 10)
        self.assertEqual(m.history, [])

    def test_a_different_journal_starts_a_new_session_and_keeps_the_old_one(self):
        m = self.manager()
        m.start_session("Alice", None, "J1.log")
        m.record_merits(ACQUISITION, 10, "Sol")
        self.assertFalse(m.sync_session("Alice", None, "J2.log"))
        self.assertEqual(S.total_merits(m.current), 0)
        self.assertEqual([S.total_merits(h) for h in m.history], [10])

    def test_a_different_commander_in_the_same_journal_never_inherits_the_totals(self):
        m = self.manager()
        m.start_session("Alice", None, "J1.log")
        m.record_merits(ACQUISITION, 10, "Sol")
        self.assertFalse(m.sync_session("Bob", None, "J1.log"))
        self.assertEqual(m.current["cmdr"], "Bob")
        self.assertEqual(S.total_merits(m.current), 0)
        self.assertEqual(m.history[0]["cmdr"], "Alice")

    def test_a_session_with_no_commander_yet_is_claimed_by_the_first_one_seen(self):
        m = self.manager()
        m.start_session("", None, "J1.log")
        self.assertTrue(m.sync_session("Alice", None, "J1.log"))
        self.assertEqual(m.current["cmdr"], "Alice")

    def test_no_journal_file_means_a_new_session(self):
        m = self.manager()
        m.start_session("Alice", None, "J1.log")
        self.assertFalse(m.sync_session("Alice", None, None))

    def test_an_empty_unnamed_session_is_not_filed_in_history(self):
        m = self.manager()
        m.start_session("Alice", None, "J1.log")
        self.assertEqual(m.history, [])

    def test_reset_session_zeroes_everything_but_keeps_who_and_when(self):
        m = self.manager()
        m.start_session("Alice", "Aisling Duval", "J1.log")
        m.record_merits(ACQUISITION, 10, "Sol")
        m.record_merits(REINFORCEMENT, 5, "Ngurii")
        started = m.current["started_at"]
        m.reset_session()
        self.assertEqual(S.total_merits(m.current), 0)
        self.assertEqual(m.current["by_system"], {})
        self.assertEqual(m.current["events"], {a: 0 for a in formulas.ACTIVITIES})
        self.assertEqual((m.current["cmdr"], m.current["power"], m.current["journal_file"], m.current["started_at"]),
                         ("Alice", "Aisling Duval", "J1.log", started))

    def test_reset_system_takes_only_that_system_back_out(self):
        m = self.manager()
        m.start_session("Alice", None, "J1.log")
        m.record_merits(ACQUISITION, 10, "Sol")
        m.record_merits(ACQUISITION, 4, "Ngurii")
        m.reset_system("Sol")
        self.assertEqual(m.current["totals"][ACQUISITION], 4)
        self.assertEqual(m.current["events"][ACQUISITION], 1)
        self.assertNotIn("Sol", m.current["by_system"])
        self.assertEqual(S.system_merit_total(m.current, "Ngurii"), 4)

    def test_reset_system_with_nothing_recorded_there_changes_nothing(self):
        m = self.manager()
        m.start_session("Alice", None, "J1.log")
        m.record_merits(ACQUISITION, 10, "Sol")
        m.reset_system("Nowhere")
        self.assertEqual(m.current["totals"][ACQUISITION], 10)

    def test_changes_are_saved_and_come_back_after_a_restart(self):
        m = self.manager()
        m.start_session("Alice", "Aisling Duval", "J1.log")
        m.record_merits(ACQUISITION, 10, "Sol", "2026-10-12T10:00:00Z")
        again = self.manager()
        self.assertEqual(S.total_merits(again.current), 10)
        self.assertEqual(again.current["cmdr"], "Alice")
        self.assertEqual(again.current["last_merit_ts"], "2026-10-12T10:00:00Z")

    def test_a_saved_session_without_a_merit_mark_gets_one_so_a_rescan_cannot_double_count(self):
        m = self.manager()
        m.start_session("Alice", None, "J1.log")
        m.record_merits(ACQUISITION, 10, "Sol")        # no timestamp given
        m.current["last_merit_ts"] = None
        m.flush()
        self.assertIsNotNone(self.manager().current["last_merit_ts"])


class StoreTests(unittest.TestCase):
    def test_a_missing_or_damaged_file_loads_as_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            s = store.SessionStore(tmp)
            self.assertEqual(s.load(), ([], None))
            with open(os.path.join(tmp, store.FILENAME), "w", encoding="utf-8") as fh:
                fh.write("{ not json")
            with self.assertLogs(level="WARNING"):   # the damaged file is reported, not raised
                self.assertEqual(s.load(), ([], None))
            with open(os.path.join(tmp, store.FILENAME), "w", encoding="utf-8") as fh:
                fh.write('["a list"]')
            self.assertEqual(s.load(), ([], None))

    def test_history_is_trimmed_per_commander_keeping_the_newest_in_order(self):
        history = [{"cmdr": "Alice", "n": i} for i in range(5)] + [{"cmdr": "Bob", "n": 99}]
        kept = store.trim(history, limit=2)
        self.assertEqual([(h["cmdr"], h["n"]) for h in kept], [("Alice", 3), ("Alice", 4), ("Bob", 99)])

    def test_commander_names_compare_without_case_or_padding(self):
        history = [{"cmdr": " ALICE "}, {"cmdr": "alice"}, {"cmdr": "Bob"}]
        self.assertEqual(len(store.sessions_of(history, "Alice")), 2)


class ClipboardTests(unittest.TestCase):
    def test_every_placeholder_is_filled(self):
        line = clip.format_system_line(clip.DEFAULT_TEMPLATE, system="Ngurii", merits="1,200", cp="300", state="Fortified")
        self.assertIn("[Ngurii](https://inara.cz/elite/starsystem/?search=Ngurii)", line)
        self.assertIn("1,200 merits (~300 CP)", line)
        self.assertTrue(line.endswith("Fortified"))

    def test_the_documented_placeholders_are_the_ones_that_work(self):
        template = " ".join(clip.PLACEHOLDERS)
        line = clip.format_system_line(template, system="Sol", merits="1", cp="2", state="x")
        self.assertNotIn("{", line)

    def test_a_system_name_is_escaped_in_the_link(self):
        self.assertEqual(clip.inara_system_url("Col 285 Sector"), "https://inara.cz/elite/starsystem/?search=Col%20285%20Sector")
        self.assertNotIn("&", clip.inara_system_url("A&B").split("search=")[1])

    def test_a_broken_template_comes_back_unchanged_instead_of_raising(self):
        for bad in ("{unknown}", "{system", "{0}", "{system!z}"):
            self.assertEqual(clip.format_system_line(bad, system="Sol", merits="1", cp="2", state="x"), bad)

    def test_a_template_with_no_placeholders_is_left_alone(self):
        self.assertEqual(clip.format_system_line("just text", system="Sol", merits="1", cp="2", state="x"), "just text")


if __name__ == "__main__":
    unittest.main()
