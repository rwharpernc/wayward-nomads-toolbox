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
import threading
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

# EDSM's names for planet types (lower case, hyphens as spaces) as the journal's PlanetClass spells them, which the value formula is keyed on.
EDSM_CLASSES = {
    "earth like world": "Earthlike body", "water world": "Water world", "ammonia world": "Ammonia world",
    "high metal content world": "High metal content body", "metal rich body": "Metal rich body", "rocky body": "Rocky body", "icy body": "Icy body",
    "rocky ice world": "Rocky ice body", "class i gas giant": "Sudarsky class I gas giant", "class ii gas giant": "Sudarsky class II gas giant",
    "class iii gas giant": "Sudarsky class III gas giant", "class iv gas giant": "Sudarsky class IV gas giant",
    "class v gas giant": "Sudarsky class V gas giant", "gas giant with ammonia based life": "Gas giant with ammonia based life",
    "gas giant with water based life": "Gas giant with water based life", "helium rich gas giant": "Helium rich gas giant",
    "helium gas giant": "Helium gas giant", "water giant": "Water giant",
}

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
    was_footfalled: Optional[bool] = None   # the scan's WasFootfalled: False means nobody has set foot here, so a first footfall pays five times on exobiology
    mass_em: Optional[float] = None
    stellar_mass: Optional[float] = None
    gravity_g: Optional[float] = None
    pressure_atm: Optional[float] = None
    temperature_k: Optional[float] = None
    distance_ls: Optional[float] = None
    volcanism: str = ""
    atmosphere: str = ""
    atmosphere_parts: List[Tuple[str, float]] = field(default_factory=list)      # (gas, percent) from the scan's AtmosphereComposition
    materials: List[Tuple[str, float]] = field(default_factory=list)
    scanned: bool = False
    known: bool = False                 # described by EDSM (other commanders' scans), not scanned by this commander yet
    mapped: bool = False                # the commander has mapped it (SAAScanComplete)
    bio: int = 0
    geo: int = 0
    genuses: List[str] = field(default_factory=list)
    analysed: List[str] = field(default_factory=list)      # genera fully analysed (ScanOrganic "Analyse")
    sampling: str = ""                  # the genus last logged or sampled, until it is analysed

    def scan_value(self) -> int:
        """The estimated credits for scanning it, from `scan_value`'s formula (the same estimate the Exploration Value readout shows). 0 for a
        body that is neither scanned nor known online."""
        if not (self.scanned or self.known):
            return 0
        from . import scan_value as value
        if self.kind == "star":
            return value.estimate_star_scan_value(self.stellar_mass, self.was_discovered, self.star_type)
        return value.estimate_planet_scan_value(self.planet_class, self.mass_em, self.terraformable, self.was_discovered)

    def mapped_value(self) -> int:
        """The estimated credits for scanning and then mapping it with an efficient probe run (what the Scan value row plus the mapping would pay), for a planet; 0
        for anything else or a body not yet scanned."""
        if self.kind != "planet" or not (self.scanned or self.known):
            return 0
        from . import scan_value as value
        return value.estimate_planet_mapped_value(self.planet_class, self.mass_em, self.terraformable, self.was_discovered, self.was_mapped)

    @property
    def first_footfall(self) -> bool:
        """A landable body nobody has set foot on: the first commander down is paid five times the usual exobiology reward."""
        return self.landable and self.was_footfalled is False

    @property
    def finished(self) -> bool:
        """Nothing left to do on it: mapped by the commander (or its life analysed) and, if it has life, all of it analysed."""
        return (self.mapped or self.life_done) and (self.bio == 0 or self.life_done)

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
        footfalled = entry.get("WasFootfalled")
        if footfalled is False:
            body.was_footfalled = False                    # kept once seen: a later scan after you have landed says True, but the bonus is still yours
        elif footfalled is True and body.was_footfalled is None:
            body.was_footfalled = True
        body.mass_em = _number(entry.get("MassEM"))
        body.stellar_mass = _number(entry.get("StellarMass"))
        gravity, pressure = _number(entry.get("SurfaceGravity")), _number(entry.get("SurfacePressure"))
        body.gravity_g = gravity / STANDARD_GRAVITY if gravity is not None else None
        body.pressure_atm = pressure / PASCALS_PER_ATMOSPHERE if pressure is not None else None
        body.temperature_k = _number(entry.get("SurfaceTemperature"))
        body.distance_ls = _number(entry.get("DistanceFromArrivalLS"))
        body.volcanism = str(entry.get("Volcanism") or "")
        body.atmosphere = str(entry.get("Atmosphere") or "")
        body.atmosphere_parts = [(str(a.get("Name") or ""), float(a.get("Percent") or 0.0)) for a in entry.get("AtmosphereComposition", [])
                                 if isinstance(a, Mapping) and a.get("Name")]
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

    def known_count(self) -> int:
        return sum(1 for b in self.bodies.values() if b.known and not b.scanned)

    def merge_known(self, system: str, rows: Any) -> int:
        """Adds the planets EDSM lists for `system` (what other commanders have scanned) as bodies this commander has not scanned: enough to estimate
        their value and tag them before the first scan. A body the commander has scanned keeps what the journal said. Ignored when the commander has
        moved on. Returns how many bodies it added or updated."""
        if not isinstance(rows, list) or system.casefold() != self.name.casefold():
            return 0
        added = 0
        for row in rows:
            if not isinstance(row, Mapping) or row.get("type") != "Planet" or not isinstance(row.get("bodyId"), int):
                continue
            existing = self.bodies.get(row["bodyId"])
            if existing is not None and existing.scanned:
                continue
            planet_class = EDSM_CLASSES.get(str(row.get("subType") or "").casefold().replace("-", " "), "")
            if not planet_class:
                continue
            name = str(row.get("name") or "")
            body = self._body(row["bodyId"], name)
            body.kind, body.planet_class, body.known = "planet", planet_class, True
            body.terraformable = str(row.get("terraformingState") or "").casefold().startswith("candidate")
            body.landable = bool(row.get("isLandable"))
            body.was_discovered, body.was_mapped = True, None
            body.mass_em = _number(row.get("earthMasses"))
            body.gravity_g = _number(row.get("gravity"))
            body.temperature_k = _number(row.get("surfaceTemperature"))
            body.distance_ls = _number(row.get("distanceToArrival"))
            body.atmosphere = str(row.get("atmosphereType") or "")
            body.volcanism = str(row.get("volcanismType") or "")
            added += 1
        return added

    def to_map(self, threshold: int, basis: str = "scan") -> List[Body]:
        """Scanned planets and moons worth at least `threshold` credits that the commander has not mapped, most valuable first. `basis` is the value
        judged: "scan" (the estimate for scanning it) or "mapped" (what scanning and then mapping it pays)."""
        value = (lambda b: b.mapped_value()) if basis == "mapped" else (lambda b: b.scan_value())
        found = [b for b in self.bodies.values() if b.kind == "planet" and (b.scanned or b.known) and not b.mapped and value(b) >= threshold]
        return sorted(found, key=lambda b: -value(b))

    def finished(self) -> List[Body]:
        """The planets and moons with nothing left to do (mapped, and any life analysed), in name order: where the commander has already been."""
        return sorted((b for b in self.bodies.values() if b.kind == "planet" and b.scanned and b.finished), key=lambda b: b.short.casefold())

    def life_counts(self) -> Tuple[int, int]:
        """(bodies whose life is all analysed, bodies with life): how far the biology of the system has got."""
        with_life = [b for b in self.bodies.values() if b.bio > 0]
        return sum(1 for b in with_life if b.life_done), len(with_life)

    def bio_totals(self) -> Tuple[int, int]:
        """(biological signals analysed, biological signals) over the whole system: how much of its life is done, counting each signal once (a body's analysed genera never exceed its signals)."""
        signals = sum(b.bio for b in self.bodies.values() if b.bio > 0)
        done = sum(min(len(set(b.analysed)), b.bio) for b in self.bodies.values() if b.bio > 0)
        return done, signals

    def mapped_count(self) -> int:
        return sum(1 for b in self.bodies.values() if b.kind == "planet" and b.mapped)

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


