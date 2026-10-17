"""Body info: a card about one body, shown when you target it or are close to it.

It reads the body from the shared system survey (`system_survey.py`), so it shows what the scan gave: the name and class, flags worth knowing
(nobody has discovered it, it is terraformable, whether it is mapped), the estimated scan value, temperature, gravity (shown in the warning color
from `HIGH_GRAVITY` up), pressure, atmosphere, volcanism, life and geology signals, how far it is from the arrival point, and its main materials. A body you
have not scanned yet shows only its name and "scan required", because the journal gives its details only when it is scanned.

Which body: the one in `Status.json`'s `Destination` when it belongs to this system (the body you have targeted), else the one named by `BodyName`
(you are close to it). Each can be switched off. Nothing is sent anywhere. Settings-tab-only and off until ticked, like every overlay; where it sits is the global
Overlay Placement setting ("Body info").
"""

from __future__ import annotations

import logging
import os
import threading
from dataclasses import dataclass
from typing import Any, Dict, List, Mapping, Optional

import tkinter as tk

import myNotebook as nb
from config import appname, config
from ttkHyperlinkLabel import HyperlinkLabel

from . import chemistry, overlay, overlay_appearance, overlay_placement, restore, system_survey
from .overlay import OverlayClient
from .overlay_card import Card, CardLayout, LiveCard, Row, Ticker, cut
from .overlay_style import LEGACY, Look
from .system_survey import Body, SystemSurvey, credits_text

plugin_name = os.path.basename(os.path.dirname(__file__))
logger = logging.getLogger(f"{appname}.{plugin_name}")

PANEL_PLACEMENT = None   # Settings-tab-only, no main-panel widget

_CFG_ENABLED = "wntb_body_info_enabled"
_CFG_TARGETED = "wntb_body_info_targeted"
_CFG_NEAR = "wntb_body_info_near"

HIGH_GRAVITY = 2.0       # g and above is shown in the warning color; an arbitrary caution level, since the real limits differ by ship and vehicle
OVERLAY_TTL = 4
NAME_CHARS = 11
TAG_CHARS = 25
SAMPLE_TAG = "thin carbon dioxide, 100%"
TITLE_CHARS = 34         # the body's full name ("<system> 3 b a"), so the title is never cut
MAX_HEADER = 6
MAX_ROWS = 10
GROUP_NAME = "wntb_body_info"
GROUP_PREFIX = "wntb_body_info_"
LAYOUT = CardLayout(GROUP_PREFIX, x=650, y=100, max_header=MAX_HEADER, max_rows=MAX_ROWS, name_chars=NAME_CHARS, tag_chars=TAG_CHARS,
                    sample_tag=SAMPLE_TAG, sample_lines=MAX_HEADER + MAX_ROWS - 3,
                    title_chars=TITLE_CHARS, sample_badge="99,999 ls")


@dataclass
class BodyInfoConfig:
    enabled: bool = False
    targeted: bool = True
    near: bool = True


def load_config() -> BodyInfoConfig:
    return BodyInfoConfig(enabled=config.get_bool(_CFG_ENABLED, default=False), targeted=config.get_bool(_CFG_TARGETED, default=True),
                          near=config.get_bool(_CFG_NEAR, default=True))


def save_config(cfg: BodyInfoConfig) -> None:
    config.set(_CFG_ENABLED, cfg.enabled)
    config.set(_CFG_TARGETED, cfg.targeted)
    config.set(_CFG_NEAR, cfg.near)


# --- which body, and what the card says (pure) -----------------------------------------------------------------------------

