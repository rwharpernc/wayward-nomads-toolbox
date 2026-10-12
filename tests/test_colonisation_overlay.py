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
        self.sent.append(("msg", msg_id, text, ttl, x, color))


class BlockRectTests(unittest.TestCase):
    """The rectangle the card occupies, which the global overlay placement uses to move it."""

    def test_block_rect_is_the_panel_rectangle_that_render_draws(self) -> None:
        built = card.build_card(site(), {"steel": 100}, {}, show_fc=False)
        client = FakeClient()
        card.render(client, built, 40, 300)
        left, top, width, height = card.block_rect(built, 40, 300)
        shape = next(c for c in client.sent if c[0] == "shape")
        self.assertEqual((width, height), (shape[2], shape[3]))
        self.assertEqual((left, top), (40 - card.PAD_X, 300 - card.PAD_Y))

    def test_block_rect_grows_with_the_content(self) -> None:
        narrow = card.build_card(site(), {}, {}, show_fc=False)
        wide = card.build_card(site(), {}, {}, show_fc=True)       # the FC column makes the card wider
        self.assertGreater(card.block_rect(wide)[2], card.block_rect(narrow)[2])
        one_row = card.build_card(site(), {}, {}, show_fc=False, max_rows=1)    # one row plus a "+1 more" line
        self.assertEqual(card.block_rect(one_row)[3], card.block_rect(narrow)[3])
        three_lines = card.Card("T", narrow.rows * 3, 0, 450, 0, False)
        self.assertGreater(card.block_rect(three_lines)[3], card.block_rect(narrow)[3])


class AlignmentTests(unittest.TestCase):
    def test_numbers_share_a_right_edge_whatever_their_digits_and_commas(self) -> None:
        client = FakeClient()
        rows = (card.Row("A", 145, 0, 0, 145), card.Row("B", 1046, 0, 0, 1046), card.Row("C", 10055, 0, 0, 10055))
        card.render(client, card.Card("T", rows, 0, 11246, 0, False), 20, 300)
        char = card.LEGACY.char_px("normal")
        ends = {item[2]: item[4] + card.text_units(item[2]) * char for item in client.sent
                if item[0] == "msg" and item[1].endswith("_1") and item[2][:1].isdigit()}
        self.assertEqual(len(ends), 3)
        self.assertEqual(len({round(v) for v in ends.values()}), 1, ends)

    def test_a_comma_counts_as_half_a_digit(self) -> None:
        self.assertEqual(card.text_units("1,046"), 4.5)


class PlacementSlotTests(unittest.TestCase):
    def test_the_placement_slot_is_wide_enough_for_the_widest_card(self) -> None:
        """Right-anchoring and the overlay group offset are worked out from the slot's size, so a card wider than it runs
        off the screen edge and the overlay's clamp squashes its last columns together."""
        from plugin import overlay_placement
        rows = tuple(card.Row("N" * 40, 999_999, 999_999, 999_999, 999_999) for _ in range(3))
        widest = card.Card("T" * 40, rows, 0, 9_999_999, 9_999, True, 9_999)
        slot_width = overlay_placement.SLOTS["colonisation"].size[0]
        self.assertLessEqual(card.block_rect(widest)[2], slot_width)


