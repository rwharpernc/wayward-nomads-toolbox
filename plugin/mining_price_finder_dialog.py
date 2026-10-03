"""
"Find Best Price" dialog (both pages) - queries Spansh for the best-price
stations trading a commodity, closest/highest-price first. Opt-in via the
"Enable Spansh Best Price Finder" setting (see mining_panel.py); the
actual network call lives in mining_spansh_client.py, kept separate so
this module only owns the Tk form/threading/results side - same split as
mining_hotspot_finder_dialog.py/mining_spansh_client.py's ring-hotspot
search, which this is modeled on directly.

Inara's API has no commodity/market endpoint to call (its events are
almost entirely write-only commander-profile-sync), so this goes through
Spansh's station-search endpoint, the same way the ring-hotspot finder
does.

The search itself is a blocking network call, so it always runs on a
background thread (matching mining_hotspot_finder_dialog.py's pattern).
"""
import logging
import os
import threading
import tkinter as tk
from typing import Optional

from config import appname

from . import mining_location as location
from . import mining_spansh_client as spansh_client
from . import panelkit
from .uikit import palette
from .uikit import style as ui_style
from .uikit.widgets import Combobox

plugin_name = os.path.basename(os.path.dirname(__file__))
logger = logging.getLogger(f"{appname}.{plugin_name}")

_DEFAULT_MAX_DISTANCE_LY = 50
_MAX_RESULTS = 10
_ERROR_COLOR = palette.DANGER
_MUTED_COLOR = palette.MUTED
_RESULTS_MAX_HEIGHT = 240
"""Hard cap on the scrollable results area's height, in pixels - past
this it scrolls internally instead of growing the dialog. _MAX_RESULTS
results at two rows each can otherwise run taller than a reasonable
dialog height, especially on a small display."""


