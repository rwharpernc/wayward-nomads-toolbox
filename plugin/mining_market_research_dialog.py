"""
The Market Research window: which markets in a system buy what you could surface-mine there.

Opened from the Mining Book. The commodities come from the commander's own records (mining_market_research.plan); the
markets come from one Spansh request for the system (mining_spansh_client.search_system_stations). Opt-in: it uses the
"Enable Spansh best price finder" setting, since it asks the same service for the same kind of data, and it sends only the
system's name. The request runs on a background thread, like the other Spansh dialogs.
"""
import logging
import os
import threading
import tkinter as tk
from typing import Optional, Sequence

from config import appname, config

from . import mining_ground
from . import mining_hotspots as hotspots
from . import mining_market_research as research
from . import mining_spansh_client as spansh_client
from . import panelkit
from .mining_body_survey import SurveyedBody
from .uikit import palette
from .uikit import style as ui_style

plugin_name = os.path.basename(os.path.dirname(__file__))
logger = logging.getLogger(f"{appname}.{plugin_name}")

CONFIG_ENABLED = "wntb_mining_spansh_price_finder_enabled"
"""The same switch as the price finder (Settings > Mining)."""

_BUYERS_SHOWN = 4
_RESULTS_HEIGHT_LINES = 22
_MARKET_DAYS = 30


def enabled() -> bool:
    return config.get_bool(CONFIG_ENABLED, default=False)


def format_report(system: str, results: Sequence[research.CommodityResult], plan: research.Plan,
                  station_count: int, counted: int) -> str:
    """The text the window shows (and Copy copies)."""
    lines = [f"{system}: {station_count} market{'s' if station_count != 1 else ''} with prices updated in the last "
             f"{_MARKET_DAYS} days (fleet carriers left out)."]
    if counted > spansh_client.SYSTEM_STATIONS_PAGE:
        lines.append(f"Spansh counts {counted} stations here and only the first {spansh_client.SYSTEM_STATIONS_PAGE} were asked for, "
                     "so some markets may be missing.")
    lines.append("")
    if not results:
        lines.append("Nothing to look for yet. Save a hotspot in this system, record deposits on its scanned bodies, or add "
                     "commodities in the box above.")
    for result in results:
        lines.append(f"{result.candidate.name}  ({'; '.join(result.candidate.reasons)})")
        if not result.buyers:
            lines.append("    No market in this system buys it right now.")
        for buyer in result.buyers[:_BUYERS_SHOWN]:
            bits = [f"{buyer.price:,} cr", f"demand {buyer.demand:,}"]
            age = buyer.days_old()
            if age is not None:
                bits.append("updated today" if age == 0 else f"updated {age} d ago")
            if buyer.distance_ls is not None:
                bits.append(f"{buyer.distance_ls:,.0f} ls")
            pads = research.pad_text(buyer)
            if pads:
                bits.append(pads)
            lines.append(f"    {buyer.station} ({buyer.station_type}): " + ", ".join(bits))
        if len(result.buyers) > _BUYERS_SHOWN:
            lines.append(f"    and {len(result.buyers) - _BUYERS_SHOWN} more")
        lines.append("")
    if plan.skipped:
        lines.append("Not a commodity Spansh knows, so left out: " + ", ".join(plan.skipped))
    lines.append("Built from what you have saved, not from what the bodies hold: the game does not say which commodities a "
                 "body carries. Prices are the last ones players uploaded.")
    return "\n".join(lines)


def open_dialog(parent: tk.Misc, system: str, surveyed: Sequence[SurveyedBody], rates: mining_ground.OwnRates) -> None:
    """Opens the window for `system`. `surveyed` are the landable bodies scanned there this session (empty for another
    system) and `rates` the commander's own rates."""
    root = parent.winfo_toplevel()
    dialog = tk.Toplevel(root)
    ui_style.skin(dialog)
    dialog.title("Market Research")
    dialog.resizable(True, True)
    dialog.transient(root)
    dialog.columnconfigure(0, weight=1)
    dialog.rowconfigure(3, weight=1)

    tk.Label(dialog, text=f"Markets in {system} that buy what you could mine there", anchor=tk.W).grid(
        row=0, column=0, columnspan=2, sticky="w", padx=8, pady=(8, 2))
    extra_row = tk.Frame(dialog)
    extra_row.grid(row=1, column=0, columnspan=2, sticky="ew", padx=8, pady=2)
    extra_row.columnconfigure(1, weight=1)
    tk.Label(extra_row, text="Also check:").grid(row=0, column=0, sticky="w")
    extra_var = tk.StringVar()
    tk.Entry(extra_row, textvariable=extra_var).grid(row=0, column=1, sticky="ew", padx=6)
    search_button = tk.Button(extra_row, text="Search")
    search_button.grid(row=0, column=2)
    status = tk.Label(dialog, text="", anchor=tk.W, justify=tk.LEFT, wraplength=560)
    status.grid(row=2, column=0, columnspan=2, sticky="w", padx=8)
    text = tk.Text(dialog, wrap="word", width=78, height=_RESULTS_HEIGHT_LINES, state="disabled",
                   bg=palette.PANE, fg=palette.TEXT, relief="flat", padx=8, pady=6)
    text.grid(row=3, column=0, sticky="nsew", padx=(8, 0), pady=4)
    scroll = tk.Scrollbar(dialog, orient="vertical", command=text.yview)
    scroll.grid(row=3, column=1, sticky="ns", pady=4)
    text.configure(yscrollcommand=scroll.set)
    buttons = tk.Frame(dialog)
    buttons.grid(row=4, column=0, columnspan=2, pady=(2, 8))
    report = {"text": ""}
    tk.Button(buttons, text="Copy", command=lambda: panelkit.copy_to_clipboard(dialog, report["text"])).pack(side=tk.LEFT, padx=4)
    tk.Button(buttons, text="Close", command=dialog.destroy).pack(side=tk.LEFT, padx=4)

    def show(body: str) -> None:
        report["text"] = body
        text.configure(state="normal")
        text.delete("1.0", "end")
        text.insert("1.0", body)
        text.configure(state="disabled")

    def search() -> None:
        saved = hotspots.hotspot_repository.all()
        grounds = [g for g in (mining_ground.classify(b.planet_class, b.volcanism) for b in surveyed) if g]
        chosen = research.plan(system, saved, grounds, rates, research.split_names(extra_var.get()))
        status.configure(fg=palette.MUTED, text="Asking Spansh for the markets in this system...")
        search_button.configure(state=tk.DISABLED)

        def worker() -> None:
            try:
                stations, counted = spansh_client.search_system_stations(system, _MARKET_DAYS)
            except Exception:
                logger.exception("Spansh system market search failed")
                dialog.after(0, lambda: failed())
                return
            dialog.after(0, lambda: done(chosen, stations, counted))

        def failed() -> None:
            if dialog.winfo_exists():
                search_button.configure(state=tk.NORMAL)
                status.configure(fg=palette.DANGER, text="The search failed - check your connection and try again (see the EDMC log).")

        def done(chosen_plan: research.Plan, stations: list, counted: int) -> None:
            if not dialog.winfo_exists():
                return
            search_button.configure(state=tk.NORMAL)
            status.configure(text="")
            results = research.match(chosen_plan.candidates, stations)
            show(format_report(system, results, chosen_plan, len(stations), counted))

        threading.Thread(target=worker, daemon=True, name="WNTB-mining-market-research").start()

    search_button.configure(command=search)
    dialog.bind("<Escape>", lambda _e: dialog.destroy())
    dialog.bind("<Return>", lambda _e: search())
    search()
