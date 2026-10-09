"""
Builds the whole WNTB Settings tab the way EDMC would and fails if any tab raises.

A tab that raises while building makes EDMC log `Failed for Plugin "WNTB"` and drop the
entire WNTB Settings tab, on Windows and Linux alike. The stand-in widgets in tests/prefs_smoke.py
copy EDMC's real myNotebook behaviour (ttk widgets; every nb.Frame holds a gridded spacer child),
so mistakes such as packing into an nb.Frame are caught here instead of by a user. Skipped when
Tk has no display. Run with: python -m unittest discover -s tests
"""

from __future__ import annotations

import os
import subprocess
import sys
import unittest


class PrefsSmokeTests(unittest.TestCase):
    def test_every_settings_tab_builds(self) -> None:
        script = os.path.join(os.path.dirname(__file__), "prefs_smoke.py")
        result = subprocess.run([sys.executable, script], capture_output=True, text=True, timeout=120)
        if result.returncode == 77:
            self.skipTest("Tk has no display here")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("SETTINGS BUILT OK", result.stdout)
        self.assertIn("Window", result.stdout)  # the window-behaviour tab (auto height fit)
        # Grouped layout: nine top-level tabs, and the merged Exploration pages are all there.
        self.assertIn("SETTINGS BUILT OK: 9 top-level tabs", result.stdout)
        for leaf in ("Exploration > Points of Interest", "Exploration > Alerts", "General > Overlay Connection",
                     "Always On > Landing", "Field Ops > Inventory"):
            self.assertIn(leaf, result.stdout)


if __name__ == "__main__":
    unittest.main()
