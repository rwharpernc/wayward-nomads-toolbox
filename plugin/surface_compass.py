"""Surface Compass: an arrow, a name and a distance on the game screen pointing at a spot on the planet you are on. It replaces
Mining's Surface Waypoint arrow, which could only point at the nearest recorded hotspot and only while Mining's Surface page was open.

- **Targets.** The nearest recorded mining hotspot with a position on this body (what the old arrow always did, and still the
  default), one of your own marks (`surface_marks.py`), or nothing. A mark is a named latitude and longitude on a body, made on the
  spot with MARK or typed into the Marks window. The compass only points at things on the body you are on.
- **Where it works.** Anywhere in the game, whichever mode is showing: it needs only your live position (`Status.json`, on foot or in
  a vehicle on a landable surface) and the body's radius (also from `Status.json`, else from the body's `Scan`).
- **The panel row** (Exploration mode, a "Compass" section) shows what it is pointing at and how far, makes a mark where you are, cycles
  the target, and opens the Marks window. The overlay card is off until ticked (Settings, Overlays, Surface Compass).

The distance and bearing are great-circle on a sphere of the body's radius (`mining_bearing.py`): good for "which way and how far",
not for the last few metres. Nothing here is sent anywhere."""
from __future__ import annotations

import logging
import os
import threading
from dataclasses import dataclass
from typing import Any, Dict, List, Mapping, Optional, Tuple

import tkinter as tk

import myNotebook as nb
from config import appname, config

from . import mining_bearing as bearing
from . import mining_hotspots as hotspots
from . import mining_live_position as live_position
from . import mining_surface as surface_mining
from . import overlay, overlay_appearance, overlay_placement, panelkit, surface_marks, surface_marks_window
from .overlay import OverlayClient
from .overlay_style import LEGACY, Look

plugin_name = os.path.basename(os.path.dirname(__file__))
logger = logging.getLogger(f"{appname}.{plugin_name}")

PANEL_PLACEMENT = "exploration"

_CFG_ENABLED = "wntb_compass_enabled"
_CFG_MIGRATED = "wntb_compass_migrated_v1"
# The Mining waypoint arrow's own settings, carried over once (see `migrate_old_waypoint_settings`).
_OLD_ENABLED = "wntb_mining_waypoint_overlay_enabled"
_OLD_PLACEMENT = "wntb_overlay_place_mining_waypoint"
_OLD_HIDDEN = "wntb_overlay_hidden_mining_waypoint"

SLOT = "surface_compass"
NAME_SHOWN = 28        # characters of a name drawn on the overlay or shown in the panel
_PANEL_WRAP_PX = 200   # the panel's line wraps here: what it shows comes from the commander and the game, and must not widen EDMC's window
_ENTRY_WIDTH = 26


# --- the pure part: what the compass points at -------------------------------------------------------------------------------------

@dataclass(frozen=True)
class Target:
    label: str
    latitude: float
    longitude: float
    kind: str    # "hotspot" or "mark"


@dataclass(frozen=True)
class Reading:
    target: Target
    distance_m: float
    bearing: float             # 0-360, 0 = north
    compass: str               # N, NE, ...
    relative: Optional[float]  # bearing relative to the way you are facing (0 = ahead); None when the heading is not known yet

    def text(self) -> str:
        """The overlay line: an arrow glyph when the heading is known, the name, the distance and the compass point."""
        label = clip(self.target.label, NAME_SHOWN)
        distance = bearing.format_distance_m(self.distance_m)
        if self.relative is None:
            return f"{label} - {distance} {self.compass}"
        return f"{bearing.arrow_glyph(self.relative)} {label} - {distance} {self.compass}"


def clip(text: str, limit: int) -> str:
    text = " ".join(str(text or "").split())
    return text if len(text) <= limit else text[:max(0, limit - 1)].rstrip() + "…"


