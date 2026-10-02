"""
Opt-in lookup against Spansh's (https://spansh.co.uk) body-search API to
find nearby rings with a confirmed hotspot for a given commodity - "where
do I go next" once the current ring's worth is exhausted. Gated behind
the "Spansh Nearby Hotspot Finder" setting (default off, like WNTB's own
shared updater) - a real outbound network call unlike anything else
Mining mode does by default.

Spansh doesn't publish this endpoint's request shape (major API calls
are still undocumented as of this port). The shape used below was
confirmed empirically: reverse-engineered from a live `POST
/api/bodies/search` call, then cross-checked against a working
open-source caller (RatherRude/Elite-Dangerous-AI-Integration's
`actions_web.py`, which builds the identical `ring_signals`/`distance`
filter shape) before trusting it. If Spansh ever changes this endpoint,
this is the one place to fix.

Also wraps Spansh's `/api/stations/search` endpoint
(search_best_price_stations()) - a best-price station finder, built as
the replacement for an originally-planned Inara commodity-lookup feature
once it turned out Inara's API has no commodity/market endpoint at all
(confirmed against Inara's own API docs - its events are almost entirely
write-only commander-profile-sync). This endpoint's shape was confirmed
the same way as bodies/search: reverse-engineered from a live call,
cross-checked against the same `actions_web.py`'s `station_finder`.

Uses only the standard library (`urllib`) rather than `requests` - this
is a deliberate choice, since there's no shared Spansh client elsewhere
in WNTB to unify with.
"""
from __future__ import annotations

import json
import urllib.request
from dataclasses import dataclass

from . import http_identity

BODIES_SEARCH_URL = "https://spansh.co.uk/api/bodies/search"
STATIONS_SEARCH_URL = "https://spansh.co.uk/api/stations/search"
REQUEST_TIMEOUT_S = 20
_USER_AGENT = http_identity.user_agent("mining-finder")

KNOWN_RING_HOTSPOT_MATERIALS: tuple[str, ...] = tuple(sorted([
    "Alexandrite", "Bauxite", "Benitoite", "Bromellite", "Cobalt", "Coltan",
    "Gallite", "Grandidierite", "Indite", "Lepidolite", "Lithium Hydroxide",
    "Low Temperature Diamonds", "Methane Clathrate", "Monazite", "Musgravite",
    "Painite", "Platinum", "Rhodplumsite", "Rutile", "Samarium", "Serendibite",
    "Tritium", "Uraninite", "Void Opals",
]))
"""Every commodity confirmed (empirically - see module docstring) to
actually return matches from Spansh's `ring_signals` filter, out of the
full ~65-entry EDCD commodity list tested against it. Common ring metals
that are NOT ring-hotspot materials in-game - Gold, Silver, Palladium,
Osmium among them - correctly returned zero matches even at a 5000 ly
radius, so their absence here isn't a gap in testing. Used to populate
mining_hotspot_finder_dialog.py's material dropdown; the field stays
editable rather than locked to this list, since Spansh or the game
itself could add another hotspot material later.

"Void Opals" (plural, matching mining_methods.py and the journal's own
Type_Localised convention) is the one display name that doesn't match
Spansh's own field value ("Void Opal", singular) - see
_to_spansh_material_name()."""

_DISPLAY_TO_SPANSH_NAME = {
    "Void Opals": "Void Opal",
}


def _to_spansh_material_name(material: str) -> str:
    return _DISPLAY_TO_SPANSH_NAME.get(material, material)


KNOWN_MINING_COMMODITIES: tuple[str, ...] = tuple(sorted(set(KNOWN_RING_HOTSPOT_MATERIALS) | {
    "Gold", "Silver", "Palladium", "Osmium",
}))
"""KNOWN_RING_HOTSPOT_MATERIALS plus the common ring metals this module's
own docstring notes are NOT ring-hotspot materials (Gold, Silver,
Palladium, Osmium) but are still commonly ship-mined and worth a price
check. Prepopulates mining_price_finder_dialog.py's commodity dropdown
(merged with whatever the current run has actually refined) and anchors
_normalize_commodity_name()'s case-insensitive matching below - not
exhaustive of every tradeable commodity in the game, just the ones
Mining mode's own pages are likely to have just refined."""


def _normalize_commodity_name(commodity: str) -> str:
    """Matches `commodity` case-insensitively against
    KNOWN_MINING_COMMODITIES, returning the correctly-cased canonical
    name if found (the price finder's commodity search is deliberately
    not case-sensitive; the response-side filtering in
    search_best_price_stations() below already compares case-
    insensitively, so this specifically guards the outgoing request's
    filter instead). Falls back to `.title()` (matches the in-game
    casing convention for the large majority of commodity names) for
    anything not in the known list, rather than sending whatever case
    the commander happened to type straight through."""
    query = commodity.strip().casefold()
    for name in KNOWN_MINING_COMMODITIES:
        if name.casefold() == query:
            return name
    return commodity.strip().title()


@dataclass
class RingHotspot:
    """One ring (not body - a body can have more than one ring, and only
    some may carry the requested material) confirmed by Spansh to have at
    least one hotspot for the searched material."""
    system: str
    body: str
    ring_name: str
    distance_ly: float
    distance_to_arrival_ls: float
    reserve_level: str
    hotspot_count: int


