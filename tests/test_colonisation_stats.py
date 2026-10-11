"""The Colonization mode's figures: the delivery ledger (colonisation_history.py) and the project and history texts
(colonisation_stats.py), for a commander with and without a fleet carrier."""
from __future__ import annotations

import os
import sys
import tempfile
import unittest
from datetime import date

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from plugin import colonisation as C  # noqa: E402
from plugin import colonisation_history as H  # noqa: E402
from plugin import colonisation_stats as S  # noqa: E402


def contribution(stamp, items, market_id=7):
    return {"event": "ColonisationContribution", "timestamp": stamp, "MarketID": market_id,
            "Contributions": [{"Name": f"${name}_name;", "Name_Localised": name.title(), "Amount": amount}
                              for name, amount in items]}


def site(**kw):
    depot = {"timestamp": kw.pop("stamp", "2026-10-01T10:00:00Z"), "MarketID": kw.pop("market_id", 7),
             "ConstructionProgress": kw.pop("progress", 0.4), "ConstructionComplete": kw.pop("complete", False),
             "ResourcesRequired": [{"Name": "$steel_name;", "Name_Localised": "Steel", "RequiredAmount": 1000, "ProvidedAmount": 200},
                                   {"Name": "$water_name;", "Name_Localised": "Water", "RequiredAmount": 300, "ProvidedAmount": 0}]}
    return C.apply_depot_event(depot, None, name=kw.pop("name", "Alpha Port"), system=kw.pop("system", "Sol"))


class LedgerTests(unittest.TestCase):
    def test_deliveries_are_summed_by_commodity_site_and_day(self):
        ledger = H.DeliveryLedger()
        self.assertTrue(ledger.apply_contribution("Bocheaux", contribution("2026-10-05T10:00:00Z", [("steel", 100), ("water", 20)])))
        self.assertTrue(ledger.apply_contribution("Bocheaux", contribution("2026-10-05T12:00:00Z", [("steel", 50)])))
        record = ledger.record("bocheaux")
        self.assertEqual((record["deliveries"], record["tonnes"]), (2, 170))
        self.assertEqual(record["by_commodity"]["steel"], {"label": "Steel", "tonnes": 150})
        self.assertEqual(record["by_site"], {"7": 170})
        self.assertEqual(record["by_day"], {"2026-10-05": 170})
        self.assertTrue(record["first"].startswith("2026-10-05T10:00:00"))

    def test_an_event_seen_twice_counts_once(self):
        ledger = H.DeliveryLedger()
        entry = contribution("2026-10-05T10:00:00Z", [("steel", 100)])
        self.assertTrue(ledger.apply_contribution("A", entry))
        self.assertFalse(ledger.apply_contribution("A", entry))
        self.assertEqual(ledger.record("A")["tonnes"], 100)

    def test_each_commander_has_their_own_record(self):
        ledger = H.DeliveryLedger()
        ledger.apply_contribution("A", contribution("2026-10-05T10:00:00Z", [("steel", 100)]))
        self.assertEqual(ledger.record("B")["tonnes"], 0)
        ledger.apply_contribution("B", contribution("2026-10-05T10:00:00Z", [("steel", 5)]))
        self.assertEqual((ledger.record("A")["tonnes"], ledger.record("B")["tonnes"]), (100, 5))

    def test_saved_and_read_back(self):
        with tempfile.TemporaryDirectory() as folder:
            ledger = H.DeliveryLedger()
            ledger.load(folder)
            ledger.apply_contribution("A", contribution("2026-10-05T10:00:00Z", [("steel", 100)]))
            ledger.commit()
            again = H.DeliveryLedger()
            again.load(folder)
            self.assertEqual(again.record("A")["tonnes"], 100)

    def test_old_days_are_dropped_but_the_total_stays(self):
        ledger = H.DeliveryLedger()
        ledger.apply_contribution("A", contribution("2024-01-01T10:00:00Z", [("steel", 100)]))
        ledger.apply_contribution("A", contribution("2026-10-05T10:00:00Z", [("steel", 10)]))
        record = ledger.record("A")
        self.assertEqual(record["tonnes"], 110)
        self.assertEqual(list(record["by_day"]), ["2026-10-05"])

    def test_junk_is_ignored(self):
        ledger = H.DeliveryLedger()
        self.assertFalse(ledger.apply_contribution("", contribution("2026-10-05T10:00:00Z", [("steel", 1)])))
        ledger.apply_contribution("A", {"event": "ColonisationContribution", "timestamp": "2026-10-05T10:00:00Z",
                                        "Contributions": ["x", {"Name": "", "Amount": 5}, {"Name": "steel", "Amount": "n"}]})
        self.assertEqual(ledger.record("A")["tonnes"], 0)


