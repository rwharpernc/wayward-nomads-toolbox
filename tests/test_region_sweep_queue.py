"""
Unit tests for plugin/region_sweep_queue.py.

region_sweep_queue.py (and boxel_walker.py, one instance of which it wraps
per queued cube) both do a hard `from config import appname` - real EDMC's
own `config` module, unlike waypoint_route.py/survey_log.py, which fall
back to a plain string when `config` isn't importable. This has been a
documented gap (see docs/BOXEL_SURVEY_TECH_SPEC.md §9): neither module has
ever had a standalone test for exactly this reason. Rather than changing
production code's import behavior just to make it testable, this file
installs a minimal fake `config` module into sys.modules before importing -
enough to satisfy `from config import appname`, nothing else EDMC-specific
is touched or needed by either module's actual logic. Run with:
    python -m unittest discover -s tests
"""

from __future__ import annotations

import os
import sys
import types
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

if "config" not in sys.modules:
    _fake_config = types.ModuleType("config")
    _fake_config.appname = "EDMarketConnector"
    sys.modules["config"] = _fake_config

from plugin.region_sweep_queue import (  # noqa: E402
    CubeEntry, RegionSweepQueue, RegionSweepSnapshot, cube_key,
)


class CubeKeyTests(unittest.TestCase):
    def test_cube_key_format(self):
        self.assertEqual(cube_key("Outotz", "LS-K", "d"), "Outotz|LS-K|d")


class AddCubeTests(unittest.TestCase):
    def test_add_cube_creates_entry_seeded_at_zero(self):
        q = RegionSweepQueue()
        entry = q.add_cube("Outotz", "LS-K", "d")
        self.assertEqual(entry.sector, "Outotz")
        self.assertEqual(entry.walker.current, "Outotz LS-K d0")

    def test_add_cube_is_idempotent(self):
        q = RegionSweepQueue()
        first = q.add_cube("Outotz", "LS-K", "d")
        second = q.add_cube("Outotz", "LS-K", "d")
        self.assertIs(first, second)
        self.assertEqual(len(q.cubes), 1)

    def test_add_cube_sets_current_when_first(self):
        q = RegionSweepQueue()
        entry = q.add_cube("Outotz", "LS-K", "d")
        self.assertIs(q.current, entry)

    def test_add_cube_from_system_parses_and_adds(self):
        q = RegionSweepQueue()
        entry = q.add_cube_from_system("Outotz LS-K d8-0")
        self.assertIsNotNone(entry)
        self.assertEqual(entry.cube_id, "LS-K")
        self.assertEqual(entry.mass_code, "d")

    def test_add_cube_from_system_rejects_non_procedural_name(self):
        q = RegionSweepQueue()
        self.assertIsNone(q.add_cube_from_system("Sol"))


class RemoveCubeTests(unittest.TestCase):
    def test_remove_cube_returns_false_when_absent(self):
        q = RegionSweepQueue()
        self.assertFalse(q.remove_cube("Outotz", "LS-K", "d"))

    def test_remove_current_cube_advances_current_index(self):
        q = RegionSweepQueue()
        q.add_cube("Outotz", "LS-K", "d")
        second = q.add_cube("Outotz", "LS-K", "e")
        q.set_current("Outotz", "LS-K", "d")
        self.assertTrue(q.remove_cube("Outotz", "LS-K", "d"))
        self.assertIs(q.current, second)

    def test_remove_last_cube_clears_current(self):
        q = RegionSweepQueue()
        q.add_cube("Outotz", "LS-K", "d")
        q.remove_cube("Outotz", "LS-K", "d")
        self.assertIsNone(q.current)


