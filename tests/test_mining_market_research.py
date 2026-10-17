"""
Unit tests for plugin/mining_market_research.py.

Pure logic - no EDMC runtime or network needed (EDMC's `config` module is stubbed). Run with:
    python -m unittest discover -s tests
"""

from __future__ import annotations

import os
import sys
import types
import unittest
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.modules.setdefault("config", types.SimpleNamespace(appname="EDMarketConnector"))

from plugin import mining_ground as ground  # noqa: E402
from plugin import mining_hotspots as hotspots  # noqa: E402
from plugin import mining_market_research as research  # noqa: E402

SYSTEM = "Sol"


def _spot(material: str, system: str = SYSTEM, **kwargs) -> hotspots.Hotspot:
    return hotspots.Hotspot(system=system, body=f"{system} 1", material=material, **kwargs)


def _plan(saved=(), grounds=(), extra=(), system=SYSTEM) -> research.Plan:
    return research.plan(system, saved, grounds, ground.OwnRates(saved), extra)


class PlanTests(unittest.TestCase):
    def test_nothing_recorded_suggests_nothing(self) -> None:
        self.assertEqual(_plan().candidates, ())

    def test_saved_deposits_in_the_system_are_candidates(self) -> None:
        names = [c.name for c in _plan([_spot("Painite"), _spot("Painite"), _spot("Monazite")]).candidates]
        self.assertEqual(names, ["Painite", "Monazite"])        # most deposits first

    def test_other_systems_are_ignored(self) -> None:
        self.assertEqual(_plan([_spot("Painite", system="Achenar")]).candidates, ())

    def test_the_reason_counts_deposits(self) -> None:
        (painite,) = _plan([_spot("Painite"), _spot("Painite")]).candidates
        self.assertEqual(painite.reasons, ("2 deposits saved in this system",))

    def test_records_on_the_same_ground_add_candidates(self) -> None:
        saved = [_spot("Platinum", system="Achenar", ground="icy"), _spot("Tritium", system="Achenar", ground="icy"),
                 _spot("Tritium", system="Achenar", ground="icy")]
        plan = _plan(saved, grounds=["icy"])
        self.assertEqual([c.name for c in plan.candidates], ["Tritium", "Platinum"])
        self.assertIn("67% of your 3 recorded deposits on this kind of ground (icy body)", plan.candidates[0].reasons[0])

    def test_a_commodity_has_all_its_reasons_once(self) -> None:
        saved = [_spot("Tritium", ground="icy")]
        (tritium,) = _plan(saved, grounds=["icy", "icy"], extra=["Tritium"]).candidates
        self.assertEqual(len(tritium.reasons), 3)

    def test_typed_names_resolve_and_unknown_ones_are_reported(self) -> None:
        plan = _plan(extra=["void opals", "not a thing"])
        self.assertEqual([c.name for c in plan.candidates], ["Void Opal"])
        self.assertEqual(plan.skipped, ("not a thing",))

    def test_capped(self) -> None:
        names = ["Gold", "Silver", "Platinum", "Palladium", "Osmium", "Painite", "Monazite", "Tritium",
                 "Bauxite", "Cobalt", "Coltan", "Lithium", "Uranium", "Titanium"]
        self.assertEqual(len(_plan(extra=names).candidates), research.MAX_CANDIDATES)

    def test_split_names(self) -> None:
        self.assertEqual(research.split_names("Gold, Silver;Platinum\n , "), ["Gold", "Silver", "Platinum"])


def _station(name: str, market: list[dict], updated: str = "2026-10-17T12:00:00Z", **kwargs) -> dict:
    station = {"name": name, "type": "Planetary Outpost", "market": market, "market_updated_at": updated,
               "distance_to_arrival": 500.0, "large_pads": 2}
    station.update(kwargs)
    return station


def _buys(commodity: str, price: int, demand: int) -> dict:
    return {"commodity": commodity, "sell_price": price, "demand": demand, "buy_price": 0, "supply": 0}


class MatchTests(unittest.TestCase):
    CANDIDATES = (research.Candidate("Gold", ("x",)), research.Candidate("Painite", ("y",)))

    def test_buyers_best_price_first(self) -> None:
        stations = [_station("A", [_buys("Gold", 50_000, 10)]), _station("B", [_buys("Gold", 51_000, 5)])]
        gold = research.match(self.CANDIDATES, stations)[0]
        self.assertEqual([b.station for b in gold.buyers], ["B", "A"])

    def test_no_demand_or_no_price_is_not_a_buyer(self) -> None:
        stations = [_station("A", [_buys("Gold", 50_000, 0)]), _station("B", [_buys("Gold", 0, 100)]),
                    _station("C", [{"commodity": "Gold", "sell_price": 9, "demand": 0, "supply": 400}])]
        self.assertEqual(research.match(self.CANDIDATES, stations)[0].buyers, ())

    def test_every_candidate_is_answered_even_with_no_buyer(self) -> None:
        results = research.match(self.CANDIDATES, [_station("A", [_buys("Gold", 1, 1)])])
        self.assertEqual([r.candidate.name for r in results], ["Gold", "Painite"])
        self.assertEqual(results[1].buyers, ())

    def test_names_match_whatever_the_case(self) -> None:
        self.assertEqual(len(research.match(self.CANDIDATES, [_station("A", [_buys("gold", 5, 5)])])[0].buyers), 1)

    def test_junk_in_the_answer_is_ignored(self) -> None:
        stations = ["x", None, {"name": "A", "market": [{"commodity": "Gold", "sell_price": "high", "demand": None}]}]
        self.assertEqual(research.match(self.CANDIDATES, stations)[0].buyers, ())

    def test_age_and_pads(self) -> None:
        now = datetime(2026, 10, 17, 12, 0, tzinfo=timezone.utc)
        buyer = research.match(self.CANDIDATES, [_station("A", [_buys("Gold", 5, 5)],
                                                          updated="2026-10-14T12:00:00Z")])[0].buyers[0]
        self.assertEqual(buyer.days_old(now), 3)
        self.assertEqual(buyer.days_old(now + timedelta(hours=-80)), 0)    # never negative
        self.assertEqual(research.pad_text(buyer), "large pads")

    def test_unreadable_update_time_is_unknown(self) -> None:
        buyer = research.match(self.CANDIDATES, [_station("A", [_buys("Gold", 5, 5)], updated="soon")])[0].buyers[0]
        self.assertIsNone(buyer.days_old())


if __name__ == "__main__":
    unittest.main()
