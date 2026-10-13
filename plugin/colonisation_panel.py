"""Colonisation: tracks what each colonisation construction site still needs
delivered (see colonisation.py), and compares it to the cargo currently
aboard so a hauler can see what's left to get.

Its own mode (PANEL_PLACEMENT = "colonisation", the COL button). The page shows the current project (progress, what is
delivered, what the ship and the fleet carrier cover, the trips left) and the commander's colonization history (sites
finished, tonnes delivered, recent activity); the full list is in a popup window (REPORT). What is shown and how it is
worded is in colonisation_stats.py, which adapts to a commander with or without a fleet carrier. A short fixed set of
rows, each clipped, so the main panel stays narrow however many sites or commodities there are.
"""

from __future__ import annotations

import logging
import os
import queue
import threading
import time
from typing import Any, Dict, FrozenSet, Optional, Tuple

import tkinter as tk

import myNotebook as nb
from config import appname, config

from . import (overlay_appearance, overlay_layout, overlay_placement, colonisation, colonisation_carrier, colonisation_catchup, colonisation_history, colonisation_overlay as card, rcc_keys, rcc_sync,
               colonisation_stats as stats, colonisation_window, overlay, panelkit, restore, trade_market, trade_panel)
from .colonisation import Site
from . import commander_data
from .colonisation_data import SiteRepository, site_repository

plugin_name = os.path.basename(os.path.dirname(__file__))
logger = logging.getLogger(f"{appname}.{plugin_name}")

PANEL_PLACEMENT = "colonisation"

_CFG_OVERLAY_ENABLED = "wntb_colonisation_overlay_enabled"
_CFG_OVERLAY_ROWS = "wntb_colonisation_overlay_row_limit"   # 0 = all; the older "..._rows" key held a default of 10
_CFG_OVERLAY_RIGHT_PANEL = "wntb_colonisation_overlay_right_panel"
_CFG_OVERLAY_FORCED = "wntb_colonisation_overlay_forced"   # the OVERLAY button: the card stays on until switched off, across restarts
_CFG_RCC_PROGRESS = "wntb_rcc_share_progress"      # report depot progress and deliveries to Raven Colonial (off by default)
_CFG_RCC_CARRIER = "wntb_rcc_share_carrier"        # report fleet carrier cargo changes to Raven Colonial (off by default)


def _journal_dir() -> str:
    """EDMC's journal folder, where the game writes Market.json."""
    return config.get_str("journaldir") or getattr(config, "default_journal_dir", "") or ""


def _get_int(key: str, default: int, low: int, high: int) -> int:
    raw = config.get_str(key)
    try:
        return max(low, min(high, int(raw))) if raw else default
    except ValueError:
        return default


def overlay_enabled() -> bool:
    return config.get_bool(_CFG_OVERLAY_ENABLED, default=False)


def rcc_share_progress() -> bool:
    return rcc_keys.enabled() and config.get_bool(_CFG_RCC_PROGRESS, default=False)


def rcc_share_carrier() -> bool:
    return rcc_keys.enabled() and config.get_bool(_CFG_RCC_CARRIER, default=False)


def overlay_right_panel() -> bool:
    return config.get_bool(_CFG_OVERLAY_RIGHT_PANEL, default=False)


def overlay_shift(shown: Optional[card.Card], look=None) -> tuple:
    """How far the card, drawn at its own fixed origin, is moved to reach the place chosen on the Overlay Placement tab
    (it depends on the card's size, so on what it is showing). (0, 0) when there is no card."""
    if shown is None:
        return (0, 0)
    look = look or overlay_appearance.current_look()
    block = card.block_rect(shown, card.DEFAULT_X, card.DEFAULT_Y, look)
    # The slot's nominal width is a worst-case guess; the card's real width is what a right edge or the group offset must use.
    if overlay_placement.note_measured_size("colonisation", (block[2], block[3]), look):
        threading.Thread(target=overlay_placement.apply_group_offsets, name="WNTB-overlay-offsets", daemon=True).start()
    return overlay_placement.shift_for("colonisation", block)


def overlay_rows() -> int:
    return _get_int(_CFG_OVERLAY_ROWS, card.DEFAULT_ROWS, card.MIN_ROWS, card.MAX_ROWS)


_NO_CMDR_TEXT = "Waiting for commander login"
_NAME_MAX = 40
_BAR_WIDTH, _BAR_HEIGHT = 220, 10   # fixed, so the progress bar can never widen EDMC's main window
_BAR_FILL, _BAR_DONE = "#ff8c0d", "#2e7d32"
_BAR_TRACK_DARK, _BAR_TRACK_LIGHT = "#3a3a3a", "#c8c8c8"


def _clip(text: str, limit: int) -> str:
    return text if len(text) <= limit else text[:limit - 1] + "…"


