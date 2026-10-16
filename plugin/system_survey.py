"""System survey: what is known about the bodies of the system the commander is in, from the journal, and what is left to do in it.

Fed by the events the game writes as a system is explored:

- `FSDJump`, `CarrierJump` and `Location` name the system (a new one starts a new survey; `StartJump` hides the old one while in hyperspace);
- `FSSDiscoveryScan` (the honk: how many bodies there are and how far the system scan has got), `FSSAllBodiesFound`;
- `Scan` (one body: its class or star type, mass, gravity, atmosphere, materials, and whether anyone had discovered or mapped it);
- `FSSBodySignals` and `SAASignalsFound` (biological and geological signal counts, and after mapping the genera present);
- `SAAScanComplete` (the body has been mapped) and `ScanOrganic` (a sample was logged, taken or analysed).

From that it answers the two questions of the System targets card: which scanned bodies are worth mapping and have not been (an estimated scan
value at or above a threshold, `to_map`), and which have life signals that have not all been analysed (`with_life`). The Body info card reads one
`Body` from it. Nothing is stored: a survey lasts as long as the commander is in the system, and `restore_from_journal` rebuilds it from the newest
journal when EDMC starts mid-system. No Tk, no overlay.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping, Optional, Tuple

try:
    from config import appname
except ImportError:   # unit tests outside EDMC
    appname = "EDMarketConnector"

plugin_name = os.path.basename(os.path.dirname(__file__))
logger = logging.getLogger(f"{appname}.{plugin_name}")

ARRIVALS = ("FSDJump", "CarrierJump", "Location")
SESSION_EVENTS = ("Fileheader", "Shutdown", "LoadGame", "Music", "Docked", "Undocked")     # when the cards may show, not what they say
EVENTS = ARRIVALS + SESSION_EVENTS + ("StartJump", "FSSDiscoveryScan", "FSSAllBodiesFound", "Scan", "FSSBodySignals", "SAASignalsFound", "SAAScanComplete", "ScanOrganic")
STANDARD_GRAVITY = 9.80665        # m/s^2 in one g
PASCALS_PER_ATMOSPHERE = 101325.0
BIO_TYPE, GEO_TYPE = "$SAA_SignalType_Biological;", "$SAA_SignalType_Geological;"
RESTORE_EVENT = "WNTBRestoreCommander"      # restore.RESTORE_EVENT, repeated here so this module stays free of the restore module's imports

# Short tags for the planet classes that matter most when choosing what to map.
CLASS_TAGS = {"Earthlike body": "ELW", "Water world": "WW", "Ammonia world": "AW", "High metal content body": "HMC", "Metal rich body": "MR"}


def credits_text(value: int) -> str:
    """`1,234,567` as `1.2M`, `56,000` as `56k`."""
    if value >= 1_000_000:
        return f"{value / 1_000_000:.1f}M"
    if value >= 1_000:
        return f"{value / 1_000:.0f}k"
    return str(value)


def _number(value: Any) -> Optional[float]:
    return float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else None


def _count(entry: Mapping[str, Any], signal_type: str) -> int:
    for item in entry.get("Signals") if isinstance(entry.get("Signals"), list) else []:
        if isinstance(item, Mapping) and item.get("Type") == signal_type and isinstance(item.get("Count"), int):
            return item["Count"]
    return 0


@dataclass
class Body:
    body_id: int
    name: str
    short: str = ""
    kind: str = ""                      # "planet", "star" or "" until a Scan has described it
    planet_class: str = ""
    star_type: str = ""
    terraformable: bool = False
    landable: bool = False
    was_discovered: Optional[bool] = None
    was_mapped: Optional[bool] = None
    mass_em: Optional[float] = None
    stellar_mass: Optional[float] = None
    gravity_g: Optional[float] = None
    pressure_atm: Optional[float] = None
    temperature_k: Optional[float] = None
    distance_ls: Optional[float] = None
    volcanism: str = ""
    atmosphere: str = ""
    materials: List[Tuple[str, float]] = field(default_factory=list)
    scanned: bool = False
    mapped: bool = False                # the commander has mapped it (SAAScanComplete)
    bio: int = 0
    geo: int = 0
    genuses: List[str] = field(default_factory=list)
    analysed: List[str] = field(default_factory=list)      # genera fully analysed (ScanOrganic "Analyse")
    sampling: str = ""                  # the genus last logged or sampled, until it is analysed

    def scan_value(self) -> int:
        """The estimated credits for scanning it, from `scan_value`'s formula (the same estimate the Exploration Value readout shows). 0 for a
        body not yet scanned."""
        if not self.scanned:
            return 0
        from . import scan_value as value
        if self.kind == "star":
            return value.estimate_star_scan_value(self.stellar_mass, self.was_discovered, self.star_type)
        return value.estimate_planet_scan_value(self.planet_class, self.mass_em, self.terraformable, self.was_discovered)

    @property
    def life_done(self) -> bool:
        return self.bio > 0 and len(set(self.analysed)) >= self.bio

    @property
    def tag(self) -> str:
        if self.terraformable and self.planet_class not in CLASS_TAGS:
            return "TF"
        return CLASS_TAGS.get(self.planet_class, "")


def short_name(name: str, system: str) -> str:
    """`Zunuae JA-A d995 3 b` in `Zunuae JA-A d995` as `3 b`; the primary star, which carries the system's name, as `Star`."""
    if system and name.casefold().startswith(system.casefold()):
        rest = name[len(system):].strip()
        return rest or "Star"
    return name


