"""Overlay appearance: the color scheme every WNTB overlay display follows, and the one fixed text size, padding and line spacing.

`overlay_style.py` is the model (palettes, and the size estimates that make a card fit its text). This module keeps the four
choice of scheme in EDMC's settings, hands every display the current `Look`, and builds the **Overlays -> Appearance** Settings tab,
whose **Show sample** button draws the Colonization card (the richest display) with the scheme as picked, where that display sits.
Text size, padding and line spacing are fixed (below): column alignment depends on estimates of the text width, and one size keeps it stable.
"""

from __future__ import annotations

import logging
import os
import threading
import time
import tkinter as tk
from typing import Optional

import myNotebook as nb
from config import appname, config

from . import overlay, overlay_style as style

plugin_name = os.path.basename(os.path.dirname(__file__))
logger = logging.getLogger(f"{appname}.{plugin_name}")

CFG_SCHEME = "wntb_overlay_scheme"
# Fixed on 2026-10-12: one text size, padding and line spacing for every display. Earlier versions saved choices under
# wntb_overlay_text_level, wntb_overlay_padding and wntb_overlay_line_spacing; they are no longer read.
LOCKED_TEXT_LEVEL = 1      # "Larger"
LOCKED_PADDING = style.DEFAULT_PADDING
LOCKED_SPACING = style.DEFAULT_SPACING

SAMPLE_SECONDS = 12


def _int(key: str, default: int) -> int:
    raw = config.get_str(key)
    try:
        return int(raw) if raw else default
    except ValueError:
        return default


def current_look() -> style.Look:
    """The look every display should draw with right now: the saved color scheme (or the default) at the fixed size and spacing."""
    return style.look_from_choices(
        config.get_str(CFG_SCHEME) or style.DEFAULT_SCHEME, LOCKED_TEXT_LEVEL, LOCKED_PADDING, LOCKED_SPACING)


# --- Settings tab --------------------------------------------------------------------------------------------------

_scheme_var: Optional[tk.StringVar] = None
_result_var: Optional[tk.StringVar] = None
_frame: Optional[tk.Misc] = None
_chips: dict = {}

_CHIP_ROLES = (("title", "Title"), ("text", "Text"), ("ok", "Covered"), ("warn", "Caution"), ("info", "Carrier"),
               ("danger", "Warning"), ("border", "Border"))


def typed_look() -> style.Look:
    """The look as currently chosen on the tab (not yet saved), or the saved one when the tab isn't built."""
    if _scheme_var is None:
        return current_look()
    return style.look_from_choices(_scheme_var.get(), LOCKED_TEXT_LEVEL, LOCKED_PADDING, LOCKED_SPACING)


def _refresh_chips(*_args) -> None:
    look = typed_look()
    for role, chip in _chips.items():
        try:
            chip.configure(bg="#" + look.color(role)[-6:])
        except tk.TclError:
            pass


def build_settings(notebook: tk.Misc) -> None:
    global _scheme_var, _result_var, _frame

    frame = nb.Frame(notebook)
    _frame = frame
    frame.columnconfigure(0, weight=1)
    notebook.add(frame, text="Appearance")

    nb.Label(
        frame,
        text=("How every WNTB overlay display looks, together: Colonization, Discovery, Notable Bodies, Interdiction, Landing, "
              "Inventory, Mining and the Screenshot message. Text size and spacing are fixed, so the columns "
              "stay aligned. The Interdiction warning keeps its red alert "
              "colors whatever the scheme."),
        wraplength=460, justify=tk.LEFT,
    ).grid(row=0, column=0, sticky=tk.W, padx=10, pady=(10, 8))

    look = current_look()
    _scheme_var = tk.StringVar(value=look.palette.name)

    grid = tk.Frame(frame)
    grid.grid(row=1, column=0, sticky=tk.W, padx=10, pady=2)
    for row, (label, var, values) in enumerate((("Color scheme", _scheme_var, list(style.SCHEMES)),)):
        nb.Label(grid, text=label + ":").grid(row=row, column=0, sticky=tk.W, padx=(0, 10), pady=2)
        tk.OptionMenu(grid, var, *values, command=_refresh_chips).grid(row=row, column=1, sticky=tk.W, pady=2)

    chips = tk.Frame(frame)
    chips.grid(row=2, column=0, sticky=tk.W, padx=10, pady=(8, 2))
    _chips.clear()
    for index, (role, name) in enumerate(_CHIP_ROLES):
        cell = tk.Frame(chips)
        cell.grid(row=0, column=index, padx=(0, 8))
        chip = tk.Label(cell, width=4, height=1, bg="#" + look.color(role)[-6:])
        chip.pack()
        nb.Label(cell, text=name).pack()
        _chips[role] = chip

    buttons = tk.Frame(frame)
    buttons.grid(row=3, column=0, sticky=tk.W, padx=10, pady=(8, 2))
    tk.Button(buttons, text="Show sample", command=_show_sample).pack(side=tk.LEFT)
    tk.Button(buttons, text="Reset scheme", command=_reset).pack(side=tk.LEFT, padx=(8, 0))
    _result_var = tk.StringVar(value="")
    nb.Label(frame, textvariable=_result_var, wraplength=460, justify=tk.LEFT).grid(
        row=4, column=0, sticky=tk.W, padx=10, pady=(2, 10))


def save_settings() -> None:
    if _scheme_var is None:
        return
    look = typed_look()
    config.set(CFG_SCHEME, look.palette.name)


def _reset() -> None:
    if _scheme_var is None:
        return
    _scheme_var.set(style.DEFAULT.palette.name)
    _refresh_chips()
    if _result_var is not None:
        _result_var.set("The default scheme is shown. Press OK in Settings to keep it.")


def _say(message: str) -> None:
    """Shows `message` under the buttons, from any thread."""
    try:
        if _frame is not None:
            _frame.after(0, lambda: _result_var.set(message) if _result_var is not None else None)
    except (tk.TclError, RuntimeError):
        pass   # the Settings window was closed


def _show_sample() -> None:
    """Draws the Colonization card with the scheme as picked, where that display sits, for a few seconds."""
    if _result_var is None:
        return
    look = typed_look()
    _result_var.set("Drawing the sample...")

    def worker() -> None:
        from . import colonisation_overlay as card, overlay_placement     # imported here: they import this module's package
        try:
            client = overlay.OverlayClient(overlay.load_config())
            sample = card.preview_card()
            block = card.block_rect(sample, card.DEFAULT_X, card.DEFAULT_Y, look)
            placed = overlay_placement.client_for("colonisation", client, block)
            slots = card.render(placed, sample, card.DEFAULT_X, card.DEFAULT_Y, look=look)
        except OSError as exc:
            _say(f"Could not reach the overlay: {exc}")
            return
        _say(f"Sample drawn for {SAMPLE_SECONDS} seconds.")
        time.sleep(SAMPLE_SECONDS)
        try:
            card.clear(placed, card.DEFAULT_X, card.DEFAULT_Y, slots)
        except OSError:
            pass

    threading.Thread(target=worker, name="WNTB-overlay-appearance-sample", daemon=True).start()