def open_price_finder_dialog(parent: tk.Misc,
                             suggested_commodities: Optional[list[str]] = None) -> None:
    reference_system = location.current_system()

    # Parented on parent's *toplevel*, not parent itself - same reasoning
    # as mining_hotspot_finder_dialog.py: a Toplevel parented directly on
    # mining_render.py's periodically-rebuilt content frame gets
    # destroyed along with it the next time that fires.
    root = parent.winfo_toplevel()
    dialog = tk.Toplevel(root)
    ui_style.skin(dialog)
    dialog.title("Find Best Price")
    dialog.resizable(True, True)
    dialog.transient(root)
    ui_style.grab_when_visible(dialog)
    dialog.columnconfigure(1, weight=1)

    system_text = reference_system or "(unknown - wait for a journal event)"
    tk.Label(dialog, text=f"Searching near: {system_text}", anchor=tk.W).grid(
        row=0, column=0, columnspan=2, sticky="w", padx=8, pady=(8, 4))

    tk.Label(dialog, text="Commodity*", anchor=tk.W).grid(row=1, column=0, sticky="w", padx=8, pady=4)
    commodity_var = tk.StringVar()
    # Editable, not "readonly": merges whatever the current run has
    # actually refined (passed in by the caller - the commodity a
    # commander is realistically about to search for right after mining
    # it) with spansh_client.KNOWN_MINING_COMMODITIES, so the dropdown
    # isn't empty before anything's been refined this run. Still not a
    # complete tradeable-commodity list (see that constant's docstring) -
    # typing a value not in either is still allowed.
    commodity_choices = sorted(set(suggested_commodities or []) | set(spansh_client.KNOWN_MINING_COMMODITIES))
    Combobox(dialog, textvariable=commodity_var, width=22,
                values=commodity_choices).grid(
        row=1, column=1, sticky="ew", padx=8, pady=4)

    tk.Label(dialog, text="Transaction", anchor=tk.W).grid(row=2, column=0, sticky="w", padx=8, pady=4)
    transaction_var = tk.StringVar(value="Sell")
    transaction_row = tk.Frame(dialog)
    transaction_row.grid(row=2, column=1, sticky="w", padx=8, pady=4)
    tk.Radiobutton(transaction_row, text="Sell (I'm selling)", variable=transaction_var,
                   value="Sell").pack(side=tk.LEFT)
    tk.Radiobutton(transaction_row, text="Buy (I'm buying)", variable=transaction_var,
                   value="Buy").pack(side=tk.LEFT)

    tk.Label(dialog, text="Max distance (ly)", anchor=tk.W).grid(row=3, column=0, sticky="w", padx=8, pady=4)
    distance_var = tk.StringVar(value=str(_DEFAULT_MAX_DISTANCE_LY))
    tk.Entry(dialog, textvariable=distance_var, width=24).grid(
        row=3, column=1, sticky="ew", padx=8, pady=4)

    search_button = tk.Button(dialog, text="Search")
    search_button.grid(row=4, column=0, columnspan=2, pady=(2, 4))

    status_label = tk.Label(dialog, text="", anchor=tk.W, justify=tk.LEFT, wraplength=520)
    status_label.grid(row=5, column=0, columnspan=2, sticky="w", padx=8)

    # Up to _MAX_RESULTS results at two rows each can run taller than the
    # dialog should grow to, so results scroll inside a fixed-height
    # Canvas rather than the dialog itself growing unbounded - same
    # Canvas/Scrollbar/content-frame-with-scrollregion approach as
    # mining_render.py's main panel, just without that module's width-
    # bounding rules (this is a plain Toplevel, not part of EDMC's own
    # window).
    results_canvas = tk.Canvas(dialog, highlightthickness=0, borderwidth=0)
    results_canvas.grid(row=6, column=0, sticky="ew", padx=(8, 0), pady=(2, 4))
    results_scrollbar = tk.Scrollbar(dialog, orient="vertical", command=results_canvas.yview)
    results_scrollbar.grid(row=6, column=1, sticky="nse", pady=(2, 4))
    results_canvas.configure(yscrollcommand=results_scrollbar.set)

    results_frame = tk.Frame(results_canvas)
    results_frame.columnconfigure(0, weight=1)
    results_window = results_canvas.create_window((0, 0), window=results_frame, anchor="nw")

    def _sync_results_scroll(_event=None) -> None:
        results_canvas.update_idletasks()
        bbox = results_canvas.bbox("all")
        content_height = (bbox[3] - bbox[1]) if bbox else 0
        results_canvas.configure(scrollregion=bbox, height=min(content_height, _RESULTS_MAX_HEIGHT))
        if content_height > _RESULTS_MAX_HEIGHT:
            results_scrollbar.grid()
        else:
            results_scrollbar.grid_remove()

    results_frame.bind("<Configure>", _sync_results_scroll)
    results_canvas.bind("<Configure>",
                        lambda event: results_canvas.itemconfigure(results_window, width=event.width))

    def _on_results_mousewheel(event) -> None:
        if event.num == 5 or event.delta < 0:
            results_canvas.yview_scroll(1, "units")
        else:
            results_canvas.yview_scroll(-1, "units")

    def _bind_results_mousewheel(_event=None) -> None:
        results_canvas.bind_all("<MouseWheel>", _on_results_mousewheel)
        results_canvas.bind_all("<Button-4>", _on_results_mousewheel)
        results_canvas.bind_all("<Button-5>", _on_results_mousewheel)

    def _unbind_results_mousewheel(_event=None) -> None:
        results_canvas.unbind_all("<MouseWheel>")
        results_canvas.unbind_all("<Button-4>")
        results_canvas.unbind_all("<Button-5>")

    results_canvas.bind("<Enter>", _bind_results_mousewheel)
    results_canvas.bind("<Leave>", _unbind_results_mousewheel)
    _sync_results_scroll()

    def _clear_results() -> None:
        for child in results_frame.winfo_children():
            child.destroy()

    def _add_copyable_row(row: int, display_text: str, copy_value: str, button_text: str, pady) -> None:
        row_var = tk.StringVar(value=display_text)
        entry = tk.Entry(results_frame, textvariable=row_var, width=70, state="readonly")
        entry.grid(row=row, column=0, sticky="ew", pady=pady)
        tk.Button(results_frame, text=button_text,
                  command=lambda: panelkit.copy_to_clipboard(dialog, copy_value)).grid(
            row=row, column=1, padx=(4, 0), pady=pady)

    def _show_results(transaction: str, results: list[spansh_client.StationPrice]) -> None:
        if not dialog.winfo_exists():
            return
        search_button.configure(state=tk.NORMAL)
        _clear_results()
        if not results:
            status_label.configure(fg=_MUTED_COLOR, text="No matches found within range.")
            return
        status_label.configure(text="")
        price_label = "Sell price" if transaction == "Sell" else "Buy price"
        quantity_label = "demand" if transaction == "Sell" else "supply"
        # Two rows per result - same layout reasoning as
        # mining_hotspot_finder_dialog.py's _show_results(): station/
        # system names vary too much in length for one combined line to
        # fit any fixed dialog width.
        for index, station in enumerate(results):
            system_row = index * 2
            body_row = system_row + 1

            _add_copyable_row(system_row, station.system, station.system,
                              "Copy system", pady=(6 if index else 0, 0))

            body_text = (f"    {station.station} ({station.station_type}) - "
                        f"{price_label}: {station.price:,} cr, {quantity_label} {station.quantity}, "
                        f"{station.distance_ly:.1f} ly")
            _add_copyable_row(body_row, body_text, station.station, "Copy station", pady=(0, 2))

    def _show_error(message: str) -> None:
        if not dialog.winfo_exists():
            return
        search_button.configure(state=tk.NORMAL)
        _clear_results()
        status_label.configure(fg=_ERROR_COLOR, text=message)

    def _on_search() -> None:
        commodity = commodity_var.get().strip()
        transaction = transaction_var.get()
        if not commodity:
            status_label.configure(fg=_ERROR_COLOR, text="Enter a commodity to search for.")
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
                results = spansh_client.search_best_price_stations(
                    reference_system, commodity, transaction, max_distance, max_results=_MAX_RESULTS)
            except Exception:
                logger.exception("Spansh price search failed")
                dialog.after(0, lambda: _show_error(
                    "Search failed - check your connection and try again (see the EDMC log)."))
                return
            dialog.after(0, lambda: _show_results(transaction, results))

        threading.Thread(target=_worker, daemon=True, name="WNTB-mining-spansh-price-search").start()

    search_button.configure(command=_on_search)

    tk.Button(dialog, text="Close", command=dialog.destroy).grid(
        row=7, column=0, columnspan=2, pady=(4, 8))

    dialog.bind("<Return>", lambda _e: _on_search())
    dialog.bind("<Escape>", lambda _e: dialog.destroy())