def read(target: Target, latitude: float, longitude: float, heading: Optional[float], radius: float) -> Reading:
    """Distance and direction from where you are to `target`."""
    dist = bearing.distance_m(latitude, longitude, target.latitude, target.longitude, radius)
    toward = bearing.initial_bearing_deg(latitude, longitude, target.latitude, target.longitude)
    return Reading(target, dist, toward, bearing.compass_point(toward),
                   None if heading is None else (toward - heading) % 360)


def pick_target(choice: str, mark: Optional[surface_marks.Mark], body: str, hotspot_list: List[Any], latitude: float,
                longitude: float, radius: float) -> Optional[Target]:
    """What to point at. `choice` is the book's target (AUTO, NONE or a mark id) and `mark` that mark when it is one. A mark on another
    body than `body` is not pointed at. AUTO is the nearest hotspot with a position among `hotspot_list` (this body's)."""
    if choice == surface_marks.NONE:
        return None
    if choice != surface_marks.AUTO:
        if mark is None or surface_marks.body_key(mark.body) != surface_marks.body_key(body):
            return None
        return Target(mark.name, mark.latitude, mark.longitude, "mark")
    spots = [h for h in hotspot_list if h.has_position()]
    if not spots:
        return None
    nearest = min(spots, key=lambda h: bearing.distance_m(latitude, longitude, h.latitude, h.longitude, radius))
    return Target(nearest.material, nearest.latitude, nearest.longitude, "hotspot")


def cycle_choices(book: surface_marks.MarkBook, body: str) -> List[str]:
    """The targets the TARGET button steps through, in order: the nearest hotspot, each mark on this body, then none."""
    return [surface_marks.AUTO] + [m.id for m in book.for_body(body)] + [surface_marks.NONE]


# --- the overlay card ----------------------------------------------------------------------------------------------------------------

_X = 20
_Y = 250
_ARROW_X = _X + 10
_ARROW_SIZE = 18
_ARROW_GAP = 14
_PAD_X = 10
_PAD_Y = 8
_TTL = 3
WIDTH_SAFETY = 1.3     # the box is measured this much wider than the plain character estimate (the overlay font runs wider)

GROUP_NAME = "wntb_compass"
GROUP_PREFIX = "wntb_compass_"
_BG_ID = "wntb_compass_bg"
_ARROW_ID = "wntb_compass_arrow"
_TEXT_ID = "wntb_compass_text"

SAMPLE = Reading(Target("Ship", 10.0, 20.0, "mark"), 340.0, 45.0, "NE", 45.0)


def _geometry(look: Look) -> Tuple[int, int, int]:
    """(line height, arrow center y, extra panel height) at the look's size: the arrow sits a fixed gap below the (large) text line."""
    line = look.line_px("large")
    center_y = _Y + line + _ARROW_GAP
    return line, center_y, max((center_y + _ARROW_SIZE) - (_Y + line), 0)


def _panel_rect(text: str, look: Look) -> Tuple[int, int, int, int]:
    line, _center, extra = _geometry(look)
    pad_x, pad_y = look.pad_x(_PAD_X), look.pad_y(_PAD_Y)
    width = int(look.text_width(text, "large") * WIDTH_SAFETY) + 2 * pad_x
    return _X - pad_x, _Y - pad_y, width, line + 2 * pad_y + extra


def block_rect(look: Look = LEGACY, reading: Optional[Reading] = None) -> tuple:
    """(left, top, width, height) of the card as `render` draws it (placement uses a sample reading when there is none)."""
    return _panel_rect((reading or SAMPLE).text(), look)


def placed_client(client: OverlayClient, look: Look = LEGACY) -> OverlayClient:
    return overlay_placement.client_for(SLOT, client, block_rect(look))


