"""
Opens the Colonization Sites window with sample sites (EDMC stubbed) and fails if picking, filtering, sorting,
following the commander or removing misbehaves. Skipped when Tk has no display.
Run with: python -m unittest discover -s tests
"""

from __future__ import annotations

import os
import subprocess
import sys
import unittest


class ColonisationWindowSmokeTests(unittest.TestCase):
    def test_the_window_builds_and_the_actions_work(self) -> None:
        script = os.path.join(os.path.dirname(__file__), "colonisation_window_smoke.py")
        result = subprocess.run([sys.executable, script], capture_output=True, text=True, timeout=180)
        if result.returncode == 77:
            self.skipTest("Tk has no display here")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("COLONISATION WINDOW OK", result.stdout)


if __name__ == "__main__":
    unittest.main()
