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
- The OS description comes from `platform_support.describe_system()`, the one place OS differences live.
"""
from __future__ import annotations

import sys
import webbrowser
from typing import Dict
from urllib.parse import urlencode

from . import __version__, platform_support
from .http_identity import HOMEPAGE

NEW_ISSUE_URL = f"{HOMEPAGE}/issues/new"
TEMPLATE = "bug_report.yml"
ENVIRONMENT_FIELD = "environment"
MAX_URL_LENGTH = 2000


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
