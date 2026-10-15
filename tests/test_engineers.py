"""Engineer standings (engineers.py) and the table helpers behind them: the real event shapes, name matching, saving per commander, a damaged
file, and the unlock rows."""
from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from plugin import blueprints as B  # noqa: E402
from plugin import engineers as E  # noqa: E402

# The shapes below are those of real EngineerProgress events (checked against real journals, 2026-10-13).
LOGIN = {"event": "EngineerProgress", "Engineers": [
    {"Engineer": "Felicity Farseer", "EngineerID": 300100, "Progress": "Unlocked", "RankProgress": 40, "Rank": 3},
    {"Engineer": "Eleanor Bresa", "EngineerID": 400011, "Progress": "Known"},
    {"Engineer": "Lei Cheung", "EngineerID": 300120, "Progress": "Invited"},
    {"Engineer": "Tod 'The Blaster' McQuinn", "EngineerID": 300260, "Progress": "Unlocked", "RankProgress": 0, "Rank": 5},
]}
SINGLE = {"event": "EngineerProgress", "Engineer": "Lei Cheung", "EngineerID": 300120, "Progress": "Unlocked", "Rank": 1, "RankProgress": 0}


def make(folder, cmdr="Bocheaux"):
    book = E.EngineerBook()
    book.load(folder)
    book.set_commander(cmdr)
    return book


class NameTests(unittest.TestCase):
    def test_a_nickname_in_quotes_is_dropped(self):
        self.assertEqual(E.name_key("Tod 'The Blaster' McQuinn"), "tod mcquinn")
        self.assertEqual(E.name_key('Tod "The Blaster" McQuinn'), "tod mcquinn")
        self.assertEqual(E.name_key("  Felicity   FARSEER "), "felicity farseer")
        self.assertEqual(E.name_key(None), "")

    def test_the_journal_and_the_table_agree_on_every_engineer_the_table_has(self):
        for name in B.engineer_names():
            self.assertEqual(E.name_key(name), E.name_key(name.upper()))
        self.assertEqual(E.name_key("Tod 'The Blaster' McQuinn"), E.name_key("Tod McQuinn"))


class EventTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.book = make(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_the_login_list_sets_every_standing(self):
        self.assertTrue(self.book.apply_event(LOGIN))
        self.assertTrue(self.book.has_data)
        felicity = self.book.standing("felicity farseer")
        self.assertEqual((felicity.progress, felicity.rank, felicity.rank_progress), ("Unlocked", 3, 40))
        self.assertEqual(felicity.describe(), "Unlocked, rank 3 (40%)")
        self.assertEqual(self.book.standing("Eleanor Bresa").describe(), "Known")
        self.assertEqual(self.book.standing("Lei Cheung").progress, "Invited")
        self.assertEqual([s.name for s in self.book.unlocked()], ["Felicity Farseer", "Tod 'The Blaster' McQuinn"])

    def test_the_journals_spelling_finds_the_tables(self):
        self.book.apply_event(LOGIN)
        self.assertTrue(self.book.standing("Tod McQuinn").unlocked)
        self.assertEqual(self.book.standing("Tod McQuinn").describe(), "Unlocked, rank 5")

    def test_a_single_engineer_event_updates_one(self):
        self.book.apply_event(LOGIN)
        self.assertTrue(self.book.apply_event(SINGLE))
        self.assertEqual(self.book.standing("Lei Cheung").describe(), "Unlocked, rank 1")
        self.assertEqual(self.book.standing("Eleanor Bresa").progress, "Known")      # the others stay
        self.assertFalse(self.book.apply_event(SINGLE))                                  # nothing changed

    def test_a_rank_up_has_no_progress_and_unlocks_at_that_rank(self):
        # The shape of a real rank-up event: a rank and nothing else.
        self.book.apply_event(LOGIN)
        rank_up = {"event": "EngineerProgress", "Engineer": "Felicity Farseer", "EngineerID": 300100, "Rank": 4}
        self.assertTrue(self.book.apply_event(rank_up))
        self.assertEqual(self.book.standing("Felicity Farseer").describe(), "Unlocked, rank 4")
        self.assertFalse(self.book.apply_event(rank_up))
        self.assertTrue(self.book.apply_event({"event": "EngineerProgress", "Engineer": "Elvira Martuuk", "EngineerID": 300160, "Rank": 3}))
        self.assertEqual(self.book.standing("Elvira Martuuk").describe(), "Unlocked, rank 3")
        for bad in (0, 6, "3", None, True):
            self.assertFalse(self.book.apply_event({"event": "EngineerProgress", "Engineer": "Zed", "Rank": bad}), bad)

    def test_a_later_list_replaces_not_adds(self):
        self.book.apply_event(LOGIN)
        self.book.apply_event({"event": "EngineerProgress", "Engineers": [{"Engineer": "Lei Cheung", "Progress": "Invited"}]})
        self.assertEqual([s.name for s in self.book.all()], ["Lei Cheung"])

    def test_an_empty_list_never_wipes_what_is_known(self):
        self.book.apply_event(LOGIN)
        self.assertFalse(self.book.apply_event({"event": "EngineerProgress", "Engineers": []}))
        self.assertEqual(len(self.book.all()), 4)

    def test_the_documented_acquainted_is_read_as_known_and_barred_is_kept(self):
        self.book.apply_event({"event": "EngineerProgress", "Engineers": [
            {"Engineer": "A", "Progress": "Acquainted"}, {"Engineer": "B", "Progress": "Barred"}]})
        self.assertEqual((self.book.standing("A").progress, self.book.standing("B").progress), ("Known", "Barred"))

    def test_rank_is_only_kept_for_an_unlocked_engineer_and_is_pulled_into_range(self):
        self.book.apply_event({"event": "EngineerProgress", "Engineers": [
            {"Engineer": "A", "Progress": "Known", "Rank": 4, "RankProgress": 50},
            {"Engineer": "B", "Progress": "Unlocked", "Rank": 99, "RankProgress": -5}]})
        self.assertEqual((self.book.standing("A").rank, self.book.standing("A").rank_progress), (0, 0))
        self.assertEqual((self.book.standing("B").rank, self.book.standing("B").rank_progress), (5, 0))

    def test_damaged_events_are_ignored(self):
        for bad in ({"event": "EngineerProgress"}, {"event": "EngineerProgress", "Engineer": "A"}, {"event": "EngineerProgress", "Engineer": "",
                    "Progress": "Unlocked"}, {"event": "EngineerProgress", "Engineer": "A", "Progress": "Nonsense"},
                    {"event": "EngineerProgress", "Engineers": [None, 5, {"Engineer": 3}]}, {"event": "Music"}):
            self.assertFalse(self.book.apply_event(bad), bad)
        self.assertEqual(self.book.all(), [])

    def test_nothing_is_taken_before_a_commander_is_known(self):
        self.assertFalse(E.EngineerBook().apply_event(LOGIN))

    def test_listeners_hear_of_a_change_and_a_failing_one_stops_nothing(self):
        heard = []
        self.book.add_listener(lambda: 1 / 0)
        self.book.add_listener(lambda: heard.append(1))
        self.book.apply_event(LOGIN)
        self.assertEqual(heard, [1])


class SavingTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.tmp.cleanup()

    def path(self):
        return os.path.join(self.tmp.name, E.STATE_FILENAME)

    def test_standings_survive_a_restart(self):
        make(self.tmp.name).apply_event(LOGIN)
        again = make(self.tmp.name)
        self.assertEqual(again.standing("Felicity Farseer").describe(), "Unlocked, rank 3 (40%)")
        self.assertEqual(len(again.all()), 4)

    def test_commanders_do_not_see_each_others_standings(self):
        make(self.tmp.name, "Bocheaux").apply_event(LOGIN)
        self.assertEqual(make(self.tmp.name, "Someone Else").all(), [])
        self.assertEqual(len(make(self.tmp.name, "BOCHEAUX").all()), 4)

    def test_no_commander_name_is_in_a_file_name(self):
        make(self.tmp.name).apply_event(LOGIN)
        self.assertEqual(os.listdir(self.tmp.name), [E.STATE_FILENAME])

    def test_a_damaged_file_gives_no_standings(self):
        with open(self.path(), "w", encoding="utf-8") as handle:
            handle.write("{not json")
        self.assertEqual(make(self.tmp.name).all(), [])

    def test_damaged_entries_are_dropped_and_the_rest_kept(self):
        make(self.tmp.name).apply_event(LOGIN)
        with open(self.path(), encoding="utf-8") as handle:
            raw = json.load(handle)
        raw["commanders"]["bocheaux"]["data"]["engineers"] += [5, "x", {"name": "Z"}, {"name": "Y", "progress": "Nonsense"}]
        with open(self.path(), "w", encoding="utf-8") as handle:
            json.dump(raw, handle)
        self.assertEqual(len(make(self.tmp.name).all()), 4)


class TableHelperTests(unittest.TestCase):
    def test_the_stand_ins_are_not_engineers(self):
        names = B.engineer_names()
        for stand_in in B.STAND_IN_NAMES:
            self.assertNotIn(stand_in, names)
        self.assertFalse(any(n.startswith("@") for n in names))
        self.assertIn("Felicity Farseer", names)

    def test_real_engineers_of_a_blueprint(self):
        for blueprint in B.ALL:
            for name in B.real_engineers(blueprint):
                self.assertNotIn(name, B.STAND_IN_NAMES)
            self.assertFalse(any(e.startswith("@") for e in blueprint.engineers), blueprint.id)

    def test_the_colonia_engineers(self):
        colonia = {"baltanos", "eleanor bresa", "rosa dayette", "yi shen"}
        self.assertTrue(colonia <= set(E.INFO))
        self.assertTrue(all(E.INFO[k].on_foot for k in colonia))
        offered = {E.name_key(e) for b in B.ALL if not b.is_unlock for e in B.real_engineers(b)}
        self.assertTrue(colonia <= offered)         # they offer suit and weapon upgrades
        unlock = B.unlock_for("Yi Shen")
        self.assertEqual([(i.name, i.count, i.kind, i.key) for i in unlock.ingredients],
                         [("Faction Associates", 10, B.ODYSSEY, "factionassociates"), ("Digital Designs", 10, B.ODYSSEY, "digitaldesigns"),
                          ("Manufacturing Instructions", 10, B.ODYSSEY, "manufacturinginstructions")])
        self.assertEqual(B.unresolved(), [])
        for name in ("Baltanos", "Eleanor Bresa", "Rosa Dayette"):
            self.assertIsNone(B.unlock_for(name))       # their unlocks are actions, not items
            self.assertTrue(E.info(name).unlock)

    def test_an_engineers_unlock_row(self):
        unlock = B.unlock_for("Bill Turner")
        self.assertEqual([(i.name, i.count) for i in unlock.ingredients], [("Bromellite", 50)])
        self.assertTrue(unlock.is_unlock)
        self.assertIsNone(B.unlock_for("Nobody At All"))
        self.assertIs(B.unlock_for("FELICITY  farseer", key=E.name_key), B.unlock_for("Felicity Farseer"))
        self.assertIsNotNone(B.unlock_for("FELICITY  farseer", key=E.name_key))


class LocationTableTests(unittest.TestCase):
    def test_every_engineer_in_the_blueprints_has_a_place_and_the_other_way_round(self):
        blueprint_names = {E.name_key(n) for n in B.engineer_names()}
        self.assertEqual(blueprint_names, set(E.INFO))
        self.assertEqual(len(E.INFO), 38)

    def test_the_journals_nickname_form_finds_the_entry(self):
        info = E.info("Tod 'The Blaster' McQuinn")
        self.assertEqual((info.system, info.base), ("Wolf 397", "Trophy Camp"))
        self.assertIsNone(E.info("Nobody"))
        self.assertIsNone(E.info(None))

    def test_places_and_flags(self):
        self.assertEqual(E.info("Felicity Farseer").place(), "Farseer Inc, Deciat 6 A")
        self.assertIn("on foot", E.info("Domino Green").place())
        self.assertFalse(E.info("Felicity Farseer").on_foot)
        self.assertTrue(E.info("Eleanor Bresa").on_foot)
        self.assertIn("permit needed", E.info("Bill Turner").place())
        self.assertEqual(len(E.info("Bill Turner").coords), 3)

    def test_regions(self):
        colonia = sorted(i.name for i in E.INFO.values() if i.region() == E.COLONIA)
        self.assertEqual(colonia, ["Baltanos", "Eleanor Bresa", "Etienne Dorn", "Marsha Hicks", "Mel Brandon", "Petra Olmanova", "Rosa Dayette", "Yi Shen"])
        self.assertEqual(len([i for i in E.INFO.values() if i.region() == E.BUBBLE]), 30)
        self.assertEqual(E.info("Felicity Farseer").region(), E.BUBBLE)
        self.assertEqual(E.REGIONS, (E.BUBBLE, E.COLONIA))

    def test_every_colonia_on_foot_engineer_is_in_colonia(self):
        for name in ("Baltanos", "Eleanor Bresa", "Rosa Dayette", "Yi Shen"):
            self.assertEqual(E.info(name).region(), E.COLONIA, name)

    def test_yarden_bonds_meeting_requirement_is_five_plans(self):
        self.assertIn("5 Smear campaign plans", E.info("Yarden Bond").invite)

    def test_the_grade_thresholds_and_the_one_quirk(self):
        self.assertEqual(E.GRADE_PROFIT_CREDITS, ((2, 500_000), (3, 2_000_000), (4, 8_000_000), (5, 16_000_000)))
        self.assertEqual(E.grade_profit_text(), "grade 2 at 500,000 cr, grade 3 at 2,000,000 cr, grade 4 at 8,000,000 cr, grade 5 at 16,000,000 cr")
        self.assertIn("terra velasquez", E.QUIRKS)


if __name__ == "__main__":
    unittest.main()
