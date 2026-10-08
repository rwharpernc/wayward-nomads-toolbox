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


class ListboxColorsTests(unittest.TestCase):
    def test_dark_theme_is_platform_independent(self):
        for win in (True, False):
            with mock.patch.object(ps, "IS_WINDOWS", win):
                self.assertEqual(ps.listbox_colors(True), ("#1e1e1e", "#e0e0e0"))

    def test_light_theme_uses_system_colors_only_on_windows(self):
        with mock.patch.object(ps, "IS_WINDOWS", True):
            self.assertEqual(ps.listbox_colors(False), ("SystemWindow", "SystemWindowText"))
        with mock.patch.object(ps, "IS_WINDOWS", False):
            self.assertEqual(ps.listbox_colors(False), ("white", "black"))


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


class SettingsNoteTests(unittest.TestCase):
    """The Works on / This system notes shown in Settings."""

    def test_windows_is_supported_for_input_and_sound(self) -> None:
        with mock.patch.object(ps, "IS_WINDOWS", True), mock.patch.object(ps, "IS_LINUX", False):
            for note in (ps.input_support_note(), ps.sound_support_note()):
                self.assertTrue(note[1])
                self.assertIn("Windows - supported", note[0])

    def test_linux_reports_whether_the_helper_tool_is_present(self) -> None:
        with mock.patch.object(ps, "IS_WINDOWS", False), mock.patch.object(ps, "IS_LINUX", True):
            with mock.patch.object(ps, "xdotool_available", return_value=True):
                self.assertEqual(ps.input_support_note()[1], True)
            with mock.patch.object(ps, "xdotool_available", return_value=False):
                text, ok = ps.input_support_note()
                self.assertFalse(ok)
                self.assertIn("xdotool NOT found", text)
            with mock.patch.object(ps, "sound_available", return_value=False):
                text, ok = ps.sound_support_note()
                self.assertFalse(ok)
                self.assertIn("no sound player", text)

    def test_other_systems_are_unsupported_and_say_so(self) -> None:
        with mock.patch.object(ps, "IS_WINDOWS", False), mock.patch.object(ps, "IS_LINUX", False):
            self.assertFalse(ps.input_support_note()[1])
            self.assertFalse(ps.sound_support_note()[1])
            self.assertIn("Not on macOS", ps.input_support_note()[0])


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

    def test_hold_key_is_a_single_xdotool_process(self) -> None:
        with mock.patch.object(ps.subprocess, "run", return_value=self._run()) as run:
            self.assertTrue(ps.hold_key("slash", 2500))
        run.assert_called_once()
        self.assertEqual(run.call_args.args[0][-6:], ["keydown", "slash", "sleep", "2.5", "keyup", "slash"])
        self.assertGreater(run.call_args.kwargs["timeout"], 2.5)

    def test_hold_key_failure_returns_false(self) -> None:
        with mock.patch.object(ps.subprocess, "run", return_value=self._run(returncode=1)):
            self.assertFalse(ps.hold_key("slash", 1000))

    def test_key_down_up_call_xdotool(self) -> None:
        with mock.patch.object(ps.subprocess, "run", return_value=self._run()) as run:
            self.assertTrue(ps.key_down("F10"))
            self.assertTrue(ps.key_up("F10"))
        self.assertEqual([c.args[0] for c in run.call_args_list],
                         [["xdotool", "keydown", "F10"], ["xdotool", "keyup", "F10"]])


class FlatpakToolTests(unittest.TestCase):
    """Inside a Flatpak, host tools are reached through flatpak-spawn --host."""

    def setUp(self) -> None:
        ps._host_tool_cache.clear()
        self.addCleanup(ps._host_tool_cache.clear)

    def _which(self, present):
        return lambda name: f"/usr/bin/{name}" if name in present else None

    def test_local_tool_is_used_directly(self) -> None:
        with mock.patch.object(ps.shutil, "which", self._which({"xdotool"})):
            self.assertEqual(ps._tool_command("xdotool"), ["xdotool"])

    def test_flatpak_falls_back_to_the_host_tool(self) -> None:
        probe = mock.Mock(returncode=0)
        with mock.patch.object(ps, "IN_FLATPAK", True), \
                mock.patch.object(ps.shutil, "which", self._which({"flatpak-spawn"})), \
                mock.patch.object(ps.subprocess, "run", return_value=probe) as run:
            self.assertEqual(ps._tool_command("xdotool"), ["flatpak-spawn", "--host", "--directory=/", "xdotool"])
            self.assertEqual(ps._tool_command("xdotool"), ["flatpak-spawn", "--host", "--directory=/", "xdotool"])
        self.assertEqual(run.call_count, 1)  # the probe is cached
        self.assertEqual(run.call_args.args[0], ["flatpak-spawn", "--host", "--directory=/", "which", "xdotool"])

    def test_flatpak_without_the_host_tool_is_unavailable(self) -> None:
        with mock.patch.object(ps, "IN_FLATPAK", True), \
                mock.patch.object(ps.shutil, "which", self._which({"flatpak-spawn"})), \
                mock.patch.object(ps.subprocess, "run", return_value=mock.Mock(returncode=1)):
            self.assertIsNone(ps._tool_command("xdotool"))

    def test_prefer_host_uses_the_host_even_when_a_sandbox_copy_exists(self) -> None:
        with mock.patch.object(ps, "IN_FLATPAK", True), \
                mock.patch.object(ps.shutil, "which", self._which({"flatpak-spawn", "pgrep"})), \
                mock.patch.object(ps.subprocess, "run", return_value=mock.Mock(returncode=0)):
            self.assertEqual(ps._tool_command("pgrep", prefer_host=True), ["flatpak-spawn", "--host", "--directory=/", "pgrep"])
            self.assertEqual(ps._tool_command("pgrep"), ["pgrep"])

    def test_prefer_host_falls_back_to_the_sandbox_copy(self) -> None:
        with mock.patch.object(ps, "IN_FLATPAK", True), \
                mock.patch.object(ps.shutil, "which", self._which({"flatpak-spawn", "pgrep"})), \
                mock.patch.object(ps.subprocess, "run", return_value=mock.Mock(returncode=1)):
            self.assertEqual(ps._tool_command("pgrep", prefer_host=True), ["pgrep"])

    def test_not_in_flatpak_never_calls_flatpak_spawn(self) -> None:
        with mock.patch.object(ps, "IN_FLATPAK", False), \
                mock.patch.object(ps.shutil, "which", self._which({"flatpak-spawn"})), \
                mock.patch.object(ps.subprocess, "run") as run:
            self.assertIsNone(ps._tool_command("xdotool"))
        run.assert_not_called()

    def test_wrappers_run_through_the_host_prefix(self) -> None:
        host = ["flatpak-spawn", "--host", "--directory=/", "xdotool"]
        with mock.patch.object(ps, "_tool_command", return_value=host), \
                mock.patch.object(ps.subprocess, "run", return_value=mock.Mock(returncode=0, stdout="", stderr="")) as run:
            self.assertTrue(ps.key_down("F10"))
        self.assertEqual(run.call_args.args[0], host + ["keydown", "F10"])


if __name__ == "__main__":
    unittest.main()