def pick_body(survey: SystemSurvey, status: Mapping[str, Any], cfg: Optional[BodyInfoConfig] = None) -> Optional[Body]:
    """The body to describe: the targeted one (`Destination`, when it is in this system), else the one the ship is close to (`BodyName`)."""
    cfg = cfg or BodyInfoConfig()
    if not survey.visible:
        return None
    destination = status.get("Destination")
    if cfg.targeted and isinstance(destination, Mapping):
        in_system = survey.address is None or destination.get("System") in (None, survey.address)
        found = survey.find(destination.get("Body") if isinstance(destination.get("Body"), int) else None, str(destination.get("Name") or "")) if in_system else None
        if found is not None and not _finished(found):
            return found
        if found is None and in_system and destination.get("Name"):       # targeted but not scanned yet: the journal has nothing on it, so the card says to scan it
            name = str(destination["Name"])
            return Body(destination["Body"] if isinstance(destination.get("Body"), int) else -1, name, system_survey.short_name(name, survey.name))
    if cfg.near and status.get("BodyName"):
        return survey.find(None, str(status["BodyName"]))
    return None


def _finished(body: Body) -> bool:
    """A body with nothing left to do: mapped by you (when it can be mapped) and all its life analysed. The card does not hold on to a finished body you
    have targeted, so it can show the next one; it still shows one you are close to."""
    return body.scanned and body.kind == "planet" and body.mapped and (body.bio == 0 or body.life_done)


def _material(name: str) -> str:
    """A material of the body's surface as the card writes it: the element's symbol (Fe, S) or, with full names, the name."""
    symbol = chemistry.element(name) if chemistry.symbols_on() else None
    return symbol or name.capitalize()


def _spaced(name: str) -> str:
    """'CarbonDioxide' as 'Carbon dioxide' (the scan writes a gas without spaces)."""
    spaced = "".join(" " + c.lower() if c.isupper() and i else c for i, c in enumerate(name)).strip()
    return spaced[:1].upper() + spaced[1:]


def _clean(text: str, suffix: str = "") -> str:
    text = text.strip()
    if suffix and text.casefold().endswith(suffix):
        text = text[:-len(suffix)].strip()
    return text


def build_card(body: Optional[Body]) -> Card:
    """The card for one body, or an empty one."""
    if body is None:
        return Card()
    if not body.scanned and not body.known:
        header = [("Scan required", "muted")]
        if body.bio:
            header.append((f"{body.bio} life signal{'s' if body.bio != 1 else ''}", "info"))
        return Card(tuple(header), title=(body.name or body.short, "title"))
    header = [(body.planet_class or (f"{body.star_type} star" if body.star_type else "Body"), "text")]
    flags = []
    if body.was_discovered is False:
        flags.append("Undiscovered")
    if body.terraformable:
        flags.append("Terraformable")
    if body.first_footfall:
        flags.append("First footfall")
    if body.known and not body.scanned:
        flags.append("From EDSM, not scanned by you")
    elif body.kind == "planet":
        flags.append("Mapped by you" if body.mapped else "Mapped before" if body.was_mapped else "Unmapped")
    if flags:
        header.append((", ".join(flags), "info"))
    if body.materials:
        header.append((" · ".join(f"{_material(name)} {percent:.1f}%" for name, percent in sorted(body.materials, key=lambda m: -m[1])), "muted"))
    rows: List[Row] = []
    value = body.scan_value()
    if value:
        rows.append(("Scan value", credits_text(value) + (" first" if body.was_discovered is False else ""), "title"))
    if body.kind == "planet" and body.mapped_value() and not body.mapped:
        rows.append(("Mapped value", "~" + credits_text(body.mapped_value()), "text"))
    if body.temperature_k is not None:
        rows.append(("Temperature", f"{body.temperature_k:,.0f} K", "text"))
    if body.kind == "planet":
        if body.gravity_g is not None:
            rows.append(("Gravity", f"{body.gravity_g:.2f} g", "warn" if body.gravity_g >= HIGH_GRAVITY else "text"))
        if body.pressure_atm:
            rows.append(("Pressure", f"{body.pressure_atm:.3f} atm", "text"))
        if body.landable or body.atmosphere:
            parts = " · ".join(f"{chemistry.gas(name) if chemistry.symbols_on() else _spaced(name)} {percent:.1f}%" for name, percent in sorted(body.atmosphere_parts, key=lambda a: -a[1]))
            rows.append(("Atmosphere" + (f"\n{parts}" if parts else ""), chemistry.shorten(_clean(body.atmosphere, " atmosphere")) or "None", "text"))
            rows.append(("Volcanism", chemistry.shorten(_clean(body.volcanism, " volcanism")) or "None", "text"))
    if body.bio:
        done = len(set(body.analysed))
        rows.append(("Life", f"{body.bio} signal{'s' if body.bio != 1 else ''}, {done} done", "info"))
        if body.genuses:
            rows.append(("Genera", ", ".join(body.genuses), "info"))
    if body.bio and body.first_footfall:
        rows.append(("Footfall", "First: exobiology pays 5x", "title"))
    if body.geo:
        rows.append(("Geology", f"{body.geo} signal{'s' if body.geo != 1 else ''}", "info"))
    badge = f"{body.distance_ls:,.0f} ls" if body.distance_ls is not None else ""
    return Card(tuple(header[:MAX_HEADER]), tuple(rows[:MAX_ROWS]), title=(body.name, "title"), badge=badge, align="column")


