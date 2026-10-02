"""
Unit tests for plugin/waypoint_route.py.

Pure logic tests — no EDMC runtime needed (waypoint_route.py falls back to
a plain appname when `config` isn't importable — see its own module
docstring). Run with:
    python -m unittest discover -s tests
"""

from __future__ import annotations

import csv
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from plugin.waypoint_route import WaypointRoute  # noqa: E402


class AddRemoveMoveTests(unittest.TestCase):
    def test_add_is_case_insensitive_idempotent(self) -> None:
        route = WaypointRoute()
        route.add("Sol")
        route.add("sol")
        self.assertEqual(len(route.waypoints), 1)

    def test_add_many_counts_only_new(self) -> None:
        route = WaypointRoute()
        route.add("Sol")
        added = route.add_many(["Sol", "Colonia", "Deciat"])
        self.assertEqual(added, 2)
        self.assertEqual(len(route.waypoints), 3)

    def test_remove_missing_returns_false(self) -> None:
        route = WaypointRoute()
        self.assertFalse(route.remove("Nowhere"))

    def test_move_swaps_neighbors_and_respects_bounds(self) -> None:
        route = WaypointRoute()
        route.add_many(["A", "B", "C"])
        self.assertTrue(route.move("B", -1))
        self.assertEqual([wp.name for wp in route.waypoints], ["B", "A", "C"])
        self.assertFalse(route.move("B", -1))  # already at the start
        self.assertFalse(route.move("C", 1))  # already at the end


class TargetingTests(unittest.TestCase):
    def test_current_target_is_first_unvisited(self) -> None:
        route = WaypointRoute()
        route.add_many(["A", "B", "C"])
        self.assertEqual(route.current_target().name, "A")
        route.mark_visited("A")
        self.assertEqual(route.current_target().name, "B")

    def test_on_jump_marks_visited_and_returns_next_target(self) -> None:
        route = WaypointRoute()
        route.add_many(["A", "B", "C"])
        next_target = route.on_jump("A")
        self.assertEqual(next_target, "B")
        self.assertTrue(route.waypoints[0].visited)

    def test_on_jump_out_of_order_still_marks_visited(self) -> None:
        route = WaypointRoute()
        route.add_many(["A", "B", "C"])
        route.on_jump("C")
        self.assertTrue(route.waypoints[2].visited)
        # Current target is still A (first unvisited in list order) - C
        # was reached out of order, not "next".
        self.assertEqual(route.current_target().name, "A")

    def test_current_target_none_when_all_visited(self) -> None:
        route = WaypointRoute()
        route.add("A")
        route.on_jump("A")
        self.assertIsNone(route.current_target())


class NearestNeighborTests(unittest.TestCase):
    def test_orders_by_greedy_nearest_neighbor(self) -> None:
        route = WaypointRoute()
        route.add_many(["Far", "Near", "Mid"])
        route.set_coords("Far", 100.0, 0.0, 0.0)
        route.set_coords("Near", 1.0, 0.0, 0.0)
        route.set_coords("Mid", 10.0, 0.0, 0.0)

        count = route.reorder_nearest_neighbor((0.0, 0.0, 0.0))
        self.assertEqual(count, 3)
        self.assertEqual([wp.name for wp in route.waypoints], ["Near", "Mid", "Far"])

    def test_unresolved_waypoints_kept_and_appended_after_ordered(self) -> None:
        route = WaypointRoute()
        route.add_many(["Near", "NoCoords", "Far"])
        route.set_coords("Near", 1.0, 0.0, 0.0)
        route.set_coords("Far", 100.0, 0.0, 0.0)
        # "NoCoords" never gets set_coords() called - EDSM couldn't locate it.

        count = route.reorder_nearest_neighbor((0.0, 0.0, 0.0))
        self.assertEqual(count, 2)  # only the resolved ones were reordered
        names = [wp.name for wp in route.waypoints]
        self.assertEqual(names, ["Near", "Far", "NoCoords"])

    def test_visited_waypoints_are_never_reordered_or_dropped(self) -> None:
        route = WaypointRoute()
        route.add_many(["Done", "Far", "Near"])
        route.mark_visited("Done")
        route.set_coords("Far", 100.0, 0.0, 0.0)
        route.set_coords("Near", 1.0, 0.0, 0.0)

        route.reorder_nearest_neighbor((0.0, 0.0, 0.0))
        names = [wp.name for wp in route.waypoints]
        # Visited stays first (untouched), then the reordered unvisited pair.
        self.assertEqual(names, ["Done", "Near", "Far"])
        self.assertTrue(route.waypoints[0].visited)


class CsvImportTests(unittest.TestCase):
    def test_parses_names_and_skips_header_and_blank_rows(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "waypoints.csv")
            with open(path, "w", newline="", encoding="utf-8") as fh:
                writer = csv.writer(fh)
                writer.writerow(["System"])
                writer.writerow(["Sol"])
                writer.writerow([])
                writer.writerow(["  Colonia  "])
                writer.writerow(["Deciat", "extra column ignored"])

            names = WaypointRoute.parse_csv_names(path)
            self.assertEqual(names, ["Sol", "Colonia", "Deciat"])

    def test_no_header_row_still_works(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "waypoints.csv")
            with open(path, "w", newline="", encoding="utf-8") as fh:
                writer = csv.writer(fh)
                writer.writerow(["Sol"])
                writer.writerow(["Colonia"])

            names = WaypointRoute.parse_csv_names(path)
            self.assertEqual(names, ["Sol", "Colonia"])


class PersistenceTests(unittest.TestCase):
    def test_snapshot_restore_round_trip(self) -> None:
        route = WaypointRoute()
        route.add_many(["A", "B"])
        route.set_coords("A", 1.0, 2.0, 3.0)
        route.mark_visited("B")

        snap = route.snapshot()
        restored = WaypointRoute()
        restored.restore(snap)

        self.assertEqual([wp.name for wp in restored.waypoints], ["A", "B"])
        self.assertEqual(restored.waypoints[0].xyz, (1.0, 2.0, 3.0))
        self.assertTrue(restored.waypoints[1].visited)

    def test_restore_skips_malformed_entries(self) -> None:
        route = WaypointRoute()
        route.restore([{"name": "Sol"}, {"missing_name": True}])
        self.assertEqual([wp.name for wp in route.waypoints], ["Sol"])


if __name__ == "__main__":
    unittest.main()
