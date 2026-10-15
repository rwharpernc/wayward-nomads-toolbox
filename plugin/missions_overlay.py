"""Missions on the in-game overlay: a small card for flying, listing the missions that matter where you are and where you are going.

You can hold up to twenty missions, so the card does not list them all. It puts first what you can act on now:

- **HERE**: missions whose turn-in (or destination) is in the system you are in,
- **NEXT**: the same for the system you have targeted for the next jump (the game's `FSDTarget`),
- the rest, soonest to expire first, up to the number of rows you set, then `+N more in M systems`.

A mission whose objective is done (the game's `MissionRedirected`) shows a tick and is listed first, with the place to hand it in. Missions against one faction
in one place (massacres and settlement raids) are stacked into a single line with a count. A mission with under an hour left shows in red, under six hours in
amber. The card has one fixed width, every line is clipped to it, and its top-left stays put (Overlay Placement says which corner), so it cannot grow across
the screen.

Everything comes from what the Missions mode already knows (`all_missions`, `kill_tracker`) and the journal's jump events; nothing is sent anywhere and nothing
is stored. Off until ticked, like every overlay. Pure layout (`build_lines`) is kept apart from drawing (`render`) so it is tested without an overlay."""
from __future__ import annotations

import logging
import os
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

import tkinter as tk

import myNotebook as nb
from config import appname, config
from ttkHyperlinkLabel import HyperlinkLabel

from . import active_missions, all_missions, kill_tracker, mission_types, overlay, overlay_appearance, overlay_placement
from .overlay import OverlayClient
from .overlay_style import LEGACY, Look

plugin_name = os.path.basename(os.path.dirname(__file__))
logger = logging.getLogger(f"{appname}.{plugin_name}")

PANEL_PLACEMENT = None   # Settings-tab-only, no main-panel widget

_CFG_ENABLED = "wntb_missions_overlay_enabled"
_CFG_ROWS = "wntb_missions_overlay_rows"
_CFG_NEXT = "wntb_missions_overlay_next"
_CFG_URGENT = "wntb_missions_overlay_urgent_minutes"

DEFAULT_ROWS = 8
MIN_ROWS = 3
MAX_ROWS = 14
DEFAULT_URGENT_MINUTES = 60
MIN_URGENT_MINUTES = 5
MAX_URGENT_MINUTES = 720
SOON_SECONDS = 6 * 3600
MASSACRES = (mission_types.MASSACRE_SPACE, mission_types.MASSACRE_GROUND)

LINE_CHARS = 46          # a line is clipped to this many characters
CHAR_SCALE = 1.25        # the wire protocol has no text metrics, so the box is measured this much wider than the plain estimate
EXTRA_LINES = 6          # heading, the three section headings, "+N more" and a spare: lines beyond the mission rows
_BASE_PAD_X = 12
_BASE_PAD_Y = 10
_X = 40
_Y = 420
GROUP_NAME = "wntb_missions"
GROUP_PREFIX = "wntb_missions_"
_CARD_ID = "wntb_missions_card"
_LINE_IDS = tuple(f"wntb_missions_line{i}" for i in range(MAX_ROWS + EXTRA_LINES))
OVERLAY_TTL = 90         # each draw lasts this long, so a stalled WNTB cannot leave the card up
RESEND_S = 45.0          # an unchanged card is drawn again this often
TICK_S = 30.0            # times left are recomputed this often
GREEN = "#4ade80"        # ready to hand in: always a clear green, whichever colour scheme is chosen
RED = "#f87171"          # under the urgent limit: a safety signal, so it does not follow the colour scheme (as the flight alerts do not)

Line = Tuple[str, str]   # (text, role)


@dataclass
class MissionsOverlayConfig:
    enabled: bool = False
    rows: int = DEFAULT_ROWS
    show_next: bool = True
    urgent_minutes: int = DEFAULT_URGENT_MINUTES


