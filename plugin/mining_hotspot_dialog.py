"""
Shared Add/Edit Hotspot form - a plain tk.Toplevel (not part of EDMC's own
window, so none of the main-window-sizing rules apply here), used by both
the in-panel "Save Hotspot Here" button (mining_render.py) and the
Settings tab's hotspot list (mining_hotspot_settings.py). Same fields and
validation either way - only the prefill data and the save callback
differ.
"""
import tkinter as tk
from typing import Callable, Optional

from . import mining_deposit
from .mining_hotspots import Hotspot, hotspot_repository
from .uikit import palette
from .uikit import style as ui_style
from .uikit.widgets import Combobox

_FIELD_WIDTH = 32
_ERROR_COLOR = palette.DANGER


def open_hotspot_dialog(
    parent: tk.Misc,
    on_save: Callable[[Hotspot], None],
    existing: Optional[Hotspot] = None,
    prefill_system: str = "",
    prefill_body: str = "",
    prefill_latitude: Optional[float] = None,
    prefill_longitude: Optional[float] = None,
) -> None:
    """Opens a modal Add/Edit Hotspot window. `existing` prefills every
    field for editing an existing entry; otherwise the individual
    prefill_* args seed a blank form (e.g. the commander's current
    system/body/last touchdown spot). Calls on_save(hotspot) once the
    form validates and Save is clicked - never called if the dialog is
    cancelled or closed."""
    # Parented on parent's *toplevel*, not parent itself: mining_render.py
    # rebuilds its content frame from scratch every second (the periodic
    # RPM-decay tick) and on every journal event - a Toplevel parented
    # directly on that frame gets destroyed along with it the next time
    # that fires, which looks like the dialog closing itself moments
    # after opening.
    root = parent.winfo_toplevel()
    dialog = tk.Toplevel(root)
    ui_style.skin(dialog)
    dialog.title("Edit Hotspot" if existing else "Add Hotspot")
    dialog.resizable(False, False)
    dialog.transient(root)
    dialog.grab_set()

    system_var = tk.StringVar(value=existing.system if existing else prefill_system)
    body_var = tk.StringVar(value=existing.body if existing else prefill_body)
    material_var = tk.StringVar(value=existing.material if existing else "")
    rigs_var = tk.StringVar(value="" if not existing or existing.rigs is None else str(existing.rigs))
    signal_number_var = tk.StringVar(
        value="" if not existing or existing.signal_number is None else str(existing.signal_number))
    notes_var = tk.StringVar(value=existing.notes if existing else "")
    lat_default = existing.latitude if existing else prefill_latitude
    lon_default = existing.longitude if existing else prefill_longitude
    lat_var = tk.StringVar(value="" if lat_default is None else str(lat_default))
    lon_var = tk.StringVar(value="" if lon_default is None else str(lon_default))
    folder_var = tk.StringVar(value=existing.folder if existing else "")
    amount_var = tk.StringVar(value=existing.amount if existing and existing.amount else "")
    density_var = tk.StringVar(value=existing.density if existing and existing.density else "")

    dialog.columnconfigure(1, weight=1)

    def _row(label: str, var: tk.StringVar, row: int) -> None:
        tk.Label(dialog, text=label, anchor=tk.W).grid(
            row=row, column=0, sticky="w", padx=8, pady=4)
        tk.Entry(dialog, textvariable=var, width=_FIELD_WIDTH).grid(
            row=row, column=1, sticky="ew", padx=8, pady=4)

    def _dropdown_row(label: str, var: tk.StringVar, values: tuple[str, ...], row: int) -> None:
        tk.Label(dialog, text=label, anchor=tk.W).grid(
            row=row, column=0, sticky="w", padx=8, pady=4)
        # readonly: unlike Folder below, a typo here (anything other than
        # a mining_deposit.AMOUNTS/DENSITIES value) would silently drop
        # out of the tons-left estimate rather than raise, so only the
        # HUD's own known readouts are offered.
        Combobox(dialog, textvariable=var, width=_FIELD_WIDTH - 2,
                     values=("",) + values, state="readonly").grid(
            row=row, column=1, sticky="ew", padx=8, pady=4)

    _row("System*", system_var, 0)
    _row("Body*", body_var, 1)
    _row("Contains*", material_var, 2)
    _row("Rigs", rigs_var, 3)
    _row("Signal #", signal_number_var, 4)
    _row("Latitude", lat_var, 5)
    _row("Longitude", lon_var, 6)
    _row("Notes", notes_var, 7)
    # HUD mining-scanner readout at the time this was recorded - feeds
    # mining_deposit.describe()'s estimated tons-remaining range, shown
    # once Rigs and Amount are both set (mining_render.py's format_hotspot()).
    _dropdown_row("Amount", amount_var, mining_deposit.AMOUNTS, 8)
    _dropdown_row("Density", density_var, mining_deposit.DENSITIES, 9)

    tk.Label(dialog, text="Folder", anchor=tk.W).grid(
        row=10, column=0, sticky="w", padx=8, pady=4)
    # Combobox (not Entry): existing folder names are offered so a
    # commander groups a new hotspot into one with a click, but the field
    # stays editable (default state) so typing a name that doesn't exist
    # yet just creates that folder - there's no separate "new folder"
    # action, see the Hotspot.folder docstring in mining_hotspots.py.
    Combobox(dialog, textvariable=folder_var, width=_FIELD_WIDTH - 2,
                 values=hotspot_repository.folders()).grid(
        row=10, column=1, sticky="ew", padx=8, pady=4)

    error_label = tk.Label(dialog, text="", fg=_ERROR_COLOR, wraplength=260, justify=tk.LEFT)
    error_label.grid(row=11, column=0, columnspan=2, sticky="w", padx=8)

    def _parse_optional_float(text: str, field_name: str) -> Optional[float]:
        text = text.strip()
        if not text:
            return None
        try:
            return float(text)
        except ValueError:
            raise ValueError(f"{field_name} must be a number (or left blank).")

    def _parse_optional_int(text: str, field_name: str) -> Optional[int]:
        text = text.strip()
        if not text:
            return None
        try:
            return int(text)
        except ValueError:
            raise ValueError(f"{field_name} must be a whole number (or left blank).")

    def _on_save() -> None:
        system = system_var.get().strip()
        body = body_var.get().strip()
        material = material_var.get().strip()
        if not system or not body or not material:
            error_label.configure(text="System, Body, and Contains are required.")
            return
        try:
            rigs = _parse_optional_int(rigs_var.get(), "Rigs")
            if rigs is not None and not 1 <= rigs <= mining_deposit.MAX_RIGS:
                raise ValueError(f"Rigs must be 1-{mining_deposit.MAX_RIGS} (or left blank).")
            signal_number = _parse_optional_int(signal_number_var.get(), "Signal #")
            latitude = _parse_optional_float(lat_var.get(), "Latitude")
            longitude = _parse_optional_float(lon_var.get(), "Longitude")
        except ValueError as exc:
            error_label.configure(text=str(exc))
            return
        on_save(Hotspot(system=system, body=body, material=material,
                        notes=notes_var.get().strip(),
                        latitude=latitude, longitude=longitude,
                        folder=folder_var.get().strip(), rigs=rigs,
                        signal_number=signal_number,
                        amount=amount_var.get().strip() or None,
                        density=density_var.get().strip() or None,
                        mined_tons=existing.mined_tons if existing else None,
                        ground=existing.ground if existing else None))
        dialog.destroy()

    button_row = tk.Frame(dialog)
    button_row.grid(row=12, column=0, columnspan=2, pady=(6, 8))
    tk.Button(button_row, text="Save", command=_on_save).pack(side=tk.LEFT, padx=4)
    tk.Button(button_row, text="Cancel", command=dialog.destroy).pack(side=tk.LEFT, padx=4)

    dialog.bind("<Return>", lambda _e: _on_save())
    dialog.bind("<Escape>", lambda _e: dialog.destroy())
