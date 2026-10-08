"""
Unit tests for plugin/notable_rules.py and the pure parts of plugin/notable.py.

Run with:
    python -m unittest discover -s tests
"""

from __future__ import annotations

import os
import sys
import types
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from plugin import notable_rules as nr  # noqa: E402

G = nr.STANDARD_GRAVITY
HIGH_G_MS2 = nr.HIGH_GRAVITY_MS2


def planet(body_id=1, **fields):
    scan = {"event": "Scan", "BodyName": f"Sys {body_id}", "BodyID": body_id, "SystemAddress": 42,
            "PlanetClass": "Rocky body", "Parents": [{"Star": 0}]}
    scan.update(fields)
    return scan


def star(body_id=0, **fields):
    scan = {"event": "Scan", "BodyName": f"Sys {chr(65 + body_id)}", "BodyID": body_id, "SystemAddress": 42,
            "StarType": "G", "Radius": 7.0e8, "Parents": [{"Null": 9}]}
    scan.update(fields)
    return scan


def ids(matches):
    return [m.rule_id for m in matches]


def run(scan, bodies=None, enabled=None):
    bodies = {} if bodies is None else bodies
    return ids(nr.evaluate(scan, bodies, enabled if enabled is not None else {r.id for r in nr.RULES}))


class SingleScanRuleTests(unittest.TestCase):
    def test_terraformable_landable(self) -> None:
        self.assertIn("terraformable_landable", run(planet(Landable=True, TerraformState="Terraformable")))
        self.assertIn("terraformable_landable", run(planet(Landable=True, TerraformState="Terraformed")))
        self.assertNotIn("terraformable_landable", run(planet(Landable=False, TerraformState="Terraformable")))
        self.assertNotIn("terraformable_landable", run(planet(Landable=True, TerraformState="")))

    def test_high_value_body(self) -> None:
        self.assertIn("high_value", run(planet(PlanetClass="Earthlike body")))
        self.assertIn("high_value", run(planet(PlanetClass="Water world")))
        self.assertIn("high_value", run(planet(PlanetClass="Ammonia world")))
        self.assertIn("high_value", run(planet(PlanetClass="High metal content body", TerraformState="Terraformable")))
        self.assertNotIn("high_value", run(planet(PlanetClass="High metal content body", TerraformState="")))
        self.assertNotIn("high_value", run(planet(PlanetClass="Icy body")))
        self.assertNotIn("high_value", run(star()))

    def test_high_value_body_detail_says_what_is_new(self) -> None:
        scan = planet(PlanetClass="Water world", TerraformState="Terraformable", WasDiscovered=False,
                      WasMapped=False, DistanceFromArrivalLS=1234.5)
        detail = nr.evaluate(scan, {}, {"high_value"})[0].detail
        self.assertEqual(detail, "Undiscovered terraformable water world, 1,234 Ls")
        scan = planet(PlanetClass="Earthlike body", WasDiscovered=True, WasMapped=False)
        self.assertTrue(nr.evaluate(scan, {}, {"high_value"})[0].detail.startswith("Unmapped earthlike"))

    def test_high_gravity_boundary(self) -> None:
        self.assertIn("high_g", run(planet(Landable=True, SurfaceGravity=29.41)))
        self.assertNotIn("high_g", run(planet(Landable=True, SurfaceGravity=29.4)))
        self.assertNotIn("high_g", run(planet(Landable=True, SurfaceGravity=2.5 * G)))  # 2.5 g is below the limit
        self.assertNotIn("high_g", run(planet(Landable=False, SurfaceGravity=40.0)))

    def test_large_landable(self) -> None:
        self.assertIn("large_landable", run(planet(Landable=True, Radius=18_000_001)))
        self.assertNotIn("large_landable", run(planet(Landable=True, Radius=18_000_000)))
        self.assertNotIn("large_landable", run(planet(Landable=False, Radius=20_000_000)))

    def test_fast_rotation_ignores_stars_and_tidally_locked(self) -> None:
        self.assertIn("fast_rotation", run(planet(RotationPeriod=-7 * 3600)))  # retrograde counts
        self.assertNotIn("fast_rotation", run(planet(RotationPeriod=9 * 3600)))
        self.assertNotIn("fast_rotation", run(planet(RotationPeriod=3600, TidalLock=True)))
        self.assertNotIn("fast_rotation", run(star(RotationPeriod=0.01)))

    def test_fast_orbit(self) -> None:
        self.assertIn("fast_orbit", run(planet(OrbitalPeriod=7 * 3600)))
        self.assertNotIn("fast_orbit", run(planet(OrbitalPeriod=8 * 3600)))
        self.assertNotIn("fast_orbit", run(planet()))

    def test_high_eccentricity(self) -> None:
        self.assertIn("high_eccentricity", run(planet(Eccentricity=0.91)))
        self.assertNotIn("high_eccentricity", run(planet(Eccentricity=0.9)))

    def test_wide_ring_uses_real_rings_only(self) -> None:
        wide = {"Name": "Sys 1 A Ring", "InnerRad": 1e8, "OuterRad": 8e8}
        belt = {"Name": "Sys A Belt", "InnerRad": 1e8, "OuterRad": 9e9}
        self.assertIn("wide_ring", run(planet(Radius=6e7, Rings=[wide])))
        edge = {"Name": "R", "InnerRad": 1e8, "OuterRad": 1e8 + 5 * 6e7}  # exactly 5x the radius: not wide
        self.assertNotIn("wide_ring", run(planet(Radius=6e7, Rings=[edge])))
        self.assertNotIn("wide_ring", run(planet(Radius=6e7, Rings=[belt])))
        self.assertNotIn("wide_ring", run(planet(Radius=6e7, Rings=[{"Name": "R", "InnerRad": 1e8, "OuterRad": 2e8}])))
        self.assertNotIn("wide_ring", run(planet(Rings=[wide])))  # no Radius -> cannot judge

    def test_landable_ring(self) -> None:
        ring = {"Name": "Sys 1 A Ring", "InnerRad": 1.0, "OuterRad": 2.0}
        self.assertIn("landable_ring", run(planet(Landable=True, Rings=[ring])))
        self.assertNotIn("landable_ring", run(planet(Landable=False, Rings=[ring])))
        self.assertNotIn("landable_ring", run(planet(Landable=True)))

    def test_good_fsd_injection_needs_five_of_six(self) -> None:
        def mats(*names):
            return [{"Name": n, "Percent": 1.0} for n in names]
        five = mats("carbon", "germanium", "arsenic", "niobium", "yttrium", "iron")
        four = mats("carbon", "germanium", "arsenic", "niobium", "iron")
        self.assertIn("good_fsd", run(planet(Landable=True, Materials=five)))
        self.assertNotIn("good_fsd", run(planet(Landable=True, Materials=four)))
        self.assertNotIn("good_fsd", run(planet(Materials=five)))  # not landable
        self.assertIn("good_fsd", run(planet(
            Landable=True, Materials=mats("Carbon", "Germanium", "Arsenic", "Niobium", "Polonium"))))

    def test_green_gas_giant_temperature_lead(self) -> None:
        iv = {"PlanetClass": "Sudarsky class IV gas giant"}
        self.assertIn("green_gas_giant", run(planet(SurfaceTemperature=1150.0, **iv)))
        self.assertNotIn("green_gas_giant", run(planet(SurfaceTemperature=1200.0, **iv)))
        self.assertNotIn("green_gas_giant", run(planet(SurfaceTemperature=1150.0)))
        ammonia = {"PlanetClass": "Gas giant with ammonia based life"}
        self.assertIn("green_gas_giant", run(planet(SurfaceTemperature=107.355812, **ammonia)))
        self.assertNotIn("green_gas_giant", run(planet(SurfaceTemperature=107.4, **ammonia)))
        # a known temperature for a different class is not a match
        self.assertNotIn("green_gas_giant", run(planet(SurfaceTemperature=107.355812, **iv)))

    def test_green_gas_giant_codex(self) -> None:
        self.assertTrue(nr.green_gas_giant_codex({"Name": "$Codex_Ent_GreenSudarsky_Name;"}))
        self.assertTrue(nr.green_gas_giant_codex({"Name_Localised": "Green Gas Giant"}))
        self.assertFalse(nr.green_gas_giant_codex({"Name_Localised": "Gas Giant Class I"}))


