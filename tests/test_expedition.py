"""Expedition planner (expedition.py): the expeditions and their stops, starting and finishing, ticking stops off from arrivals, the jump totals,
ordering, import and export, saving per commander, and loading a damaged file."""
from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from plugin import expedition as X  # noqa: E402


class Clock:
    def __init__(self):
        self.n = 0

    def __call__(self):
        self.n += 1
        return f"2026-10-13T12:{self.n:02d}:00Z"


class Mono:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now


def make(folder, cmdr="Bocheaux", mono=None):
    ids = iter(f"id{i}" for i in range(1, 1000))
    book = X.ExpeditionBook(now=Clock(), new_id=lambda: next(ids), clock=mono or Mono())
    book.load(folder)
    book.set_commander(cmdr)
    return book


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.mono = Mono()
        self.book = make(self.tmp.name, mono=self.mono)

    def tearDown(self):
        self.tmp.cleanup()

    def trip(self, name="Colonia run", systems=("Sol", "Sagittarius A*", "Colonia")):
        e = self.book.create(name)
        for s in systems:
            self.book.add_stop(e.id, s)
        return e


class ExpeditionTests(Base):
    def test_an_expedition_is_created_planned(self):
        e = self.book.create("  Colonia   run ")
        self.assertEqual((e.name, e.status, e.stops), ("Colonia run", X.PLANNED, []))
        self.assertIs(self.book.get(e.id), e)

    def test_names_are_validated_and_unique(self):
        self.book.create("A")
        for bad in ("", "   ", "x" * 81, "a"):
            with self.assertRaises(X.ExpeditionError, msg=repr(bad)):
                self.book.create(bad)

    def test_the_limit_is_enforced(self):
        for n in range(X.MAX_EXPEDITIONS):
            self.book.create(f"E{n}")
        with self.assertRaises(X.ExpeditionError) as caught:
            self.book.create("one too many")
        self.assertIn(str(X.MAX_EXPEDITIONS), str(caught.exception))

    def test_nothing_can_be_created_before_a_commander_is_known(self):
        with self.assertRaises(X.ExpeditionError):
            X.ExpeditionBook().create("A")

    def test_rename_and_delete(self):
        a, b = self.book.create("A"), self.book.create("B")
        self.assertEqual(self.book.rename(a.id, "Alpha").name, "Alpha")
        with self.assertRaises(X.ExpeditionError):
            self.book.rename(a.id, "b")                    # B exists (case ignored)
        self.assertEqual(self.book.rename(b.id, "B").name, "B")   # its own name is fine
        self.assertTrue(self.book.delete(a.id))
        self.assertFalse(self.book.delete(a.id))
        with self.assertRaises(X.ExpeditionError):
            self.book.rename(a.id, "Z")

    def test_the_list_puts_active_first_and_done_last(self):
        a, b, c = self.trip("A"), self.trip("B"), self.trip("C")
        self.book.start(b.id)
        self.book.finish(c.id)
        self.assertEqual([e.name for e in self.book.expeditions()], ["B", "A", "C"])


class StatusTests(Base):
    def test_starting_needs_a_stop(self):
        e = self.book.create("Empty")
        with self.assertRaises(X.ExpeditionError):
            self.book.start(e.id)

    def test_only_one_is_active_and_the_other_is_paused_with_its_progress(self):
        a, b = self.trip("A"), self.trip("B")
        self.book.start(a.id)
        self.book.on_arrival("Sol", is_jump=True, jump_distance=10)
        self.book.start(b.id)
        self.assertEqual((a.status, b.status, self.book.active()), (X.PAUSED, X.ACTIVE, b))
        self.assertEqual((a.visited_count, a.jumps), (1, 1))
        self.book.start(a.id)
        self.assertEqual((a.status, b.status), (X.ACTIVE, X.PAUSED))
        self.assertEqual(a.started, self.book.get(a.id).started)

    def test_pause_finish_and_reset(self):
        e = self.trip()
        self.book.start(e.id)
        self.book.on_arrival("Sol", is_jump=True, jump_distance=5)
        self.assertEqual(self.book.pause(e.id).status, X.PAUSED)
        self.assertIsNone(self.book.active())
        self.assertEqual(self.book.finish(e.id).status, X.DONE)
        self.assertTrue(e.finished)
        self.assertEqual(self.book.start(e.id).status, X.ACTIVE)           # a finished one can be reopened
        self.assertEqual(e.finished, "")
        reset = self.book.reset(e.id)
        self.assertEqual((reset.status, reset.started, reset.jumps, reset.light_years, reset.visited_count, len(reset.stops)),
                         (X.PLANNED, "", 0, 0.0, 0, 3))


