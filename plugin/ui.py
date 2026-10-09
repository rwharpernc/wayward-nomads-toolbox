"""Tkinter UI for WNTB: main-window mode-switching panel and the Settings
tab.

This file is deliberately a thin orchestrator, not a place where feature
widgets get built — each feature module (`powerplay.py`, `interdiction.py`,
`landing.py`, `autohonk.py`, `discovery.py`, and shared `overlay.py`) owns
its own main-panel widgets and Settings-tab section, per this shared
feature-module contract:

- `PANEL_PLACEMENT` (module attribute): a mode key (build into that mode's
  frame), `"always"` (build once, outside any mode frame), or `None`
  (Settings-tab-only, no main-panel widget).
- `build_panel(parent)` (only when `PANEL_PLACEMENT is not None`)
- `build_settings(notebook)` / `save_settings()`
- `handle_event(entry, cmdr, system, station, state)` — called from
  `load.py`, not from here.

This module never reaches into a feature module's internals beyond calling
those functions — new modes/features register themselves in `FEATURES`
below and ui.py never needs to change to accommodate them.
"""

from __future__ import annotations

import logging
import os
from typing import Callable, Dict, List, Optional, Tuple

import tkinter as tk
from tkinter import ttk

import myNotebook as nb
from config import appname, config
from theme import theme
from ttkHyperlinkLabel import HyperlinkLabel

from . import (
    __version__, autohonk, bgs_panel, boxel_survey, canonn_poi_panel, codex_completionist_panel, colonisation_panel, discovery,
    exploration_value, gec_poi_panel, interdiction, inventory_panel, landing, mining_panel, missions,
    notable, organic_scan_panel, overlay, panelkit, powerplay, screenshots, ship_builds_panel,
    game_mode, session_credits,
)
from .update import CONFIG_AUTO_UPDATE, RELEASES_PAGE_URL

plugin_name = os.path.basename(os.path.dirname(__file__))
logger = logging.getLogger(f"{appname}.{plugin_name}")

# Every feature module contributing main-panel widgets and/or a Settings
# tab. Order here is Settings-tab order; main-panel placement is driven by
# each module's own PANEL_PLACEMENT.
FEATURES = (
    powerplay, missions,
    # Exploration mode's own display order: the
    # frequently-glanced readouts/lookups first, Codex Completionist above
    # Boxel Survey (the largest single feature here, collapsed by default),
    # and Auto-Honk/Discovery Alerts last, side by side - see
    # _SIDE_BY_SIDE_PAIRS below, which is why they must stay adjacent here.
    exploration_value, organic_scan_panel, gec_poi_panel, canonn_poi_panel,
    codex_completionist_panel, boxel_survey, autohonk, discovery, notable,
    screenshots,
    inventory_panel, ship_builds_panel, colonisation_panel,
    mining_panel,
    bgs_panel,
    interdiction, landing,
)

# Feature pairs built into a single shared row (side by side) instead of
# each getting its own full-width row - only Auto-Honk/Discovery Alerts
# (the only pair so far): both are just a single toggle button (plus,
# for Discovery, a short status line), narrow enough that stacking them
# wastes vertical space. Keyed by the first module in the pair; both must
# stay adjacent in FEATURES above for this to take effect.
_SIDE_BY_SIDE_PAIRS = {autohonk: discovery}

CONFIG_COLLAPSED = "wntb_main_collapsed"
CONFIG_PANEL_MODE = "wntb_active_panel_mode"
CONFIG_FIT_HEIGHT = "wntb_fit_window_height"
_DEFAULT_FIT_HEIGHT = True

