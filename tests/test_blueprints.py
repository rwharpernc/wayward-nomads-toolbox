"""Blueprints (blueprints.py and its generated data): the data's shape, that every counted ingredient matches the game's tables, and the
browse and search helpers."""
from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from plugin import blueprints as B  # noqa: E402
from plugin.inventory_names_fdevids import FDEVIDS_DISPLAY_NAMES  # noqa: E402
from plugin.materials import CATALOG  # noqa: E402


class DataTests(unittest.TestCase):
    def test_the_whole_table_is_there(self):
        self.assertEqual(len(B.ALL), 1172)
        self.assertEqual(len({b.id for b in B.ALL}), 1172)    # no two blueprints share an id

    def test_every_blueprint_has_ingredients_with_counts(self):
        for b in B.ALL:
            self.assertTrue(b.ingredients, b.id)
            for i in b.ingredients:
                self.assertGreater(i.count, 0, (b.id, i.name))
            self.assertTrue(0 <= b.grade <= 5, b.id)

    def test_every_counted_ingredient_matches_a_known_material(self):
        self.assertEqual(B.unresolved(), [])

    def test_ship_ingredients_are_in_the_materials_table(self):
        for b in B.ALL:
            for i in b.ingredients:
                if i.kind == B.SHIP:
                    self.assertIn(i.key, CATALOG, (b.id, i.name))

    def test_odyssey_ingredients_are_in_the_inventorys_table(self):
        for b in B.ALL:
            for i in b.ingredients:
                if i.kind == B.ODYSSEY:
                    self.assertIn(i.key, FDEVIDS_DISPLAY_NAMES, (b.id, i.name))

    def test_the_spelling_variants_resolve(self):
        self.assertEqual(B.ship_key("Abnormal Compact Emission Data"), "compactemissionsdata")
        self.assertEqual(B.ship_key("Guardian Wreckage Components"), "guardian_sentinel_wreckagecomponents")
        self.assertEqual(B.ship_key("untypical  shield scans"), "shielddensityreports")
        self.assertEqual(B.ship_key("Iron"), "iron")
        self.assertIsNone(B.ship_key("Unobtainium"))

    def test_the_stand_in_engineers_are_named(self):
        engineers = {e for b in B.ALL for e in b.engineers}
        self.assertNotIn("@Synthesis", engineers)
        self.assertNotIn("@Technology", engineers)
        self.assertIn("Synthesis", engineers)
        self.assertIn("Technology Broker", engineers)

    def test_where_things_are_found_is_kept(self):
        data_ingredient = next(i for b in B.ALL for i in b.ingredients if i.name == "Aberrant Shield Pattern Analysis")
        self.assertIn("Mission reward", data_ingredient.found)
        self.assertTrue(all(not f.startswith("Needed for") for b in B.ALL for i in b.ingredients for f in i.found))


class BrowseTests(unittest.TestCase):
    def test_types_are_sorted_and_include_the_odyssey_ones(self):
        kinds = B.types()
        self.assertEqual(kinds, sorted(kinds, key=str.casefold))
        for expected in ("Frame Shift Drive", "Suit", "Weapon", "Unlock"):
            self.assertIn(expected, kinds)

    def test_grades_of_one_blueprint_are_in_order(self):
        grades = B.grades_for("Frame Shift Drive", "Increased FSD Range")
        self.assertEqual([b.grade for b in grades], [1, 2, 3, 4, 5])
        self.assertEqual(grades[0].title, "Increased FSD Range (grade 1)")

    def test_names_for_a_type(self):
        self.assertIn("Increased FSD Range", B.names_for("Frame Shift Drive"))

    def test_search_needs_every_word(self):
        found = B.search("frame shift range")
        self.assertTrue(found)
        self.assertTrue(all(b.type == "Frame Shift Drive" for b in found[:3]))    # the type and the name both match
        self.assertEqual(B.search("frame shift zzzzzz"), [])

    def test_search_can_be_limited_to_a_type_and_a_count(self):
        found = B.search("", kind="Suit")
        self.assertTrue(found and all(b.type == "Suit" for b in found))
        self.assertEqual(len(B.search("", limit=5)), 5)

    def test_search_finds_by_ingredient_and_by_engineer(self):
        self.assertTrue(any(i.name == "Zinc" for b in B.search("zinc") for i in b.ingredients))
        self.assertTrue(B.search("felicity farseer"))

    def test_an_unknown_id_is_none(self):
        self.assertIsNone(B.get("nope"))
        b = B.ALL[0]
        self.assertIs(B.get(b.id), b)

    def test_an_unlock_is_recognised(self):
        self.assertTrue(next(b for b in B.ALL if b.type == "Unlock").is_unlock)


if __name__ == "__main__":
    unittest.main()
