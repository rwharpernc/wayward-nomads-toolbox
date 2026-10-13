"""Sharing progress with Raven Colonial (rcc_sync.py): what is built from each journal event, and what is and is not sent."""
from __future__ import annotations

import os
import sys
import threading
import types
import unittest
import urllib.error
import io

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
if "config" not in sys.modules:
    _stub = types.ModuleType("config")
    _stub.appname = "EDMarketConnector"
    _stub.config = types.SimpleNamespace(get_str=lambda key: "", default_journal_dir="")
    sys.modules["config"] = _stub

from plugin import rcc_client, rcc_sync as S  # noqa: E402

DEPOT = {"event": "ColonisationConstructionDepot", "timestamp": "2026-10-12T20:00:00Z", "MarketID": 77,
         "ConstructionProgress": 0.4, "ConstructionComplete": False, "ConstructionFailed": False,
         "ResourcesRequired": [
             {"Name": "$steel_name;", "Name_Localised": "Steel", "RequiredAmount": 500, "ProvidedAmount": 100, "Payment": 1},
             {"Name": "$water_name;", "RequiredAmount": 50, "ProvidedAmount": 50, "Payment": 1}]}
CONTRIBUTION = {"event": "ColonisationContribution", "timestamp": "2026-10-12T20:05:00Z", "MarketID": 77,
                "Contributions": [{"Name": "$steel_name;", "Amount": 120}, {"Name": "$water_name;", "Amount": 0}]}
TRANSFER = {"event": "CargoTransfer", "timestamp": "2026-10-12T20:06:00Z", "Transfers": [
    {"Type": "steel", "Count": 100, "Direction": "tocarrier"}, {"Type": "copper", "Count": 30, "Direction": "toship"}]}


def plan(build_id="B-1", market_id=77):
    return rcc_client.RccSystem("Sol", "", None, [rcc_client.RccSite("Depot", "build", "no_truss", 1, market_id, build_id)])


class Harness:
    def __init__(self, progress=True, carrier=False, key="k", sites=None):
        self.writes = []
        self.lookups = []
        self.done = threading.Event()
        self.sites = sites if sites is not None else plan()

        self.cmdrs = []

        def writer(method, path, body, key_="", cmdr=""):
            self.writes.append((method, path, body, key_))
            self.cmdrs.append(cmdr)

        def find(system):
            self.lookups.append(system)
            return self.sites

        self.sync = S.RccSync(lambda: progress, lambda: carrier, lambda cmdr: key, find, writer)

    def settle(self) -> None:
        self.sync._queue.join()


class BodyTests(unittest.TestCase):
    def test_depot_body_is_the_remaining_need_and_the_total(self) -> None:
        body = S.depot_body("B-1", DEPOT)
        self.assertEqual(body["commodities"], {"steel": 400, "water": 0})
        self.assertEqual(body["maxNeed"], 550)
        self.assertEqual(body["buildId"], "B-1")
        self.assertEqual(body["colonisationConstructionDepot"]["MarketID"], 77)
        self.assertIsNone(S.depot_body("B-1", {"event": "ColonisationConstructionDepot"}))

    def test_contribution_and_carrier_bodies(self) -> None:
        self.assertEqual(S.contribution_body(CONTRIBUTION), {"steel": 120})
        self.assertEqual(S.carrier_body(TRANSFER), {"steel": 100, "copper": -30})


