"""Shared Tk helpers for building `plugin_app`/Settings-tab widgets — used by
every feature module (`powerplay.py`, `interdiction.py`, `landing.py`,
`autohonk.py`, `discovery.py`) and by `ui.py` itself.

Feature modules import this module, never `ui.py` — that's what keeps `ui.py`
from becoming the thing every feature reaches into (a circular import).
Each feature owns its own widgets
and Settings section; this module only holds the generic, content-agnostic
mechanics every one of them needs.
"""

from __future__ import annotations

WORK_IN_PROGRESS_NOTE = (
    "Work in progress: this feature is still being developed. Feedback, bug reports and ideas are very welcome - "
    "please open an issue at https://github.com/rwharpernc/wayward-nomads-toolbox/issues or find me in the "
    "Wayward Nomads squadron."
)
"""Shown at the foot of the Settings tab of every feature that is still taking shape."""

import logging
import os
import tkinter as tk
import tkinter.font as tkfont
from typing import List, Tuple

from config import appname, config
from theme import theme

plugin_name = os.path.basename(os.path.dirname(__file__))
logger = logging.getLogger(f"{appname}.{plugin_name}")

# Every label whose wraplength should track its frame's width - starting
# tight and growing to match the frame's real, already-established width
# means this plugin's own long lines (station/system/Power names - all
# externally-sourced, unbounded strings) are never themselves the reason
# EDMC's window grows. EDMC sizes its main window to whatever's widest among
# every plugin it's running - see the global EDMC-plugin-development
# instruction on bounding anything that can size the main window.
MIN_WRAP = 300

_wrap_labels: List[tk.Label] = []


def wrap_label(parent: tk.Frame, **kwargs) -> tk.Label:
    """A `tk.Label` whose `wraplength` is kept in sync with its containing
    frame's width (see `on_frame_configure`) - use this for any label whose
    text comes from the game/journal rather than this plugin's own fixed
    strings."""
    label = tk.Label(parent, wraplength=MIN_WRAP, justify=tk.LEFT, **kwargs)
    _wrap_labels.append(label)
    return label


def on_frame_configure(event: tk.Event) -> None:
    """Bind this to the top-level `plugin_app` frame's `<Configure>` -
    widens every registered `wrap_label` to match, never below `MIN_WRAP`."""
    wrap = max(MIN_WRAP, event.width)
    for label in _wrap_labels:
        label.configure(wraplength=wrap)


def bold_font(_widget: tk.Widget) -> tuple:
    """Bold variant of EDMC's default font, for a collapsible header title -
    `_widget` is unused (kept so call sites read naturally as "bold font for
    this widget") since TkDefaultFont is global, not per-widget; a plain
    tk.Label/Frame has no "font" option to read back in the first place."""
    try:
        base = tkfont.nametofont("TkDefaultFont")
        return (base.actual("family"), base.actual("size"), "bold")
    except tk.TclError:
        return ("TkDefaultFont", 9, "bold")


# --- Toggle-button coloring (shared by every feature's own main-panel quick-
# toggle button, and by ui.py's mode-select buttons) -----------------------

TOGGLE_ON_BG = "#2e7d32"
TOGGLE_ON_FG = "#ffffff"


def capture_toggle_off_colors(widget: tk.Button) -> Tuple[str, str]:
    """Call once, on a widget still in its natural (never-toggled) state, to
    learn the theme's own off-state bg/fg - so `apply_toggle_button_state`
    can restore exactly that instead of a hardcoded guess."""
    return widget.cget("background"), widget.cget("foreground")


def apply_toggle_button_state(widget: tk.Button, on: bool, off_colors: Tuple[str, str]) -> None:
    bg, fg = (TOGGLE_ON_BG, TOGGLE_ON_FG) if on else off_colors
    try:
        widget.configure(background=bg, foreground=fg, activebackground=bg, activeforeground=fg)
    except tk.TclError:
        pass


TOOLTIP_DELAY_MS = 500
TOOLTIP_WRAP = 280


