"""How far along each mission is (mission_progress.py), the hold it reads (current_cargo.py), and the colours the overlay card gives progress."""
from __future__ import annotations

import os
import sys
import types
import unittest
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
if "config" not in sys.modules:
    _stub = types.ModuleType("config")
    _stub.appname = "EDMarketConnector"
    _stub.config = types.SimpleNamespace(get_str=lambda key: "", default_journal_dir="")
    sys.modules["config"] = _stub

from plugin import current_cargo  # noqa: E402
from plugin import mission_progress as P  # noqa: E402
from plugin.mission_cargo import CargoProgress  # noqa: E402

NOW = datetime(2026, 10, 15, 12, 0, tzinfo=timezone.utc)


def mission(mission_id, count=60, key="agriculturalmedicines", expiry_minutes=600, cargo=None):
    return types.SimpleNamespace(id=mission_id, cargo=cargo, needed_commodity="Agri-Medicines", needed_commodity_count=count, commodity_key=key,
                                 expiry=(NOW + timedelta(minutes=expiry_minutes)).strftime("%Y-%m-%dT%H:%M:%SZ"))


class ProgressTests(unittest.TestCase):
    def test_the_commodity_key_matches_edmcs_cargo_names(self):
        self.assertEqual(P.commodity_key("$AgriculturalMedicines_Name;"), "agriculturalmedicines")
        self.assertEqual(P.commodity_key("Gold"), "gold")
        self.assertEqual(P.commodity_key(None), "")

    def test_a_source_and_return_mission_is_measured_against_the_hold(self):
        found = P.compute([mission(1)], held={"agriculturalmedicines": 36})[1]
        self.assertEqual((found.text, found.fraction, found.done, found.required), ("36/60 held", 0.6, 36, 60))

    def test_nothing_in_the_hold_is_zero_not_unknown(self):
        found = P.compute([mission(1)], held={})[1]
        self.assertEqual((found.text, found.fraction), ("0/60 held", 0.0))

    def test_missions_for_one_commodity_share_the_hold_soonest_first(self):
        found = P.compute([mission(1, 60, expiry_minutes=900), mission(2, 40, expiry_minutes=100)], held={"agriculturalmedicines": 70})
        self.assertEqual((found[2].done, found[1].done), (40, 30))        # 70 t: 40 to the sooner mission, the other 30 to the later one

    def test_the_games_count_wins_over_the_hold(self):
        found = P.compute([mission(1, cargo=CargoProgress(collected=60, delivered=20, total=60))], held={"agriculturalmedicines": 5})[1]
        self.assertEqual((found.text, round(found.fraction, 2)), ("20/60", 0.33))

    def test_cargo_picked_up_but_not_delivered_reads_as_loaded(self):
        found = P.compute([mission(1, cargo=CargoProgress(collected=36, delivered=0, total=36))])[1]
        self.assertEqual((found.text, found.fraction), ("36/36 loaded", 1.0))

    def test_kills_are_estimates_until_the_mission_is_ready(self):
        massacre = types.SimpleNamespace(id=5, cargo=None, needed_commodity="", needed_commodity_count=0, commodity_key="", expiry="")
        self.assertEqual(P.compute([massacre], kills={5: (18, 40, True)})[5].text, "~18/40 kills")
        self.assertEqual(P.compute([massacre], kills={5: (40, 40, True)}, ready={5})[5].text, "40/40 kills")

    def test_ready_is_always_full(self):
        found = P.compute([mission(1)], held={"agriculturalmedicines": 10}, ready={1})[1]
        self.assertEqual(found.fraction, 1.0)

    def test_the_colour_bands(self):
        self.assertEqual([P.tier(f) for f in (None, 0.0, 0.01, 0.49, 0.5, 1.0)], [P.NONE, P.NONE, P.LOW, P.LOW, P.HIGH, P.HIGH])
        self.assertEqual(P.tier(0.2, ready=True), P.READY)


class HoldTests(unittest.TestCase):
    def setUp(self):
        current_cargo._held = {}
        self.told = []
        current_cargo.changed.connect(lambda: self.told.append(1))
        self.addCleanup(lambda: current_cargo.changed._subscribers.clear())

    def test_the_hold_is_taken_from_edmcs_state_and_listeners_hear_only_of_changes(self):
        current_cargo.update({"Cargo": {"Gold": 12, "Silver": 0}})
        self.assertEqual(current_cargo.held(), {"gold": 12})
        current_cargo.update({"Cargo": {"Gold": 12}})
        self.assertEqual(len(self.told), 1)
        current_cargo.update({"Cargo": {"Gold": 20}})
        self.assertEqual(len(self.told), 2)

    def test_a_state_without_cargo_changes_nothing(self):
        current_cargo.update({"Cargo": {"Gold": 1}})
        current_cargo.update({})
        current_cargo.update(None)
        self.assertEqual(current_cargo.held(), {"gold": 1})


if __name__ == "__main__":
    unittest.main()
