"""
Unit tests for plugin/mining_depletion.py and the repository's use of it.

Pure logic - no EDMC runtime needed (EDMC's `config` module is stubbed). Run with:
    python -m unittest discover -s tests
"""

from __future__ import annotations

import dataclasses
import os
import sys
import types
import unittest
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.modules.setdefault("config", types.SimpleNamespace(appname="EDMarketConnector"))

from plugin import mining_depletion as depletion  # noqa: E402
from plugin import mining_hotspots as hotspots  # noqa: E402

START = datetime(2026, 10, 1, 12, 0, tzinfo=timezone.utc)


def _day(n: float) -> datetime:
    return START + timedelta(days=n)


def _spot(**kwargs) -> hotspots.Hotspot:
    fields = dict(system="Sol", body="Mars 1", material="Monazite", rigs=4, amount="High")
    fields.update(kwargs)
    return hotspots.Hotspot(**fields)


def _depleted(at: float = 0, **kwargs) -> hotspots.Hotspot:
    return depletion.apply(_spot(), _spot(amount="Depleted", **kwargs), _day(at))


class MarkingTests(unittest.TestCase):
    def test_marking_depleted_dates_it(self) -> None:
        spot = _depleted()
        self.assertEqual(spot.depleted_at, depletion.stamp(START))
        self.assertEqual(spot.rechecks, [])

    def test_a_new_depleted_hotspot_is_dated(self) -> None:
        self.assertIsNotNone(depletion.apply(None, _spot(amount="Depleted"), START).depleted_at)

    def test_editing_other_fields_keeps_the_bookkeeping(self) -> None:
        spot = _depleted()
        edited = depletion.apply(spot, _spot(amount="Depleted", notes="loc 3"), _day(3))
        self.assertEqual(edited.depleted_at, spot.depleted_at)

    def test_setting_it_active_clears_the_cycle(self) -> None:
        spot = depletion.apply(_depleted(), _spot(amount="High"), _day(2))
        self.assertIsNone(spot.depleted_at)
        self.assertEqual(spot.rechecks, [])

    def test_the_dialog_cannot_drop_the_bookkeeping(self) -> None:
        # The edit dialog builds a Hotspot without the bookkeeping fields.
        spot = _depleted()
        rebuilt = hotspots.Hotspot(system="Sol", body="Mars 1", material="Monazite", rigs=4, amount="Depleted")
        self.assertEqual(depletion.apply(spot, rebuilt, _day(1)).depleted_at, spot.depleted_at)


class RegrowthTests(unittest.TestCase):
    def test_not_due_before_14_days(self) -> None:
        spot = _depleted()
        self.assertIs(depletion.settle(spot, _day(13.9), 14), spot)

    def test_taken_off_at_14_days(self) -> None:
        spot = depletion.settle(_depleted(mined_tons=40), _day(14), 14)
        self.assertIsNone(spot.amount)
        self.assertEqual(spot.regrown_at, depletion.stamp(_day(14)))
        self.assertEqual(spot.tons_at_regrow, 40)

    def test_a_legacy_mark_is_dated_not_removed(self) -> None:
        legacy = _spot(amount="Depleted")
        settled = depletion.settle(legacy, _day(100), 14)
        self.assertEqual(settled.amount, "Depleted")
        self.assertEqual(settled.depleted_at, depletion.stamp(_day(100)))

    def test_a_damaged_stamp_does_not_raise(self) -> None:
        spot = _spot(amount="Depleted", depleted_at="garbage")
        self.assertEqual(depletion.settle(spot, _day(1), 14).depleted_at, depletion.stamp(_day(1)))

    def test_other_hotspots_are_untouched(self) -> None:
        spot = _spot()
        self.assertIs(depletion.settle(spot, _day(99), 14), spot)


