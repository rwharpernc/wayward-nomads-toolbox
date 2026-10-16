"""
Opens the Expedition Log row and window with EDMC stubbed and feeds them journal-shaped events, and fails if the counting, START and STOP, the editor, Reset and Delete, Rescan,
Copy summary, Export CSV, a commander change or the overlay card misbehave. Skipped when Tk has no display.
Run with: python -m unittest discover -s tests
"""

from __future__ import annotations

import os
import subprocess
import sys
import unittest


class ExpeditionLogSmokeTests(unittest.TestCase):
    def test_the_log_works(self) -> None:
        script = os.path.join(os.path.dirname(__file__), "expedition_log_smoke.py")
        result = subprocess.run([sys.executable, script], capture_output=True, text=True, timeout=180)
        if result.returncode == 77:
            self.skipTest("Tk has no display here")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("EXPEDITION LOG OK", result.stdout)


if __name__ == "__main__":
    unittest.main()
