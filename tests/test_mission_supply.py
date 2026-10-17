"""
Which missions count as needing cargo you have to find (mission_types.needs_commodity_supply and MissionSummary.from_event), including
Delivery missions whose cargo the faction did not hand over. The events are shaped like real ones from the journal (2026-10-17).

Pure logic - no EDMC runtime needed. Run with: python -m unittest discover -s tests
"""

from __future__ import annotations

import os
import sys
import types
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.modules.setdefault("config", types.SimpleNamespace(appname="EDMarketConnector"))

from plugin import all_missions, mission_cargo, mission_sources, mission_types  # noqa: E402


def _event(name: str = "Mission_Delivery", commodity: str = "$PersonalWeapons_Name;", count: int = 132, **extra) -> dict:
    event = {"timestamp": "2026-10-17T22:11:12Z", "event": "MissionAccepted", "Faction": "The Brigade", "Name": name,
             "LocalisedName": f"Deliver {count} units of Personal Weapons", "Commodity": commodity,
             "Commodity_Localised": "Personal Weapons", "Count": count, "DestinationSystem": "Pegasi Sector VP-O b6-7",
             "Expiry": "2026-10-18T22:10:25Z", "Wing": False, "Reward": 810462, "MissionID": 1068710723}
    event.update(extra)
    return event


class NeedsSupplyTests(unittest.TestCase):
    def test_a_plain_delivery_of_goods_needs_them_found(self) -> None:
        self.assertTrue(mission_types.needs_commodity_supply(_event()))
        self.assertTrue(mission_types.needs_commodity_supply(_event("Mission_Delivery_Agriculture")))

    def test_collect_and_mining_still_do(self) -> None:
        for name in ("Mission_Collect_Industrial", "Mission_Mining", "Mission_Mining_Expansion", "Mission_Collect"):
            self.assertTrue(mission_types.needs_commodity_supply(_event(name)), name)

    def test_other_missions_do_not(self) -> None:
        for name in ("Mission_Sightseeing", "Mission_Altruism", "Mission_OnFoot_Delivery_Contact_MB", "Mission_ColonisationDelivery",
                     "Mission_Courier", "Mission_Salvage_Expansion"):
            self.assertFalse(mission_types.needs_commodity_supply(_event(name)), name)

    def test_a_delivery_with_no_commodity_or_count_does_not(self) -> None:
        self.assertFalse(mission_types.needs_commodity_supply({"Name": "Mission_Delivery"}))
        self.assertFalse(mission_types.needs_commodity_supply(_event(count=0)))
        self.assertFalse(mission_types.needs_commodity_supply(_event(Commodity="")))


class SummaryTests(unittest.TestCase):
    def test_the_weapons_missions_are_needs_until_the_cargo_is_reported(self) -> None:
        summary = all_missions.MissionSummary.from_event(_event())
        self.assertEqual((summary.needed_commodity, summary.needed_commodity_count), ("Personal Weapons", 132))
        needs = mission_sources.needs_from([summary, all_missions.MissionSummary.from_event(_event(count=48, MissionID=2))])
        self.assertEqual([(n.commodity, n.tonnes, n.missions) for n in needs], [("Personal Weapons", 180, 2)])

    def test_cargo_handed_over_at_acceptance_takes_the_need_away(self) -> None:
        handed_over = mission_cargo.CargoProgress(collected=108, delivered=0, total=108)
        summary = all_missions.MissionSummary.from_event(_event("Mission_Delivery_War", "$Landmines_Name;", 108), handed_over)
        self.assertEqual(summary.needed_commodity_count, 0)
        self.assertEqual(mission_sources.needs_from([summary]), [])

    def test_partly_collected_leaves_the_rest(self) -> None:
        summary = all_missions.MissionSummary.from_event(_event(), mission_cargo.CargoProgress(collected=100, delivered=0, total=132))
        self.assertEqual(summary.needed_commodity_count, 32)


if __name__ == "__main__":
    unittest.main()
