"""Fleet carrier jump countdown (carrier_jump_timer.py): the planned jump, the time left, one alert per threshold, and reading a
request back from journal files."""
from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from plugin import carrier_jump_timer as T  # noqa: E402

NOW = datetime(2026, 10, 13, 12, 0, 0, tzinfo=timezone.utc).timestamp()


def request(minutes_ahead, system="Sol", body="Earth", **extra):
    stamp = datetime.fromtimestamp(NOW + minutes_ahead * 60, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return {"event": "CarrierJumpRequest", "SystemName": system, "Body": body, "DepartureTime": stamp, **extra}


class Clock:
    def __init__(self, at=NOW):
        self.at = at

    def __call__(self):
        return self.at


class ParseTests(unittest.TestCase):
    def test_the_journal_time_form_is_read_as_utc(self):
        self.assertEqual(T.parse_departure("2026-10-13T12:00:00Z"), NOW)
        self.assertEqual(T.parse_departure("2026-10-13T12:00:00"), NOW)

    def test_junk_gives_none(self):
        for value in (None, "", "   ", "soon", 5, ["2026-10-13T12:00:00Z"]):
            self.assertIsNone(T.parse_departure(value))

    def test_remaining_time_reads_as_minutes_and_seconds(self):
        self.assertEqual(T.format_remaining(272), "4:32")
        self.assertEqual(T.format_remaining(3725), "1:02:05")
        self.assertEqual(T.format_remaining(0), "0:00")
        self.assertEqual(T.format_remaining(-5), "0:00")
        self.assertEqual(T.format_remaining(59.2), "1:00")      # rounds up, so it never shows 0:00 with time left


class PlanTests(unittest.TestCase):
    def setUp(self):
        self.clock = Clock()
        self.timer = T.CarrierJumpTimer(now=self.clock)

    def test_a_request_plans_a_jump(self):
        self.assertTrue(self.timer.handle_event(request(15)))
        self.assertEqual(self.timer.jump.system, "Sol")
        self.assertEqual(self.timer.remaining(), 900)
        self.assertEqual(self.timer.lines(), ["Carrier jump in 15:00", "To: Sol", "Body: Earth"])

    def test_the_system_has_its_own_line_and_a_body_is_said_without_the_system_in_front(self):
        self.timer.handle_event(request(15, system="Eorld Byoi XX-X d1-23", body="Eorld Byoi XX-X d1-23 A 2"))
        self.assertEqual(self.timer.lines(), ["Carrier jump in 15:00", "To: Eorld Byoi XX-X d1-23", "Body: A 2"])

    def test_departing_then_clearing_the_lines(self):
        self.timer.handle_event(request(15))
        self.clock.at = NOW + 15 * 60
        self.assertEqual(self.timer.lines(), ["Carrier departing now", "To: Sol", "Body: Earth"])
        self.clock.at = NOW + 15 * 60 + T.AFTER_DEPARTURE_S + 1
        self.assertEqual(self.timer.lines(), [])

    def test_a_body_is_shortened_by_taking_the_system_off_the_front(self):
        for system, body, expected in (
                ("Colonia", "Colonia 3 a", "3 a"), ("colonia", "COLONIA 3 a", "3 a"), ("Colonia", "Colonia", ""), ("Colonia", "", ""),
                ("Colonia", "  ", ""), ("Colonia", "Other Place B 1", "Other Place B 1"), ("Colonia", "Colonia - 3 a", "3 a"),
                ("Sol", "Solar Flare 2", "Solar Flare 2"), ("Sol", "Sol 3", "3")):
            with self.subTest(system=system, body=body):
                self.assertEqual(T.short_body(system, body), expected)

    def test_no_jump_no_lines(self):
        self.assertEqual(self.timer.lines(), [])

    def test_a_jump_to_the_system_itself_has_no_body_line(self):
        self.timer.handle_event(request(15, system="Sol", body="Sol"))
        self.assertEqual(self.timer.lines(), ["Carrier jump in 15:00", "To: Sol"])
        self.timer.handle_event(request(16, system="Sol", body=""))
        self.assertEqual(self.timer.lines(), ["Carrier jump in 16:00", "To: Sol"])

    def test_long_names_are_clipped_so_the_lines_stay_short(self):
        self.timer.handle_event(request(15, system="S" * 90, body="S" * 90 + " " + "B" * 90))
        lines = self.timer.lines()
        self.assertEqual(len(lines), 3)
        self.assertTrue(all(len(line) <= 50 for line in lines), lines)
        self.assertIn("…", lines[1])
        self.assertIn("…", lines[2])

    def test_requests_without_a_time_or_a_system_are_ignored(self):
        self.assertFalse(self.timer.handle_event({"event": "CarrierJumpRequest", "SystemName": "Sol"}))
        self.assertFalse(self.timer.handle_event({**request(15), "SystemName": ""}))
        self.assertIsNone(self.timer.jump)

    def test_an_old_request_read_back_from_a_journal_is_ignored(self):
        self.assertFalse(self.timer.handle_event(request(-10)))
        self.assertIsNone(self.timer.jump)

    def test_a_cancel_or_a_completed_jump_clears_it(self):
        for event in ("CarrierJumpCancelled", "CarrierJump"):
            self.timer.handle_event(request(15))
            self.assertTrue(self.timer.handle_event({"event": event}))
            self.assertIsNone(self.timer.jump)
            self.assertEqual(self.timer.lines(), [])

    def test_a_cancel_with_nothing_planned_changes_nothing(self):
        self.assertFalse(self.timer.handle_event({"event": "CarrierJumpCancelled"}))

    def test_a_new_request_replaces_the_old_one_and_re_arms_the_alerts(self):
        self.timer.handle_event(request(5))
        self.clock.at = NOW + 100          # 3:20 left
        self.assertEqual(self.timer.due_alert(), 300)
        self.timer.handle_event(request(30, system="Colonia"))
        self.assertEqual(self.timer.jump.system, "Colonia")
        self.clock.at = NOW + 30 * 60 - 590
        self.assertEqual(self.timer.due_alert(), 600)

    def test_the_same_request_twice_is_not_a_change(self):
        self.timer.handle_event(request(15))
        self.assertFalse(self.timer.handle_event(request(15)))

    def test_departing_then_clearing(self):
        self.timer.handle_event(request(1))
        self.clock.at = NOW + 60
        self.assertEqual(self.timer.lines()[0], "Carrier departing now")
        self.assertTrue(self.timer.active())
        self.clock.at = NOW + 60 + T.AFTER_DEPARTURE_S + 1
        self.assertFalse(self.timer.active())
        self.assertEqual(self.timer.lines(), [])
        self.assertTrue(self.timer.expire())
        self.assertIsNone(self.timer.jump)
        self.assertFalse(self.timer.expire())


class AlertTests(unittest.TestCase):
    def setUp(self):
        self.clock = Clock()
        self.timer = T.CarrierJumpTimer(now=self.clock)
        self.timer.handle_event(request(15))

    def test_each_threshold_fires_once_as_it_is_crossed(self):
        got = []
        for seconds_in in (0, 300, 301, 599, 600, 700, 840, 841, 880, 899, 900, 901):
            self.clock.at = NOW + seconds_in
            alert = self.timer.due_alert()
            if alert is not None:
                got.append((seconds_in, alert))
        self.assertEqual(got, [(300, 600), (600, 300), (840, 60), (900, 0)])

    def test_starting_inside_a_threshold_gives_only_the_nearest_one(self):
        self.clock.at = NOW + 15 * 60 - 200       # 3:20 left: 600 and 300 are both already crossed
        self.assertEqual(self.timer.due_alert(), 300)
        self.assertIsNone(self.timer.due_alert())

    def test_no_alert_without_a_jump(self):
        self.timer.handle_event({"event": "CarrierJumpCancelled"})
        self.assertIsNone(self.timer.due_alert())

    def test_alert_wording(self):
        self.assertEqual(T.alert_text(600), "Carrier jump in 10 minutes")
        self.assertEqual(T.alert_text(60), "Carrier jump in 1 minute")
        self.assertEqual(T.alert_text(0), "Carrier jump departing now")


class RecoverTests(unittest.TestCase):
    def write(self, folder, name, events):
        with open(os.path.join(folder, name), "w", encoding="utf-8") as handle:
            for event in events:
                handle.write(json.dumps(event) + "\n")

    def test_a_request_is_read_back_from_a_recent_journal(self):
        timer = T.CarrierJumpTimer(now=Clock())
        with tempfile.TemporaryDirectory() as folder:
            self.write(folder, "Journal.2026-10-13T110000.01.log", [
                {"event": "Fileheader"}, request(-20), request(12, system="Colonia"), {"event": "Music"}])
            self.assertTrue(T.recover(timer, 0, folder))
        self.assertEqual(timer.jump.system, "Colonia")

    def test_a_cancel_after_the_request_leaves_nothing(self):
        timer = T.CarrierJumpTimer(now=Clock())
        with tempfile.TemporaryDirectory() as folder:
            self.write(folder, "Journal.2026-10-13T110000.01.log", [request(12), {"event": "CarrierJumpCancelled"}])
            self.assertFalse(T.recover(timer, 0, folder))

    def test_a_missing_folder_is_not_an_error(self):
        timer = T.CarrierJumpTimer(now=Clock())
        self.assertFalse(T.recover(timer, 0, os.path.join(tempfile.gettempdir(), "no-such-wntb-journals")))


if __name__ == "__main__":
    unittest.main()
