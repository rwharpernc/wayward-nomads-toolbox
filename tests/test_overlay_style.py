"""The shared overlay look: palettes, text size stepping, the size estimates cards are built from, and the saved choices
(overlay_style.py and overlay_appearance.py)."""
from __future__ import annotations

import os
import re
import sys
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

from plugin import overlay_appearance as A  # noqa: E402
from plugin import overlay_style as S  # noqa: E402

HEX = re.compile(r"^#(?:[0-9a-f]{6}|[0-9a-f]{8})$")


class PaletteTests(unittest.TestCase):
    def test_every_scheme_defines_every_role_with_a_real_color(self):
        for name, palette in S.SCHEMES.items():
            self.assertEqual(name, palette.name)
            for role in S.ROLES:
                if role != "faint":      # derived from muted (below)
                    self.assertRegex(getattr(palette, role), HEX, f"{name} {role}")
            faint, muted = S.Look(palette).color("faint"), palette.muted
            self.assertRegex(faint, HEX, f"{name} faint")
            self.assertLess(int(faint[1:3], 16), int(muted[1:3], 16), f"{name}: faint is darker than muted")
            self.assertEqual(len(palette.accents), 3, name)
            self.assertEqual(len(palette.series), 4, name)
            for color in palette.accents + palette.series:
                self.assertRegex(color, HEX, name)

    def test_darken_scales_each_channel_and_keeps_alpha(self):
        self.assertEqual(S.darken("#808040", 0.5), "#404020")
        self.assertEqual(S.darken("#80ffffff", 0.5), "#807f7f7f")
        self.assertEqual(S.darken("white", 0.5), "white")

    def test_card_fills_are_translucent_black_so_the_game_shows_through(self):
        for name, palette in S.SCHEMES.items():
            self.assertRegex(palette.fill, r"^#[0-9a-f]{2}000000$", name)

    def test_there_are_presets_including_a_high_contrast_and_a_color_blind_safe_one(self):
        self.assertGreaterEqual(len(S.SCHEMES), 5)
        self.assertIn("High contrast", S.SCHEMES)
        self.assertIn("Color-blind safe", S.SCHEMES)
        self.assertIn(S.DEFAULT_SCHEME, S.SCHEMES)

    def test_a_color_blind_safe_scheme_does_not_ask_red_and_green_to_mean_good_and_bad(self):
        palette = S.SCHEMES["Color-blind safe"]
        self.assertNotEqual(palette.ok, palette.danger)
        for color in (palette.ok, palette.danger, palette.warn):          # none of them a pure green
            red, green, blue = (int(color[i:i + 2], 16) for i in (1, 3, 5))
            self.assertFalse(green > red + 60 and green > blue + 60, color)

    def test_the_four_series_and_three_accents_are_distinct(self):
        for name, palette in S.SCHEMES.items():
            self.assertEqual(len(set(palette.series)), 4, name)
            self.assertEqual(len(set(palette.accents)), 3, name)

    def test_alpha_helpers(self):
        self.assertEqual(S.with_alpha("#f97316", 0x80), "#80f97316")
        self.assertEqual(S.with_alpha("#80f97316", 0x40), "#80f97316")      # already has one
        self.assertEqual(S.LEGACY.soft("#f97316"), "#80f97316")

    def test_an_unknown_scheme_falls_back_to_the_default(self):
        self.assertEqual(S.scheme_named("Not a scheme").name, S.DEFAULT_SCHEME)
        self.assertEqual(S.scheme_named(None).name, S.DEFAULT_SCHEME)


