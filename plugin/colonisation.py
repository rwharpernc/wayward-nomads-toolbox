"""Colonisation construction-site tracking for Field Ops - pure logic, no
EDMC imports (so it's unit-testable; see tests/test_colonisation.py).

Elite's colonisation (system claims, orbital/surface construction) is
supplied by hauling commodities to a *construction depot* - a "Primary
Port" construction site, a colonisation ship, or a planetary/orbital
build-in-progress. The journal gives us, per depot:

* `ColonisationConstructionDepot` - written when the commander docks at /
  opens the depot's market: the full, authoritative list of
  `ResourcesRequired` (`RequiredAmount`, `ProvidedAmount`, `Payment`),
  overall `ConstructionProgress` (0.0-1.0), and `ConstructionComplete` /
  `ConstructionFailed` flags.
* `ColonisationContribution` - written when the commander hands cargo
  over: `Contributions` of `{Name, Amount}`. Between depot refreshes this
  is how we keep `ProvidedAmount` current without re-docking.

The depot event carries no station/system name, only a `MarketID`, so the
panel supplies a best-effort name from the most recent `Docked` (see
colonisation_panel.py).

What this is for: the in-game depot screen shows "required vs. delivered"
only while you're docked there. Tracking it lets a hauler see, anywhere,
what's still outstanding at each site - and, against the cargo currently
in the hold, what still has to be sourced.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Mapping, Optional, Tuple

EVENT_DEPOT = "ColonisationConstructionDepot"
EVENT_CONTRIBUTION = "ColonisationContribution"

_NAME_KEY = re.compile(r"^\$?(.*?)(?:_name)?;?$", re.IGNORECASE)


def commodity_key(raw: Any) -> str:
    """Canonical comparison key for a commodity name: the journal writes
    `$steel_name;` in colonisation events but plain `steel` in
    Cargo.json/EDMC's `state["Cargo"]`, so both reduce to `steel`."""
    if not isinstance(raw, str):
        return ""
    match = _NAME_KEY.match(raw.strip())
    return (match.group(1) if match else raw).strip().casefold()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _as_int(value: Any) -> int:
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return 0


@dataclass
class Resource:
    key: str
    label: str
    required: int
    provided: int = 0
    payment: int = 0

    @property
    def remaining(self) -> int:
        return max(0, self.required - self.provided)


@dataclass
class Site:
    market_id: int
    name: str = ""
    system: str = ""
    progress: float = 0.0
    complete: bool = False
    failed: bool = False
    resources: List[Resource] = field(default_factory=list)
    updated: str = field(default_factory=_now_iso)
    journal_at: str = ""
    """Time of the newest journal event folded into this site; "" for a site saved before this was kept (its `updated`
    time stands in). An event is applied only if it is newer, so catching up never counts a delivery twice."""

    @property
    def remaining_total(self) -> int:
        return sum(r.remaining for r in self.resources)

    @property
    def active(self) -> bool:
        return not (self.complete or self.failed)

    def display_name(self) -> str:
        return self.name or f"Construction site {self.market_id}"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "market_id": self.market_id, "name": self.name, "system": self.system,
            "progress": self.progress, "complete": self.complete, "failed": self.failed,
            "updated": self.updated, "journal_at": self.journal_at,
            "resources": [
                {"key": r.key, "label": r.label, "required": r.required,
                 "provided": r.provided, "payment": r.payment}
                for r in self.resources
            ],
        }

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> "Site":
        return cls(
            market_id=_as_int(raw.get("market_id")),
            name=str(raw.get("name") or ""),
            system=str(raw.get("system") or ""),
            progress=float(raw.get("progress") or 0.0),
            complete=bool(raw.get("complete")),
            failed=bool(raw.get("failed")),
            updated=str(raw.get("updated") or _now_iso()),
            journal_at=str(raw.get("journal_at") or ""),
            resources=[
                Resource(
                    key=str(r.get("key") or ""), label=str(r.get("label") or ""),
                    required=_as_int(r.get("required")), provided=_as_int(r.get("provided")),
                    payment=_as_int(r.get("payment")),
                )
                for r in raw.get("resources", []) if isinstance(r, Mapping)
            ],
        )


def _parse_time(value: Any) -> Optional[datetime]:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def event_time(entry: Mapping[str, Any]) -> Optional[datetime]:
    return _parse_time(entry.get("timestamp"))


