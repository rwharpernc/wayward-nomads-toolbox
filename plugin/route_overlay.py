"""Route overlay: the ship's travel status and the systems of the plotted route, on one overlay card.

At the top, the numbers that matter for a trip: the fuel on board, the ship's jump range and what the last jump used, how many jumps
and light years are left, and how far away the next supercharge is. Below, the systems still to jump to in order, each with its star:
a **neutron star** or a **white dwarf** is picked out in color so the supercharge can be prepared for, and any other star that cannot
be scooped is marked so the fuel is planned around it. See `route_plan.py` for what the game provides and what it does not (it does
not say what the next jump will cost in fuel, and a plotted route is only shown while the ship is on it).

Nothing is sent anywhere: it reads the journal, `NavRoute.json` and EDMC's copy of `Status.json`, and draws through the shared overlay
connection (EDMCModernOverlay, which WNTB does not install or launch). Settings-tab-only and off until ticked, like every overlay.
Where the card sits is the global Overlay Placement setting ("Route and ship status")."""

from __future__ import annotations

import json
import logging
import os
import threading
import time
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Tuple

import tkinter as tk

import myNotebook as nb
from config import appname, config
from ttkHyperlinkLabel import HyperlinkLabel

from . import fuel_alerts, journal_files, overlay, overlay_appearance, overlay_placement, restore, route_plan
from .overlay import OverlayClient
from .overlay_style import CARD_PAD_X, CARD_PAD_Y, LEGACY, Look
from .route_plan import Hop, RouteTracker

plugin_name = os.path.basename(os.path.dirname(__file__))
logger = logging.getLogger(f"{appname}.{plugin_name}")

PANEL_PLACEMENT = None   # Settings-tab-only, no main-panel widget

_CFG_ENABLED = "wntb_route_enabled"
_CFG_ROWS = "wntb_route_rows"

ROWS_RANGE = (3, 20)
DEFAULT_ROWS = 8
TICK_S = 1.0
OVERLAY_TTL = 4          # each draw lasts this long, so a stalled WNTB cannot leave the card up
RESEND_S = 3.0           # an unchanged card is drawn again this often, so it does not expire between fuel changes


@dataclass
class RouteConfig:
    enabled: bool = False
    rows: int = DEFAULT_ROWS


def clamp_rows(value: Any) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        return DEFAULT_ROWS
    return max(ROWS_RANGE[0], min(ROWS_RANGE[1], number))


def load_config() -> RouteConfig:
    return RouteConfig(enabled=config.get_bool(_CFG_ENABLED, default=False), rows=clamp_rows(config.get_str(_CFG_ROWS)))


def save_config(cfg: RouteConfig) -> None:
    config.set(_CFG_ENABLED, cfg.enabled)
    config.set(_CFG_ROWS, str(cfg.rows))


# --- what the card says (pure) ---------------------------------------------------------------------------------------

Line = Tuple[str, str]            # (text, color role)
Row = Tuple[str, str, str]        # (system text, star text, color role)

NAME_CHARS = 24                   # characters of "N. System name" in a row; a longer name is cut with an ellipsis
TAG_CHARS = 11                    # the widest star text ("WHITE DWARF")
SAMPLE_TAG = "WHITE DWARF"

_KIND_ROLE = {route_plan.KIND_NEUTRON: "info", route_plan.KIND_WHITE_DWARF: "ok", route_plan.KIND_NO_SCOOP: "warn"}
_KIND_WORD = {route_plan.KIND_NEUTRON: "neutron star", route_plan.KIND_WHITE_DWARF: "white dwarf"}


@dataclass(frozen=True)
class Card:
    header: Tuple[Line, ...] = ()
    rows: Tuple[Row, ...] = ()
    footer: Optional[Line] = None

    def __bool__(self) -> bool:
        return bool(self.header or self.rows)


def _cut(text: str, limit: int) -> str:
    return text if len(text) <= limit else text[:max(1, limit - 1)].rstrip() + "…"


def _jumps(count: int) -> str:
    return f"{count} jump" + ("" if count == 1 else "s")


