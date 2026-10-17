"""The Online lookups page (plugin/settings_online.py) lists real settings, once each, with a place that exists in Settings. It reads the sources, so it needs no EDMC
stand-ins and behaves the same on Windows and Linux."""
from __future__ import annotations

import os
import re
import unittest

ROOT = os.path.join(os.path.dirname(__file__), "..")


def _source(name: str) -> str:
    with open(os.path.join(ROOT, "plugin", name), "r", encoding="utf-8") as handle:
        return handle.read()


def _lookups():
    block = _source("settings_online.py")
    block = block[block.index("LOOKUPS:"):block.index("BUTTON_ONLY")]
    return re.findall(r'\("([^"]+)", "([^"]+)", "(wntb_\w+)", (True|False), "([^"]+)"\)', block)


class OnlineLookupsPageTests(unittest.TestCase):
    def test_every_entry_names_a_setting_the_code_has(self) -> None:
        everything = "".join(_source(name) for name in os.listdir(os.path.join(ROOT, "plugin")) if name.endswith(".py") and name != "settings_online.py")
        entries = _lookups()
        self.assertGreaterEqual(len(entries), 15, "the parse found too little; the test is broken")
        for what, _service, key, _default, _where in entries:
            self.assertIn(f'"{key}"', everything, f"{what}: no setting called {key}")

    def test_no_setting_is_listed_twice(self) -> None:
        keys = [key for _w, _s, key, _d, _p in _lookups()]
        self.assertEqual(len(keys), len(set(keys)))

    def test_every_place_is_a_settings_tab(self) -> None:
        """The 'where to change it' text names a top-level tab or 'Group > Tab' that the Settings build really makes (see tests/prefs_smoke.py's leaf list)."""
        real = {
            "BGS", "Colonization", "Mining", "Missions", "Powerplay", "Trade",
            "Exploration > Exploration Value", "Exploration > Boxel Survey", "Exploration > Nearest place to land",
            "Overlays > System targets", "Overlays > Route", "General > Window", "General > Updates",
        }
        for what, _service, _key, _default, where in _lookups():
            self.assertIn(where, real, f"{what}: {where} is not a Settings page")


if __name__ == "__main__":
    unittest.main()
