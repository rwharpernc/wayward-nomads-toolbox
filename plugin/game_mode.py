"""The "You are in <mode> mode." line shown above the credits line, under the
mode buttons, in every mode (see ui.py's create_plugin_app).

Which game mode the pilot is flying in (Open, Solo or a Private Group) comes
from the journal's `LoadGame` event (`GameMode`, and `Group` for a private
group). This module owns that on its own: it is not part of Powerplay, and
Powerplay no longer shows or tracks it.

When EDMC starts with the game already running there is no journal replay;
EDMC sends a synthetic `StartUp` event instead, so the mode is recovered by
reading the `LoadGame` line from the top of the current journal file.

`mode_text` and `read_mode_from_journal` are pure so they can be tested
without EDMC; the widget code imports Tk helpers lazily for the same reason.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict, Optional, Tuple

import tkinter as tk

try:
    from config import appname
except ImportError:  # unit tests outside EDMC
    appname = "EDMarketConnector"

plugin_name = os.path.basename(os.path.dirname(__file__))
logger = logging.getLogger(f"{appname}.{plugin_name}")

_WAITING_TEXT = "Game mode: waiting for login…"
_LOADGAME_SCAN_LIMIT = 50  # "LoadGame" is always one of the first few lines in a journal file

Mode = Tuple[Optional[str], Optional[str]]
"""(GameMode, Group) as the journal reports them."""


def mode_text(game_mode: Optional[str], group: Optional[str] = None) -> str:
    """'You are in Solo mode.' (Open / Solo / Private Group), or a neutral
    line when the journal gave nothing recognisable."""
    if game_mode == "Open":
        return "You are in Open mode."
    if game_mode == "Solo":
        return "You are in Solo mode."
    if game_mode == "Group":
        name = f" ({group})" if group else ""
        return f"You are in Private Group mode{name}."
    return _WAITING_TEXT


def read_mode_from_journal(path: Optional[str]) -> Optional[Mode]:
    """The (GameMode, Group) in the `LoadGame` event near the top of a journal
    file, or None if there isn't one or the file can't be read."""
    if not path:
        return None
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as handle:
            for _ in range(_LOADGAME_SCAN_LIMIT):
                line = handle.readline()
                if not line:
                    break
                try:
                    entry = json.loads(line)
                except ValueError:
                    continue
                if isinstance(entry, dict) and entry.get("event") == "LoadGame":
                    return entry.get("GameMode"), entry.get("Group")
    except FileNotFoundError:
        logger.debug("No journal file at %s for game-mode recovery", path)
    except OSError:
        logger.warning("Could not read %s for game-mode recovery", path, exc_info=True)
    return None


def _current_logfile() -> Optional[str]:
    try:
        from monitor import monitor  # EDMC's own module; absent in unit tests
    except ImportError:
        return None
    logfile = getattr(monitor, "logfile", None)
    return str(logfile) if logfile else None  # a str or a pathlib.Path depending on the EDMC version


class GameModeTracker:
    def __init__(self) -> None:
        self._mode: Optional[Mode] = None
        self._label: Optional[tk.Label] = None

    # --- journal ------------------------------------------------------------

    def handle_event(
        self, entry: Dict[str, Any], cmdr: str, system: Optional[str], station: Optional[str], state: Dict[str, Any],
    ) -> None:
        event = entry.get("event")
        if event == "LoadGame":
            self._mode = (entry.get("GameMode"), entry.get("Group"))
        elif event == "StartUp":
            self._mode = read_mode_from_journal(_current_logfile())
        elif event == "Shutdown":
            self._mode = None  # the game closed: no longer in any mode
        else:
            return
        self._refresh()

    # --- widget ---------------------------------------------------------------

    def text(self) -> str:
        return mode_text(*self._mode) if self._mode else _WAITING_TEXT

    def build(self, parent: tk.Frame, row: int) -> tk.Label:
        """Create the line's label in `parent` at `row`. Wraps to the panel
        width like every label showing live data (a long private-group name
        can't widen EDMC's window)."""
        from . import panelkit

        self._label = panelkit.wrap_label(parent, text=self.text(), anchor="w")
        self._label.grid(row=row, column=0, columnspan=3, sticky=tk.W)
        return self._label

    def _refresh(self) -> None:
        if self._label is not None:
            self._label["text"] = self.text()


tracker = GameModeTracker()


def handle_event(
    entry: Dict[str, Any], cmdr: str, system: Optional[str], station: Optional[str], state: Dict[str, Any],
) -> None:
    tracker.handle_event(entry, cmdr, system, station, state)


def build(parent: tk.Frame, row: int) -> tk.Label:
    return tracker.build(parent, row)
