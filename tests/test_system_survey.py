"""System survey (system_survey.py): bodies from the journal, what is left to map, which have life to analyse, and rebuilding from a journal file."""
from __future__ import annotations

import json
import os
import sys
import tempfile
import types
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
for name in ("myNotebook", "ttkHyperlinkLabel", "theme", "monitor", "plug", "l10n", "requests"):
    sys.modules.setdefault(name, mock.MagicMock())
if "config" not in sys.modules:
    config_stub = types.ModuleType("config")
    config_stub.appname = "EDMarketConnector"
    config_stub.config = mock.MagicMock()
    sys.modules["config"] = config_stub

from plugin import system_survey as S  # noqa: E402

SYSTEM = "Test Sector AB-C d1"


def arrive(system=SYSTEM):
    return {"event": "FSDJump", "StarSystem": system, "SystemAddress": 99}


def scan(number, planet_class="Rocky body", mass=1.0, discovered=False, terraform="", **extra):
    return {"event": "Scan", "BodyName": f"{SYSTEM} {number}", "BodyID": hash(number) % 1000, "StarSystem": SYSTEM, "PlanetClass": planet_class,
            "MassEM": mass, "WasDiscovered": discovered, "WasMapped": False, "TerraformState": terraform, "SurfaceGravity": 4.9, "Landable": True, **extra}


class Feed(unittest.TestCase):
    def setUp(self):
        self.survey = S.SystemSurvey()
        self.survey.handle_event(arrive())

    def feed(self, *entries):
        for entry in entries:
            self.survey.handle_event(entry)


class SurveyTests(Feed):
    def test_a_new_system_starts_a_new_survey_and_a_repeat_of_the_same_one_does_not(self):
        self.feed(scan("1"))
        self.assertEqual(self.survey.scanned_count(), 1)
        self.survey.handle_event({"event": "Location", "StarSystem": SYSTEM})
        self.assertEqual(self.survey.scanned_count(), 1)
        self.survey.handle_event(arrive("Elsewhere"))
        self.assertEqual((self.survey.name, self.survey.scanned_count()), ("Elsewhere", 0))

    def test_hyperspace_hides_the_survey_until_arrival(self):
        self.assertTrue(self.survey.visible)
        self.survey.handle_event({"event": "StartJump", "JumpType": "Hyperspace"})
        self.assertFalse(self.survey.visible)
        self.survey.handle_event(arrive("Elsewhere"))
        self.assertTrue(self.survey.visible)

    def test_the_honk_and_the_system_scan(self):
        self.feed({"event": "FSSDiscoveryScan", "Progress": 0.25, "BodyCount": 8, "SystemName": SYSTEM})
        self.assertEqual((self.survey.honked, self.survey.body_count, self.survey.progress, self.survey.fss_complete), (True, 8, 0.25, False))
        self.feed({"event": "FSSAllBodiesFound", "SystemName": SYSTEM, "Count": 9})
        self.assertEqual((self.survey.fss_complete, self.survey.body_count, self.survey.progress), (True, 9, 1.0))

    def test_a_scan_describes_a_body_and_belts_and_late_events_are_ignored(self):
        self.feed(scan("A 1", "Earthlike body", 1.0, terraform="Terraformable"))
        body = next(iter(self.survey.bodies.values()))
        self.assertEqual((body.short, body.kind, body.tag, body.terraformable, body.scanned), ("A 1", "planet", "ELW", True, True))
        self.assertAlmostEqual(body.gravity_g, 0.4996, places=3)
        self.feed({"event": "Scan", "BodyName": f"{SYSTEM} A Belt Cluster 1", "BodyID": 5, "StarSystem": SYSTEM})
        self.feed(dict(scan("B 1"), StarSystem="Somewhere Else"))
        self.assertEqual(len(self.survey.bodies), 1)

    def test_a_star_is_a_star_and_the_primary_is_named_star(self):
        self.feed({"event": "Scan", "BodyName": SYSTEM, "BodyID": 0, "StarSystem": SYSTEM, "StarType": "K", "StellarMass": 0.8, "WasDiscovered": True})
        body = self.survey.bodies[0]
        self.assertEqual((body.kind, body.short), ("star", "Star"))

    def test_the_scan_value_uses_the_exploration_value_estimate(self):
        from plugin import scan_value
        self.feed(scan("A 1", "Earthlike body", 1.0, discovered=True, terraform="Terraformable"))
        body = next(iter(self.survey.bodies.values()))
        self.assertEqual(body.scan_value(), scan_value.estimate_planet_scan_value("Earthlike body", 1.0, True, True))
        self.assertGreater(body.scan_value(), 100_000)


