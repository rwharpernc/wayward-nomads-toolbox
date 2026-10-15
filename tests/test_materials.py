"""Engineering materials (materials.py): the table, the login list, every event that changes a count, the grade limits, EDMC's running totals,
unknown materials, saving per commander and a damaged file."""
from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from plugin import materials as M  # noqa: E402


class Clock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now


def make(folder, cmdr="Bocheaux", clock=None):
    book = M.MaterialBook(clock=clock or Clock())
    book.load(folder)
    book.set_commander(cmdr)
    return book


LOGIN = {"event": "Materials",
         "Raw": [{"Name": "iron", "Name_Localised": "Iron", "Count": 120}, {"Name": "tin", "Count": 12}],
         "Manufactured": [{"Name": "gridresistors", "Count": 40}],
         "Encoded": [{"Name": "legacyfirmware", "Count": 7}]}


class TableTests(unittest.TestCase):
    def test_every_material_has_a_known_type_and_grade(self):
        self.assertEqual(len(M.CATALOG), 146)
        for material in M.CATALOG.values():
            self.assertIn(material.type, M.TYPES)
            self.assertIn(material.grade, M.CAPS)
            self.assertEqual(material.key, material.key.lower())

    def test_known_materials(self):
        iron = M.CATALOG["iron"]
        self.assertEqual((iron.name, iron.type, iron.grade, iron.cap), ("Iron", "Raw", 1, 300))
        self.assertEqual(M.CATALOG["gridresistors"].type, "Manufactured")
        self.assertEqual(M.CATALOG["legacyfirmware"].type, "Encoded")

    def test_the_caps_follow_the_grade(self):
        self.assertEqual([M.CAPS[g] for g in (1, 2, 3, 4, 5)], [300, 250, 200, 150, 100])

    def test_key_for_reduces_tokens(self):
        self.assertEqual(M.key_for("Iron"), "iron")
        self.assertEqual(M.key_for("$iron_name;"), "iron")
        self.assertEqual(M.key_for(None), "")


class LoginTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.book = make(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_the_login_list_sets_every_count(self):
        self.assertTrue(self.book.apply_event(LOGIN))
        self.assertEqual(self.book.count_of("iron"), 120)
        self.assertEqual(self.book.count_of("Gridresistors"), 40)
        self.assertEqual(self.book.totals(), {"Raw": 132, "Manufactured": 40, "Encoded": 7})
        self.assertTrue(self.book.has_counts)

    def test_a_later_list_replaces_not_adds(self):
        self.book.apply_event(LOGIN)
        self.book.apply_event({"event": "Materials", "Raw": [{"Name": "iron", "Count": 5}], "Manufactured": [], "Encoded": []})
        self.assertEqual(self.book.count_of("iron"), 5)
        self.assertEqual(self.book.count_of("tin"), 0)
        self.assertEqual(self.book.totals(), {"Raw": 5, "Manufactured": 0, "Encoded": 0})

    def test_held_is_sorted_by_type_grade_and_name(self):
        self.book.apply_event(LOGIN)
        self.assertEqual([h.material.key for h in self.book.held()], ["iron", "tin", "gridresistors", "legacyfirmware"])

    def test_nothing_is_taken_before_a_commander_is_known(self):
        self.assertFalse(M.MaterialBook().apply_event(LOGIN))


class ChangeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.book = make(self.tmp.name)
        self.book.apply_event(LOGIN)

    def tearDown(self):
        self.tmp.cleanup()

    def test_collecting_adds_and_is_remembered_as_the_last_change(self):
        self.assertTrue(self.book.apply_event({"event": "MaterialCollected", "Category": "Raw", "Name": "iron", "Count": 3}))
        self.assertEqual(self.book.count_of("iron"), 123)
        self.assertEqual(self.book.last, M.Change("Iron", 3, 123))

    def test_discarding_takes_away_and_never_goes_below_nothing(self):
        self.book.apply_event({"event": "MaterialDiscarded", "Category": "Raw", "Name": "tin", "Count": 5})
        self.assertEqual(self.book.count_of("tin"), 7)
        self.book.apply_event({"event": "MaterialDiscarded", "Category": "Raw", "Name": "tin", "Count": 500})
        self.assertEqual(self.book.count_of("tin"), 0)
        self.assertNotIn("tin", [h.material.key for h in self.book.held()])

    def test_a_trade_takes_what_was_paid_and_adds_what_was_received(self):
        self.book.apply_event({"event": "MaterialTrade", "Paid": {"Material": "iron", "Category": "Raw", "Quantity": 6},
                               "Received": {"Material": "tin", "Category": "Raw", "Quantity": 2}})
        self.assertEqual((self.book.count_of("iron"), self.book.count_of("tin")), (114, 14))

    def test_synthesis_uses_materials_found_by_name_alone(self):
        self.book.apply_event({"event": "Synthesis", "Name": "Basic", "Materials": [{"Name": "iron", "Count": 2}, {"Name": "gridresistors", "Count": 1}]})
        self.assertEqual((self.book.count_of("iron"), self.book.count_of("gridresistors")), (118, 39))

    def test_an_engineer_craft_takes_its_ingredients_in_either_shape(self):
        self.book.apply_event({"event": "EngineerCraft", "Ingredients": [{"Name": "iron", "Count": 1}]})
        self.assertEqual(self.book.count_of("iron"), 119)
        self.book.apply_event({"event": "EngineerCraft", "Ingredients": {"iron": 4}})
        self.assertEqual(self.book.count_of("iron"), 115)

    def test_the_technology_broker_takes_its_materials(self):
        self.book.apply_event({"event": "TechnologyBroker", "Materials": [{"Name": "legacyfirmware", "Count": 3, "Category": "Encoded"}]})
        self.assertEqual(self.book.count_of("legacyfirmware"), 4)

    def test_a_mission_reward_adds(self):
        self.book.apply_event({"event": "MissionCompleted", "MaterialsReward": [{"Name": "tin", "Category": "Raw", "Count": 3}]})
        self.assertEqual(self.book.count_of("tin"), 15)

    def test_a_mission_reward_in_the_real_journal_shape_counts_materials_and_skips_on_foot_items(self):
        # Real rewards write the category as $MICRORESOURCE_CATEGORY_<kind>; and can include Odyssey items, which are not engineering materials.
        self.book.apply_event({"event": "MissionCompleted", "MaterialsReward": [
            {"Name": "Polonium", "Category": "$MICRORESOURCE_CATEGORY_Elements;", "Count": 3},
            {"Name": "FSDTelemetry", "Category": "$MICRORESOURCE_CATEGORY_Encoded;", "Count": 12},
            {"Name": "WeaponSchematic", "Category": "$MICRORESOURCE_CATEGORY_Item;", "Count": 7},
            {"Name": "WeaponComponent", "Category": "$MICRORESOURCE_CATEGORY_Component;", "Count": 12},
            {"Name": "ManufacturingInstructions", "Category": "$MICRORESOURCE_CATEGORY_Data;", "Count": 13}]})
        self.assertEqual(self.book.count_of("polonium"), 3)
        self.assertEqual(self.book.count_of("fsdtelemetry"), 12)
        for name in ("weaponschematic", "weaponcomponent", "manufacturinginstructions"):
            self.assertEqual(self.book.count_of(name), 0)

    def test_handing_a_material_to_an_engineer_takes_it(self):
        self.book.apply_event({"event": "EngineerContribution", "Type": "Material", "Material": "iron", "Quantity": 10, "TotalQuantity": 10})
        self.assertEqual(self.book.count_of("iron"), 110)
        self.book.apply_event({"event": "EngineerContribution", "Type": "Commodity", "Commodity": "gold", "Quantity": 10})
        self.assertEqual(self.book.count_of("iron"), 110)

    def test_a_count_is_never_taken_above_the_grade_limit(self):
        self.book.apply_event({"event": "MaterialCollected", "Category": "Raw", "Name": "iron", "Count": 1000})
        self.assertEqual(self.book.count_of("iron"), 300)
        self.assertEqual([h.material.key for h in self.book.full()], ["iron"])
        self.assertEqual(self.book.held()[0].room, 0)
        self.assertEqual(self.book.held()[1].room, M.CAPS[M.CATALOG["tin"].grade] - 12)   # tin is grade 3

    def test_a_damaged_event_is_ignored(self):
        before = self.book.totals()
        for bad in ({"event": "MaterialCollected"}, {"event": "MaterialCollected", "Name": "iron", "Count": "x"},
                    {"event": "Synthesis", "Materials": "nope"}, {"event": "MaterialTrade", "Paid": 5, "Received": None},
                    {"event": "EngineerCraft", "Ingredients": [None, 3]}, {"event": "Music"}):
            self.assertFalse(self.book.apply_event(bad), bad)
        self.assertEqual(self.book.totals(), before)

    def test_an_event_that_changes_nothing_says_so(self):
        self.assertFalse(self.book.apply_event({"event": "MaterialCollected", "Category": "Raw", "Name": "iron", "Count": 0}))


class UnknownTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.book = make(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_a_material_the_table_does_not_know_is_still_tracked(self):
        self.book.apply_event({"event": "MaterialCollected", "Category": "Encoded", "Name": "newthing", "Name_Localised": "Brand New Thing", "Count": 4})
        held = self.book.held()[0]
        self.assertEqual((held.material.name, held.material.type, held.material.grade, held.count), ("Brand New Thing", "Encoded", 0, 4))
        self.assertFalse(held.is_full)
        self.assertEqual(self.book.totals()["Encoded"], 4)

    def test_it_survives_a_restart_with_its_name(self):
        self.book.apply_event({"event": "MaterialCollected", "Category": "Encoded", "Name": "newthing", "Name_Localised": "Brand New Thing", "Count": 4})
        self.book.flush()
        again = make(self.tmp.name)
        self.assertEqual(again.held()[0].material.name, "Brand New Thing")

    def test_only_so_many_unknown_materials_are_tracked(self):
        for n in range(M.MAX_UNKNOWN + 20):
            self.book.apply_event({"event": "MaterialCollected", "Category": "Raw", "Name": f"unk{n}", "Count": 1})
        self.assertEqual(len(self.book.held()), M.MAX_UNKNOWN)

    def test_a_very_long_name_is_cut(self):
        self.book.apply_event({"event": "MaterialCollected", "Category": "Raw", "Name": "z", "Name_Localised": "N" * 500, "Count": 1})
        self.assertEqual(len(self.book.held()[0].material.name), M.MAX_NAME)


class StateTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.book = make(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_edmcs_totals_are_taken_once_and_the_event_is_not_counted_twice(self):
        state = {"Raw": {"iron": 50}, "Manufactured": {"gridresistors": 9}, "Encoded": {}}
        self.book.apply_event({"event": "MaterialCollected", "Category": "Raw", "Name": "iron", "Count": 3}, state)
        self.assertEqual(self.book.count_of("iron"), 50)        # EDMC's total already holds the 3
        self.assertEqual(self.book.count_of("gridresistors"), 9)
        self.assertTrue(self.book.has_counts)
        self.book.apply_event({"event": "MaterialCollected", "Category": "Raw", "Name": "iron", "Count": 3}, {"Raw": {"iron": 999}})
        self.assertEqual(self.book.count_of("iron"), 53)        # from then on the events are followed

    def test_empty_totals_change_nothing(self):
        self.assertFalse(self.book.apply_event({"event": "Music"}, {"Raw": {}, "Manufactured": {}, "Encoded": {}}))
        self.assertFalse(self.book.has_counts)

    def test_damaged_totals_are_ignored(self):
        self.assertFalse(self.book.apply_event({"event": "Music"}, {"Raw": "x", "Manufactured": None}))

    def test_no_state_at_all_is_fine(self):
        self.book.apply_event({"event": "MaterialCollected", "Category": "Raw", "Name": "iron", "Count": 3}, None)
        self.assertEqual(self.book.count_of("iron"), 3)


class SavingTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.clock = Clock()

    def tearDown(self):
        self.tmp.cleanup()

    def path(self):
        return os.path.join(self.tmp.name, M.STATE_FILENAME)

    def test_the_login_list_is_saved_at_once(self):
        book = make(self.tmp.name, clock=self.clock)
        book.apply_event(LOGIN)
        self.assertEqual(make(self.tmp.name).count_of("iron"), 120)

    def test_a_burst_of_events_is_written_once_in_a_while_and_flush_writes_the_rest(self):
        book = make(self.tmp.name, clock=self.clock)
        book.apply_event(LOGIN)
        for _ in range(5):
            book.apply_event({"event": "MaterialCollected", "Category": "Raw", "Name": "iron", "Count": 1})
        self.assertEqual(make(self.tmp.name).count_of("iron"), 120)    # still waiting
        self.clock.now += M.SAVE_EVERY_S + 1
        book.apply_event({"event": "MaterialCollected", "Category": "Raw", "Name": "iron", "Count": 1})
        self.assertEqual(make(self.tmp.name).count_of("iron"), 126)
        book.apply_event({"event": "MaterialCollected", "Category": "Raw", "Name": "iron", "Count": 1})
        book.flush()
        self.assertEqual(make(self.tmp.name).count_of("iron"), 127)

    def test_changing_commander_writes_the_waiting_change_first(self):
        book = make(self.tmp.name, clock=self.clock)
        book.apply_event(LOGIN)
        book.apply_event({"event": "MaterialCollected", "Category": "Raw", "Name": "iron", "Count": 2})
        book.set_commander("Other Cmdr")
        self.assertEqual(book.held(), [])
        self.assertEqual(make(self.tmp.name).count_of("iron"), 122)

    def test_commanders_do_not_see_each_others_materials(self):
        make(self.tmp.name, "Bocheaux", clock=self.clock).apply_event(LOGIN)
        self.assertEqual(make(self.tmp.name, "Someone Else").held(), [])
        self.assertEqual(make(self.tmp.name, "BOCHEAUX").count_of("iron"), 120)

    def test_no_commander_name_is_in_a_file_name(self):
        make(self.tmp.name, clock=self.clock).apply_event(LOGIN)
        self.assertEqual(os.listdir(self.tmp.name), [M.STATE_FILENAME])

    def test_a_damaged_file_gives_empty_counts(self):
        with open(self.path(), "w", encoding="utf-8") as handle:
            handle.write("{not json")
        self.assertEqual(make(self.tmp.name).held(), [])

    def test_damaged_entries_are_dropped_and_the_rest_kept(self):
        make(self.tmp.name, clock=self.clock).apply_event(LOGIN)
        with open(self.path(), encoding="utf-8") as handle:
            raw = json.load(handle)
        counts = raw["commanders"]["bocheaux"]["data"]["counts"]
        counts.update({"nosuchmaterial": 5, "tin": "x", "carbon": -3, "lead": 99999})
        with open(self.path(), "w", encoding="utf-8") as handle:
            json.dump(raw, handle)
        again = make(self.tmp.name)
        self.assertEqual(again.count_of("iron"), 120)
        self.assertEqual((again.count_of("nosuchmaterial"), again.count_of("tin"), again.count_of("carbon")), (0, 0, 0))
        self.assertEqual(again.count_of("lead"), 300)             # cut to the limit


if __name__ == "__main__":
    unittest.main()
