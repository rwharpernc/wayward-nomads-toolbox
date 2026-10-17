"""Known sites (system_known.py): what Spansh lists in a system, how the survey keeps it, and that it replaces the card's "Nothing to map" line."""
from __future__ import annotations

import os
import sys
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

from plugin import system_known as K  # noqa: E402
from plugin import system_survey as S  # noqa: E402

SYSTEM = "Test Sector AB-C d1"


def record():
    return {"bodies": [
        {"name": SYSTEM, "type": "Star", "subtype": "K (Yellow-Orange) Star"},
        {"name": f"{SYSTEM} 1", "type": "Planet", "subtype": "Rocky body", "distance_to_arrival": 900.0, "estimated_mapping_value": 90_000,
         "landmarks": [{"type": "Fungoida", "subtype": "Fungoida Setisis", "count": 2, "value": 1_600_000},
                       {"type": "Bacterium", "subtype": "Bacterium Aurasus", "count": 1, "value": 1_000_000},
                       {"type": "Surface Station", "subtype": "Settlement", "count": 3, "value": 0},
                       {"type": "Geyser", "subtype": "Water Ice Geyser", "count": 9, "value": 0}]},
        {"name": f"{SYSTEM} 2", "type": "Planet", "subtype": "Icy body", "estimated_mapping_value": 5_000,
         "landmarks": [{"type": "Tourist Beacon", "subtype": "Tourist Beacon", "count": 1, "value": 0},
                       {"type": "Wrecked Ship", "subtype": "Wrecked Ship", "count": 2, "value": 0}]},
        {"name": f"{SYSTEM} 3", "type": "Planet", "subtype": "Rocky body", "landmarks": [{"type": "Surface Station", "subtype": "Settlement", "count": 1, "value": 0}]},
        "not a body", {"type": "Planet"},
    ]}


class Parse(unittest.TestCase):
    def test_biology_and_points_of_interest_are_kept_and_scenery_is_not(self):
        sites = {s.short: s for s in K.parse(record(), SYSTEM)}
        self.assertEqual(sites["1"].species, [("Fungoida Setisis", 2, 1_600_000), ("Bacterium Aurasus", 1, 1_000_000)])
        self.assertEqual(sites["1"].pois, [], "a settlement and a geyser are on almost every world, not something to go and see")
        self.assertEqual(sites["2"].pois, [("Beacon", 1), ("Wreck", 2)])
        self.assertFalse(sites["3"].interesting)

    def test_best_first_and_the_star_is_left_out(self):
        sites = K.parse(record(), SYSTEM)
        self.assertEqual([s.short for s in sites][0], "1")
        self.assertNotIn("Star", [s.short for s in sites])

    def test_damaged_records_give_nothing(self):
        for bad in (None, [], {}, {"bodies": "x"}, {"bodies": [None, 3]}):
            self.assertEqual(K.parse(bad, SYSTEM), [])

    def test_a_failed_lookup_is_retried_and_an_unknown_system_is_remembered(self):
        K._cache.clear()
        with mock.patch.object(K, "fetch", return_value=None) as fetch:
            self.assertIsNone(K.lookup(7, SYSTEM))
            self.assertIsNone(K.lookup(7, SYSTEM))
        self.assertEqual(fetch.call_count, 2, "a failure is not remembered")
        with mock.patch.object(K, "fetch", return_value={}) as fetch:
            self.assertEqual(K.lookup(8, SYSTEM), [])
            self.assertEqual(K.lookup(8, SYSTEM), [])
        self.assertEqual(fetch.call_count, 1, "Spansh not having the system is")
        K._cache.clear()


class Survey(unittest.TestCase):
    def setUp(self):
        self.survey = S.SystemSurvey()
        self.survey.handle_event({"event": "FSDJump", "StarSystem": SYSTEM, "SystemAddress": 99})

    def test_sites_are_taken_for_this_system_only(self):
        sites = K.parse(record(), SYSTEM)
        self.assertEqual(self.survey.merge_sites("Elsewhere", sites), 0)
        self.assertEqual(self.survey.merge_sites(SYSTEM, sites), len(sites))
        self.survey.handle_event({"event": "FSDJump", "StarSystem": "Elsewhere", "SystemAddress": 5})
        self.assertEqual(self.survey.sites, [], "leaving the system drops them")

    def test_finished_biology_is_dropped_and_scanned_life_is_left_to_the_life_list(self):
        self.survey.merge_sites(SYSTEM, K.parse(record(), SYSTEM))
        self.assertEqual([s.short for s in self.survey.known_to_visit()], ["1", "2"])
        self.survey.handle_event({"event": "FSSBodySignals", "BodyName": f"{SYSTEM} 1", "BodyID": 1, "Signals": [{"Type": S.BIO_TYPE, "Count": 2}]})
        self.survey.handle_event({"event": "Scan", "BodyName": f"{SYSTEM} 1", "BodyID": 1, "StarSystem": SYSTEM, "PlanetClass": "Rocky body", "MassEM": 1.0})
        self.assertEqual([s.short for s in self.survey.known_to_visit()], ["2"], "the Life list covers a body you have found life on")


class Card(unittest.TestCase):
    def test_known_sites_replace_the_nothing_line_and_get_a_section(self):
        from plugin import targets_overlay as T
        survey = S.SystemSurvey()
        survey.handle_event({"event": "FSDJump", "StarSystem": SYSTEM, "SystemAddress": 99})
        self.assertFalse(T.build_card(survey, 100_000, 6, True), "nothing known, nothing scanned: no card")
        survey.merge_sites(SYSTEM, K.parse(record(), SYSTEM))
        card = T.build_card(survey, 100_000, 6, True)
        self.assertTrue(card, "a system others surveyed shows without a honk or a scan")
        self.assertEqual(card.header[0][0], "Known (Spansh): 1 with life · 3 points of interest")
        self.assertFalse(any(h[0].startswith("Nothing") for h in card.header))
        self.assertEqual(card.rows[0][0], "Known (2)")
        self.assertEqual(card.rows[1][1], "2.6M", "the reward for the biology listed on the body")
        self.assertEqual(card.rows[2][1], "POI")

    def test_the_card_says_while_it_is_looking_and_when_there_is_nothing(self):
        from plugin import targets_overlay as T
        survey = S.SystemSurvey()
        survey.handle_event({"event": "FSDJump", "StarSystem": SYSTEM, "SystemAddress": 99})
        for status, text in (("looking", "Looking up"), ("none", "Spansh has nothing"), ("failed", "Spansh lookup failed")):
            survey.sites_status = status
            card = T.build_card(survey, 100_000, 6, True)
            self.assertTrue(card.header and card.header[0][0].startswith(text), f"{status}: {card.header}")

    def test_without_sites_the_card_is_as_before(self):
        from plugin import targets_overlay as T
        survey = S.SystemSurvey()
        survey.handle_event({"event": "FSDJump", "StarSystem": SYSTEM, "SystemAddress": 99})
        survey.handle_event({"event": "FSSDiscoveryScan", "Progress": 0.5, "BodyCount": 8})
        self.assertEqual(T.build_card(survey, 100_000, 6, True).header[0][0], "Nothing over 100k to map yet")


if __name__ == "__main__":
    unittest.main()
