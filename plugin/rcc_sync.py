"""
Sharing a commander's colonization progress with Raven Colonial, as its own documentation recommends for a tool that reads the journal.

Everything here is opt-in (two Settings checkboxes, both off) and only sends live journal events, never old ones caught up at
start-up. What goes out, and when:

- **Depot snapshot** - on a `ColonisationConstructionDepot` event, `PATCH /api/project/<build id>` with the event, the commodities
  still needed and the total need. This is what moves Raven's "remaining". It is sent only when the needed amounts changed.
- **Delivery** - on a `ColonisationContribution` event, `POST /api/project/<build id>/contribute/<commander>` with the commodities and
  tons delivered. This credits the commander in Raven's history. (Raven's `supply` call is deliberately never used: it is meant for
  tools with no journal, and used beside the depot snapshot it reduces need twice.)
- **Commander link** - `PUT /api/project/<build id>/link/<commander>`, once per commander and project in a session, before the first send.
- **Carrier cargo** (its own checkbox) - on a `CargoTransfer` at the commander's fleet carrier, `PATCH /api/FC/<market id>/cargo` with the
  tons moved as signed amounts (to the carrier plus, back to the ship minus). Never a replacement of Raven's record, which WNTB's own
  tally is not a complete copy of.

The Raven project for a site is found by reading the system's plan (one lookup, remembered; a site Raven has no project for is not
asked about again for ten minutes). Requests are made one at a time on a worker thread through a bounded queue (a full queue drops the
newest), each retried once on 429 / 503, and a failure is only logged: it never reaches the commander's play. The key goes in the
`rcc-key` header and nowhere else. The commander's name is only ever part of a URL.

Keeping each live event to one request means two tools reporting the same deliveries (another plugin, SrvSurvey) would make Raven
count them twice; the docs say so.
"""
from __future__ import annotations

import logging
import queue
import threading
import time
import urllib.parse
from typing import Any, Callable, Dict, Mapping, Optional, Set, Tuple

from . import colonisation, rcc_client

logger = logging.getLogger(__name__)

QUEUE_MAX = 50
NEGATIVE_SECONDS = 600
SEEN_MAX = 200


def _cmdr_path(cmdr: str) -> str:
    return urllib.parse.quote(cmdr.strip().casefold(), safe="")


def depot_body(build_id: str, entry: Mapping[str, Any]) -> Optional[Dict[str, Any]]:
    """The snapshot to send for a depot event, or None when the event holds no resources."""
    required = [r for r in entry.get("ResourcesRequired") or [] if isinstance(r, dict)]
    if not required:
        return None
    commodities: Dict[str, int] = {}
    total = 0
    for resource in required:
        key = colonisation.commodity_key(resource.get("Name"))
        if not key:
            continue
        try:
            wanted, given = int(resource.get("RequiredAmount") or 0), int(resource.get("ProvidedAmount") or 0)
        except (TypeError, ValueError):
            continue
        commodities[key] = max(0, wanted - given)
        total += max(0, wanted)
    return {"buildId": build_id, "colonisationConstructionDepot": dict(entry), "commodities": commodities, "maxNeed": total}


def contribution_body(entry: Mapping[str, Any]) -> Dict[str, int]:
    """Commodity key -> tons delivered, from a `ColonisationContribution` event."""
    delivered: Dict[str, int] = {}
    for item in entry.get("Contributions") or []:
        if not isinstance(item, dict):
            continue
        key = colonisation.commodity_key(item.get("Name"))
        try:
            amount = int(item.get("Amount") or 0)
        except (TypeError, ValueError):
            amount = 0
        if key and amount > 0:
            delivered[key] = delivered.get(key, 0) + amount
    return delivered


def carrier_body(entry: Mapping[str, Any]) -> Dict[str, int]:
    """Commodity key -> signed tons moved, from a `CargoTransfer` (to the carrier plus, back to the ship minus)."""
    moved: Dict[str, int] = {}
    for item in entry.get("Transfers") or []:
        if not isinstance(item, dict):
            continue
        key = colonisation.commodity_key(item.get("Type"))
        direction = str(item.get("Direction") or "").lower()
        try:
            count = int(item.get("Count") or 0)
        except (TypeError, ValueError):
            count = 0
        if key and count > 0 and direction in ("tocarrier", "toship"):
            moved[key] = moved.get(key, 0) + (count if direction == "tocarrier" else -count)
    return {k: v for k, v in moved.items() if v}


