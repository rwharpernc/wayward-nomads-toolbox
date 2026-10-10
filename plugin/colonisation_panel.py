"""Colonisation: tracks what each colonisation construction site still needs
delivered (see colonisation.py), and compares it to the cargo currently
aboard so a hauler can see what's left to source.

Field Ops only (PANEL_PLACEMENT = "fieldops") - hauling is ship/SRV cargo
work, alongside Inventory and Ship Builds. Same "one summary line + one
button in the panel, full list in a popup window" split as Ship Builds, so
the main panel stays narrow however many sites or commodities there are.
"""

from __future__ import annotations

import logging
import os
import threading
import time
from typing import Any, Dict, List, Optional

import tkinter as tk

import myNotebook as nb
from config import appname, config

from . import (colonisation, colonisation_carrier, colonisation_catchup, colonisation_overlay as card, colonisation_window,
               overlay, panelkit, restore)
from .colonisation import Site
from .colonisation_data import SiteRepository, site_repository

plugin_name = os.path.basename(os.path.dirname(__file__))
logger = logging.getLogger(f"{appname}.{plugin_name}")

PANEL_PLACEMENT = "fieldops"

_CFG_OVERLAY_ENABLED = "wntb_colonisation_overlay_enabled"
_CFG_OVERLAY_X = "wntb_colonisation_overlay_x"
_CFG_OVERLAY_Y = "wntb_colonisation_overlay_y"
_CFG_OVERLAY_ROWS = "wntb_colonisation_overlay_rows"


def _get_int(key: str, default: int, low: int, high: int) -> int:
    raw = config.get_str(key)
    try:
        return max(low, min(high, int(raw))) if raw else default
    except ValueError:
        return default


def overlay_enabled() -> bool:
    return config.get_bool(_CFG_OVERLAY_ENABLED, default=False)


def overlay_position() -> tuple:
    return (_get_int(_CFG_OVERLAY_X, card.DEFAULT_X, 0, card.MAX_ORIGIN_X),
            _get_int(_CFG_OVERLAY_Y, card.DEFAULT_Y, 0, card.MAX_ORIGIN_Y))


def overlay_rows() -> int:
    return _get_int(_CFG_OVERLAY_ROWS, card.DEFAULT_ROWS, card.MIN_ROWS, card.MAX_ROWS)


_NO_CMDR_TEXT = "Colonisation: (waiting for commander login)"
_NAME_MAX = 40


def _clip(text: str, limit: int) -> str:
    return text if len(text) <= limit else text[:limit - 1] + "…"


