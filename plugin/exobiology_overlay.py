"""Exobiology overlay cards for the body you are on, built from Organic Scanning's own prediction and sample tracking.

Four cards, each switched on separately in Settings -> Overlays -> Exobiology and placed on Overlay Placement:

- **Bio status**: how many of the body's biological signals you have analysed (with a progress bar); while you are sampling a genus, its species and
  color variant with three circles for the samples taken, what it pays (five times as much on a first footfall) and how far you are from the last
  sample against the distance the genus needs; with nothing in progress, each genus with its distance and whether it is done.
- **Biology**: every genus on the body with the species it could be (or is) and what each pays, and what the body could pay in all.
- **Bio radar**: where you are against the places you took samples, with a circle at each as wide as the genus's minimum distance (red while you are
  inside it, green once you are clear), the ship and the SRV, and the distance to the first two samples. See `exo_radar.py`.
- **Sample popup**: for a few seconds after each sample, the species, its estimated value, the distance the genus needs and what the sample was.

All read `organic_scan_panel.overlay_view()` (the controller's per-body state: genera from the journal, predictions from the scan conditions, sample
positions and the commander's position from Status.json), so they never disagree with the Organic Scanning panel. Nothing is sent anywhere. The idea of
showing these as separate cards over the cockpit comes from SrvSurvey's biology plotters; the code is WNTB's own.
"""

from __future__ import annotations

import logging
import os
import threading
import time
from dataclasses import dataclass
from typing import Any, Dict, Mapping, Optional

import tkinter as tk

import myNotebook as nb
from config import appname, config
from ttkHyperlinkLabel import HyperlinkLabel

from . import exo_radar, organic_scan, organic_species_data, overlay, overlay_appearance, overlay_placement, restore, system_survey
from .overlay import OverlayClient
from .overlay_card import Card, CardLayout, LiveCard, Ticker
from .overlay_style import LEGACY, Look
from .system_survey import credits_text, short_name

plugin_name = os.path.basename(os.path.dirname(__file__))
logger = logging.getLogger(f"{appname}.{plugin_name}")

PANEL_PLACEMENT = None   # Settings-tab-only, no main-panel widget

_CFG = {"status": "wntb_exo_status_enabled", "list": "wntb_exo_list_enabled", "radar": "wntb_exo_radar_enabled", "popup": "wntb_exo_popup_enabled"}

OVERLAY_TTL = 4
POPUP_SECONDS = 10.0
NAME_CHARS = 24
GROUPS = {"status": ("wntb_exo_status", "wntb_exo_status_"), "list": ("wntb_exo_pred", "wntb_exo_pred_"),
          "radar": ("wntb_exo_radar", "wntb_exo_radar_"), "popup": ("wntb_exo_popup", "wntb_exo_popup_")}
LAYOUT_STATUS = CardLayout(GROUPS["status"][1], x=650, y=100, max_header=3, max_rows=8, name_chars=NAME_CHARS, tag_chars=12, sample_tag="1000 m apart", sample_lines=6)
LAYOUT_LIST = CardLayout(GROUPS["list"][1], x=650, y=100, max_header=1, max_rows=12, name_chars=NAME_CHARS, tag_chars=14, sample_tag="up to 12.3M CR", sample_lines=8)
LAYOUT_POPUP = CardLayout(GROUPS["popup"][1], x=650, y=100, max_header=3, max_rows=4, name_chars=NAME_CHARS, tag_chars=14, sample_tag="5,000,000 cr", sample_lines=4)
LAYOUT_RADAR = exo_radar.RadarLayout(GROUPS["radar"][1], x=650, y=100)


@dataclass
class ExoConfig:
    status: bool = False
    list: bool = False
    radar: bool = False
    popup: bool = False


def load_config() -> ExoConfig:
    return ExoConfig(**{key: config.get_bool(name, default=False) for key, name in _CFG.items()})


def save_config(cfg: ExoConfig) -> None:
    for key, name in _CFG.items():
        config.set(name, getattr(cfg, key))


# --- what the cards say (pure) ---------------------------------------------------------------------------------------

def _credits(value: Optional[int]) -> str:
    return f"{credits_text(value)} CR" if value else "?"


def _metres(meters: float) -> str:
    return f"{meters:.0f} m"


