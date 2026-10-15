"""Megaship scans for the Powerplay cycle - pure logic (no Tk, no network, no EDMC), shared by the live journal feed and the journal back-fill.

**What the journal gives.** Powerplay 2.0 rewards scanning the datalink ("ship uplink") of a megaship. The journal records the scan as
`DataScanned` with `Type` `$Datascan_ShipUplink;`, and it does not name the ship. The name comes from the event before it: dropping out of supercruise
at the megaship writes `SupercruiseDestinationDrop` with `Type` set to the megaship's name (`HIP 117706 Demeter-class Cropper`), and an FSS scan of a
system lists its megaships as `FSSSignalDiscovered` with `SignalType` `Megaship`. The merits the scan earns arrive as a `PowerplayMerits` a second later.
Checked against real journals: 37 of 39 uplink scans resolved to a megaship that way (the other two were not megaships).

**What a scan is.** A `DataScanned` uplink whose destination is a megaship: the name is in the FSS list for the system, or it contains the word "class"
(every megaship class name does: "Aquarius-class Tanker", "Gordon Class Bulk Cargo Ship"). Anything else (a station, a settlement, an ordinary ship) is
not counted. The same megaship in the same system counts once a cycle (the ledger de-duplicates by `key`), and the merits of that scan are added to it when
the `PowerplayMerits` follows within `MERIT_WINDOW_S`.

The idea of counting megaship scans through the cycle follows ODEliteTracker's BGS data store, whose approach (the destination just dropped to, plus the
uplink scan) this reads the same way; the code is WNTB's own."""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set, Tuple

UPLINK = "$Datascan_ShipUplink;"
MERIT_WINDOW_S = 6
MAX_NAME_CHARS = 80
MAX_SYSTEM_CHARS = 60

_CLASS_WORD = re.compile(r"\bclass\b", re.IGNORECASE)
_JUMP_EVENTS = ("FSDJump", "Location", "CarrierJump")


def _norm(name: Any) -> str:
    return " ".join(str(name or "").split()).casefold()


def _stamp(value: Any) -> Optional[datetime]:
    if not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)
    except ValueError:
        return None


@dataclass
class MegaShipScan:
    name: str
    system: str
    address: int          # the journal's SystemAddress, 0 when unknown
    at: str               # the scan's journal timestamp
    merits: int = 0       # merits the scan earned (from the PowerplayMerits that followed), 0 if none were seen
    merit_at: str = ""    # the timestamp of the newest merit event counted in `merits`: a replay of the same events adds nothing

    @property
    def key(self) -> Tuple[str, Any]:
        """One megaship in one system: the same key is the same ship, scanned again."""
        return (_norm(self.name), self.address or _norm(self.system))

    def to_dict(self) -> Dict[str, Any]:
        data = {"name": self.name, "system": self.system, "address": self.address, "at": self.at, "merits": self.merits}
        if self.merit_at:
            data["merit_at"] = self.merit_at
        return data

    @classmethod
    def from_dict(cls, data: Any) -> Optional["MegaShipScan"]:
        if not isinstance(data, dict):
            return None
        name, system, at = data.get("name"), data.get("system"), data.get("at")
        if not isinstance(name, str) or not name.strip() or not isinstance(system, str) or _stamp(at) is None:
            return None

        def whole(value: Any) -> int:
            return value if isinstance(value, int) and not isinstance(value, bool) and value > 0 else 0

        merit_at = data.get("merit_at")
        return cls(name.strip()[:MAX_NAME_CHARS], system.strip()[:MAX_SYSTEM_CHARS], whole(data.get("address")), at, whole(data.get("merits")),
                   merit_at if _stamp(merit_at) is not None else "")


# What the tracker reports: ("scan", MegaShipScan) for a new uplink scan, ("merits", key, gained, at) for merits that followed one.
Result = Tuple[Any, ...]


class MegaShipTracker:
    """Follows the journal for one commander's session and says when a megaship was scanned. Feed it every entry, in order."""

    def __init__(self) -> None:
        self._system = ""
        self._address = 0
        self._destination = ""
        self._megaships: Set[str] = set()
        self._last: Optional[Tuple[Tuple[str, Any], datetime]] = None

    def feed(self, entry: Dict[str, Any]) -> List[Result]:
        event = entry.get("event")
        if event in _JUMP_EVENTS:
            address = entry.get("SystemAddress")
            address = address if isinstance(address, int) and not isinstance(address, bool) else 0
            if address != self._address or not address:
                self._megaships = set()          # a Location at login repeats the system you are already in: keep what the FSS found
            self._system = str(entry.get("StarSystem") or self._system)[:MAX_SYSTEM_CHARS]
            self._address = address
            self._destination = ""
        elif event == "FSSSignalDiscovered":
            if entry.get("SignalType") == "Megaship" and entry.get("SignalName"):
                self._megaships.add(_norm(entry["SignalName"]))
        elif event == "SupercruiseDestinationDrop":
            self._destination = str(entry.get("Type") or "")[:MAX_NAME_CHARS * 2]
        elif event == "SupercruiseEntry":
            self._destination = ""
        elif event == "DataScanned" and entry.get("Type") == UPLINK:
            return self._scanned(entry)
        elif event == "PowerplayMerits":
            return self._merits(entry)
        return []

    def _is_megaship(self, name: str) -> bool:
        return bool(name) and (_norm(name) in self._megaships or bool(_CLASS_WORD.search(name)))

    def _scanned(self, entry: Dict[str, Any]) -> List[Result]:
        when = _stamp(entry.get("timestamp"))
        if when is None or not self._system or not self._is_megaship(self._destination):
            self._last = None
            return []
        scan = MegaShipScan(" ".join(self._destination.split())[:MAX_NAME_CHARS], self._system, self._address, entry["timestamp"])
        self._last = (scan.key, when)
        return [("scan", scan)]

    def _merits(self, entry: Dict[str, Any]) -> List[Result]:
        gained = entry.get("MeritsGained")
        when = _stamp(entry.get("timestamp"))
        if self._last is None or when is None or not isinstance(gained, int) or isinstance(gained, bool) or gained <= 0:
            return []
        key, scanned = self._last
        if not 0 <= (when - scanned).total_seconds() <= MERIT_WINDOW_S:
            self._last = None
            return []
        return [("merits", key, gained, entry["timestamp"])]
