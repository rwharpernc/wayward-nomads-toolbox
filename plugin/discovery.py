"""Discovery: alerts when the system you just jumped into, or a body you
just scanned/mapped, has never been found by anyone before - drawn via
overlay.py, same shape as interdiction.py/landing.py.

Detection relies on fields the journal already carries, no extra scanning
required on the player's part:

1. System-level: the instant you jump into a system, the game auto-scans
   the arrival star and reports it as a "Scan" event with `ScanType`:
   "AutoScan" — that event's `WasDiscovered` field is `False` when nobody
   has ever scanned this star before. Detected via the presence of
   `StarType` on the Scan entry (only stars carry it).
2. Body-level (scan): every "Scan" event carries its own `WasDiscovered` —
   `False` means you're the first to scan it.
3. Body-level (mapped): "SAAScanComplete" carries no discovery flag of its
   own — whether it makes you first-to-map is decided by the *previous*
   Scan event's own `WasMapped` field for the same body, cached per body
   name and consulted when the matching SAAScanComplete arrives. Cleared
   on system change so a stale cache entry can never leak into the next
   system.

Deliberately silent on the (overwhelmingly common) "already discovered"
case — this reads as a celebratory alert for the genuinely new case, not a
running status readout.

Lives inside Exploration mode's panel (PANEL_PLACEMENT = "exploration").
"""

from __future__ import annotations

import logging
import os
import queue
import threading
from dataclasses import dataclass
from typing import Any, Dict, Mapping, Optional, Tuple

import tkinter as tk

import myNotebook as nb
from config import appname, config

from . import neutron_finder, overlay, panelkit
from .overlay import OverlayClient

plugin_name = os.path.basename(os.path.dirname(__file__))
logger = logging.getLogger(f"{appname}.{plugin_name}")

PANEL_PLACEMENT = "exploration"

_CFG_ENABLED = "wntb_discovery_enabled"
_CFG_X = "wntb_discovery_x"
_CFG_Y = "wntb_discovery_y"
DEFAULT_ENABLED = False

# Position IS user-configurable (unlike Interdiction/Landing's fixed
# placement) - Settings exposes these as the anchor (the system title's own
# position); every other line in render() is a fixed offset from that one
# point, so the whole two-alert block moves together. Default lands
# top-center-ish on a 1920-wide HUD.
DEFAULT_X = 700
DEFAULT_Y = 60

SYSTEM_CLEAR_S = 12.0
BODY_CLEAR_S = 8.0

DISCOVERY_EVENTS = ("Scan", "SAAScanComplete")


@dataclass
class DiscoveryConfig:
    enabled: bool = DEFAULT_ENABLED
    x: int = DEFAULT_X
    y: int = DEFAULT_Y


def load_config() -> DiscoveryConfig:
    return DiscoveryConfig(
        enabled=config.get_bool(_CFG_ENABLED, default=DEFAULT_ENABLED),
        x=_get_int(_CFG_X, DEFAULT_X),
        y=_get_int(_CFG_Y, DEFAULT_Y),
    )


def save_config(cfg: DiscoveryConfig) -> None:
    config.set(_CFG_ENABLED, cfg.enabled)
    config.set(_CFG_X, str(cfg.x))
    config.set(_CFG_Y, str(cfg.y))


def _get_int(key: str, default: int) -> int:
    raw = config.get_str(key)
    try:
        return int(raw) if raw else default
    except ValueError:
        return default


@dataclass
class DiscoverySnapshot:
    system_visible: bool = False
    system_name: Optional[str] = None
    body_visible: bool = False
    body_name: Optional[str] = None
    body_action: Optional[str] = None  # "scanned" | "mapped"


