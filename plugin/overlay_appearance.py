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

from . import overlay, overlay_fonts, overlay_native, overlay_placement, overlay_style as style

plugin_name = os.path.basename(os.path.dirname(__file__))
logger = logging.getLogger(f"{appname}.{plugin_name}")

CFG_SCHEME = "wntb_overlay_scheme"
CFG_OPACITY = "wntb_overlay_panel_opacity"      # percent; unset keeps each scheme's own (about 90%)
CFG_TEXT_SIZE = "wntb_overlay_text_size"     # 0 Default, 1 Larger (-1, the removed Smaller, reads as Default)
# One padding and line spacing for every display. Earlier versions saved choices under wntb_overlay_text_level,
# wntb_overlay_padding and wntb_overlay_line_spacing; they are no longer read. The text size is a new setting (CFG_TEXT_SIZE) that
# starts at "Larger", the size the displays were fixed at on 2026-10-12, so nobody's overlay changes until they choose.
DEFAULT_TEXT_SIZE = 1
LOCKED_PADDING = style.DEFAULT_PADDING
LOCKED_SPACING = style.DEFAULT_SPACING

SAMPLE_SECONDS = 12


def _int(key: str, default: int) -> int:
    raw = config.get_str(key)
    try:
        return int(raw) if raw else default
    except ValueError:
        return default


def saved_text_size() -> int:
    levels = [value for _label, value in style.TEXT_CHOICES]
    return max(min(levels), min(max(levels), _int(CFG_TEXT_SIZE, DEFAULT_TEXT_SIZE)))


def saved_opacity() -> Optional[int]:
    raw = config.get_str(CFG_OPACITY)
    try:
        return max(style.MIN_OPACITY, min(100, int(raw))) if raw else None
    except ValueError:
        return None


def current_look() -> style.Look:
    """The look every display should draw with right now: the saved color scheme and text size (or the defaults) at the fixed
    padding and spacing."""
    return style.look_from_choices(
        config.get_str(CFG_SCHEME) or style.DEFAULT_SCHEME, saved_text_size(), LOCKED_PADDING, LOCKED_SPACING, saved_opacity())


# --- Settings tab --------------------------------------------------------------------------------------------------

_scheme_var: Optional[tk.StringVar] = None
_size_var: Optional[tk.StringVar] = None
_opacity_var: Optional[tk.StringVar] = None
_corners_var: Optional[tk.StringVar] = None
_result_var: Optional[tk.StringVar] = None
_frame: Optional[tk.Misc] = None
_font_var: Optional[tk.StringVar] = None
_font_menu: Optional[tk.Misc] = None
_chips: dict = {}

_CHIP_ROLES = (("title", "Title"), ("text", "Text"), ("ok", "Covered"), ("warn", "Caution"), ("info", "Carrier"),
               ("danger", "Warning"), ("border", "Border"))


def typed_look() -> style.Look:
    """The look as currently chosen on the tab (not yet saved), or the saved one when the tab isn't built."""
    if _scheme_var is None:
        return current_look()
    size = style.value_for(style.TEXT_CHOICES, _size_var.get() if _size_var is not None else "", saved_text_size())
    opacity = style.value_for(style.OPACITY_CHOICES, _opacity_var.get() if _opacity_var is not None else "", style.DEFAULT_OPACITY)
    return style.look_from_choices(_scheme_var.get(), size, LOCKED_PADDING, LOCKED_SPACING, None if opacity == style.DEFAULT_OPACITY else opacity)


def _refresh_chips(*_args) -> None:
    look = typed_look()
    for role, chip in _chips.items():
        try:
            chip.configure(bg="#" + look.color(role)[-6:])
        except tk.TclError:
            pass


