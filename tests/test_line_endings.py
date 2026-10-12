"""
Source, docs and scripts are LF on every machine.

`.gitattributes` makes Git store LF, but an editor or tool on Windows can still write CRLF into the working tree, which makes
Git print "CRLF will be replaced by LF" on every touch and shows whole-file diffs. This fails on the first file that has any, so
it is fixed before it is committed. It reads the files directly, so it behaves the same on Windows and Linux.
"""
from __future__ import annotations

import os
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SKIP_DIRS = {".git", "dist", "node_modules", "__pycache__", ".claude"}
TEXT_EXTENSIONS = {".py", ".md", ".mjs", ".js", ".json", ".txt", ".toml", ".yml", ".yaml", ".cfg", ".ini", ".gitignore",
                   ".gitattributes", ".editorconfig"}


def _text_files():
    for folder, dirs, names in os.walk(ROOT):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for name in names:
            if os.path.splitext(name)[1].lower() in TEXT_EXTENSIONS or name.startswith("."):
                yield os.path.join(folder, name)


class LineEndingTests(unittest.TestCase):
    def test_no_crlf_in_text_files(self):
        bad = []
        for path in _text_files():
            with open(path, "rb") as handle:
                if b"\r" in handle.read():
                    bad.append(os.path.relpath(path, ROOT))
        self.assertEqual(bad, [], "CRLF line endings (convert to LF, e.g. `sed -i 's/\r$//' <file>`): " + ", ".join(bad))


if __name__ == "__main__":
    unittest.main()