def sample_body() -> Body:
    """A made-up body for the Test Card."""
    body = Body(7, "Sample System 3 b", "3 b", "planet", "Rocky body", terraformable=True, landable=True, was_discovered=False, was_mapped=False, was_footfalled=False,
                mass_em=0.35, gravity_g=0.57, pressure_atm=0.006, temperature_k=157.0, distance_ls=3936.0, atmosphere="thin carbon dioxide atmosphere",
                volcanism="minor silicate vapour volcanism", materials=[("iron", 20.9), ("sulphur", 20.3), ("carbon", 17.0)], scanned=True, bio=3, geo=2,
                genuses=["Bacterium", "Fungoida", "Osseus"], analysed=["Bacterium"])
    return body


# --- state and the live path -----------------------------------------------------------------------------------------

_overlay_client = overlay.OverlayClient()
_status: Dict[str, Any] = {}


def set_overlay_client(client: overlay.OverlayClient) -> None:
    global _overlay_client
    _overlay_client = client


def block_rect(look: Look = LEGACY, card: Optional[Card] = None) -> tuple:
    return LAYOUT.block_rect(look, card)


def placed_client(client: OverlayClient, look: Look = LEGACY, card: Optional[Card] = None) -> OverlayClient:
    """`client` moved to where this card is placed, from the card's real size (so a bottom or right edge is the card's own edge)."""
    return overlay_placement.client_for_measured("body_info", client, block_rect(look, card), look)


def render(card: Card, client: OverlayClient, look: Look = LEGACY) -> None:
    LAYOUT.render(card, client, look, ttl=OVERLAY_TTL)


def _build() -> Card:
    return build_card(pick_body(system_survey.survey, _status, load_config()))


def _draw_live(card: Card) -> None:
    look = overlay_appearance.current_look()

    def worker() -> None:
        try:
            render(card, placed_client(_overlay_client, look, card), look)
        except OSError:
            logger.debug("Could not reach the overlay for the body info", exc_info=True)

    threading.Thread(target=worker, name="WNTB-bodyinfo-render", daemon=True).start()


live = LiveCard(_build, lambda: load_config().enabled, _draw_live)
_ticker = Ticker("WNTB-bodyinfo-tick", live.refresh, 1.0, logger)


def start(plugin_dir: str) -> None:
    _ticker.start()


def stop() -> None:
    _ticker.stop()


def handle_event(entry: Dict[str, Any], cmdr: str, system: Optional[str], station: Optional[str], state: Dict[str, Any]) -> None:
    """Runs after `system_survey.handle_event` has updated the shared survey."""
    if entry.get("event") in system_survey.EVENTS or entry.get("event") in ("StartUp", restore.RESTORE_EVENT):
        live.refresh()


def dashboard_status(entry: Mapping[str, Any]) -> None:
    """The game's Status.json (about once a second in flight): keeps the target and the nearby body."""
    _status.clear()
    for key in ("Destination", "BodyName"):
        if key in entry:
            _status[key] = entry[key]
    live.refresh()


# --- Settings tab ----------------------------------------------------------------------------------------------------------

_vars: Dict[str, Any] = {}
_result_label: Optional[nb.Label] = None