class DiscoveryTracker:
    """Combines system-entry tracking (handle_system_change) with Scan/
    SAAScanComplete journal events (handle_event) to decide when to fire a
    "first discovery" alert."""

    def __init__(self, on_change) -> None:
        self._on_change = on_change
        self._system_name: Optional[str] = None
        self._star_evaluated = False
        self._mapped_cache: Dict[str, bool] = {}

        self._system_visible = False
        self._system_display_name: Optional[str] = None
        self._body_visible = False
        self._body_name: Optional[str] = None
        self._body_action: Optional[str] = None

        self._system_timer: Optional[threading.Timer] = None
        self._body_timer: Optional[threading.Timer] = None
        self._test_timer: Optional[threading.Timer] = None

    def get_snapshot(self) -> DiscoverySnapshot:
        return DiscoverySnapshot(
            system_visible=self._system_visible,
            system_name=self._system_display_name,
            body_visible=self._body_visible,
            body_name=self._body_name,
            body_action=self._body_action,
        )

    def trigger_test(self) -> None:
        """Settings tab's "Test Discovery" button — fires both alert slots
        at once through the same snapshot the live path renders."""
        self._clear_test_timer()
        self._show_system("Test System")
        self._show_body("Test Body 1 c", "scanned")

        def _map() -> None:
            self._test_timer = None
            self._show_body("Test Body 1 c", "mapped")

        self._test_timer = threading.Timer(2.0, _map)
        self._test_timer.daemon = True
        self._test_timer.start()

    def handle_system_change(self, system: Optional[str]) -> None:
        """Called whenever the current system name is (re)established —
        resets per-system discovery state so a body cached from the
        previous system can never be mistaken for one in this system."""
        if system and system != self._system_name:
            self._system_name = system
            self._star_evaluated = False
            self._mapped_cache = {}

    def handle_event(self, entry: Mapping[str, Any]) -> None:
        event = entry.get("event")

        if event == "Scan":
            body_name = entry.get("BodyName")
            if not body_name:
                return
            was_discovered = entry.get("WasDiscovered")
            was_mapped = entry.get("WasMapped")
            if isinstance(was_mapped, bool):
                self._mapped_cache[body_name] = was_mapped

            if "StarType" in entry and not self._star_evaluated:
                self._star_evaluated = True
                if was_discovered is False:
                    self._show_system(self._system_name or body_name)

            if was_discovered is False:
                self._show_body(body_name, "scanned")
            return

        if event == "SAAScanComplete":
            body_name = entry.get("BodyName")
            if not body_name:
                return
            was_mapped = self._mapped_cache.get(body_name)
            self._mapped_cache[body_name] = True
            if was_mapped is False:
                self._show_body(body_name, "mapped")
            return

    def _show_system(self, name: str) -> None:
        self._system_visible = True
        self._system_display_name = name
        self._schedule_system_clear(SYSTEM_CLEAR_S)
        self._emit_changed()

    def _show_body(self, name: str, action: str) -> None:
        self._body_visible = True
        self._body_name = name
        self._body_action = action
        self._schedule_body_clear(BODY_CLEAR_S)
        self._emit_changed()

    def _schedule_system_clear(self, seconds: float) -> None:
        if self._system_timer is not None:
            self._system_timer.cancel()

        def _clear() -> None:
            self._system_visible = False
            self._system_display_name = None
            self._system_timer = None
            self._emit_changed()

        self._system_timer = threading.Timer(seconds, _clear)
        self._system_timer.daemon = True
        self._system_timer.start()

    def _schedule_body_clear(self, seconds: float) -> None:
        if self._body_timer is not None:
            self._body_timer.cancel()

        def _clear() -> None:
            self._body_visible = False
            self._body_name = None
            self._body_action = None
            self._body_timer = None
            self._emit_changed()

        self._body_timer = threading.Timer(seconds, _clear)
        self._body_timer.daemon = True
        self._body_timer.start()

    def _clear_test_timer(self) -> None:
        if self._test_timer is not None:
            self._test_timer.cancel()
            self._test_timer = None

    def _emit_changed(self) -> None:
        self._on_change(self.get_snapshot())


# --- Rendering (overlay.py's OverlayClient is generic; this is the one
# place that knows what a discovery alert should look like) ---------------

_SYSTEM_TITLE_ID = "wntb_discovery_system_title"
_SYSTEM_NAME_ID = "wntb_discovery_system_name"
_BODY_TITLE_ID = "wntb_discovery_body_title"
_BODY_NAME_ID = "wntb_discovery_body_name"

