"""
Unit tests for plugin/issue_report.py: the prefilled GitHub issue address.

Run with: python -m unittest discover -s tests
"""

from __future__ import annotations

import os
import sys
import unittest
from unittest import mock
from urllib.parse import parse_qs, urlparse

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from plugin import __version__  # noqa: E402
from plugin import issue_report  # noqa: E402

TEMPLATE_PATH = os.path.join(os.path.dirname(__file__), "..", ".github", "ISSUE_TEMPLATE", "bug_report.yml")


class BuildUrlTests(unittest.TestCase):
    def test_points_at_the_new_issue_form_with_the_template(self) -> None:
        url = issue_report.build_url("- OS: test")
        parts = urlparse(url)
        self.assertEqual(f"{parts.scheme}://{parts.netloc}{parts.path}", issue_report.NEW_ISSUE_URL)
        query = parse_qs(parts.query)
        self.assertEqual(["bug_report.yml"], query["template"])
        self.assertEqual(["bug"], query["labels"])
        self.assertEqual(["- OS: test"], query["environment"])
        self.assertIn(__version__, query["title"][0])

    def test_environment_names_the_versions_and_os_and_nothing_personal(self) -> None:
        text = issue_report.environment_text(edmc="5.13.0", system="TestOS 1")
        self.assertIn(f"WNTB: {__version__}", text)
        self.assertIn("EDMC: 5.13.0", text)
        self.assertIn("Python: ", text)
        self.assertIn("OS: TestOS 1", text)
        self.assertEqual(4, len(text.splitlines()))

    def test_default_url_is_short(self) -> None:
        self.assertLess(len(issue_report.build_url()), issue_report.MAX_URL_LENGTH)

    def test_oversized_prefill_falls_back_to_the_plain_form(self) -> None:
        url = issue_report.build_url("x" * 5000)
        self.assertNotIn("environment", url)
        self.assertIn("template=bug_report.yml", url)

    def test_open_report_opens_the_built_address(self) -> None:
        with mock.patch.object(issue_report.webbrowser, "open") as opened:
            issue_report.open_report()
        opened.assert_called_once()
        self.assertTrue(opened.call_args[0][0].startswith(issue_report.NEW_ISSUE_URL))


LOG = r"""2026-10-14 14:56:50.352 UTC - INFO - 1:2:3 <plugins>.WNTB.inventory_panel.Panel.run:808: Docked as Silas Kade in C:\Users\bob\x
2026-10-14 14:56:51.000 UTC - INFO - 1:2:3 <plugins>.OtherPlugin.mod.f:1: not ours
2026-10-14 14:56:52.000 UTC - ERROR - 1:2:3 <plugins>.WNTB.load.journal_entry:9: failed
Traceback (most recent call last):
  File "x.py", line 1, in f
ValueError: boom
"""


class DiagnosticsTests(unittest.TestCase):
    def test_keeps_only_wntb_records_with_their_tracebacks(self) -> None:
        lines = issue_report.wntb_log_lines(LOG, "WNTB")
        self.assertEqual(5, len(lines))
        self.assertFalse(any("OtherPlugin" in line for line in lines))
        self.assertIn("ValueError: boom", lines[-1])

    def test_keeps_only_the_newest_lines(self) -> None:
        lines = issue_report.wntb_log_lines(LOG, "WNTB", limit=2)
        self.assertEqual(2, len(lines))
        self.assertIn("ValueError: boom", lines[-1])

    def test_redacts_commander_in_any_case_and_the_home_folder(self) -> None:
        text = issue_report.redact(r"Silas Kade / SILAS KADE in C:\Users\bob\x and C:/Users/bob/y",
                                   ["silas kade"], home=r"C:\Users\bob")
        self.assertNotIn("ilas", text)
        self.assertNotIn("bob", text)
        self.assertEqual(r"<commander> / <commander> in ~\x and ~/y", text)

    def test_blank_names_redact_nothing(self) -> None:
        self.assertEqual("abc", issue_report.redact("abc", ["", "  "], home="~"))

    def test_diagnostics_text_has_environment_and_redacted_log(self) -> None:
        with mock.patch.object(issue_report, "_plugin_dir", "WNTB"):
            text = issue_report.diagnostics_text(LOG, ["Silas Kade"], home=r"C:\Users\bob")
        self.assertIn(f"WNTB: {__version__}", text)
        self.assertIn("<commander>", text)
        self.assertNotIn("Silas", text)
        self.assertNotIn("OtherPlugin", text)

    def test_no_wntb_lines_says_so(self) -> None:
        self.assertIn("no WNTB lines", issue_report.diagnostics_text("nothing here\n"))

    def test_read_log_tail_of_a_missing_file_is_empty(self) -> None:
        self.assertEqual("", issue_report.read_log_tail(os.path.join(os.path.dirname(__file__), "nope.log")))

    def test_copy_diagnostics_hands_text_to_the_clipboard(self) -> None:
        with mock.patch.object(issue_report, "log_path", return_value=""), \
                mock.patch.object(issue_report, "commander_names", return_value=[]):
            widget = mock.MagicMock()
            self.assertTrue(issue_report.copy_diagnostics(widget))
        self.assertIn(f"WNTB: {__version__}", widget.clipboard_append.call_args[0][0])


class TemplateTests(unittest.TestCase):
    def test_template_has_the_prefilled_field_id(self) -> None:
        with open(TEMPLATE_PATH, encoding="utf-8") as handle:
            self.assertIn(f"id: {issue_report.ENVIRONMENT_FIELD}", handle.read())


if __name__ == "__main__":
    unittest.main()
