"""System targets: a card listing what is left to do in the system you are in.

After you have scanned bodies, it lists the ones worth mapping that you have not mapped (an estimated scan value at or above a threshold you choose,
most valuable first, with a tag for the classes that matter and a mark for a first discovery) and the ones with life that you have not finished
analysing (`2/3 life`). A body drops off the list when you map it or analyse its last organism, and the whole card goes when you leave the system. At the top
it shows how far the system scan has got after you have honked. The value is the same scan-value estimate the Exploration Value readout shows (see
`exploration_value.py`); what mapping pays on top of it is not estimated. The model is `system_survey.py`.

Nothing is sent anywhere: it reads the journal and draws through the shared overlay connection (EDMCModernOverlay, which WNTB does not install or
launch). Settings-tab-only and off until ticked, like every overlay. Where it sits is the global Overlay Placement setting ("System targets").
"""

from __future__ import annotations

import logging
import os
import threading
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import tkinter as tk

import myNotebook as nb
from config import appname, config
from ttkHyperlinkLabel import HyperlinkLabel

from . import overlay, overlay_appearance, overlay_placement, restore, system_survey
from .overlay import OverlayClient
from .overlay_card import Card, CardLayout, LiveCard, Ticker, Row, cut
from .overlay_style import LEGACY, Look
from .system_survey import Body, SystemSurvey, credits_text

plugin_name = os.path.basename(os.path.dirname(__file__))
logger = logging.getLogger(f"{appname}.{plugin_name}")

PANEL_PLACEMENT = None   # Settings-tab-only, no main-panel widget

_CFG_ENABLED = "wntb_targets_enabled"
_CFG_THRESHOLD = "wntb_targets_threshold"
_CFG_ROWS = "wntb_targets_rows"
_CFG_LIFE = "wntb_targets_life"
_CFG_ONLINE = "wntb_targets_online"
_CFG_DONE = "wntb_targets_done"
_CFG_BASIS = "wntb_targets_basis"

DEFAULT_THRESHOLD = 100_000
BASIS_SCAN, BASIS_MAPPED = "scan", "mapped"
DEFAULT_BASIS = BASIS_MAPPED          # a card of bodies to map ranks them by what mapping them pays
BASIS_LABELS = {BASIS_MAPPED: "Mapped value (what scanning and mapping pays)", BASIS_SCAN: "Scan value (what scanning alone pays)"}
THRESHOLD_RANGE = (0, 50_000_000)
ROWS_RANGE = (3, 16)
DEFAULT_ROWS = 6
OVERLAY_TTL = 4
NAME_CHARS = 26          # the body's short name, class tag and distance
TAG_CHARS = 12           # the value or the life count
SAMPLE_TAG = "123.4M first"
MAX_HEADER = 2
GROUP_NAME = "wntb_targets"
GROUP_PREFIX = "wntb_targets_"
LAYOUT = CardLayout(GROUP_PREFIX, x=650, y=100, max_header=MAX_HEADER, max_rows=ROWS_RANGE[1] + 2, name_chars=NAME_CHARS, tag_chars=TAG_CHARS,
                    sample_tag=SAMPLE_TAG, sample_lines=1 + DEFAULT_ROWS + 3)


@dataclass
class TargetsConfig:
    enabled: bool = False
    threshold: int = DEFAULT_THRESHOLD
    rows: int = DEFAULT_ROWS
    life: bool = True
    done: bool = True             # also list the bodies already finished, so where you left off is on the card
    online: bool = False          # also look up what other commanders have scanned in the system (EDSM)
    basis: str = DEFAULT_BASIS    # the value bodies are ranked and filtered by: what mapping them pays, or the scan alone


def _clamp(value: Any, low: int, high: int, default: int) -> int:
    try:
        return max(low, min(high, int(str(value).replace(",", "").strip())))
    except (TypeError, ValueError):
        return default


