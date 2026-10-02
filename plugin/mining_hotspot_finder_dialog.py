"""
"Find Nearby Hotspots" dialog (Space Mining page) - queries Spansh for
the nearest rings with a confirmed hotspot for a commodity, closest
first. Opt-in via the "Enable Spansh Nearby Hotspot Finder" setting (see
mining_panel.py); the actual network call lives in
mining_spansh_client.py, kept separate so this module only owns the Tk
form/threading/results-display side. A plain tk.Toplevel like
mining_hotspot_dialog.py - not part of EDMC's own window, so none of the
main-window-sizing rules apply here.

The search itself is a blocking network call, so it always runs on a
background thread - the Search button disables itself while a search is
in flight, and results/errors are marshaled back via
`dialog.after(0, ...)`.
"""
import logging
import os
import threading
import tkinter as tk

from config import appname

from . import mining_location as location
from . import mining_spansh_client as spansh_client
from . import panelkit
from .uikit import palette
from .uikit import style as ui_style
from .uikit.widgets import Combobox

plugin_name = os.path.basename(os.path.dirname(__file__))
logger = logging.getLogger(f"{appname}.{plugin_name}")

_DEFAULT_MAX_DISTANCE_LY = 100
_MAX_RESULTS = 10
_ERROR_COLOR = palette.DANGER
_MUTED_COLOR = palette.MUTED


