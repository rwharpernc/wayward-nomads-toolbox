"""
The "Merits this session" line (session_merits.py): its text, the hourly rate, and that the time is read as UTC.
Pure functions only; the label itself is covered by version_line_smoke.py's panel build.
"""
from __future__ import annotations

import calendar
import os
import sys
import time
import types
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
if "config" not in sys.modules:
    _stub = types.ModuleType("config")
    _stub.appname = "EDMarketConnector"
    _stub.config = types.SimpleNamespace(get_str=lambda key: "", default_journal_dir="")
    sys.modules["config"] = _stub

from plugin import session_merits as M  # noqa: E402


class TextTests(unittest.TestCase):
    def test_merits_with_a_rate(self):
        self.assertEqual(M.summary_text(1234, 2.0), "Merits this session: +1,234 (+617 merits/hr)")

    def test_no_rate_until_the_session_has_run_a_few_minutes(self):
        self.assertEqual(M.summary_text(500, 0.01), "Merits this session: +500")
        self.assertEqual(M.summary_text(500, 0.0), "Merits this session: +500")

    def test_no_rate_for_no_merits(self):
        self.assertEqual(M.summary_text(0, 3.0), "Merits this session: +0")


class HoursTests(unittest.TestCase):
    def test_hours_are_measured_in_utc_to_the_given_moment(self):
        start = "2026-10-12T08:00:00Z"
        epoch = calendar.timegm(time.strptime(start, "%Y-%m-%dT%H:%M:%SZ"))
        self.assertAlmostEqual(M.hours_since(start, epoch + 5400), 1.5)

    def test_a_missing_or_bad_start_is_zero_hours(self):
        for bad in (None, "", "yesterday"):
            self.assertEqual(M.hours_since(bad, 1_000_000), 0.0)

    def test_a_start_in_the_future_is_zero_hours(self):
        self.assertEqual(M.hours_since("2999-01-01T00:00:00Z", 1_000_000), 0.0)


if __name__ == "__main__":
    unittest.main()