def load_config() -> TargetsConfig:
    return TargetsConfig(enabled=config.get_bool(_CFG_ENABLED, default=False),
                         threshold=_clamp(config.get_str(_CFG_THRESHOLD), *THRESHOLD_RANGE, DEFAULT_THRESHOLD),
                         rows=_clamp(config.get_str(_CFG_ROWS), *ROWS_RANGE, DEFAULT_ROWS), life=config.get_bool(_CFG_LIFE, default=True),
                         done=config.get_bool(_CFG_DONE, default=True), online=config.get_bool(_CFG_ONLINE, default=False),
                         basis=config.get_str(_CFG_BASIS) if config.get_str(_CFG_BASIS) in BASIS_LABELS else DEFAULT_BASIS)


def save_config(cfg: TargetsConfig) -> None:
    config.set(_CFG_ENABLED, cfg.enabled)
    config.set(_CFG_THRESHOLD, str(cfg.threshold))
    config.set(_CFG_ROWS, str(cfg.rows))
    config.set(_CFG_LIFE, cfg.life)
    config.set(_CFG_ONLINE, cfg.online)
    config.set(_CFG_DONE, cfg.done)
    config.set(_CFG_BASIS, cfg.basis)


# --- what the card says (pure) ---------------------------------------------------------------------------------------

def _distance(body: Body) -> str:
    ls = body.distance_ls
    if ls is None:
        return ""
    return f"{ls / 1000:.1f}k ls" if ls >= 10_000 else f"{ls:,.0f} ls"


def _map_row(body: Body, basis: str = BASIS_SCAN) -> Row:
    first = body.was_discovered is False
    left = f"{cut(body.short, 7)}\t{(body.tag + '  ' + _distance(body) + ('  EDSM' if body.known and not body.scanned else '')).strip()}"
    right = credits_text(body.mapped_value() if basis == BASIS_MAPPED else body.scan_value()) + (" first" if first else "")
    return cut(left, NAME_CHARS), cut(right, TAG_CHARS), "title" if first else "text"


def _life_row(body: Body) -> Row:
    done = len(set(body.analysed))
    genera = ", ".join(body.genuses)               # every genus, on lines of its own under the row
    return cut(body.short, NAME_CHARS) + (f"\n{genera}" if genera else ""), f"{done}/{body.bio} life" + (" FF" if body.first_footfall else ""), "info"


def _done_row(body: Body) -> Row:
    status = "mapped" if body.mapped else ""
    if body.bio:
        status += (" · " if status else "") + f"life {len(set(body.analysed))}/{body.bio}"
    return f"{cut(body.short, 7)}	{status}", "done", "ok"


def _summary(survey: SystemSurvey) -> str:
    """Where the survey stands in one line: how many bodies are mapped and how much of the life is analysed."""
    parts = []
    if survey.mapped_count():
        parts.append(f"{survey.mapped_count()} mapped")
    finished, with_life = survey.life_counts()
    if with_life:
        analysed, signals = survey.bio_totals()
        parts.append(f"life {finished} of {with_life} done" + (f" · {analysed} of {signals} analysed" if signals else ""))
    return " · ".join(parts)


