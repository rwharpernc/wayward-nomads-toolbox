"""What the Colonisation Sites window shows for one site: the commodity rows after the commander's filters, and the
totals under them. Pure functions with no Tk, so the filtering and the arithmetic are tested on their own and the
window only draws the result."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import List, Mapping, Optional

from .colonisation import Site, still_to_source


STATE_SHORT = "short"      # still working on it
STATE_ENOUGH = "enough"    # the hold plus the fleet carrier covers what the site still needs, exactly or with room
STATE_OVER = "over"        # the hold plus the fleet carrier is more than the site still needs


@dataclass(frozen=True)
class CommodityRow:
    key: str
    label: str
    required: int
    delivered: int
    remaining: int
    in_cargo: int
    to_source: int       # remaining less what the hold already carries
    on_carrier: int      # tonnes moved onto the commander's fleet carrier (0 when none)

    @property
    def stock(self) -> int:
        """Tonnes the commander already has for this commodity: in the hold plus moved onto the fleet carrier."""
        return self.in_cargo + self.on_carrier

    @property
    def state(self) -> str:
        if self.stock > self.remaining:
            return STATE_OVER
        return STATE_ENOUGH if self.stock >= self.remaining else STATE_SHORT

    @property
    def covered(self) -> bool:
        """The hold plus the fleet carrier already cover what the site still needs (exactly or more)."""
        return self.state != STATE_SHORT


@dataclass(frozen=True)
class Totals:
    remaining: int       # tonnes the site still needs
    to_source: int       # of that, tonnes not yet in the hold
    in_hold: int         # tonnes of needed commodities already in the hold (capped at what is needed)
    lines: int           # commodities still needed
    covered: int         # of those, how many the hold plus the fleet carrier already cover
    trips: int           # trips of the current ship to deliver everything still `remaining` (0 when its capacity is unknown)


def commodity_rows(site: Site, cargo: Mapping[str, int], carrier: Optional[Mapping[str, int]] = None,
                   hide_covered: bool = False, text: str = "") -> List[CommodityRow]:
    """The site's outstanding commodities, alphabetical (so rows stay put while numbers change), less any the
    filters take out: `hide_covered` drops those the hold plus the carrier already cover, `text` keeps labels containing it."""
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
            to_source=still_to_source(resource, cargo), on_carrier=carrier.get(resource.key, 0))
        if hide_covered and row.covered:
            continue
        rows.append(row)
    return sorted(rows, key=lambda r: r.label.casefold())


def totals(site: Site, cargo: Mapping[str, int], capacity: int = 0,
           carrier: Optional[Mapping[str, int]] = None) -> Totals:
    """The figures under the table, always for every outstanding commodity (not only those the filters leave)."""
    rows = commodity_rows(site, cargo, carrier)
    to_source = sum(r.to_source for r in rows)
    in_hold = sum(min(r.in_cargo, r.remaining) for r in rows)
    remaining = sum(r.remaining for r in rows)
    # Deliveries are what the trips count: the whole remaining need, a full hold at a time. What is already in the hold
    # is the start of the first load, so it is not taken off.
    trips = math.ceil(remaining / capacity) if capacity and capacity > 0 and remaining > 0 else 0
    return Totals(remaining=remaining, to_source=to_source, in_hold=in_hold,
                  lines=len(rows), covered=sum(1 for r in rows if r.covered), trips=trips)


def site_status(site: Site) -> str:
    """The one-word state shown beside a site: its progress, or complete / failed."""
    if site.complete:
        return "complete"
    if site.failed:
        return "failed"
    return f"{site.progress:.0%}"