# (mode key, button label) - order here is left-to-right button order.
# A mode with no feature module registered for it just shows a placeholder.
PANEL_MODES: Tuple[Tuple[str, str], ...] = (
    ("powerplay", "Powerplay"),
    ("bgs", "BGS"),
    ("exploration", "Exploration"),
    ("mining", "Mining"),
    ("missions", "Missions"),
    ("fieldops", "Field Ops"),
)
# Short text for the mode-select buttons - EDMC's main window is small and shared
# with every other plugin - with the full label plus a one-line description (_MODE_TOOLTIPS) as the tooltip.
_MODE_BUTTON_TEXT = {
    "powerplay": "P.P.", "bgs": "BGS", "exploration": "EXP", "mining": "MIN", "missions": "MSN", "fieldops": "OPS",
}
_MODE_TOOLTIPS = {
    "powerplay": "Powerplay - merits and Control Points you earn for your Power, and the rare goods finder",
    "bgs": "BGS - faction states in the Background Simulation, and what your own activity does to them",
    "exploration": "Exploration - auto-honk, first-discovery alerts, boxel survey, scan values, exobiology help and Codex tally",
    "mining": "Mining - space and surface (SRV) mining, and your own catalogue of mining hotspots",
    "missions": "Missions - every mission you have in one view, with kill-progress bars for massacres",
    "fieldops": "Field Ops - screenshots, backpack/locker/cargo, saved ship builds and colonisation sites",
}
_DEFAULT_PANEL_MODE = PANEL_MODES[0][0]
_MODE_KEYS = {key for key, _ in PANEL_MODES}

_UPDATED_COLOR = "#2e7d32"
_UPDATED_MESSAGE_DURATION_MS = 15_000

_frame: Optional[tk.Frame] = None
_title_label: Optional[tk.Label] = None
_version_label: Optional[HyperlinkLabel] = None
_collapsed: bool = False
_collapsible_widgets: List[tk.Widget] = []

_panel_mode: str = _DEFAULT_PANEL_MODE
_mode_buttons: Dict[str, tk.Button] = {}
_mode_frames: Dict[str, tk.Frame] = {}
_mode_holder: Optional[tk.Frame] = None
_always_frame: Optional[tk.Frame] = None
_toggle_off_colors: Tuple[str, str] = ("", "")

_auto_update_var: Optional[tk.BooleanVar] = None
_fit_height_var: Optional[tk.BooleanVar] = None

PLUGIN_DISPLAY_NAME = "Wayward Nomads Toolbox (WNTB)"


def _stack_features(frame: tk.Frame, placement_key: str, placeholder_text: Optional[str] = None) -> None:
    """Builds every feature matching `placement_key` into its *own* child
    frame of `frame`, stacked top to bottom with a separator between
    consecutive features (never before the first) - each feature no longer
    needs to hand-pick a row number that avoids colliding with whichever
    siblings happen to share its placement key, the root cause of both a
    real collision bug and a "too jumbled, no visual separation between
    features" report earlier in this project's history. If nothing
    matches `placement_key` and `placeholder_text` is given (mode frames
    only, not "always"), shows that instead."""
    row = 0
    built = False
    features = list(FEATURES)
    i = 0
    while i < len(features):
        feature = features[i]
        if getattr(feature, "PANEL_PLACEMENT", None) != placement_key:
            i += 1
            continue
        if built:
            row = panelkit.add_separator(frame, row)

        partner = _SIDE_BY_SIDE_PAIRS.get(feature)
        if partner is not None and i + 1 < len(features) and features[i + 1] is partner:
            # Both members of the pair share one row instead of each
            # getting its own - see _SIDE_BY_SIDE_PAIRS's own docstring.
            pair_frame = tk.Frame(frame)
            pair_frame.grid(row=row, column=0, columnspan=3, sticky="ew")
            left_frame = tk.Frame(pair_frame)
            left_frame.grid(row=0, column=0, sticky="nw")
            feature.build_panel(left_frame)
            right_frame = tk.Frame(pair_frame)
            right_frame.grid(row=0, column=1, sticky="nw", padx=(6, 0))  # same 6px gap as the mode-select buttons
            partner.build_panel(right_frame)
            if partner is discovery:
                # Boxel Survey's "Random" button shares this button row (its
                # status line goes below Discovery's, in row 3); Boxel Survey
                # itself is built earlier in this stack.
                boxel_survey.build_random_button(
                    discovery.controller.button_row, discovery.controller.panel_frame, 3)
            row += 1
            built = True
            i += 2
            continue

        feature_frame = tk.Frame(frame)
        # sticky="ew" (not tk.W) plus the weighted middle column below: a
        # feature that only ever left-aligns its own widgets in column 0
        # looks identical either way, but a feature that centers something
        # via columnspan=3 (e.g. landing.py's pad diagram) needs this frame
        # actually stretched to the real content width for that centering
        # to mean anything - sticky=W left it pinned to its own minimum
        # natural size, so a spanning child had no spare room to center
        # within.
        feature_frame.columnconfigure(1, weight=1)
        feature_frame.grid(row=row, column=0, columnspan=3, sticky="ew")
        feature.build_panel(feature_frame)
        row += 1
        built = True
        i += 1
    if not built and placeholder_text:
        placeholder = panelkit.wrap_label(frame, text=placeholder_text)
        placeholder.grid(row=0, column=0, sticky=tk.W, pady=(4, 0))


