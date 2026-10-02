"""Exploration Value: shows an estimated exploration-scan payout for the
last body you scanned, and the current system's age - both surfaced live as
you fly.

Scope is deliberately narrow: only the *scan* value (before any DSS
mapping) is estimated. Mapped-value estimation needs SAAScanComplete/
efficiency-probe correlation on top of this - a materially bigger, separate
problem, not attempted here. "System age" needs no formula at all - the
journal's own Scan event for a star already carries Age_MY directly.

The exploration-value formula (per-planet-class k values + terraforming
bonus, a mass exponent, and a first-discovery multiplier) is the same
community-reverse-engineered game formula every exploration-value tool
uses. These are empirically-determined game constants, not original
creative expression - any correct implementation reproduces the same
numbers.

Also shows the current galactic region (e.g. "Inner Orion Spur"), from the
same journal-reported StarPos every FSDJump/Location event already carries -
purely a local lookup against `organic_region_data`'s own coordinate-to-
region grid (see that module's docstring for provenance), no network call,
same passive/always-on treatment as the system-age readout above.
Also backfilled on a mid-session EDMC restart (EDMC's synthetic StartUp
event) from the current journal file's last FSDJump/Location entry, same
"catch up on state EDMC missed while it wasn't running" problem
mining_panel.py's own StartUp handling solves - see
`_backfill_region_from_journal()`.

Also hosts two more opt-in (default off, unlike the scan/age readout above)
readouts that each make a live network call: **ELW rarity
comparison** (on scanning an Earthlike World, counts how many others
Spansh already knows within `elw_rarity_spansh.DEFAULT_RADIUS_LY` - fewer
known nearby means a rarer find) and **EDSM upload-status** (on selecting
any system as a galaxy-map nav target via the journal's `FSDTarget` event -
no jump required - checks whether EDSM already has a record for it via
`edsm_client.system_known()`, unchanged/reused).

Lives inside Exploration mode's panel (PANEL_PLACEMENT = "exploration"),
alongside Auto-Honk/Discovery/Boxel Survey - each gets its own dedicated
child frame (see ui.py's
create_plugin_app/_stack_features()), separated by a thin panelkit-drawn
rule, so no cross-feature row coordination is needed here.
"""

from __future__ import annotations

import json
import logging
import math
import os
import queue
import threading
import time
from pathlib import Path
from typing import Any, Dict, Mapping, Optional

import tkinter as tk

import myNotebook as nb
from config import appname, config

from . import edsm_client, elw_rarity_spansh, organic_region_data, panelkit

plugin_name = os.path.basename(os.path.dirname(__file__))
logger = logging.getLogger(f"{appname}.{plugin_name}")

PANEL_PLACEMENT = "exploration"

_CFG_ENABLED = "wntb_exploration_value_enabled"
_CFG_ELW_RARITY_ENABLED = "wntb_exploration_value_elw_rarity_enabled"
_CFG_EDSM_UPLOAD_ENABLED = "wntb_exploration_value_edsm_upload_enabled"

_UPLOAD_RECHECK_S = 600
"""A system EDSM was already asked about is not asked about again for this
long (selecting the same galaxy-map target repeatedly costs no extra calls)."""

# --- Formula constants -----------------------------------------------------

# Mass exponent applied to every planet class's base k value.
Q = 0.56591828

# Scan-time multiplier for a body nobody has ever scanned before - the only
# multiplier this module's scan-only scope needs (mapped/first-mapped
# multipliers exist in the wider formula but aren't used here - see module
# docstring).
FIRST_DISCOVERY_MULTIPLIER = 2.6

# (k, terraforming bonus) per PlanetClass, as the journal spells it.
# Terraformable bodies (TerraformState == "Terraformable") add the second
# number to k before applying the mass exponent below.
PLANET_K_VALUES: Dict[str, tuple[float, float]] = {
    "Ammonia world": (96932, 93328),
    "Earthlike body": (64831, 116295),
    "Water world": (64831, 116295),
    "High metal content body": (9654, 100677),
    "Metal rich body": (21790, 65631),
    "Icy body": (300, 93328),
    "Rocky body": (300, 93328),
    "Rocky ice body": (300, 93328),
    "Sudarsky class I gas giant": (1656, 93328),
    "Sudarsky class II gas giant": (9654, 100677),
    "Sudarsky class III gas giant": (300, 93328),
    "Sudarsky class IV gas giant": (300, 93328),
    "Sudarsky class V gas giant": (300, 93328),
    "Gas giant with ammonia based life": (300, 93328),
    "Gas giant with water based life": (300, 93328),
    "Helium rich gas giant": (300, 93328),
    "Helium gas giant": (300, 93328),
    "Water giant": (300, 93328),
    "Water giant with life": (300, 93328),
}
_DEFAULT_PLANET_K = (300.0, 93328.0)

