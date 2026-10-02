"""
Unit tests for plugin/http_identity.py and the rule that every web client
identifies WNTB.

Run with: python -m unittest discover -s tests
"""

from __future__ import annotations

import glob
import os
import re
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from plugin import __version__  # noqa: E402
from plugin import http_identity  # noqa: E402

PLUGIN_DIR = os.path.join(os.path.dirname(__file__), "..", "plugin")


class UserAgentTests(unittest.TestCase):
    def test_names_wntb_version_feature_and_project(self) -> None:
        agent = http_identity.user_agent("rare-goods")
        self.assertTrue(agent.startswith(f"WNTB/{__version__} "))
        self.assertIn("rare-goods", agent)
        self.assertIn(http_identity.HOMEPAGE, agent)

    def test_feature_is_optional(self) -> None:
        self.assertNotIn(";", http_identity.user_agent())


class EveryClientIdentifiesItselfTests(unittest.TestCase):
    def test_no_module_sets_its_own_hard_coded_user_agent(self) -> None:
        # A literal "User-Agent" value would bypass http_identity (and so the
        # project name/address). Header names are fine; values must come from it.
        offenders = []
        for path in glob.glob(os.path.join(PLUGIN_DIR, "*.py")):
            if os.path.basename(path) == "http_identity.py":
                continue
            with open(path, encoding="utf-8") as handle:
                text = handle.read()
            if re.search(r"_USER_AGENT\s*=\s*[\"']", text) or re.search(r"[\"']User-Agent[\"']\s*:\s*[\"']", text):
                offenders.append(os.path.basename(path))
        self.assertEqual(offenders, [])


if __name__ == "__main__":
    unittest.main()
