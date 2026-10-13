"""
Runs the Flight Alerts controller with EDMC, the overlay, the clock and the sound stubbed (flight_alerts_smoke.py) and fails if the
card says the wrong thing, redraws at the wrong time, sounds twice, or moves as its lines change.
Run with: python -m unittest discover -s tests
"""

from __future__ import annotations

import os
import subprocess
import sys
import unittest


class FlightAlertsSmokeTests(unittest.TestCase):
    def test_the_controller_behaves(self) -> None:
        script = os.path.join(os.path.dirname(__file__), "flight_alerts_smoke.py")
        result = subprocess.run([sys.executable, script], capture_output=True, text=True, timeout=120)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("FLIGHT ALERTS OK", result.stdout)


if __name__ == "__main__":
    unittest.main()
