"""Per-commander overlay settings (overlay_profile.py): switching commanders swaps the overlay choices in EDMC's config, a
first-seen commander starts from what the config holds, and shared (machine) settings never move. EDMC's config is replaced by
a dictionary that, like the real one, refuses to read a number as text."""
from __future__ import annotations

import os
import sys
import tempfile
import types
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

_stub = types.ModuleType("config")
_stub.appname = "EDMarketConnector"
_stub.config = mock.MagicMock()
sys.modules.setdefault("config", _stub)
sys.modules.setdefault("myNotebook", mock.MagicMock())

from plugin import overlay_profile as P  # noqa: E402

ENABLED = "wntb_expedition_log_overlay"       # an on/off switch (stored as a number)
PLACE = "wntb_overlay_place_expedition_log"   # not a real key: registered below as a text placement
SHARED = "wntb_overlay_backend"               # the overlay's connection: never swapped


class FakeConfig:
    def __init__(self):
        self.values = {}

    def get_str(self, key, default=None):
        value = self.values.get(key, default)
        if isinstance(value, int):
            raise ValueError("not a string")
        return value

    def get_int(self, key, default=0):
        value = self.values.get(key, default)
        if isinstance(value, str):
            raise ValueError("not a number")
        return value

    def set(self, key, value):
        self.values[key] = int(value) if isinstance(value, bool) else value

    def delete(self, key, suppress=False):
        self.values.pop(key, None)


class OverlayProfileTests(unittest.TestCase):
    def setUp(self):
        P.register([PLACE])
        self.dir = tempfile.mkdtemp()
        self.cfg = FakeConfig()
        self.changed = []
        self.profiles = P.OverlayProfiles(self.dir, self.cfg, lambda: self.changed.append(1))

    def reopened(self):
        return P.OverlayProfiles(self.dir, self.cfg, lambda: self.changed.append(1))

    def test_first_commander_keeps_what_the_config_holds(self):
        self.cfg.values.update({ENABLED: 1, PLACE: "left,top,10,20"})
        self.assertFalse(self.profiles.activate("Alpha"))
        self.assertEqual(self.cfg.values[ENABLED], 1)
        self.assertEqual(self.profiles.settings_of("Alpha")[PLACE], "left,top,10,20")

    def test_commanders_keep_their_own_choices(self):
        self.cfg.values.update({ENABLED: 1, PLACE: "left,top,10,20"})
        self.profiles.activate("Alpha")
        self.assertFalse(self.profiles.activate("Beta"))            # new: starts from Alpha's, nothing changes on screen
        self.cfg.values[ENABLED] = 0
        self.cfg.values[PLACE] = "right,bottom,5,5"
        self.assertTrue(self.profiles.activate("Alpha"))
        self.assertEqual((self.cfg.values[ENABLED], self.cfg.values[PLACE]), (1, "left,top,10,20"))
        self.assertTrue(self.profiles.activate("Beta"))
        self.assertEqual((self.cfg.values[ENABLED], self.cfg.values[PLACE]), (0, "right,bottom,5,5"))
        self.assertEqual(len(self.changed), 2)

    def test_commander_names_match_regardless_of_case(self):
        self.profiles.activate("Alpha")
        self.assertFalse(self.profiles.activate("ALPHA"))

    def test_a_key_the_commander_never_set_does_not_leak_from_another(self):
        self.profiles.activate("Alpha")
        self.cfg.values[ENABLED] = 1
        self.profiles.save_current()
        self.profiles.activate("Beta")                              # Beta starts as a copy of Alpha (enabled)
        del self.cfg.values[ENABLED]
        self.profiles.save_current()                                # ... and then has nothing saved for it
        self.profiles.activate("Alpha")
        self.assertEqual(self.cfg.values[ENABLED], 1)
        self.profiles.activate("Beta")
        self.assertNotIn(ENABLED, self.cfg.values)

    def test_machine_settings_are_shared(self):
        self.cfg.values[SHARED] = "builtin"
        self.profiles.activate("Alpha")
        self.profiles.activate("Beta")
        self.cfg.values[SHARED] = "modern"
        self.profiles.activate("Alpha")
        self.assertEqual(self.cfg.values[SHARED], "modern")
        self.assertNotIn(SHARED, self.profiles.settings_of("Alpha"))

    def test_saved_settings_survive_a_restart(self):
        self.profiles.activate("Alpha")
        self.cfg.values[ENABLED] = 1
        self.profiles.save_current("Alpha")
        self.profiles.activate("Beta")
        self.cfg.values[ENABLED] = 0
        self.profiles.save_current("Beta")
        fresh = self.reopened()
        fresh.activate("Alpha")
        self.assertEqual(self.cfg.values[ENABLED], 1)
        fresh.activate("Beta")
        self.assertEqual(self.cfg.values[ENABLED], 0)

    def test_settings_saved_before_anyone_is_known_go_to_the_first_commander(self):
        self.profiles.activate("Alpha")
        self.profiles.save_current()
        fresh = self.reopened()
        self.cfg.values[ENABLED] = 1
        fresh.save_current()                                        # no commander known yet
        fresh.activate("Alpha")
        self.assertEqual(self.cfg.values[ENABLED], 1)
        self.assertEqual(fresh.settings_of("Alpha")[ENABLED], 1)

    def test_nobody_known_means_nothing_to_switch(self):
        self.assertFalse(self.profiles.activate(""))
        self.assertFalse(self.profiles.activate(None))
        self.assertEqual(self.profiles.active, "")

    def test_a_number_is_read_back_as_a_number_and_text_as_text(self):
        self.cfg.values.update({ENABLED: 1, PLACE: "center,top,0,0"})
        found = P.snapshot(self.cfg)
        self.assertEqual(found[ENABLED], 1)
        self.assertIsInstance(found[ENABLED], int)
        self.assertEqual(found[PLACE], "center,top,0,0")

    def test_the_file_is_per_commander_in_shape(self):
        self.cfg.values[ENABLED] = 1
        self.profiles.activate("Alpha")
        raw = self.profiles._store
        self.assertIn("alpha", raw["commanders"])
        self.assertNotIn("alpha", os.listdir(self.dir))             # a name is never a file name


