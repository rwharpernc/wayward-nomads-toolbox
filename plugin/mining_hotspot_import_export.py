"""
Import/export for the known-surface-hotspots list (mining_hotspots.py),
shared between the Settings tab's hotspot section
(mining_hotspot_settings.py) and the in-panel "Import/Export
Hotspots..." button (mining_render.py) so the file-picker/merge-prompt/
error-handling logic exists in exactly one place.
"""
import logging
import os
import tkinter as tk
import tkinter.filedialog as filedialog
import tkinter.messagebox as messagebox

from config import appname

from . import mining_hotspots as hotspots
from .uikit import palette
from .uikit import style as ui_style

plugin_name = os.path.basename(os.path.dirname(__file__))
logger = logging.getLogger(f"{appname}.{plugin_name}")


def import_hotspots(parent: tk.Misc) -> None:
    """Opens a file picker, asks merge-vs-replace, and imports. Accepts
    either WNTB's own export shape or a PlanetPOI poi.json export -
    HotspotRepository.import_from_file() auto-detects which (see
    mining_hotspots.py) - so this dialog doesn't need to ask which
    format it is. Any listener registered on hotspot_repository (the
    main panel included, via mining_panel.py's add_listener call)
    refreshes on its own once the import succeeds - this function
    doesn't need to know who's displaying the list."""
    path = filedialog.askopenfilename(
        title="Import Hotspots (WNTB or PlanetPOI export)",
        filetypes=[("JSON files", "*.json")])
    if not path:
        return
    merge = messagebox.askyesno(
        "Import Hotspots",
        "Merge with the existing list?\n\nYes = add to current list.\nNo = replace it entirely.")
    try:
        count = hotspots.hotspot_repository.import_from_file(path, merge=merge)
    except Exception:
        logger.exception("Failed to import hotspots from %s", path)
        messagebox.showerror("Import Hotspots", "Could not read that file - see the log.")
        return
    messagebox.showinfo("Import Hotspots", f"Imported {count} hotspot(s).")


def export_hotspots(_parent: tk.Misc) -> None:
    """Opens a save-file picker and writes the full hotspot list in
    WNTB's own flat JSON shape (see mining_hotspots.py's
    HotspotRepository.export_to_file()) - this is the file another
    commander's import_hotspots() call above can read back in
    directly."""
    path = filedialog.asksaveasfilename(defaultextension=".json",
                                        filetypes=[("JSON files", "*.json")])
    if not path:
        return
    try:
        hotspots.hotspot_repository.export_to_file(path)
    except Exception:
        logger.exception("Failed to export hotspots to %s", path)
        messagebox.showerror("Export Hotspots", "Could not write that file - see the log.")


def import_from_link(parent: tk.Misc) -> None:
    """Opens a small paste-a-link dialog and imports a single PlanetPOI
    shareable-POI link (or its bare payload) - see mining_hotspots.
    parse_planetpoi_share_link(). Complements the file-based import
    above for the "someone pasted one link in Discord/a forum" case,
    which doesn't need a whole poi.json export just for one spot."""
    root = parent.winfo_toplevel()
    dialog = tk.Toplevel(root)
    ui_style.skin(dialog)
    dialog.title("Import Hotspot from Link")
    dialog.resizable(False, False)
    dialog.transient(root)
    ui_style.grab_when_visible(dialog)

    tk.Label(dialog, text="Paste a PlanetPOI share link (or its payload):", anchor=tk.W).grid(
        row=0, column=0, sticky="w", padx=8, pady=(8, 4))
    link_var = tk.StringVar()
    tk.Entry(dialog, textvariable=link_var, width=70).grid(
        row=1, column=0, sticky="ew", padx=8, pady=(0, 4))

    error_label = tk.Label(dialog, text="", fg=palette.DANGER, wraplength=420, justify=tk.LEFT)
    error_label.grid(row=2, column=0, sticky="w", padx=8)

    def _on_import() -> None:
        text = link_var.get().strip()
        if not text:
            error_label.configure(text="Paste a link first.")
            return
        try:
            hotspot = hotspots.parse_planetpoi_share_link(text)
        except Exception as exc:
            error_label.configure(text=str(exc))
            return
        hotspots.hotspot_repository.add(hotspot)
        dialog.destroy()
        messagebox.showinfo("Import Hotspot from Link",
                            f"Added {hotspot.system} / {hotspot.body} - {hotspot.material}.")

    button_row = tk.Frame(dialog)
    button_row.grid(row=3, column=0, pady=(6, 8))
    tk.Button(button_row, text="Import", command=_on_import).pack(side=tk.LEFT, padx=4)
    tk.Button(button_row, text="Cancel", command=dialog.destroy).pack(side=tk.LEFT, padx=4)

    dialog.bind("<Return>", lambda _e: _on_import())
    dialog.bind("<Escape>", lambda _e: dialog.destroy())


def open_import_export_dialog(parent: tk.Misc) -> None:
    """The in-panel entry point (mining_render.py's "Import/Export
    Hotspots..." button) - a small Toplevel offering both actions,
    rather than two separate persistent buttons crowding the panel. The
    Settings tab keeps its own always-visible Import.../Export...
    buttons since it already has the room (see
    mining_hotspot_settings.py)."""
    # Parented on parent's *toplevel*, not parent itself - same reasoning
    # as mining_hotspot_dialog.py: a Toplevel parented directly on
    # mining_render.py's periodically-rebuilt content frame gets
    # destroyed along with it the next time that fires.
    root = parent.winfo_toplevel()
    dialog = tk.Toplevel(root)
    ui_style.skin(dialog)
    dialog.title("Import/Export Hotspots")
    dialog.resizable(False, False)
    dialog.transient(root)
    ui_style.grab_when_visible(dialog)

    tk.Label(dialog, text="Known Surface Hotspots", anchor=tk.W).grid(
        row=0, column=0, columnspan=2, sticky="w", padx=8, pady=(8, 4))

    button_row = tk.Frame(dialog)
    button_row.grid(row=1, column=0, columnspan=2, pady=(2, 8))
    tk.Button(button_row, text="Import...",
             command=lambda: import_hotspots(dialog)).pack(side=tk.LEFT, padx=4)
    tk.Button(button_row, text="Export...",
             command=lambda: export_hotspots(dialog)).pack(side=tk.LEFT, padx=4)
    tk.Button(button_row, text="Import from Link...",
             command=lambda: import_from_link(dialog)).pack(side=tk.LEFT, padx=4)
    tk.Button(button_row, text="Close", command=dialog.destroy).pack(side=tk.LEFT, padx=4)

    dialog.bind("<Escape>", lambda _e: dialog.destroy())