class ColonisationController:
    def __init__(self, repository: SiteRepository) -> None:
        self._repository = repository
        self._cmdr: Optional[str] = None
        # The depot events carry only a MarketID, so the station name is
        # remembered from the latest Docked (MarketID -> (station, system)).
        self._docked: Dict[int, tuple] = {}
        self._cargo: Dict[str, int] = {}
        self._carrier_cargo = colonisation_carrier.carrier_cargo
        self._carrier_feed = colonisation_carrier.Feeder(self._carrier_cargo)

        self._summary_var: Optional[tk.StringVar] = None
        self._parent: Optional[tk.Frame] = None

        # Overlay card state: what was last sent, when, and where (so it can be cleared or moved).
        self._overlay_client = overlay.OverlayClient()
        self._overlay_sent: List[card.Line] = []
        self._overlay_sent_at = 0.0
        self._overlay_pos = (card.DEFAULT_X, card.DEFAULT_Y)
        self._overlay_lock = threading.Lock()
        self._overlay_enabled_var: Optional[tk.BooleanVar] = None
        self._overlay_vars: Dict[str, tk.StringVar] = {}
        self._overlay_result: Optional[tk.Label] = None

    def set_overlay_client(self, client: overlay.OverlayClient) -> None:
        self._overlay_client = client

    # --- lifecycle ----------------------------------------------------------

    def start(self, plugin_dir: str) -> None:
        self._repository.load(plugin_dir)
        # EDMC does not replay old events at start-up, so the commander would stay unknown until the next one.
        self._cmdr = restore.latest_commander() or self._cmdr
        if self._cmdr:
            self._carrier_feed.cmdr = self._cmdr
        try:
            # Deliveries made while EDMC was closed are only in the journals.
            changed = colonisation_catchup.catch_up(
                self._repository, colonisation_catchup.known_commanders(self._repository))
            if changed:
                logger.info("Colonisation caught up from the journals: %d update(s) applied", changed)
        except Exception:
            logger.exception("Colonisation journal catch-up failed")
        self._repository.add_listener(self._refresh_summary)
        self._repository.add_listener(self._update_overlay)
        self._carrier_cargo.add_listener(self._update_overlay)
        self._carrier_cargo.load(plugin_dir)
        try:
            known = colonisation_catchup.known_commanders(self._repository)
            if colonisation_carrier.catch_up(self._carrier_cargo, known):
                logger.info("Fleet carrier transfers caught up from the journals")
        except Exception:
            logger.exception("Fleet carrier transfer catch-up failed")

    # --- journal dispatch -----------------------------------------------

    def handle_event(self, entry: Dict[str, Any], cmdr: str, system: Optional[str], station: Optional[str], state: Dict[str, Any]) -> None:
        self._handle_event(entry, cmdr, system, station, state)
        self._update_overlay()

    def _handle_event(self, entry: Dict[str, Any], cmdr: str, system: Optional[str], station: Optional[str], state: Dict[str, Any]) -> None:
        if cmdr and cmdr != self._cmdr:
            self._cmdr = cmdr
            self._refresh_summary()
            colonisation_window.refresh_cmdr(cmdr)
        if cmdr:
            self._carrier_feed.cmdr = cmdr
        try:
            if self._carrier_feed.feed(entry):
                self._carrier_cargo.commit()
        except Exception:
            logger.exception("Fleet carrier transfer tracking failed")

        cargo = colonisation.cargo_by_key(state.get("Cargo"))
        if cargo != self._cargo:
            self._cargo = cargo
            colonisation_window.refresh_cargo(cargo)

        event = entry.get("event")
        if not self._cmdr:
            return
        if event == "Docked":
            market_id = entry.get("MarketID")
            if isinstance(market_id, int) and entry.get("StationName"):
                self._docked[market_id] = (str(entry["StationName"]), str(entry.get("StarSystem") or system or ""))
        elif event == colonisation.EVENT_DEPOT:
            market_id = entry.get("MarketID")
            existing = self._repository.get(self._cmdr, market_id) if isinstance(market_id, int) else None
            # Work on a copy so the repository can tell whether anything changed.
            if existing is not None and not colonisation.is_newer(existing, entry, inclusive=True):
                return   # the start-up catch-up already folded this in
            working = Site.from_dict(existing.to_dict()) if existing else None
            name, docked_system = self._docked.get(market_id, ("", system or "")) if isinstance(market_id, int) else ("", "")
            site = colonisation.apply_depot_event(entry, working, name=name, system=docked_system)
            if site is not None:
                self._repository.upsert(self._cmdr, site)
        elif event == colonisation.EVENT_CONTRIBUTION:
            market_id = entry.get("MarketID")
            existing = self._repository.get(self._cmdr, market_id) if isinstance(market_id, int) else None
            if existing is not None and colonisation.is_newer(existing, entry, inclusive=False):
                working = Site.from_dict(existing.to_dict())
                if colonisation.apply_contribution(working, entry):
                    self._repository.upsert(self._cmdr, working)

    # --- overlay card ---------------------------------------------------------

    def _current_lines(self) -> List[card.Line]:
        if not overlay_enabled() or not self._cmdr:
            return []
        sites = [s for s in self._repository.for_cmdr(self._cmdr) if s.active]
        site = sites[0] if sites else None
        return card.card_lines(site, self._cargo, self._carrier_cargo.tonnes(self._cmdr), overlay_rows())

    def _update_overlay(self) -> None:
        """Redraw the shopping-list card if its content or position changed, or it is due a re-send before its time to
        live runs out; clear it when disabled or nothing is left to source. Cheap enough to call on every event."""
        lines = self._current_lines()
        position = overlay_position()
        now = time.monotonic()
        if (lines == self._overlay_sent and position == self._overlay_pos
                and (not lines or now - self._overlay_sent_at < card.RESEND_AFTER_S)):
            return
        previous, old_pos = self._overlay_sent, self._overlay_pos
        self._overlay_sent, self._overlay_pos, self._overlay_sent_at = lines, position, now
        if not lines and not previous:
            return

        def worker() -> None:
            with self._overlay_lock:
                try:
                    if old_pos != position and previous:
                        card.clear(self._overlay_client, old_pos[0], old_pos[1], len(previous))
                    card.render(self._overlay_client, lines, position[0], position[1], len(previous))
                except OSError:
                    logger.debug("Could not reach EDMCOverlay for the colonization shopping list", exc_info=True)

        threading.Thread(target=worker, name="WNTB-colonisation-overlay", daemon=True).start()

    def stop(self) -> None:
        """Synchronous clear at shutdown (EDMC does not wait for background threads)."""
        try:
            if self._overlay_sent:
                card.clear(self._overlay_client, self._overlay_pos[0], self._overlay_pos[1], len(self._overlay_sent))
        except OSError:
            logger.debug("Could not reach EDMCOverlay to clear on shutdown", exc_info=True)
        self._overlay_sent = []

    def _refresh_summary(self) -> None:
        if self._summary_var is None:
            return
        if not self._cmdr:
            self._summary_var.set(_NO_CMDR_TEXT)
            return
        active = [s for s in self._repository.for_cmdr(self._cmdr) if s.active]
        if not active:
            self._summary_var.set("Colonisation: no active construction sites")
            return
        latest = active[0]
        extra = f" (+{len(active) - 1} more)" if len(active) > 1 else ""
        self._summary_var.set(
            f"Colonisation: {_clip(latest.display_name(), _NAME_MAX)} — "
            f"{latest.progress:.0%}, {latest.remaining_total:,} t to go{extra}"
        )

    # --- main-panel widgets -----------------------------------------------

    def build_panel(self, parent: tk.Frame) -> None:
        self._parent = parent
        self._summary_var = tk.StringVar(value=_NO_CMDR_TEXT)
        self._refresh_summary()

        tk.Label(parent, text="Colonisation", font=panelkit.bold_font(parent)).grid(
            row=0, column=0, columnspan=3, sticky=tk.W,
        )
        panelkit.wrap_label(parent, textvariable=self._summary_var, anchor="w").grid(
            row=1, column=0, columnspan=3, sticky=tk.W, pady=(2, 0),
        )
        manage_button = tk.Button(parent, text="REPORT", command=self._on_manage_clicked)
        manage_button.grid(row=2, column=0, sticky=tk.W, pady=(4, 0))
        panelkit.add_tooltip(manage_button, "Colonisation Sites - open your colonisation sites")

    def _on_manage_clicked(self) -> None:
        if self._parent is None:
            return
        colonisation_window.show(self._parent, self._repository, self._cmdr or "", self._cargo, self._carrier_cargo)

    # --- Settings tab --------------------------------------------------

    def build_settings(self, notebook: nb.Notebook) -> None:
        frame = nb.Frame(notebook)
        frame.columnconfigure(0, weight=1)
        notebook.add(frame, text="Colonisation")

        nb.Label(frame, text="Colonization", font=("TkDefaultFont", 9, "bold")).grid(
            row=0, column=0, sticky=tk.W, padx=10, pady=(10, 4),
        )
        nb.Label(
            frame,
            text=(
                "Tracks what each colonization construction site still needs delivered. Dock at a "
                "construction depot (or open its market) once to register it; deliveries are then "
                "tallied from your journal. Press REPORT in Field Ops to "
                "open the sites window and see each site's outstanding commodities against the cargo you're carrying, and to "
                "copy a shopping list."
            ),
            wraplength=440, justify=tk.LEFT,
        ).grid(row=1, column=0, sticky=tk.W, padx=10, pady=(0, 10))

        self._overlay_enabled_var = tk.BooleanVar(value=overlay_enabled())
        nb.Checkbutton(
            frame, text="Show the shopping list on the in-game overlay", variable=self._overlay_enabled_var,
        ).grid(row=2, column=0, sticky=tk.W, padx=10, pady=(0, 2))
        nb.Label(
            frame,
            text=(
                "Lists what is still to source for your most recently updated active site (the To Source "
                "figures), biggest first, with any stock you have moved onto your fleet carrier shown as FC."
            ),
            wraplength=440, justify=tk.LEFT,
        ).grid(row=3, column=0, sticky=tk.W, padx=10, pady=(0, 6))

        x, y = overlay_position()
        self._overlay_vars = {"x": tk.StringVar(value=str(x)), "y": tk.StringVar(value=str(y)),
                              "rows": tk.StringVar(value=str(overlay_rows()))}
        position = tk.Frame(frame)
        position.grid(row=4, column=0, sticky=tk.W, padx=10, pady=(0, 2))
        nb.Label(position, text="Overlay position — X:").pack(side=tk.LEFT)
        nb.EntryMenu(position, textvariable=self._overlay_vars["x"], width=6).pack(side=tk.LEFT, padx=(4, 10))
        nb.Label(position, text="Y:").pack(side=tk.LEFT)
        nb.EntryMenu(position, textvariable=self._overlay_vars["y"], width=6).pack(side=tk.LEFT, padx=(4, 10))
        nb.Label(position, text="Rows:").pack(side=tk.LEFT)
        nb.EntryMenu(position, textvariable=self._overlay_vars["rows"], width=4).pack(side=tk.LEFT, padx=(4, 0))
        nb.Label(
            frame,
            text=(f"On the overlay's virtual screen (0-{card.MAX_ORIGIN_X} x 0-{card.MAX_ORIGIN_Y}). Default "
                  f"{card.DEFAULT_X}, {card.DEFAULT_Y}. Rows is how many commodities to list "
                  f"({card.MIN_ROWS}-{card.MAX_ROWS}); the rest are summarized."),
            wraplength=440, justify=tk.LEFT,
        ).grid(row=5, column=0, sticky=tk.W, padx=10, pady=(0, 6))

        action_row = tk.Frame(frame)
        action_row.grid(row=6, column=0, sticky=tk.W, padx=10, pady=(0, 10))
        tk.Button(action_row, text="Test Overlay", command=self._test_overlay).pack(side=tk.LEFT)
        self._overlay_result = nb.Label(action_row, text="", wraplength=320, justify=tk.LEFT)
        self._overlay_result.pack(side=tk.LEFT, padx=(10, 0))

    def _test_overlay(self) -> None:
        """Draw a sample card for a few seconds (works even while the overlay is switched off above)."""
        if self._overlay_result is None:
            return
        cfg = overlay.load_config()
        client = overlay.OverlayClient(cfg)
        label = self._overlay_result
        try:
            x = int(self._overlay_vars["x"].get().strip())
            y = int(self._overlay_vars["y"].get().strip())
        except (ValueError, KeyError):
            x, y = overlay_position()
        x, y = max(0, min(card.MAX_ORIGIN_X, x)), max(0, min(card.MAX_ORIGIN_Y, y))

        def worker() -> None:
            try:
                lines = card.preview_lines()
                card.render(client, lines, x, y)
                time.sleep(8)
                card.clear(client, x, y, len(lines))
                outcome, color = "Sent — check your overlay.", "#2e7d32"
            except OSError as err:
                outcome, color = f"Could not reach EDMCOverlay at {cfg.host}:{cfg.port} ({err}).", "#c07000"
            try:
                label.after(0, lambda: label.configure(text=outcome, foreground=color))
            except tk.TclError:
                pass

        threading.Thread(target=worker, name="WNTB-colonisation-overlay-test", daemon=True).start()

    def save_settings(self) -> None:
        if self._overlay_enabled_var is None:
            return
        config.set(_CFG_OVERLAY_ENABLED, self._overlay_enabled_var.get())
        for key, cfg_key, low, high in (("x", _CFG_OVERLAY_X, 0, card.MAX_ORIGIN_X),
                                        ("y", _CFG_OVERLAY_Y, 0, card.MAX_ORIGIN_Y),
                                        ("rows", _CFG_OVERLAY_ROWS, card.MIN_ROWS, card.MAX_ROWS)):
            try:
                config.set(cfg_key, max(low, min(high, int(self._overlay_vars[key].get().strip()))))
            except (ValueError, KeyError):
                pass
        self._update_overlay()


controller = ColonisationController(site_repository)


def start(plugin_dir: str) -> None:
    controller.start(plugin_dir)


def handle_event(entry: Dict[str, Any], cmdr: str, system: Optional[str], station: Optional[str], state: Dict[str, Any]) -> None:
    controller.handle_event(entry, cmdr, system, station, state)


def build_panel(parent: tk.Frame) -> None:
    controller.build_panel(parent)


def build_settings(notebook: nb.Notebook) -> None:
    controller.build_settings(notebook)


def save_settings() -> None:
    controller.save_settings()


def set_overlay_client(client: overlay.OverlayClient) -> None:
    controller.set_overlay_client(client)


def stop() -> None:
    controller.stop()