class TargetTests(Feed):
    def setUp(self):
        super().setUp()
        self.feed(scan("A 1", "Earthlike body", 1.0, terraform="Terraformable"), scan("A 2", "Icy body", 0.1, discovered=True), scan("A 3", "Water world", 1.0))

    def short_names(self, bodies):
        return [b.short for b in bodies]

    def test_the_threshold_and_the_order(self):
        valuable = self.short_names(self.survey.to_map(100_000))
        self.assertEqual(valuable, ["A 1", "A 3"] if self.survey.bodies and valuable[0] == "A 1" else valuable)
        self.assertNotIn("A 2", valuable)
        self.assertEqual(len(self.survey.to_map(0)), 3)
        values = [b.scan_value() for b in self.survey.to_map(0)]
        self.assertEqual(values, sorted(values, reverse=True))

    def test_the_basis_is_the_scan_value_or_what_mapping_pays(self):
        scan_only = self.short_names(self.survey.to_map(1_000_000, "scan"))
        mapped = self.survey.to_map(1_000_000, "mapped")
        self.assertEqual(scan_only, [])                                  # no body's scan alone reaches a million
        self.assertTrue(mapped)                                          # mapping pays far more, so some do
        values = [b.mapped_value() for b in mapped]
        self.assertEqual(values, sorted(values, reverse=True))
        self.assertTrue(all(v >= 1_000_000 for v in values))

    def test_mapping_a_body_removes_it(self):
        first = self.survey.to_map(100_000)[0]
        self.feed({"event": "SAAScanComplete", "BodyName": first.name, "BodyID": first.body_id})
        self.assertNotIn(first.short, self.short_names(self.survey.to_map(100_000)))

    def test_life_stays_until_every_signal_is_analysed(self):
        body = next(b for b in self.survey.bodies.values() if b.short == "A 2")
        self.feed({"event": "FSSBodySignals", "BodyName": body.name, "BodyID": body.body_id, "Signals": [{"Type": S.BIO_TYPE, "Count": 2}]})
        self.assertEqual(self.short_names(self.survey.with_life()), ["A 2"])
        self.feed({"event": "SAASignalsFound", "BodyName": body.name, "BodyID": body.body_id, "Signals": [{"Type": S.BIO_TYPE, "Count": 2}],
                   "Genuses": [{"Genus": "$a;", "Genus_Localised": "Bacterium"}, {"Genus": "$b;", "Genus_Localised": "Osseus"}]})
        self.assertEqual(body.genuses, ["Bacterium", "Osseus"])
        self.feed({"event": "ScanOrganic", "ScanType": "Log", "Genus_Localised": "Bacterium", "Body": body.body_id})
        self.assertEqual((body.sampling, body.analysed), ("Bacterium", []))
        self.feed({"event": "ScanOrganic", "ScanType": "Analyse", "Genus_Localised": "Bacterium", "Body": body.body_id})
        self.assertEqual((body.sampling, body.analysed, self.short_names(self.survey.with_life())), ("", ["Bacterium"], ["A 2"]))
        self.feed({"event": "ScanOrganic", "ScanType": "Analyse", "Genus_Localised": "Osseus", "Body": body.body_id})
        self.assertEqual(self.survey.with_life(), [])

    def test_signals_before_the_scan_are_kept_for_it(self):
        self.feed({"event": "FSSBodySignals", "BodyName": f"{SYSTEM} B 1", "BodyID": 777, "Signals": [{"Type": S.BIO_TYPE, "Count": 1}]})
        self.assertEqual(self.survey.bodies[777].bio, 1)
        self.assertEqual(self.survey.to_map(0)[0].short in ("A 1", "A 3", "A 2"), True, "an unscanned body is never offered for mapping")
        self.assertNotIn(777, [b.body_id for b in self.survey.to_map(0)])