# Settings that mention "enabled" or "overlay" but are deliberately shared, with the reason. A new such setting fails the
# test below until it is either swapped per commander (overlay_profile._FIXED) or listed here.
SHARED_BY_DESIGN = {
    "wntb_overlay_host": "the overlay's connection: a machine fact",
    "wntb_overlay_port": "the overlay's connection: a machine fact",
    "wntb_overlay_backend": "which overlay program draws: a machine fact",
    "wntb_overlay_hide_hotkey": "a keyboard shortcut for this machine",
    "wntb_overlay_editor_size": "the size of the layout picture on the Settings tab",
    "wntb_overlay_reset_v1": "a one-time marker for the install",
    "wntb_overlay_place_mining_waypoint": "an old key, read once to migrate",
    "wntb_overlay_hidden_mining_waypoint": "an old key, read once to migrate",
    "wntb_mining_waypoint_overlay_enabled": "an old key, read once to migrate",
    "wntb_colonisation_overlay_x": "an old position, read once to migrate",
    "wntb_colonisation_overlay_y": "an old position, read once to migrate",
    "wntb_inventory_overlay_x": "an old position, read once to migrate",
    "wntb_inventory_overlay_y": "an old position, read once to migrate",
    "wntb_screenshot_include_overlay": "a screenshot conversion option, not a card",
    "wntb_autohonk_enabled": "not an overlay setting",
    "wntb_canonn_poi_thargoid_enabled": "not an overlay setting",
    "wntb_canonn_poi_guardian_enabled": "not an overlay setting",
    "wntb_bgs_enabled": "not an overlay setting",
    "wntb_bgs_tick_enabled": "not an overlay setting",
    "wntb_codex_completionist_enabled": "not an overlay setting",
    "wntb_exploration_value_enabled": "not an overlay setting",
    "wntb_exploration_value_elw_rarity_enabled": "not an overlay setting",
    "wntb_exploration_value_edsm_upload_enabled": "not an overlay setting",
    "wntb_mining_spansh_hotspot_finder_enabled": "not an overlay setting",
    "wntb_mining_spansh_price_finder_enabled": "not an overlay setting",
    "wntb_mining_edsm_reserve_lookup_enabled": "not an overlay setting",
    "wntb_trade_lookups_enabled": "not an overlay setting",
    "wntb_organic_enabled": "not an overlay setting",
    "wntb_exo_observations_enabled": "not an overlay setting",
    "wntb_rcc_enabled": "not an overlay setting",
}


class EveryOverlaySettingIsClassifiedTests(unittest.TestCase):
    def test_every_overlay_setting_is_swapped_or_shared_on_purpose(self):
        import re
        from plugin import overlay_placement  # noqa: F401  (registers the per-display keys)
        known = set(P.profile_keys()) | set(SHARED_BY_DESIGN)
        root = os.path.join(os.path.dirname(__file__), "..", "plugin")
        missing = set()
        for name in sorted(os.listdir(root)):
            if not name.endswith(".py") or name == "overlay_profile.py":
                continue
            with open(os.path.join(root, name), "r", encoding="utf-8") as handle:
                text = handle.read()
            for key in re.findall(r'"(wntb_\w*(?:enabled|overlay)\w*)"', text):
                if not key.endswith("_") and key not in known:
                    missing.add(f"{name}: {key}")
        self.assertEqual(sorted(missing), [], "a new overlay setting: add it to overlay_profile._FIXED, or to SHARED_BY_DESIGN with a reason")

    def test_nothing_is_both_swapped_and_shared(self):
        self.assertEqual(set(P.profile_keys()) & set(SHARED_BY_DESIGN), set())


if __name__ == "__main__":
    unittest.main()
