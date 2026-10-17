"""
Runs system_name_room_smoke.py with EDMC stubbed and fails if any overlay card cuts a long system or body name with an ellipsis.
Run with: python -m unittest discover -s tests
"""

from __future__ import annotations

import os
import subprocess
import sys
import unittest


class SystemNameRoomSmokeTests(unittest.TestCase):
    def test_every_card_shows_the_whole_name(self) -> None:
        script = os.path.join(os.path.dirname(__file__), "system_name_room_smoke.py")
        result = subprocess.run([sys.executable, script], capture_output=True, text=True, timeout=120)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("SYSTEM NAME ROOM OK", result.stdout)


if __name__ == "__main__":
    unittest.main()
