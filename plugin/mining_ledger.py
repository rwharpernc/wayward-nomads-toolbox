"""
The Mining Book - Mining mode's three-pane window - bodies on the left,
a body's saved hotspots in the middle, and a detail card with a map on the
right. Built on the shared kit in plugin/uikit (see
docs/WINDOW_FRAMEWORK_SPEC.md).

Singleton, like the other WNTB windows (module-level show/refresh/close,
saved geometry). It lists what this session's journal scan has shown for
the current system plus every saved hotspot, anywhere, so it also replaces
the old "Search Known Hotspots" dialog; the data shaping is in
mining_ledger_data.py (tested), this file is only widgets.

No "Guide me there" button: the waypoint overlay always points at the
nearest saved hotspot on the current body (mining_overlay.py), there is no
per-hotspot target to set.
"""
from __future__ import annotations

import dataclasses
import logging
import os
import tkinter as tk
from tkinter import messagebox
from typing import Optional

from config import appname, config

from . import mining_coverage as coverage
from . import mining_deposit
from . import mining_hotspot_dialog as hotspot_dialog
from . import mining_hotspots as hotspots
from . import mining_live_position as live_position
from . import mining_ground
from . import mining_ledger_data as data
from . import mining_surface as surface_mining
from . import panelkit
from .mining_body_survey import system_body_survey
from .uikit import palette as P
from .uikit import style
from .uikit.mapview import MapMarker, MapView
from .uikit.shell import WindowShell
from .uikit.table import Column, DataTable
from .uikit.widgets import Card, Combobox, FlatButton, FoldList, Pill, StatTile, clip, section_header

plugin_name = os.path.basename(os.path.dirname(__file__))
logger = logging.getLogger(f"{appname}.{plugin_name}")

CONFIG_GEOMETRY = "wntb_mining_ledger_geometry"

_DENSITY_COLORS = {"High": P.OK, "Medium": P.WARN, "Low": P.DANGER}
_AMOUNT_COLORS = {"High": P.OK, "Medium": P.WARN, "Low": P.DANGER, "Depleted": P.MUTED}

_PROSPECT_COLUMNS = (
    Column("material", "Material", 150, stretch=True, max_chars=28),
    Column("pct", "Share", 80, anchor="e"),
    Column("count", "Recorded", 90, anchor="e"),
    Column("saved", "Saved", 60, anchor="center"),
)

_window: Optional["MiningBook"] = None


def show(parent: tk.Misc) -> None:
    """Open the browser, or raise it (and refresh) if it's already open.
    Parented on the main window's toplevel - the panel rebuilds its own
    content frame every second, which would destroy a child of it."""
    global _window
    if _window is not None and _window.alive:
        _window.refresh()
        _window.lift()
        return
    _window = MiningBook(parent.winfo_toplevel())


def close() -> None:
    if _window is not None and _window.alive:
        _window.close()


def _spot_ident(spot: hotspots.Hotspot) -> tuple:
    return (spot.system, spot.body, spot.material, spot.latitude, spot.longitude)


