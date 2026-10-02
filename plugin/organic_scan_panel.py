"""Organic Scanning — a new Exploration feature (see organic_scan.py's own
docstring for the full "synergize with EDMC-Canonn, not duplicate it"
rationale and scope boundaries).

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
            )

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
        elif event == "ScanOrganic":
            self._handle_scan_organic(entry)

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
        self._save_current_conditions(body_name, cond)
        if body_name == self._current_body_name:
            self._refresh_predictions()

    def _handle_body_signals(self, entry: Dict[str, Any]) -> None:
        body_name = entry.get("BodyName")
        genuses = entry.get("Genuses")
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
        species_name = entry.get("Species_Localised") or entry.get("Species") or "Unknown species"
        scan_type = entry.get("ScanType")
        if not genus_key or not species_key or not scan_type:
            return
        organism = self._tracker.record_scan(
            genus_key, species_key, species_name, scan_type, self._current_lat, self._current_lon,
        )
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
        if isinstance(lat, (int, float)):
            self._current_lat = lat
        if isinstance(lon, (int, float)):
            self._current_lon = lon
        if isinstance(radius, (int, float)):
            self._current_planet_radius = radius

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
                "slightly more often than the real game allows, never less. Designed to complement "
                "EDMC-Canonn, not duplicate its own data submission."
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