class RestoreTests(unittest.TestCase):
    def test_the_survey_is_rebuilt_from_the_newest_journal_since_the_last_arrival(self):
        with tempfile.TemporaryDirectory() as folder:
            lines = [arrive("Old System"), dict(scan("1"), StarSystem="Old System"), arrive(), {"event": "FSSDiscoveryScan", "BodyCount": 5, "Progress": 0.2},
                     scan("A 1", "Earthlike body", 1.0), {"event": "Music"}]
            with open(os.path.join(folder, "Journal.2026-10-16T000000.01.log"), "w", encoding="utf-8") as handle:
                handle.write("\n".join(json.dumps(line) for line in lines) + "\n")
            survey = S.SystemSurvey()
            self.assertTrue(S.restore_from_journal(survey, folder))
            self.assertEqual((survey.name, survey.honked, survey.body_count, survey.scanned_count()), (SYSTEM, True, 5, 1))

    def _write(self, folder, name, lines):
        with open(os.path.join(folder, name), "w", encoding="utf-8") as handle:
            handle.write(chr(10).join(json.dumps(line) for line in lines) + chr(10))

    def test_a_relog_in_the_same_system_keeps_the_scans_from_the_journal_before(self):
        with tempfile.TemporaryDirectory() as folder:
            self._write(folder, "Journal.2026-10-16T000000.01.log", [
                {"event": "LoadGame", "Commander": "A"}, arrive("Elsewhere"), arrive(), scan("A 1", "Earthlike body", 1.0, WasFootfalled=False)])
            os.utime(os.path.join(folder, "Journal.2026-10-16T000000.01.log"), (1, 1))
            self._write(folder, "Journal.2026-10-16T010000.01.log", [
                {"event": "Fileheader", "part": 1}, {"event": "LoadGame", "Commander": "A"}, {"event": "Location", "StarSystem": SYSTEM, "SystemAddress": 99},
                scan("A 2", "Water world", 1.0)])
            survey = S.SystemSurvey()
            self.assertTrue(S.restore_from_journal(survey, folder))
            self.assertEqual((survey.name, survey.scanned_count(), survey.visible), (SYSTEM, 2, True))
            self.assertTrue(any(b.first_footfall for b in survey.bodies.values()))

    def test_an_older_journal_from_another_system_or_commander_is_not_mixed_in(self):
        for older in ([{"event": "LoadGame", "Commander": "A"}, arrive("Elsewhere"), dict(scan("1"), StarSystem="Elsewhere")],
                      [{"event": "LoadGame", "Commander": "B"}, arrive(), scan("B 1", "Earthlike body", 1.0)]):
            with tempfile.TemporaryDirectory() as folder:
                self._write(folder, "Journal.2026-10-16T000000.01.log", older)
                os.utime(os.path.join(folder, "Journal.2026-10-16T000000.01.log"), (1, 1))
                self._write(folder, "Journal.2026-10-16T010000.01.log", [
                    {"event": "LoadGame", "Commander": "A"}, {"event": "Location", "StarSystem": SYSTEM, "SystemAddress": 99}, scan("A 2", "Water world", 1.0)])
                survey = S.SystemSurvey()
                self.assertTrue(S.restore_from_journal(survey, folder))
                self.assertEqual(survey.scanned_count(), 1)

    def test_an_empty_folder_restores_nothing_and_does_not_raise(self):
        with tempfile.TemporaryDirectory() as folder:
            self.assertFalse(S.restore_from_journal(S.SystemSurvey(), folder))

    def test_the_restore_event_name_matches_the_restore_module(self):
        from plugin import restore
        self.assertEqual(S.RESTORE_EVENT, restore.RESTORE_EVENT)


class Finished(Feed):
    def test_a_mapped_body_with_no_life_is_finished_and_one_with_life_is_until_all_is_analysed(self):
        self.feed(scan("A 1", "Earthlike body", 1.0), scan("A 2", "Water world", 1.0), scan("A 3", "Icy body", 0.1))
        by = {b.short: b for b in self.survey.bodies.values()}
        self.feed({"event": "SAAScanComplete", "BodyName": by["A 1"].name, "BodyID": by["A 1"].body_id})
        self.feed({"event": "SAAScanComplete", "BodyName": by["A 2"].name, "BodyID": by["A 2"].body_id},
                  {"event": "SAASignalsFound", "BodyName": by["A 2"].name, "BodyID": by["A 2"].body_id, "Signals": [{"Type": S.BIO_TYPE, "Count": 1}],
                   "Genuses": [{"Genus": "$a;", "Genus_Localised": "Bacterium"}]})
        self.assertEqual([b.short for b in self.survey.finished()], ["A 1"])
        self.assertEqual((self.survey.mapped_count(), self.survey.life_counts()), (2, (0, 1)))
        self.feed({"event": "ScanOrganic", "ScanType": "Analyse", "Genus_Localised": "Bacterium", "Body": by["A 2"].body_id})
        self.assertEqual([b.short for b in self.survey.finished()], ["A 1", "A 2"])
        self.assertEqual(self.survey.life_counts(), (1, 1))
        analysed, signals = self.survey.bio_totals()
        self.assertEqual(analysed, signals)                                # the one body with life is finished: every signal of it is analysed
        self.assertGreater(signals, 0)