def _mode_row_full_label_size(frame: tk.Frame) -> Tuple[int, int]:
    """(width, height) the mode-button row had when the buttons carried their full
    labels. EDMC sizes its main window to the widest row across every plugin, and
    that row used to be what set WNTB's width - shortening the labels
    (_MODE_BUTTON_TEXT) alone made the whole EDMC window open much narrower. Measured
    from a throwaway, never-displayed row of full-label buttons, so it follows the
    user's font/DPI and is fixed by the six labels in PANEL_MODES: nothing external
    can make it grow."""
    probe = tk.Frame(frame)
    for _key, label in PANEL_MODES:
        tk.Button(probe, text=label).pack(side=tk.LEFT, padx=(0, 6))
    probe.update_idletasks()
    size = (probe.winfo_reqwidth(), probe.winfo_reqheight())
    probe.destroy()
    return size


def create_plugin_app(parent: tk.Frame) -> tk.Frame:
    """Create the main-window frame for EDMC."""
    global _frame, _title_label, _version_label, _collapsed, _collapsible_widgets
    global _panel_mode, _toggle_off_colors, _always_frame, _mode_holder

    _frame = tk.Frame(parent)
    _frame.columnconfigure(1, weight=1)
    _frame.bind("<Configure>", panelkit.on_frame_configure)

    _collapsed = config.get_bool(CONFIG_COLLAPSED, default=True)
    _panel_mode = config.get_str(CONFIG_PANEL_MODE) or _DEFAULT_PANEL_MODE
    if _panel_mode not in _MODE_KEYS:
        _panel_mode = _DEFAULT_PANEL_MODE

    _title_label = tk.Label(_frame, text=_title_text(), font=panelkit.bold_font(_frame), cursor="hand2")
    _title_label.grid(row=0, column=0, sticky=tk.W, padx=(0, 4))
    _title_label.bind("<Button-1>", _toggle_collapsed)

    _version_label = HyperlinkLabel(
        _frame, text="", background=nb.Label().cget("background"), url=RELEASES_PAGE_URL, underline=True,
    )
    _version_label.grid(row=0, column=2, sticky=tk.E, padx=(4, 0))
    _version_label.grid_remove()

    # The row itself is held at the full-label size (see _mode_row_full_label_size) with
    # the short buttons left-justified inside it - no extra widget sits over the buttons.
    row_width, row_height = _mode_row_full_label_size(_frame)
    mode_row = tk.Frame(_frame, width=row_width, height=row_height)
    mode_row.pack_propagate(False)
    mode_row.grid(row=1, column=0, columnspan=3, sticky=tk.W, pady=(6, 0))
    mode_buttons_frame = tk.Frame(mode_row)
    mode_buttons_frame.place(relx=0, rely=0.5, anchor=tk.W)
    for key, label in PANEL_MODES:
        btn = tk.Button(mode_buttons_frame, text=_MODE_BUTTON_TEXT.get(key, label), command=lambda k=key: _on_panel_mode_click(k))
        panelkit.add_tooltip(btn, _MODE_TOOLTIPS.get(key, label))
        btn.pack(side=tk.LEFT, padx=(0, 6) if key != PANEL_MODES[-1][0] else (0, 0))
        _mode_buttons[key] = btn

    # Session strip (game mode, then credits this session) + a separator,
    # directly under the buttons and before any page content: visible in every
    # mode (it is not part of one), hidden only by the master collapse toggle.
    # Each line is its own module (game_mode.py, session_credits.py).
    session_strip = tk.Frame(_frame)
    session_strip.grid(row=2, column=0, columnspan=3, sticky=tk.W, pady=(6, 0))
    game_mode.build(session_strip, row=0)          # "You are in Solo mode."
    session_credits.build(session_strip, row=1)    # "Credits this session: +N cr earned"
    panelkit.add_separator(_frame, 3)
    session_rule = _frame.grid_slaves(row=3, column=0)[0]

    # Every mode's content lives in one holder whose WIDTH is pinned to the
    # mode-button row's and whose height follows whichever mode is showing.
    # EDMC sizes its main window to the widest row of every plugin, so without
    # this the window grew and shrank as you switched modes (each mode asked
    # for a different width). The holder never lets a mode ask for more than
    # the button row; content wraps to the available width instead. See
    # docs/TECHNICAL.md section 5.
    _mode_holder = tk.Frame(_frame)
    _mode_holder.grid(row=4, column=0, columnspan=3, sticky="ew")
    _mode_holder.columnconfigure(0, weight=1)
    _mode_holder.grid_propagate(False)
    try:
        mode_row.update_idletasks()
        _mode_holder.configure(width=mode_row.winfo_reqwidth(), height=1)
    except tk.TclError:
        _mode_holder.configure(width=1, height=1)
    mode_row.bind("<Configure>", lambda e: _mode_holder.configure(width=max(1, e.width)) if _mode_holder else None)

    for key, label in PANEL_MODES:
        mode_frame = tk.Frame(_mode_holder)
        mode_frame.columnconfigure(0, weight=1)
        mode_frame.grid(row=0, column=0, sticky="new")
        mode_frame.bind("<Configure>", lambda _e: _sync_mode_holder_height())
        _stack_features(mode_frame, key, placeholder_text=f"{label} — coming soon.")
        _mode_frames[key] = mode_frame

    # Mode-independent features ("always" placement, e.g. Landing) build
    # once into their own frame, gridded after every mode frame - visible
    # regardless of which mode is selected, gated only on the master
    # collapse toggle.
    _always_frame = tk.Frame(_frame)
    _always_frame.columnconfigure(1, weight=1)
    _always_frame.grid(row=5, column=0, columnspan=3, sticky="ew")
    _stack_features(_always_frame, "always")

    _collapsible_widgets = [mode_row, session_strip, session_rule, _mode_holder, _always_frame]
    _apply_collapsed_state()

    theme.update(_frame)
    _toggle_off_colors = panelkit.capture_toggle_off_colors(_mode_buttons[_DEFAULT_PANEL_MODE])
    _apply_panel_mode_button_colors()

    # This first theme.update(_frame) call happens while EDMC is still
    # building every plugin's panel (create_plugin_app() runs from
    # EDMarketConnector.py's _config_plugins(), which always runs before
    # its own first theme.apply() call - confirmed by reading EDMC's real
    # theme.py: theme.update(widget) is a documented no-op ("No need to
    # call this for widgets created in plugin_app()") that returns *before*
    # ever calling self.register(widget) whenever theme.current is still
    # empty, which it always is at this point). So this call above may
    # have silently registered nothing at all - inventory_panel.py's own
    # bar-track-colour fix hit exactly this for its own widgets
    # specifically; retrying here covers the rest
    # of WNTB's frame tree the same way, once theme.current is actually
    # populated. Uses apply_theme_deep(), not a second bare theme.update()
    # call - EDMC's own theme.update() only recolors *direct* children
    # even once registration succeeds (its own register() recurses the
    # whole subtree, but _update_widget() is only applied one level deep),
    # so a bare retry would still leave grandchildren (e.g. a mode's own
    # nested labels several frames deep) registered but never actually
    # recoloured until some later, not-guaranteed EDMC-triggered sweep.
    for delay_ms in (500, 1500, 3000, 6000):
        _frame.after(delay_ms, lambda: panelkit.apply_theme_deep(_frame))

    return _frame


