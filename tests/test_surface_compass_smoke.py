"""
Runs the Surface Compass and the Marks window with EDMC, the overlay and the clock stubbed (surface_compass_smoke.py) and fails if the maths,
the choice of target, marking, cycling, the overlay's drawing and clearing, the carry-over of the old Mining waypoint settings, the panel
row's width or the window misbehave. Skipped when Tk has no display.
Run with: python -m unittest discover -s tests
"""

from __future__ import annotations

import os
import subprocess
import sys
import unittest


class SurfaceCompassSmokeTests(unittest.TestCase):
    def test_the_compass_the_panel_row_and_the_window_work(self) -> None:
        script = os.path.join(os.path.dirname(__file__), "surface_compass_smoke.py")
        result = subprocess.run([sys.executable, script], capture_output=True, text=True, timeout=180)
        if result.returncode == 77:
            self.skipTest("Tk has no display here")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("SURFACE COMPASS OK", result.stdout)


if __name__ == "__main__":
    unittest.main()
