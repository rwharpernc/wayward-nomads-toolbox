"""Spansh's Road to Riches and Expressway to Exomastery planners (spansh_planners.py): the form sent, the answer turned into expedition stops, and
the wait for a job, with the network replaced. The sample answers are shaped like real ones from spansh.co.uk (2026-10-13)."""
from __future__ import annotations

import os
import sys
import threading
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from plugin import spansh_planners as S  # noqa: E402

EXO_RESULT = [
    {"bodies": [], "id64": "10477373803", "jumps": 1, "name": "Sol", "x": 0, "y": 0, "z": 0},
    {"bodies": [
        {"distance_to_arrival": 156.29, "estimated_mapping_value": 2221, "estimated_scan_value": 500, "id64": "1", "landmark_value": 7774700,
         "landmarks": [{"count": 82, "subtype": "Bacterium Volu", "type": "Bacterium", "value": 7774700}],
         "name": "Sesuang A 3", "subtype": "Icy body", "type": "Planet"},
        {"distance_to_arrival": 400.0, "landmark_value": 1200000,
         "landmarks": [{"count": 2, "subtype": "Stratum Tectonicas", "type": "Stratum", "value": 600000},
                       {"count": 1, "subtype": "Fumerola Aquatis", "type": "Fumerola", "value": 400000},
                       {"count": 1, "subtype": "Bacterium Nebulus", "type": "Bacterium", "value": 200000}],
         "name": "Sesuang A 6", "subtype": "Icy body", "type": "Planet"}],
     "id64": "2", "jumps": 2, "name": "Sesuang", "x": 45.6875, "y": -3.21875, "z": 22.125},
    {"bodies": [{"distance_to_arrival": 10.0, "landmark_value": 500000, "landmarks": [], "name": "Kushen 3", "subtype": "Icy body"}],
     "id64": "3", "jumps": 1, "name": "Kushen", "x": 26.46875, "y": -8.5, "z": 7.84375},
]

RICHES_RESULT = [
    {"bodies": [], "jumps": 1, "name": "Sol", "x": 0, "y": 0, "z": 0},
    {"bodies": [{"name": "Eme A 1", "subtype": "Earth-like world", "is_terraformable": False, "distance_to_arrival": 12.5,
                 "estimated_scan_value": 270000, "estimated_mapping_value": 1100000},
                {"name": "Eme A 2", "subtype": "High metal content world", "is_terraformable": True, "distance_to_arrival": 90,
                 "estimated_scan_value": 90000, "estimated_mapping_value": 300000}],
     "jumps": 3, "name": "Eme", "x": 33.7, "y": 26.2, "z": 4.0},
]


class FormTests(unittest.TestCase):
    def test_riches_form_has_the_fields_spansh_expects(self):
        form = S.build_form(S.PlanQuery(S.RICHES, "  Sol ", 38.5, "Colonia", 30, 50, 20000, 250000, True, True, False))
        self.assertEqual(form, {"from": "Sol", "to": "Colonia", "range": "38.5", "radius": "30", "max_results": "50", "max_distance": "20000",
                                "min_value": "250000", "avoid_thargoids": "1", "loop": "0", "use_mapping_value": "1"})

    def test_exobiology_form_has_no_mapping_field_and_no_destination_when_empty(self):
        form = S.build_form(S.PlanQuery(S.EXOBIOLOGY, "Sol"))
        self.assertNotIn("use_mapping_value", form)
        self.assertNotIn("to", form)
        self.assertEqual(form["min_value"], "10000000")        # the planner's own starting value
        self.assertEqual(S.build_form(S.PlanQuery(S.RICHES, "Sol"))["min_value"], "100000")

    def test_numbers_are_kept_inside_sensible_limits(self):
        form = S.build_form(S.PlanQuery(S.RICHES, "Sol", jump_range=-3, radius=10 ** 9, max_results=0, max_distance=10 ** 12))
        self.assertEqual((form["range"], form["radius"], form["max_results"], form["max_distance"]), ("1", "1000", "1", "5000000"))

    def test_a_start_is_needed_and_the_kind_is_checked(self):
        with self.assertRaises(S.RouteSearchError):
            S.build_form(S.PlanQuery(S.RICHES, "   "))
        with self.assertRaises(S.RouteSearchError):
            S.build_form(S.PlanQuery("nonsense", "Sol"))

    def test_the_expedition_is_named_after_the_planner_and_the_start(self):
        self.assertEqual(S.default_name(S.PlanQuery(S.RICHES, " Sol ")), "Road to Riches from Sol")
        self.assertEqual(S.default_name(S.PlanQuery(S.EXOBIOLOGY, "Sol")), "Expressway to Exomastery from Sol")

    def test_credits_are_written_short(self):
        self.assertEqual([S.credits(v) for v in (900, 12345, 45600, 7774700, "x")], ["900 cr", "12.3k cr", "45.6k cr", "7.8M cr", ""])


