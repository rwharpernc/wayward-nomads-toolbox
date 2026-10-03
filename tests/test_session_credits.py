"""
Unit tests for plugin/session_credits.py: the session logic, the text, the saved
record and the journal-event handling. No EDMC runtime needed.

Run with: python -m unittest discover -s tests
"""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from plugin import session_credits as sc  # noqa: E402


class SummaryTextTests(unittest.TestCase):
    def test_earned_credits_show_a_plus_and_the_hourly_rate(self) -> None:
        self.assertEqual(sc.summary_text(1_234_567, 3.0), "Credits this session: +1,234,567 cr earned (+411,522 cr/hr)")

    def test_lost_credits_say_lost_with_no_plus_sign(self) -> None:
        self.assertEqual(sc.summary_text(-5_000, 0.5), "Credits this session: -5,000 cr lost (-10,000 cr/hr)")

    def test_rate_is_left_out_while_the_session_is_too_young_to_mean_anything(self) -> None:
        self.assertEqual(sc.summary_text(100, 0.01), "Credits this session: +100 cr earned")
        self.assertEqual(sc.summary_text(100, 0.0), "Credits this session: +100 cr earned")

    def test_no_change_and_unknown_balance(self) -> None:
        self.assertEqual(sc.summary_text(0, 2.0), "Credits this session: no change yet")
        self.assertIn("waiting for your balance", sc.summary_text(None, 2.0))


class SessionLogicTests(unittest.TestCase):
    def test_a_new_session_starts_at_the_login_balance(self) -> None:
        session, continued = sc.sync_session(None, "Bocheaux", 1_000, "J1.log")
        self.assertFalse(continued)
        self.assertEqual(sc.credits_earned(session), 0)

    def test_same_journal_and_commander_continues_keeping_the_original_start(self) -> None:
        session, _ = sc.sync_session(None, "Bocheaux", 1_000, "J1.log")
        sc.update_balance(session, 1_500)
        again, continued = sc.sync_session(session, "Bocheaux", 1_500, "J1.log")  # logout to menu and back
        self.assertTrue(continued)
        self.assertEqual(sc.credits_earned(again), 500)

    def test_a_different_journal_or_commander_starts_over(self) -> None:
        session, _ = sc.sync_session(None, "Bocheaux", 1_000, "J1.log")
        sc.update_balance(session, 1_500)
        _, continued = sc.sync_session(session, "Bocheaux", 1_500, "J2.log")
        self.assertFalse(continued)
        _, continued = sc.sync_session(session, "Mactavious", 9_000, "J1.log")
        self.assertFalse(continued)

    def test_the_balance_can_go_down_and_that_is_a_loss(self) -> None:
        session, _ = sc.sync_session(None, "Bocheaux", 10_000, "J1.log")
        sc.update_balance(session, 4_000)
        self.assertEqual(sc.credits_earned(session), -6_000)

    def test_a_session_with_no_login_balance_adopts_the_first_one_it_sees(self) -> None:
        session, _ = sc.sync_session(None, "Bocheaux", None, "J1.log")  # EDMC attached mid-game
        self.assertIsNone(sc.credits_earned(session))
        sc.update_balance(session, 7_000)
        sc.update_balance(session, 7_250)
        self.assertEqual(sc.credits_earned(session), 250)


class PersistenceAndEventsTests(unittest.TestCase):
    def test_saved_record_round_trips_and_a_bad_file_is_ignored(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            self.assertIsNone(sc.load_session(folder))
            session, _ = sc.sync_session(None, "Bocheaux", 1_000, "J1.log")
            sc.save_session(folder, session)
            self.assertEqual(sc.load_session(folder)["credits_start"], 1_000)
            with open(os.path.join(folder, sc.STATE_FILENAME), "w", encoding="utf-8") as handle:
                handle.write("not json")
            self.assertIsNone(sc.load_session(folder))

    def test_journal_events_drive_the_line_without_any_powerplay(self) -> None:
        with tempfile.TemporaryDirectory() as folder, mock.patch.object(sc, "_current_logfile", return_value="J1.log"):
            feature = sc.SessionCredits()
            feature.start(folder)
            feature.handle_event({"event": "LoadGame", "Credits": 1_000}, "Bocheaux", "Sol", None, {"Credits": 1_000})
            self.assertEqual(feature.text(), "Credits this session: no change yet")
            feature.handle_event({"event": "MarketSell"}, "Bocheaux", "Sol", None, {"Credits": 1_600})
            self.assertIn("+600 cr earned", feature.text())
            feature.handle_event({"event": "BuyAmmo"}, "Bocheaux", "Sol", None, {"Credits": 100})
            self.assertIn("-900 cr lost", feature.text())
            feature.stop()

            restarted = sc.SessionCredits()  # EDMC restarted with the game still running
            restarted.start(folder)
            restarted.handle_event({"event": "StartUp"}, "Bocheaux", None, None, {"Credits": 100})
            self.assertIn("-900 cr lost", restarted.text())

    def test_a_pathlib_logfile_is_turned_into_a_plain_string(self) -> None:
        import pathlib
        import types

        fake_monitor = types.SimpleNamespace(monitor=types.SimpleNamespace(logfile=pathlib.Path("J1.log")))
        with mock.patch.dict(sys.modules, {"monitor": fake_monitor}):
            self.assertEqual(sc._current_logfile(), str(pathlib.Path("J1.log")))
        fake_monitor.monitor.logfile = None
        with mock.patch.dict(sys.modules, {"monitor": fake_monitor}):
            self.assertIsNone(sc._current_logfile())

    def test_refresh_without_a_widget_is_harmless(self) -> None:
        sc.SessionCredits().refresh()


if __name__ == "__main__":
    unittest.main()
