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
from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence, Tuple

import tkinter as tk

import myNotebook as nb
from config import appname, config

from . import neutron_finder, overlay, overlay_appearance, overlay_placement, panelkit
from .overlay import OverlayClient
from .overlay_style import LEGACY, Look

plugin_name = os.path.basename(os.path.dirname(__file__))
logger = logging.getLogger(f"{appname}.{plugin_name}")

PANEL_PLACEMENT = "exploration"

_CFG_ENABLED = "wntb_discovery_enabled"
_CFG_X = "wntb_discovery_x"
_CFG_Y = "wntb_discovery_y"
DEFAULT_ENABLED = False

# The alerts are drawn at this fixed origin (the system title's own position); every other line in render() is a
# fixed offset from that one point. WHERE the block sits on screen is the global Overlay Placement setting
# (overlay_placement.py), which moves everything drawn through `placed_client`.
DEFAULT_X = 700
DEFAULT_Y = 60

SYSTEM_CLEAR_S = 12.0
BODY_CLEAR_S = 8.0

DISCOVERY_EVENTS = ("Scan", "SAAScanComplete")


@dataclass
class DiscoveryConfig:
    enabled: bool = DEFAULT_ENABLED


def load_config() -> DiscoveryConfig:
    return DiscoveryConfig(
        enabled=config.get_bool(_CFG_ENABLED, default=DEFAULT_ENABLED),
    )


def save_config(cfg: DiscoveryConfig) -> None:
    config.set(_CFG_ENABLED, cfg.enabled)   # _CFG_X / _CFG_Y are only read, once, by overlay_placement's migration


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

# Each alert sits inside its own semi-transparent card in the display's color scheme (the first accent for the system alert, the
# second for the body alert, the third for a notable body), the same card treatment as Landing and the other overlays.
# Each alert is a card holding a large title over a smaller name. The card is sized from that text at the look's text size (so a bigger
# size makes a bigger card and the text always fits inside the border), with these base measures that a look adds its padding and line
# spacing to. At the legacy look they give the sizes this display always had: a 460 x 84 card with the name 38 below the title, and
# the body card 66 below the system card.
_NAME_GAP = 4               # between the title's line and the name's, on top of the title line's own height
_BODY_GAP = 66              # between the system card and the body card
_CARD_MIN_W = 460
_CARD_BASE_PAD_X = 22
_CARD_BASE_PAD_TOP = 16
_CARD_BASE_PAD_BOTTOM = 4
_CARD_BORDER_THICKNESS = 2
_TITLE_BASE = "huge"       # the sizes a display asks for at the default text size
_NAME_BASE = "large"

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

_SYSTEM_TITLE = "NEW SYSTEM DISCOVERY"


@dataclass(frozen=True)
class CardGeometry:
    """The measures of one alert card (and of the card below it), from the text it will hold and the look."""
    pad_x: int
    pad_top: int
    width: int
    height: int
    name_offset: int      # from the title's line down to the name's
    body_offset: int      # from the top of the system card down to the top of the body card

    def left(self, x: int) -> int:
        return x - self.pad_x

    def top(self, y: int) -> int:
        return y - self.pad_top

    def center_x(self, x: int) -> int:
        return x - self.pad_x + self.width // 2


def card_geometry(look: Look, texts: Sequence[Tuple[str, str]] = ()) -> CardGeometry:
    """The card measures for the given (title, name) pairs: wide enough for the widest of them at the look's sizes, never narrower
    than the standard card. Shared by the Notable Bodies card, which is drawn the same way."""
    widest = max((max(look.text_width(title, _TITLE_BASE), look.text_width(name, _NAME_BASE)) for title, name in texts), default=0)
    pad_x = look.pad_x(_CARD_BASE_PAD_X)
    pad_top = look.pad_y(_CARD_BASE_PAD_TOP)
    name_offset = look.line_px(_TITLE_BASE) + _NAME_GAP
    height = pad_top + name_offset + look.line_px(_NAME_BASE) + look.pad_y(_CARD_BASE_PAD_BOTTOM)
    return CardGeometry(pad_x, pad_top, max(_CARD_MIN_W, widest + 2 * pad_x), height, name_offset, height + _BODY_GAP)