class OrderAndAvailabilityTests(unittest.TestCase):
    """The SrvSurvey order: alphabetical at a construction site, grouped by market category elsewhere; what the market does not
    sell is dimmed."""

    def colours(self, built):
        client = FakeClient()
        card.render(client, built, 20, 300)
        return {item[2]: item[5] for item in client.sent if item[0] == "msg" and item[2] and item[1].endswith("_0")}

    def test_alphabetical_at_a_site_and_grouped_by_category_elsewhere(self) -> None:
        flat = card.build_card(site(), {}, {}, show_fc=False)
        self.assertEqual([r.name for r in flat.rows], ["Steel", "Water"])
        self.assertFalse(flat.grouped)
        grouped = card.build_card(site(), {}, {}, show_fc=False, grouped=True)
        self.assertEqual([(r.category, r.name) for r in grouped.rows], [("Chemicals", "Water"), ("Metals", "Steel")])
        self.assertEqual(grouped.slot_count, flat.slot_count + 2)        # a heading line per category

    def test_categories_sort_alphabetically_then_by_name_with_unknown_last(self) -> None:
        raw = {"ResourcesRequired": [
            {"Name": "$zzzunknown_name;", "RequiredAmount": 5, "ProvidedAmount": 0},
            {"Name": "$titanium_name;", "RequiredAmount": 5, "ProvidedAmount": 0},
            {"Name": "$polymers_name;", "RequiredAmount": 5, "ProvidedAmount": 0},
            {"Name": "$aluminium_name;", "RequiredAmount": 5, "ProvidedAmount": 0},
            {"Name": "$water_name;", "RequiredAmount": 5, "ProvidedAmount": 0}], "MarketID": 9}
        built = card.build_card(colonisation.apply_depot_event(raw, None, name="X", system="Sol"), {}, {}, False, grouped=True)
        self.assertEqual([(r.category, r.name.casefold()) for r in built.rows],
                         [("Chemicals", "water"), ("Industrial Materials", "polymers"), ("Metals", "aluminium"),
                          ("Metals", "titanium"), ("Other", "zzzunknown")])

    def test_a_commodity_the_market_does_not_sell_is_dimmed_unless_covered(self) -> None:
        built = card.build_card(site(), {}, {}, show_fc=False, grouped=True, market_keys=frozenset({"steel"}))
        self.assertEqual({r.name: r.available for r in built.rows}, {"Water": False, "Steel": True})
        look = card.LEGACY
        colours = self.colours(built)
        self.assertEqual(colours["Water"], look.color("muted"))
        self.assertEqual(colours["Steel"], look.color("text"))
        covered = card.build_card(site(), {"water": 50}, {}, show_fc=False, grouped=True, market_keys=frozenset({"steel"}))
        self.assertEqual(self.colours(covered)["Water ✓"], look.color("ok"))        # covered: keeps its green

    def test_no_dimming_without_a_market(self) -> None:
        for keys in (None, frozenset()):
            built = card.build_card(site(), {}, {}, show_fc=False, grouped=True, market_keys=keys)
            self.assertTrue(all(r.available for r in built.rows))


class MeasuredSlotTests(unittest.TestCase):
    def setUp(self) -> None:
        from plugin import overlay_placement
        self.placement = overlay_placement
        self.placement._measured.clear()
        self.addCleanup(self.placement._measured.clear)

    def test_the_measured_size_replaces_the_nominal_one_and_only_grows(self) -> None:
        nominal = self.placement.slot_size("colonisation")
        self.assertTrue(self.placement.note_measured_size("colonisation", (700, 200)))
        self.assertEqual(self.placement.slot_size("colonisation"), (700, 200))
        self.assertNotEqual(self.placement.slot_size("colonisation"), nominal)
        self.assertFalse(self.placement.note_measured_size("colonisation", (650, 150)))     # smaller: nothing changes
        self.assertTrue(self.placement.note_measured_size("colonisation", (720, 150)))
        self.assertEqual(self.placement.slot_size("colonisation"), (720, 200))

    def test_a_new_look_starts_again(self) -> None:
        import dataclasses
        from plugin.overlay_style import LEGACY
        bigger = dataclasses.replace(LEGACY, text_level=LEGACY.text_level + 1)
        self.assertTrue(self.placement.note_measured_size("colonisation", (900, 200), LEGACY))
        self.assertTrue(self.placement.note_measured_size("colonisation", (400, 100), bigger))
        self.assertEqual(self.placement.slot_size("colonisation", bigger), (400, 100))


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

    def test_the_carrier_counts_toward_covered_and_surplus(self) -> None:
        built = card.build_card(site(), {"steel": 100}, {"steel": 300, "water": 60}, show_fc=True)
        steel, water = built.rows
        self.assertTrue(steel.covered and not steel.surplus)      # 100 + 300 = the 400 needed
        self.assertTrue(water.covered and water.surplus)          # 60 on the carrier, 50 needed
        short = card.build_card(site(), {"steel": 100}, {"steel": 299}, show_fc=True).rows[0]
        self.assertFalse(short.covered)

    def test_carrier_tonnes_and_trips(self) -> None:
        built = card.build_card(site(), {}, {"water": 40}, show_fc=True, capacity=200)
        self.assertEqual([r.fc for r in built.rows], [0, 40])
        self.assertEqual(built.trips, 3)          # 450 t in a 200 t ship
        self.assertEqual(card.build_card(site(), {}, {}, show_fc=False, capacity=0).trips, 0)

    def test_buy_trips_take_the_ship_and_the_carrier_off_and_count_every_commodity(self) -> None:
        # 450 t needed (400 steel, 50 water); 100 steel in the ship, 40 water on the carrier -> 310 t still to get
        built = card.build_card(site(), {"steel": 100}, {"water": 40}, show_fc=True, capacity=200)
        self.assertEqual((built.buy_trips, built.trips), (2, 3))        # ceil(310/200), ceil(450/200)
        limited = card.build_card(site(), {"steel": 100}, {"water": 40}, show_fc=True, capacity=200, max_rows=1)
        self.assertEqual(limited.buy_trips, 2)                          # a hidden row still counts

    def test_buy_trips_reach_zero_once_everything_is_stocked_but_hauling_does_not(self) -> None:
        built = card.build_card(site(), {"steel": 100}, {"steel": 300, "water": 50}, show_fc=True, capacity=200)
        self.assertEqual((built.buy_trips, built.trips), (0, 3))

    def test_buy_trips_are_zero_when_the_capacity_is_unknown(self) -> None:
        built = card.build_card(site(), {}, {}, show_fc=True, capacity=0)
        self.assertEqual((built.buy_trips, built.trips), (0, 0))

    def test_row_limit_is_summarized(self) -> None:
        built = card.build_card(site(), {}, {}, show_fc=False, max_rows=1)
        self.assertEqual((len(built.rows), built.hidden), (1, 1))

    def test_no_limit_lists_every_commodity(self) -> None:
        built = card.build_card(site(), {}, {}, show_fc=False, max_rows=0)
        self.assertEqual((len(built.rows), built.hidden), (2, 0))
        self.assertEqual(card.DEFAULT_ROWS, 0)

    def test_nothing_to_draw(self) -> None:
        self.assertIsNone(card.build_card(None, {}, {}, False))
        self.assertIsNone(card.build_card(site(complete=True), {}, {}, False))