def _bounded(value: Any, low: int, high: int, default: int) -> int:
    try:
        number = int(str(value).strip())
    except ValueError:
        return default
    return max(low, min(high, number))


def load_config() -> MissionsOverlayConfig:
    return MissionsOverlayConfig(
        enabled=config.get_bool(_CFG_ENABLED, default=False),
        rows=_bounded(config.get_str(_CFG_ROWS), MIN_ROWS, MAX_ROWS, DEFAULT_ROWS),
        show_next=config.get_bool(_CFG_NEXT, default=True),
        urgent_minutes=_bounded(config.get_str(_CFG_URGENT), MIN_URGENT_MINUTES, MAX_URGENT_MINUTES, DEFAULT_URGENT_MINUTES))


def save_config(cfg: MissionsOverlayConfig) -> None:
    config.set(_CFG_ENABLED, cfg.enabled)
    config.set(_CFG_ROWS, str(cfg.rows))
    config.set(_CFG_NEXT, cfg.show_next)
    config.set(_CFG_URGENT, str(cfg.urgent_minutes))


# --- what a mission is, for the card ---------------------------------------------------------------------------------------

@dataclass(frozen=True)
class Entry:
    """One mission as the card sees it."""
    id: int
    category: str
    label: str                   # "Deliver 40 Gold", "Massacre"
    faction: str
    system: str                  # where to go now: the hand-in place once the objective is done, else the destination
    station: str
    reward: int
    expiry: Optional[datetime]
    ready: bool                  # the objective is done: hand it in
    progress: str = ""           # "12/40" for cargo


@dataclass(frozen=True)
class Item:
    """A line of the card: one mission, or several stacked."""
    label: str
    system: str
    station: str
    expiry: Optional[datetime]
    ready: bool
    count: int = 1


def parse_expiry(text: Any) -> Optional[datetime]:
    if not isinstance(text, str) or not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).astimezone(timezone.utc)
    except ValueError:
        return None


def _short_label(summary: all_missions.MissionSummary) -> str:
    """What to do, in a few words: the kind plus what or whom it is about."""
    category = summary.category
    if category in MASSACRES:
        return "Massacre" if category == mission_types.MASSACRE_SPACE else "Raid"
    if summary.needed_commodity and summary.cargo is not None and summary.cargo.total:
        return f"{summary.cargo.total} {summary.needed_commodity}"
    if summary.needed_commodity:
        return f"{summary.needed_commodity}"
    if summary.commodity:
        return f"Mine {summary.commodity}"
    return summary.name


def entries_from(missions: Dict[int, all_missions.MissionSummary], cmdr: Optional[str]) -> List[Entry]:
    """The card's entries from the Missions mode's active missions. A redirected mission is ready, and goes to its new hand-in place if the game gave one."""
    done = kill_tracker.get_redirected(cmdr)
    entries = []
    for summary in missions.values():
        ready = summary.id in done
        system, station = summary.destination_system, summary.destination_station
        if ready:
            dropoff = kill_tracker.get_redirect_destination(cmdr, summary.id)
            if dropoff and (dropoff.get("system") or dropoff.get("station")):
                system, station = str(dropoff.get("system") or system), str(dropoff.get("station") or station)
        progress = ""
        if summary.cargo is not None and summary.cargo.total:
            progress = f"{summary.cargo.delivered}/{summary.cargo.total}"
        entries.append(Entry(summary.id, summary.category, _short_label(summary), summary.source_faction, system, station, summary.reward,
                             parse_expiry(summary.expiry), ready, progress))
    return entries


# --- the lines -------------------------------------------------------------------------------------------------------------

def time_left(expiry: Optional[datetime], now: datetime) -> str:
    """'1h20m', '35m', '2d' or 'expired'; blank for a mission with no expiry."""
    if expiry is None:
        return ""
    seconds = int((expiry - now).total_seconds())
    if seconds <= 0:
        return "expired"
    if seconds < 60:
        return "<1m"
    if seconds < 3600:
        return f"{seconds // 60}m"
    if seconds < 86400:
        return f"{seconds // 3600}h{(seconds % 3600) // 60:02d}m"
    return f"{seconds // 86400}d"


