"""Global overlay placement glue (overlay_placement.py): reading the screen from the overlay's log and the game's files,
saved and migrated placements, and the preview. EDMC's config is replaced by a dictionary."""
from __future__ import annotations

import os
import sys
import tempfile
import time
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
SCALING_LINE = ("2026-10-11 09:48:11 UTC - DEBUG - Overlay scaling updated: window=3840x2160 px mode=fill base_scale=2.4000 "
                "scale_x=3.000 scale_y=3.000 diag=3.00 scaled=3072.0x2304.0 offset=(0.0,0.0) overflow_x=0 overflow_y=1")
MEASURED = L.Screen(3840, 2160, L.MODE_FILL, "test", 2, 1.25, True)


class Install:
    """A throwaway EDMC data folder: plugins/ (with or without EDMCModernOverlay), logs/ and the game's graphics folder."""

    def __init__(self, modern=True, log_line=None, display_xml=None, settings_json=None):
        self.root = tempfile.mkdtemp()
        self.plugins = os.path.join(self.root, "plugins")
        self.graphics = os.path.join(self.root, "graphics")
        os.makedirs(self.plugins)
        os.makedirs(self.graphics)
        if modern:
            os.makedirs(os.path.join(self.plugins, P.MODERN_OVERLAY_FOLDER))
        if settings_json is not None:
            with open(os.path.join(self.plugins, P.MODERN_OVERLAY_FOLDER, P.MODERN_OVERLAY_SETTINGS), "w") as handle:
                handle.write(settings_json)
        self.log = os.path.join(self.root, P.MODERN_OVERLAY_LOG)
        if log_line is not None:
            os.makedirs(os.path.dirname(self.log))
            with open(self.log, "w", encoding="utf-8") as handle:
                handle.write("some other line\n" + log_line + "\nand another\n")
        self.display = os.path.join(self.graphics, P.DISPLAY_SETTINGS_FILE)
        if display_xml is not None:
            with open(self.display, "w", encoding="utf-8") as handle:
                handle.write(display_xml)
            two_hours_ago = time.time() - 7200      # explicit times, so the order the files were written in never matters
            os.utime(self.display, (two_hours_ago, two_hours_ago))

    def patches(self, windows_scaling=None):
        return (mock.patch.object(P, "_plugins_dir", return_value=self.plugins),
                mock.patch.object(P.platform_support, "elite_graphics_dir", return_value=self.graphics),
                mock.patch.object(P, "windows_display_scaling", return_value=windows_scaling))

    def screen(self, scaling="auto", mode="auto", windows_scaling=None):
        a, b, c = self.patches(windows_scaling)
        with a, b, c:
            return P.screen_for(scaling, mode)


