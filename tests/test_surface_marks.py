"""Marks (surface_marks.py): validation, per-body lookup, the compass target, and saving per commander."""
from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from plugin import surface_marks as M  # noqa: E402


def make(folder, cmdr="Bocheaux"):
    ids = iter(f"id{i}" for i in range(1, 200))
    book = M.MarkBook(now=lambda: "2026-10-13T12:00:00Z", new_id=lambda: next(ids))
    book.load(folder)
    book.set_commander(cmdr)
    return book


class AddTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.book = make(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_a_mark_is_added_with_its_place(self):
        mark = self.book.add("  Ship  ", " Col 70 A 1 ", "12.5", "-45,25")
        self.assertEqual((mark.name, mark.body, mark.latitude, mark.longitude), ("Ship", "Col 70 A 1", 12.5, -45.25))
        self.assertEqual(self.book.count(), 1)

    def test_bad_marks_are_refused_with_a_reason(self):
        cases = [("", "Body", 0, 0, "name"), ("A", "  ", 0, 0, "body"), ("A", "B", "north", 0, "Latitude"),
                 ("A", "B", 91, 0, "Latitude"), ("A", "B", -90.1, 0, "Latitude"), ("A", "B", 0, 181, "Longitude"),
                 ("A", "B", float("nan"), 0, "Latitude"), ("A", "B", 0, float("inf"), "Longitude"),
                 ("N" * (M.MAX_NAME + 1), "B", 0, 0, "name"), ("A", "B" * (M.MAX_BODY + 1), 0, 0, "body"), ("A", "B", None, 0, "Latitude")]
        for name, body, lat, lon, word in cases:
            with self.subTest(name=name[:5], body=body[:5], lat=lat, lon=lon):
                with self.assertRaises(M.MarkError) as raised:
                    self.book.add(name, body, lat, lon)
                self.assertIn(word, str(raised.exception))
        self.assertEqual(self.book.count(), 0)

    def test_the_edges_of_the_range_are_fine(self):
        self.book.add("Pole", "B", 90, 180)
        self.book.add("Pole2", "B", -90, -180)
        self.assertEqual(self.book.count(), 2)

    def test_the_count_limit(self):
        for i in range(M.MAX_MARKS):
            self.book._marks.append(M.Mark(f"m{i}", f"M{i}", "B", 0.0, 0.0, ""))
        with self.assertRaises(M.MarkError) as raised:
            self.book.add("one more", "B", 0, 0)
        self.assertIn("500", str(raised.exception))

    def test_no_commander_no_marks(self):
        book = M.MarkBook()
        book.load(self.tmp.name)
        with self.assertRaises(M.MarkError) as raised:
            book.add("A", "B", 0, 0)
        self.assertIn("commander", str(raised.exception))
        with self.assertRaises(M.MarkError):
            book.set_target(M.NONE)

    def test_default_names_skip_the_ones_in_use(self):
        self.assertEqual(self.book.next_name(), "Mark 1")
        self.book.add("Mark 1", "B", 0, 0)
        self.book.add("mark 3", "B", 0, 0)
        self.assertEqual(self.book.next_name(), "Mark 2")


class LookupTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.book = make(self.tmp.name)
        self.a = self.book.add("Beta camp", "Col 70 A 1", 10, 20)
        self.b = self.book.add("Alpha ship", "Col 70 A 1", -5, 40)
        self.c = self.book.add("Elsewhere", "Sol 3", 0, 0)

    def tearDown(self):
        self.tmp.cleanup()

    def test_marks_are_listed_by_name(self):
        self.assertEqual([m.name for m in self.book.all()], ["Alpha ship", "Beta camp", "Elsewhere"])

    def test_a_body_matches_trimmed_and_case_folded(self):
        self.assertEqual([m.name for m in self.book.for_body("  COL 70 a 1 ")], ["Alpha ship", "Beta camp"])
        self.assertEqual(self.book.for_body(""), [])
        self.assertEqual(self.book.for_body(None), [])
        self.assertEqual(self.book.for_body("Col 70 A"), [])

    def test_update_keeps_the_id_and_created_time(self):
        changed = self.book.update(self.a.id, "Beta base", "Col 70 A 1", 11, 21)
        self.assertEqual((changed.id, changed.created, changed.name, changed.latitude), (self.a.id, self.a.created, "Beta base", 11.0))
        with self.assertRaises(M.MarkError):
            self.book.update("missing", "X", "B", 0, 0)
        with self.assertRaises(M.MarkError):
            self.book.update(self.a.id, "", "B", 0, 0)
        self.assertEqual(self.book.get(self.a.id).name, "Beta base")


class TargetTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.book = make(self.tmp.name)
        self.mark = self.book.add("Ship", "B", 1, 2)

    def tearDown(self):
        self.tmp.cleanup()

    def test_the_target_starts_as_the_nearest_hotspot(self):
        self.assertEqual(self.book.target, M.AUTO)
        self.assertIsNone(self.book.target_mark())

    def test_a_mark_can_be_the_target_and_none_can_be_chosen(self):
        self.book.set_target(self.mark.id)
        self.assertEqual(self.book.target_mark().name, "Ship")
        self.book.set_target(M.NONE)
        self.assertIsNone(self.book.target_mark())
        self.assertEqual(self.book.target, M.NONE)
        with self.assertRaises(M.MarkError):
            self.book.set_target("nonsense")

    def test_deleting_the_target_goes_back_to_the_nearest_hotspot(self):
        self.book.set_target(self.mark.id)
        self.book.delete(self.mark.id)
        self.assertEqual(self.book.target, M.AUTO)
        self.assertFalse(self.book.delete(self.mark.id))

    def test_deleting_another_mark_keeps_the_target(self):
        other = self.book.add("Camp", "B", 3, 4)
        self.book.set_target(self.mark.id)
        self.book.delete(other.id)
        self.assertEqual(self.book.target, self.mark.id)

    def test_listeners_hear_every_change_and_a_failing_one_stops_nothing(self):
        heard = []
        self.book.add_listener(lambda: (_ for _ in ()).throw(RuntimeError("window gone")))
        callback = lambda: heard.append(1)   # noqa: E731
        self.book.add_listener(callback)
        self.book.set_target(M.NONE)
        self.book.add("Camp", "B", 0, 0)
        self.assertEqual(len(heard), 2)
        self.book.remove_listener(callback)
        self.book.set_target(M.AUTO)
        self.assertEqual(len(heard), 2)


class PersistenceTests(unittest.TestCase):
    def test_marks_and_target_come_back_for_the_same_commander_only(self):
        with tempfile.TemporaryDirectory() as folder:
            book = make(folder, "Bocheaux")
            mark = book.add("Ship", "B", 1, 2)
            book.set_target(mark.id)
            other = make(folder, "Someone Else")
            self.assertEqual((other.count(), other.target), (0, M.AUTO))
            again = make(folder, "BOCHEAUX")
            self.assertEqual([m.name for m in again.all()], ["Ship"])
            self.assertEqual(again.target_mark().name, "Ship")

    def test_a_target_that_points_at_a_missing_mark_falls_back(self):
        with tempfile.TemporaryDirectory() as folder:
            raw = {"version": 2, "commanders": {"bocheaux": {"name": "Bocheaux", "data": {"marks": [], "target": "gone"}}},
                   "legacy": None, "meta": {}}
            with open(os.path.join(folder, M.STATE_FILENAME), "w", encoding="utf-8") as handle:
                json.dump(raw, handle)
            self.assertEqual(make(folder).target, M.AUTO)

    def test_damaged_entries_are_dropped_and_the_rest_kept(self):
        with tempfile.TemporaryDirectory() as folder:
            good = {"id": "g", "name": "Ship", "body": "B", "latitude": 1, "longitude": 2, "created": "c"}
            raw = {"version": 2, "commanders": {"bocheaux": {"name": "Bocheaux", "data": {"marks": [
                good, {"id": "x"}, "junk", {**good, "id": "bad", "latitude": 500}, {**good, "id": "bad2", "longitude": "east"},
                {**good, "id": "bad3", "body": ""}], "target": "g"}}}, "legacy": None, "meta": {}}
            with open(os.path.join(folder, M.STATE_FILENAME), "w", encoding="utf-8") as handle:
                json.dump(raw, handle)
            book = make(folder)
            self.assertEqual([m.id for m in book.all()], ["g"])
            self.assertEqual(book.target, "g")

    def test_the_commander_name_is_never_part_of_a_file_name(self):
        with tempfile.TemporaryDirectory() as folder:
            make(folder, "CMDR / <Bad>: Name").add("Ship", "B", 0, 0)
            self.assertEqual(os.listdir(folder), [M.STATE_FILENAME])

    def test_switching_commanders_shows_the_other_marks_and_target(self):
        with tempfile.TemporaryDirectory() as folder:
            book = make(folder, "A")
            mark = book.add("Ship", "B", 0, 0)
            book.set_target(mark.id)
            self.assertTrue(book.set_commander("B"))
            self.assertEqual((book.count(), book.target), (0, M.AUTO))
            self.assertFalse(book.set_commander("b"))
            self.assertTrue(book.set_commander("A"))
            self.assertEqual((book.count(), book.target), (1, mark.id))


if __name__ == "__main__":
    unittest.main()
