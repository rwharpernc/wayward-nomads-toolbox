"""Global overlay placement glue (overlay_placement.py): reading the screen from the game's files, saved and migrated
placements, and the preview. EDMC's config is replaced by a dictionary."""
from __future__ import annotations

import os
import sys
import tempfile
import types
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

STORE = {}


class FakeConfig:
    default_journal_dir = ""

    def get_str(self, key, default=""):
        return STORE.get(key, default) or ""

    def get_bool(self, key, default=False):
        return bool(STORE.get(key, default))

    def set(self, key, value):
        STORE[key] = value


_stub = types.ModuleType("config")
_stub.appname = "EDMarketConnector"
_stub.config = FakeConfig()
sys.modules["config"] = _stub
sys.modules.setdefault("myNotebook", mock.MagicMock())

from plugin import overlay_layout as L  # noqa: E402
from plugin import overlay_placement as P  # noqa: E402

DISPLAY_XML = ("<DisplayConfig><ScreenWidth>3840</ScreenWidth><ScreenHeight>2160</ScreenHeight>"
               "<FullScreen>2</FullScreen></DisplayConfig>")


def with_display_file(xml):
    folder = tempfile.mkdtemp()
    if xml is not None:
        with open(os.path.join(folder, P.DISPLAY_SETTINGS_FILE), "w", encoding="utf-8") as handle:
            handle.write(xml)
    return folder


class ScreenTests(unittest.TestCase):
    def setUp(self):
        STORE.clear()
        P.refresh()

    def test_the_screen_comes_from_the_games_display_file(self):
        folder = with_display_file(DISPLAY_XML)
        with mock.patch.object(P.platform_support, "elite_graphics_dir", return_value=folder), \
                mock.patch.object(P, "detect_scale_mode", return_value=(L.MODE_FILL, "assumed")):
            screen = P.screen_for(P.AUTO, P.AUTO)
        self.assertEqual((screen.width, screen.height, screen.full_screen, screen.mode), (3840, 2160, 2, L.MODE_FILL))
        self.assertEqual(screen.visible, (1280, 720))

    def test_no_file_assumes_the_smallest_common_area_so_nothing_is_out_of_sight(self):
        folder = with_display_file(None)
        with mock.patch.object(P.platform_support, "elite_graphics_dir", return_value=folder), \
                mock.patch.object(P, "detect_scale_mode", return_value=(L.MODE_FILL, "assumed")):
            screen = P.screen_for(P.AUTO, P.AUTO)
        self.assertEqual(screen.visible, (1280, 720))
        self.assertIn("assuming", screen.source)

    def test_an_unreadable_folder_is_not_a_crash(self):
        with mock.patch.object(P.platform_support, "elite_graphics_dir", return_value=None), \
                mock.patch.object(P, "detect_scale_mode", return_value=(L.MODE_FILL, "assumed")):
            self.assertEqual(P.screen_for(P.AUTO, P.AUTO).visible, (1280, 720))

    def test_a_chosen_shape_and_mode_win_over_the_files(self):
        folder = with_display_file(DISPLAY_XML)
        with mock.patch.object(P.platform_support, "elite_graphics_dir", return_value=folder):
            ultrawide = P.screen_for("32:9", L.MODE_FILL)
            fit = P.screen_for("32:9", L.MODE_FIT)
        self.assertEqual(ultrawide.visible, (1280, 360))
        self.assertEqual(fit.visible, (1280, 960))

    def test_the_overlays_scale_mode_is_read_from_its_settings_file(self):
        plugins = tempfile.mkdtemp()
        os.makedirs(os.path.join(plugins, P.MODERN_OVERLAY_FOLDER))
        path = os.path.join(plugins, P.MODERN_OVERLAY_FOLDER, P.MODERN_OVERLAY_SETTINGS)
        with mock.patch.object(P, "_plugins_dir", return_value=plugins):
            self.assertEqual(P.detect_scale_mode()[0], L.MODE_FILL)           # no file: assume fill
            with open(path, "w", encoding="utf-8") as handle:
                handle.write('{"scale_mode": "fit"}')
            self.assertEqual(P.detect_scale_mode(), (L.MODE_FIT, "EDMCModernOverlay settings"))
            with open(path, "w", encoding="utf-8") as handle:
                handle.write("{not json")
            self.assertEqual(P.detect_scale_mode()[0], L.MODE_FILL)           # damaged: assume fill

    def test_the_screen_is_cached_until_refreshed(self):
        folder = with_display_file(DISPLAY_XML)
        with mock.patch.object(P.platform_support, "elite_graphics_dir", return_value=folder), \
                mock.patch.object(P, "detect_scale_mode", return_value=(L.MODE_FILL, "assumed")):
            first = P.current_screen()
            os.remove(os.path.join(folder, P.DISPLAY_SETTINGS_FILE))
            self.assertIs(P.current_screen(), first)
            P.refresh()
            self.assertIn("assuming", P.current_screen().source)


