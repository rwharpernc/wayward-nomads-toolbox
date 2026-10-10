"""
Finding and reading the game's journal files, for the features that catch up from them when EDMC starts.

EDMC only hands plugins the events that happen while it runs, so anything played with EDMC closed has to be read back
from the journal folder. This is the shared part: where the folder is, which files changed since a moment, and a
reader that parses only the lines a feature asked for (a cheap regular-expression test first, so a large journal costs
little). Each feature decides what the events mean and how to avoid counting one twice.

Files are returned oldest first by modified time, not by name: the game has used two naming styles that do not sort
chronologically together. A missing folder, an unreadable file or a malformed line never raises.
"""
from __future__ import annotations

import json
import logging
import os
import re
from typing import Any, Dict, Iterator, List, Optional

try:
    from config import appname, config
except ImportError:  # unit tests outside EDMC
    appname, config = "EDMarketConnector", None

plugin_name = os.path.basename(os.path.dirname(__file__))
logger = logging.getLogger(f"{appname}.{plugin_name}")


def journal_folder() -> str:
    """EDMC's journal directory setting, else its default (empty on Linux until the setting is made)."""
    if config is None:
        return ""
    getter = getattr(config, "get_str", None) or getattr(config, "get", None)
    configured = getter("journaldir") if getter else ""
    return configured or getattr(config, "default_journal_dir", "") or ""


def event_pattern(*names: str) -> "re.Pattern[str]":
    """A cheap line test for the named journal events."""
    return re.compile(r'"event"\s*:\s*"(?:' + "|".join(re.escape(n) for n in names) + r')"')


def files_modified_since(since_epoch: float, folder: Optional[str] = None) -> List[str]:
    """Journal files modified at or after `since_epoch`, oldest first."""
    folder = journal_folder() if folder is None else folder
    if not folder:
        return []
    found = []
    try:
        with os.scandir(folder) as entries:
            for entry in entries:
                if entry.name.startswith("Journal.") and entry.name.endswith(".log") and entry.is_file():
                    modified = entry.stat().st_mtime
                    if modified >= since_epoch:
                        found.append((modified, entry.path))
    except OSError:
        logger.warning("Could not list the journal folder %s", folder)
        return []
    found.sort()
    return [path for _modified, path in found]


def read_events(path: str, wanted: "re.Pattern[str]") -> Iterator[Dict[str, Any]]:
    """The parsed events in `path` whose line matches `wanted`, in file order."""
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as handle:
            for line in handle:
                if not wanted.search(line):
                    continue
                try:
                    entry = json.loads(line)
                except ValueError:
                    continue
                if isinstance(entry, dict):
                    yield entry
    except OSError:
        logger.warning("Could not read journal %s", path)
