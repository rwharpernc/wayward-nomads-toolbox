"""
Surface Mining market research: which markets in a system buy what you could mine on its bodies.

Two pure steps, with the Spansh call (mining_spansh_client.search_system_stations) and the window
(mining_market_research_dialog.py) kept apart from them:

1. `plan` names the commodities worth checking for a system, each with the reason, from the commander's own records only:
   deposits saved in that system, and what the commander has recorded on the same kind of ground as the system's scanned
   bodies (mining_ground.OwnRates), plus any the commander adds by hand. There is deliberately no table of which commodity
   sits on which planet type behind it: the game does not publish one, and community testing says planet class is only a
   screening lead, not a rule. A system with no records yet therefore has nothing to suggest until the commander adds a
   commodity or saves a hotspot.
2. `match` takes the stations Spansh returned for the system and lists, per commodity, the markets that buy it, best price
   first.

No tkinter and no network; see tests/test_mining_market_research.py.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional, Sequence

from . import mining_depletion as depletion
from . import mining_ground
from . import mining_hotspots as hotspots
from . import trade_commodities

MAX_CANDIDATES = 12
"""The most commodities checked at once, so the answer stays readable."""


@dataclass(frozen=True)
class Candidate:
    name: str
    """The game's (and Spansh's) name for the commodity."""
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class Plan:
    candidates: tuple[Candidate, ...]
    skipped: tuple[str, ...] = ()
    """Materials that are not a commodity Spansh knows (a typo, or something typed as a note), left out."""


def _norm(text: str) -> str:
    return text.strip().casefold()


def split_names(text: str) -> list[str]:
    """A comma, semicolon or line separated list typed by the commander, without blanks."""
    return [part.strip() for part in text.replace(";", ",").replace("\n", ",").split(",") if part.strip()]


def plan(system: str, saved: Sequence[hotspots.Hotspot], grounds: Sequence[str],
         rates: mining_ground.OwnRates, extra: Sequence[str] = ()) -> Plan:
    """The commodities to check for `system`.

    `saved` is all of the commander's hotspots (only those in `system` count), `grounds` the ground keys of the system's
    scanned landable bodies, `rates` the commander's own rates and `extra` names typed by hand."""
    order: list[str] = []
    reasons: dict[str, list[str]] = {}
    skipped: list[str] = []

    def add(raw: str, reason: str) -> None:
        name = trade_commodities.resolve(raw)
        if name is None:
            if raw.strip() and raw.strip() not in skipped:
                skipped.append(raw.strip())
            return
        if name not in reasons:
            order.append(name)
            reasons[name] = []
        if reason not in reasons[name]:
            reasons[name].append(reason)

    here: dict[str, int] = {}
    labels: dict[str, str] = {}
    for spot in saved:
        if _norm(spot.system) == _norm(system) and spot.material.strip():
            key = _norm(spot.material)
            here[key] = here.get(key, 0) + 1
            labels.setdefault(key, spot.material.strip())
    for key in sorted(here, key=lambda k: (-here[k], k)):
        count = here[key]
        add(labels[key], f"{count} deposit{'s' if count != 1 else ''} saved in this system")

    ranked: list[tuple[float, str, str]] = []
    for ground in dict.fromkeys(grounds):
        size = rates.sample_size(ground)
        for rate in rates.rates(ground):
            ranked.append((rate.pct, rate.material,
                           f"{rate.pct:.0f}% of your {size} recorded deposit{'s' if size != 1 else ''} on "
                           f"this kind of ground ({mining_ground.label(ground).lower()})"))
    for _pct, material, reason in sorted(ranked, key=lambda r: (-r[0], r[1].casefold())):
        add(material, reason)

    for raw in extra:
        add(raw, "added by you")

    chosen = tuple(Candidate(name, tuple(reasons[name])) for name in order[:MAX_CANDIDATES])
    return Plan(chosen, tuple(skipped))


@dataclass(frozen=True)
class Buyer:
    station: str
    station_type: str
    is_planetary: bool
    price: int
    demand: int
    updated: Optional[datetime]
    distance_ls: Optional[float]
    large_pads: Optional[int]
    medium_pads: Optional[int]
    small_pads: Optional[int]

    def days_old(self, now: Optional[datetime] = None) -> Optional[int]:
        if self.updated is None:
            return None
        return max(0, ((now or datetime.now(timezone.utc)) - self.updated).days)


@dataclass(frozen=True)
class CommodityResult:
    candidate: Candidate
    buyers: tuple[Buyer, ...] = field(default_factory=tuple)
    """Markets that buy it, best price first; empty when none does."""


def _int(value: object) -> Optional[int]:
    return int(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else None


def match(candidates: Sequence[Candidate], stations: Sequence[dict]) -> list[CommodityResult]:
    """For each candidate, the stations whose market has it with demand and a sell price above zero, best price first.

    `stations` are Spansh station records, each with its whole `market` (that is what its station search returns)."""
    wanted = {c.name.casefold(): c.name for c in candidates}
    buyers: dict[str, list[Buyer]] = {c.name: [] for c in candidates}
    for station in stations:
        if not isinstance(station, dict):
            continue
        for entry in station.get("market") or []:
            name = wanted.get(str(entry.get("commodity", "")).casefold())
            price, demand = _int(entry.get("sell_price")), _int(entry.get("demand"))
            if name is None or not price or not demand or price <= 0 or demand <= 0:
                continue
            distance = station.get("distance_to_arrival")
            buyers[name].append(Buyer(
                station=str(station.get("name") or "?"), station_type=str(station.get("type") or "?"),
                is_planetary=bool(station.get("is_planetary", False)), price=price, demand=demand,
                updated=depletion.parse(station.get("market_updated_at")),
                distance_ls=float(distance) if isinstance(distance, (int, float)) else None,
                large_pads=_int(station.get("large_pads")), medium_pads=_int(station.get("medium_pads")),
                small_pads=_int(station.get("small_pads"))))
    return [CommodityResult(c, tuple(sorted(buyers[c.name], key=lambda b: (-b.price, b.station.casefold()))))
            for c in candidates]


def pad_text(buyer: Buyer) -> str:
    """"large pads", "medium pads", "small pads only" or "" when Spansh gave no counts."""
    if buyer.large_pads:
        return "large pads"
    if buyer.medium_pads:
        return "medium pads"
    if buyer.small_pads:
        return "small pads only"
    return ""
