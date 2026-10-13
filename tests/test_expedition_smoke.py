"""
Opens the Expedition row with EDMC stubbed and feeds it journal-shaped events, and fails if the lines, the ticking off of stops, the distance and
notes, COPY and copy-on-arrival, a commander change or the row's width misbehave. Skipped when Tk has no display.
Run with: python -m unittest discover -s tests
"""

from __future__ import annotations

import os
import subprocess
import sys
import unittest


class ExpeditionSmokeTests(unittest.TestCase):
    def test_the_row_works(self) -> None:
        script = os.path.join(os.path.dirname(__file__), "expedition_smoke.py")
        result = subprocess.run([sys.executable, script], capture_output=True, text=True, timeout=180)
        if result.returncode == 77:
            self.skipTest("Tk has no display here")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("EXPEDITION OK", result.stdout)


if __name__ == "__main__":
    unittest.main()