def render(reading: Optional[Reading], client: OverlayClient, look: Look = LEGACY) -> None:
    """Draws the compass card (a backing panel, the line of text and an arrow), or clears it when there is no reading. Raises on an
    overlay failure; the live path swallows it and the Settings test reports it."""
    if reading is None:
        left, top, _w, _h = _panel_rect(SAMPLE.text(), LEGACY)
        client.send_shape(_BG_ID, "rect", "", "", left, top, 0, 0, ttl=1)
        client.send_message(_TEXT_ID, "", "white", _X, _Y, ttl=1)
        client.send_vector(_ARROW_ID, [], "white", ttl=1)
        return
    text = reading.text()
    left, top, width, height = _panel_rect(text, look)
    client.send_shape(_BG_ID, "rect", look.color("border"), look.color("fill"), left, top, width, height, ttl=_TTL)
    client.send_message(_TEXT_ID, text, look.color("title"), _X, _Y, ttl=_TTL, size=look.size("large"))
    if reading.relative is not None:
        _line, center_y, _extra = _geometry(look)
        client.send_vector(_ARROW_ID, bearing.arrow_vector_points(_ARROW_X, center_y, _ARROW_SIZE, reading.relative),
                           look.color("border"), ttl=_TTL)
    else:
        client.send_vector(_ARROW_ID, [], "white", ttl=1)


# --- settings carried over from the Mining waypoint arrow ------------------------------------------------------------------------------

def migrate_old_waypoint_settings() -> None:
    """Once: someone who had Mining's Surface Waypoint Overlay on has the compass on, and keeps where they put it (its placement
    and whether they had hidden it). The old setting is then no longer read."""
    try:
        if config.get_bool(_CFG_MIGRATED, default=False):
            return
        if config.get_bool(_OLD_ENABLED, default=False):
            config.set(_CFG_ENABLED, True)
        for old, new in ((_OLD_PLACEMENT, overlay_placement.layout.setting_key(SLOT)),
                         (_OLD_HIDDEN, overlay_placement.CFG_HIDDEN_PREFIX + SLOT)):
            value = config.get_str(old)
            if value and not config.get_str(new):
                config.set(new, value)
        config.set(_CFG_MIGRATED, True)
    except Exception:   # a damaged setting must never stop the plugin starting
        logger.exception("Could not carry the Mining waypoint settings over to the Surface Compass")


def enabled() -> bool:
    return config.get_bool(_CFG_ENABLED, default=False)


# --- the controller ------------------------------------------------------------------------------------------------------------------

book = surface_marks.MarkBook()


