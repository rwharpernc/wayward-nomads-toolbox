"""
Unit tests for the journal-filename handling in plugin/screenshot_naming.py.

Pure logic - run with: python -m unittest discover -s tests
"""

from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from plugin import screenshot_naming as naming  # noqa: E402


class JournalFilenameTests(unittest.TestCase):
    def test_windows_style_journal_path_gives_the_file_name_on_any_os(self) -> None:
        # Elite writes backslashes even under Proton; POSIX basename() would keep them all.
        self.assertEqual(naming.journal_basename("\\ED_Pictures\\Screenshot_0001.bmp"), "Screenshot_0001.bmp")

    def test_forward_slashes_and_bare_names_work_too(self) -> None:
        self.assertEqual(naming.journal_basename("/ED_Pictures/Screenshot_0002.bmp"), "Screenshot_0002.bmp")
        self.assertEqual(naming.journal_basename("Screenshot_0003.bmp"), "Screenshot_0003.bmp")

    def test_high_res_is_detected_from_a_windows_style_path(self) -> None:
        self.assertTrue(naming.is_high_res("\\ED_Pictures\\HighRes_0001.png"))
        self.assertFalse(naming.is_high_res("\\ED_Pictures\\Screenshot_0001.bmp"))


if __name__ == "__main__":
    unittest.main()