def _short(view: organic_scan.BodyView, system: str) -> str:
    return short_name(view.body_name, system) if system else view.body_name


def _distance_line(genus: organic_scan.GenusView) -> Optional[tuple]:
    """(text, role) for how far you are from the last sample against what the genus needs, or None before the first sample or without a position."""
    if genus.distance_m is None or not genus.min_distance_m:
        return None
    if genus.distance_m >= genus.min_distance_m:
        return f"Clear: {_metres(genus.distance_m)} from the last sample, {_metres(genus.min_distance_m)} needed", "ok"
    return f"Move {_metres(genus.min_distance_m - genus.distance_m)} further: {_metres(genus.distance_m)} of {_metres(genus.min_distance_m)}", "warn"


def build_status_card(view: Optional[organic_scan.BodyView], system: str = "", scanned: Optional[tuple] = None) -> Card:
    """The Bio status card. `scanned` is (name, value) of the plant the Composition Scanner last identified, shown until it is sampled."""
    if view is None:
        return Card()
    total = view.signal_count or len(view.genera)
    title = ("Biological signals", "title")
    badge = f"{view.analysed} of {total} analysed" if total else ""
    progress = view.progress if total else None
    if not view.genera:
        return Card((("Map this body with the surface scanner to learn what lives here", "muted"),), title=title, badge=f"{total} signals", progress=None)
    active = view.active_genus
    if active is not None:
        filled = min(organic_scan.REQUIRED_SAMPLES, max(len(active.positions), active.stage))
        header = []
        reward = active.best_value
        if reward:
            header.append((f"{_credits(reward * view.multiplier)}" + (" (first footfall bonus)" if view.first_footfall else ""), "text"))
        header.append(_distance_line(active) or (f"Samples must be {_metres(active.min_distance_m)} apart", "muted"))
        header.extend(_tracking(view))
        return Card(tuple(header), title=title, badge=badge, progress=progress, headline=(active.title, "title"),
                    dots=tuple(i < filled for i in range(organic_scan.REQUIRED_SAMPLES)))
    rows = []
    for genus in view.genera:
        if genus.complete:
            rows.append((genus.title, "Done", "ok"))
        else:
            rows.append((genus.title, f"{_metres(genus.min_distance_m)} apart" if genus.min_distance_m else "", "muted"))
    if scanned and not (total and view.analysed >= total):
        name, value = scanned
        footer = (f"Scanned: {name}" + (f"  {_credits(value * view.multiplier)}" if value else "") + (" (first footfall bonus)" if value and view.first_footfall else ""), "info")
    elif total and view.analysed >= total:
        footer = ("All samples analysed" + (": first footfall paid five times" if view.first_footfall else ""), "ok")
    elif view.first_footfall:
        footer = ("First footfall: every reward here is five times as much", "info")
    else:
        footer = ("Use the Composition Scanner on a plant to begin", "muted")
    return Card(tuple(_tracking(view)), tuple(rows), footer, title=title, badge=badge, progress=progress)


def _tracking(view: organic_scan.BodyView) -> list:
    """One line that leads you back to the plant you identified, as a card header line: 'Tracking Tussock Pennatis: 342 m, 30° right'."""
    lines = exo_radar.track_lines(view)
    return [(f"{lines[0]}: {lines[1]}", "warn")] if lines else []


def build_list_card(view: Optional[organic_scan.BodyView], system: str = "") -> Card:
    """The Biology card: each genus with the species it could be, or is, and what it pays."""
    if view is None or not view.genera:
        return Card()
    rows = []
    for genus in view.genera:
        if genus.species:
            rows.append((genus.variant or genus.species, _credits(genus.value), "ok" if genus.complete else "title" if genus.stage else "text"))
        elif len(genus.candidates) == 1:
            name, value = genus.candidates[0]
            rows.append((name, "~" + _credits(value), "info"))
        elif genus.candidates:
            lines = "\n".join(f"{name}  {_credits(value)}" for name, value in sorted(genus.candidates, key=lambda c: -c[1]))
            rows.append((f"{genus.name}\n{lines}", f"up to {_credits(genus.best_value)}", "info"))
        else:
            rows.append((genus.name, "unknown", "muted"))
    total = view.reward_up_to
    footer = None
    if total:
        footer = (f"Rewards up to {_credits(total)}" + (f" (first footfall bonus: {_credits(total * view.multiplier)})" if view.first_footfall else ""), "title")
    count = view.signal_count or len(view.genera)
    return Card((), tuple(rows), footer, title=(f"Bio signals {_short(view, system)}", "title"), badge=f"{view.analysed} of {count} done")