def build_settings(notebook: nb.Notebook) -> None:
    global _result_label
    frame = nb.Frame(notebook)
    frame.columnconfigure(0, weight=1)
    notebook.add(frame, text="Body info")
    cfg = load_config()

    nb.Label(
        frame,
        text=("A card on your in-game overlay, through the overlay (WNTB's built-in one on Windows, or EDMCModernOverlay: a separate, optional helper WNTB does not install or launch; its connection "
              "settings are on the Overlay Connection tab). It describes one body: its class, whether it is undiscovered or terraformable or mapped, the "
              "estimated scan value, temperature, gravity, pressure, atmosphere, volcanism, life and geology signals, distance and its materials, written as "
              "element symbols and formulas (Fe, S, CO2) unless you choose full names below. It "
              "shows for the body you have targeted, and for the body you are close to. Everything comes from your journal and the game's Status.json; "
              "nothing is sent anywhere."),
        wraplength=440, justify=tk.LEFT,
    ).grid(row=0, column=0, sticky=tk.W, padx=10, pady=(10, 4))
    HyperlinkLabel(
        frame, text="Get EDMCModernOverlay (needed on Linux, and for other plugins' overlays)", background=nb.Label().cget("background"),
        url="https://github.com/SweetJonnySauce/EDMCModernOverlay", underline=True,
    ).grid(row=1, column=0, sticky=tk.W, padx=10, pady=(0, 8))

    _vars["enabled"] = tk.BooleanVar(value=cfg.enabled)
    _vars["targeted"] = tk.BooleanVar(value=cfg.targeted)
    _vars["near"] = tk.BooleanVar(value=cfg.near)
    nb.Checkbutton(frame, text="Enable the Body info card", variable=_vars["enabled"]).grid(row=2, column=0, sticky=tk.W, padx=10, pady=2)
    nb.Checkbutton(frame, text="Show the body I have targeted", variable=_vars["targeted"]).grid(row=3, column=0, sticky=tk.W, padx=(30, 10), pady=2)
    nb.Checkbutton(frame, text="Show the body I am close to", variable=_vars["near"]).grid(row=4, column=0, sticky=tk.W, padx=(30, 10), pady=2)

    style_row = tk.Frame(frame)
    style_row.grid(row=5, column=0, sticky=tk.W, padx=(30, 10), pady=2)
    nb.Label(style_row, text="Element and compound names:").pack(side=tk.LEFT)
    _vars["style"] = tk.StringVar(value=next((label for label, value in chemistry.STYLE_CHOICES if value == chemistry.style()), chemistry.STYLE_CHOICES[0][0]))
    tk.OptionMenu(style_row, _vars["style"], *[label for label, _v in chemistry.STYLE_CHOICES]).pack(side=tk.LEFT, padx=4)

    nb.Label(
        frame,
        text=("What WNTB cannot know: a body's details are known only after you have scanned it, so a body you have not scanned shows only its "
              "name. The scan value is an estimate and does not include what mapping pays. Gravity of 2.0 g and over is shown in the warning color; "
              "the real limit differs by ship and vehicle."),
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

    def worker() -> None:
        try:
            sample = build_card(sample_body())
            render(sample, placed_client(client, look, sample), look)
            outcome, color = "Sent: check your overlay.", "#2e7d32"
        except OSError as err:
            outcome, color = f"Could not reach the overlay at {cfg.host}:{cfg.port} ({err}).", "#c07000"
        try:
            label.after(0, lambda: label.configure(text=outcome, foreground=color))
        except tk.TclError:
            pass   # the Settings dialog was closed before the test finished

    threading.Thread(target=worker, name="WNTB-bodyinfo-test", daemon=True).start()


def save_settings() -> None:
    if _vars:
        save_config(BodyInfoConfig(enabled=bool(_vars["enabled"].get()), targeted=bool(_vars["targeted"].get()), near=bool(_vars["near"].get())))
        chosen = next((value for label, value in chemistry.STYLE_CHOICES if label == _vars["style"].get()), chemistry.DEFAULT_STYLE)
        config.set(chemistry.CFG_STYLE, chosen)