class StopTests(Base):
    def test_stops_are_added_in_order_and_validated(self):
        e = self.trip(systems=("A", "B"))
        self.assertEqual([s.system for s in e.stops], ["A", "B"])
        for bad in ({"system": ""}, {"system": "x" * 101}, {"system": "A", "body": "b" * 101}, {"system": "A", "note": "n" * 501}):
            with self.assertRaises(X.ExpeditionError, msg=bad):
                self.book.add_stop(e.id, **bad)

    def test_the_stop_limit_is_enforced(self):
        e = self.book.create("Big")
        self.book.add_systems(e.id, ((f"S{n}", None) for n in range(X.MAX_STOPS + 20)))
        self.assertEqual(len(e.stops), X.MAX_STOPS)
        with self.assertRaises(X.ExpeditionError):
            self.book.add_stop(e.id, "one more")

    def test_update_clears_the_visit_and_position_when_the_system_changes(self):
        e = self.trip()
        self.book.start(e.id)
        stop = e.stops[0]
        self.book.set_coords(e.id, {"Sol": (0.0, 0.0, 0.0)})
        self.book.on_arrival("Sol")
        self.assertTrue(stop.is_visited and stop.xyz is not None)
        self.book.update_stop(e.id, stop.id, "Sol", "Earth", "Nice")                # same system: keeps both
        self.assertTrue(stop.is_visited and stop.xyz is not None)
        self.assertEqual((stop.body, stop.note), ("Earth", "Nice"))
        self.book.update_stop(e.id, stop.id, "Alpha Centauri", "", "")
        self.assertFalse(stop.is_visited)
        self.assertIsNone(stop.xyz)

    def test_remove_and_move(self):
        e = self.trip(systems=("A", "B", "C"))
        a, b, c = e.stops
        self.assertTrue(self.book.move_stop(e.id, b.id, -1))
        self.assertEqual([s.system for s in e.stops], ["B", "A", "C"])
        self.assertFalse(self.book.move_stop(e.id, b.id, -1))                        # already first
        self.assertFalse(self.book.move_stop(e.id, c.id, 1))                         # already last
        self.assertFalse(self.book.move_stop(e.id, "nope", 1))
        self.assertTrue(self.book.remove_stop(e.id, a.id))
        self.assertFalse(self.book.remove_stop(e.id, a.id))
        self.assertEqual([s.system for s in e.stops], ["B", "C"])

    def test_a_stop_can_be_ticked_off_by_hand_and_unticked(self):
        e = self.trip()
        self.assertTrue(self.book.set_visited(e.id, e.stops[0].id, True).is_visited)
        self.assertFalse(self.book.set_visited(e.id, e.stops[0].id, False).is_visited)
        with self.assertRaises(X.ExpeditionError):
            self.book.set_visited(e.id, "nope", True)

    def test_add_systems_skips_a_repeat_of_the_last_stop_and_keeps_positions(self):
        e = self.book.create("Plot")
        added = self.book.add_systems(e.id, [("A", (1.0, 2.0, 3.0)), ("a", None), ("B", None), ("A", None)])
        self.assertEqual(added, 3)                                   # the second "a" repeats the one before it; the last "A" does not
        self.assertEqual([s.system for s in e.stops], ["A", "B", "A"])
        self.assertEqual(e.stops[0].xyz, (1.0, 2.0, 3.0))

    def test_rows_are_added_in_one_go_and_bad_ones_are_skipped_not_trimmed(self):
        e = self.book.create("Rows")
        rows = [("Sol", "Earth", "hi"), ("", "", ""), ("x" * 101, "", ""), ("Colonia", "", "n" * 501), ("Alpha", "", "")]
        self.assertEqual(self.book.add_rows(e.id, rows), (2, 3))
        self.assertEqual([(s.system, s.body, s.note) for s in e.stops], [("Sol", "Earth", "hi"), ("Alpha", "", "")])
        self.assertEqual(self.book.add_rows(e.id, []), (0, 0))

    def test_rows_stop_at_the_limit(self):
        e = self.book.create("Big")
        self.assertEqual(self.book.add_rows(e.id, ((f"S{n}", "", "") for n in range(X.MAX_STOPS + 5))), (X.MAX_STOPS, 5))

    def test_set_coords_only_fills_stops_without_a_position(self):
        e = self.trip(systems=("A", "B"))
        e.stops[0].xyz = (9.0, 9.0, 9.0)
        given = self.book.set_coords(e.id, {"a": (1.0, 1.0, 1.0), "B": (2.0, 2.0, 2.0), "C": (3.0, 3.0, 3.0), "bad": "x"})
        self.assertEqual(given, 1)
        self.assertEqual((e.stops[0].xyz, e.stops[1].xyz), ((9.0, 9.0, 9.0), (2.0, 2.0, 2.0)))

    def test_nearest_neighbor_reorders_the_unvisited_located_stops(self):
        e = self.book.create("NN")
        for name, xyz in (("Done", (0.0, 0.0, 0.0)), ("Far", (100.0, 0.0, 0.0)), ("Near", (10.0, 0.0, 0.0)), ("Unknown", None), ("Mid", (50.0, 0.0, 0.0))):
            self.book.add_stop(e.id, name, xyz=xyz)
        self.book.set_visited(e.id, e.stops[0].id, True)
        self.assertEqual(self.book.reorder_nearest_neighbor(e.id, (0.0, 0.0, 0.0)), 3)
        self.assertEqual([s.system for s in e.stops], ["Done", "Near", "Mid", "Far", "Unknown"])