def site_watermark(site: Site) -> Optional[datetime]:
    """How far the journal has been folded into `site`: its `journal_at`, else when it was last updated."""
    return _parse_time(site.journal_at) or _parse_time(site.updated)


def is_newer(site: Site, entry: Mapping[str, Any], inclusive: bool) -> bool:
    """Should this journal event be applied to `site`? Yes if it is newer than what the site has seen (a depot
    snapshot, which replaces the figures, is also applied at the very same time). An event with no usable time is
    applied, as before."""
    when, mark = event_time(entry), site_watermark(site)
    if when is None or mark is None:
        return True
    return when >= mark if inclusive else when > mark


def apply_depot_event(entry: Mapping[str, Any], existing: Optional[Site],
                      name: str = "", system: str = "") -> Optional[Site]:
    """Build/refresh a Site from a `ColonisationConstructionDepot` entry
    (the authoritative snapshot - replaces the resource list wholesale).
    Returns None when the entry has no usable MarketID. `name`/`system`
    only fill blanks: an already-known name is never overwritten by a
    guess from an unrelated `Docked`."""
    market_id = _as_int(entry.get("MarketID"))
    if not market_id:
        return None
    site = existing or Site(market_id=market_id)
    if name and not site.name:
        site.name = name
    if system and not site.system:
        site.system = system
    try:
        site.progress = min(1.0, max(0.0, float(entry.get("ConstructionProgress") or 0.0)))
    except (TypeError, ValueError):
        site.progress = 0.0
    site.complete = bool(entry.get("ConstructionComplete"))
    site.failed = bool(entry.get("ConstructionFailed"))
    resources = []
    for raw in entry.get("ResourcesRequired") or []:
        if not isinstance(raw, Mapping):
            continue
        key = commodity_key(raw.get("Name"))
        if not key:
            continue
        resources.append(Resource(
            key=key,
            label=str(raw.get("Name_Localised") or key.replace("_", " ").title()),
            required=_as_int(raw.get("RequiredAmount")),
            provided=min(_as_int(raw.get("ProvidedAmount")), _as_int(raw.get("RequiredAmount"))),
            payment=_as_int(raw.get("Payment")),
        ))
    site.resources = resources
    site.updated = _now_iso()
    site.journal_at = str(entry.get("timestamp") or site.journal_at)
    return site


def apply_contribution(site: Site, entry: Mapping[str, Any]) -> bool:
    """Add a `ColonisationContribution`'s amounts to the matching
    resources' `provided` (clamped to `required`). True if anything
    changed - a contribution for a commodity the depot doesn't list is
    ignored rather than inventing a row for it."""
    changed = False
    for raw in entry.get("Contributions") or []:
        if not isinstance(raw, Mapping):
            continue
        key = commodity_key(raw.get("Name"))
        amount = _as_int(raw.get("Amount"))
        if not key or not amount:
            continue
        for resource in site.resources:
            if resource.key == key:
                new_provided = min(resource.required, resource.provided + amount)
                if new_provided != resource.provided:
                    resource.provided = new_provided
                    changed = True
                break
    if changed:
        site.updated = _now_iso()
    site.journal_at = str(entry.get("timestamp") or site.journal_at)
    return changed


def cargo_by_key(cargo: Any) -> Dict[str, int]:
    """EDMC's `state["Cargo"]` ({name: count}) re-keyed by commodity_key,
    so it lines up with Resource.key regardless of `$..._name;` decoration."""
    if not isinstance(cargo, Mapping):
        return {}
    totals: Dict[str, int] = {}
    for name, count in cargo.items():
        key = commodity_key(name)
        if key:
            totals[key] = totals.get(key, 0) + _as_int(count)
    return totals


def still_to_source(resource: Resource, cargo: Mapping[str, int]) -> int:
    """Tonnage still to be bought/mined once what's already in the hold is
    counted against the outstanding amount."""
    return max(0, resource.remaining - cargo.get(resource.key, 0))


def shopping_list(site: Site, cargo: Optional[Mapping[str, int]] = None) -> List[Tuple[str, int]]:
    """(label, tonnes) for every commodity still needed, biggest first.
    With `cargo`, subtracts what's already aboard (the "still to source"
    view); without, the full outstanding amount."""
    rows = []
    for resource in site.resources:
        amount = still_to_source(resource, cargo) if cargo is not None else resource.remaining
        if amount > 0:
            rows.append((resource.label, amount))
    return sorted(rows, key=lambda row: (-row[1], row[0].casefold()))
