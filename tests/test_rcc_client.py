"""
The Raven Colonial client (rcc_client.py): parsing a system's build sites, ordering and summarising them, and the one request
with its error handling and short memory. The answer shapes are copied from the live API (2026-10-12); the network is a stand-in.
"""
from __future__ import annotations

import io
import json
import os
import sys
import types
import unittest
import urllib.error

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
if "config" not in sys.modules:
    _stub = types.ModuleType("config")
    _stub.appname = "EDMarketConnector"
    _stub.config = types.SimpleNamespace(get_str=lambda key: "", default_journal_dir="")
    sys.modules["config"] = _stub

from plugin import rcc_client as R  # noqa: E402

LIVE = [
    {"id": "&4244307203", "name": "Abbot Barracks", "bodyNum": 8, "buildType": "nemesis", "status": "complete",
     "buildId": "1c4aa5e6", "marketId": 4244307203},
    {"id": "x1778340111618", "name": "Grinning Station", "bodyNum": 7, "buildType": "no_truss", "status": "build", "buildId": "3527"},
    {"id": "x1784074357502", "name": "Victor Xray", "bodyNum": 31, "buildType": "hermes", "status": "plan"},
    {"id": "x1773945381523", "name": "The Empty Share", "bodyNum": 7, "buildType": "dysnomia", "status": "complete", "marketId": 4347887107},
]


SYSTEM = {"v": 6, "rev": 42, "cmdr": "MACTAVIOUS", "name": "Hyades Sector DB-W b2-6", "id64": 13864556963153, "architect": "MACTAVIOUS",
          "reserveLevel": "pristine", "open": False, "sites": LIVE, "bodies": [{"name": "x"}]}


class FakeResponse:
    def __init__(self, body: bytes):
        self._body = io.BytesIO(body)

    def read(self, size=-1):
        return self._body.read(size)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class Opener:
    """Stands in for urlopen: records the requests and answers from a script."""

    def __init__(self, *answers):
        self.answers, self.requests = list(answers), []

    def __call__(self, request, timeout=None):
        self.requests.append((request, timeout))
        answer = self.answers.pop(0)
        if isinstance(answer, Exception):
            raise answer
        return FakeResponse(answer if isinstance(answer, bytes) else json.dumps(answer).encode("utf-8"))


class ParseTests(unittest.TestCase):
    def test_building_then_planned_then_complete_each_by_name(self):
        sites = R.parse_sites(LIVE)
        self.assertEqual([(s.name, s.status) for s in sites], [
            ("Grinning Station", "build"), ("Victor Xray", "plan"), ("Abbot Barracks", "complete"), ("The Empty Share", "complete")])

    def test_the_fields_are_read(self):
        site = next(s for s in R.parse_sites(LIVE) if s.name == "Abbot Barracks")
        self.assertEqual((site.build_type, site.body_num, site.market_id), ("nemesis", 8, 4244307203))
        planned = next(s for s in R.parse_sites(LIVE) if s.name == "Victor Xray")
        self.assertIsNone(planned.market_id)                                 # not in the game yet
        self.assertEqual((planned.status_label, planned.type_label), ("Planned", "Hermes"))

    def test_a_type_key_reads_as_words(self):
        self.assertEqual(R.build_type_label("dual_truss"), "Dual truss")
        self.assertEqual(R.build_type_label(None), "")
        self.assertEqual(R.build_type_label("  "), "")

    def test_numbers_that_arrive_as_text_are_accepted_and_junk_is_not(self):
        sites = R.parse_sites([{"name": "A", "status": "plan", "bodyNum": "7", "marketId": "123"},
                               {"name": "B", "status": "plan", "bodyNum": True, "marketId": "x1"}])
        self.assertEqual((sites[0].body_num, sites[0].market_id), (7, 123))
        self.assertEqual((sites[1].body_num, sites[1].market_id), (None, None))

    def test_malformed_entries_are_skipped_and_an_unknown_status_is_kept_apart(self):
        sites = R.parse_sites(["junk", {}, {"name": ""}, {"name": "Odd", "status": "mothballed"}, {"name": "Fine", "status": "plan"}])
        self.assertEqual([(s.name, s.status) for s in sites], [("Fine", "plan"), ("Odd", "")])
        self.assertEqual(sites[1].status_label, "Unknown")

    def test_anything_that_is_not_a_list_gives_nothing(self):
        for data in (None, {}, "x", 3, {"sites": []}):
            self.assertEqual(R.parse_sites(data), [])

    def test_a_long_name_is_clipped_and_the_number_of_sites_is_bounded(self):
        long = R.parse_sites([{"name": "N" * 500, "status": "plan"}])[0]
        self.assertLessEqual(len(long.name), R.NAME_MAX)
        many = R.parse_sites([{"name": f"S{i}", "status": "plan"} for i in range(R.MAX_SITES + 50)])
        self.assertEqual(len(many), R.MAX_SITES)

    def test_the_summary_counts_each_kind(self):
        self.assertEqual(R.summary_text(R.parse_sites(LIVE)), "1 building · 1 planned · 2 complete")
        self.assertEqual(R.summary_text([]), "")
        self.assertEqual(R.summary_text(R.parse_sites([{"name": "X", "status": "weird"}])), "1 other")