SAVED_EVENTS = ("FSSDiscoveryScan", "FSSAllBodiesFound", "Scan", "FSSBodySignals", "SAASignalsFound", "SAAScanComplete", "ScanOrganic")


def start(plugin_dir: str) -> None:
    from . import system_survey_store
    system_survey_store.store.start(plugin_dir)


def stop() -> None:
    from . import system_survey_store
    system_survey_store.store.flush()


_visited: Dict[str, set] = {}            # commander -> the systems (lower case names) their journals say they have been in; read once, in the background
_pending = {"merge": False}


def _index_visited(commander: str) -> None:
    """Reads the commander's journals once (newest MAX_BACKFILL_FILES) for the systems they have been in, so arriving in one that is not saved can be told from
    arriving somewhere new, without reading the journals again at every jump."""
    from . import journal_files
    key = commander.casefold()
    if not key or key in _visited:
        return
    _visited[key] = set()

    def worker() -> None:
        try:
            names = set()
            for path in journal_files.files_modified_since(0.0)[-MAX_BACKFILL_FILES:]:
                entries = list(journal_files.read_events(path, journal_files.event_pattern(*ARRIVALS, "LoadGame")))
                owner = _commander_of(entries)
                if owner and owner != key:
                    continue
                names.update(str(e.get("StarSystem") or "").casefold() for e in entries if e.get("event") in ARRIVALS)
            _visited[key] = names
        except Exception:
            logger.debug("Could not index the visited systems", exc_info=True)

    threading.Thread(target=worker, name="WNTB-survey-index", daemon=True).start()


