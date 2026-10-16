"""Organic Scanning — a new Exploration feature (see organic_scan.py's own
docstring for the rationale and scope boundaries).

Lives inside Exploration mode's panel (PANEL_PLACEMENT = "exploration"),
alongside Auto-Honk/Discovery/Boxel Survey/Exploration Value - each gets
its own dedicated child frame (see
ui.py's create_plugin_app/_stack_features()), separated by a thin
panelkit-drawn rule, so no cross-feature row coordination is needed here.

Per-body state (habitability conditions, detected genera, confirmed-
species scan progress) is persisted per commander via organic_scan_state.py
(see that module's own docstring) - restored on cmdr switch/plugin start
and re-saved after every state-changing journal event, same
save-cadence convention as codex_completionist_panel.py's own
CodexEntry-triggered persist. This is what lets a body's known biology
survive a log-out/relog (a new journal file replays none of the original
FSSBodySignals/Scan/ScanOrganic events) instead of resetting - see
organic_scan.py's own docstring.
"""

from __future__ import annotations

import logging
import os
from dataclasses import asdict, replace
from typing import Any, Dict, List, Optional

import tkinter as tk

import myNotebook as nb
from config import appname, config

from . import organic_scan, organic_scan_state, panelkit
from .organic_scan import BodyConditions, OrganicTracker

plugin_name = os.path.basename(os.path.dirname(__file__))
logger = logging.getLogger(f"{appname}.{plugin_name}")

PANEL_PLACEMENT = "exploration"

_CFG_ENABLED = "wntb_organic_enabled"

_NO_BODY_TEXT = "Predicted species: (land on a body with biological signals)"
_NO_ACTIVE_TEXT = "Active scan: (none yet)"
_DISABLED_TEXT = "Organic Scanning is disabled — see Settings."


def enabled() -> bool:
    # On by default - pure journal + bundled-data math, no network calls,
    # same reasoning as exploration_value.py's own scan/age readout.
    return config.get_bool(_CFG_ENABLED, default=True)


def _format_credits(value: Optional[int]) -> str:
    return f"~{value:,} cr" if value is not None else "value unknown"