class ScreenTests(unittest.TestCase):
    def setUp(self):
        STORE.clear()
        P.refresh()

    def test_the_overlays_own_log_is_the_best_source(self):
        screen = Install(log_line=SCALING_LINE, display_xml=DISPLAY_XML).screen()
        self.assertEqual((screen.width, screen.height, screen.mode, screen.pixel_sizes), (3840, 2160, "fill", True))
        self.assertAlmostEqual(screen.ratio, 1.25)
        self.assertEqual(screen.logical, (3072.0, 1728.0))
        self.assertIn("log", screen.source)
        self.assertEqual(screen.full_screen, 2)          # the game's own FullScreen value is still reported

    def test_a_log_older_than_the_games_screen_settings_is_not_trusted(self):
        install = Install(log_line=SCALING_LINE, display_xml=DISPLAY_XML.replace("3840", "2560").replace("2160", "1440"))
        old = time.time() - 10_000                  # older than the settings file, which is two hours old
        os.utime(install.log, (old, old))
        screen = install.screen(windows_scaling=1.0)
        self.assertEqual((screen.width, screen.height), (2560, 1440))
        self.assertEqual(screen.ratio, 1.0)

    def test_without_a_log_the_games_files_and_windows_scaling_are_used(self):
        screen = Install(display_xml=DISPLAY_XML, settings_json='{"scale_mode": "fit"}').screen(windows_scaling=1.5)
        self.assertEqual((screen.width, screen.height, screen.mode, screen.ratio), (3840, 2160, "fit", 1.5))
        self.assertTrue(screen.pixel_sizes)
        self.assertIn("Windows", screen.source)

    def test_nothing_known_about_scaling_assumes_100_percent_and_says_so(self):
        screen = Install(display_xml=DISPLAY_XML).screen()
        self.assertEqual(screen.ratio, 1.0)
        self.assertIn("assumed", screen.source)
        self.assertEqual(screen.mode, "fill")

    def test_chosen_scaling_and_mode_win_over_what_was_found(self):
        screen = Install(log_line=SCALING_LINE, display_xml=DISPLAY_XML).screen(scaling="150%", mode="fit")
        self.assertEqual((screen.ratio, screen.mode), (1.5, "fit"))
        screen = Install(display_xml=DISPLAY_XML).screen(scaling="200%", mode="fit", windows_scaling=1.25)
        self.assertEqual((screen.ratio, screen.mode), (2.0, "fit"))

    def test_no_files_at_all_assumes_a_1080p_screen(self):
        screen = Install().screen()
        self.assertEqual((screen.width, screen.height), P.ASSUMED_SCREEN)
        self.assertIn("assuming", screen.source)

    def test_without_edmcmodernoverlay_sizes_are_canvas_units(self):
        screen = Install(modern=False, display_xml=DISPLAY_XML).screen()
        self.assertFalse(screen.pixel_sizes)
        self.assertEqual(screen.units_per_px, (1.0, 1.0))

    def test_a_damaged_log_is_not_a_crash(self):
        install = Install(log_line="Overlay scaling updated: window=oops", display_xml=DISPLAY_XML)
        self.assertEqual((install.screen().width, install.screen().height), (3840, 2160))

    def test_the_overlays_mode_file_is_read_and_a_damaged_one_ignored(self):
        install = Install(display_xml=DISPLAY_XML, settings_json='{"scale_mode": "fit"}')
        a, b, c = install.patches()
        with a, b, c:
            self.assertEqual(P.detect_scale_mode(), (L.MODE_FIT, "EDMCModernOverlay settings"))
        damaged = Install(display_xml=DISPLAY_XML, settings_json="{not json")
        a, b, c = damaged.patches()
        with a, b, c:
            self.assertEqual(P.detect_scale_mode()[0], L.MODE_FILL)

    def test_the_screen_is_cached_until_refreshed(self):
        install = Install(log_line=SCALING_LINE, display_xml=DISPLAY_XML)
        a, b, c = install.patches()
        with a, b, c:
            first = P.current_screen()
            os.remove(install.log)
            self.assertIs(P.current_screen(), first)
            P.refresh()
            self.assertIsNot(P.current_screen(), first)


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

    def test_an_exact_position_off_the_canvas_gives_the_default(self):
        STORE[L.setting_key("colonisation")] = "custom,1280,0"
        self.assertEqual(P.placement_for("colonisation"), P.SLOTS["colonisation"].default)
        STORE.clear()
        STORE["wntb_colonisation_overlay_x"], STORE["wntb_colonisation_overlay_y"] = "1280", "0"
        self.assertEqual(P.placement_for("colonisation"), P.SLOTS["colonisation"].default)

    def test_an_exact_position_on_the_canvas_is_kept(self):
        STORE[L.setting_key("colonisation")] = "custom,1200,900"
        self.assertEqual(P.placement_for("colonisation"), L.custom_placement(1200, 900))

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

    def recorder(self):
        calls = []

        class Rec:
            def send_message(self, *a, **k):
                calls.append((a, k))
        return Rec(), calls

    def test_a_display_is_moved_to_its_place(self):
        P.save_placement("landing", L.Placement("left", "top", 0, 0))      # block drawn at (20, 636)
        rec, calls = self.recorder()
        with mock.patch.object(P, "current_screen", return_value=MEASURED):
            client = P.client_for("landing", rec, (20, 636, 320, 324))
            client.send_message("id", "hi", "red", 40, 650)
        self.assertEqual(calls[0][0][3:5], (20, 14))     # moved by (-20, -636)

    def test_a_hidden_display_draws_nothing_and_is_shown_by_default(self):
        self.assertFalse(P.is_hidden("landing"))
        P.save_hidden("landing", True)
        self.addCleanup(P.save_hidden, "landing", False)
        self.assertTrue(P.is_hidden("landing"))
        calls = []

        class Rec:
            def send_message(self, *a, **k):
                calls.append(("msg", a, k))

            def send_shape(self, *a, **k):
                calls.append(("shape", a, k))

            def send_vector(self, *a, **k):
                calls.append(("vect", a, k))

        client = P.client_for("landing", Rec(), (20, 636, 320, 324))
        client.send_message("id", "hi", "red", 40, 650, ttl=8)
        client.send_shape("box", "rect", "red", "blue", 1, 2, 30, 40, ttl=8, thickness=2)
        client.send_vector("v", [{"x": 1, "y": 2}], "red", ttl=8)
        self.assertEqual(calls[0][1][1], "")                       # text cleared
        self.assertEqual(calls[0][2]["ttl"], 1)
        self.assertEqual(calls[1][1][2:4] + calls[1][1][6:8], ("", "", 0, 0))    # shape cleared to nothing
        self.assertEqual(calls[2][1][1], [])                       # vector cleared
        P.save_hidden("landing", False)
        self.assertFalse(P.is_hidden("landing"))

    def test_a_display_already_in_place_is_not_wrapped(self):
        P.save_placement("landing", L.custom_placement(20, 636))
        rec, _calls = self.recorder()
        with mock.patch.object(P, "current_screen", return_value=MEASURED):
            self.assertIs(P.client_for("landing", rec, (20, 636, 320, 324)), rec)

    def test_a_placement_failure_leaves_the_display_where_it_was_drawn(self):
        rec, _calls = self.recorder()
        with mock.patch.object(P, "current_screen", side_effect=RuntimeError("boom")):
            self.assertIs(P.client_for("landing", rec, (20, 636, 320, 324)), rec)

    def test_origin_for_keeps_a_right_edge_display_whole(self):
        P.save_placement("inventory", L.Placement("right", "top", 0, 120))
        with mock.patch.object(P, "current_screen", return_value=MEASURED):
            x, y = P.origin_for("inventory", (420, 226))
        self.assertEqual(x, 1280 - 420)           # as far right as the overlay will draw all 420 px of it
        self.assertEqual(y, round(120 * 960 / 1728))


