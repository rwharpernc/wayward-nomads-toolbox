"""
Unit tests for plugin/organic_scan.py.

Pure logic tests — no EDMC runtime needed. Run with:
    python -m unittest discover -s tests
"""

from __future__ import annotations

import math
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from plugin import organic_region_data as region_data  # noqa: E402
from plugin import organic_scan as scan  # noqa: E402
from plugin import organic_species_data as data  # noqa: E402

_BACTERIUM_GENUS = "$Codex_Ent_Bacterial_Genus_Name;"
_AURASUS = "$Codex_Ent_Bacterial_01_Name;"  # atmosphere=CarbonDioxide, gravity 0.039-0.608, temp 145-400K


class UnitConversionTests(unittest.TestCase):
    def test_gravity_conversion_matches_known_earth_value(self) -> None:
        # 1G is defined as 9.80665 m/s^2 - a body at exactly that should read 1.0G.
        self.assertAlmostEqual(scan.gravity_ms2_to_g(9.80665), 1.0, places=6)

    def test_pressure_conversion_matches_known_atm_value(self) -> None:
        self.assertAlmostEqual(scan.pressure_pa_to_atm(101325.0), 1.0, places=6)


class PredictionTests(unittest.TestCase):
    def test_matches_known_real_species(self) -> None:
        # Bacterium Aurasus's own real ruleset (organic_species_data.py):
        # atmosphere=CarbonDioxide, body_type includes Rocky body,
        # gravity 0.039-0.608, temperature 145-400.
        cond = scan.BodyConditions(
            body_name="Test 1", planet_class="Rocky body", atmosphere="CarbonDioxide",
            gravity_g=0.3, temperature_k=200.0, pressure_atm=0.01, volcanism="",
        )
        matches = scan.predict_species(_BACTERIUM_GENUS, cond)
        names = [m.name for m in matches]
        self.assertIn("Bacterium Aurasus", names)

    def test_does_not_match_outside_temperature_range(self) -> None:
        cond = scan.BodyConditions(
            body_name="Test 2", planet_class="Rocky body", atmosphere="CarbonDioxide",
            gravity_g=0.3, temperature_k=50.0,  # below Aurasus's own min_temperature of 145
        )
        matches = scan.predict_species(_BACTERIUM_GENUS, cond)
        names = [m.name for m in matches]
        self.assertNotIn("Bacterium Aurasus", names)

    def test_does_not_match_wrong_atmosphere(self) -> None:
        cond = scan.BodyConditions(
            body_name="Test 3", planet_class="Rocky body", atmosphere="Ammonia",
            gravity_g=0.3, temperature_k=200.0,
        )
        matches = scan.predict_species(_BACTERIUM_GENUS, cond)
        names = [m.name for m in matches]
        self.assertNotIn("Bacterium Aurasus", names)

    def test_species_with_no_rulesets_never_predicted(self) -> None:
        # Stratum Aranaemus has an empty rulesets tuple in the real data -
        # no condition should ever "match" an empty any().
        cond = scan.BodyConditions(body_name="Test 4", planet_class="Rocky body")
        matches = scan.predict_species("$Codex_Ent_Stratum_04_Name;", cond)
        self.assertEqual(matches, [])


