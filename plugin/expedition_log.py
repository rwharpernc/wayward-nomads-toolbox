"""Expedition Log: an archive of the commander's exploration expeditions, with what each one found and earned.

An **expedition** here is a stretch of exploring that the commander starts and stops: it has a name, a start and an end, where it began, the ships used, notes,
and totals worked out from the journal while it runs: for exploration the jumps and light-years, systems, bodies scanned, first discoveries, mapped bodies, the
exploration data sold and what the unsold scans are worth; for exobiology the samples, species analysed, first footfalls, what was sold and what the analysed
species are worth. It is separate from the Expedition planner (`expedition.py`), which plans stops to visit: the log records what happened, whether or not a
route was planned.

Every figure comes from journal events (`Tally.apply`), so a run can be **rescanned** (`rescan`): its totals are worked out again from the commander's own
journals between its start and its end, which fixes a run that missed events (EDMC was closed) and fills in one started by hand with an earlier date. A
commander's runs are kept per commander in `expedition_log.json` (`commander_data.py`) and never leave the computer.

What is exact and what is an estimate: credits **earned** are the totals the game reports when data is sold (`SellExplorationData`, `MultiSellExplorationData`,
`SellOrganicData`). The **unsold** figures are WNTB's estimate of what the scans and analysed species not yet sold are worth (the scan value formula, and the species'
value, five times that on a first footfall); selling clears them, since the game sells what you hold. Mapping bonuses are not estimated. Pure apart from the file:
no Tk, no EDMC beyond the logger.
"""

from __future__ import annotations

import logging
import os
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Dict, Iterable, List, Mapping, Optional

from . import commander_data, scan_value

try:
    from config import appname
except ImportError:   # unit tests outside EDMC
    appname = "EDMarketConnector"

plugin_name = os.path.basename(os.path.dirname(__file__))
logger = logging.getLogger(f"{appname}.{plugin_name}")

STATE_FILENAME = "expedition_log.json"
MAX_RUNS = 200
MAX_SEEN = 40_000             # bodies remembered per run so a body scanned twice is counted once
MAX_SYSTEMS = 6_000
MAX_SHIPS = 30
MAX_NOTES = 4_000
MAX_NAME = 80
SAVE_EVERY_S = 5.0
RUNNING, STOPPED = "running", "stopped"
FIRST_FOOTFALL_MULTIPLIER = 5

TOTAL_FIELDS = ("jumps", "light_years", "honks", "bodies_scanned", "stars", "planets", "first_discoveries", "mapped", "first_mapped", "terraformables",
                "earth_likes", "water_worlds", "ammonia_worlds", "landings", "codex_new", "explore_earned", "explore_estimated", "bio_samples",
                "bio_species", "bio_first_footfalls", "bio_earned", "bio_estimated")
_FLOAT_FIELDS = ("light_years",)

SALE_EVENTS = ("SellExplorationData", "MultiSellExplorationData", "SellOrganicData")
SCAN_EVENTS = ("FSDJump", "CarrierJump", "Location", "FSSDiscoveryScan", "Scan", "SAAScanComplete", "SellExplorationData", "MultiSellExplorationData",
               "ScanOrganic", "SellOrganicData", "CodexEntry", "Touchdown", "Loadout")


SHIP_NAMES = {
    "adder": "Adder", "anaconda": "Anaconda", "asp": "Asp Explorer", "asp_scout": "Asp Scout", "belugaliner": "Beluga Liner", "cobramkiii": "Cobra Mk III",
    "cobramkiv": "Cobra Mk IV", "cobramkv": "Cobra Mk V", "diamondback": "Diamondback Scout", "diamondbackxl": "Diamondback Explorer", "dolphin": "Dolphin",
    "eagle": "Eagle", "empire_courier": "Imperial Courier", "empire_eagle": "Imperial Eagle", "empire_trader": "Imperial Clipper", "federation_corvette": "Federal Corvette",
    "federation_dropship": "Federal Dropship", "federation_dropship_mkii": "Federal Assault Ship", "federation_gunship": "Federal Gunship", "ferdelance": "Fer-de-Lance",
    "hauler": "Hauler", "independant_trader": "Keelback", "independent_trader": "Keelback", "krait_light": "Krait Phantom", "krait_mkii": "Krait Mk II", "mamba": "Mamba",
    "orca": "Orca", "python": "Python", "python_nx": "Python Mk II", "sidewinder": "Sidewinder", "type6": "Type-6 Transporter", "type7": "Type-7 Transporter",
    "type8": "Type-8 Transporter", "type9": "Type-9 Heavy", "type9_military": "Type-10 Defender", "typex": "Alliance Chieftain", "typex_2": "Alliance Crusader",
    "typex_3": "Alliance Challenger", "viper": "Viper Mk III", "viper_mkiv": "Viper Mk IV", "vulture": "Vulture", "cutter": "Imperial Cutter", "explorer_nx": "Caspian Explorer",
}


