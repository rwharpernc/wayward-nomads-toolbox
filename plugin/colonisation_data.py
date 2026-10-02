"""Per-commander persistence for colonisation construction sites - a JSON
file next to the plugin (not committed, not in any release build; listed in
update.py's `_OWN_DATA_FILES`), keyed by commander name (case-preserved,
matched case-insensitively) like ship_builds_data.py. Within a commander,
sites are keyed by the depot's MarketID.

The depot events themselves arrive far more often than anything changes
(every dock at a depot), so `upsert` only saves + notifies when the
serialised site actually differs.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Callable, Dict, List, Optional

from config import appname

from .colonisation import Site

plugin_name = os.path.basename(os.path.dirname(__file__))
logger = logging.getLogger(f"{appname}.{plugin_name}")

SITES_FILENAME = "colonisation_sites.json"


class SiteRepository:
    """Constructed empty (no file access at import time); `load(plugin_dir)`
    is called once from colonisation_panel.start()."""

    def __init__(self) -> None:
        self._by_cmdr: Dict[str, Dict[int, Site]] = {}
        self._listeners: List[Callable[[], None]] = []
        self._plugin_dir: Optional[str] = None

    def load(self, plugin_dir: str) -> None:
        self._plugin_dir = plugin_dir
        path = os.path.join(plugin_dir, SITES_FILENAME)
        if not os.path.exists(path):
            return
        try:
            with open(path, "r", encoding="utf8") as fh:
                raw = json.load(fh)
            self._by_cmdr = {}
            for cmdr, sites in raw.items():
                parsed = [Site.from_dict(entry) for entry in sites]
                self._by_cmdr[cmdr] = {s.market_id: s for s in parsed if s.market_id}
        except Exception:
            logger.exception("Failed to load %s - starting with no tracked sites", SITES_FILENAME)
            self._by_cmdr = {}

    def add_listener(self, callback: Callable[[], None]) -> None:
        self._listeners.append(callback)

    def _save_and_notify(self) -> None:
        if self._plugin_dir is not None:
            path = os.path.join(self._plugin_dir, SITES_FILENAME)
            tmp_path = f"{path}.tmp"
            try:
                raw = {cmdr: [s.to_dict() for s in sites.values()] for cmdr, sites in self._by_cmdr.items()}
                with open(tmp_path, "w", encoding="utf8") as fh:
                    json.dump(raw, fh, indent=2, sort_keys=True)
                os.replace(tmp_path, path)
            except OSError:
                logger.exception("Failed to write %s", SITES_FILENAME)
        for listener in self._listeners:
            listener()

    def _cmdr_key(self, cmdr: str) -> Optional[str]:
        target = cmdr.strip().casefold()
        for key in self._by_cmdr:
            if key.strip().casefold() == target:
                return key
        return None

    def for_cmdr(self, cmdr: str) -> List[Site]:
        """Newest-updated first."""
        key = self._cmdr_key(cmdr) if cmdr else None
        sites = list(self._by_cmdr.get(key, {}).values()) if key else []
        return sorted(sites, key=lambda s: s.updated, reverse=True)

    def get(self, cmdr: str, market_id: int) -> Optional[Site]:
        key = self._cmdr_key(cmdr) if cmdr else None
        return self._by_cmdr.get(key, {}).get(market_id) if key else None

    def upsert(self, cmdr: str, site: Site) -> None:
        if not cmdr:
            return
        key = self._cmdr_key(cmdr) or cmdr
        bucket = self._by_cmdr.setdefault(key, {})
        previous = bucket.get(site.market_id)
        if previous is not None and previous is not site:
            # `updated` is always fresh on a refresh; ignore it so an
            # unchanged re-dock doesn't rewrite the file.
            old, new = previous.to_dict(), site.to_dict()
            old.pop("updated"), new.pop("updated")
            if old == new:
                return
        bucket[site.market_id] = site
        self._save_and_notify()

    def remove(self, cmdr: str, market_id: int) -> None:
        key = self._cmdr_key(cmdr) if cmdr else None
        if key is None or market_id not in self._by_cmdr.get(key, {}):
            return
        del self._by_cmdr[key][market_id]
        self._save_and_notify()


site_repository = SiteRepository()
