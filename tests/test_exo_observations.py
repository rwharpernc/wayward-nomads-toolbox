"""
Unit tests for plugin/exo_observations.py: the record of what lived where, kept to check the species prediction over time.

Pure logic, no EDMC runtime. The file is global on purpose (see the module's docstring); one test pins that it names no commander.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from plugin import exo_analysis as A  # noqa: E402
from plugin import exo_observations as E  # noqa: E402
from plugin import organic_scan as scan  # noqa: E402

BACTERIUM = "$Codex_Ent_Bacterial_Genus_Name;"
AURASUS = "$Codex_Ent_Bacterial_01_Name;"        # Rocky body, CarbonDioxide, 0.039-0.608 g, 145-400 K
TUSSOCK = "$Codex_Ent_Tussocks_Genus_Name;"


def conditions(body: str = "Sol 3", **changes) -> scan.BodyConditions:
    values = dict(body_name=body, planet_class="Rocky body", atmosphere="CarbonDioxide", gravity_g=0.2, temperature_k=180.0, pressure_atm=0.05,
                  volcanism="", star_type="K", system_name="Sol", galactic_position=(1.0, 2.0, 3.0), atmosphere_components={"CarbonDioxide": 95.0},
                  materials=("iron", "nickel"), system_body_types=("Rocky body", "Icy body"))
    values.update(changes)
    return scan.BodyConditions(**values)


class RecordTests(unittest.TestCase):
    def setUp(self) -> None:
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        self.book = E.ObservationBook()
        self.book.load(self.dir.name)

    def test_a_find_keeps_the_conditions_the_species_and_what_was_predicted(self) -> None:
        predicted = E.predicted_keys(BACTERIUM, conditions())
        self.assertIn(AURASUS, predicted)
        self.assertTrue(self.book.record(conditions(), [BACTERIUM], BACTERIUM, AURASUS, "Bacterium Aurasus", "Bacterium Aurasus - Teal", predicted,
                                         when="2026-10-17T10:00:00Z"))
        record = self.book.bodies()["Sol|Sol 3"]
        self.assertEqual((record["planet_class"], record["atmosphere"], record["temperature_k"], record["star_type"]), ("Rocky body", "CarbonDioxide", 180.0, "K"))
        self.assertEqual(record["materials"], ["iron", "nickel"])
        self.assertEqual(record["system_body_types"], ["Icy body", "Rocky body"])
        entry = record["species"][BACTERIUM]
        self.assertEqual((entry["species_key"], entry["variant"], entry["predicted"]), (AURASUS, "Bacterium Aurasus - Teal", predicted))
        self.assertEqual(self.book.count(), 1)

    def test_several_genera_on_one_body_share_a_record_and_the_first_seen_time_is_kept(self) -> None:
        self.book.record(conditions(), [BACTERIUM, TUSSOCK], BACTERIUM, AURASUS, "Bacterium Aurasus", None, [AURASUS], when="2026-10-17T10:00:00Z")
        self.book.record(conditions(), [BACTERIUM, TUSSOCK], TUSSOCK, "$Codex_Ent_Tussocks_07_Name;", "Tussock Pennatis", None, [], when="2026-10-17T11:00:00Z")
        self.book.record(conditions(), [BACTERIUM, TUSSOCK], BACTERIUM, AURASUS, "Bacterium Aurasus", "Teal", [AURASUS], when="2026-10-18T09:00:00Z")
        self.assertEqual(len(self.book.bodies()), 1)
        record = self.book.bodies()["Sol|Sol 3"]
        self.assertEqual(set(record["species"]), {BACTERIUM, TUSSOCK})
        self.assertEqual(record["species"][BACTERIUM]["seen"], "2026-10-17T10:00:00Z")      # the first sighting stays
        self.assertEqual(record["species"][BACTERIUM]["variant"], "Teal")                  # a later sample can name the color
        self.assertEqual(record["first_seen"], "2026-10-17T10:00:00Z")
        self.assertEqual(self.book.count(), 2)

    def test_a_find_without_a_body_or_species_is_ignored(self) -> None:
        self.assertFalse(self.book.record(conditions(body=""), [], BACTERIUM, AURASUS, "x", None, []))
        self.assertFalse(self.book.record(conditions(), [], "", AURASUS, "x", None, []))
        self.assertFalse(self.book.record(conditions(), [], BACTERIUM, "", "x", None, []))
        self.assertEqual(self.book.bodies(), {})

    def test_clearing_forgets_every_find_and_review_and_saves_the_empty_file(self) -> None:
        self.book.record(conditions(), [BACTERIUM], BACTERIUM, AURASUS, "Bacterium Aurasus", None, [AURASUS])
        self.book.record(conditions("Sol 4"), [BACTERIUM], BACTERIUM, AURASUS, "Bacterium Aurasus", None, [AURASUS])
        self.book.set_review("Sol|Sol 4", BACTERIUM, "rule", "x")
        self.assertEqual(self.book.clear(), 2)
        self.assertEqual((self.book.count(), self.book.bodies()), (0, {}))
        again = E.ObservationBook()
        again.load(self.dir.name)
        self.assertEqual(again.bodies(), {})
        self.assertEqual(self.book.clear(), 0)

    def test_it_survives_a_restart(self) -> None:
        self.book.record(conditions(), [BACTERIUM], BACTERIUM, AURASUS, "Bacterium Aurasus", None, [AURASUS])
        again = E.ObservationBook()
        again.load(self.dir.name)
        self.assertEqual(again.count(), 1)
        self.assertEqual(again.bodies()["Sol|Sol 3"]["galactic_position"], [1.0, 2.0, 3.0])

    def test_an_unreadable_file_gives_an_empty_book(self) -> None:
        with open(os.path.join(self.dir.name, E.FILENAME), "w", encoding="utf-8") as handle:
            handle.write("{not json")
        broken = E.ObservationBook()
        broken.load(self.dir.name)
        self.assertEqual(broken.bodies(), {})

    def test_the_file_names_no_commander(self) -> None:
        """Global on purpose: nothing in it may say who found what."""
        self.book.record(conditions(), [BACTERIUM], BACTERIUM, AURASUS, "Bacterium Aurasus", None, [AURASUS])
        with open(os.path.join(self.dir.name, E.FILENAME), "r", encoding="utf-8") as handle:
            raw = json.load(handle)
        self.assertEqual(set(raw), {"version", "bodies"})
        keys = set()

        def walk(node) -> None:
            if isinstance(node, dict):
                keys.update(str(k).casefold() for k in node)
                for value in node.values():
                    walk(value)
            elif isinstance(node, list):
                for value in node:
                    walk(value)
        walk(raw)
        self.assertFalse({k for k in keys if "cmdr" in k or "commander" in k})


class BackfillTests(unittest.TestCase):
    def setUp(self) -> None:
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        self.book = E.ObservationBook()
        self.book.load(self.dir.name)

    @staticmethod
    def saved() -> dict:
        from dataclasses import asdict
        cond = asdict(conditions())
        cond.pop("system_body_types")
        cond["galactic_position"] = list(cond["galactic_position"])      # JSON has no tuples
        cond["materials"] = list(cond["materials"])
        return {"Sol|Sol 3": {"conditions": cond, "genus_hints": [BACTERIUM], "organisms": {
            BACTERIUM: {"species_key": AURASUS, "species_name": "Bacterium Aurasus", "variant_name": "Teal"}}}}

    def test_saved_per_body_state_fills_the_book_and_says_so(self) -> None:
        self.assertEqual(self.book.backfill(self.saved()), 1)
        entry = self.book.bodies()["Sol|Sol 3"]["species"][BACTERIUM]
        self.assertEqual((entry["species_key"], entry["variant"]), (AURASUS, "Teal"))
        self.assertIn(AURASUS, entry["predicted"])
        self.assertEqual(self.book.bodies()["Sol|Sol 3"]["source"], "backfill")

    def test_repeating_it_adds_nothing_and_never_replaces_a_live_record(self) -> None:
        self.book.record(conditions(), [BACTERIUM], BACTERIUM, AURASUS, "Bacterium Aurasus", "Live color", [AURASUS], when="2026-10-17T10:00:00Z")
        self.assertEqual(self.book.backfill(self.saved()), 0)
        self.assertEqual(self.book.bodies()["Sol|Sol 3"]["species"][BACTERIUM]["variant"], "Live color")
        self.assertEqual(self.book.bodies()["Sol|Sol 3"]["source"], "live")

    def test_two_commanders_with_the_same_body_make_one_record(self) -> None:
        self.assertEqual(self.book.backfill(self.saved()), 1)
        self.assertEqual(self.book.backfill(self.saved()), 0)
        self.assertEqual(len(self.book.bodies()), 1)

    def test_incompatible_saved_conditions_are_skipped(self) -> None:
        saved = self.saved()
        saved["Sol|Sol 3"]["conditions"]["a_field_from_the_future"] = 1
        self.assertEqual(self.book.backfill(saved), 0)
        self.assertEqual(self.book.backfill({}), 0)


class ReviewAndAnalysisTests(unittest.TestCase):
    def setUp(self) -> None:
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        self.book = E.ObservationBook()
        self.book.load(self.dir.name)
        warm, cold = conditions("Sol 3"), conditions("Sol 4", temperature_k=20.0)       # too cold for Aurasus (145 K and up)
        self.book.record(warm, [BACTERIUM], BACTERIUM, AURASUS, "Bacterium Aurasus", None, E.predicted_keys(BACTERIUM, warm), when="2026-10-17T10:00:00Z")
        self.book.record(cold, [BACTERIUM], BACTERIUM, AURASUS, "Bacterium Aurasus", None, E.predicted_keys(BACTERIUM, cold), when="2026-10-17T11:00:00Z")

    def test_a_find_is_a_hit_when_the_prediction_listed_it_and_flagged_when_outside_a_range(self) -> None:
        by_body = {f.body: f for f in A.finds(self.book.bodies())}
        self.assertTrue(by_body["Sol 3"].hit)
        self.assertFalse(by_body["Sol 3"].outside)
        self.assertFalse(by_body["Sol 4"].hit)
        self.assertEqual(by_body["Sol 4"].outside, ("temperature",))

    def test_the_genus_and_range_rows_count_the_finds(self) -> None:
        (row,) = A.genus_rows(A.finds(self.book.bodies()))
        self.assertEqual((row.genus, row.finds, row.hits, row.percent), ("Bacterium", 2, 1, 50))
        temperature = next(r for r in A.range_rows(A.finds(self.book.bodies())) if r.name == "temperature")
        self.assertEqual((temperature.low, temperature.high, temperature.outside), (20.0, 180.0, True))

    def test_species_on_one_body_are_counted_together(self) -> None:
        self.book.record(conditions("Sol 3"), [BACTERIUM, TUSSOCK], TUSSOCK, "$Codex_Ent_Tussocks_07_Name;", "Tussock Pennatis", None, [], when="2026-10-17T12:00:00Z")
        (row,) = A.together_rows(self.book.bodies())
        self.assertEqual((row.species, row.bodies), (("Bacterium Aurasus", "Tussock Pennatis"), 1))

    def test_a_review_is_saved_cleared_and_kept_through_a_later_sample(self) -> None:
        self.assertTrue(self.book.set_review("Sol|Sol 4", BACTERIUM, "rule", "  too   cold  "))
        find = next(f for f in A.finds(self.book.bodies()) if f.body == "Sol 4")
        self.assertEqual((find.status, find.note), ("rule", "too cold"))
        self.book.record(conditions("Sol 4", temperature_k=20.0), [BACTERIUM], BACTERIUM, AURASUS, "Bacterium Aurasus", "Teal", [], when="2026-10-19T00:00:00Z")
        self.assertEqual(next(f for f in A.finds(self.book.bodies()) if f.body == "Sol 4").status, "rule")
        self.assertTrue(self.book.set_review("Sol|Sol 4", BACTERIUM, "", ""))
        self.assertEqual(next(f for f in A.finds(self.book.bodies()) if f.body == "Sol 4").status, "")
        self.assertFalse(self.book.set_review("Sol|Nowhere", BACTERIUM, "rule", ""))
        self.assertFalse(self.book.set_review("Sol|Sol 4", TUSSOCK, "rule", ""))

    def test_the_report_lists_the_misses_and_the_reviews(self) -> None:
        self.book.set_review("Sol|Sol 4", BACTERIUM, "later", "check the cold limit")
        report = A.report_text(self.book.bodies())
        for text in ("2 bodies, 2 species finds", "Bacterium", "50%", "Finds the prediction did not list (1)", "<-- outside",
                     "Reviewed finds (1)", "Look at again later - check the cold limit"):
            self.assertIn(text, report)
        self.assertIn("0 bodies, 0 species finds", A.report_text({}))


if __name__ == "__main__":
    unittest.main()