# Each alert now sits inside its own semi-transparent card - exactly
# landing.py's own _CHROME_BORDER/_CHROME_FILL recipe (same alpha values,
# same thickness, same registered-Plugin-Group treatment), just re-tinted
# per alert (amber for system, cyan for body) and without landing's own
# diagram shapes.
_Y_NAME_OFFSET = 38
_Y_BODY_OFFSET = 150

_SYSTEM_TITLE_COLOR = "#fbbf24"  # amber-400
_SYSTEM_NAME_COLOR = "#fef3c7"  # amber-100 - softer than pure white, still high-contrast
_BODY_TITLE_COLOR = "#67e8f9"  # cyan-300
_BODY_NAME_COLOR = "#e0f7fa"  # cyan-50

_SYSTEM_BORDER_COLOR = "#80fbbf24"  # amber-400 at 50% alpha - landing.py's own _CHROME_BORDER recipe
_BODY_BORDER_COLOR = "#8067e8f9"  # cyan-300 at 50% alpha - same recipe
_CHROME_FILL = "#d9000000"  # black at 85% alpha - identical to landing.py's own _CHROME_FILL
_CARD_BORDER_THICKNESS = 2

_CARD_W = 460
_CARD_PAD_X = 22
_CARD_PAD_TOP = 16
_CARD_H = _Y_NAME_OFFSET + 46  # room for huge title + large name + bottom padding

# No text-metrics query exists over the wire protocol (same limitation
# mining_overlay.py's own _OVERLAY_CHAR_WIDTH_PX notes), so each line's
# width is estimated from character count to center it in the card -
# tuned to look right rather than measured, erring slightly wide (a bit
# more centering slop) rather than narrow (text creeping off-center).
_CHAR_WIDTH_LARGE = 11
_CHAR_WIDTH_HUGE = 14

_SYSTEM_CARD_ID = "wntb_discovery_system_card"
_BODY_CARD_ID = "wntb_discovery_body_card"

_BODY_ACTION_TEXT = {
    "scanned": "First scan of a new discovery!",
    "mapped": "First to map this body!",
}

# This mode's own EDMCModernOverlay Plugin Group - same treatment as
# landing.py's GROUP_NAME/GROUP_PREFIX (see load.py's registration call),
# so the card and its text anchor/scale together as one unit.
GROUP_NAME = "wntb_discovery"
GROUP_PREFIX = "wntb_discovery_"


def _card_geometry(x: int, y: int) -> Tuple[int, int]:
    """Top-left corner of the card behind a title/name pair anchored at
    (x, y) - shared by system and body slots since both use the same
    title/name layout, just at a different y."""
    return x - _CARD_PAD_X, y - _CARD_PAD_TOP


def _card_center_x(x: int) -> int:
    """Horizontal center of the card anchored at `x` - shared by system
    and body slots since both use the same card width."""
    return x - _CARD_PAD_X + _CARD_W // 2


def _centered_x(text: str, size: str, center_x: int) -> int:
    """Left-edge draw position that centers `text` on `center_x`, using
    this module's own estimated per-size character width."""
    char_width = _CHAR_WIDTH_HUGE if size == "huge" else _CHAR_WIDTH_LARGE
    return center_x - (len(text) * char_width) // 2