def _fit(left: str, right: str, width: int = LINE_CHARS) -> str:
    """`left` and `right` on one line of `width` characters: `left` is cut short (with an ellipsis) so `right`, the time, always shows."""
    room = max(8, width - len(right) - (2 if right else 0))
    if len(left) > room:
        left = left[:room - 1].rstrip() + "…"
    return f"{left}  {right}" if right else left


def stack(entries: Sequence[Entry]) -> List[Item]:
    """Missions of one kind for one place become one item with a count (and the soonest expiry): massacres and raids against one faction, and any other
    missions with the same title, the same place and nothing that tells them apart (cargo progress). A mission with its own progress stays on its own line."""
    items: List[Item] = []
    stacked: Dict[Tuple[Any, ...], List[Entry]] = {}
    for entry in entries:
        if entry.progress:
            items.append(Item(f"{entry.label} {entry.progress}".strip(), entry.system, entry.station, entry.expiry, entry.ready))
            continue
        faction = entry.faction if entry.category in MASSACRES else ""
        stacked.setdefault((entry.category, entry.label, faction, entry.system.casefold(), entry.station.casefold(), entry.ready), []).append(entry)
    for group in stacked.values():
        first = group[0]
        expiries = [e.expiry for e in group if e.expiry is not None]
        text = f"{first.label} x{len(group)}" if len(group) > 1 else first.label
        if first.category in MASSACRES and first.faction:
            text += f" {first.faction}"
        items.append(Item(text, first.system, first.station, min(expiries) if expiries else None, first.ready, len(group)))
    return items


def _order(item: Item) -> Tuple[Any, ...]:
    far = datetime.max.replace(tzinfo=timezone.utc)
    return (not item.ready, item.expiry or far, item.label.casefold())


def _same(a: str, b: str) -> bool:
    return bool(a) and a.casefold() == b.casefold()


def _role(item: Item, now: datetime, urgent_seconds: int) -> str:
    if item.ready:
        return "ok"
    if item.expiry is not None:
        left = (item.expiry - now).total_seconds()
        if left < urgent_seconds:
            return "red"
        if left < SOON_SECONDS:
            return "warn"
    return "text"


def _clip(text: str, room: int) -> str:
    return text if len(text) <= room else text[:max(1, room - 1)].rstrip() + "…"


def _item_line(item: Item, where: str, now: datetime) -> str:
    """'✓ Title > Place  time': the title and the place share the room, the title getting a little over half, so neither pushes the other (or the time) off."""
    mark = "✓ " if item.ready else ""
    right = time_left(item.expiry, now)
    budget = LINE_CHARS - len(right) - (2 if right else 0) - len(mark)
    if not where:
        return _fit(mark + item.label, right)
    place_room = max(8, budget - len(" > ") - max(12, min(len(item.label), int(budget * 0.55))))
    place = _clip(where, place_room)
    title = _clip(item.label, budget - len(" > ") - len(place))
    return f"{mark}{title} > {place}" + (f"  {right}" if right else "")


