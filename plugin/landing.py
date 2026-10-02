"""Landing: docking status + pad-layout diagram, drawn via overlay.py and
mirrored as an in-app widget.

The pad-index numbering (the 15-entry shell/sector table in this module's
`_PAD_LIST`/`_PAD_SECTORS`/`_DODECAGON` constants) is dictated by the real
game's station layout: any correct implementation reproduces the same
numbers. The docking state machine, status text, auto-hide timer and overlay
rendering are this project's own code.

Mode-independent (PANEL_PLACEMENT = "always") - not one of WNTB's five
toolbox modes, so its main-panel widgets sit outside any mode frame,
visible regardless of which mode is selected.

Purely journal-driven (DockingRequested/Granted/Denied/Timeout/Cancelled,
Docked/Undocked, plus FSDJump/CarrierJump/SupercruiseEntry to reset a
stale in-flight request) - no Status.json signal needed, unlike
interdiction.py. Ephemeral by design, same as interdiction.py.
"""

from __future__ import annotations

import logging
import math
import os
import re
import textwrap
import threading
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Mapping, Optional, Tuple

import tkinter as tk

import myNotebook as nb
from config import appname, config
from ttkHyperlinkLabel import HyperlinkLabel

from . import overlay, panelkit
from .overlay import OverlayClient

plugin_name = os.path.basename(os.path.dirname(__file__))
logger = logging.getLogger(f"{appname}.{plugin_name}")

PANEL_PLACEMENT = "always"

_CFG_ENABLED = "wntb_landing_enabled"
_CFG_OVERLAY_ENABLED = "wntb_landing_overlay_enabled"
_CFG_IN_APP_ENABLED = "wntb_landing_in_app_enabled"
DEFAULT_ENABLED = False
DEFAULT_OVERLAY_ENABLED = True
DEFAULT_IN_APP_ENABLED = True

# How long the overlay keeps showing "Docking Approved" info after touchdown
# before auto-hiding.
HIDE_AFTER_LANDING_S = 10.0

# Rendering is event-driven, and each graphic is sent with a ttl - this
# interval re-emits the current snapshot on a repeating timer for as long as
# a docking request is outstanding, so the widget keeps refreshing itself
# even when nothing journal-driven happens between DockingGranted and
# actually touching down (which can easily outlast a single ttl).
_HEARTBEAT_INTERVAL_S = 12.0

# Fixed on both axes regardless of diagram family/pad count/game window size
# - see the global EDMC-plugin-development instruction on bounding anything
# that can size the main window. Bumped from 200 (R.W. Harper, 2026-09-18: the
# diagram read a bit small in the panel), then from 240 (R.W. Harper,
# 2026-09-19: still a bit small even once actually centered) - still a
# static, hard-coded bound, not data-derived, so the sizing rule above
# still holds.
_LANDING_DIAGRAM_SIZE = 280


@dataclass
class LandingConfig:
    enabled: bool = DEFAULT_ENABLED
    overlay_enabled: bool = DEFAULT_OVERLAY_ENABLED
    in_app_enabled: bool = DEFAULT_IN_APP_ENABLED


def load_config() -> LandingConfig:
    return LandingConfig(
        enabled=config.get_bool(_CFG_ENABLED, default=DEFAULT_ENABLED),
        overlay_enabled=config.get_bool(_CFG_OVERLAY_ENABLED, default=DEFAULT_OVERLAY_ENABLED),
        in_app_enabled=config.get_bool(_CFG_IN_APP_ENABLED, default=DEFAULT_IN_APP_ENABLED),
    )


def save_config(cfg: LandingConfig) -> None:
    config.set(_CFG_ENABLED, cfg.enabled)
    config.set(_CFG_OVERLAY_ENABLED, cfg.overlay_enabled)
    config.set(_CFG_IN_APP_ENABLED, cfg.in_app_enabled)


# --- Docking/landing helpers -----------------------------------------

CarrierType = Optional[str]  # "FleetCarrier" | "SquadronCarrier" | "ColonisationShip" | None
PadDiagramType = Optional[str]  # "starport" | "fleetcarrier" | None

_COLONISATION_DEPOT_MARKET_IDS = {
    129032183, 129032439, 129032695, 129032951, 129033207, 129033463,
}
_COLONISATION_SHIP_STATION_KEY = re.compile(r"^\$EXT_PANEL_(?:Colonisation|Colonization)Ship", re.IGNORECASE)


def _raw_station_name(raw: Mapping[str, Any]) -> str:
    value = raw.get("StationName")
    return value.strip() if isinstance(value, str) else ""


def extract_landing_pad_from_event(raw: Mapping[str, Any]) -> Any:
    """Assigned pad from journal (DockingGranted/Docked). Field name has
    varied by game build."""
    for key in ("LandingPad", "landingpad", "LandingPadNumber", "PadNumber", "Pad", "AssignedLandingPad", "DockedPad"):
        value = raw.get(key)
        if value not in (None, ""):
            return value
    return None


def infer_carrier_type_from_dock_event(raw: Mapping[str, Any]) -> CarrierType:
    """Fleet-style pad layout (16 pads): personal FC, squadron carrier, or
    system colonisation megaship. Colonisation ships are often journal-
    reported as SurfaceStation/Unknown and need the MarketID/symbolic-name
    backstop to be recognized at all."""
    station_type = raw.get("StationType")
    station_type = station_type.lower() if isinstance(station_type, str) else ""
    name = _raw_station_name(raw)
    market_id = raw.get("MarketID")
    market_id = market_id if isinstance(market_id, int) else None

    is_colonisation_depot = (
        (market_id is not None and market_id in _COLONISATION_DEPOT_MARKET_IDS)
        or bool(_COLONISATION_SHIP_STATION_KEY.match(name))
    )

    if station_type in ("surfacestation", "unknown"):
        return "ColonisationShip" if is_colonisation_depot else None

    dockable_carrier_like = any(
        token in station_type
        for token in ("fleetcarrier", "fleet carrier", "colonisationship", "colonizationship", "dockablemegaship")
    )
    if not dockable_carrier_like:
        return None

    if "colonisationship" in station_type or "colonizationship" in station_type or is_colonisation_depot:
        return "ColonisationShip"
    if len(name) == 4:
        return "SquadronCarrier"
    return "FleetCarrier"


