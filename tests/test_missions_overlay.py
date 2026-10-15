"""
The Missions card on the in-game overlay (missions_overlay.py): the lines it builds from a mix of missions, how it follows where the commander is and is heading, how it
is drawn, and its settings. Pure logic with stand-ins for the overlay and the clock; the module imports EDMC, so it is imported with stand-ins that are removed again.
Run with: python -m unittest discover -s tests
"""
from __future__ import annotations

import importlib
import os
import sys
import types
import unittest
from datetime import datetime, timedelta, timezone
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

class _Anything(types.ModuleType):
    def __getattr__(self, name: str):
        if name.startswith("__"):
            raise AttributeError(name)
        return mock.MagicMock(name=f"{self.__name__}.{name}")


import tkinter  # noqa: E402,F401  (kept in sys.modules: the stand-ins below would otherwise drop it again)

_EDMC = ("theme", "myNotebook", "monitor", "ttkHyperlinkLabel", "edmc_data", "plug", "companion", "EDMCLogging", "l10n", "timeout_session",
         "protocol", "prefs", "killswitch", "Tooltips", "ttkDefaults", "requests")
_CONFIG = types.ModuleType("config")
_CONFIG.appname = "EDMarketConnector"  # type: ignore[attr-defined]
_CONFIG.config = types.SimpleNamespace(get_str=lambda *_a, **_k: "", get_bool=lambda *_a, default=False, **_k: default, set=lambda *_a: None)  # type: ignore[attr-defined]

import plugin as _plugin_package  # noqa: E402

_BEFORE = set(sys.modules)
with mock.patch.dict(sys.modules, {**{name: _Anything(name) for name in _EDMC}, "config": _CONFIG}):
    M = importlib.import_module("plugin.missions_overlay")
    all_missions = importlib.import_module("plugin.all_missions")
    kill_tracker = importlib.import_module("plugin.kill_tracker")
    mission_types = importlib.import_module("plugin.mission_types")
    overlay_placement = importlib.import_module("plugin.overlay_placement")
    _ADDED = [name for name in sys.modules if name not in _BEFORE and name.startswith("plugin.")]
# The stand-ins leave sys.modules on exit, but the package keeps an attribute for every submodule imported under them; `from plugin import x` in a test
# module that comes later would find those, bound to the stand-in `config`. Drop them so the next import is a fresh one.
for _name in _ADDED:
    _short = _name.split(".", 1)[1]
    if "." not in _short and hasattr(_plugin_package, _short):
        delattr(_plugin_package, _short)

NOW = datetime(2026, 10, 15, 12, 0, 0, tzinfo=timezone.utc)


def at(minutes):
    return NOW + timedelta(minutes=minutes)


def entry(mission_id, category=mission_types.TRADE, label="Deliver", system="Jarogee", station="Fabian Port", minutes=600, ready=False, faction="", progress="",
          reward=100000):
    return M.Entry(mission_id, category, label, faction, system, station, reward, at(minutes) if minutes is not None else None, ready, progress)


def texts(lines):
    return [t for t, _r in lines]


class TimeLeftTests(unittest.TestCase):
    def test_the_formats(self):
        for minutes, seconds, expected in ((None, None, ""), (-5, None, "expired"), (0, None, "expired")):
            self.assertEqual(M.time_left(at(minutes) if minutes is not None else None, NOW), expected)
        self.assertEqual(M.time_left(NOW + timedelta(seconds=30), NOW), "<1m")
        self.assertEqual(M.time_left(at(35), NOW), "35m")
        self.assertEqual(M.time_left(at(80), NOW), "1h20m")
        self.assertEqual(M.time_left(at(23 * 60 + 59), NOW), "23h59m")
        self.assertEqual(M.time_left(at(24 * 60), NOW), "1d")
        self.assertEqual(M.time_left(at(3 * 24 * 60 + 600), NOW), "3d")

    def test_expiry_text_is_parsed_or_ignored(self):
        self.assertEqual(M.parse_expiry("2026-10-16T10:00:00Z"), datetime(2026, 10, 16, 10, tzinfo=timezone.utc))
        for bad in ("", None, "never", 5):
            self.assertIsNone(M.parse_expiry(bad))


class FitTests(unittest.TestCase):
    def test_the_time_always_shows_and_the_left_part_is_cut(self):
        line = M._fit("A very long mission title that goes on and on and on and on", "1h20m")
        self.assertLessEqual(len(line), M.LINE_CHARS)
        self.assertTrue(line.endswith("  1h20m"))
        self.assertIn("…", line)
        self.assertEqual(M._fit("Short", "5m"), "Short  5m")
        self.assertEqual(M._fit("Short", ""), "Short")