def status_lines(tracker: RouteTracker, low_percent: int = fuel_alerts.DEFAULT_LOW_PERCENT) -> List[Line]:
    """The travel status lines: fuel, range, what is left of the route and the next supercharge. A number the game has not given yet
    leaves its line out."""
    lines: List[Line] = []
    watcher = tracker.fuel
    if watcher.fuel is not None:
        percent = watcher.percent()
        if percent is not None and watcher.capacity:
            text = f"Fuel {percent:.0f}%  {watcher.fuel:.1f} / {watcher.capacity:.0f} t"
        else:
            text = f"Fuel {watcher.fuel:.1f} t"
        low = (percent is not None and percent <= low_percent) or (percent is None and bool(watcher.flags & fuel_alerts.FLAG_LOW_FUEL))
        lines.append((text, "danger" if low else "text"))
    parts = []
    if tracker.jump_range is not None:
        parts.append(f"Range {tracker.jump_range:.1f} ly")
    if tracker.last_fuel_used is not None:
        parts.append(f"Last jump {tracker.last_fuel_used:.1f} t")
    if parts:
        lines.append(("   ".join(parts), "text"))
    ahead = tracker.remaining()
    if ahead:
        left = tracker.distance_left()
        lines.append((f"{_jumps(len(ahead))} left" + (f"   {left:,.0f} ly" if left is not None else ""), "title"))
        found = tracker.next_supercharge()
        if found is not None:
            number, hop = found
            kind = route_plan.star_kind(hop.star_class)
            lines.append((f"Next supercharge: {_jumps(number)}, {_KIND_WORD[kind]}", _KIND_ROLE[kind]))
        else:
            lines.append(("No supercharge on the route", "muted"))
    return lines


def build_card(tracker: RouteTracker, rows: int = DEFAULT_ROWS, low_percent: int = fuel_alerts.DEFAULT_LOW_PERCENT) -> Card:
    """The card for the tracker's state: status lines, the next `rows` systems, and a line for the rest. Empty when no route applies."""
    ahead = tracker.remaining()
    if not ahead:
        return Card()
    shown = ahead[:rows]
    listed: List[Row] = []
    for number, hop in enumerate(shown, 1):
        tag, kind = route_plan.star_tag(hop.star_class)
        role = _KIND_ROLE.get(kind, "muted")
        listed.append((_cut(f"{number}. {hop.name}", NAME_CHARS), _cut(tag, TAG_CHARS), role))
    rest = ahead[rows:]
    footer: Optional[Line] = None
    if rest:
        neutrons, dwarfs = tracker.special_counts(rest)
        extra = [f"{count} {word}" for count, word in ((neutrons, "neutron"), (dwarfs, "white dwarf")) if count]
        footer = (f"+ {len(rest)} more" + (f" ({', '.join(extra)})" if extra else ""), "muted")
    return Card(tuple(status_lines(tracker, low_percent)), tuple(listed), footer)


# --- drawing -------------------------------------------------------------------------------------------------------------

# The card is drawn at this fixed origin; where it sits on the screen is the global Overlay Placement setting. Its top and its width
# are fixed, so it grows downward as rows are added and never moves sideways with what it says.
_X = 650
_Y = 100
_LINE_GAP = 4
_COLUMN_GAP = 14
_SAMPLE_LINES = 4 + DEFAULT_ROWS + 1    # the card's height as placement sees it
MAX_HEADER = 4
GROUP_NAME = "wntb_route"
GROUP_PREFIX = "wntb_route_"
_CARD_ID = "wntb_route_card"
_HEADER_IDS = tuple(f"wntb_route_h{i}" for i in range(MAX_HEADER))
_NAME_IDS = tuple(f"wntb_route_n{i}" for i in range(ROWS_RANGE[1]))
_TAG_IDS = tuple(f"wntb_route_t{i}" for i in range(ROWS_RANGE[1]))
_FOOT_ID = "wntb_route_foot"


def _name_width(look: Look) -> int:
    return look.measured_width("X" * NAME_CHARS)


def _inner_width(look: Look) -> int:
    return _name_width(look) + _COLUMN_GAP + look.measured_width(SAMPLE_TAG)


def _fit(text: str, look: Look, limit_px: int) -> str:
    """`text` cut with an ellipsis until it fits the card's width at the look's size."""
    while len(text) > 1 and look.measured_width(text) > limit_px:
        text = text[:-2].rstrip() + "…"
    return text


