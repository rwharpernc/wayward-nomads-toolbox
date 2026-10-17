"""
Unit tests for plugin/mining_share.py.

Pure logic - no EDMC runtime needed (EDMC's `config` module is stubbed). Run with:
    python -m unittest discover -s tests
"""

from __future__ import annotations

import base64
import json
import os
import sys
import types
import unittest
import zlib

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.modules.setdefault("config", types.SimpleNamespace(appname="EDMarketConnector"))

from plugin import mining_hotspots as hotspots  # noqa: E402
from plugin import mining_share as share  # noqa: E402

RADIUS_M = 1_000_000.0
M_PER_DEG = RADIUS_M * 3.141592653589793 / 180.0


def _spot(north_m: float = 0.0, **kwargs) -> hotspots.Hotspot:
    fields = dict(system="Sol", body="Mars 1", material="Monazite", latitude=north_m / M_PER_DEG, longitude=10.0)
    fields.update(kwargs)
    return hotspots.Hotspot(**fields)


def _line(data: dict) -> str:
    code = base64.urlsafe_b64encode(json.dumps(data).encode()).decode().rstrip("=")
    return f"{share.PREFIX}:{code}:{zlib.crc32(code.encode()):08x}"


GOOD = {"s": "Sol", "b": "Mars 1", "m": "Monazite", "la": 1.5, "lo": 2.5}


class RoundTripTests(unittest.TestCase):
    def test_what_is_shared_comes_back(self) -> None:
        spot = _spot(rigs=4, signal_number=3, amount="High", density="Low", ground="icy")
        got = share.decode(share.encode(spot, 1_200_000.0))
        self.assertEqual((got.hotspot.system, got.hotspot.body, got.hotspot.material), ("Sol", "Mars 1", "Monazite"))
        self.assertEqual((got.hotspot.rigs, got.hotspot.signal_number, got.hotspot.amount, got.hotspot.density, got.hotspot.ground),
                         (4, 3, "High", "Low", "icy"))
        self.assertAlmostEqual(got.hotspot.longitude, 10.0)
        self.assertEqual(got.radius_m, 1_200_000.0)

    def test_nothing_personal_is_in_the_line(self) -> None:
        spot = _spot(notes="my secret base", folder="Private", mined_tons=500, depleted_at="2026-10-01T00:00:00Z", rechecks=["x"])
        line = share.encode(spot)
        decoded = base64.urlsafe_b64decode(line.split(":")[1] + "==").decode()
        for private in ("secret", "Private", "500", "2026", "notes", "tons"):
            self.assertNotIn(private, decoded)
        got = share.decode(line).hotspot
        self.assertEqual((got.notes, got.folder, got.mined_tons, got.depleted_at, got.rechecks), ("", "", None, None, []))

    def test_a_spot_with_no_position_cannot_be_shared(self) -> None:
        with self.assertRaises(share.ShareError):
            share.encode(hotspots.Hotspot(system="Sol", body="Mars 1", material="X"))

    def test_chat_decoration_is_ignored(self) -> None:
        line = share.encode(_spot())
        for wrapped in (f"  {line}\n", f"`{line}`", f'"{line}"', f"<{line}>"):
            self.assertEqual(share.decode(wrapped).hotspot.material, "Monazite")


class RefusalTests(unittest.TestCase):
    def refused(self, text: str) -> str:
        with self.assertRaises(share.ShareError) as caught:
            share.decode(text)
        return str(caught.exception)

    def test_not_a_spot(self) -> None:
        self.assertIn("not a shared", self.refused("hello"))
        self.assertIn("nothing", self.refused("   "))
        self.assertIn("not a shared", self.refused("WNTB-SPOT2:abc:00000000"))

    def test_cut_short_or_changed_lines(self) -> None:
        line = share.encode(_spot())
        self.assertIn("damaged", self.refused(line[:-12]))
        head, code, check = line.split(":")
        flipped = code[:5] + ("A" if code[5] != "A" else "B") + code[6:]
        self.assertIn("damaged", self.refused(f"{head}:{flipped}:{check}"))

    def test_too_long(self) -> None:
        self.assertIn("too long", self.refused("x" * 700))

    def test_values_out_of_range_are_refused(self) -> None:
        for change in ({"la": 91}, {"lo": -181}, {"r": 9}, {"r": 0}, {"r": 2.5}, {"r": True}, {"a": "Huge"}, {"d": "Dense"}, {"n": -1},
                       {"R": 5}, {"s": ""}, {"b": "x" * 200}, {"m": 5}, {"m": "bad\x07name"}):
            self.assertIn("line", self.refused(_line({**GOOD, **change})), change)

    def test_missing_required_parts(self) -> None:
        for key in ("s", "b", "m"):
            data = {k: v for k, v in GOOD.items() if k != key}
            self.assertIn("line", self.refused(_line(data)))
        self.assertIn("position", self.refused(_line({k: v for k, v in GOOD.items() if k not in ("la", "lo")})))

    def test_not_an_object(self) -> None:
        code = base64.urlsafe_b64encode(b"[1,2]").decode().rstrip("=")
        self.assertIn("damaged", self.refused(f"{share.PREFIX}:{code}:{zlib.crc32(code.encode()):08x}"))


class DuplicateTests(unittest.TestCase):
    def test_close_on_the_same_body_is_a_duplicate(self) -> None:
        mine = _spot(0)
        incoming = share.Shared(_spot(60), RADIUS_M)
        self.assertIs(share.find_duplicate(incoming, [mine]), mine)

    def test_far_or_other_body_is_not(self) -> None:
        incoming = share.Shared(_spot(500), RADIUS_M)
        self.assertIsNone(share.find_duplicate(incoming, [_spot(0)]))
        self.assertIsNone(share.find_duplicate(share.Shared(_spot(10), RADIUS_M), [_spot(0, body="Mars 2")]))

    def test_the_receivers_own_radius_wins(self) -> None:
        incoming = share.Shared(_spot(60), RADIUS_M)
        self.assertIsNone(share.find_duplicate(incoming, [_spot(0)], known_radius_m=RADIUS_M * 10))

    def test_unpositioned_saved_spots_are_ignored(self) -> None:
        self.assertIsNone(share.find_duplicate(share.Shared(_spot(0), None), [hotspots.Hotspot(system="Sol", body="Mars 1", material="X")]))


if __name__ == "__main__":
    unittest.main()