class CatchUpTests(unittest.TestCase):
    def test_the_catch_up_feeds_the_ledger_once_even_when_it_runs_twice(self):
        from plugin import colonisation_catchup as K
        from plugin.colonisation_data import SiteRepository
        ledger = H.DeliveryLedger()
        events = [("A", contribution("2026-10-05T10:00:00Z", [("steel", 100)])),
                  ("A", contribution("2026-10-06T10:00:00Z", [("steel", 25)]))]
        K.apply_events(SiteRepository(), events, ledger)        # no site known: the delivery still counts for the history
        K.apply_events(SiteRepository(), events, ledger)
        self.assertEqual(ledger.record("A")["tonnes"], 125)


class CarrierCapiTests(unittest.TestCase):
    def test_frontiers_cargo_list_replaces_the_tally_and_later_transfers_add_on_top(self):
        from plugin import colonisation_carrier as K
        cargo = K.CarrierCargo()
        cargo.apply_transfer("A", {"timestamp": "2026-10-01T10:00:00Z",
                                   "Transfers": [{"Type": "steel", "Count": 10, "Direction": "tocarrier"}]})
        self.assertTrue(cargo.apply_capi_cargo("A", [{"commodity": "Steel", "qty": 40}, {"commodity": "Water", "qty": 7},
                                                      {"commodity": "Steel", "qty": 5}, "junk", {"commodity": "", "qty": 3}]))
        self.assertEqual(cargo.tonnes("A"), {"steel": 45, "water": 7})
        self.assertFalse(cargo.apply_capi_cargo("A", [{"commodity": "Steel", "qty": 45}, {"commodity": "Water", "qty": 7}]))
        cargo.apply_transfer("A", {"timestamp": "2026-10-02T10:00:00Z",
                                   "Transfers": [{"Type": "water", "Count": 2, "Direction": "toship"}]})
        self.assertEqual(cargo.tonnes("A"), {"steel": 45, "water": 5})


class SiteTimesTests(unittest.TestCase):
    def test_first_seen_and_completion_time_are_kept_and_survive_a_save(self):
        first = site(stamp="2026-10-01T10:00:00Z")
        self.assertEqual(first.first_seen, "2026-10-01T10:00:00Z")
        self.assertEqual(first.completed_at, "")
        done = C.apply_depot_event({"timestamp": "2026-10-04T10:00:00Z", "MarketID": 7, "ConstructionComplete": True,
                                    "ResourcesRequired": []}, first)
        self.assertEqual((done.first_seen, done.completed_at), ("2026-10-01T10:00:00Z", "2026-10-04T10:00:00Z"))
        self.assertEqual(C.Site.from_dict(done.to_dict()).completed_at, "2026-10-04T10:00:00Z")

    def test_a_site_saved_before_these_existed_loads_with_blanks(self):
        old = C.Site.from_dict({"market_id": 3, "name": "x"})
        self.assertEqual((old.first_seen, old.completed_at), ("", ""))


