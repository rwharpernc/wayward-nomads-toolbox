"""The ship engineering planner (ship_plan.py and the journal_blueprints.py mapping): reading a pasted loadout, placing each engineered module in the
blueprint table, what a plan adds up to, and that the generated mapping only ever points at rows the table has."""
from __future__ import annotations

import json
import os
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

from plugin import blueprint_wishlist as W  # noqa: E402
from plugin import blueprints as B  # noqa: E402
from plugin import journal_blueprints as J  # noqa: E402
from plugin import ship_plan as S  # noqa: E402


def module(slot, item, blueprint=None, level=5, effect=None, **engineering):
    entry = {"Slot": slot, "Item": item, "On": True}
    if blueprint:
        entry["Engineering"] = {"Engineer": "Someone", "EngineerID": 300000, "BlueprintName": blueprint, "Level": level, "Quality": 0.5, **engineering}
        if effect:
            entry["Engineering"]["ExperimentalEffect"] = effect
    return entry


FSD = module("FrameShiftDrive", "int_hyperdrive_size5_class5", "FSD_LongRange", 5, "special_fsd_heavy")
BEAM = module("HugeHardpoint1", "hpt_beamlaser_fixed_huge", "Weapon_LongRange", 3, "special_weapon_toughened")
ARMOUR = module("Armour", "asp_armour_grade1", "Armour_HeavyDuty", 2)
PLAIN = module("CargoHatch", "modularcargobaydoor")
LOADOUT = {"event": "Loadout", "Ship": "federation_corvette", "ShipName": "Big Red", "Modules": [FSD, BEAM, ARMOUR, PLAIN]}


class ParseTests(unittest.TestCase):
    def test_a_slef_list_a_slef_object_and_a_bare_loadout_all_read(self):
        for text in (json.dumps([{"header": {"appName": "EDSY"}, "data": LOADOUT}]), json.dumps({"header": {}, "data": LOADOUT}), json.dumps(LOADOUT)):
            builds = S.parse(text)
            self.assertEqual(len(builds), 1)
            self.assertEqual(builds[0].label, "Big Red (Federation Corvette)")
            self.assertEqual(len(builds[0].modules), 4)

    def test_several_ships_in_one_paste(self):
        other = dict(LOADOUT, ShipName="", Ship="asp")
        self.assertEqual([b.label for b in S.parse(json.dumps([{"data": LOADOUT}, {"data": other}]))], ["Big Red (Federation Corvette)", "Asp"])

    def test_text_that_is_not_a_loadout_says_why(self):
        for text, fragment in ((None, "Nothing to read"), ("   ", "Nothing to read"), ("not json", "not JSON"), ("{}", "No ship with modules"),
                               (json.dumps({"Modules": "x"}), "No ship with modules"), ("x" * (S.MAX_TEXT_CHARS + 1), "too much text")):
            with self.assertRaises(S.PlanError) as caught:
                S.parse(text)
            self.assertIn(fragment, str(caught.exception))

    def test_too_many_modules_are_refused(self):
        with self.assertRaises(S.PlanError):
            S.parse(json.dumps({"Modules": [PLAIN] * (S.MAX_MODULES + 1)}))


