"""
The known-surface-hotspots list section (see mining_hotspots.py) of
Mining mode's Settings tab: add/edit/delete rows plus JSON import/
export. Split out of mining_panel.py's own build_settings() into its
own module - at ~115 lines it's substantial enough to give its own
home, same reasoning as every other feature-module split in this project.

A plain tk.Listbox/Buttons, unlike the rest of Mining's tab's nb.*
widgets - myNotebook has no themed Listbox, so its colors are set
explicitly from the active theme below rather than left to inherit
EDMC's ttk styling like the checkboxes do. Uses plain tk.Button (not
nb.Button, which doesn't exist in WNTB's myNotebook - same fix made to
screenshots.py).
"""
import tkinter as tk
from typing import Optional

import myNotebook as nb
from theme import theme

from . import mining_deposit
from . import mining_hotspot_dialog as hotspot_dialog
from . import mining_hotspot_import_export as hotspot_import_export
from . import mining_hotspots as hotspots

_UNFILED = "Unfiled"


def build(frame: tk.Frame, start_row: int) -> None:
    """Builds the hotspot-list section into `frame`, starting at grid
    row `start_row`. `frame` is Mining's own Settings-tab frame - this
    function is a continuation of that same grid, not a separate
    Toplevel/tab."""
    is_dark = theme.active not in (None, theme.THEME_DEFAULT)
    listbox_bg = "#1e1e1e" if is_dark else "SystemWindow"
    listbox_fg = "#e0e0e0" if is_dark else "SystemWindowText"

    nb.Label(frame, text="Known Surface Hotspots").grid(
        row=start_row, column=0, columnspan=2, sticky=tk.W, padx=10, pady=(14, 0))
    nb.Label(frame, text="Static, manually-recorded surface material sites.").grid(
        row=start_row + 1, column=0, columnspan=2, sticky=tk.W, padx=10)

    list_row = nb.Frame(frame)
    list_row.grid(row=start_row + 2, column=0, columnspan=2, padx=10, pady=(4, 0), sticky=tk.W)
    hotspot_listbox = tk.Listbox(list_row, width=64, height=6,
                                 background=listbox_bg, foreground=listbox_fg,
                                 selectbackground="#3a6ea5", exportselection=False)
    hotspot_listbox.grid(row=0, column=0, sticky="ns")
    hotspot_scrollbar = tk.Scrollbar(list_row, orient="vertical", command=hotspot_listbox.yview)
    hotspot_scrollbar.grid(row=0, column=1, sticky="ns")
    hotspot_listbox.configure(yscrollcommand=hotspot_scrollbar.set)

    # Grouped by folder ("" = "Unfiled", listed last): each render rebuilds
    # this row -> hotspot-index map alongside the listbox rows themselves,
    # since folder header rows shift every hotspot's display row away from
    # its index in hotspot_repository.all(). A header row maps to None so
    # _selected_index() can tell "no selection" apart from "selected a
    # header", and Edit/Delete no-op on the latter rather than acting on
    # the wrong hotspot.
    _row_to_index: list[Optional[int]] = []

    def _refresh() -> None:
        hotspot_listbox.delete(0, tk.END)
        _row_to_index.clear()
        all_hotspots = hotspots.hotspot_repository.all()
        by_folder: dict[str, list[int]] = {}
        for i, hotspot in enumerate(all_hotspots):
            by_folder.setdefault(hotspot.folder.strip() or _UNFILED, []).append(i)
        for folder in sorted(by_folder, key=lambda f: (f == _UNFILED, f.casefold())):
            hotspot_listbox.insert(tk.END, f"▾ {folder}")
            _row_to_index.append(None)
            for i in by_folder[folder]:
                hotspot = all_hotspots[i]
                label = f"    {hotspot.system} / {hotspot.body} - {hotspot.material}"
                if hotspot.rigs is not None:
                    label += f" ({hotspot.rigs}R)"
                if hotspot.signal_number is not None:
                    label += f" [Signal {hotspot.signal_number}]"
                estimate = mining_deposit.describe(hotspot.rigs, hotspot.amount, hotspot.density, hotspot.mined_tons)
                if estimate:
                    label += f" [{estimate}]"
                hotspot_listbox.insert(tk.END, label)
                _row_to_index.append(i)

    def _selected_index() -> Optional[int]:
        selection = hotspot_listbox.curselection()
        if not selection:
            return None
        return _row_to_index[selection[0]]

    def _save_new(hotspot: hotspots.Hotspot) -> None:
        hotspots.hotspot_repository.add(hotspot)
        _refresh()

    def _save_edit(index: int, hotspot: hotspots.Hotspot) -> None:
        hotspots.hotspot_repository.update(index, hotspot)
        _refresh()

    def _on_add() -> None:
        hotspot_dialog.open_hotspot_dialog(frame, on_save=_save_new)

    def _on_edit() -> None:
        index = _selected_index()
        if index is None:
            return
        existing = hotspots.hotspot_repository.all()[index]
        hotspot_dialog.open_hotspot_dialog(
            frame, existing=existing,
            on_save=lambda h, i=index: _save_edit(i, h))

    def _on_delete() -> None:
        index = _selected_index()
        if index is None:
            return
        hotspots.hotspot_repository.remove(index)
        _refresh()

    def _on_import() -> None:
        hotspot_import_export.import_hotspots(frame)
        _refresh()

    def _on_export() -> None:
        hotspot_import_export.export_hotspots(frame)

    def _on_import_link() -> None:
        hotspot_import_export.import_from_link(frame)
        _refresh()

    hotspots.hotspot_repository.add_listener(_refresh)
    _refresh()

    button_row = nb.Frame(frame)
    button_row.grid(row=start_row + 3, column=0, columnspan=2, padx=10, pady=(4, 10), sticky=tk.W)
    tk.Button(button_row, text="Add", command=_on_add).grid(row=0, column=0, padx=2)
    tk.Button(button_row, text="Edit", command=_on_edit).grid(row=0, column=1, padx=2)
    tk.Button(button_row, text="Delete", command=_on_delete).grid(row=0, column=2, padx=2)
    tk.Button(button_row, text="Import...", command=_on_import).grid(row=0, column=3, padx=2)
    tk.Button(button_row, text="Export...", command=_on_export).grid(row=0, column=4, padx=2)
    tk.Button(button_row, text="Import from Link...", command=_on_import_link).grid(
        row=0, column=5, padx=2)