def _title_text() -> str:
    return f"{'▸' if _collapsed else '▾'} {PLUGIN_DISPLAY_NAME}"


def _toggle_collapsed(_event: Optional[tk.Event] = None) -> None:
    global _collapsed
    _collapsed = not _collapsed
    config.set(CONFIG_COLLAPSED, _collapsed)
    _apply_collapsed_state()


def _apply_collapsed_state() -> None:
    if _title_label is not None:
        _title_label["text"] = _title_text()
    for widget in _collapsible_widgets:
        if _collapsed:
            widget.grid_remove()
        else:
            widget.grid()
    _apply_panel_mode_visibility()


def _sync_mode_holder_height() -> None:
    """The holder's width is pinned, so its height has to follow the visible
    mode's content by hand."""
    if _mode_holder is None or _panel_mode not in _mode_frames:
        return
    height = max(1, _mode_frames[_panel_mode].winfo_reqheight())
    if int(_mode_holder.cget("height")) != height:
        _mode_holder.configure(height=height)
    _schedule_window_fit()


_fit_pending = False


def _schedule_window_fit() -> None:
    """Asks for one window re-fit once Tk is idle; several height changes in a
    row (a mode switch redraws a few frames) collapse into a single resize."""
    global _fit_pending
    if _fit_pending or _frame is None:
        return
    _fit_pending = True
    _frame.after_idle(_fit_window_height)