class ModuleTypeTests(unittest.TestCase):
    def test_items_map_to_the_tables_module_types(self):
        for item, kind in (("hpt_beamlaser_fixed_huge", "Beam Laser"), ("hpt_pulselaserburst_fixed_medium", "Burst Laser"), ("hpt_pulselaser_fixed_small", "Pulse Laser"),
                           ("hpt_multicannon_gimbal_large", "Multi-cannon"), ("hpt_slugshot_fixed_large", "Fragment Cannon"), ("hpt_dumbfiremissilerack_fixed_small", "Missile Rack"),
                           ("hpt_advancedtorppylon_fixed_large", "Torpedo Pylon"), ("int_hyperdrive_size5_class5", "Frame Shift Drive"), ("int_engine_size4_class2", "Thrusters"),
                           ("int_shieldgenerator_size3_class5_strong", "Shield Generator"), ("asp_armour_grade1", "Armour"), ("python_armour_reactive", "Armour"),
                           ("int_detailedsurfacescanner_tiny", "Surface Scanner"), ("int_repairer_size3_class5", "Auto Field-Maintenance Unit"),
                           ("hpt_chafflauncher_tiny", "Chaff Launcher"), ("int_sensors_size5_class2", "Sensors")):
            self.assertEqual(S.module_type(item), kind, item)

    def test_unknown_items_and_non_text_have_no_type(self):
        for item in ("modularcargobaydoor", "int_cargorack_size6_class1", "", None, 5):
            self.assertEqual(S.module_type(item), "" if item != 5 else S.module_type("5"))

    def test_every_module_type_is_a_type_the_table_has(self):
        known = set(B.types())
        for _prefix, kind in S.MODULE_TYPES:
            self.assertIn(kind, known, kind)
        self.assertIn("Armour", known)


class PlanModuleTests(unittest.TestCase):
    def test_a_module_with_no_engineering_is_left_out(self):
        self.assertIsNone(S.plan_module(PLAIN))
        self.assertIsNone(S.plan_module({"Slot": "x", "Item": "y", "Engineering": {}}))
        self.assertIsNone(S.plan_module({"Slot": "x", "Item": "y", "Engineering": "no"}))

    def test_an_fsd_to_level_5_with_an_effect(self):
        planned = S.plan_module(FSD)
        self.assertEqual((planned.module_type, planned.blueprint, planned.status, planned.note), ("Frame Shift Drive", "Increased FSD Range", S.COUNTED, ""))
        self.assertEqual([b.grade for b in planned.grades], [1, 2, 3, 4, 5])
        self.assertEqual((planned.special.name, planned.special.grade), ("Mass Manager", 0))
        self.assertEqual(planned.experimental, "Mass Manager")

    def test_the_level_sets_how_many_grades(self):
        self.assertEqual([b.grade for b in S.plan_module(ARMOUR).grades], [1, 2])
        self.assertEqual([b.grade for b in S.plan_module(BEAM).grades], [1, 2, 3])

    def test_the_same_journal_blueprint_is_a_different_row_per_module_type(self):
        weapon = S.plan_module(module("a", "hpt_pulselaser_fixed_small", "Weapon_LightWeight", 1))
        utility = S.plan_module(module("b", "hpt_chafflauncher_tiny", "Misc_LightWeight", 1))
        self.assertEqual((weapon.blueprint, utility.blueprint), ("Lightweight Mount", "Lightweight"))

    def test_a_pre_engineered_module_has_nothing_to_craft(self):
        planned = S.plan_module(module("a", "int_hyperdrive_size3_class5", "FSD_LongRange", 5, EngineerID=399999))
        self.assertEqual((planned.status, planned.grades), (S.PRE, ()))

    def test_what_the_table_lacks_is_not_counted_with_a_reason(self):
        unknown_item = S.plan_module(module("a", "int_cargorack_size6_class1", "CargoRack_IncreasedCapacity"))
        self.assertEqual(unknown_item.status, S.NOT_COUNTED)
        self.assertIn("no module type", unknown_item.note)
        no_blueprint = S.plan_module(module("a", "int_hyperdrive_size5_class5", "Weapon_LongRange"))
        self.assertEqual(no_blueprint.status, S.NOT_COUNTED)
        self.assertIn("Weapon_LongRange", no_blueprint.note)
        bad_level = S.plan_module(module("a", "int_hyperdrive_size5_class5", "FSD_LongRange", 9))
        self.assertEqual(bad_level.status, S.NOT_COUNTED)
        self.assertEqual(S.plan_module(module("a", "int_hyperdrive_size5_class5", "FSD_LongRange", True)).status, S.NOT_COUNTED)

    def test_an_experimental_effect_the_table_lacks_counts_the_grades_only(self):
        planned = S.plan_module(module("a", "int_hyperdrive_size5_class5", "FSD_LongRange", 3, "special_not_a_real_one"))
        self.assertEqual(planned.status, S.PARTLY)
        self.assertEqual(len(planned.grades), 3)
        self.assertIsNone(planned.special)

    def test_garbage_in_the_engineering_block_never_raises(self):
        for engineering in ({"BlueprintName": "FSD_LongRange", "Level": "5"}, {"BlueprintName": "FSD_LongRange", "Level": None, "Quality": "x"},
                            {"BlueprintName": 7}, {"BlueprintName": "FSD_LongRange", "Level": 5, "Quality": True, "ExperimentalEffect": 3}):
            S.plan_module({"Slot": "s", "Item": "int_hyperdrive_size5_class5", "Engineering": engineering})