class CompassController:
    def __init__(self) -> None:
        self._body = ""
        self._reading: Optional[Reading] = None
        self._shown = False
        self._client: OverlayClient = overlay.OverlayClient()
        self._summary_var: Optional[tk.StringVar] = None
        self._entry_var: Optional[tk.StringVar] = None
        self._parent: Optional[tk.Frame] = None
        self._notice = ""
        book.add_listener(self._update_summary)

    def set_overlay_client(self, client: OverlayClient) -> None:
        self._client = client

    def start(self, plugin_dir: str) -> None:
        migrate_old_waypoint_settings()
        book.load(plugin_dir)

    def stop(self) -> None:
        surface_marks_window.close()

    # --- what the game tells us --------------------------------------------------------------------------------------------------

    def handle_event(self, entry: Mapping[str, Any], cmdr: str, system: Optional[str], station: Optional[str],
                     state: Dict[str, Any]) -> None:
        book.set_commander(cmdr)

    def dashboard_status(self, entry: Mapping[str, Any]) -> None:
        """Called with every Status.json update, after Mining's live position has been refreshed from the same entry."""
        body = entry.get("BodyName")
        self._body = body.strip() if isinstance(body, str) else ""
        self._reading = self._compute()
        self._update_summary()
        self._draw()

    def _current_body(self) -> str:
        return self._body or (surface_mining.surface_mining_repository.current_body or "")

    def here(self) -> surface_marks.Here:
        position = live_position.current_position()
        if position is None:
            return surface_marks.Here(self._current_body())
        radius = position.planet_radius or surface_mining.surface_mining_repository.radius_for_current_body()
        return surface_marks.Here(self._current_body(), position.latitude, position.longitude, radius)

    def _compute(self) -> Optional[Reading]:
        position = live_position.current_position()
        if position is None or not book.ready:
            return None
        repo = surface_mining.surface_mining_repository
        radius = position.planet_radius or repo.radius_for_current_body()
        if radius is None:
            return None
        body = self._current_body()
        spots = hotspots.hotspot_repository.for_body(repo.current_system, repo.current_body) if book.target == surface_marks.AUTO else []
        target = pick_target(book.target, book.target_mark(), body, spots, position.latitude, position.longitude, radius)
        if target is None:
            return None
        return read(target, position.latitude, position.longitude, position.heading, radius)

    # --- the overlay ------------------------------------------------------------------------------------------------------------

    def _draw(self) -> None:
        reading = self._reading if enabled() else None
        if reading is None and not self._shown:
            return
        self._shown = reading is not None
        look = overlay_appearance.current_look()
        client = self._client

        def worker() -> None:
            try:
                render(reading, placed_client(client, look), look)
            except OSError:
                logger.debug("Could not reach the overlay for the surface compass", exc_info=True)

        threading.Thread(target=worker, name="WNTB-compass-render", daemon=True).start()

    # --- the panel row -----------------------------------------------------------------------------------------------------------

    def target_description(self) -> str:
        if book.target == surface_marks.NONE:
            return "no target"
        if book.target == surface_marks.AUTO:
            return "the nearest hotspot"
        mark = book.target_mark()
        return f"mark {clip(mark.name, NAME_SHOWN)}" if mark else "the nearest hotspot"

    def summary(self) -> str:
        if not book.ready:
            return "Log in to use the compass."
        if self._notice:
            return self._notice
        if live_position.current_position() is None:
            return f"Aiming at {self.target_description()}. Waiting for a surface position."
        if self._reading is not None:
            return f"{self._reading.text()}"
        if book.target not in (surface_marks.AUTO, surface_marks.NONE) and book.target_mark() is not None:
            return f"Mark {clip(book.target_mark().name, NAME_SHOWN)} is on {clip(book.target_mark().body, 40)}, not here."
        return f"Aiming at {self.target_description()}; nothing to point at here."

    def _update_summary(self) -> None:
        if self._summary_var is None:
            return
        try:
            self._summary_var.set(self.summary())
        except tk.TclError:
            pass   # the panel is being torn down

    def _say(self, text: str) -> None:
        """A message in the panel row until the next position update replaces it."""
        self._notice = text
        self._update_summary()
        if self._parent is not None:
            self._parent.after(4000, self._clear_notice)

    def _clear_notice(self) -> None:
        self._notice = ""
        self._update_summary()

    def mark_here(self, name: str = "") -> Optional[surface_marks.Mark]:
        here = self.here()
        if not here.on_surface:
            self._say("No surface position yet: land, or get out, first.")
            return None
        try:
            mark = book.add(name.strip() or book.next_name(), here.body, here.latitude, here.longitude)
        except surface_marks.MarkError as err:
            self._say(str(err))
            return None
        self._say(f"Marked {clip(mark.name, NAME_SHOWN)} here.")
        return mark

    def cycle_target(self) -> None:
        choices = cycle_choices(book, self._current_body())
        try:
            current = choices.index(book.target)
        except ValueError:
            current = -1
        try:
            book.set_target(choices[(current + 1) % len(choices)])
        except surface_marks.MarkError as err:
            self._say(str(err))
            return
        self._say(f"Now aiming at {self.target_description()}.")

    def build_panel(self, parent: tk.Frame) -> None:
        self._parent = parent
        self._summary_var = tk.StringVar()
        self._entry_var = tk.StringVar()
        body = panelkit.collapsible_section(parent, "Compass", "wntb_compass_collapsed")
        # A plain label with a hard wrap, not panelkit.wrap_label (which never wraps narrower than 300 px): what it shows comes from the
        # commander and the game, and must not make this the widest row in the panel and so widen the whole EDMC window.
        tk.Label(body, textvariable=self._summary_var, anchor="w", justify=tk.LEFT, wraplength=_PANEL_WRAP_PX).grid(
            row=1, column=0, columnspan=3, sticky=tk.W, pady=(2, 0))
        entry = tk.Entry(body, textvariable=self._entry_var, width=_ENTRY_WIDTH)
        entry.grid(row=2, column=0, columnspan=3, sticky=tk.W, pady=(4, 0))
        entry.bind("<Return>", lambda _e: self._on_mark())
        buttons = (("MARK", self._on_mark, "Save where you are as a mark, named with what is typed above (or Mark 1, Mark 2, ...)"),
                   ("TARGET", self.cycle_target, "Aim at the next target: the nearest hotspot, each mark on this body, then none"),
                   ("MARKS", self._open_window, "Open the Marks window: every mark, edit, delete, choose the target"))
        for column, (text, command, tip) in enumerate(buttons):
            button = tk.Button(body, text=text, command=command)
            button.grid(row=3, column=column, sticky=tk.W, padx=(0 if column == 0 else 4, 0), pady=(4, 0))
            panelkit.add_tooltip(button, tip)
        self._update_summary()

    def _on_mark(self) -> None:
        if self.mark_here(self._entry_var.get() if self._entry_var is not None else "") is not None and self._entry_var is not None:
            self._entry_var.set("")

    def _open_window(self) -> None:
        if self._parent is not None:
            surface_marks_window.show(self._parent, book, self.here)


