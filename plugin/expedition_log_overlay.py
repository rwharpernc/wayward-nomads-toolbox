"""Expedition Log overlay: one card on the game screen that keeps the running expedition's totals in view: what exploring has found and earned, and what exobiology has
found and earned.

It reads the log (`expedition_log_panel.book`, totals from `expedition_log.py`), so it shows the same figures as the Expedition Log window. Exploration: systems, jumps and
light-years, bodies scanned and first discoveries, bodies mapped, the credits earned from selling data and what the unsold scans are worth. Exobiology: samples and species
analysed, first footfalls, the credits earned and what the unsold species are worth. The heading is the expedition's name and how long it has run; the foot is the total
earned. The unsold figures are estimates (marked `~`); earned figures are the totals the game reports when data is sold. Off until ticked in Settings -> Overlays ->
Expedition Log; it shows while an expedition is running (and, if you ask, the last one after it is stopped). Where it sits is the Overlay Placement setting
("Expedition Log"). Nothing is sent anywhere.
"""

from __future__ import annotations

import logging
import os
import threading
from dataclasses import dataclass
from typing import Any, Dict, Optional

import tkinter as tk

import myNotebook as nb
from config import appname, config
from ttkHyperlinkLabel import HyperlinkLabel

from . import expedition_log, expedition_log_panel, overlay, overlay_appearance, overlay_placement, restore, system_survey
from .expedition_log import short_credits
from .overlay import OverlayClient
from .overlay_card import Card, CardLayout, LiveCard, Row, Ticker
from .overlay_style import LEGACY, Look

plugin_name = os.path.basename(os.path.dirname(__file__))
logger = logging.getLogger(f"{appname}.{plugin_name}")

PANEL_PLACEMENT = None   # Settings-tab-only, no main-panel widget

_CFG_ENABLED = "wntb_expedition_log_overlay"
_CFG_AFTER = "wntb_expedition_log_overlay_after_stop"

OVERLAY_TTL = 4
GROUP_NAME = "wntb_expedition_log"
GROUP_PREFIX = "wntb_expedition_log_"
NAME_CHARS = 20
SAMPLE_TAG = "~1,234.5M cr"
LAYOUT = CardLayout(GROUP_PREFIX, x=650, y=100, max_header=1, max_rows=14, name_chars=NAME_CHARS, tag_chars=12, sample_tag=SAMPLE_TAG, sample_lines=13)


@dataclass
class LogOverlayConfig:
    enabled: bool = False
    after_stop: bool = False       # keep showing the last expedition once it has been stopped


def load_config() -> LogOverlayConfig:
    return LogOverlayConfig(enabled=config.get_bool(_CFG_ENABLED, default=False), after_stop=config.get_bool(_CFG_AFTER, default=False))


def save_config(cfg: LogOverlayConfig) -> None:
    config.set(_CFG_ENABLED, cfg.enabled)
    config.set(_CFG_AFTER, cfg.after_stop)


# --- what the card says (pure) ---------------------------------------------------------------------------------------

def build_card(run: Optional[expedition_log.Run], now: Optional[float] = None) -> Card:
    """The card for an expedition, or an empty one when there is none."""
    if run is None:
        return Card()
    t = run.totals
    state = "" if run.status == expedition_log.RUNNING else "stopped · "
    rows = [
        ("Exploration", "", "title"),
        ("Systems · jumps", f"{len(run.systems):,} · {t.jumps:,}", "text"),
        ("Distance", f"{t.light_years:,.0f} ly", "text"),
        ("Bodies scanned", f"{t.bodies_scanned:,}", "text"),
        ("First discoveries", f"{t.first_discoveries:,}", "title" if t.first_discoveries else "text"),
        ("Mapped (first)", f"{t.mapped:,} ({t.first_mapped:,})", "text"),
        ("Earned", f"{short_credits(t.explore_earned)} cr", "ok"),
        ("Unsold (est.)", f"~{short_credits(t.explore_estimated)} cr", "text"),
        ("Exobiology", "", "title"),
        ("Samples · species", f"{t.bio_samples:,} · {t.bio_species:,}", "text"),
        ("First footfalls", f"{t.bio_first_footfalls:,}", "title" if t.bio_first_footfalls else "text"),
        ("Earned", f"{short_credits(t.bio_earned)} cr", "ok"),
        ("Unsold (est.)", f"~{short_credits(t.bio_estimated)} cr", "text"),
    ]
    footer = (f"Total earned {short_credits(t.earned)} cr   (unsold ~{short_credits(t.unsold)})", "ok")
    return Card((), tuple(rows), footer, title=(expedition_log.clip(run.name, 28), "title"),
                badge=state + expedition_log.duration_text(run.elapsed(now)))


def idle_card(has_commander: bool = True) -> Card:
    """What the card says while it is switched on and no expedition is running, so a card that is on but empty is never a mystery."""
    if not has_commander:
        return Card((("Waiting for a commander (log in)", "muted"),), title=("Expedition Log", "title"))
    return Card((("No expedition is running", "muted"), ("Press START in the Exploration panel,", "muted"), ("or LOG, then Start since my last sale", "muted")),
                title=("Expedition Log", "title"))


def sample_run() -> expedition_log.Run:
    """A made-up expedition for the Test Card."""
    run = expedition_log.Run("sample", "Core Run", expedition_log.RUNNING, "2026-10-16T08:00:00Z", systems=[f"System {n}" for n in range(1, 13)])
    t = run.totals
    t.jumps, t.light_years, t.bodies_scanned, t.first_discoveries, t.mapped, t.first_mapped = 18, 342.0, 47, 31, 6, 4
    t.explore_earned, t.explore_estimated, t.bio_samples, t.bio_species, t.bio_first_footfalls = 1_234_567, 56_000, 9, 3, 2
    t.bio_earned, t.bio_estimated = 5_000_200, 1_100_000
    return run


