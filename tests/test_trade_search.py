"""
Unit tests for Trade mode's search side: commodity names, ship pad sizes, offer ranking and the
fleet carrier cargo record. No EDMC runtime and no network needed.

Run with: python -m unittest discover -s tests
"""

from __future__ import annotations

import json
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


def _line(**fields) -> str:
    return json.dumps(fields, separators=(",", ":")) + "\n"


FLEET = carrier.FLEET
SQUADRON = carrier.SQUADRON


def stats_event(ctype: str = FLEET, cargo: int = 4_000, carrier_id: int = 111, stamp: str = "2026-10-09T10:00:00Z",
                name: str = "Wayward Hauler", reserved: int = 500) -> dict:
    return {"event": "CarrierStats", "CarrierID": carrier_id, "CarrierType": ctype, "Callsign": "ABC-123", "Name": name,
            "timestamp": stamp,
            "SpaceUsage": {"TotalCapacity": 25_000, "Crew": 6_000, "Cargo": cargo, "CargoSpaceReserved": reserved,
                           "ShipPacks": 0, "ModulePacks": 1_000, "FreeSpace": 18_000 - cargo - reserved}}


def transfer_event(count: int, stamp: str = "2026-10-09T10:30:00Z", direction: str = "tocarrier") -> dict:
    return {"event": "CargoTransfer", "timestamp": stamp,
            "Transfers": [{"Type": "gold", "Count": count, "Direction": direction}]}


def docked_event(market_id: int, station_type: str = FLEET) -> dict:
    return {"event": "Docked", "MarketID": market_id, "StationType": station_type}


