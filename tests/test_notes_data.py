"""Notes (notes_data.py): validation and limits, searching, saving per commander, and loading a damaged file."""
from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from plugin import notes_data as N  # noqa: E402


class Clock:
    def __init__(self):
        self.n = 0

    def __call__(self):
        self.n += 1
        return f"2026-10-13T12:{self.n:02d}:00Z"


def make(folder, cmdr="Bocheaux", **kwargs):
    ids = iter(f"id{i}" for i in range(1, 100))
    book = N.NoteBook(now=Clock(), new_id=lambda: next(ids), **kwargs)
    book.load(folder)
    book.set_commander(cmdr)
    return book


class AddTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.book = make(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_a_note_is_added_with_its_place_and_times(self):
        note = self.book.add("  Sol ", " Earth ", "  Nice rings.  ")
        self.assertEqual((note.system, note.body, note.text), ("Sol", "Earth", "Nice rings."))
        self.assertEqual(note.created, note.updated)
        self.assertEqual(note.place(), "Sol / Earth")
        self.assertEqual(N.Note("x", "Sol", "", "t", "", "").place(), "Sol")
        self.assertEqual(self.book.count(), 1)

    def test_a_note_without_a_system_or_text_is_refused_with_a_reason(self):
        for system, text, words in (("", "x", "system"), ("Sol", "   ", "text")):
            with self.assertRaises(N.NoteError) as raised:
                self.book.add(system, "", text)
            self.assertIn(words, str(raised.exception))
        self.assertEqual(self.book.count(), 0)

    def test_limits_refuse_instead_of_trimming(self):
        with self.assertRaises(N.NoteError):
            self.book.add("S" * (N.MAX_NAME + 1), "", "x")
        with self.assertRaises(N.NoteError):
            self.book.add("Sol", "B" * (N.MAX_NAME + 1), "x")
        with self.assertRaises(N.NoteError) as raised:
            self.book.add("Sol", "", "t" * (N.MAX_TEXT + 1))
        self.assertIn("2,000", str(raised.exception))
        self.book.add("Sol", "", "t" * N.MAX_TEXT)    # exactly the limit is fine

    def test_the_count_limit(self):
        for i in range(N.MAX_NOTES):
            self.book._notes.append(N.Note(f"n{i}", "Sol", "", "x", "", ""))
        with self.assertRaises(N.NoteError) as raised:
            self.book.add("Sol", "", "one more")
        self.assertIn("2,000", str(raised.exception))

    def test_no_commander_no_notes(self):
        book = N.NoteBook()
        book.load(self.tmp.name)
        self.assertFalse(book.ready)
        with self.assertRaises(N.NoteError) as raised:
            book.add("Sol", "", "x")
        self.assertIn("commander", str(raised.exception))


class ChangeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.book = make(self.tmp.name)
        self.first = self.book.add("Sol", "Earth", "first")
        self.second = self.book.add("Colonia", "", "second")

    def tearDown(self):
        self.tmp.cleanup()

    def test_newest_change_first(self):
        self.assertEqual([n.text for n in self.book.all()], ["second", "first"])
        self.book.update(self.first.id, "Sol", "Earth", "first, changed")
        self.assertEqual([n.text for n in self.book.all()], ["first, changed", "second"])

    def test_update_keeps_the_created_time_and_moves_the_changed_time_only_when_something_changed(self):
        same = self.book.update(self.first.id, "Sol", "Earth", "first")
        self.assertEqual(same.updated, self.first.updated)
        changed = self.book.update(self.first.id, "Sol", "Earth", "different")
        self.assertEqual(changed.created, self.first.created)
        self.assertGreater(changed.updated, self.first.updated)

    def test_update_checks_what_add_checks(self):
        with self.assertRaises(N.NoteError):
            self.book.update(self.first.id, "", "", "x")
        with self.assertRaises(N.NoteError):
            self.book.update("missing", "Sol", "", "x")
        self.assertEqual(self.book.get(self.first.id).text, "first")

    def test_delete(self):
        self.assertTrue(self.book.delete(self.first.id))
        self.assertFalse(self.book.delete(self.first.id))
        self.assertEqual([n.id for n in self.book.all()], [self.second.id])

    def test_listeners_hear_every_change_and_a_failing_one_stops_nothing(self):
        heard = []
        self.book.add_listener(lambda: (_ for _ in ()).throw(RuntimeError("window gone")))
        self.book.add_listener(lambda: heard.append(1))
        self.book.add("Sol", "", "third")
        self.book.delete(self.first.id)
        self.assertEqual(len(heard), 2)
        callback = lambda: heard.append(2)   # noqa: E731
        self.book.add_listener(callback)
        self.book.remove_listener(callback)
        self.book.add("Sol", "", "fourth")
        self.assertNotIn(2, heard)


class SearchTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.book = make(self.tmp.name)
        self.book.add("Sol", "Earth", "Blue world with a moon")
        self.book.add("Sol", "Mars", "Red, dusty")
        self.book.add("Colonia", "", "Blue giant nearby")

    def tearDown(self):
        self.tmp.cleanup()

    def test_a_system_matches_trimmed_and_case_folded(self):
        self.assertEqual(len(self.book.for_system(" SOL ")), 2)
        self.assertEqual(self.book.for_system(""), [])
        self.assertEqual(self.book.for_system(None), [])
        self.assertEqual(self.book.for_system("Sol Prime"), [])

    def test_search_needs_every_word_in_the_system_body_or_text(self):
        texts = lambda found: sorted(n.text for n in found)   # noqa: E731
        self.assertEqual(len(self.book.search("")), 3)
        self.assertEqual(texts(self.book.search("blue")), ["Blue giant nearby", "Blue world with a moon"])
        self.assertEqual(texts(self.book.search("BLUE earth")), ["Blue world with a moon"])
        self.assertEqual(texts(self.book.search("mars dusty")), ["Red, dusty"])
        self.assertEqual(self.book.search("nothing like this"), [])

    def test_search_can_be_limited_to_one_system(self):
        self.assertEqual([n.body for n in self.book.search("", system="sol")], ["Mars", "Earth"])
        self.assertEqual(len(self.book.search("blue", system="Colonia")), 1)


class PersistenceTests(unittest.TestCase):
    def test_notes_are_saved_and_come_back_for_the_same_commander_only(self):
        with tempfile.TemporaryDirectory() as folder:
            book = make(folder, "Bocheaux")
            book.add("Sol", "Earth", "mine")
            other = make(folder, "Someone Else")
            self.assertEqual(other.count(), 0)
            other.add("Sol", "", "theirs")
            again = make(folder, "BOCHEAUX")           # the journal sometimes writes the name in capitals
            self.assertEqual([n.text for n in again.all()], ["mine"])
            self.assertEqual([n.text for n in make(folder, "someone else").all()], ["theirs"])

    def test_switching_commanders_shows_the_other_list(self):
        with tempfile.TemporaryDirectory() as folder:
            book = make(folder, "A")
            book.add("Sol", "", "a's")
            self.assertTrue(book.set_commander("B"))
            self.assertEqual(book.count(), 0)
            self.assertFalse(book.set_commander("b"))   # the same commander again is no change
            self.assertTrue(book.set_commander("A"))
            self.assertEqual(book.count(), 1)

    def test_the_commander_name_is_never_part_of_a_file_name(self):
        with tempfile.TemporaryDirectory() as folder:
            make(folder, "CMDR / <Bad>: Name").add("Sol", "", "x")
            self.assertEqual(os.listdir(folder), [N.STATE_FILENAME])

    def test_damaged_entries_are_dropped_and_the_rest_kept(self):
        with tempfile.TemporaryDirectory() as folder:
            good = {"id": "g", "system": "Sol", "body": "", "text": "kept", "created": "c", "updated": "u"}
            raw = {"version": 2, "commanders": {"bocheaux": {"name": "Bocheaux", "data": {"notes": [
                good, {"id": "x"}, "junk", {"id": "y", "system": "", "text": "t"}, {**good, "id": "h", "body": 5, "text": "t" * 5000}]}}},
                "legacy": None, "meta": {}}
            with open(os.path.join(folder, N.STATE_FILENAME), "w", encoding="utf-8") as handle:
                json.dump(raw, handle)
            book = make(folder)
            self.assertEqual(sorted(n.id for n in book.all()), ["g", "h"])
            self.assertEqual(book.get("h").body, "")
            self.assertEqual(len(book.get("h").text), N.MAX_TEXT)

    def test_an_unreadable_file_gives_no_notes_and_no_error(self):
        with tempfile.TemporaryDirectory() as folder:
            with open(os.path.join(folder, N.STATE_FILENAME), "w", encoding="utf-8") as handle:
                handle.write("{not json")
            self.assertEqual(make(folder).count(), 0)


class ClipTests(unittest.TestCase):
    def test_clip_puts_text_on_one_line_and_shortens_it(self):
        self.assertEqual(N.clip("a\n  b\tc", 20), "a b c")
        self.assertEqual(N.clip("x" * 10, 5), "xxxx…")
        self.assertEqual(N.clip("", 5), "")
        self.assertEqual(N.clip(None, 5), "")


if __name__ == "__main__":
    unittest.main()