def render(snapshot: DiscoverySnapshot, client: OverlayClient, x: int = DEFAULT_X, y: int = DEFAULT_Y) -> None:
    """Draws (or clears) both alert slots, anchored at (x, y). Title and
    name are each horizontally centered in the card independently, since
    they're usually different lengths."""
    center_x = _card_center_x(x)

    if snapshot.system_visible:
        card_x, card_y = _card_geometry(x, y)
        client.send_shape(
            _SYSTEM_CARD_ID, "rect", _SYSTEM_BORDER_COLOR, _CHROME_FILL, card_x, card_y, _CARD_W, _CARD_H,
            ttl=30, thickness=_CARD_BORDER_THICKNESS,
        )
        title_text = "NEW SYSTEM DISCOVERY"
        name_text = snapshot.system_name or "Unknown system"
        client.send_message(
            _SYSTEM_TITLE_ID, title_text, _SYSTEM_TITLE_COLOR, _centered_x(title_text, "huge", center_x), y,
            ttl=30, size="huge",
        )
        client.send_message(
            _SYSTEM_NAME_ID, name_text, _SYSTEM_NAME_COLOR, _centered_x(name_text, "large", center_x),
            y + _Y_NAME_OFFSET, ttl=30, size="large",
        )
    else:
        _clear_system(client, x, y)

    if snapshot.body_visible:
        body_y = y + _Y_BODY_OFFSET
        card_x, card_y = _card_geometry(x, body_y)
        title_text = _BODY_ACTION_TEXT.get(snapshot.body_action or "", "New discovery!")
        name_text = snapshot.body_name or "Unknown body"
        client.send_shape(
            _BODY_CARD_ID, "rect", _BODY_BORDER_COLOR, _CHROME_FILL, card_x, card_y, _CARD_W, _CARD_H,
            ttl=30, thickness=_CARD_BORDER_THICKNESS,
        )
        client.send_message(
            _BODY_TITLE_ID, title_text, _BODY_TITLE_COLOR, _centered_x(title_text, "huge", center_x), body_y,
            ttl=30, size="huge",
        )
        client.send_message(
            _BODY_NAME_ID, name_text, _BODY_NAME_COLOR, _centered_x(name_text, "large", center_x),
            body_y + _Y_NAME_OFFSET, ttl=30, size="large",
        )
    else:
        _clear_body(client, x, y)


def clear(client: OverlayClient, x: int = DEFAULT_X, y: int = DEFAULT_Y) -> None:
    _clear_system(client, x, y)
    _clear_body(client, x, y)


def _clear_system(client: OverlayClient, x: int, y: int) -> None:
    card_x, card_y = _card_geometry(x, y)
    client.send_shape(_SYSTEM_CARD_ID, "rect", "", "", card_x, card_y, 0, 0, ttl=1)
    client.send_message(_SYSTEM_TITLE_ID, "", "white", x, y, ttl=1)
    client.send_message(_SYSTEM_NAME_ID, "", "white", x, y + _Y_NAME_OFFSET, ttl=1)


def _clear_body(client: OverlayClient, x: int, y: int) -> None:
    body_y = y + _Y_BODY_OFFSET
    card_x, card_y = _card_geometry(x, body_y)
    client.send_shape(_BODY_CARD_ID, "rect", "", "", card_x, card_y, 0, 0, ttl=1)
    client.send_message(_BODY_TITLE_ID, "", "white", x, body_y, ttl=1)
    client.send_message(_BODY_NAME_ID, "", "white", x, body_y + _Y_NAME_OFFSET, ttl=1)


# --- Controller: this mode's one entry point for load.py/ui.py -----------

_overlay_client = overlay.OverlayClient()

_IDLE_STATUS = "Watching for new discoveries…"
_DISABLED_STATUS = "Discovery alerts are disabled."
_NEUTRON_NO_POSITION = "Neutron: position unknown - jump or reload first"
_NEUTRON_SEARCHING = "Neutron: searching spansh.co.uk..."
_NEUTRON_FAILED = "Neutron: lookup failed - see EDMarketConnector.log"


def set_overlay_client(client: overlay.OverlayClient) -> None:
    global _overlay_client
    _overlay_client = client


def _status_text(snapshot: DiscoverySnapshot) -> str:
    parts = []
    if snapshot.system_visible:
        parts.append(f"New system: {snapshot.system_name or 'Unknown system'}")
    if snapshot.body_visible:
        action = "Mapped" if snapshot.body_action == "mapped" else "Scanned"
        parts.append(f"{action} first: {snapshot.body_name or 'Unknown body'}")
    return " | ".join(parts) if parts else _IDLE_STATUS


