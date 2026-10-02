"""
Unit tests for plugin/platform_support.py (Linux/Wine-prefix helpers).

No EDMC runtime or Linux needed - filesystem cases use temp dirs and
subprocess is mocked. Run with:
    python -m unittest discover -s tests
"""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from plugin import platform_support as ps  # noqa: E402


def _make_prefix(root: str, user: str = "steamuser") -> str:
    prefix = os.path.join(root, "steamapps", "compatdata", ps.ELITE_STEAM_APP_ID, "pfx")
    os.makedirs(os.path.join(prefix, "drive_c", "users", user), exist_ok=True)
    os.makedirs(os.path.join(prefix, "drive_c", "users", "Public"), exist_ok=True)
    return prefix


class X11KeysymTests(unittest.TestCase):
    def test_letters_digits_and_function_keys(self) -> None:
        self.assertEqual(ps.x11_keysym("Key_G"), "g")
        self.assertEqual(ps.x11_keysym("Key_7"), "7")
        self.assertEqual(ps.x11_keysym("Key_F10"), "F10")
        self.assertEqual(ps.x11_keysym("Key_F24"), "F24")

    def test_numpad_and_named_keys(self) -> None:
        self.assertEqual(ps.x11_keysym("Key_Numpad_5"), "KP_5")
        self.assertEqual(ps.x11_keysym("Key_Numpad_Divide"), "KP_Divide")
        self.assertEqual(ps.x11_keysym("Key_PageUp"), "Prior")
        self.assertEqual(ps.x11_keysym("Key_Space"), "space")
        self.assertEqual(ps.x11_keysym("Key_LeftControl"), "Control_L")

    def test_unsupported_keys_return_none(self) -> None:
        self.assertIsNone(ps.x11_keysym("Key_F25"))
        self.assertIsNone(ps.x11_keysym("Key_Nonsense"))
        self.assertIsNone(ps.x11_keysym("Mouse_1"))


