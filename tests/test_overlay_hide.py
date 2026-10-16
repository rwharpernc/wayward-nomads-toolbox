"""Hiding every overlay for a while (overlay.py's switch and overlay_visibility.py's shortcut parsing)."""
from __future__ import annotations

import os
import sys
import types
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

_config = types.ModuleType("config")
_config.appname = "EDMarketConnector"
_config.config = types.SimpleNamespace(get_str=lambda key: "", set=lambda *a, **k: None)
sys.modules.setdefault("config", _config)
sys.modules.setdefault("myNotebook", types.ModuleType("myNotebook"))

from plugin import overlay  # noqa: E402
from plugin import overlay_visibility as V  # noqa: E402


class HideTests(unittest.TestCase):
    def setUp(self):
        overlay._hidden = False
        overlay._last.clear()
        self.sent = []
        patcher = mock.patch.object(overlay.OverlayClient, "_send_raw", lambda _self, payload: self.sent.append(payload))
        patcher.start()
        self.addCleanup(patcher.stop)
        self.addCleanup(lambda: (setattr(overlay, "_hidden", False), overlay._last.clear()))
        self.client = overlay.OverlayClient()

    def draw(self):
        self.client.send_message("t1", "hello", "#fff", 10, 20, ttl=4)
        self.client.send_shape("r1", "rect", "#000", "#111", 1, 2, 30, 40, ttl=4)
        self.client.send_circle("c1", "#fff", "#000", 5, 6, 7, ttl=4)
        self.client.send_vector("v1", [{"x": 1, "y": 2}, {"x": 3, "y": 4}], "#fff", ttl=4)

    def test_hiding_clears_everything_drawn_and_stops_new_drawing(self):
        self.draw()
        self.sent.clear()
        overlay.set_all_hidden(True)
        by_id = {p["id"]: p for p in self.sent}
        self.assertEqual(set(by_id), {"t1", "r1", "c1", "v1"})
        self.assertEqual((by_id["t1"]["text"], by_id["t1"]["ttl"]), ("", 1))
        self.assertEqual((by_id["r1"]["w"], by_id["r1"]["h"], by_id["r1"]["fill"]), (0, 0, ""))
        self.assertEqual((by_id["c1"]["color"], by_id["c1"]["ttl"]), ("", 1))
        self.assertEqual(by_id["v1"]["vector"], [])
        self.sent.clear()
        self.client.send_message("t2", "later", "#fff", 0, 0, ttl=4)
        self.assertEqual(self.sent, [])                      # not drawn while hidden
        self.assertTrue(overlay.all_hidden())

    def test_showing_puts_back_what_was_up_including_what_was_drawn_while_hidden(self):
        self.draw()
        overlay.set_all_hidden(True)
        self.client.send_message("t2", "later", "#fff", 0, 0, ttl=4)
        self.sent.clear()
        overlay.set_all_hidden(False)
        self.assertEqual({p["id"] for p in self.sent}, {"t1", "r1", "c1", "v1", "t2"})
        self.assertTrue(all(p["ttl"] >= 1 for p in self.sent))
        self.assertEqual({p["id"]: p["text"] for p in self.sent if "text" in p}["t1"], "hello")

    def test_something_that_ran_out_is_not_put_back_and_a_clear_forgets_the_id(self):
        self.client.send_message("old", "gone", "#fff", 0, 0, ttl=4)
        self.client.send_message("cleared", "x", "#fff", 0, 0, ttl=4)
        self.client.send_message("cleared", "", "white", 0, 0, ttl=1)
        overlay._last["old"] = (overlay._last["old"][0], overlay._last["old"][1] - 100)         # drawn long ago
        overlay.set_all_hidden(True)
        self.sent.clear()
        overlay.set_all_hidden(False)
        self.assertEqual(self.sent, [])

    def test_a_long_lasting_display_comes_back_with_the_time_it_had_left(self):
        self.client.send_shape("card", "rect", "#000", "#111", 0, 0, 10, 10, ttl=3600)
        overlay.set_all_hidden(True)
        self.sent.clear()
        overlay.set_all_hidden(False)
        self.assertEqual(len(self.sent), 1)
        self.assertGreater(self.sent[0]["ttl"], 3000)

    def test_listeners_hear_each_change_and_a_repeat_changes_nothing(self):
        heard = []
        overlay.on_visibility_change(heard.append)
        self.addCleanup(lambda: overlay._listeners.remove(heard.append))
        overlay.set_all_hidden(True)
        overlay.set_all_hidden(True)
        self.assertTrue(overlay.toggle_all_hidden() is False)
        self.assertEqual(heard, [True, False])


class ShortcutTests(unittest.TestCase):
    def test_a_combination_is_modifiers_and_a_key(self):
        self.assertEqual(V.parse_combo("Ctrl+Alt+H"), (V.MOD_CONTROL | V.MOD_ALT, ord("H")))
        self.assertEqual(V.parse_combo("Ctrl+Shift+O"), (V.MOD_CONTROL | V.MOD_SHIFT, ord("O")))
        self.assertEqual(V.parse_combo("Ctrl+Alt+F10"), (V.MOD_CONTROL | V.MOD_ALT, 0x79))

    def test_off_and_anything_else_is_none(self):
        for text in ("Off", "", "H", "Ctrl", "Win+H", "Ctrl+Alt+Home", "Ctrl+Alt+F99"):
            self.assertIsNone(V.parse_combo(text), text)

    def test_every_choice_but_off_is_a_valid_combination(self):
        for choice in V.CHOICES:
            self.assertEqual(V.parse_combo(choice) is None, choice == V.OFF, choice)

    def test_the_panel_line_says_which_state_it_is_in(self):
        self.assertIn("hidden", V.panel_text(True))
        self.assertIn("shown", V.panel_text(False))


if __name__ == "__main__":
    unittest.main()