class RegionMatchTests(unittest.TestCase):
    # Cactoida Cortexum's real ruleset (organic_species_data.py):
    # atmosphere=CarbonDioxide, body_type Rocky/High metal content,
    # gravity 0.04-0.276, temp 180-197, min_pressure 0.025, no volcanism,
    # regions=('orion-cygnus',). Sol (0,0,0) resolves to region 18, which
    # IS in REGION_GROUPS['orion-cygnus'] - confirmed via
    # organic_region_data.region_id_for_position.
    _CACTOID_GENUS = "$Codex_Ent_Cactoid_Genus_Name;"
    _SOL_POS = (0.0, 0.0, 0.0)
    # Resolves to region 34, which is NOT in REGION_GROUPS['orion-cygnus']
    # (1, 4, 7, 8, 16, 17, 18, 35) - confirmed the same way.
    _OUTSIDE_ORION_CYGNUS_POS = (5000.0, -20.0, -5000.0)

    def _cactoid_conditions(self, galactic_position) -> scan.BodyConditions:
        return scan.BodyConditions(
            body_name="Test", planet_class="Rocky body", atmosphere="CarbonDioxide",
            gravity_g=0.1, temperature_k=190.0, pressure_atm=0.05, volcanism="",
            galactic_position=galactic_position,
        )

    def test_matches_when_in_required_region(self) -> None:
        matches = scan.predict_species(self._CACTOID_GENUS, self._cactoid_conditions(self._SOL_POS))
        self.assertIn("Cactoida Cortexum", [m.name for m in matches])

    def test_does_not_match_when_outside_required_region(self) -> None:
        matches = scan.predict_species(
            self._CACTOID_GENUS, self._cactoid_conditions(self._OUTSIDE_ORION_CYGNUS_POS))
        self.assertNotIn("Cactoida Cortexum", [m.name for m in matches])

    def test_unknown_position_does_not_eliminate(self) -> None:
        # No FSDJump/Location seen yet this session - the region condition
        # must not eliminate an otherwise-matching species.
        matches = scan.predict_species(self._CACTOID_GENUS, self._cactoid_conditions(None))
        self.assertIn("Cactoida Cortexum", [m.name for m in matches])

    def test_region_id_for_position_matches_bundled_grid(self) -> None:
        self.assertEqual(region_data.region_id_for_position(*self._SOL_POS), 18)
        self.assertIn(18, region_data.REGION_GROUPS["orion-cygnus"])


class GuardianMatchTests(unittest.TestCase):
    # Roseum Brain Tree's real ruleset: temp 200-500, requires_volcanism=True,
    # regions=('brain-tree',), guardian=True.
    _BRANCAE_GENUS = "$Codex_Ent_Brancae_Name;"
    _BRAIN_TREE_SPECIES = "Roseum Brain Tree"
    # Exactly on a real GUARDIAN_ZONES entry's own coordinates (distance 0,
    # well inside its radius) - and confirmed to resolve to a region_id
    # that IS in REGION_GROUPS['brain-tree'].
    _ZONE_NAME = "Hen 2-333"

    def _zone_position(self):
        _radius, coordinates = region_data.GUARDIAN_ZONES[self._ZONE_NAME]
        return coordinates

    def test_zone_coordinates_resolve_into_brain_tree_region(self) -> None:
        # A precondition of the rest of this test class - if the bundled
        # region grid ever regenerates differently, this fails loudly
        # instead of the two tests below silently testing nothing.
        region_id = region_data.region_id_for_position(*self._zone_position())
        self.assertIn(region_id, region_data.REGION_GROUPS["brain-tree"])

    def test_matches_within_guardian_zone(self) -> None:
        cond = scan.BodyConditions(
            body_name="Test", planet_class="Rocky body", temperature_k=300.0,
            volcanism="major rocky magma volcanism", galactic_position=self._zone_position(),
        )
        matches = scan.predict_species(self._BRANCAE_GENUS, cond)
        self.assertIn(self._BRAIN_TREE_SPECIES, [m.name for m in matches])

    def test_does_not_match_far_from_any_guardian_zone(self) -> None:
        # Sol is confirmed (organic_region_data.GUARDIAN_ZONES) farther than
        # every zone's own radius from all eight zones.
        cond = scan.BodyConditions(
            body_name="Test", planet_class="Rocky body", temperature_k=300.0,
            volcanism="major rocky magma volcanism", galactic_position=(0.0, 0.0, 0.0),
        )
        matches = scan.predict_species(self._BRANCAE_GENUS, cond)
        self.assertNotIn(self._BRAIN_TREE_SPECIES, [m.name for m in matches])

    def test_unknown_position_does_not_eliminate(self) -> None:
        cond = scan.BodyConditions(
            body_name="Test", planet_class="Rocky body", temperature_k=300.0,
            volcanism="major rocky magma volcanism", galactic_position=None,
        )
        matches = scan.predict_species(self._BRANCAE_GENUS, cond)
        self.assertIn(self._BRAIN_TREE_SPECIES, [m.name for m in matches])