def build_settings(notebook: tk.Misc) -> None:
    global _scheme_var, _size_var, _opacity_var, _corners_var, _result_var, _frame

    frame = nb.Frame(notebook)
    _frame = frame
    frame.columnconfigure(0, weight=1)
    notebook.add(frame, text="Appearance")

    nb.Label(
        frame,
        text=("How every WNTB overlay display looks, together: Colonization, Discovery, Notable Bodies, Interdiction, Landing, "
              "Inventory, Mining, the Screenshot message and the cards (Route, System targets, Body info, Exobiology, Missions). Spacing is fixed so the "
              "columns stay aligned; the text size is yours to choose, and every box is sized from it. Panel opacity is how solid each box's background is "
              "(lower lets more of the game show through; the text stays solid). The Interdiction warning keeps its red alert colors whatever the scheme."),
        wraplength=460, justify=tk.LEFT,
    ).grid(row=0, column=0, sticky=tk.W, padx=10, pady=(10, 8))

    look = current_look()
    _scheme_var = tk.StringVar(value=look.palette.name)
    _size_var = tk.StringVar(value=style.label_for(style.TEXT_CHOICES, saved_text_size()))
    _opacity_var = tk.StringVar(value=style.label_for(style.OPACITY_CHOICES, saved_opacity() or style.DEFAULT_OPACITY))

    _corners_var = tk.StringVar(value=next(label for key, label, _r in overlay_native.CORNER_CHOICES if key == overlay_native.corner_key()))
    grid = tk.Frame(frame)
    grid.grid(row=1, column=0, sticky=tk.W, padx=10, pady=2)
    corner_rows = ((("Corners (built-in overlay)", _corners_var, [label for _k, label, _r in overlay_native.CORNER_CHOICES]),)
                   if overlay_native.supported() else ())
    for row, (label, var, values) in enumerate((("Color scheme", _scheme_var, list(style.SCHEMES)),
                                                ("Text size", _size_var, [label for label, _v in style.TEXT_CHOICES]),
                                                ("Panel opacity", _opacity_var, [label for label, _v in style.OPACITY_CHOICES])) + corner_rows):
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
    tk.Button(buttons, text="Reset appearance", command=_reset).pack(side=tk.LEFT, padx=(8, 0))
    _result_var = tk.StringVar(value="")
    nb.Label(frame, textvariable=_result_var, wraplength=460, justify=tk.LEFT).grid(
        row=4, column=0, sticky=tk.W, padx=10, pady=(2, 4))
    _build_font_section(frame, row=5)


def save_settings() -> None:
    if _scheme_var is None:
        return
    look = typed_look()
    config.set(CFG_SCHEME, look.palette.name)
    config.set(CFG_TEXT_SIZE, str(look.text_level))
    config.set(CFG_OPACITY, str(look.panel_opacity) if look.panel_opacity is not None else "")
    _save_font()
    if _corners_var is not None:
        overlay_native.save_corners(next((key for key, label, _r in overlay_native.CORNER_CHOICES if label == _corners_var.get()), overlay_native.DEFAULT_CORNERS))


# --- the overlay font ----------------------------------------------------------------------------------------------
# Which overlay draws decides whose font this is. With WNTB's built-in overlay it is WNTB's own: the fonts in WNTB's `fonts` folder (the bundled Source Sans 3 and any font file added), chosen and used
# straight away. With EDMCModernOverlay it is that program's font, one for every plugin, kept in its `preferred_fonts.txt`, and it takes effect when it starts again.

def _builtin() -> bool:
    return overlay_native.selected() == overlay_native.BUILTIN


def _fonts_folder() -> str:
    return overlay_native.fonts_folder() if _builtin() else overlay_fonts.fonts_dir(overlay_placement._plugins_dir())


def _font_labels() -> list:
    names = overlay_fonts.installed(_fonts_folder())
    return names if _builtin() else [overlay_fonts.DEFAULT_LABEL] + names