class MergeKnownSystemsTests(unittest.TestCase):
    def test_merge_adds_cube_and_systems(self):
        q = RegionSweepQueue()
        entry = q.merge_known_systems("Outotz", "LS-K", "d", ["Outotz LS-K d8-0", "Outotz LS-K d8-5"])
        self.assertEqual(entry.known_count, 2)
        self.assertFalse(entry.systems["Outotz LS-K d8-0"])

    def test_merge_reseeds_untouched_walker_to_lowest_known(self):
        q = RegionSweepQueue()
        entry = q.merge_known_systems(
            "Outotz", "LS-K", "d", ["Outotz LS-K d8-9", "Outotz LS-K d8-2", "Outotz LS-K d8-5"],
        )
        self.assertEqual(entry.walker.current, "Outotz LS-K d8-2")

    def test_merge_does_not_reseed_once_walker_has_moved(self):
        q = RegionSweepQueue()
        entry = q.add_cube("Outotz", "LS-K", "d")
        entry.walker.advance(skip_visited=False)  # moves off the synthetic d0 seed
        moved_target = entry.walker.current
        q.merge_known_systems("Outotz", "LS-K", "d", ["Outotz LS-K d8-9"])
        self.assertEqual(entry.walker.current, moved_target)

    def test_merge_never_overwrites_true_completion_with_false(self):
        q = RegionSweepQueue()
        q.merge_known_systems("Outotz", "LS-K", "d", ["Outotz LS-K d8-0"])
        q.mark_system_complete("Outotz LS-K d8-0")
        q.merge_known_systems("Outotz", "LS-K", "d", ["Outotz LS-K d8-0"])
        entry = q.current
        self.assertTrue(entry.systems["Outotz LS-K d8-0"])


class CompletionTests(unittest.TestCase):
    def test_cube_complete_when_marked_empty(self):
        entry = CubeEntry(sector="Outotz", cube_id="LS-K", mass_code="d")
        entry.empty = True
        self.assertTrue(entry.complete)

    def test_cube_complete_when_all_known_systems_complete(self):
        entry = CubeEntry(sector="Outotz", cube_id="LS-K", mass_code="d")
        entry.systems = {"A": True, "B": True}
        self.assertTrue(entry.complete)

    def test_cube_not_complete_with_no_known_systems(self):
        entry = CubeEntry(sector="Outotz", cube_id="LS-K", mass_code="d")
        self.assertFalse(entry.complete)

    def test_cube_not_complete_with_partial_progress(self):
        entry = CubeEntry(sector="Outotz", cube_id="LS-K", mass_code="d")
        entry.systems = {"A": True, "B": False}
        self.assertFalse(entry.complete)

    def test_mark_system_complete_implies_visited(self):
        q = RegionSweepQueue()
        q.add_cube("Outotz", "LS-K", "d")
        q.mark_system_complete("Outotz LS-K d8-0")
        entry = q.current
        self.assertTrue(entry.systems["Outotz LS-K d8-0"])
        self.assertIn("Outotz LS-K d8-0", entry.walker.snapshot().visited)

    def test_mark_visited_does_not_mark_complete(self):
        q = RegionSweepQueue()
        q.add_cube("Outotz", "LS-K", "d")
        q.mark_visited("Outotz LS-K d8-0")
        entry = q.current
        self.assertFalse(entry.systems["Outotz LS-K d8-0"])

    def test_mark_visited_noop_for_unqueued_cube(self):
        q = RegionSweepQueue()
        q.mark_visited("Outotz LS-K d8-0")  # procedural-shaped, but no cube queued for it
        self.assertIsNone(q.current)

    def test_mark_visited_noop_for_non_procedural_name(self):
        q = RegionSweepQueue()
        q.mark_visited("Sol")
        self.assertIsNone(q.current)


class AdvanceCubeTests(unittest.TestCase):
    def test_advance_cube_skips_complete_cubes(self):
        q = RegionSweepQueue()
        first = q.add_cube("Outotz", "LS-K", "d")
        first.empty = True
        second = q.add_cube("Outotz", "LS-K", "e")
        q.set_current("Outotz", "LS-K", "d")
        result = q.advance_cube()
        self.assertIs(result, second)

    def test_advance_cube_wraps_around(self):
        q = RegionSweepQueue()
        first = q.add_cube("Outotz", "LS-K", "d")
        second = q.add_cube("Outotz", "LS-K", "e")
        second.empty = True
        q.set_current("Outotz", "LS-K", "e")
        result = q.advance_cube()
        self.assertIs(result, first)

    def test_advance_cube_returns_none_when_all_complete(self):
        q = RegionSweepQueue()
        entry = q.add_cube("Outotz", "LS-K", "d")
        entry.empty = True
        self.assertIsNone(q.advance_cube())

    def test_advance_cube_returns_none_when_queue_empty(self):
        q = RegionSweepQueue()
        self.assertIsNone(q.advance_cube())


