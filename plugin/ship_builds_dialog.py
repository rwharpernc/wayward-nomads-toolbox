"""Add/Edit Ship Build modal - same plain-tk.Toplevel, parented on the
caller's own toplevel (not the frame that might get torn down and
rebuilt under it) convention as mining_hotspot_dialog.py."""

from __future__ import annotations

import tkinter as tk
from typing import Callable, Optional

from .ship_builds_data import KNOWN_SITES, ShipBuild, new_id
from .uikit import palette
from .uikit import style as ui_style
from .uikit.widgets import Combobox

_FIELD_WIDTH = 40
_ERROR_COLOR = palette.DANGER


def open_ship_build_dialog(
    parent: tk.Misc,
    on_save: Callable[[ShipBuild], None],
    existing: Optional[ShipBuild] = None,
    prefill_ship: str = "",
) -> None:
    """Opens a modal Add/Edit Ship Build window. `existing` prefills every
    field for editing; otherwise `prefill_ship` seeds a blank form with
    the commander's currently-flown ship (see ship_builds_panel.py).
    Calls on_save(build) once the form validates and Save is clicked -
    never called if the dialog is cancelled or closed."""
    root = parent.winfo_toplevel()
    dialog = tk.Toplevel(root)
    ui_style.skin(dialog)
    dialog.title("Edit Ship Build" if existing else "Add Ship Build")
    dialog.resizable(False, False)
    dialog.transient(root)
    dialog.grab_set()

    name_var = tk.StringVar(value=existing.name if existing else "")
    ship_var = tk.StringVar(value=existing.ship if existing else prefill_ship)
    role_var = tk.StringVar(value=existing.role if existing else "")
    site_var = tk.StringVar(value=existing.site if existing else KNOWN_SITES[0])
    url_var = tk.StringVar(value=existing.url if existing else "")
    notes_var = tk.StringVar(value=existing.notes if existing else "")

    dialog.columnconfigure(1, weight=1)

    def _row(label: str, var: tk.StringVar, row: int) -> None:
        tk.Label(dialog, text=label, anchor=tk.W).grid(row=row, column=0, sticky="w", padx=8, pady=4)
        tk.Entry(dialog, textvariable=var, width=_FIELD_WIDTH).grid(row=row, column=1, sticky="ew", padx=8, pady=4)

    _row("Name*", name_var, 0)
    _row("Ship*", ship_var, 1)
    _row("Role", role_var, 2)

    tk.Label(dialog, text="Site*", anchor=tk.W).grid(row=3, column=0, sticky="w", padx=8, pady=4)
    # Editable (default state, not readonly): the quick-pick list covers
    # the common providers, but a commander using some other build site
    # entirely should still be able to type its name in free text - same
    # "offer known values, don't force them" convention as mining_hotspot_
    # dialog.py's own Folder combobox.
    Combobox(dialog, textvariable=site_var, width=_FIELD_WIDTH - 2, values=KNOWN_SITES).grid(
        row=3, column=1, sticky="ew", padx=8, pady=4,
    )

    _row("URL*", url_var, 4)
    _row("Notes", notes_var, 5)

    error_label = tk.Label(dialog, text="", fg=_ERROR_COLOR, wraplength=320, justify=tk.LEFT)
    error_label.grid(row=6, column=0, columnspan=2, sticky="w", padx=8)

    def _on_save() -> None:
        name = name_var.get().strip()
        ship = ship_var.get().strip()
        site = site_var.get().strip()
        url = url_var.get().strip()
        if not name or not ship or not site or not url:
            error_label.configure(text="Name, Ship, Site, and URL are required.")
            return
        if not (url.startswith("http://") or url.startswith("https://")):
            error_label.configure(text="URL must start with http:// or https://")
            return

        if existing is not None:
            build = ShipBuild(
                id=existing.id, ship=ship, name=name, site=site, url=url,
                role=role_var.get().strip(), notes=notes_var.get().strip(),
                created=existing.created, updated=existing.updated,
            )
        else:
            build = ShipBuild(
                id=new_id(), ship=ship, name=name, site=site, url=url,
                role=role_var.get().strip(), notes=notes_var.get().strip(),
            )
        on_save(build)
        dialog.destroy()

    button_row = tk.Frame(dialog)
    button_row.grid(row=7, column=0, columnspan=2, pady=(6, 8))
    tk.Button(button_row, text="Save", command=_on_save).pack(side=tk.LEFT, padx=4)
    tk.Button(button_row, text="Cancel", command=dialog.destroy).pack(side=tk.LEFT, padx=4)

    dialog.bind("<Return>", lambda _e: _on_save())
    dialog.bind("<Escape>", lambda _e: dialog.destroy())
