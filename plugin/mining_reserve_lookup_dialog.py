"""
"Check Ring Reserve Level" dialog (Space Mining page) - queries EDSM for a
ring's reserve level and composition type, and flags a non-Metallic ring
as a laser-mining caution. Opt-in via the "Enable EDSM Ring Reserve
Lookup" setting (see mining_panel.py); the network call lives in the
shared `edsm_client.py` (`system_bodies()`), kept separate so this
module only owns the Tk form/threading/results side plus the Mining-
specific `BodyInfo`/`RingInfo` parsing of that raw response - same split
as mining_hotspot_finder_dialog.py/mining_spansh_client.py.

An on-demand lookup (type a body/ring name, see its reserve level and
type) - the passive counterpart lives in mining_render.py's ring-caution
display, fed automatically by mining_panel.py on every `SupercruiseExit`
into a ring, via mining_space.py's set_current_ring()/
set_ring_caution(). This dialog still exists for looking up a ring by
name without having to fly there (e.g. planning a next stop) - it
prefills both fields from that same tracked state (mining_location.py's
current system, mining_space.py's current ring) when available, but the
fields stay editable either way.

The search itself is a blocking network call, so it always runs on a
background thread - the Search button disables itself while a search is
in flight, and results/errors are marshaled back via
`dialog.after(0, ...)`.
"""
import logging
import os
import threading
import tkinter as tk
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from config import appname

from . import edsm_client
from . import mining_location as location
from . import mining_space as space_mining
from .uikit import palette
from .uikit import style as ui_style

plugin_name = os.path.basename(os.path.dirname(__file__))
logger = logging.getLogger(f"{appname}.{plugin_name}")

_ERROR_COLOR = palette.DANGER
_WARNING_COLOR = palette.WARN
_MUTED_COLOR = palette.MUTED

METALLIC_RING_TYPES = frozenset({"Metallic"})
"""Community knowledge, not journal/API-documented fact - like
mining_methods.py's commodity table, this needs the same kind of manual
upkeep as the game's ring-composition mechanics evolve. Premium-metal
laser-mining yields are generally best on Metallic rings; Metal Rich,
Rocky and Icy rings are the ones a "non-metallic ring" warning should
flag, hence only "Metallic" itself is excluded here."""


@dataclass
class RingInfo:
    name: str
    ring_type: str

    def is_metallic(self) -> bool:
        return self.ring_type in METALLIC_RING_TYPES


@dataclass
class BodyInfo:
    """One ringed body in a system, parsed from edsm_client.system_bodies()'s
    raw response. `reserve_level` is None for a body EDSM has on file
    without ring reserve data (rare, but the API doesn't guarantee every
    ringed body has it filled in)."""
    name: str
    reserve_level: Optional[str]
    rings: List[RingInfo]


def parse_ringed_bodies(raw_bodies: List[Dict[str, Any]]) -> List[BodyInfo]:
    """Filters `edsm_client.system_bodies()`'s raw list down to bodies
    that actually have rings, parsed into BodyInfo/RingInfo. Kept as
    Mining-specific parsing (not part of the shared edsm_client.py)
    since no other WNTB mode needs this shape. Public (not
    underscore-prefixed): mining_panel.py's automatic ring-reserve
    lookup (`_check_ring_reserve()`) reuses this directly rather than
    duplicating the same parse."""
    bodies: List[BodyInfo] = []
    for body in raw_bodies:
        rings = body.get("rings") or []
        if not rings:
            continue
        bodies.append(BodyInfo(
            name=body.get("name", "?"),
            reserve_level=body.get("reserveLevel"),
            rings=[RingInfo(name=r.get("name", "?"), ring_type=r.get("type", "?")) for r in rings],
        ))
    return bodies


def find_body_or_ring(bodies: List[BodyInfo], name: str) -> Optional[BodyInfo]:
    """Matches `name` case-insensitively against either a body's own name
    or any of its ring names - a commander is as likely to type the ring
    name off their nav panel ("Jupiter Halo Ring") as the body name
    ("Jupiter")."""
    query = name.strip().casefold()
    if not query:
        return None
    for body in bodies:
        if body.name.strip().casefold() == query:
            return body
        if any(ring.name.strip().casefold() == query for ring in body.rings):
            return body
    return None


