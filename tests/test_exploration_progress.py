"""Exploration Value: system scan progress and the last data sales, from journal events."""
from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from plugin import exploration_progress as ep  # noqa: E402


def scan(name: str, **extra) -> dict:
    return {"event": "Scan", "BodyName": name, **extra}


class SystemProgressTests(unittest.TestCase):
    def test_counts_scanned_stars_and_planets_against_the_honk(self) -> None:
        progress = ep.SystemProgress()
        progress.feed({"event": "FSDJump", "StarSystem": "Sol"})
        self.assertIn("honk", progress.text())
        progress.feed({"event": "FSSDiscoveryScan", "BodyCount": 14, "NonBodyCount": 60, "Progress": 0.1})
        progress.feed(scan("Sol A", StarType="G"))
        progress.feed(scan("Sol 3", PlanetClass="Earthlike body"))
        progress.feed(scan("Sol 3", PlanetClass="Earthlike body"))          # the same body twice counts once
        progress.feed(scan("Sol A Belt Cluster 1"))                         # no StarType / PlanetClass: not a body
        self.assertEqual(progress.text(), "System bodies: 2 scanned of 14")
        progress.feed({"event": "FSSAllBodiesFound", "SystemName": "Sol", "Count": 14})
        self.assertTrue(progress.text().endswith("all found"))

    def test_a_new_system_starts_over(self) -> None:
        progress = ep.SystemProgress()
        progress.feed({"event": "FSDJump", "StarSystem": "Sol"})
        progress.feed({"event": "FSSDiscoveryScan", "BodyCount": 3})
        progress.feed(scan("Sol A", StarType="G"))
        progress.feed({"event": "CarrierJump", "StarSystem": "Lave"})
        self.assertEqual(progress.scanned, 0)
        self.assertIsNone(progress.body_total)

    def test_scans_before_the_honk_are_counted_and_the_count_never_exceeds_the_total(self) -> None:
        progress = ep.SystemProgress()
        progress.feed(scan("A", StarType="G"))
        self.assertIn("1 scanned", progress.text())
        progress.feed({"event": "FSSDiscoveryScan", "BodyCount": 1})
        progress.feed(scan("B", PlanetClass="Icy body"))
        self.assertEqual(progress.text(), "System bodies: 1 scanned of 1")


class SalesTests(unittest.TestCase):
    def test_exploration_and_organic_sales_are_remembered_separately(self) -> None:
        sales = ep.LastSales()
        self.assertIn("none yet", sales.text())
        sales.feed({"event": "MultiSellExplorationData", "TotalEarnings": 1_234_567})
        sales.feed({"event": "SellOrganicData", "BioData": [{"Value": 100_000, "Bonus": 0}, {"Value": 50_000, "Bonus": 200_000}]})
        self.assertEqual(sales.text(), "Last data sale: exploration 1,234,567 cr, organic 350,000 cr")
        sales.feed({"event": "SellExplorationData", "TotalEarnings": 5})
        self.assertIn("exploration 5 cr", sales.text())
        self.assertFalse(sales.feed({"event": "MultiSellExplorationData", "TotalEarnings": 0}))   # empty sale ignored

    def test_replay_gives_the_state_after_a_whole_file(self) -> None:
        events = [{"event": "FSDJump", "StarSystem": "Sol"}, {"event": "FSSDiscoveryScan", "BodyCount": 2},
                  scan("Sol A", StarType="G"), {"event": "SellOrganicData", "BioData": [{"Value": 10, "Bonus": 5}]},
                  {"event": "FSDJump", "StarSystem": "Lave"}, {"event": "FSSDiscoveryScan", "BodyCount": 7}]
        progress, sales = ep.replay(events)
        self.assertEqual(progress.system, "Lave")
        self.assertEqual(progress.body_total, 7)
        self.assertEqual(sales.organic, 15)


if __name__ == "__main__":
    unittest.main()