STAR_K_MAIN_SEQUENCE = 1200.0
STAR_K_WHITE_DWARF = 14057.0
STAR_K_NEUTRON_OR_BLACK_HOLE = 22628.0

# StarType prefixes/values for the two exotic tiers above - everything else
# (O/B/A/F/G/K/M and their variants, T Tauri, Wolf-Rayet, carbon stars,
# etc.) uses the flat main-sequence k. White dwarf codes all start with
# "D" (DA/DAB/DAO/DAZ/DAV/DB/DBZ/DBV/DO/DOV/DQ/DC/DCV/DX); neutron stars
# are "N"; black holes are "H" or "SupermassiveBlackHole".
_WHITE_DWARF_PREFIX = "D"
_NEUTRON_OR_BLACK_HOLE_TYPES = {"N", "H", "SupermassiveBlackHole"}


def _star_k(star_type: str) -> float:
    if star_type in _NEUTRON_OR_BLACK_HOLE_TYPES:
        return STAR_K_NEUTRON_OR_BLACK_HOLE
    if star_type.startswith(_WHITE_DWARF_PREFIX):
        return STAR_K_WHITE_DWARF
    return STAR_K_MAIN_SEQUENCE


def estimate_planet_scan_value(
    planet_class: str, mass_em: Optional[float], terraformable: bool, was_discovered: Optional[bool],
) -> int:
    """Estimated credit value of scanning this planet for the first time
    this session (i.e. the value the in-game "Scan" event itself pays),
    before any DSS mapping. `was_discovered` is the journal's own field -
    False (nobody's ever scanned it) applies the first-discovery
    multiplier; True or None (already known, or undeterminable) does not."""
    k, terra_bonus = PLANET_K_VALUES.get(planet_class, _DEFAULT_PLANET_K)
    if terraformable:
        k += terra_bonus

    mass = mass_em if isinstance(mass_em, (int, float)) and mass_em > 0 else 1.0
    value = k + (k * math.pow(mass, Q))
    if was_discovered is False:
        value *= FIRST_DISCOVERY_MULTIPLIER
    return max(int(value), 0)


def estimate_star_scan_value(
    stellar_mass: Optional[float], was_discovered: Optional[bool], star_type: str = "",
) -> int:
    """Estimated credit value of scanning this star for the first time this
    session. Stars can't be DSS-mapped, so this is their only scan value.
    `star_type` selects the k-value tier (main-sequence/white-dwarf/
    neutron-or-black-hole) - omit it (or pass an unrecognized type) for the
    flat main-sequence estimate."""
    k = _star_k(star_type)
    mass = stellar_mass if isinstance(stellar_mass, (int, float)) and stellar_mass > 0 else 1.0
    value = k + (mass * k / 66.25)
    if was_discovered is False:
        value *= FIRST_DISCOVERY_MULTIPLIER
    return max(int(value), 0)


def format_credits(value: int) -> str:
    return f"{value:,} cr"


def format_age(age_my: float) -> str:
    """`age_my` is million-years, straight off the journal's own Age_MY
    field. Shown as-is plus a friendlier billion-years figure for large
    ages, since most stars are thousands of My old."""
    if age_my >= 1000:
        return f"{age_my:,.0f} My (~{age_my / 1000:.1f} By)"
    return f"{age_my:,.0f} My"


def enabled() -> bool:
    return config.get_bool(_CFG_ENABLED, default=True)


def elw_rarity_enabled() -> bool:
    # Opt-in, default off - unlike the passive scan/age estimate above,
    # this adds a live Spansh network call per Earthlike World scanned.
    return config.get_bool(_CFG_ELW_RARITY_ENABLED, default=False)


def edsm_upload_enabled() -> bool:
    # Opt-in, default off - adds a live EDSM network call per galaxy-map
    # target selection, same reasoning as ELW rarity above.
    return config.get_bool(_CFG_EDSM_UPLOAD_ENABLED, default=False)


