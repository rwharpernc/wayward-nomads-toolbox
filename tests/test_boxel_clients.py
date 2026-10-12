"""
The Boxel Survey network clients: EDSM (edsm_client.py) and Spansh's system search (region_sweep_spansh.py).

No test touches a live service. The point is the contracts the callers depend on, which a mock can check:
- a lookup that fails gives `None` (or an empty result), never an exception and never a confident "no", because a temporary EDSM
  outage must never cause a good candidate to be silently skipped;
- the shapes of a good answer, an empty answer ("not found") and a surprising one are told apart;
- every request names WNTB in its User-Agent and has a timeout.

EDMC's own modules (`config`, `requests`) are stood in for just for these tests, and the plugin modules are imported against them and
then removed again, so nothing leaks into other tests.
"""
from __future__ import annotations

import importlib
import json
import os
import sys
import types
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


class FakeResponse:
    def __init__(self, data=None, status_error=None, body=None):
        self._data, self._error = data, status_error
        self._body = body if body is not None else json.dumps(data).encode("utf-8")

    def raise_for_status(self):
        if self._error:
            raise self._error

    def json(self):
        return self._data

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class EdsmTests(unittest.TestCase):
    def setUp(self):
        config = types.ModuleType("config")
        config.appname = "EDMarketConnector"
        config.user_agent = "EDMarketConnector/6.1.2"
        config.config = types.SimpleNamespace(get_str=lambda key: "", default_journal_dir="")
        fake_requests = types.ModuleType("requests")
        fake_requests.get = mock.MagicMock(name="requests.get")
        patcher = mock.patch.dict(sys.modules, {"config": config, "requests": fake_requests})
        patcher.start()
        self.addCleanup(patcher.stop)
        for name in [m for m in sys.modules if m in ("plugin.edsm_client", "plugin.http_identity")]:
            sys.modules.pop(name)
        self.client = importlib.import_module("plugin.edsm_client")
        self.get = fake_requests.get

    def answer(self, data=None, error=None):
        self.get.side_effect = None
        self.get.return_value = FakeResponse(data, error)

    def fail(self):
        self.get.side_effect = OSError("down")

    # --- every request ---------------------------------------------------------------------------------------------

    def test_every_request_names_wntb_and_has_a_timeout(self):
        self.answer([])
        self.client.system_known("Sol")
        _args, kwargs = self.get.call_args
        self.assertIn("WNTB", kwargs["headers"]["User-Agent"])
        self.assertIn("EDMarketConnector", kwargs["headers"]["User-Agent"])
        self.assertEqual(kwargs["timeout"], self.client.REQUEST_TIMEOUT)

    # --- system_known ----------------------------------------------------------------------------------------------

    def test_a_known_system_is_true_and_an_empty_answer_is_a_confident_false(self):
        self.answer({"name": "Sol", "id": 1})
        self.assertIs(self.client.system_known("Sol"), True)
        for empty in ([], {}):
            self.answer(empty)
            self.assertIs(self.client.system_known("Nowhere"), False)

    def test_a_failure_or_a_surprise_is_none_never_false(self):
        self.fail()
        with self.assertLogs(level="ERROR"):
            self.assertIsNone(self.client.system_known("Sol"))
        self.answer(None, error=ValueError("503"))
        with self.assertLogs(level="ERROR"):
            self.assertIsNone(self.client.system_known("Sol"))
        self.answer("a string")
        with self.assertLogs(level="WARNING"):
            self.assertIsNone(self.client.system_known("Sol"))

    # --- nearby_systems --------------------------------------------------------------------------------------------

    def test_nearby_systems_returns_the_list_and_an_empty_one_on_any_trouble(self):
        rows = [{"name": "A", "distance": 3.0, "coords": {"x": 1, "y": 2, "z": 3}}]
        self.answer(rows)
        self.assertEqual(self.client.nearby_systems(0, 0, 0), rows)
        self.fail()
        with self.assertLogs(level="ERROR"):
            self.assertEqual(self.client.nearby_systems(0, 0, 0), [])
        self.answer({"not": "a list"})
        with self.assertLogs(level="WARNING"):
            self.assertEqual(self.client.nearby_systems(0, 0, 0), [])

    def test_nearby_systems_asks_for_the_cube_around_the_point(self):
        self.answer([])
        self.client.nearby_systems(1.5, -2.0, 3.0, size=80)
        params = self.get.call_args.kwargs["params"]
        self.assertEqual((params["x"], params["y"], params["z"], params["size"]), (1.5, -2.0, 3.0, 80))

    # --- system_bodies ---------------------------------------------------------------------------------------------

    def test_system_bodies_returns_the_raw_list_and_none_on_trouble(self):
        bodies = [{"name": "Sol 3", "reserveLevel": "Pristine"}]
        self.answer({"name": "Sol", "bodies": bodies})
        self.assertEqual(self.client.system_bodies("Sol"), bodies)
        self.answer({"name": "Sol"})                                       # a system with no bodies listed
        self.assertEqual(self.client.system_bodies("Sol"), [])
        self.fail()
        with self.assertLogs(level="ERROR"):
            self.assertIsNone(self.client.system_bodies("Sol"))
        self.answer([1, 2])
        with self.assertLogs(level="WARNING"):
            self.assertIsNone(self.client.system_bodies("Sol"))

    # --- system_fully_scanned --------------------------------------------------------------------------------------

    def test_fully_scanned_compares_the_bodies_found_with_the_body_count(self):
        self.answer({"bodyCount": 3, "bodies": [{}, {}, {}]})
        self.assertIs(self.client.system_fully_scanned("Sol"), True)
        self.answer({"bodyCount": 3, "bodies": [{}, {}]})
        self.assertIs(self.client.system_fully_scanned("Sol"), False)
        self.answer({"bodyCount": 2, "bodies": [{}, {}, {}]})
        self.assertIs(self.client.system_fully_scanned("Sol"), True)

    def test_fully_scanned_is_none_when_it_cannot_be_decided(self):
        for data in ({"bodies": [{}]}, {"bodyCount": 0, "bodies": []}, {"bodyCount": "3", "bodies": []},
                     {"bodyCount": 3}, {"bodyCount": 3, "bodies": "x"}):
            self.answer(data)
            self.assertIsNone(self.client.system_fully_scanned("Sol"), data)
        self.fail()
        with self.assertLogs(level="ERROR"):
            self.assertIsNone(self.client.system_fully_scanned("Sol"))
        self.answer(["x"])
        with self.assertLogs(level="WARNING"):
            self.assertIsNone(self.client.system_fully_scanned("Sol"))

    # --- systems_coords --------------------------------------------------------------------------------------------

    def test_systems_coords_resolves_what_it_can_in_one_request(self):
        self.answer([{"name": "A", "coords": {"x": 1, "y": 2, "z": 3}}, {"name": "B", "coords": {"x": "4", "y": 5.5, "z": -6}},
                     {"name": "C"}, {"name": "D", "coords": {"x": 1}}, "junk", {"coords": {"x": 1, "y": 2, "z": 3}}])
        resolved = self.client.systems_coords(["A", "B", "C", "D", "E"])
        self.assertEqual(resolved, {"A": (1.0, 2.0, 3.0), "B": (4.0, 5.5, -6.0)})
        self.assertEqual(self.get.call_count, 1)
        params = self.get.call_args.kwargs["params"]
        self.assertEqual([v for k, v in params if k == "systemName[]"], ["A", "B", "C", "D", "E"])

    def test_systems_coords_asks_nothing_for_no_names_and_gives_nothing_on_trouble(self):
        self.assertEqual(self.client.systems_coords([]), {})
        self.get.assert_not_called()
        self.fail()
        with self.assertLogs(level="ERROR"):
            self.assertEqual(self.client.systems_coords(["A"]), {})
        self.answer({"not": "a list"})
        with self.assertLogs(level="WARNING"):
            self.assertEqual(self.client.systems_coords(["A"]), {})