def fake_overlay_api(record, fail_for=()):
    """A stand-in for EDMCModernOverlay's overlay_plugin.overlay_api module, recording what is asked of it."""
    def define_plugin_group(**kwargs):
        if kwargs.get("plugin_group_name") in fail_for:
            raise RuntimeError("boom")
        record.append(kwargs)
        return True

    package = types.ModuleType("overlay_plugin")
    api = types.ModuleType("overlay_plugin.overlay_api")
    api.define_plugin_group = define_plugin_group
    package.overlay_api = api
    return {"overlay_plugin": package, "overlay_plugin.overlay_api": api}


class GroupOffsetTests(unittest.TestCase):
    def setUp(self):
        STORE.clear()
        P.refresh()
        P.overlay._applied_offsets.clear()

    def test_only_displays_with_a_group_are_listed_and_most_need_no_offset(self):
        offsets = P.group_offsets({k: s.default for k, s in P.SLOTS.items()}, MEASURED)
        self.assertEqual(set(offsets), {s.group for s in P.SLOTS.values() if s.group})
        self.assertNotIn("", offsets)
        self.assertGreater(offsets["wntb_inventory"], 0)         # right, top: past the clamp
        self.assertGreater(offsets["wntb_screenshot"], 0)
        self.assertEqual(offsets["wntb_landing"], 0.0)           # left, bottom
        self.assertEqual(offsets["wntb_discovery"], 0.0)         # center, top

    def test_offsets_are_sent_through_the_overlays_api_and_only_when_they_change(self):
        calls = []
        with mock.patch.dict(sys.modules, fake_overlay_api(calls)):
            self.assertTrue(P.overlay.set_group_offsets({"wntb_inventory": 245.0, "wntb_landing": 0.0}))
            self.assertEqual(len(calls), 2)
            self.assertEqual(calls[0]["plugin_name"], "WNTB")
            self.assertEqual((calls[0]["plugin_group_name"], calls[0]["plugin_group_offset_x"]), ("wntb_inventory", 245.0))
            self.assertTrue(P.overlay.set_group_offsets({"wntb_inventory": 245.0, "wntb_landing": 0.0}))
            self.assertEqual(len(calls), 2)                                  # nothing changed: nothing sent
            self.assertTrue(P.overlay.set_group_offsets({"wntb_inventory": 100.0}))
            self.assertEqual(len(calls), 3)

    def test_a_missing_overlay_api_is_a_quiet_false(self):
        with mock.patch.dict(sys.modules, {"overlay_plugin": None, "overlay_plugin.overlay_api": None}):
            self.assertFalse(P.overlay.group_offsets_available())
            self.assertFalse(P.overlay.set_group_offsets({"wntb_inventory": 245.0}))

    def test_one_failing_group_does_not_stop_the_others(self):
        calls = []
        with mock.patch.dict(sys.modules, fake_overlay_api(calls, fail_for=("wntb_inventory",))):
            self.assertFalse(P.overlay.set_group_offsets({"wntb_inventory": 245.0, "wntb_screenshot": 10.0}))
        self.assertEqual([c["plugin_group_name"] for c in calls], ["wntb_screenshot"])

    def test_applying_uses_the_saved_placements(self):
        P.save_placement("inventory", L.Placement("left", "top", 0, 0))
        calls = []
        with mock.patch.dict(sys.modules, fake_overlay_api(calls)), mock.patch.object(P, "current_screen", return_value=MEASURED):
            self.assertTrue(P.apply_group_offsets())
        sent = {c["plugin_group_name"]: c["plugin_group_offset_x"] for c in calls}
        self.assertEqual(sent["wntb_inventory"], 0.0)                      # moved to the left: no offset
        self.assertGreater(sent["wntb_screenshot"], 0)                     # its default is still bottom right

    def test_a_display_with_a_group_is_drawn_at_the_clamp_when_the_api_is_there(self):
        P.save_placement("inventory", L.Placement("right", "top", 0, 0))
        with mock.patch.dict(sys.modules, fake_overlay_api([])), mock.patch.object(P, "current_screen", return_value=MEASURED):
            dx, dy = P.shift_for("inventory", (900, 120, 420, 226))
            origin = P.origin_for("inventory", (420, 226))
        width = P.slot_size("inventory")[0]       # the display's nominal width at the current look
        self.assertEqual(dx, 1280 - width - 900)
        self.assertEqual(origin[0], 1280 - width)

    def test_the_switch_turns_offsets_off_and_clears_them(self):
        STORE[P.CFG_OFFSETS] = "0"
        with mock.patch.dict(sys.modules, fake_overlay_api([])):
            self.assertFalse(P.can_offset("inventory"))
        offsets = P.group_offsets(None, MEASURED)
        self.assertTrue(offsets)
        self.assertEqual(set(offsets.values()), {0.0})                      # nothing offset, so earlier ones are cleared
        STORE[P.CFG_OFFSETS] = "1"
        self.assertTrue(P.offsets_enabled())
        STORE.clear()
        self.assertTrue(P.offsets_enabled())                                # on unless turned off

    def test_without_the_api_a_display_just_stops_at_the_clamp_and_mining_never_uses_it(self):
        with mock.patch.dict(sys.modules, {"overlay_plugin": None, "overlay_plugin.overlay_api": None}):
            self.assertFalse(P.can_offset("inventory"))
        with mock.patch.dict(sys.modules, fake_overlay_api([])):
            self.assertTrue(P.can_offset("inventory"))
            self.assertFalse(P.can_offset("mining_stats"))                  # two displays share one overlay group: not offset

    def test_the_group_names_match_the_ones_the_modules_register(self):
        import re
        plugin_dir = os.path.join(os.path.dirname(__file__), "..", "plugin")
        modules = {"colonisation": "colonisation_overlay.py", "discovery": "discovery.py", "notable": "notable.py",
                   "interdiction": "interdiction.py", "landing": "landing.py", "inventory": "inventory_panel.py",
                   "screenshots": "screenshots.py"}
        for key, filename in modules.items():
            with open(os.path.join(plugin_dir, filename), encoding="utf-8") as handle:
                source = handle.read()
            name = re.search(r'^GROUP_NAME = "(\w+)"', source, re.M).group(1)
            self.assertEqual(P.SLOTS[key].group, name, key)
            self.assertTrue(P.SLOTS[key].group_prefix.startswith(name), key)


