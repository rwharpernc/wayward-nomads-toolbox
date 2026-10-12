"""
Screenshot file handling: output names from a mask (screenshot_naming.py), HUD-panel crop rectangles
(screenshot_gui_focus.py) and conversion, cropping, thumbnails and the delayed delete (screenshot_convert.py).

The thumbnail tests guard the rule that a picture shown in EDMC's main window is bounded on both axes, so an ultrawide or
triple-monitor screenshot can never widen the window. Temporary folders only; the same on Windows and Linux.

Run with: python -m unittest discover -s tests
"""
from __future__ import annotations

import os
import re
import sys
import tempfile
import types
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
if "config" not in sys.modules:
    _stub = types.ModuleType("config")
    _stub.appname = "EDMarketConnector"
    _stub.config = types.SimpleNamespace(get_str=lambda key: "", default_journal_dir="")
    sys.modules["config"] = _stub

from plugin import screenshot_gui_focus as focus, screenshot_naming as naming  # noqa: E402

try:
    from PIL import Image
    from plugin import screenshot_convert as convert
except ImportError:   # Pillow ships with EDMC; a bare Python may not have it
    Image = None
    convert = None


def build(mask, directory, **kwargs):
    fields = dict(system="Sol", body="Sol 3", cmdr="Alice", source_filename="\\ED_Pictures\\Screenshot_0001.bmp")
    fields.update(kwargs)
    return naming.build_output_path(mask, directory, **fields)


class NamingTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.dir = self._tmp.name

    def touch(self, name):
        open(os.path.join(self.dir, name), "w").close()

    def test_the_tokens_are_replaced_and_the_body_drops_the_system_prefix(self):
        path = build("SYSTEM(BODY)_NNNNN.png", self.dir)
        self.assertEqual(os.path.basename(path), "Sol(3)_00001.png")
        self.assertEqual(os.path.dirname(path), self.dir)

    def test_missing_names_read_unknown(self):
        path = build("SYSTEM(BODY)(CMDR)_NNNNN.png", self.dir, system=None, body=None, cmdr="")
        self.assertEqual(os.path.basename(path), "Unknown(Unknown)(Unknown)_00001.png")

    def test_a_body_that_is_only_the_system_name_is_kept_whole(self):
        self.assertEqual(os.path.basename(build("BODY_NNNNN.png", self.dir, body="Sol")), "Sol_00001.png")

    def test_characters_a_filesystem_rejects_are_stripped(self):
        path = build("SYSTEM_NNNNN.png", self.dir, system='Bad:Name/With*Odd?"<>|Chars')
        name = os.path.basename(path)
        self.assertEqual(name, "BadNameWithOddChars_00001.png")
        self.assertFalse(set(':/*?"<>|\\') & set(name))

    def test_the_sequence_continues_after_the_highest_existing_number(self):
        for name in ("Sol(3)_00001.png", "Sol(3)_00007.png", "Sol(3)_00003.png", "Other(1)_00099.png", "Sol(3)_notanumber.png"):
            self.touch(name)
        self.assertEqual(os.path.basename(build("SYSTEM(BODY)_NNNNN.png", self.dir)), "Sol(3)_00008.png")

    def test_a_date_mask_has_no_sequence_and_a_utc_stamp(self):
        name = os.path.basename(build("SYSTEM_DATE.png", self.dir))
        self.assertRegex(name, r"^Sol_\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2}\.png$")

    def test_high_resolution_captures_are_prefixed(self):
        path = build("SYSTEM_NNNNN.png", self.dir, source_filename="\\ED_Pictures\\HighRes_0004.png")
        self.assertEqual(os.path.basename(path), "HighRes_Sol_00001.png")

    def test_every_preset_renders_to_a_clean_file_name(self):
        for mask in naming.MASK_PRESETS:
            name = os.path.basename(build(mask, self.dir))
            self.assertTrue(name.endswith(".png"), mask)
            for token in ("SYSTEM", "BODY", "CMDR", "DATE", "NNNNN"):
                self.assertNotIn(token, name, mask)
            self.assertIsNone(re.search(r'[:/\\*?"<>|]', name), mask)

    def test_the_default_mask_is_one_of_the_presets(self):
        self.assertIn(naming.DEFAULT_MASK, naming.MASK_PRESETS)


