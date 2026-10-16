"""
Runs the System targets and Body info cards with EDMC, the overlay and the clock stubbed (system_cards_smoke.py) and fails if a card says the wrong
thing, picks the wrong body, redraws at the wrong time, or does not start every line at the same left edge.
Run with: python -m unittest discover -s tests
"""

from __future__ import annotations

import os
import subprocess
import sys
import unittest


class SystemCardsSmokeTests(unittest.TestCase):
    def test_the_cards_behave(self) -> None:
        script = os.path.join(os.path.dirname(__file__), "system_cards_smoke.py")
        result = subprocess.run([sys.executable, script], capture_output=True, text=True, timeout=120)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("SYSTEM CARDS OK", result.stdout)


if __name__ == "__main__":
    unittest.main()
