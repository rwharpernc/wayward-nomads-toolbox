"""
Every data file a plugin module writes beside the plugin must be listed in update.py's _OWN_DATA_FILES,
or the pre-update backup sweeps it up like code (docs/TECHNICAL.md, "Known gaps"). This reads the
sources instead of importing them, so it needs no EDMC stand-ins.

Run with: python -m unittest discover -s tests
"""

from __future__ import annotations

import glob
import os
import re
import unittest

ROOT = os.path.join(os.path.dirname(__file__), "..")


def _read(path: str) -> str:
    with open(path, "r", encoding="utf-8") as handle:
        return handle.read()


class OwnDataFilesTests(unittest.TestCase):
    def test_every_data_file_constant_is_protected(self) -> None:
        update_source = _read(os.path.join(ROOT, "plugin", "update.py"))
        block = update_source[update_source.index("_OWN_DATA_FILES: set"):update_source.index("_OWN_DIRS =")]
        protected = set(re.findall(r'"([^"]+\.(?:json|csv))"', block))
        self.assertIn("sessions.json", protected, "the parse found nothing; the test is broken")

        missing = {}
        for path in glob.glob(os.path.join(ROOT, "plugin", "*.py")):
            for match in re.finditer(r'^[A-Z_]*FILENAME\w*\s*=\s*"([^"]+\.(?:json|csv))"', _read(path), re.M):
                if match.group(1) not in protected:
                    missing[match.group(1)] = os.path.basename(path)
        self.assertEqual(missing, {}, "add these to _OWN_DATA_FILES in plugin/update.py")


if __name__ == "__main__":
    unittest.main()
