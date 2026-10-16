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

    def test_the_overlay_clamp_still_applies_to_the_other_overlay(self):
        self.assertEqual(L.Screen(3840, 2160, ratio=1.25).clamped, (True, False))
        self.assertEqual(L.Screen(3840, 2160, ratio=1.25, native=True).clamped, (False, False))


if __name__ == "__main__":
    unittest.main()
