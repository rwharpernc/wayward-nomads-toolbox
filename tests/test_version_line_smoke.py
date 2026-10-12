"""
The plugin version line above the game-mode line in the EDMC panel (ui.py): "Plugin: vX", and in bold black on orange
"vY download - Restart EDMC" once an update is staged, including an update that finished before the panel was built.
Built with stand-ins in tests/version_line_smoke.py in a subprocess. Skipped when Tk has no display.
"""

from __future__ import annotations

import os
import subprocess
import sys
import unittest


class VersionLineSmokeTests(unittest.TestCase):
    def test_version_line_shows_each_update_state(self) -> None:
        script = os.path.join(os.path.dirname(__file__), "version_line_smoke.py")
        result = subprocess.run([sys.executable, script], capture_output=True, text=True, timeout=120)
        if result.returncode == 77:
            self.skipTest("Tk has no display here")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("VERSION LINE: OK", result.stdout)


if __name__ == "__main__":
    unittest.main()
