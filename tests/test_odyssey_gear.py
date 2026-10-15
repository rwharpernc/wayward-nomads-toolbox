"""The gear the commander owns, read from the journal (odyssey_gear.py), and the Upgrade planner using it. The loadout events follow real journals (the fields are
the game's; the ids and names are made up)."""
from __future__ import annotations

import json
import os
import shutil
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
from plugin import odyssey_gear as G  # noqa: E402
from plugin import odyssey_plan_tab as T  # noqa: E402
from plugin import odyssey_upgrade_plan as O  # noqa: E402


def weapon(module, cls, mods=(), module_id=1):
    return {"SlotName": "PrimaryWeapon1", "SuitModuleID": module_id, "ModuleName": module, "Class": cls, "WeaponMods": list(mods)}


def loadout(suit="utilitysuit_class4", suit_id=10, mods=(), name="Mav 3", modules=(), event="SuitLoadout"):
    return {"timestamp": "2026-10-15T10:00:00Z", "event": event, "SuitID": suit_id, "SuitName": suit, "SuitMods": list(mods), "LoadoutID": 1, "LoadoutName": name,
            "Modules": list(modules)}


class FromLoadoutsTests(unittest.TestCase):
    def test_a_suit_and_its_weapons(self):
        owned = G.from_loadouts([loadout(mods=["suit_nightvision", "suit_increasedo2capacity"], modules=[
            weapon("wpn_m_assaultrifle_kinetic_fauto", 3, ["weapon_range", "weapon_scope"]),
            weapon("wpn_s_pistol_plasma_charged", 5, [], 2)])])
        self.assertEqual([g.label for g in owned], ["Maverick suit, class 4 (Mav 3)", "Karma AR-50, class 3 (Mav 3)", "Manticore Tormentor, class 5 (Mav 3)"])
        suit, rifle, pistol = owned
        self.assertEqual(suit.fitted, ("Night vision", "Increased air reserves"))
        self.assertEqual(rifle.fitted, ("Greater range (Kinematic kinetic)", "Scope"))
        self.assertEqual(pistol.fitted, ())

    def test_every_suit_and_weapon_the_planner_upgrades_is_recognised(self):
        modules = [weapon(name, 2, module_id=i) for i, name in enumerate(G.WEAPONS)]
        entries = [loadout(f"{kind}_class2", suit_id=i, modules=modules if i == 0 else []) for i, kind in enumerate(G.SUITS)]
        owned = G.from_loadouts(entries)
        self.assertEqual({g.item.name for g in owned}, {"Maverick", "Artemis", "Dominator", *G.WEAPONS.values()})
        self.assertEqual({g.item.name for g in owned if g.item.kind == "Weapon"}, {g.name for g in O.GEAR if g.kind == "Weapon"})

    def test_every_mod_id_maps_to_a_name_the_planner_offers_for_that_item(self):
        for mod_id, name in G.SUIT_MODS.items():
            self.assertIn(name, O.modifications_for(O.gear("Maverick suit")), mod_id)
        for family, example in (("Kinematic kinetic", "Karma AR-50"), ("Manticore plasma", "Manticore Tormentor"), ("Takada laser", "TK Zenith")):
            offered = O.modifications_for(O.gear(example))
            for mod_id, name in G.WEAPON_MODS.items():
                self.assertIn(name.format(family=family), offered, (mod_id, family))

    def test_the_newest_sighting_wins_and_an_upgrade_after_it_raises_the_class(self):
        first = loadout(suit="utilitysuit_class3", modules=[weapon("wpn_m_assaultrifle_kinetic_fauto", 2)])
        later = loadout(suit="utilitysuit_class3", modules=[weapon("wpn_m_assaultrifle_kinetic_fauto", 3, ["weapon_scope"])], event="SwitchSuitLoadout")
        upgrade_suit = {"event": "UpgradeSuit", "SuitID": 10, "Class": 4, "Cost": 1}
        upgrade_gun = {"event": "UpgradeWeapon", "SuitModuleID": 1, "Class": 4, "Cost": 1}
        owned = {g.item.name: g for g in G.from_loadouts([first, later, upgrade_suit, upgrade_gun])}
        self.assertEqual((owned["Maverick"].current, owned["Karma AR-50"].current, owned["Karma AR-50"].fitted), (4, 4, ("Scope",)))
        self.assertEqual(len(G.from_loadouts([first, later])), 2)                          # one suit and one weapon, not two of each

    def test_an_upgrade_of_something_not_listed_is_ignored(self):
        self.assertEqual(G.from_loadouts([{"event": "UpgradeSuit", "SuitID": 99, "Class": 5}, {"event": "UpgradeWeapon", "SuitModuleID": 99, "Class": 5}]), [])

    def test_the_flight_suit_and_unknown_things_are_left_out(self):
        owned = G.from_loadouts([loadout(suit="flightsuit", modules=[weapon("wpn_unknown_future_gun", 3), weapon("wpn_m_assaultrifle_laser_fauto", 9)])])
        self.assertEqual(owned, [])

    def test_unnamed_mods_are_reported_not_dropped_silently(self):
        owned = G.from_loadouts([loadout(mods=["suit_nightvision", "suit_future_thing", 7, None])])
        self.assertEqual((owned[0].fitted, owned[0].unknown_mods), (("Night vision",), ("suit_future_thing",)))

    def test_junk_never_raises(self):
        for entry in ({}, {"SuitName": 5}, {"SuitName": "utilitysuit_classx"}, {"SuitName": "utilitysuit_class9"}, {"Modules": "x"}, {"Modules": [None, 5, {}]},
                      {"event": "UpgradeSuit"}, {"event": "UpgradeWeapon", "Class": True}):
            G.from_loadouts([entry])