def _fit_window_height() -> None:
    """Resizes EDMC's main window to the height its content needs, keeping its
    current width and position. Once a window has been given an explicit size
    (EDMC restores the last one, and dragging it does the same), Tk stops
    fitting it to its content, so switching to a taller mode or expanding a
    section left the bottom cut off until the window was dragged taller; this
    does that automatically, and shrinks it back when the content gets shorter.
    Left alone when the window is maximized/minimized or not yet on screen."""
    global _fit_pending
    _fit_pending = False
    if _frame is None or not config.get_bool(CONFIG_FIT_HEIGHT, default=_DEFAULT_FIT_HEIGHT):
        return
    try:
        top = _frame.winfo_toplevel()
        if top.state() != "normal" or not top.winfo_viewable():
            return
        top.update_idletasks()
        wanted = top.winfo_reqheight()
        if abs(wanted - top.winfo_height()) > 1:
            top.geometry(f"{top.winfo_width()}x{wanted}")
    except tk.TclError:
        logger.debug("Could not fit the EDMC window to its content", exc_info=True)


def _apply_panel_mode_visibility() -> None:
    if _collapsed:
        return
    for key, frame in _mode_frames.items():
        if key == _panel_mode:
            frame.grid()
        else:
            frame.grid_remove()
    _sync_mode_holder_height()


def _apply_panel_mode_button_colors() -> None:
    for key, btn in _mode_buttons.items():
        panelkit.apply_toggle_button_state(btn, key == _panel_mode, _toggle_off_colors)


def _on_panel_mode_click(mode: str) -> None:
    global _panel_mode
    if mode == _panel_mode:
        return
    _panel_mode = mode
    config.set(CONFIG_PANEL_MODE, _panel_mode)
    _apply_panel_mode_button_colors()
    _apply_panel_mode_visibility()


# --- Settings tab ----------------------------------------------------------

_SETTINGS_NOTEBOOK_STYLE = "WNTB.TNotebook"


def _style_settings_notebook() -> None:
    """The active ttk theme's default Notebook styling renders tabs with
    little to no visible border against the page background, so the tab
    strip doesn't read as a set of clickable tabs. Scoped to our own style
    name so this doesn't bleed into EDMC's own outer plugin-tabs notebook or
    any other plugin's notebook."""
    style = ttk.Style()
    style.configure(f"{_SETTINGS_NOTEBOOK_STYLE}.Tab", padding=(10, 4), borderwidth=1, relief=tk.RAISED)
    style.map(f"{_SETTINGS_NOTEBOOK_STYLE}.Tab", relief=[("selected", tk.SUNKEN)])