class StackTests(unittest.TestCase):
    def test_massacres_for_one_faction_at_one_place_become_one_line(self):
        items = M.stack([entry(1, mission_types.MASSACRE_SPACE, "Massacre", faction="Li Yong-Rui", minutes=1500),
                         entry(2, mission_types.MASSACRE_SPACE, "Massacre", faction="Li Yong-Rui", minutes=900),
                         entry(3, mission_types.MASSACRE_SPACE, "Massacre", faction="Other Faction", minutes=900),
                         entry(4, mission_types.TRADE, "Deliver")])
        by_label = {i.label: i for i in items}
        self.assertEqual(sorted(by_label), ["Deliver", "Massacre Other Faction", "Massacre x2 Li Yong-Rui"])
        stacked = by_label["Massacre x2 Li Yong-Rui"]
        self.assertEqual((stacked.count, stacked.expiry), (2, at(900)))                # the soonest expiry of the stack

    def test_identical_missions_for_the_same_place_stack_and_different_places_do_not(self):
        items = M.stack([entry(1, label="Strategic Data Transfer", station="Fabian Port", minutes=600), entry(2, label="Strategic Data Transfer", station="Fabian Port", minutes=300),
                         entry(3, label="Strategic Data Transfer", station="Other Port"), entry(4, label="54 Tourists Seeking Transport", station="Fabian Port")])
        self.assertEqual(sorted((i.label, i.station, i.count) for i in items),
                         [("54 Tourists Seeking Transport", "Fabian Port", 1), ("Strategic Data Transfer", "Other Port", 1), ("Strategic Data Transfer x2", "Fabian Port", 2)])
        self.assertEqual(next(i for i in items if i.count == 2).expiry, at(300))

    def test_a_ready_massacre_is_not_stacked_with_one_still_to_do(self):
        items = M.stack([entry(1, mission_types.MASSACRE_SPACE, "Massacre", faction="F", ready=True), entry(2, mission_types.MASSACRE_SPACE, "Massacre", faction="F")])
        self.assertEqual(len(items), 2)

    def test_cargo_progress_goes_on_the_line(self):
        item = M.stack([entry(1, label="40 Gold", progress="12/40")])[0]
        self.assertEqual(item.label, "40 Gold 12/40")