def centered_x(text: str, base: str, center_x: int, look: Look = LEGACY) -> int:
    """Left-edge draw position that centers `text`, drawn where a display would normally use size `base`, on `center_x`."""
    return center_x - look.text_width(text, base) // 2


def _alerts(snapshot: Optional[DiscoverySnapshot]) -> List[Tuple[str, str]]:
    """The (title, name) of each alert that is showing."""
    pairs: List[Tuple[str, str]] = []
    if snapshot is None or snapshot.system_visible:
        pairs.append((_SYSTEM_TITLE, (snapshot.system_name if snapshot else "") or "Unknown system"))
    if snapshot is None or snapshot.body_visible:
        pairs.append((_BODY_ACTION_TEXT.get((snapshot.body_action if snapshot else "") or "", "New discovery!"),
                      (snapshot.body_name if snapshot else "") or "Unknown body"))
    return pairs


def block_rect(snapshot: Optional[DiscoverySnapshot] = None, look: Look = LEGACY) -> Tuple[int, int, int, int]:
    """(left, top, width, height) of the two stacked alert cards as `render` draws them at the default origin. With no snapshot, the
    widest the cards usually are."""
    geometry = card_geometry(look, _alerts(snapshot))
    return geometry.left(DEFAULT_X), geometry.top(DEFAULT_Y), geometry.width, geometry.body_offset + geometry.height


def placed_client(client: Any, snapshot: Optional[DiscoverySnapshot] = None, look: Look = LEGACY) -> Any:
    """`client` moved to where the Overlay Placement settings put the discovery alerts."""
    return overlay_placement.client_for("discovery", client, block_rect(snapshot, look))


def render(snapshot: DiscoverySnapshot, client: OverlayClient, x: int = DEFAULT_X, y: int = DEFAULT_Y,
           look: Look = LEGACY) -> None:
    """Draws (or clears) both alert slots, anchored at (x, y). Title and name are each horizontally centered in the card
    independently, since they're usually different lengths. Both cards share one width, so they line up."""
    geometry = card_geometry(look, _alerts(snapshot))
    center_x = geometry.center_x(x)
    title_size, name_size = look.size(_TITLE_BASE), look.size(_NAME_BASE)

    def draw(card_id, title_id, name_id, top_y, title, name, accent_index):
        accent = look.accent(accent_index)
        client.send_shape(card_id, "rect", look.soft(accent), look.color("fill"), geometry.left(x), geometry.top(top_y),
                          geometry.width, geometry.height, ttl=30, thickness=_CARD_BORDER_THICKNESS)
        client.send_message(title_id, title, accent, centered_x(title, _TITLE_BASE, center_x, look), top_y, ttl=30, size=title_size)
        client.send_message(name_id, name, look.color("text"), centered_x(name, _NAME_BASE, center_x, look),
                            top_y + geometry.name_offset, ttl=30, size=name_size)

    if snapshot.system_visible:
        draw(_SYSTEM_CARD_ID, _SYSTEM_TITLE_ID, _SYSTEM_NAME_ID, y, _SYSTEM_TITLE,
             snapshot.system_name or "Unknown system", 0)
    else:
        _clear_system(client, x, y)

    if snapshot.body_visible:
        draw(_BODY_CARD_ID, _BODY_TITLE_ID, _BODY_NAME_ID, y + geometry.body_offset,
             _BODY_ACTION_TEXT.get(snapshot.body_action or "", "New discovery!"), snapshot.body_name or "Unknown body", 1)
    else:
        _clear_body(client, x, y)


def clear(client: OverlayClient, x: int = DEFAULT_X, y: int = DEFAULT_Y) -> None:
    _clear_system(client, x, y)
    _clear_body(client, x, y)


# Clearing replaces a shape or message by id, so where the blank one is sent does not matter.
def _clear_system(client: OverlayClient, x: int, y: int) -> None:
    client.send_shape(_SYSTEM_CARD_ID, "rect", "", "", x, y, 0, 0, ttl=1)
    client.send_message(_SYSTEM_TITLE_ID, "", "white", x, y, ttl=1)
    client.send_message(_SYSTEM_NAME_ID, "", "white", x, y, ttl=1)