class DiscoveryController:
    def __init__(self) -> None:
        self.tracker = DiscoveryTracker(on_change=self._on_change)
        self._status_label: Optional[tk.Label] = None
        self._toggle_btn: Optional[tk.Button] = None
        self._toggle_off_colors = ("", "")

        self._enabled_var: Optional[tk.BooleanVar] = None
        self._x_var: Optional[tk.StringVar] = None
        self._y_var: Optional[tk.StringVar] = None
        self._dependent_widgets = []
        self._result_label: Optional[nb.Label] = None

        # "Neutron" button (see neutron_finder.py): position comes from the
        # journal's StarPos; the lookup runs on a worker thread and hands its
        # result back through a queue polled via after(), like gec_poi_panel.py.
        self._star_pos: Optional[Tuple[float, float, float]] = None
        self._current_system: Optional[str] = None
        self._neutron_btn: Optional[tk.Button] = None
        self._neutron_label: Optional[tk.Label] = None
        self._neutron_parent: Optional[tk.Frame] = None
        self._neutron_generation = 0
        self._neutron_queue: "queue.Queue[Tuple[int, Optional[neutron_finder.NearestNeutron], bool]]" = queue.Queue()

    def handle_event(self, entry: Dict[str, Any], cmdr: str, system: Optional[str], station: Optional[str], state: Dict[str, Any]) -> None:
        if system:
            self._current_system = system
        if entry.get("event") in ("FSDJump", "Location"):
            star_pos = entry.get("StarPos")
            if (isinstance(star_pos, list) and len(star_pos) == 3
                    and all(isinstance(v, (int, float)) for v in star_pos)):
                self._star_pos = (float(star_pos[0]), float(star_pos[1]), float(star_pos[2]))
        if system:
            self.tracker.handle_system_change(system)
        if entry.get("event") in DISCOVERY_EVENTS:
            self.tracker.handle_event(entry)

    def _on_change(self, snapshot: DiscoverySnapshot) -> None:
        cfg = load_config()
        if not cfg.enabled:
            return

        self._sync_status_label()

        def worker(x=cfg.x, y=cfg.y) -> None:
            try:
                render(snapshot, _overlay_client, x, y)
            except OSError:
                logger.debug("Could not reach EDMCOverlay for discovery alert", exc_info=True)

        threading.Thread(target=worker, name="WNTB-discovery-render", daemon=True).start()

    def _sync_status_label(self) -> None:
        if self._status_label is None:
            return
        snapshot = self.tracker.get_snapshot()
        self._status_label["text"] = _status_text(snapshot) if load_config().enabled else _DISABLED_STATUS

    # --- main-panel widgets -------------------------------------------------

    def build_panel(self, parent: tk.Frame) -> None:
        row = tk.Frame(parent)
        row.grid(row=0, column=0, sticky=tk.W, pady=(4, 0))
        self._toggle_btn = tk.Button(row, text="Discovery Alerts", command=self._on_toggle_click)
        self._toggle_btn.pack(side=tk.LEFT)
        self._toggle_off_colors = panelkit.capture_toggle_off_colors(self._toggle_btn)
        panelkit.apply_toggle_button_state(self._toggle_btn, load_config().enabled, self._toggle_off_colors)

        self._neutron_btn = tk.Button(row, text="Neutron", command=self._on_neutron_click)
        self._neutron_btn.pack(side=tk.LEFT, padx=(24, 0))  # same gap ui.py puts between Auto-Honk and Discovery

        self._status_label = panelkit.wrap_label(parent, text=_IDLE_STATUS)
        self._status_label.grid(row=1, column=0, sticky=tk.W, pady=(4, 0))
        self._sync_status_label()

        self._neutron_label = panelkit.wrap_label(parent, text="")
        self._neutron_label.grid(row=2, column=0, sticky=tk.W, pady=(2, 0))
        self._neutron_label.grid_remove()  # nothing to say until the first click
        self._neutron_parent = parent
        parent.after(200, self._poll_neutron_queue)

    # --- Neutron button ------------------------------------------------------

    def _show_neutron_text(self, text: str) -> None:
        if self._neutron_label is not None:
            self._neutron_label["text"] = text
            self._neutron_label.grid()

    def _on_neutron_click(self) -> None:
        if self._star_pos is None:
            self._show_neutron_text(_NEUTRON_NO_POSITION)
            return
        self._neutron_generation += 1
        generation = self._neutron_generation
        self._show_neutron_text(_NEUTRON_SEARCHING)
        if self._neutron_btn is not None:
            self._neutron_btn.config(state=tk.DISABLED)
        x, y, z = self._star_pos
        threading.Thread(
            target=self._neutron_worker, args=(generation, x, y, z, self._current_system),
            name="WNTB-neutron-find", daemon=True,
        ).start()

    def _neutron_worker(self, generation: int, x: float, y: float, z: float, current_system: Optional[str]) -> None:
        """Runs off the main thread - must not touch any Tk widget."""
        try:
            result = neutron_finder.find_nearest_neutron(x, y, z, current_system)
        except Exception:
            logger.exception("Neutron lookup failed for (%s, %s, %s)", x, y, z)
            self._neutron_queue.put((generation, None, True))
            return
        self._neutron_queue.put((generation, result, False))

    def _poll_neutron_queue(self) -> None:
        """Runs on the main thread via after() - safe to touch widgets."""
        try:
            generation, result, failed = self._neutron_queue.get_nowait()
        except queue.Empty:
            pass
        else:
            if generation == self._neutron_generation:
                if self._neutron_btn is not None:
                    self._neutron_btn.config(state=tk.NORMAL)
                if failed or result is None:
                    self._show_neutron_text(_NEUTRON_FAILED)
                else:
                    # Copy the full (untruncated) name so it can be pasted straight
                    # into the galaxy map's search box.
                    copied = self._neutron_parent is not None and panelkit.copy_to_clipboard(
                        self._neutron_parent, result.system)
                    suffix = " (copied)" if copied else ""
                    self._show_neutron_text(
                        f"Neutron: {neutron_finder.display_name(result.system)} - "
                        f"{result.distance_ly:,.1f} ly{suffix}"
                    )
        if self._neutron_parent is not None:
            self._neutron_parent.after(200, self._poll_neutron_queue)

    def _on_toggle_click(self) -> None:
        cfg = load_config()
        cfg.enabled = not cfg.enabled
        save_config(cfg)
        panelkit.apply_toggle_button_state(self._toggle_btn, cfg.enabled, self._toggle_off_colors)
        self._sync_status_label()
        if not cfg.enabled:
            def worker(x=cfg.x, y=cfg.y) -> None:
                try:
                    clear(_overlay_client, x, y)
                except OSError:
                    logger.debug("Could not reach EDMCOverlay to clear discovery alerts", exc_info=True)

            threading.Thread(target=worker, name="WNTB-discovery-clear", daemon=True).start()

    # --- Settings tab --------------------------------------------------------

    def build_settings(self, notebook: nb.Notebook) -> None:
        frame = nb.Frame(notebook)
        frame.columnconfigure(0, weight=1)
        notebook.add(frame, text="Discovery")

        cfg = load_config()

        nb.Label(
            frame,
            text=(
                "Shows a gold alert on your in-game overlay the moment you jump into a system nobody's "
                "ever scanned before, and a cyan alert the moment you're the first to scan or map a "
                "body — via EDMCOverlay. Connection settings are on the Overlay Connection tab."
            ),
            wraplength=440, justify=tk.LEFT,
        ).grid(row=0, column=0, columnspan=2, sticky=tk.W, padx=10, pady=(10, 4))

        self._enabled_var = tk.BooleanVar(value=cfg.enabled)
        nb.Checkbutton(
            frame, text="Enable Discovery Alerts", variable=self._enabled_var, command=self._update_dependent_state,
        ).grid(row=1, column=0, columnspan=2, sticky=tk.W, padx=10, pady=2)

        sub = nb.Frame(frame)
        sub.grid(row=2, column=0, columnspan=2, sticky=tk.W, padx=(28, 10))

        position_row = tk.Frame(sub)
        position_row.grid(row=0, column=0, sticky=tk.W, pady=2)
        nb.Label(position_row, text="Position — X:").pack(side=tk.LEFT)
        self._x_var = tk.StringVar(value=str(cfg.x))
        x_entry = nb.EntryMenu(position_row, textvariable=self._x_var, width=6)
        x_entry.pack(side=tk.LEFT, padx=(4, 0))
        nb.Label(position_row, text="   Y:").pack(side=tk.LEFT)
        self._y_var = tk.StringVar(value=str(cfg.y))
        y_entry = nb.EntryMenu(position_row, textvariable=self._y_var, width=6)
        y_entry.pack(side=tk.LEFT, padx=(4, 0))

        self._dependent_widgets = [x_entry, y_entry]

        nb.Label(
            frame,
            text=(
                "Position is the system-discovery title's own top-left corner — every other line is "
                "drawn at a fixed offset below it. Default is roughly top-center on a 1920-wide HUD."
            ),
            wraplength=440, justify=tk.LEFT,
        ).grid(row=3, column=0, columnspan=2, sticky=tk.W, padx=10, pady=(4, 4))

        action_row = tk.Frame(frame)
        action_row.grid(row=4, column=0, columnspan=2, sticky=tk.W, padx=10, pady=(6, 2))
        tk.Button(action_row, text="Test Discovery", command=self._test_discovery).pack(side=tk.LEFT)
        self._result_label = nb.Label(action_row, text="", wraplength=320, justify=tk.LEFT)
        self._result_label.pack(side=tk.LEFT, padx=(10, 0))

        nb.Label(
            frame,
            text="(Test Discovery works even while disabled above, and reports whether EDMCOverlay was reachable.)",
            wraplength=440, justify=tk.LEFT,
        ).grid(row=5, column=0, columnspan=2, sticky=tk.W, padx=10, pady=(0, 10))

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

    def _parse_coord(self, var: Optional[tk.StringVar], default: int) -> int:
        if var is None:
            return default
        try:
            return int(var.get().strip())
        except (ValueError, tk.TclError):
            return default

    def _test_discovery(self) -> None:
        if self._result_label is None:
            return

        cfg = overlay.load_config()
        client = overlay.OverlayClient(cfg)
        frame = self._result_label
        pos_x = self._parse_coord(self._x_var, DEFAULT_X)
        pos_y = self._parse_coord(self._y_var, DEFAULT_Y)

        def render_once(snapshot: DiscoverySnapshot) -> None:
            try:
                render(snapshot, client, pos_x, pos_y)
                outcome, color = "Sent — check your overlay.", "#2e7d32"
            except OSError as err:
                outcome, color = f"Could not reach EDMCOverlay at {cfg.host}:{cfg.port} ({err}).", "#c07000"
            try:
                frame.after(0, lambda: (frame.configure(text=outcome, foreground=color)))
            except tk.TclError:
                pass

        tracker = DiscoveryTracker(on_change=render_once)

        def worker() -> None:
            tracker.trigger_test()

        threading.Thread(target=worker, name="WNTB-discovery-test", daemon=True).start()

    def save_settings(self) -> None:
        if self._enabled_var is None:
            return
        save_config(DiscoveryConfig(
            enabled=bool(self._enabled_var.get()),
            x=self._parse_coord(self._x_var, DEFAULT_X),
            y=self._parse_coord(self._y_var, DEFAULT_Y),
        ))
        if self._toggle_btn is not None:
            panelkit.apply_toggle_button_state(self._toggle_btn, self._enabled_var.get(), self._toggle_off_colors)
        self._sync_status_label()
        if not self._enabled_var.get():
            cfg = load_config()

            def worker(x=cfg.x, y=cfg.y) -> None:
                try:
                    clear(_overlay_client, x, y)
                except OSError:
                    logger.debug("Could not reach EDMCOverlay to clear discovery alerts", exc_info=True)

            threading.Thread(target=worker, name="WNTB-discovery-clear", daemon=True).start()


controller = DiscoveryController()


def handle_event(entry: Dict[str, Any], cmdr: str, system: Optional[str], station: Optional[str], state: Dict[str, Any]) -> None:
    controller.handle_event(entry, cmdr, system, station, state)


def build_panel(parent: tk.Frame) -> None:
    controller.build_panel(parent)


def build_settings(notebook: nb.Notebook) -> None:
    controller.build_settings(notebook)


def save_settings() -> None:
    controller.save_settings()