class OnJumpTests(unittest.TestCase):
    def test_on_jump_advances_within_cube(self):
        q = RegionSweepQueue()
        entry = q.add_cube("Outotz", "LS-K", "d")
        target = entry.walker.current  # "Outotz LS-K d0"
        next_target = q.on_jump(target)
        self.assertEqual(next_target, "Outotz LS-K d1")

    def test_on_jump_off_target_returns_none_but_marks_visited(self):
        q = RegionSweepQueue()
        q.add_cube("Outotz", "LS-K", "d")
        result = q.on_jump("Outotz LS-K d99")
        self.assertIsNone(result)
        self.assertIn("Outotz LS-K d99", q.current.walker.snapshot().visited)

    def test_on_jump_with_complete_false_only_marks_visited(self):
        q = RegionSweepQueue()
        entry = q.add_cube("Outotz", "LS-K", "d")
        entry.systems["Outotz LS-K d0"] = False
        target = entry.walker.current
        q.on_jump(target, complete=False)
        self.assertFalse(entry.systems[target])

    def test_on_jump_advances_to_next_cube_once_current_completes(self):
        q = RegionSweepQueue()
        q.merge_known_systems("Outotz", "LS-K", "d", ["Outotz LS-K d0"])
        second = q.add_cube("Outotz", "LS-K", "e")
        q.set_current("Outotz", "LS-K", "d")
        next_target = q.on_jump("Outotz LS-K d0")
        self.assertEqual(next_target, second.walker.current)
        self.assertIs(q.current, second)

    def test_on_jump_returns_none_when_no_current_cube(self):
        q = RegionSweepQueue()
        self.assertIsNone(q.on_jump("Outotz LS-K d0"))


class StatsTests(unittest.TestCase):
    def test_stats_aggregate_across_cubes(self):
        q = RegionSweepQueue()
        q.merge_known_systems("Outotz", "LS-K", "d", ["Outotz LS-K d8-0", "Outotz LS-K d8-1"])
        q.merge_known_systems("Outotz", "LS-K", "e", ["Outotz LS-K e8-0"])
        q.mark_system_complete("Outotz LS-K d8-0")
        self.assertEqual(q.systems_known, 3)
        self.assertEqual(q.systems_complete, 1)
        self.assertEqual(q.cubes_complete, 0)

    def test_cubes_complete_counts_empty_cubes(self):
        q = RegionSweepQueue()
        entry = q.add_cube("Outotz", "LS-K", "d")
        entry.empty = True
        q.add_cube("Outotz", "LS-K", "e")
        self.assertEqual(q.cubes_complete, 1)


class PersistenceTests(unittest.TestCase):
    def test_snapshot_restore_round_trip(self):
        q = RegionSweepQueue()
        q.merge_known_systems("Outotz", "LS-K", "d", ["Outotz LS-K d8-0", "Outotz LS-K d8-5"])
        q.mark_system_complete("Outotz LS-K d8-0")
        q.add_cube("Outotz", "LS-K", "e")
        q.set_current("Outotz", "LS-K", "e")
        snap = q.snapshot()

        restored = RegionSweepQueue()
        restored.restore(snap)

        self.assertEqual(len(restored.cubes), 2)
        self.assertEqual(restored.current.mass_code, "e")
        d_cube = next(c for c in restored.cubes if c.mass_code == "d")
        self.assertTrue(d_cube.systems["Outotz LS-K d8-0"])
        self.assertFalse(d_cube.systems["Outotz LS-K d8-5"])

    def test_restore_skips_malformed_entries(self):
        snap = RegionSweepSnapshot(cubes=[{"sector": "Outotz"}], current_index=0)  # missing cube_id/mass_code
        q = RegionSweepQueue()
        q.restore(snap)
        self.assertEqual(len(q.cubes), 0)
        self.assertIsNone(q.current)

    def test_restore_reseeds_walker_when_current_missing(self):
        snap = RegionSweepSnapshot(
            cubes=[{"sector": "Outotz", "cube_id": "LS-K", "mass_code": "d", "systems": {}, "empty": False}],
            current_index=0,
        )
        q = RegionSweepQueue()
        q.restore(snap)
        self.assertEqual(q.current.walker.current, "Outotz LS-K d0")


if __name__ == "__main__":
    unittest.main()