def ship_label(entry: Mapping[str, Any]) -> str:
    """'Caspian Explorer 'Far Horizon' WN-01' from a Loadout (or LoadGame) event: the ship's name from the game, else the table above, else the key tidied; then its given
    name and ident. Empty when the event names no ship."""
    key = str(entry.get("Ship") or "")
    ship = clip(entry.get("Ship_Localised"), 40) or SHIP_NAMES.get(key.casefold()) or clip(key.replace("_", " ").title(), 40)
    if not ship:
        return ""
    name, ident = clip(entry.get("ShipName"), 40), clip(entry.get("ShipIdent"), 12)
    return ship + (f" '{name}'" if name else "") + (f" {ident}" if ident else "")


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_time(text: Any) -> Optional[float]:
    """A journal-style UTC time ('2026-10-16T11:30:44Z') or 'YYYY-MM-DD HH:MM' or 'YYYY-MM-DD' as seconds since the epoch, or None when it is not a date."""
    value = str(text or "").strip()
    if not value:
        return None
    for pattern in ("%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(value, pattern).replace(tzinfo=timezone.utc).timestamp()
        except ValueError:
            continue
    return None


def stamp(seconds: float) -> str:
    return datetime.fromtimestamp(seconds, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def clip(text: Any, limit: int) -> str:
    return " ".join(str(text or "").split())[:limit]


def credits(value: float) -> str:
    """'1,234,567' for a figure of credits."""
    return f"{int(round(value)):,}"


def short_credits(value: float) -> str:
    """'1.2M', '56k' or '900': a figure of credits for a narrow card."""
    value = int(round(value))
    if abs(value) >= 1_000_000:
        return f"{value / 1_000_000:.1f}M"
    if abs(value) >= 10_000:
        return f"{value / 1000:.0f}k"
    return f"{value:,}"


def duration_text(seconds: float) -> str:
    seconds = max(0, int(seconds))
    days, rest = divmod(seconds, 86_400)
    hours, rest = divmod(rest, 3_600)
    minutes = rest // 60
    if days:
        return f"{days}d {hours}h"
    return f"{hours}h {minutes:02d}m" if hours else f"{minutes}m"


@dataclass
class Totals:
    jumps: int = 0
    light_years: float = 0.0
    honks: int = 0
    bodies_scanned: int = 0
    stars: int = 0
    planets: int = 0
    first_discoveries: int = 0
    mapped: int = 0
    first_mapped: int = 0
    terraformables: int = 0
    earth_likes: int = 0
    water_worlds: int = 0
    ammonia_worlds: int = 0
    landings: int = 0
    codex_new: int = 0
    explore_earned: int = 0
    explore_estimated: int = 0
    bio_samples: int = 0
    bio_species: int = 0
    bio_first_footfalls: int = 0
    bio_earned: int = 0
    bio_estimated: int = 0

    @property
    def earned(self) -> int:
        return self.explore_earned + self.bio_earned

    @property
    def unsold(self) -> int:
        return self.explore_estimated + self.bio_estimated

    def to_raw(self) -> Dict[str, Any]:
        return {name: getattr(self, name) for name in TOTAL_FIELDS}

    @classmethod
    def from_raw(cls, raw: Any) -> "Totals":
        totals = cls()
        if isinstance(raw, Mapping):
            for name in TOTAL_FIELDS:
                value = raw.get(name)
                if isinstance(value, (int, float)) and not isinstance(value, bool) and value >= 0:
                    setattr(totals, name, float(value) if name in _FLOAT_FIELDS else int(value))
        return totals


@dataclass
class Run:
    id: str
    name: str
    status: str = STOPPED
    started: str = ""
    ended: str = ""
    start_system: str = ""
    end_system: str = ""
    ships: List[str] = field(default_factory=list)
    notes: str = ""
    totals: Totals = field(default_factory=Totals)
    systems: List[str] = field(default_factory=list)               # the systems visited, in order, without repeats
    seen: List[str] = field(default_factory=list)                   # "address:body" keys of the bodies counted
    mapped_seen: List[str] = field(default_factory=list)
    first_map: List[str] = field(default_factory=list)              # bodies scanned unmapped, so mapping one is a first
    footfall: List[str] = field(default_factory=list)               # bodies nobody had set foot on when scanned
    analysed: List[str] = field(default_factory=list)               # "body:species" analysed
    genera: List[str] = field(default_factory=list)
    planets: Dict[str, List[Any]] = field(default_factory=dict)     # "address:body" -> [class, mass, terraformable, was discovered, was mapped], to value a body when it is mapped
    rescanned: str = ""

    @property
    def system_count(self) -> int:
        return len(self.systems)

    def elapsed(self, now: Optional[float] = None) -> float:
        began = parse_time(self.started)
        end = parse_time(self.ended) if self.ended else (now if now is not None else time.time())
        return max(0.0, (end or 0.0) - began) if began is not None and end is not None else 0.0


def _add_unique(items: List[str], value: str, limit: int) -> bool:
    if not value or value in items:
        return False
    items.append(value)
    if len(items) > limit:
        del items[:len(items) - limit]
    return True


class Tally:
    """Adds journal events to a run's totals. `apply(entry)` returns True when the run changed. The same events in the same order always give the same totals,
    which is what makes `rescan` possible."""

    def __init__(self, run: Run) -> None:
        self.run = run

    def apply(self, entry: Mapping[str, Any]) -> bool:
        event = entry.get("event")
        handler = _HANDLERS.get(str(event))
        return bool(handler(self, entry)) if handler else False

    # --- travel -----------------------------------------------------------------------------------------------------
    def _arrival(self, entry: Mapping[str, Any]) -> bool:
        run, totals = self.run, self.run.totals
        name = clip(entry.get("StarSystem"), 80)
        changed = False
        if name:
            changed |= _add_unique(run.systems, name, MAX_SYSTEMS)
            if not run.start_system and not run.systems[:-1]:
                run.start_system = name
            run.end_system = name
        if entry.get("event") == "FSDJump":
            totals.jumps += 1
            distance = entry.get("JumpDist")
            if isinstance(distance, (int, float)) and distance > 0:
                totals.light_years += float(distance)
            changed = True
        return changed or bool(name)

    def _honk(self, entry: Mapping[str, Any]) -> bool:
        self.run.totals.honks += 1
        return True

    def _landing(self, entry: Mapping[str, Any]) -> bool:
        if entry.get("PlayerControlled") is False:
            return False
        self.run.totals.landings += 1
        return True

    def _loadout(self, entry: Mapping[str, Any]) -> bool:
        label = ship_label(entry)
        if not label or label in self.run.ships or len(self.run.ships) >= MAX_SHIPS:
            return False
        self.run.ships.append(label)
        return True

    # --- scans -------------------------------------------------------------------------------------------------------
    def _scan(self, entry: Mapping[str, Any]) -> bool:
        run, totals = self.run, self.run.totals
        body_id, address = entry.get("BodyID"), entry.get("SystemAddress")
        name = str(entry.get("BodyName") or "")
        planet, star = str(entry.get("PlanetClass") or ""), str(entry.get("StarType") or "")
        if not isinstance(body_id, int) or "belt cluster" in name.casefold() or (not planet and not star):
            return False
        key = f"{address}:{body_id}"
        if not _add_unique(run.seen, key, MAX_SEEN):
            return False
        totals.bodies_scanned += 1
        discovered = entry.get("WasDiscovered")
        if discovered is False:
            totals.first_discoveries += 1
        if planet:
            totals.planets += 1
            if str(entry.get("TerraformState") or "").casefold() == "terraformable":
                totals.terraformables += 1
            if planet == "Earthlike body":
                totals.earth_likes += 1
            elif planet == "Water world":
                totals.water_worlds += 1
            elif planet == "Ammonia world":
                totals.ammonia_worlds += 1
            if entry.get("WasMapped") is False:
                _add_unique(run.first_map, key, MAX_SEEN)
            if entry.get("WasFootfalled") is False and entry.get("Landable"):
                _add_unique(run.footfall, key, MAX_SEEN)
            mass = entry.get("MassEM")
            terraformable = str(entry.get("TerraformState") or "").casefold() == "terraformable"
            totals.explore_estimated += scan_value.estimate_planet_scan_value(
                planet, mass if isinstance(mass, (int, float)) else None, terraformable, discovered if isinstance(discovered, bool) else None)
            if len(run.planets) < MAX_SEEN:
                mapped_before = entry.get("WasMapped")
                run.planets[key] = [planet, float(mass) if isinstance(mass, (int, float)) else None, terraformable,
                                    discovered if isinstance(discovered, bool) else None, mapped_before if isinstance(mapped_before, bool) else None]
        else:
            totals.stars += 1
            solar = entry.get("StellarMass")
            totals.explore_estimated += scan_value.estimate_star_scan_value(solar if isinstance(solar, (int, float)) else None,
                                                                            discovered if isinstance(discovered, bool) else None, star)
        return True

    def _mapped(self, entry: Mapping[str, Any]) -> bool:
        run, totals = self.run, self.run.totals
        body_id = entry.get("BodyID")
        if not isinstance(body_id, int):
            return False
        key = f"{entry.get('SystemAddress')}:{body_id}"
        if not _add_unique(run.mapped_seen, key, MAX_SEEN):
            return False
        totals.mapped += 1
        if key in run.first_map:
            totals.first_mapped += 1
        known = run.planets.get(key)
        if known:                       # mapping pays more than the scan alone: the estimate becomes the mapped value
            efficient = isinstance(entry.get("ProbesUsed"), int) and isinstance(entry.get("EfficiencyTarget"), int) and entry["ProbesUsed"] <= entry["EfficiencyTarget"]
            scanned = scan_value.estimate_planet_scan_value(known[0], known[1], bool(known[2]), known[3])
            mapped = scan_value.estimate_planet_mapped_value(known[0], known[1], bool(known[2]), known[3], known[4], efficient)
            totals.explore_estimated += max(0, mapped - scanned)
        return True

    def _sold_exploration(self, entry: Mapping[str, Any]) -> bool:
        earned = entry.get("TotalEarnings")
        if not isinstance(earned, (int, float)) or earned < 0:
            return False
        self.run.totals.explore_earned += int(earned)
        self.run.totals.explore_estimated = 0
        return True

    def _codex(self, entry: Mapping[str, Any]) -> bool:
        if entry.get("IsNewEntry") is True:
            self.run.totals.codex_new += 1
            return True
        return False

    # --- exobiology --------------------------------------------------------------------------------------------------
    def _organic(self, entry: Mapping[str, Any]) -> bool:
        from . import organic_species_data as data
        run, totals = self.run, self.run.totals
        totals.bio_samples += 1
        if entry.get("ScanType") == "Analyse":
            key = f"{entry.get('SystemAddress')}:{entry.get('Body')}:{entry.get('Species')}"
            if _add_unique(run.analysed, key, MAX_SEEN):
                totals.bio_species += 1
                info = data.SPECIES.get(f"{entry.get('Genus')}|{entry.get('Species')}")
                value = info.value if info else 0
                first = f"{entry.get('SystemAddress')}:{entry.get('Body')}" in run.footfall
                if first:
                    totals.bio_first_footfalls += 1
                totals.bio_estimated += value * (FIRST_FOOTFALL_MULTIPLIER if first else 1)
                _add_unique(run.genera, clip(entry.get("Genus_Localised") or entry.get("Genus"), 40), 200)
        return True

    def _sold_organic(self, entry: Mapping[str, Any]) -> bool:
        total = 0
        for item in entry.get("BioData", []) if isinstance(entry.get("BioData"), list) else []:
            if isinstance(item, Mapping):
                for field_name in ("Value", "Bonus"):
                    value = item.get(field_name)
                    if isinstance(value, (int, float)) and value > 0:
                        total += int(value)
        self.run.totals.bio_earned += total
        self.run.totals.bio_estimated = 0
        return True


_HANDLERS: Dict[str, Callable[[Tally, Mapping[str, Any]], bool]] = {
    "FSDJump": Tally._arrival, "CarrierJump": Tally._arrival, "Location": Tally._arrival, "FSSDiscoveryScan": Tally._honk, "Scan": Tally._scan,
    "SAAScanComplete": Tally._mapped, "SellExplorationData": Tally._sold_exploration, "MultiSellExplorationData": Tally._sold_exploration,
    "ScanOrganic": Tally._organic, "SellOrganicData": Tally._sold_organic, "CodexEntry": Tally._codex, "Touchdown": Tally._landing, "Loadout": Tally._loadout,
}


# --- saving ---------------------------------------------------------------------------------------------------------------

def _list(value: Any, limit: int, text_limit: int = 200) -> List[str]:
    return [clip(v, text_limit) for v in value[:limit]] if isinstance(value, list) else []


def run_to_raw(run: Run) -> Dict[str, Any]:
    return {"id": run.id, "name": run.name, "status": run.status, "started": run.started, "ended": run.ended, "start_system": run.start_system,
            "end_system": run.end_system, "ships": run.ships, "notes": run.notes, "totals": run.totals.to_raw(), "systems": run.systems, "seen": run.seen,
            "mapped_seen": run.mapped_seen, "first_map": run.first_map, "footfall": run.footfall, "analysed": run.analysed, "genera": run.genera,
            "planets": run.planets, "rescanned": run.rescanned}


def run_from_raw(raw: Any) -> Optional[Run]:
    if not isinstance(raw, Mapping) or not isinstance(raw.get("id"), str) or not raw["id"]:
        return None
    return Run(
        id=raw["id"], name=clip(raw.get("name"), MAX_NAME) or "Expedition", status=RUNNING if raw.get("status") == RUNNING else STOPPED,
        started=clip(raw.get("started"), 30), ended=clip(raw.get("ended"), 30), start_system=clip(raw.get("start_system"), 80),
        end_system=clip(raw.get("end_system"), 80), ships=_list(raw.get("ships"), MAX_SHIPS, 90), notes=str(raw.get("notes") or "")[:MAX_NOTES],
        totals=Totals.from_raw(raw.get("totals")), systems=_list(raw.get("systems"), MAX_SYSTEMS, 80), seen=_list(raw.get("seen"), MAX_SEEN, 40),
        mapped_seen=_list(raw.get("mapped_seen"), MAX_SEEN, 40), first_map=_list(raw.get("first_map"), MAX_SEEN, 40),
        footfall=_list(raw.get("footfall"), MAX_SEEN, 40), analysed=_list(raw.get("analysed"), MAX_SEEN, 90), genera=_list(raw.get("genera"), 200, 40),
        planets={str(k): list(v)[:5] for k, v in list((raw.get("planets") or {}).items())[:MAX_SEEN] if isinstance(v, (list, tuple)) and len(v) == 5}
        if isinstance(raw.get("planets"), Mapping) else {}, rescanned=clip(raw.get("rescanned"), 30))


def _empty() -> Dict[str, Any]:
    return {"runs": []}


def _is_legacy(_raw: Any) -> bool:
    return False


class LogBook:
    """The commander's expeditions. `load(plugin_dir)` once at start-up and `set_commander(cmdr)` whenever the commander is known or changes. Changes the
    commander makes are written at once; the totals, which change with every scan, at most every few seconds (`flush()` writes what is waiting)."""

    def __init__(self, now: Callable[[], str] = _now, new_id: Callable[[], str] = lambda: uuid.uuid4().hex[:8],
                 clock: Callable[[], float] = time.monotonic) -> None:
        self._store = commander_data.new_store()
        self._plugin_dir: Optional[str] = None
        self._cmdr = ""
        self._now, self._new_id, self._clock = now, new_id, clock
        self._runs: List[Run] = []
        self._dirty = False
        self._saved_at = -SAVE_EVERY_S
        self._listeners: List[Callable[[], None]] = []

    # --- loading and saving ---------------------------------------------------------------------------------------
    def load(self, plugin_dir: str) -> None:
        self._plugin_dir = plugin_dir
        self._store = commander_data.read(os.path.join(plugin_dir, STATE_FILENAME), _is_legacy)
        self._reload()

    def set_commander(self, cmdr: str) -> bool:
        """True when this changed whose expeditions are showing."""
        cmdr = str(cmdr or "").strip()
        if not cmdr or commander_data.key_for(cmdr) == commander_data.key_for(self._cmdr):
            return False
        self.flush()
        self._cmdr = cmdr
        self._reload()
        return True

    def _reload(self) -> None:
        self._runs = []
        if self._cmdr:
            payload = commander_data.payload_for(self._store, self._cmdr, _empty)
            raw = payload.get("runs") if isinstance(payload, dict) else None
            seen = set()
            for item in raw if isinstance(raw, list) else []:
                run = run_from_raw(item)
                if run is not None and run.id not in seen and len(self._runs) < MAX_RUNS:
                    seen.add(run.id)
                    self._runs.append(run)
            for extra in [r for r in self._runs if r.status == RUNNING][1:]:        # only one runs at a time
                extra.status = STOPPED
        self._dirty = False
        self._changed()

    def _save(self, force: bool = True) -> None:
        self._dirty = True
        if not self._cmdr or self._plugin_dir is None:
            return
        if not force and self._clock() - self._saved_at < SAVE_EVERY_S:
            return
        commander_data.put(self._store, self._cmdr, {"runs": [run_to_raw(r) for r in self._runs]})
        commander_data.write(os.path.join(self._plugin_dir, STATE_FILENAME), self._store)
        self._dirty = False
        self._saved_at = self._clock()

    def flush(self) -> None:
        if self._dirty:
            self._save(force=True)

    def add_listener(self, callback: Callable[[], None]) -> None:
        self._listeners.append(callback)

    def remove_listener(self, callback: Callable[[], None]) -> None:
        if callback in self._listeners:
            self._listeners.remove(callback)

    def _changed(self) -> None:
        for callback in list(self._listeners):
            try:
                callback()
            except Exception:
                logger.exception("An expedition log listener failed")

    # --- reading ----------------------------------------------------------------------------------------------------
    @property
    def commander(self) -> str:
        return self._cmdr

    @property
    def ready(self) -> bool:
        return bool(self._cmdr)

    def runs(self) -> List[Run]:
        """Newest first."""
        return sorted(self._runs, key=lambda r: (parse_time(r.started) or 0.0, r.id), reverse=True)

    def get(self, run_id: Optional[str]) -> Optional[Run]:
        return next((r for r in self._runs if r.id == run_id), None) if run_id else None

    def running(self) -> Optional[Run]:
        return next((r for r in self._runs if r.status == RUNNING), None)

    def next_name(self) -> str:
        used = {r.name.casefold() for r in self._runs}
        number = len(self._runs) + 1
        while f"expedition {number}" in used:
            number += 1
        return f"Expedition {number}"

    # --- changing ---------------------------------------------------------------------------------------------------
    def start(self, name: str = "", system: str = "", ship: str = "") -> Optional[Run]:
        """Starts a new expedition now (stopping the one that is running). None when no commander is known yet."""
        if not self._cmdr:
            return None
        current = self.running()
        if current is not None:
            self._stop(current)
        run = Run(self._new_id(), clip(name, MAX_NAME) or self.next_name(), RUNNING, self._now(), start_system=clip(system, 80))
        if system:
            run.systems.append(clip(system, 80))
            run.end_system = run.start_system
        if ship:
            run.ships.append(clip(ship, 90))
        self._runs.append(run)
        if len(self._runs) > MAX_RUNS:
            oldest = sorted(self._runs, key=lambda r: parse_time(r.started) or 0.0)
            for old in [r for r in oldest if r.status != RUNNING][:len(self._runs) - MAX_RUNS]:
                self._runs.remove(old)
        self._save()
        self._changed()
        return run

    def _stop(self, run: Run) -> None:
        run.status = STOPPED
        run.ended = run.ended or self._now()

    def stop(self, run_id: Optional[str] = None) -> Optional[Run]:
        run = self.get(run_id) if run_id else self.running()
        if run is None:
            return None
        self._stop(run)
        self._save()
        self._changed()
        return run

    def resume(self, run_id: str) -> Optional[Run]:
        """Carries on counting an expedition that was stopped (its end is cleared); the one running is stopped."""
        run = self.get(run_id)
        if run is None:
            return None
        current = self.running()
        if current is not None and current is not run:
            self._stop(current)
        run.status, run.ended = RUNNING, ""
        self._save()
        self._changed()
        return run

    def reset(self, run_id: str) -> Optional[Run]:
        """Clears an expedition's totals and starts it counting again from now (its name, ships and notes stay)."""
        run = self.get(run_id)
        if run is None:
            return None
        keep = (run.id, run.name, run.ships, run.notes)
        fresh = Run(keep[0], keep[1], RUNNING, self._now(), ships=keep[2], notes=keep[3])
        current = self.running()
        if current is not None and current is not run:
            self._stop(current)
        self._runs[self._runs.index(run)] = fresh
        self._save()
        self._changed()
        return fresh

    def delete(self, run_id: str) -> bool:
        run = self.get(run_id)
        if run is None:
            return False
        self._runs.remove(run)
        self._save()
        self._changed()
        return True

    def update(self, run_id: str, **fields: Any) -> Optional[Run]:
        """Edits the details of an expedition: name, started, ended, start_system, end_system, ships (a list or text) and notes. Raises ValueError for a date
        that is not one or an end before the start."""
        run = self.get(run_id)
        if run is None:
            return None
        if "name" in fields:
            run.name = clip(fields["name"], MAX_NAME) or run.name
        started = parse_time(fields["started"]) if "started" in fields else parse_time(run.started)
        if "started" in fields and (started is None):
            raise ValueError("The start is not a date. Use 2026-10-16 or 2026-10-16 18:30 (UTC).")
        ended = parse_time(fields["ended"]) if fields.get("ended") else (parse_time(run.ended) if "ended" not in fields else None)
        if fields.get("ended") and ended is None:
            raise ValueError("The end is not a date. Use 2026-10-16 or 2026-10-16 18:30 (UTC), or leave it empty while it is running.")
        if started is not None and ended is not None and ended < started:
            raise ValueError("The end is before the start.")
        if "started" in fields and started is not None:
            run.started = stamp(started)
        if "ended" in fields:
            run.ended = stamp(ended) if ended is not None else ""
            if run.ended and run.status == RUNNING:
                run.status = STOPPED
        for field_name in ("start_system", "end_system"):
            if field_name in fields:
                setattr(run, field_name, clip(fields[field_name], 80))
        if "ships" in fields:
            raw = fields["ships"]
            parts = raw if isinstance(raw, list) else str(raw or "").replace("\n", ";").split(";")
            run.ships = [clip(p, 90) for p in parts if clip(p, 90)][:MAX_SHIPS]
        if "notes" in fields:
            run.notes = str(fields["notes"] or "")[:MAX_NOTES]
        self._save()
        self._changed()
        return run

    def replace_totals(self, run_id: str, rebuilt: Run) -> Optional[Run]:
        """Puts the totals and the lists a rescan worked out into an expedition; its name, dates and notes are kept, and any ships added by hand stay."""
        run = self.get(run_id)
        if run is None:
            return None
        run.totals, run.systems, run.seen, run.mapped_seen = rebuilt.totals, rebuilt.systems, rebuilt.seen, rebuilt.mapped_seen
        run.first_map, run.footfall, run.analysed, run.genera = rebuilt.first_map, rebuilt.footfall, rebuilt.analysed, rebuilt.genera
        run.planets = rebuilt.planets
        for ship in rebuilt.ships:
            if ship not in run.ships and len(run.ships) < MAX_SHIPS:
                run.ships.append(ship)
        if not run.start_system:
            run.start_system = rebuilt.start_system
        run.end_system = rebuilt.end_system or run.end_system
        run.rescanned = self._now()
        self._save()
        self._changed()
        return run

    def start_at(self, started: str, name: str = "", system: str = "", ship: str = "", rebuilt: Optional[Run] = None) -> Optional[Run]:
        """Starts a new expedition dated `started` (the one running is stopped) with the totals a rescan worked out for that date (`rebuilt`), so it carries on from what
        was already done. None when no commander is known yet."""
        run = self.start(name, system, ship)
        if run is None:
            return None
        run.started = stamp(parse_time(started) or time.time())
        if rebuilt is not None:
            self.replace_totals(run.id, rebuilt)
            if rebuilt.start_system:
                run.start_system = rebuilt.start_system
            for label in ([ship] if ship else []):
                if label and label not in run.ships:
                    run.ships.append(label)
        self._save()
        self._changed()
        return run

    # --- the journal -------------------------------------------------------------------------------------------------
    def apply(self, entry: Mapping[str, Any]) -> bool:
        """Feeds a journal event to the expedition that is running. True when it changed."""
        run = self.running()
        if run is None or str(entry.get("event")) not in _HANDLERS:
            return False
        if Tally(run).apply(entry):
            self._save(force=False)
            self._changed()
            return True
        return False


def rebuild(started: str, ended: str, events: Iterable[Mapping[str, Any]]) -> Run:
    """A run's totals worked out from journal events: those whose timestamp falls between `started` and `ended` (empty: now). The events must be in order."""
    run = Run("rebuilt", "rebuilt", started=started, ended=ended)
    begin = parse_time(started)
    end = parse_time(ended) if ended else None
    tally = Tally(run)
    for entry in events:
        when = parse_time(entry.get("timestamp"))
        if when is None or (begin is not None and when < begin) or (end is not None and when > end):
            continue
        tally.apply(entry)
    return run


def events_from_journals(commander: str, since: str, folder: Optional[str] = None) -> List[Dict[str, Any]]:
    """The commander's journal events of the kinds the log counts, oldest first, from the journals modified since `since` (a day of slack for a journal that was
    written to long after it began). Only that commander's journals are read: each begins with their LoadGame."""
    from . import journal_files
    pattern = journal_files.event_pattern(*SCAN_EVENTS, "LoadGame")
    began = parse_time(since)
    files = journal_files.files_modified_since((began - 86_400) if began is not None else 0.0, folder)
    wanted = commander_data.key_for(commander)
    found: List[Dict[str, Any]] = []
    for path in files:
        entries = list(journal_files.read_events(path, pattern))
        owner = next((commander_data.key_for(e.get("Commander")) for e in entries if e.get("event") == "LoadGame"), "")
        if wanted and owner and owner != wanted:
            continue
        found.extend(e for e in entries if e.get("event") != "LoadGame")
    return found


def rescan(run: Run, commander: str, folder: Optional[str] = None) -> Run:
    """The run's totals worked out again from the commander's journals between its start and its end (or now)."""
    return rebuild(run.started, run.ended, events_from_journals(commander, run.started, folder))


# --- how a run reads -------------------------------------------------------------------------------------------------------

def display_time(text: str) -> str:
    """'2026-10-16T11:30:44Z' as '2026-10-16 11:30' (UTC) for the window; empty stays empty."""
    seconds = parse_time(text)
    return datetime.fromtimestamp(seconds, tz=timezone.utc).strftime("%Y-%m-%d %H:%M") if seconds is not None else ""


def facts_lines(run: Run, now: Optional[float] = None) -> List[str]:
    """Everything a run recorded, in plain lines, for the window and for copying."""
    t = run.totals
    lines = [f"{run.name}  ({'running' if run.status == RUNNING else 'stopped'}, {duration_text(run.elapsed(now))})",
             f"Started {display_time(run.started) or '-'} UTC" + (f"   Ended {display_time(run.ended)} UTC" if run.ended else "")
             + (f"   From {run.start_system}" if run.start_system else "") + (f"   Now/last {run.end_system}" if run.end_system else ""),
             "",
             "EXPLORATION",
             f"  Systems visited {len(run.systems):,}   Jumps {t.jumps:,}   Distance {t.light_years:,.0f} ly   Honks {t.honks:,}",
             f"  Bodies scanned {t.bodies_scanned:,} ({t.first_discoveries:,} first discoveries)   Stars {t.stars:,}   Planets {t.planets:,}",
             f"  Earth-likes {t.earth_likes:,}   Water worlds {t.water_worlds:,}   Ammonia worlds {t.ammonia_worlds:,}   Terraformable {t.terraformables:,}",
             f"  Mapped {t.mapped:,} ({t.first_mapped:,} first)   Landings {t.landings:,}   New codex entries {t.codex_new:,}",
             f"  Earned (data sold) {credits(t.explore_earned)} cr   Unsold scans (estimate) {credits(t.explore_estimated)} cr",
             "",
             "EXOBIOLOGY",
             f"  Samples {t.bio_samples:,}   Species analysed {t.bio_species:,}   First footfalls {t.bio_first_footfalls:,}"
             + (f"   Genera: {', '.join(run.genera)}" if run.genera else ""),
             f"  Earned (sold) {credits(t.bio_earned)} cr   Unsold species (estimate) {credits(t.bio_estimated)} cr",
             "",
             f"TOTAL EARNED {credits(t.earned)} cr   Unsold (estimate) {credits(t.unsold)} cr"]
    if run.ships:
        lines.append("Ships: " + "; ".join(run.ships))
    if run.notes.strip():
        lines += ["", "Notes: " + run.notes.strip()]
    if run.rescanned:
        lines.append(f"Totals last worked out again from the journals {display_time(run.rescanned)} UTC.")
    return lines


CSV_HEADINGS = ("Name", "Status", "Started (UTC)", "Ended (UTC)", "Start location", "End location", "Ships", "Systems", "Jumps", "Light-years", "Honks",
                "Bodies scanned", "First discoveries", "Mapped", "First mapped", "Landings", "New codex entries", "Exploration earned (cr)",
                "Exploration unsold estimate (cr)", "Bio samples", "Species analysed", "First footfalls", "Exobiology earned (cr)", "Exobiology unsold estimate (cr)",
                "Total earned (cr)", "Notes")


def csv_rows(runs: Iterable[Run]) -> List[List[Any]]:
    """The archive as rows for a spreadsheet (headings first), one row for each expedition."""
    rows: List[List[Any]] = [list(CSV_HEADINGS)]
    for run in runs:
        t = run.totals
        rows.append([run.name, run.status, display_time(run.started), display_time(run.ended), run.start_system, run.end_system, "; ".join(run.ships),
                     len(run.systems), t.jumps, round(t.light_years, 1), t.honks, t.bodies_scanned, t.first_discoveries, t.mapped, t.first_mapped, t.landings,
                     t.codex_new, t.explore_earned, t.explore_estimated, t.bio_samples, t.bio_species, t.bio_first_footfalls, t.bio_earned, t.bio_estimated,
                     t.earned, run.notes.replace(chr(10), " ")])
    return rows


def since_last_sale(events: Iterable[Mapping[str, Any]]) -> Optional[str]:
    """Where an expedition that carries on from the data you are still holding begins: one second after the earlier of your last exploration sale and your last exobiology
    sale (the data you have not sold is what has been gathered since). If you have only ever sold one kind, that sale; None when you have sold nothing."""
    exploration = organic = None
    for entry in events:
        when = parse_time(entry.get("timestamp"))
        if when is None:
            continue
        event = entry.get("event")
        if event in ("SellExplorationData", "MultiSellExplorationData"):
            exploration = when if exploration is None else max(exploration, when)
        elif event == "SellOrganicData":
            organic = when if organic is None else max(organic, when)
    chosen = [t for t in (exploration, organic) if t is not None]
    return stamp(min(chosen) + 1) if chosen else None


def plan_since_last_sale(commander: str, folder: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """What starting an expedition from the last sale would be: its start and the totals the journals give since then. Reads the commander's journals and changes nothing,
    so it can run on a worker thread. None when the commander has never sold anything."""
    from . import journal_files
    pattern = journal_files.event_pattern(*SALE_EVENTS)
    wanted = commander_data.key_for(commander)
    sales: List[Dict[str, Any]] = []
    for path in journal_files.files_modified_since(0.0, folder):
        whole = list(journal_files.read_events(path, journal_files.event_pattern(*SALE_EVENTS, "LoadGame")))
        owner = next((commander_data.key_for(e.get("Commander")) for e in whole if e.get("event") == "LoadGame"), "")
        if wanted and owner and owner != wanted:
            continue
        sales.extend(e for e in whole if e.get("event") in SALE_EVENTS)
    started = since_last_sale(sales)
    if started is None:
        return None
    events = events_from_journals(commander, started, folder)
    return {"started": started, "rebuilt": rebuild(started, "", events)}
