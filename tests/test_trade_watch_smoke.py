"""
Opens the Watch list window and the Trade row with EDMC stubbed, and fails if adding, removing, keeping prices from a Market event, the
Spansh refresh, or the row's width misbehaves. Skipped when Tk has no display.
Run with: python -m unittest discover -s tests
"""

from __future__ import annotations

import os
import subprocess
import sys
import unittest


class TradeWatchSmokeTests(unittest.TestCase):
    def test_the_window_and_the_row_work(self) -> None:
        script = os.path.join(os.path.dirname(__file__), "trade_watch_smoke.py")
        result = subprocess.run([sys.executable, script], capture_output=True, text=True, timeout=180)
        if result.returncode == 77:
            self.skipTest("Tk has no display here")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("WATCH OK", result.stdout)


if __name__ == "__main__":
    unittest.main()
