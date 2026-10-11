"""
Draws every WNTB overlay display (EDMC stubbed) at 144 looks - every color scheme, four text sizes, three paddings, two line spacings -
and fails if any text would run outside its card, if a display's block rectangle disagrees with what it draws, or if the legacy look no
longer reproduces the sizes the displays always had. Run with: python -m unittest discover -s tests
"""

from __future__ import annotations

import os
import subprocess
import sys
import unittest


class OverlayLookSmokeTests(unittest.TestCase):
    def test_every_display_fits_its_text_at_every_look(self) -> None:
        script = os.path.join(os.path.dirname(__file__), "overlay_look_smoke.py")
        result = subprocess.run([sys.executable, script], capture_output=True, text=True, timeout=180)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("OVERLAY LOOKS OK: 144 looks", result.stdout)


if __name__ == "__main__":
    unittest.main()