class SendTests(unittest.TestCase):
    def test_nothing_is_sent_while_sharing_is_off(self) -> None:
        h = Harness(progress=False, carrier=False)
        h.sync.on_depot("Alice", DEPOT, "Sol")
        h.sync.on_contribution("Alice", CONTRIBUTION, "Sol")
        h.sync.on_carrier_transfer("Alice", 3700, TRANSFER)
        h.settle()
        self.assertEqual((h.writes, h.lookups), ([], []))

    def test_a_delivery_links_the_commander_then_contributes_once(self) -> None:
        h = Harness()
        h.sync.on_contribution("Alice Smith", CONTRIBUTION, "Sol")
        h.sync.on_contribution("Alice Smith", CONTRIBUTION, "Sol")      # the same journal line twice
        h.settle()
        self.assertEqual([(m, p) for m, p, _b, _k in h.writes],
                         [("PUT", "/api/project/B-1/link/alice%20smith"), ("POST", "/api/project/B-1/contribute/alice%20smith")])
        self.assertEqual(h.writes[1][2], {"steel": 120})
        self.assertEqual(h.writes[1][3], "k")
        self.assertEqual(h.lookups, ["Sol"])

    def test_the_depot_snapshot_is_sent_only_when_the_need_changes(self) -> None:
        h = Harness()
        h.sync.on_depot("Alice", DEPOT, "Sol")
        h.settle()
        again = dict(DEPOT, timestamp="2026-10-12T20:01:00Z")
        h.sync.on_depot("Alice", again, "Sol")                           # same amounts, new event
        h.settle()
        patches = [w for w in h.writes if w[0] == "PATCH"]
        self.assertEqual(len(patches), 1)
        self.assertEqual(patches[0][1], "/api/project/B-1")
        changed = dict(DEPOT, timestamp="2026-10-12T20:02:00Z",
                       ResourcesRequired=[dict(DEPOT["ResourcesRequired"][0], ProvidedAmount=300)])
        h.sync.on_depot("Alice", changed, "Sol")
        h.settle()
        self.assertEqual(len([w for w in h.writes if w[0] == "PATCH"]), 2)

    def test_a_site_raven_has_no_project_for_sends_nothing_and_is_not_asked_again(self) -> None:
        h = Harness(sites=rcc_client.RccSystem("Sol", "", None, []))
        h.sync.on_contribution("Alice", CONTRIBUTION, "Sol")
        h.settle()
        h.sync.on_contribution("Alice", dict(CONTRIBUTION, timestamp="2026-10-12T20:09:00Z"), "Sol")
        h.settle()
        self.assertEqual(h.writes, [])
        self.assertEqual(len(h.lookups), 1)
        self.assertIn("no project", h.sync.last_result)

    def test_carrier_cargo_needs_its_own_switch_a_key_and_a_carrier(self) -> None:
        off = Harness(progress=True, carrier=False)
        off.sync.on_carrier_transfer("Alice", 3700, TRANSFER)
        off.settle()
        self.assertEqual(off.writes, [])
        no_key = Harness(carrier=True, key="")
        no_key.sync.on_carrier_transfer("Alice", 3700, TRANSFER)
        no_key.settle()
        self.assertEqual(no_key.writes, [])
        unknown = Harness(carrier=True)
        unknown.sync.on_carrier_transfer("Alice", None, TRANSFER)
        unknown.settle()
        self.assertEqual(unknown.writes, [])
        on = Harness(carrier=True)
        on.sync.on_carrier_transfer("Alice", 3700, TRANSFER)
        on.settle()
        self.assertEqual(on.writes, [("PATCH", "/api/FC/3700/cargo", {"steel": 100, "copper": -30}, "k")])

    def test_progress_and_deliveries_without_a_key_look_up_and_send_nothing(self) -> None:
        h = Harness(key="  ")
        h.sync.on_depot("Alice", DEPOT, "Sol")
        h.sync.on_contribution("Alice", CONTRIBUTION, "Sol")
        h.settle()
        self.assertEqual(h.writes, [])
        self.assertEqual(h.lookups, [])                       # not even a read of Raven's plan
        self.assertIn("No Raven Colonial key", h.sync.last_result)

    def test_every_write_names_the_commander_it_is_for(self) -> None:
        h = Harness(carrier=True)
        h.sync.on_depot("Alice", DEPOT, "Sol")
        h.sync.on_contribution("Alice", CONTRIBUTION, "Sol")
        h.sync.on_carrier_transfer("Alice", 3700, TRANSFER)
        h.settle()
        self.assertEqual(len(h.cmdrs), len(h.writes))
        self.assertGreaterEqual(len(h.writes), 4)             # link, progress, delivery, carrier cargo
        self.assertEqual(set(h.cmdrs), {"Alice"})

    def test_a_failed_send_is_remembered_in_words_and_does_not_raise(self) -> None:
        h = Harness()

        def failing(method, path, body, key="", cmdr=""):
            raise rcc_client.RccError("Could not reach Raven Colonial.")
        h.sync._write = failing
        h.sync.on_contribution("Alice", CONTRIBUTION, "Sol")
        h.settle()
        self.assertIn("Could not reach", h.sync.last_result)


class SendWriteTests(unittest.TestCase):
    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self, n=-1):
            return b""

    def test_json_body_key_header_and_one_retry_on_429(self) -> None:
        calls, waits = [], []

        def opener(request, timeout=None):
            calls.append(request)
            if len(calls) == 1:
                raise urllib.error.HTTPError(request.full_url, 429, "slow", {"Retry-After": "3"}, io.BytesIO(b""))
            return self.Response()

        rcc_client.send_write("POST", "/api/x", {"a": 1}, "secret", opener, waits.append)
        self.assertEqual(len(calls), 2)
        self.assertEqual(waits, [3.0])
        self.assertEqual(calls[1].data, b'{"a":1}')
        self.assertEqual(calls[1].get_header("Rcc-key"), "secret")
        self.assertEqual(calls[1].get_header("Content-type"), "application/json")

    def test_no_key_header_without_a_key_and_errors_never_show_it(self) -> None:
        seen = []

        def opener(request, timeout=None):
            seen.append(request)
            raise urllib.error.HTTPError(request.full_url, 500, "x", {}, io.BytesIO(b""))

        with self.assertRaises(rcc_client.RccError) as ctx:
            rcc_client.send_write("PUT", "/api/y", None, "", opener, lambda s: None)
        self.assertIsNone(seen[0].get_header("Rcc-key"))
        self.assertEqual(seen[0].data, b"")
        self.assertNotIn("secret", str(ctx.exception))

    def test_a_persistent_429_gives_up_after_one_retry(self) -> None:
        count = []

        def opener(request, timeout=None):
            count.append(1)
            raise urllib.error.HTTPError(request.full_url, 503, "x", {}, io.BytesIO(b""))

        with self.assertRaises(rcc_client.RccError):
            rcc_client.send_write("POST", "/api/z", {}, "k", opener, lambda s: None)
        self.assertEqual(len(count), 2)


class ProjectTests(unittest.TestCase):
    def test_a_project_is_read_back(self) -> None:
        project = rcc_client.parse_project({"buildId": "B", "sumNeed": 120, "maxNeed": 900, "complete": False,
                                            "commodities": {"Steel": 100, "water": "20"}})
        self.assertEqual((project.sum_need, project.max_need, project.complete), (120, 900, False))
        self.assertEqual(project.commodities, {"steel": 100, "water": 20})
        with self.assertRaises(rcc_client.RccError):
            rcc_client.parse_project([])


if __name__ == "__main__":
    unittest.main()
