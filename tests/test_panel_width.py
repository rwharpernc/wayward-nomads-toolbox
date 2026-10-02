"""
Guards for the "main window must not change width when you switch modes" rule
(docs/TECHNICAL.md section 5).

These are source-level checks, because the real thing needs EDMC and a
display: they stop the two known causes from coming back.

Run with: python -m unittest discover -s tests
"""

from __future__ import annotations

import os
import re
import unittest

PLUGIN = os.path.join(os.path.dirname(__file__), "..", "plugin")


def _source(name: str) -> str:
    with open(os.path.join(PLUGIN, name), encoding="utf-8") as handle:
        return handle.read()


class ModePanelWidthTests(unittest.TestCase):
    def test_every_mode_lives_in_a_width_pinned_holder(self) -> None:
        source = _source("ui.py")
        self.assertIn("_mode_holder.grid_propagate(False)", source)
        # mode frames are children of the holder, never gridded straight into the panel
        self.assertIn("mode_frame = tk.Frame(_mode_holder)", source)

    def test_scrolling_panels_do_not_ask_for_a_default_canvas_width(self) -> None:
        # A bare tk.Canvas requests 10 cm (~378 px) of width, which is what made Mining and
        # Missions wider than the other modes.
        for name in ("mining_panel.py", "missions_ui.py"):
            canvases = re.findall(r"tk\.Canvas\(parent,[^)]*\)", _source(name), flags=re.S)
            self.assertTrue(canvases, f"no main-panel canvas found in {name}")
            for call in canvases:
                self.assertIn("width=1", call, f"{name}: a main-panel Canvas must set width=1")


if __name__ == "__main__":
    unittest.main()
