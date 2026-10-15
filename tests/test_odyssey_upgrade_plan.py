"""The Odyssey suit and weapon upgrade planner (odyssey_upgrade_plan.py, odyssey_plan_tab.py): the corrected upgrade rows against real journal events, the
credit formula, what a plan holds, the modification lists, and the tab."""
from __future__ import annotations

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

import tkinter  # noqa: E402,F401
from plugin import blueprint_wishlist as W  # noqa: E402
from plugin import blueprints as B  # noqa: E402
from plugin import odyssey_plan_tab as T  # noqa: E402
from plugin import odyssey_upgrade_plan as O  # noqa: E402

# UpgradeSuit / UpgradeWeapon events from real journals (2025-2026): (table name, type, class reached, credits, materials). Transcribed, not generated.
KINETIC = lambda a, b: (("Weapon Schematic", a), ("Compression-Liquefied Gas", a), ("Manufacturing Instructions", a), ("Tungsten Carbide", b), ("Weapon Component", b))  # noqa: E731
PLASMA = lambda a, b: (("Weapon Schematic", a), ("Ionised Gas", a), ("Manufacturing Instructions", a), ("Chemical Superbase", b), ("Microelectrode", b))  # noqa: E731
SUIT = lambda plate, a, b: (("Suit Schematic", a), ("Health Monitor", a), ("Manufacturing Instructions", a), (plate, b), ("Graphene", b))  # noqa: E731
SEEN = (
    ("Karma AR-50", "Weapon", 3, 1_875_000, KINETIC(2, 5)), ("Karma AR-50", "Weapon", 4, 3_750_000, KINETIC(4, 9)), ("Karma AR-50", "Weapon", 5, 6_250_000, KINETIC(5, 12)),
    ("Karma L-6", "Weapon", 2, 700_000, KINETIC(1, 2)), ("Karma C-44", "Weapon", 3, 1_125_000, KINETIC(2, 5)),
    ("Manticore Tormentor", "Weapon", 3, 750_000, PLASMA(2, 5)), ("Manticore Tormentor", "Weapon", 4, 1_500_000, PLASMA(4, 9)),
    ("Manticore Tormentor", "Weapon", 5, 2_500_000, PLASMA(5, 12)), ("Manticore Executioner", "Weapon", 4, 5_250_000, PLASMA(4, 9)),
    ("Maverick", "Suit", 4, 4_500_000, SUIT("Carbon Fibre Plating", 4, 9)), ("Maverick", "Suit", 5, 7_500_000, SUIT("Carbon Fibre Plating", 5, 12)),
    ("Artemis", "Suit", 4, 4_500_000, SUIT("Aerogel", 4, 9)), ("Dominator", "Suit", 2, 600_000, SUIT("Titanium Plating", 1, 2)),
)


def step(kind, name, grade):
    return next(b for b in B.ALL if (b.type, b.name, b.grade) == (kind, name, grade))


class UpgradeRowsTests(unittest.TestCase):
    def test_every_row_matches_what_the_game_charged(self):
        for name, kind, grade, _credits, materials in SEEN:
            row = step(kind, name, grade)
            self.assertEqual(tuple((i.name, i.count) for i in row.ingredients), materials, (name, grade))

    def test_the_counts_are_the_same_for_every_item_and_class(self):
        for item in O.GEAR:
            for grade, first, second in ((2, 1, 2), (3, 2, 5), (4, 4, 9), (5, 5, 12)):
                counts = [i.count for i in step(item.kind, item.name, grade).ingredients]
                self.assertEqual(sorted(set(counts)), sorted({first, second}), (item.label, grade))
                self.assertEqual(len(counts), 5, (item.label, grade))

    def test_a_suit_no_longer_needs_a_power_regulator_and_the_opressor_typo_is_gone(self):
        self.assertFalse([b for b in B.ALL if b.type == "Suit" and any(i.name == "Power Regulator" for i in b.ingredients) and "Merchant" in b.engineers])
        self.assertFalse([b for b in B.ALL if b.name == "Manticore Opressor"])
        self.assertEqual([b.grade for b in B.grades_for("Weapon", "Manticore Oppressor")], [2, 3, 4, 5])

    def test_every_ingredient_of_every_upgrade_is_a_counted_material(self):
        self.assertEqual(B.unresolved(), [])