class PrefixDetectionTests(unittest.TestCase):
    def test_finds_steam_proton_prefix(self) -> None:
        with tempfile.TemporaryDirectory() as home:
            steam = os.path.join(home, ".local", "share", "Steam")
            prefix = _make_prefix(steam)
            self.assertEqual(os.path.realpath(ps.find_elite_prefix(home=home)), os.path.realpath(prefix))

    def test_finds_prefix_in_extra_library_folder(self) -> None:
        with tempfile.TemporaryDirectory() as home, tempfile.TemporaryDirectory() as library:
            steam = os.path.join(home, ".local", "share", "Steam")
            os.makedirs(os.path.join(steam, "steamapps"))
            with open(os.path.join(steam, "steamapps", "libraryfolders.vdf"), "w", encoding="utf-8") as fh:
                fh.write('"libraryfolders"\n{\n "1"\n {\n  "path"\t\t"%s"\n }\n}\n' % library.replace("\\", "\\\\"))
            prefix = _make_prefix(library)
            self.assertEqual(os.path.realpath(ps.find_elite_prefix(home=home)), os.path.realpath(prefix))

    def test_none_when_no_steam(self) -> None:
        with tempfile.TemporaryDirectory() as home:
            self.assertIsNone(ps.find_elite_prefix(home=home))

    def test_override_accepts_prefix_pfx_or_compatdata_folder(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            prefix = _make_prefix(root)
            compatdata = os.path.dirname(prefix)
            self.assertEqual(ps.find_elite_prefix(prefix), prefix)
            self.assertEqual(ps.find_elite_prefix(compatdata), prefix)

    def test_bad_override_does_not_fall_back_to_autodetect(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            self.assertIsNone(ps.find_elite_prefix(os.path.join(root, "nope")))


class PrefixUserDirTests(unittest.TestCase):
    def test_prefers_steamuser_and_skips_public(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            prefix = _make_prefix(root)
            self.assertTrue(ps.prefix_user_dir(prefix).endswith("steamuser"))

    def test_uses_real_username_for_wine_prefix(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            prefix = _make_prefix(root, user="cmdr")
            self.assertTrue(ps.prefix_user_dir(prefix).endswith("cmdr"))


class EliteDirTests(unittest.TestCase):
    def test_linux_bindings_and_pictures_dirs_are_inside_prefix(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            prefix = _make_prefix(root)
            with mock.patch.object(ps, "IS_WINDOWS", False):
                bindings = ps.elite_bindings_dir(prefix)
                pictures = ps.elite_pictures_dir(prefix)
        self.assertIn(os.path.join("AppData", "Local", "Frontier Developments", "Elite Dangerous", "Options", "Bindings"),
                      bindings)
        self.assertTrue(pictures.endswith(os.path.join("Pictures", "Frontier Developments", "Elite Dangerous")))

    def test_linux_dirs_are_none_without_a_prefix(self) -> None:
        with tempfile.TemporaryDirectory() as root, mock.patch.object(ps, "IS_WINDOWS", False):
            self.assertIsNone(ps.elite_bindings_dir(os.path.join(root, "nope")))

    def test_windows_bindings_dir_uses_localappdata(self) -> None:
        with mock.patch.object(ps, "IS_WINDOWS", True), mock.patch.dict(os.environ, {"LOCALAPPDATA": "C:\L"}):
            self.assertEqual(
                ps.elite_bindings_dir(),
                os.path.join("C:\L", "Frontier Developments", "Elite Dangerous", "Options", "Bindings"),
            )


class JournalDirTests(unittest.TestCase):
    def _linux(self):
        return mock.patch.multiple(ps, IS_WINDOWS=False, IS_LINUX=True)

    def test_journal_dir_is_prefix_saved_games(self) -> None:
        with tempfile.TemporaryDirectory() as root, self._linux():
            prefix = _make_prefix(root)
            expected = os.path.join(ps.prefix_user_dir(prefix), "Saved Games", "Frontier Developments", "Elite Dangerous")
            self.assertEqual(ps.elite_journal_dir(prefix), expected)

    def test_advice_none_when_correct_including_via_symlink_or_tilde(self) -> None:
        with tempfile.TemporaryDirectory() as root, self._linux():
            prefix = _make_prefix(root)
            expected = ps.elite_journal_dir(prefix)
            os.makedirs(expected)
            self.assertIsNone(ps.journal_dir_advice(expected, prefix))

    def test_advice_when_empty_or_different(self) -> None:
        with tempfile.TemporaryDirectory() as root, self._linux():
            prefix = _make_prefix(root)
            expected = ps.elite_journal_dir(prefix)
            self.assertIn(expected, ps.journal_dir_advice("", prefix))
            self.assertIn("Journal directory is /elsewhere", ps.journal_dir_advice("/elsewhere", prefix))

    def test_advice_when_no_prefix_and_none_off_linux(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            with self._linux():
                self.assertIn("Couldn't find", ps.journal_dir_advice("", os.path.join(root, "nope")))
            with mock.patch.object(ps, "IS_LINUX", False):
                self.assertIsNone(ps.journal_dir_advice("", os.path.join(root, "nope")))


class XdotoolWrapperTests(unittest.TestCase):
    def _run(self, returncode: int = 0, stdout: str = ""):
        return mock.Mock(returncode=returncode, stdout=stdout, stderr="")

    def test_find_elite_windows_parses_ids(self) -> None:
        with mock.patch.object(ps.subprocess, "run", return_value=self._run(stdout="123\n456\n")) as run:
            self.assertEqual(ps.find_elite_windows(), ["123", "456"])
        self.assertEqual(run.call_args.args[0][:2], ["xdotool", "search"])

    def test_failure_returns_empty_or_false_never_raises(self) -> None:
        with mock.patch.object(ps.subprocess, "run", return_value=self._run(returncode=1)):
            self.assertEqual(ps.find_elite_windows(), [])
            self.assertFalse(ps.key_down("g"))
        with mock.patch.object(ps.subprocess, "run", side_effect=FileNotFoundError):
            self.assertFalse(ps.key_up("g"))
            self.assertEqual(ps.active_window_title(), "")

    def test_key_down_up_call_xdotool(self) -> None:
        with mock.patch.object(ps.subprocess, "run", return_value=self._run()) as run:
            self.assertTrue(ps.key_down("F10"))
            self.assertTrue(ps.key_up("F10"))
        self.assertEqual([c.args[0] for c in run.call_args_list],
                         [["xdotool", "keydown", "F10"], ["xdotool", "keyup", "F10"]])


if __name__ == "__main__":
    unittest.main()
