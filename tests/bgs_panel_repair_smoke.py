"""The BGS panel's handling of a period that closes: the closed period is rebuilt from the journals (bgs_panel._roll_period / _backfill_worker /
_apply_repair), over what was filed live. Run by test_bgs_panel_repair.py in a subprocess so the EDMC stand-ins never leak into other tests.
Exits 0 if every check passes, 1 if any fails."""
import os
import queue
import sys
import types
from datetime import datetime, timedelta, timezone
from unittest import mock

repo = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, repo)


class Any(types.ModuleType):
    def __getattr__(self, n):
        if n.startswith("__"):
            raise AttributeError(n)
        return mock.MagicMock()


for n in ("config", "monitor", "plug", "EDMCLogging", "l10n", "killswitch", "requests", "theme", "myNotebook", "ttkHyperlinkLabel"):
    sys.modules[n] = Any(n)
sys.modules["config"].appname = "EDMarketConnector"

from plugin import bgs_ledger, bgs_panel  # noqa: E402

problems = []


def check(ok, what):
    if not ok:
        problems.append(what)


def stamp(moment):
    return moment.strftime("%Y-%m-%dT%H:%M:%SZ")


now = datetime.now(timezone.utc).replace(microsecond=0)
OLD = (now - timedelta(hours=30)).isoformat()
NEW = (now - timedelta(hours=6)).isoformat()


def jump(when):
    return {"timestamp": stamp(when), "event": "FSDJump", "StarSystem": "Sol", "SystemFaction": {"Name": "Alpha Party"},
            "Factions": [{"Name": "Alpha Party", "FactionState": "None", "Influence": 0.4}]}


def mission(when, mission_id):
    return {"timestamp": stamp(when), "event": "MissionCompleted", "MissionID": mission_id,
            "FactionEffects": [{"Faction": "Alpha Party", "Influence": [{"Trend": "UpGood", "Influence": "++"}]}]}


events = [jump(now - timedelta(hours=31)), mission(now - timedelta(hours=28), 1), mission(now - timedelta(hours=20), 2),
          mission(now - timedelta(hours=3), 3)]           # the last is after the tick: the next period's


def controller():
    c = bgs_panel.BgsController()
    c._cmdr = "Bocheaux"
    c._persist = mock.MagicMock()
    c._refresh_display = mock.MagicMock()
    c._set_tick_status = mock.MagicMock()
    return c


# 1. A tick closes a period that held one live mission: the live record is filed at once, and a repair is queued for the journals.
c = controller()
c._ledger = bgs_ledger.TickLedger(OLD)
c._ledger.process(jump(now - timedelta(hours=31)))
c._ledger.process(mission(now - timedelta(hours=28), 1))
c._roll_period(NEW)
check(len(c._archive) == 1 and c._archive[0]["activity"]["sol|alpha party"]["missions"] == 1, f"the live record is filed at once: {c._archive}")
check(c._repair is not None and c._repair[0] == OLD and c._repair[1] == NEW, f"a repair is queued for the closed period: {c._repair}")

# 2. The worker replays the journals; the panel files the rebuilt period over the live one.
with mock.patch.object(bgs_panel.bgs_journal, "read_events", return_value=events) as reader:
    c._backfill_worker(1, "Bocheaux", NEW, {}, c._repair)
check(reader.call_args[0][1] == OLD, f"the journals are read from the closed period's start: {reader.call_args}")
try:
    result = c._backfill_queue.get_nowait()
except queue.Empty:
    result = None
check(result is not None and result[4] is not None, f"the worker hands back a rebuilt record: {result}")
if result is not None:
    c._finish_backfill(*result)
    check(len(c._archive) == 1, f"the rebuilt record replaces the live one, not beside it: {len(c._archive)}")
    check(c._archive[0]["activity"]["sol|alpha party"]["missions"] == 2, f"play made while EDMC was closed is now in it: {c._archive[0]['activity']}")
    check(c._persist.called and c._refresh_display.called, "the change is saved and redrawn")

# 3. Nothing was filed live (EDMC was closed for the whole period): the rebuilt record is added.
c2 = controller()
c2._ledger = bgs_ledger.TickLedger(OLD)
c2._roll_period(NEW)
check(c2._archive == [] and c2._repair is not None, "an empty period files nothing live but still queues a repair")
with mock.patch.object(bgs_panel.bgs_journal, "read_events", return_value=events):
    c2._backfill_worker(1, "Bocheaux", NEW, {}, c2._repair)
c2._finish_backfill(*c2._backfill_queue.get_nowait())
check(len(c2._archive) == 1 and c2._archive[0]["tick_end"] == NEW, f"the rebuilt period is added: {c2._archive}")

# 4. Another commander took over before the result came back: the record is not filed under the wrong commander.
c3 = controller()
c3._ledger = bgs_ledger.TickLedger(OLD)
c3._roll_period(NEW)
with mock.patch.object(bgs_panel.bgs_journal, "read_events", return_value=events):
    c3._backfill_worker(1, "Bocheaux", NEW, {}, c3._repair)
c3._cmdr = "Mactavious"
c3._finish_backfill(*c3._backfill_queue.get_nowait())
check(c3._archive == [], f"a different commander's archive is left alone: {c3._archive}")

# 5. No journals (nothing to replay): the live record stays as filed.
c4 = controller()
c4._ledger = bgs_ledger.TickLedger(OLD)
c4._ledger.process(jump(now - timedelta(hours=31)))
c4._ledger.process(mission(now - timedelta(hours=28), 1))
c4._roll_period(NEW)
with mock.patch.object(bgs_panel.bgs_journal, "read_events", return_value=[]):
    c4._backfill_worker(1, "Bocheaux", NEW, {}, c4._repair)
c4._finish_backfill(*c4._backfill_queue.get_nowait())
check(len(c4._archive) == 1 and c4._archive[0]["activity"]["sol|alpha party"]["missions"] == 1, "with no journals the live record stays")

if problems:
    print("PROBLEMS:", len(problems))
    for p in problems:
        print(" -", p)
    sys.exit(1)
print("BGS REPAIR OK")