class MiningBook:
    def __init__(self, root: tk.Misc) -> None:
        self._shell = WindowShell(
            root, "Mining Book", "",
            load_geometry=lambda: config.get_str(CONFIG_GEOMETRY) or "",
            save_geometry=lambda geometry: config.set(CONFIG_GEOMETRY, geometry))
        self._shell.window.protocol("WM_DELETE_WINDOW", self.close)
        self._shell.add_action("Add hotspot", self._add_hotspot, accent=True)

        self._body_entry: Optional[data.BodyEntry] = None
        self._entries: dict[str, data.BodyEntry] = {}
        self._spot_by_key: dict[str, hotspots.Hotspot] = {}
        self._selected_spot: Optional[hotspots.Hotspot] = None
        self._rates = mining_ground.OwnRates([])

        panes = tk.PanedWindow(self._shell.body, orient="horizontal", bg=P.BG, bd=0, sashwidth=6, sashrelief="flat", opaqueresize=True)
        panes.pack(fill="both", expand=True, pady=(0, P.PAD_SM))
        self._panes = panes

        left = tk.Frame(panes, bg=P.PANE)
        section_header(left, "Bodies").pack(fill="x")
        filter_row = tk.Frame(left, bg=P.PANE, padx=P.PAD, pady=P.PAD_SM)
        filter_row.pack(fill="x")
        self._material = Combobox(filter_row, state="readonly", values=[data.ALL_MATERIALS])
        self._material.current(0)
        self._material.pack(fill="x")
        self._material.bind("<<ComboboxSelected>>", lambda _e: self.refresh())
        self._rigs = Combobox(filter_row, state="readonly", values=[data.ANY_RIGS])
        self._rigs.current(0)
        self._rigs.pack(fill="x", pady=(P.PAD_SM, 0))
        self._rigs.bind("<<ComboboxSelected>>", lambda _e: self.refresh())
        self._bodies = FoldList(left, on_select=self._select_body)
        self._bodies.pack(fill="both", expand=True)
        panes.add(left, stretch="always", minsize=220)

        middle = tk.Frame(panes, bg=P.PANE)
        self._middle_title = section_header(middle, "Hotspots")
        self._middle_title.pack(fill="x")
        tiles = tk.Frame(middle, bg=P.PANE, padx=P.PAD, pady=P.PAD_SM)
        tiles.pack(fill="x")
        self._tile_saved = StatTile(tiles, "0", "hotspots")
        self._tile_mined = StatTile(tiles, "0 t", "mined here", P.ACCENT)
        self._tile_active = StatTile(tiles, "0", "not depleted", P.OK)
        for tile in (self._tile_saved, self._tile_mined, self._tile_active):
            tile.pack(side="left", padx=(0, 6))
        self._materials = tk.Label(middle, text="", bg=P.PANE, fg=P.MUTED, anchor="w", justify="left",
                                   padx=P.PAD)
        self._materials.pack(fill="x", pady=(0, P.PAD_SM))
        middle.bind("<Configure>", lambda e: self._materials.configure(wraplength=max(e.width - 2 * P.PAD, 120)))
        self._prospect_head = tk.Frame(middle, bg=P.PANE, padx=P.PAD)
        self._prospect_title = tk.Label(self._prospect_head, text="", bg=P.PANE, fg=P.MUTED, anchor="w",
                                        font=style.font(P.FONT_SMALL))
        self._prospect_title.pack(side="left")
        self._prospect_table = DataTable(middle, _PROSPECT_COLUMNS, visible_rows=5)
        self._prospect_note = tk.Label(middle, text="", bg=P.PANE, fg=P.FAINT, anchor="w", justify="left",
                                       padx=P.PAD, font=style.font(P.FONT_SMALL))
        middle.bind("<Configure>", lambda e: self._prospect_note.configure(wraplength=max(e.width - 2 * P.PAD, 120)), add="+")
        self._hotspots = FoldList(middle, on_select=self._select_spot, single_open=False)
        self._hotspots.pack(fill="both", expand=True)
        panes.add(middle, stretch="always", minsize=220)

        right = tk.Frame(panes, bg=P.PANE, padx=P.PAD, pady=P.PAD)
        self._card = Card(right)
        self._card.pack(fill="x")
        self._map = MapView(right, size=280, on_select=self._select_spot)
        self._map.pack(fill="both", expand=True, pady=(P.PAD, 0))
        panes.add(right, stretch="always", minsize=int(330 * style.dpi_factor(self._shell.window)))

        self._shell.window.after(50, self._set_sashes)
        hotspots.hotspot_repository.add_listener(self._on_repo_changed)
        self.refresh(select_current=True)

    # --- lifecycle ------------------------------------------------------------
    @property
    def alive(self) -> bool:
        return self._shell.alive

    def lift(self) -> None:
        self._shell.window.deiconify()
        self._shell.window.lift()

    def close(self) -> None:
        hotspots.hotspot_repository.remove_listener(self._on_repo_changed)
        self._shell.close()

    def _set_sashes(self) -> None:
        """Initial pane widths (set once the window has its real size)."""
        total = self._panes.winfo_width()
        if total > 600:
            self._panes.sash_place(0, int(total * 0.26), 0)
            self._panes.sash_place(1, int(total * 0.63), 0)

    def _on_repo_changed(self) -> None:
        if self.alive:
            self._shell.window.after_idle(self.refresh)

    # --- data -> widgets -------------------------------------------------------
    def refresh(self, select_current: bool = False) -> None:
        """Re-read everything and redraw, keeping the selected body and
        hotspot where they still exist."""
        if not self.alive:
            return
        saved = hotspots.hotspot_repository.all()
        surface = surface_mining.surface_mining_repository
        current_system = surface.current_system or system_body_survey.current_system
        self._shell.set_subtitle(current_system or "No system yet")

        # Your own rates: rebuilt from the saved hotspots on every refresh
        # (one cheap pass), counting hotspots saved before they carried a
        # ground via this session's scanned bodies.
        surveyed = system_body_survey.landable_bodies()
        self._rates = mining_ground.OwnRates(saved, mining_ground.survey_grounds(surveyed, current_system))

        materials = data.materials_in(saved)
        self._material.configure(values=materials)
        if self._material.get() not in materials:
            self._material.current(0)

        rig_labels = data.rig_labels(saved)
        self._rigs.configure(values=rig_labels)
        if self._rigs.get() not in rig_labels:
            self._rigs.current(0)

        groups = data.build_body_groups(current_system, surveyed, saved,
                                        self._material.get(), data.rigs_from_label(self._rigs.get()), self._rates)
        self._entries = {}
        rows_by_group = []
        for group_key, heading, entries in groups:
            rows = []
            for entry in entries:
                self._entries[entry.key] = entry
                title = entry.short_name if group_key != "other-systems" else f"{entry.system} · {entry.short_name}"
                bits = []
                if entry.rate_pct is not None:
                    bits.append(f"{entry.rate_pct:.0f}% of your recorded deposits here are {self._material.get()}")
                if entry.mining_signal_count is not None:
                    bits.append(f"{entry.mining_signal_count} mining location(s)")
                sub = "  ·  ".join(bits)
                rows.append(dict(key=entry.key, title=title, sub=sub,
                                 pill=(f"{entry.saved_count} saved", P.ACCENT) if entry.saved_count else None))
            rows_by_group.append((group_key, f"{heading}  ({len(entries)})", rows))
        open_before = self._bodies.open_keys()
        self._bodies.populate(rows_by_group, keep_scroll=True)
        for group_key in open_before:
            self._bodies.open_group(group_key)

        wanted = self._body_entry.key if self._body_entry else None
        if select_current or wanted not in self._entries:
            wanted = self._current_body_key(surface) or next(iter(self._entries), None)
        if wanted in self._entries:
            for group_key, _heading, entries in groups:
                if any(e.key == wanted for e in entries):
                    self._bodies.open_group(group_key)
            self._bodies.select(wanted, notify=False)
            self._show_body(self._entries[wanted])
        else:
            self._body_entry = None
            self._show_body(None)

    @staticmethod
    def _current_body_key(surface: surface_mining.SurfaceMiningRepository) -> Optional[str]:
        if surface.current_system and surface.current_body:
            return f"{surface.current_system}|{surface.current_body}"
        return None

    def _select_body(self, key: str) -> None:
        entry = self._entries.get(key)
        if entry is not None:
            self._selected_spot = None
            self._show_body(entry)

    def _show_body(self, entry: Optional[data.BodyEntry]) -> None:
        self._body_entry = entry
        previous = _spot_ident(self._selected_spot) if self._selected_spot else None
        self._selected_spot = None
        self._spot_by_key = {}
        if entry is None:
            self._middle_title.configure(text="HOTSPOTS")
            self._hotspots.populate([])
            for tile, text in ((self._tile_saved, "0"), (self._tile_mined, "0 t"), (self._tile_active, "0")):
                tile.set(text)
            self._draw_materials([])
            self._show_prospecting(False)
            self._map.set_message("Nothing to show yet")
            self._render_card(None)
            return

        self._middle_title.configure(text=f"HOTSPOTS  ·  {clip(entry.short_name, 28).upper()}")
        saved = hotspots.hotspot_repository.all()
        spots = data.spots_on(saved, entry.system, entry.body)
        position_of = {id(h): i for i, h in enumerate(saved)}  # identity, not equality: duplicates compare equal
        groups = []
        for label, group_spots in data.group_by_location(spots):
            rows = []
            for spot in group_spots:
                key = str(position_of[id(spot)])
                self._spot_by_key[key] = spot
                estimate = mining_deposit.reserve_text(spot.rigs, spot.amount, spot.density, spot.mined_tons)
                bits = [f"{spot.rigs} rigs"] if spot.rigs else []
                bits.append(estimate or "no estimate")
                rows.append(dict(key=key, title=spot.material, indent=10, sub="  ·  ".join(bits),
                                 detail=f"{spot.mined_tons:,} t" if spot.mined_tons else "",
                                 pill=(spot.amount, _AMOUNT_COLORS.get(spot.amount, P.MUTED)) if spot.amount else None))
            groups.append((label, label, rows))
        self._hotspots.populate(groups, keep_scroll=True)
        for label, _heading, _rows in groups:
            self._hotspots.open_group(label)

        summary = data.summarize(spots)
        self._tile_saved.set(str(summary.saved))
        self._tile_mined.set(f"{summary.mined_tons:,} t")
        self._tile_active.set(str(summary.still_active))
        self._draw_materials(spots)
        self._draw_prospecting(entry, spots)
        self._draw_map(entry, spots)

        reselect = next((k for k, s in self._spot_by_key.items() if _spot_ident(s) == previous), None)
        if reselect:
            self._select_spot(reselect)
        else:
            self._render_card(None)

    def _draw_materials(self, spots: list[hotspots.Hotspot]) -> None:
        """One line summarising what's saved on this body (your own records):
        "Monazite ×2 · Painite ×1 · +2 more"."""
        lines = data.material_summary(spots)
        text = "  ·  ".join(f"{clip(m.material, 24)} ×{m.hotspots}" for m in lines[:6])
        if len(lines) > 6:
            text += f"  ·  +{len(lines) - 6} more"
        self._materials.configure(text=text)

    def _show_prospecting(self, visible: bool) -> None:
        for widget in (self._prospect_head, self._prospect_table, self._prospect_note):
            widget.pack_forget()
        if visible:
            before = self._hotspots
            self._prospect_head.pack(fill="x", pady=(0, 2), before=before)
            self._prospect_table.pack(fill="x", padx=P.PAD, pady=(0, 2), before=before)
            self._prospect_note.pack(fill="x", pady=(0, P.PAD_SM), before=before)

    def _draw_prospecting(self, entry: data.BodyEntry, spots: list[hotspots.Hotspot]) -> None:
        """Your own rates for this kind of body (see mining_ground.OwnRates):
        the share of the deposits you have recorded on this kind of ground
        that were each material. Hidden for a body we only know from a saved
        hotspot (no class to look up) and until something is recorded on
        this kind of ground."""
        rows = data.prospect_rows(self._rates, entry.ground, spots)
        if not rows:
            self._show_prospecting(False)
            return
        self._show_prospecting(True)
        self._prospect_title.configure(
            text=f"YOUR RECORDS  ·  {mining_ground.label(entry.ground).upper()}  ·  "
                 f"{self._rates.sample_size(entry.ground)} DEPOSITS RECORDED")
        self._prospect_table.clear()
        chosen = self._material.get().strip().casefold()
        if chosen and chosen != data.ALL_MATERIALS.casefold():
            rows = sorted(rows, key=lambda r: r.material.casefold() != chosen)  # the filtered material first
        for row in rows[:12]:
            self._prospect_table.append((row.material, f"{row.pct:.0f}%", row.count,
                                         "✓" if row.saved_here else ""))
        self._prospect_note.configure(
            text="Built only from deposits you have saved: what you have found so far on this kind of "
                 "body, not what this body holds. A small sample says little.")

    def _draw_map(self, entry: data.BodyEntry, spots: list[hotspots.Hotspot]) -> None:
        surface = surface_mining.surface_mining_repository
        here = (surface.current_system or "").casefold() == entry.system.casefold() and \
               (surface.current_body or "").casefold() == entry.body.casefold()
        radius = surface.radius_for_current_body() if here else None
        if not radius:
            self._map.set_message("Map needs the body's radius - visit the body to see it here"
                                  if not here else "Body radius not known yet")
            return
        position = live_position.current_position() if here else None
        current = (position.latitude, position.longitude) if position else None
        body_coverage = coverage.coverage_repository.for_body(entry.system, entry.body)
        center = data.map_center(body_coverage, current, spots)
        if center is None:
            self._map.set_message("Nothing recorded on this body yet")
            return
        cover = [data.project_m(center[0], center[1], p.latitude, p.longitude, radius)
                 for p in (body_coverage.points if body_coverage else ())]
        markers = []
        for key, spot in self._spot_by_key.items():
            if spot.has_position():
                east, north = data.project_m(center[0], center[1], spot.latitude, spot.longitude, radius)
                label = str(spot.signal_number) if spot.signal_number is not None else ""
                markers.append(MapMarker(key, east, north, label, spot.amount == "Depleted"))
        you = data.project_m(center[0], center[1], current[0], current[1], radius) if current else None
        self._map.set_message(None)
        self._map.set_data(cover, markers, you)

    # --- selection / card --------------------------------------------------------
    def _select_spot(self, key: str) -> None:
        spot = self._spot_by_key.get(key)
        if spot is None:
            return
        self._selected_spot = spot
        self._hotspots.select(key, notify=False)
        self._map.select(key)
        self._render_card(spot)

    def _render_card(self, spot: Optional[hotspots.Hotspot]) -> None:
        for child in self._card.winfo_children():
            child.destroy()
        if spot is None:
            tk.Label(self._card, text="Select a hotspot", fg=P.MUTED, bg=P.CARD).pack(anchor="w")
            return
        tk.Label(self._card, text=clip(spot.material, 30), fg=P.TEXT, bg=P.CARD,
                 font=style.font(P.FONT_TITLE)).pack(anchor="w")
        subtitle = [data.location_label(spot)]
        if spot.rigs:
            subtitle.append(f"{spot.rigs} rigs")
        tk.Label(self._card, text="  ·  ".join(subtitle), fg=P.MUTED, bg=P.CARD).pack(anchor="w", pady=(0, 6))
        pills = tk.Frame(self._card, bg=P.CARD)
        pills.pack(anchor="w", pady=(0, 8))
        if spot.density:
            Pill(pills, f"{spot.density} density", _DENSITY_COLORS.get(spot.density, P.MUTED)).pack(side="left", padx=(0, 6))
        if spot.amount:
            Pill(pills, f"{spot.amount} amount", _AMOUNT_COLORS.get(spot.amount, P.MUTED)).pack(side="left")
        estimate = mining_deposit.reserve_text(spot.rigs, spot.amount, spot.density, spot.mined_tons)
        if estimate:
            tk.Label(self._card, text=estimate, fg=P.ACCENT, bg=P.CARD,
                     font=style.font(P.FONT_SECTION)).pack(anchor="w")
        if spot.mined_tons:
            tk.Label(self._card, text=f"{spot.mined_tons:,} t mined so far", fg=P.MUTED, bg=P.CARD).pack(anchor="w")
        if spot.has_position():
            tk.Label(self._card, text=f"{spot.latitude:.4f}, {spot.longitude:.4f}", fg=P.MUTED,
                     bg=P.CARD).pack(anchor="w")
        if spot.notes:
            tk.Label(self._card, text=clip(spot.notes, 120), fg=P.TEXT, bg=P.CARD, wraplength=300,
                     justify="left").pack(anchor="w", pady=(6, 0))
        buttons = tk.Frame(self._card, bg=P.CARD)
        buttons.pack(fill="x", pady=(10, 0))
        buttons.columnconfigure((0, 1), weight=1)
        actions = [("Mark depleted", self._mark_depleted, spot.amount != "Depleted"),
                   ("Copy coords", self._copy_coords, spot.has_position()),
                   ("Edit", self._edit, True), ("Delete", self._delete, True)]
        for index, (text, command, enabled) in enumerate(a for a in actions if a[2]):
            FlatButton(buttons, text, command, kind="danger" if text == "Delete" else "normal"
                       ).grid(row=index // 2, column=index % 2, sticky="ew", padx=2, pady=2)

    # --- actions ---------------------------------------------------------------
    def _index_of(self, spot: hotspots.Hotspot) -> Optional[int]:
        for index, candidate in enumerate(hotspots.hotspot_repository.all()):
            if candidate is spot:
                return index
        return None

    def _mark_depleted(self) -> None:
        spot = self._selected_spot
        index = self._index_of(spot) if spot else None
        if spot is not None and index is not None:
            hotspots.hotspot_repository.update(index, dataclasses.replace(spot, amount="Depleted"))
            self._shell.set_status(f"{spot.material} marked depleted")

    def _copy_coords(self) -> None:
        spot = self._selected_spot
        if spot is not None and spot.has_position():
            if panelkit.copy_to_clipboard(self._shell.window, f"{spot.latitude:.4f}, {spot.longitude:.4f}"):
                self._shell.set_status("Coordinates copied")

    def _edit(self) -> None:
        spot = self._selected_spot
        index = self._index_of(spot) if spot else None
        if spot is None or index is None:
            return
        hotspot_dialog.open_hotspot_dialog(
            self._shell.window, existing=spot,
            on_save=lambda updated, i=index: hotspots.hotspot_repository.update(i, updated))

    def _delete(self) -> None:
        spot = self._selected_spot
        index = self._index_of(spot) if spot else None
        if spot is None or index is None:
            return
        if messagebox.askyesno("Delete hotspot", f"Delete {spot.material} on {spot.body}?",
                               parent=self._shell.window):
            hotspots.hotspot_repository.remove(index)
            self._shell.set_status("Hotspot deleted")

    def _add_hotspot(self) -> None:
        from . import mining_render
        mining_render.open_add_hotspot_dialog(self._shell.window)
