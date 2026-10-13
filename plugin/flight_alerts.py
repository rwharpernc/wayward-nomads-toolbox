"""Flight Alerts: a fleet carrier jump countdown and fuel warnings, on one small overlay card.

- **Carrier jump countdown.** When a `CarrierJumpRequest` names a departure time, the card counts down to it and alerts (the card
  turns red, and a sound plays if you want one) at 10 minutes, 5 minutes, 1 minute and at departure. A cancelled or completed jump
  clears it. The request is read back from the newest journals when WNTB starts, so a restart of the game or of EDMC does not lose
  it. See `carrier_jump_timer.py` for what the journal does and does not say.
- **Fuel warnings.** Low fuel at a percentage you choose, and "the next star cannot be scooped" when a destination is plotted whose
  star is not scoopable (neutron stars, white dwarfs and the rest) and the tank is at or under a second percentage. See
  `fuel_alerts.py` for the sources and what WNTB cannot know (what a jump costs in fuel).

Nothing is sent anywhere: it reads the journal, EDMC's copy of `Status.json` and the clock, and draws through the shared overlay
connection (EDMCModernOverlay, which WNTB does not install or launch). Settings-tab-only, like Interdiction Warning, and off until
ticked, like every overlay. Where the card sits is the global Overlay Placement setting ("Flight alerts")."""

from __future__ import annotations

import logging
import os
import threading
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import tkinter as tk

import myNotebook as nb
from config import appname, config
from ttkHyperlinkLabel import HyperlinkLabel

from . import carrier_jump_timer as jump_timer
from . import fuel_alerts, overlay, overlay_appearance, overlay_placement, platform_support, restore
from .overlay import OverlayClient
from .overlay_style import LEGACY, Look

try:
    import winsound  # stdlib, Windows-only
except ImportError:
    winsound = None  # type: ignore

plugin_name = os.path.basename(os.path.dirname(__file__))
logger = logging.getLogger(f"{appname}.{plugin_name}")

PANEL_PLACEMENT = None   # Settings-tab-only, no main-panel widget

_CFG_ENABLED = "wntb_flight_enabled"
_CFG_CARRIER = "wntb_flight_carrier"
_CFG_FUEL = "wntb_flight_fuel"
_CFG_LOW = "wntb_flight_low_percent"
_CFG_UNSCOOPABLE = "wntb_flight_unscoopable_percent"
_CFG_SOUND = "wntb_flight_sound"

RECOVER_WINDOW_S = 3 * 3600   # journals this recent are read for a planned jump when WNTB starts
TICK_S = 1.0
OVERLAY_TTL = 4               # each draw lasts this long, so a stalled WNTB cannot leave the card up
RESEND_S = 3.0                # an unchanged card is drawn again this often (fuel changes only arrive with Status.json)


@dataclass
class FlightConfig:
    enabled: bool = False
    carrier: bool = True
    fuel: bool = True
    low_percent: int = fuel_alerts.DEFAULT_LOW_PERCENT
    unscoopable_percent: int = fuel_alerts.DEFAULT_UNSCOOPABLE_PERCENT
    sound: bool = False


def load_config() -> FlightConfig:
    return FlightConfig(
        enabled=config.get_bool(_CFG_ENABLED, default=False),
        carrier=config.get_bool(_CFG_CARRIER, default=True),
        fuel=config.get_bool(_CFG_FUEL, default=True),
        low_percent=fuel_alerts.clamp_percent(config.get_str(_CFG_LOW), fuel_alerts.DEFAULT_LOW_PERCENT),
        unscoopable_percent=fuel_alerts.clamp_percent(config.get_str(_CFG_UNSCOOPABLE), fuel_alerts.DEFAULT_UNSCOOPABLE_PERCENT),
        sound=config.get_bool(_CFG_SOUND, default=False))


def save_config(cfg: FlightConfig) -> None:
    config.set(_CFG_ENABLED, cfg.enabled)
    config.set(_CFG_CARRIER, cfg.carrier)
    config.set(_CFG_FUEL, cfg.fuel)
    config.set(_CFG_LOW, str(cfg.low_percent))
    config.set(_CFG_UNSCOOPABLE, str(cfg.unscoopable_percent))
    config.set(_CFG_SOUND, cfg.sound)