class ParseTests(unittest.TestCase):
    def test_the_start_system_is_left_out_and_positions_are_kept(self):
        stops = S.parse_stops(S.EXOBIOLOGY, EXO_RESULT, "Sol")
        self.assertEqual([s.system for s in stops], ["Sesuang", "Kushen"])
        self.assertEqual(stops[0].xyz, (45.6875, -3.21875, 22.125))

    def test_the_most_valuable_body_is_the_stop_body_and_the_note_lists_the_best_few(self):
        stop = S.parse_stops(S.EXOBIOLOGY, EXO_RESULT, "Sol")[0]
        self.assertEqual(stop.body, "Sesuang A 3")
        self.assertTrue(stop.note.startswith("Sesuang A 3 (Icy body): Bacterium Volu x82 (7.8M cr)"), stop.note)
        self.assertIn("Sesuang A 6 (Icy body): Stratum Tectonicas x2 (600.0k cr), Fumerola Aquatis (400.0k cr), +1 more", stop.note)

    def test_a_riches_note_gives_scan_and_map_values_and_terraformable(self):
        stop = S.parse_stops(S.RICHES, RICHES_RESULT, "Sol")[0]
        self.assertEqual((stop.system, stop.body), ("Eme", "Eme A 1"))
        self.assertIn("Eme A 1 (Earth-like world, scan 270.0k cr / map 1.1M cr)", stop.note)
        self.assertIn("Eme A 2 (High metal content world, terraformable, scan 90.0k cr / map 300.0k cr)", stop.note)

    def test_a_system_with_no_bodies_that_is_not_the_start_is_kept(self):
        stops = S.parse_stops(S.RICHES, [{"name": "Somewhere", "bodies": [], "jumps": 1}], "Sol")
        self.assertEqual([s.system for s in stops], ["Somewhere"])
        self.assertIsNone(stops[0].xyz)

    def test_damaged_entries_are_skipped_not_fatal(self):
        stops = S.parse_stops(S.RICHES, [None, 5, {"name": ""}, {"name": "Ok", "bodies": [None, {"name": "B"}]}, {"bodies": []}], "")
        self.assertEqual([s.system for s in stops], ["Ok"])
        self.assertEqual(S.parse_stops(S.RICHES, "nonsense", ""), [])

    def test_a_long_note_is_cut_to_what_a_stop_can_hold(self):
        bodies = [{"name": f"Body {i} " + "x" * 80, "subtype": "Icy body", "estimated_scan_value": 1000 + i} for i in range(9)]
        stop = S.parse_stops(S.RICHES, [{"name": "Big", "bodies": bodies}], "")[0]
        self.assertLessEqual(len(stop.note), S.NOTE_CHARS)


class PlanTests(unittest.TestCase):
    def run_plan(self, replies, query=None, **kw):
        answers = iter(replies)
        with mock.patch.object(S, "_request", side_effect=lambda *a, **k: next(answers)) as request, \
                mock.patch.object(S, "POLL_INTERVAL_S", 0), mock.patch.object(S.time, "sleep"):
            return S.plan(query or S.PlanQuery(S.EXOBIOLOGY, "Sol"), **kw), request

    def test_it_submits_waits_and_returns_the_stops(self):
        states = []
        stops, request = self.run_plan([{"job": "J1", "status": "queued"}, {"state": "queued", "status": "queued"},
                                        {"state": "completed", "status": "ok", "result": EXO_RESULT}], on_state=states.append)
        self.assertEqual([s.system for s in stops], ["Sesuang", "Kushen"])
        first = request.call_args_list[0]
        self.assertEqual(first.args[0], "https://spansh.co.uk/api/exobiology/route")
        self.assertIn(b"from=Sol", first.args[1])
        self.assertEqual(request.call_args_list[1].args[0], "https://spansh.co.uk/api/results/J1")
        self.assertIn("Waiting in Spansh's queue.", states)

    def test_riches_goes_to_its_own_endpoint(self):
        _stops, request = self.run_plan([{"job": "J"}, {"state": "completed", "result": []}], S.PlanQuery(S.RICHES, "Sol"))
        self.assertEqual(request.call_args_list[0].args[0], "https://spansh.co.uk/api/riches/route")

    def test_nothing_worth_visiting_is_an_empty_list_not_an_error(self):
        stops, _ = self.run_plan([{"job": "J"}, {"state": "completed", "status": "ok", "result": EXO_RESULT[:1]}])
        self.assertEqual(stops, [])

    def test_a_refusal_a_failed_job_and_a_missing_job_are_errors_with_spanshs_words(self):
        with self.assertRaisesRegex(S.RouteSearchError, "Could not find system"):
            self.run_plan([{"error": "Could not find system"}])
        with self.assertRaisesRegex(S.RouteSearchError, "no route"):
            self.run_plan([{"job": "J"}, {"state": "failed", "error": "no route"}])
        with self.assertRaisesRegex(S.RouteSearchError, "bad start"):
            self.run_plan([{"job": "J"}, {"state": "completed", "status": "error", "error": "bad start"}])

    def test_cancelling_stops_the_wait(self):
        cancel = threading.Event()
        cancel.set()
        with self.assertRaisesRegex(S.RouteSearchError, "Cancelled"):
            self.run_plan([{"job": "J"}], cancel=cancel)

    def test_it_gives_up_after_the_longest_wait(self):
        with mock.patch.object(S, "MAX_WAIT_S", -1):
            with self.assertRaisesRegex(S.RouteSearchError, "took too long"):
                self.run_plan([{"job": "J"}])


if __name__ == "__main__":
    unittest.main()