class FooterTests(unittest.TestCase):
    def test_with_a_carrier_the_footer_gives_both_legs(self) -> None:
        built = card.build_card(site(), {"steel": 100}, {"water": 40}, show_fc=True, capacity=200)
        self.assertEqual(built.footer_text(), "► 450 remaining  ► 2 to buy  ► 3 to haul")

    def test_with_a_carrier_all_stocked_it_still_says_what_is_left_to_haul(self) -> None:
        built = card.build_card(site(), {}, {"steel": 400, "water": 50}, show_fc=True, capacity=200)
        self.assertEqual(built.footer_text(), "► 450 remaining  ► 0 to buy  ► 3 to haul")

    def test_without_a_carrier_there_is_one_figure_and_it_says_to_finish(self) -> None:
        self.assertEqual(card.build_card(site(), {}, {}, show_fc=False, capacity=200).footer_text(),
                         "► 450 remaining  ► 3 trips to finish")
        self.assertEqual(card.build_card(site(), {}, {}, show_fc=False, capacity=1000).footer_text(),
                         "► 450 remaining  ► 1 trip to finish")

    def test_without_a_capacity_there_are_no_trip_figures(self) -> None:
        for carrier in (False, True):
            self.assertEqual(card.build_card(site(), {}, {}, show_fc=carrier, capacity=0).footer_text(), "► 450 remaining")

    def test_the_card_is_wide_enough_for_the_longer_footer(self) -> None:
        short = card.build_card(site(), {}, {}, show_fc=True, capacity=0)
        long = card.build_card(site(), {}, {}, show_fc=True, capacity=1)      # 450 trips each way
        self.assertGreaterEqual(card.block_rect(long)[2], card.block_rect(short)[2])

    def test_the_footer_is_drawn(self) -> None:
        built = card.build_card(site(), {}, {"water": 40}, show_fc=True, capacity=200)
        client = FakeClient()
        card.render(client, built, 40, 300)
        texts = [c[2] for c in client.sent if c[0] == "msg"]
        self.assertIn(built.footer_text(), texts)


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
        self.v.set_focus(6)                      # the galaxy map
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
        self.v.set_focus(0)
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
        self.assertEqual([texts[f"s1_{i}"] for i in range(1, 6)], ["Required", "Remaining", "FC", "Cargo", "To buy"])
        self.assertEqual(texts["s2_0"], "Chemicals")          # grouped: a heading before each market category
        self.assertEqual(texts["s4_0"], "Metals")
        self.assertEqual(texts["s6_0"], "Steel ✓")
        self.assertEqual(texts["s6_1"], "15,000")
        self.assertEqual(texts["s6_4"], "14,000")
        self.assertEqual(texts["s5_5"], "10,055")     # To buy: nothing in the hold or on the carrier
        self.assertTrue(texts[f"s{slots - 1}_0"].startswith("► 32,769 remaining  ► 21 to buy  ► 33 to haul"))

    def test_no_fc_column_without_a_carrier(self) -> None:
        client = FakeClient()
        built = card.build_card(site(), {"steel": 10}, {}, show_fc=False, capacity=100)
        card.render(client, built, 20, 300)
        texts = self.texts(client)
        self.assertNotIn("FC", texts.values())
        self.assertEqual(texts["s2_3"], "10")     # Cargo follows Required and Remaining when there is no FC column
        self.assertEqual(texts["s2_4"], "390")    # To buy

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
        self.assertEqual(sum(1 for item in client.sent if item[0] == "msg"), 2 * card.MAX_COLUMNS)


if __name__ == "__main__":
    unittest.main()