def build_popup_card(info: Optional[Mapping[str, Any]]) -> Card:
    """The card shown for a few seconds after a sample. `info` has `name`, `value`, `range_m`, `scan` and `first_footfall`."""
    if not info:
        return Card()
    value = info.get("value") or 0
    paid = value * (organic_scan.FIRST_FOOTFALL_MULTIPLIER if info.get("first_footfall") else 1)
    rows = []
    if value:
        rows.append(("Estimated value", f"{paid:,} cr" + (" (FF bonus)" if info.get("first_footfall") else ""), "title"))
    if info.get("range_m"):
        rows.append(("Colony range", _metres(info["range_m"]), "text"))
    stage = {"Log": "Logged", "Sample": "Sampled", "Analyse": "Analysed"}.get(str(info.get("scan")), str(info.get("scan") or ""))
    return Card((), tuple(rows), (stage, "ok"), title=(str(info.get("name") or "Sample"), "title"))


def sample_view() -> organic_scan.BodyView:
    """A made-up body for the Test Cards: sampling a Tussock, standing 78 m from its second sample and 209 m from its first."""
    return organic_scan.BodyView(
        "Sample System 2 d", (
            organic_scan.GenusView("b", "Bacterium", 500.0, candidates=(("Bacterium Aurasus", 1_000_000), ("Bacterium Nebulus", 5_289_900))),
            organic_scan.GenusView("f", "Frutexa", 150.0, candidates=(("Frutexa Fera", 1_632_500),)),
            organic_scan.GenusView("t", "Tussock", 200.0, species="Tussock Pennatis", value=1_000_000, stage=2, distance_m=78.0,
                                   variant="Tussock Pennatis - Lime", positions=((0.0, 0.0), (0.0, 0.0125))),
            organic_scan.GenusView("o", "Osseus", 800.0, species="Osseus Fractus", value=4_000_000, stage=3, variant="Osseus Fractus - Red")),
        first_footfall=True, signal_count=4, here=(0.0, 0.0200), heading=30.0, radius_m=600_000.0, ship=(0.0, 0.0215), srv=None, active="t",
        waypoints=(organic_scan.Waypoint("t", "Tussock Pennatis - Lime", 0.0, 0.0290),), focus="t")


def sample_popup() -> Dict[str, Any]:
    return {"name": "Tussock Pennatis - Lime", "value": 1_000_000, "range_m": 200, "scan": "Sample", "first_footfall": True}


# --- state and the live path -----------------------------------------------------------------------------------------

_overlay_client = overlay.OverlayClient()
_popup: Dict[str, Any] = {"info": None, "until": 0.0}


def set_overlay_client(client: overlay.OverlayClient) -> None:
    global _overlay_client
    _overlay_client = client


def _view() -> Optional[organic_scan.BodyView]:
    from . import organic_scan_panel
    return organic_scan_panel.overlay_view()


class _Display:
    """One card: its layout, its Overlay Placement slot, how it is built and whether it is switched on."""

    def __init__(self, slot: str, layout: Any, build: Any, enabled: Any) -> None:
        self.slot, self.layout, self._build_card = slot, layout, build
        self.live = LiveCard(self._build, enabled, self._draw_live)

    def block_rect(self, look: Look = LEGACY, card: Any = None) -> tuple:
        return self.layout.block_rect(look) if isinstance(self.layout, exo_radar.RadarLayout) else self.layout.block_rect(look, card)

    def placed_client(self, client: OverlayClient, look: Look = LEGACY, card: Any = None) -> OverlayClient:
        """`client` moved to where this card is placed, from the card's real size (so a bottom or right edge is the card's own edge)."""
        return overlay_placement.client_for_measured(self.slot, client, self.block_rect(look, card), look)

    def render(self, card: Any, client: OverlayClient, look: Look = LEGACY) -> None:
        self.layout.render(card, client, look, ttl=OVERLAY_TTL)

    def _build(self) -> Any:
        if not system_survey.survey.visible:
            return Card() if not isinstance(self.layout, exo_radar.RadarLayout) else exo_radar.Plan()
        return self._build_card(_view(), system_survey.survey.name)

    def _draw_live(self, card: Any) -> None:
        look = overlay_appearance.current_look()

        def worker() -> None:
            try:
                self.render(card, self.placed_client(_overlay_client, look, card), look)
            except OSError:
                logger.debug("Could not reach the overlay for the %s card", self.slot, exc_info=True)

        threading.Thread(target=worker, name=f"WNTB-{self.slot}-render", daemon=True).start()