def _card_size(look: Look, lines: int) -> Tuple[int, int]:
    pad_x, pad_y = look.pad_x(CARD_PAD_X), look.pad_y(CARD_PAD_Y)
    return _inner_width(look) + 2 * pad_x, 2 * pad_y + lines * look.line_px("normal") + max(0, lines - 1) * _LINE_GAP


def block_rect(look: Look = LEGACY, card: Optional[Card] = None) -> tuple:
    """(left, top, width, height) of the card as `render` draws it. Placement always uses a card of `_SAMPLE_LINES` lines."""
    lines = _SAMPLE_LINES if card is None else len(card.header) + len(card.rows) + (1 if card.footer else 0)
    width, height = _card_size(look, lines)
    return _X - look.pad_x(CARD_PAD_X), _Y - look.pad_y(CARD_PAD_Y), width, height


def placed_client(client: OverlayClient, look: Look = LEGACY) -> OverlayClient:
    return overlay_placement.client_for("route", client, block_rect(look))


def render(card: Card, client: OverlayClient, look: Look = LEGACY) -> None:
    """Draws the card, or clears it when it is empty. Every line starts at the card's left padding. Raises on an overlay failure; the
    live path swallows it and the Settings test reports it."""
    if not card:
        _clear(client)
        return
    lines = len(card.header) + len(card.rows) + (1 if card.footer else 0)
    width, height = _card_size(look, lines)
    left, top = _X - look.pad_x(CARD_PAD_X), _Y - look.pad_y(CARD_PAD_Y)
    client.send_shape(_CARD_ID, "rect", look.color("border"), look.color("fill"), left, top, width, height, ttl=OVERLAY_TTL, thickness=2)
    step = look.line_px("normal") + _LINE_GAP
    size = look.size("normal")
    tag_x = _X + _name_width(look) + _COLUMN_GAP
    inner = _inner_width(look)
    row = 0
    for index, msg_id in enumerate(_HEADER_IDS):
        if index < len(card.header):
            text, role = card.header[index]
            client.send_message(msg_id, _fit(text, look, inner), look.color(role), _X, _Y + row * step, ttl=OVERLAY_TTL, size=size)
            row += 1
        else:
            client.send_message(msg_id, "", "white", _X, _Y, ttl=1)
    for index, (name_id, tag_id) in enumerate(zip(_NAME_IDS, _TAG_IDS)):
        if index < len(card.rows):
            name, tag, role = card.rows[index]
            y = _Y + row * step
            client.send_message(name_id, name, look.color("text" if role == "muted" else role), _X, y, ttl=OVERLAY_TTL, size=size)
            client.send_message(tag_id, tag, look.color(role), tag_x, y, ttl=OVERLAY_TTL, size=size)
            row += 1
        else:
            client.send_message(name_id, "", "white", _X, _Y, ttl=1)
            client.send_message(tag_id, "", "white", _X, _Y, ttl=1)
    if card.footer:
        text, role = card.footer
        client.send_message(_FOOT_ID, _fit(text, look, inner), look.color(role), _X, _Y + row * step, ttl=OVERLAY_TTL, size=size)
    else:
        client.send_message(_FOOT_ID, "", "white", _X, _Y, ttl=1)


def _clear(client: OverlayClient) -> None:
    left, top, _w, _h = block_rect(LEGACY)
    client.send_shape(_CARD_ID, "rect", "", "", left, top, 0, 0, ttl=1)
    for msg_id in _HEADER_IDS + _NAME_IDS + _TAG_IDS + (_FOOT_ID,):
        client.send_message(msg_id, "", "white", _X, _Y, ttl=1)


def sample_tracker() -> RouteTracker:
    """A made-up trip for the Test Card: a neutron highway with a white dwarf and a black hole on it."""
    tracker = RouteTracker(system="Sol", jump_range=61.4, last_fuel_used=3.2)
    tracker.fuel.capacity, tracker.fuel.fuel = 32.0, 12.2
    classes = ("M", "N", "K", "DA", "G", "N", "H", "F", "N", "M", "K", "N")
    tracker.set_route([Hop("Sol", "G", (0.0, 0.0, 0.0))] + [
        Hop(f"Sample System {i}", c, (60.0 * i, 0.0, 0.0)) for i, c in enumerate(classes, 1)])
    return tracker


# --- state and the live path -------------------------------------------------------------------------------------------

