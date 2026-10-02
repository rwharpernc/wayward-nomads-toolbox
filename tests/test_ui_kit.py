"""
Unit tests for the pure parts of plugin/uikit (no display needed).
Run with: python -m unittest discover -s tests
"""

from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from plugin.uikit.shell import WindowShell  # noqa: E402
from plugin.uikit.table import _sort_value  # noqa: E402
from plugin.uikit.widgets import clip  # noqa: E402


class ClipTests(unittest.TestCase):
    def test_short_text_unchanged(self) -> None:
        self.assertEqual(clip("Monazite", 20), "Monazite")

    def test_long_text_capped_with_ellipsis(self) -> None:
        out = clip("x" * 500, 40)
        self.assertEqual(len(out), 40)
        self.assertTrue(out.endswith("…"))


class GeometryTests(unittest.TestCase):
    def test_no_saved_geometry_uses_default(self) -> None:
        self.assertEqual(WindowShell._geometry(None, (1180, 720), (900, 520)), "1180x720")

    def test_garbage_saved_geometry_uses_default(self) -> None:
        self.assertEqual(WindowShell._geometry(lambda: "nonsense", (1180, 720), (900, 520)), "1180x720")

    def test_saved_geometry_kept_with_position(self) -> None:
        self.assertEqual(WindowShell._geometry(lambda: "1300x800+50+60", (1180, 720), (900, 520)),
                         "1300x800+50+60")

    def test_saved_geometry_grown_to_minimum(self) -> None:
        self.assertEqual(WindowShell._geometry(lambda: "400x300+10+10", (1180, 720), (900, 520)),
                         "900x520+10+10")

    def test_negative_monitor_offsets_accepted(self) -> None:
        self.assertEqual(WindowShell._geometry(lambda: "1000x600+-1920+30", (1180, 720), (900, 520)),
                         "1000x600+-1920+30")


class SortValueTests(unittest.TestCase):
    def test_numbers_sort_numerically_not_alphabetically(self) -> None:
        values = ["10", "9", "1,200", "2"]
        self.assertEqual(sorted(values, key=_sort_value), ["2", "9", "10", "1,200"])

    def test_numbers_before_text_and_text_case_insensitive(self) -> None:
        values = ["beta", "Alpha", "7", "—"]
        self.assertEqual(sorted(values, key=_sort_value), ["7", "Alpha", "beta", "—"])

    def test_suffixed_numbers(self) -> None:
        self.assertEqual(sorted(["412 ls", "98 ls", "3,210 ls"], key=_sort_value),
                         ["98 ls", "412 ls", "3,210 ls"])


class NoShadowingTests(unittest.TestCase):
    """A package directory beats a same-named module on import, so `plugin/ui/`
    once silently replaced `plugin/ui.py` (the main panel builder) and WNTB
    failed to load in EDMC with "module 'WNTB.ui' has no attribute
    'create_plugin_app'". The unit tests never import load.py, hence this check."""

    def test_no_package_shares_a_name_with_a_module(self) -> None:
        plugin_dir = os.path.join(os.path.dirname(__file__), "..", "plugin")
        entries = os.listdir(plugin_dir)
        packages = {e for e in entries if os.path.isdir(os.path.join(plugin_dir, e)) and e != "__pycache__"}
        modules = {e[:-3] for e in entries if e.endswith(".py")}
        self.assertEqual(sorted(packages & modules), [])


class NoGlobalTtkTests(unittest.TestCase):
    """ttk themes and styles are application-wide: switching the theme or
    restyling a stock style ("TButton", "Treeview", ...) from the kit would
    recolour EDMC's main window and every other plugin. The kit must stay
    on classic tk widgets and name-scoped option-database skinning."""

    def test_kit_never_touches_global_ttk(self) -> None:
        import glob
        import re
        root = os.path.join(os.path.dirname(__file__), "..", "plugin", "uikit")
        for path in glob.glob(os.path.join(root, "*.py")):
            source = open(path, encoding="utf-8").read()
            code = re.sub(r'""".*?"""', "", source, flags=re.S)  # docstrings may explain the rule
            code = re.sub(r"#.*", "", code)
            for needle in ("theme_use(", "ttk.Style", "style.configure(", "style.map(", "from tkinter import ttk"):
                self.assertNotIn(needle, code, f"{os.path.basename(path)} uses {needle!r}")


if __name__ == "__main__":
    unittest.main()