class PlanTests(unittest.TestCase):
    def setUp(self):
        self.plan = S.plan(S.parse(json.dumps(LOADOUT))[0])

    def test_only_engineered_modules_are_in_the_plan(self):
        self.assertEqual([m.slot for m in self.plan.modules], ["FrameShiftDrive", "HugeHardpoint1", "Armour"])
        self.assertEqual(self.plan.counted(), 3)

    def test_entries_have_each_grade_at_the_rolls_and_each_effect_once(self):
        entries = dict(self.plan.entries(rolls=2))
        self.assertEqual(entries["Frame Shift Drive|Increased FSD Range|3"], 2)
        self.assertEqual(entries["Frame Shift Drive|Mass Manager|0"], 1)
        self.assertEqual(sum(entries.values()), (5 + 3 + 2) * 2 + 2)       # grades at 2 rolls each, plus an effect each for the FSD and the beam laser

    def test_the_same_blueprint_on_two_modules_is_added_together(self):
        twin = S.plan(S.Build("Ship", "", (BEAM, dict(BEAM, Slot="HugeHardpoint2"))))
        entries = dict(twin.entries())
        self.assertEqual(entries["Beam Laser|Long Range Weapon|1"], 2)
        self.assertEqual(len(entries), 3 + 1)

    def test_rolls_are_checked(self):
        for rolls in (0, S.MAX_ROLLS + 1, True, "2", None, 1.5):
            with self.assertRaises(S.PlanError):
                self.plan.entries(rolls)

    def test_every_entry_is_a_blueprint_in_the_table(self):
        for blueprint_id, crafts in self.plan.entries():
            self.assertIsNotNone(B.get(blueprint_id), blueprint_id)
            self.assertGreaterEqual(crafts, 1)

    def test_the_summary_counts_blueprints_crafts_and_what_was_skipped(self):
        entries = self.plan.entries(1)
        self.assertEqual(self.plan.summary(1), f"3 engineered modules: {len(entries)} blueprints, {sum(c for _i, c in entries)} crafts")
        skipped = S.plan(S.Build("Ship", "", (FSD, module("a", "int_cargorack_size6_class1", "CargoRack_IncreasedCapacity"))))
        self.assertIn("1 not counted", skipped.summary())