def build_lines(entries: Sequence[Entry], here: str, next_system: str, rows: int, now: datetime,
                urgent_minutes: int = DEFAULT_URGENT_MINUTES, show_next: bool = True) -> List[Line]:
    """The card's lines, (text, role) each, for `entries`. Empty when there are no missions. At most `rows` mission lines are shown: the ones here first,
    then the next jump's, then the rest, each group soonest to expire first (a ready mission before any of them)."""
    if not entries:
        return []
    rows = max(MIN_ROWS, min(MAX_ROWS, rows))
    urgent = urgent_minutes * 60
    items = stack(entries)
    here_items = sorted((i for i in items if _same(i.system, here)), key=_order)
    next_items = sorted((i for i in items if show_next and _same(i.system, next_system) and not _same(next_system, here)), key=_order)
    placed = {id(i) for i in (*here_items, *next_items)}
    other_items = sorted((i for i in items if id(i) not in placed), key=_order)

    here_shown = here_items[:rows]
    next_shown = next_items[:max(0, rows - len(here_shown))]
    other_shown = other_items[:max(0, rows - len(here_shown) - len(next_shown))]
    hidden = [*here_items[len(here_shown):], *next_items[len(next_shown):], *other_items[len(other_shown):]]

    expiring = sum(i.count for i in items if not i.ready and i.expiry is not None and (i.expiry - now).total_seconds() < urgent)
    ready = sum(i.count for i in items if i.ready)
    total = sum(i.count for i in items)
    lines: List[Line] = [(_fit(f"MISSIONS {total}" + (f" · {ready} ready" if ready else "") + (f" · {expiring} soon" if expiring else ""), ""), "title")]

    def section(title: str, group: List[Item], use_station: bool) -> None:
        if not group:
            return
        if title:
            lines.append((_fit(title, ""), "header"))
        for item in group:
            where = item.station if use_station else (item.system or item.station)
            lines.append((_item_line(item, where, now), _role(item, now, urgent)))

    section(f"HERE {here}".strip(), here_shown, True)
    section(f"NEXT {next_system}".strip(), next_shown, True)
    section("ELSEWHERE" if (here_shown or next_shown) else "", other_shown, False)
    if hidden:
        systems = {(i.system or "?").casefold() for i in hidden}
        count = sum(i.count for i in hidden)
        lines.append((_fit(f"+{count} more in {len(systems)} system{'s' if len(systems) != 1 else ''}", ""), "muted"))
    return lines


# --- drawing ---------------------------------------------------------------------------------------------------------------

def _card_size(look: Look, line_count: int) -> Tuple[int, int]:
    """(width, height) of the card: the width never changes, the height is for `line_count` lines."""
    pad_x, pad_y = look.pad_x(_BASE_PAD_X), look.pad_y(_BASE_PAD_Y)
    width = int(look.char_px("normal") * LINE_CHARS * CHAR_SCALE) + 2 * pad_x
    return width, 2 * pad_y + line_count * look.line_px("normal")


def block_rect(look: Look = LEGACY, rows: int = DEFAULT_ROWS) -> Tuple[int, int, int, int]:
    """(left, top, width, height) of the card as placement sees it: a card of `rows` mission lines and its headings, so its top-left and its width do not
    move as lines come and go."""
    width, height = _card_size(look, rows + 4)
    return _X - look.pad_x(_BASE_PAD_X), _Y - look.pad_y(_BASE_PAD_Y), width, height


def placed_client(client: OverlayClient, look: Look = LEGACY, rows: int = DEFAULT_ROWS) -> OverlayClient:
    return overlay_placement.client_for("missions", client, block_rect(look, rows))


def _colour(look: Look, role: str) -> str:
    return RED if role == "red" else GREEN if role == "ok" else look.color(role)


def render(lines: List[Line], client: OverlayClient, look: Look = LEGACY) -> None:
    """Draws the card, or clears it when there are no lines. Raises OSError if the overlay cannot be reached; the live path swallows that and the Settings test
    reports it."""
    if not lines:
        clear(client)
        return
    lines = lines[:MAX_ROWS + EXTRA_LINES]
    width, height = _card_size(look, len(lines))
    left, top = _X - look.pad_x(_BASE_PAD_X), _Y - look.pad_y(_BASE_PAD_Y)
    client.send_shape(_CARD_ID, "rect", look.color("border"), look.color("fill"), left, top, width, height, ttl=OVERLAY_TTL, thickness=2)
    step = look.line_px("normal")
    for index, msg_id in enumerate(_LINE_IDS):
        if index < len(lines):
            text, role = lines[index]
            client.send_message(msg_id, text, _colour(look, role), _X, _Y + index * step, ttl=OVERLAY_TTL, size=look.size("normal"))
        else:
            client.send_message(msg_id, "", "white", _X, _Y + index * step, ttl=1)