class LookTests(unittest.TestCase):
    def test_the_legacy_look_is_the_geometry_the_displays_always_had(self):
        look = S.LEGACY
        self.assertEqual((look.char_px("normal"), look.line_px("normal"), look.pad_x(10), look.pad_y(8)), (8.0, 20, 10, 8))
        self.assertEqual((look.char_px("large"), look.line_px("large"), look.char_px("huge"), look.line_px("huge")), (12.5, 26, 16.5, 34))
        self.assertEqual(look.size("large"), "large")

    def test_text_size_steps_through_the_four_sizes_and_stops_at_the_ends(self):
        for level, expected in ((-1, "small"), (0, "normal"), (1, "large"), (2, "huge")):
            self.assertEqual(S.Look(text_level=level).size("normal"), expected)
        self.assertEqual(S.Look(text_level=2).size("huge"), "huge")        # already the largest: stays
        self.assertEqual(S.Look(text_level=-1).size("small"), "small")
        self.assertEqual(S.Look(text_level=1).size("huge"), "huge")

    def test_a_larger_size_means_wider_characters_taller_lines_and_so_a_wider_card(self):
        small, normal, large = (S.Look(text_level=n) for n in (-1, 0, 1))
        self.assertLess(small.char_px(), normal.char_px())
        self.assertLess(normal.char_px(), large.char_px())
        self.assertLess(normal.line_px(), large.line_px())
        self.assertLess(normal.text_width("Ceramic Composites"), large.text_width("Ceramic Composites"))

    def test_padding_and_line_spacing_are_added_to_each_display_own_base(self):
        look = S.Look(pad_extra=6, line_extra=3)
        self.assertEqual((look.pad_x(22), look.pad_y(16)), (28, 22))
        self.assertEqual(look.line_px("normal"), 23)
        self.assertEqual(look.line_px("large"), 29)

    def test_scale_compares_a_size_with_its_default(self):
        self.assertEqual(S.LEGACY.scale("normal"), 1.0)
        self.assertGreater(S.Look(text_level=1).scale("normal"), 1.0)

    def test_colors_by_role_and_a_bad_role_is_an_error(self):
        self.assertEqual(S.LEGACY.color("title"), "#fdba74")
        self.assertEqual(S.Look(S.SCHEMES["Ice blue"]).color("border"), "#38bdf8")
        with self.assertRaises(ValueError):
            S.LEGACY.color("nonsense")
        self.assertEqual(S.LEGACY.accent(4), S.LEGACY.palette.accents[1])      # wraps rather than failing
        self.assertEqual(S.LEGACY.series(5), S.LEGACY.palette.series[1])

    def test_the_default_look_is_a_little_roomier_than_the_legacy_one(self):
        self.assertGreater(S.DEFAULT.pad_extra, S.LEGACY.pad_extra)
        self.assertGreater(S.DEFAULT.line_extra, S.LEGACY.line_extra)
        self.assertEqual(S.DEFAULT.text_level, 0)

    def test_choices_are_clamped_so_damaged_settings_never_break_drawing(self):
        look = S.look_from_choices("Nope", 99, -5, 500)
        self.assertEqual(look.palette.name, S.DEFAULT_SCHEME)
        self.assertEqual((look.text_level, look.pad_extra, look.line_extra), (1, 0, 20))   # the largest offered size is Larger
        self.assertEqual(S.look_from_choices("Ice blue", -9, 99, -1).text_level, -1)

    def test_menu_labels_round_trip_and_unknown_values_use_the_nearest(self):
        for choices in (S.TEXT_CHOICES, S.PADDING_CHOICES, S.SPACING_CHOICES):
            for label, value in choices:
                self.assertEqual(S.label_for(choices, value), label)
                self.assertEqual(S.value_for(choices, label, -99), value)
        self.assertEqual(S.label_for(S.PADDING_CHOICES, 7), "Comfortable")
        self.assertEqual(S.value_for(S.TEXT_CHOICES, "Nonsense", 5), 5)


class SavedChoicesTests(unittest.TestCase):
    def setUp(self):
        STORE.clear()
        # The module binds EDMC's `config` when first imported, which another test file may have done with its own stand-in.
        patcher = mock.patch.object(A, "config", FakeConfig())
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_nothing_saved_gives_the_default_scheme_at_the_size_the_displays_have_had(self):
        look = A.current_look()
        self.assertEqual((look.palette, look.text_level, look.pad_extra, look.line_extra),
                         (S.DEFAULT.palette, A.DEFAULT_TEXT_SIZE, A.LOCKED_PADDING, A.LOCKED_SPACING))
        self.assertEqual(A.DEFAULT_TEXT_SIZE, 1)     # "Larger": nobody's overlay changes until they pick a size

    def test_the_scheme_and_text_size_are_read_back_and_spacing_cannot_be_changed(self):
        # Choices saved by earlier versions (text level, padding, spacing) are ignored.
        STORE.update({A.CFG_SCHEME: "High contrast", A.CFG_TEXT_SIZE: "-1", "wntb_overlay_text_level": "2",
                      "wntb_overlay_padding": "14", "wntb_overlay_line_spacing": "7"})
        look = A.current_look()
        self.assertEqual((look.palette.name, look.text_level, look.pad_extra, look.line_extra),
                         ("High contrast", -1, A.LOCKED_PADDING, A.LOCKED_SPACING))

    def test_a_damaged_or_out_of_range_text_size_is_kept_in_range(self):
        for saved, expected in (("9", 1), ("-9", -1), ("nonsense", 1)):
            STORE[A.CFG_TEXT_SIZE] = saved
            self.assertEqual(A.current_look().text_level, expected, saved)

    def test_widths_are_padded_so_a_box_holds_its_text(self):
        look = S.Look()
        self.assertEqual(look.text_width("x" * 10, "normal"), round(10 * S.CHAR_PX["normal"] * S.WIDTH_PAD))
        self.assertGreater(look.text_width("x" * 10, "normal"), round(10 * S.CHAR_PX["normal"]))

    def test_a_damaged_scheme_falls_back_instead_of_failing(self):
        STORE.update({A.CFG_SCHEME: "???"})
        self.assertEqual(A.current_look().palette, S.DEFAULT.palette)

    def test_every_overlay_module_takes_its_look_from_the_shared_settings(self):
        plugin_dir = os.path.join(os.path.dirname(__file__), "..", "plugin")
        for filename in ("colonisation_panel.py", "discovery.py", "notable.py", "interdiction.py", "landing.py", "inventory_panel.py",
                         "mining_overlay.py", "screenshots.py"):
            with open(os.path.join(plugin_dir, filename), encoding="utf-8") as handle:
                self.assertIn("overlay_appearance.current_look()", handle.read(), filename)


if __name__ == "__main__":
    unittest.main()