def _popup_card(_view_: Any, _system: str) -> Card:
    return build_popup_card(_popup["info"]) if time.time() < _popup["until"] else Card()


status = _Display("bio_status", LAYOUT_STATUS, lambda view, system: build_status_card(view, system, _codex_scan()), lambda: load_config().status)
listing = _Display("exobiology", LAYOUT_LIST, build_list_card, lambda: load_config().list)
radar = _Display("bio_radar", LAYOUT_RADAR, lambda view, system: exo_radar.build_plan(view), lambda: load_config().radar)
popup = _Display("bio_popup", LAYOUT_POPUP, _popup_card, lambda: load_config().popup)
DISPLAYS = (status, listing, radar, popup)


def _refresh_all() -> None:
    for display in DISPLAYS:
        display.live.refresh()


_ticker = Ticker("WNTB-exobiology-tick", lambda: [d.live.refresh() for d in DISPLAYS if d.live.showing()], 1.0, logger)


def start(plugin_dir: str) -> None:
    _ticker.start()


def stop() -> None:
    _ticker.stop()


def handle_event(entry: Dict[str, Any], cmdr: str, system: Optional[str], station: Optional[str], state: Dict[str, Any]) -> None:
    """Runs after Organic Scanning and the system survey have taken the event."""
    event = entry.get("event")
    if event == "ScanOrganic":
        _note_sample(entry)
        _codex.clear()
    elif event == "CodexEntry":
        _note_codex(entry)
    elif event in ("FSDJump", "Location", "CarrierJump"):
        _codex.clear()
    if event in ("ScanOrganic", "SAASignalsFound", "FSSBodySignals", "Scan", "SAAScanComplete", "Touchdown", "Liftoff", "LaunchSRV", "DockSRV",
                 "Disembark", "Embark", "StartUp", "Shutdown", restore.RESTORE_EVENT) or event in system_survey.EVENTS:
        _refresh_all()


_codex: Dict[str, Any] = {}      # the plant the Composition Scanner last identified: {"name": ..., "value": ...}


def _codex_scan() -> Optional[tuple]:
    return (_codex["name"], _codex["value"]) if _codex else None


def _note_codex(entry: Mapping[str, Any]) -> None:
    """An organism identified with the Composition Scanner (a CodexEntry of the organic-structures sub-category), before any sample is taken: its name and what it pays."""
    if entry.get("SubCategory") != "$Codex_SubCategory_Organic_Structures;":
        return
    name = str(entry.get("Name_Localised") or "")
    if not name:
        return
    value = next((s.value for s in organic_species_data.SPECIES.values() if name.casefold().startswith(s.name.casefold())), 0)
    _codex.clear()
    _codex.update({"name": name, "value": value})
    _refresh_all()


def _note_sample(entry: Mapping[str, Any]) -> None:
    """Remembers a sample for the popup: the species' value and the distance its genus needs between samples."""
    genus_key, species_key = entry.get("Genus"), entry.get("Species")
    info = organic_species_data.SPECIES.get(f"{genus_key}|{species_key}")
    genus = organic_species_data.GENUS.get(str(genus_key))
    view = _view()
    _popup["info"] = {"name": entry.get("Variant_Localised") or entry.get("Species_Localised") or entry.get("Genus_Localised") or "Sample",
                      "value": info.value if info else 0, "range_m": genus.min_distance_m if genus else 0, "scan": entry.get("ScanType"),
                      "first_footfall": bool(view and view.first_footfall)}
    _popup["until"] = time.time() + POPUP_SECONDS


def dashboard_status(entry: Mapping[str, Any]) -> None:
    """Status.json (about once a second): the commander's position moves, so the distances and the radar do."""
    _refresh_all()


