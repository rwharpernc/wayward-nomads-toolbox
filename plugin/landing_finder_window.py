"""The Nearest place to land window: the closest stations that can take your ship and give you what you need, and the fleet carriers that let anyone dock.

It starts from the position the journal last gave and the pad your ship needs, so in deep space the answer is one press away. Pick what you need (fuel, repairs, rearming, outfitting), whether fleet carriers should be
listed and how fresh their records must be, tick that the lookup may go online, and press **Find**. Stations are listed nearest first with the pads and the wanted services; carriers are listed only when Spansh says
docking is open to everyone, with how long ago it last had a report of each (carriers jump and change access, so an old record is a guess). Double-click a row to copy its system name for the galaxy map.

The only thing that goes online is the search: your position (three numbers), the pad size, the services and the carrier freshness, to Spansh, when you press Find (`landing_finder.py`). It does not run until the box saying so is ticked
and never on its own. Built on the shared window kit (plugin/uikit); the lookup runs on a worker thread and the result is picked up by an after() poll, so no widget is touched off the main thread. `find_places` is a module-level
name so tests can replace it."""
from __future__ import annotations

import logging
import os
import queue
import threading
import tkinter as tk
from typing import Any, Dict, List, Optional, Tuple

from config import appname, config

from . import landing_finder, panelkit
from .uikit import palette as P
from .uikit import style
from .uikit.shell import WindowShell
from .uikit.table import Column, DataTable
from .uikit.widgets import Combobox, FlatButton, clip

plugin_name = os.path.basename(os.path.dirname(__file__))
logger = logging.getLogger(f"{appname}.{plugin_name}")

CONFIG_GEOMETRY = "wntb_landing_finder_window_geometry"
CONFIG_ALLOWED = "wntb_landing_finder_allowed"
CONFIG_SERVICES = "wntb_landing_finder_services"
CONFIG_PAD = "wntb_landing_finder_pad"
CONFIG_CARRIERS = "wntb_landing_finder_carriers"
CONFIG_FRESH = "wntb_landing_finder_fresh_days"
DEFAULT_SIZE = (1040, 700)
MIN_SIZE = (820, 520)
POLL_MS = 200

PAD_LABELS: Tuple[Tuple[str, str], ...] = ((landing_finder.PAD_AUTO, "My ship's pad"), (landing_finder.PAD_ANY, "Any size"),
                                           (landing_finder.PAD_MEDIUM, "Medium or larger"), (landing_finder.PAD_LARGE, "Large only"))

find_places = landing_finder.find

_window: Optional["LandingFinderWindow"] = None

_STATION_COLUMNS = (
    Column("name", "Station", 200, stretch=True, max_chars=40),
    Column("system", "System", 190, max_chars=34),
    Column("where", "Where", 250, stretch=True, max_chars=52),
    Column("distance", "Distance (ly)", 105, anchor="e"),
    Column("pads", "Pads", 90),
    Column("services", "Has", 150, max_chars=34),
)
_CARRIER_COLUMNS = (
    Column("name", "Carrier", 110),
    Column("system", "System", 230, stretch=True, max_chars=40),
    Column("distance", "Distance (ly)", 105, anchor="e"),
    Column("pads", "Pads", 90),
    Column("services", "Has", 190, max_chars=40),
    Column("age", "Last reported", 120),
)


def show(parent: tk.Misc, ctx: Any) -> None:
    """Open the window, or raise it if it is open. `ctx` says where the commander is: `position()`, `system()` and `ship()`."""
    global _window
    if _window is not None and _window.alive:
        _window.refresh()
        _window.lift()
        return
    _window = LandingFinderWindow(parent, ctx)


def refresh() -> None:
    if _window is not None and _window.alive:
        _window.refresh()


def close() -> None:
    if _window is not None and _window.alive:
        _window.close()


def saved_services() -> List[str]:
    raw = config.get_str(CONFIG_SERVICES)
    if not raw:
        return list(landing_finder.DEFAULT_SERVICES)
    return [name for name in raw.split(",") if name in landing_finder.SERVICES]


def position_text(position: Optional[Tuple[float, float, float]], system: str) -> str:
    """The origin line: the system and the coordinates, or that no position is known yet."""
    if position is None:
        return "Your position is not known yet. Jump to a system or log in first."
    x, y, z = position
    where = f"{system} " if system else ""
    return f"{where}({x:,.1f}, {y:,.1f}, {z:,.1f})"


