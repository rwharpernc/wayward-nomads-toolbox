"""JSON persistence for Codex Completionist's tally, stored alongside the
plugin. Same atomic-write pattern as boxel_state.py/region_sweep_state.py.
Unlike Discovery/Interdiction/Landing's ephemeral precedent, this state
genuinely persists across restarts - see codex_completionist.py's own
docstring for why."""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Optional

from config import appname

plugin_name = os.path.basename(os.path.dirname(__file__))
logger = logging.getLogger(f"{appname}.{plugin_name}")

STATE_FILENAME = "codex_completionist_state.json"


def _state_path(plugin_dir: str) -> str:
    return os.path.join(plugin_dir, STATE_FILENAME)


def load_state(plugin_dir: str) -> Optional[Any]:
    """Load persisted state, or None if there's nothing saved / it's unreadable."""
    path = _state_path(plugin_dir)
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except FileNotFoundError:
        return None
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("Could not read %s: %s", path, exc)
        return None


def save_state(plugin_dir: str, data: Any) -> None:
    """
    Save state, writing to a temp file and replacing atomically so a crash
    or EDMC being killed mid-write can't leave a corrupt/truncated state file.
    """
    path = _state_path(plugin_dir)
    tmp_path = f"{path}.tmp"
    try:
        with open(tmp_path, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2, sort_keys=True)
        os.replace(tmp_path, path)
    except OSError as exc:
        logger.warning("Could not write %s: %s", path, exc)