class JournalReadTests(unittest.TestCase):
    def folder(self, files):
        folder = tempfile.mkdtemp()
        self.addCleanup(lambda: shutil.rmtree(folder, ignore_errors=True))
        for index, (name, commander, events) in enumerate(files):
            path = os.path.join(folder, name)
            lines = [{"event": "Commander", "Name": commander}, *events]
            with open(path, "w", encoding="utf-8") as handle:
                handle.write("\n".join(json.dumps(e) for e in lines) + "\n")
            os.utime(path, (1_700_000_000 + index * 100,) * 2)
        return folder

    def test_it_looks_back_past_sessions_with_no_loadouts_and_skips_other_commanders(self):
        folder = self.folder([
            ("Journal.2026-10-10T100000.01.log", "Bocheaux", [loadout(suit="explorationsuit_class5", name="Exo 5")]),
            ("Journal.2026-10-12T100000.01.log", "Zeb", [loadout(suit="utilitysuit_class3", modules=[weapon("wpn_m_assaultrifle_kinetic_fauto", 2)])]),
            ("Journal.2026-10-14T100000.01.log", "Zeb", [{"event": "UpgradeWeapon", "SuitModuleID": 1, "Class": 3, "Cost": 1}]),
            ("Journal.2026-10-15T100000.01.log", "Zeb", [{"event": "Music"}]),                      # newest: a short session, no loadouts
        ])
        owned = G.owned_gear(folder)
        self.assertEqual([(g.item.label, g.current) for g in owned], [("Maverick suit", 3), ("Karma AR-50", 3)])

    def test_nothing_to_find_gives_an_empty_list(self):
        self.assertEqual(G.owned_gear(self.folder([])), [])
        self.assertEqual(G.owned_gear(os.path.join(tempfile.gettempdir(), "no-such-journal-folder-xyz")), [])
        self.assertEqual(G.owned_gear(self.folder([("Journal.2026-10-15T100000.01.log", "Zeb", [{"event": "Music"}])])), [])


class PlanWithFittedTests(unittest.TestCase):
    def test_fitted_modifications_take_slots_and_are_not_planned_again(self):
        item = O.gear("Karma AR-50")
        plan = O.plan(item, 3, 5, ["Stability"], fitted=["Scope", "Magazine size"])
        self.assertEqual([b.name for b in plan.mods], ["Stability"])
        self.assertEqual(plan.fitted, ("Scope", "Magazine size"))
        self.assertIn("Already fitted: Scope, Magazine size.", plan.notes())
        with self.assertRaises(O.OdysseyPlanError) as caught:
            O.plan(item, 3, 5, ["Stability", "Reload speed", "Audio Masking"], fitted=["Scope", "Magazine size"])
        self.assertIn("already has 2", str(caught.exception))
        with self.assertRaises(O.OdysseyPlanError):
            O.plan(item, 3, 5, ["Scope"], fitted=["Scope"])


class TabGearTests(unittest.TestCase):
    def test_picking_my_gear_fills_in_the_item_class_and_fitted_mods(self):
        import tkinter as tk
        try:
            root = tk.Tk()
        except tk.TclError:
            self.skipTest("Tk has no display here")
        self.addCleanup(root.destroy)
        mine = G.from_loadouts([loadout(modules=[weapon("wpn_m_assaultrifle_kinetic_fauto", 3, ["weapon_scope", "weapon_range", "weapon_clipsize"])])])
        with tempfile.TemporaryDirectory() as folder:
            book = W.WishBook()
            book.load(folder)
            book.set_commander("Bocheaux")
            said = []
            tab = T.UpgradePlanTab(tk.Frame(root), book, said.append, owned_source=lambda: mine)
            tab.read_gear()
            self.assertIn("Found 2 suits and weapons", said[-1])
            tab._mine.set("Karma AR-50, class 3 (Mav 3)")
            tab._pick_owned()
            self.assertEqual((tab._gear.get(), tab._current.get(), tab._target.get()), ("Karma AR-50", "3", "5"))
            self.assertEqual(tab._fitted, ("Scope", "Greater range (Kinematic kinetic)", "Magazine size"))
            self.assertEqual(len(tab._table), 2)                               # classes 4 and 5
            # one slot is free: the first box offers the rest, the others only "(none)"
            self.assertNotIn("Scope", tab._mod_boxes[0]._values)
            self.assertIn("Stability", tab._mod_boxes[0]._values)
            self.assertEqual(tab._mod_boxes[1]._values, [T.NONE])
            tab._mod_vars[0].set("Stability")
            tab.refresh()
            tab.add_to_wishlist()
            self.assertEqual(sorted(i.blueprint_id for i in book.items()), ["Weapon|Karma AR-50|4", "Weapon|Karma AR-50|5", "Weapon|Stability|0"])
            tab._gear.set("TK Zenith")
            tab._gear_chosen()
            self.assertEqual((tab._fitted, tab._mine.get()), ((), ""))             # picking by hand forgets what was read

    def test_no_gear_found_says_so(self):
        import tkinter as tk
        try:
            root = tk.Tk()
        except tk.TclError:
            self.skipTest("Tk has no display here")
        self.addCleanup(root.destroy)
        with tempfile.TemporaryDirectory() as folder:
            book = W.WishBook()
            book.load(folder)
            said = []
            tab = T.UpgradePlanTab(tk.Frame(root), book, said.append, owned_source=lambda: [])
            tab.read_gear()
            self.assertIn("No suits or weapons found", said[-1])


if __name__ == "__main__":
    unittest.main()