class ProjectTests(unittest.TestCase):
    def test_without_a_carrier_the_words_carrier_and_haul_never_appear(self):
        project = S.project_for(site(), {"steel": 300}, {"steel": 500}, has_carrier=False, capacity=400)
        self.assertEqual(project.on_carrier, 0)             # a carrier's tonnes are ignored
        texts = [S.coverage_text(project), S.trips_text(project), S.next_step(project)]
        for text in texts:
            self.assertNotIn("carrier", text.lower(), text)
            self.assertNotIn("haul", text.lower(), text)
        self.assertEqual(S.trips_text(project), "3 loads of 400 t")        # 1,100 t still needed
        self.assertEqual(S.coverage_text(project), "0 fully · 1 partly · 1 not yet (of 2 commodities)")

    def test_with_a_carrier_the_ship_and_carrier_together_cover_and_there_are_two_legs(self):
        project = S.project_for(site(), {"steel": 300}, {"steel": 500, "water": 300}, has_carrier=True, capacity=400)
        self.assertEqual(S.coverage_text(project), "2 fully · 0 partly · 0 not yet (of 2 commodities)")
        self.assertEqual(project.to_get, 0)
        self.assertEqual(S.trips_text(project), "0 to buy · 3 to haul (400 t ship)")
        self.assertIn("ship and carrier", S.next_step(project).lower())

    def test_fully_partly_and_not_yet_covered(self):
        project = S.project_for(site(), {"steel": 100}, {"steel": 100, "water": 300}, has_carrier=True, capacity=400)
        self.assertEqual(S.coverage_text(project), "1 fully · 1 partly · 0 not yet (of 2 commodities)")
        project = S.project_for(site(), {"water": 5}, None, has_carrier=False, capacity=400)
        self.assertEqual((project.covered, project.partial, project.uncovered), (0, 1, 1))

    def test_unknown_ship_size_and_a_finished_build(self):
        project = S.project_for(site(), {}, None, False, 0)
        self.assertIn("Unknown", S.trips_text(project))
        done = S.project_for(site(complete=True), {}, None, False, 400)
        self.assertEqual(S.next_step(done), "This build is complete.")
        self.assertEqual(done.progress, 1.0)

    def test_the_biggest_gaps_are_listed_biggest_first(self):
        project = S.project_for(site(), {}, None, False, 400)
        self.assertEqual(project.gaps, (("Steel", 800), ("Water", 300)))


class HistoryTests(unittest.TestCase):
    def test_sites_and_delivery_figures(self):
        done = site(market_id=1, stamp="2026-09-01T00:00:00Z", system="Sol")
        done.complete, done.completed_at = True, "2026-09-04T00:00:00Z"
        working = site(market_id=2, system="Sol")
        failed = site(market_id=3, system="Wolf 359")
        failed.failed = True
        ledger = H.DeliveryLedger()
        ledger.apply_contribution("A", contribution("2026-10-02T10:00:00Z", [("water", 40)]))
        ledger.apply_contribution("A", contribution("2026-10-10T10:00:00Z", [("steel", 100)]))
        ledger.apply_contribution("A", contribution("2026-10-11T10:00:00Z", [("steel", 60)]))
        history = S.history_for([done, working, failed], ledger.record("A"), today=date(2026, 10, 11))
        self.assertEqual((history.sites, history.completed, history.in_progress, history.failed, history.systems), (3, 1, 1, 1, 2))
        self.assertEqual((history.deliveries, history.tonnes), (3, 200))
        self.assertEqual((history.last_7_days, history.last_30_days), (160, 200))
        self.assertEqual(history.busiest_day, ("2026-10-10", 100))
        self.assertEqual(history.top_commodities, (("Steel", 160), ("Water", 40)))
        self.assertEqual(history.since, "2026-10-02")
        self.assertEqual(history.average_days, 3.0)
        self.assertEqual(S.sites_text(history), "1 done · 1 in progress · 1 failed")
        self.assertEqual(S.average_text(3.0), "3 days")
        self.assertEqual(S.average_text(2.5), "2.5 days")
        self.assertEqual(S.average_text(0.2), "under a day")
        self.assertEqual(S.average_text(None), "–")

    def test_nothing_yet(self):
        history = S.history_for([], {})
        self.assertEqual((history.sites, history.tonnes, history.busiest_day, history.average_days), (0, 0, None, None))
        self.assertEqual(S.sites_text(history), "None tracked yet")


if __name__ == "__main__":
    unittest.main()
