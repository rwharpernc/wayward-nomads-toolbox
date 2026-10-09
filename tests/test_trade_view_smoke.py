"""
Draws Trade mode's page in a real Tk window (EDMC stubbed) and fails if any label would widen EDMC's narrow main
window, if unchanged blocks are redrawn, or if a table's number columns don't line up. The page is the part of Trade
that can't be unit-tested as text, and "it got wider than the window and was clipped" is exactly the bug it guards
against. Skipped when Tk has no display. Run with: python -m unittest discover -s tests
"""

from __future__ import annotations

import os
import subprocess
import sys
import unittest


class TradeViewSmokeTests(unittest.TestCase):
    def test_the_page_fits_and_lines_up(self) -> None:
        script = os.path.join(os.path.dirname(__file__), "trade_view_smoke.py")
        result = subprocess.run([sys.executable, script], capture_output=True, text=True, timeout=120)
        if result.returncode == 77:
            self.skipTest("Tk has no display here")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("TRADE VIEW OK", result.stdout)


if __name__ == "__main__":
    unittest.main()