class OrganicScanController:
    def __init__(self) -> None:
        self._plugin_dir: Optional[str] = None
        self._cmdr: Optional[str] = None
        self._persisted: Dict[str, Dict[str, Any]] = {}
        """This commander's saved per-body state (organic_scan_state.py),
        keyed by `_body_key()` - unlike `_body_conditions`/`_genus_hints`
        below, this is never cleared on a system change, since it's meant
        to outlive both a system change and a full relog."""

        self._system_name: Optional[str] = None
        self._star_type: Optional[str] = None
        self._star_pos: Optional[tuple] = None
        self._body_conditions: Dict[str, BodyConditions] = {}
        self._genus_hints: Dict[str, List[str]] = {}

        self._current_body_name: Optional[str] = None
        self._current_lat: Optional[float] = None
        self._current_lon: Optional[float] = None
        self._current_planet_radius: Optional[float] = None
        self._current_heading: Optional[float] = None
        self._ship_pos: Optional[tuple] = None        # where the ship touched down on the current body
        self._srv_pos: Optional[tuple] = None         # where the SRV was left or launched
        self._footfall: Dict[str, bool] = {}          # body name -> nobody had set foot there (from its Scan)
        self._signal_counts: Dict[str, int] = {}      # body name -> biological signals
        self._mapped_bodies: set = set()
        self._active_genus: Optional[str] = None      # the genus last sampled and not yet analysed
        self._focus_genus: Optional[str] = None       # the genus being surveyed: the one in progress, else the one last identified
        self._waypoints: Dict[str, List[organic_scan.Waypoint]] = {}     # body name -> plants identified there and not yet sampled
        self._tracker = OrganicTracker()

        self._predictions_var: Optional[tk.StringVar] = None
        self._active_var: Optional[tk.StringVar] = None
        self._enabled_var: Optional[tk.BooleanVar] = None

    # --- lifecycle / persistence -----------------------------------------

    def start(self, plugin_dir: str) -> None:
        self._plugin_dir = plugin_dir
        # Per-body state is per-commander and EDMC doesn't know which
        # commander is active until the first journal event - actual
        # restore happens in _switch_cmdr(), called from handle_event().

    def stop(self) -> None:
        self._persist()

    def _body_key(self, system: Optional[str], body_name: str) -> str:
        return f"{system or ''}|{body_name}"

    def _switch_cmdr(self, cmdr: str) -> None:
        """Called whenever the active commander changes, including the
        first journal event of a session - saves the previous commander's
        per-body state (if one was loaded) and loads this commander's own,
        so two commanders on the same install never share or overwrite
        one commander's biology data."""
        self._persist()
        self._cmdr = cmdr
        saved = organic_scan_state.load_state(self._plugin_dir, cmdr) if self._plugin_dir else None
        self._persisted = saved if isinstance(saved, dict) else {}
        if self._persisted:
            logger.info("Restored Organic Scanning state for %s: %d bodies", cmdr, len(self._persisted))

    def _persist(self) -> None:
        if self._plugin_dir is not None and self._cmdr is not None:
            organic_scan_state.save_state(self._plugin_dir, self._cmdr, self._persisted)

    def _save_current_conditions(self, body_name: str, cond: BodyConditions) -> None:
        key = self._body_key(cond.system_name, body_name)
        stored = self._persisted.setdefault(key, {})
        conditions_dict = asdict(cond)
        conditions_dict.pop("system_body_types", None)  # computed fresh, not this body's own state
        stored["conditions"] = conditions_dict
        self._persist()

    def _save_genus_hints(self, system: Optional[str], body_name: str, genus_keys: List[str]) -> None:
        key = self._body_key(system, body_name)
        stored = self._persisted.setdefault(key, {})
        stored["genus_hints"] = genus_keys
        self._persist()

    def _save_organism(self, system: Optional[str], body_name: str, organism: organic_scan.OrganismProgress) -> None:
        key = self._body_key(system, body_name)
        stored = self._persisted.setdefault(key, {})
        organisms = stored.setdefault("organisms", {})
        organisms[organism.genus_key] = {
            "species_key": organism.species_key,
            "species_name": organism.species_name,
            "value": organism.value,
            "stage": organism.stage,
            "last_lat": organism.last_lat,
            "last_lon": organism.last_lon,
            "variant_name": organism.variant_name,
            "positions": [list(p) for p in organism.positions],
        }
        self._persist()

    def _restore_body(self, system: Optional[str], body_name: str) -> None:
        """Repopulates this body's conditions/genus-hints/scan-progress
        from persisted state where this session hasn't already seen a live
        journal event for it - the log-out/relog case, where no
        FSSBodySignals/Scan/ScanOrganic events for this body get replayed
        from the new journal file."""
        stored = self._persisted.get(self._body_key(system, body_name))
        if not stored:
            return
        if body_name not in self._body_conditions and stored.get("conditions"):
            try:
                conditions_dict = dict(stored["conditions"])
                position = conditions_dict.get("galactic_position")
                if isinstance(position, list) and len(position) == 3:
                    conditions_dict["galactic_position"] = tuple(position)
                self._body_conditions[body_name] = BodyConditions(**conditions_dict)
            except TypeError:
                logger.warning("Discarding stale/incompatible saved conditions for %s", body_name)
        if body_name not in self._genus_hints and stored.get("genus_hints"):
            self._genus_hints[body_name] = list(stored["genus_hints"])
        for genus_key, organism_data in (stored.get("organisms") or {}).items():
            self._tracker.restore_organism(
                genus_key,
                organism_data.get("species_key"),
                organism_data.get("species_name"),
                organism_data.get("value"),
                organism_data.get("stage", 0),
                organism_data.get("last_lat"),
                organism_data.get("last_lon"),
                organism_data.get("variant_name"),
                organism_data.get("positions"),
            )
        if body_name not in self._waypoints and stored.get("waypoints"):
            self._waypoints[body_name] = [organic_scan.Waypoint(w[0], w[1], float(w[2]), float(w[3])) for w in stored["waypoints"]
                                          if isinstance(w, (list, tuple)) and len(w) == 4]
        if body_name not in self._footfall and "first_footfall" in stored:
            self._footfall[body_name] = bool(stored["first_footfall"])

    # --- journal dispatch -----------------------------------------------

    def handle_event(self, entry: Dict[str, Any], cmdr: str, system: Optional[str], station: Optional[str], state: Dict[str, Any]) -> None:
        if cmdr and cmdr != self._cmdr:
            self._switch_cmdr(cmdr)

        if system and system != self._system_name:
            self._system_name = system
            self._star_type = None
            self._star_pos = None
            self._body_conditions = {}
            self._genus_hints = {}
            # Predictions and active-scan progress are body-specific - leaving
            # the system means the previously-tracked body no longer applies,
            # even before Status.json reports a new BodyName (e.g. mid-
            # supercruise, where BodyName often goes blank rather than
            # naming the next body immediately). Without this, the panel
            # kept showing the old system's predictions/active scan until
            # dashboard_status() happened to see a new non-empty body_name.
            self._current_body_name = None
            self._current_lat = None
            self._current_lon = None
            self._current_planet_radius = None
            self._current_heading = None
            self._ship_pos = self._srv_pos = self._active_genus = self._focus_genus = None
            self._waypoints = {}
            self._footfall, self._signal_counts, self._mapped_bodies = {}, {}, set()
            self._tracker.reset()
            self._refresh_predictions()
            self._refresh_active()

        event = entry.get("event", "")

        if event in ("FSDJump", "Location"):
            star_pos = entry.get("StarPos")
            if (isinstance(star_pos, list) and len(star_pos) == 3
                    and all(isinstance(v, (int, float)) for v in star_pos)):
                self._star_pos = tuple(star_pos)

        if event == "Scan":
            self._handle_scan(entry)
        elif event in ("FSSBodySignals", "SAASignalsFound"):
            self._handle_body_signals(entry)
        elif event == "SAAScanComplete" and entry.get("BodyName"):
            self._mapped_bodies.add(entry["BodyName"])
        elif event == "ScanOrganic":
            self._handle_scan_organic(entry)
        elif event == "CodexEntry":
            self._handle_codex(entry)
        elif event in ("Touchdown", "Liftoff"):
            self._handle_ship(event, entry)
        elif event in ("LaunchSRV", "Disembark", "DockSRV", "Embark"):
            self._handle_vehicle(event, entry)

    def _handle_codex(self, entry: Dict[str, Any]) -> None:
        """A plant identified with the Composition Scanner: keep where it is, so the commander can be led back to it. Only one genus is followed at a time
        (the latest), and each genus keeps a few plants."""
        if entry.get("SubCategory") != "$Codex_SubCategory_Organic_Structures;" or not self._current_body_name:
            return
        lat, lon = entry.get("Latitude"), entry.get("Longitude")
        genus_key = organic_scan.genus_key_for_codex_name(str(entry.get("Name") or ""))
        if genus_key is None or not isinstance(lat, (int, float)) or not isinstance(lon, (int, float)):
            return
        body = self._current_body_name
        points = [p for p in self._waypoints.get(body, []) if p.genus_key != genus_key or abs(p.lat - lat) > 1e-5 or abs(p.lon - lon) > 1e-5]
        points.append(organic_scan.Waypoint(genus_key, str(entry.get("Name_Localised") or ""), float(lat), float(lon)))
        same = [p for p in points if p.genus_key == genus_key]
        for extra in same[:-organic_scan.WAYPOINTS_PER_GENUS]:
            points.remove(extra)
        self._waypoints[body] = points
        self._focus_genus = genus_key
        self._save_waypoints(body)

    def _drop_waypoints(self, genus_key: str, complete: bool) -> None:
        """A sample was taken: the plant sampled is no longer one to come back to (the waypoint nearest the commander, within a few dozen meters), and a genus
        that is analysed has none left."""
        body = self._current_body_name
        if not body or body not in self._waypoints:
            return
        points = self._waypoints[body]
        if complete:
            points = [p for p in points if p.genus_key != genus_key]
        elif self._current_lat is not None and self._current_lon is not None and self._current_planet_radius:
            near = [(organic_scan.haversine_distance_m(p.lat, p.lon, self._current_lat, self._current_lon, self._current_planet_radius), p)
                    for p in points if p.genus_key == genus_key]
            near = [item for item in near if item[0] <= organic_scan.WAYPOINT_SAMPLED_M]
            if near:
                points = [p for p in points if p is not min(near, key=lambda item: item[0])[1]]
        self._waypoints[body] = points
        self._save_waypoints(body)

    def _save_waypoints(self, body: str) -> None:
        stored = self._persisted.setdefault(self._body_key(self._system_name, body), {})
        stored["waypoints"] = [[p.genus_key, p.name, p.lat, p.lon] for p in self._waypoints.get(body, [])]
        self._persist()

    def _handle_ship(self, event: str, entry: Dict[str, Any]) -> None:
        lat, lon = entry.get("Latitude"), entry.get("Longitude")
        if event == "Touchdown" and isinstance(lat, (int, float)) and isinstance(lon, (int, float)):
            self._ship_pos = (float(lat), float(lon))
        elif event == "Liftoff":
            self._ship_pos = None

    def _handle_vehicle(self, event: str, entry: Dict[str, Any]) -> None:
        """The SRV is where the commander was when it was launched or left (the journal does not give its position, Status.json gives ours)."""
        if event == "DockSRV" or (event == "Embark" and entry.get("SRV")):
            self._srv_pos = None
        elif event == "LaunchSRV" or (event == "Disembark" and entry.get("SRV")):
            if self._current_lat is not None and self._current_lon is not None:
                self._srv_pos = (self._current_lat, self._current_lon)
            elif self._ship_pos is not None:
                self._srv_pos = self._ship_pos

    def _handle_scan(self, entry: Dict[str, Any]) -> None:
        star_type = entry.get("StarType")
        if star_type:
            # Approximated as the system's most-recently-scanned star, same
            # simplification exploration_value.py's own system-age readout
            # already makes - see organic_scan.BodyConditions's docstring.
            self._star_type = star_type
            return

        body_name = entry.get("BodyName")
        planet_class = entry.get("PlanetClass")
        if not body_name or not planet_class:
            return

        gravity_ms2 = entry.get("SurfaceGravity")
        pressure_pa = entry.get("SurfacePressure")
        atmosphere_composition = entry.get("AtmosphereComposition")
        atmosphere_components = None
        if isinstance(atmosphere_composition, list):
            atmosphere_components = {
                c["Name"]: c["Percent"] for c in atmosphere_composition
                if isinstance(c, dict) and isinstance(c.get("Name"), str)
                and isinstance(c.get("Percent"), (int, float))
            }
        cond = BodyConditions(
            body_name=body_name,
            planet_class=planet_class,
            atmosphere=entry.get("AtmosphereType"),
            gravity_g=organic_scan.gravity_ms2_to_g(gravity_ms2) if isinstance(gravity_ms2, (int, float)) else None,
            temperature_k=entry.get("SurfaceTemperature"),
            pressure_atm=organic_scan.pressure_pa_to_atm(pressure_pa) if isinstance(pressure_pa, (int, float)) else None,
            volcanism=entry.get("Volcanism") or "",
            star_type=self._star_type,
            system_name=self._system_name,
            galactic_position=self._star_pos,
            atmosphere_components=atmosphere_components,
        )
        self._body_conditions[body_name] = cond
        if isinstance(entry.get("WasFootfalled"), bool):
            self._footfall[body_name] = not entry["WasFootfalled"]
            self._persisted.setdefault(self._body_key(self._system_name, body_name), {})["first_footfall"] = self._footfall[body_name]
        self._save_current_conditions(body_name, cond)
        if body_name == self._current_body_name:
            self._refresh_predictions()

    def _handle_body_signals(self, entry: Dict[str, Any]) -> None:
        body_name = entry.get("BodyName")
        genuses = entry.get("Genuses")
        count = next((s.get("Count") for s in entry.get("Signals", []) if isinstance(s, dict) and s.get("Type") == "$SAA_SignalType_Biological;"), None)
        if body_name and isinstance(count, int):
            self._signal_counts[body_name] = count
        if not body_name or not isinstance(genuses, list):
            return
        genus_keys = [g.get("Genus") for g in genuses if isinstance(g, dict) and g.get("Genus")]
        self._genus_hints[body_name] = genus_keys
        self._save_genus_hints(self._system_name, body_name, genus_keys)
        if body_name == self._current_body_name:
            for genus_key in genus_keys:
                self._tracker.note_genus_detected(genus_key)
            self._refresh_predictions()

    def _handle_scan_organic(self, entry: Dict[str, Any]) -> None:
        genus_key = entry.get("Genus")
        species_key = entry.get("Species")
        variant_name = entry.get("Variant_Localised")
        species_name = entry.get("Species_Localised") or entry.get("Species") or "Unknown species"
        scan_type = entry.get("ScanType")
        if not genus_key or not species_key or not scan_type:
            return
        organism = self._tracker.record_scan(
            genus_key, species_key, species_name, scan_type, self._current_lat, self._current_lon,
            variant_name if isinstance(variant_name, str) else None,
        )
        self._active_genus = None if organism.complete else genus_key
        self._focus_genus = genus_key
        self._drop_waypoints(genus_key, organism.complete)
        if self._current_body_name:
            self._save_organism(self._system_name, self._current_body_name, organism)
        self._refresh_active()

    # --- dashboard (Status.json) dispatch --------------------------------

    def dashboard_status(self, entry: Dict[str, Any]) -> None:
        """Called from load.py's dashboard_entry, same pattern as
        mining_panel.dashboard_status/interdiction.handle_dashboard_flags -
        the only source WNTB has for on-foot Latitude/Longitude/
        PlanetRadius, roughly once a second."""
        body_name = entry.get("BodyName")
        lat = entry.get("Latitude")
        lon = entry.get("Longitude")
        radius = entry.get("PlanetRadius")
        heading = entry.get("Heading")
        if isinstance(heading, (int, float)):
            self._current_heading = float(heading)
        if isinstance(lat, (int, float)):
            self._current_lat = lat
        if isinstance(lon, (int, float)):
            self._current_lon = lon
        if isinstance(radius, (int, float)):
            self._current_planet_radius = radius

        if not body_name and self._current_body_name is not None:
            # Status.json names no body once the commander has left the planet's vicinity (or is in the menu): the body just finished no longer applies,
            # so the overlay cards reset and the next body can take over. What was sampled stays saved and returns with the body.
            self._current_body_name = None
            self._current_lat = self._current_lon = self._current_planet_radius = self._current_heading = None
            self._ship_pos = self._srv_pos = self._active_genus = self._focus_genus = None
            self._tracker.reset()
            self._refresh_predictions()

        if body_name and body_name != self._current_body_name:
            self._current_body_name = body_name
            self._tracker.reset()
            for genus_key in self._genus_hints.get(body_name, []):
                self._tracker.note_genus_detected(genus_key)
            self._restore_body(self._system_name, body_name)
            self._refresh_predictions()

        # Always re-render the active-scan line, not just on a body change -
        # the "next sample ready"/"move further away" distance readout must
        # track the commander's own position as they walk, not just refresh
        # once when landing or on the next ScanOrganic event.
        self._refresh_active()

    # --- prediction/progress display -------------------------------------

    def _refresh_predictions(self) -> None:
        if self._predictions_var is None or not enabled():
            return
        body_name = self._current_body_name
        cond = self._body_conditions.get(body_name) if body_name else None
        genus_keys = self._genus_hints.get(body_name, []) if body_name else []
        if not body_name or not genus_keys:
            self._predictions_var.set(_NO_BODY_TEXT)
            return
        if cond is None:
            self._predictions_var.set(f"Predicted species: {body_name} — waiting on body scan data...")
            return

        # Every PlanetClass scanned so far this system - feeds
        # SpeciesRuleset.bodies (Brain Tree/Crystalline Shards need a
        # specific body type to exist *somewhere* in the system, not
        # necessarily the one being scanned). Computed fresh here rather
        # than stored on each BodyConditions in self._body_conditions,
        # since it depends on every body scanned so far, not just this one.
        system_body_types = tuple(
            c.planet_class for c in self._body_conditions.values() if c.planet_class)
        cond = replace(cond, system_body_types=system_body_types)

        parts = []
        for genus_key in genus_keys:
            genus_info = organic_scan.species_data.GENUS.get(genus_key)
            genus_name = genus_info.name if genus_info else genus_key
            candidates = organic_scan.predict_species(genus_key, cond)
            if not candidates:
                parts.append(f"{genus_name}: unknown")
            elif len(candidates) == 1:
                parts.append(f"{genus_name}: {candidates[0].name} ({_format_credits(candidates[0].value)})")
            else:
                names = ", ".join(c.name for c in candidates)
                parts.append(f"{genus_name}: {names}")
        self._predictions_var.set(f"Predicted species ({body_name}):\n" + "\n".join(parts))

    def overlay_view(self) -> Optional[organic_scan.BodyView]:
        """The exobiology of the body the commander is at, for the overlay cards: each genus with its predicted species and values, its sample
        stage, and how far the commander is from its last sample. None away from a body or before any genus is known. Needs no widgets."""
        body_name = self._current_body_name
        if not body_name:
            return None
        genus_keys = list(self._genus_hints.get(body_name, []))
        for organism in self._tracker.organisms:
            if organism.genus_key not in genus_keys:
                genus_keys.append(organism.genus_key)
        if not genus_keys and not self._signal_counts.get(body_name):
            return None
        cond = self._body_conditions.get(body_name)
        if cond is not None:
            cond = replace(cond, system_body_types=tuple(c.planet_class for c in self._body_conditions.values() if c.planet_class))
        organisms = {o.genus_key: o for o in self._tracker.organisms}
        if self._active_genus not in organisms or organisms[self._active_genus].complete:
            self._active_genus = None
        if self._active_genus is None:         # after a restart or a relog: the genus part-way through its samples, the furthest along if there are several
            started = [o for o in organisms.values() if 0 < o.stage < organic_scan.REQUIRED_SAMPLES]
            if started:
                self._active_genus = max(started, key=lambda o: o.stage).genus_key
        genera = []
        for genus_key in genus_keys:
            info = organic_scan.species_data.GENUS.get(genus_key)
            candidates = organic_scan.predict_species(genus_key, cond) if cond is not None else []
            organism = organisms.get(genus_key)
            distance = None
            if (organism is not None and organism.last_lat is not None and organism.last_lon is not None and self._current_lat is not None
                    and self._current_lon is not None and self._current_planet_radius):
                distance = organic_scan.haversine_distance_m(organism.last_lat, organism.last_lon, self._current_lat, self._current_lon,
                                                             self._current_planet_radius)
            genera.append(organic_scan.GenusView(
                key=genus_key, name=info.name if info else genus_key.strip("$;").replace("Codex_Ent_", "").replace("_Name", ""),
                min_distance_m=info.min_distance_m if info else 0.0,
                candidates=tuple((c.name, c.value) for c in candidates),
                species=organism.species_name if organism else None, value=organism.value if organism else None,
                stage=organism.stage if organism else 0, distance_m=distance, variant=organism.variant_name if organism else None,
                positions=tuple(organism.positions) if organism else ()))
        here = (self._current_lat, self._current_lon) if self._current_lat is not None and self._current_lon is not None else None
        focus = self._active_genus or self._focus_genus
        waypoints = tuple(p for p in self._waypoints.get(body_name, []) if p.genus_key == focus)
        return organic_scan.BodyView(
            body_name, tuple(genera), first_footfall=self._footfall.get(body_name, False), mapped=bool(self._genus_hints.get(body_name)),
            signal_count=self._signal_counts.get(body_name, 0), here=here, heading=self._current_heading,
            radius_m=self._current_planet_radius or 0.0, ship=self._ship_pos, srv=self._srv_pos, active=self._active_genus,
            waypoints=waypoints, focus=focus)

    def _refresh_active(self) -> None:
        if self._active_var is None or not enabled():
            return
        organisms = [o for o in self._tracker.organisms if o.stage > 0]
        if not organisms:
            self._active_var.set(_NO_ACTIVE_TEXT)
            return
        parts = []
        for organism in organisms:
            name = organism.species_name or organism.genus_key
            value_text = f" ({_format_credits(organism.value)})" if organism.complete else ""
            distance_text = ""
            if not organism.complete and self._current_lat is not None and self._current_lon is not None:
                ok = self._tracker.next_sample_distance_ok(
                    organism.genus_key, self._current_lat, self._current_lon,
                    self._current_planet_radius or 0.0,
                )
                if ok is True:
                    distance_text = " — next sample ready"
                elif ok is False:
                    distance_text = " — move further away"
            parts.append(f"{name}: {organism.stage_name} ({organism.stage}/{organic_scan.REQUIRED_SAMPLES}){value_text}{distance_text}")
        self._active_var.set("Active scan:\n" + "\n".join(parts))

    # --- main-panel widgets -----------------------------------------------

    def build_panel(self, parent: tk.Frame) -> None:
        tk.Label(parent, text="Organic Scanning", font=panelkit.bold_font(parent)).grid(
            row=0, column=0, columnspan=3, sticky=tk.W,
        )

        self._predictions_var = tk.StringVar(value=_NO_BODY_TEXT if enabled() else _DISABLED_TEXT)
        self._active_var = tk.StringVar(value=_NO_ACTIVE_TEXT if enabled() else "")

        panelkit.wrap_label(parent, textvariable=self._predictions_var, anchor="w").grid(
            row=1, column=0, columnspan=3, sticky=tk.W, pady=(2, 0),
        )
        panelkit.wrap_label(parent, textvariable=self._active_var, anchor="w").grid(
            row=2, column=0, columnspan=3, sticky=tk.W,
        )

    def _refresh_enabled_display(self) -> None:
        if self._predictions_var is None or self._active_var is None:
            return
        if enabled():
            self._predictions_var.set(_NO_BODY_TEXT)
            self._active_var.set(_NO_ACTIVE_TEXT)
        else:
            self._predictions_var.set(_DISABLED_TEXT)
            self._active_var.set("")

    # --- Settings tab --------------------------------------------------

    def build_settings(self, notebook: nb.Notebook) -> None:
        frame = nb.Frame(notebook)
        frame.columnconfigure(0, weight=1)
        notebook.add(frame, text="Organic Scanning")

        self._enabled_var = tk.BooleanVar(value=enabled())

        nb.Label(frame, text="Organic Scanning", font=("TkDefaultFont", 9, "bold")).grid(
            row=0, column=0, sticky=tk.W, padx=10, pady=(10, 4),
        )
        nb.Label(
            frame,
            text=(
                "Predicts which exobiology species can appear on the body you're on (from its "
                "atmosphere/gravity/temperature/volcanism, galactic region, Guardian proximity, and "
                "any biological signals already detected), tracks scan-stage progress (Log/Sample/"
                "Analyse) and whether you've moved far enough for the next sample. What it's found "
                "on a body is remembered per commander, so it's still there if you log out and back "
                "in. Local and read-only, no network calls - a species may show as a candidate "
                "slightly more often than the real game allows, never less. It submits nothing."
            ),
            wraplength=440, justify=tk.LEFT,
        ).grid(row=1, column=0, sticky=tk.W, padx=10, pady=(0, 4))
        nb.Checkbutton(
            frame, text="Show predicted species and scan progress", variable=self._enabled_var,
        ).grid(row=2, column=0, sticky=tk.W, padx=10, pady=(0, 10))

    def save_settings(self) -> None:
        if self._enabled_var is None:
            return
        config.set(_CFG_ENABLED, self._enabled_var.get())
        self._refresh_enabled_display()


controller = OrganicScanController()


def overlay_view() -> Optional[organic_scan.BodyView]:
    return controller.overlay_view()


def start(plugin_dir: str) -> None:
    controller.start(plugin_dir)


def stop() -> None:
    controller.stop()


def handle_event(entry: Dict[str, Any], cmdr: str, system: Optional[str], station: Optional[str], state: Dict[str, Any]) -> None:
    controller.handle_event(entry, cmdr, system, station, state)


def dashboard_status(entry: Dict[str, Any]) -> None:
    controller.dashboard_status(entry)


def build_panel(parent: tk.Frame) -> None:
    controller.build_panel(parent)


def build_settings(notebook: nb.Notebook) -> None:
    controller.build_settings(notebook)


def save_settings() -> None:
    controller.save_settings()
