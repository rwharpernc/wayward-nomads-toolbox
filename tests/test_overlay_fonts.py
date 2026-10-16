"""overlay_fonts: listing the overlay's fonts, putting one first in preferred_fonts.txt, and adding a font file."""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from plugin import overlay_fonts as F  # noqa: E402


def touch(folder, name, data=b"font"):
    with open(os.path.join(folder, name), "wb") as handle:
        handle.write(data)


class FontsTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.folder = os.path.join(self._tmp.name, "fonts")
        os.makedirs(self.folder)
        for name in ("Eurocaps.ttf", "SourceSans3-Regular.ttf", "NotoColorEmoji.ttf", "unifont-17.otf", "README.txt"):
            touch(self.folder, name)
        with open(os.path.join(self.folder, F.PREFERRED_FILE), "w", encoding="utf-8") as handle:
            handle.write("; comment\nEurocaps.ttf\n")

    def test_the_fonts_dir_is_inside_the_overlay_plugin(self):
        self.assertEqual(F.fonts_dir("plugins"), os.path.join("plugins", "EDMCModernOverlay", "overlay_client", "fonts"))

    def test_installed_lists_fonts_but_not_emoji_symbols_or_other_files(self):
        self.assertEqual(F.installed(self.folder), ["Eurocaps.ttf", "SourceSans3-Regular.ttf"])
        self.assertEqual(F.installed(os.path.join(self._tmp.name, "missing")), [])

    def test_current_and_preferred_skip_comments(self):
        self.assertEqual(F.preferred(self.folder), ["Eurocaps.ttf"])
        self.assertEqual(F.current(self.folder), "Eurocaps.ttf")
        self.assertTrue(F.is_default(F.current(self.folder)))

    def test_set_first_puts_the_choice_on_top_and_keeps_the_rest_and_a_backup(self):
        F.set_first(self.folder, "SourceSans3-Regular.ttf")
        self.assertEqual(F.preferred(self.folder), ["SourceSans3-Regular.ttf", "Eurocaps.ttf"])
        self.assertFalse(F.is_default(F.current(self.folder)))
        backup = os.path.join(self.folder, F.PREFERRED_FILE + ".bak")
        self.assertTrue(os.path.exists(backup))
        F.set_first(self.folder, "sourcesans3-regular.ttf")            # again, in another case: no duplicate
        self.assertEqual(len(F.preferred(self.folder)), 2)
        with open(backup, encoding="utf-8") as handle:
            self.assertIn("Eurocaps.ttf", handle.read())             # the backup is the original, kept once

    def test_an_empty_choice_restores_the_default(self):
        F.set_first(self.folder, "SourceSans3-Regular.ttf")
        F.set_first(self.folder, "")
        self.assertEqual(F.current(self.folder), "Eurocaps.ttf")

    def test_the_file_is_written_with_unix_line_endings(self):
        F.set_first(self.folder, "SourceSans3-Regular.ttf")
        with open(os.path.join(self.folder, F.PREFERRED_FILE), "rb") as handle:
            self.assertNotIn(b"\r", handle.read())

    def test_wntb_has_its_own_fonts_folder_with_the_bundled_font_and_its_license(self):
        self.assertEqual(F.own_dir("plugin"), os.path.join("plugin", "fonts"))
        folder = F.own_dir(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "plugin"))
        self.assertIn(F.BUNDLED, F.installed(folder))
        self.assertTrue(os.path.isfile(os.path.join(folder, "SourceSans3-OFL.txt")))              # the font's license travels with it

    def test_add_font_copies_a_font_file(self):
        source = os.path.join(self._tmp.name, "Lato-Regular.ttf")
        touch(self._tmp.name, "Lato-Regular.ttf")
        name, problem = F.add_font(self.folder, source)
        self.assertEqual((name, problem), ("Lato-Regular.ttf", ""))
        self.assertIn("Lato-Regular.ttf", F.installed(self.folder))

    def test_add_font_refuses_what_is_not_a_font(self):
        touch(self._tmp.name, "notes.txt")
        touch(self._tmp.name, "empty.ttf", b"")
        self.assertIsNone(F.add_font(self.folder, os.path.join(self._tmp.name, "notes.txt"))[0])
        self.assertIsNone(F.add_font(self.folder, os.path.join(self._tmp.name, "empty.ttf"))[0])
        self.assertIsNone(F.add_font(self.folder, os.path.join(self._tmp.name, "absent.ttf"))[0])
        touch(self._tmp.name, "A.ttf")
        self.assertIsNone(F.add_font(os.path.join(self._tmp.name, "nowhere"), os.path.join(self._tmp.name, "A.ttf"))[0])


if __name__ == "__main__":
    unittest.main()
