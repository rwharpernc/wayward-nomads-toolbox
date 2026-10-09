"""
Opens the Trade History window with sample sessions (EDMC stubbed) and fails if a table would be clipped at the window's
minimum size, or if picking, filtering, copying, deleting or refreshing misbehaves. Skipped when Tk has no display.
Run with: python -m unittest discover -s tests
"""

from __future__ import annotations

import os
import subprocess
import sys
import unittest


class TradeHistoryWindowSmokeTests(unittest.TestCase):
    def test_every_tab_fits_and_the_actions_work(self) -> None:
        script = os.path.join(os.path.dirname(__file__), "trade_history_window_smoke.py")
        result = subprocess.run([sys.executable, script], capture_output=True, text=True, timeout=180)
        if result.returncode == 77:
            self.skipTest("Tk has no display here")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("TRADE HISTORY WINDOW OK", result.stdout)


if __name__ == "__main__":
    unittest.main()