class StoreTests(unittest.TestCase):
    """The per-commander saved surveys (system_survey_store.py): what was known about a system comes back on a later visit, and never crosses commanders."""

    def setUp(self):
        from plugin import system_survey_store as Store
        self.Store = Store
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)

    def new_store(self, cmdr):
        store = self.Store.SurveyStore()
        store.delay = 0.01
        store.start(self.folder.name)
        store.set_commander(cmdr)
        return store

    def surveyed(self):
        survey = S.SystemSurvey()
        survey.handle_event(arrive())
        survey.handle_event({"event": "FSSDiscoveryScan", "BodyCount": 9, "Progress": 0.5})
        for number, mass in (("A 1", 1.0), ("A 2", 0.5)):
            survey.handle_event(scan(number, "Earthlike body", mass))
        survey.handle_event({"event": "SAAScanComplete", "BodyName": f"{SYSTEM} A 1", "BodyID": hash("A 1") % 1000})
        return survey

    def test_a_saved_system_comes_back_on_a_later_visit(self):
        store = self.new_store("CMDR A")
        store.remember(self.surveyed())
        store.flush()
        later = S.SystemSurvey()
        later.handle_event(arrive())
        later_store = self.new_store("cmdr a")                      # a new session reads the file; the commander key ignores case
        self.assertEqual(later_store.merge_into(later, S.Body), 2)
        self.assertEqual((later.scanned_count(), later.honked, later.body_count), (2, True, 9))
        self.assertEqual(sorted(b.mapped for b in later.bodies.values()), [False, True])

    def test_another_commander_sees_nothing_of_it(self):
        store = self.new_store("CMDR A")
        store.remember(self.surveyed())
        store.flush()
        other = S.SystemSurvey()
        other.handle_event(arrive())
        self.assertEqual(self.new_store("CMDR B").merge_into(other, S.Body), 0)
        self.assertEqual(other.scanned_count(), 0)

    def test_what_the_live_survey_knows_wins_and_the_saved_copy_fills_the_gaps(self):
        store = self.new_store("A")
        store.remember(self.surveyed())
        store.flush()
        live = S.SystemSurvey()
        live.handle_event(arrive())
        live.handle_event(scan("A 1", "Water world", 3.0))                 # rescanned this visit: its own data stays
        store.merge_into(live, S.Body)
        first = next(b for b in live.bodies.values() if b.short == "A 1")
        self.assertEqual(first.planet_class, "Water world")
        self.assertTrue(first.mapped)                                       # but the mapping the saved copy knew is added
        self.assertEqual(live.scanned_count(), 2)

    def test_only_the_most_recent_systems_are_kept(self):
        store = self.new_store("A")
        for number in range(self.Store.MAX_SYSTEMS + 5):
            survey = S.SystemSurvey()
            survey.handle_event(dict(arrive(f"System {number}"), SystemAddress=1000 + number))
            survey.handle_event(dict(scan("1"), StarSystem=f"System {number}"))
            store.remember(survey)
            store.flush()
        self.assertEqual(len(store._systems()), self.Store.MAX_SYSTEMS)
        self.assertIsNone(store.saved("System 0", 1000))
        self.assertIsNotNone(store.saved(f"System {self.Store.MAX_SYSTEMS + 4}", 1000 + self.Store.MAX_SYSTEMS + 4))

    def test_a_system_with_nothing_in_it_is_not_saved(self):
        store = self.new_store("A")
        empty = S.SystemSurvey()
        empty.handle_event(arrive())
        store.remember(empty)
        store.flush()
        self.assertIsNone(store.saved(SYSTEM, 99))

    def test_a_damaged_file_gives_an_empty_store(self):
        with open(os.path.join(self.folder.name, self.Store.STATE_FILENAME), "w", encoding="utf-8") as handle:
            handle.write("not json")
        self.assertIsNone(self.new_store("A").saved(SYSTEM, 99))