class LandingFinderWindow:
    def __init__(self, parent: tk.Misc, ctx: Any) -> None:
        self._ctx = ctx
        self._busy = False
        self._results: "queue.Queue[Tuple[str, Any]]" = queue.Queue()
        self._shown: Dict[str, landing_finder.Place] = {}

        self._shell = WindowShell(
            parent, "Nearest place to land", "", size=DEFAULT_SIZE, min_size=MIN_SIZE,
            load_geometry=lambda: config.get_str(CONFIG_GEOMETRY) or "",
            save_geometry=lambda geometry: config.set(CONFIG_GEOMETRY, geometry))
        self._shell.window.protocol("WM_DELETE_WINDOW", self.close)
        body = self._shell.body

        origin = tk.Frame(body, bg=P.BG)
        origin.pack(fill="x", pady=(0, P.PAD_SM))
        tk.Label(origin, text="From", fg=P.MUTED, bg=P.BG).pack(side="left")
        self._from = tk.Label(origin, text="", fg=P.TEXT, bg=P.BG, anchor="w")
        self._from.pack(side="left", padx=(P.PAD_SM, 0))

        needs = tk.Frame(body, bg=P.BG)
        needs.pack(fill="x", pady=(0, P.PAD_SM))
        tk.Label(needs, text="I need", fg=P.MUTED, bg=P.BG).pack(side="left")
        chosen = set(saved_services())
        self._service_vars: Dict[str, tk.BooleanVar] = {}
        for name in landing_finder.SERVICES:
            var = tk.BooleanVar(value=name in chosen)
            self._service_vars[name] = var
            tk.Checkbutton(needs, text=landing_finder.SERVICE_LABELS[name], variable=var).pack(side="left", padx=(P.PAD_SM, 0))

        options = tk.Frame(body, bg=P.BG)
        options.pack(fill="x", pady=(0, P.PAD_SM))
        tk.Label(options, text="Landing pad", fg=P.MUTED, bg=P.BG).pack(side="left")
        self._pad = tk.StringVar(value=dict(PAD_LABELS).get(config.get_str(CONFIG_PAD) or landing_finder.PAD_AUTO, PAD_LABELS[0][1]))
        Combobox(options, textvariable=self._pad, values=[label for _, label in PAD_LABELS], state="readonly", width=18).pack(side="left", padx=(P.PAD_SM, P.PAD))
        self._carriers = tk.BooleanVar(value=config.get_bool(CONFIG_CARRIERS, default=True))
        tk.Checkbutton(options, text="Include fleet carriers open to all, updated within", variable=self._carriers).pack(side="left")
        saved_days = config.get_str(CONFIG_FRESH)
        days = int(saved_days) if saved_days and saved_days.isdigit() and int(saved_days) in landing_finder.FRESH_CHOICES else landing_finder.DEFAULT_FRESH_DAYS
        self._fresh = tk.StringVar(value=f"{days} days")
        Combobox(options, textvariable=self._fresh, values=[f"{d} days" for d in landing_finder.FRESH_CHOICES], state="readonly", width=9).pack(side="left", padx=(P.PAD_SM, 0))

        ask = tk.Frame(body, bg=P.BG)
        ask.pack(fill="x", pady=(0, P.PAD_SM))
        self._allowed = tk.BooleanVar(value=config.get_bool(CONFIG_ALLOWED, default=False))
        tk.Checkbutton(ask, text="Allow this lookup: pressing Find sends Spansh my position, the pad size and these choices, nothing else", variable=self._allowed,
                       command=self._save_choices).pack(side="left")
        self._find_button = FlatButton(ask, "Find", self._find, kind="accent")
        self._find_button.pack(side="right")

        self._station_heading = tk.Label(body, text="", fg=P.MUTED, bg=P.BG, anchor="w", font=style.font(P.FONT_BOLD))
        self._station_heading.pack(fill="x")
        self._stations = DataTable(body, _STATION_COLUMNS, on_activate=self._copy_system, sortable=False, visible_rows=7,
                                   empty_text="Press Find to look for the nearest station.")
        self._stations.pack(fill="x", pady=(0, P.PAD_SM))
        self._carrier_heading = tk.Label(body, text="", fg=P.MUTED, bg=P.BG, anchor="w", font=style.font(P.FONT_BOLD))
        self._carrier_heading.pack(fill="x")
        self._carrier_table = DataTable(body, _CARRIER_COLUMNS, on_activate=self._copy_system, sortable=False, visible_rows=7,
                                        empty_text="Fleet carriers open to all appear here.")
        self._carrier_table.pack(fill="x", pady=(0, P.PAD_SM))

        self.refresh()

    # --- the window ---------------------------------------------------------------------------------------------------

    @property
    def alive(self) -> bool:
        return self._shell.alive

    def lift(self) -> None:
        self._shell.window.deiconify()
        self._shell.window.lift()

    def close(self) -> None:
        self._save_choices()
        self._shell.close()

    def refresh(self) -> None:
        if not self.alive:
            return
        self._from.configure(text=position_text(self._ctx.position(), self._ctx.system()))
        pad = landing_finder.ship_pad(self._ctx.ship())
        self._shell.set_subtitle(f"Your ship needs a {pad} pad" if pad else "Your ship is not known: no pad restriction unless you choose one")
        if not self._shell._status.cget("text"):
            self._shell.set_status("Fleet carriers move and change who may dock, so check a carrier's age before relying on it. Stations rarely change.")

    def _say(self, text: str) -> None:
        self._shell.set_status(text)

    def _chosen_services(self) -> List[str]:
        return [name for name, var in self._service_vars.items() if var.get()]

    def _chosen_pad(self) -> str:
        return next((key for key, label in PAD_LABELS if label == self._pad.get()), landing_finder.PAD_AUTO)

    def _chosen_days(self) -> int:
        digits = "".join(ch for ch in self._fresh.get() if ch.isdigit())
        return int(digits) if digits and int(digits) in landing_finder.FRESH_CHOICES else landing_finder.DEFAULT_FRESH_DAYS

    def _save_choices(self) -> None:
        try:
            config.set(CONFIG_ALLOWED, bool(self._allowed.get()))
            config.set(CONFIG_SERVICES, ",".join(self._chosen_services()))
            config.set(CONFIG_PAD, self._chosen_pad())
            config.set(CONFIG_CARRIERS, bool(self._carriers.get()))
            config.set(CONFIG_FRESH, str(self._chosen_days()))
        except tk.TclError:
            pass   # the window is going away

    # --- the lookup ---------------------------------------------------------------------------------------------------

    def _find(self) -> None:
        if self._busy:
            return
        self._save_choices()
        if not self._allowed.get():
            self._say("Tick the box above to allow the lookup first: it sends Spansh your position, the pad size and these choices when you press Find.")
            return
        position = self._ctx.position()
        if position is None:
            self._say("Your position is not known yet. Jump to a system or log in first.")
            return
        pad = landing_finder.pad_for(self._chosen_pad(), self._ctx.ship())
        services, carriers, days = self._chosen_services(), bool(self._carriers.get()), self._chosen_days()
        self._busy = True
        self._find_button.set_enabled(False)
        self._say("Asking Spansh for the nearest places to land...")
        threading.Thread(target=self._worker, args=(position, pad, services, carriers, days), daemon=True).start()
        self._shell.window.after(POLL_MS, self._poll)

    def _worker(self, position: Any, pad: Optional[str], services: List[str], carriers: bool, days: int) -> None:
        """Runs off the main thread: it must not touch any Tk widget."""
        try:
            self._results.put(("ok", find_places(position, pad, services, carriers, days)))
        except ValueError as err:
            self._results.put(("refused", str(err)))
        except Exception:
            logger.exception("Nearest place to land lookup failed")
            self._results.put(("failed", "Spansh could not be reached. Check your connection and try again (see the EDMC log)."))

    def _poll(self) -> None:
        """Runs on the main thread via after(): safe to touch widgets."""
        try:
            outcome, payload = self._results.get_nowait()
        except queue.Empty:
            if self.alive and self._busy:
                self._shell.window.after(POLL_MS, self._poll)
            return
        self._busy = False
        if not self.alive:
            return
        self._find_button.set_enabled(True)
        if outcome != "ok":
            self._say(str(payload))
            return
        self._fill(payload)

    def _fill(self, result: landing_finder.Result) -> None:
        self._stations.clear()
        self._carrier_table.clear()
        self._shown = {}
        wanted = result.services
        for number, place in enumerate(result.stations):
            iid = f"s{number}"
            self._shown[iid] = place
            self._stations.insert(iid, (clip(place.name, 40), clip(place.system, 34), clip(landing_finder.describe_place(place), 52),
                                        f"{place.distance_ly:,.1f}", landing_finder.pads_text(place), clip(landing_finder.services_text(place, wanted), 34)))
        for number, place in enumerate(result.carriers):
            iid = f"c{number}"
            self._shown[iid] = place
            self._carrier_table.insert(iid, (place.name, clip(place.system, 40), f"{place.distance_ly:,.1f}", landing_finder.pads_text(place),
                                             clip(landing_finder.services_text(place, wanted), 40), landing_finder.age_text(place.updated)))
        need = f"a {result.pad} pad or larger" if result.pad else "any pad"
        self._station_heading.configure(text=f"Stations with {need}")
        if result.carriers_asked:
            self._carrier_heading.configure(text=f"Fleet carriers open to all, reported within {result.fresh_days} days")
        else:
            self._carrier_heading.configure(text="Fleet carriers were not asked for")
        found = len(result.stations) + len(result.carriers)
        if not found:
            self._say("Nothing found with those needs. Untick a service, allow any pad size, or allow older carrier records.")
        else:
            nearest = result.stations[0] if result.stations else None
            tip = f" The nearest station is {nearest.distance_ly:,.0f} ly away." if nearest else ""
            self._say(f"{len(result.stations)} station(s) and {len(result.carriers)} carrier(s) found.{tip} Double-click a row to copy its system name.")

    def _copy_system(self, iid: str) -> None:
        place = self._shown.get(iid)
        if place is not None:
            ok = panelkit.copy_to_clipboard(self._shell.window, place.system)
            self._say(f"Copied {place.system}." if ok else "Could not reach the clipboard.")