controller = CompassController()


def set_overlay_client(client: OverlayClient) -> None:
    controller.set_overlay_client(client)


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


# --- Settings tab (on the Overlays tab) --------------------------------------------------------------------------------------------------

_enabled_var: Optional[tk.BooleanVar] = None
_result_label: Optional[nb.Label] = None


def build_settings(notebook: nb.Notebook) -> None:
    global _enabled_var, _result_label
    frame = nb.Frame(notebook)
    frame.columnconfigure(0, weight=1)
    notebook.add(frame, text="Surface Compass")
    nb.Label(
        frame,
        text=("An arrow, a name and a distance on your in-game overlay (through EDMCModernOverlay) pointing at a spot on the planet you are "
              "on. It replaces Mining's Surface Waypoint arrow: by default it points at the nearest hotspot you have recorded, and in "
              "Exploration mode's Compass section you can mark spots (MARK), choose what it points at (TARGET) and manage them (MARKS). "
              "It works from any mode, on foot or in a vehicle on a landable surface. Where it sits is set on Overlay Placement."),
        wraplength=440, justify=tk.LEFT,
    ).grid(row=0, column=0, sticky=tk.W, padx=10, pady=(10, 6))
    _enabled_var = tk.BooleanVar(value=enabled())
    nb.Checkbutton(frame, text="Enable Surface Compass", variable=_enabled_var).grid(row=1, column=0, sticky=tk.W, padx=10, pady=2)
    action_row = tk.Frame(frame)
    action_row.grid(row=2, column=0, sticky=tk.W, padx=10, pady=(6, 2))
    tk.Button(action_row, text="Test Compass", command=_test_compass).pack(side=tk.LEFT)
    _result_label = nb.Label(action_row, text="", wraplength=320, justify=tk.LEFT)
    _result_label.pack(side=tk.LEFT, padx=(10, 0))
    nb.Label(frame, text="(Test Compass works even while disabled above, and reports whether the overlay was actually reachable.)",
             wraplength=440, justify=tk.LEFT).grid(row=3, column=0, sticky=tk.W, padx=10, pady=(0, 10))


def _test_compass() -> None:
    if _result_label is None:
        return
    cfg = overlay.load_config()
    client = overlay.OverlayClient(cfg)
    label = _result_label
    look = overlay_appearance.current_look()

    def worker() -> None:
        try:
            render(SAMPLE, placed_client(client, look), look)
            outcome, color = "Sent: check your overlay.", "#2e7d32"
        except OSError as err:
            outcome, color = f"Could not reach the overlay at {cfg.host}:{cfg.port} ({err}).", "#c07000"
        try:
            label.after(0, lambda: label.configure(text=outcome, foreground=color))
        except tk.TclError:
            pass   # the Settings dialog was closed before the test finished

    threading.Thread(target=worker, name="WNTB-compass-test", daemon=True).start()


def save_settings() -> None:
    if _enabled_var is not None:
        config.set(_CFG_ENABLED, bool(_enabled_var.get()))
