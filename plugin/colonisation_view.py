"""What the Colonisation Sites window shows for one site: the commodity rows after the commander's filters, and the
totals under them. Pure functions with no Tk, so the filtering and the arithmetic are tested on their own and the
window only draws the result."""

from __future__ import annotations

import math
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from typing import List, Mapping, Optional

from .colonisation import Site


STATE_SHORT = "short"      # still working on it
STATE_ENOUGH = "enough"    # the ship plus the fleet carrier covers what the site still needs, exactly or with room
STATE_OVER = "over"        # the ship plus the fleet carrier is more than the site still needs


@dataclass(frozen=True)
class CommodityRow:
    key: str
    label: str
    required: int
    delivered: int
    remaining: int
    in_cargo: int
    to_get: int          # remaining less what is in the ship and on the fleet carrier: still to buy or mine
    on_carrier: int      # tons moved onto the commander's fleet carrier (0 when none)
    trips: Optional[Decimal] = None   # trips of the current ship to deliver `remaining` (None when its capacity is unknown)

    @property
    def stock(self) -> int:
        """Tons the commander already has for this commodity: in the ship plus moved onto the fleet carrier."""
        return self.in_cargo + self.on_carrier

    @property
    def state(self) -> str:
        if self.stock > self.remaining:
            return STATE_OVER
        return STATE_ENOUGH if self.stock >= self.remaining else STATE_SHORT

    @property
    def covered(self) -> bool:
        """The ship plus the fleet carrier already cover what the site still needs (exactly or more)."""
        return self.state != STATE_SHORT


@dataclass(frozen=True)
class Totals:
    remaining: int       # tons the site still needs
    to_get: int          # of that, tons not yet in the ship or on the fleet carrier
    in_hold: int         # tons of needed commodities already in the ship (capped at what is needed)
    lines: int           # commodities still needed
    covered: int         # of those, how many the ship plus the fleet carrier already cover
    trips: int           # trips of the current ship to deliver everything still `remaining` (0 when its capacity is unknown)


def trips_for(tons: int, capacity: int) -> Optional[Decimal]:
    """How many loads of a ship that carries `capacity` tons `tons` takes, to two decimal places (half up, and at
    least 0.01 while anything is left, so a small remainder never reads as 0). None when the capacity is unknown."""
    if not capacity or capacity <= 0:
        return None
    if tons <= 0:
        return Decimal(0)
    trips = (Decimal(tons) / Decimal(capacity)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return max(trips, Decimal("0.01"))


def format_trips(trips: Optional[Decimal]) -> str:
    """`trips` as text with at most two decimals and no trailing zeros: 4, 1.5, 1.25, 1,234.57. A dash when unknown."""
    if trips is None:
        return "–"
    text = f"{trips:,f}"
    return text.rstrip("0").rstrip(".") if "." in text else text


def commodity_rows(site: Site, cargo: Mapping[str, int], carrier: Optional[Mapping[str, int]] = None,
                   hide_covered: bool = False, text: str = "", capacity: int = 0) -> List[CommodityRow]:
    """The site's outstanding commodities, alphabetical (so rows stay put while numbers change), less any the
    filters take out: `hide_covered` drops those the ship plus the carrier already cover, `text` keeps labels containing it."""
    wanted = text.strip().casefold()
    carrier = carrier or {}
    rows: List[CommodityRow] = []
    for resource in site.resources:
        if resource.remaining <= 0:
            continue
        if wanted and wanted not in resource.label.casefold():
            continue
        row = CommodityRow(
            key=resource.key, label=resource.label, required=resource.required, delivered=resource.provided,
            remaining=resource.remaining, in_cargo=cargo.get(resource.key, 0),
            to_get=max(0, resource.remaining - cargo.get(resource.key, 0) - carrier.get(resource.key, 0)),
            on_carrier=carrier.get(resource.key, 0), trips=trips_for(resource.remaining, capacity))
        if hide_covered and row.covered:
            continue
        rows.append(row)
    return sorted(rows, key=lambda r: r.label.casefold())


def totals(site: Site, cargo: Mapping[str, int], capacity: int = 0,
           carrier: Optional[Mapping[str, int]] = None) -> Totals:
    """The figures under the table, always for every outstanding commodity (not only those the filters leave)."""
    rows = commodity_rows(site, cargo, carrier)
    to_get = sum(r.to_get for r in rows)
    in_hold = sum(min(r.in_cargo, r.remaining) for r in rows)
    remaining = sum(r.remaining for r in rows)
    # Deliveries are what the trips count: the whole remaining need, a full ship at a time. What is already in the ship
    # is the start of the first load, so it is not taken off.
    trips = math.ceil(remaining / capacity) if capacity and capacity > 0 and remaining > 0 else 0
    return Totals(remaining=remaining, to_get=to_get, in_hold=in_hold,
                  lines=len(rows), covered=sum(1 for r in rows if r.covered), trips=trips)


def site_status(site: Site) -> str:
    """The one-word state shown beside a site: its progress, or complete / failed."""
    if site.complete:
        return "complete"
    if site.failed:
        return "failed"
    return f"{site.progress:.0%}"