class CropRectTests(unittest.TestCase):
    def test_at_the_reference_size_the_rectangles_are_unchanged(self):
        self.assertEqual(focus.panel_crop_rect(focus.GUI_FOCUS_EXTERNAL_PANEL, 1920, 1080), (850, 279, 1306, 538))
        self.assertEqual(focus.panel_crop_rect(focus.GUI_FOCUS_COMMS_PANEL, 1920, 1080), (406, 123, 919, 832))

    def test_the_role_and_internal_panels_share_one_rectangle(self):
        self.assertEqual(focus.panel_crop_rect(focus.GUI_FOCUS_ROLE_PANEL, 1920, 1080),
                         focus.panel_crop_rect(focus.GUI_FOCUS_INTERNAL_PANEL, 1920, 1080))

    def test_a_screen_with_no_panel_to_crop_gives_none(self):
        for gui_focus in (focus.GUI_FOCUS_NONE, focus.GUI_FOCUS_GALAXY_MAP, focus.GUI_FOCUS_CODEX, 99):
            self.assertIsNone(focus.panel_crop_rect(gui_focus, 1920, 1080))

    def test_a_larger_16_by_9_screenshot_scales_the_rectangle_evenly(self):
        self.assertEqual(focus.panel_crop_rect(focus.GUI_FOCUS_EXTERNAL_PANEL, 3840, 2160), (1700, 558, 2612, 1076))

    def test_an_ultrawide_screenshot_keeps_the_panel_the_same_shape_and_centres_it(self):
        normal = focus.panel_crop_rect(focus.GUI_FOCUS_COMMS_PANEL, 1920, 1080)
        wide = focus.panel_crop_rect(focus.GUI_FOCUS_COMMS_PANEL, 5760, 1080)   # three monitors
        self.assertEqual((wide[2] - wide[0], wide[3] - wide[1]), (normal[2] - normal[0], normal[3] - normal[1]))
        self.assertEqual(wide[0] - normal[0], (5760 - 1920) // 2)

    def test_a_taller_than_16_by_9_screenshot_is_centred_vertically(self):
        normal = focus.panel_crop_rect(focus.GUI_FOCUS_COMMS_PANEL, 1920, 1080)
        tall = focus.panel_crop_rect(focus.GUI_FOCUS_COMMS_PANEL, 1920, 1440)
        self.assertEqual((tall[2] - tall[0], tall[3] - tall[1]), (normal[2] - normal[0], normal[3] - normal[1]))
        self.assertEqual(tall[1] - normal[1], (1440 - 1080) // 2)

    def test_the_rectangle_always_fits_inside_the_screenshot(self):
        for width, height in ((1280, 720), (1920, 1080), (2560, 1440), (3440, 1440), (5760, 1080), (1920, 1200)):
            for gui_focus in (focus.GUI_FOCUS_EXTERNAL_PANEL, focus.GUI_FOCUS_COMMS_PANEL, focus.GUI_FOCUS_ROLE_PANEL):
                left, top, right, bottom = focus.panel_crop_rect(gui_focus, width, height)
                self.assertTrue(0 <= left < right <= width and 0 <= top < bottom <= height, (width, height, gui_focus))

    def test_the_thargoid_crop_is_the_bottom_left_quarter(self):
        self.assertEqual(focus.thargoid_crop_rect(1920, 1080), (0, 540, 960, 1080))
        self.assertEqual(focus.thargoid_crop_rect(3841, 2161), (0, 1080, 1920, 2161))


@unittest.skipIf(convert is None, "Pillow is not installed")
class ConvertTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.dir = self._tmp.name

    def save_image(self, name, size=(64, 48), mode="RGB"):
        path = os.path.join(self.dir, name)
        Image.new(mode, size, (200, 100, 50)).save(path)
        return path

    def test_the_source_is_found_by_its_file_name_in_the_first_folder_that_has_it(self):
        first, second = os.path.join(self.dir, "a"), os.path.join(self.dir, "b")
        os.makedirs(first)
        os.makedirs(second)
        open(os.path.join(second, "Screenshot_0001.bmp"), "w").close()
        found = convert.find_source_file([first, second], "\\ED_Pictures\\Screenshot_0001.bmp")
        self.assertEqual(found, os.path.join(second, "Screenshot_0001.bmp"))
        open(os.path.join(first, "Screenshot_0001.bmp"), "w").close()
        self.assertEqual(convert.find_source_file([first, second], "Screenshot_0001.bmp"),
                         os.path.join(first, "Screenshot_0001.bmp"))

    def test_a_source_that_is_nowhere_gives_none(self):
        self.assertIsNone(convert.find_source_file([self.dir], "Screenshot_9999.bmp"))
        self.assertIsNone(convert.find_source_file([], "Screenshot_0001.bmp"))

    def test_a_png_is_written_into_a_folder_made_for_it(self):
        source = self.save_image("Screenshot_0001.bmp", (64, 48))
        destination = os.path.join(self.dir, "out", "deeper", "shot.png")
        image = convert.convert_to_png(source, destination)
        self.assertEqual(image.size, (64, 48))
        with Image.open(destination) as written:
            self.assertEqual((written.format, written.size), ("PNG", (64, 48)))

    def test_the_source_can_be_deleted_straight_after_converting(self):
        source = self.save_image("Screenshot_0002.bmp")
        image = convert.convert_to_png(source, os.path.join(self.dir, "shot.png"))
        os.remove(source)
        self.assertEqual(image.size, (64, 48))   # already read into memory

    def test_cropping_returns_the_requested_box(self):
        image = Image.new("RGB", (100, 80))
        self.assertEqual(convert.crop(image, (10, 20, 60, 70)).size, (50, 50))

    def test_a_thumbnail_is_a_gif_within_both_limits(self):
        data = convert.thumbnail_photo_data(Image.new("RGB", (1920, 1080)))
        self.assertTrue(data.startswith(b"GIF8"))
        import io
        with Image.open(io.BytesIO(data)) as thumb:
            self.assertLessEqual(thumb.width, 200)
            self.assertLessEqual(thumb.height, 140)

    def test_an_ultrawide_or_surround_screenshot_cannot_make_a_wide_thumbnail(self):
        import io
        for size in ((7680, 1080), (11520, 2160), (5760, 1080), (1000, 8000), (50, 30)):
            with Image.open(io.BytesIO(convert.thumbnail_photo_data(Image.new("RGB", size)))) as thumb:
                self.assertLessEqual(thumb.width, 200, size)
                self.assertLessEqual(thumb.height, 140, size)

    def test_a_small_picture_is_not_enlarged(self):
        import io
        with Image.open(io.BytesIO(convert.thumbnail_photo_data(Image.new("RGB", (50, 30))))) as thumb:
            self.assertEqual(thumb.size, (50, 30))

    def test_the_limits_can_be_chosen_and_the_original_is_left_alone(self):
        import io
        image = Image.new("RGB", (1000, 1000))
        with Image.open(io.BytesIO(convert.thumbnail_photo_data(image, max_height=40, max_width=60))) as thumb:
            self.assertLessEqual(thumb.width, 60)
            self.assertLessEqual(thumb.height, 40)
        self.assertEqual(image.size, (1000, 1000))

    def test_a_thumbnail_can_be_made_from_a_saved_file(self):
        import io
        path = self.save_image("saved.png", (4000, 500))
        with Image.open(io.BytesIO(convert.open_thumbnail_data(path, max_height=140, max_width=200))) as thumb:
            self.assertLessEqual(thumb.width, 200)

    def test_a_permission_problem_is_explained_for_the_os_it_happened_on(self):
        text = convert.describe_os_error(PermissionError("denied"))
        if os.name == "nt":
            self.assertIn("Controlled Folder Access", text)
        else:
            self.assertIn("permissions", text)
        self.assertIn("denied", text)
        self.assertEqual(convert.describe_os_error(OSError("disk full")), "disk full")

    def test_delayed_deletes_remove_the_oldest_file_first_and_survive_a_missing_one(self):
        scheduled = []
        queue = convert.DeleteQueue(lambda delay, callback: scheduled.append((delay, callback)))
        older, newer = self.save_image("older.bmp"), self.save_image("newer.bmp")
        queue.schedule(older, 5000)
        queue.schedule(newer, 5000)
        queue.schedule(os.path.join(self.dir, "never-existed.bmp"), 5000)
        self.assertEqual([delay for delay, _ in scheduled], [5000, 5000, 5000])
        self.assertTrue(os.path.exists(older) and os.path.exists(newer))   # nothing goes before the grace period
        scheduled[0][1]()
        self.assertFalse(os.path.exists(older))
        self.assertTrue(os.path.exists(newer))
        scheduled[1][1]()
        with self.assertLogs(level="WARNING"):
            scheduled[2][1]()          # the missing file is reported, not raised
        self.assertFalse(os.path.exists(newer))
        scheduled[0][1]()               # a spare callback with nothing queued does nothing
        self.assertTrue(True)


if __name__ == "__main__":
    unittest.main()
