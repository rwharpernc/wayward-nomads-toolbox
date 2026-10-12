"""
What a colonization build costs, so a planned build can be sized before any construction depot has been visited.

The journal only reports a depot's needs once you dock at it, but the cost of each kind of building is fixed by the game. The
table is `colonisation_costs.json`, bundled with WNTB: a copy of the community-compiled `colonization-costs2.json` (credits and
licence in THIRD-PARTY-NOTICES.md). It lists, for each kind of building, the tons of each commodity a build needs in all. It is
only as current as that table: the game can change costs.

Pure apart from reading the one bundled file (once).

A site's `buildType` is its layout's name in lower case with underscores (`no_truss`, `dual_truss`, `hermes`). A table entry names
one layout as its own `buildType` and lists the others it covers in `layouts`; a layout is matched to the entry that names it as
its own `buildType` first, else to the first entry that lists it.
"""
from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from typing import Any, Dict, List, Mapping, Optional, Tuple

try:
    from config import appname
except ImportError:      # unit tests outside EDMC
    appname = "EDMarketConnector"

from . import trade_commodities

plugin_name = os.path.basename(os.path.dirname(__file__))
logger = logging.getLogger(f"{appname}.{plugin_name}")

TABLE_FILE = "colonisation_costs.json"   # shipped reference data, read-only: never written, so not one of the update-protected data files


@dataclass(frozen=True)
class BuildCost:
    key: str                          # the entry's own build type
    name: str                         # the game's name for the building, e.g. "Satellite Installation"
    category: str
    tier: int
    location: str                     # "orbital" or "surface"
    cargo: Mapping[str, int]          # commodity key -> tons needed in all

    @property
    def total(self) -> int:
        return sum(self.cargo.values())

    def biggest(self, count: int = 5) -> List[Tuple[str, int]]:
        """The commodities needing the most tons, as (display name, tons), biggest first."""
        ranked = sorted(self.cargo.items(), key=lambda kv: (-kv[1], kv[0]))
        return [(commodity_label(key), tons) for key, tons in ranked if tons > 0][:count]


def commodity_label(key: str) -> str:
    """The game's display name for a commodity key ('liquidoxygen' -> 'Liquid Oxygen'); the key tidied up when it is not known."""
    return trade_commodities.resolve(key) or key.replace("_", " ").title()


def _normal(name: Any) -> str:
    return str(name or "").strip().lower().replace(" ", "_")


def _int(value: Any) -> int:
    return value if isinstance(value, int) and not isinstance(value, bool) and value > 0 else 0


def parse(data: Any) -> Dict[str, BuildCost]:
    """`{normalised layout name: BuildCost}` from the table's content; entries and layouts that make no sense are skipped."""
    if not isinstance(data, list):
        return {}
    entries: List[Tuple[BuildCost, List[str]]] = []
    for raw in data:
        if not isinstance(raw, dict) or not _normal(raw.get("buildType")):
            continue
        cargo = {str(k): _int(v) for k, v in (raw.get("cargo") or {}).items() if _int(v)} if isinstance(raw.get("cargo"), dict) else {}
        if not cargo:
            continue
        cost = BuildCost(key=_normal(raw["buildType"]), name=str(raw.get("displayName") or raw["buildType"]).strip(),
                         category=str(raw.get("category") or "").strip(), tier=_int(raw.get("tier")),
                         location=str(raw.get("location") or "").strip().lower(), cargo=cargo)
        layouts = raw.get("layouts")
        entries.append((cost, [_normal(x) for x in layouts] if isinstance(layouts, list) else []))
    table: Dict[str, BuildCost] = {cost.key: cost for cost, _layouts in entries}      # an entry's own type wins
    for cost, layouts in entries:
        for layout in layouts:
            if layout:
                table.setdefault(layout, cost)
    return table


_table: Optional[Dict[str, BuildCost]] = None


def table() -> Dict[str, BuildCost]:
    """The bundled table, read once. Empty (and logged) if the file is missing or damaged, so nothing breaks without it."""
    global _table
    if _table is None:
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)), TABLE_FILE)
        try:
            with open(path, "r", encoding="utf-8") as handle:
                _table = parse(json.load(handle))
        except (OSError, ValueError):
            logger.warning("Could not read the build cost table %s", path, exc_info=True)
            _table = {}
    return _table


def cost_for(build_type: Any) -> Optional[BuildCost]:
    """The cost of a building by its layout / build type name (case and spaces do not matter), or None if the table lacks it."""
    return table().get(_normal(build_type))
