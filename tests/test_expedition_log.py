"""Expedition Log (expedition_log.py): what the totals count and what they leave out, selling, the archive operations, saving per commander, and rescanning from journals."""
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

from plugin import expedition_log as L  # noqa: E402

ADDRESS = 111
TUSSOCK, TUSSOCK_06 = "$Codex_Ent_Tussocks_Genus_Name;", "$Codex_Ent_Tussocks_06_Name;"


def jump(system, distance=10.0, address=ADDRESS):
    return {"event": "FSDJump", "StarSystem": system, "SystemAddress": address, "JumpDist": distance}


def scan(body_id, planet="Rocky body", discovered=True, mapped=True, footfalled=True, landable=False, terraform="", mass=1.0, star=""):
    entry = {"event": "Scan", "BodyID": body_id, "BodyName": f"Sys {body_id}", "SystemAddress": ADDRESS, "WasDiscovered": discovered, "WasMapped": mapped,
             "WasFootfalled": footfalled, "Landable": landable, "TerraformState": terraform, "MassEM": mass}
    if star:
        entry["StarType"] = star
    else:
        entry["PlanetClass"] = planet
    return entry


def organic(scan_type, body=5, species=TUSSOCK_06):
    return {"event": "ScanOrganic", "ScanType": scan_type, "Genus": TUSSOCK, "Genus_Localised": "Tussock", "Species": species, "Body": body, "SystemAddress": ADDRESS}


