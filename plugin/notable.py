"""
Notable Bodies: an on-screen alert when a body you scan matches a rule you care about
(a terraformable landable, a shepherd moon, a body with every premium FSD material...).

Same shape as discovery.py: a tracker turns journal events into a card, `render()` draws it
through the shared EDMCOverlay connection, and a controller owns the Settings page. The rules
themselves live in notable_rules.py (pure and unit-tested); this module only decides *when*
to fire and *how long* to show it.

Off by default, and Settings only (no main-panel button): the Exploration row is already full.

Lives in the Exploration settings tab's "Alerts" page, beside Auto-Honk and Discovery Alerts.
"""

from __future__ import annotations

import json
import logging
import os
import threading
from collections import deque
from dataclasses import dataclass
from typing import Any, Callable, Deque, Dict, List, Mapping, Optional, Set, Tuple

import tkinter as tk

import myNotebook as nb
from config import appname, config

from . import discovery, notable_rules, overlay
from .overlay import OverlayClient

plugin_name = os.path.basename(os.path.dirname(__file__))
logger = logging.getLogger(f"{appname}.{plugin_name}")

_CFG_ENABLED = "wntb_notable_enabled"
_CFG_X = "wntb_notable_x"
_CFG_Y = "wntb_notable_y"
_CFG_RULES = "wntb_notable_rules"
DEFAULT_ENABLED = False

# Default position: straight under discovery.py's body card (its default Y plus the card offset
# and height), so the three alert cards stack when they fire together.
DEFAULT_X = discovery.DEFAULT_X
DEFAULT_Y = discovery.DEFAULT_Y + discovery._Y_BODY_OFFSET + discovery._CARD_H + 16

CARD_SHOW_S = 6.0
MAX_QUEUED = 3  # cards waiting behind the one on screen; any further ones are counted, not shown

# Worst-case sizes. The overlay is not EDMC's main window, but discovery.py's centring math
# estimates text width from character count, so the text must stay inside the card.
TITLE_MAX_CHARS = 28  # the card is ~416 px of text; "huge" estimates 14 px per character
NAME_MAX_CHARS = 24
NAME_WITH_MORE_MAX_CHARS = 34

_ELLIPSIS = "…"


def cap(text: str, limit: int) -> str:
    text = " ".join(str(text).split())
    return text if len(text) <= limit else text[: max(limit - 1, 0)].rstrip() + _ELLIPSIS


@dataclass
class NotableConfig:
    enabled: bool = DEFAULT_ENABLED
    x: int = DEFAULT_X
    y: int = DEFAULT_Y
    rules: Optional[Dict[str, bool]] = None  # explicit per-rule choices; a missing rule uses its default

    def enabled_rules(self) -> Set[str]:
        chosen = self.rules or {}
        return {rule.id for rule in notable_rules.RULES if chosen.get(rule.id, rule.default_on)}


def _get_int(key: str, default: int) -> int:
    raw = config.get_str(key)
    try:
        return int(raw) if raw else default
    except ValueError:
        return default


def parse_rules(raw: Optional[str]) -> Dict[str, bool]:
    """Saved rule choices; anything malformed or unknown is ignored (defaults apply)."""
    if not raw:
        return {}
    try:
        value = json.loads(raw)
    except ValueError:
        return {}
    if not isinstance(value, dict):
        return {}
    return {k: v for k, v in value.items() if k in notable_rules.RULES_BY_ID and isinstance(v, bool)}


def load_config() -> NotableConfig:
    return NotableConfig(
        enabled=config.get_bool(_CFG_ENABLED, default=DEFAULT_ENABLED),
        x=_get_int(_CFG_X, DEFAULT_X),
        y=_get_int(_CFG_Y, DEFAULT_Y),
        rules=parse_rules(config.get_str(_CFG_RULES)),
    )