# --- the card ------------------------------------------------------------------------------------------------------

# Like the interdiction warning, these colors are safety signals, not chrome, so they do not follow the color scheme.
COLOR_AMBER = "#fbbf24"
COLOR_RED = "#f87171"
BORDER_AMBER = "#f59e0b"
BORDER_RED = "#ef4444"
FILL = "#f2200a0a"

Line = Tuple[str, str]   # (text, color)

MAX_LINES = 4
_X = 650
_Y = 100
_MIN_W = 380
_BASE_PAD_X = 18
_BASE_PAD_Y = 14
_LINE_GAP = 6
_SAMPLE_LINES = 3
# The wire protocol has no text metrics, so a line's width is estimated from its characters, and the overlay font runs wider than the
# plain estimate (capitals, digits). The box is measured this much wider, as the Colonization card does (colonisation_overlay.CHAR_SCALE),
# and a line is cut off at MAX_LINE_CHARS so a long name cannot grow the card without limit.
WIDTH_SAFETY = 1.3
MAX_LINE_CHARS = 60

GROUP_NAME = "wntb_flight"
GROUP_PREFIX = "wntb_flight_"
_CARD_ID = "wntb_flight_card"
_LINE_IDS = tuple(f"wntb_flight_line{i}" for i in range(MAX_LINES))

SAMPLE_LINES: List[Line] = [
    ("Carrier jumps to Sol in 4:32", COLOR_AMBER),
    ("No scoop at next star (neutron star). Fuel 38% (12.2 t)", COLOR_AMBER),
    ("Low fuel: 18% (5.8 t)", COLOR_RED),
]


def _card_size(look: Look, lines: List[Line]) -> Tuple[int, int]:
    pad_x, pad_y = look.pad_x(_BASE_PAD_X), look.pad_y(_BASE_PAD_Y)
    widest = max([int(look.text_width(text, "normal") * WIDTH_SAFETY) for text, _color in lines] + [_MIN_W - 2 * pad_x])
    height = 2 * pad_y + len(lines) * look.line_px("normal") + (len(lines) - 1) * _LINE_GAP
    return widest + 2 * pad_x, height


def block_rect(look: Look = LEGACY, lines: Optional[List[Line]] = None) -> tuple:
    """(left, top, width, height) of the card as `render` draws it. Placement always uses a card of three sample lines, so the
    card's top does not move as the number of lines changes."""
    sample = lines if lines is not None else SAMPLE_LINES[:_SAMPLE_LINES]
    width, height = _card_size(look, sample)
    return _X - look.pad_x(_BASE_PAD_X), _Y - look.pad_y(_BASE_PAD_Y), width, height


def placed_client(client: OverlayClient, look: Look = LEGACY) -> OverlayClient:
    return overlay_placement.client_for("flight_alerts", client, block_rect(look))


def render(lines: List[Line], client: OverlayClient, look: Look = LEGACY) -> None:
    """Draws the card with `lines` (at most MAX_LINES), or clears it when there are none. Raises on an overlay failure, as the
    interdiction warning does; the live path swallows it and the Settings test reports it."""
    lines = [(text if len(text) <= MAX_LINE_CHARS else text[:MAX_LINE_CHARS - 1].rstrip() + "…", color) for text, color in lines[:MAX_LINES]]
    if not lines:
        _clear(client)
        return
    width, height = _card_size(look, lines)
    left, top = _X - look.pad_x(_BASE_PAD_X), _Y - look.pad_y(_BASE_PAD_Y)
    red = any(color == COLOR_RED for _text, color in lines)
    client.send_shape(_CARD_ID, "rect", BORDER_RED if red else BORDER_AMBER, FILL, left, top, width, height, ttl=OVERLAY_TTL, thickness=2)
    step = look.line_px("normal") + _LINE_GAP
    for index, msg_id in enumerate(_LINE_IDS):
        if index < len(lines):
            text, color = lines[index]
            client.send_message(msg_id, text, color, _X, _Y + index * step, ttl=OVERLAY_TTL, size=look.size("normal"))
        else:
            client.send_message(msg_id, "", "white", _X, _Y, ttl=1)