class RebuildTests(unittest.TestCase):
    """rebuild_system: one system from every visit in the commander's journals, however many other systems were visited between."""

    def write(self, folder, name, lines):
        with open(os.path.join(folder, name), "w", encoding="utf-8") as handle:
            handle.write(chr(10).join(json.dumps(line) for line in lines) + chr(10))

    def test_every_visit_to_the_system_is_replayed_and_other_systems_and_commanders_are_left_out(self):
        with tempfile.TemporaryDirectory() as folder:
            self.write(folder, "Journal.2026-10-16T000000.01.log", [
                {"event": "LoadGame", "Commander": "A"}, arrive(), scan("A 1", "Earthlike body", 1.0), arrive("Elsewhere"), dict(scan("1"), StarSystem="Elsewhere")])
            self.write(folder, "Journal.2026-10-16T010000.01.log", [
                {"event": "LoadGame", "Commander": "B"}, arrive(), scan("B 1", "Earthlike body", 1.0)])
            self.write(folder, "Journal.2026-10-16T020000.01.log", [
                {"event": "LoadGame", "Commander": "A"}, arrive("Elsewhere"), arrive(), scan("A 2", "Water world", 1.0)])
            for index, name in enumerate(sorted(os.listdir(folder))):
                os.utime(os.path.join(folder, name), (index + 1, index + 1))
            found = S.rebuild_system(SYSTEM, "A", folder)
            self.assertEqual(sorted(b.short for b in found.bodies.values()), sorted(S.short_name(f"{SYSTEM} {n}", SYSTEM) for n in ("A 1", "A 2")))
            self.assertIsNone(S.rebuild_system("Never Been", "A", folder))
            self.assertEqual(S.rebuild_system(SYSTEM, "B", folder).scanned_count(), 1)

    def test_absorbing_a_rebuilt_survey_adds_to_what_was_saved(self):
        from plugin import system_survey_store as Store
        with tempfile.TemporaryDirectory() as folder:
            store = Store.SurveyStore()
            store.start(folder)
            store.set_commander("A")
            first = S.SystemSurvey()
            first.handle_event(arrive())
            first.handle_event(scan("A 1", "Earthlike body", 1.0))
            store.remember(first)
            store.flush()
            older = S.SystemSurvey()
            older.handle_event(arrive())
            older.handle_event(scan("A 2", "Water world", 1.0))
            store.absorb(older, S.Body)
            live = S.SystemSurvey()
            live.handle_event(arrive())
            store.merge_into(live, S.Body)
            self.assertEqual(live.scanned_count(), 2)


class Footfall(Feed):
    def test_a_landable_body_nobody_has_stood_on_is_a_first_footfall(self):
        self.feed(scan("1", WasFootfalled=False))
        body = next(iter(self.survey.bodies.values()))
        self.assertTrue(body.first_footfall)

    def test_a_footfalled_or_unlandable_body_is_not(self):
        self.feed(scan("1", WasFootfalled=True), scan("2", WasFootfalled=False, Landable=False))
        self.assertFalse(any(b.first_footfall for b in self.survey.bodies.values()))

    def test_a_later_scan_after_landing_does_not_take_the_bonus_away(self):
        self.feed(scan("1", WasFootfalled=False), scan("1", WasFootfalled=True))
        self.assertTrue(next(iter(self.survey.bodies.values())).first_footfall)


class Guardrails(Feed):
    """When the cards may show: not on the main menu, after the game closes, while another commander signs in, or while docked."""

    def test_the_game_closing_hides_the_survey_until_a_commander_loads_in(self):
        self.assertTrue(self.survey.visible)
        self.feed({"event": "Shutdown"})
        self.assertFalse(self.survey.visible)
        self.feed({"event": "LoadGame", "Commander": "A"}, arrive())
        self.assertTrue(self.survey.visible)

    def test_the_main_menu_hides_it_and_other_music_does_not(self):
        self.feed({"event": "Music", "MusicTrack": "Supercruise"})
        self.assertTrue(self.survey.visible)
        self.feed({"event": "Music", "MusicTrack": "MainMenu"})
        self.assertFalse(self.survey.visible)

    def test_a_new_game_session_hides_it_but_a_journal_that_carries_on_does_not(self):
        self.feed({"event": "Fileheader", "part": 2})
        self.assertTrue(self.survey.visible)
        self.feed({"event": "Fileheader", "part": 1})
        self.assertFalse(self.survey.visible)

    def test_another_commander_loading_in_clears_the_survey(self):
        self.feed({"event": "LoadGame", "Commander": "A"}, scan("1"))
        self.assertEqual(self.survey.scanned_count(), 1)
        self.feed({"event": "Music", "MusicTrack": "MainMenu"}, {"event": "LoadGame", "Commander": "B"})
        self.assertEqual(self.survey.scanned_count(), 0)
        self.assertFalse(self.survey.visible)          # no system until they arrive somewhere
        self.feed({"event": "Location", "StarSystem": SYSTEM, "SystemAddress": 99})
        self.assertTrue(self.survey.visible)
        self.assertEqual(self.survey.scanned_count(), 0)

    def test_the_same_commander_loading_back_in_keeps_the_survey(self):
        self.feed({"event": "LoadGame", "Commander": "A"}, scan("1"), {"event": "Shutdown"}, {"event": "LoadGame", "Commander": "A"})
        self.feed({"event": "Location", "StarSystem": SYSTEM, "SystemAddress": 99})
        self.assertEqual(self.survey.scanned_count(), 1)

    def test_docking_hides_it_and_undocking_brings_it_back(self):
        self.feed({"event": "Docked"})
        self.assertFalse(self.survey.visible)
        self.feed({"event": "Undocked"})
        self.assertTrue(self.survey.visible)
        self.feed({"event": "Location", "StarSystem": SYSTEM, "SystemAddress": 99, "Docked": True})
        self.assertFalse(self.survey.visible)