class UnknownRefillTests(unittest.TestCase):
    """The default: nobody knows when a deposit refills, so a mark stays."""

    def test_a_mark_is_never_taken_off(self) -> None:
        spot = _depleted()
        self.assertIs(depletion.settle(spot, _day(400)), spot)
        self.assertIsNone(depletion.due_at(spot, 0))

    def test_a_legacy_mark_is_still_dated(self) -> None:
        self.assertEqual(depletion.settle(_spot(amount="Depleted"), _day(5)).depleted_at, depletion.stamp(_day(5)))

    def test_the_text_says_it_is_unknown(self) -> None:
        text = depletion.status_text(_depleted(), _day(20))
        self.assertIn("Depleted 20 d ago", text)
        self.assertIn("unknown", text)

    def test_the_repository_follows_its_setting(self) -> None:
        repo = hotspots.HotspotRepository()
        repo._hotspots = [dataclasses.replace(_depleted(), depleted_at=depletion.stamp(START))]
        self.assertFalse(repo.settle_depletion(notify=False))      # unknown: nothing to do
        repo.refill_days = 14
        self.assertTrue(repo.settle_depletion(notify=False))       # 14 days and START is long past
        self.assertIsNone(repo.all()[0].amount)


class RecheckTests(unittest.TestCase):
    def _regrown(self, tons: int = 0) -> hotspots.Hotspot:
        return depletion.settle(_depleted(mined_tons=tons or None), _day(14), 14)

    def test_pressing_again_with_no_tons_is_a_recheck(self) -> None:
        again = depletion.apply(self._regrown(), dataclasses.replace(self._regrown(), amount="Depleted"), _day(15))
        self.assertEqual(again.depleted_at, depletion.stamp(START))     # first date kept
        self.assertEqual(again.rechecks, [depletion.stamp(_day(15))])
        self.assertIsNone(again.regrown_at)

    def test_the_mark_comes_off_7_days_after_the_look(self) -> None:
        regrown = self._regrown()
        again = depletion.apply(regrown, dataclasses.replace(regrown, amount="Depleted"), _day(15))
        self.assertIs(depletion.settle(again, _day(21.9), 14), again)
        self.assertIsNone(depletion.settle(again, _day(22), 14).amount)

    def test_tons_since_regrowth_make_it_a_new_depletion(self) -> None:
        regrown = self._regrown(tons=40)
        mined = dataclasses.replace(regrown, mined_tons=65)
        fresh = depletion.apply(mined, dataclasses.replace(mined, amount="Depleted"), _day(16))
        self.assertEqual(fresh.depleted_at, depletion.stamp(_day(16)))
        self.assertEqual(fresh.rechecks, [])

    def test_a_fresh_amount_reading_ends_the_cycle(self) -> None:
        regrown = self._regrown()
        read = depletion.apply(regrown, dataclasses.replace(regrown, amount="Medium"), _day(15))
        self.assertIsNone(read.regrown_at)
        self.assertIsNone(read.tons_at_regrow)


class StatusTextTests(unittest.TestCase):
    def test_waiting(self) -> None:
        self.assertIn("refill in 11 d", depletion.status_text(_depleted(), _day(3), 14))

    def test_after_a_look(self) -> None:
        regrown = depletion.settle(_depleted(), _day(14), 14)
        again = depletion.apply(regrown, dataclasses.replace(regrown, amount="Depleted"), _day(15))
        self.assertEqual(depletion.status_text(again, _day(15), 14), "Still depleted at 15 d; look again in 7 d")

    def test_regrown(self) -> None:
        self.assertIn("Assumed refilled", depletion.status_text(depletion.settle(_depleted(), _day(14), 14), _day(14), 14))

    def test_ordinary_hotspot_has_none(self) -> None:
        self.assertEqual(depletion.status_text(_spot(), START, 14), "")


class RepositoryTests(unittest.TestCase):
    def test_update_to_depleted_is_dated(self) -> None:
        repo = hotspots.HotspotRepository()
        repo.add(_spot())
        repo.update(0, _spot(amount="Depleted"))
        self.assertIsNotNone(repo.all()[0].depleted_at)

    def test_old_files_without_the_fields_still_load(self) -> None:
        raw = {"system": "Sol", "body": "Mars 1", "material": "Monazite", "amount": "Depleted"}
        spot = hotspots.Hotspot(**raw)
        self.assertEqual(spot.rechecks, [])
        self.assertIsNone(spot.depleted_at)

    def test_settle_depletion_reports_a_change_once(self) -> None:
        repo = hotspots.HotspotRepository()
        repo._hotspots = [_spot(amount="Depleted")]   # a mark from before dates were kept
        self.assertTrue(repo.settle_depletion(notify=False))
        self.assertFalse(repo.settle_depletion(notify=False))


if __name__ == "__main__":
    unittest.main()