def _clear(client: OverlayClient) -> None:
    left, top, _w, _h = block_rect(LEGACY)
    client.send_shape(_CARD_ID, "rect", "", "", left, top, 0, 0, ttl=1)
    for msg_id in _LINE_IDS:
        client.send_message(msg_id, "", "white", _X, _Y, ttl=1)


# --- state and the live path -----------------------------------------------------------------------------------------


class FlightAlerts:
    """The two watchers, the sound bookkeeping and what is on the card. `now`, `clock`, `draw` and `beep` are injected so the
    behavior is tested without the overlay, the real clock or a sound device."""

    def __init__(self, draw=None, beep=None, now=time.time, cfg=load_config) -> None:
        self._lock = threading.RLock()
        self.timer = jump_timer.CarrierJumpTimer(now=now)
        self.fuel = fuel_alerts.FuelWatcher()
        self._draw = draw or (lambda lines: None)
        self._beep = beep or (lambda: None)
        self._now = now
        self._cfg = cfg
        self._sounded: set = set()
        self._last: Optional[List[Line]] = None
        self._last_sent = 0.0
        self._recovered = False

    # events -------------------------------------------------------------------------------------------------------

    def handle_event(self, entry: Dict[str, Any]) -> None:
        event = entry.get("event")
        with self._lock:
            if event in jump_timer.EVENTS:
                self.timer.handle_event(entry)
            self.fuel.handle_event(entry)
            if event in ("LoadGame", "StartUp", restore.RESTORE_EVENT) and not self._recovered:
                self._recovered = True
                try:
                    jump_timer.recover(self.timer, self._now() - RECOVER_WINDOW_S)
                except Exception:   # reading old journals is a convenience; it must never stop the live path
                    logger.debug("Could not read a planned carrier jump from the journal", exc_info=True)
        self.refresh()

    def handle_status(self, entry: Dict[str, Any]) -> None:
        with self._lock:
            self.fuel.handle_status(entry)
        self.refresh()

    # what to show ---------------------------------------------------------------------------------------------------

    def lines(self) -> List[Line]:
        cfg = self._cfg()
        found: List[Line] = []
        with self._lock:
            if cfg.carrier:
                self.timer.expire()
                text = self.timer.line()
                if text:
                    left = self.timer.remaining() or 0
                    found.append((text, COLOR_RED if left <= 60 else COLOR_AMBER))
            if cfg.fuel:
                for alert in self.fuel.alerts(cfg.low_percent, cfg.unscoopable_percent):
                    found.append((alert.text, COLOR_RED if alert.kind == "low" else COLOR_AMBER))
        return found

    def _sound_keys(self) -> set:
        """The alerts that are active that deserve a sound: a fuel alert when it starts, a carrier alert as its time arrives."""
        keys = set()
        cfg = self._cfg()
        with self._lock:
            if cfg.fuel:
                keys.update(("fuel", a.kind) for a in self.fuel.alerts(cfg.low_percent, cfg.unscoopable_percent))
        return keys

    def refresh(self) -> None:
        """Work out what the card should say, play any sound that is due, and draw it when it changed (or now and then, so it
        does not expire). Does nothing when Flight Alerts is off."""
        cfg = self._cfg()
        if not cfg.enabled:
            return
        lines = self.lines()
        if cfg.sound:
            self._sound(cfg)
        now = self._now()
        if lines == self._last and now - self._last_sent < RESEND_S:
            return
        if not lines and not self._last:
            self._last = lines
            return
        self._last, self._last_sent = lines, now
        self._draw(lines)

    def _sound(self, cfg: FlightConfig) -> None:
        keys = self._sound_keys()
        fresh = keys - self._sounded
        self._sounded = keys     # a fuel alert that ended may sound again next time
        due = None
        if cfg.carrier:
            with self._lock:
                due = self.timer.due_alert()
        if fresh or due is not None:
            try:
                self._beep()
            except Exception:
                logger.debug("Alert sound failed", exc_info=True)

    def ticking(self) -> bool:
        """The countdown needs a one-second tick while a jump is planned."""
        with self._lock:
            return self.timer.jump is not None and self.timer.active()


# --- wiring ----------------------------------------------------------------------------------------------------------

_overlay_client = overlay.OverlayClient()


