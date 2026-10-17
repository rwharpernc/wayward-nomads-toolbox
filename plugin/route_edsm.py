"""Which systems of the plotted route EDSM does not know yet, for the Route overlay's optional check.

A system EDSM has no record of has not been uploaded by anyone using EDSM, which for an explorer usually means a first discovery waiting (or a system
nobody who shares data has been to). The check is opt-in (Settings → Overlays → Route) because it sends the names of the next systems on the route to EDSM
(and nothing else about the commander), one request for the lot. Pure apart from the lookup function, which is injected: no Tk, no EDMC.

`EdsmChecker.ensure(names)` never waits: it starts one background lookup for the names it has no answer for and returns at once; `status(name)` is True
(EDSM knows it), False (it does not) or None (not asked yet, still asking, or the lookup failed). A failure is never read as "unknown to EDSM" and is retried
after a pause. A "known" answer is kept for the session; a "not known" answer is asked again after a while, since someone may upload the system meanwhile.
"""
from __future__ import annotations

import logging
import threading
import time
from typing import Callable, Dict, Iterable, List, Optional, Tuple

from . import edsm_client

logger = logging.getLogger(__name__)

MAX_NAMES = 40            # systems per request
NOT_KNOWN_TTL_S = 600     # ask again about a system EDSM did not know after this long
FAILED_RETRY_S = 300      # and about every system after a failed lookup

Lookup = Callable[[List[str]], Optional[Dict[str, bool]]]


class EdsmChecker:
    def __init__(self, lookup: Lookup = edsm_client.systems_known, now: Callable[[], float] = time.time, background: bool = True) -> None:
        self._lookup = lookup
        self._now = now
        self._background = background
        self._lock = threading.Lock()
        self._answers: Dict[str, Tuple[bool, float]] = {}      # casefolded name -> (known, when asked)
        self._busy = False
        self._failed_at: Optional[float] = None

    # --- reading -----------------------------------------------------------------------------------------------
    def status(self, name: str) -> Optional[bool]:
        """True when EDSM knows `name`, False when it did not at the last ask, None when there is no usable answer."""
        with self._lock:
            return self._fresh(name.casefold())

    def _fresh(self, key: str) -> Optional[bool]:
        answer = self._answers.get(key)
        if answer is None:
            return None
        known, when = answer
        if not known and self._now() - when > NOT_KNOWN_TTL_S:
            return None
        return known

    def pending(self) -> bool:
        with self._lock:
            return self._busy

    def failing(self) -> bool:
        """The last lookup failed and the retry pause has not passed."""
        with self._lock:
            return self._failed_at is not None and self._now() - self._failed_at < FAILED_RETRY_S

    # --- asking ------------------------------------------------------------------------------------------------
    def ensure(self, names: Iterable[str]) -> bool:
        """Ask EDSM about the names with no usable answer, once, in the background. Returns whether a lookup was started."""
        with self._lock:
            if self._busy or (self._failed_at is not None and self._now() - self._failed_at < FAILED_RETRY_S):
                return False
            wanted: List[str] = []
            seen = set()
            for name in names:
                key = name.casefold()
                if name and key not in seen and self._fresh(key) is None:
                    seen.add(key)
                    wanted.append(name)
            wanted = wanted[:MAX_NAMES]
            if not wanted:
                return False
            self._busy = True
        if self._background:
            threading.Thread(target=self._run, args=(wanted,), name="WNTB-route-edsm", daemon=True).start()
        else:
            self._run(wanted)
        return True

    def _run(self, names: List[str]) -> None:
        try:
            result = self._lookup(names)
        except Exception:      # a lookup must never take the overlay down
            logger.debug("EDSM route lookup raised", exc_info=True)
            result = None
        with self._lock:
            self._busy = False
            if result is None:
                self._failed_at = self._now()
                return
            self._failed_at = None
            stamp = self._now()
            for name in names:
                if name in result:
                    self._answers[name.casefold()] = (bool(result[name]), stamp)


def sample_checker() -> EdsmChecker:
    """A checker pre-loaded for the Test Card's made-up route, in which jumps 3 and 7 are to systems EDSM does not know (no network is used)."""
    names = [f"Sample System {number}" for number in range(1, 13)]
    checker = EdsmChecker(lookup=lambda asked: {name: not name.endswith((" 3", " 7")) for name in asked}, background=False)
    checker.ensure(names)
    return checker
