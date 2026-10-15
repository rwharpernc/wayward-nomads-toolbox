"""The "Source commodities" window of the Missions mode: for each commodity your Collect and Mining missions still need, the closest place that has it in stock,
the best nearby, the cheapest anywhere and a recommended one (see `source_picks.py`). Opened from the "Commodities needed" list.

Nothing is looked up until you press **Find sources**, and only when Trade's online-lookups switch is on (it is off by default): that is the only thing here
that goes online, a few Spansh searches per commodity. Pick a row and **Copy system** puts its system name on the clipboard for the galaxy map."""
from __future__ import annotations

import logging
import threading
import tkinter as tk
from typing import Callable, Dict, List, Optional

from . import mission_sources, panelkit, ship_current, source_picks, trade_ship
from .uikit import palette as P
from .uikit.shell import WindowShell
from .uikit.table import Column, DataTable
from .uikit.widgets import Combobox

try:
    from config import appname, config
except ImportError:  # unit tests outside EDMC
    appname, config = "EDMarketConnector", None

logger = logging.getLogger(f"{appname}.wntb.mission_sources")

_CFG_LOOKUPS = "wntb_trade_lookups_enabled"          # Trade's own switch for every Spansh lookup (trade_panel.py)
_CFG_NEAR_RADIUS = "wntb_trade_near_radius_ly"
_CFG_CARRIERS = "wntb_trade_include_carriers"
_CFG_GROUND = "wntb_trade_include_ground"
_CFG_SHIP_PAD = "wntb_trade_ship_pad_override"
_CFG_GEOMETRY = "wntb_mission_sources_geometry"
_DEFAULT_RADIUS = 100
_MODES = {"From where I am": mission_sources.HERE, "From the turn-in system": mission_sources.TURN_IN}
_POLL_MS = 400
_COLUMNS = (
    Column("commodity", "Commodity", 150, max_chars=28),
    Column("need", "Need", 70, anchor="e"),
    Column("pick", "Pick", 130),
    Column("station", "Station", 210, stretch=True, max_chars=40),
    Column("system", "System", 170, max_chars=32),
    Column("ly", "ly", 70, anchor="e"),
    Column("price", "cr/t", 80, anchor="e"),
    Column("note", "Note", 190, max_chars=40),
)


def lookups_enabled() -> bool:
    return bool(config and config.get_bool(_CFG_LOOKUPS, default=False))


def _radius() -> float:
    try:
        raw = config.get_str(_CFG_NEAR_RADIUS) if config else ""
        return float(max(1, min(100_000, int(raw)))) if raw else float(_DEFAULT_RADIUS)
    except (ValueError, TypeError):
        return float(_DEFAULT_RADIUS)


def read_options() -> mission_sources.Options:
    """The Trade settings the picks follow: the Near me radius, carriers, ground facilities and the landing pad (the Settings override, else the ship you are in)."""
    pad = ((config.get_str(_CFG_SHIP_PAD) if config else "") or "").strip().lower()
    if pad not in (trade_ship.SMALL, trade_ship.MEDIUM, trade_ship.LARGE):
        loadout = ship_current.latest_loadout() or {}
        pad = trade_ship.pad_size(loadout.get("Ship")) or ""
    return mission_sources.Options(
        radius_ly=_radius(), ship_pad=pad or None,
        include_carriers=bool(config.get_bool(_CFG_CARRIERS, default=True)) if config else True,
        include_ground=bool(config.get_bool(_CFG_GROUND, default=True)) if config else True)


def rows_for(need: mission_sources.Need, picks: Optional[source_picks.Picks]) -> List[List[str]]:
    """The table rows for one commodity: its name and need on the first, then one row per pick found (or why there is none). Each row is
    the eight cells followed by the system name to copy (not shown)."""
    first = [need.commodity, f"{need.tonnes:,} t"]
    if picks is None:
        return [first + ["", "", "", "", "", "", ""]]
    rows: List[List[str]] = []
    for kind in source_picks.KINDS:
        pick = picks.picks.get(kind)
        if pick is None:
            continue
        offer = pick.offer
        lead = first if not rows else ["", ""]
        rows.append(lead + [picks.label(kind), offer.station, offer.system, f"{offer.distance_ly:.0f}", f"{offer.price:,}", pick.note, offer.system])
    if not rows:
        rows.append(first + ["", picks.notes[0] if picks.notes else "Nothing found", "", "", "", "", ""])
    elif picks.notes:
        rows.append(["", "", "", picks.notes[0], "", "", "", "", ""])
    return rows


