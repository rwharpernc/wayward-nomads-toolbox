"""Fuel warnings: the pure part. Two warnings, both from what the game already writes:

- **Low fuel**: the main tank is at or under a chosen percentage (the game's own cockpit warning comes at 25 %; this one is
  on the overlay and the percentage is yours to choose).
- **Next star cannot be scooped**: a destination is plotted whose star class is not one of the scoopable ones (O, B, A, F, G, K,
  M) and the tank is at or under a second percentage. This is the one the game does not warn about, and the one that strands a
  ship on a neutron-star route.

Sources and their limits: the tank size comes from the `Loadout` event (`FuelCapacity.Main`), so it is known only after a login
or a change of ship; the current fuel is in `Status.json` (`Fuel.FuelMain`), which EDMC passes on about once a second in flight; the
plotted star is the `FSDTarget` event's `StarClass`. The journal does not say what a jump will cost in fuel, so WNTB cannot tell
whether the fuel on board is enough for the next jump: it compares percentages only, and says so. Nothing here touches Tk or the
overlay."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, List, Mapping, Optional, Tuple

SCOOPABLE_CLASSES = frozenset("OBAFGKM")

DEFAULT_LOW_PERCENT = 25
DEFAULT_UNSCOOPABLE_PERCENT = 50
PERCENT_RANGE = (5, 95)

# Status.json Flags (edmc_data.py in EDMarketConnector).
FLAG_DOCKED = 1 << 0
FLAG_LANDED = 1 << 1
FLAG_SCOOPING = 1 << 11
FLAG_LOW_FUEL = 1 << 19     # the game's own warning, set at 25 %
FLAG_IN_MAIN_SHIP = 1 << 24

# Events after which a plotted destination no longer applies.
_TARGET_ENDS = ("FSDJump", "Location", "LoadGame", "StartUp", "Docked", "CarrierJump", "Shutdown")

SEVERITY_LOW = "low"                 # shown in red
SEVERITY_UNSCOOPABLE = "unscoopable"  # shown in amber


@dataclass(frozen=True)
class FuelAlert:
    kind: str                  # "low" or "unscoopable"
    lines: Tuple[str, ...]     # short lines for the display, none longer than a card line

    @property
    def text(self) -> str:
        return " ".join(self.lines)


def is_scoopable(star_class: Optional[str]) -> bool:
    return star_class in SCOOPABLE_CLASSES


def star_description(star_class: str) -> str:
    """A short name for a star class the journal gives, for the warning text."""
    if star_class == "N":
        return "neutron star"
    if star_class == "H":
        return "black hole"
    if star_class.startswith("D"):
        return "white dwarf"
    if star_class.startswith("W"):
        return "Wolf-Rayet star"
    if star_class.startswith("C") or star_class == "MS" or star_class == "S":
        return "carbon or S-type star"
    if star_class in ("TTS", "AeBe"):
        return "protostar"
    if star_class in ("T", "L", "Y"):
        return "brown dwarf"
    return f"class {star_class} star"


def clamp_percent(value: Any, default: int) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        return default
    return max(PERCENT_RANGE[0], min(PERCENT_RANGE[1], number))


class FuelWatcher:
    def __init__(self) -> None:
        self.capacity: Optional[float] = None      # main tank, tonnes
        self.fuel: Optional[float] = None          # main tank now, tonnes
        self.flags: int = 0
        self.target_class: Optional[str] = None
        self.target_name: str = ""

    def handle_event(self, entry: Mapping[str, Any]) -> None:
        event = entry.get("event")
        if event == "Loadout":
            capacity = (entry.get("FuelCapacity") or {}).get("Main") if isinstance(entry.get("FuelCapacity"), Mapping) else None
            if isinstance(capacity, (int, float)) and capacity > 0:
                self.capacity = float(capacity)
        elif event == "FSDTarget":
            star = entry.get("StarClass")
            self.target_class = star if isinstance(star, str) and star else None
            self.target_name = str(entry.get("Name") or "")
        elif event in _TARGET_ENDS:
            self.target_class, self.target_name = None, ""

    def handle_status(self, entry: Mapping[str, Any]) -> None:
        flags = entry.get("Flags")
        self.flags = flags if isinstance(flags, int) else 0
        fuel = entry.get("Fuel")
        main = fuel.get("FuelMain") if isinstance(fuel, Mapping) else None
        self.fuel = float(main) if isinstance(main, (int, float)) else None

    def percent(self) -> Optional[float]:
        if self.fuel is None or not self.capacity:
            return None
        return max(0.0, min(100.0, self.fuel / self.capacity * 100))

    def _in_flight(self) -> bool:
        """In the main ship and neither docked nor landed: the only time a fuel warning is any use."""
        return bool(self.flags & FLAG_IN_MAIN_SHIP) and not self.flags & (FLAG_DOCKED | FLAG_LANDED)

    def alerts(self, low_percent: int = DEFAULT_LOW_PERCENT, unscoopable_percent: int = DEFAULT_UNSCOOPABLE_PERCENT,
               low: bool = True, unscoopable: bool = True) -> List[FuelAlert]:
        if self.fuel is None or not self._in_flight() or self.flags & FLAG_SCOOPING:
            return []
        percent = self.percent()
        found: List[FuelAlert] = []
        shown = f"{percent:.0f}% ({self.fuel:.1f} t)" if percent is not None else f"{self.fuel:.1f} t"
        if low and ((percent is not None and percent <= low_percent) or (percent is None and self.flags & FLAG_LOW_FUEL)):
            found.append(FuelAlert("low", ("Low fuel", f"Tank {shown}" if percent is not None else f"Tank {shown}, under 25%")))
        if (unscoopable and percent is not None and self.target_class and not is_scoopable(self.target_class)
                and percent <= unscoopable_percent):
            found.append(FuelAlert("unscoopable", ("No scoop at next star", f"({star_description(self.target_class)})", f"Fuel {shown}")))
        return found