class RccSync:
    def __init__(self, share_progress: Callable[[], bool], share_carrier: Callable[[], bool], key_for: Callable[[str], str],
                 find_sites: Optional[Callable[[str], Any]] = None, writer: Optional[Callable[..., None]] = None,
                 now: Callable[[], float] = time.monotonic) -> None:
        self._share_progress, self._share_carrier, self._key_for = share_progress, share_carrier, key_for
        self._find_sites = find_sites or rcc_client.fetch_system
        self._write = writer or rcc_client.send_write
        self._now = now
        self._queue: "queue.Queue[Tuple[Callable[[], None], str]]" = queue.Queue(QUEUE_MAX)
        self._thread: Optional[threading.Thread] = None
        self._builds: Dict[int, str] = {}                  # market id -> Raven build id
        self._missing: Dict[int, float] = {}               # market id -> when Raven last had no project for it
        self._last_depot: Dict[Tuple[str, int], Tuple] = {}
        self._linked: Set[Tuple[str, str]] = set()
        self._seen: Set[Tuple[str, str]] = set()
        self.last_result = ""                              # the newest outcome, in words, for the window's status line

    # --- events from the journal (live only) ---------------------------------------------------------
    def on_depot(self, cmdr: str, entry: Mapping[str, Any], system: str, name: str = "") -> None:
        market_id = entry.get("MarketID")
        if not self._share_progress() or not cmdr or not isinstance(market_id, int):
            return
        marker = ("depot", self._stamp(entry))
        if self._already(cmdr, marker):
            return
        self._submit(lambda: self._send_depot(cmdr, entry, market_id, system, name), "depot")

    def on_contribution(self, cmdr: str, entry: Mapping[str, Any], system: str, name: str = "") -> None:
        market_id = entry.get("MarketID")
        if not self._share_progress() or not cmdr or not isinstance(market_id, int):
            return
        if self._already(cmdr, ("contribution", self._stamp(entry))):
            return
        delivered = contribution_body(entry)
        if delivered:
            self._submit(lambda: self._send_contribution(cmdr, market_id, system, delivered, name), "delivery")

    def on_carrier_transfer(self, cmdr: str, carrier_market_id: Optional[int], entry: Mapping[str, Any]) -> None:
        if not self._share_carrier() or not cmdr or not isinstance(carrier_market_id, int):
            return
        if self._already(cmdr, ("carrier", self._stamp(entry))):
            return
        moved = carrier_body(entry)
        key = self._key_for(cmdr)
        if moved and key:
            self._submit(lambda: self._send("PATCH", f"/api/FC/{carrier_market_id}/cargo", moved, key, "carrier cargo"), "carrier cargo")

    # --- one send at a time --------------------------------------------------------------------------
    @staticmethod
    def _stamp(entry: Mapping[str, Any]) -> str:
        return str(entry.get("timestamp") or "")

    def _already(self, cmdr: str, marker: Tuple[str, str]) -> bool:
        """True for an event seen before (the same journal line delivered twice); remembers it otherwise."""
        if not marker[1]:
            return False
        token = (cmdr.casefold(), "|".join(marker))
        if token in self._seen:
            return True
        if len(self._seen) >= SEEN_MAX:
            self._seen.clear()
        self._seen.add(token)
        return False

    def _submit(self, job: Callable[[], None], label: str) -> None:
        try:
            self._queue.put_nowait((job, label))
        except queue.Full:
            logger.debug("Raven Colonial send queue is full; dropped a %s", label)
            return
        if self._thread is None or not self._thread.is_alive():
            self._thread = threading.Thread(target=self._run, name="WNTB-rcc-sync", daemon=True)
            self._thread.start()

    def _run(self) -> None:
        while True:
            try:
                job, label = self._queue.get(timeout=30)
            except queue.Empty:
                return
            try:
                job()
            except Exception:
                logger.debug("Raven Colonial %s send failed", label, exc_info=True)
            finally:
                self._queue.task_done()

    def _build_id(self, market_id: int, system: str, name: str = "") -> str:
        if market_id in self._builds:
            return self._builds[market_id]
        missed = self._missing.get(market_id)
        if missed is not None and self._now() - missed < NEGATIVE_SECONDS:
            return ""
        try:
            build_id = rcc_client.find_build_id(self._find_sites(system).sites, market_id, name) if system else ""
        except rcc_client.RccError as err:
            self.last_result = str(err)
            return ""
        if build_id:
            self._builds[market_id] = build_id
        else:
            self._missing[market_id] = self._now()
            self.last_result = "Raven Colonial has no project linked to this site, so nothing was sent."
        return build_id

    def _send(self, method: str, path: str, body: Optional[Any], key: str, what: str) -> bool:
        try:
            self._write(method, path, body, key)
        except rcc_client.RccError as err:
            self.last_result = f"Raven Colonial {what}: {err}"
            logger.debug("Raven Colonial %s not sent: %s", what, err)
            return False
        self.last_result = f"Raven Colonial updated ({what})."
        return True

    def _link(self, cmdr: str, build_id: str, key: str) -> None:
        token = (cmdr.casefold(), build_id)
        if token in self._linked:
            return
        if self._send("PUT", f"/api/project/{urllib.parse.quote(build_id, safe='')}/link/{_cmdr_path(cmdr)}", None, key, "commander link"):
            self._linked.add(token)

    def _has_key(self, cmdr: str) -> bool:
        """Every write needs the commander's key; without one nothing is looked up or sent (Raven's API spec says nothing about
        which writes work keyless, so none is tried)."""
        if self._key_for(cmdr).strip():
            return True
        self.last_result = "No Raven Colonial key is saved for this commander, so nothing was sent."
        return False

    def _send_depot(self, cmdr: str, entry: Mapping[str, Any], market_id: int, system: str, name: str = "") -> None:
        if not self._has_key(cmdr):
            return
        build_id = self._build_id(market_id, system, name)
        if not build_id:
            return
        body = depot_body(build_id, entry)
        if body is None:
            return
        snapshot = tuple(sorted(body["commodities"].items()))
        marker = (cmdr.casefold(), market_id)
        if self._last_depot.get(marker) == snapshot:
            return                                  # the needed amounts have not changed since the last one sent
        key = self._key_for(cmdr)
        self._link(cmdr, build_id, key)
        if self._send("PATCH", f"/api/project/{urllib.parse.quote(build_id, safe='')}", body, key, "progress"):
            self._last_depot[marker] = snapshot

    def _send_contribution(self, cmdr: str, market_id: int, system: str, delivered: Dict[str, int], name: str = "") -> None:
        if not self._has_key(cmdr):
            return
        build_id = self._build_id(market_id, system, name)
        if not build_id:
            return
        key = self._key_for(cmdr)
        self._link(cmdr, build_id, key)
        self._send("POST", f"/api/project/{urllib.parse.quote(build_id, safe='')}/contribute/{_cmdr_path(cmdr)}", delivered, key,
                   "delivery")
