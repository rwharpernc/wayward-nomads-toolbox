"""
Opens the Nearest place to land window and the Exploration row with EDMC stubbed, and fails if the row, the consent box, the choices passed on, the lists or the messages misbehave.
Skipped when Tk has no display.
Run with: python -m unittest discover -s tests
"""

from __future__ import annotations

import os
import subprocess
import sys
import unittest


class LandingFinderSmokeTests(unittest.TestCase):
    def test_the_window_and_the_row_work(self) -> None:
        script = os.path.join(os.path.dirname(__file__), "landing_finder_smoke.py")
        result = subprocess.run([sys.executable, script], capture_output=True, text=True, timeout=180)
        if result.returncode == 77:
            self.skipTest("Tk has no display here")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("LANDING FINDER OK", result.stdout)


if __name__ == "__main__":
    unittest.main()