_DOCKING_DENIED_REASONS = {
    "NoSpace": "All pads occupied",
    "TooLarge": "Ship too large",
    "Hostile": "Hostile to station",
    "Offences": "Criminal offences",
    "Distance": "Must be within 7.5km",
    "ActiveFighter": "Active SLF deployed",
    "RestrictedAccess": "Carrier access restricted",
    "JumpImminent": "Carrier jump imminent",
}


def docking_denied_reason_to_text(reason_id: Any) -> str:
    if not isinstance(reason_id, str) or not reason_id:
        return "Unknown"
    return _DOCKING_DENIED_REASONS.get(reason_id, reason_id)


_PANEL_MATCH = re.compile(r"^\$EXT_PANEL_(?:Colonisation|Colonization)Ship_(.+)$", re.IGNORECASE)
_PANEL_MATCH_GENERIC = re.compile(r"^\$EXT_PANEL_(.+)$", re.IGNORECASE)


def format_station_display_name(raw: Mapping[str, Any]) -> str:
    """Strips `$EXT_PANEL_...` symbolic station-name tokens down to a
    readable suffix."""
    localised = raw.get("StationName_Localised")
    if isinstance(localised, str) and localised.strip():
        return localised.strip()

    name = _raw_station_name(raw)
    if not name:
        return ""
    if not name.startswith("$"):
        return name

    match = _PANEL_MATCH.match(name) or _PANEL_MATCH_GENERIC.match(name)
    if match:
        suffix = match.group(1)
        suffix = re.sub(r";+$", "", suffix).replace("_", " ")
        return re.sub(r"\s+", " ", suffix).strip()
    return name


_STARPORT_TYPES = (
    "bernal", "coriolis", "orbis", "asteroidbase", "ocellus", "dodec",
    "starport", "planetary port", "asteroid base",
)
_FLEETCARRIER_TYPES = (
    "fleetcarrier", "fleet carrier", "colonisationship", "colonizationship",
    "colonisation ship", "colonization ship", "colonisation", "colonization",
    "dockablemegaship", "dockable megaship", "squadroncarrier", "squadron carrier",
)


def _diagram_type_from_string(value: str) -> PadDiagramType:
    lower = value.lower()
    if any(t in lower for t in _FLEETCARRIER_TYPES):
        return "fleetcarrier"
    if any(t in lower for t in _STARPORT_TYPES):
        return "starport"
    return None


def _diagram_type_from_carrier(carrier: CarrierType) -> PadDiagramType:
    if carrier in ("FleetCarrier", "SquadronCarrier", "ColonisationShip"):
        return "fleetcarrier"
    return None


@dataclass
class DockingRequest:
    status: str = ""  # "" | "pending" | "granted" | "denied"
    station: str = ""
    pad: Any = None
    denied_reason: str = ""
    station_type: str = ""
    carrier_type: CarrierType = None


def get_pad_diagram_type(docking: DockingRequest, last_station_type: str, last_carrier_type: CarrierType) -> PadDiagramType:
    """Which pad-diagram family applies. `last_station_type` is only
    consulted when the in-flight request has no station type of its own yet
    - once it does (e.g. an outpost, which has no diagram family), that's
    authoritative and must not fall through to a stale value left over from
    a previous, unrelated station."""
    if docking.station_type:
        return _diagram_type_from_string(docking.station_type) or _diagram_type_from_carrier(docking.carrier_type)
    if last_station_type:
        kind = _diagram_type_from_string(last_station_type)
        if kind:
            return kind
    return _diagram_type_from_carrier(docking.carrier_type or last_carrier_type)


def parse_numeric_pad(pad: Any) -> Optional[int]:
    """Journal may send pad as a number or a string ("12", "Pad 12")."""
    if pad is None or pad == "":
        return None
    if isinstance(pad, bool):
        return None
    if isinstance(pad, (int, float)):
        n = int(pad)
        return n if n > 0 else None
    match = re.search(r"(\d+)", str(pad).strip())
    if not match:
        return None
    n = int(match.group(1))
    return n if n > 0 else None


@dataclass
class LandingDisplayInfo:
    status_label: Optional[str] = None  # "Docking Requested" | "Docking Approved" | "Docking Denied" | None
    station: str = ""
    denied_reason: str = ""
    pad: Optional[int] = None
    diagram_type: PadDiagramType = None
    show_diagram: bool = False


def build_landing_display_info(
    docking: DockingRequest,
    docked: bool,
    last_assigned_pad: Any,
    last_station_type: str,
    last_carrier_type: CarrierType,
) -> LandingDisplayInfo:
    """One shared derivation: while docking.status is
    'granted'/'denied'/'pending' that drives the text;
    once it's cleared (post-touchdown), fall back to the persisted
    docked+last_assigned_pad."""
    diagram_type = get_pad_diagram_type(docking, last_station_type, last_carrier_type)

    status_label: Optional[str] = None
    if docking.status == "granted":
        status_label = "Docking Approved"
    elif docking.status == "denied":
        status_label = "Docking Denied"
    elif docking.status == "pending":
        status_label = "Docking Requested"
    elif docked and last_assigned_pad is not None:
        status_label = "Docking Approved"

    if docking.status == "granted":
        pad = parse_numeric_pad(docking.pad)
    elif status_label == "Docking Approved" and docked:
        pad = parse_numeric_pad(last_assigned_pad)
    else:
        pad = None

    show_diagram = diagram_type is not None and (docking.status in ("granted", "denied") or docked)

    return LandingDisplayInfo(
        status_label=status_label,
        station=docking.station,
        denied_reason=docking.denied_reason,
        pad=pad,
        diagram_type=diagram_type,
        show_diagram=show_diagram,
    )


def format_in_app_text(info: LandingDisplayInfo) -> str:
    """One-line status text for the EDMC main-panel widget - the same
    status/pad/denied-reason facts as the overlay's text column (render(),
    below), just condensed onto one line. Bounded by construction - station
    names are the only unbounded input, and the caller wraps this through
    panelkit's wraplength-tracking label rather than letting it stretch the
    main window."""
    if not info.status_label:
        return ""
    parts = [info.status_label]
    if info.station:
        parts.append(info.station)
    if info.pad is not None:
        parts.append(f"Pad {info.pad}")
    text = " — ".join(parts)
    if info.status_label == "Docking Denied":
        text += f" ({info.denied_reason or 'Unknown'})"
    return text