class ColonisationController:
    def __init__(self, repository: SiteRepository) -> None:
        self._repository = repository
        self._cmdr: Optional[str] = None
        self._system = ""   # the system the commander is in, for the window's "where to buy" search
        # The commodities the docked station has for sale, from its market when it was opened (None = no market known),
        # for the window's "Only what this station sells" filter.
        self._market: Optional[Tuple[str, FrozenSet[str]]] = None
        # The depot events carry only a MarketID, so the station name is
        # remembered from the latest Docked (MarketID -> (station, system)).
        self._docked: Dict[int, tuple] = {}
        self._cargo: Dict[str, int] = {}
        self._capacity = 0   # the ship's cargo capacity, for the trips figure on the overlay
        self._carrier_cargo = colonisation_carrier.carrier_cargo
        self._ledger = colonisation_history.DeliveryLedger()
        # The one-time rebuild of each commander's delivery history from every journal they have: read on a worker thread,
        # applied on the Tk thread (the queue), with any delivery made meanwhile held to be folded in afterwards.
        self._history_results: "queue.Queue[Tuple[str, list]]" = queue.Queue()
        self._history_pending: set = set()
        self._history_live: list = []
        self._carrier_feed = colonisation_carrier.Feeder(self._carrier_cargo)
        self._rcc = rcc_sync.RccSync(rcc_share_progress, rcc_share_carrier, rcc_keys.keys.get)

        self._vars: Dict[str, tk.StringVar] = {}      # the page's value cells, by name
        self._rows: Dict[str, tuple] = {}             # name -> (caption label, value label), to hide a row that does not apply
        self._bar: Optional[tk.Canvas] = None
        self._parent: Optional[tk.Frame] = None

        # Overlay card state: what was last sent, when, and where (so it can be cleared or moved).
        self._overlay_client = overlay.OverlayClient()
        self._overlay_sent: Optional[card.Card] = None
        self._overlay_sent_at = 0.0
        self._overlay_pos = (0, 0)   # how far the card is shifted from where it is drawn
        self._overlay_look = None    # the look it was last drawn with, so a change of appearance redraws it
        self._visibility = card.Visibility()
        self._last_focus: Any = None
        self._last_reason = ""
        self._overlay_lock = threading.Lock()
        self._overlay_enabled_var: Optional[tk.BooleanVar] = None
        self._rcc_enabled_var: Optional[tk.BooleanVar] = None
        self._rcc_progress_box: Any = None
        self._rcc_carrier_box: Any = None
        self._rcc_progress_var: Optional[tk.BooleanVar] = None
        self._rcc_carrier_var: Optional[tk.BooleanVar] = None
        self._rcc_key_var: Optional[tk.StringVar] = None
        self._right_panel_var: Optional[tk.BooleanVar] = None
        self._show_button: Optional[tk.Button] = None
        self._show_off_colors = ("", "")
        self._overlay_vars: Dict[str, tk.StringVar] = {}
        self._overlay_result: Optional[tk.Label] = None

    def set_overlay_client(self, client: overlay.OverlayClient) -> None:
        self._overlay_client = client

    # --- lifecycle ----------------------------------------------------------

    def start(self, plugin_dir: str) -> None:
        self._repository.load(plugin_dir)
        self._carrier_cargo.set_external_check(trade_panel.fleet_carrier)   # the same answer Trade gives
        # EDMC does not replay old events at start-up, so the commander would stay unknown until the next one.
        self._cmdr = restore.latest_commander() or self._cmdr
        if self._cmdr:
            self._carrier_feed.cmdr = self._cmdr
        try:
            # Deliveries made while EDMC was closed are only in the journals.
            self._ledger.load(plugin_dir)
            changed = colonisation_catchup.catch_up(
                self._repository, colonisation_catchup.known_commanders(self._repository), ledger=self._ledger)
            if changed:
                logger.info("Colonisation caught up from the journals: %d update(s) applied", changed)
        except Exception:
            logger.exception("Colonisation journal catch-up failed")
        self._repository.add_listener(self._refresh_summary)
        self._repository.add_listener(self._update_overlay)
        self._carrier_cargo.add_listener(self._update_overlay)
        self._carrier_cargo.add_listener(self._refresh_summary)
        self._ledger.add_listener(self._refresh_summary)
        self._carrier_cargo.load(plugin_dir)
        for cmdr in {*colonisation_catchup.known_commanders(self._repository), self._cmdr or ""}:
            self._maybe_backfill_history(cmdr)
        try:
            known = colonisation_catchup.known_commanders(self._repository)
            if colonisation_carrier.catch_up(self._carrier_cargo, known):
                logger.info("Fleet carrier transfers caught up from the journals")
        except Exception:
            logger.exception("Fleet carrier transfer catch-up failed")

    # --- delivery history rebuild ---------------------------------------------

    def _maybe_backfill_history(self, cmdr: str) -> None:
        """Once per commander, rebuild their delivery history from all their journals (the start-up catch-up only reads the
        last 14 to 30 days). A failure is logged and tried again at the next start."""
        key = commander_data.key_for(cmdr)
        if not key or key in self._history_pending or self._ledger.backfilled(cmdr):
            return
        self._history_pending.add(key)

        def work() -> None:
            try:
                self._history_results.put((cmdr, colonisation_catchup.read_all_events(cmdr)))
            except Exception:
                logger.exception("Colonization history rebuild failed for %s", cmdr)
                self._history_pending.discard(key)

        threading.Thread(target=work, daemon=True, name="WNTB-colonisation-history").start()

    def _poll_history_backfill(self) -> None:
        """On the Tk thread: apply a finished rebuild."""
        try:
            cmdr, entries = self._history_results.get_nowait()
        except queue.Empty:
            pass
        else:
            key = commander_data.key_for(cmdr)
            newer = [e for who, e in self._history_live if commander_data.key_for(who) == key]
            self._history_live = [(who, e) for who, e in self._history_live if commander_data.key_for(who) != key]
            try:
                replaced = self._ledger.rebuild(cmdr, entries, newer)
                self._ledger.commit()
                logger.info("Colonization history rebuilt for %s from %d delivery event(s)%s", cmdr, len(entries),
                            "" if replaced else " (the saved figures were larger, so they were kept)")
            except Exception:
                logger.exception("Could not apply the rebuilt colonization history for %s", cmdr)
            self._history_pending.discard(key)
        if self._parent is not None:
            self._parent.after(500, self._poll_history_backfill)

    # --- journal dispatch -----------------------------------------------

    def handle_event(self, entry: Dict[str, Any], cmdr: str, system: Optional[str], station: Optional[str], state: Dict[str, Any]) -> None:
        if entry.get("event") in ("Market", "Music", "Docked", "Undocked", "CarrierStats", "CargoTransfer", "Outfitting",
                                  "Shipyard", "ColonisationConstructionDepot"):
            logger.debug("Colonization overlay: journal event %s %s", entry.get("event"),
                         entry.get("MusicTrack") or entry.get("StationType") or "")
        self._visibility.feed(entry)
        self._handle_event(entry, cmdr, system, station, state)
        self._update_overlay()

    def _handle_event(self, entry: Dict[str, Any], cmdr: str, system: Optional[str], station: Optional[str], state: Dict[str, Any]) -> None:
        if system:
            self._system = system
        if cmdr and cmdr != self._cmdr:
            self._cmdr = cmdr
            self._maybe_backfill_history(cmdr)
            self._refresh_summary()
            colonisation_window.refresh_cmdr(cmdr)
        if cmdr:
            self._carrier_feed.cmdr = cmdr
        try:
            if self._carrier_feed.feed(entry):
                self._carrier_cargo.commit()
        except Exception:
            logger.exception("Fleet carrier transfer tracking failed")
        if entry.get("event") == "CargoTransfer" and self._carrier_feed.at_fleet_carrier and cmdr:
            self._rcc.on_carrier_transfer(cmdr, self._carrier_feed.carrier_market_id, entry)

        capacity = state.get("CargoCapacity")
        capacity_changed = False
        if isinstance(capacity, (int, float)) and not isinstance(capacity, bool):
            capacity_changed = int(capacity) != self._capacity
            self._capacity = int(capacity)
        cargo = colonisation.cargo_by_key(state.get("Cargo"))
        if cargo != self._cargo:
            self._cargo = cargo
            colonisation_window.refresh_cargo(cargo)
            self._refresh_summary()
        elif capacity_changed:   # a different ship with the same cargo (say both empty): the trips figure changes
            colonisation_window.refresh_cargo(cargo)
            self._refresh_summary()

        event = entry.get("event")
        self._track_market(event, entry, station)
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
                self._rcc.on_depot(self._cmdr, entry, site.system or docked_system, site.name)
        elif event in colonisation.CLAIM_EVENTS:
            if commander_data.key_for(self._cmdr) in self._history_pending:
                self._history_live.append((self._cmdr, entry))
            if self._ledger.apply_event(self._cmdr, entry):
                self._ledger.commit()
        elif event == colonisation.EVENT_CONTRIBUTION:
            if commander_data.key_for(self._cmdr) in self._history_pending:
                self._history_live.append((self._cmdr, entry))   # the rebuild in progress may not have read this one
            if self._ledger.apply_contribution(self._cmdr, entry):
                self._ledger.commit()
            market_id = entry.get("MarketID")
            existing = self._repository.get(self._cmdr, market_id) if isinstance(market_id, int) else None
            if existing is not None and colonisation.is_newer(existing, entry, inclusive=False):
                working = Site.from_dict(existing.to_dict())
                if colonisation.apply_contribution(working, entry):
                    self._repository.upsert(self._cmdr, working)
            if isinstance(market_id, int):
                known = self._repository.get(self._cmdr, market_id)
                self._rcc.on_contribution(self._cmdr, entry, (known.system if known else "") or self._system or "",
                                          known.name if known else "")

    def _track_market(self, event: Any, entry: Dict[str, Any], station: Optional[str]) -> None:
        """Remember what the station sells when its commodity market is opened, and forget it once the commander leaves
        (Market.json stays on disk after undocking, so the file alone would offer a station they are no longer at)."""
        if event == "Market":
            keys = trade_market.sold_keys(trade_market.read_market_file(_journal_dir()))
            self._market = (str(entry.get("StationName") or station or ""), keys)
        elif event in ("Undocked", "FSDJump", "SupercruiseEntry") or (event == "Location" and not station):
            if self._market is None:
                return
            self._market = None
        else:
            return
        colonisation_window.refresh_market()

    def capi_fleetcarrier(self, data: Any) -> None:
        """Frontier's own list of what is in the fleet carrier's cargo hold (EDMC fetches it when signed in, on CarrierStats and
        CarrierBuy, at most every 15 minutes). It replaces the tally built from the transfers this tool saw, which cannot see
        cargo that reached the carrier another way; transfers after it are counted on top as before."""
        cmdr = getattr(data, "request_cmdr", None)
        cargo = data.get("cargo") if hasattr(data, "get") else None
        if not cmdr or not isinstance(cargo, list):
            return
        try:
            if self._carrier_cargo.apply_capi_cargo(cmdr, cargo):
                self._carrier_cargo.commit()
        except Exception:
            logger.exception("Could not read the fleet carrier cargo from the CAPI")

    # --- overlay card ---------------------------------------------------------

    def dashboard_status(self, entry: Dict[str, Any]) -> None:
        """From `Status.json` (about once a second while it changes): which screen is open."""
        focus = entry.get("GuiFocus")
        if focus != self._last_focus:
            self._last_focus = focus
            logger.debug("Colonization overlay: Status GuiFocus is now %r", focus)
        self._visibility.set_focus(focus)
        self._update_overlay()

    def _current_card(self) -> Optional[card.Card]:
        self._visibility.right_panel_anywhere = overlay_right_panel()
        if not self._cmdr or overlay_placement.is_hidden("colonisation"):     # hidden on the Overlay Placement tab
            return None
        if not self._visibility.forced and not (overlay_enabled() and self._visibility.visible):
            return None
        sites = [s for s in self._repository.for_cmdr(self._cmdr) if s.active]
        # Alphabetical at a construction site, grouped by market category elsewhere; at a market, what it does not sell is dimmed.
        grouped = not self._visibility.at_depot
        market_keys = self._market[1] if self._market is not None and grouped else None
        return card.build_card(sites[0] if sites else None, self._cargo, self._carrier_cargo.tonnes(self._cmdr),
                               self._carrier_cargo.has_carrier(self._cmdr), self._capacity, overlay_rows(), grouped, market_keys)

    def _update_overlay(self) -> None:
        """Redraw the shopping-list card if its content or position changed, or it is due a re-send before its time to
        live runs out; clear it when disabled, out of view, or nothing is left to get. Cheap enough to call on every
        event."""
        shown = self._current_card()
        reason = (f"{'show' if shown else 'hide'}: enabled={overlay_enabled()} cmdr={bool(self._cmdr)} "
                  f"{self._visibility.describe()}")
        if reason != self._last_reason:
            self._last_reason = reason
            logger.debug("Colonization overlay %s", reason)
        look = overlay_appearance.current_look()
        position = overlay_shift(shown, look) if shown is not None else self._overlay_pos
        now = time.monotonic()
        if (shown == self._overlay_sent and position == self._overlay_pos and look == self._overlay_look
                and (shown is None or now - self._overlay_sent_at < card.RESEND_AFTER_S)):
            return
        previous, old_pos = self._overlay_sent, self._overlay_pos
        self._overlay_sent, self._overlay_pos, self._overlay_sent_at, self._overlay_look = shown, position, now, look
        if shown is None and previous is None:
            return
        previous_slots = previous.slot_count if previous is not None else 0

        def worker() -> None:
            with self._overlay_lock:
                try:
                    if old_pos != position and previous is not None:
                        card.clear(overlay_layout.ShiftedClient(self._overlay_client, *old_pos),
                                   card.DEFAULT_X, card.DEFAULT_Y, previous_slots)
                        previous_slots_now = 0
                    else:
                        previous_slots_now = previous_slots
                    placed = overlay_layout.ShiftedClient(self._overlay_client, *position)
                    if shown is None:
                        card.clear(placed, card.DEFAULT_X, card.DEFAULT_Y, previous_slots)
                    else:
                        card.render(placed, shown, card.DEFAULT_X, card.DEFAULT_Y, previous_slots_now, look)
                    logger.debug("Colonization overlay sent (%s)", "card" if shown else "clear")
                except OSError:
                    logger.debug("Could not reach the overlay for the colonization shopping list", exc_info=True)

        threading.Thread(target=worker, name="WNTB-colonisation-overlay", daemon=True).start()

    def stop(self) -> None:
        """Synchronous clear at shutdown (EDMC does not wait for background threads)."""
        try:
            if self._overlay_sent is not None:
                card.clear(overlay_layout.ShiftedClient(self._overlay_client, *self._overlay_pos),
                           card.DEFAULT_X, card.DEFAULT_Y, self._overlay_sent.slot_count)
        except OSError:
            logger.debug("Could not reach the overlay to clear on shutdown", exc_info=True)
        self._overlay_sent = None

    # --- the page ---------------------------------------------------------------

    def _set(self, name: str, text: str, show: bool = True) -> None:
        """Set a value cell, and show or hide its whole row (a row that does not apply to this commander is not drawn)."""
        var = self._vars.get(name)
        if var is None:
            return
        var.set(text)
        caption, value = self._rows[name]
        (caption.grid if show else caption.grid_remove)()
        (value.grid if show else value.grid_remove)()

    def _draw_bar(self, fraction: float, done: bool) -> None:
        if self._bar is None:
            return
        bar = self._bar
        bar.delete("all")
        track = _BAR_TRACK_DARK if panelkit.is_dark_theme() else _BAR_TRACK_LIGHT
        bar.create_rectangle(0, 0, _BAR_WIDTH, _BAR_HEIGHT, fill=track, outline="")
        width = int(round(_BAR_WIDTH * max(0.0, min(1.0, fraction))))
        if width:
            bar.create_rectangle(0, 0, width, _BAR_HEIGHT, fill=_BAR_DONE if done else _BAR_FILL, outline="")

    def _refresh_summary(self) -> None:
        """Fill the page from the saved sites, the ship's hold and capacity, the carrier and the delivery history."""
        if not self._vars:
            return
        if not self._cmdr:
            self._set("project", _NO_CMDR_TEXT)
            self._draw_bar(0, False)
            for name in ("progress", "delivered", "needed", "coverage", "hold", "carrier", "to_get", "trips", "gaps", "next", "more"):
                self._set(name, "", show=False)
            self._refresh_history(stats.history_for([], {}))
            return
        sites = self._repository.for_cmdr(self._cmdr)
        active = [s for s in sites if s.active]
        has_carrier = self._carrier_cargo.has_carrier(self._cmdr)
        if not active:
            self._set("project", "No active construction site. Dock at one to register it.")
            self._draw_bar(0, False)
            for name in ("progress", "delivered", "needed", "coverage", "hold", "carrier", "to_get", "trips", "gaps", "next", "more"):
                self._set(name, "", show=False)
        else:
            current = active[0]
            p = stats.project_for(current, self._cargo, self._carrier_cargo.tonnes(self._cmdr), has_carrier, self._capacity,
                                  more_active=len(active) - 1)
            where = f"{_clip(p.name, _NAME_MAX)}" + (f"\n{_clip(p.system, _NAME_MAX)}" if p.system else "")
            self._set("project", where)
            self._draw_bar(p.progress, p.complete)
            self._set("progress", f"{p.progress:.0%} complete")
            self._set("delivered", f"{p.delivered:,} of {p.required:,} t")
            self._set("needed", f"{p.remaining:,} t")
            self._set("coverage", stats.coverage_text(p))
            self._set("hold", f"{p.in_hold:,} t in your ship")
            self._set("carrier", f"{p.on_carrier:,} t moved onto your carrier", show=p.has_carrier)
            self._set("to_get", f"{p.to_get:,} t")
            self._set("trips", stats.trips_text(p))
            self._set("gaps", ", ".join(f"{_clip(label, 22)} {tons:,}" for label, tons in p.gaps) or "None", show=bool(p.gaps))
            self._set("next", stats.next_step(p))
            self._set("more", f"+{p.more_active} more active {'site' if p.more_active == 1 else 'sites'}", show=p.more_active > 0)
        self._refresh_history(stats.history_for(sites, self._ledger.record(self._cmdr)))

    def _refresh_history(self, h: "stats.History") -> None:
        self._set("h_sites", stats.sites_text(h))
        has = h.deliveries > 0
        self._set("h_tonnes", f"{h.tonnes:,} t in {h.deliveries:,} {'delivery' if h.deliveries == 1 else 'deliveries'}"
                  if has else "None counted yet")
        self._set("h_recent", f"{h.last_7_days:,} t this week · {h.last_30_days:,} t this month", show=has)
        chart = stats.chart_text(h.daily)
        self._set("h_chart", f"{chart}  (peak {max(h.daily):,} t a day)" if chart else "", show=bool(chart))
        self._set("h_busiest", f"{h.busiest_day[1]:,} t on {h.busiest_day[0]}" if h.busiest_day else "", show=bool(h.busiest_day))
        self._set("h_site", f"{_clip(h.top_site[0], 30)} ({h.top_site[1]:,} t)" if h.top_site else "", show=bool(h.top_site))
        claims = stats.claims_text(h)
        self._set("h_claims", claims, show=bool(claims))
        self._set("h_top", ", ".join(f"{_clip(label, 22)} {tons:,}" for label, tons in h.top_commodities),
                  show=bool(h.top_commodities))
        self._set("h_average", stats.average_text(h.average_days), show=h.average_days is not None)
        self._set("h_since", f"Counted since {h.since}", show=bool(h.since))

    # --- main-panel widgets -----------------------------------------------

    def build_panel(self, parent: tk.Frame) -> None:
        self._parent = parent
        parent.columnconfigure(1, weight=1)
        fonts = panelkit.view_fonts()
        row = 0

        def heading(text: str, top: int = 0) -> None:
            nonlocal row
            tk.Label(parent, text=text, font=fonts["bold"]).grid(row=row, column=0, columnspan=3, sticky=tk.W, pady=(top, 0))
            row += 1

        def line(name: str, caption: str, wide: bool = False) -> None:
            """A caption and its value; a `wide` one puts the value on its own line under the caption (long text)."""
            nonlocal row
            self._vars[name] = tk.StringVar()
            cap = tk.Label(parent, text=caption, font=fonts["small"], anchor="w")
            val = panelkit.wrap_label(parent, textvariable=self._vars[name], anchor="w")
            self._rows[name] = (cap, val)
            if wide:
                cap.grid(row=row, column=0, columnspan=3, sticky=tk.W, pady=(2, 0))
                val.grid(row=row + 1, column=0, columnspan=3, sticky=tk.W)
                row += 2
            else:
                cap.grid(row=row, column=0, sticky=tk.NW, padx=(0, 8))
                val.grid(row=row, column=1, columnspan=2, sticky=tk.W)
                row += 1

        heading("Current project")
        self._vars["project"] = tk.StringVar()
        project = panelkit.wrap_label(parent, textvariable=self._vars["project"], anchor="w", font=fonts["bold"])
        project.grid(row=row, column=0, columnspan=3, sticky=tk.W, pady=(2, 0))
        self._rows["project"] = (project, project)
        row += 1
        self._bar = tk.Canvas(parent, width=_BAR_WIDTH, height=_BAR_HEIGHT, highlightthickness=0, bd=0)
        self._bar.grid(row=row, column=0, columnspan=3, sticky=tk.W, pady=(4, 2))
        row += 1
        line("progress", "Progress")
        line("delivered", "Delivered")
        line("needed", "Still needed")
        line("coverage", "Covered")
        line("hold", "On hand")
        line("carrier", "Carrier")
        line("to_get", "Still to get")
        line("trips", "Trips left")
        line("gaps", "Biggest gaps (t)", wide=True)
        line("next", "Next", wide=True)
        line("more", "Others")

        row = panelkit.add_separator(parent, row)
        heading("History")
        line("h_sites", "Sites")
        line("h_tonnes", "You delivered")
        line("h_recent", "Recently")
        line("h_chart", f"Last {stats.CHART_DAYS} days", wide=True)
        line("h_busiest", "Best day")
        line("h_site", "Busiest site", wide=True)
        line("h_claims", "Claims", wide=True)
        line("h_top", "Most delivered (t)", wide=True)
        line("h_average", "Average build")
        line("h_since", "Note")

        buttons = tk.Frame(parent)
        buttons.grid(row=row, column=0, columnspan=3, sticky=tk.W, pady=(6, 0))
        manage_button = tk.Button(buttons, text="REPORT", command=self._on_manage_clicked)
        manage_button.pack(side=tk.LEFT)
        panelkit.add_tooltip(manage_button, "Colonization Sites - open your colonization sites")
        self._show_button = tk.Button(buttons, text="OVERLAY", command=self._on_show_clicked)
        self._show_off_colors = panelkit.capture_toggle_off_colors(self._show_button)
        self._show_button.pack(side=tk.LEFT, padx=(6, 0))
        panelkit.add_tooltip(self._show_button, "Turn the shopping list on the overlay on or off, whatever screen you are on "
                                                "(lit while it is on). It stays as you leave it, even after a restart, and works "
                                                "whether or not the automatic option in Settings is ticked.")
        self._visibility.forced = config.get_bool(_CFG_OVERLAY_FORCED, default=False)
        panelkit.apply_toggle_button_state(self._show_button, self._visibility.forced, self._show_off_colors)
        if self._visibility.forced:
            self._update_overlay()
        self._refresh_summary()
        parent.after(500, self._poll_history_backfill)

    def _on_show_clicked(self) -> None:
        """Manual override of the automatic screens: force the shopping list on the overlay, or let go again."""
        self._visibility.forced = not self._visibility.forced
        config.set(_CFG_OVERLAY_FORCED, self._visibility.forced)
        if self._show_button is not None:
            panelkit.apply_toggle_button_state(self._show_button, self._visibility.forced, self._show_off_colors)
        self._update_overlay()

    def _on_manage_clicked(self) -> None:
        if self._parent is None:
            return
        colonisation_window.show(self._parent, self._repository, self._cmdr or "", self._cargo, self._carrier_cargo,
                               lambda: self._capacity, lambda: self._system, lambda: self._market)

    # --- Settings tab --------------------------------------------------

    def build_settings(self, notebook: nb.Notebook) -> None:
        frame = nb.Frame(notebook)
        frame.columnconfigure(0, weight=1)
        notebook.add(frame, text="Colonization")

        nb.Label(frame, text="Colonization", font=("TkDefaultFont", 9, "bold")).grid(
            row=0, column=0, sticky=tk.W, padx=10, pady=(10, 4),
        )
        nb.Label(
            frame,
            text=(
                "Tracks what each colonization construction site still needs delivered. Dock at a "
                "construction depot (or open its market) once to register it; deliveries are then "
                "tallied from your journal. Press REPORT in the COL mode to "
                "open the sites window and see each site's outstanding commodities against the cargo you're carrying, and to "
                "copy a shopping list."
            ),
            wraplength=440, justify=tk.LEFT,
        ).grid(row=1, column=0, sticky=tk.W, padx=10, pady=(0, 10))
        nb.Label(
            frame, text="The in-game overlay card for this list is set up on the Overlays tab.",
            wraplength=440, justify=tk.LEFT,
        ).grid(row=2, column=0, sticky=tk.W, padx=10, pady=(0, 10))

        nb.Label(frame, text="Raven Colonial", font=("TkDefaultFont", 9, "bold")).grid(
            row=3, column=0, sticky=tk.W, padx=10, pady=(0, 4))
        nb.Label(
            frame,
            text=("Optional, and everything here is off until you tick the master switch. Shares your construction progress with Raven Colonial (ravencolonial.com), a community "
                  "planning site, as it happens: the site's depot figures and the deliveries you make. It only sends live events, "
                  "needs Raven to already have a project linked to the site, and uses your commander name. If another tool also "
                  "reports your deliveries to Raven, turn one of them off or they are counted twice."),
            wraplength=440, justify=tk.LEFT,
        ).grid(row=4, column=0, sticky=tk.W, padx=10, pady=(0, 4))
        self._rcc_enabled_var = tk.BooleanVar(value=rcc_keys.enabled())
        nb.Checkbutton(frame, text="Allow WNTB to send anything to Raven Colonial (master switch)",
                       variable=self._rcc_enabled_var, command=self._rcc_sync_state).grid(
            row=5, column=0, sticky=tk.W, padx=10, pady=(0, 2))
        self._rcc_progress_var = tk.BooleanVar(value=config.get_bool(_CFG_RCC_PROGRESS, default=False))
        self._rcc_progress_box = nb.Checkbutton(frame, text="Report my construction progress and deliveries to Raven Colonial",
                                                variable=self._rcc_progress_var)
        self._rcc_progress_box.grid(row=6, column=0, sticky=tk.W, padx=(30, 10), pady=(0, 2))
        self._rcc_carrier_var = tk.BooleanVar(value=config.get_bool(_CFG_RCC_CARRIER, default=False))
        self._rcc_carrier_box = nb.Checkbutton(frame, text="Also report cargo I move to and from my fleet carrier (needs the key below)",
                                               variable=self._rcc_carrier_var)
        self._rcc_carrier_box.grid(row=7, column=0, sticky=tk.W, padx=(30, 10), pady=(0, 2))
        key_row = tk.Frame(frame)
        key_row.grid(row=8, column=0, sticky=tk.W, padx=10, pady=(0, 2))
        nb.Label(key_row, text="Raven Colonial key:").pack(side=tk.LEFT)
        self._rcc_key_var = tk.StringVar(value=rcc_keys.keys.get(self._cmdr or ""))
        nb.EntryMenu(key_row, textvariable=self._rcc_key_var, width=34, show="*").pack(side=tk.LEFT, padx=(4, 0))
        nb.Label(
            frame,
            text=(f"Saved for {self._cmdr or 'the current commander'} only, on this computer, and sent only to Raven Colonial. "
                  "Also used by Report Complete to Raven. Leave it empty if you have none; progress and deliveries need no key."),
            wraplength=440, justify=tk.LEFT,
        ).grid(row=9, column=0, sticky=tk.W, padx=10, pady=(0, 10))
        self._rcc_sync_state()

    def _rcc_sync_state(self) -> None:
        """Grey out the two Raven options while the master switch is off (their choices are kept)."""
        state = tk.NORMAL if self._rcc_enabled_var is not None and self._rcc_enabled_var.get() else tk.DISABLED
        for box in (self._rcc_progress_box, self._rcc_carrier_box):
            if box is not None:
                try:
                    box.configure(state=state)
                except tk.TclError:
                    pass

    def build_overlay_settings(self, notebook: nb.Notebook) -> None:
        """The shopping-list card's options, on the Overlays tab."""
        frame = nb.Frame(notebook)
        frame.columnconfigure(0, weight=1)
        notebook.add(frame, text="Colonization")

        self._overlay_enabled_var = tk.BooleanVar(value=overlay_enabled())
        nb.Checkbutton(
            frame, text="Also show the shopping list automatically (markets, carrier inventory, construction sites)",
            variable=self._overlay_enabled_var,
        ).grid(row=2, column=0, sticky=tk.W, padx=10, pady=(10, 2))
        nb.Label(
            frame,
            text=(
                "Leave this off to switch the overlay on and off only with the OVERLAY button on the COL page; the button works "
                "either way. When ticked, the card also appears by itself in a commodity market, the carrier inventory, or docked at a "
                "construction site. "
                "A table for your most recently updated active site: what it still needs, what is in your ship's hold "
                "(a tick when it is covered), and, if you have a fleet carrier, what you have moved onto it."
            ),
            wraplength=440, justify=tk.LEFT,
        ).grid(row=3, column=0, sticky=tk.W, padx=10, pady=(0, 6))

        self._right_panel_var = tk.BooleanVar(value=overlay_right_panel())
        nb.Checkbutton(
            frame, text="Also show whenever the right-hand cockpit panel is open, anywhere",
            variable=self._right_panel_var,
        ).grid(row=4, column=0, sticky=tk.W, padx=10, pady=(0, 6))

        self._overlay_vars = {"rows": tk.StringVar(value=str(overlay_rows()))}
        position = tk.Frame(frame)
        position.grid(row=5, column=0, sticky=tk.W, padx=10, pady=(0, 2))
        nb.Label(position, text="Rows:").pack(side=tk.LEFT)
        nb.EntryMenu(position, textvariable=self._overlay_vars["rows"], width=4).pack(side=tk.LEFT, padx=(4, 0))
        nb.Label(
            frame,
            text=(f"Rows limits how many commodities are listed (1-{card.MAX_ROWS}, the rest are summarized); 0 lists "
                  "them all. Where the card sits on the screen is set on the Overlay Placement tab."),
            wraplength=440, justify=tk.LEFT,
        ).grid(row=6, column=0, sticky=tk.W, padx=10, pady=(0, 6))

        action_row = tk.Frame(frame)
        action_row.grid(row=7, column=0, sticky=tk.W, padx=10, pady=(0, 10))
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
        sample = card.preview_card()
        look = overlay_appearance.current_look()
        placed = overlay_layout.ShiftedClient(client, *overlay_shift(sample, look))
        x, y = card.DEFAULT_X, card.DEFAULT_Y

        def worker() -> None:
            try:
                slots = card.render(placed, sample, x, y, look=look)
                time.sleep(8)
                card.clear(placed, x, y, slots)
                outcome, color = "Sent — check your overlay.", "#2e7d32"
            except OSError as err:
                outcome, color = f"Could not reach the overlay at {cfg.host}:{cfg.port} ({err}).", "#c07000"
            try:
                label.after(0, lambda: label.configure(text=outcome, foreground=color))
            except tk.TclError:
                pass

        threading.Thread(target=worker, name="WNTB-colonisation-overlay-test", daemon=True).start()

    def save_settings(self) -> None:
        if self._rcc_enabled_var is not None:
            config.set(rcc_keys.CFG_ENABLED, self._rcc_enabled_var.get())
        if self._rcc_progress_var is not None:
            config.set(_CFG_RCC_PROGRESS, self._rcc_progress_var.get())
            config.set(_CFG_RCC_CARRIER, self._rcc_carrier_var.get() if self._rcc_carrier_var is not None else False)
            if self._rcc_key_var is not None and self._cmdr:
                rcc_keys.keys.set(self._cmdr, self._rcc_key_var.get())
        if self._overlay_enabled_var is None:
            return
        config.set(_CFG_OVERLAY_ENABLED, self._overlay_enabled_var.get())
        if self._right_panel_var is not None:
            config.set(_CFG_OVERLAY_RIGHT_PANEL, self._right_panel_var.get())
        for key, cfg_key, low, high in (("rows", _CFG_OVERLAY_ROWS, card.MIN_ROWS, card.MAX_ROWS),):
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


def build_overlay_settings(notebook: nb.Notebook) -> None:
    controller.build_overlay_settings(notebook)


def save_settings() -> None:
    controller.save_settings()


def set_overlay_client(client: overlay.OverlayClient) -> None:
    controller.set_overlay_client(client)


def capi_fleetcarrier(data: Any) -> None:
    controller.capi_fleetcarrier(data)


def dashboard_status(entry: Dict[str, Any]) -> None:
    controller.dashboard_status(entry)


def stop() -> None:
    controller.stop()