# --- Settings tab ----------------------------------------------------------------------------------------------------------

_vars: Dict[str, Any] = {}
_result_label: Optional[nb.Label] = None
_LABELS = {"status": "Enable the Bio status card (progress, current species, distance to the last sample)",
           "list": "Enable the Biology card (predicted species and what they pay)",
           "radar": "Enable the Bio radar (samples, their circles, your ship and SRV)",
           "popup": "Enable the Sample popup (a few seconds after each sample)"}


def build_settings(notebook: nb.Notebook) -> None:
    global _result_label
    frame = nb.Frame(notebook)
    frame.columnconfigure(0, weight=1)
    notebook.add(frame, text="Exobiology")
    cfg = load_config()

    nb.Label(
        frame,
        text=("Four cards on your in-game overlay, through EDMCModernOverlay (a separate, optional helper WNTB does not install or launch; its connection "
              "settings are on the Overlay Connection tab), for the body you are on, whether you are in the ship, the SRV or on foot. They use Organic "
              "Scanning's prediction and sample tracking, so the genera appear once you have mapped the body. Everything comes from your journal and the "
              "game's Status.json; nothing is sent anywhere."),
        wraplength=440, justify=tk.LEFT,
    ).grid(row=0, column=0, sticky=tk.W, padx=10, pady=(10, 4))
    HyperlinkLabel(
        frame, text="Get EDMCModernOverlay (recommended)", background=nb.Label().cget("background"),
        url="https://github.com/SweetJonnySauce/EDMCModernOverlay", underline=True,
    ).grid(row=1, column=0, sticky=tk.W, padx=10, pady=(0, 8))

    for row, key in enumerate(_CFG, start=2):
        _vars[key] = tk.BooleanVar(value=getattr(cfg, key))
        nb.Checkbutton(frame, text=_LABELS[key], variable=_vars[key]).grid(row=row, column=0, sticky=tk.W, padx=10, pady=2)

    nb.Label(
        frame,
        text=("What WNTB cannot know: species are predicted from the body's conditions (the same prediction as the Organic Scanning panel), so a body can "
              "show several candidates until a sample names the species, and the color variant is known only after the first sample. A sample's "
              "position is known only for samples taken while EDMC was running, and the SRV's only from where you launched or left it."),
        wraplength=440, justify=tk.LEFT,
    ).grid(row=6, column=0, sticky=tk.W, padx=10, pady=(6, 4))

    action_row = tk.Frame(frame)
    action_row.grid(row=7, column=0, sticky=tk.W, padx=10, pady=(6, 2))
    tk.Button(action_row, text="Test Cards", command=_test_cards).pack(side=tk.LEFT)
    _result_label = nb.Label(action_row, text="", wraplength=320, justify=tk.LEFT)
    _result_label.pack(side=tk.LEFT, padx=(10, 0))
    nb.Label(frame, text="(Test Cards works even while disabled above, and reports whether the overlay was actually reachable.)",
             wraplength=440, justify=tk.LEFT).grid(row=8, column=0, sticky=tk.W, padx=10, pady=(0, 10))


def _test_cards() -> None:
    if _result_label is None:
        return
    cfg = overlay.load_config()
    client = overlay.OverlayClient(cfg)
    label = _result_label
    look = overlay_appearance.current_look()
    view = sample_view()

    def worker() -> None:
        try:
            for display, card in ((status, build_status_card(view, "Sample System")), (listing, build_list_card(view, "Sample System")),
                                  (radar, exo_radar.build_plan(view)), (popup, build_popup_card(sample_popup()))):
                display.render(card, display.placed_client(client, look, card), look)
            outcome, color = "Sent: check your overlay.", "#2e7d32"
        except OSError as err:
            outcome, color = f"Could not reach the overlay at {cfg.host}:{cfg.port} ({err}).", "#c07000"
        try:
            label.after(0, lambda: label.configure(text=outcome, foreground=color))
        except tk.TclError:
            pass   # the Settings dialog was closed before the test finished

    threading.Thread(target=worker, name="WNTB-exobiology-test", daemon=True).start()


def save_settings() -> None:
    if _vars:
        save_config(ExoConfig(**{key: bool(_vars[key].get()) for key in _CFG}))