def read_route_file() -> Optional[Any]:
    """The parsed `NavRoute.json` in the journal folder, or None when it is missing or unreadable."""
    folder = journal_files.journal_folder()
    if not folder:
        return None
    try:
        with open(os.path.join(folder, "NavRoute.json"), encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, ValueError):
        return None


class RouteOverlay:
    """The tracker, the route file and what is on the card. `draw`, `now`, `cfg` and `read` are injected so the behavior is tested
    without the overlay, the real clock or a journal folder."""

    def __init__(self, draw: Optional[Callable[[Card], None]] = None, now: Callable[[], float] = time.time,
                 cfg: Callable[[], RouteConfig] = load_config, read: Callable[[], Optional[Any]] = read_route_file) -> None:
        self._lock = threading.RLock()
        self.tracker = RouteTracker()
        self._draw = draw or (lambda card: None)
        self._now = now
        self._cfg = cfg
        self._read = read
        self._last: Optional[Card] = None
        self._last_sent = 0.0

    def _load_route(self) -> None:
        data = self._read()
        if data is not None:
            self.tracker.set_route(route_plan.parse_route(data))

    def handle_event(self, entry: Dict[str, Any], system: Optional[str] = None) -> None:
        event = entry.get("event")
        with self._lock:
            reload = self.tracker.handle_event(entry, system)
            if reload or event in ("LoadGame", "StartUp", restore.RESTORE_EVENT):
                try:
                    self._load_route()
                except Exception:   # a route that cannot be read must never stop the live path
                    logger.debug("Could not read the plotted route", exc_info=True)
        self.refresh()

    def handle_status(self, entry: Dict[str, Any]) -> None:
        with self._lock:
            self.tracker.handle_status(entry)
        self.refresh()

    def card(self) -> Card:
        cfg = self._cfg()
        with self._lock:
            return build_card(self.tracker, cfg.rows)

    def refresh(self) -> None:
        """Draws the card when it changed (or now and then, so it does not expire). Does nothing when the Route overlay is off."""
        if not self._cfg().enabled:
            return
        card = self.card()
        now = self._now()
        if card == self._last and now - self._last_sent < RESEND_S:
            return
        if not card and not self._last:
            self._last = card
            return
        self._last, self._last_sent = card, now
        self._draw(card)

    def showing(self) -> bool:
        with self._lock:
            return self.tracker.on_route() and bool(self.tracker.remaining())


# --- wiring ----------------------------------------------------------------------------------------------------------------

_overlay_client = overlay.OverlayClient()


def set_overlay_client(client: overlay.OverlayClient) -> None:
    global _overlay_client
    _overlay_client = client


def _draw_live(card: Card) -> None:
    look = overlay_appearance.current_look()

    def worker() -> None:
        try:
            render(card, placed_client(_overlay_client, look), look)
        except OSError:
            logger.debug("Could not reach the overlay for the route card", exc_info=True)

    threading.Thread(target=worker, name="WNTB-route-render", daemon=True).start()


_state: Optional[RouteOverlay] = None
_ticker: Optional[threading.Thread] = None
_stop = threading.Event()


def get_state() -> RouteOverlay:
    global _state
    if _state is None:
        _state = RouteOverlay(draw=_draw_live)
    return _state


def _tick_loop() -> None:
    state = get_state()
    while not _stop.wait(TICK_S):
        try:
            if state.showing():
                state.refresh()
        except Exception:
            logger.debug("Route overlay tick failed", exc_info=True)


def start(plugin_dir: str) -> None:
    global _ticker
    _stop.clear()
    if _ticker is None or not _ticker.is_alive():
        _ticker = threading.Thread(target=_tick_loop, name="WNTB-route-tick", daemon=True)
        _ticker.start()


def stop() -> None:
    _stop.set()


def handle_event(entry: Dict[str, Any], cmdr: str, system: Optional[str], station: Optional[str], state: Dict[str, Any]) -> None:
    get_state().handle_event(entry, system)


def dashboard_status(entry: Dict[str, Any]) -> None:
    get_state().handle_status(entry)


# --- Settings tab ----------------------------------------------------------------------------------------------------------

_vars: Dict[str, Any] = {}
_result_label: Optional[nb.Label] = None


