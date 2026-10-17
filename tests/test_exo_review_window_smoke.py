"""
Opens the Prediction review window with EDMC stubbed, and fails if its tables, filter, review box or report misbehave. Skipped when Tk has no display.
Run with: python -m unittest discover -s tests
"""

from __future__ import annotations

import os
import subprocess
import sys
import unittest


class ExoReviewWindowSmokeTests(unittest.TestCase):
    def test_the_window_reviews_and_keeps_finds(self) -> None:
        script = os.path.join(os.path.dirname(__file__), "exo_review_window_smoke.py")
        result = subprocess.run([sys.executable, script], capture_output=True, text=True, timeout=180)
        if result.returncode == 77:
            self.skipTest("Tk has no display here")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("EXO REVIEW OK", result.stdout)


if __name__ == "__main__":
    unittest.main()