class SystemSurvey:
    def __init__(self) -> None:
        self.name = ""
        self.address: Optional[int] = None
        self.honked = False
        self.body_count = 0
        self.progress = 0.0
        self.fss_complete = False
        self.in_transit = False         # between systems: the survey of the last one is not shown
        self.playing = True             # False from the game closing or its main menu until a commander loads in again
        self.docked = False             # docked, or on a carrier: nothing to explore from here
        self.cmdr = ""                  # whose survey this is; another commander loading in clears it
        self.bodies: Dict[int, Body] = {}

    # --- events ----------------------------------------------------------------------------------------------------------
    def reset(self, name: str, address: Optional[int] = None) -> None:
        self.name, self.address = name, address
        self.honked, self.body_count, self.progress, self.fss_complete = False, 0, 0.0, False
        self.bodies = {}

    def handle_event(self, entry: Mapping[str, Any], system: str = "") -> bool:
        """Takes one journal event. True when something the cards show may have changed."""
        event = entry.get("event")
        if event not in EVENTS:
            return False
        if event in ARRIVALS:
            name = str(entry.get("StarSystem") or "").strip()
            if name and name.casefold() != self.name.casefold():
                self.reset(name, entry.get("SystemAddress") if isinstance(entry.get("SystemAddress"), int) else None)
            self.in_transit, self.playing, self.docked = False, True, bool(entry.get("Docked"))
            return True
        if event in SESSION_EVENTS:
            return self._session(entry, event)
        if event == "StartJump":
            self.in_transit = entry.get("JumpType") == "Hyperspace"
            return self.in_transit
        if not self.name and system:
            self.reset(system)
        if event == "FSSDiscoveryScan":
            count = entry.get("BodyCount")
            self.honked = True
            self.body_count = count if isinstance(count, int) and count >= 0 else self.body_count
            progress = _number(entry.get("Progress"))
            self.progress = progress if progress is not None else self.progress
            return True
        if event == "FSSAllBodiesFound":
            count = entry.get("Count")
            self.honked, self.fss_complete = True, True
            self.body_count = count if isinstance(count, int) and count >= 0 else self.body_count
            self.progress = 1.0
            return True
        body_id = entry.get("BodyID") if isinstance(entry.get("BodyID"), int) else entry.get("Body") if isinstance(entry.get("Body"), int) else None
        if event == "Scan":
            return self._scan(entry)
        if body_id is None:
            return False
        body = self._body(body_id, str(entry.get("BodyName") or ""))
        if event == "FSSBodySignals" or event == "SAASignalsFound":
            body.bio, body.geo = _count(entry, BIO_TYPE) or body.bio, _count(entry, GEO_TYPE) or body.geo
            if event == "SAASignalsFound":
                body.genuses = [str(g.get("Genus_Localised") or g.get("Genus") or "") for g in entry.get("Genuses", []) if isinstance(g, Mapping)] or body.genuses
            return True
        if event == "SAAScanComplete":
            body.mapped = True
            return True
        if event == "ScanOrganic":
            genus = str(entry.get("Genus_Localised") or entry.get("Genus") or "")
            if entry.get("ScanType") == "Analyse":
                if genus and genus not in body.analysed:
                    body.analysed.append(genus)
                body.sampling = ""
            else:
                body.sampling = genus
            return True
        return False

    def _session(self, entry: Mapping[str, Any], event: str) -> bool:
        """The game closing, going to its main menu, or a commander loading in: whether the cards may show at all, and whose survey this is."""
        if event == "Shutdown" or (event == "Fileheader" and entry.get("part", 1) in (1, None)):
            self.playing = False          # a journal that carries on from the last one (part 2 and up) is the same session
        elif event == "Music":
            if entry.get("MusicTrack") != "MainMenu":
                return False
            self.playing = False
        elif event == "LoadGame":
            name = str(entry.get("Commander") or "").strip()
            if name and self.cmdr and name.casefold() != self.cmdr.casefold():
                self.reset("", None)      # another commander: nothing scanned by the last one applies
            self.cmdr = name or self.cmdr
            self.playing = True
        elif event == "Docked":
            self.docked = True
        elif event == "Undocked":
            self.docked = False
        return True

    def _body(self, body_id: int, name: str = "") -> Body:
        body = self.bodies.get(body_id)
        if body is None:
            body = self.bodies[body_id] = Body(body_id, name, short_name(name, self.name))
        elif name and not body.name:
            body.name, body.short = name, short_name(name, self.name)
        return body

    def _scan(self, entry: Mapping[str, Any]) -> bool:
        body_id, name = entry.get("BodyID"), str(entry.get("BodyName") or "")
        system = str(entry.get("StarSystem") or "")
        if not isinstance(body_id, int) or not name or "belt cluster" in name.casefold():
            return False
        if system and self.name and system.casefold() != self.name.casefold():
            return False                      # a late event from the system just left
        planet, star = str(entry.get("PlanetClass") or ""), str(entry.get("StarType") or "")
        if not planet and not star:
            return False
        body = self._body(body_id, name)
        body.kind = "planet" if planet else "star"
        body.planet_class, body.star_type = planet, star
        body.terraformable = str(entry.get("TerraformState") or "").casefold() == "terraformable"
        body.landable = bool(entry.get("Landable"))
        body.was_discovered = entry.get("WasDiscovered") if isinstance(entry.get("WasDiscovered"), bool) else None
        body.was_mapped = entry.get("WasMapped") if isinstance(entry.get("WasMapped"), bool) else None
        body.mass_em = _number(entry.get("MassEM"))
        body.stellar_mass = _number(entry.get("StellarMass"))
        gravity, pressure = _number(entry.get("SurfaceGravity")), _number(entry.get("SurfacePressure"))
        body.gravity_g = gravity / STANDARD_GRAVITY if gravity is not None else None
        body.pressure_atm = pressure / PASCALS_PER_ATMOSPHERE if pressure is not None else None
        body.temperature_k = _number(entry.get("SurfaceTemperature"))
        body.distance_ls = _number(entry.get("DistanceFromArrivalLS"))
        body.volcanism = str(entry.get("Volcanism") or "")
        body.atmosphere = str(entry.get("Atmosphere") or "")
        body.materials = [(str(m.get("Name") or ""), float(m.get("Percent") or 0.0)) for m in entry.get("Materials", [])
                          if isinstance(m, Mapping) and m.get("Name")]
        body.scanned = True
        return True

    # --- what is left to do -------------------------------------------------------------------------------------------------
    @property
    def visible(self) -> bool:
        return bool(self.name) and not self.in_transit and self.playing and not self.docked

    def scanned_count(self) -> int:
        return sum(1 for b in self.bodies.values() if b.scanned)

    def to_map(self, threshold: int) -> List[Body]:
        """Scanned planets and moons worth at least `threshold` credits that the commander has not mapped, most valuable first."""
        found = [b for b in self.bodies.values() if b.kind == "planet" and b.scanned and not b.mapped and b.scan_value() >= threshold]
        return sorted(found, key=lambda b: -b.scan_value())

    def with_life(self) -> List[Body]:
        """Bodies with biological signals that are not fully analysed yet, in name order."""
        return sorted((b for b in self.bodies.values() if b.bio > 0 and not b.life_done), key=lambda b: b.short.casefold())

    def find(self, body_id: Optional[int] = None, name: str = "") -> Optional[Body]:
        if body_id is not None and body_id in self.bodies:
            return self.bodies[body_id]
        if name:
            wanted = name.casefold()
            return next((b for b in self.bodies.values() if b.name.casefold() == wanted), None)
        return None