class SpellingTests(Base):
    def test_a_stop_takes_the_spelling_edsm_gives_whatever_case_it_was_typed_in(self):
        e = self.trip(systems=("sol", "OUTOTZ LS-K D8-0", "Colonia"))
        changed = self.book.canonical_names(e.id, ["Sol", "Outotz LS-K d8-0", "Sagittarius A*"])
        self.assertEqual((changed, [s.system for s in e.stops]), (2, ["Sol", "Outotz LS-K d8-0", "Colonia"]))
        self.assertEqual(self.book.canonical_names(e.id, ["Sol"]), 0)       # nothing left to change

    def test_only_case_and_spacing_can_differ(self):
        e = self.trip(systems=("Sol",))
        self.assertEqual(self.book.canonical_names(e.id, ["Solana"]), 0)
        self.assertEqual(e.stops[0].system, "Sol")

    def test_a_system_already_in_any_expedition_gives_its_spelling_for_another_case(self):
        self.trip(systems=("Outotz LS-K d8-0",))
        self.assertEqual(self.book.known_spelling("  outotz ls-k D8-0 "), "Outotz LS-K d8-0")
        self.assertEqual(self.book.known_spelling("Nowhere"), "")


class ArrivalTests(Base):
    def test_nothing_happens_without_an_active_expedition(self):
        self.trip()
        self.assertIsNone(self.book.on_arrival("Sol", is_jump=True, jump_distance=5))

    def test_an_arrival_ticks_the_stop_and_counts_the_jump(self):
        e = self.trip()
        self.book.start(e.id)
        arrival = self.book.on_arrival("sol", stamp="2026-10-14T01:02:03Z", is_jump=True, jump_distance=12.5)
        self.assertEqual((arrival.stop.system, arrival.stop.visited, arrival.completed), ("Sol", "2026-10-14T01:02:03Z", False))
        self.assertEqual((e.jumps, e.light_years, e.visited_count), (1, 12.5, 1))
        self.assertEqual(e.next_stop().system, "Sagittarius A*")

    def test_a_system_that_is_not_a_stop_still_counts_as_a_jump(self):
        e = self.trip()
        self.book.start(e.id)
        arrival = self.book.on_arrival("Nowhere", is_jump=True, jump_distance=7)
        self.assertIsNone(arrival.stop)
        self.assertEqual((e.jumps, e.light_years, e.visited_count), (1, 7.0, 0))

    def test_arriving_out_of_order_is_recorded(self):
        e = self.trip()
        self.book.start(e.id)
        self.book.on_arrival("Colonia", is_jump=True)
        self.assertEqual([s.is_visited for s in e.stops], [False, False, True])
        self.assertEqual(e.next_stop().system, "Sol")

    def test_a_system_listed_twice_is_ticked_once_per_arrival(self):
        e = self.trip(systems=("Sol", "Away", "Sol"))
        self.book.start(e.id)
        self.book.on_arrival("Sol", is_jump=True)
        self.assertEqual([s.is_visited for s in e.stops], [True, False, False])
        self.book.on_arrival("Sol", is_jump=True)
        self.assertEqual([s.is_visited for s in e.stops], [True, False, True])

    def test_the_last_stop_says_so_and_the_expedition_stays_active(self):
        e = self.trip(systems=("A", "B"))
        self.book.start(e.id)
        self.assertFalse(self.book.on_arrival("A", is_jump=True).completed)
        done = self.book.on_arrival("B", is_jump=True)
        self.assertTrue(done.completed)
        self.assertTrue(e.all_visited)
        self.assertEqual(e.status, X.ACTIVE)

    def test_a_login_in_a_stop_ticks_it_but_is_not_a_jump(self):
        e = self.trip()
        self.book.start(e.id)
        self.book.on_arrival("Sol")
        self.assertEqual((e.visited_count, e.jumps), (1, 0))

    def test_a_paused_expedition_collects_nothing(self):
        e = self.trip()
        self.book.start(e.id)
        self.book.pause(e.id)
        self.assertIsNone(self.book.on_arrival("Sol", is_jump=True, jump_distance=5))
        self.assertEqual((e.jumps, e.visited_count), (0, 0))

    def test_odd_jump_distances_are_ignored(self):
        e = self.trip()
        self.book.start(e.id)
        for bad in (None, -3, 0, float("nan"), float("inf"), "5", True):
            self.book.on_arrival("Nowhere", is_jump=True, jump_distance=bad)
        self.assertEqual((e.jumps, e.light_years), (7, 0.0))

    def test_a_bad_time_stamp_falls_back_to_now(self):
        e = self.trip()
        self.book.start(e.id)
        self.assertTrue(self.book.on_arrival("Sol", stamp="garbage").stop.visited.startswith("2026-10-13"))


