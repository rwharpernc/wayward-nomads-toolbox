"""
Opens the Notes window and the Notes panel row with EDMC stubbed, and fails if writing, searching, changing or deleting a note, or the
panel row's follow of the system and the commander, misbehaves. Skipped when Tk has no display.
Run with: python -m unittest discover -s tests
"""

from __future__ import annotations

import os
import subprocess
import sys
import unittest


class NotesWindowSmokeTests(unittest.TestCase):
    def test_the_window_and_the_panel_row_work(self) -> None:
        script = os.path.join(os.path.dirname(__file__), "notes_window_smoke.py")
        result = subprocess.run([sys.executable, script], capture_output=True, text=True, timeout=180)
        if result.returncode == 77:
            self.skipTest("Tk has no display here")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("NOTES OK", result.stdout)


if __name__ == "__main__":
    unittest.main()