def save_config(cfg: NotableConfig) -> None:
    config.set(_CFG_ENABLED, cfg.enabled)
    config.set(_CFG_X, str(cfg.x))
    config.set(_CFG_Y, str(cfg.y))
    config.set(_CFG_RULES, json.dumps(cfg.rules or {}))


@dataclass(frozen=True)
class Card:
    title: str
    name: str
    detail: str = ""


@dataclass
class NotableSnapshot:
    visible: bool = False
    title: str = ""
    name: str = ""
    more: int = 0  # cards waiting behind this one


def make_card(body_name: str, matches: List[notable_rules.Match]) -> Card:
    """One card for a body: the first rule's label as the title (+N when several matched)."""
    suffix = f" +{len(matches) - 1}" if len(matches) > 1 else ""
    title = cap(matches[0].label, TITLE_MAX_CHARS - len(suffix)) + suffix  # the "+N" must survive the cap
    detail = "; ".join(f"{m.label}: {m.detail}" for m in matches)
    return Card(title, cap(body_name or "Unknown body", NAME_MAX_CHARS), detail)


class NotableTracker:
    """Journal events in, cards out. `get_enabled` is read on every event so a Settings change
    applies immediately."""

    def __init__(self, on_change: Callable[[NotableSnapshot], None],
                 get_enabled: Callable[[], Set[str]] = notable_rules.default_enabled) -> None:
        self._on_change = on_change
        self._get_enabled = get_enabled
        self._lock = threading.RLock()

        self._system_address: Optional[int] = None
        self._bodies: Dict[int, Mapping[str, Any]] = {}
        self._alerted: Set[Tuple[Any, str]] = set()  # (BodyID or codex name, rule id)

        self._current: Optional[Card] = None
        self._queue: Deque[Card] = deque()
        self._overflow = 0
        self._timer: Optional[threading.Timer] = None

    # --- snapshot / test ------------------------------------------------------

    def get_snapshot(self) -> NotableSnapshot:
        with self._lock:
            if self._current is None:
                return NotableSnapshot()
            return NotableSnapshot(True, self._current.title, self._current.name, len(self._queue) + self._overflow)

    def trigger_test(self) -> None:
        """Settings' "Test Notable" button - one sample card through the live render path."""
        self._enqueue(Card("Terraformable landable", "Test Body 1 c", "Test"))

    # --- journal events -------------------------------------------------------

    def handle_event(self, entry: Mapping[str, Any]) -> None:
        event = entry.get("event")
        if event in ("FSDJump", "Location", "CarrierJump"):
            self._enter_system(entry.get("SystemAddress"))
        elif event == "Scan":
            self._on_scan(entry)
        elif event == "CodexEntry":
            self._on_codex(entry)

    def _enter_system(self, address: Any) -> None:
        if not isinstance(address, int) or isinstance(address, bool):
            return
        with self._lock:
            if address != self._system_address:
                self._system_address = address
                self._bodies = {}
                self._alerted = set()

    def _on_scan(self, entry: Mapping[str, Any]) -> None:
        body_id = entry.get("BodyID")
        if not isinstance(body_id, int) or isinstance(body_id, bool):
            return
        self._enter_system(entry.get("SystemAddress"))
        enabled = self._get_enabled()
        cards: List[Card] = []
        with self._lock:
            self._bodies[body_id] = entry
            # The body itself, plus any already-scanned body that orbits it: a moon scanned
            # before its parent can only be judged (shepherd, close orbit) once the parent arrives.
            candidates = [entry] + [
                other for other_id, other in self._bodies.items()
                if other_id != body_id and notable_rules.first_parent(other)[1] == body_id
            ]
            for scan in candidates:
                scan_id = scan.get("BodyID")
                new = [
                    m for m in notable_rules.evaluate(scan, self._bodies, enabled)
                    if (scan_id, m.rule_id) not in self._alerted
                ]
                if new:
                    self._alerted.update((scan_id, m.rule_id) for m in new)
                    cards.append(make_card(str(scan.get("BodyName") or ""), new))
                    logger.info("Notable body %s: %s", scan.get("BodyName"), cards[-1].detail)
        for card in cards:
            self._enqueue(card)

    def _on_codex(self, entry: Mapping[str, Any]) -> None:
        if "green_gas_giant" not in self._get_enabled() or not notable_rules.green_gas_giant_codex(entry):
            return
        name = str(entry.get("NearestDestination_Localised") or entry.get("NearestDestination")
                   or entry.get("Name_Localised") or "Codex entry")
        key = (str(entry.get("Name") or name), "green_gas_giant")
        with self._lock:
            if key in self._alerted:
                return
            self._alerted.add(key)
        self._enqueue(Card("Green gas giant", cap(name, NAME_MAX_CHARS), "Codex entry"))

    # --- queue and timer ------------------------------------------------------

    def _enqueue(self, card: Card) -> None:
        with self._lock:
            if self._current is None:
                self._show(card)
            elif len(self._queue) < MAX_QUEUED:
                self._queue.append(card)
            else:
                self._overflow += 1
        self._on_change(self.get_snapshot())

    def _show(self, card: Card) -> None:
        # Caller holds the lock.
        self._current = card
        if self._timer is not None:
            self._timer.cancel()
        self._timer = threading.Timer(CARD_SHOW_S, self._advance)
        self._timer.daemon = True
        self._timer.start()

    def _advance(self) -> None:
        with self._lock:
            self._timer = None
            if self._queue:
                self._show(self._queue.popleft())
            elif self._overflow:
                self._overflow = 0
                self._current = None
            else:
                self._current = None
        self._on_change(self.get_snapshot())