class AtmosphereComponentMatchTests(unittest.TestCase):
    # Recepta Umbrux's first real ruleset: atmosphere=CarbonDioxide,
    # gravity 0.04-0.276, temp 151-200, atmosphere_component requires
    # SulphurDioxide >= 1.05%.
    _RECEPTA_GENUS = "$Codex_Ent_Recepta_Genus_Name;"
    _UMBRUX = "Recepta Umbrux"

    def _conditions(self, atmosphere_components) -> scan.BodyConditions:
        return scan.BodyConditions(
            body_name="Test", planet_class="Rocky body", atmosphere="CarbonDioxide",
            gravity_g=0.1, temperature_k=175.0, atmosphere_components=atmosphere_components,
        )

    def test_matches_when_trace_gas_meets_threshold(self) -> None:
        matches = scan.predict_species(self._RECEPTA_GENUS, self._conditions({"SulphurDioxide": 1.5}))
        self.assertIn(self._UMBRUX, [m.name for m in matches])

    def test_matches_at_exact_threshold(self) -> None:
        matches = scan.predict_species(self._RECEPTA_GENUS, self._conditions({"SulphurDioxide": 1.05}))
        self.assertIn(self._UMBRUX, [m.name for m in matches])

    def test_does_not_match_below_threshold(self) -> None:
        matches = scan.predict_species(self._RECEPTA_GENUS, self._conditions({"SulphurDioxide": 0.5}))
        self.assertNotIn(self._UMBRUX, [m.name for m in matches])

    def test_does_not_match_when_gas_absent(self) -> None:
        matches = scan.predict_species(self._RECEPTA_GENUS, self._conditions({}))
        self.assertNotIn(self._UMBRUX, [m.name for m in matches])
        matches = scan.predict_species(self._RECEPTA_GENUS, self._conditions(None))
        self.assertNotIn(self._UMBRUX, [m.name for m in matches])


class TuberZoneMatchTests(unittest.TestCase):
    # Roseum Sinuous Tubers' real ruleset (Bark Mound genus): body_type=High
    # metal content body, temp 200-500, volcanism='rocky magma',
    # tuber=('Galactic Center', 'Odin A', 'Ryker B').
    _TUBE_GENUS = "$Codex_Ent_Tube_Name;"
    _ROSEUM = "Roseum Sinuous Tubers"
    # Sol is confirmed (organic_region_data.TUBER_ZONES) farther than every
    # one of these three zones' own max distance.
    _SOL_POS = (0.0, 0.0, 0.0)

    def _within_galactic_center_zone(self):
        (min_ly, max_ly), coordinates = region_data.TUBER_ZONES["Galactic Center"]
        midpoint = (min_ly + max_ly) / 2
        x, y, z = coordinates
        return (x + midpoint, y, z)

    def _conditions(self, galactic_position) -> scan.BodyConditions:
        return scan.BodyConditions(
            body_name="Test", planet_class="High metal content body", temperature_k=300.0,
            volcanism="major rocky magma volcanism", galactic_position=galactic_position,
        )

    def test_zone_midpoint_falls_within_its_own_distance_band(self) -> None:
        # Precondition, same reasoning as GuardianMatchTests' own zone check.
        (min_ly, max_ly), coordinates = region_data.TUBER_ZONES["Galactic Center"]
        distance = ((self._within_galactic_center_zone()[0] - coordinates[0]) ** 2
                   + (self._within_galactic_center_zone()[1] - coordinates[1]) ** 2
                   + (self._within_galactic_center_zone()[2] - coordinates[2]) ** 2) ** 0.5
        self.assertTrue(min_ly <= distance <= max_ly)

    def test_matches_within_a_named_zone(self) -> None:
        matches = scan.predict_species(self._TUBE_GENUS, self._conditions(self._within_galactic_center_zone()))
        self.assertIn(self._ROSEUM, [m.name for m in matches])

    def test_does_not_match_far_from_every_named_zone(self) -> None:
        matches = scan.predict_species(self._TUBE_GENUS, self._conditions(self._SOL_POS))
        self.assertNotIn(self._ROSEUM, [m.name for m in matches])

    def test_unknown_position_does_not_eliminate(self) -> None:
        matches = scan.predict_species(self._TUBE_GENUS, self._conditions(None))
        self.assertIn(self._ROSEUM, [m.name for m in matches])

    def test_any_sentinel_matches_a_position_within_some_zones_band(self) -> None:
        self.assertTrue(scan._tuber_matches(("Any",), self._conditions(self._within_galactic_center_zone())))

    def test_any_sentinel_does_not_match_a_position_within_no_zones_band(self) -> None:
        self.assertFalse(scan._tuber_matches(("Any",), self._conditions(self._SOL_POS)))

    def test_zone_named_but_distance_outside_its_band_does_not_match(self) -> None:
        (min_ly, _max_ly), coordinates = region_data.TUBER_ZONES["Galactic Center"]
        # Well inside the minimum distance - too close, not "in the zone".
        too_close = (coordinates[0] + min_ly / 2, coordinates[1], coordinates[2])
        cond = self._conditions(too_close)
        self.assertFalse(scan._tuber_matches(("Galactic Center",), cond))


