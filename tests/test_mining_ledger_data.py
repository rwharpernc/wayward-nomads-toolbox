"""
Unit tests for plugin/mining_ledger_data.py.

Pure logic - no EDMC runtime or display needed (EDMC's `config` module is
stubbed). Run with: python -m unittest discover -s tests
"""

from __future__ import annotations

import os
import sys
import types
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.modules.setdefault("config", types.SimpleNamespace(appname="EDMarketConnector"))

from plugin import mining_body_survey as survey  # noqa: E402
from plugin import mining_coverage as coverage  # noqa: E402
from plugin import mining_hotspots as hotspots  # noqa: E402
from plugin import mining_ledger_data as data  # noqa: E402
from plugin import mining_ground  # noqa: E402

SYSTEM = "Col 285 Sector XT-Q c5-21"


def _spot(body: str, material: str = "Monazite", system: str = SYSTEM, **kwargs) -> hotspots.Hotspot:
    return hotspots.Hotspot(system=system, body=body, material=material, **kwargs)


def _body(suffix: str, planet_class: str = "Rocky body", signals=None) -> survey.SurveyedBody:
    return survey.SurveyedBody(f"{SYSTEM} {suffix}", planet_class, None, signals)


class ShortNameTests(unittest.TestCase):
    def test_strips_system_prefix(self) -> None:
        self.assertEqual(data.short_body_name(SYSTEM, f"{SYSTEM} 6 a"), "6 a")

    def test_other_name_unchanged(self) -> None:
        self.assertEqual(data.short_body_name(SYSTEM, "Somewhere else 1"), "Somewhere else 1")

    def test_body_equal_to_system_unchanged(self) -> None:
        self.assertEqual(data.short_body_name(SYSTEM, SYSTEM), SYSTEM)


class BodyGroupTests(unittest.TestCase):
    def test_surveyed_bodies_grouped_by_class_with_saved_counts(self) -> None:
        groups = data.build_body_groups(
            SYSTEM, [_body("6 a", signals=14), _body("7 a", "Icy body")],
            [_spot(f"{SYSTEM} 6 a"), _spot(f"{SYSTEM} 6 a", "Painite")])
        self.assertEqual([g[1] for g in groups], ["Rocky body", "Icy body"])
        rocky = groups[0][2][0]
        self.assertEqual((rocky.saved_count, rocky.mining_signal_count), (2, 14))

    def test_saved_here_and_other_systems_groups(self) -> None:
        saved = [_spot(f"{SYSTEM} 9 z"), _spot("Sol 3 a", system="Sol")]
        groups = data.build_body_groups(SYSTEM, [], saved)
        self.assertEqual([g[1] for g in groups], [data.GROUP_SAVED_HERE, data.GROUP_OTHER_SYSTEMS])
        self.assertEqual(groups[1][2][0].system, "Sol")

    def test_surveyed_body_not_repeated_in_saved_here(self) -> None:
        groups = data.build_body_groups(SYSTEM, [_body("6 a")], [_spot(f"{SYSTEM} 6 a")])
        self.assertEqual([g[1] for g in groups], ["Rocky body"])

    def test_material_filter_keeps_only_matching_saved_bodies(self) -> None:
        saved = [_spot(f"{SYSTEM} 6 a", "Monazite"), _spot(f"{SYSTEM} 7 a", "Painite")]
        groups = data.build_body_groups(SYSTEM, [_body("6 a"), _body("7 a"), _body("8 a")],
                                        saved, material="painite")
        names = [e.short_name for _k, _h, entries in groups for e in entries]
        self.assertEqual(names, ["7 a"])

    def test_no_current_system_still_lists_saved(self) -> None:
        groups = data.build_body_groups(None, [], [_spot("Sol 3 a", system="Sol")])
        self.assertEqual(groups[0][1], data.GROUP_OTHER_SYSTEMS)

    def test_entry_keys_unique_across_systems(self) -> None:
        saved = [_spot("1 a", system="A"), _spot("1 a", system="B")]
        keys = [e.key for _k, _h, entries in data.build_body_groups(None, [], saved) for e in entries]
        self.assertEqual(len(keys), len(set(keys)))