def build_card(survey: SystemSurvey, threshold: int = DEFAULT_THRESHOLD, rows: int = DEFAULT_ROWS, life: bool = True, done: bool = True, basis: str = BASIS_SCAN) -> Card:
    """The card for the survey: the scan progress, a line on how far the mapping and the life have got, then what is left to map, what has life, and (when `done`)
    what is already finished, at most `rows` rows. Empty before the system is honked and while there is nothing to say."""
    if not survey.visible:
        return Card()
    maps = survey.to_map(threshold, basis)
    lives = survey.with_life() if life else []
    finished = survey.finished() if done else []
    total = survey.body_count
    badge = f"{survey.scanned_count()} of {total} scanned" if total else f"{survey.scanned_count()} scanned"
    if survey.known_count():
        badge += f" · {survey.known_count()} online"
    heading, progress = (survey.name, "title"), (survey.progress if survey.honked else None)
    summary = _summary(survey)
    header: List[tuple] = []
    if not maps and not lives:
        if not survey.honked and not finished:
            return Card()
        over = f"over {credits_text(threshold)}" if threshold else "scanned"
        header.append((f"Nothing {over} left to map or sample" if survey.fss_complete else f"Nothing {over} to map yet", "ok" if survey.fss_complete else "muted"))
    if summary:
        header.append((summary, "muted"))
    listed: List[Row] = []
    budget = rows
    for title, items, make in (("To map", maps, lambda body: _map_row(body, basis)), ("Life", lives, _life_row), ("Done", finished, _done_row)):
        if not items or budget < 2:
            continue
        listed.append((f"{title} ({len(items)})", "", "title"))
        budget -= 1
        for body in items[:budget]:
            listed.append(make(body))
        budget -= min(budget, len(items))
    hidden = (len(maps) + len(lives) + len(finished)) - sum(1 for r in listed if r[1])
    footer = (f"+ {hidden} more", "muted") if hidden > 0 else None
    return Card(tuple(header), tuple(listed), footer, title=heading, badge=badge, progress=progress)


def sample_survey() -> SystemSurvey:
    """A made-up system for the Test Card."""
    survey = SystemSurvey()
    survey.reset("Sample System", 1)
    survey.honked, survey.body_count, survey.progress = True, 9, 0.67
    data = [(1, "Earthlike body", True, False, 1.1), (2, "Water world", False, True, 0.9), (3, "High metal content body", False, True, 0.5),
            (4, "Icy body", False, False, 0.3), (5, "Rocky body", False, True, 0.2), (6, "Rocky body", False, True, 0.05)]
    for number, planet_class, terraformable, discovered, mass in data:
        body = survey._body(number, f"Sample System {number}")
        body.kind, body.planet_class, body.terraformable, body.was_discovered, body.mass_em, body.scanned = "planet", planet_class, terraformable, discovered, mass, True
    survey._body(4, "").bio = 3
    survey._body(4, "").landable, survey._body(4, "").was_footfalled = True, False
    survey._body(5, "").bio, survey._body(5, "").analysed = 2, ["Bacterium"]
    return survey


# --- state and the live path -----------------------------------------------------------------------------------------

_overlay_client = overlay.OverlayClient()


def set_overlay_client(client: overlay.OverlayClient) -> None:
    global _overlay_client
    _overlay_client = client


def block_rect(look: Look = LEGACY, card: Optional[Card] = None) -> tuple:
    return LAYOUT.block_rect(look, card)


def placed_client(client: OverlayClient, look: Look = LEGACY, card: Optional[Card] = None) -> OverlayClient:
    """`client` moved to where this card is placed, from the card's real size (so a bottom or right edge is the card's own edge)."""
    return overlay_placement.client_for_measured("system_targets", client, block_rect(look, card), look)


def render(card: Card, client: OverlayClient, look: Look = LEGACY) -> None:
    LAYOUT.render(card, client, look, ttl=OVERLAY_TTL)


def _build() -> Card:
    cfg = load_config()
    return build_card(system_survey.survey, cfg.threshold, cfg.rows, cfg.life, cfg.done, cfg.basis)


def _draw_live(card: Card) -> None:
    look = overlay_appearance.current_look()

    def worker() -> None:
        try:
            render(card, placed_client(_overlay_client, look, card), look)
        except OSError:
            logger.debug("Could not reach the overlay for the system targets", exc_info=True)

    threading.Thread(target=worker, name="WNTB-targets-render", daemon=True).start()


live = LiveCard(_build, lambda: load_config().enabled, _draw_live)
_ticker = Ticker("WNTB-targets-tick", live.refresh, 1.0, logger)


def start(plugin_dir: str) -> None:
    _ticker.start()


def stop() -> None:
    _ticker.stop()


def handle_event(entry: Dict[str, Any], cmdr: str, system: Optional[str], station: Optional[str], state: Dict[str, Any]) -> None:
    """Runs after `system_survey.handle_event` has updated the shared survey."""
    event = entry.get("event")
    if event in system_survey.EVENTS or event in ("StartUp", restore.RESTORE_EVENT):
        live.refresh()
    if event in ("FSSDiscoveryScan", "FSSAllBodiesFound", "StartUp", restore.RESTORE_EVENT):
        _look_up_known()


