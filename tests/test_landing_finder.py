"""Nearest place to land (landing_finder.py): the request, the pad and service rules, the carrier rules, the age text and the position tracker."""
import json
import os
import sys
import tempfile
import unittest
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from plugin import landing_finder as F  # noqa: E402

POS = (-624.78125, -24.5625, 23273.25)


def record(name="Anchorage", kind="Ocellus Starport", distance=10.0, small=4, medium=2, large=1, services=("Dock", "Refuel", "Repair", "Restock"),
           updated="2026-10-10T00:00:00Z", access=None, planetary=False, arrival=500.0):
    out = {"name": name, "system_name": "Sys " + name, "type": kind, "distance": distance, "distance_to_arrival": arrival, "is_planetary": planetary,
           "small_pads": small, "medium_pads": medium, "large_pads": large, "services": [{"name": s} for s in services], "updated_at": updated}
    if access:
        out["carrier_docking_access"] = access
    return out


class RequestTests(unittest.TestCase):
    def test_stations_are_asked_for_by_coordinates_with_the_pad_services_and_types(self):
        body = F.build_request(POS, "medium", ("Refuel", "Repair"), False, 14)
        self.assertEqual(body["reference_coords"], {"x": POS[0], "y": POS[1], "z": POS[2]})
        self.assertNotIn("reference_system", body)                                  # a new system is not in any database; its coordinates still work
        self.assertEqual(body["sort"], [{"distance": {"direction": "asc"}}])
        filters = body["filters"]
        self.assertEqual(filters["services"], [{"name": "Refuel"}, {"name": "Repair"}])
        self.assertEqual(filters["medium_pads"], {"comparison": "<=>", "value": [1, 999]})
        self.assertEqual(filters["type"]["value"], list(F.STATION_TYPES))
        self.assertNotIn(F.CARRIER_TYPE, filters["type"]["value"])
        self.assertNotIn("carrier_docking_access", filters)

    def test_carriers_are_asked_for_when_open_to_all_and_recently_reported(self):
        filters = F.build_request(POS, "large", ("Refuel",), True, 30)["filters"]
        self.assertEqual(filters["type"], {"value": [F.CARRIER_TYPE]})
        self.assertEqual(filters["carrier_docking_access"], {"value": ["All"]})
        self.assertEqual(filters["updated_at"], {"comparison": "<=>", "value": ["now-30d", "now"]})
        self.assertIn("large_pads", filters)

    def test_a_small_ship_or_an_unknown_one_asks_for_no_pad_and_no_services_asks_for_none(self):
        filters = F.build_request(POS, None, (), False, 14)["filters"]
        self.assertFalse([k for k in filters if k.endswith("_pads")])
        self.assertNotIn("services", filters)
        self.assertEqual(F.build_request(POS, None, ("Bogus", "Repair"), False, 14)["filters"]["services"], [{"name": "Repair"}])


class ShipTests(unittest.TestCase):
    def test_the_pad_comes_from_the_ship(self):
        self.assertEqual(F.ship_pad("python"), "medium")
        self.assertEqual(F.ship_pad("anaconda"), "large")
        self.assertEqual(F.ship_pad("cobramkiii"), "small")
        self.assertIsNone(F.ship_pad("not_a_ship"))
        self.assertIsNone(F.ship_pad(None))

    def test_auto_follows_the_ship_a_small_or_unknown_ship_needs_no_restriction_and_a_choice_is_used(self):
        self.assertEqual(F.pad_for(F.PAD_AUTO, "anaconda"), "large")
        self.assertEqual(F.pad_for(F.PAD_AUTO, "python"), "medium")
        self.assertIsNone(F.pad_for(F.PAD_AUTO, "cobramkiii"))
        self.assertIsNone(F.pad_for(F.PAD_AUTO, None))
        self.assertEqual(F.pad_for(F.PAD_LARGE, "cobramkiii"), "large")
        self.assertIsNone(F.pad_for(F.PAD_ANY, "anaconda"))


class FindTests(unittest.TestCase):
    def setUp(self):
        F.clear_cache()
        self.addCleanup(F.clear_cache)
        self.calls = []

    def search(self, stations, carriers):
        def ask(body):
            self.calls.append(body)
            return {"results": carriers if body["filters"]["type"]["value"] == [F.CARRIER_TYPE] else stations}
        return ask

    def test_stations_and_carriers_are_listed_nearest_first_and_only_what_fits(self):
        stations = [record("Far", distance=300), record("Near", distance=20), record("NoRepair", services=("Dock", "Refuel"), distance=5),
                    record("Tiny", small=3, medium=0, large=0, distance=6), record("Carrier", kind=F.CARRIER_TYPE, distance=1, access="All")]
        carriers = [record("ABC-123", kind=F.CARRIER_TYPE, distance=80, access="All"), record("XYZ-999", kind=F.CARRIER_TYPE, distance=40, access="All"),
                    record("Closed", kind=F.CARRIER_TYPE, distance=10, access="Friends"), record("Unknown", kind=F.CARRIER_TYPE, distance=11),
                    record("Starport", distance=2)]
        result = F.find(POS, "medium", ("Refuel", "Repair"), True, 14, search=self.search(stations, carriers))
        self.assertEqual([p.name for p in result.stations], ["Near", "Far"])           # no repair, no medium pad and a carrier in the station list are dropped
        self.assertEqual([p.name for p in result.carriers], ["XYZ-999", "ABC-123"])    # closed or unknown access and a non-carrier are dropped
        self.assertTrue(all(p.is_carrier for p in result.carriers))
        self.assertEqual(len(self.calls), 2)

    def test_carriers_are_not_asked_for_when_not_wanted(self):
        result = F.find(POS, None, ("Refuel",), False, 14, search=self.search([record()], []))
        self.assertEqual(len(self.calls), 1)
        self.assertEqual((result.carriers, result.carriers_asked), ((), False))

    def test_the_same_question_is_answered_from_memory_for_two_minutes(self):
        clock = [0.0]
        ask = self.search([record()], [])
        F.find(POS, None, ("Refuel",), False, 14, search=ask, now=lambda: clock[0])
        F.find(POS, None, ("Refuel",), False, 14, search=ask, now=lambda: clock[0] + 100)
        self.assertEqual(len(self.calls), 1)
        F.find(POS, None, ("Refuel",), False, 14, search=ask, now=lambda: clock[0] + 130)
        self.assertEqual(len(self.calls), 2)

    def test_an_unknown_position_is_refused_in_plain_words(self):
        for position in (None, (1, 2), ("a", "b", "c")):
            with self.assertRaises(ValueError):
                F.find(position, None, search=self.search([], []))

    def test_a_failed_search_is_not_remembered(self):
        def broken(body):
            raise OSError("offline")
        with self.assertRaises(OSError):
            F.find(POS, None, search=broken)
        result = F.find(POS, None, search=self.search([record()], []))
        self.assertEqual(len(result.stations), 1)