class RigsFilterTests(unittest.TestCase):
    def test_rigs_filter_keeps_only_bodies_with_that_rig_count(self) -> None:
        saved = [_spot(f"{SYSTEM} 6 a", rigs=4), _spot(f"{SYSTEM} 7 a", rigs=3)]
        groups = data.build_body_groups(SYSTEM, [_body("6 a"), _body("7 a")], saved, rigs=3)
        self.assertEqual([e.short_name for _k, _h, es in groups for e in es], ["7 a"])

    def test_both_filters_must_hold_for_the_same_hotspot(self) -> None:
        # 6 a has Painite (3 rigs) and Monazite (4 rigs): no single hotspot is Painite AND 4 rigs.
        saved = [_spot(f"{SYSTEM} 6 a", "Painite", rigs=3), _spot(f"{SYSTEM} 6 a", "Monazite", rigs=4)]
        groups = data.build_body_groups(SYSTEM, [_body("6 a")], saved, material="Painite", rigs=4)
        self.assertEqual(groups, [])
        groups = data.build_body_groups(SYSTEM, [_body("6 a")], saved, material="Painite", rigs=3)
        self.assertEqual(len(groups), 1)

    def test_rig_labels_and_parsing_round_trip(self) -> None:
        saved = [_spot("a", rigs=4), _spot("b", rigs=2), _spot("c", rigs=4), _spot("d")]
        labels = data.rig_labels(saved)
        self.assertEqual(labels, [data.ANY_RIGS, "2 rigs", "4 rigs"])
        self.assertEqual([data.rigs_from_label(l) for l in labels], [None, 2, 4])


def _rates() -> mining_ground.OwnRates:
    """Your own records: icy bodies mostly gave Painite, rocky ones rarely."""
    saved = ([_spot("1", "Painite", ground="icy")] * 5 + [_spot("1", "Bromellite", ground="icy")]
             + [_spot("2", "Painite", ground="rock 80%+ [none]"), _spot("2", "Monazite", ground="rock 80%+ [none]")])
    return mining_ground.OwnRates(saved)


class OwnRatesFilterTests(unittest.TestCase):
    def test_material_filter_keeps_bodies_your_records_favour_highest_share_first(self) -> None:
        bodies = [_body("6 a", "Rocky body"), _body("7 a", "Icy body"), _body("8 a", "Icy body"),
                  _body("9 a", "Metal rich body")]
        groups = data.build_body_groups(SYSTEM, bodies, [], material="Painite", rates=_rates())
        by_heading = {h: [e.short_name for e in es] for _k, h, es in groups}
        self.assertEqual(by_heading, {"Rocky body": ["6 a"], "Icy body": ["7 a", "8 a"]})  # metal-rich: no records
        icy = next(es for _k, h, es in groups if h == "Icy body")
        self.assertAlmostEqual(icy[0].rate_pct, 5 * 100 / 6)

    def test_without_rates_only_saved_hotspots_match(self) -> None:
        groups = data.build_body_groups(SYSTEM, [_body("7 a", "Icy body")], [], material="Painite")
        self.assertEqual(groups, [])

    def test_rigs_filter_ignores_the_rates(self) -> None:
        groups = data.build_body_groups(SYSTEM, [_body("7 a", "Icy body")], [], material="Painite", rigs=3,
                                        rates=_rates())
        self.assertEqual(groups, [])

    def test_materials_come_only_from_saved_hotspots(self) -> None:
        self.assertEqual(data.materials_in([]), [data.ALL_MATERIALS])
        self.assertEqual(data.materials_in([_spot("a", "Painite"), _spot("b", "monazite")]),
                         [data.ALL_MATERIALS, "monazite", "Painite"])

    def test_prospect_rows_flag_materials_saved_on_this_body(self) -> None:
        rows = data.prospect_rows(_rates(), "icy", [_spot("1", "Bromellite")])
        self.assertEqual([(r.material, r.count, r.saved_here) for r in rows],
                         [("Painite", 5, False), ("Bromellite", 1, True)])

    def test_ground_recorded_on_entries(self) -> None:
        groups = data.build_body_groups(SYSTEM, [_body("7 a", "Icy body")], [])
        self.assertEqual(groups[0][2][0].ground, "icy")