# --- State machine ------------------------------------------------------

_RESET_DOCKING_EVENTS = ("FSDJump", "CarrierJump", "SupercruiseEntry")

DOCKING_EVENTS = (
    "DockingRequested", "DockingGranted", "DockingDenied", "DockingTimeout", "DockingCancelled",
    "Docked", "Undocked",
) + _RESET_DOCKING_EVENTS


@dataclass
class LandingSnapshot:
    docking: DockingRequest = field(default_factory=DockingRequest)
    docked: bool = False
    last_assigned_pad: Any = None
    last_station_type: str = ""
    last_carrier_type: CarrierType = None
    hidden_after_landing: bool = False


class LandingTracker:
    """Tracks docking state, plus the overlay widget's own post-touchdown
    auto-hide timer."""

    def __init__(self, on_change: Callable[[LandingSnapshot], None]) -> None:
        self._on_change = on_change
        self._docking = DockingRequest()
        self._docked = False
        self._last_assigned_pad: Any = None
        self._last_station_type = ""
        self._last_carrier_type: CarrierType = None
        self._hide_timer: Optional[threading.Timer] = None
        self._hidden_after_landing = False
        self._heartbeat_timer: Optional[threading.Timer] = None

    def get_snapshot(self) -> LandingSnapshot:
        return LandingSnapshot(
            docking=self._docking,
            docked=self._docked,
            last_assigned_pad=self._last_assigned_pad,
            last_station_type=self._last_station_type,
            last_carrier_type=self._last_carrier_type,
            hidden_after_landing=self._hidden_after_landing,
        )

    def handle_event(self, entry: Mapping[str, Any]) -> None:
        event = entry.get("event")

        if event == "DockingRequested":
            self._docking = DockingRequest(
                status="pending", station=format_station_display_name(entry), pad=None, denied_reason="",
                station_type=self._docking.station_type, carrier_type=self._docking.carrier_type,
            )
        elif event == "DockingGranted":
            station_type = entry.get("StationType")
            station_type = station_type.lower() if isinstance(station_type, str) else ""
            self._docking = DockingRequest(
                status="granted", station=format_station_display_name(entry),
                pad=extract_landing_pad_from_event(entry), denied_reason="",
                station_type=station_type, carrier_type=infer_carrier_type_from_dock_event(entry),
            )
        elif event == "DockingDenied":
            self._docking.status = "denied"
            self._docking.station = format_station_display_name(entry)
            self._docking.pad = None
            self._docking.denied_reason = docking_denied_reason_to_text(entry.get("Reason"))
        elif event == "DockingTimeout":
            self._docking.status = "denied"
            self._docking.station = format_station_display_name(entry) or self._docking.station
            self._docking.denied_reason = "Timed out"
        elif event == "DockingCancelled":
            self._docking = DockingRequest()
        elif event == "Docked":
            self._clear_hide_timer()
            pad = extract_landing_pad_from_event(entry)
            if pad is None:
                pad = self._docking.pad
            event_station_type = entry.get("StationType")
            station_type = (
                event_station_type if isinstance(event_station_type, str)
                else (self._docking.station_type or self._last_station_type or "")
            ).lower()
            carrier_type = self._docking.carrier_type or infer_carrier_type_from_dock_event(entry)

            self._docking = DockingRequest()
            self._docked = True
            if pad is not None:
                self._last_assigned_pad = pad
            self._last_station_type = station_type
            self._last_carrier_type = carrier_type
            self._hidden_after_landing = False
            self._schedule_hide()
        elif event == "Undocked":
            self._docked = False
            self._clear_hide_timer()
            self._hidden_after_landing = False
        elif event in _RESET_DOCKING_EVENTS:
            self._docking = DockingRequest()
            self._docked = False
            self._clear_hide_timer()
            self._hidden_after_landing = False
        else:
            return

        if self._docking.status:
            self._schedule_heartbeat()
        else:
            self._clear_heartbeat()

        self._emit_changed()

    def _schedule_heartbeat(self) -> None:
        self._clear_heartbeat()

        def _beat() -> None:
            self._heartbeat_timer = None
            if self._docking.status:
                self._emit_changed()
                self._schedule_heartbeat()

        self._heartbeat_timer = threading.Timer(_HEARTBEAT_INTERVAL_S, _beat)
        self._heartbeat_timer.daemon = True
        self._heartbeat_timer.start()

    def _clear_heartbeat(self) -> None:
        if self._heartbeat_timer is not None:
            self._heartbeat_timer.cancel()
            self._heartbeat_timer = None

    def _schedule_hide(self) -> None:
        self._clear_hide_timer()

        def _hide() -> None:
            self._hide_timer = None
            self._hidden_after_landing = True
            self._emit_changed()

        self._hide_timer = threading.Timer(HIDE_AFTER_LANDING_S, _hide)
        self._hide_timer.daemon = True
        self._hide_timer.start()

    def _clear_hide_timer(self) -> None:
        if self._hide_timer is not None:
            self._hide_timer.cancel()
            self._hide_timer = None

    def _emit_changed(self) -> None:
        self._on_change(self.get_snapshot())


# --- Pad diagram geometry (the pad-index math is dictated by the real game's
# station layout - don't "clean up" without re-checking against it) -----------

_SHELL_SCALE = (1.0, 0.625, 0.455, 0.25)
_SIN15 = math.sin(math.pi / 12)
_COS15 = math.cos(math.pi / 12)
_SIN45 = math.sqrt(2) / 2
_SIN60 = math.sqrt(3) / 2