def create_prefs(parent: tk.Frame) -> nb.Frame:
    global _auto_update_var

    outer = nb.Frame(parent)
    outer.columnconfigure(0, weight=1)
    outer.rowconfigure(1, weight=1)

    HyperlinkLabel(
        outer, text=f"{PLUGIN_DISPLAY_NAME} v{__version__}", background=nb.Label().cget("background"),
        url=RELEASES_PAGE_URL, underline=True,
    ).grid(row=0, column=0, sticky=tk.W, padx=10, pady=(10, 6))

    notebook_border = tk.Frame(outer, relief=tk.GROOVE, borderwidth=2)
    notebook_border.grid(row=1, column=0, sticky=tk.NSEW, padx=10, pady=(0, 10))
    notebook_border.columnconfigure(0, weight=1)
    notebook_border.rowconfigure(0, weight=1)

    _style_settings_notebook()
    tabs = nb.Notebook(notebook_border, style=_SETTINGS_NOTEBOOK_STYLE)
    tabs.grid(row=0, column=0, sticky=tk.NSEW, padx=4, pady=4)

    _build_settings_tabs(tabs)

    return outer


class _SectionStack(nb.Frame):
    """A Settings page that stacks several features' settings one under another
    (with a rule between). Each feature's `build_settings(notebook)` builds a frame
    of its own and calls `notebook.add(frame, text=...)`; handing it one of these
    instead of a real notebook makes `add` stack that frame as a section. Frames are
    only ever placed with `grid` - never `pack` into an nb.Frame (the development
    guide's Settings rule)."""

    def __init__(self, parent: tk.Misc) -> None:
        super().__init__(parent)
        self.columnconfigure(0, weight=1)
        self._next_row = 1  # row 0 is nb.Frame's own gridded spacer

    def add(self, child: tk.Misc, **_options: object) -> None:
        if self._next_row > 1:
            ttk.Separator(self, orient=tk.HORIZONTAL).grid(
                row=self._next_row, column=0, sticky=tk.EW, padx=10, pady=4)
            self._next_row += 1
        child.grid(row=self._next_row, column=0, sticky=tk.EW)
        self._next_row += 1


def _settings_group(tabs: nb.Notebook, title: str, builders: List[Callable[[tk.Misc], None]]) -> None:
    """One top-level Settings tab holding its own row of tabs, so the strip across
    the top stays short instead of listing every feature."""
    page = nb.Frame(tabs)
    page.columnconfigure(0, weight=1)
    page.rowconfigure(1, weight=1)
    tabs.add(page, text=title)
    inner = nb.Notebook(page, style=_SETTINGS_NOTEBOOK_STYLE)
    inner.grid(row=1, column=0, sticky=tk.NSEW, padx=4, pady=4)
    for build in builders:
        build(inner)


def _stacked_page(title: str, builders: List[Callable[[tk.Misc], None]]) -> Callable[[tk.Misc], None]:
    """A builder that adds ONE tab called `title` holding all of `builders`' settings stacked."""
    def build(notebook: tk.Misc) -> None:
        stack = _SectionStack(notebook)
        notebook.add(stack, text=title)
        for build_section in builders:
            build_section(stack)
    return build


def _build_settings_tabs(tabs: nb.Notebook) -> None:
    """Top-level Settings tabs: General, then one per mode (modes with several
    features get a row of tabs inside), then the always-on overlays. Small related
    Exploration pages are merged: the three point-of-interest/codex pages into one,
    Auto-Honk, Discovery and Notable Bodies into one. Any feature with settings that is not listed
    here lands in "Other", so a new feature can never lose its Settings tab."""
    placed = set()

    def settings_of(*features) -> List[Callable[[tk.Misc], None]]:
        placed.update(features)
        return [feature.build_settings for feature in features]

    # General: Overlay Connection is the one shared host/port pair that Interdiction/
    # Landing/Discovery's own settings all point to.
    _settings_group(tabs, "General", [overlay.build_settings, _create_window_tab, _create_updates_tab])
    for feature in (powerplay, missions):
        for build in settings_of(feature):
            build(tabs)
    _settings_group(tabs, "Exploration", [
        *settings_of(exploration_value, organic_scan_panel),
        _stacked_page("Points of Interest", settings_of(gec_poi_panel, canonn_poi_panel, codex_completionist_panel)),
        *settings_of(boxel_survey),
        _stacked_page("Alerts", settings_of(autohonk, discovery, notable)),
    ])
    for feature in (mining_panel, bgs_panel):
        for build in settings_of(feature):
            build(tabs)
    _settings_group(tabs, "Field Ops", settings_of(screenshots, inventory_panel, ship_builds_panel, colonisation_panel))
    _settings_group(tabs, "Always On", settings_of(interdiction, landing))

    leftovers = [f for f in FEATURES if hasattr(f, "build_settings") and f not in placed]
    if leftovers:
        _settings_group(tabs, "Other", settings_of(*leftovers))


