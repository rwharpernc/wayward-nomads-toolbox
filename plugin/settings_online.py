"""Settings → General → Online lookups: every switch that lets WNTB contact another service, with whether it is on now and where to change it.

WNTB reads your journal and files on your own computer; anything that asks the internet is its own opt-in switch on the page of the feature it belongs
to (the full list with what each sends is in docs/guide/internet-and-privacy.md). The switches are spread over a dozen pages, so this page lists them in one
place. It is a read-out of what is saved, not another set of controls: change a switch where it lives. A new online switch is added to `LOOKUPS`;
`tests/test_settings_online.py` fails when an entry names a setting the code does not have.
"""
from __future__ import annotations

import tkinter as tk
from typing import List, Tuple

import myNotebook as nb
from config import config

# (what it does, who it asks, the saved setting, on when never changed, where to change it)
LOOKUPS: Tuple[Tuple[str, str, str, bool, str], ...] = (
    ("BGS tick detection (every minute)", "tick.infomancer.uk", "wntb_bgs_tick_enabled", True, "BGS"),
    ("Exploration Value: Earth-like world rarity", "Spansh", "wntb_exploration_value_elw_rarity_enabled", False, "Exploration > Exploration Value"),
    ("Exploration Value: EDSM upload status", "EDSM", "wntb_exploration_value_edsm_upload_enabled", False, "Exploration > Exploration Value"),
    ("Boxel Survey: skip systems anyone has visited", "EDSM", "wntb_boxel_skip_edsm_visited", False, "Exploration > Boxel Survey"),
    ("Boxel Survey: skip systems fully scanned", "EDSM", "wntb_boxel_skip_edsm_scanned", False, "Exploration > Boxel Survey"),
    ("Boxel Survey: confirm off-sequence arrivals", "EDSM", "wntb_boxel_confirm_alias_arrival", False, "Exploration > Boxel Survey"),
    ("Region Sweep: skip systems anyone has visited", "EDSM", "wntb_boxel_sweep_skip_edsm_visited", False, "Exploration > Boxel Survey"),
    ("Region Sweep: find more nearby cubes", "EDSM", "wntb_boxel_sweep_auto_discover", False, "Exploration > Boxel Survey"),
    ("Nearest place to land", "Spansh", "wntb_landing_finder_allowed", False, "Exploration > Nearest place to land"),
    ("Mining: nearby hotspot finder", "Spansh", "wntb_mining_spansh_hotspot_finder_enabled", False, "Mining"),
    ("Mining: best price finder", "Spansh", "wntb_mining_spansh_price_finder_enabled", False, "Mining"),
    ("Mining: ring reserve lookup", "EDSM", "wntb_mining_edsm_reserve_lookup_enabled", False, "Mining"),
    ("Trade: routes, prices and best picks", "Spansh", "wntb_trade_lookups_enabled", False, "Trade"),
    ("System targets: bodies other commanders scanned", "EDSM", "wntb_targets_online", False, "Overlays > System targets"),
    ("System targets: life and points of interest others found", "Spansh", "wntb_targets_known", False, "Overlays > System targets"),
    ("Route overlay: systems EDSM does not know", "EDSM", "wntb_route_edsm", False, "Overlays > Route"),
    ("Colonization: share progress and deliveries", "Raven Colonial", "wntb_rcc_enabled", False, "Colonization"),
    ("System name suggestions while typing", "Spansh", "wntb_system_suggest_spansh", False, "General > Window"),
    ("Download and install updates", "GitHub", "wntb_auto_update", False, "General > Updates"),
)

# Lookups with no switch because they run only when a button is pressed, listed so the page is the whole picture.
BUTTON_ONLY: Tuple[Tuple[str, str], ...] = (
    ("Rare Goods Finder window and the Codex \"Not found\" tab (they ask when you open them, with no switch)", "Spansh and Canonn"),
    ("Find Nearest POI (Exploration panel)", "edastro.com GEC and Canonn"),
    ("Where to buy, Find sources, the Raven Colonial menu, Report an issue", "Spansh, Raven Colonial, GitHub (your browser)"),
)


def states() -> List[Tuple[str, str, bool, str]]:
    """(what, service, on now, where) for every lookup, from what is saved."""
    return [(what, service, bool(config.get_bool(key, default=default)), where) for what, service, key, default, where in LOOKUPS]


def build_settings(notebook: nb.Notebook) -> None:
    frame = nb.Frame(notebook)
    frame.columnconfigure(0, weight=1)
    notebook.add(frame, text="Online lookups")
    nb.Label(frame, text="Online lookups", font=("TkDefaultFont", 9, "bold")).grid(row=0, column=0, sticky=tk.W, padx=10, pady=(10, 4))
    nb.Label(
        frame,
        text=("WNTB reads your journal and game files on this computer. Everything that asks another service is a switch of its own, on the page of the feature it "
              "belongs to, and this page lists them all. It only shows what is saved now; change a switch on the page named at the end of its line. What each one sends "
              "is in the guide under internet and privacy."),
        wraplength=440, justify=tk.LEFT,
    ).grid(row=1, column=0, sticky=tk.W, padx=10, pady=(0, 6))
    table = tk.Frame(frame)
    table.grid(row=2, column=0, sticky=tk.W, padx=10)
    for column, heading in enumerate(("", "Lookup", "Asks", "Where to change it")):
        nb.Label(table, text=heading, font=("TkDefaultFont", 9, "bold")).grid(row=0, column=column, sticky=tk.W, padx=(0, 10))
    for row, (what, service, on, where) in enumerate(states(), 1):
        nb.Label(table, text="On" if on else "Off", foreground="#c07000" if on else "#2e7d32", width=4, anchor=tk.W).grid(row=row, column=0, sticky=tk.W, padx=(0, 10))
        nb.Label(table, text=what).grid(row=row, column=1, sticky=tk.W, padx=(0, 10))
        nb.Label(table, text=service).grid(row=row, column=2, sticky=tk.W, padx=(0, 10))
        nb.Label(table, text=where).grid(row=row, column=3, sticky=tk.W)
    nb.Label(frame, text="Only when you open or press something (no switch):", font=("TkDefaultFont", 9, "bold")).grid(row=3, column=0, sticky=tk.W, padx=10, pady=(10, 2))
    for offset, (what, service) in enumerate(BUTTON_ONLY):
        nb.Label(frame, text=f"{what} ({service})", wraplength=440, justify=tk.LEFT).grid(row=4 + offset, column=0, sticky=tk.W, padx=10)
    nb.Label(frame, text="").grid(row=4 + len(BUTTON_ONLY), column=0, pady=4)