_DODECAGON: Tuple[Tuple[float, float], ...] = (
    (_COS15, -_SIN15), (_SIN45, -_SIN45), (_SIN15, -_COS15), (-_SIN15, -_COS15),
    (-_SIN45, -_SIN45), (-_COS15, -_SIN15), (-_COS15, _SIN15), (-_SIN45, _SIN45),
    (-_SIN15, _COS15), (_SIN15, _COS15), (_SIN45, _SIN45), (_COS15, _SIN15),
)
_PAD_LIST: Tuple[Tuple[int, int], ...] = (
    (0, 0), (0, 0), (0, 2), (0, 2), (1, 0), (1, 0), (1, 1), (1, 2),
    (2, 0), (2, 2), (3, 0), (3, 0), (3, 1), (3, 2), (3, 2),
)
_PAD_SECTORS: Tuple[Tuple[float, float], ...] = (
    (0, 1), (-0.5, _SIN60), (-_SIN60, 0.5), (-1, 0), (-_SIN60, -0.5), (-0.5, -_SIN60),
    (0, -1), (0.5, -_SIN60), (_SIN60, -0.5), (1, 0), (_SIN60, 0.5), (0.5, _SIN60),
)


def _starport_shell_points(cx: float, cy: float, r: float, scale: float) -> List[Tuple[float, float]]:
    return [(cx + dx * r * scale, cy + dy * r * scale) for dx, dy in _DODECAGON]


