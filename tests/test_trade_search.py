"""
Unit tests for Trade mode's search side: commodity names, ship pad sizes, offer ranking and the
fleet carrier cargo record. No EDMC runtime and no network needed.

Run with: python -m unittest discover -s tests
"""

from __future__ import annotations

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from plugin import mining_spansh_client as prices_client  # noqa: E402
from plugin import trade_carrier as carrier  # noqa: E402
from plugin import trade_commodities as commodities  # noqa: E402
from plugin import trade_prices as prices  # noqa: E402
from plugin import trade_ship as ship  # noqa: E402


class CommodityTests(unittest.TestCase):
    def test_resolve_uses_the_names_spansh_knows(self) -> None:
        # Spansh's market search is case-sensitive and uses these exact names (checked live 2026-10-09).
        self.assertEqual(commodities.resolve("Void Opals"), "Void Opal")  # the journal's plural finds nothing there
        self.assertEqual(commodities.resolve("lowtemperaturediamond"), "Low Temperature Diamonds")
        self.assertEqual(commodities.resolve("liquid OXYGEN"), "Liquid oxygen")
        self.assertEqual(commodities.resolve("  gold "), "Gold")

    def test_unknown_or_empty_does_not_resolve(self) -> None:
        self.assertIsNone(commodities.resolve("nonsense"))
        self.assertIsNone(commodities.resolve(""))
        self.assertIsNone(commodities.resolve(None))

    def test_suggestions_prefix_first_and_preferred_lead(self) -> None:
        self.assertEqual(commodities.suggest("gol")[0], "Gold")
        names = commodities.suggest("", ["gold", "lowtemperaturediamond", "unknownthing"])
        self.assertEqual(names, ["Gold", "Low Temperature Diamonds"])
        self.assertLessEqual(len(commodities.suggest("a", limit=5)), 5)

    def test_suggestions_leave_out_salvage_but_it_still_resolves(self) -> None:
        self.assertNotIn("Black Box", commodities.SUGGESTIBLE)
        self.assertEqual(commodities.resolve("Black Box"), "Black Box")
        self.assertNotIn("Limpets", commodities.SUGGESTIBLE)

    def test_mining_price_finder_uses_the_exact_game_name(self) -> None:
        self.assertEqual(prices_client._normalize_commodity_name("liquid oxygen"), "Liquid oxygen")


class ShipPadTests(unittest.TestCase):
    def test_journal_names_map_to_pad_sizes(self) -> None:
        for name, pad in (("cobramkiii", "small"), ("sidewinder", "small"), ("asp", "medium"), ("python", "medium"),
                          ("federation_dropship", "medium"), ("type9", "large"), ("anaconda", "large"),
                          ("empire_trader", "large"), ("cutter", "large")):
            self.assertEqual(ship.pad_size(name), pad, name)

    def test_unknown_ship_gives_none(self) -> None:
        self.assertIsNone(ship.pad_size("somenewship"))
        self.assertIsNone(ship.pad_size(None))

    def test_a_ship_fits_a_pad_its_size_or_bigger(self) -> None:
        self.assertTrue(ship.fits("small", 0, 0, 0))
        self.assertFalse(ship.fits("medium", 4, 0, 0))   # only small pads
        self.assertTrue(ship.fits("medium", 4, 1, 0))
        self.assertTrue(ship.fits("medium", 0, 0, 2))    # a large pad takes a medium ship
        self.assertFalse(ship.fits("large", 4, 2, 0))    # an outpost with no large pad
        self.assertTrue(ship.fits("large", 4, 2, 1))

    def test_missing_pad_data_is_not_held_against_a_station(self) -> None:
        self.assertTrue(ship.fits("large", None, None, None))
        self.assertTrue(ship.fits(None, 0, 0, 0))


def station(name: str, price: int, demand: int, kind: str = "Coriolis Starport", ly: float = 10.0,
            pads: tuple = (4, 4, 2)) -> prices_client.StationPrice:
    return prices_client.StationPrice(
        station=name, system="Sys", station_type=kind, distance_ly=ly, distance_to_arrival_ls=100.0,
        is_planetary=False, price=price, quantity=demand, small_pads=pads[0], medium_pads=pads[1], large_pads=pads[2])


