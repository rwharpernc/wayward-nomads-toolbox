"""
Import smoke test: every plugin module imports under EDMC-style conditions.

The unit tests import single modules with a stubbed `config`, so they never
exercise load.py or the module graph around it - which is how a package named
`ui` (shadowing ui.py) once shipped and stopped WNTB loading at all. This runs
tests/import_smoke.py in a subprocess (its EDMC stand-ins must not leak into
other tests). Run with: python -m unittest discover -s tests
"""

from __future__ import annotations

import os
import subprocess
import sys
import unittest


class ImportSmokeTests(unittest.TestCase):
    def test_every_plugin_module_imports_and_ui_is_the_panel_module(self) -> None:
        script = os.path.join(os.path.dirname(__file__), "import_smoke.py")
        result = subprocess.run([sys.executable, script], capture_output=True, text=True, timeout=120)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