class NeighbourRuleTests(unittest.TestCase):
    def test_shepherd_moon_needs_parent_ring(self) -> None:
        parent = planet(1, Radius=6e7, Rings=[{"Name": "P A Ring", "InnerRad": 1.0e8, "OuterRad": 2.0e8}],
                        Parents=[{"Star": 0}])
        moon = planet(2, SemiMajorAxis=1.5e8, Parents=[{"Planet": 1}, {"Star": 0}])
        self.assertIn("shepherd_moon", run(moon, {1: parent, 2: moon}))
        far = planet(3, SemiMajorAxis=9e8, Parents=[{"Planet": 1}, {"Star": 0}])
        self.assertNotIn("shepherd_moon", run(far, {1: parent, 3: far}))
        self.assertNotIn("shepherd_moon", run(moon, {2: moon}))  # parent not scanned yet

    def test_shepherd_moon_is_judged_against_the_outermost_ring_only(self) -> None:
        belt = {"Name": "P A Belt", "InnerRad": 1.0, "OuterRad": 9e9}
        parent = planet(1, Radius=6e7, Rings=[belt], Parents=[{"Star": 0}])
        moon = planet(2, SemiMajorAxis=1.5e8, Parents=[{"Planet": 1}, {"Star": 0}])
        self.assertNotIn("shepherd_moon", run(moon, {1: parent}))
        inner_ring = {"Name": "P A Ring", "InnerRad": 1e8, "OuterRad": 2e8}
        outer_ring = {"Name": "P B Ring", "InnerRad": 3e8, "OuterRad": 4e8}
        parent = planet(1, Radius=6e7, Rings=[inner_ring, outer_ring], Parents=[{"Star": 0}])
        outside = planet(3, SemiMajorAxis=3.5e8, Parents=[{"Planet": 1}, {"Star": 0}])
        beyond = planet(4, SemiMajorAxis=4.5e8, Parents=[{"Planet": 1}, {"Star": 0}])
        self.assertIn("shepherd_moon", run(outside, {1: parent}))
        self.assertNotIn("shepherd_moon", run(beyond, {1: parent}))

    def test_close_orbit_of_a_planet_or_a_star(self) -> None:
        parent = planet(1, Radius=6e6)
        near = planet(2, SemiMajorAxis=1.0e7, Parents=[{"Planet": 1}])
        far = planet(3, SemiMajorAxis=5.0e7, Parents=[{"Planet": 1}])
        self.assertIn("close_orbit", run(near, {1: parent}))
        self.assertNotIn("close_orbit", run(far, {1: parent}))
        self.assertNotIn("close_orbit", run(near, {}))
        sun = star(0, Radius=7e8)
        hot = planet(4, SemiMajorAxis=1.0e9, Parents=[{"Star": 0}])
        self.assertIn("close_orbit", run(hot, {0: sun}))

    def test_close_binary_needs_both_bodies_close_to_their_centre(self) -> None:
        a = star(0, SemiMajorAxis=1.0e9, Radius=5.0e8, Eccentricity=0.0)
        b = star(1, SemiMajorAxis=1.0e9, Radius=5.0e8, Eccentricity=0.0)
        self.assertIn("close_binary", run(b, {0: a, 1: b}))
        self.assertNotIn("colliding_binary", run(b, {0: a, 1: b}))
        wide = star(1, SemiMajorAxis=4.0e10, Radius=7.0e8)
        self.assertNotIn("close_binary", run(wide, {0: a, 1: wide}))
        self.assertNotIn("close_binary", run(a, {0: a}))  # no partner yet

    def test_colliding_binary_replaces_close_binary(self) -> None:
        a = star(0, SemiMajorAxis=1.0e9, Radius=5.0e8, Eccentricity=0.6)
        b = star(1, SemiMajorAxis=1.0e9, Radius=5.0e8, Eccentricity=0.6)
        found = run(b, {0: a, 1: b})
        self.assertIn("colliding_binary", found)
        self.assertNotIn("close_binary", found)

    def test_binary_needs_exactly_one_partner(self) -> None:
        a, b = star(0, SemiMajorAxis=1e9, Radius=5e8), star(1, SemiMajorAxis=1e9, Radius=5e8)
        c = star(2, SemiMajorAxis=1e9, Radius=5e8)  # a third body on the same barycentre
        self.assertNotIn("close_binary", run(b, {0: a, 1: b, 2: c}))

    def test_malformed_events_never_raise(self) -> None:
        junk = {"BodyID": 1, "Landable": True, "SurfaceGravity": "x", "Radius": None, "Rings": "no",
                "Materials": [None, 3], "Parents": "oops", "SemiMajorAxis": True}
        self.assertEqual(run(junk), [])