class BodiesMatchTests(unittest.TestCase):
    # Gypseeum Brain Tree's real `bodies` requirement: at least one
    # Earthlike body, Gas giant with water based life, or Water giant
    # somewhere in the system (not necessarily the body being scanned).
    _REQUIRED = ("Earthlike body", "Gas giant with water based life", "Water giant")

    def test_matches_when_required_type_present_in_system(self) -> None:
        ruleset = data.SpeciesRuleset(bodies=self._REQUIRED)
        cond = scan.BodyConditions(body_name="Test", system_body_types=("Rocky body", "Earthlike body"))
        self.assertTrue(scan.ruleset_matches(ruleset, cond))

    def test_does_not_match_when_required_type_absent(self) -> None:
        ruleset = data.SpeciesRuleset(bodies=self._REQUIRED)
        cond = scan.BodyConditions(body_name="Test", system_body_types=("Rocky body", "Icy body"))
        self.assertFalse(scan.ruleset_matches(ruleset, cond))

    def test_unknown_system_body_types_does_not_eliminate(self) -> None:
        ruleset = data.SpeciesRuleset(bodies=self._REQUIRED)
        cond = scan.BodyConditions(body_name="Test", system_body_types=None)
        self.assertTrue(scan.ruleset_matches(ruleset, cond))

    def test_matches_real_gypseeum_brain_tree_ruleset_end_to_end(self) -> None:
        # The rest of Gypseeum Brain Tree's own ruleset: body_type=Rocky
        # body, max_gravity=0.42, temp 200-400, volcanism includes 'water',
        # regions=('brain-tree',), guardian=True.
        (_radius, coordinates) = region_data.GUARDIAN_ZONES["Hen 2-333"]
        cond = scan.BodyConditions(
            body_name="Test", planet_class="Rocky body", gravity_g=0.3, temperature_k=300.0,
            volcanism="minor water geysers volcanism", galactic_position=coordinates,
            system_body_types=("Rocky body", "Earthlike body"),
        )
        matches = scan.predict_species("$Codex_Ent_Brancae_Name;", cond)
        self.assertIn("Gypseeum Brain Tree", [m.name for m in matches])

    def test_real_gypseeum_brain_tree_ruleset_fails_without_required_body(self) -> None:
        (_radius, coordinates) = region_data.GUARDIAN_ZONES["Hen 2-333"]
        cond = scan.BodyConditions(
            body_name="Test", planet_class="Rocky body", gravity_g=0.3, temperature_k=300.0,
            volcanism="minor water geysers volcanism", galactic_position=coordinates,
            system_body_types=("Rocky body", "Icy body"),
        )
        matches = scan.predict_species("$Codex_Ent_Brancae_Name;", cond)
        self.assertNotIn("Gypseeum Brain Tree", [m.name for m in matches])


