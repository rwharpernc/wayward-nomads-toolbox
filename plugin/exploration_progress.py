"""
How far through a system you are, and what your last data sales actually paid, for the Exploration Value readout.

Both come straight from journal events the plugin did not read before:

- `FSSDiscoveryScan` (the honk): `BodyCount`, how many bodies the system has, and `Progress`. Each `Scan` of a star or
  planet then counts one scanned. (Belt clusters and rings arrive as `Scan` too but are not counted in `BodyCount`, so
  only scans carrying a `StarType` or `PlanetClass` are.) `FSSAllBodiesFound` says the FSS has found every body.
- `MultiSellExplorationData` / `SellExplorationData` (`TotalEarnings`) and `SellOrganicData` (`BioData`, each with a
  `Value` and `Bonus`): what a sale really paid, to set against the scan estimate.

Pure logic: no Tk, no EDMC.
"""
from __future__ import annotations

from typing import Any, Dict, Iterable, Mapping, Optional, Set

ARRIVAL_EVENTS = ("FSDJump", "Location", "CarrierJump")
_UNKNOWN_TEXT = "System bodies: (honk to count them)"
_NO_SALE_TEXT = "Last data sale: (none yet)"


def _int(value: Any) -> int:
    return int(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else 0


class SystemProgress:
    """Bodies scanned in the current system against how many the honk said there are."""

    def __init__(self) -> None:
        self.system: Optional[str] = None
        self.body_total: Optional[int] = None
        self.all_found = False
        self._scanned: Set[str] = set()

    @property
    def scanned(self) -> int:
        return len(self._scanned)

    def enter(self, system: Optional[str]) -> None:
        """A new system: forget the last one's counts."""
        self.system, self.body_total, self.all_found = system, None, False
        self._scanned = set()

    def feed(self, entry: Mapping[str, Any]) -> bool:
        """Fold in one journal event. Returns True if the text changed."""
        event = entry.get("event")
        if event in ARRIVAL_EVENTS:
            self.enter(entry.get("StarSystem"))
            return True
        if event == "FSSDiscoveryScan":
            total = _int(entry.get("BodyCount"))
            if total > 0:
                self.body_total = total
                return True
        elif event == "FSSAllBodiesFound":
            self.all_found = True
            return True
        elif event == "Scan" and (entry.get("StarType") or entry.get("PlanetClass")) and entry.get("BodyName"):
            name = str(entry["BodyName"])
            if name not in self._scanned:
                self._scanned.add(name)
                return True
        return False

    def text(self) -> str:
        if self.body_total is None:
            return _UNKNOWN_TEXT if not self._scanned else f"System bodies: {self.scanned} scanned (honk to count them)"
        done = " — all found" if self.all_found else ""
        return f"System bodies: {min(self.scanned, self.body_total)} scanned of {self.body_total}{done}"


def organic_payout(entry: Mapping[str, Any]) -> int:
    """What a `SellOrganicData` paid: every species' value plus its first-discovery bonus."""
    total = 0
    for item in entry.get("BioData") or []:
        if isinstance(item, dict):
            total += _int(item.get("Value")) + _int(item.get("Bonus"))
    return total


class LastSales:
    """The most recent exploration-data sale and the most recent organic-data sale."""

    def __init__(self) -> None:
        self.exploration: Optional[int] = None
        self.organic: Optional[int] = None

    def feed(self, entry: Mapping[str, Any]) -> bool:
        event = entry.get("event")
        if event in ("MultiSellExplorationData", "SellExplorationData"):
            earned = _int(entry.get("TotalEarnings"))
            if earned > 0:
                self.exploration = earned
                return True
        elif event == "SellOrganicData":
            earned = organic_payout(entry)
            if earned > 0:
                self.organic = earned
                return True
        return False

    def text(self) -> str:
        parts = []
        if self.exploration is not None:
            parts.append(f"exploration {self.exploration:,} cr")
        if self.organic is not None:
            parts.append(f"organic {self.organic:,} cr")
        return "Last data sale: " + ", ".join(parts) if parts else _NO_SALE_TEXT


def replay(entries: Iterable[Mapping[str, Any]]) -> "tuple[SystemProgress, LastSales]":
    """Both of the above as they stand after `entries` (a journal file's events in order), for an EDMC that started
    mid-session and has seen none of them live."""
    progress, sales = SystemProgress(), LastSales()
    for entry in entries:
        progress.feed(entry)
        sales.feed(entry)
    return progress, sales
