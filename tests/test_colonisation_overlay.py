"""The Colonization shopping-list overlay card: what it lists, and how it is drawn and cleared."""
from __future__ import annotations

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

from unittest import mock  # noqa: E402

sys.modules.setdefault("myNotebook", mock.MagicMock())   # overlay.py builds Settings with it; not needed here

from plugin import colonisation, colonisation_overlay as card  # noqa: E402


def site(complete: bool = False) -> colonisation.Site:
    entry = {"MarketID": 7, "ConstructionComplete": complete, "ResourcesRequired": [
        {"Name": "$steel_name;", "Name_Localised": "Steel", "RequiredAmount": 500, "ProvidedAmount": 100},
        {"Name": "$water_name;", "Name_Localised": "Water", "RequiredAmount": 50, "ProvidedAmount": 0},
        {"Name": "$copper_name;", "Name_Localised": "Copper", "RequiredAmount": 20, "ProvidedAmount": 20}]}
    return colonisation.apply_depot_event(entry, None, name="Depot One", system="Sol")


class FakeClient:
    def __init__(self) -> None:
        self.sent = []

    def send_shape(self, shape_id, shape, color, fill, x, y, w, h, ttl=8, thickness=None):
        self.sent.append(("shape", shape_id, w, h, ttl))

    def send_message(self, msg_id, text, color, x, y, ttl=8, size="normal"):
        self.sent.append(("msg", msg_id, text, ttl))


class BuildCardTests(unittest.TestCase):
    def test_need_is_not_reduced_by_the_hold_and_rows_are_alphabetical(self) -> None:
        built = card.build_card(site(), {"steel": 100}, {}, show_fc=False)
        self.assertEqual([(r.name, r.need, r.ship) for r in built.rows], [("Steel", 400, 100), ("Water", 50, 0)])
        self.assertEqual(built.remaining, 450)

    def test_covered_and_surplus(self) -> None:
        built = card.build_card(site(), {"steel": 400, "water": 80}, {}, show_fc=False)
        steel, water = built.rows
        self.assertTrue(steel.covered and not steel.surplus)
        self.assertTrue(water.covered and water.surplus)

    def test_carrier_tonnes_and_trips(self) -> None:
        built = card.build_card(site(), {}, {"water": 40}, show_fc=True, capacity=200)
        self.assertEqual([r.fc for r in built.rows], [0, 40])
        self.assertEqual(built.trips, 3)          # 450 t in a 200 t ship
        self.assertEqual(card.build_card(site(), {}, {}, show_fc=False, capacity=0).trips, 0)

    def test_row_limit_is_summarized(self) -> None:
        built = card.build_card(site(), {}, {}, show_fc=False, max_rows=1)
        self.assertEqual((len(built.rows), built.hidden), (1, 1))

    def test_nothing_to_draw(self) -> None:
        self.assertIsNone(card.build_card(None, {}, {}, False))
        self.assertIsNone(card.build_card(site(complete=True), {}, {}, False))


class VisibilityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.v = card.Visibility()

    def test_hidden_until_a_market_is_open(self) -> None:
        self.v.feed({"event": "Docked"})
        self.v.set_focus(0)
        self.assertFalse(self.v.visible)
        self.v.set_focus(5)                      # station services menu, no service chosen yet
        self.assertFalse(self.v.visible)
        self.v.feed({"event": "Market"})
        self.assertTrue(self.v.visible)

    def test_leaving_the_screen_hides_it_and_reopening_needs_a_new_market_event(self) -> None:
        self.v.feed({"event": "Market"})
        self.v.set_focus(5)
        self.v.set_focus(0)
        self.assertFalse(self.v.visible)
        self.v.set_focus(5)
        self.assertFalse(self.v.visible)
        self.v.feed({"event": "Market"})
        self.assertTrue(self.v.visible)

    def test_carrier_inventory_counts(self) -> None:
        self.v.set_focus(5)
        self.v.feed({"event": "CarrierStats"})
        self.assertTrue(self.v.visible)

    def test_docked_at_a_carrier_shows_with_the_right_hand_panel_open(self) -> None:
        # the transfer to the carrier is done from the cockpit's right-hand panel, which writes no journal event
        self.v.feed({"event": "Docked", "StationType": "FleetCarrier", "StationName": "WLF-LXW"})
        self.v.set_focus(0)
        self.assertFalse(self.v.visible)
        self.v.set_focus(1)
        self.assertTrue(self.v.visible)
        self.v.set_focus(2)                      # the left-hand panel
        self.assertFalse(self.v.visible)
        self.v.set_focus(5)                      # station services without the market
        self.assertFalse(self.v.visible)
        self.v.set_focus(1)
        self.v.feed({"event": "Undocked"})
        self.assertFalse(self.v.visible)

    def test_a_carriers_services_screen_shows_without_a_market_event_unless_outfitting_or_shipyard(self) -> None:
        # the game writes no Market event for the commander's own carrier (checked against a real journal)
        self.v.feed({"event": "Docked", "StationType": "FleetCarrier", "StationName": "WLF-LXW"})
        self.v.set_focus(5)
        self.assertTrue(self.v.visible)
        self.v.feed({"event": "Shipyard"})
        self.assertFalse(self.v.visible)
        self.v.set_focus(0)
        self.v.set_focus(5)                      # the screen was closed and opened again
        self.assertTrue(self.v.visible)

    def test_an_ordinary_stations_services_screen_still_needs_the_market_event(self) -> None:
        self.v.feed({"event": "Docked", "StationType": "Coriolis", "StationName": "Jameson Memorial"})
        self.v.set_focus(5)
        self.assertFalse(self.v.visible)

    def test_right_hand_panel_elsewhere_does_not_show(self) -> None:
        self.v.feed({"event": "Docked", "StationType": "Coriolis", "StationName": "Jameson Memorial"})
        self.v.set_focus(1)
        self.assertFalse(self.v.visible)

    def test_a_carrier_found_by_location_at_start_up(self) -> None:
        self.v.feed({"event": "Location", "Docked": True, "StationType": "SquadronCarrier"})
        self.v.set_focus(1)
        self.assertTrue(self.v.visible)
        self.v.feed({"event": "Location", "Docked": False})
        self.assertFalse(self.v.visible)

    def test_other_services_and_undocking_hide_it(self) -> None:
        self.v.set_focus(5)
        self.v.feed({"event": "Market"})
        self.v.feed({"event": "Outfitting"})
        self.assertFalse(self.v.visible)
        self.v.feed({"event": "Market"})
        self.v.feed({"event": "Undocked"})
        self.assertFalse(self.v.visible)

    def test_a_market_event_alone_is_not_enough(self) -> None:
        self.v.feed({"event": "Market"})         # e.g. the focus never reported as services
        self.assertFalse(self.v.visible)

    def test_docked_at_a_construction_depot_shows_without_the_market(self) -> None:
        self.v.feed({"event": "Docked", "StationType": "SpaceConstructionDepot",
                     "StationName": "Orbital Construction Site: Grinning Station"})
        self.v.set_focus(0)                      # looking out of the cockpit
        self.assertTrue(self.v.visible)
        self.v.set_focus(5)
        self.assertTrue(self.v.visible)
        self.v.set_focus(6)                      # galaxy map
        self.assertFalse(self.v.visible)
        self.v.set_focus(0)
        self.v.feed({"event": "Undocked"})
        self.assertFalse(self.v.visible)

    def test_depot_found_by_name_or_by_its_own_event(self) -> None:
        self.v.feed({"event": "Docked", "StationType": "Unknown", "StationName": "Planetary Construction Site: X"})
        self.assertTrue(self.v.visible)
        self.v.feed({"event": "Undocked"})
        self.v.feed({"event": "Docked", "StationType": "Coriolis", "StationName": "Somewhere"})
        self.assertFalse(self.v.visible)
        self.v.feed({"event": "ColonisationConstructionDepot"})
        self.assertTrue(self.v.visible)

    def test_an_ordinary_station_is_not_a_depot(self) -> None:
        self.v.feed({"event": "Docked", "StationType": "Coriolis", "StationName": "Jameson Memorial"})
        self.v.set_focus(0)
        self.assertFalse(self.v.visible)

    def test_carrier_management_is_known_from_the_music_track(self) -> None:
        self.v.feed({"event": "Docked", "StationType": "FleetCarrier"})
        self.v.set_focus(5)
        self.v.feed({"event": "Music", "MusicTrack": "FleetCarrier_Managment"})
        self.assertTrue(self.v.visible)
        self.v.feed({"event": "Music", "MusicTrack": "Starport"})
        self.assertFalse(self.v.visible)

    def test_right_hand_panel_anywhere_is_an_option(self) -> None:
        self.v.set_focus(1)
        self.assertFalse(self.v.visible)
        self.v.right_panel_anywhere = True
        self.assertTrue(self.v.visible)
        self.v.set_focus(0)
        self.assertFalse(self.v.visible)

    def test_forced_is_separate_from_visible(self) -> None:
        self.v.forced = True
        self.assertFalse(self.v.visible)

    def test_a_bad_focus_value_is_treated_as_none(self) -> None:
        self.v.feed({"event": "Market"})
        self.v.set_focus(None)
        self.assertFalse(self.v.visible)


class RenderTests(unittest.TestCase):
    def texts(self, client):
        return {item[1].split("_", 2)[-1]: item[2] for item in client.sent if item[0] == "msg" and item[2]}

    def test_draws_card_columns_and_footer(self) -> None:
        client = FakeClient()
        slots = card.render(client, card.preview_card(), 20, 300)
        self.assertEqual(slots, card.preview_card().slot_count)
        self.assertEqual(client.sent[0][:2], ("shape", card.CARD_ID))
        texts = self.texts(client)
        self.assertEqual(texts["s1_1"], "Need")
        self.assertEqual(texts["s1_3"], "Ship")
        self.assertEqual(texts["s3_0"], "Steel ✓")
        self.assertEqual(texts["s3_3"], "14,000")
        self.assertTrue(texts[f"s{slots - 1}_0"].startswith("► 32,769 remaining  ► 33 trips"))

    def test_no_fc_column_without_a_carrier(self) -> None:
        client = FakeClient()
        built = card.build_card(site(), {"steel": 10}, {}, show_fc=False, capacity=100)
        card.render(client, built, 20, 300)
        texts = self.texts(client)
        self.assertNotIn("FC", texts.values())
        self.assertEqual(texts["s2_2"], "10")     # Ship is the third column

    def test_shorter_card_clears_leftover_lines(self) -> None:
        client = FakeClient()
        built = card.build_card(site(), {}, {}, show_fc=False)
        card.render(client, built, 20, 300, previous_slots=built.slot_count + 2)
        cleared_slots = {item[1].split("_")[2] for item in client.sent if item[0] == "msg" and item[2] == ""}
        self.assertIn(f"s{built.slot_count}", cleared_slots)
        self.assertIn(f"s{built.slot_count + 1}", cleared_slots)

    def test_clear_removes_card_and_text(self) -> None:
        client = FakeClient()
        card.clear(client, 20, 300, 2)
        self.assertEqual(client.sent[0][1], card.CARD_ID)
        self.assertEqual(sum(1 for item in client.sent if item[0] == "msg"), 8)


if __name__ == "__main__":
    unittest.main()