def open_hotspot_finder_dialog(parent: tk.Misc) -> None:
    reference_system = location.current_system()

    # Parented on parent's *toplevel*, not parent itself: mining_render.py
    # rebuilds its content frame from scratch every second (the periodic
    # RPM-decay tick) and on every journal event - a Toplevel parented
    # directly on that frame gets destroyed along with it the next time
    # that fires, which looks like the dialog closing itself moments
    # after opening.
    root = parent.winfo_toplevel()
    dialog = tk.Toplevel(root)
    ui_style.skin(dialog)
    dialog.title("Find Nearby Hotspots")
    # Resizable (unlike mining_hotspot_dialog.py's fixed-size form): a
    # result row's width depends on system/body/ring name length, which
    # varies a lot for procedurally-generated names - no fixed width
    # fits every result, so let the commander widen the window
    # themselves rather than guessing.
    dialog.resizable(True, True)
    dialog.transient(root)
    dialog.grab_set()
    dialog.columnconfigure(1, weight=1)

    system_text = reference_system or "(unknown - wait for a journal event)"
    tk.Label(dialog, text=f"Searching near: {system_text}", anchor=tk.W).grid(
        row=0, column=0, columnspan=2, sticky="w", padx=8, pady=(8, 4))

    tk.Label(dialog, text="Material*", anchor=tk.W).grid(row=1, column=0, sticky="w", padx=8, pady=4)
    material_var = tk.StringVar()
    # Editable, not "readonly": the dropdown lists every material
    # confirmed to work (see spansh_client.KNOWN_RING_HOTSPOT_MATERIALS),
    # but typing a value not in that list is still allowed - covers a
    # hotspot material Spansh or the game adds later.
    Combobox(dialog, textvariable=material_var, width=22,
                values=spansh_client.KNOWN_RING_HOTSPOT_MATERIALS).grid(
        row=1, column=1, sticky="ew", padx=8, pady=4)

    tk.Label(dialog, text="Max distance (ly)", anchor=tk.W).grid(row=2, column=0, sticky="w", padx=8, pady=4)
    distance_var = tk.StringVar(value=str(_DEFAULT_MAX_DISTANCE_LY))
    tk.Entry(dialog, textvariable=distance_var, width=24).grid(
        row=2, column=1, sticky="ew", padx=8, pady=4)

    search_button = tk.Button(dialog, text="Search")
    search_button.grid(row=3, column=0, columnspan=2, pady=(2, 4))

    status_label = tk.Label(dialog, text="", anchor=tk.W, justify=tk.LEFT, wraplength=520)
    status_label.grid(row=4, column=0, columnspan=2, sticky="w", padx=8)

    results_frame = tk.Frame(dialog)
    results_frame.grid(row=5, column=0, columnspan=2, sticky="ew", padx=8, pady=(2, 4))
    results_frame.columnconfigure(0, weight=1)

    def _clear_results() -> None:
        for child in results_frame.winfo_children():
            child.destroy()

    def _add_copyable_row(parent: tk.Frame, row: int, display_text: str,
                          copy_value: str, button_text: str, pady) -> None:
        row_var = tk.StringVar(value=display_text)
        # A readonly Entry, not a Label: Labels can't be selected, so there
        # was no way to copy a name out of the results to paste into the
        # galaxy map. Readonly still allows select/Ctrl+C like a normal
        # Entry, just blocks editing.
        entry = tk.Entry(parent, textvariable=row_var, width=70, state="readonly")
        entry.grid(row=row, column=0, sticky="ew", pady=pady)
        tk.Button(parent, text=button_text,
                  command=lambda: panelkit.copy_to_clipboard(dialog, copy_value)).grid(
            row=row, column=1, padx=(4, 0), pady=pady)

    def _show_results(results: list[spansh_client.RingHotspot]) -> None:
        if not dialog.winfo_exists():
            return
        search_button.configure(state=tk.NORMAL)
        _clear_results()
        if not results:
            status_label.configure(fg=_MUTED_COLOR, text="No matches found within range.")
            return
        status_label.configure(text="")
        # Two rows per result - system name on its own line, the body/ring/
        # stats indented below it - rather than one long combined line.
        # Squeezing system + body + ring + stats onto a single line meant
        # widening the whole dialog just to see the tail end of one row;
        # splitting the line in two fixes that without a wider window.
        for index, hotspot in enumerate(results):
            system_row = index * 2
            body_row = system_row + 1

            _add_copyable_row(results_frame, system_row, hotspot.system,
                              hotspot.system, "Copy system",
                              pady=(6 if index else 0, 0))

            body_text = (f"    {hotspot.body} ({hotspot.ring_name}) - "
                        f"{hotspot.hotspot_count}x, {hotspot.distance_ly:.1f} ly, "
                        f"reserve: {hotspot.reserve_level}")
            _add_copyable_row(results_frame, body_row, body_text,
                              hotspot.body, "Copy body", pady=(0, 2))

    def _show_error(message: str) -> None:
        if not dialog.winfo_exists():
            return
        search_button.configure(state=tk.NORMAL)
        _clear_results()
        status_label.configure(fg=_ERROR_COLOR, text=message)

    def _on_search() -> None:
        material = material_var.get().strip()
        if not material:
            status_label.configure(fg=_ERROR_COLOR, text="Enter a material to search for.")
            return
        if not reference_system:
            status_label.configure(fg=_ERROR_COLOR,
                                   text="Current system not yet known - wait for a journal event.")
            return
        try:
            max_distance = float(distance_var.get().strip())
        except ValueError:
            status_label.configure(fg=_ERROR_COLOR, text="Max distance must be a number.")
            return

        status_label.configure(fg=_MUTED_COLOR, text="Searching...")
        _clear_results()
        search_button.configure(state=tk.DISABLED)

        def _worker() -> None:
            try:
                results = spansh_client.search_ring_hotspots(
                    reference_system, material, max_distance, max_results=_MAX_RESULTS)
            except Exception:
                logger.exception("Spansh hotspot search failed")
                dialog.after(0, lambda: _show_error(
                    "Search failed - check your connection and try again (see the EDMC log)."))
                return
            dialog.after(0, lambda: _show_results(results))

        threading.Thread(target=_worker, daemon=True, name="WNTB-mining-spansh-search").start()

    search_button.configure(command=_on_search)

    tk.Button(dialog, text="Close", command=dialog.destroy).grid(
        row=6, column=0, columnspan=2, pady=(4, 8))

    dialog.bind("<Return>", lambda _e: _on_search())
    dialog.bind("<Escape>", lambda _e: dialog.destroy())