def _journal_dir() -> Optional[str]:
    # Same journaldir/fallback pattern as mining_journal_backfill.py/
    # journal_scan.py/codex_backfill.py - each feature module that needs
    # journal backfill keeps its own small copy rather than importing
    # another feature's module (see codex_backfill.py's own docstring for
    # why this project prefers that over reaching into another module's
    # private helpers).
    if hasattr(config, "get_str"):
        location = config.get_str("journaldir")
    else:
        location = config.get("journaldir")  # type: ignore[attr-defined]
    return location or config.default_journal_dir


def _find_current_journal_file() -> Optional[Path]:
    """The journal file EDMC is currently tailing - the most recently
    modified `Journal.*.log` in the configured journal directory."""
    location = _journal_dir()
    if not location:
        return None
    try:
        candidates = [path for path in Path(location).glob("Journal.*.log") if path.is_file()]
        if not candidates:
            return None
        return max(candidates, key=lambda path: path.stat().st_mtime)
    except OSError:
        logger.exception("Exploration Value: couldn't list journal directory")
        return None


_NO_SCAN_TEXT = "Last scan: (none yet)"
_NO_AGE_TEXT = "System age: (unknown)"
_NO_REGION_TEXT = "Region: (unknown)"
_DISABLED_TEXT = "Exploration Value display is disabled — see Settings."
_ELW_RARITY_IDLE_TEXT = "ELW rarity: (scan an Earthlike World)"
_ELW_RARITY_DISABLED_TEXT = ""
_UPLOAD_STATUS_IDLE_TEXT = "EDSM upload status: (select a system on the galaxy map)"
_UPLOAD_STATUS_DISABLED_TEXT = ""