def _backfill_if_visited_before(saved: Any, force: bool = False) -> None:
    """Arrived in a system with no saved survey: if the journals say the commander has been here before, rebuild it from those visits in the background."""
    if not survey.name or saved.has_saved(survey.name, survey.address) or not saved.commander:
        return
    commander, name, address = saved.commander, survey.name, survey.address
    if not force and name.casefold() not in _visited.get(commander.casefold(), set()):
        return
    key = (commander.casefold(), name.casefold())
    if key in _backfilled:
        return
    _backfilled.add(key)

    def worker() -> None:
        try:
            found = rebuild_system(name, commander)
            if found is not None:
                found.address = found.address or address
                saved.absorb(found, Body)
                _pending["merge"] = True
        except Exception:
            logger.debug("Could not rebuild the system survey from the journals", exc_info=True)

    threading.Thread(target=worker, name="WNTB-survey-backfill", daemon=True).start()


_backfilled: set = set()


def apply_pending() -> None:
    """Applies a survey rebuilt in the background (called on the main thread, from the journal and Status.json hooks, so the survey is never changed from two
    threads)."""
    if _pending["merge"]:
        _pending["merge"] = False
        from . import system_survey_store
        _merge_saved()
        system_survey_store.store.remember(survey)


def dashboard_status(entry: Mapping[str, Any]) -> None:
    apply_pending()


def _merge_saved() -> None:
    """Adds what was saved about this system on earlier visits (see system_survey_store.py): the bodies scanned, what is mapped and analysed."""
    from . import system_survey_store
    try:
        system_survey_store.store.merge_into(survey, Body)
    except Exception:    # a damaged save must never stop the live path
        logger.debug("Could not merge the saved system survey", exc_info=True)