class EvaluateTests(unittest.TestCase):
    def test_only_enabled_rules_run(self) -> None:
        scan = planet(Landable=True, TerraformState="Terraformable", SurfaceGravity=3.5 * G)
        self.assertEqual(run(scan, enabled={"high_g"}), ["high_g"])
        self.assertEqual(run(scan, enabled=set()), [])

    def test_defaults_are_the_rare_rules(self) -> None:
        self.assertEqual(
            nr.default_enabled(),
            {"terraformable_landable", "high_value", "high_g", "shepherd_moon", "good_fsd", "green_gas_giant",
             "colliding_binary"},
        )

    def test_labels_fit_the_card_title(self) -> None:
        from plugin import notable  # noqa: PLC0415  (imported lazily: needs the EDMC stand-ins below)
        for rule in nr.RULES:
            self.assertLessEqual(len(rule.label), notable.TITLE_MAX_CHARS, rule.id)


def _load_notable():
    """Import plugin.notable with EDMC's own modules stubbed (it imports config/myNotebook/tkinter)."""
    for name in ("config", "myNotebook", "theme", "monitor", "plug"):
        sys.modules.setdefault(name, mock.MagicMock(name=name))
    sys.modules["config"].appname = "EDMarketConnector"
    from plugin import notable  # noqa: PLC0415
    return notable


class TrackerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.notable = _load_notable()
        self.changes: list = []
        self.tracker = self.notable.NotableTracker(self.changes.append, lambda: nr.default_enabled())
        timer = mock.patch.object(self.notable.threading, "Timer")
        self.timer = timer.start()
        self.addCleanup(timer.stop)

    def snapshot(self):
        return self.tracker.get_snapshot()

    def test_matching_scan_shows_a_card(self) -> None:
        self.tracker.handle_event(planet(5, BodyName="Sys 5 b", Landable=True, SurfaceGravity=35.0))
        snap = self.snapshot()
        self.assertTrue(snap.visible)
        self.assertEqual((snap.title, snap.name), ("High-g landable", "Sys 5 b"))

    def test_repeat_scan_does_not_alert_twice(self) -> None:
        scan = planet(5, Landable=True, SurfaceGravity=35.0)
        self.tracker.handle_event(scan)
        self.tracker.handle_event(scan)
        self.assertEqual(self.snapshot().more, 0)

    def test_two_rules_on_one_body_merge_into_one_card(self) -> None:
        self.tracker.handle_event(planet(5, Landable=True, TerraformState="Terraformable", SurfaceGravity=3.5 * G))
        snap = self.snapshot()
        self.assertEqual(snap.title, "Terraformable landable +2")  # + high-value body and high-g
        self.assertEqual(snap.more, 0)

    def test_moon_scanned_before_its_parent_alerts_when_the_parent_arrives(self) -> None:
        moon = planet(2, BodyName="Sys 1 a", SemiMajorAxis=1.5e8, Parents=[{"Planet": 1}, {"Star": 0}])
        parent = planet(1, Radius=6e7, Rings=[{"Name": "R", "InnerRad": 1.0e8, "OuterRad": 2.0e8}])
        self.tracker.handle_event(moon)
        self.assertFalse(self.snapshot().visible)
        self.tracker.handle_event(parent)
        self.assertEqual((self.snapshot().title, self.snapshot().name), ("Shepherd moon", "Sys 1 a"))

    def test_cards_queue_and_overflow_is_counted(self) -> None:
        for body_id in range(1, 8):
            self.tracker.handle_event(planet(body_id, Landable=True, SurfaceGravity=35.0))
        snap = self.snapshot()
        self.assertEqual(snap.name, "Sys 1")
        self.assertEqual(snap.more, 6)  # 3 queued + 3 counted
        self.tracker._advance()
        self.assertEqual(self.snapshot().name, "Sys 2")

    def test_changing_system_forgets_bodies_and_alerts(self) -> None:
        scan = planet(5, Landable=True, SurfaceGravity=35.0)
        self.tracker.handle_event(scan)
        self.tracker._advance()
        self.assertFalse(self.snapshot().visible)
        self.tracker.handle_event({"event": "FSDJump", "SystemAddress": 99})
        self.tracker.handle_event(dict(scan, SystemAddress=99))
        self.assertTrue(self.snapshot().visible)

    def test_green_gas_giant_codex_alerts_once(self) -> None:
        entry = {"event": "CodexEntry", "Name": "$Codex_Ent_GreenSudarsky_Name;",
                 "NearestDestination_Localised": "Sys 3"}
        self.tracker.handle_event(entry)
        self.assertEqual((self.snapshot().title, self.snapshot().name), ("Green gas giant", "Sys 3"))
        self.tracker._advance()
        self.tracker.handle_event(entry)
        self.assertFalse(self.snapshot().visible)

    def test_nothing_fires_when_no_rules_are_enabled(self) -> None:
        tracker = self.notable.NotableTracker(self.changes.append, lambda: set())
        tracker.handle_event(planet(5, Landable=True, SurfaceGravity=35.0))
        self.assertFalse(tracker.get_snapshot().visible)

    def test_worst_case_text_is_capped(self) -> None:
        long_name = "X" * 200
        self.tracker.handle_event(planet(5, BodyName=long_name, Landable=True, SurfaceGravity=35.0))
        self.assertLessEqual(len(self.snapshot().name), self.notable.NAME_MAX_CHARS)
        self.assertLessEqual(len(self.snapshot().title), self.notable.TITLE_MAX_CHARS)


class ConfigTests(unittest.TestCase):
    def setUp(self) -> None:
        self.notable = _load_notable()

    def test_parse_rules_ignores_junk(self) -> None:
        parse = self.notable.parse_rules
        self.assertEqual(parse(None), {})
        self.assertEqual(parse("not json"), {})
        self.assertEqual(parse("[1]"), {})
        self.assertEqual(parse('{"high_g": false, "nope": true, "good_fsd": "yes"}'), {"high_g": False})

    def test_missing_rule_choice_uses_the_default(self) -> None:
        cfg = self.notable.NotableConfig(rules={"high_g": False, "fast_orbit": True})
        enabled = cfg.enabled_rules()
        self.assertNotIn("high_g", enabled)
        self.assertIn("fast_orbit", enabled)
        self.assertIn("terraformable_landable", enabled)

    def test_cap(self) -> None:
        self.assertEqual(self.notable.cap("short", 10), "short")
        self.assertEqual(len(self.notable.cap("x" * 50, 10)), 10)
        self.assertTrue(self.notable.cap("x" * 50, 10).endswith("…"))


if __name__ == "__main__":
    unittest.main()