def _build_font_section(frame: tk.Misc, row: int) -> None:
    """Choose the font the overlay is drawn in, or add one from a file."""
    global _font_var, _font_menu
    box = tk.LabelFrame(frame, text="Overlay font")
    box.grid(row=row, column=0, sticky=tk.W + tk.E, padx=10, pady=(6, 10))
    if _builtin():
        explain = ("The font WNTB's built-in overlay draws in. It starts with Source Sans 3, which WNTB ships (lower case and easy to read). To use another, press Add font file... and pick a .ttf or .otf "
                   "(for example one from Google Fonts; keep its license with it): it is copied into WNTB's fonts folder and used at once. A font file you add stays through updates. "
                   "Other plugins' overlays, if you use EDMCModernOverlay too, keep that program's own font.")
    else:
        explain = ("The font is EDMCModernOverlay's, not WNTB's, so it applies to every plugin's text. Its default, Elite's cockpit font, has capital letters only, so species names show as "
                   "TUSSOCK PENNATIS. Pick a font with lower case letters, or add a .ttf or .otf file you downloaded (for example from Google Fonts; keep its license with it). It takes effect "
                   "when the overlay starts again (restart EDMC). WNTB's built-in overlay (Windows) has a font of its own, with its own folder.")
    nb.Label(box, text=explain, wraplength=440, justify=tk.LEFT).grid(row=0, column=0, columnspan=3, sticky=tk.W, padx=6, pady=(4, 6))
    if not os.path.isdir(_fonts_folder()):
        nb.Label(box, text="The fonts folder was not found (is EDMCModernOverlay installed?), so there is no font to choose here.", wraplength=440,
                 justify=tk.LEFT).grid(row=1, column=0, columnspan=3, sticky=tk.W, padx=6, pady=(0, 6))
        _font_var = None
        return
    labels = _font_labels()
    if _builtin():
        current = overlay_native.chosen_font()
        initial = current if current in labels else (overlay_fonts.BUNDLED if overlay_fonts.BUNDLED in labels else (labels[0] if labels else ""))
    else:
        current = overlay_fonts.current(_fonts_folder())
        initial = current if current in labels and not overlay_fonts.is_default(current) else overlay_fonts.DEFAULT_LABEL
    _font_var = tk.StringVar(value=initial)
    nb.Label(box, text="Font:").grid(row=1, column=0, sticky=tk.W, padx=6, pady=2)
    _font_menu = tk.OptionMenu(box, _font_var, *(labels or [""]))
    _font_menu.grid(row=1, column=1, sticky=tk.W, pady=2)
    tk.Button(box, text="Add font file...", command=_add_font).grid(row=1, column=2, sticky=tk.W, padx=(8, 0), pady=2)
    tk.Button(box, text="Open fonts folder", command=_open_fonts_folder).grid(row=2, column=1, columnspan=2, sticky=tk.W, pady=(0, 6))


def _refresh_font_menu() -> None:
    if _font_menu is None or _font_var is None:
        return
    menu = _font_menu["menu"]
    menu.delete(0, "end")
    for label in _font_labels():
        menu.add_command(label=label, command=lambda value=label: _font_var.set(value))


def _add_font() -> None:
    from tkinter import filedialog
    path = filedialog.askopenfilename(title="Choose a font file", filetypes=[("Font files", "*.ttf *.otf"), ("All files", "*.*")])
    if not path or _font_var is None:
        return
    name, problem = overlay_fonts.add_font(_fonts_folder(), path)
    if name is None:
        _say(problem)
        return
    _refresh_font_menu()
    _font_var.set(name)
    _say(f"Added {name} and chose it. Press OK in Settings to keep it" + ("." if _builtin() else ", then restart EDMC."))


def _open_fonts_folder() -> None:
    from . import screenshots
    screenshots.open_folder(_fonts_folder())


def _save_font() -> None:
    """Keeps the chosen font: for the built-in overlay in WNTB's settings (used at once), for EDMCModernOverlay in its own font list when it differs from what is there."""
    if _font_var is None:
        return
    choice = _font_var.get()
    if _builtin():
        overlay_native.save_font(choice)
        return
    wanted = "" if choice == overlay_fonts.DEFAULT_LABEL else choice
    folder = _fonts_folder()
    now = overlay_fonts.current(folder)
    if (wanted or overlay_fonts.DEFAULT_FONT).casefold() == (now or overlay_fonts.DEFAULT_FONT).casefold():
        return
    try:
        overlay_fonts.set_first(folder, wanted)
    except OSError:
        logger.warning("Could not write the overlay's font list", exc_info=True)


def _reset() -> None:
    if _scheme_var is None:
        return
    _scheme_var.set(style.DEFAULT.palette.name)
    if _size_var is not None:
        _size_var.set(style.label_for(style.TEXT_CHOICES, DEFAULT_TEXT_SIZE))
    if _opacity_var is not None:
        _opacity_var.set(style.label_for(style.OPACITY_CHOICES, style.DEFAULT_OPACITY))
    if _corners_var is not None:
        _corners_var.set(next(label for key, label, _r in overlay_native.CORNER_CHOICES if key == overlay_native.DEFAULT_CORNERS))
    _refresh_chips()
    if _result_var is not None:
        _result_var.set("The default scheme and size are shown. Press OK in Settings to keep it.")


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