def _clear_body(client: OverlayClient, x: int, y: int) -> None:
    client.send_shape(_BODY_CARD_ID, "rect", "", "", x, y, 0, 0, ttl=1)
    client.send_message(_BODY_TITLE_ID, "", "white", x, y, ttl=1)
    client.send_message(_BODY_NAME_ID, "", "white", x, y, ttl=1)


# --- Controller: this mode's one entry point for load.py/ui.py -----------

_overlay_client = overlay.OverlayClient()

_IDLE_STATUS = "Watching for new discoveries…"
_DISABLED_STATUS = "Discovery alerts are disabled."
_STAR_NO_POSITION = "position unknown - jump or reload first"
_STAR_SEARCHING = "searching spansh.co.uk..."
_STAR_FAILED = "lookup failed - see EDMarketConnector.log"
# (button label, tooltip, finder function) - the label doubles as the result-line prefix.
_STAR_FINDERS = (
    ("N.S.", "Neutron Star - find the nearest system whose primary star is a neutron star",
     neutron_finder.find_nearest_neutron),
    ("W.D.", "White Dwarf - find the nearest system whose primary star is a white dwarf",
     neutron_finder.find_nearest_white_dwarf),
)


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
        self._dependent_widgets = []
        self._result_label: Optional[nb.Label] = None

        # "N.S." / "W.D." buttons (see neutron_finder.py): position comes from the
        # journal's StarPos; the lookup runs on a worker thread and hands its
        # result back through a queue polled via after(), like gec_poi_panel.py.
        self._star_pos: Optional[Tuple[float, float, float]] = None
        self._current_system: Optional[str] = None
        self.button_row: Optional[tk.Frame] = None
        self.panel_frame: Optional[tk.Frame] = None
        self._star_buttons: List[tk.Button] = []
        self._neutron_label: Optional[tk.Label] = None
        self._neutron_parent: Optional[tk.Frame] = None
        self._neutron_generation = 0
        self._neutron_queue: "queue.Queue[Tuple[int, str, Optional[neutron_finder.NearestStar], bool]]" = queue.Queue()

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

        look = overlay_appearance.current_look()

        def worker() -> None:
            try:
                render(snapshot, placed_client(_overlay_client, snapshot, look), look=look)
            except OSError:
                logger.debug("Could not reach the overlay for discovery alert", exc_info=True)

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
        self._toggle_btn = tk.Button(row, text="D.A.", command=self._on_toggle_click)
        self._toggle_btn.pack(side=tk.LEFT)
        panelkit.add_tooltip(self._toggle_btn, "Discovery Alerts - toggle the on-screen alert for undiscovered systems and first scans/maps")
        self._toggle_off_colors = panelkit.capture_toggle_off_colors(self._toggle_btn)
        panelkit.apply_toggle_button_state(self._toggle_btn, load_config().enabled, self._toggle_off_colors)

        self.button_row = row  # ui.py adds the Boxel Survey "Random" button here
        self.panel_frame = parent
        for label, tip, finder in _STAR_FINDERS:
            button = tk.Button(row, text=label, command=lambda label=label, finder=finder: self._on_star_click(label, finder))
            button.pack(side=tk.LEFT, padx=(6, 0))  # same 6px gap as ui.py's mode-select buttons
            panelkit.add_tooltip(button, tip)
            self._star_buttons.append(button)

        self._status_label = panelkit.wrap_label(parent, text=_IDLE_STATUS, font=panelkit.view_fonts()["small"])
        self._status_label.grid(row=1, column=0, sticky=tk.W, pady=(4, 0))
        self._sync_status_label()

        self._neutron_label = panelkit.wrap_label(parent, text="", font=panelkit.view_fonts()["small"])
        self._neutron_label.grid(row=2, column=0, sticky=tk.W, pady=(2, 0))
        self._neutron_label.grid_remove()  # nothing to say until the first click
        self._neutron_parent = parent
        parent.after(200, self._poll_neutron_queue)

    # --- N.S. / W.D. buttons ------------------------------------------------

    def _show_neutron_text(self, text: str) -> None:
        if self._neutron_label is not None:
            self._neutron_label["text"] = text
            self._neutron_label.grid()

    def _on_star_click(self, label: str, finder: Callable[..., neutron_finder.NearestStar]) -> None:
        if self._star_pos is None:
            self._show_neutron_text(f"{label}: {_STAR_NO_POSITION}")
            return
        self._neutron_generation += 1
        generation = self._neutron_generation
        self._show_neutron_text(f"{label}: {_STAR_SEARCHING}")
        for button in self._star_buttons:
            button.config(state=tk.DISABLED)
        x, y, z = self._star_pos
        threading.Thread(
            target=self._star_worker, args=(generation, label, finder, x, y, z, self._current_system),
            name="WNTB-star-find", daemon=True,
        ).start()

    def _star_worker(self, generation: int, label: str, finder: Callable[..., neutron_finder.NearestStar],
                     x: float, y: float, z: float, current_system: Optional[str]) -> None:
        """Runs off the main thread - must not touch any Tk widget."""
        try:
            result = finder(x, y, z, current_system)
        except Exception:
            logger.exception("%s lookup failed for (%s, %s, %s)", label, x, y, z)
            self._neutron_queue.put((generation, label, None, True))
            return
        self._neutron_queue.put((generation, label, result, False))

    def _poll_neutron_queue(self) -> None:
        """Runs on the main thread via after() - safe to touch widgets."""
        try:
            generation, label, result, failed = self._neutron_queue.get_nowait()
        except queue.Empty:
            pass
        else:
            if generation == self._neutron_generation:
                for button in self._star_buttons:
                    button.config(state=tk.NORMAL)
                if failed or result is None:
                    self._show_neutron_text(f"{label}: {_STAR_FAILED}")
                else:
                    # Copy the full (untruncated) name so it can be pasted straight
                    # into the galaxy map's search box.
                    copied = self._neutron_parent is not None and panelkit.copy_to_clipboard(
                        self._neutron_parent, result.system)
                    suffix = " (copied)" if copied else ""
                    self._show_neutron_text(
                        f"{label}: {neutron_finder.display_name(result.system)} - "
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
            def worker() -> None:
                try:
                    clear(placed_client(_overlay_client))
                except OSError:
                    logger.debug("Could not reach the overlay to clear discovery alerts", exc_info=True)

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
                "body — via EDMCModernOverlay. Connection settings are on the Overlay Connection tab."
            ),
            wraplength=440, justify=tk.LEFT,
        ).grid(row=0, column=0, columnspan=2, sticky=tk.W, padx=10, pady=(10, 4))

        self._enabled_var = tk.BooleanVar(value=cfg.enabled)
        nb.Checkbutton(
            frame, text="Enable Discovery Alerts", variable=self._enabled_var, command=self._update_dependent_state,
        ).grid(row=1, column=0, columnspan=2, sticky=tk.W, padx=10, pady=2)

        sub = nb.Frame(frame)
        sub.grid(row=2, column=0, columnspan=2, sticky=tk.W, padx=(28, 10))

        self._dependent_widgets = []

        nb.Label(
            frame,
            text=(
                "Where the alerts appear is set on the Overlay Placement tab, the same for every "
                "on-screen display. The default is the top center."
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
            text="(Test Discovery works even while disabled above, and reports whether the overlay was reachable.)",
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

    def _test_discovery(self) -> None:
        if self._result_label is None:
            return

        cfg = overlay.load_config()
        client = overlay.OverlayClient(cfg)
        frame = self._result_label
        look = overlay_appearance.current_look()

        def render_once(snapshot: DiscoverySnapshot) -> None:
            try:
                render(snapshot, placed_client(client, snapshot, look), look=look)
                outcome, color = "Sent — check your overlay.", "#2e7d32"
            except OSError as err:
                outcome, color = f"Could not reach the overlay at {cfg.host}:{cfg.port} ({err}).", "#c07000"
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
        save_config(DiscoveryConfig(enabled=bool(self._enabled_var.get())))
        if self._toggle_btn is not None:
            panelkit.apply_toggle_button_state(self._toggle_btn, self._enabled_var.get(), self._toggle_off_colors)
        self._sync_status_label()
        if not self._enabled_var.get():
            def worker() -> None:
                try:
                    clear(placed_client(_overlay_client))
                except OSError:
                    logger.debug("Could not reach the overlay to clear discovery alerts", exc_info=True)

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