class CreditTests(unittest.TestCase):
    def test_the_formula_gives_every_cost_the_game_charged(self):
        for name, kind, grade, credits, _materials in SEEN:
            item = O.gear(f"{name} suit" if kind == "Suit" else name)
            self.assertEqual(O.credits_to(item, grade - 1, grade), credits, (name, grade))

    def test_several_classes_add_up_and_an_unseen_item_is_unknown(self):
        self.assertEqual(O.credits_to(O.gear("Karma AR-50"), 1, 5), 12_500_000)
        self.assertEqual(O.credits_to(O.gear("Karma AR-50"), 3, 3), 0)
        self.assertIsNone(O.credits_to(O.gear("TK Zenith"), 1, 2))

    def test_the_factors_are_one_three_six_ten(self):
        self.assertEqual(O.CLASS_FACTOR, {2: 1, 3: 3, 4: 6, 5: 10})


class GearTests(unittest.TestCase):
    def test_the_items_the_table_upgrades(self):
        self.assertEqual(O.labels(), ["Artemis suit", "Dominator suit", "Maverick suit", "Karma AR-50", "Karma C-44", "Karma L-6", "Karma P-15", "Manticore Executioner",
                                      "Manticore Intimidator", "Manticore Oppressor", "Manticore Tormentor", "TK Aphelion", "TK Eclipse", "TK Zenith"])
        self.assertEqual({g.family for g in O.GEAR if g.kind == "Weapon"}, {"Kinematic kinetic", "Manticore plasma", "Takada laser"})
        self.assertEqual({g.family for g in O.GEAR if g.kind == "Suit"}, {""})
        self.assertIsNone(O.gear("Flight Suit"))

    def test_which_items_have_been_confirmed(self):
        self.assertEqual({g.name for g in O.GEAR if g.confirmed}, set(O.CREDIT_UNIT))
        self.assertEqual(len(O.CREDIT_UNIT), 8)

    def test_modifications_follow_the_item(self):
        suit = O.modifications_for(O.gear("Maverick suit"))
        self.assertIn("Extra backpack capacity", suit)
        self.assertNotIn("Scope", suit)
        kinetic = O.modifications_for(O.gear("Karma AR-50"))
        self.assertIn("Greater range (Kinematic kinetic)", kinetic)
        self.assertNotIn("Greater range (Takada laser)", kinetic)
        self.assertNotIn("Karma AR-50", kinetic)                     # an upgrade row is not a modification
        self.assertIn("Scope", kinetic)
        self.assertIn("Greater range (Takada laser)", O.modifications_for(O.gear("TK Aphelion")))
        for item in O.GEAR:
            self.assertEqual(len(O.modifications_for(item)), len(set(O.modifications_for(item))))


class PlanTests(unittest.TestCase):
    def test_a_full_upgrade_with_two_modifications(self):
        plan = O.plan(O.gear("Karma AR-50"), 1, 5, ["Scope", "Greater range (Kinematic kinetic)"])
        self.assertEqual([b.grade for b in plan.steps], [2, 3, 4, 5])
        self.assertEqual(plan.credits, 12_500_000)
        self.assertEqual(plan.entries(), [("Weapon|Karma AR-50|2", 1), ("Weapon|Karma AR-50|3", 1), ("Weapon|Karma AR-50|4", 1), ("Weapon|Karma AR-50|5", 1),
                                          ("Weapon|Scope|0", 1), ("Weapon|Greater range (Kinematic kinetic)|0", 1)])
        self.assertEqual(plan.notes(), ["Modification fees (the engineer's credits) are not in the table and not counted."])

    def test_a_partial_upgrade_and_no_upgrade(self):
        plan = O.plan(O.gear("Maverick suit"), 3, 4)
        self.assertEqual(([b.grade for b in plan.steps], plan.credits, plan.notes()), ([4], 4_500_000, []))
        none = O.plan(O.gear("Maverick suit"), 4, 4, ["Night vision"])
        self.assertEqual((none.steps, none.credits, none.entries()), ((), 0, [("Suit|Night vision|0", 1)]))

    def test_an_unconfirmed_item_says_what_is_missing(self):
        plan = O.plan(O.gear("TK Zenith"), 1, 3)
        self.assertIsNone(plan.credits)
        notes = " ".join(plan.notes())
        self.assertIn("credit cost of TK Zenith has not been recorded", notes)
        self.assertIn("not been confirmed", notes)

    def test_choices_that_cannot_be_planned_say_why(self):
        item = O.gear("Karma AR-50")
        for args, fragment in (((item, 4, 2), "cannot be lower"), ((item, 0, 3), "1 to 5"), ((item, 1, 6), "1 to 5"), ((item, True, 3), "1 to 5"),
                               ((item, 1, 3, ["Scope"] * 2), "once"), ((item, 1, 3, ["Scope", "Stability", "Magazine size", "Reload speed", "Audio Masking"]), "at most 4"),
                               ((item, 1, 3, ["Greater range (Takada laser)"]), "not offered")):
            with self.assertRaises(O.OdysseyPlanError) as caught:
                O.plan(*args)
            self.assertIn(fragment, str(caught.exception))

    def test_every_planned_blueprint_is_in_the_table(self):
        for item in O.GEAR:
            plan = O.plan(item, 1, 5, O.modifications_for(item)[:4])
            for blueprint_id, _crafts in plan.entries():
                self.assertIsNotNone(B.get(blueprint_id), blueprint_id)


