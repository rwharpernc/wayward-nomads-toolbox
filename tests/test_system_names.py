"""System-name suggestions (system_names.py): the systems remembered, the registered sources, Spansh's answers and the switch that gates them.
The network is replaced. The sample answer is shaped like a real one from spansh.co.uk (2026-10-13)."""
from __future__ import annotations

import io
import json
import os
import sys
import types
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

SETTINGS = {}
if "config" not in sys.modules:
    _stub = types.ModuleType("config")
    _stub.appname = "EDMarketConnector"  # type: ignore[attr-defined]
    _stub.config = types.SimpleNamespace(get_bool=lambda key, default=False: False, get_str=lambda *_a, **_k: "", default_journal_dir="")
    sys.modules["config"] = _stub

from plugin import system_names as N  # noqa: E402

ANSWER = {"min_max": [{"id64": 1, "name": "Sol", "x": 0, "y": 0, "z": 0}], "values": ["Sol", "Solitude", "Sollaro"]}


class Response(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def reply(data):
    return mock.patch.object(N.urllib.request, "urlopen", return_value=Response(json.dumps(data).encode("utf-8")))


class SystemNameTests(unittest.TestCase):
    def setUp(self):
        N.clear()
        SETTINGS.clear()
        patch = mock.patch.object(N, "config", types.SimpleNamespace(get_bool=lambda key, default=False: SETTINGS.get(key, default)))
        patch.start()
        self.addCleanup(patch.stop)

    def test_the_systems_you_have_been_in_come_first_most_recent_first(self):
        for name in ("Sol", "Colonia", "  sol ", "Sagittarius A*"):
            N.remember(name)
        self.assertEqual(N.local(), ["Sagittarius A*", "sol", "Colonia"])

    def test_registered_sources_follow_after_without_repeats_and_a_broken_one_is_ignored(self):
        N.remember("Sol")
        N.add_source(lambda: ["Colonia", "SOL", "", "  Beagle Point "])
        N.add_source(lambda: 1 / 0)
        self.assertEqual(N.local(), ["Sol", "Colonia", "Beagle Point"])

    def test_the_session_list_is_limited(self):
        for number in range(N.MAX_REMEMBERED + 25):
            N.remember(f"System {number}")
        self.assertEqual(len(N.local()), N.MAX_REMEMBERED)
        self.assertEqual(N.local()[0], f"System {N.MAX_REMEMBERED + 24}")

    def test_spansh_is_off_until_it_is_switched_on_and_nothing_is_sent_while_it_is_off(self):
        self.assertFalse(N.remote_enabled())
        with reply(ANSWER) as call:
            self.assertEqual(N.fetch("sol"), [])
        call.assert_not_called()

    def test_an_answer_is_parsed_kept_and_found_again_for_longer_text(self):
        SETTINGS[N.CFG_REMOTE] = True
        with reply(ANSWER) as call:
            self.assertEqual(N.fetch("sol"), ["Sol", "Solitude", "Sollaro"])
        request = call.call_args.args[0]
        self.assertIn("q=sol", request.full_url)
        self.assertIn("system-name-suggestions", request.get_header("User-agent"))
        self.assertTrue(N.is_cached("SOL"))
        self.assertEqual(N.cached("solit"), ["Sol", "Solitude", "Sollaro"])      # the longest start already asked about
        self.assertEqual(N.cached("so"), [])                                      # too short to have been asked

    def test_two_letters_are_never_sent(self):
        SETTINGS[N.CFG_REMOTE] = True
        with reply(ANSWER) as call:
            self.assertEqual(N.fetch("so"), [])
        call.assert_not_called()

    def test_a_failure_gives_nothing_and_is_not_kept_so_a_later_try_can_work(self):
        SETTINGS[N.CFG_REMOTE] = True
        with mock.patch.object(N.urllib.request, "urlopen", side_effect=OSError("down")):
            self.assertEqual(N.fetch("sol"), [])
        self.assertFalse(N.is_cached("sol"))

    def test_a_damaged_answer_gives_no_suggestions(self):
        for bad in (None, [], {"values": "Sol"}, {"values": [1, None, ""]}, {"min_max": []}):
            self.assertEqual(N.parse(bad), [], bad)
        self.assertEqual(N.parse({"values": [" Outotz   LS-K d8-0 ", 5, "Sol"]}), ["Outotz LS-K d8-0", "Sol"])


if __name__ == "__main__":
    unittest.main()