def _create_window_tab(notebook: nb.Notebook) -> None:
    """Window behaviour. Everything here is placed with `grid` (never `pack`) - an
    nb.Frame already holds a gridded child, and packing into it makes the whole
    WNTB Settings tab vanish (tests/test_settings_layout.py)."""
    global _fit_height_var

    frame = nb.Frame(notebook)
    frame.columnconfigure(0, weight=1)
    notebook.add(frame, text="Window")

    _fit_height_var = tk.BooleanVar(value=config.get_bool(CONFIG_FIT_HEIGHT, default=_DEFAULT_FIT_HEIGHT))
    nb.Checkbutton(
        frame, text="Resize the EDMC window's height to fit WNTB automatically", variable=_fit_height_var,
    ).grid(row=0, column=0, sticky=tk.W, padx=10, pady=(10, 2))
    nb.Label(
        frame,
        text=(
            "When you open EDMC, switch modes, or expand or collapse a section, the window grows or shrinks "
            "to show everything, so you don't have to drag it taller. Your width and window position are "
            "never changed. Turn this off if you prefer to set the height yourself."
        ),
        wraplength=440, justify=tk.LEFT,
    ).grid(row=1, column=0, sticky=tk.W, padx=10, pady=(0, 10))


def _create_updates_tab(notebook: nb.Notebook) -> None:
    global _auto_update_var

    frame = nb.Frame(notebook)
    frame.columnconfigure(0, weight=1)
    notebook.add(frame, text="Updates")

    _auto_update_var = tk.BooleanVar(value=config.get_bool(CONFIG_AUTO_UPDATE, default=False))
    nb.Checkbutton(
        frame, text="Automatically download and install updates", variable=_auto_update_var,
    ).grid(row=0, column=0, sticky=tk.W, padx=10, pady=(10, 2))

    HyperlinkLabel(
        frame, text="Release notes", background=nb.Label().cget("background"), url=RELEASES_PAGE_URL, underline=True,
    ).grid(row=1, column=0, sticky=tk.W, padx=10, pady=(2, 10))


def save_prefs() -> None:
    if _fit_height_var is not None:
        config.set(CONFIG_FIT_HEIGHT, bool(_fit_height_var.get()))
        if _fit_height_var.get() and _frame is not None:
            _schedule_window_fit()
    if _auto_update_var is not None:
        config.set(CONFIG_AUTO_UPDATE, bool(_auto_update_var.get()))

    overlay.save_settings()
    for feature in FEATURES:
        if hasattr(feature, "save_settings"):
            feature.save_settings()


# --- Update-status slot ("Updated to vX") ---------------------------------

_version_state: str = "idle"


def set_update_downloading(version: str) -> None:
    _set_version_state("downloading", f"Downloading v{version}…", "")


def set_update_downloaded(version: str) -> None:
    _set_version_state("downloaded", f"v{version} ready — restart EDMC", "")


def set_update_applied(version: str) -> None:
    _set_version_state("updated", f"Updated to v{version}", _UPDATED_COLOR)
    if _frame is not None:
        _frame.after(_UPDATED_MESSAGE_DURATION_MS, _clear_updated_state)


def _set_version_state(kind: str, text: str, color: str) -> None:
    global _version_state
    _version_state = kind
    if _version_label is None:
        return
    _version_label["text"] = text
    if color:
        _version_label["foreground"] = color
    if text:
        _version_label.grid()
    else:
        _version_label.grid_remove()


def _clear_updated_state() -> None:
    if _version_state == "updated":
        _set_version_state("idle", "", "")