class SavedPlacementTests(unittest.TestCase):
    def setUp(self):
        STORE.clear()
        P.refresh()

    def test_the_default_when_nothing_is_saved(self):
        self.assertEqual(P.placement_for("colonisation"), P.SLOTS["colonisation"].default)

    def test_a_saved_placement_is_read_back(self):
        P.save_placement("landing", L.Placement("right", "bottom", 30, 15))
        self.assertEqual(P.placement_for("landing"), L.Placement("right", "bottom", 30, 15))

    def test_damaged_saved_text_falls_back_to_the_default(self):
        STORE[L.setting_key("landing")] = "garbage"
        self.assertEqual(P.placement_for("landing"), P.SLOTS["landing"].default)

    def test_an_old_hand_set_position_is_kept_as_an_exact_position(self):
        STORE["wntb_discovery_x"], STORE["wntb_discovery_y"] = "900", "40"
        self.assertEqual(P.placement_for("discovery"), L.custom_placement(900, 40))

    def test_an_old_untouched_default_gives_the_new_default(self):
        STORE["wntb_discovery_x"], STORE["wntb_discovery_y"] = "700", "60"
        self.assertEqual(P.placement_for("discovery"), P.SLOTS["discovery"].default)

    def test_a_new_saved_placement_beats_the_old_position(self):
        STORE["wntb_discovery_x"], STORE["wntb_discovery_y"] = "900", "40"
        P.save_placement("discovery", L.Placement("left", "top", 5, 5))
        self.assertEqual(P.placement_for("discovery"), L.Placement("left", "top", 5, 5))

    def test_every_slot_has_a_valid_default_and_a_unique_key(self):
        self.assertEqual(len(P.SLOTS), len(set(P.SLOTS)))
        for key, slot in P.SLOTS.items():
            self.assertEqual(key, slot.key)
            self.assertIn(slot.default.h, L.H_ANCHORS)
            self.assertIn(slot.default.v, L.V_ANCHORS)
            self.assertGreater(slot.size[0], 0)
            self.assertGreater(slot.size[1], 0)
            L.setting_key(key)          # a safe settings key


class ClientTests(unittest.TestCase):
    def setUp(self):
        STORE.clear()
        P.refresh()
        self.screen = L.Screen(3840, 2160, L.MODE_FILL, "test")

    def recorder(self):
        calls = []

        class Rec:
            def send_message(self, *a, **k):
                calls.append((a, k))
        return Rec(), calls

    def test_a_display_is_moved_to_its_place(self):
        P.save_placement("landing", L.Placement("left", "top", 0, 0))      # block drawn at (20, 636)
        rec, calls = self.recorder()
        with mock.patch.object(P, "current_screen", return_value=self.screen):
            client = P.client_for("landing", rec, (20, 636, 320, 324))
            client.send_message("id", "hi", "red", 40, 650)
        self.assertEqual(calls[0][0][3:5], (20, 14))     # moved by (-20, -636)

    def test_a_display_already_in_place_is_not_wrapped(self):
        P.save_placement("landing", L.custom_placement(20, 636))
        rec, _calls = self.recorder()
        with mock.patch.object(P, "current_screen", return_value=self.screen):
            self.assertIs(P.client_for("landing", rec, (20, 636, 320, 324)), rec)

    def test_a_placement_failure_leaves_the_display_where_it_was_drawn(self):
        rec, _calls = self.recorder()
        with mock.patch.object(P, "current_screen", side_effect=RuntimeError("boom")):
            self.assertIs(P.client_for("landing", rec, (20, 636, 320, 324)), rec)

    def test_origin_for_keeps_a_right_edge_display_inside_the_screen(self):
        P.save_placement("inventory", L.Placement("right", "top", 20, 120))
        with mock.patch.object(P, "current_screen", return_value=self.screen):
            x, y = P.origin_for("inventory", (420, 226))
        self.assertEqual((x, y), (1280 - 420 - 20, 120))


class PreviewTests(unittest.TestCase):
    def test_the_preview_has_the_edge_and_one_box_per_display_inside_the_visible_area(self):
        screen = L.Screen(3840, 2160, L.MODE_FILL, "test")
        placements = {key: slot.default for key, slot in P.SLOTS.items()}
        items = P.preview_shapes(placements, screen)
        self.assertEqual(len(items), len(P.SLOTS) + 1)
        edge = items[0]
        self.assertEqual((edge["w"], edge["h"]), (1280, 720))
        for item in items[1:]:
            self.assertGreaterEqual(item["x"], 0)
            self.assertGreaterEqual(item["y"], 0)
            self.assertLessEqual(item["x"] + item["w"], 1280, item["label"])
            self.assertLessEqual(item["y"] + item["h"], 720, item["label"])

    def test_every_default_stays_inside_the_smallest_common_area_too(self):
        screen = L.Screen(5120, 1440, L.MODE_FILL, "test")        # 32:9: 1280 x 360 visible
        for item in P.preview_shapes({k: s.default for k, s in P.SLOTS.items()}, screen)[1:]:
            self.assertLessEqual(item["x"] + item["w"], 1280, item["label"])
            # Bigger than the area: pinned to the top so the start of it shows.
            self.assertTrue(item["y"] + item["h"] <= 360 or item["y"] == 0, item["label"])


if __name__ == "__main__":
    unittest.main()