class WishlistTests(unittest.TestCase):
    def test_a_plan_goes_on_the_wishlist_in_one_step(self):
        with tempfile.TemporaryDirectory() as folder:
            book = W.WishBook()
            book.load(folder)
            book.set_commander("Bocheaux")
            plan = O.plan(O.gear("Maverick suit"), 1, 5, ["Night vision"])
            self.assertEqual(book.add_many(plan.entries()), 5)
            self.assertEqual(book.get("Suit|Maverick|5").crafts, 1)
            shopping = B.get("Suit|Maverick|5")
            self.assertIn(("Carbon Fibre Plating", 12), [(i.name, i.count) for i in shopping.ingredients])


class TabHelperTests(unittest.TestCase):
    def test_rows_and_summary(self):
        plan = O.plan(O.gear("Karma AR-50"), 2, 4, ["Scope"])
        rows = T.rows(plan)
        self.assertEqual(rows[0], ("Class 2 to 3", "2 Weapon Schematic, 2 Compression-Liquefied Gas, 2 Manufacturing Instructions, 5 Tungsten Carbide, 5 Weapon Component", "1,875,000"))
        self.assertEqual(rows[1][0], "Class 3 to 4")
        self.assertEqual(rows[2][0], "Modification: Scope")
        self.assertEqual(rows[2][2], "engineer's fee")
        self.assertEqual(T.summary(plan), "Karma AR-50, class 2 to 4: 5,625,000 credits; 1 modification")

    def test_an_unrecorded_item_and_an_empty_plan(self):
        rows = T.rows(O.plan(O.gear("TK Zenith"), 1, 2))
        self.assertEqual(rows[0][2], "not recorded")
        self.assertIn("credits not recorded", T.summary(O.plan(O.gear("TK Zenith"), 1, 2)))
        self.assertIn("Nothing to plan", T.summary(O.plan(O.gear("TK Zenith"), 2, 2)))


class TabWindowTests(unittest.TestCase):
    def test_the_tab_follows_its_choices(self):
        import tkinter as tk
        try:
            root = tk.Tk()
        except tk.TclError:
            self.skipTest("Tk has no display here")
        self.addCleanup(root.destroy)
        with tempfile.TemporaryDirectory() as folder:
            book = W.WishBook()
            book.load(folder)
            book.set_commander("Bocheaux")
            said = []
            tab = T.UpgradePlanTab(tk.Frame(root), book, said.append)
            self.assertEqual(len(tab._table), 4)                              # the first item, class 1 to 5
            tab._current.set("3")
            tab._target.set("3")
            tab.refresh()
            self.assertEqual(len(tab._table), 0)
            tab.add_to_wishlist()
            self.assertIn("Nothing to add", said[-1])
            tab._gear.set("Karma AR-50")
            tab._gear_changed()
            tab._current.set("4")
            tab._class_changed()
            self.assertEqual(tab._target.get(), "4")                         # moving "now" past "wanted" drags it along
            tab._target.set("5")
            tab._class_changed(target_chosen=True)
            tab._mod_vars[0].set("Scope")
            tab._mod_vars[1].set("Greater range (Takada laser)")             # not offered for a kinetic weapon
            tab.refresh()
            self.assertIn("not offered", tab._summary.cget("text"))
            tab._mod_vars[1].set("Stability")
            tab.refresh()
            self.assertEqual(len(tab._table), 3)                              # class 5 and two modifications
            tab.add_to_wishlist()
            self.assertEqual(book.count(), 3)
            self.assertIn("Put 3 entries for Karma AR-50", said[-1])
            tab._gear.set("Maverick suit")
            tab._gear_changed()
            self.assertEqual(tab.chosen_mods(), [])                           # the old choices do not fit a suit and are dropped


if __name__ == "__main__":
    unittest.main()