class AddToWishlistTests(unittest.TestCase):
    def book(self, folder):
        book = W.WishBook()
        book.load(folder)
        book.set_commander("Bocheaux")
        return book

    def test_the_plan_goes_on_the_wishlist_in_one_step(self):
        plan = S.plan(S.parse(json.dumps(LOADOUT))[0])
        with tempfile.TemporaryDirectory() as folder:
            book = self.book(folder)
            changes = []
            book.add_listener(lambda: changes.append(1))
            self.assertEqual(book.add_many(plan.entries(2)), len(plan.entries(2)))
            self.assertEqual(len(changes), 1)                      # one redraw for the lot
            self.assertEqual(book.get("Frame Shift Drive|Increased FSD Range|5").crafts, 2)
            self.assertEqual(book.get("Frame Shift Drive|Mass Manager|0").crafts, 1)
            book.add_many(plan.entries(2))                         # adding again adds to the crafts
            self.assertEqual(book.get("Frame Shift Drive|Increased FSD Range|5").crafts, 4)

    def test_nothing_is_added_when_a_limit_would_be_broken(self):
        with tempfile.TemporaryDirectory() as folder:
            book = self.book(folder)
            book.add("Armour|Heavy Duty|1", 98)
            with self.assertRaises(W.WishError):
                book.add_many([("Frame Shift Drive|Mass Manager|0", 1), ("Armour|Heavy Duty|1", 2)])        # 98 + 2 passes 99
            self.assertEqual((book.count(), book.get("Armour|Heavy Duty|1").crafts), (1, 98))
            everything = [(b.id, 1) for b in B.ALL[:W.MAX_ITEMS + 1]]
            with self.assertRaises(W.WishError) as caught:
                book.add_many(everything)
            self.assertIn("room", str(caught.exception))
            self.assertEqual(book.count(), 1)
            with self.assertRaises(W.WishError):
                book.add_many([("No|Such|1", 1)])
            with self.assertRaises(W.WishError):
                book.add_many([("Armour|Heavy Duty|2", 0)])

    def test_without_a_commander_it_says_to_log_in(self):
        with tempfile.TemporaryDirectory() as folder:
            book = W.WishBook()
            book.load(folder)
            with self.assertRaises(W.WishError) as caught:
                book.add_many([("Armour|Heavy Duty|1", 1)])
            self.assertIn("Log in", str(caught.exception))

    def test_an_empty_plan_changes_nothing(self):
        with tempfile.TemporaryDirectory() as folder:
            book = self.book(folder)
            self.assertEqual(book.add_many([]), 0)


class MappingTests(unittest.TestCase):
    """journal_blueprints.py is generated; whatever it holds must point at rows the table really has."""

    def test_every_linked_blueprint_has_its_grades_in_the_table(self):
        for journal_name, kinds in J.BLUEPRINT_NAMES.items():
            for kind, name in kinds.items():
                grades = [b.grade for b in B.grades_for(kind, name)]
                self.assertEqual(grades, list(range(1, len(grades) + 1)), (journal_name, kind, name))        # 1 up with no gap
                self.assertGreaterEqual(len(grades), 1, (journal_name, kind, name))

    def test_blueprints_with_a_single_grade_plan_at_level_one(self):
        planned = S.plan_module(module("a", "hpt_chafflauncher_tiny", "Misc_ChaffCapacity", 1))
        self.assertEqual((planned.status, [g.grade for g in planned.grades]), (S.COUNTED, [1]))

    def test_every_linked_effect_is_a_grade_zero_row_for_some_module_type(self):
        for journal_name, names in J.SPECIAL_NAMES.items():
            self.assertTrue(any(b.grade == 0 and b.name in names for b in B.ALL), journal_name)

    def test_the_mapping_is_big_enough_to_be_the_real_one(self):
        self.assertGreaterEqual(len(J.BLUEPRINT_NAMES), 78)
        self.assertGreaterEqual(len(J.SPECIAL_NAMES), 88)

    def test_the_sample_names_the_journal_writes_are_there(self):
        for name in ("FSD_LongRange", "Weapon_LongRange", "Armour_HeavyDuty", "Engine_Dirty", "ShieldGenerator_Optimised", "Misc_LightWeight", "Sensor_Expanded"):
            self.assertIn(name, J.BLUEPRINT_NAMES)
        for effect in ("special_fsd_heavy", "special_weapon_toughened", "special_scramble_spectrum", "special_high_yield_shell", "special_phasing_sequence"):
            self.assertIn(effect, J.SPECIAL_NAMES)


if __name__ == "__main__":
    unittest.main()
