"""The "Credits this session" line: how many credits the pilot has earned or
lost since logging in, shown under the mode buttons in every mode (see ui.py's
create_plugin_app).

This is a feature of its own. It used to piggy-back on Powerplay's session
store; it no longer touches Powerplay at all. It keeps its own small record
of the current session (balance at login, balance now, which journal file and
commander it belongs to) in `session_credits.json` beside the plugin.

A session is one game login, tied to the journal file it started in:
- `LoadGame` carries the balance at login. Seeing the same journal file and
  commander again (a logout to the menu and back) continues the session.
- When EDMC starts with the game already running there is no journal replay,
  only a synthetic `StartUp`; the saved record is picked back up if it belongs
  to the same journal file, otherwise a new session begins.
- On every event the balance is read from EDMC's `state["Credits"]`.

The session logic and the text are pure functions so they can be unit-tested
without EDMC; Tk helpers and EDMC's `monitor` are imported lazily for the same
reason.
"""

from __future__ import annotations

import calendar
import json
import logging
import os
import time
from typing import Any, Dict, Optional, Tuple

import tkinter as tk

try:
    from config import appname
except ImportError:  # unit tests outside EDMC
    appname = "EDMarketConnector"

plugin_name = os.path.basename(os.path.dirname(__file__))
logger = logging.getLogger(f"{appname}.{plugin_name}")

STATE_FILENAME = "session_credits.json"
_WAITING_TEXT = "Credits this session: waiting for your balance…"
_PERSIST_EVERY_S = 30.0  # the balance changes on most events; don't write a file for each one
_MIN_HOURS_FOR_RATE = 0.05  # about three minutes


# --- pure session logic ------------------------------------------------------

def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _parse_iso(value: Optional[str]) -> Optional[float]:
    if not value:
        return None
    try:
        return float(calendar.timegm(time.strptime(value, "%Y-%m-%dT%H:%M:%SZ")))
    except ValueError:
        return None


def new_session(cmdr: str, credits_start: Optional[int], journal_file: Optional[str]) -> Dict[str, Any]:
    now = _now_iso()
    return {
        "cmdr": cmdr, "journal_file": journal_file, "credits_start": credits_start,
        "credits_now": credits_start, "started_at": now, "updated_at": now,
    }


def sync_session(
    session: Optional[Dict[str, Any]], cmdr: str, credits_start: Optional[int], journal_file: Optional[str],
) -> Tuple[Dict[str, Any], bool]:
    """Reconcile the saved session against the journal file EDMC is tracking.
    Returns (session, continued). The same journal file *and* the same
    commander means one continuous session (Frontier keeps writing to one
    journal across a logout-to-menu-and-back even when another commander is
    picked, so the file alone isn't enough); anything else starts a new one."""
    if session and journal_file and session.get("journal_file") == journal_file:
        saved_cmdr = session.get("cmdr")
        if not saved_cmdr or not cmdr or saved_cmdr == cmdr:
            if cmdr:
                session["cmdr"] = cmdr
            session["updated_at"] = _now_iso()
            return session, True
    return new_session(cmdr, credits_start, journal_file), False


def update_balance(session: Dict[str, Any], credits_now: Optional[int]) -> bool:
    """Record the balance now. Returns True if it changed."""
    if credits_now is None:
        return False
    if session.get("credits_start") is None:
        session["credits_start"] = credits_now
    changed = session.get("credits_now") != credits_now
    session["credits_now"] = credits_now
    session["updated_at"] = _now_iso()
    return changed


def credits_earned(session: Dict[str, Any]) -> Optional[int]:
    """Balance now minus balance at login (negative = credits lost), or None
    while either is unknown."""
    start, now = session.get("credits_start"), session.get("credits_now")
    if start is None or now is None:
        return None
    return int(now) - int(start)


def duration_hours(session: Dict[str, Any]) -> float:
    started, updated = _parse_iso(session.get("started_at")), _parse_iso(session.get("updated_at"))
    if started is None or updated is None:
        return 0.0
    return max(0.0, updated - started) / 3600.0


def summary_text(earned: Optional[int], hours: float) -> str:
    """'Credits this session: +1,234,567 cr earned (+411,522 cr/hr)', or
    '... -5,000 cr lost', or 'no change yet'. `earned` is the balance now minus
    the balance at login; None means the balance isn't known yet. The hourly
    rate is left out until the session has run long enough to mean something."""
    if earned is None:
        return _WAITING_TEXT
    if earned > 0:
        text = f"Credits this session: +{earned:,} cr earned"
    elif earned < 0:
        text = f"Credits this session: -{abs(earned):,} cr lost"
    else:
        return "Credits this session: no change yet"
    if hours >= _MIN_HOURS_FOR_RATE:
        text += f" ({earned / hours:+,.0f} cr/hr)"
    return text