_looked_up: Dict[str, bool] = {}


def _look_up_known() -> None:
    """When it is switched on, asks EDSM once per system (after the honk) for the planets other commanders have scanned, and adds them to the survey."""
    survey = system_survey.survey
    if not load_config().online or not survey.visible or not survey.honked or _looked_up.get("system") == survey.name:
        return
    _looked_up["system"] = survey.name
    name = survey.name

    def worker() -> None:
        try:
            from . import edsm_client
            rows = edsm_client.system_bodies(name)
        except Exception:
            logger.debug("EDSM lookup for the system targets failed", exc_info=True)
            return
        if rows and system_survey.survey.merge_known(name, rows):
            live.refresh()

    threading.Thread(target=worker, name="WNTB-targets-edsm", daemon=True).start()


# --- Settings tab ----------------------------------------------------------------------------------------------------------

_vars: Dict[str, Any] = {}
_result_label: Optional[nb.Label] = None


def build_settings(notebook: nb.Notebook) -> None:
    global _result_label
    frame = nb.Frame(notebook)
    frame.columnconfigure(0, weight=1)
    notebook.add(frame, text="System targets")
    cfg = load_config()

    nb.Label(
        frame,
        text=("A card on your in-game overlay, through EDMCModernOverlay (a separate, optional helper WNTB does not install or launch; its connection "
              "settings are on the Overlay Connection tab). After you scan bodies in a system it lists the ones worth mapping that you have not mapped yet, "
              "and the ones with life that you have not finished analysing, until you do. It goes when you leave the system. The value is an estimate: what scanning "
              "and then mapping a body pays (or, if you choose, the scan alone), from the published formula; the game's own figure is the truth. Everything comes from your journal; nothing is sent anywhere unless you tick the EDSM lookup further down."),
        wraplength=440, justify=tk.LEFT,
    ).grid(row=0, column=0, sticky=tk.W, padx=10, pady=(10, 4))
    HyperlinkLabel(
        frame, text="Get EDMCModernOverlay (recommended)", background=nb.Label().cget("background"),
        url="https://github.com/SweetJonnySauce/EDMCModernOverlay", underline=True,
    ).grid(row=1, column=0, sticky=tk.W, padx=10, pady=(0, 8))

    _vars["enabled"] = tk.BooleanVar(value=cfg.enabled)
    _vars["life"] = tk.BooleanVar(value=cfg.life)
    _vars["done"] = tk.BooleanVar(value=cfg.done)
    _vars["online"] = tk.BooleanVar(value=cfg.online)
    _vars["threshold"] = tk.StringVar(value=f"{cfg.threshold}")
    _vars["rows"] = tk.StringVar(value=str(cfg.rows))
    nb.Checkbutton(frame, text="Enable the System targets card", variable=_vars["enabled"]).grid(row=2, column=0, sticky=tk.W, padx=10, pady=2)

    value_row = tk.Frame(frame)
    value_row.grid(row=3, column=0, sticky=tk.W, padx=(30, 10), pady=2)
    nb.Label(value_row, text="List bodies worth at least").pack(side=tk.LEFT)
    tk.Spinbox(value_row, from_=THRESHOLD_RANGE[0], to=THRESHOLD_RANGE[1], increment=25_000, width=10, textvariable=_vars["threshold"]).pack(side=tk.LEFT, padx=4)
    nb.Label(value_row, text="credits, judged by").pack(side=tk.LEFT)
    _vars["basis"] = tk.StringVar(value=BASIS_LABELS[cfg.basis])
    tk.OptionMenu(value_row, _vars["basis"], *BASIS_LABELS.values()).pack(side=tk.LEFT, padx=4)

    rows_row = tk.Frame(frame)
    rows_row.grid(row=4, column=0, sticky=tk.W, padx=(30, 10), pady=2)
    nb.Label(rows_row, text="Rows shown:").pack(side=tk.LEFT)
    tk.Spinbox(rows_row, from_=ROWS_RANGE[0], to=ROWS_RANGE[1], width=4, textvariable=_vars["rows"]).pack(side=tk.LEFT, padx=4)
    nb.Label(rows_row, text="(the rest are counted)").pack(side=tk.LEFT)

    nb.Checkbutton(frame, text="Also list bodies with life that I have not finished analysing", variable=_vars["life"]).grid(
        row=5, column=0, sticky=tk.W, padx=(30, 10), pady=2)

    nb.Checkbutton(frame, text="Also list the bodies I have finished (mapped, and their life analysed), so I can see where I left off", variable=_vars["done"]).grid(
        row=6, column=0, sticky=tk.W, padx=(30, 10), pady=2)
    nb.Checkbutton(frame, text="Also look up bodies other commanders have scanned (EDSM, once per system)",
                   variable=_vars["online"]).grid(row=7, column=0, sticky=tk.W, padx=(30, 10), pady=2)

    nb.Label(
        frame,
        text=("What WNTB cannot know: a body appears only after you have scanned it (the system scan or a detailed scan), because the journal gives its "
              "class and mass then, unless you tick the EDSM lookup above, which asks EDSM once per system after the honk (it sends only the system name) and adds the planets other commanders have already scanned. The list is rebuilt from your newest journal when EDMC starts in the middle of a system. Life counts come from the "
              "signal counts the scans give; the genera are known only after you map the body."),
        wraplength=440, justify=tk.LEFT,
    ).grid(row=8, column=0, sticky=tk.W, padx=10, pady=(6, 4))

    action_row = tk.Frame(frame)
    action_row.grid(row=9, column=0, sticky=tk.W, padx=10, pady=(6, 2))
    tk.Button(action_row, text="Test Card", command=_test_card).pack(side=tk.LEFT)
    _result_label = nb.Label(action_row, text="", wraplength=320, justify=tk.LEFT)
    _result_label.pack(side=tk.LEFT, padx=(10, 0))
    nb.Label(frame, text="(Test Card works even while disabled above, and reports whether the overlay was actually reachable.)",
             wraplength=440, justify=tk.LEFT).grid(row=10, column=0, sticky=tk.W, padx=10, pady=(0, 10))