def build_settings(notebook: nb.Notebook) -> None:
    global _result_label
    frame = nb.Frame(notebook)
    frame.columnconfigure(0, weight=1)
    notebook.add(frame, text="Route")
    cfg = load_config()

    nb.Label(
        frame,
        text=("A card on your in-game overlay, through EDMCModernOverlay (a separate, optional helper WNTB does not install or launch; "
              "its connection settings are on the Overlay Connection tab). At the top it shows your fuel, jump range, the fuel your "
              "last jump used, the jumps and light years left, and how far away the next supercharge is. Below it, the systems of the "
              "route plotted in the game, in order, with each system's star: neutron stars and white dwarfs are picked out so you can "
              "prepare for the supercharge, and other stars that cannot be scooped are marked too. Everything comes from your journal, "
              "the game's NavRoute.json and Status.json; nothing is sent anywhere."),
        wraplength=440, justify=tk.LEFT,
    ).grid(row=0, column=0, sticky=tk.W, padx=10, pady=(10, 4))
    HyperlinkLabel(
        frame, text="Get EDMCModernOverlay (recommended)", background=nb.Label().cget("background"),
        url="https://github.com/SweetJonnySauce/EDMCModernOverlay", underline=True,
    ).grid(row=1, column=0, sticky=tk.W, padx=10, pady=(0, 8))

    _vars["enabled"] = tk.BooleanVar(value=cfg.enabled)
    _vars["rows"] = tk.StringVar(value=str(cfg.rows))
    nb.Checkbutton(frame, text="Enable the Route overlay", variable=_vars["enabled"]).grid(row=2, column=0, sticky=tk.W, padx=10, pady=2)

    rows_row = tk.Frame(frame)
    rows_row.grid(row=3, column=0, sticky=tk.W, padx=(30, 10), pady=2)
    nb.Label(rows_row, text="Systems listed:").pack(side=tk.LEFT)
    tk.Spinbox(rows_row, from_=ROWS_RANGE[0], to=ROWS_RANGE[1], width=4, textvariable=_vars["rows"]).pack(side=tk.LEFT, padx=4)
    nb.Label(rows_row, text="(the rest are counted, with how many are neutron stars or white dwarfs)").pack(side=tk.LEFT)

    nb.Label(
        frame,
        text=("What WNTB cannot know: the journal does not say what a jump will cost in fuel, so the card shows the fuel on board and "
              "what your last jump used. The range is your ship's maximum with its current modules, not the range with the cargo and "
              "fuel it carries now. The route is shown while you are in one of its systems; if you jump off it, the card clears until "
              "you plot a new route."),
        wraplength=440, justify=tk.LEFT,
    ).grid(row=4, column=0, sticky=tk.W, padx=10, pady=(6, 4))

    action_row = tk.Frame(frame)
    action_row.grid(row=5, column=0, sticky=tk.W, padx=10, pady=(6, 2))
    tk.Button(action_row, text="Test Card", command=_test_card).pack(side=tk.LEFT)
    _result_label = nb.Label(action_row, text="", wraplength=320, justify=tk.LEFT)
    _result_label.pack(side=tk.LEFT, padx=(10, 0))
    nb.Label(frame, text="(Test Card works even while disabled above, and reports whether the overlay was actually reachable.)",
             wraplength=440, justify=tk.LEFT).grid(row=6, column=0, sticky=tk.W, padx=10, pady=(0, 10))


def _test_card() -> None:
    if _result_label is None:
        return
    cfg = overlay.load_config()
    client = overlay.OverlayClient(cfg)
    label = _result_label
    look = overlay_appearance.current_look()
    rows = clamp_rows(_vars["rows"].get()) if "rows" in _vars else DEFAULT_ROWS

    def worker() -> None:
        try:
            render(build_card(sample_tracker(), rows), placed_client(client, look), look)
            outcome, color = "Sent: check your overlay.", "#2e7d32"
        except OSError as err:
            outcome, color = f"Could not reach the overlay at {cfg.host}:{cfg.port} ({err}).", "#c07000"
        try:
            label.after(0, lambda: label.configure(text=outcome, foreground=color))
        except tk.TclError:
            pass   # the Settings dialog was closed before the test finished

    threading.Thread(target=worker, name="WNTB-route-test", daemon=True).start()


def save_settings() -> None:
    if not _vars:
        return
    save_config(RouteConfig(enabled=bool(_vars["enabled"].get()), rows=clamp_rows(_vars["rows"].get())))   # a card left up simply expires
