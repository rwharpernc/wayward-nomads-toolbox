"""GEC Nearby POI: the nearest point of interest is worked out from edastro's full list, so it changes with position.

A live check on 2026-10-10 found edastro's own `nearest` endpoint answering "The Solar System" for every coordinate; these
tests keep the plugin honest about that: different positions must give different answers. No network is used.
"""
from __future__ import annotations

import json
import os
import sys
import types
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
if "config" not in sys.modules:
    _stub = types.ModuleType("config")
    _stub.appname = "EDMarketConnector"
    _stub.config = types.SimpleNamespace(get_str=lambda key: "", default_journal_dir="")
    sys.modules["config"] = _stub

from plugin import gec_poi_edastro as gec  # noqa: E402


def item(name: str, coords, rating=7.5, **extra) -> dict:
    return {"name": name, "coordinates": coords, "type": "Sights and Scenery", "region": "Somewhere", "rating": rating,
            "galMapSearch": f"{name} System", "poiUrl": "https://edastro.com/gec/view/1", **extra}


CATALOG = json.dumps([
    item("The Solar System", [0, 0, 0], 9.0),
    item("Colonia", [-9530.5, -910.28, 19808.1], 8.0),
    item("Beagle Point", [-1111.56, -134.22, 65269.75], 9.5),
    item("Low rated near Sol", [5, 0, 0], 3.0),
])


class NearestTests(unittest.TestCase):
    def setUp(self) -> None:
        self.entries = gec.parse_catalog(CATALOG)

    def test_different_positions_give_different_answers(self) -> None:
        sol = gec.nearest_in(self.entries, 1, 0, 0)
        colonia = gec.nearest_in(self.entries, -9500, -900, 19800)
        beagle = gec.nearest_in(self.entries, -1100, -130, 65000)
        self.assertEqual([sol.name, colonia.name, beagle.name], ["The Solar System", "Colonia", "Beagle Point"])

    def test_distance_is_straight_line_light_years_and_fields_are_carried(self) -> None:
        poi = gec.nearest_in(self.entries, 3, 4, 0)
        self.assertEqual(poi.name, "Low rated near Sol")      # 4.12 ly away, closer than Sol at 5
        self.assertAlmostEqual(poi.distance_ly, ((5 - 3) ** 2 + 4 ** 2) ** 0.5)
        self.assertEqual((poi.system, poi.region, poi.rating), ("Low rated near Sol System", "Somewhere", 3.0))
        self.assertEqual(poi.url, "https://edastro.com/gec/view/1")

    def test_minimum_rating_skips_low_rated_entries(self) -> None:
        self.assertEqual(gec.nearest_in(self.entries, 5, 0, 0, min_rating=8.0).name, "The Solar System")
        with self.assertRaises(ValueError):
            gec.nearest_in(self.entries, 0, 0, 0, min_rating=10.0)

    def test_bad_entries_are_skipped_and_an_unusable_list_is_an_error(self) -> None:
        messy = json.dumps([item("Good", [1, 2, 3]), {"name": "no coords"}, item("Bad coords", [1, 2]),
                            item("Strings", ["1", "2", "3"]), "junk", item(None, [0, 0, 0])])
        self.assertEqual([e[3].name for e in gec.parse_catalog(messy)], ["Good"])
        for bad in ("[]", "{}", json.dumps([{"name": "x"}]), "not json"):
            with self.assertRaises(ValueError):
                gec.parse_catalog(bad)

    def test_a_missing_rating_or_link_is_tolerated(self) -> None:
        entry = gec.parse_catalog(json.dumps([{"name": "Plain", "coordinates": [0, 0, 0]}]))[0][3]
        self.assertIsNone(entry.rating)
        self.assertIsNone(entry.url)
        self.assertEqual((entry.category, entry.region, entry.system), ("Unknown", "Unknown region", ""))


if __name__ == "__main__":
    unittest.main()