class VolcanismTests(unittest.TestCase):
    def test_requires_volcanism_true_rejects_no_volcanism(self) -> None:
        ruleset = data.SpeciesRuleset(requires_volcanism=True)
        cond_no_volcanism = scan.BodyConditions(body_name="Test 5", volcanism="")
        self.assertFalse(scan.ruleset_matches(ruleset, cond_no_volcanism))
        cond_with_volcanism = scan.BodyConditions(body_name="Test 5", volcanism="minor rocky volcanism")
        self.assertTrue(scan.ruleset_matches(ruleset, cond_with_volcanism))

    def test_requires_volcanism_false_rejects_any_volcanism(self) -> None:
        ruleset = data.SpeciesRuleset(requires_volcanism=False)
        cond_with_volcanism = scan.BodyConditions(body_name="Test 6", volcanism="major water geysers volcanism")
        self.assertFalse(scan.ruleset_matches(ruleset, cond_with_volcanism))

    def test_specific_volcanism_substring_match_is_case_insensitive(self) -> None:
        ruleset = data.SpeciesRuleset(volcanism=("water",))
        cond = scan.BodyConditions(body_name="Test 7", volcanism="Major Water Geysers Volcanism")
        self.assertTrue(scan.ruleset_matches(ruleset, cond))
        cond_other = scan.BodyConditions(body_name="Test 7", volcanism="major rocky magma volcanism")
        self.assertFalse(scan.ruleset_matches(ruleset, cond_other))


class HaversineTests(unittest.TestCase):
    def test_zero_distance_for_identical_points(self) -> None:
        self.assertAlmostEqual(scan.haversine_distance_m(10.0, 20.0, 10.0, 20.0, 300000.0), 0.0, places=6)

    def test_quarter_circumference_for_90_degrees_apart_on_equator(self) -> None:
        # A point 90 degrees of longitude away on the equator is exactly
        # one quarter of the sphere's circumference away.
        radius = 300_000.0
        expected = (2 * math.pi * radius) / 4
        actual = scan.haversine_distance_m(0.0, 0.0, 0.0, 90.0, radius)
        self.assertAlmostEqual(actual, expected, delta=1.0)


class TrackerTests(unittest.TestCase):
    def test_scan_stage_progression(self) -> None:
        tracker = scan.OrganicTracker()
        tracker.note_genus_detected(_BACTERIUM_GENUS)
        organism = tracker.record_scan(_BACTERIUM_GENUS, _AURASUS, "Bacterium Aurasus", "Log", 10.0, 20.0)
        self.assertEqual(organism.stage, 1)
        self.assertFalse(organism.complete)

        tracker.record_scan(_BACTERIUM_GENUS, _AURASUS, "Bacterium Aurasus", "Sample", 10.1, 20.1)
        tracker.record_scan(_BACTERIUM_GENUS, _AURASUS, "Bacterium Aurasus", "Analyse", 10.2, 20.2)
        organism = tracker.organisms[0]
        self.assertEqual(organism.stage, 3)
        self.assertTrue(organism.complete)
        self.assertEqual(organism.value, data.SPECIES[f"{_BACTERIUM_GENUS}|{_AURASUS}"].value)

    def test_next_sample_distance_ok_none_before_first_sample(self) -> None:
        tracker = scan.OrganicTracker()
        tracker.note_genus_detected(_BACTERIUM_GENUS)
        self.assertIsNone(tracker.next_sample_distance_ok(_BACTERIUM_GENUS, 10.0, 20.0, 300000.0))

    def test_next_sample_distance_ok_respects_genus_minimum(self) -> None:
        tracker = scan.OrganicTracker()
        tracker.record_scan(_BACTERIUM_GENUS, _AURASUS, "Bacterium Aurasus", "Log", 0.0, 0.0)
        genus_min_m = data.GENUS[_BACTERIUM_GENUS].min_distance_m
        self.assertGreater(genus_min_m, 0)

        # A point far too close (1 meter of longitude on a huge planet) should fail.
        self.assertFalse(tracker.next_sample_distance_ok(_BACTERIUM_GENUS, 0.0, 0.00001, 300_000.0))
        # A point on the opposite side of the planet should clear any genus's minimum.
        self.assertTrue(tracker.next_sample_distance_ok(_BACTERIUM_GENUS, 0.0, 180.0, 300_000.0))

    def test_reset_clears_all_organisms(self) -> None:
        tracker = scan.OrganicTracker()
        tracker.note_genus_detected(_BACTERIUM_GENUS)
        self.assertEqual(len(tracker.organisms), 1)
        tracker.reset()
        self.assertEqual(len(tracker.organisms), 0)


if __name__ == "__main__":
    unittest.main()