def _starport_pad_pos(pad: int, cx: float, cy: float, r: float) -> Tuple[float, float]:
    normalized = ((pad - 1) % 45 + 45) % 45
    s, t = _PAD_LIST[normalized % 15]
    sector = s + (normalized // 15) * 4
    dx, dy = _PAD_SECTORS[sector % 12]
    td = (_SHELL_SCALE[t] + _SHELL_SCALE[t + 1]) / 2
    rt = r * _COS15 * td
    return (cx + rt * dx, cy + rt * dy)


def _fleetcarrier_pad_rects(carrier_type: CarrierType) -> List[Tuple[float, float, float, float]]:
    """8 Large + 4 Medium + 4 Small pads; SquadronCarrier duplicates the
    cluster left/right (32 total)."""

    def add_pads(x_off: float, rects: List[Tuple[float, float, float, float]]) -> None:
        for y in (22, 2, -18, -38):
            for x in (-12, 2):
                rects.append((x + x_off, y, x + x_off + 10, y + 16))
        for x in (-22, 15):
            for y in (25, 10):
                rects.append((x + x_off, y, x + x_off + 7, y + 11))
        small_x = (-24, -18, 14, 20) if carrier_type == "ColonisationShip" else (-24, 14, 20, -18)
        for x in small_x:
            rects.append((x + x_off, 0, x + x_off + 4, 6))

    pad_list: List[Tuple[float, float, float, float]] = []
    if carrier_type == "SquadronCarrier":
        squad_offset = 48 / 2 + 2
        add_pads(squad_offset, pad_list)
        add_pads(-squad_offset, pad_list)
    else:
        add_pads(0, pad_list)
    return pad_list


_MAX_FLEETCARRIER_PADS = 32  # SquadronCarrier's doubled cluster - the widest case


# --- Rendering (overlay.py's OverlayClient is generic; this is the one
# place that knows what the Landing widget should look like) -------------

STROKE_COLOR = "#fb923c"  # orange-400, theme-independent
ACTIVE_COLOR = "#fbbf24"  # amber-400

# In-app-only diagram colors (the overlay above is drawn over the game's own
# dark HUD backdrop and stays theme-independent; the in-app Canvas sits on
# EDMC's own panel, which switches between a near-white and a near-black
# background depending on Light/Dark/Transparent theme - STROKE_COLOR and
# especially ACTIVE_COLOR's hollow-outline marker read poorly against a light
# background, which is what this pair fixes). See _diagram_colors() below -
# panelkit.is_dark_theme() is the same check missions_ui.py/
# mining_hotspot_settings.py already use for this.
_DIAGRAM_STROKE_LIGHT = "#c2410c"  # orange-700 - dark enough to read on white
_DIAGRAM_STROKE_DARK = STROKE_COLOR
_DIAGRAM_MARKER_LIGHT = "#0369a1"  # sky-700 - strong contrast against both
                                    # the orange stroke and a white background
_DIAGRAM_MARKER_DARK = "#38bdf8"  # sky-400 - same contrast logic against the
                                    # dark-theme stroke and a near-black background


def _diagram_colors() -> Tuple[str, str]:
    """(stroke_color, marker_color) for the in-app pad diagram, picked for
    contrast against whichever of EDMC's own themes is currently active -
    never the overlay's own theme-independent STROKE_COLOR/ACTIVE_COLOR."""
    if panelkit.is_dark_theme():
        return _DIAGRAM_STROKE_DARK, _DIAGRAM_MARKER_DARK
    return _DIAGRAM_STROKE_LIGHT, _DIAGRAM_MARKER_LIGHT

_CHROME_BORDER = "#80f97316"  # orange-500 at 50% alpha
_CHROME_FILL = "#d9000000"  # black at 85% alpha
_TEXT_PRIMARY = "#fdba74"  # orange-300
_TEXT_MUTED = "#c2410c"  # orange-700
_STATUS_OK = "#34d399"  # emerald-400
_STATUS_DENIED = "#f87171"  # red-400

_TEXT_X = 40
_Y_TITLE = 650
_Y_STATUS = 675
_Y_STATION = 698
_Y_PAD = 721
_Y_DENIED = 744

_CARD_ID = "wntb_landing_card"
_CARD_X = 20
_CARD_Y = _Y_TITLE - 14
_CARD_W = 320
_DIAGRAM_CX = _CARD_X + _CARD_W // 2
_DIAGRAM_CY = 860
_DIAGRAM_SIZE = 160
_CARD_H = int(_DIAGRAM_CY + _DIAGRAM_SIZE / 2 + 20 - _CARD_Y)

_TTL = 20

_STARPORT_SHELL_IDS = tuple(f"wntb_landing_shell{i}" for i in range(4))
_STARPORT_SPOKE_IDS = tuple(f"wntb_landing_spoke{i}" for i in range(12))
_STARPORT_PADMARK_ID = "wntb_landing_padmark"
_FLEETCARRIER_PAD_IDS = tuple(f"wntb_landing_fcpad{i}" for i in range(_MAX_FLEETCARRIER_PADS))
_FLEETCARRIER_LABEL_ID = "wntb_landing_fclabel"

_PLACEHOLDER_W = 200
_PLACEHOLDER_H = 100
_FALLBACK_TEXT_SIZE = "normal"
_FALLBACK_LABEL_TEXT = "No actual diagram - it probably looks something like this."
_FALLBACK_LABEL_GAP = 16
_FALLBACK_LABEL_X = _DIAGRAM_CX + _PLACEHOLDER_W // 2 + _FALLBACK_LABEL_GAP
_FALLBACK_LABEL_W = 180
_FALLBACK_CARD_W = _FALLBACK_LABEL_X + _FALLBACK_LABEL_W + 10 - _CARD_X
_FALLBACK_MAX_CHARS_PER_LINE = _FALLBACK_LABEL_W // 9
_FALLBACK_LINE_HEIGHT = 22
_FALLBACK_MAX_LINES = 6
_FALLBACK_LINE_IDS = tuple(f"wntb_landing_fallback{i}" for i in range(_FALLBACK_MAX_LINES))
_PLACEHOLDER_RECT_ID = "wntb_landing_placeholder_rect"
_PLACEHOLDER_PAD_ID = "wntb_landing_placeholder_pad"

_STATUS_TEXT_IDS = (
    ("wntb_landing_title", _Y_TITLE), ("wntb_landing_status", _Y_STATUS),
    ("wntb_landing_station", _Y_STATION), ("wntb_landing_pad", _Y_PAD),
    ("wntb_landing_denied", _Y_DENIED),
)

# This mode's own EDMCModernOverlay Plugin Group - legitimate use per
# overlay.py's own docstring, since this widget's several shapes (status
# text + shell/spoke/pad-marker or pad-grid rects) genuinely need to
# scale/anchor together as one composite diagram.
GROUP_NAME = "wntb_landing"
GROUP_PREFIX = "wntb_landing_"


def render(info: LandingDisplayInfo, carrier_type: CarrierType, client: OverlayClient) -> None:
    """Draws (or clears) the Landing widget. Raises on an OverlayClient
    failure - load.py's live listener wraps this call and decides that's an
    expected, silent-fail state; the Settings "Test Overlay" button wraps
    its own call and surfaces it instead."""
    if not info.status_label:
        clear(client)
        return

    status_color = _STATUS_DENIED if info.status_label == "Docking Denied" else _STATUS_OK
    has_diagram = info.show_diagram and info.diagram_type in ("starport", "fleetcarrier")
    show_placeholder = not has_diagram and info.pad is not None and info.status_label == "Docking Approved"
    card_w = _FALLBACK_CARD_W if show_placeholder else _CARD_W
    client.send_shape(_CARD_ID, "rect", _CHROME_BORDER, _CHROME_FILL, _CARD_X, _CARD_Y, card_w, _CARD_H, ttl=_TTL, thickness=2)
    client.send_message("wntb_landing_title", "Landing", _TEXT_PRIMARY, _TEXT_X, _Y_TITLE, ttl=_TTL, size="large")
    client.send_message("wntb_landing_status", info.status_label, status_color, _TEXT_X, _Y_STATUS, ttl=_TTL)
    _send_or_clear(client, "wntb_landing_station", info.station, _TEXT_MUTED, _TEXT_X, _Y_STATION)
    _send_or_clear(client, "wntb_landing_pad", f"Pad {info.pad}" if info.pad is not None else "", _TEXT_MUTED, _TEXT_X, _Y_PAD)

    denied_label = (info.denied_reason or "Unknown") if info.status_label == "Docking Denied" else ""
    _send_or_clear(client, "wntb_landing_denied", denied_label, _STATUS_DENIED, _TEXT_X, _Y_DENIED)

    if info.show_diagram and info.diagram_type == "starport":
        _render_starport_diagram(client, info.pad)
        _clear_fleetcarrier_diagram(client)
        _clear_placeholder(client)
    elif info.show_diagram and info.diagram_type == "fleetcarrier":
        _render_fleetcarrier_diagram(client, info.pad, carrier_type)
        _clear_starport_diagram(client)
        _clear_placeholder(client)
    else:
        _clear_starport_diagram(client)
        _clear_fleetcarrier_diagram(client)
        if show_placeholder:
            _render_placeholder(client, info.pad)
        else:
            _clear_placeholder(client)


def clear(client: OverlayClient) -> None:
    client.send_shape(_CARD_ID, "rect", "", "", _CARD_X, _CARD_Y, 0, 0, ttl=1)
    for msg_id, y in _STATUS_TEXT_IDS:
        client.send_message(msg_id, "", "white", _TEXT_X, y, ttl=1)
    _clear_starport_diagram(client)
    _clear_fleetcarrier_diagram(client)
    _clear_placeholder(client)


def _send_or_clear(client: OverlayClient, msg_id: str, text: str, color: str, x: int, y: int) -> None:
    if text:
        client.send_message(msg_id, text, color, x, y, ttl=_TTL)
    else:
        client.send_message(msg_id, "", "white", x, y, ttl=1)


def _render_placeholder(client: OverlayClient, pad: int) -> None:
    """No pad-diagram family exists for this station type (e.g. an
    outpost). Stands in for the missing diagram with a plain landscape
    rectangle roughly at the position a real diagram would occupy, the pad
    number large inside it, and a short word-wrapped caption to its right."""
    box_x = _DIAGRAM_CX - _PLACEHOLDER_W // 2
    box_y = _DIAGRAM_CY - _PLACEHOLDER_H // 2
    client.send_shape(
        _PLACEHOLDER_RECT_ID, "rect", STROKE_COLOR, "", box_x, box_y, _PLACEHOLDER_W, _PLACEHOLDER_H,
        ttl=_TTL, thickness=2,
    )

    pad_text = str(pad)
    pad_x = _DIAGRAM_CX - (14 if len(pad_text) > 1 else 8)
    client.send_message(_PLACEHOLDER_PAD_ID, pad_text, ACTIVE_COLOR, pad_x, _DIAGRAM_CY - 14, ttl=_TTL, size="large")

    lines = textwrap.wrap(_FALLBACK_LABEL_TEXT, width=_FALLBACK_MAX_CHARS_PER_LINE)[:_FALLBACK_MAX_LINES]
    block_height = len(lines) * _FALLBACK_LINE_HEIGHT
    start_y = int(_DIAGRAM_CY - block_height / 2)
    for i, msg_id in enumerate(_FALLBACK_LINE_IDS):
        if i < len(lines):
            client.send_message(
                msg_id, lines[i], _TEXT_MUTED, _FALLBACK_LABEL_X, start_y + i * _FALLBACK_LINE_HEIGHT,
                ttl=_TTL, size=_FALLBACK_TEXT_SIZE,
            )
        else:
            client.send_message(msg_id, "", "white", _DIAGRAM_CX, _DIAGRAM_CY, ttl=1)


def _clear_placeholder(client: OverlayClient) -> None:
    client.send_shape(_PLACEHOLDER_RECT_ID, "rect", "", "", _DIAGRAM_CX, _DIAGRAM_CY, 0, 0, ttl=1)
    client.send_message(_PLACEHOLDER_PAD_ID, "", "white", _DIAGRAM_CX, _DIAGRAM_CY, ttl=1)
    for msg_id in _FALLBACK_LINE_IDS:
        client.send_message(msg_id, "", "white", _DIAGRAM_CX, _DIAGRAM_CY, ttl=1)


# --- Shared diagram geometry (target-agnostic - consumed by both the
# overlay-rendering functions below and ui's in-app Canvas diagram, which
# turns the exact same numbers into Canvas create_line/create_oval/
# create_rectangle calls) -------------------------------------------------

_FLEETCARRIER_BOX = (48, 76)  # box_w, box_h - the carrier layout's own unscaled bounding box


def starport_diagram_geometry(cx: float, cy: float, diagram_size: float, pad: Optional[int]) -> dict:
    """Pure pixel-space geometry for the starport pad-layout diagram."""
    r = diagram_size / 2 - 8
    shells = [_starport_shell_points(cx, cy, r, scale) for scale in _SHELL_SCALE]
    spokes = [(shells[0][i], shells[3][i]) for i in range(12)]
    marker = _starport_pad_pos(pad, cx, cy, r) if pad is not None else None
    return {"shells": shells, "spokes": spokes, "marker": marker}


def fleetcarrier_diagram_geometry(
    cx: float, cy: float, diagram_size: float, carrier_type: CarrierType, pad: Optional[int],
) -> List[Tuple[Tuple[float, float, float, float], bool]]:
    """Pure pixel-space geometry for the fleet-carrier pad grid."""
    box_w, box_h = _FLEETCARRIER_BOX
    pad_list = _fleetcarrier_pad_rects(carrier_type)
    pad_count = len(pad_list)
    scale = min((diagram_size - 16) / box_w, (diagram_size - 16) / box_h, 4)
    active_index = ((pad - 1) % pad_count + pad_count) % pad_count if pad is not None and pad_count else -1

    rects: List[Tuple[Tuple[float, float, float, float], bool]] = []
    for i, (x1, y1, x2, y2) in enumerate(pad_list):
        sx1, sy1 = cx + x1 * scale, cy - y1 * scale
        sx2, sy2 = cx + x2 * scale, cy - y2 * scale
        rects.append(((min(sx1, sx2), min(sy1, sy2), max(sx1, sx2), max(sy1, sy2)), i == active_index))
    return rects


def _render_starport_diagram(client: OverlayClient, pad: Optional[int]) -> None:
    geometry = starport_diagram_geometry(_DIAGRAM_CX, _DIAGRAM_CY, _DIAGRAM_SIZE, pad)

    for shape_id, points in zip(_STARPORT_SHELL_IDS, geometry["shells"]):
        closed = list(points) + [points[0]]
        client.send_vector(shape_id, [{"x": x, "y": y} for x, y in closed], STROKE_COLOR, ttl=_TTL)

    for i, shape_id in enumerate(_STARPORT_SPOKE_IDS):
        outer, inner = geometry["spokes"][i]
        client.send_vector(
            shape_id, [{"x": outer[0], "y": outer[1]}, {"x": inner[0], "y": inner[1]}], STROKE_COLOR, ttl=_TTL,
        )

    if geometry["marker"] is not None:
        px, py = geometry["marker"]
        client.send_vector(
            _STARPORT_PADMARK_ID,
            [{"x": px, "y": py, "color": ACTIVE_COLOR, "marker": "circle"}],
            ACTIVE_COLOR, ttl=_TTL,
        )
    else:
        client.send_vector(_STARPORT_PADMARK_ID, [], "", ttl=1)


def _render_fleetcarrier_diagram(client: OverlayClient, pad: Optional[int], carrier_type: CarrierType) -> None:
    rects = fleetcarrier_diagram_geometry(_DIAGRAM_CX, _DIAGRAM_CY, _DIAGRAM_SIZE, carrier_type, pad)
    pad_count = len(rects)

    for i, shape_id in enumerate(_FLEETCARRIER_PAD_IDS):
        if i >= pad_count:
            client.send_shape(shape_id, "rect", "", "", _DIAGRAM_CX, _DIAGRAM_CY, 0, 0, ttl=1)
            continue
        (x1, y1, x2, y2), is_active = rects[i]
        client.send_shape(
            shape_id, "rect", STROKE_COLOR, ACTIVE_COLOR if is_active else "",
            int(round(x1)), int(round(y1)), max(int(round(x2 - x1)), 1), max(int(round(y2 - y1)), 1), ttl=_TTL,
        )

    client.send_message(_FLEETCARRIER_LABEL_ID, "", "white", _DIAGRAM_CX, _DIAGRAM_CY, ttl=1)


def _clear_starport_diagram(client: OverlayClient) -> None:
    for shape_id in _STARPORT_SHELL_IDS + _STARPORT_SPOKE_IDS:
        client.send_vector(shape_id, [], "", ttl=1)
    client.send_vector(_STARPORT_PADMARK_ID, [], "", ttl=1)


def _clear_fleetcarrier_diagram(client: OverlayClient) -> None:
    # Parked at the diagram's own center (_DIAGRAM_CX/_DIAGRAM_CY), not
    # literal (0, 0) - a Plugin Group's Fill-mode bounding box includes
    # every live payload's raw (x, y) unconditionally, even a zero-size
    # rect that renders nothing, so a "cleared" payload sent to (0, 0) drags
    # the group's computed anchor/scale toward the screen's top-left corner
    # for as long as that payload stays live.
    for shape_id in _FLEETCARRIER_PAD_IDS:
        client.send_shape(shape_id, "rect", "", "", _DIAGRAM_CX, _DIAGRAM_CY, 0, 0, ttl=1)
    client.send_message(_FLEETCARRIER_LABEL_ID, "", "white", _DIAGRAM_CX, _DIAGRAM_CY, ttl=1)


# --- Controller: this mode's one entry point for load.py/ui.py -----------

_overlay_client = overlay.OverlayClient()


def set_overlay_client(client: overlay.OverlayClient) -> None:
    global _overlay_client
    _overlay_client = client


class LandingController:
    def __init__(self) -> None:
        self.tracker = LandingTracker(on_change=self._on_change)
        self._ui_frame: Optional[tk.Widget] = None

        self._info_label: Optional[tk.Label] = None
        self._diagram_canvas: Optional[tk.Canvas] = None
        self._diagram_visible = False

        self._enabled_var: Optional[tk.BooleanVar] = None
        self._overlay_var: Optional[tk.BooleanVar] = None
        self._in_app_var: Optional[tk.BooleanVar] = None
        self._dependent_widgets: List[tk.Widget] = []
        self._result_label: Optional[nb.Label] = None

    def handle_event(self, entry: Dict[str, Any], cmdr: str, system: Optional[str], station: Optional[str], state: Dict[str, Any]) -> None:
        if entry.get("event") in DOCKING_EVENTS:
            self.tracker.handle_event(entry)

    def _on_change(self, snapshot: LandingSnapshot) -> None:
        """Called synchronously from load.py's journal dispatch on every
        docking-state change - the actual overlay send is pushed onto a
        background thread; the in-app label/canvas update is marshalled
        onto the Tk main thread via `after`."""
        cfg = load_config()
        if not cfg.enabled:
            return

        if snapshot.docked and snapshot.hidden_after_landing:
            if cfg.overlay_enabled:
                self._render_overlay_async(None)
            if cfg.in_app_enabled and self._ui_frame is not None:
                self._ui_frame.after(0, lambda: self._update_widgets("", None, None))
            return

        info = build_landing_display_info(
            snapshot.docking, snapshot.docked, snapshot.last_assigned_pad,
            snapshot.last_station_type, snapshot.last_carrier_type,
        )

        if cfg.overlay_enabled:
            self._render_overlay_async(info, snapshot.last_carrier_type)

        if cfg.in_app_enabled and self._ui_frame is not None:
            text = format_in_app_text(info)
            carrier_type = snapshot.last_carrier_type
            self._ui_frame.after(0, lambda t=text, i=info, c=carrier_type: self._update_widgets(t, i, c))

    def _render_overlay_async(self, info: Optional[LandingDisplayInfo], carrier_type: CarrierType = None) -> None:
        def worker() -> None:
            try:
                if info is None:
                    clear(_overlay_client)
                else:
                    render(info, carrier_type, _overlay_client)
            except OSError:
                logger.debug("Could not reach EDMCOverlay for landing pad overlay", exc_info=True)

        threading.Thread(target=worker, name="WNTB-landing-render", daemon=True).start()

    def _clear_display(self) -> None:
        """Clears whichever of the overlay/in-app widgets is currently
        turned off, per the live config - called right after a config
        change so a toggle takes effect right away."""
        cfg = load_config()
        if not (cfg.enabled and cfg.in_app_enabled):
            self._update_widgets("", None, None)
        if not (cfg.enabled and cfg.overlay_enabled):
            self._render_overlay_async(None)

    # --- main-panel widgets ("always" placement) --------------------------

    def build_panel(self, parent: tk.Frame) -> None:
        # No enable/disable toggle here - Landing's on/off state lives
        # solely in the Settings tab's "Enable Landing" checkbox (see
        # build_settings() below); the main panel only ever shows the
        # live status line/diagram once enabled, never a control for
        # turning it on or off.
        self._ui_frame = parent

        self._info_label = panelkit.wrap_label(parent, text="")
        self._info_label.grid(row=0, column=0, sticky=tk.W, pady=(6, 0))
        self._info_label.grid_remove()

        # In-app pad-layout diagram, drawn straight onto a Canvas rather
        # than an image - fed by the same target-agnostic geometry the
        # overlay draws from. No explicit background= at construction -
        # theme.update() recolors a plain tk.Canvas on its own, but only
        # when it hasn't already been given an explicit background.
        self._diagram_canvas = tk.Canvas(
            parent, width=_LANDING_DIAGRAM_SIZE, height=_LANDING_DIAGRAM_SIZE, highlightthickness=0,
        )
        # columnspan=3 (matching panelkit.add_separator's own 3-column
        # convention for this shared "always" frame) with no sticky, so Tk
        # centers the fixed-size canvas across those columns instead of
        # pinning it to column 0's own left edge. This only actually
        # centers relative to the *whole app window* because `parent` (this
        # frame) and its own parent `_always_frame` are now stretched to
        # the app's real content width via sticky="ew" plus a weighted
        # middle column - see ui.py's `_stack_features`/`create_plugin_app`
        # (R.W. Harper, 2026-09-18; centering fix 2026-09-19).
        self._diagram_canvas.grid(row=1, column=0, columnspan=3, pady=(4, 0))
        self._diagram_canvas.grid_remove()

    def _update_widgets(self, text: str, info: Optional[LandingDisplayInfo], carrier_type: CarrierType) -> None:
        if self._info_label is not None:
            if text:
                self._info_label["text"] = f"Landing: {text}"
                self._info_label.grid()
            else:
                self._info_label["text"] = ""
                self._info_label.grid_remove()
        self._update_diagram(info, carrier_type)

    def _update_diagram(self, info: Optional[LandingDisplayInfo], carrier_type: CarrierType) -> None:
        canvas = self._diagram_canvas
        if canvas is None:
            return

        canvas.delete("all")
        show = info is not None and info.show_diagram and info.diagram_type is not None
        self._diagram_visible = show
        if not show:
            canvas.grid_remove()
            return

        stroke_color, marker_color = _diagram_colors()
        cx = cy = _LANDING_DIAGRAM_SIZE / 2
        if info.diagram_type == "starport":
            geometry = starport_diagram_geometry(cx, cy, _LANDING_DIAGRAM_SIZE, info.pad)
            for shell in geometry["shells"]:
                closed = list(shell) + [shell[0]]
                canvas.create_line(*[c for point in closed for c in point], fill=stroke_color, width=2)
            for outer, inner in geometry["spokes"]:
                canvas.create_line(outer[0], outer[1], inner[0], inner[1], fill=stroke_color, width=2)
            if geometry["marker"] is not None:
                mx, my = geometry["marker"]
                # Filled, not just outlined - a hollow ring at this radius
                # read as barely-there against the panel background (R.W.
                # Harper, 2026-09-18). A thin dark outline keeps the solid
                # marker_color fill from blending into a same-hued stroke
                # line passing behind it.
                radius = 7
                canvas.create_oval(mx - radius, my - radius, mx + radius, my + radius,
                                  fill=marker_color, outline="#000000", width=1)
        elif info.diagram_type == "fleetcarrier":
            for (x1, y1, x2, y2), is_active in fleetcarrier_diagram_geometry(
                cx, cy, _LANDING_DIAGRAM_SIZE, carrier_type, info.pad,
            ):
                canvas.create_rectangle(
                    x1, y1, x2, y2, outline=stroke_color, width=2, fill=marker_color if is_active else "",
                )

        canvas.grid()

    # --- Settings tab --------------------------------------------------------

    def build_settings(self, notebook: nb.Notebook) -> None:
        frame = nb.Frame(notebook)
        frame.columnconfigure(0, weight=1)
        notebook.add(frame, text="Landing")

        cfg = load_config()

        nb.Label(
            frame,
            text=(
                "Shows docking status and which pad you're assigned while requesting/approaching a "
                "dock — on your in-game overlay (a pad-layout diagram too, via EDMCOverlay), and/or "
                "as a line + diagram on the EDMC main panel itself. Connection settings for the overlay "
                "are on the Overlay Connection tab."
            ),
            wraplength=440, justify=tk.LEFT,
        ).grid(row=0, column=0, sticky=tk.W, padx=10, pady=(10, 4))

        HyperlinkLabel(
            frame, text="Get EDMCOverlay", background=nb.Label().cget("background"),
            url="https://github.com/inorton/EDMCOverlay", underline=True,
        ).grid(row=1, column=0, sticky=tk.W, padx=10, pady=(0, 8))

        self._enabled_var = tk.BooleanVar(value=cfg.enabled)
        nb.Checkbutton(
            frame, text="Enable Landing", variable=self._enabled_var, command=self._update_dependent_state,
        ).grid(row=2, column=0, sticky=tk.W, padx=10, pady=2)

        sub = nb.Frame(frame)
        sub.grid(row=3, column=0, sticky=tk.W, padx=(28, 10))

        self._overlay_var = tk.BooleanVar(value=cfg.overlay_enabled)
        overlay_check = nb.Checkbutton(sub, text="Show on Overlay", variable=self._overlay_var)
        overlay_check.grid(row=0, column=0, sticky=tk.W, pady=2)

        self._in_app_var = tk.BooleanVar(value=cfg.in_app_enabled)
        in_app_check = nb.Checkbutton(sub, text="Show in EDMC app", variable=self._in_app_var)
        in_app_check.grid(row=1, column=0, sticky=tk.W, pady=2)

        self._dependent_widgets = [overlay_check, in_app_check]

        action_row = tk.Frame(frame)
        action_row.grid(row=4, column=0, sticky=tk.W, padx=10, pady=(6, 2))
        tk.Button(action_row, text="Test Overlay", command=self._test_landing).pack(side=tk.LEFT)
        self._result_label = nb.Label(action_row, text="", wraplength=320, justify=tk.LEFT)
        self._result_label.pack(side=tk.LEFT, padx=(10, 0))

        nb.Label(
            frame,
            text=(
                "(Test Overlay works even while disabled above, and also previews the in-app text/"
                "diagram, regardless of the checkboxes.)"
            ),
            wraplength=440, justify=tk.LEFT,
        ).grid(row=5, column=0, sticky=tk.W, padx=10, pady=(0, 10))

        self._update_dependent_state()

    def _update_dependent_state(self) -> None:
        if self._enabled_var is None:
            return
        state = tk.NORMAL if self._enabled_var.get() else tk.DISABLED
        for widget in self._dependent_widgets:
            try:
                widget["state"] = state
            except tk.TclError:
                pass

    def _test_landing(self) -> None:
        if self._result_label is None:
            return

        preview_info = LandingDisplayInfo(
            status_label="Docking Approved", station="Preview Station", pad=24,
            diagram_type="starport", show_diagram=True,
        )
        self._update_widgets(format_in_app_text(preview_info), preview_info, None)

        cfg = overlay.load_config()
        client = overlay.OverlayClient(cfg)
        frame = self._result_label

        def worker() -> None:
            try:
                render(preview_info, None, client)
                outcome, color = "Sent — check your overlay (and the main panel diagram).", "#2e7d32"
            except OSError as err:
                outcome, color = f"Could not reach EDMCOverlay at {cfg.host}:{cfg.port} ({err}).", "#c07000"
            try:
                frame.after(0, lambda: (frame.configure(text=outcome, foreground=color)))
            except tk.TclError:
                pass

        threading.Thread(target=worker, name="WNTB-landing-test", daemon=True).start()

    def save_settings(self) -> None:
        if self._enabled_var is None:
            return
        save_config(LandingConfig(
            enabled=bool(self._enabled_var.get()),
            overlay_enabled=bool(self._overlay_var.get()) if self._overlay_var is not None else DEFAULT_OVERLAY_ENABLED,
            in_app_enabled=bool(self._in_app_var.get()) if self._in_app_var is not None else DEFAULT_IN_APP_ENABLED,
        ))
        self._clear_display()


controller = LandingController()


def handle_event(entry: Dict[str, Any], cmdr: str, system: Optional[str], station: Optional[str], state: Dict[str, Any]) -> None:
    controller.handle_event(entry, cmdr, system, station, state)


def build_panel(parent: tk.Frame) -> None:
    controller.build_panel(parent)


def build_settings(notebook: nb.Notebook) -> None:
    controller.build_settings(notebook)


def save_settings() -> None:
    controller.save_settings()