def set_overlay_client(client: overlay.OverlayClient) -> None:
    global _overlay_client
    _overlay_client = client


def _draw_live(lines: List[Line]) -> None:
    look = overlay_appearance.current_look()

    def worker() -> None:
        try:
            render(lines, placed_client(_overlay_client, look), look)
        except OSError:
            logger.debug("Could not reach the overlay for flight alerts", exc_info=True)

    threading.Thread(target=worker, name="WNTB-flight-render", daemon=True).start()


def sound_available() -> bool:
    return winsound is not None or platform_support.sound_available()


def play_alert_sound() -> None:
    if winsound is not None:
        winsound.MessageBeep(winsound.MB_ICONEXCLAMATION)
    else:
        platform_support.play_notification_sound()


_state: Optional[FlightAlerts] = None
_ticker: Optional[threading.Thread] = None
_stop = threading.Event()


def get_state() -> FlightAlerts:
    global _state
    if _state is None:
        _state = FlightAlerts(draw=_draw_live, beep=play_alert_sound)
    return _state


def _tick_loop() -> None:
    state = get_state()
    while not _stop.wait(TICK_S):
        try:
            if state.ticking():
                state.refresh()
        except Exception:
            logger.debug("Flight alerts tick failed", exc_info=True)


def start(plugin_dir: str) -> None:
    global _ticker
    _stop.clear()
    if _ticker is None or not _ticker.is_alive():
        _ticker = threading.Thread(target=_tick_loop, name="WNTB-flight-tick", daemon=True)
        _ticker.start()


def stop() -> None:
    _stop.set()


def handle_event(entry: Dict[str, Any], cmdr: str, system: Optional[str], station: Optional[str], state: Dict[str, Any]) -> None:
    get_state().handle_event(entry)


def dashboard_status(entry: Dict[str, Any]) -> None:
    get_state().handle_status(entry)


# --- Settings tab ----------------------------------------------------------------------------------------------------

_vars: Dict[str, Any] = {}
_result_label: Optional[nb.Label] = None


