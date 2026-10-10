"""
Every data file WNTB keeps is either per commander or has a stated reason it is not.

Two commanders on one install must never share data about their own play. This lists every file the updater protects
(`_OWN_DATA_FILES`) and how each one keeps commanders apart; a new data file fails this test until it is classified here, so
nobody can add a shared one by accident. The behaviour behind each entry is tested where it lives (see
`test_per_commander_data.py` and the per-feature suites).

It reads the sources instead of importing them, so it needs no EDMC stand-ins and behaves the same on Windows and Linux.
"""
from __future__ import annotations

import os
import re
import unittest

ROOT = os.path.join(os.path.dirname(__file__), "..")

# file -> how the commander's data is kept apart
PER_COMMANDER = {
    "sessions.json": "every session records its commander; the history window and its totals show only the active commander's, "
                     "and the 200-session limit is per commander (store.sessions_of / trim)",
    "boxel_state.json": "keyed by commander (boxel_state.py)",
    "survey_log.json": "one log per commander (commander_data.py, survey_log.load_log/save_log)",
    "region_sweep_state.json": "keyed by commander (region_sweep_state.py)",
    "waypoint_route_state.json": "keyed by commander (waypoint_route_state.py)",
    "visited_systems.json": "keyed by commander (visited_systems.py)",
    "organic_scan_state.json": "keyed by commander (organic_scan_state.py)",
    "codex_completionist_state.json": "one tally per commander (codex_completionist_state.py)",
    "bgs_state.json": "keyed by commander (bgs_state.py)",
    "powerplay_state.json": "keyed by commander (powerplay_state.py)",
    "mining_hotspots.json": "one list per commander (commander_data.py, HotspotRepository.set_commander)",
    "mining_coverage.json": "one map per commander (commander_data.py, CoverageRepository.set_commander)",
    "ship_builds.json": "keyed by commander (ship_builds_data.py)",
    "colonisation_sites.json": "keyed by commander (colonisation_data.py)",
    "colonisation_carrier.json": "one record per commander (commander_data.py, colonisation_carrier.py)",
    "trade_ledger.json": "one session per commander (trade_ledger.LedgerBook)",
    "trade_carrier.json": "keyed by commander (trade_carrier.py)",
    "trade_route_start.json": "keyed by commander (trade_route_start.py)",
    "trade_stock.json": "keyed by commander (trade_stock.py)",
    "trade_history.json": "every saved session records its commander; the window opens on the active commander's",
}

# file -> why it holds no commander's play
NOT_COMMANDER_DATA = {
    "boxel_survey_export.csv": "an on-demand export of the active commander's survey finds; running it for another "
                               "commander overwrites it",
    "codex_catalog.json": "a cache of Canonn's public list of Codex entries",
    "session_credits.json": "the current login only: one record that names its commander and is replaced when another "
                            "commander logs in (session_credits.sync_session)",
    "trade_journal_scan.json": "which journal files have been read (a fact about files, not about a commander)",
}


def _protected_files() -> set:
    with open(os.path.join(ROOT, "plugin", "update.py"), "r", encoding="utf-8") as handle:
        source = handle.read()
    block = source[source.index("_OWN_DATA_FILES: set"):source.index("_OWN_DIRS =")]
    return set(re.findall(r'"([^"]+\.(?:json|csv))"', block))


class DataFilesPerCommanderTests(unittest.TestCase):
    def test_every_protected_data_file_is_classified(self) -> None:
        protected = _protected_files()
        self.assertIn("sessions.json", protected, "the parse found nothing; the test is broken")
        classified = set(PER_COMMANDER) | set(NOT_COMMANDER_DATA)
        self.assertEqual(protected - classified, set(),
                         "a new data file: say in this test how it keeps commanders apart (or why it holds no commander's play)")
        self.assertEqual(classified - protected, set(), "listed here but not a protected data file any more")

    def test_no_file_is_in_both_lists(self) -> None:
        self.assertEqual(set(PER_COMMANDER) & set(NOT_COMMANDER_DATA), set())

    def test_every_entry_says_how(self) -> None:
        for table in (PER_COMMANDER, NOT_COMMANDER_DATA):
            for name, how in table.items():
                self.assertGreater(len(how.strip()), 10, name)

    def test_commander_names_never_become_file_names_outside_the_run_archive(self) -> None:
        """A file named after a commander would behave differently on Windows (case-insensitive, reserved characters) and
        Linux (case-sensitive). Only the mining run archive does it, through its filename sanitiser."""
        offenders = []
        for name in sorted(os.listdir(os.path.join(ROOT, "plugin"))):
            if not name.endswith(".py") or name == "mining_session_archive.py":
                continue
            with open(os.path.join(ROOT, "plugin", name), "r", encoding="utf-8") as handle:
                text = handle.read()
            if re.search(r'os\.path\.join\([^)]*\b(cmdr|commander)\b[^)]*\)', text):
                offenders.append(name)
        self.assertEqual(offenders, [])


if __name__ == "__main__":
    unittest.main()
