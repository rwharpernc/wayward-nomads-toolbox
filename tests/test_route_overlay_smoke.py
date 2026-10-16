"""
Runs the Route overlay with EDMC, the overlay, the clock and the route file stubbed (route_overlay_smoke.py) and fails if the card says
the wrong thing, redraws at the wrong time, does not start every line at the same left edge, or does not clear when the ship leaves the
route.
Run with: python -m unittest discover -s tests
"""

from __future__ import annotations

import os
import subprocess
import sys
import unittest


class RouteOverlaySmokeTests(unittest.TestCase):
    def test_the_overlay_behaves(self) -> None:
        script = os.path.join(os.path.dirname(__file__), "route_overlay_smoke.py")
        result = subprocess.run([sys.executable, script], capture_output=True, text=True, timeout=120)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("ROUTE OVERLAY OK", result.stdout)


if __name__ == "__main__":
    unittest.main()