class OfferRankingTests(unittest.TestCase):
    def test_ranked_by_what_your_load_actually_earns(self) -> None:
        results = [station("HighPriceLowDemand", 95_000, 40), station("LowerPriceBigDemand", 90_000, 5_000)]
        offers = prices.rank_offers(results, 200)
        self.assertEqual([o.station for o in offers], ["LowerPriceBigDemand", "HighPriceLowDemand"])
        self.assertEqual(offers[0].revenue, 90_000 * 200)
        self.assertEqual(offers[1].sellable_t, 40)

    def test_stations_without_a_suitable_pad_are_dropped(self) -> None:
        results = [station("Outpost", 90_000, 500, "Outpost", pads=(2, 1, 0)), station("Port", 80_000, 500)]
        self.assertEqual([o.station for o in prices.rank_offers(results, 100, ship_pad="large")], ["Port"])
        self.assertEqual(len(prices.rank_offers(results, 100, ship_pad="small")), 2)

    def test_carriers_are_kept_apart_and_always_fit(self) -> None:
        results = [station("FC", 95_000, 500, "Drake-Class Carrier", pads=(0, 0, 0)), station("Port", 80_000, 500)]
        offers = prices.rank_offers(results, 100, ship_pad="large")
        stations, carriers = prices.split_carriers(offers)
        self.assertEqual([o.station for o in stations], ["Port"])
        self.assertEqual([o.station for o in carriers], ["FC"])
        self.assertEqual([o.station for o in prices.rank_offers(results, 100, include_carriers=False)], ["Port"])

    def test_carrier_note_only_when_a_carrier_would_pay_more(self) -> None:
        stations, carriers = prices.split_carriers(prices.rank_offers(
            [station("FC", 95_000, 500, "Drake-Class Carrier"), station("Port", 80_000, 500)], 100))
        self.assertIn("1,500,000 cr more", prices.carrier_note(stations, carriers))
        cheap, _ = prices.split_carriers(prices.rank_offers([station("Port", 99_000, 500)], 100))
        self.assertIsNone(prices.carrier_note(cheap, carriers))
        self.assertIsNone(prices.carrier_note(stations, []))

    def test_verdict_compares_near_with_galaxy(self) -> None:
        near = prices.rank_offers([station("Near", 60_000, 500, ly=20)], 100)
        galaxy = prices.rank_offers([station("Far", 90_000, 500, ly=120)], 100)
        text = prices.verdict(near, galaxy)
        self.assertIn("Far", text)
        self.assertIn("+50%", text)
        self.assertIsNone(prices.verdict(near, []))
        self.assertIn("nearby", prices.verdict(galaxy, near))


class CarrierCargoTests(unittest.TestCase):
    STATS = {"event": "CarrierStats", "Callsign": "ABC-123", "Name": "Wayward Hauler",
             "timestamp": "2026-10-09T10:00:00Z",
             "SpaceUsage": {"TotalCapacity": 25_000, "Crew": 6_000, "Cargo": 4_000, "CargoSpaceReserved": 500,
                            "ShipPacks": 0, "ModulePacks": 1_000, "FreeSpace": 13_500}}

    def test_stats_give_capacity_used_and_free(self) -> None:
        record = carrier.parse_stats(self.STATS)
        self.assertEqual((record["capacity"], record["cargo"], record["reserved"], record["free"]),
                         (18_000, 4_000, 500, 13_500))
        lines = carrier.cargo_lines(record)
        self.assertIn("Wayward Hauler", lines[0])
        self.assertIn("4,000/18,000 t used, 13,500 t free", lines[1])
        self.assertIn("500 t reserved", lines[2])

    def test_free_space_is_worked_out_when_the_journal_omits_it(self) -> None:
        usage = {k: v for k, v in self.STATS["SpaceUsage"].items() if k != "FreeSpace"}
        self.assertEqual(carrier.parse_stats({**self.STATS, "SpaceUsage": usage})["free"], 13_500)

    def test_transfers_move_the_used_figure_and_never_go_negative(self) -> None:
        record = carrier.parse_stats(self.STATS)
        carrier.apply_transfer(record, {"Transfers": [{"Type": "gold", "Count": 100, "Direction": "tocarrier"}]})
        self.assertEqual((record["cargo"], record["free"]), (4_100, 13_400))
        carrier.apply_transfer(record, {"Transfers": [{"Type": "gold", "Count": 99_999, "Direction": "toship"}]})
        self.assertEqual(record["cargo"], 0)
        self.assertFalse(carrier.apply_transfer(record, {"Transfers": [{"Count": 5, "Direction": "tosrv"}]}))

    def test_no_carrier_means_no_lines(self) -> None:
        self.assertEqual(carrier.cargo_lines(None), [])
        self.assertIsNone(carrier.parse_stats({"event": "CarrierStats"}))

    def test_a_new_carrier_asks_for_one_visit_to_management(self) -> None:
        lines = carrier.cargo_lines(carrier.note_purchase({"Callsign": "XYZ-999"}))
        self.assertIn("XYZ-999", lines[0])
        self.assertIn("Carrier Management", lines[1])

    def test_each_commander_has_their_own_record(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            self.assertEqual(carrier.load_all(folder), {})
            carrier.save_all(folder, {"Bocheaux": carrier.parse_stats(self.STATS)})
            self.assertEqual(set(carrier.load_all(folder)), {"Bocheaux"})


if __name__ == "__main__":
    unittest.main()
