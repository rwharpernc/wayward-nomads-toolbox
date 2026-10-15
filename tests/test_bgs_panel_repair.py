"""
The BGS panel rebuilds a period that closed while EDMC was not running, from the journals (tests/bgs_panel_repair_smoke.py, run in a subprocess so
its EDMC stand-ins stay out of the other tests). Run with: python -m unittest discover -s tests
"""

from __future__ import annotations

import os
import subprocess
import sys
import unittest


class BgsPanelRepairTests(unittest.TestCase):
    def test_a_closed_period_is_rebuilt_from_the_journals(self) -> None:
        script = os.path.join(os.path.dirname(__file__), "bgs_panel_repair_smoke.py")
        result = subprocess.run([sys.executable, script], capture_output=True, text=True, timeout=120)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("BGS REPAIR OK", result.stdout)


if __name__ == "__main__":
    unittest.main()
