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
        from plugin.blueprints_data import BLUEPRINT_ROWS
        from plugin.blueprints_extra import EXTRA_ROWS
        self.assertEqual(len(BLUEPRINT_ROWS), 1176)
        self.assertEqual(len(B.ALL), 1176 + len(EXTRA_ROWS))
        self.assertEqual(len({b.id for b in B.ALL}), len(B.ALL))    # no two blueprints share an id

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


class EdddtAlignmentTests(unittest.TestCase):
    """The corrections and additions made to match ED-DDT's tables (EDDiscovery's data), each pinned."""

    @staticmethod
    def _row(kind, name, grade):
        return next(b for b in B.ALL if (b.type, b.name, b.grade) == (kind, name, grade))

    @staticmethod
    def _counts(blueprint):
        return {i.name: i.count for i in blueprint.ingredients}

    def test_five_corrected_synthesis_recipes(self):
        self.assertEqual(self._counts(self._row("AX Remote Flak Munitions", "+10% Damage Boost", 3))["Weapon Parts"], 1)
        self.assertNotIn("Wreckage Components", self._counts(self._row("AX Remote Flak Munitions", "+10% Damage Boost", 3)))
        self.assertEqual(self._counts(self._row("Chaff Launcher", "100% Refill, +2 Seconds Duration", 3))["Thermic Alloys"], 1)
        flechette = self._counts(self._row("Flechette Launcher Munitions", "+10% Damage Boost", 3))
        self.assertEqual((flechette["Electrochemical Arrays"], flechette["Mechanical Components"]), (5, 9))
        self.assertEqual(self._counts(self._row("Guardian Gauss Cannon Munitions", "None", 1))["Guardian Power Conduit"], 2)
        plasma = self._counts(self._row("Guardian Plasma Charger Munitions", "+30% Damage Boost", 3))
        self.assertEqual((plasma["Phase Alloys"], plasma["Guardian Power Cell"]), (6, 4))

    def test_seven_new_synthesis_rows(self):
        for kind, name, grade in (("Caustic Sinks", "Standard", 2), ("Configurable Small Calibre Munitions", "Basic", 1),
                                  ("Configurable Small Calibre Munitions", "Standard", 2), ("Mining Rig", "Basic", 1),
                                  ("Nanite Munitions", "Basic", 1), ("Seismic Charge Munitions", "Basic", 1),
                                  ("Sub-Surface Displacement Munitions", "Basic", 1)):
            row = self._row(kind, name, grade)
            self.assertEqual(row.engineers, ("Synthesis",))        # the data's "@Synthesis" stand-in, shown without the @
        self.assertEqual(self._counts(self._row("Caustic Sinks", "Standard", 2)),
                         {"Chemical Storage Units": 1, "Galvanising Alloys": 1, "Caustic Shard": 4, "Corrosive Mechanisms": 2})

    def test_the_duplicate_higher_accuracy_rows_are_gone(self):
        self.assertFalse([b for b in B.ALL if b.name.startswith("Higher Accuracy")])
        self.assertEqual(len([b for b in B.ALL if b.name.startswith("Improved Hip Fire Accuracy")]), 3)

    def test_the_colonia_engineers_offer_suit_and_weapon_upgrades(self):
        by_engineer = {}
        for b in B.ALL:
            if b.is_unlock:
                continue
            for engineer in b.engineers:
                by_engineer.setdefault(engineer, []).append(b)
        self.assertEqual({k: len(by_engineer[k]) for k in ("Baltanos", "Eleanor Bresa", "Rosa Dayette", "Yi Shen")},
                         {"Baltanos": 9, "Eleanor Bresa": 7, "Rosa Dayette": 9, "Yi Shen": 6})
        for engineer in ("Baltanos", "Eleanor Bresa", "Rosa Dayette", "Yi Shen"):
            self.assertTrue(all(b.type in ("Suit", "Weapon") for b in by_engineer[engineer]), engineer)
        self.assertIn("Eleanor Bresa", self._row("Suit", "Added melee damage", 0).engineers)

    def test_the_thargoid_war_materials_resolve(self):
        for name in ("Caustic Shard", "Corrosive Mechanisms", "Heat Exposure Specimen", "Phasing Membrane Residue"):
            ingredient = next(i for b in B.ALL for i in b.ingredients if i.name == name)
            self.assertEqual(ingredient.kind, B.SHIP, name)
            self.assertIn(ingredient.key, CATALOG, name)
        self.assertEqual(B.unresolved(), [])


if __name__ == "__main__":
    unittest.main()