class ExplorationValueController:
    def __init__(self) -> None:
        self._system_name: Optional[str] = None
        self._star_evaluated = False

        self._scan_var: Optional[tk.StringVar] = None
        self._age_var: Optional[tk.StringVar] = None
        self._region_var: Optional[tk.StringVar] = None
        self._elw_rarity_var: Optional[tk.StringVar] = None
        self._upload_status_var: Optional[tk.StringVar] = None
        self._parent: Optional[tk.Frame] = None

        self._enabled_var: Optional[tk.BooleanVar] = None
        self._elw_rarity_enabled_var: Optional[tk.BooleanVar] = None
        self._edsm_upload_enabled_var: Optional[tk.BooleanVar] = None

        # Worker-thread + queue.Queue + after()-polling plumbing, same
        # pattern as boxel_survey.py's own EDSM lookups - workers must
        # never touch a Tk widget directly. Each queue carries a generation
        # counter so a later scan/target selection can supersede an
        # in-flight lookup's eventual result.
        self._elw_generation = 0
        self._elw_cache: dict[str, int] = {}  # system -> known ELW count, for this session
        self._upload_cache: dict[str, tuple[float, bool]] = {}  # system -> (when asked, known to EDSM)
        self._elw_result_queue: "queue.Queue[tuple[int, str, Optional[int], Optional[str]]]" = queue.Queue()
        self._upload_generation = 0
        self._upload_result_queue: "queue.Queue[tuple[int, str, Optional[bool]]]" = queue.Queue()

    # --- journal dispatch -----------------------------------------------

    def handle_event(self, entry: Mapping[str, Any], cmdr: str, system: Optional[str], station: Optional[str], state: Dict[str, Any]) -> None:
        # Reset per-system state the same way discovery.py's own tracker
        # does, so a star's age cached from the previous system can never
        # leak into this one.
        if system and system != self._system_name:
            self._system_name = system
            self._star_evaluated = False

        event = entry.get("event")

        if event == "StartUp":
            # EDMC sends this synthetic event once, only when it's started
            # while the game is already running - same mid-session-start
            # signal mining_panel.py's own StartUp handling uses. Only the
            # region readout is backfilled (a single position lookup);
            # last-scan/system-age intentionally stay at their "none
            # yet"/"unknown" defaults until the next real Scan event, same
            # as before this addition - a full scan/age replay would need
            # walking every Scan in the file, a materially bigger change.
            self._backfill_region_from_journal()
            return

        if event == "FSDTarget":
            # Fires whenever ANY system is selected as a nav target on the
            # galaxy map - no jump required, so this works independently of
            # the boxel-walk flow.
            if edsm_upload_enabled():
                target_name = entry.get("Name")
                if target_name:
                    self._check_edsm_upload_status(target_name)
            return

        if event in ("FSDJump", "Location"):
            star_pos = entry.get("StarPos")
            if (isinstance(star_pos, list) and len(star_pos) == 3
                    and all(isinstance(v, (int, float)) for v in star_pos)):
                self._set_region(*star_pos)
            return

        if event != "Scan":
            return

        was_discovered = entry.get("WasDiscovered")
        star_type = entry.get("StarType")
        planet_class = entry.get("PlanetClass")
        body_name = entry.get("BodyName") or "Unknown body"

        if star_type:
            value = estimate_star_scan_value(entry.get("StellarMass"), was_discovered, star_type)
            self._set_scan(body_name, value)
            # Same "first star scan this system" gate as discovery.py's own
            # DiscoveryTracker - only the arrival/primary star sets the
            # system's displayed age, not every star in a multi-star system.
            if not self._star_evaluated:
                self._star_evaluated = True
                age_my = entry.get("Age_MY")
                if isinstance(age_my, (int, float)):
                    self._set_age(system or body_name, age_my)
        elif planet_class:
            terraformable = entry.get("TerraformState") == "Terraformable"
            value = estimate_planet_scan_value(planet_class, entry.get("MassEM"), terraformable, was_discovered)
            self._set_scan(body_name, value)
            if planet_class == "Earthlike body" and elw_rarity_enabled() and system:
                self._check_elw_rarity(body_name, system)

    def _set_scan(self, body_name: str, value: int) -> None:
        if self._scan_var is not None:
            self._scan_var.set(f"Last scan: {body_name} — est. {format_credits(value)}")

    def _set_age(self, system_name: str, age_my: float) -> None:
        if self._age_var is not None:
            self._age_var.set(f"System age: {system_name} — {format_age(age_my)}")

    def _set_region(self, x: float, y: float, z: float) -> None:
        if self._region_var is None:
            return
        region_id = organic_region_data.region_id_for_position(x, y, z)
        if region_id is None:
            self._region_var.set(_NO_REGION_TEXT)
        else:
            self._region_var.set(f"Region: {organic_region_data.REGION_NAMES[region_id]}")

    def _backfill_region_from_journal(self) -> None:
        """Finds the current journal file's *last* FSDJump/Location entry
        and sets the region immediately from it, so a mid-session EDMC
        restart shows the region you're actually in rather than leaving it
        blank until your next jump. Scans the whole file for the last
        match rather than stopping early - StarPos-carrying events are
        infrequent enough per session that this is cheap, and journal
        lines don't come with a reverse-readable format to tail instead."""
        path = _find_current_journal_file()
        if path is None:
            return
        star_pos: Optional[list] = None
        try:
            with open(path, "r", encoding="utf8", errors="replace") as journal_file:
                for line in journal_file:
                    try:
                        line_entry = json.loads(line)
                    except (json.JSONDecodeError, ValueError):
                        continue
                    if line_entry.get("event") not in ("FSDJump", "Location"):
                        continue
                    candidate = line_entry.get("StarPos")
                    if (isinstance(candidate, list) and len(candidate) == 3
                            and all(isinstance(v, (int, float)) for v in candidate)):
                        star_pos = candidate
        except OSError:
            logger.exception("Exploration Value: couldn't read journal file for region backfill")
            return
        if star_pos is not None:
            self._set_region(*star_pos)

    # --- ELW rarity (Spansh, opt-in) --------------------------------------

    def _check_elw_rarity(self, body_name: str, reference_system: str) -> None:
        self._elw_generation += 1
        generation = self._elw_generation
        cached = self._elw_cache.get(reference_system.casefold())
        if cached is not None:
            self._elw_result_queue.put((generation, body_name, cached, None))
            return
        if self._elw_rarity_var is not None:
            self._elw_rarity_var.set(f"ELW rarity: {body_name} — checking Spansh...")
        threading.Thread(
            target=self._elw_rarity_worker, args=(generation, body_name, reference_system), daemon=True,
        ).start()

    def _elw_rarity_worker(self, generation: int, body_name: str, reference_system: str) -> None:
        """Runs off the main thread — must not touch any Tk widget directly."""
        count: Optional[int] = None
        error: Optional[str] = None
        try:
            count = elw_rarity_spansh.count_nearby_earthlike_worlds(reference_system)
            if count is not None:
                self._elw_cache[reference_system.casefold()] = count
        except Exception:
            logger.exception("_elw_rarity_worker failed for %r near %r", body_name, reference_system)
            error = "Spansh lookup failed"
        self._elw_result_queue.put((generation, body_name, count, error))

    def _poll_elw_queue(self) -> None:
        """Runs on the main thread via after() — safe to touch widgets here."""
        try:
            generation, body_name, count, error = self._elw_result_queue.get_nowait()
        except queue.Empty:
            pass
        else:
            if generation == self._elw_generation and self._elw_rarity_var is not None:
                if error:
                    self._elw_rarity_var.set(f"ELW rarity: {body_name} — {error}, see EDMarketConnector.log")
                else:
                    radius = int(elw_rarity_spansh.DEFAULT_RADIUS_LY)
                    plural = "s" if count != 1 else ""
                    rarity = "a rare find!" if (count or 0) <= 3 else "not unusual here."
                    self._elw_rarity_var.set(
                        f"ELW rarity: {body_name} — {count} known ELW{plural} within {radius} ly — {rarity}"
                    )
        if self._parent is not None:
            self._parent.after(200, self._poll_elw_queue)

    # --- EDSM upload status (opt-in) --------------------------------------

    def _check_edsm_upload_status(self, target_name: str) -> None:
        self._upload_generation += 1
        generation = self._upload_generation
        cached = self._upload_cache.get(target_name.casefold())
        if cached is not None and time.monotonic() - cached[0] < _UPLOAD_RECHECK_S:
            self._upload_result_queue.put((generation, target_name, cached[1]))
            return
        if self._upload_status_var is not None:
            self._upload_status_var.set(f"EDSM upload status: {target_name} — checking...")
        threading.Thread(
            target=self._edsm_upload_worker, args=(generation, target_name), daemon=True,
        ).start()

    def _edsm_upload_worker(self, generation: int, target_name: str) -> None:
        """Runs off the main thread — must not touch any Tk widget directly."""
        known = edsm_client.system_known(target_name)
        if known is not None:
            self._upload_cache[target_name.casefold()] = (time.monotonic(), known)
        self._upload_result_queue.put((generation, target_name, known))

    def _poll_upload_queue(self) -> None:
        """Runs on the main thread via after() — safe to touch widgets here."""
        try:
            generation, target_name, known = self._upload_result_queue.get_nowait()
        except queue.Empty:
            pass
        else:
            if generation == self._upload_generation and self._upload_status_var is not None:
                if known is True:
                    status = "already in EDSM"
                elif known is False:
                    status = "not yet in EDSM"
                else:
                    status = "EDSM check unavailable"
                self._upload_status_var.set(f"EDSM upload status: {target_name} — {status}")
        if self._parent is not None:
            self._parent.after(200, self._poll_upload_queue)

    # --- main-panel widgets -----------------------------------------------

    def build_panel(self, parent: tk.Frame) -> None:
        self._parent = parent
        self._scan_var = tk.StringVar(value=_NO_SCAN_TEXT if enabled() else _DISABLED_TEXT)
        self._age_var = tk.StringVar(value=_NO_AGE_TEXT if enabled() else "")
        self._region_var = tk.StringVar(value=_NO_REGION_TEXT if enabled() else "")
        self._elw_rarity_var = tk.StringVar(
            value=_ELW_RARITY_IDLE_TEXT if elw_rarity_enabled() else _ELW_RARITY_DISABLED_TEXT,
        )
        self._upload_status_var = tk.StringVar(
            value=_UPLOAD_STATUS_IDLE_TEXT if edsm_upload_enabled() else _UPLOAD_STATUS_DISABLED_TEXT,
        )

        # ui.py's create_plugin_app() gives this its own dedicated child
        # frame, separated from its siblings by panelkit.add_separator() -
        # no cross-feature row coordination needed, just a title + its own
        # rows starting at 1.
        tk.Label(parent, text="Exploration Value", font=panelkit.bold_font(parent)).grid(
            row=0, column=0, columnspan=3, sticky=tk.W,
        )
        panelkit.wrap_label(parent, textvariable=self._scan_var, anchor="w").grid(
            row=1, column=0, columnspan=3, sticky=tk.W, pady=(2, 0),
        )
        panelkit.wrap_label(parent, textvariable=self._age_var, anchor="w").grid(
            row=2, column=0, columnspan=3, sticky=tk.W,
        )
        panelkit.wrap_label(parent, textvariable=self._region_var, anchor="w").grid(
            row=3, column=0, columnspan=3, sticky=tk.W,
        )
        panelkit.wrap_label(parent, textvariable=self._elw_rarity_var, anchor="w").grid(
            row=4, column=0, columnspan=3, sticky=tk.W,
        )
        panelkit.wrap_label(parent, textvariable=self._upload_status_var, anchor="w").grid(
            row=5, column=0, columnspan=3, sticky=tk.W,
        )

        parent.after(200, self._poll_elw_queue)
        parent.after(200, self._poll_upload_queue)

    def _refresh_enabled_display(self) -> None:
        if self._scan_var is not None and self._age_var is not None:
            if enabled():
                self._scan_var.set(_NO_SCAN_TEXT)
                self._age_var.set(_NO_AGE_TEXT)
                if self._region_var is not None:
                    self._region_var.set(_NO_REGION_TEXT)
            else:
                self._scan_var.set(_DISABLED_TEXT)
                self._age_var.set("")
                if self._region_var is not None:
                    self._region_var.set("")
        if self._elw_rarity_var is not None:
            self._elw_rarity_var.set(_ELW_RARITY_IDLE_TEXT if elw_rarity_enabled() else _ELW_RARITY_DISABLED_TEXT)
        if self._upload_status_var is not None:
            self._upload_status_var.set(
                _UPLOAD_STATUS_IDLE_TEXT if edsm_upload_enabled() else _UPLOAD_STATUS_DISABLED_TEXT,
            )

    # --- Settings tab --------------------------------------------------

    def build_settings(self, notebook: nb.Notebook) -> None:
        frame = nb.Frame(notebook)
        frame.columnconfigure(0, weight=1)
        notebook.add(frame, text="Exploration Value")

        self._enabled_var = tk.BooleanVar(value=enabled())
        self._elw_rarity_enabled_var = tk.BooleanVar(value=elw_rarity_enabled())
        self._edsm_upload_enabled_var = tk.BooleanVar(value=edsm_upload_enabled())

        nb.Label(frame, text="Exploration Value", font=("TkDefaultFont", 9, "bold")).grid(
            row=0, column=0, sticky=tk.W, padx=10, pady=(10, 4),
        )
        nb.Label(
            frame,
            text=(
                "Shows an estimated scan payout for the last body you scanned, the current "
                "system's age, and the current galactic region, in the Exploration panel. "
                "Scan-value only (not DSS-mapped value) — always an estimate, not a guaranteed "
                "in-game payout."
            ),
            wraplength=440, justify=tk.LEFT,
        ).grid(row=1, column=0, sticky=tk.W, padx=10, pady=(0, 4))
        nb.Checkbutton(
            frame, text="Show estimated scan value, system age, and current region", variable=self._enabled_var,
        ).grid(row=2, column=0, sticky=tk.W, padx=10, pady=(0, 10))

        nb.Label(
            frame,
            text=(
                "The two options below each make a live network call (Spansh/EDSM) — off by "
                "default, unlike the passive estimate above."
            ),
            wraplength=440, justify=tk.LEFT,
        ).grid(row=3, column=0, sticky=tk.W, padx=10, pady=(0, 4))
        nb.Checkbutton(
            frame,
            text="Show ELW rarity comparison when you scan an Earthlike World (Spansh)",
            variable=self._elw_rarity_enabled_var,
        ).grid(row=4, column=0, sticky=tk.W, padx=10)
        nb.Checkbutton(
            frame,
            text="Show EDSM upload status when you select a system on the galaxy map (EDSM)",
            variable=self._edsm_upload_enabled_var,
        ).grid(row=5, column=0, sticky=tk.W, padx=10, pady=(0, 10))

    def save_settings(self) -> None:
        if self._enabled_var is None:
            return
        config.set(_CFG_ENABLED, self._enabled_var.get())
        config.set(_CFG_ELW_RARITY_ENABLED, self._elw_rarity_enabled_var.get())
        config.set(_CFG_EDSM_UPLOAD_ENABLED, self._edsm_upload_enabled_var.get())
        self._refresh_enabled_display()


controller = ExplorationValueController()


def handle_event(entry: Dict[str, Any], cmdr: str, system: Optional[str], station: Optional[str], state: Dict[str, Any]) -> None:
    controller.handle_event(entry, cmdr, system, station, state)


def build_panel(parent: tk.Frame) -> None:
    controller.build_panel(parent)


def build_settings(notebook: nb.Notebook) -> None:
    controller.build_settings(notebook)


def save_settings() -> None:
    controller.save_settings()