class MissionSourcesWindow:
    def __init__(self, parent: tk.Misc, needs: Callable[[], List[mission_sources.Need]], here: Callable[[], str]) -> None:
        self._needs, self._here = needs, here
        self._results: Dict[str, source_picks.Picks] = {}
        self._pending: Dict[str, source_picks.Picks] = {}
        self._worker: Optional[threading.Thread] = None
        self._cancel = threading.Event()
        self._error = ""
        self._copyable: Dict[str, str] = {}      # table row id -> the system on that row
        self._selected: Optional[str] = None
        self._shell = WindowShell(
            parent, "WNTB - Source commodities", "Where to get what your missions still need", size=(1100, 520), min_size=(760, 320),
            load_geometry=lambda: (config.get_str(_CFG_GEOMETRY) if config else "") or "",
            save_geometry=lambda value: config.set(_CFG_GEOMETRY, value) if config else None)
        self._shell.window.protocol("WM_DELETE_WINDOW", self.close)
        self._find = self._shell.add_action("Find sources", self._start, accent=True)
        self._shell.add_action("Copy system", self._copy)

        bar = tk.Frame(self._shell.body, bg=P.BG)
        bar.pack(fill="x", pady=(P.PAD_SM, P.PAD_SM))
        self._mode = tk.StringVar(value=next(iter(_MODES)))
        box = Combobox(bar, textvariable=self._mode, values=list(_MODES), state="readonly", width=26)
        box.pack(side="left")
        box.bind("<<ComboboxSelected>>", lambda _e: self._clear_results())
        self._table = DataTable(self._shell.body, _COLUMNS, on_select=self._select, sortable=False,
                                empty_text="Nothing to source: no active Collect or Mining mission still needs cargo.")
        self._table.pack(fill="both", expand=True, pady=(0, P.PAD_SM))
        self.refresh()

    @property
    def alive(self) -> bool:
        return self._shell.alive

    def lift(self) -> None:
        self._shell.window.lift()

    def close(self) -> None:
        self._cancel.set()
        self._shell.close()

    def refresh(self) -> None:
        """Redraw from the current missions and whatever has been found. Safe to call whenever the missions change."""
        if not self.alive:
            return
        needs = self._needs()
        self._table.clear()
        self._copyable, self._selected = {}, None
        count = 0
        for need in needs:
            for row in rows_for(need, self._results.get(need.commodity)):
                iid = f"r{count}"
                count += 1
                self._table.insert(iid, row[:8])
                if row[8:] and row[8]:
                    self._copyable[iid] = row[8]
        if not lookups_enabled():
            self._shell.set_status("Online lookups are off. Turn them on in Settings > Trade to find sources (it asks Spansh, spansh.co.uk).")
        elif self._error:
            self._shell.set_status(self._error)
        elif needs and not self._results and not self._busy():
            self._shell.set_status("Press Find sources. It asks Spansh a few times per commodity, one after another.")

    def _busy(self) -> bool:
        return self._worker is not None and self._worker.is_alive()

    def _clear_results(self) -> None:
        self._results, self._error = {}, ""
        self.refresh()

    def _start(self) -> None:
        if self._busy():
            self._cancel.set()
            return
        if not lookups_enabled():
            self.refresh()
            return
        needs, here = self._needs(), self._here()
        mode = _MODES.get(self._mode.get(), mission_sources.HERE)
        if not needs:
            self.refresh()
            return
        if mode == mission_sources.HERE and not here:
            self._shell.set_status("WNTB does not know your system yet: jump or log in, or choose the turn-in system.")
            return
        options = read_options()
        self._cancel = cancel = threading.Event()
        self._results, self._pending, self._error = {}, {}, ""
        self._find.configure(text="Cancel")
        self._shell.set_status("Asking Spansh...")
        pending = self._pending

        def work() -> None:
            try:
                mission_sources.lookup(needs, mode, here, options, cancelled=cancel.is_set,
                                       on_done=lambda need, picks: pending.__setitem__(need.commodity, picks))
            except Exception:
                logger.exception("Mission source lookup failed")
                self._error = "Lookup failed - check your connection and try again (see the EDMC log)."

        self._worker = threading.Thread(target=work, name="WNTB-mission-sources", daemon=True)
        self._worker.start()
        self._shell.window.after(_POLL_MS, self._poll)

    def _poll(self) -> None:
        if not self.alive:
            return
        self._results.update(self._pending)
        self.refresh()
        if self._busy():
            self._shell.set_status(f"Asking Spansh... {len(self._results)} of {len(self._needs())} done (press Cancel to stop)")
            self._shell.window.after(_POLL_MS, self._poll)
            return
        self._find.configure(text="Find sources")
        self._shell.set_status(self._error or ("Cancelled." if self._cancel.is_set() else
                                               "Done. Pick a row and press Copy system to put its system name on the clipboard."))

    def _select(self, iid: str) -> None:
        self._selected = iid

    def _copy(self) -> None:
        system = self._copyable.get(self._selected or "", "")
        if not system:
            self._shell.set_status("Pick a row with a station first.")
        elif panelkit.copy_to_clipboard(self._shell.window, system):
            self._shell.set_status(f"Copied {system}.")