def clear(client: OverlayClient) -> None:
    left, top, _w, _h = block_rect(LEGACY)
    client.send_shape(_CARD_ID, "rect", "", "", left, top, 0, 0, ttl=1)
    for index, msg_id in enumerate(_LINE_IDS):
        client.send_message(msg_id, "", "white", _X, _Y + index * LEGACY.line_px("normal"), ttl=1)


# --- state and the live path -----------------------------------------------------------------------------------------------

JUMP_EVENTS = ("FSDJump", "Location", "CarrierJump")


class MissionsOverlay:
    """Where the commander is and is heading, and what is on the card. `entries`, `now`, `draw` and `cfg` are injected so the behaviour is tested without the
    overlay, the Missions mode or the real clock."""

    def __init__(self, entries: Callable[[], List[Entry]], draw: Optional[Callable[[List[Line]], None]] = None,
                 now: Callable[[], datetime] = lambda: datetime.now(timezone.utc), cfg: Callable[[], MissionsOverlayConfig] = load_config,
                 clock: Callable[[], float] = time.monotonic) -> None:
        self._lock = threading.RLock()
        self._entries = entries
        self._draw = draw or (lambda lines: None)
        self._now = now
        self._cfg = cfg
        self._clock = clock
        self.here = ""
        self.next_system = ""
        self._last: Optional[List[Line]] = None
        self._last_sent = 0.0

    def handle_event(self, entry: Dict[str, Any]) -> None:
        event = entry.get("event")
        changed = False
        with self._lock:
            if event in JUMP_EVENTS:
                system = str(entry.get("StarSystem") or "")
                if system and system != self.here:
                    self.here, changed = system, True
                if _same(self.next_system, self.here):
                    self.next_system = ""          # arrived: the target is behind us
            elif event == "FSDTarget":
                target = str(entry.get("Name") or "")
                self.next_system = "" if _same(target, self.here) else target
                changed = True
            elif event in ("NavRouteClear", "LoadGame", "Shutdown"):
                self.next_system = ""
                changed = True
        if changed or event in ("MissionAccepted", "MissionCompleted", "MissionFailed", "MissionAbandoned", "MissionRedirected", "Missions"):
            self.refresh()

    def lines(self) -> List[Line]:
        cfg = self._cfg()
        with self._lock:
            return build_lines(self._entries(), self.here, self.next_system, cfg.rows, self._now(), cfg.urgent_minutes, cfg.show_next)

    def refresh(self) -> None:
        """Work out the card and draw it when it changed (or now and then, so it does not expire). Does nothing while the overlay is off."""
        if not self._cfg().enabled:
            return
        lines = self.lines()
        now = self._clock()
        if lines == self._last and now - self._last_sent < RESEND_S:
            return
        if not lines and not self._last:
            self._last = lines
            return
        self._last, self._last_sent = lines, now
        self._draw(lines)


_overlay_client = overlay.OverlayClient()


def set_overlay_client(client: overlay.OverlayClient) -> None:
    global _overlay_client
    _overlay_client = client


def _draw_live(lines: List[Line]) -> None:
    look = overlay_appearance.current_look()
    rows = load_config().rows

    def worker() -> None:
        try:
            render(lines, placed_client(_overlay_client, look, rows), look)
        except OSError:
            logger.debug("Could not reach the overlay for the missions card", exc_info=True)

    threading.Thread(target=worker, name="WNTB-missions-render", daemon=True).start()


def _live_entries() -> List[Entry]:
    return entries_from(all_missions.view.missions or {}, active_missions.tracker.commander)


_state: Optional[MissionsOverlay] = None
_ticker: Optional[threading.Thread] = None
_stop = threading.Event()


def get_state() -> MissionsOverlay:
    global _state
    if _state is None:
        _state = MissionsOverlay(_live_entries, draw=_draw_live)
    return _state


