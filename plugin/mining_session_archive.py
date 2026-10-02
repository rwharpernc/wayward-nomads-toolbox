"""
Optional per-run JSON archive, written when a completed run has data,
for post-session analysis outside the plugin itself. Opt-in via the
"Archive Completed Mining Runs" setting (default off) - see
mining_panel.py.

Called from mining_panel.py at each page's natural run-end event
(`Docked` for Space Mining, `DockSRV` for Surface Mining), only when the
ending run actually has data (SpaceMiningRun.has_data() /
SurfaceMiningRun.has_data()) - undocking and redocking without mining
shouldn't produce an empty file.
"""
import json
import logging
import os
from dataclasses import asdict
from datetime import datetime, timezone
from typing import Any

from config import appname

plugin_name = os.path.basename(os.path.dirname(__file__))
logger = logging.getLogger(f"{appname}.{plugin_name}")

ARCHIVE_DIRNAME = "mining_sessions"
"""Named `mining_sessions` to avoid any ambiguity
against store.py's own `sessions.json` (a different file, same plugin
directory)."""


def _safe_filename_part(text: str) -> str:
    return "".join(char if char.isalnum() else "_" for char in text) or "unknown"


def archive_run(plugin_dir: str, page: str, cmdr: str, run: Any) -> None:
    """Writes one completed run's data as a JSON file under
    <plugin_dir>/mining_sessions/, named `<page>-<cmdr>-<UTC
    timestamp>.json`. `page` is "space" or "surface". Never raises - a
    failed write shouldn't interrupt the plugin's live tracking, so any
    error is logged and swallowed."""
    try:
        archive_dir = os.path.join(plugin_dir, ARCHIVE_DIRNAME)
        os.makedirs(archive_dir, exist_ok=True)
        data = {key: value for key, value in asdict(run).items()
                if not key.startswith("_")}
        data["page"] = page
        data["cmdr"] = cmdr
        now = datetime.now(timezone.utc)
        data["archived_at"] = now.isoformat()
        timestamp = now.strftime("%Y%m%dT%H%M%SZ")
        path = os.path.join(archive_dir, f"{page}-{_safe_filename_part(cmdr)}-{timestamp}.json")
        with open(path, "w", encoding="utf8") as fh:
            json.dump(data, fh, indent=2)
    except Exception:
        logger.exception("Failed to archive %s mining run for %s", page, cmdr)