def open_reserve_lookup_dialog(parent: tk.Misc) -> None:
    reference_system = location.current_system()
    tracked_ring = space_mining.space_mining_repository.current_ring()
    reference_ring = tracked_ring[1] if tracked_ring else ""

    # Parented on parent's *toplevel*, not parent itself - same reasoning
    # as mining_hotspot_dialog.py/mining_hotspot_finder_dialog.py: a
    # Toplevel parented directly on mining_render.py's periodically-
    # rebuilt content frame gets destroyed along with it the next time
    # that fires.
    root = parent.winfo_toplevel()
    dialog = tk.Toplevel(root)
    ui_style.skin(dialog)
    dialog.title("Check Ring Reserve Level")
    dialog.resizable(True, True)
    dialog.transient(root)
    dialog.grab_set()
    dialog.columnconfigure(1, weight=1)

    tk.Label(dialog, text="System*", anchor=tk.W).grid(row=0, column=0, sticky="w", padx=8, pady=(8, 4))
    system_var = tk.StringVar(value=reference_system or "")
    tk.Entry(dialog, textvariable=system_var, width=26).grid(
        row=0, column=1, sticky="ew", padx=8, pady=(8, 4))

    tk.Label(dialog, text="Body or ring name*", anchor=tk.W).grid(
        row=1, column=0, sticky="w", padx=8, pady=4)
    body_var = tk.StringVar(value=reference_ring)
    tk.Entry(dialog, textvariable=body_var, width=26).grid(
        row=1, column=1, sticky="ew", padx=8, pady=4)

    search_button = tk.Button(dialog, text="Search")
    search_button.grid(row=2, column=0, columnspan=2, pady=(2, 4))

    status_label = tk.Label(dialog, text="", anchor=tk.W, justify=tk.LEFT, wraplength=420)
    status_label.grid(row=3, column=0, columnspan=2, sticky="w", padx=8, pady=(0, 8))

    def _show_result(body: BodyInfo) -> None:
        if not dialog.winfo_exists():
            return
        search_button.configure(state=tk.NORMAL)
        ring_lines = []
        any_non_metallic = False
        for ring in body.rings:
            marker = ""
            if not ring.is_metallic():
                marker = " - not Metallic: premium laser-mined yields are typically best on Metallic rings"
                any_non_metallic = True
            ring_lines.append(f"{ring.name}: {ring.ring_type}{marker}")
        reserve_text = body.reserve_level or "Unknown"
        text = f"{body.name} - Reserve level: {reserve_text}\n" + "\n".join(ring_lines)
        status_label.configure(fg=_WARNING_COLOR if any_non_metallic else _MUTED_COLOR, text=text)

    def _show_not_found() -> None:
        if not dialog.winfo_exists():
            return
        search_button.configure(state=tk.NORMAL)
        status_label.configure(
            fg=_MUTED_COLOR,
            text="No ringed body by that name found in EDSM's data for this system.")

    def _show_error(message: str) -> None:
        if not dialog.winfo_exists():
            return
        search_button.configure(state=tk.NORMAL)
        status_label.configure(fg=_ERROR_COLOR, text=message)

    def _on_search() -> None:
        system = system_var.get().strip()
        body_name = body_var.get().strip()
        if not system or not body_name:
            status_label.configure(fg=_ERROR_COLOR, text="Enter both a system and a body/ring name.")
            return

        status_label.configure(fg=_MUTED_COLOR, text="Searching...")
        search_button.configure(state=tk.DISABLED)

        def _worker() -> None:
            raw_bodies = edsm_client.system_bodies(system)
            if raw_bodies is None:
                logger.warning("EDSM reserve lookup failed for %r", system)
                dialog.after(0, lambda: _show_error(
                    "Lookup failed - check your connection and try again (see the EDMC log)."))
                return
            bodies = parse_ringed_bodies(raw_bodies)
            match = find_body_or_ring(bodies, body_name)
            if match is None:
                dialog.after(0, _show_not_found)
                return
            dialog.after(0, lambda: _show_result(match))

        threading.Thread(target=_worker, daemon=True, name="WNTB-mining-edsm-search").start()

    search_button.configure(command=_on_search)

    tk.Button(dialog, text="Close", command=dialog.destroy).grid(
        row=4, column=0, columnspan=2, pady=(4, 8))

    dialog.bind("<Return>", lambda _e: _on_search())
    dialog.bind("<Escape>", lambda _e: dialog.destroy())
