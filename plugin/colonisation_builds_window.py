"""The "Planned Builds" window: the build sites Raven Colonial knows in one system, opened from the Colonization Sites window.

The journal only reports a construction site once you dock at it, so a build that is merely planned is invisible to WNTB. This
shows what the community site has for the system (planned, being built, complete), marks the ones WNTB is also tracking, and
sizes each planned or building site from the bundled cost table (build_costs.py), so a plan can be costed before any depot is
visited.
Nothing is fetched until the window is opened or Refresh is pressed; only the system's name is sent (see rcc_client.py). The
subtitle also names the system's architect and whether Raven Colonial has it open or locked.

Built on the shared window kit (plugin/uikit); a worker thread does the one request and the Tk thread polls for its answer.
"""
from __future__ import annotations

import logging
import os
import threading
import tkinter as tk
from typing import Any, Callable, Dict, FrozenSet, List, Optional

from config import appname, config

from . import build_costs, rcc_client
from .uikit import palette as P
from .uikit.shell import WindowShell
from .uikit.table import Column, DataTable

plugin_name = os.path.basename(os.path.dirname(__file__))
logger = logging.getLogger(f"{appname}.{plugin_name}")

CONFIG_GEOMETRY = "wntb_colonisation_builds_window_geometry"
MIN_WIDTH = 620
MIN_HEIGHT = 360
DEFAULT_SIZE = (700, 480)
_POLL_MS = 150
_SYSTEM_MAX = 60

_COLUMNS = (
    Column("name", "Site", 260, stretch=True, max_chars=40),
    Column("status", "Status", 90, max_chars=12),
    Column("type", "Type", 180, max_chars=30),
    Column("body", "Body", 60, anchor="e", max_chars=8),
    Column("cost", "Full cost", 90, anchor="e", max_chars=12),
    Column("tracked", "In WNTB", 80, anchor="center", max_chars=8),
)
_NOTE = ("Planned builds come from Raven Colonial (ravencolonial.com), a community site; your journal never reports a build that "
         "is only planned. Only the system's name was sent. \"In WNTB\" marks a site you have docked at. \"Full cost\" is the tons the "
         "whole build needs, from a table bundled with WNTB that the game can outdate; click a row for its biggest commodities.")
_COSTED = (rcc_client.STATUS_PLANNED, rcc_client.STATUS_BUILDING)   # a finished build's cost is no longer of interest

_window: Optional["BuildsWindow"] = None


def show(parent: tk.Misc, system: str, tracked: Callable[[], FrozenSet[int]],
         fetch: Optional[Callable[[str], rcc_client.RccSystem]] = None) -> None:
    """Open the window for `system`, or raise it (showing that system) if it is already open. `tracked` gives the market ids of
    the sites WNTB is tracking for the commander."""
    global _window
    if _window is not None and _window.alive:
        _window.set_system(system)
        _window.lift()
        return
    _window = BuildsWindow(parent, system, tracked, fetch or rcc_client.fetch_system)


def close() -> None:
    if _window is not None and _window.alive:
        _window.close()