class PreviewTests(unittest.TestCase):
    def test_there_is_a_marker_at_the_screens_top_left_corner_and_no_full_screen_outline(self):
        items = P.preview_shapes({}, MEASURED)
        self.assertEqual(len(items), 1)
        self.assertEqual((items[0]["x"], items[0]["y"]), (0, 0))
        self.assertLess(items[0]["w"], 400)       # the overlay squashes anything wider than the canvas, so no big outline

    def test_every_default_box_is_on_the_screen_at_its_real_size(self):
        placements = {key: slot.default for key, slot in P.SLOTS.items()}
        items = P.preview_shapes(placements, MEASURED)
        self.assertEqual(len(items), len(P.SLOTS) + 1)
        ux, uy = MEASURED.units_per_px
        for item in items[1:]:
            self.assertGreaterEqual(item["x"], 0, item["label"])
            self.assertGreaterEqual(item["y"], 0, item["label"])
            self.assertLessEqual(item["x"] + item["w"] * ux, 1280.5, item["label"])      # the right edge is on the canvas
            self.assertLessEqual(item["y"] + item["h"] * uy, 960.5, item["label"])

    def test_a_bottom_right_box_is_whole_and_reaches_the_bottom_where_the_overlay_allows(self):
        for screen in (MEASURED, L.Screen(1920, 1080, ratio=1.0, pixel_sizes=True),
                       L.Screen(5120, 1440, ratio=1.0, pixel_sizes=True)):
            item = P.preview_shapes({"screenshots": L.Placement("right", "bottom", 0, 0)}, screen)[1]
            ux, uy = screen.units_per_px
            self.assertLessEqual(item["x"] + item["w"], 1280, str(screen))            # never squashed by the overlay
            self.assertAlmostEqual(item["y"] + item["h"] * uy, 960, delta=1.0, msg=str(screen))   # flush with the bottom

    def test_a_grouped_preview_is_drawn_inside_the_displays_overlay_group_at_the_clamp(self):
        placements = {"inventory": L.Placement("right", "top", 0, 0), "mining_stats": L.Placement("right", "top", 0, 0)}
        items = {i["label"]: i for i in P.preview_shapes(placements, MEASURED, use_groups=True)}
        inventory = items["Inventory pickups and bars"]
        self.assertTrue(inventory["id"].startswith("wntb_inventory_"))      # so the group's offset moves it like the real display
        self.assertEqual(inventory["x"], 1280 - P.slot_size("inventory")[0])
        self.assertGreater(inventory["offset_x"], 0)
        mining = items["Mining stats"]
        self.assertTrue(mining["id"].startswith("wntb_placeprev_"))          # no group: it just stops at the clamp
        self.assertEqual(mining["offset_x"], 0.0)

    def test_a_fit_overlay_clamps_both_ways_so_the_box_stays_whole(self):
        screen = L.Screen(1920, 1200, mode=L.MODE_FIT)
        item = P.preview_shapes({"screenshots": L.Placement("right", "bottom", 0, 0)}, screen)[1]
        self.assertLessEqual(item["x"] + item["w"], 1280)
        self.assertLessEqual(item["y"] + item["h"], 960)


