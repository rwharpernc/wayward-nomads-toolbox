"""
What a commander has delivered to colonization construction sites, kept for the Colonization mode's history figures.

The sites file (colonisation_data.py) holds each site's *current* needs, which count everyone's deliveries and forget how
they got there. This keeps the commander's own: every `ColonisationContribution` they made, summed by commodity, by site
and by day. One small per-commander JSON file (`colonisation_history.json` beside the plugin, commander_data.py).

A delivery is an addition, so counting one twice would be wrong. Each commander's record keeps `journal_at`, the time of
the newest contribution folded in, and one is applied only if it is newer, which makes the start-up catch-up from the
journals (colonisation_catchup.py) safe next to the live events. The catch-up reads at most 30 days back, so deliveries
made before this file existed and more than that long ago are not in it; the figures say "since" the first one counted.
`rebuild` fills that gap once per commander from the whole journal history (colonisation_catchup.read_all_contributions).
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Dict, Iterable, List, Optional

from . import colonisation, commander_data

try:
    from config import appname
except ImportError:  # unit tests outside EDMC
    appname = "EDMarketConnector"

plugin_name = os.path.basename(os.path.dirname(__file__))
logger = logging.getLogger(f"{appname}.{plugin_name}")

STATE_FILENAME = "colonisation_history.json"
DAYS_KEPT = 400   # by_day entries older than this are dropped (the totals keep them)

Record = Dict[str, Any]


def _empty() -> Record:
    return {"journal_at": "", "first": "", "last": "", "deliveries": 0, "tonnes": 0,
            "by_commodity": {}, "by_site": {}, "by_day": {}}


def _is_legacy(_raw: Any) -> bool:
    return False   # the file is new; nothing older to claim


class DeliveryLedger:
    """Per-commander totals of what was delivered to construction sites. Constructed empty; `load(plugin_dir)` is called
    from the colonization panel's start."""

    def __init__(self) -> None:
        self._store = commander_data.new_store()
        self._plugin_dir: Optional[str] = None
        self._listeners: List[Callable[[], None]] = []

    def load(self, plugin_dir: str) -> None:
        self._plugin_dir = plugin_dir
        self._store = commander_data.read(os.path.join(plugin_dir, STATE_FILENAME), _is_legacy)

    def add_listener(self, callback: Callable[[], None]) -> None:
        self._listeners.append(callback)

    def commit(self) -> None:
        if self._plugin_dir is not None:
            commander_data.write(os.path.join(self._plugin_dir, STATE_FILENAME), self._store)
        for listener in self._listeners:
            listener()

    def record(self, cmdr: str) -> Record:
        """A copy-safe view of this commander's totals (an empty record for a commander with none)."""
        if not cmdr or not commander_data.known(self._store, cmdr):
            return _empty()
        return commander_data.payload_for(self._store, cmdr, _empty)

    def watermark(self, cmdr: str) -> Optional[datetime]:
        if not cmdr or not commander_data.known(self._store, cmdr):
            return None
        return colonisation._parse_time(self.record(cmdr).get("journal_at"))   # noqa: SLF001 - same package

    def apply_contribution(self, cmdr: str, entry: Dict[str, Any]) -> bool:
        """Fold a `ColonisationContribution` in. True if anything changed (the caller then `commit`s)."""
        if not commander_data.key_for(cmdr):
            return False
        return _fold(commander_data.payload_for(self._store, cmdr, _empty), entry)

    def backfilled(self, cmdr: str) -> bool:
        """Whether this commander's record has already been rebuilt from the whole journal history."""
        return bool(cmdr and commander_data.known(self._store, cmdr) and self.record(cmdr).get("backfilled"))

    def rebuild(self, cmdr: str, entries: Iterable[Dict[str, Any]], newer: Iterable[Dict[str, Any]] = ()) -> bool:
        """Rebuild the commander's record from every `ColonisationContribution` they have in the journals (`entries`, in
        any order), so deliveries from before this file existed are counted. `newer` are live events that arrived while the
        journals were being read; the newest-only rule skips any the journals already held.

        The rebuilt figures replace the saved ones only if they are at least as large: a commander who has since deleted old
        journals keeps what was counted live. Either way the record is marked as backfilled so it is done once. Returns True if
        the saved figures were replaced (the caller then `commit`s, as it must after any call)."""
        if not commander_data.key_for(cmdr):
            return False
        fresh = _empty()
        for entry in sorted(entries, key=lambda e: str(e.get("timestamp") or "")):
            _fold(fresh, entry)
        for entry in sorted(newer, key=lambda e: str(e.get("timestamp") or "")):
            _fold(fresh, entry)
        current = commander_data.payload_for(self._store, cmdr, _empty)
        replace = fresh["tonnes"] >= current["tonnes"] and fresh["deliveries"] >= current["deliveries"]
        if replace:
            commander_data.put(self._store, cmdr, fresh)
            current = fresh
        current["backfilled"] = True
        return replace


def _fold(record: Record, entry: Dict[str, Any]) -> bool:
    """Add one `ColonisationContribution` to `record`, unless it is not newer than the last one counted. True if it changed."""
    stamp = str(entry.get("timestamp") or "")
    if stamp and record.get("journal_at") and stamp <= record["journal_at"]:
        return False   # already counted (a journal read twice, or caught up after the live event)
    total = 0
    for raw in entry.get("Contributions") or []:
        if not isinstance(raw, dict):
            continue
        key = colonisation.commodity_key(raw.get("Name"))
        amount = colonisation._as_int(raw.get("Amount"))   # noqa: SLF001 - same package
        if not key or not amount:
            continue
        total += amount
        slot = record["by_commodity"].setdefault(key, {"label": "", "tonnes": 0})
        slot["tonnes"] += amount
        slot["label"] = str(raw.get("Name_Localised") or slot["label"] or key.replace("_", " ").title())
    if total <= 0:
        if stamp:
            record["journal_at"] = stamp
            return True
        return False
    when = colonisation.event_time(entry) or datetime.now(timezone.utc)
    iso, day = when.isoformat(timespec="seconds"), when.date().isoformat()
    record["deliveries"] += 1
    record["tonnes"] += total
    record["first"] = record["first"] or iso
    record["last"] = max(record["last"], iso)
    market_id = entry.get("MarketID")
    if isinstance(market_id, int):
        record["by_site"][str(market_id)] = record["by_site"].get(str(market_id), 0) + total
    record["by_day"][day] = record["by_day"].get(day, 0) + total
    cutoff = (when - timedelta(days=DAYS_KEPT)).date().isoformat()
    for old in [d for d in record["by_day"] if d < cutoff]:
        del record["by_day"][old]
    if stamp:
        record["journal_at"] = stamp
    return True
