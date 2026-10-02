"""Sync HTTP client for the community-run Elite Dangerous BGS "galaxy tick"
time API (`tick.infomancer.uk`).

One function, no Tk/threading here - `bgs_panel.py` supplies the
`queue.Queue`/generation-counter/`threading.Thread`/`after()`-poll wrapper
around this, the same off-main-thread pattern already established by
`canonn_poi_panel.py`/`boxel_survey.py`. Raises on any failure - the caller
decides how to handle a temporarily-unreachable service, same convention as
`gec_poi_edastro.py`.

This is a third-party, community-run service, not an official Frontier API
- it can go down, rate-limit, or change response shape without notice.
Every failure here should be treated by the caller as "tick unknown right
now", never fatal to the rest of BGS tracking (faction-state snapshots and
the activity tally both work fine with no tick data at all - see
docs/BGS_TECH_SPEC.md)."""

from __future__ import annotations

import json
import urllib.request
from datetime import datetime, timezone

from . import http_identity

TICK_URL = "http://tick.infomancer.uk/galtick.json"
"""Plain HTTP, not HTTPS - the service doesn't serve HTTPS."""

_TIMEOUT_S = 10
_TIMESTAMP_FORMAT = "%Y-%m-%dT%H:%M:%S.%fZ"
_USER_AGENT = http_identity.user_agent("bgs-tick")


def fetch_latest_tick() -> datetime:
    """Returns the current galaxy tick's UTC timestamp. Raises (OSError,
    ValueError, KeyError, json.JSONDecodeError) on any network, parsing, or
    unexpected-response-shape failure - never returns a guessed/stale
    value on failure."""
    request = urllib.request.Request(TICK_URL, headers={"User-Agent": _USER_AGENT})
    with urllib.request.urlopen(request, timeout=_TIMEOUT_S) as response:
        payload = json.loads(response.read().decode("utf-8"))
    raw = payload["lastGalaxyTick"]
    return datetime.strptime(raw, _TIMESTAMP_FORMAT).replace(tzinfo=timezone.utc)
