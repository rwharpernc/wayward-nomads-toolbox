"""Per-commander catalog of ship-build *links* - not a build tool itself.

WNTB doesn't build loadouts (EDMC already has a
built-in "Shipyard provider" setting - Coriolis/EDSY - that opens your
*current* ship's live loadout on whichever site you've configured). This
module is for the builds a commander designs and saves on one of those
sites independently, possibly long before or after actually flying that
ship - a bookmark catalog with enough metadata (ship, role, site, notes)
to find the right one again, kept separate per commander since two
commanders on the same install fly very different fleets.

Same JSON-file-next-to-the-plugin persistence and Repository shape as
mining_hotspots.py, but keyed by commander name (case-preserved for
display, matched case-insensitively) rather than a single flat list -
`ShipBuildRepository.for_cmdr()` is the per-commander view every caller
actually wants.
"""

from __future__ import annotations

import json
import logging
import os
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Callable, Dict, List, Optional

from config import appname

plugin_name = os.path.basename(os.path.dirname(__file__))
logger = logging.getLogger(f"{appname}.{plugin_name}")

BUILDS_FILENAME = "ship_builds.json"
"""Not committed to git and not part of any release build - the
commander's own data, same convention as mining_hotspots.py's own
HOTSPOTS_FILENAME."""

# The two shipyard-provider sites EDMC's own "Shipyard provider" Settings
# option supports (confirmed against EDMarketConnector's own ChangeLog -
# "coriolis.io or edsy.org"), plus Spansh (spansh.co.uk/shipyard, already
# used elsewhere in WNTB for mining/system lookups) and a free-text
# "Other" for anything else - not an exhaustive enum, just quick picks for
# the dialog's dropdown; `site` is still a plain string underneath.
KNOWN_SITES = ("Coriolis", "EDSY (E:D Shipyard)", "Spansh", "Other")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass
class ShipBuild:
    """One saved build link. `id` is a stable identifier (not the list
    index, which shifts on delete) so the management window and dialog
    can refer to a build safely across a refresh. `ship` is free text
    (best-effort prefilled from the journal's own Loadout event, see
    ship_builds_panel.py) rather than a fixed enum - new ships ship
    faster than any hard-coded list here would be kept in sync."""
    id: str
    ship: str
    name: str
    site: str
    url: str
    role: str = ""
    notes: str = ""
    created: str = field(default_factory=_now_iso)
    updated: str = field(default_factory=_now_iso)

    def touch(self) -> None:
        self.updated = _now_iso()


def new_id() -> str:
    return uuid.uuid4().hex[:12]


class ShipBuildRepository:
    """Constructed empty (no file access at import time, matching WNTB's
    own convention) - `load(plugin_dir)` is called once from
    ship_builds_panel.start()."""

    def __init__(self) -> None:
        self._by_cmdr: Dict[str, List[ShipBuild]] = {}
        self._listeners: List[Callable[[], None]] = []
        self._plugin_dir: Optional[str] = None

    def load(self, plugin_dir: str) -> None:
        self._plugin_dir = plugin_dir
        path = os.path.join(plugin_dir, BUILDS_FILENAME)
        if not os.path.exists(path):
            return
        try:
            with open(path, "r", encoding="utf8") as fh:
                raw = json.load(fh)
            self._by_cmdr = {
                cmdr: [ShipBuild(**entry) for entry in entries]
                for cmdr, entries in raw.items()
            }
        except Exception:
            logger.exception("Failed to load %s - starting with an empty catalog", BUILDS_FILENAME)
            self._by_cmdr = {}

    def add_listener(self, callback: Callable[[], None]) -> None:
        self._listeners.append(callback)

    def _save_and_notify(self) -> None:
        if self._plugin_dir is not None:
            path = os.path.join(self._plugin_dir, BUILDS_FILENAME)
            tmp_path = f"{path}.tmp"
            try:
                raw = {cmdr: [asdict(b) for b in builds] for cmdr, builds in self._by_cmdr.items()}
                with open(tmp_path, "w", encoding="utf8") as fh:
                    json.dump(raw, fh, indent=2, sort_keys=True)
                os.replace(tmp_path, path)
            except OSError:
                logger.exception("Failed to write %s", BUILDS_FILENAME)
        for listener in self._listeners:
            listener()

    def _cmdr_key(self, cmdr: str) -> Optional[str]:
        """Matches an existing bucket case-insensitively, returning its
        real stored key - so "cmdr Bocheaux" and "Cmdr Bocheaux" (EDMC has
        been known to vary case across a Beta vs. live journal) share one
        catalog instead of silently splitting into two."""
        target = cmdr.strip().casefold()
        for key in self._by_cmdr:
            if key.strip().casefold() == target:
                return key
        return None

    def for_cmdr(self, cmdr: str) -> List[ShipBuild]:
        if not cmdr:
            return []
        key = self._cmdr_key(cmdr)
        return list(self._by_cmdr.get(key, [])) if key else []

    def add(self, cmdr: str, build: ShipBuild) -> None:
        key = self._cmdr_key(cmdr) or cmdr
        self._by_cmdr.setdefault(key, []).append(build)
        self._save_and_notify()

    def update(self, cmdr: str, build: ShipBuild) -> None:
        key = self._cmdr_key(cmdr)
        if key is None:
            self.add(cmdr, build)
            return
        builds = self._by_cmdr[key]
        for i, existing in enumerate(builds):
            if existing.id == build.id:
                build.touch()
                builds[i] = build
                break
        self._save_and_notify()

    def remove(self, cmdr: str, build_id: str) -> None:
        key = self._cmdr_key(cmdr)
        if key is None:
            return
        self._by_cmdr[key] = [b for b in self._by_cmdr[key] if b.id != build_id]
        self._save_and_notify()


ship_build_repository = ShipBuildRepository()