class BuildLinesTests(unittest.TestCase):
    def build(self, entries, here="Jarogee", next_system="Sol", rows=8, **kw):
        return M.build_lines(entries, here, next_system, rows, NOW, **kw)

    def test_no_missions_no_card(self):
        self.assertEqual(self.build([]), [])

    def test_here_then_next_then_elsewhere(self):
        lines = self.build([entry(1, system="Ross 310", station="Hudson Hub"), entry(2, system="Sol", station="Abraham Lincoln"), entry(3, system="Jarogee", station="Fabian Port")], )
        self.assertEqual([r for _t, r in lines], ["title", "header", "text", "header", "text", "header", "text"])
        self.assertEqual(texts(lines)[1], "HERE Jarogee")
        self.assertEqual(texts(lines)[3], "NEXT Sol")
        self.assertEqual(texts(lines)[5], "ELSEWHERE")
        self.assertIn("Deliver > Fabian Port", lines[2][0])                         # here: the station
        self.assertIn("Deliver > Ross 310", lines[6][0])                            # elsewhere: the system

    def test_the_header_counts_missions_ready_and_soon(self):
        lines = self.build([entry(1, label="A", ready=True), entry(2, label="B", minutes=30), entry(3, label="C"),
                            entry(4, mission_types.MASSACRE_SPACE, "Massacre", faction="F"), entry(5, mission_types.MASSACRE_SPACE, "Massacre", faction="F")])
        self.assertEqual(lines[0], ("MISSIONS 5 · 1 ready · 1 soon", "title"))               # the two massacres are one line but count as two missions

    def test_ready_first_then_soonest(self):
        lines = self.build([entry(1, label="Late", minutes=3000), entry(2, label="Soon", minutes=90), entry(3, label="Done", minutes=4000, ready=True), entry(4, label="No expiry", minutes=None)])
        self.assertEqual([t.split("  ")[0] for t in texts(lines)[2:]], ["✓ Done > Fabian Port", "Soon > Fabian Port", "Late > Fabian Port", "No expiry > Fabian Port"])

    def test_colours_follow_urgency(self):
        lines = dict((t.split(" > ")[0], r) for t, r in self.build([entry(1, label="Red", minutes=30), entry(2, label="Amber", minutes=200), entry(3, label="Plain", minutes=2000),
                                                                    entry(4, label="Ready", minutes=10, ready=True)])[2:])
        self.assertEqual(lines, {"Red": "red", "Amber": "warn", "Plain": "text", "✓ Ready": "ok"})

    def test_the_urgent_limit_is_a_setting(self):
        lines = self.build([entry(1, label="Two hours", minutes=120)], urgent_minutes=180)
        self.assertEqual(lines[-1][1], "red")

    def test_the_row_limit_hides_the_rest_and_says_how_many_and_where(self):
        entries = [entry(i, system=f"System {i}", minutes=100 + i) for i in range(10)]
        lines = self.build(entries, here="Nowhere", next_system="", rows=4)
        self.assertEqual(len([t for t in texts(lines) if " > " in t]), 4)
        self.assertEqual(lines[-1], ("+6 more in 6 systems", "muted"))
        self.assertNotIn("ELSEWHERE", texts(lines))                                 # with no HERE or NEXT the rest has no heading of its own

    def test_here_takes_the_rows_before_next_and_the_rest(self):
        entries = [entry(1, label="A", system="Jarogee"), entry(2, label="B", system="Jarogee"), entry(3, label="C", system="Jarogee"), entry(4, system="Sol"), entry(5, system="Ross 310")]
        lines = self.build(entries, rows=3)
        self.assertEqual(len([t for t in texts(lines) if " > " in t]), 3)
        self.assertNotIn("NEXT Sol", texts(lines))
        self.assertEqual(lines[-1][0], "+2 more in 2 systems")

    def test_the_row_limit_is_kept_within_its_bounds(self):
        entries = [entry(i, system=f"S{i}") for i in range(20)]
        self.assertEqual(len([t for t in texts(self.build(entries, rows=1)) if " > " in t]), M.MIN_ROWS)
        self.assertEqual(len([t for t in texts(self.build(entries, rows=99)) if " > " in t]), M.MAX_ROWS)

    def test_next_can_be_turned_off(self):
        lines = self.build([entry(1, system="Sol")], show_next=False)
        self.assertNotIn("NEXT Sol", texts(lines))
        self.assertIn("MISSIONS 1", texts(lines)[0])

    def test_systems_match_without_regard_to_case_and_a_target_equal_to_here_is_not_next(self):
        lines = self.build([entry(1, system="JAROGEE")], here="jarogee", next_system="Jarogee")
        self.assertEqual(texts(lines)[1], "HERE jarogee")
        self.assertNotIn("NEXT", " ".join(texts(lines)))

    def test_a_mission_with_no_known_place_is_elsewhere(self):
        lines = self.build([entry(1, system="", station="")])
        self.assertTrue(texts(lines)[1].startswith("Deliver"))
        self.assertNotIn(" > ", texts(lines)[1])

    def test_no_line_is_longer_than_the_card(self):
        entries = [entry(i, label="A very long label for a mission " * 3, system="A System With A Long Name " * 3, station="Station " * 8) for i in range(6)]
        for text, _role in self.build(entries):
            self.assertLessEqual(len(text), M.LINE_CHARS + 2)


class EntriesFromTests(unittest.TestCase):
    CMDR = "Overlay Test"

    def summary(self, mission_id, name="Mission_Delivery", dest_system="Sol", dest_station="Abraham Lincoln", **extra):
        event = {"MissionID": mission_id, "Name": name, "LocalisedName": "Deliver goods", "Faction": "Some Faction", "DestinationSystem": dest_system,
                 "DestinationStation": dest_station, "Reward": 50000, "Wing": False, "Expiry": "2026-10-16T10:00:00Z", "timestamp": "2026-10-15T09:00:00Z", **extra}
        return all_missions.MissionSummary.from_event(event)

    def test_a_pending_mission_goes_to_its_destination(self):
        entries = M.entries_from({1: self.summary(1)}, self.CMDR)
        self.assertEqual((entries[0].system, entries[0].station, entries[0].ready, entries[0].expiry), ("Sol", "Abraham Lincoln", False, datetime(2026, 10, 16, 10, tzinfo=timezone.utc)))

    def test_a_redirected_mission_is_ready_and_goes_to_its_new_hand_in(self):
        kill_tracker.add_redirect(self.CMDR, {"MissionID": 2, "NewDestinationSystem": "Jarogee", "NewDestinationStation": "Fabian Port"})
        entries = M.entries_from({2: self.summary(2)}, self.CMDR)
        self.assertEqual((entries[0].ready, entries[0].system, entries[0].station), (True, "Jarogee", "Fabian Port"))

    def test_massacre_missions_get_a_short_label_and_their_faction(self):
        entries = M.entries_from({3: self.summary(3, name="Mission_Massacre")}, self.CMDR)
        self.assertEqual((entries[0].category, entries[0].label, entries[0].faction), (mission_types.MASSACRE_SPACE, "Massacre", "Some Faction"))


