"""
Unit tests for Trade mode's page model (plugin/trade_blocks.py) and the pieces that build it. No EDMC or display needed.

Run with: python -m unittest discover -s tests
"""

from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from plugin import mining_spansh_client as client  # noqa: E402
from plugin import trade_prices as prices  # noqa: E402
from plugin.trade_blocks import Columns, Heading, Item, Note, Pair, to_text  # noqa: E402


class ToTextTests(unittest.TestCase):
    def test_each_block_has_a_plain_form(self) -> None:
        lines = to_text([
            Heading("Near me"), Pair("Hold", "10 / 20 t"), Pair("Gold", "+5 cr", indent=1),
            Columns(("cr/t", "Total")), Item("Port", ("1", "2"), detail="Sys · orbital", warn="Only 3 t"),
            Note("one\ntwo"),
        ])
        self.assertEqual(lines, ["Near me", "Hold: 10 / 20 t", "  Gold: +5 cr", "cr/t  Total",
                                 "  Port  1  2", "    Sys · orbital - Only 3 t", "one", "two"])

    def test_blocks_compare_by_value_so_an_unchanged_page_can_be_skipped(self) -> None:
        self.assertEqual([Pair("a", "b")], [Pair("a", "b")])
        self.assertNotEqual(Pair("a", "b"), Pair("a", "b", bold=True))
        self.assertEqual(Item("x", ("1",)), Item("x", ("1",)))


def _place(name: str, planetary: bool, kind: str = "Settlement") -> client.StationPrice:
    return client.StationPrice(station=name, system="Sys", station_type=kind, distance_ly=5.0, distance_to_arrival_ls=10.0,
                               is_planetary=planetary, price=100, quantity=50, small_pads=1, medium_pads=1, large_pads=1)


class GroundFacilityTests(unittest.TestCase):
    def test_ground_facilities_can_be_left_out(self) -> None:
        results = [_place("Ground", True, "Planetary Port"), _place("Orbital", False, "Coriolis Starport")]
        self.assertEqual([o.station for o in prices.rank_offers(results, 10)], ["Ground", "Orbital"])
        self.assertEqual([o.station for o in prices.rank_offers(results, 10, include_ground=False)], ["Orbital"])

    def test_a_carrier_is_never_treated_as_a_ground_facility(self) -> None:
        carrier = _place("FC", False, "Drake-Class Carrier")
        self.assertEqual(len(prices.rank_offers([carrier], 10, include_ground=False)), 1)

    def test_the_type_lists_split_orbital_from_ground(self) -> None:
        orbital = prices.station_types(include_ground=False)
        everything = prices.station_types(include_ground=True)
        self.assertTrue(set(orbital) < set(everything))
        self.assertFalse({"Planetary Outpost", "Planetary Port", "Settlement"} & set(orbital))
        self.assertTrue({"Coriolis Starport", "Orbis Starport", "Ocellus Starport", "Outpost"} <= set(orbital))
        self.assertFalse(any("carrier" in t.lower() for t in everything))


if __name__ == "__main__":
    unittest.main()