class Counting(unittest.TestCase):
    def setUp(self):
        self.run = L.Run("r1", "Test", L.RUNNING, "2026-10-16T10:00:00Z")
        self.tally = L.Tally(self.run)

    def feed(self, *entries):
        return [self.tally.apply(e) for e in entries]

    def test_jumps_light_years_and_systems(self):
        self.feed(jump("A", 12.5), jump("B", 20.0), jump("A", 5.0))
        self.assertEqual((self.run.totals.jumps, self.run.totals.light_years, self.run.systems, self.run.start_system, self.run.end_system), (3, 37.5, ["A", "B"], "A", "A"))

    def test_a_carrier_jump_counts_the_system_but_not_a_jump(self):
        self.feed({"event": "CarrierJump", "StarSystem": "C", "SystemAddress": 5})
        self.assertEqual((self.run.totals.jumps, self.run.systems), (0, ["C"]))

    def test_bodies_are_counted_once_and_belts_and_rings_are_not_bodies(self):
        self.feed(scan(1), scan(1), scan(2, star="G"), {"event": "Scan", "BodyID": 3, "BodyName": "Sys A Belt Cluster 1", "SystemAddress": ADDRESS})
        totals = self.run.totals
        self.assertEqual((totals.bodies_scanned, totals.planets, totals.stars), (2, 1, 1))

    def test_first_discoveries_and_the_notable_kinds(self):
        self.feed(scan(1, "Earthlike body", discovered=False), scan(2, "Water world", terraform="Terraformable"), scan(3, "Ammonia world"), scan(4, "Rocky body", discovered=False))
        totals = self.run.totals
        self.assertEqual((totals.first_discoveries, totals.earth_likes, totals.water_worlds, totals.ammonia_worlds, totals.terraformables), (2, 1, 1, 1, 1))

    def test_a_first_map_is_one_of_a_body_that_was_unmapped_when_scanned(self):
        self.feed(scan(1, mapped=False), scan(2, mapped=True),
                  {"event": "SAAScanComplete", "BodyID": 1, "SystemAddress": ADDRESS}, {"event": "SAAScanComplete", "BodyID": 2, "SystemAddress": ADDRESS},
                  {"event": "SAAScanComplete", "BodyID": 1, "SystemAddress": ADDRESS})
        self.assertEqual((self.run.totals.mapped, self.run.totals.first_mapped), (2, 1))

    def test_the_unsold_estimate_grows_with_scans_and_selling_clears_it_and_adds_the_earnings(self):
        self.feed(scan(1, "Earthlike body", discovered=False, terraform="Terraformable"), scan(2, star="K", discovered=False))
        self.assertGreater(self.run.totals.explore_estimated, 100_000)
        self.feed({"event": "MultiSellExplorationData", "TotalEarnings": 1_234_567, "BaseValue": 1_000_000, "Bonus": 234_567})
        self.assertEqual((self.run.totals.explore_earned, self.run.totals.explore_estimated), (1_234_567, 0))
        self.feed({"event": "SellExplorationData", "TotalEarnings": 500})
        self.assertEqual(self.run.totals.explore_earned, 1_234_567 + 500)

    def test_exobiology_counts_samples_species_first_footfalls_and_the_unsold_value(self):
        from plugin import organic_species_data as data
        value = data.SPECIES[f"{TUSSOCK}|{TUSSOCK_06}"].value
        self.feed(scan(5, landable=True, footfalled=False), organic("Log"), organic("Sample"), organic("Sample"), organic("Analyse"), organic("Analyse"))
        totals = self.run.totals
        self.assertEqual((totals.bio_samples, totals.bio_species, totals.bio_first_footfalls, totals.bio_estimated), (5, 1, 1, value * 5))   # a repeat Analyse is one species
        self.assertEqual(self.run.genera, ["Tussock"])
        self.feed({"event": "SellOrganicData", "BioData": [{"Genus": TUSSOCK, "Value": 1_000_000, "Bonus": 4_000_000}, {"Value": 200}]})
        self.assertEqual((totals.bio_earned, totals.bio_estimated), (5_000_200, 0))
        self.assertEqual(totals.earned, 5_000_200)

    def test_a_species_on_a_body_somebody_had_walked_on_is_not_a_first_footfall(self):
        from plugin import organic_species_data as data
        self.feed(scan(5, landable=True, footfalled=True), organic("Analyse"))
        self.assertEqual((self.run.totals.bio_first_footfalls, self.run.totals.bio_estimated), (0, data.SPECIES[f"{TUSSOCK}|{TUSSOCK_06}"].value))

    def test_codex_landings_honks_and_ships(self):
        self.feed({"event": "CodexEntry", "IsNewEntry": True}, {"event": "CodexEntry", "IsNewEntry": False}, {"event": "Touchdown", "PlayerControlled": True},
                  {"event": "Touchdown", "PlayerControlled": False}, {"event": "FSSDiscoveryScan"},
                  {"event": "Loadout", "Ship": "explorer_nx", "Ship_Localised": "Caspian Explorer", "ShipName": "Far Horizon", "ShipIdent": "WN-01"},
                  {"event": "Loadout", "Ship": "explorer_nx", "Ship_Localised": "Caspian Explorer", "ShipName": "Far Horizon", "ShipIdent": "WN-01"})
        totals = self.run.totals
        self.assertEqual((totals.codex_new, totals.landings, totals.honks), (1, 1, 1))
        self.assertEqual(self.run.ships, ["Caspian Explorer 'Far Horizon' WN-01"])

    def test_events_the_log_does_not_count_change_nothing(self):
        self.assertEqual(self.feed({"event": "Music"}, {"event": "Status"}), [False, False])


