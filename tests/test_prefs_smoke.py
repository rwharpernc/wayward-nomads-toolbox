"""
Builds the whole WNTB Settings tab the way EDMC would and fails if any tab raises.

A tab that raises while building makes EDMC log `Failed for Plugin "WNTB"` and drop the
entire WNTB Settings tab, on Windows and Linux alike. The stand-in widgets in tests/prefs_smoke.py
copy EDMC's real myNotebook behavior (ttk widgets; every nb.Frame holds a gridded spacer child),
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
        self.assertIn("Window", result.stdout)  # the window-behavior tab (auto height fit)
        # Grouped layout: ten top-level tabs, and the merged Exploration pages are all there.
        self.assertIn("SETTINGS BUILT OK: 10 top-level tabs", result.stdout)
        # Every page is wrapped in a scroller capped in height, so a long page can't push OK off the screen.
        self.assertIn("PAGES OVER HEIGHT CAP: 0 of 35", result.stdout)
        for leaf in ("Exploration > Points of Interest", "Exploration > Auto-Honk", "Field Ops > Inventory"):
            self.assertIn(leaf, result.stdout)
        # Every overlay setting and toggle is under one Overlays tab, a subtab per feature that draws on the overlay.
        for leaf in ("Overlays > Overlay Connection", "Overlays > Overlay Placement", "Overlays > Appearance", "Overlays > Colonization",
                     "Overlays > Discovery", "Overlays > Inventory", "Overlays > Interdiction Warning",
                     "Overlays > Landing", "Overlays > Mining", "Overlays > Notable Bodies", "Overlays > Screenshots", "Overlays > Missions"):
            self.assertIn(leaf, result.stdout)
        self.assertIn("OVERLAY APPEARANCE SAVED: 1 of 1", result.stdout)
        self.assertIn("OVERLAY PLACEMENTS SAVED: 18 of 18", result.stdout)     # saving works across the split tabs
        for gone in ("General > Overlay", "Always On"):
            self.assertNotIn(gone, result.stdout)


if __name__ == "__main__":
    unittest.main()