class BuildsWindow:
    def __init__(self, parent: tk.Misc, system: str, tracked: Callable[[], FrozenSet[int]],
                 fetch: Callable[[str], rcc_client.RccSystem]) -> None:
        self._tracked = tracked
        self._fetch = fetch
        self._system = ""
        self._request_id = 0
        self._sites: Dict[str, rcc_client.RccSite] = {}      # row id -> the site it shows
        self._shell = WindowShell(
            parent, "Planned Builds", "", size=DEFAULT_SIZE, min_size=(MIN_WIDTH, MIN_HEIGHT),
            load_geometry=lambda: config.get_str(CONFIG_GEOMETRY) or "",
            save_geometry=lambda geometry: config.set(CONFIG_GEOMETRY, geometry))
        self._shell.window.protocol("WM_DELETE_WINDOW", self.close)
        self._shell.add_action("Refresh", self.refresh, accent=True)
        self._table = DataTable(self._shell.body, _COLUMNS, sortable=False, on_select=self._on_pick,
                                empty_text="Nothing to show yet.")
        self._table.tag_configure(rcc_client.STATUS_BUILDING, foreground=P.ACCENT)
        self._table.tag_configure(rcc_client.STATUS_PLANNED, foreground=P.INFO)
        self._table.tag_configure(rcc_client.STATUS_DEMOLISH, foreground=P.MUTED)
        self._table.pack(fill="both", expand=True, pady=(0, P.PAD_SM))
        self._shell.set_status(_NOTE)
        self.set_system(system)

    @property
    def alive(self) -> bool:
        return self._shell.alive

    def lift(self) -> None:
        self._shell.window.deiconify()
        self._shell.window.lift()

    def set_system(self, system: str) -> None:
        self._system = (system or "").strip()
        self.refresh()

    def refresh(self) -> None:
        """Ask for the system's sites on a worker thread and poll for the answer; an older answer is dropped."""
        if not self.alive:
            return
        self._request_id += 1
        job: Dict[str, Any] = {"id": self._request_id, "done": False, "system": None, "error": ""}
        system = self._system
        label = system[:_SYSTEM_MAX] + ("…" if len(system) > _SYSTEM_MAX else "")
        self._shell.set_subtitle(f"{label or 'No system'} - asking Raven Colonial…")
        self._table.clear()
        self._sites.clear()

        def work() -> None:
            try:
                job["system"] = self._fetch(system)
            except rcc_client.RccError as err:
                job["error"] = str(err)
            except Exception:    # a bug or something unforeseen: shown plainly, never raised into the Tk thread
                logger.exception("Raven Colonial lookup failed")
                job["error"] = "The lookup failed unexpectedly; see the EDMC log."
            job["done"] = True

        threading.Thread(target=work, daemon=True, name="WNTB-rcc-sites").start()
        self._shell.window.after(_POLL_MS, self._poll, job, label)

    def _poll(self, job: Dict[str, Any], label: str) -> None:
        if not self.alive or job["id"] != self._request_id:
            return
        if not job["done"]:
            self._shell.window.after(_POLL_MS, self._poll, job, label)
            return
        if job["error"]:
            self._shell.set_subtitle(f"{label} - not available")
            self._shell.set_status(job["error"])
            return
        plan: rcc_client.RccSystem = job["system"]
        sites: List[rcc_client.RccSite] = plan.sites
        summary = rcc_client.summary_text(sites)
        if not summary:
            self._shell.set_subtitle(f"{label} - Raven Colonial has no sites for it")
        else:
            facts = [summary]
            if plan.architect:
                facts.append(f"architect {plan.architect}")
            if plan.access_label:
                facts.append(plan.access_label.lower())
            planned_t = sum(c.total for c in (build_costs.cost_for(s.build_type) for s in sites if s.status == rcc_client.STATUS_PLANNED) if c)
            if planned_t:
                facts.append(f"planned builds need {planned_t:,} t")
            self._shell.set_subtitle(f"{label} - " + " · ".join(facts))
        self._shell.set_status(_NOTE)
        tracked = self._tracked()
        self._table.clear()
        self._sites.clear()
        for index, site in enumerate(sites):
            cost = build_costs.cost_for(site.build_type)
            self._sites[f"s{index}"] = site
            self._table.insert(
                f"s{index}", (site.name, site.status_label, cost.name if cost else site.type_label,
                              str(site.body_num) if site.body_num is not None else "",
                              f"{cost.total:,} t" if cost and site.status in _COSTED else "",
                              "yes" if site.market_id is not None and site.market_id in tracked else ""),
                tag=site.status or None)

    def _on_pick(self, iid: str) -> None:
        """Click a row: its building, layout and biggest commodities in the footer (or the usual note when the cost is not known)."""
        site = self._sites.get(iid)
        cost = build_costs.cost_for(site.build_type) if site else None
        if site is None or cost is None:
            self._shell.set_status(_NOTE)
            return
        biggest = ", ".join(f"{name} {tons:,}" for name, tons in cost.biggest(5))
        layout = f" ({site.type_label})" if site.type_label and site.type_label.casefold() != cost.name.casefold() else ""
        self._shell.set_status(f"{site.name}: {cost.name}{layout}, {cost.total:,} t in all. Biggest: {biggest}.")

    def close(self) -> None:
        self._request_id += 1      # an answer still on its way has nowhere to show
        self._shell.close()