def _typed() -> TargetsConfig:
    return TargetsConfig(enabled=bool(_vars["enabled"].get()), threshold=_clamp(_vars["threshold"].get(), *THRESHOLD_RANGE, DEFAULT_THRESHOLD),
                         rows=_clamp(_vars["rows"].get(), *ROWS_RANGE, DEFAULT_ROWS), life=bool(_vars["life"].get()), done=bool(_vars["done"].get()),
                         online=bool(_vars["online"].get()),
                         basis=next((key for key, label in BASIS_LABELS.items() if label == _vars["basis"].get()), DEFAULT_BASIS))


def _test_card() -> None:
    if _result_label is None or not _vars:
        return
    cfg = overlay.load_config()
    client = overlay.OverlayClient(cfg)
    label = _result_label
    look = overlay_appearance.current_look()
    typed = _typed()

    def worker() -> None:
        try:
            sample = build_card(sample_survey(), min(typed.threshold, 100_000), typed.rows, typed.life, typed.done, typed.basis)
            render(sample, placed_client(client, look, sample), look)
            outcome, color = "Sent: check your overlay.", "#2e7d32"
        except OSError as err:
            outcome, color = f"Could not reach the overlay at {cfg.host}:{cfg.port} ({err}).", "#c07000"
        try:
            label.after(0, lambda: label.configure(text=outcome, foreground=color))
        except tk.TclError:
            pass   # the Settings dialog was closed before the test finished

    threading.Thread(target=worker, name="WNTB-targets-test", daemon=True).start()


def save_settings() -> None:
    if _vars:
        save_config(_typed())   # a card left up simply expires
