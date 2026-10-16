"""Runs the Exobiology overlay checks (exobiology_checks.py) in their own process: they stub EDMC's config, and the modules they import keep that stub, which
would reach the placement and trade tests that install their own. Run with: python -m unittest discover -s tests"""

from __future__ import annotations

import os
import subprocess
import sys
import unittest


class ExobiologyOverlayTests(unittest.TestCase):
    def test_the_cards_the_radar_and_the_view_behave(self) -> None:
        script = os.path.join(os.path.dirname(__file__), "exobiology_checks.py")
        result = subprocess.run([sys.executable, script], capture_output=True, text=True, timeout=120)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