class Archive(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.ticks = iter(range(1, 1000))
        self.book = L.LogBook(now=lambda: f"2026-10-16T10:{next(self.ticks) % 60:02d}:00Z", new_id=lambda: f"id{next(self.ticks)}", clock=lambda: 1e9)
        self.book.load(self.folder.name)
        self.book.set_commander("CMDR A")

    def test_no_commander_no_expedition(self):
        book = L.LogBook()
        self.assertIsNone(book.start("x"))

    def test_start_names_it_and_a_new_start_stops_the_one_running(self):
        first = self.book.start("", "Sol", "Python")
        self.assertEqual((first.name, first.status, first.start_system, first.ships, first.systems), ("Expedition 1", L.RUNNING, "Sol", ["Python"], ["Sol"]))
        second = self.book.start("Deep Space")
        self.assertEqual((second.name, self.book.running().id, first.status), ("Deep Space", second.id, L.STOPPED))
        self.assertTrue(first.ended)

    def test_stop_resume_reset_and_delete(self):
        run = self.book.start("One")
        self.book.apply(jump("A"))
        self.book.stop()
        self.assertEqual((run.status, self.book.running()), (L.STOPPED, None))
        self.assertFalse(self.book.apply(jump("B")))                         # nothing counts while stopped
        self.book.resume(run.id)
        self.assertEqual((run.status, run.ended), (L.RUNNING, ""))
        self.book.apply(jump("C"))
        self.assertEqual(run.totals.jumps, 2)
        fresh = self.book.reset(run.id)
        self.assertEqual((fresh.totals.jumps, fresh.name, fresh.status), (0, "One", L.RUNNING))
        self.assertTrue(self.book.delete(run.id))
        self.assertEqual(self.book.runs(), [])

    def test_editing_the_details_and_refusing_a_bad_date(self):
        run = self.book.start("One")
        self.book.update(run.id, name="Core run", start_system="Colonia", end_system="Sol", ships="Python 'A'; Caspian 'B'\nAsp", notes="note")
        self.assertEqual((run.name, run.start_system, run.end_system, run.ships, run.notes), ("Core run", "Colonia", "Sol", ["Python 'A'", "Caspian 'B'", "Asp"], "note"))
        self.book.update(run.id, started="2026-10-01 08:30", ended="2026-10-03")
        self.assertEqual((run.started, run.ended, run.status), ("2026-10-01T08:30:00Z", "2026-10-03T00:00:00Z", L.STOPPED))
        for bad in ({"started": "yesterday"}, {"ended": "soon"}, {"ended": "2026-09-01"}):
            with self.assertRaises(ValueError):
                self.book.update(run.id, **bad)
        self.assertEqual(run.started, "2026-10-01T08:30:00Z")

    def test_a_commander_sees_only_their_own_expeditions_and_they_survive_a_restart(self):
        run = self.book.start("Mine")
        self.book.apply(jump("A", 7.0))
        self.book.flush()
        again = L.LogBook()
        again.load(self.folder.name)
        again.set_commander("cmdr a")
        self.assertEqual([r.name for r in again.runs()], ["Mine"])
        self.assertEqual(again.get(run.id).totals.light_years, 7.0)
        other = L.LogBook()
        other.load(self.folder.name)
        other.set_commander("CMDR B")
        self.assertEqual(other.runs(), [])

    def test_a_damaged_file_gives_an_empty_book_and_two_running_keep_one(self):
        with open(os.path.join(self.folder.name, L.STATE_FILENAME), "w", encoding="utf-8") as handle:
            handle.write("not json")
        book = L.LogBook()
        book.load(self.folder.name)
        book.set_commander("X")
        self.assertEqual(book.runs(), [])
        raw = [L.run_to_raw(L.Run("a", "A", L.RUNNING, "2026-10-01T00:00:00Z")), L.run_to_raw(L.Run("b", "B", L.RUNNING, "2026-10-02T00:00:00Z"))]
        with open(os.path.join(self.folder.name, L.STATE_FILENAME), "w", encoding="utf-8") as handle:
            json.dump({"version": 2, "commanders": {"x": {"name": "X", "data": {"runs": raw}}}, "legacy": None, "meta": {}}, handle)
        book.load(self.folder.name)
        book.set_commander("Y")
        book.set_commander("X")
        self.assertEqual(sum(1 for r in book.runs() if r.status == L.RUNNING), 1)

    def test_the_newest_is_listed_first(self):
        self.book.update(self.book.start("Old").id, started="2026-01-01")
        self.book.update(self.book.start("New").id, started="2026-06-01")
        self.assertEqual([r.name for r in self.book.runs()], ["New", "Old"])


class Rescan(unittest.TestCase):
    def write(self, folder, name, commander, entries):
        lines = [{"event": "LoadGame", "Commander": commander, "timestamp": "2026-10-16T09:00:00Z"}] + entries
        with open(os.path.join(folder, name), "w", encoding="utf-8") as handle:
            handle.write("\n".join(json.dumps(line) for line in lines) + "\n")

    def test_the_totals_are_worked_out_again_from_the_commander_s_journals_in_the_window(self):
        with tempfile.TemporaryDirectory() as folder:
            self.write(folder, "Journal.2026-10-16T090000.01.log", "CMDR A", [
                dict(jump("Before", 99.0), timestamp="2026-10-16T09:30:00Z"), dict(jump("A", 10.0), timestamp="2026-10-16T10:05:00Z"),
                dict(scan(1, discovered=False), timestamp="2026-10-16T10:06:00Z"), dict(jump("B", 5.0), timestamp="2026-10-16T11:00:00Z"),
                dict(jump("After", 99.0), timestamp="2026-10-16T13:00:00Z")])
            self.write(folder, "Journal.2026-10-16T100000.01.log", "CMDR B", [dict(jump("Other", 50.0), timestamp="2026-10-16T10:30:00Z")])
            run = L.Run("r", "R", L.STOPPED, "2026-10-16T10:00:00Z", "2026-10-16T12:00:00Z")
            rebuilt = L.rescan(run, "cmdr a", folder)
            self.assertEqual((rebuilt.totals.jumps, rebuilt.totals.light_years, rebuilt.systems, rebuilt.totals.first_discoveries), (2, 15.0, ["A", "B"], 1))

    def test_replace_totals_keeps_the_name_dates_notes_and_hand_added_ships(self):
        with tempfile.TemporaryDirectory() as folder:
            book = L.LogBook(clock=lambda: 1e9)
            book.load(folder)
            book.set_commander("A")
            run = book.start("Mine", "Sol")
            book.update(run.id, ships="Hand Ship", notes="keep", started="2026-10-16 10:00")
            rebuilt = L.Run("x", "x")
            rebuilt.totals.jumps = 9
            rebuilt.ships = ["Python"]
            rebuilt.systems = ["Sol", "A"]
            book.replace_totals(run.id, rebuilt)
            self.assertEqual((run.totals.jumps, run.name, run.notes, run.ships, run.rescanned != ""), (9, "Mine", "keep", ["Hand Ship", "Python"], True))


class MappedEstimate(unittest.TestCase):
    def test_mapping_replaces_the_scan_estimate_with_the_mapped_value(self):
        run = L.Run("r", "R", L.RUNNING, "2026-10-16T10:00:00Z")
        tally = L.Tally(run)
        tally.apply(scan(1, "Water world", discovered=False, mapped=False))
        scanned = run.totals.explore_estimated
        tally.apply({"event": "SAAScanComplete", "BodyID": 1, "SystemAddress": ADDRESS, "ProbesUsed": 5, "EfficiencyTarget": 6})
        from plugin import scan_value
        self.assertEqual(run.totals.explore_estimated, scan_value.estimate_planet_mapped_value("Water world", 1.0, False, False, False, True))
        self.assertGreater(run.totals.explore_estimated, scanned * 3)
        tally.apply({"event": "SAAScanComplete", "BodyID": 1, "SystemAddress": ADDRESS, "ProbesUsed": 5, "EfficiencyTarget": 6})        # a repeat changes nothing
        self.assertEqual(run.totals.explore_estimated, scan_value.estimate_planet_mapped_value("Water world", 1.0, False, False, False, True))

    def test_a_probe_run_over_the_target_loses_the_efficiency_bonus(self):
        from plugin import scan_value
        run = L.Run("r", "R", L.RUNNING, "2026-10-16T10:00:00Z")
        L.Tally(run).apply(scan(1, "Rocky body", terraform="Terraformable", discovered=True, mapped=True))
        before = run.totals.explore_estimated
        L.Tally(run).apply({"event": "SAAScanComplete", "BodyID": 1, "SystemAddress": ADDRESS, "ProbesUsed": 9, "EfficiencyTarget": 4})
        self.assertEqual(run.totals.explore_estimated - before, scan_value.estimate_planet_mapped_value("Rocky body", 1.0, True, True, True, False) - before)

    def test_the_per_body_detail_survives_saving(self):
        run = L.Run("r", "R", L.RUNNING, "2026-10-16T10:00:00Z")
        L.Tally(run).apply(scan(1, "Water world", discovered=False, mapped=False))
        again = L.run_from_raw(L.run_to_raw(run))
        self.assertEqual(again.planets, run.planets)


class SinceLastSale(unittest.TestCase):
    def write(self, folder, name, commander, entries):
        lines = [{"event": "LoadGame", "Commander": commander, "timestamp": "2026-10-01T00:00:00Z"}] + entries
        with open(os.path.join(folder, name), "w", encoding="utf-8") as handle:
            handle.write("\n".join(json.dumps(line) for line in lines) + "\n")

    def test_it_begins_one_second_after_the_earlier_of_the_two_last_sales(self):
        events = [{"event": "SellOrganicData", "timestamp": "2026-09-25T17:47:16Z"}, {"event": "MultiSellExplorationData", "timestamp": "2026-09-30T10:36:24Z"},
                  {"event": "SellOrganicData", "timestamp": "2026-09-10T00:00:00Z"}]
        self.assertEqual(L.since_last_sale(events), "2026-09-25T17:47:17Z")
        self.assertEqual(L.since_last_sale([{"event": "SellOrganicData", "timestamp": "2026-09-25T17:47:16Z"}]), "2026-09-25T17:47:17Z")
        self.assertIsNone(L.since_last_sale([{"event": "FSDJump", "timestamp": "2026-09-25T17:47:16Z"}]))

    def test_the_plan_carries_the_totals_gathered_since_the_sale_for_that_commander_only(self):
        with tempfile.TemporaryDirectory() as folder:
            self.write(folder, "Journal.2026-10-01T000000.01.log", "CMDR A", [
                dict(jump("Before", 11.0), timestamp="2026-10-01T01:00:00Z"), {"event": "SellOrganicData", "BioData": [], "timestamp": "2026-10-01T02:00:00Z"},
                dict(jump("After", 22.0), timestamp="2026-10-01T03:00:00Z"), dict(scan(1, "Water world", discovered=False), timestamp="2026-10-01T03:05:00Z")])
            self.write(folder, "Journal.2026-10-02T000000.01.log", "CMDR B", [dict(jump("Elsewhere", 99.0), timestamp="2026-10-02T01:00:00Z")])
            plan = L.plan_since_last_sale("cmdr a", folder)
            self.assertEqual(plan["started"], "2026-10-01T02:00:01Z")
            totals = plan["rebuilt"].totals
            self.assertEqual((totals.jumps, totals.light_years, totals.bodies_scanned), (1, 22.0, 1))
            self.assertIsNone(L.plan_since_last_sale("CMDR C", folder))

    def test_starting_at_a_date_takes_the_rebuilt_totals_and_carries_on_counting(self):
        with tempfile.TemporaryDirectory() as folder:
            book = L.LogBook(clock=lambda: 1e9)
            book.load(folder)
            book.set_commander("A")
            rebuilt = L.rebuild("2026-10-01T02:00:01Z", "", [dict(jump("S1", 5.0), timestamp="2026-10-01T03:00:00Z")])
            run = book.start_at("2026-10-01T02:00:01Z", "Carry on", "Here", "Python", rebuilt)
            self.assertEqual((run.started, run.status, run.totals.jumps, run.start_system, run.ships), ("2026-10-01T02:00:01Z", L.RUNNING, 1, "S1", ["Python"]))
            book.apply(jump("S2", 7.0))
            self.assertEqual((run.totals.jumps, run.totals.light_years), (2, 12.0))


class Ships(unittest.TestCase):
    def test_a_loadout_without_a_localised_name_uses_the_table_or_a_tidied_key(self):
        self.assertEqual(L.ship_label({"Ship": "explorer_nx", "ShipName": "Far Horizon", "ShipIdent": "WN-01"}), "Caspian Explorer 'Far Horizon' WN-01")
        self.assertEqual(L.ship_label({"Ship": "some_new_ship"}), "Some New Ship")
        self.assertEqual(L.ship_label({"Ship": "python", "Ship_Localised": "Python", "ShipName": ""}), "Python")
        self.assertEqual(L.ship_label({}), "")


class Text(unittest.TestCase):
    def test_times_credits_and_durations(self):
        self.assertEqual(L.parse_time("2026-10-16"), L.parse_time("2026-10-16T00:00:00Z"))
        self.assertIsNone(L.parse_time("nonsense"))
        self.assertEqual((L.short_credits(950), L.short_credits(56_000), L.short_credits(1_234_567)), ("950", "56k", "1.2M"))
        self.assertEqual((L.duration_text(59), L.duration_text(3_700), L.duration_text(90_000)), ("0m", "1h 01m", "1d 1h"))
        self.assertEqual(L.credits(1234567), "1,234,567")


if __name__ == "__main__":
    unittest.main()