class StateTests(unittest.TestCase):
    def state(self, entries=None, enabled=True, rows=8):
        self.drawn = []
        self.clock = [0.0]
        cfg = M.MissionsOverlayConfig(enabled=enabled, rows=rows)
        self.entries = entries if entries is not None else [entry(1, system="Jarogee"), entry(2, system="Sol")]
        return M.MissionsOverlay(lambda: self.entries, draw=self.drawn.append, now=lambda: NOW, cfg=lambda: cfg, clock=lambda: self.clock[0])

    def test_jumps_set_where_you_are_and_a_target_sets_the_next_jump(self):
        state = self.state()
        state.handle_event({"event": "FSDJump", "StarSystem": "Jarogee"})
        state.handle_event({"event": "FSDTarget", "Name": "Sol", "RemainingJumpsInRoute": 2})
        self.assertEqual((state.here, state.next_system), ("Jarogee", "Sol"))
        self.assertIn("NEXT Sol", texts(self.drawn[-1]))

    def test_arriving_at_the_target_clears_it(self):
        state = self.state()
        state.handle_event({"event": "FSDTarget", "Name": "Sol"})
        state.handle_event({"event": "FSDJump", "StarSystem": "Sol"})
        self.assertEqual((state.here, state.next_system), ("Sol", ""))
        state.handle_event({"event": "FSDTarget", "Name": "Sol"})                 # a target equal to where you are is no target
        self.assertEqual(state.next_system, "")

    def test_the_route_ending_or_a_new_game_clears_the_target(self):
        for clearing in ("NavRouteClear", "LoadGame"):
            state = self.state()
            state.handle_event({"event": "FSDTarget", "Name": "Sol"})
            state.handle_event({"event": clearing})
            self.assertEqual(state.next_system, "", clearing)

    def test_nothing_is_drawn_while_it_is_off(self):
        state = self.state(enabled=False)
        state.handle_event({"event": "FSDJump", "StarSystem": "Jarogee"})
        state.refresh()
        self.assertEqual(self.drawn, [])

    def test_an_unchanged_card_is_drawn_again_only_now_and_then(self):
        state = self.state()
        state.handle_event({"event": "FSDJump", "StarSystem": "Jarogee"})
        count = len(self.drawn)
        state.refresh()
        self.assertEqual(len(self.drawn), count)
        self.clock[0] += M.RESEND_S + 1
        state.refresh()
        self.assertEqual(len(self.drawn), count + 1)

    def test_a_change_in_the_missions_is_drawn_and_an_empty_board_clears_the_card_once(self):
        state = self.state()
        state.handle_event({"event": "FSDJump", "StarSystem": "Jarogee"})
        count = len(self.drawn)
        self.entries.append(entry(3, system="Jarogee"))
        state.handle_event({"event": "MissionAccepted"})
        self.assertEqual(len(self.drawn), count + 1)
        self.entries.clear()
        state.handle_event({"event": "MissionCompleted"})
        self.assertEqual(self.drawn[-1], [])
        count = len(self.drawn)
        state.handle_event({"event": "MissionCompleted"})
        state.refresh()
        self.assertEqual(len(self.drawn), count)                                   # already clear: nothing more to say

    def test_other_events_do_not_redraw(self):
        state = self.state()
        state.handle_event({"event": "FSDJump", "StarSystem": "Jarogee"})
        count = len(self.drawn)
        for event in ("Music", "ReceiveText", "Scan", "Status"):
            state.handle_event({"event": event})
        self.assertEqual(len(self.drawn), count)

    def test_junk_events_never_raise(self):
        state = self.state()
        for junk in ({}, {"event": None}, {"event": "FSDJump"}, {"event": "FSDJump", "StarSystem": 5}, {"event": "FSDTarget"}, {"event": "FSDTarget", "Name": None}):
            state.handle_event(junk)