def _tick_loop() -> None:
    while not _stop.wait(TICK_S):
        try:
            get_state().refresh()
        except Exception:
            logger.debug("Missions overlay tick failed", exc_info=True)


def start(plugin_dir: str) -> None:
    global _ticker
    _stop.clear()
    all_missions.view.changed.connect(lambda _missions: get_state().refresh())     # the roster changed: a mission came, went or was handed in
    if _ticker is None or not _ticker.is_alive():
        _ticker = threading.Thread(target=_tick_loop, name="WNTB-missions-tick", daemon=True)
        _ticker.start()


def stop() -> None:
    _stop.set()


def handle_event(entry: Dict[str, Any], cmdr: str, system: Optional[str], station: Optional[str], state: Dict[str, Any]) -> None:
    get_state().handle_event(entry)


# --- Settings tab ----------------------------------------------------------------------------------------------------------

def sample_lines() -> List[Line]:
    """A made-up card for the Settings test: a mix of missions here, at the next jump and elsewhere."""
    soon = datetime.now(timezone.utc).replace(microsecond=0)

    def at(minutes: int) -> datetime:
        return soon + timedelta(minutes=minutes)

    entries = [
        Entry(1, mission_types.TRADE, "Gold", "", "Jarogee", "Newcomb Orbital", 720000, at(35), True),
        Entry(2, mission_types.TRADE, "40 Palladium", "", "Jarogee", "Fabian Port", 310000, at(200), False, "12/40"),
        Entry(3, mission_types.MASSACRE_SPACE, "Massacre", "Li Yong-Rui", "Jarogee", "Fabian Port", 900000, at(1500), False),
        Entry(4, mission_types.MASSACRE_SPACE, "Massacre", "Li Yong-Rui", "Jarogee", "Fabian Port", 800000, at(1700), False),
        Entry(5, mission_types.PASSENGER, "Passengers", "", "Sol", "Abraham Lincoln", 90000, at(300), False),
        Entry(6, mission_types.COMBAT, "Combat", "", "HIP 20019", "", 450000, at(5000), False),
        Entry(7, mission_types.COVERT, "Covert", "", "Ross 310", "Hudson Hub", 150000, at(9000), False),
    ]
    return build_lines(entries, "Jarogee", "Sol", DEFAULT_ROWS, soon)


_vars: Dict[str, Any] = {}
_result_label: Optional[nb.Label] = None