# --- state and the live path -----------------------------------------------------------------------------------------

_overlay_client = overlay.OverlayClient()


def set_overlay_client(client: overlay.OverlayClient) -> None:
    global _overlay_client
    _overlay_client = client


def block_rect(look: Look = LEGACY, card: Optional[Card] = None) -> tuple:
    return LAYOUT.block_rect(look, card)


def placed_client(client: OverlayClient, look: Look = LEGACY, card: Optional[Card] = None) -> OverlayClient:
    return overlay_placement.client_for_measured("expedition_log", client, block_rect(look, card), look)


def render(card: Card, client: OverlayClient, look: Look = LEGACY) -> None:
    LAYOUT.render(card, client, look, ttl=OVERLAY_TTL)


def _shown_run() -> Optional[expedition_log.Run]:
    book = expedition_log_panel.book
    run = book.running()
    if run is not None:
        return run
    if load_config().after_stop:
        runs = book.runs()
        return runs[0] if runs else None
    return None


def _build() -> Card:
    if not system_survey.survey.playing:
        return Card()
    run = _shown_run()
    return build_card(run) if run is not None else idle_card(expedition_log_panel.book.ready)


def _draw_live(card: Card) -> None:
    look = overlay_appearance.current_look()

    def worker() -> None:
        try:
            render(card, placed_client(_overlay_client, look, card), look)
        except OSError:
            logger.debug("Could not reach the overlay for the expedition log", exc_info=True)

    threading.Thread(target=worker, name="WNTB-explog-render", daemon=True).start()


live = LiveCard(_build, lambda: load_config().enabled, _draw_live)
_ticker = Ticker("WNTB-explog-tick", live.refresh, 1.0, logger)


def start(plugin_dir: str) -> None:
    _ticker.start()


def stop() -> None:
    _ticker.stop()


def handle_event(entry: Dict[str, Any], cmdr: str, system: Optional[str], station: Optional[str], state: Dict[str, Any]) -> None:
    """Runs after the log has counted the event."""
    if entry.get("event") in expedition_log.SCAN_EVENTS or entry.get("event") in ("StartUp", "Shutdown", restore.RESTORE_EVENT):
        live.refresh()


# --- Settings tab ----------------------------------------------------------------------------------------------------------

_vars: Dict[str, Any] = {}
_result_label: Optional[nb.Label] = None


def build_settings(notebook: nb.Notebook) -> None:
    global _result_label
    frame = nb.Frame(notebook)
    frame.columnconfigure(0, weight=1)
    notebook.add(frame, text="Expedition Log")
    cfg = load_config()

    nb.Label(
        frame,
        text=("A card on your in-game overlay, through EDMCModernOverlay (a separate, optional helper WNTB does not install or launch; its connection "
              "settings are on the Overlay Connection tab), that keeps the running expedition's totals in view: exploration (systems, jumps, light-years, bodies "
              "scanned, first discoveries, mapped, and what you have earned from selling data) and exobiology (samples, species, first footfalls and what you have "
              "earned). You start, stop, name and edit expeditions with the LOG button in the Exploration panel. Everything comes from your journal; nothing is "
              "sent anywhere."),
        wraplength=440, justify=tk.LEFT,
    ).grid(row=0, column=0, sticky=tk.W, padx=10, pady=(10, 4))
    HyperlinkLabel(
        frame, text="Get EDMCModernOverlay (recommended)", background=nb.Label().cget("background"),
        url="https://github.com/SweetJonnySauce/EDMCModernOverlay", underline=True,
    ).grid(row=1, column=0, sticky=tk.W, padx=10, pady=(0, 8))

    _vars["enabled"] = tk.BooleanVar(value=cfg.enabled)
    _vars["after_stop"] = tk.BooleanVar(value=cfg.after_stop)
    nb.Checkbutton(frame, text="Enable the Expedition Log card", variable=_vars["enabled"]).grid(row=2, column=0, sticky=tk.W, padx=10, pady=2)
    nb.Checkbutton(frame, text="Keep showing the last expedition after I stop it", variable=_vars["after_stop"]).grid(
        row=3, column=0, sticky=tk.W, padx=(30, 10), pady=2)

    nb.Label(
        frame,
        text=("What WNTB cannot know: what the unsold scans and species are worth is an estimate (marked ~), cleared when you sell, and the mapping bonus is not "
              "included. Earned figures are what the game reports when you sell data, so they count when you sell, not when you scan. Only what happens while an "
              "expedition is running is counted; Rescan in the log window works an expedition out again from your journals."),
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

    def worker() -> None:
        try:
            sample = build_card(sample_run(), expedition_log.parse_time("2026-10-16T10:14:00Z"))
            render(sample, placed_client(client, look, sample), look)
            outcome, color = "Sent: check your overlay.", "#2e7d32"
        except OSError as err:
            outcome, color = f"Could not reach the overlay at {cfg.host}:{cfg.port} ({err}).", "#c07000"
        try:
            label.after(0, lambda: label.configure(text=outcome, foreground=color))
        except tk.TclError:
            pass   # the Settings dialog was closed before the test finished

    threading.Thread(target=worker, name="WNTB-explog-test", daemon=True).start()


def save_settings() -> None:
    if _vars:
        save_config(LogOverlayConfig(enabled=bool(_vars["enabled"].get()), after_stop=bool(_vars["after_stop"].get())))