class FakeClient:
    def __init__(self):
        self.shapes, self.messages = [], []

    def send_shape(self, shape_id, shape, border, fill, x, y, w, h, ttl=0, thickness=1):
        self.shapes.append((shape_id, border, fill, x, y, w, h, ttl))

    def send_message(self, msg_id, text, color, x, y, ttl=0, size="normal"):
        self.messages.append((msg_id, text, color, x, y, ttl))


class RenderTests(unittest.TestCase):
    def test_the_card_and_its_lines_are_drawn_with_the_roles_coloured(self):
        client = FakeClient()
        lines = [("MISSIONS 2", "title"), ("HERE Sol", "header"), ("Late  5m", "red"), ("Later  9h", "text")]
        M.render(lines, client)
        self.assertEqual(len(client.shapes), 1)
        drawn = {m[0]: m for m in client.messages if m[1]}
        self.assertEqual(len(drawn), 4)
        self.assertEqual(drawn["wntb_missions_line2"][2], M.RED)
        self.assertEqual(drawn["wntb_missions_line0"][2], M.LEGACY.color("title"))

    def test_a_mission_ready_to_hand_in_is_always_green(self):
        client = FakeClient()
        M.render([("MISSIONS 1", "title"), ("✓ Gold > Dock  35m", "ok")], client)
        drawn = {m[0]: m for m in client.messages if m[1]}
        self.assertEqual(drawn["wntb_missions_line1"][2], M.GREEN)

    def test_lines_left_over_from_a_longer_card_are_blanked(self):
        client = FakeClient()
        M.render([("a", "text")], client)
        blanks = [m for m in client.messages if not m[1]]
        self.assertEqual(len(blanks), len(M._LINE_IDS) - 1)

    def test_no_lines_clears_the_card(self):
        client = FakeClient()
        M.render([], client)
        self.assertEqual(client.shapes[0][2], "")
        self.assertTrue(all(not m[1] for m in client.messages))

    def test_the_card_never_has_more_lines_than_it_has_ids_for(self):
        client = FakeClient()
        M.render([(f"line {i}", "text") for i in range(100)], client)
        self.assertEqual(len([m for m in client.messages if m[1]]), len(M._LINE_IDS))

    def test_width_is_fixed_and_the_corner_slot_exists(self):
        short = M._card_size(M.LEGACY, 3)[0]
        self.assertEqual(M._card_size(M.LEGACY, 12)[0], short)
        self.assertIn("missions", overlay_placement.SLOTS)
        self.assertEqual(overlay_placement.SLOTS["missions"].group, M.GROUP_NAME)

    def test_the_test_card_fits(self):
        lines = M.sample_lines()
        self.assertGreater(len(lines), 5)
        self.assertLessEqual(len(lines), M.MAX_ROWS + M.EXTRA_LINES)
        for text, _role in lines:
            self.assertLessEqual(len(text), M.LINE_CHARS + 2)


class ConfigTests(unittest.TestCase):
    def test_bounds(self):
        self.assertEqual(M._bounded("5", 3, 14, 8), 5)
        self.assertEqual(M._bounded("99", 3, 14, 8), 14)
        self.assertEqual(M._bounded("1", 3, 14, 8), 3)
        for bad in ("", "x", None):
            self.assertEqual(M._bounded(bad, 3, 14, 8), 8)

    def test_defaults_are_off_and_sensible(self):
        cfg = M.MissionsOverlayConfig()
        self.assertEqual((cfg.enabled, cfg.rows, cfg.show_next, cfg.urgent_minutes), (False, 8, True, 60))