class DefaultSpotTests(unittest.TestCase):
    """The default spots, at the slots' nominal (worst-case) sizes, on a 16:9 screen of 1920 x 1080 or larger. The displays are sized in
    pixels, so on a smaller screen they take up more of it and can overlap; Overlay Placement is where to move them then."""

    # Pairs that overlap by design. None: every default spot is clear of every other.
    KNOWN: set = set()

    @staticmethod
    def rects(width, height):
        out = {}
        for key, slot in P.SLOTS.items():
            w, h = slot.size
            place = slot.default
            x = {"left": place.dx, "right": width - w - place.dx}.get(place.h, (width - w) / 2 + place.dx)
            y = {"top": place.dy, "bottom": height - h - place.dy}.get(place.v, (height - h) / 2 + place.dy)
            out[key] = (x, y, x + w, y + h)
        return out

    def overlaps(self, width, height):
        rects, found = self.rects(width, height), set()
        keys = list(rects)
        for i, first in enumerate(keys):
            for second in keys[i + 1:]:
                a, b = rects[first], rects[second]
                if min(a[2], b[2]) > max(a[0], b[0]) and min(a[3], b[3]) > max(a[1], b[1]):
                    found.add(frozenset((first, second)))
        return found

    def test_no_default_spots_overlap_on_common_16_9_screens(self):
        for width, height in ((1920, 1080), (2560, 1440), (3840, 2160)):
            with self.subTest(screen=(width, height)):
                self.assertEqual(self.overlaps(width, height) - self.KNOWN, set())

    def test_the_alerts_that_can_show_at_once_are_stacked_not_overlaid(self):
        rects = self.rects(1920, 1080)
        interdiction, discovery = rects["interdiction"], rects["discovery"]
        self.assertLessEqual(interdiction[3], discovery[1])            # the warning sits above the discovery alerts
        notable, inventory, flight = rects["notable"], rects["inventory"], rects["flight_alerts"]
        self.assertLessEqual(notable[3], inventory[1])                  # the notable-find card is above the inventory display, top right
        self.assertLessEqual(inventory[3], flight[1])                   # and the flight card is below it
        self.assertGreaterEqual(notable[0], rects["colonisation"][2])   # clear of the Colonization list's widest case

    def test_flight_alerts_clear_the_inventory_display_on_a_short_screen_too(self):
        for height in (720, 900, 1080):
            rects = self.rects(1920, height)
            self.assertLessEqual(rects["inventory"][3], rects["flight_alerts"][1], height)

    def test_the_route_card_clears_the_colonization_list(self):
        rects = self.rects(1920, 1080)
        self.assertLessEqual(rects["route"][3], rects["colonisation"][1])

    def test_the_right_hand_column_is_stacked_top_to_bottom_without_gaps_overlapping(self):
        rects = self.rects(1920, 1080)
        order = ["notable", "surface_compass", "inventory", "mining_stats", "flight_alerts", "missions", "screenshots"]
        for upper, lower in zip(order, order[1:]):
            self.assertLessEqual(rects[upper][3], rects[lower][1], f"{upper} should sit above {lower}")


if __name__ == "__main__":
    unittest.main()