class KnownBodies(Feed):
    """Planets other commanders have scanned (EDSM) listed before the commander's own scans."""

    ROWS = [
        {"bodyId": 5, "name": f"{SYSTEM} 2", "type": "Planet", "subType": "High metal content world", "distanceToArrival": 1200.5, "isLandable": False,
         "earthMasses": 2.0, "gravity": 1.4, "surfaceTemperature": 600, "terraformingState": "Candidate for terraforming", "atmosphereType": "No atmosphere"},
        {"bodyId": 6, "name": f"{SYSTEM} 3", "type": "Planet", "subType": "Earth-like world", "distanceToArrival": 90.0, "earthMasses": 1.0},
        {"bodyId": 7, "name": f"{SYSTEM} A", "type": "Star", "subType": "K (Yellow-Orange) Star"},
        {"bodyId": 8, "name": f"{SYSTEM} 4", "type": "Planet", "subType": "Something new"},
        {"name": f"{SYSTEM} 5", "type": "Planet", "subType": "Icy body"},
    ]

    def test_known_planets_are_listed_with_a_value_and_a_tag(self):
        added = self.survey.merge_known(SYSTEM, self.ROWS)
        self.assertEqual(added, 2)                      # a star, an unknown type and a body with no id are skipped
        listed = self.survey.to_map(0)
        self.assertEqual([b.short for b in listed], ["3", "2"])        # an Earth-like world is always counted as terraformable, so it is worth more
        self.assertEqual((listed[0].tag, listed[1].tag), ("ELW", "HMC"))
        self.assertTrue(all(b.known and not b.scanned and b.scan_value() > 0 for b in listed))
        self.assertEqual(self.survey.known_count(), 2)

    def test_the_commanders_own_scan_wins_and_a_move_discards_the_lookup(self):
        self.feed(scan("2", planet_class="Rocky body", mass=0.1))
        body = next(b for b in self.survey.bodies.values() if b.scanned)
        self.survey.merge_known(SYSTEM, [{"bodyId": body.body_id, "name": body.name, "type": "Planet", "subType": "Water world", "earthMasses": 3.0}])
        self.assertEqual(body.planet_class, "Rocky body")
        self.assertFalse(body.known)
        self.assertEqual(self.survey.merge_known("Another System", self.ROWS), 0)
        self.assertEqual(self.survey.merge_known(SYSTEM, "not a list"), 0)

    def test_a_scan_replaces_what_the_lookup_said(self):
        self.survey.merge_known(SYSTEM, self.ROWS)
        self.feed({**scan("3", planet_class="Water world", mass=0.5), "BodyID": 6})
        self.assertEqual(self.survey.bodies[6].planet_class, "Water world")
        self.assertTrue(self.survey.bodies[6].scanned)


class Text(unittest.TestCase):
    def test_credits_text(self):
        self.assertEqual((S.credits_text(999), S.credits_text(56_000), S.credits_text(1_234_567)), ("999", "56k", "1.2M"))

    def test_short_names(self):
        self.assertEqual((S.short_name(f"{SYSTEM} 3 b", SYSTEM), S.short_name(SYSTEM, SYSTEM), S.short_name("Other 1", SYSTEM)), ("3 b", "Star", "Other 1"))


if __name__ == "__main__":
    unittest.main()