class SpanshSweepTests(unittest.TestCase):
    def setUp(self):
        config = types.ModuleType("config")
        config.appname = "EDMarketConnector"
        config.user_agent = "EDMarketConnector/6.1.2"
        config.config = types.SimpleNamespace(get_str=lambda key: "", default_journal_dir="")
        patcher = mock.patch.dict(sys.modules, {"config": config})
        patcher.start()
        self.addCleanup(patcher.stop)
        for name in [m for m in sys.modules if m in ("plugin.region_sweep_spansh", "plugin.http_identity")]:
            sys.modules.pop(name)
        self.client = importlib.import_module("plugin.region_sweep_spansh")

    def search(self, data, *args):
        response = FakeResponse(data)
        with mock.patch.object(self.client.urllib.request, "urlopen", return_value=response) as opened:
            result = self.client.search_boxel_systems(*args)
        return result, opened

    def test_only_names_that_start_with_the_prefix_are_kept(self):
        names = ["Eorld Byoi AA-A h0", "Eorld Byoi AA-A h1", "Eorld Byoi AB-A h0", "Eorld Byoi AA-A h2"]
        result, _ = self.search(names, "Eorld Byoi", "AA-A")
        self.assertEqual(result, ["Eorld Byoi AA-A h0", "Eorld Byoi AA-A h1", "Eorld Byoi AA-A h2"])

    def test_a_mass_code_narrows_the_prefix(self):
        names = ["Sec AA-A h0", "Sec AA-A g1"]
        result, opened = self.search(names, "Sec", "AA-A", "h")
        self.assertEqual(result, ["Sec AA-A h0"])
        self.assertIn("q=Sec+AA-A+h", opened.call_args.args[0].full_url)

    def test_non_text_entries_are_skipped(self):
        result, _ = self.search(["Sec AA-A h0", 5, None, {"x": 1}], "Sec", "AA-A")
        self.assertEqual(result, ["Sec AA-A h0"])

    def test_the_request_names_wntb_and_has_a_timeout(self):
        _result, opened = self.search([], "Sec", "AA-A")
        request = opened.call_args.args[0]
        self.assertIn("WNTB", request.get_header("User-agent"))
        self.assertEqual(opened.call_args.kwargs["timeout"], self.client.REQUEST_TIMEOUT_S)
        self.assertEqual(request.get_method(), "GET")

    def test_a_surprising_answer_raises_so_the_caller_can_report_it(self):
        for data in ({"not": "a list"}, "text", None):
            with self.assertRaises(ValueError):
                self.search(data, "Sec", "AA-A")

    def test_a_network_failure_is_raised_not_swallowed(self):
        with mock.patch.object(self.client.urllib.request, "urlopen", side_effect=OSError("down")):
            with self.assertRaises(OSError):
                self.client.search_boxel_systems("Sec", "AA-A")


if __name__ == "__main__":
    unittest.main()
