"""
Report-an-issue support for Settings: builds a GitHub "new issue" address that already holds the facts a bug
report always needs, and opens it in the browser.

Nothing is sent from here. The browser opens the issue form on GitHub with the title and the Environment box
filled in; the user reads and edits it there, and submits it with their own GitHub account (or closes the tab).
The Environment line holds the WNTB, EDMC and Python versions and the OS, and nothing about the player: no
commander name, system or file path (this repository is public).

Design notes:
- The form fields are prefilled by id, so `Environment` below must match the `id: environment` field of
  `.github/ISSUE_TEMPLATE/bug_report.yml`. If the template is missing GitHub still opens a plain new-issue page.
- Addresses past a few KB are refused by some servers, so the prefill is short by design.
- Copy diagnostics puts the Environment lines and the latest WNTB lines of EDMC's log on the clipboard, for
  pasting into the issue's log box (too long for the address). Before they leave the log, the commander's name is
  replaced by `<commander>` and the user's home folder by `~`; the user can read the text before posting it.
- The OS description comes from `platform_support.describe_system()`, the one place OS differences live.
"""
from __future__ import annotations

import logging
import os
import re
import sys
import webbrowser
from typing import Dict, Iterable, List
from urllib.parse import urlencode

from . import __version__, platform_support
from .http_identity import HOMEPAGE

NEW_ISSUE_URL = f"{HOMEPAGE}/issues/new"
TEMPLATE = "bug_report.yml"
ENVIRONMENT_FIELD = "environment"
MAX_URL_LENGTH = 2000

LOG_NAME = "EDMarketConnector-debug.log"
LOG_TAIL_BYTES = 400_000      # only the end of the log is read; it can be many MB
MAX_LOG_LINES = 80            # newest WNTB lines kept, tracebacks included
MAX_LOG_CHARS = 12_000
_RECORD_START = re.compile(r"^\d{4}-\d\d-\d\d ")
_plugin_dir = os.path.basename(os.path.dirname(__file__))
logger = logging.getLogger(__name__)


def edmc_version() -> str:
    """EDMC's version; `config.appversion` is a function in current EDMC and a plain string in old ones."""
    try:
        from config import appversion
        return str(appversion() if callable(appversion) else appversion)
    except Exception:
        return "unknown"


def environment_text(edmc: str = "", system: str = "") -> str:
    """The Environment box: WNTB, EDMC and Python versions, and the OS."""
    return "\n".join([
        f"- WNTB: {__version__}",
        f"- EDMC: {edmc or edmc_version()}",
        f"- Python: {sys.version.split()[0]}",
        f"- OS: {system or platform_support.describe_system()}",
    ])


def build_url(environment: str = "") -> str:
    """The prefilled new-issue address for the bug report form."""
    params: Dict[str, str] = {
        "template": TEMPLATE,
        "labels": "bug",
        "title": f"[{__version__}] ",
        ENVIRONMENT_FIELD: environment or environment_text(),
    }
    url = f"{NEW_ISSUE_URL}?{urlencode(params)}"
    if len(url) > MAX_URL_LENGTH:  # never expected; fall back to the plain form rather than a broken link
        url = f"{NEW_ISSUE_URL}?{urlencode({'template': TEMPLATE})}"
    return url


def open_report() -> None:
    """Open the prefilled issue form in the user's browser."""
    webbrowser.open(build_url())


def log_path() -> str:
    """EDMC's debug log: the file its own logger writes to, else `logs/` in its data folder; "" if neither is found."""
    root = logging.getLogger()
    for logger in (logging.getLogger("EDMarketConnector"), root):
        for handler in logger.handlers:
            name = getattr(handler, "baseFilename", "")
            if name and os.path.basename(name).startswith("EDMarketConnector"):
                return str(name)
    try:
        from config import config
        candidate = os.path.join(str(config.app_dir_path), "logs", LOG_NAME)
        return candidate if os.path.isfile(candidate) else ""
    except Exception:
        return ""


def wntb_log_lines(text: str, plugin_dir: str = "", limit: int = MAX_LOG_LINES) -> List[str]:
    """The newest `limit` lines of log `text` that belong to WNTB: each record whose header names the plugin
    folder, with the lines that continue it (a traceback)."""
    marker = f".{plugin_dir or _plugin_dir}."
    kept: List[str] = []
    belongs = False
    for line in text.splitlines():
        if _RECORD_START.match(line):
            belongs = marker in line
        if belongs:
            kept.append(line)
    return kept[-limit:]


def redact(text: str, names: Iterable[str], home: str = "") -> str:
    """`text` with each commander name replaced by `<commander>` (any case) and the home folder by `~`."""
    home = home or os.path.expanduser("~")
    if home and home != "~":
        for form in {home, home.replace("\\", "/"), home.replace("/", "\\")}:
            text = text.replace(form, "~")
    for name in sorted({n.strip() for n in names if n and n.strip()}, key=len, reverse=True):
        text = re.sub(re.escape(name), "<commander>", text, flags=re.IGNORECASE)
    return text


def commander_names() -> List[str]:
    """The commander names WNTB can tell: EDMC's current one and the one in the newest journal."""
    from . import restore
    names = []
    try:
        names.append(restore.latest_commander())
    except Exception:
        pass
    try:
        from monitor import monitor
        names.append(str(getattr(monitor, "cmdr", "") or ""))
    except Exception:
        pass
    return [n for n in names if n]


def diagnostics_text(log_text: str = "", names: Iterable[str] = (), home: str = "") -> str:
    """The text Copy diagnostics puts on the clipboard: the Environment lines, then the newest WNTB log lines."""
    lines = wntb_log_lines(log_text)
    body = redact("\n".join(lines), names, home)[-MAX_LOG_CHARS:] if lines else "(no WNTB lines found in the log)"
    return f"{environment_text()}\n\nWNTB log lines:\n{body}\n"


def read_log_tail(path: str) -> str:
    """The last part of the log file at `path`, "" if it can't be read."""
    try:
        with open(path, "rb") as handle:
            handle.seek(0, os.SEEK_END)
            handle.seek(max(0, handle.tell() - LOG_TAIL_BYTES))
            return handle.read().decode("utf-8", errors="replace")
    except OSError:
        return ""


def copy_diagnostics(widget) -> bool:
    """Copy the diagnostics to the clipboard via `widget`; False if the clipboard refused."""
    path = log_path()
    text = diagnostics_text(read_log_tail(path) if path else "", commander_names())
    try:
        widget.clipboard_clear()
        widget.clipboard_append(text)
        widget.update()  # hands the clipboard over now, before focus moves back to the game
        return True
    except Exception:
        logger.warning("Could not copy the diagnostics to the clipboard", exc_info=True)
        return False
