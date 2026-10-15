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


class TemplateTests(unittest.TestCase):
    def test_template_has_the_prefilled_field_id(self) -> None:
        with open(TEMPLATE_PATH, encoding="utf-8") as handle:
            self.assertIn(f"id: {issue_report.ENVIRONMENT_FIELD}", handle.read())


if __name__ == "__main__":
    unittest.main()
