"""The built-in overlay's scene (overlay_scene.py) and how it is drawn (overlay_raster.py)."""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from plugin import overlay_scene as S  # noqa: E402

try:
    from PIL import Image  # noqa: F401
    from plugin import overlay_raster as R  # noqa: E402
except ImportError:                                                    # pragma: no cover - Pillow ships with EDMC; a bare test machine may lack it
    R = None


class Clock:
    def __init__(self):
        self.now = 100.0

    def __call__(self):
        return self.now


def text(ident="t", body="hi", ttl=4, **extra):
    return {"id": ident, "text": body, "color": "#ffffff", "x": 10, "y": 20, "ttl": ttl, "size": "normal", **extra}


def rect(ident="r", ttl=4, w=100, h=50, **extra):
    return {"id": ident, "shape": "rect", "color": "#ff0000", "fill": "#80000000", "x": 5, "y": 6, "w": w, "h": h, "ttl": ttl, **extra}


class SceneTests(unittest.TestCase):
    def setUp(self):
        self.clock = Clock()
        self.scene = S.Scene(self.clock)

    def test_each_kind_of_payload_becomes_an_item(self):
        self.scene.apply(text())
        self.scene.apply(rect())
        self.scene.apply({"id": "c", "shape": "circle", "color": "#fff", "fill": "", "x": 1, "y": 2, "radius": 7, "ttl": 4})
        self.scene.apply({"id": "v", "shape": "vect", "color": "#fff", "ttl": 4, "vector": [{"x": 1, "y": 2}, {"x": 3, "y": 4, "marker": "cross"}]})
        kinds = {item.id: item.kind for item in self.scene.items()}
        self.assertEqual(kinds, {"t": S.TEXT, "r": S.RECT, "c": S.CIRCLE, "v": S.VECT})

    def test_text_is_always_drawn_above_panels_whatever_order_they_were_sent_in(self):
        self.scene.apply(text("t1"))
        self.scene.apply(rect("panel"))                       # the panel arrives after the text
        self.scene.apply({"id": "c", "shape": "circle", "color": "#fff", "x": 1, "y": 2, "radius": 7, "ttl": 4})
        self.assertEqual([item.id for item in self.scene.items()], ["panel", "c", "t1"])
        self.clock.now += 3
        self.scene.apply(rect("panel"))                       # the panel is sent again: still below
        self.assertEqual([item.id for item in self.scene.items()][0], "panel")

    def test_an_id_sent_again_replaces_what_it_drew(self):
        self.scene.apply(text("t", "first"))
        self.scene.apply(text("t", "second"))
        self.assertEqual([item.text for item in self.scene.items()], ["second"])

    def test_something_that_draws_nothing_removes_the_id(self):
        self.scene.apply(text("t"))
        self.scene.apply(rect("r"))
        self.scene.apply({"id": "c", "shape": "circle", "color": "#fff", "x": 1, "y": 2, "radius": 7, "ttl": 4})
        self.scene.apply({"id": "v", "shape": "vect", "color": "#fff", "ttl": 4, "vector": [{"x": 1, "y": 2}]})
        self.scene.apply(text("t", "", ttl=1))
        self.scene.apply(rect("r", w=0, h=0, color="", fill="", ttl=1))
        self.scene.apply({"id": "c", "shape": "circle", "color": "", "fill": "", "x": 1, "y": 2, "radius": 7, "ttl": 1})
        self.scene.apply({"id": "v", "shape": "vect", "color": "#fff", "ttl": 1, "vector": []})
        self.assertEqual(self.scene.items(), [])

    def test_an_item_runs_out_after_its_ttl(self):
        self.scene.apply(text("t", ttl=4))
        self.clock.now += 3.9
        self.assertEqual(len(self.scene.items()), 1)
        self.clock.now += 0.2
        self.assertEqual(self.scene.items(), [])

    def test_the_version_changes_only_when_the_picture_would(self):
        self.scene.apply(text("t"))
        before = self.scene.version
        self.clock.now += 2
        self.scene.apply(text("t"))                           # the same thing, sent again to keep it up
        self.assertEqual(self.scene.version, before)
        self.scene.apply(text("t", "changed"))
        self.assertGreater(self.scene.version, before)
        before = self.scene.version
        self.clock.now += 10
        self.scene.items()                                    # it ran out
        self.assertGreater(self.scene.version, before)

    def test_resending_keeps_it_up_past_the_first_ttl(self):
        self.scene.apply(text("t", ttl=4))
        self.clock.now += 3
        self.scene.apply(text("t", ttl=4))
        self.clock.now += 3
        self.assertEqual(len(self.scene.items()), 1)

    def test_next_change_is_the_soonest_expiry(self):
        self.assertIsNone(self.scene.next_change())
        self.scene.apply(text("a", ttl=10))
        self.scene.apply(text("b", ttl=4))
        self.assertAlmostEqual(self.scene.next_change(), 4.0)

    def test_unusable_payloads_are_ignored(self):
        for payload in ({}, {"id": ""}, {"id": "x", "shape": "star"}, {"id": "y", "ttl": "soon"}):
            self.scene.apply(payload)
        self.assertEqual(len(self.scene), 0)

    def test_clear_empties_the_scene(self):
        self.scene.apply(text())
        self.scene.clear()
        self.assertEqual(self.scene.items(), [])


