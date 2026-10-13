"""Fuel warnings (fuel_alerts.py): low fuel, and a plotted star that cannot be scooped."""
from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from plugin import fuel_alerts as F  # noqa: E402

FLYING = F.FLAG_IN_MAIN_SHIP


def watcher(capacity=32.0, fuel=32.0, flags=FLYING, target=None, name=""):
    w = F.FuelWatcher()
    if capacity is not None:
        w.handle_event({"event": "Loadout", "FuelCapacity": {"Main": capacity, "Reserve": 0.63}})
    w.handle_status({"Flags": flags, "Fuel": {"FuelMain": fuel, "FuelReservoir": 0.5}})
    if target is not None:
        w.handle_event({"event": "FSDTarget", "Name": name, "StarClass": target})
    return w


class StarTests(unittest.TestCase):
    def test_only_the_main_sequence_letters_are_scoopable(self):
        for star in "OBAFGKM":
            self.assertTrue(F.is_scoopable(star), star)
        for star in ("N", "H", "DA", "DB", "W", "WN", "C", "CN", "MS", "S", "TTS", "AeBe", "T", "L", "Y", "", None):
            self.assertFalse(F.is_scoopable(star), star)

    def test_descriptions(self):
        self.assertEqual(F.star_description("N"), "neutron star")
        self.assertEqual(F.star_description("H"), "black hole")
        self.assertEqual(F.star_description("DAB"), "white dwarf")
        self.assertEqual(F.star_description("WC"), "Wolf-Rayet star")
        self.assertEqual(F.star_description("TTS"), "protostar")
        self.assertEqual(F.star_description("X"), "class X star")

    def test_percentages_are_kept_in_range(self):
        self.assertEqual(F.clamp_percent("30", 25), 30)
        self.assertEqual(F.clamp_percent(2, 25), F.PERCENT_RANGE[0])
        self.assertEqual(F.clamp_percent(500, 25), F.PERCENT_RANGE[1])
        self.assertEqual(F.clamp_percent("abc", 25), 25)
        self.assertEqual(F.clamp_percent(None, 25), 25)


class LowFuelTests(unittest.TestCase):
    def test_a_tank_at_the_threshold_warns(self):
        alerts = watcher(fuel=8.0).alerts()           # exactly 25 %
        self.assertEqual([a.kind for a in alerts], ["low"])
        self.assertEqual(alerts[0].lines, ("Low fuel", "Tank 25% (8.0 t)"))

    def test_a_fuller_tank_does_not(self):
        self.assertEqual(watcher(fuel=8.4).alerts(), [])

    def test_the_threshold_is_the_commanders(self):
        self.assertEqual(watcher(fuel=12.0).alerts(low_percent=40)[0].kind, "low")
        self.assertEqual(watcher(fuel=12.0).alerts(low_percent=30), [])

    def test_it_can_be_turned_off(self):
        self.assertEqual(watcher(fuel=2.0).alerts(low=False), [])

    def test_without_the_tank_size_the_games_own_flag_is_used(self):
        w = watcher(capacity=None, fuel=6.0, flags=FLYING | F.FLAG_LOW_FUEL)
        self.assertIsNone(w.percent())
        self.assertEqual(w.alerts()[0].lines, ("Low fuel", "Tank 6.0 t, under 25%"))
        self.assertEqual(watcher(capacity=None, fuel=6.0).alerts(), [])

    def test_no_warning_when_docked_landed_scooping_or_not_in_the_main_ship(self):
        for flags in (FLYING | F.FLAG_DOCKED, FLYING | F.FLAG_LANDED, FLYING | F.FLAG_SCOOPING, 0):
            self.assertEqual(watcher(fuel=1.0, flags=flags).alerts(), [], flags)

    def test_no_warning_without_a_fuel_reading(self):
        w = F.FuelWatcher()
        w.handle_event({"event": "Loadout", "FuelCapacity": {"Main": 32.0}})
        w.handle_status({"Flags": FLYING})
        self.assertEqual(w.alerts(), [])


class UnscoopableTests(unittest.TestCase):
    def test_an_unscoopable_target_with_a_half_tank_warns(self):
        alerts = watcher(fuel=16.0, target="N", name="Col 70 Sector").alerts()
        self.assertEqual([a.kind for a in alerts], ["unscoopable"])
        self.assertEqual(alerts[0].lines, ("No scoop at next star", "(neutron star)", "Fuel 50% (16.0 t)"))
        self.assertEqual(alerts[0].text, "No scoop at next star (neutron star) Fuel 50% (16.0 t)")

    def test_no_line_is_longer_than_a_card_line(self):
        for star in ("N", "H", "DAB", "WC", "TTS", "MS", "X", "AeBe"):
            for alert in watcher(fuel=2.0, target=star).alerts():
                for line in alert.lines:
                    self.assertLessEqual(len(line), 30, line)

    def test_a_fuller_tank_does_not(self):
        self.assertEqual(watcher(fuel=17.0, target="N").alerts(), [])

    def test_a_scoopable_target_does_not(self):
        self.assertEqual(watcher(fuel=10.0, target="K").alerts(low_percent=5), [])

    def test_both_warnings_can_show_together(self):
        self.assertEqual([a.kind for a in watcher(fuel=4.0, target="H").alerts()], ["low", "unscoopable"])

    def test_the_threshold_and_the_switch_are_the_commanders(self):
        self.assertEqual(watcher(fuel=24.0, target="N").alerts(unscoopable_percent=80)[0].kind, "unscoopable")
        self.assertEqual(watcher(fuel=24.0, target="N").alerts(unscoopable_percent=80, unscoopable=False), [])

    def test_the_target_ends_with_the_jump_or_a_new_session(self):
        for event in ("FSDJump", "Location", "LoadGame", "StartUp", "Docked", "CarrierJump"):
            w = watcher(fuel=10.0, target="N")
            w.handle_event({"event": event})
            self.assertEqual(w.alerts(low_percent=5), [], event)

    def test_a_new_target_replaces_the_old(self):
        w = watcher(fuel=10.0, target="N")
        w.handle_event({"event": "FSDTarget", "Name": "Sol", "StarClass": "G"})
        self.assertEqual(w.alerts(low_percent=5), [])

    def test_without_the_tank_size_it_cannot_judge_the_percentage(self):
        self.assertEqual(watcher(capacity=None, fuel=2.0, target="N").alerts(), [])


class EventTests(unittest.TestCase):
    def test_odd_data_never_raises(self):
        w = F.FuelWatcher()
        for entry in ({"event": "Loadout"}, {"event": "Loadout", "FuelCapacity": "big"}, {"event": "Loadout", "FuelCapacity": {"Main": -1}},
                      {"event": "FSDTarget"}, {"event": "FSDTarget", "StarClass": 5}):
            w.handle_event(entry)
        w.handle_status({"Flags": "x", "Fuel": []})
        w.handle_status({})
        self.assertIsNone(w.capacity)
        self.assertEqual(w.alerts(), [])


if __name__ == "__main__":
    unittest.main()
