"""
Community Goal payouts (community_goal_state.py): the `CommunityGoalReward` event is kept per commander, newest first,
never twice, and the journal scan collects it. Pure logic; run with: python -m unittest discover -s tests
"""
from __future__ import annotations

import datetime as dt
import json
import os
import sys
import tempfile
import time
import types
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
if "config" not in sys.modules:
    _stub = types.ModuleType("config")
    _stub.appname = "EDMarketConnector"
    _stub.config = types.SimpleNamespace(get_str=lambda key: "", default_journal_dir="")
    sys.modules["config"] = _stub

from plugin import community_goal_state as cg  # noqa: E402


def reward(cg_id=827, credits=125_000_000, at="2025-07-25T18:50:31Z", name="Support Panther Clipper Mk II Launch with Critical Deliveries"):
    return {"timestamp": at, "event": "CommunityGoalReward", "CGID": cg_id, "Name": name, "System": "Aiaba", "Reward": credits}


class RewardStateTests(unittest.TestCase):
    def setUp(self):
        cg.initialize({})
        cg.community_goal_listeners.clear()
        cg.current_cmdr = None

    def test_a_payout_is_kept_for_the_commander_that_earned_it(self):
        cg.add_reward("Alice", reward())
        self.assertEqual([r.credits for r in cg.get_rewards("Alice")], [125_000_000])
        self.assertEqual(cg.get_rewards("Bob"), [])
        self.assertEqual(cg.get_rewards(None), [])

    def test_payouts_list_newest_first(self):
        cg.add_reward("Alice", reward(1, 100, "2025-07-01T00:00:00Z"))
        cg.add_reward("Alice", reward(2, 200, "2025-08-01T00:00:00Z"))
        cg.add_reward("Alice", reward(3, 300, "2025-06-01T00:00:00Z"))
        self.assertEqual([r.credits for r in cg.get_rewards("Alice")], [200, 100, 300])

    def test_the_same_payout_seen_twice_is_kept_once(self):
        cg.add_reward("Alice", reward())
        cg.add_reward("Alice", reward())
        self.assertEqual(len(cg.get_rewards("Alice")), 1)

    def test_events_without_a_usable_amount_are_ignored(self):
        for credits in (0, -5, None, "lots", True):
            cg.add_reward("Alice", reward(credits=credits))
        cg.add_reward("", reward())
        self.assertEqual(cg.get_rewards("Alice"), [])

    def test_only_the_latest_payouts_are_kept(self):
        for i in range(cg.MAX_REWARDS + 5):
            cg.add_reward("Alice", reward(i, 1000 + i, f"2025-01-{(i % 28) + 1:02d}T{i // 28:02d}:00:00Z"))
        self.assertEqual(len(cg.get_rewards("Alice")), cg.MAX_REWARDS)

    def test_seeding_from_the_journal_scan_includes_the_payouts(self):
        cg.initialize({}, {"Alice": [reward(1, 100, "2025-07-01T00:00:00Z"), reward(1, 100, "2025-07-01T00:00:00Z"), reward(2, 50)]})
        self.assertEqual(sorted(r.credits for r in cg.get_rewards("Alice")), [50, 100])

    def test_a_new_payout_tells_the_page_to_redraw_only_for_the_commander_on_screen(self):
        seen = []
        cg.community_goal_listeners.append(lambda goals: seen.append(len(goals)))
        cg.current_cmdr = "Alice"
        cg.add_reward("Bob", reward())
        self.assertEqual(seen, [])
        cg.add_reward("Alice", reward())
        self.assertEqual(len(seen), 1)

    def test_the_line_names_the_goal_the_credits_and_the_day(self):
        text = cg.get_rewards("Alice") or []
        cg.add_reward("Alice", reward())
        line = cg.get_rewards("Alice")[0].text()
        self.assertIn("125,000,000 cr", line)
        self.assertTrue(line.endswith("(2025-07-25)"))
        self.assertEqual(text, [])

    def test_a_long_or_missing_title_stays_bounded(self):
        cg.add_reward("Alice", reward(name="X" * 500))
        self.assertLessEqual(len(cg.get_rewards("Alice")[0].text().split(" - ")[0]), 60)
        cg.add_reward("Bob", reward(name=""))
        self.assertTrue(cg.get_rewards("Bob")[0].text().startswith("Community Goal - "))


class JournalScanTests(unittest.TestCase):
    def test_the_scan_collects_each_commanders_payouts(self):
        # Imported here, not at the top: journal_scan binds to whichever `config` stand-in was in place when it was first
        # imported, and test_missions_data.py's scan tests rely on theirs being the one.
        from plugin import journal_scan
        with tempfile.TemporaryDirectory() as folder, mock.patch.object(journal_scan, "_journal_folder", return_value=folder):
            path = os.path.join(folder, "Journal.1.log")
            with open(path, "w", encoding="utf8") as handle:
                for entry in ({"event": "Commander", "Name": "A"}, reward(1, 100), {"event": "Commander", "Name": "B"}, reward(2, 200)):
                    handle.write(json.dumps(entry) + "\n")
            now = time.time()
            os.utime(path, (now, now))
            log = journal_scan.read_backlog(dt.date.today() - dt.timedelta(days=14))
        self.assertEqual({c: [e["Reward"] for e in events] for c, events in log.rewards.items()}, {"A": [100], "B": [200]})


if __name__ == "__main__":
    unittest.main()