# --- Rendering -------------------------------------------------------------------------------

_TITLE_ID = "wntb_notable_title"
_NAME_ID = "wntb_notable_name"
_CARD_ID = "wntb_notable_card"

_TITLE_COLOR = "#c4b5fd"  # violet-300
_NAME_COLOR = "#ede9fe"  # violet-100
_BORDER_COLOR = "#80c4b5fd"  # violet-300 at 50% alpha - discovery.py's own border recipe

# This feature's own EDMCModernOverlay Plugin Group (see load.py's registration call).
GROUP_NAME = "wntb_notable"
GROUP_PREFIX = "wntb_notable_"


def render(snapshot: NotableSnapshot, client: OverlayClient, x: int = DEFAULT_X, y: int = DEFAULT_Y) -> None:
    """Draws (or clears) the card, anchored at (x, y), with discovery.py's card layout."""
    if not snapshot.visible:
        clear(client, x, y)
        return
    center_x = discovery._card_center_x(x)
    card_x, card_y = discovery._card_geometry(x, y)
    name = cap(snapshot.name, NAME_MAX_CHARS)
    if snapshot.more:
        name = cap(f"{name} ({snapshot.more} more)", NAME_WITH_MORE_MAX_CHARS)
    title = cap(snapshot.title, TITLE_MAX_CHARS)
    client.send_shape(
        _CARD_ID, "rect", _BORDER_COLOR, discovery._CHROME_FILL, card_x, card_y,
        discovery._CARD_W, discovery._CARD_H, ttl=30, thickness=discovery._CARD_BORDER_THICKNESS,
    )
    client.send_message(
        _TITLE_ID, title, _TITLE_COLOR, discovery._centered_x(title, "huge", center_x), y, ttl=30, size="huge",
    )
    client.send_message(
        _NAME_ID, name, _NAME_COLOR, discovery._centered_x(name, "large", center_x),
        y + discovery._Y_NAME_OFFSET, ttl=30, size="large",
    )


def clear(client: OverlayClient, x: int = DEFAULT_X, y: int = DEFAULT_Y) -> None:
    card_x, card_y = discovery._card_geometry(x, y)
    client.send_shape(_CARD_ID, "rect", "", "", card_x, card_y, 0, 0, ttl=1)
    client.send_message(_TITLE_ID, "", "white", x, y, ttl=1)
    client.send_message(_NAME_ID, "", "white", x, y + discovery._Y_NAME_OFFSET, ttl=1)