def search_ring_hotspots(reference_system: str, material: str,
                         max_distance_ly: float, max_results: int = 10) -> list[RingHotspot]:
    """Queries Spansh for the nearest rings to `reference_system` with a
    confirmed `material` hotspot, closest first. Raises on any network/
    parse failure - this is a synchronous, blocking call (real network
    I/O), so callers must run it off the Tk main thread and catch
    exceptions themselves (see mining_hotspot_finder_dialog.py) rather
    than this module swallowing them, since there's no sensible fallback
    value for "the search failed" other than telling the commander why."""
    spansh_material = _to_spansh_material_name(material)
    request_body = {
        "filters": {
            "distance": {"min": "0", "max": str(max_distance_ly)},
            "ring_signals": [
                {"name": spansh_material, "value": [1, 99], "comparison": "<=>"},
            ],
        },
        "sort": [{"distance": {"direction": "asc"}}],
        "size": max_results,
        "page": 0,
        "reference_system": reference_system,
    }
    request = urllib.request.Request(
        BODIES_SEARCH_URL,
        data=json.dumps(request_body).encode("utf8"),
        headers={"User-Agent": _USER_AGENT, "Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT_S) as response:
        data = json.loads(response.read().decode("utf-8"))

    results: list[RingHotspot] = []
    for body in data.get("results", []):
        for ring in body.get("rings") or []:
            signals = ring.get("signals") or []
            count = next((s.get("count", 0) for s in signals
                         if str(s.get("name", "")).casefold() == spansh_material.casefold()), 0)
            if count > 0:
                results.append(RingHotspot(
                    system=body.get("system_name", "?"),
                    body=body.get("name", "?"),
                    ring_name=ring.get("name", "?"),
                    distance_ly=body.get("distance", 0.0),
                    distance_to_arrival_ls=body.get("distance_to_arrival", 0.0),
                    reserve_level=body.get("reserve_level") or "Unknown",
                    hotspot_count=count,
                ))
    return results


@dataclass
class StationPrice:
    """One station Spansh confirms trades `commodity`, closest first
    unless sorted by price. `price`/`quantity` mean sell_price/demand for
    a Sell search (where the commander sells to the station) or buy_price/
    supply for a Buy search (where the commander buys from the station) -
    see search_best_price_stations()."""
    station: str
    system: str
    station_type: str
    distance_ly: float
    distance_to_arrival_ls: float
    is_planetary: bool
    price: int
    quantity: int


_MARKET_DAYS_OLD_DEFAULT = 30
"""Excludes stale market snapshots - confirmed empirically that a query
with no freshness filter returned Fleet Carrier markets over 5 years old
ranked ahead of active stations (carriers can sit indefinitely without
anyone updating their market), which would recommend a station that's
since moved or stopped trading."""


def search_best_price_stations(reference_system: str, commodity: str, transaction: str,
                               max_distance_ly: float, max_results: int = 10,
                               market_days_old: int = _MARKET_DAYS_OLD_DEFAULT) -> list[StationPrice]:
    """Queries Spansh for the best-price stations trading `commodity`
    within `max_distance_ly` of `reference_system`. `transaction` is
    "Sell" (commander sells to the station - sorted by highest sell
    price) or "Buy" (commander buys from the station - sorted by lowest
    buy price); anything else raises ValueError. Raises on any network/
    parse failure - synchronous, blocking call, same calling convention
    as search_ring_hotspots()."""
    if transaction not in ("Sell", "Buy"):
        raise ValueError('transaction must be "Sell" or "Buy"')

    commodity = _normalize_commodity_name(commodity)
    market_filter: dict = {"name": commodity}
    if transaction == "Sell":
        market_filter["demand"] = {"value": ["1", "999999999"], "comparison": "<=>"}
        sort_object = {"market_sell_price": [{"name": commodity, "direction": "desc"}]}
    else:
        market_filter["supply"] = {"value": ["1", "999999999"], "comparison": "<=>"}
        sort_object = {"market_buy_price": [{"name": commodity, "direction": "asc"}]}

    request_body = {
        "filters": {
            "distance": {"min": "0", "max": str(max_distance_ly)},
            "market_updated_at": {"comparison": "<=>", "value": [f"now-{market_days_old}d", "now"]},
            "market": [market_filter],
        },
        "sort": [sort_object],
        "size": max_results,
        "page": 0,
        "reference_system": reference_system,
    }
    request = urllib.request.Request(
        STATIONS_SEARCH_URL,
        data=json.dumps(request_body).encode("utf8"),
        headers={"User-Agent": _USER_AGENT, "Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT_S) as response:
        data = json.loads(response.read().decode("utf-8"))

    results: list[StationPrice] = []
    for station in data.get("results", []):
        # Spansh's own filter only restricts which stations match, not
        # which commodities come back per station - the response's
        # "market" is that station's *entire* market, so the specific
        # commodity searched for still has to be picked out here
        # (confirmed empirically, cross-checked against
        # actions_web.py's filter_station_response doing the same
        # client-side filtering).
        entry = next((c for c in station.get("market") or []
                     if str(c.get("commodity", "")).casefold() == commodity.casefold()), None)
        if entry is None:
            continue
        price = entry.get("sell_price", 0) if transaction == "Sell" else entry.get("buy_price", 0)
        quantity = entry.get("demand", 0) if transaction == "Sell" else entry.get("supply", 0)
        if price <= 0:
            continue
        results.append(StationPrice(
            station=station.get("name", "?"),
            system=station.get("system_name", "?"),
            station_type=station.get("type") or "?",
            distance_ly=station.get("distance", 0.0),
            distance_to_arrival_ls=station.get("distance_to_arrival", 0.0),
            is_planetary=bool(station.get("is_planetary", False)),
            price=price,
            quantity=quantity,
        ))
    return results