# --- the shared survey, and the live path ---------------------------------------------------------------------------------------------

survey = SystemSurvey()


def handle_event(entry: Dict[str, Any], cmdr: str, system: Optional[str], station: Optional[str], state: Dict[str, Any]) -> None:
    """The journal hook: feeds the shared survey. Registered ahead of the cards that read it, so they see the state after the event."""
    if entry.get("event") in ("StartUp", RESTORE_EVENT):
        restore_from_journal(survey)      # EDMC started in the middle of a system: rebuild it from the newest journal
        survey.cmdr = cmdr or survey.cmdr
        return
    survey.handle_event(entry, system or "")


def restore_from_journal(target: Optional[SystemSurvey] = None, folder: Optional[str] = None) -> bool:
    """Rebuilds the survey of the system the commander is in from the newest journal: everything since the last arrival. True when it found one."""
    from . import journal_files
    target = target or survey
    try:
        files = journal_files.files_modified_since(0.0, folder)
        if not files:
            return False
        entries = list(journal_files.read_events(files[-1], journal_files.event_pattern(*EVENTS)))
    except Exception:    # reading an old journal is a convenience; it must never stop the live path
        logger.debug("Could not restore the system survey", exc_info=True)
        return False
    last = max((i for i, e in enumerate(entries) if e.get("event") in ARRIVALS), default=None)
    if last is None:
        return False
    target.reset("", None)
    for entry in entries[last:]:
        target.handle_event(entry)
    return True