# --- Controller ------------------------------------------------------------------------------

_overlay_client = overlay.OverlayClient()


def set_overlay_client(client: overlay.OverlayClient) -> None:
    global _overlay_client
    _overlay_client = client


class NotableController:
    def __init__(self) -> None:
        self.tracker = NotableTracker(on_change=self._on_change, get_enabled=self._enabled_rules)
        self._enabled_var: Optional[tk.BooleanVar] = None
        self._x_var: Optional[tk.StringVar] = None
        self._y_var: Optional[tk.StringVar] = None
        self._rule_vars: Dict[str, tk.BooleanVar] = {}
        self._dependent_widgets: List[Any] = []
        self._result_label: Optional[nb.Label] = None

    def _enabled_rules(self) -> Set[str]:
        cfg = load_config()
        return cfg.enabled_rules() if cfg.enabled else set()

    def handle_event(self, entry: Dict[str, Any], cmdr: str, system: Optional[str], station: Optional[str],
                     state: Dict[str, Any]) -> None:
        # Body state is kept even while disabled, so turning the feature on mid-system still
        # has the neighbours it needs; the enabled-rule set (empty when off) is what gates alerts.
        if entry.get("event") in ("FSDJump", "Location", "CarrierJump", "Scan", "CodexEntry"):
            self.tracker.handle_event(entry)

    def _on_change(self, snapshot: NotableSnapshot) -> None:
        cfg = load_config()
        if not cfg.enabled:
            return

        def worker(x=cfg.x, y=cfg.y) -> None:
            try:
                render(snapshot, _overlay_client, x, y)
            except OSError:
                logger.debug("Could not reach EDMCOverlay for notable body alert", exc_info=True)

        threading.Thread(target=worker, name="WNTB-notable-render", daemon=True).start()

    # --- Settings tab -------------------------------------------------------------------------

    def build_settings(self, notebook: nb.Notebook) -> None:
        frame = nb.Frame(notebook)
        frame.columnconfigure(0, weight=1)
        notebook.add(frame, text="Notable Bodies")

        cfg = load_config()
        chosen = cfg.enabled_rules()

        nb.Label(
            frame,
            text=(
                "Shows a violet alert on your in-game overlay when a body you scan matches one of the "
                "rules below - via EDMCOverlay. A match is a lead from the scan data, not a promise: "
                "check the body in the system map. Connection settings are on the Overlay Connection tab."
            ),
            wraplength=440, justify=tk.LEFT,
        ).grid(row=0, column=0, columnspan=2, sticky=tk.W, padx=10, pady=(10, 4))

        self._enabled_var = tk.BooleanVar(value=cfg.enabled)
        nb.Checkbutton(
            frame, text="Enable Notable Bodies alerts", variable=self._enabled_var,
            command=self._update_dependent_state,
        ).grid(row=1, column=0, columnspan=2, sticky=tk.W, padx=10, pady=2)

        sub = nb.Frame(frame)
        sub.grid(row=2, column=0, columnspan=2, sticky=tk.W, padx=(28, 10))
        self._dependent_widgets = []
        self._rule_vars = {}
        for row, rule in enumerate(notable_rules.RULES):
            var = tk.BooleanVar(value=rule.id in chosen)
            self._rule_vars[rule.id] = var
            # ttk checkbuttons cannot wrap, so the label is the checkbox and the description a wrapped
            # label beside it.
            box = nb.Checkbutton(sub, text=rule.label, variable=var)
            box.grid(row=row, column=0, sticky=tk.W, pady=1)
            nb.Label(sub, text=rule.description, wraplength=260, justify=tk.LEFT).grid(
                row=row, column=1, sticky=tk.W, padx=(8, 0), pady=1)
            self._dependent_widgets.append(box)

        position_row = tk.Frame(frame)
        position_row.grid(row=3, column=0, columnspan=2, sticky=tk.W, padx=10, pady=(8, 2))
        nb.Label(position_row, text="Position — X:").pack(side=tk.LEFT)
        self._x_var = tk.StringVar(value=str(cfg.x))
        x_entry = nb.EntryMenu(position_row, textvariable=self._x_var, width=6)
        x_entry.pack(side=tk.LEFT, padx=(4, 0))
        nb.Label(position_row, text="   Y:").pack(side=tk.LEFT)
        self._y_var = tk.StringVar(value=str(cfg.y))
        y_entry = nb.EntryMenu(position_row, textvariable=self._y_var, width=6)
        y_entry.pack(side=tk.LEFT, padx=(4, 0))
        self._dependent_widgets += [x_entry, y_entry]

        nb.Label(
            frame,
            text=(
                "Position is the card's top-left corner. The default sits just below the Discovery "
                "Alerts cards. If several bodies match at once the cards take turns."
            ),
            wraplength=440, justify=tk.LEFT,
        ).grid(row=4, column=0, columnspan=2, sticky=tk.W, padx=10, pady=(4, 4))

        action_row = tk.Frame(frame)
        action_row.grid(row=5, column=0, columnspan=2, sticky=tk.W, padx=10, pady=(6, 2))
        tk.Button(action_row, text="Test Notable", command=self._test).pack(side=tk.LEFT)
        self._result_label = nb.Label(action_row, text="", wraplength=320, justify=tk.LEFT)
        self._result_label.pack(side=tk.LEFT, padx=(10, 0))

        nb.Label(
            frame,
            text="(Test Notable works even while disabled above, and reports whether EDMCOverlay was reachable.)",
            wraplength=440, justify=tk.LEFT,
        ).grid(row=6, column=0, columnspan=2, sticky=tk.W, padx=10, pady=(0, 10))

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

    def _test(self) -> None:
        if self._result_label is None:
            return
        cfg = overlay.load_config()
        client = OverlayClient(cfg)
        label = self._result_label
        pos_x = self._parse_coord(self._x_var, DEFAULT_X)
        pos_y = self._parse_coord(self._y_var, DEFAULT_Y)

        def render_once(snapshot: NotableSnapshot) -> None:
            try:
                render(snapshot, client, pos_x, pos_y)
                outcome, color = "Sent — check your overlay.", "#2e7d32"
            except OSError as err:
                outcome, color = f"Could not reach EDMCOverlay at {cfg.host}:{cfg.port} ({err}).", "#c07000"
            try:
                label.after(0, lambda: label.configure(text=cap(outcome, 120), foreground=color))
            except tk.TclError:
                pass

        tracker = NotableTracker(on_change=render_once)
        threading.Thread(target=tracker.trigger_test, name="WNTB-notable-test", daemon=True).start()

    def save_settings(self) -> None:
        if self._enabled_var is None:
            return
        save_config(NotableConfig(
            enabled=bool(self._enabled_var.get()),
            x=self._parse_coord(self._x_var, DEFAULT_X),
            y=self._parse_coord(self._y_var, DEFAULT_Y),
            rules={rule_id: bool(var.get()) for rule_id, var in self._rule_vars.items()},
        ))
        if not self._enabled_var.get():
            cfg = load_config()

            def worker(x=cfg.x, y=cfg.y) -> None:
                try:
                    clear(_overlay_client, x, y)
                except OSError:
                    logger.debug("Could not reach EDMCOverlay to clear notable body alert", exc_info=True)

            threading.Thread(target=worker, name="WNTB-notable-clear", daemon=True).start()


controller = NotableController()


def handle_event(entry: Dict[str, Any], cmdr: str, system: Optional[str], station: Optional[str],
                 state: Dict[str, Any]) -> None:
    controller.handle_event(entry, cmdr, system, station, state)


def build_settings(notebook: nb.Notebook) -> None:
    controller.build_settings(notebook)


def save_settings() -> None:
    controller.save_settings()