@unittest.skipIf(R is None, "Pillow is not installed")
class RasterTests(unittest.TestCase):
    def draw(self, payloads, width=1280, height=960, ratio=1.0):
        scene = S.Scene(Clock())
        for payload in payloads:
            scene.apply(payload)
        return R.render(scene.items(), width, height, ratio, R.Fonts(R.default_font_path()))

    def test_colors_parse_with_alpha_first(self):
        self.assertEqual(R.parse_color("#ff8040"), (255, 128, 64, 255))
        self.assertEqual(R.parse_color("#80ff8040"), (255, 128, 64, 128))
        self.assertEqual(R.parse_color("white"), (255, 255, 255, 255))
        self.assertIsNone(R.parse_color(""))
        self.assertIsNone(R.parse_color("not a color"))

    def test_a_rectangle_lands_where_its_canvas_position_and_pixel_size_say(self):
        image = self.draw([rect(x=640, y=480, w=100, h=50, color="", fill="#ffff0000")], width=2560, height=1920, ratio=2.0)
        self.assertEqual(image.getpixel((1285, 965))[:3], (255, 0, 0))              # just inside the top left: x 640 of 1280 is 1280 of 2560
        self.assertEqual(image.getpixel((1270, 965))[3], 0)                          # left of it: nothing
        self.assertEqual(image.getpixel((1280 + 199, 960 + 99))[:3], (255, 0, 0))    # 100 x 50 logical pixels at ratio 2 is 200 x 100 device pixels
        self.assertEqual(image.getpixel((1280 + 205, 960 + 50))[3], 0)

    def test_the_canvas_is_stretched_over_the_whole_window(self):
        image = self.draw([rect(x=1260, y=940, w=10, h=10, color="", fill="#ffff0000")], width=1920, height=1080)
        self.assertEqual(image.getpixel((1890 + 5, 1057 + 5))[:3], (255, 0, 0))      # x 1260 of 1280 across 1920 pixels; y 940 of 960 down 1080

    def test_text_draws_pixels_in_its_color_and_nothing_elsewhere(self):
        image = self.draw([text("t", "WNTB", x=100, y=100, color="#00ff00")], width=1280, height=960)
        box = image.getbbox()
        self.assertIsNotNone(box)
        self.assertGreaterEqual(box[0], 99)
        self.assertGreaterEqual(box[1], 99)
        self.assertLess(box[2], 200)
        greens = [p for p in image.crop(box).getdata() if p[3] > 200]
        self.assertTrue(greens and all(p[:3] == (0, 255, 0) for p in greens))

    def test_text_scales_with_display_scaling(self):
        small = self.draw([text("t", "WNTB", x=10, y=10)], ratio=1.0).getbbox()
        large = self.draw([text("t", "WNTB", x=10, y=10)], ratio=2.0).getbbox()
        self.assertGreater(large[2] - large[0], (small[2] - small[0]) * 1.6)

    def test_circles_and_lines_draw(self):
        image = self.draw([{"id": "c", "shape": "circle", "color": "#ff00ff", "fill": "", "x": 640, "y": 480, "radius": 20, "ttl": 4},
                           {"id": "v", "shape": "vect", "color": "#00ffff", "ttl": 4, "vector": [{"x": 100, "y": 100}, {"x": 300, "y": 100, "marker": "cross"}]}])
        self.assertEqual(image.getpixel((640, 480 - 20))[:3], (255, 0, 255))        # the top of the ring
        self.assertEqual(image.getpixel((640, 480))[3], 0)                           # hollow
        self.assertEqual(image.getpixel((200, 100))[:3], (0, 255, 255))             # the line between the points

    def test_an_empty_scene_is_a_transparent_picture(self):
        self.assertIsNone(self.draw([]).getbbox())


if __name__ == "__main__":
    unittest.main()