# --- persistence ---------------------------------------------------------------

def load_session(plugin_dir: str) -> Optional[Dict[str, Any]]:
    try:
        with open(os.path.join(plugin_dir, STATE_FILENAME), "r", encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def save_session(plugin_dir: str, session: Dict[str, Any]) -> None:
    """Write via a temp file and replace, so a crash can't leave it half-written."""
    path = os.path.join(plugin_dir, STATE_FILENAME)
    tmp = f"{path}.tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as handle:
            json.dump(session, handle, indent=2, sort_keys=True)
        os.replace(tmp, path)
    except OSError:
        logger.warning("Could not write %s", path, exc_info=True)


# --- the feature -----------------------------------------------------------------

def _current_logfile() -> Optional[str]:
    try:
        from monitor import monitor  # EDMC's own module; absent in unit tests
    except ImportError:
        return None
    logfile = getattr(monitor, "logfile", None)
    return str(logfile) if logfile else None  # a str or a pathlib.Path depending on the EDMC version


def _as_int(value: Any) -> Optional[int]:
    return int(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else None


class SessionCredits:
    def __init__(self) -> None:
        self._plugin_dir: Optional[str] = None
        self._session: Optional[Dict[str, Any]] = None
        self._label: Optional[tk.Label] = None
        self._last_saved = 0.0

    # --- lifecycle ---------------------------------------------------------------

    def start(self, plugin_dir: str) -> None:
        self._plugin_dir = plugin_dir
        self._session = load_session(plugin_dir)

    def stop(self) -> None:
        self._save(force=True)

    def _save(self, force: bool = False) -> None:
        if self._plugin_dir is None or self._session is None:
            return
        if force or time.monotonic() - self._last_saved >= _PERSIST_EVERY_S:
            save_session(self._plugin_dir, self._session)
            self._last_saved = time.monotonic()

    # --- journal ---------------------------------------------------------------------

    def handle_event(
        self, entry: Dict[str, Any], cmdr: str, system: Optional[str], station: Optional[str], state: Dict[str, Any],
    ) -> None:
        event = entry.get("event")
        new_session_started = False
        if event == "LoadGame":
            self._session, continued = sync_session(self._session, cmdr, _as_int(entry.get("Credits")), _current_logfile())
            new_session_started = not continued
        elif event == "StartUp":
            # EDMC (re)started with the game already running: no replay, so
            # pick the saved session back up if it is the same journal file.
            self._session, continued = sync_session(self._session, cmdr, None, _current_logfile())
            new_session_started = not continued
        if self._session is None:
            return

        balance = _as_int(state.get("Credits")) if isinstance(state, dict) else None
        changed = update_balance(self._session, balance) if balance is not None else False
        if new_session_started:
            self._save(force=True)
        elif changed:
            self._save()
        if changed or event in ("LoadGame", "StartUp"):
            self.refresh()

    # --- widget --------------------------------------------------------------------

    def text(self) -> str:
        if not self._session:
            return _WAITING_TEXT
        return summary_text(credits_earned(self._session), duration_hours(self._session))

    def build(self, parent: tk.Frame, row: int) -> tk.Label:
        """Create the line's label in `parent` at `row`. Wraps to the panel
        width like every label showing live data, so a long number can't
        widen EDMC's window."""
        from . import panelkit

        self._label = panelkit.wrap_label(parent, text=self.text(), anchor="w")
        self._label.grid(row=row, column=0, columnspan=3, sticky=tk.W)
        return self._label

    def refresh(self) -> None:
        if self._label is not None:
            self._label["text"] = self.text()

    def set_visible(self, visible: bool) -> None:
        """Show or hide the line (the mode in view decides: see ui.py's _MODES_WITHOUT_CREDITS). The
        session record keeps being updated either way, so it is right when the line comes back."""
        if self._label is None:
            return
        if visible:
            self._label.grid()
        else:
            self._label.grid_remove()


controller = SessionCredits()


def start(plugin_dir: str) -> None:
    controller.start(plugin_dir)


def stop() -> None:
    controller.stop()


def handle_event(
    entry: Dict[str, Any], cmdr: str, system: Optional[str], station: Optional[str], state: Dict[str, Any],
) -> None:
    controller.handle_event(entry, cmdr, system, station, state)


def build(parent: tk.Frame, row: int) -> tk.Label:
    return controller.build(parent, row)


def set_visible(visible: bool) -> None:
    controller.set_visible(visible)