class ReadingTests(unittest.TestCase):
    def test_how_old_a_record_is(self):
        now = datetime(2026, 10, 16, tzinfo=timezone.utc)
        self.assertEqual(F.age_text("2026-10-16T03:00:00Z", now), "today")
        self.assertEqual(F.age_text("2026-10-15T00:00:00Z", now), "1 day ago")
        self.assertEqual(F.age_text("2026-10-03T00:00:00Z", now), "13 days ago")
        self.assertEqual(F.age_text("2026-03-08T00:00:00Z", now), "7 months ago")
        self.assertEqual(F.age_text("2023-05-15T00:00:00Z", now), "3 years ago")
        self.assertEqual(F.age_text("", now), "unknown")
        self.assertEqual(F.age_text("not a time", now), "unknown")

    def test_a_place_reads_in_plain_words(self):
        place = F.to_place(record("A", planetary=True, kind="Planetary Outpost", arrival=80, small=4, medium=0, large=1))
        self.assertEqual(F.describe_place(place), "ground Planetary Outpost, 80 ls")
        self.assertEqual(F.pads_text(place), "S4 L1")
        self.assertEqual(F.services_text(place, ("Refuel", "Outfitting", "Repair")), "Refuel, Repair")
        self.assertEqual(F.services_text(place, ("Outfitting",)), "-")
        self.assertEqual(F.describe_place(F.to_place(record("C", kind=F.CARRIER_TYPE))), "fleet carrier")
        self.assertEqual(F.pads_text(F.to_place({"name": "x"})), "?")


class TrackerTests(unittest.TestCase):
    def test_a_jump_a_location_and_a_carrier_jump_give_the_position_and_a_loadout_the_ship(self):
        tracker = F.Tracker()
        self.assertTrue(tracker.apply({"event": "FSDJump", "StarSystem": "Sys A", "StarPos": [1, 2, 3]}))
        self.assertEqual((tracker.position, tracker.system), ((1.0, 2.0, 3.0), "Sys A"))
        self.assertFalse(tracker.apply({"event": "Location", "StarSystem": "Sys A", "StarPos": [1, 2, 3]}))      # nothing changed
        self.assertTrue(tracker.apply({"event": "CarrierJump", "StarSystem": "Sys B", "StarPos": [4, 5, 6]}))
        self.assertEqual(tracker.system, "Sys B")
        self.assertTrue(tracker.apply({"event": "Loadout", "Ship": "python"}))
        self.assertEqual(tracker.ship, "python")
        self.assertFalse(tracker.apply({"event": "Loadout", "Ship": "python"}))

    def test_bad_positions_and_other_events_are_ignored(self):
        tracker = F.Tracker()
        for entry in ({"event": "FSDJump", "StarPos": [1, 2]}, {"event": "FSDJump", "StarPos": ["a", "b", "c"]}, {"event": "Scan"}, {"event": "Loadout"}):
            self.assertFalse(tracker.apply(entry))
        self.assertIsNone(tracker.position)

    def test_the_newest_journals_give_the_position_and_ship_when_edmc_starts_mid_session(self):
        with tempfile.TemporaryDirectory() as folder:
            lines = [{"event": "Loadout", "Ship": "anaconda"}, {"event": "Location", "StarSystem": "Old", "StarPos": [0, 0, 0]},
                     {"event": "Scan", "BodyName": "x"}, {"event": "FSDJump", "StarSystem": "Latest", "StarPos": [7, 8, 9]}]
            with open(os.path.join(folder, "Journal.2026-10-16T000000.01.log"), "w", encoding="utf-8") as handle:
                handle.write("\n".join(json.dumps(line) for line in lines) + "\n")
            tracker = F.read_from_journals(folder)
        self.assertEqual((tracker.position, tracker.system, tracker.ship), ((7.0, 8.0, 9.0), "Latest", "anaconda"))

    def test_no_journals_give_nothing(self):
        with tempfile.TemporaryDirectory() as folder:
            self.assertIsNone(F.read_from_journals(folder).position)


if __name__ == "__main__":
    unittest.main()
