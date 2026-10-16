"""The built-in overlay's switch (overlay_native.py): payloads go to the scene when it is chosen, and placement reads its screen."""
import os
import sys
import types
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

_store = {}
_config = types.ModuleType("config")
_config.appname = "EDMarketConnector"
_config.config = types.SimpleNamespace(get_str=lambda key: _store.get(key, ""), set=lambda key, value: _store.__setitem__(key, value),
                                       get_bool=lambda key, default=False: default)
sys.modules.setdefault("config", _config)
sys.modules.setdefault("myNotebook", types.ModuleType("myNotebook"))
for _name in ("ttkHyperlinkLabel", "theme", "monitor", "plug", "l10n", "requests"):
    sys.modules.setdefault(_name, mock.MagicMock())

from plugin import overlay, overlay_layout as L, overlay_native as N  # noqa: E402


@unittest.skipUnless(N.supported(), "the built-in overlay is for Windows")
class NativeSwitchTests(unittest.TestCase):
    def setUp(self):
        patcher = mock.patch.object(N, "config", _config.config)       # whichever stub config another test file loaded first, this file's own is used here
        patcher.start()
        self.addCleanup(patcher.stop)
        _store.clear()
        N.window.geometry = None
        N.scene.clear()
        overlay._hidden = False
        overlay._last.clear()
        self.addCleanup(lambda: (N.save_choice(N.MODERN), N.scene.clear(), setattr(N.window, "geometry", None), overlay._last.clear()))

    def test_it_is_off_until_chosen(self):
        N.save_choice(N.MODERN)
        self.assertEqual(N.selected(), N.MODERN)
        self.assertFalse(N.accepting())
        self.assertIsNone(N.screen())
        self.assertEqual(N.status_text(), "")

    def test_a_payload_goes_to_the_scene_when_it_is_chosen_and_never_to_the_socket(self):
        N.save_choice(N.BUILTIN)
        with mock.patch.object(overlay.OverlayClient, "_connect_locked", side_effect=AssertionError("the socket must not be used")):
            overlay.OverlayClient().send_message("t", "hello", "#fff", 10, 20, ttl=4)
        self.assertEqual([item.text for item in N.scene.items()], ["hello"])

    def test_hiding_and_showing_work_with_it(self):
        N.save_choice(N.BUILTIN)
        client = overlay.OverlayClient()
        client.send_message("t", "hello", "#fff", 10, 20, ttl=30)
        overlay.set_all_hidden(True)
        self.assertEqual(N.scene.items(), [])
        overlay.set_all_hidden(False)
        self.assertEqual([item.text for item in N.scene.items()], ["hello"])

    def test_the_screen_is_the_game_window_with_no_right_hand_clamp(self):
        N.save_choice(N.BUILTIN)
        waiting = N.screen()
        self.assertTrue(waiting.native)
        self.assertEqual((waiting.width, waiting.height), N.FALLBACK_SCREEN)
        N.window.geometry = (0, 0, 2560, 1080, 1.25)
        screen = N.screen()
        self.assertEqual((screen.width, screen.height, screen.ratio, screen.mode), (2560, 1080, 1.25, L.MODE_FILL))
        self.assertEqual(screen.clamped, (False, False))

    def test_placement_does_not_use_group_offsets_with_it(self):
        from plugin import overlay_placement
        N.save_choice(N.BUILTIN)
        for key, slot in overlay_placement.SLOTS.items():
            self.assertFalse(overlay_placement.can_offset(key), key)

    def test_a_snapshot_draws_the_scene_at_the_size_asked_for(self):
        N.save_corners("square")
        self.assertIsNone(N.snapshot(1920, 1080))                        # not chosen
        N.save_choice(N.BUILTIN)
        self.assertIsNone(N.snapshot(1920, 1080))                        # Elite's window not known yet
        N.window.geometry = (0, 0, 1920, 1080, 1.0)
        self.assertIsNone(N.snapshot(1920, 1080))                        # nothing showing
        overlay.OverlayClient().send_shape("r", "rect", "", "#ffff0000", 640, 480, 100, 50, ttl=30)
        image = N.snapshot(3840, 2160)                                   # a screenshot twice the window's size
        self.assertEqual(image.size, (3840, 2160))
        self.assertEqual(image.getpixel((1925, 1085))[:3], (255, 0, 0))  # 640 of 1280 across is 1920 of 3840, 480 of 960 down is 1080 of 2160; the rectangle is twice as many pixels
        self.assertEqual(image.getpixel((1920 + 199, 1080 + 99))[:3], (255, 0, 0))
        self.assertEqual(image.getpixel((1920 + 210, 1080 + 50))[3], 0)

    def test_windows_capture_tools_are_recognized_by_program_name(self):
        from plugin import overlay_window as W
        for name in ("ScreenClippingHost.exe", r"C:\Windows\SystemApps\SnippingTool.exe", "screensketch.EXE"):
            self.assertTrue(W.is_capture_tool(name), name)
        for name in ("", "notepad.exe", "EliteDangerous64.exe"):
            self.assertFalse(W.is_capture_tool(name), name)

    def test_cards_are_measured_with_the_font_only_while_the_built_in_overlay_is_chosen(self):
        from plugin import overlay_style
        self.addCleanup(lambda: overlay_style.set_text_measurer(None))
        N.save_choice(N.MODERN)
        N.install_measurer()
        estimate = overlay_style.DEFAULT.text_width("Systems · jumps", "normal")
        N.save_choice(N.BUILTIN)
        N.install_measurer()
        measured = overlay_style.DEFAULT.text_width("Systems · jumps", "normal")
        self.assertNotEqual(measured, estimate)
        self.assertGreater(measured, 0)
        self.assertGreater(N.measure("Systems · jumps and more", "normal"), N.measure("Systems", "normal"))      # a longer text is wider
        self.assertGreater(N.measure("Systems", "large"), N.measure("Systems", "normal"))                         # and a larger size
        N.save_choice(N.MODERN)
        N.install_measurer()
        self.assertEqual(overlay_style.DEFAULT.text_width("Systems · jumps", "normal"), estimate)

    def test_the_built_in_overlay_draws_in_the_bundled_font_until_another_is_added_and_chosen(self):
        import tempfile
        from plugin import overlay_fonts
        bundled = os.path.join(N.fonts_folder(), overlay_fonts.BUNDLED)
        self.assertTrue(os.path.isfile(bundled))
        self.assertEqual(N._font_path(), bundled)                                   # nothing chosen: the font WNTB ships
        with tempfile.TemporaryDirectory() as folder:
            with mock.patch.object(N, "fonts_folder", lambda: folder):
                with open(os.path.join(folder, "Mine.ttf"), "wb") as handle:
                    handle.write(b"font")
                N.save_font("Mine.ttf")
                self.assertEqual(N._font_path(), os.path.join(folder, "Mine.ttf"))     # a chosen font in WNTB's folder is used
                N.save_font("Gone.ttf")
                self.assertTrue(N._font_path().endswith("Gone.ttf") is False)         # one that is not there falls back (to the bundled one, here a stand-in folder has none)
        N.save_font(overlay_fonts.BUNDLED)
        self.assertEqual(N._font_path(), bundled)

    def test_panels_get_rounded_corners_in_the_built_in_overlay_only(self):
        client = overlay.OverlayClient()
        sent = []
        with mock.patch.object(overlay.OverlayClient, "_send", lambda _self, payload: sent.append(payload)):
            N.save_choice(N.MODERN)
            client.send_shape("panel", "rect", "#fff", "#000", 0, 0, 300, 200)
            self.assertNotIn("radius", sent[-1])                           # EDMCModernOverlay is sent nothing extra
            N.save_choice(N.BUILTIN)
            N.save_corners("rounded")
            client.send_shape("panel", "rect", "#fff", "#000", 0, 0, 300, 200)
            self.assertEqual(sent[-1]["radius"], 10.0)
            client.send_shape("divider", "rect", "#fff", "#fff", 0, 0, 300, 1)
            client.send_shape("bar", "rect", "#fff", "#fff", 0, 0, 300, 4)
            self.assertNotIn("radius", sent[-1])                           # dividers and bars stay square
            self.assertNotIn("radius", sent[-2])
            N.save_corners("square")
            client.send_shape("panel", "rect", "#fff", "#000", 0, 0, 300, 200)
            self.assertNotIn("radius", sent[-1])
            N.save_corners("very")
            client.send_shape("panel", "rect", "#fff", "#000", 0, 0, 300, 200)
            self.assertEqual(sent[-1]["radius"], 16.0)
        self.assertEqual(N.corner_key(), "very")
        N.save_corners("bogus")
        self.assertEqual(N.corner_key(), N.DEFAULT_CORNERS)                  # an unknown value falls back

    def test_the_overlay_clamp_still_applies_to_the_other_overlay(self):
        self.assertEqual(L.Screen(3840, 2160, ratio=1.25).clamped, (True, False))
        self.assertEqual(L.Screen(3840, 2160, ratio=1.25, native=True).clamped, (False, False))


if __name__ == "__main__":
    unittest.main()