def build_settings(notebook: nb.Notebook) -> None:
    global _result_label
    frame = nb.Frame(notebook)
    frame.columnconfigure(0, weight=1)
    notebook.add(frame, text="Flight Alerts")
    cfg = load_config()

    nb.Label(
        frame,
        text=("A small card on your in-game overlay, through EDMCModernOverlay (a separate, optional helper WNTB does not install or "
              "launch; its connection settings are on the Overlay Connection tab). It counts down to a fleet carrier jump you have "
              "scheduled, and warns about fuel: low fuel, and a plotted destination whose star cannot be scooped. Everything comes "
              "from your journal and the game's Status.json; nothing is sent anywhere."),
        wraplength=440, justify=tk.LEFT,
    ).grid(row=0, column=0, sticky=tk.W, padx=10, pady=(10, 4))
    HyperlinkLabel(
        frame, text="Get EDMCModernOverlay (recommended)", background=nb.Label().cget("background"),
        url="https://github.com/SweetJonnySauce/EDMCModernOverlay", underline=True,
    ).grid(row=1, column=0, sticky=tk.W, padx=10, pady=(0, 8))

    _vars["enabled"] = tk.BooleanVar(value=cfg.enabled)
    _vars["carrier"] = tk.BooleanVar(value=cfg.carrier)
    _vars["fuel"] = tk.BooleanVar(value=cfg.fuel)
    _vars["sound"] = tk.BooleanVar(value=cfg.sound)
    _vars["low"] = tk.StringVar(value=str(cfg.low_percent))
    _vars["unscoopable"] = tk.StringVar(value=str(cfg.unscoopable_percent))

    nb.Checkbutton(frame, text="Enable Flight Alerts", variable=_vars["enabled"]).grid(row=2, column=0, sticky=tk.W, padx=10, pady=2)
    nb.Checkbutton(frame, text="Fleet carrier jump countdown (alerts at 10, 5 and 1 minute, and at departure)",
                   variable=_vars["carrier"]).grid(row=3, column=0, sticky=tk.W, padx=10, pady=2)
    nb.Checkbutton(frame, text="Fuel warnings", variable=_vars["fuel"]).grid(row=4, column=0, sticky=tk.W, padx=10, pady=2)

    low_row = tk.Frame(frame)
    low_row.grid(row=5, column=0, sticky=tk.W, padx=(30, 10), pady=2)
    nb.Label(low_row, text="Warn when the tank is at or under").pack(side=tk.LEFT)
    tk.Spinbox(low_row, from_=fuel_alerts.PERCENT_RANGE[0], to=fuel_alerts.PERCENT_RANGE[1], width=4, textvariable=_vars["low"]).pack(
        side=tk.LEFT, padx=4)
    nb.Label(low_row, text="% (the game's own warning comes at 25%)").pack(side=tk.LEFT)

    unscoop_row = tk.Frame(frame)
    unscoop_row.grid(row=6, column=0, sticky=tk.W, padx=(30, 10), pady=2)
    nb.Label(unscoop_row, text="Warn about a star that cannot be scooped when the tank is at or under").pack(side=tk.LEFT)
    tk.Spinbox(unscoop_row, from_=fuel_alerts.PERCENT_RANGE[0], to=fuel_alerts.PERCENT_RANGE[1], width=4,
               textvariable=_vars["unscoopable"]).pack(side=tk.LEFT, padx=4)
    nb.Label(unscoop_row, text="%").pack(side=tk.LEFT)

    sound_box = nb.Checkbutton(frame, text="Play a sound when an alert starts", variable=_vars["sound"])
    sound_box.grid(row=7, column=0, sticky=tk.W, padx=10, pady=2)
    if not sound_available():
        sound_box.configure(state=tk.DISABLED)
        _vars["sound"].set(False)

    nb.Label(
        frame,
        text=("What WNTB cannot know: the journal does not say what a jump will cost in fuel, so the fuel warnings compare percentages "
              "of the tank, not the next jump's needs. The tank size is learned from the game's Loadout event (at login, or when you "
              "change ship), so right after starting EDMC mid-flight only the game's own low-fuel flag is available until then."),
        wraplength=440, justify=tk.LEFT,
    ).grid(row=8, column=0, sticky=tk.W, padx=10, pady=(6, 4))

    action_row = tk.Frame(frame)
    action_row.grid(row=9, column=0, sticky=tk.W, padx=10, pady=(6, 2))
    tk.Button(action_row, text="Test Card", command=_test_card).pack(side=tk.LEFT)
    _result_label = nb.Label(action_row, text="", wraplength=320, justify=tk.LEFT)
    _result_label.pack(side=tk.LEFT, padx=(10, 0))
    nb.Label(frame, text="(Test Card works even while disabled above, and reports whether the overlay was actually reachable.)",
             wraplength=440, justify=tk.LEFT).grid(row=10, column=0, sticky=tk.W, padx=10, pady=(0, 10))


def _test_card() -> None:
    if _result_label is None:
        return
    cfg = overlay.load_config()
    client = overlay.OverlayClient(cfg)
    label = _result_label
    look = overlay_appearance.current_look()

    def worker() -> None:
        try:
            render(list(SAMPLE_LINES), placed_client(client, look), look)
            outcome, color = "Sent: check your overlay.", "#2e7d32"
        except OSError as err:
            outcome, color = f"Could not reach the overlay at {cfg.host}:{cfg.port} ({err}).", "#c07000"
        try:
            label.after(0, lambda: label.configure(text=outcome, foreground=color))
        except tk.TclError:
            pass   # the Settings dialog was closed before the test finished

    threading.Thread(target=worker, name="WNTB-flight-test", daemon=True).start()


def save_settings() -> None:
    if not _vars:
        return
    cfg = FlightConfig(
        enabled=bool(_vars["enabled"].get()), carrier=bool(_vars["carrier"].get()), fuel=bool(_vars["fuel"].get()),
        low_percent=fuel_alerts.clamp_percent(_vars["low"].get(), fuel_alerts.DEFAULT_LOW_PERCENT),
        unscoopable_percent=fuel_alerts.clamp_percent(_vars["unscoopable"].get(), fuel_alerts.DEFAULT_UNSCOOPABLE_PERCENT),
        sound=bool(_vars["sound"].get()))
    save_config(cfg)   # a card left up by turning this off simply expires