def add_tooltip(widget: tk.Widget, text: str) -> None:
    """Shows `text` in a small popup next to `widget` after the pointer rests on
    it for TOOLTIP_DELAY_MS, and hides it on leave/click. The popup is its own
    borderless top-level window, so it never affects the size of EDMC's main
    window; fixed light colours keep it legible under every EDMC theme."""
    state = {"after": None, "tip": None}

    def hide(_event: object = None) -> None:
        if state["after"] is not None:
            widget.after_cancel(state["after"])
            state["after"] = None
        if state["tip"] is not None:
            state["tip"].destroy()
            state["tip"] = None

    def show() -> None:
        state["after"] = None
        try:
            tip = tk.Toplevel(widget)
            tip.wm_overrideredirect(True)
            tip.wm_geometry(f"+{widget.winfo_rootx() + 8}+{widget.winfo_rooty() + widget.winfo_height() + 4}")
            tk.Label(
                tip, text=text, justify=tk.LEFT, wraplength=TOOLTIP_WRAP, background="#ffffe0",
                foreground="#000000", relief=tk.SOLID, borderwidth=1, padx=4, pady=2,
            ).pack()
            state["tip"] = tip
        except tk.TclError:
            state["tip"] = None

    def schedule(_event: object = None) -> None:
        hide()
        state["after"] = widget.after(TOOLTIP_DELAY_MS, show)

    widget.bind("<Enter>", schedule, add="+")
    widget.bind("<Leave>", hide, add="+")
    widget.bind("<ButtonPress>", hide, add="+")
    widget.bind("<Destroy>", hide, add="+")


def collapsible_section(parent: tk.Frame, title: str, config_key: str, default_collapsed: bool = True) -> tk.Frame:
    """A bold, click-to-toggle title (▸ collapsed / ▾ expanded) in row 0 of
    `parent`, with a body frame in row 1 that the caller builds its widgets
    into. The state is remembered in EDMC's config under `config_key`; with
    nothing saved yet the section starts collapsed (`default_collapsed`) -
    same convention as Boxel Survey's own title (boxel_survey.py) and ui.py's
    main-panel collapse."""
    collapsed = config.get_bool(config_key, default=default_collapsed)
    title_label = tk.Label(parent, font=bold_font(parent), cursor="hand2")
    title_label.grid(row=0, column=0, columnspan=3, sticky=tk.W)
    body = tk.Frame(parent)
    body.grid(row=1, column=0, columnspan=3, sticky=tk.W)

    def apply() -> None:
        title_label.config(text=f"{'▸' if collapsed else '▾'} {title}")
        (body.grid_remove if collapsed else body.grid)()

    def toggle(_event: tk.Event) -> None:
        nonlocal collapsed
        collapsed = not collapsed
        config.set(config_key, collapsed)
        apply()

    title_label.bind("<Button-1>", toggle)
    apply()
    return body


def copy_to_clipboard(widget: tk.Misc, text: str) -> bool:
    """Copies `text` to the OS clipboard via `widget`. The explicit
    `update()` after `clipboard_append` is required on some platforms/
    window managers for the clipboard-ownership handoff to actually take
    effect before focus moves elsewhere (e.g. back to the game window) -
    without it, pastes can silently grab stale content. Returns True on
    success."""
    try:
        widget.clipboard_clear()
        widget.clipboard_append(text)
        widget.update()
        return True
    except tk.TclError as exc:
        logger.warning("Clipboard copy failed: %s", exc)
        return False


_SEPARATOR_LIGHT = "#5a5f62"
_SEPARATOR_DARK = "#82878b"


def is_dark_theme() -> bool:
    """Whether Dark or Transparent theme is active - same check
    missions_ui.py's own private `_is_dark_theme()` uses; generalized here
    since `add_separator` below is the first cross-feature use of it."""
    return theme.active not in (None, theme.THEME_DEFAULT)


def add_separator(parent: tk.Frame, row: int) -> int:
    """A thin horizontal rule marking the boundary between two features'
    sections stacked in the same mode/always frame (see `ui.py`'s
    `create_plugin_app`) - call before every feature after the first, never
    before the first. Colour is set directly from a static light/dark
    choice, not read back through `theme.update()`/a themed widget's own
    background - sidesteps the theme.update()-is-a-no-op-until-theme.current-
    is-populated pitfall documented in `ui.py`'s own `create_plugin_app` and
    `inventory_panel.py`'s bar-track-colour fix, so this never needs a retry
    to show the right colour. Returns `row + 1`."""
    sep = tk.Frame(parent, height=1, borderwidth=0)
    sep.configure(background=_SEPARATOR_DARK if is_dark_theme() else _SEPARATOR_LIGHT)
    sep.grid(row=row, column=0, columnspan=3, sticky="ew", pady=6)
    return row + 1


def apply_theme_deep(widget: tk.Misc) -> None:
    """EDMC's own `theme.update()` only recolors `widget` itself plus its
    *direct* children - not enough once a feature's own widgets nest a
    button/label inside a wrapper Frame of their own (several levels below
    the mode frame `theme.update()` is called on once in `ui.py`). Walks
    the whole subtree instead; use it after building any nested widget
    structure whose leaves wouldn't otherwise get themed."""
    try:
        theme.update(widget)  # type: ignore[arg-type]
    except Exception:
        logger.debug("theme.update() failed for %r", widget, exc_info=True)

    for child in widget.winfo_children():
        apply_theme_deep(child)