def build_settings(notebook: nb.Notebook) -> None:
    global _result_label
    frame = nb.Frame(notebook)
    frame.columnconfigure(0, weight=1)
    notebook.add(frame, text="Missions")
    cfg = load_config()

    nb.Label(
        frame,
        text=("A small card on your in-game overlay, through EDMCModernOverlay (a separate, optional helper WNTB does not install or launch; its connection "
              "settings are on the Overlay Connection tab). It lists the missions that matter where you are: those for the system you are in, then those for "
              "the system you have targeted for the next jump, then the rest soonest to expire, up to the number of rows you choose. A mission whose objective "
              "is done shows a tick and the place to hand it in; massacres against one faction stack into one line. Everything comes from the Missions mode "
              "and the journal; nothing is sent anywhere. Where the card sits is the Overlay Placement setting (\"Missions list\")."),
        wraplength=440, justify=tk.LEFT,
    ).grid(row=0, column=0, sticky=tk.W, padx=10, pady=(10, 4))
    HyperlinkLabel(
        frame, text="Get EDMCModernOverlay (recommended)", background=nb.Label().cget("background"),
        url="https://github.com/SweetJonnySauce/EDMCModernOverlay", underline=True,
    ).grid(row=1, column=0, sticky=tk.W, padx=10, pady=(0, 8))

    _vars["enabled"] = tk.BooleanVar(value=cfg.enabled)
    _vars["next"] = tk.BooleanVar(value=cfg.show_next)
    _vars["rows"] = tk.StringVar(value=str(cfg.rows))
    _vars["urgent"] = tk.StringVar(value=str(cfg.urgent_minutes))
    nb.Checkbutton(frame, text="Show missions on the overlay", variable=_vars["enabled"]).grid(row=2, column=0, sticky=tk.W, padx=10, pady=2)
    nb.Checkbutton(frame, text="Show the missions for the next jump (the system you have targeted)", variable=_vars["next"]).grid(
        row=3, column=0, sticky=tk.W, padx=10, pady=2)
    rows_row = tk.Frame(frame)
    rows_row.grid(row=4, column=0, sticky=tk.W, padx=(30, 10), pady=2)
    nb.Label(rows_row, text="Mission lines to show (at most)").pack(side=tk.LEFT)
    tk.Spinbox(rows_row, from_=MIN_ROWS, to=MAX_ROWS, width=4, textvariable=_vars["rows"]).pack(side=tk.LEFT, padx=4)
    nb.Label(rows_row, text="(the rest become \"+N more\")").pack(side=tk.LEFT)
    urgent_row = tk.Frame(frame)
    urgent_row.grid(row=5, column=0, sticky=tk.W, padx=(30, 10), pady=2)
    nb.Label(urgent_row, text="Show a mission in red when it has less than").pack(side=tk.LEFT)
    tk.Spinbox(urgent_row, from_=MIN_URGENT_MINUTES, to=MAX_URGENT_MINUTES, width=5, textvariable=_vars["urgent"]).pack(side=tk.LEFT, padx=4)
    nb.Label(urgent_row, text="minutes left (amber under six hours)").pack(side=tk.LEFT)

    nb.Label(
        frame,
        text=("What WNTB cannot know: the game lists your active missions only when you log in, so after restarting EDMC mid-game the card is built from your "
              "last two weeks of journals (see the Missions guide). The next jump is the system you have targeted; with no target, or a route you have not "
              "targeted a hop of, there is no NEXT section."),
        wraplength=440, justify=tk.LEFT,
    ).grid(row=6, column=0, sticky=tk.W, padx=10, pady=(6, 4))
    action_row = tk.Frame(frame)
    action_row.grid(row=7, column=0, sticky=tk.W, padx=10, pady=(6, 2))
    tk.Button(action_row, text="Test Card", command=_test_card).pack(side=tk.LEFT)
    _result_label = nb.Label(action_row, text="", wraplength=320, justify=tk.LEFT)
    _result_label.pack(side=tk.LEFT, padx=(10, 0))
    nb.Label(frame, text="(Test Card works even while disabled above, and reports whether the overlay was actually reachable.)",
             wraplength=440, justify=tk.LEFT).grid(row=8, column=0, sticky=tk.W, padx=10, pady=(0, 10))


def _test_card() -> None:
    if _result_label is None:
        return
    cfg = overlay.load_config()
    client = overlay.OverlayClient(cfg)
    label = _result_label
    look = overlay_appearance.current_look()
    lines = sample_lines()

    def worker() -> None:
        try:
            render(lines, placed_client(client, look, load_config().rows), look)
            outcome, color = "Sent: check your overlay.", "#2e7d32"
        except OSError as err:
            outcome, color = f"Could not reach the overlay at {cfg.host}:{cfg.port} ({err}).", "#c07000"
        try:
            label.after(0, lambda: label.configure(text=outcome, foreground=color))
        except tk.TclError:
            pass   # the Settings dialog was closed before the test finished

    threading.Thread(target=worker, name="WNTB-missions-test", daemon=True).start()


def save_settings() -> None:
    if not _vars:
        return
    save_config(MissionsOverlayConfig(
        enabled=bool(_vars["enabled"].get()), show_next=bool(_vars["next"].get()),
        rows=_bounded(_vars["rows"].get(), MIN_ROWS, MAX_ROWS, DEFAULT_ROWS),
        urgent_minutes=_bounded(_vars["urgent"].get(), MIN_URGENT_MINUTES, MAX_URGENT_MINUTES, DEFAULT_URGENT_MINUTES)))
    get_state().refresh()
