"""The blueprint wishlist (blueprint_wishlist.py) and the shopping math (blueprint_needs.py): adding and limits, saving per commander, a damaged
file, ready in list order, the combined list, ingredients that cannot be counted, and the Inventory's ship locker count."""
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

from plugin import blueprint_needs as N  # noqa: E402
from plugin import blueprint_wishlist as W  # noqa: E402
from plugin import blueprints as B  # noqa: E402
from plugin.inventory import InventoryTracker  # noqa: E402


def make(folder, cmdr="Bocheaux"):
    book = W.WishBook()
    book.load(folder)
    book.set_commander(cmdr)
    return book


def pick(kind, name, grade):
    return next(b for b in B.grades_for(kind, name) if b.grade == grade)


FSD = pick("Frame Shift Drive", "Increased FSD Range", 1)
FSD5 = pick("Frame Shift Drive", "Increased FSD Range", 5)


class WishlistTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.book = make(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_a_blueprint_is_added_with_one_craft(self):
        item = self.book.add(FSD.id)
        self.assertEqual((item.blueprint_id, item.crafts), (FSD.id, 1))
        self.assertIs(item.blueprint, FSD)

    def test_adding_it_again_adds_to_its_crafts(self):
        self.book.add(FSD.id, 2)
        self.assertEqual(self.book.add(FSD.id, 3).crafts, 5)
        self.assertEqual(self.book.count(), 1)

    def test_the_limits_are_enforced_not_trimmed(self):
        self.book.add(FSD.id, W.MAX_CRAFTS)
        with self.assertRaises(W.WishError):
            self.book.add(FSD.id, 1)
        for bad in (0, -1, W.MAX_CRAFTS + 1, 1.5, "2", True):
            with self.assertRaises(W.WishError, msg=repr(bad)):
                self.book.add(FSD5.id, bad)
        for blueprint in B.ALL[:W.MAX_ITEMS + 5]:
            if blueprint.id != FSD.id:
                try:
                    self.book.add(blueprint.id)
                except W.WishError as err:
                    self.assertIn(str(W.MAX_ITEMS), str(err))
                    break
        self.assertLessEqual(self.book.count(), W.MAX_ITEMS)

    def test_an_unknown_blueprint_is_refused(self):
        with self.assertRaises(W.WishError):
            self.book.add("nope|nope|0")

    def test_nothing_can_be_added_before_a_commander_is_known(self):
        with self.assertRaises(W.WishError):
            W.WishBook().add(FSD.id)

    def test_set_crafts_and_remove(self):
        self.book.add(FSD.id)
        self.assertEqual(self.book.set_crafts(FSD.id, 7).crafts, 7)
        with self.assertRaises(W.WishError):
            self.book.set_crafts("nope", 2)
        self.assertTrue(self.book.remove(FSD.id))
        self.assertFalse(self.book.remove(FSD.id))

    def test_clear_empties_the_list(self):
        self.book.add(FSD.id)
        self.book.add(FSD5.id)
        self.assertEqual(self.book.clear(), 2)
        self.assertEqual(self.book.items(), [])
        self.assertEqual(self.book.clear(), 0)

    def test_order_is_the_order_added(self):
        self.book.add(FSD5.id)
        self.book.add(FSD.id)
        self.assertEqual([i.blueprint_id for i in self.book.items()], [FSD5.id, FSD.id])

    def test_listeners_hear_of_changes_and_a_failing_one_stops_nothing(self):
        heard = []
        self.book.add_listener(lambda: 1 / 0)
        self.book.add_listener(lambda: heard.append(1))
        self.book.add(FSD.id)
        self.assertEqual(heard, [1])


class SavingTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.tmp.cleanup()

    def path(self):
        return os.path.join(self.tmp.name, W.STATE_FILENAME)

    def test_a_list_survives_a_restart(self):
        book = make(self.tmp.name)
        book.add(FSD.id, 3)
        book.add(FSD5.id)
        again = make(self.tmp.name)
        self.assertEqual([(i.blueprint_id, i.crafts) for i in again.items()], [(FSD.id, 3), (FSD5.id, 1)])

    def test_commanders_do_not_see_each_others_lists(self):
        make(self.tmp.name, "Bocheaux").add(FSD.id)
        self.assertEqual(make(self.tmp.name, "Someone Else").items(), [])
        self.assertEqual(make(self.tmp.name, "BOCHEAUX").count(), 1)

    def test_no_commander_name_is_in_a_file_name(self):
        make(self.tmp.name).add(FSD.id)
        self.assertEqual(os.listdir(self.tmp.name), [W.STATE_FILENAME])

    def test_a_damaged_file_gives_an_empty_list(self):
        with open(self.path(), "w", encoding="utf-8") as handle:
            handle.write("{not json")
        self.assertEqual(make(self.tmp.name).items(), [])

    def test_damaged_and_unknown_entries_are_dropped_and_crafts_are_pulled_into_range(self):
        make(self.tmp.name).add(FSD.id)
        with open(self.path(), encoding="utf-8") as handle:
            raw = json.load(handle)
        items = raw["commanders"]["bocheaux"]["data"]["items"]
        items += [5, "x", {"id": "gone|gone|1", "crafts": 2}, {"id": FSD5.id, "crafts": "2"}, {"id": FSD5.id, "crafts": 9999},
                  {"id": FSD5.id, "crafts": 3}, {"crafts": 2}]
        with open(self.path(), "w", encoding="utf-8") as handle:
            json.dump(raw, handle)
        again = make(self.tmp.name)
        self.assertEqual([(i.blueprint_id, i.crafts) for i in again.items()], [(FSD.id, 1), (FSD5.id, W.MAX_CRAFTS)])


class Hold:
    """Counts for the tests: ship materials by key, micro-resources by key."""

    def __init__(self, ship=None, odyssey=None):
        self.ship_counts, self.odyssey_counts = ship or {}, odyssey or {}

    def holdings(self):
        return N.Holdings(lambda k: self.ship_counts.get(k, 0), lambda k: self.odyssey_counts.get(k, 0))


def enough_for(blueprint, crafts=1, extra=0):
    """Ship-material counts that exactly cover `crafts` crafts of a blueprint made of ship materials only (plus `extra`)."""
    return {i.key: i.count * crafts + extra for i in blueprint.ingredients}


class NeedsTests(unittest.TestCase):
    def test_a_blueprints_needs_are_weighed_against_what_is_held(self):
        held = enough_for(FSD5)
        first = FSD5.ingredients[0]
        held[first.key] = first.count - 1
        needs = N.needs_for(FSD5, 2, Hold(held).holdings())
        self.assertEqual([n.need for n in needs], [i.count * 2 for i in FSD5.ingredients])
        self.assertEqual(needs[0].have, first.count - 1)
        self.assertEqual(needs[0].short, first.count * 2 - (first.count - 1))
        self.assertEqual(needs[1].short, FSD5.ingredients[1].count)    # holds enough for one craft of it, needs two

    def test_odyssey_ingredients_use_the_inventory_counts(self):
        suit = next(b for b in B.ALL if b.type == "Suit" and all(i.kind == B.ODYSSEY for i in b.ingredients))
        counts = {i.key: i.count for i in suit.ingredients}
        status = N.shopping_list([W.WishItem(suit.id, 1)], Hold(odyssey=counts).holdings())
        self.assertTrue(status.entries[0].ready)
        self.assertEqual(status.short_pieces, 0)

    def test_a_commodity_is_not_counted_and_the_entry_says_so(self):
        broker = next(b for b in B.ALL if any(i.kind == B.COMMODITY for i in b.ingredients))
        every = Hold({i.key: 10 ** 6 for i in broker.ingredients if i.kind == B.SHIP},
                     {i.key: 10 ** 6 for i in broker.ingredients if i.kind == B.ODYSSEY})
        status = N.shopping_list([W.WishItem(broker.id, 1)], every.holdings())
        entry = status.entries[0]
        self.assertTrue(entry.ready)                                  # everything that can be counted is covered
        self.assertTrue(entry.uncounted)
        self.assertTrue(all(i.kind == B.COMMODITY or i.key is None for i in broker.ingredients if i.name in entry.uncounted))
        self.assertTrue(all(n.short is None for n in entry.needs if n.ingredient.name in entry.uncounted))


class ShoppingTests(unittest.TestCase):
    def test_an_empty_list_is_not_ready(self):
        shopping = N.shopping_list([], Hold().holdings())
        self.assertEqual((shopping.entries, shopping.needs, shopping.all_ready), ((), (), False))

    def test_a_covered_entry_is_ready_and_the_list_is_complete(self):
        shopping = N.shopping_list([W.WishItem(FSD.id, 2)], Hold(enough_for(FSD, 2)).holdings())
        self.assertTrue(shopping.entries[0].ready)
        self.assertTrue(shopping.all_ready)
        self.assertEqual((shopping.ready_count, shopping.short_pieces), (1, 0))

    def test_nothing_held_means_everything_is_short(self):
        shopping = N.shopping_list([W.WishItem(FSD.id, 2)], Hold().holdings())
        self.assertFalse(shopping.entries[0].ready)
        self.assertEqual(shopping.short_pieces, sum(i.count * 2 for i in FSD.ingredients))
        self.assertFalse(shopping.all_ready)

    def test_ready_is_in_list_order_and_a_short_entry_takes_nothing(self):
        # Enough for exactly one craft of FSD: the first entry takes it, the second (the same again) is short.
        shopping = N.shopping_list([W.WishItem(FSD.id, 1), W.WishItem(FSD5.id, 1)], Hold(enough_for(FSD)).holdings())
        self.assertEqual([e.ready for e in shopping.entries], [True, False])
        # Swap the order: the grade 5 is not coverable, so it takes nothing, and the grade 1 is still ready.
        swapped = N.shopping_list([W.WishItem(FSD5.id, 1), W.WishItem(FSD.id, 1)], Hold(enough_for(FSD)).holdings())
        self.assertEqual([e.ready for e in swapped.entries], [False, True])

    def test_the_second_entry_sees_only_what_is_left(self):
        shopping = N.shopping_list([W.WishItem(FSD.id, 1), W.WishItem(FSD.id, 1)], Hold(enough_for(FSD)).holdings())
        self.assertEqual(len(shopping.entries), 2)
        self.assertTrue(shopping.entries[0].ready)
        self.assertTrue(all(n.have == 0 for n in shopping.entries[1].needs if n.have is not None))

    def test_the_combined_list_adds_an_ingredient_across_entries_and_weighs_it_once(self):
        a, b = FSD, pick("Frame Shift Drive", "Increased FSD Range", 2)
        shared = {i.key for i in a.ingredients} & {i.key for i in b.ingredients}
        self.assertTrue(shared, "the test needs two blueprints that share an ingredient")
        key = sorted(shared)[0]
        want = sum(i.count for bp in (a, b) for i in bp.ingredients if i.key == key)
        shopping = N.shopping_list([W.WishItem(a.id, 1), W.WishItem(b.id, 1)], Hold({key: 1}).holdings())
        line = next(n for n in shopping.needs if n.ingredient.key == key)
        self.assertEqual((line.need, line.have, line.short), (want, 1, want - 1))
        self.assertEqual(len([n for n in shopping.needs if n.ingredient.key == key]), 1)

    def test_the_list_puts_what_is_short_first_and_what_is_not_counted_last(self):
        broker = next(b for b in B.ALL if any(i.kind == B.COMMODITY for i in b.ingredients))
        shopping = N.shopping_list([W.WishItem(broker.id, 1), W.WishItem(FSD.id, 1)], Hold().holdings())
        flags = [n.have is None for n in shopping.needs]
        self.assertEqual(flags, sorted(flags))                       # counted first, uncounted last
        counted = [n.short for n in shopping.needs if n.have is not None]
        self.assertEqual(counted, sorted(counted, reverse=True))

    def test_an_entry_whose_blueprint_has_gone_is_skipped(self):
        shopping = N.shopping_list([W.WishItem("gone|gone|1", 1), W.WishItem(FSD.id, 1)], Hold().holdings())
        self.assertEqual(len(shopping.entries), 1)

    def test_negative_or_odd_holdings_never_make_a_negative_have(self):
        shopping = N.shopping_list([W.WishItem(FSD.id, 1)], N.Holdings(lambda k: -5, lambda k: -5))
        self.assertTrue(all(n.have == 0 for n in shopping.needs))


class ShipLockerTests(unittest.TestCase):
    def test_only_the_ship_locker_counts(self):
        tracker = InventoryTracker()
        tracker._backpack["Component"]["circuitboard"] = 2
        tracker._ship_locker["Component"]["circuitboard"] = 3
        tracker._ship_locker["Item"]["circuitboard"] = 1          # the same name in another category still counts
        tracker._fleet_carrier_locker["Component"]["circuitboard"] = 50
        self.assertEqual(tracker.in_ship_locker("Circuit Board"), 4)
        self.assertEqual(tracker.in_ship_locker("circuitboard"), 4)
        self.assertEqual(tracker.in_ship_locker("Unknown Thing"), 0)


if __name__ == "__main__":
    unittest.main()