class SystemTests(unittest.TestCase):
    def test_the_architect_whether_it_is_open_and_the_sites_are_read(self):
        plan = R.parse_system(SYSTEM)
        self.assertEqual((plan.name, plan.architect, plan.is_open, plan.access_label), ("Hyades Sector DB-W b2-6", "MACTAVIOUS", False, "Locked"))
        self.assertEqual(len(plan.sites), 4)
        self.assertEqual(R.parse_system({"open": True}).access_label, "Open")

    def test_missing_or_odd_fields_are_left_empty(self):
        for data in (None, [], "x", {}, {"open": "yes", "architect": None, "sites": "x"}):
            plan = R.parse_system(data, "Fallback")
            self.assertEqual((plan.architect, plan.is_open, plan.access_label, plan.sites), ("", None, "", []))
        self.assertEqual(R.parse_system({}, "Fallback").name, "Fallback")

    def test_names_from_outside_are_clipped(self):
        plan = R.parse_system({"name": "N" * 500, "architect": "A" * 500})
        self.assertLessEqual(len(plan.name), R.NAME_MAX)
        self.assertLessEqual(len(plan.architect), R.NAME_MAX)


class FetchTests(unittest.TestCase):
    def setUp(self):
        R.clear_cache()

    def test_one_request_to_the_system_address_with_a_user_agent_and_a_timeout(self):
        opener = Opener(SYSTEM)
        plan = R.fetch_system("Hyades Sector DB-W b2-6", opener)
        request, timeout = opener.requests[0]
        self.assertEqual(request.full_url, R.BASE_URL + "/api/v2/system/Hyades%20Sector%20DB-W%20b2-6")
        self.assertIn("WNTB", request.get_header("User-agent"))
        self.assertEqual(timeout, R.TIMEOUT_S)
        self.assertEqual(len(plan.sites), 4)

    def test_a_system_name_cannot_change_the_address(self):
        opener = Opener({})
        R.fetch_system("Sol/../../admin?x=1#y", opener)
        url = opener.requests[0][0].full_url
        self.assertTrue(url.startswith(R.BASE_URL + "/api/v2/system/"))
        self.assertNotIn("?", url)
        self.assertNotIn("#", url)
        self.assertEqual(url.count("/"), R.BASE_URL.count("/") + 4)     # /api/v2/system/<one segment>

    def test_the_same_system_asked_again_soon_is_answered_from_memory(self):
        clock = [100.0]
        opener = Opener(SYSTEM)
        R.fetch_system("Sol", opener, now=lambda: clock[0])
        clock[0] += R.CACHE_SECONDS - 1
        self.assertEqual(len(R.fetch_system("SOL", opener, now=lambda: clock[0]).sites), 4)   # no second request, and case does not matter
        self.assertEqual(len(opener.requests), 1)
        clock[0] += 2
        opener.answers.append({"sites": []})
        self.assertEqual(R.fetch_system("Sol", opener, now=lambda: clock[0]).sites, [])        # asked again after a minute
        self.assertEqual(len(opener.requests), 2)

    def test_a_system_it_has_no_record_of_has_no_sites(self):
        opener = Opener(urllib.error.HTTPError("u", 404, "Not Found", {}, io.BytesIO(b"")))
        plan = R.fetch_system("Nowhere", opener)
        self.assertEqual((plan.name, plan.sites, plan.architect, plan.is_open), ("Nowhere", [], "", None))

    def test_a_server_error_is_explained_and_not_remembered(self):
        opener = Opener(urllib.error.HTTPError("u", 500, "Boom", {}, io.BytesIO(b"")), SYSTEM)
        with self.assertRaises(R.RccError) as caught:
            R.fetch_system("Sol", opener)
        self.assertIn("500", str(caught.exception))
        self.assertEqual(len(R.fetch_system("Sol", opener).sites), 4)                    # the failure was not cached

    def test_no_connection_and_a_timeout_are_explained(self):
        for failure in (urllib.error.URLError("down"), TimeoutError("slow"), OSError("reset")):
            with self.assertRaises(R.RccError) as caught:
                R.fetch_system("Sol", Opener(failure))
            self.assertIn("Could not reach Raven Colonial", str(caught.exception))

    def test_an_answer_that_is_not_json_or_far_too_large_is_refused(self):
        with self.assertRaises(R.RccError):
            R.fetch_system("Sol", Opener(b"<html>nope</html>"))
        with self.assertRaises(R.RccError):
            R.fetch_system("Sol", Opener(b" " * (R.MAX_BYTES + 5)))

    def test_a_blank_system_asks_nothing(self):
        opener = Opener()
        for name in ("", "   ", None):
            with self.assertRaises(R.RccError):
                R.fetch_system(name, opener)
        self.assertEqual(opener.requests, [])


if __name__ == "__main__":
    unittest.main()