class PinnedTests(unittest.TestCase):
    def lines(self, entries, rows=8, here="Jarogee", next_system=""):
        return M.build_lines(entries, here, next_system, rows, NOW, show_next=True)

    def test_pinned_missions_come_first_under_their_own_heading(self):
        entries = [entry(1, system="Jarogee", minutes=30), entry(2, system="Lave", label="Mine Gold", minutes=5000)]
        entries[1] = M.Entry(2, mission_types.TRADE, "Mine Gold", "", "Lave", "Dock", 100000, at(5000), False, "", True)
        lines = self.lines(entries)
        texts = [t for t, _r in lines]
        self.assertEqual(texts[1], "PINNED")
        self.assertIn("Mine Gold", texts[2])
        self.assertIn("Lave", texts[2])                               # not in this system: the system to go to
        self.assertTrue(texts[3].startswith("HERE"))

    def test_a_pinned_mission_in_this_system_shows_its_station(self):
        pinned = M.Entry(1, mission_types.TRADE, "Deliver", "", "Jarogee", "Fabian Port", 1, at(300), False, "", True)
        self.assertIn("Fabian Port", self.lines([pinned])[2][0])

    def test_pinned_missions_are_not_stacked_and_not_listed_twice(self):
        a = M.Entry(1, mission_types.MASSACRE_SPACE, "Massacre", "Li Yong-Rui", "Jarogee", "Dock", 1, at(60), False, "", True)
        b = M.Entry(2, mission_types.MASSACRE_SPACE, "Massacre", "Li Yong-Rui", "Jarogee", "Dock", 1, at(90), False, "", False)
        c = M.Entry(3, mission_types.MASSACRE_SPACE, "Massacre", "Li Yong-Rui", "Jarogee", "Dock", 1, at(95), False, "", False)
        texts = [t for t, _r in self.lines([a, b, c])]
        self.assertEqual(sum("Massacre" in t for t in texts), 2)       # the pinned one, and the other two stacked as x2
        self.assertTrue(any("x2" in t for t in texts))

    def test_pinned_take_the_rows_first_and_the_rest_is_counted(self):
        entries = [M.Entry(i, mission_types.TRADE, f"P{i}", "", "Far", "", 1, at(100 + i), False, "", True) for i in range(3)]
        entries += [entry(10 + i, minutes=50 + i) for i in range(4)]
        lines = self.lines(entries, rows=3)
        texts = [t for t, _r in lines]
        self.assertEqual(sum(t[:1] == "P" and t[1:2].isdigit() for t in texts), 3)
        self.assertTrue(texts[-1].startswith("+4 more"))
        self.assertTrue(texts[0].startswith("MISSIONS 7"))

    def test_entries_from_marks_the_pinned_ids(self):
        summary = all_missions.MissionSummary.from_event({"MissionID": 7, "Name": "Mission_Delivery", "LocalisedName": "Deliver", "Faction": "F", "Expiry": "2026-10-16T12:00:00Z",
                                                          "DestinationSystem": "Sol", "DestinationStation": "Dock", "Reward": 5, "timestamp": "2026-10-15T10:00:00Z"})
        with mock.patch.object(kill_tracker, "get_redirected", lambda cmdr: set()):
            marked = M.entries_from({7: summary}, "cmdr", pinned={7})
            plain = M.entries_from({7: summary}, "cmdr")
        self.assertTrue(marked[0].pinned)
        self.assertFalse(plain[0].pinned)


class ProgressColourTests(unittest.TestCase):
    def line_roles(self, entries, here="Jarogee"):
        return [role for _t, role in M.build_lines(entries, here, "", 8, NOW)][1:]

    def test_progress_colours_the_line(self):
        def e(i, done, required, minutes=3000, ready=False):
            return M.Entry(i, mission_types.TRADE, f"Gold {i}", "", "Jarogee", "Dock", 1, at(minutes), ready, f"{done}/{required}", False, done, required)
        roles = self.line_roles([e(1, 0, 40), e(2, 10, 40), e(3, 30, 40), e(4, 40, 40, ready=True)])
        self.assertEqual(sorted(roles[1:]), sorted(["ok", "high", "low", "text"]))     # ready, over half, started, not started

    def test_time_pressure_still_comes_before_progress(self):
        late = M.Entry(1, mission_types.TRADE, "Gold", "", "Jarogee", "Dock", 1, at(20), False, "30/40", False, 30, 40)
        self.assertEqual(self.line_roles([late])[1], "red")

    def test_stacked_missions_use_their_combined_progress(self):
        a = M.Entry(1, mission_types.MASSACRE_SPACE, "Massacre", "F", "Jarogee", "Dock", 1, at(3000), False, "", False, 40, 40)
        b = M.Entry(2, mission_types.MASSACRE_SPACE, "Massacre", "F", "Jarogee", "Dock", 1, at(3100), False, "", False, 0, 40)
        item = M.stack([a, b])[0]
        self.assertEqual((item.count, item.fraction), (2, 0.5))

    def test_the_colours_are_fixed_whatever_the_scheme(self):
        self.assertEqual(M._colour(M.LEGACY, "high"), M.LIME)
        self.assertEqual(M._colour(M.LEGACY, "low"), M.BLUE)
        self.assertEqual(M._colour(M.LEGACY, "ok"), M.GREEN)


if __name__ == "__main__":
    unittest.main()