def handle_event(entry: Dict[str, Any], cmdr: str, system: Optional[str], station: Optional[str], state: Dict[str, Any]) -> None:
    """The journal hook: feeds the shared survey. Registered ahead of the cards that read it, so they see the state after the event."""
    from . import system_survey_store
    saved = system_survey_store.store
    saved.set_commander(cmdr)
    apply_pending()
    event = entry.get("event")
    if cmdr:
        _index_visited(cmdr)
    if event in ("StartUp", RESTORE_EVENT):
        restore_from_journal(survey)      # EDMC started in the middle of a system: rebuild it from the journals
        survey.cmdr = cmdr or survey.cmdr
        _merge_saved()
        _backfill_if_visited_before(saved, force=True)       # the system EDMC found the commander in: rebuild it from every visit
        saved.remember(survey)
        return
    changed = survey.handle_event(entry, system or "")
    if event in ARRIVALS:
        _merge_saved()                    # back in a system surveyed before: what was known comes back
        _backfill_if_visited_before(saved)
    if event == "Shutdown":
        saved.flush()
    elif changed and (event in SAVED_EVENTS or event in ARRIVALS):
        saved.remember(survey)


MAX_RESTORE_FILES = 8             # journals read back at most, newest first, while the commander has stayed in the same system


def _commander_of(entries: List[Dict[str, Any]]) -> str:
    return next((str(e.get("Commander") or "").casefold() for e in entries if e.get("event") == "LoadGame"), "")


MAX_BACKFILL_FILES = 80


def rebuild_system(name: str, commander: str = "", folder: Optional[str] = None, max_files: int = MAX_BACKFILL_FILES) -> Optional[SystemSurvey]:
    """What the journals say about one system across every visit: the scans, signals, mapping and organisms from each time the commander was in it, in order.
    Only the given commander's journals are read (each begins with their LoadGame). None when the commander was never in it. Reads at most `max_files` journals,
    newest first, so a long history is not walked in full."""
    from . import journal_files
    files = journal_files.files_modified_since(0.0, folder)[-max_files:]
    pattern = journal_files.event_pattern(*EVENTS)
    found = SystemSurvey()
    seen = False
    wanted = commander.casefold()
    for path in files:
        entries = list(journal_files.read_events(path, pattern))
        owner = _commander_of(entries)
        if wanted and owner and owner != wanted:
            continue
        inside = False
        for entry in entries:
            event = entry.get("event")
            if event in ARRIVALS:
                inside = str(entry.get("StarSystem") or "").casefold() == name.casefold()
                if inside:
                    found.handle_event(entry)
                    seen = True
            elif inside and event in SAVED_EVENTS:
                found.handle_event(entry, name)
    return found if seen else None


def restore_from_journal(target: Optional[SystemSurvey] = None, folder: Optional[str] = None) -> bool:
    """Rebuilds the survey of the system the commander is in from the journals: everything since they arrived. A relog starts a new journal, so when the
    newest one begins in the system they were already in, the journals before it (the same commander's, up to MAX_RESTORE_FILES) are read back to the
    arrival, and the scans made before the relog are not lost. True when it found one."""
    from . import journal_files
    target = target or survey
    try:
        files = journal_files.files_modified_since(0.0, folder)
        if not files:
            return False
        pattern = journal_files.event_pattern(*EVENTS)
        entries = list(journal_files.read_events(files[-1], pattern))
        commander = _commander_of(entries)
        for path in reversed(files[-MAX_RESTORE_FILES:-1]):
            arrivals = {str(e.get("StarSystem") or "").casefold() for e in entries if e.get("event") in ARRIVALS}
            if len(arrivals) > 1:
                break                                   # the boundary of the current system is already in hand
            older = list(journal_files.read_events(path, pattern))
            if _commander_of(older) != commander:
                break                                   # another commander's journal: nothing in it is theirs
            entries = older + entries
    except Exception:    # reading an old journal is a convenience; it must never stop the live path
        logger.debug("Could not restore the system survey", exc_info=True)
        return False
    arrival_indexes = [i for i, e in enumerate(entries) if e.get("event") in ARRIVALS]
    if not arrival_indexes:
        return False
    here = str(entries[arrival_indexes[-1]].get("StarSystem") or "").casefold()
    start = arrival_indexes[-1]
    for index in reversed(arrival_indexes[:-1]):
        if str(entries[index].get("StarSystem") or "").casefold() != here:
            break
        start = index
    target.reset("", None)
    for entry in entries[start:]:
        target.handle_event(entry)
    return True