class ProgressTests(Base):
    def test_distance_to_the_next_stop(self):
        e = self.book.create("D")
        self.book.add_stop(e.id, "A", xyz=(3.0, 4.0, 0.0))
        self.assertEqual(self.book.distance_to_next(e, (0.0, 0.0, 0.0)), 5.0)
        self.assertIsNone(self.book.distance_to_next(e, None))
        self.book.add_stop(e.id, "B")
        self.book.set_visited(e.id, e.stops[0].id, True)
        self.assertIsNone(self.book.distance_to_next(e, (0.0, 0.0, 0.0)))          # the next stop has no position

    def test_elapsed_text(self):
        self.assertEqual(X.elapsed_text("2026-10-13T12:00:00Z", "2026-10-13T12:40:00Z"), "40 min")
        self.assertEqual(X.elapsed_text("2026-10-13T12:00:00Z", "2026-10-13T17:12:00Z"), "5 h 12 min")
        self.assertEqual(X.elapsed_text("2026-10-10T12:00:00Z", "2026-10-13T16:00:00Z"), "3 d 4 h")
        self.assertEqual(X.elapsed_text("garbage", "2026-10-13T16:00:00Z"), "")
        self.assertEqual(X.elapsed_text(""), "")


class ExportTests(Base):
    def test_csv_round_trips_system_body_and_note(self):
        e = self.book.create("Out")
        self.book.add_stop(e.id, "Sol", "Earth", 'Say "hi", then go')
        self.book.add_stop(e.id, "Colonia")
        rows = X.ExpeditionBook.parse_csv_stops(X.ExpeditionBook.to_csv(e))
        self.assertEqual(rows, [("Sol", "Earth", 'Say "hi", then go'), ("Colonia", "", "")])

    def test_a_one_column_file_and_a_header_and_blanks_are_read(self):
        text = "﻿System\nSol\n\n  \nColonia\n,ignored\n"
        self.assertEqual(X.ExpeditionBook.parse_csv_stops(text), [("Sol", "", ""), ("Colonia", "", "")])

    def test_text_shows_progress_and_notes(self):
        e = self.book.create("T")
        self.book.add_stop(e.id, "Sol", "Earth", "line one\nline two")
        self.book.add_stop(e.id, "Colonia")
        self.book.set_visited(e.id, e.stops[0].id, True)
        self.assertEqual(X.ExpeditionBook.to_text(e).splitlines(),
                         ["T (planned): 1 of 2 stops", "1. [x] Sol / Earth - line one line two", "2. [ ] Colonia"])

    def test_the_game_plotted_route_is_read(self):
        data = {"Route": [{"StarSystem": "Sol", "StarPos": [0, 0, 0]}, {"StarSystem": "Alpha", "StarPos": [1, 2, 3]}, {"StarSystem": "Nopos"}]}
        self.assertEqual(X.ExpeditionBook.parse_navroute(data, skip_system="sol"), [("Alpha", (1.0, 2.0, 3.0)), ("Nopos", None)])


class SavingTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.tmp.cleanup()

    def path(self):
        return os.path.join(self.tmp.name, X.STATE_FILENAME)

    def test_a_plan_and_its_progress_survive_a_restart(self):
        book = make(self.tmp.name)
        e = book.create("Colonia run")
        book.add_stop(e.id, "Sol", "Earth", "Start", xyz=(0.0, 0.0, 0.0))
        book.add_stop(e.id, "Colonia")
        book.start(e.id)
        book.on_arrival("Sol", stamp="2026-10-14T01:00:00Z", is_jump=True, jump_distance=8.25)
        book.flush()
        again = make(self.tmp.name)
        loaded = again.active()
        self.assertEqual((loaded.name, loaded.jumps, loaded.light_years, loaded.visited_count), ("Colonia run", 1, 8.25, 1))
        self.assertEqual((loaded.stops[0].body, loaded.stops[0].note, loaded.stops[0].xyz, loaded.stops[0].visited),
                         ("Earth", "Start", (0.0, 0.0, 0.0), "2026-10-14T01:00:00Z"))

    def test_a_tick_is_saved_at_once_but_jump_totals_wait_for_flush(self):
        mono = Mono()
        book = make(self.tmp.name, mono=mono)
        e = book.create("E")
        book.add_stop(e.id, "A")
        book.start(e.id)
        book.on_arrival("Away", is_jump=True, jump_distance=10)                       # totals only: throttled
        self.assertEqual(make(self.tmp.name).active().jumps, 0)
        book.on_arrival("A", is_jump=True, jump_distance=10)                          # a tick: saved with the totals
        self.assertEqual(make(self.tmp.name).active().jumps, 2)
        book.on_arrival("Away", is_jump=True, jump_distance=10)
        book.flush()
        self.assertEqual(make(self.tmp.name).active().jumps, 3)

    def test_changing_commander_writes_the_waiting_change_first(self):
        book = make(self.tmp.name)
        e = book.create("E")
        book.add_stop(e.id, "A")
        book.start(e.id)
        book.on_arrival("Away", is_jump=True, jump_distance=4)
        book.on_arrival("Away", is_jump=True, jump_distance=4)
        book.set_commander("Other Cmdr")
        self.assertEqual(book.expeditions(), [])
        self.assertEqual(make(self.tmp.name).active().jumps, 2)

    def test_commanders_do_not_see_each_others_expeditions(self):
        make(self.tmp.name, "Bocheaux").create("Mine")
        self.assertEqual(make(self.tmp.name, "Someone Else").expeditions(), [])
        self.assertEqual([e.name for e in make(self.tmp.name, "BOCHEAUX").expeditions()], ["Mine"])

    def test_no_commander_name_is_in_a_file_name(self):
        make(self.tmp.name).create("E")
        self.assertEqual(os.listdir(self.tmp.name), [X.STATE_FILENAME])

    def test_a_damaged_file_gives_no_expeditions(self):
        with open(self.path(), "w", encoding="utf-8") as handle:
            handle.write("{not json")
        self.assertEqual(make(self.tmp.name).expeditions(), [])

    def test_damaged_entries_are_dropped_two_active_become_one_and_values_are_pulled_into_range(self):
        book = make(self.tmp.name)
        for name in ("A", "B", "C"):
            e = book.create(name)
            book.add_stop(e.id, "Sol")
        with open(self.path(), encoding="utf-8") as handle:
            raw = json.load(handle)
        items = raw["commanders"]["bocheaux"]["data"]["expeditions"]
        items[0]["status"] = items[1]["status"] = "active"
        items[2]["status"] = "nonsense"
        items[2]["jumps"], items[2]["light_years"] = -5, "far"
        items[2]["stops"] += [5, {"system": ""}, {"system": "Ok", "xyz": [1, 2]}, {"system": "Ok2", "xyz": [1, 2, "x"]}]
        items += [5, {"id": "x"}, {"id": "dup", "name": "D"}, {"id": items[0]["id"], "name": "Duplicate id"}]
        with open(self.path(), "w", encoding="utf-8") as handle:
            json.dump(raw, handle)
        again = make(self.tmp.name)
        self.assertEqual([e.name for e in again.expeditions() if e.name in ("A", "B", "C", "D")].__len__(), 4)
        self.assertEqual(sorted(e.status for e in again.expeditions() if e.name in ("A", "B")), ["active", "paused"])
        c = next(e for e in again.expeditions() if e.name == "C")
        self.assertEqual((c.status, c.jumps, c.light_years), (X.PLANNED, 0, 0.0))
        self.assertEqual([(s.system, s.xyz) for s in c.stops], [("Sol", None), ("Ok", None), ("Ok2", None)])
        self.assertNotIn("Duplicate id", [e.name for e in again.expeditions()])


if __name__ == "__main__":
    unittest.main()