class CarrierCargoTests(unittest.TestCase):
    def test_stats_give_capacity_used_and_free(self) -> None:
        record = carrier.parse_stats(stats_event())
        self.assertEqual((record["capacity"], record["cargo"], record["reserved"], record["free"]),
                         (18_000, 4_000, 500, 13_500))
        self.assertEqual((record["type"], record["id"]), (FLEET, 111))
        lines = carrier.cargo_lines({FLEET: record})
        self.assertEqual(lines[0], "Fleet carrier: Wayward Hauler")
        self.assertIn("4,000/18,000 t used, 13,500 t free", lines[1])
        self.assertIn("500 t reserved", lines[2])

    def test_free_space_is_worked_out_when_the_journal_omits_it(self) -> None:
        event = stats_event()
        del event["SpaceUsage"]["FreeSpace"]
        self.assertEqual(carrier.parse_stats(event)["free"], 13_500)

    def test_a_squadron_carrier_is_its_own_type(self) -> None:
        self.assertEqual(carrier.parse_stats(stats_event(SQUADRON))["type"], SQUADRON)
        self.assertEqual(carrier.parse_stats({**stats_event(), "CarrierType": None})["type"], FLEET)

    def test_transfers_move_the_used_figure_and_never_go_negative(self) -> None:
        record = carrier.parse_stats(stats_event())
        carrier.apply_transfer(record, transfer_event(100))
        self.assertEqual((record["cargo"], record["free"]), (4_100, 13_400))
        carrier.apply_transfer(record, transfer_event(99_999, direction="toship"))
        self.assertEqual(record["cargo"], 0)
        self.assertFalse(carrier.apply_transfer(record, transfer_event(5, direction="tosrv")))

    def test_no_carrier_means_no_lines(self) -> None:
        self.assertEqual(carrier.cargo_lines(None), [])
        self.assertEqual(carrier.cargo_lines({}), [])
        self.assertIsNone(carrier.parse_stats({"event": "CarrierStats"}))

    def test_a_new_carrier_asks_for_one_visit_to_management(self) -> None:
        lines = carrier.cargo_lines({FLEET: carrier.note_purchase({"Callsign": "XYZ-999"})})
        self.assertIn("XYZ-999", lines[0])
        self.assertIn("Carrier Management", lines[1])

    def test_each_commander_has_their_own_records_keyed_ignoring_case(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            self.assertEqual(carrier.load_all(folder), {})
            carrier.save_all(folder, {"bocheaux": {FLEET: carrier.parse_stats(stats_event())}})
            self.assertEqual(set(carrier.load_all(folder)), {"bocheaux"})

    def test_an_older_flat_save_is_read_as_a_fleet_carrier(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            flat = {"Bocheaux": {k: v for k, v in carrier.parse_stats(stats_event()).items() if k != "type"}}
            with open(os.path.join(folder, carrier.STATE_FILENAME), "w", encoding="utf-8") as handle:
                json.dump(flat, handle)
            loaded = carrier.load_all(folder)
        self.assertEqual(loaded["bocheaux"][FLEET]["cargo"], 4_000)


class CarrierChoiceTests(unittest.TestCase):
    PRESENT = {FLEET: {}, SQUADRON: {}}

    def test_auto_shows_what_has_been_seen(self) -> None:
        self.assertEqual(carrier.visible_types(carrier.AUTO, [FLEET]), [FLEET])
        self.assertEqual(carrier.visible_types(carrier.AUTO, [SQUADRON, FLEET]), [FLEET, SQUADRON])
        self.assertEqual(carrier.visible_types("junk", []), [])

    def test_the_choice_limits_what_is_shown(self) -> None:
        self.assertEqual(carrier.visible_types(carrier.NONE, [FLEET, SQUADRON]), [])
        self.assertEqual(carrier.visible_types(carrier.FLEET_ONLY, [FLEET, SQUADRON]), [FLEET])
        self.assertEqual(carrier.visible_types(carrier.SQUADRON_ONLY, [FLEET]), [SQUADRON])
        self.assertEqual(carrier.visible_types(carrier.BOTH, []), [FLEET, SQUADRON])

    def test_none_hides_even_a_known_carrier(self) -> None:
        records = {FLEET: carrier.parse_stats(stats_event())}
        self.assertEqual(carrier.cargo_lines(records, carrier.NONE), [])

    def test_a_chosen_carrier_not_yet_seen_asks_for_a_visit(self) -> None:
        lines = carrier.cargo_lines({FLEET: carrier.parse_stats(stats_event())}, carrier.BOTH)
        self.assertEqual([l for l in lines if "carrier" in l.lower() and not l.startswith(" ")],
                         ["Fleet carrier: Wayward Hauler", "Squadron carrier"])
        self.assertIn("Carrier Management", lines[-1])

    def test_both_carriers_are_listed_separately(self) -> None:
        records = {FLEET: carrier.parse_stats(stats_event(FLEET, 1_000, name="Fleety")),
                   SQUADRON: carrier.parse_stats(stats_event(SQUADRON, 2_000, 222, name="Squaddy"))}
        text = "\n".join(carrier.cargo_lines(records))
        self.assertIn("Fleet carrier: Fleety", text)
        self.assertIn("Squadron carrier: Squaddy", text)
        self.assertIn("1,000/18,000", text)
        self.assertIn("2,000/18,000", text)


class CarrierTrackerTests(unittest.TestCase):
    def _tracker(self, *events: dict) -> carrier.CarrierTracker:
        tracker = carrier.CarrierTracker()
        tracker.set_cmdr("Bocheaux")
        for event in events:
            tracker.feed(event)
        return tracker

    def test_a_transfer_goes_to_the_carrier_you_are_docked_at(self) -> None:
        tracker = self._tracker(stats_event(FLEET, 1_000, 111), stats_event(SQUADRON, 2_000, 222),
                                docked_event(222, SQUADRON), transfer_event(300))
        mine = tracker.records["bocheaux"]
        self.assertEqual((mine[FLEET]["cargo"], mine[SQUADRON]["cargo"]), (1_000, 2_300))

    def test_docked_at_someone_elses_carrier_counts_nothing(self) -> None:
        tracker = self._tracker(stats_event(FLEET, 1_000, 111), docked_event(999), transfer_event(300))
        self.assertEqual(tracker.records["bocheaux"][FLEET]["cargo"], 1_000)

    def test_two_carriers_and_no_dock_information_is_not_guessed(self) -> None:
        tracker = self._tracker(stats_event(FLEET, 1_000, 111), stats_event(SQUADRON, 2_000, 222), transfer_event(300))
        mine = tracker.records["bocheaux"]
        self.assertEqual((mine[FLEET]["cargo"], mine[SQUADRON]["cargo"]), (1_000, 2_000))

    def test_one_carrier_and_no_dock_information_takes_the_transfer(self) -> None:
        tracker = self._tracker(stats_event(FLEET, 1_000, 111), transfer_event(300))
        self.assertEqual(tracker.records["bocheaux"][FLEET]["cargo"], 1_300)

    def test_undocking_and_a_new_login_forget_the_dock(self) -> None:
        tracker = self._tracker(stats_event(FLEET, 1_000, 111), stats_event(SQUADRON, 2_000, 222),
                                docked_event(222, SQUADRON), {"event": "Undocked"}, transfer_event(300))
        self.assertEqual(tracker.records["bocheaux"][SQUADRON]["cargo"], 2_000)
        tracker.feed(docked_event(111))
        tracker.feed({"event": "LoadGame", "Commander": "BOCHEAUX"})
        self.assertEqual(tracker.dock_state(), (0, ""))

    def test_location_while_docked_sets_the_dock(self) -> None:
        tracker = self._tracker(stats_event(FLEET, 1_000, 111), stats_event(SQUADRON, 2_000, 222),
                                {"event": "Location", "Docked": True, "MarketID": 111, "StationType": FLEET},
                                transfer_event(50))
        self.assertEqual(tracker.records["bocheaux"][FLEET]["cargo"], 1_050)

    def test_merge_keeps_the_newer_record(self) -> None:
        held = {"bocheaux": {FLEET: carrier.parse_stats(stats_event(cargo=100, stamp="2026-10-09T12:00:00Z"))}}
        older = {"bocheaux": {FLEET: carrier.parse_stats(stats_event(cargo=999, stamp="2026-10-09T11:00:00Z"))}}
        newer = {"bocheaux": {FLEET: carrier.parse_stats(stats_event(cargo=555, stamp="2026-10-09T13:00:00Z"))}}
        self.assertFalse(carrier.merge(held, older))
        self.assertEqual(held["bocheaux"][FLEET]["cargo"], 100)
        self.assertTrue(carrier.merge(held, newer))
        self.assertEqual(held["bocheaux"][FLEET]["cargo"], 555)


class CarrierBackfillTests(unittest.TestCase):
    """The shape of a real session: baseline seen, then transfers, with EDMC started afterwards."""

    def _journal(self, folder: str, name: str, lines: list) -> None:
        with open(os.path.join(folder, name), "w", encoding="utf-8") as handle:
            handle.writelines(lines)

    def test_baseline_plus_later_transfers_for_the_carrier_you_docked_at(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            self._journal(folder, "Journal.2026-10-09T053605.01.log", [
                _line(event="Commander", Name="BOCHEAUX"),
                _line(**docked_event(3707024384)),
                _line(**stats_event(FLEET, 2_530, 3707024384, "2026-10-09T10:07:13Z", "ELDER WARDEN", 0)),
                _line(**transfer_event(1_265, "2026-10-09T10:07:38Z")),
                _line(event="Cargo", Vessel="Ship", Count=0),
                _line(**transfer_event(1_265, "2026-10-09T10:17:25Z")),
            ])
            records = carrier.backfill(folder)
        record = records["bocheaux"][FLEET]
        self.assertEqual((record["cargo"], record["free"]), (5_060, 18_000 - 5_060))
        self.assertEqual(record["updated"], "2026-10-09T10:17:25Z")

    def test_a_baseline_in_an_older_file_still_counts(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            self._journal(folder, "Journal.2026-10-08T100000.01.log", [
                _line(event="LoadGame", Commander="BOCHEAUX"), _line(**stats_event(cargo=1_000))])
            self._journal(folder, "Journal.2026-10-09T100000.01.log", [
                _line(event="LoadGame", Commander="BOCHEAUX"), _line(**transfer_event(500))])
            self.assertEqual(carrier.backfill(folder)["bocheaux"][FLEET]["cargo"], 1_500)

    def test_commanders_are_kept_apart_and_one_without_a_carrier_gets_nothing(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            self._journal(folder, "Journal.2026-10-09T100000.01.log", [
                _line(event="LoadGame", Commander="BOCHEAUX"), _line(**stats_event(cargo=100)),
                _line(event="LoadGame", Commander="MACTAVIOUS"), _line(**transfer_event(50)),
                _line(event="LoadGame", Commander="BOCHEAUX"), _line(**transfer_event(25))])
            records = carrier.backfill(folder)
        self.assertEqual(set(records), {"bocheaux"})
        self.assertEqual(records["bocheaux"][FLEET]["cargo"], 125)

    def test_the_dock_state_at_the_end_is_handed_back(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            self._journal(folder, "Journal.2026-10-09T100000.01.log", [
                _line(event="LoadGame", Commander="BOCHEAUX"), _line(**stats_event(carrier_id=111)),
                _line(**docked_event(111))])
            self.assertEqual(carrier.backfill_tracker(folder).dock_state(), (111, FLEET))

    def test_unreadable_or_missing_folder_and_junk_lines_are_fine(self) -> None:
        self.assertEqual(carrier.backfill(os.path.join(tempfile.gettempdir(), "no-such-wntb-folder")), {})
        with tempfile.TemporaryDirectory() as folder:
            self._journal(folder, "Journal.2026-10-09T100000.01.log", [
                '{"event":"CarrierStats" this is not json\n', _line(event="LoadGame", Commander="X")])
            self.assertEqual(carrier.backfill(folder), {})


if __name__ == "__main__":
    unittest.main()