class HotspotGroupingTests(unittest.TestCase):
    def test_numbered_ascending_unnumbered_last(self) -> None:
        spots = [_spot("b", signal_number=None), _spot("b", signal_number=13), _spot("b", signal_number=8)]
        labels = [label for label, _ in data.group_by_location(spots)]
        self.assertEqual(labels, ["Location 8", "Location 13", data.UNNUMBERED])

    def test_spots_on_matches_case_insensitively(self) -> None:
        saved = [_spot("Body A"), _spot("Body B")]
        self.assertEqual(len(data.spots_on(saved, SYSTEM.lower(), "body a")), 1)

    def test_materials_list_starts_with_all_and_dedupes(self) -> None:
        saved = [_spot("a", "Painite"), _spot("b", "painite"), _spot("c", "Alexandrite")]
        self.assertEqual(data.materials_in(saved), [data.ALL_MATERIALS, "Alexandrite", "Painite"])

    def test_summarize(self) -> None:
        spots = [_spot("a", mined_tons=500, amount="Depleted"), _spot("a", mined_tons=40, amount="High"),
                 _spot("a")]
        self.assertEqual(data.summarize(spots), data.BodySummary(saved=3, mined_tons=540, still_active=2))


class MaterialSummaryTests(unittest.TestCase):
    def test_groups_case_insensitively_and_orders_by_mined_then_count(self) -> None:
        spots = [_spot("a", "Painite", mined_tons=100), _spot("a", "painite", mined_tons=50, amount="Depleted"),
                 _spot("a", "Monazite", mined_tons=900), _spot("a", "Alexandrite"), _spot("a", "Bromellite")]
        lines = data.material_summary(spots)
        self.assertEqual([m.material for m in lines], ["Monazite", "Painite", "Alexandrite", "Bromellite"])
        painite = lines[1]
        self.assertEqual((painite.hotspots, painite.active, painite.mined_tons), (2, 1, 150))

    def test_empty_and_blank_material(self) -> None:
        self.assertEqual(data.material_summary([]), [])
        self.assertEqual(data.material_summary([_spot("a", "")])[0].material, "Unknown")


class ProjectionTests(unittest.TestCase):
    _RADIUS = 1_000_000.0
    _M_PER_DEG = _RADIUS * 3.141592653589793 / 180.0

    def test_north_offset(self) -> None:
        east, north = data.project_m(0.0, 0.0, 1000 / self._M_PER_DEG, 0.0, self._RADIUS)
        self.assertAlmostEqual(east, 0.0, delta=1.0)
        self.assertAlmostEqual(north, 1000.0, delta=1.0)

    def test_east_offset(self) -> None:
        east, north = data.project_m(0.0, 0.0, 0.0, 500 / self._M_PER_DEG, self._RADIUS)
        self.assertAlmostEqual(east, 500.0, delta=1.0)
        self.assertAlmostEqual(north, 0.0, delta=1.0)

    def test_map_center_preference(self) -> None:
        cov = coverage.BodyCoverage(center=coverage.CoveragePoint(1.0, 2.0))
        spot = _spot("a", latitude=5.0, longitude=6.0)
        self.assertEqual(data.map_center(cov, (3.0, 4.0), [spot]), (1.0, 2.0))
        self.assertEqual(data.map_center(None, (3.0, 4.0), [spot]), (3.0, 4.0))
        self.assertEqual(data.map_center(None, None, [spot]), (5.0, 6.0))
        self.assertIsNone(data.map_center(None, None, [_spot("a")]))


if __name__ == "__main__":
    unittest.main()
