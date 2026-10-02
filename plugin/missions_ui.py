"""
Renders Missions mode's content: two detailed kill-stacking pages (Massacre
Space, Settlement Raids Ground), a handful of general pages covering every
other mission type, and one non-mission page (Community Goals) tacked onto
the same ◂/▸ nav — see _PAGE_ORDER/_PAGE_LABELS below. Mission pages are
separate rather than merged because kill-stacking math doesn't generalize
to missions that have no kill count - see mission_types.py for how a
mission lands on a given page.

Visual design notes:
- Text widgets are plain tk and inherit EDMC's configured theme colors by
  default, for accessibility and custom dark-theme text colors. A widget
  that sets its own `fg` at creation - before theme.update() ever sees it -
  keeps that color permanently instead: EDMC's theme system only ever
  auto-colors a widget's foreground if it didn't already have one at first
  registration (see the nav arrows' ACCENT color below).
- Kill progress is drawn as small Canvas bars; the drawn rectangles fully
  cover the canvas, so theming the canvas background is irrelevant.
- EDMC's panel is narrow and its width isn't under this plugin's control, so
  entries are laid out as stacked "cards" (a couple of short lines each)
  rather than a wide multi-column table: a fixed-column grid can't wrap, so
  on a narrow panel it either overflows or squashes unreadably. Each line is
  a small pack()-managed frame with left-anchored content on one side and
  right-anchored content on the other (see _line()) - unlike grid columns,
  the left side can wrap onto extra lines without disturbing the right side.

This module deliberately keeps its own dynamic wraplength recompute
(_WRAP/_WRAP_NAME derived from the Canvas's real measured width every
refresh) rather than using panelkit.wrap_label - that helper tracks the
*outer* main-window frame's width, which is correct for simple single-
column mode content but wrong here, since this content sits inside its own
scrollable Canvas sub-region whose width differs from the outer frame's.

No collapse header, no update-status row: both are redundant here - WNTB's
own master collapse (see ui.py) already gates this mode's whole frame, and
WNTB's own "Updated to vX" slot (also ui.py) already covers the one shared
self-updater every mode uses.
"""
import datetime as dt
import logging
import os
import random
import tkinter as tk
import tkinter.font as tkfont
from dataclasses import dataclass
from typing import Callable, Optional

from config import appname, config
from theme import theme
from ttkHyperlinkLabel import HyperlinkLabel

from .uikit import style as ui_style
from . import all_missions, community_goal_state, kill_missions, kill_tracker, mining_methods, mission_types
from .community_goal_state import CommunityGoal
from .kill_missions import KillMission, estimate_progress

plugin_name = os.path.basename(os.path.dirname(__file__))
logger = logging.getLogger(f"{appname}.{plugin_name}")

MISSION_CAP = 20
REFRESH_INTERVAL_MS = 60_000
"""How often the panel re-renders on its own, so mission expiry countdowns
stay live without waiting for a journal event."""

CONFIG_CURRENT_CATEGORY = "wntb_missions_current_category"

# Elite-style accent palette, tuned to read fine on both EDMC's Default
# (light, system-colored) and Dark/Transparent themes. Text colors are
# otherwise left to EDMC so they retain contrast with the selected theme;
# these are the deliberate exceptions (progress-bar fills, the nav arrows).
ACCENT = "#ff8c0d"      # Elite orange - progress-bar fill, nav arrows
OK = "#71c837"          # complete / totals - progress-bar fill

# The separator line and the progress-bar track are flat grays, so unlike the
# fill colors above they need their own light/dark variants: a single gray
# can't have enough contrast against both EDMC's near-black Dark theme
# (background "grey4") and its usually light-system-colored Default theme.
_SEPARATOR_LIGHT = "#5a5f62"
_SEPARATOR_DARK = "#82878b"
_BAR_TRACK_LIGHT = "#3c4043"
_BAR_TRACK_DARK = "#64686c"


def _is_dark_theme() -> bool:
    """True for EDMC's Dark/Transparent themes (near-black background), as
    opposed to Default (system colors, usually light)."""
    return theme.active not in (None, theme.THEME_DEFAULT)


def _separator_color() -> str:
    return _SEPARATOR_DARK if _is_dark_theme() else _SEPARATOR_LIGHT


def _bar_track_color() -> str:
    return _BAR_TRACK_DARK if _is_dark_theme() else _BAR_TRACK_LIGHT


BAR_WIDTH = 64
BAR_HEIGHT = 7

_WRAP = 280
"""Wrap width for lines that run the full panel width on their own.
Recalculated from the panel's real measured width at the top of every
redraw() (see _recompute_wrap_widths) - EDMC panel width varies with the
window, other docked plugins, and DPI scaling, so a fixed guess can't track
it. This starting value only matters before the canvas has been realized
once (see the winfo_width() > 1 guard in redraw())."""
_WRAP_NAME = 165
"""Wrap width for a name/faction label sharing a line with a right-anchored
value (kills, reward) - narrower than _WRAP to leave that value room.
Recalculated alongside _WRAP; see above."""
_WRAP_NAME_ALLOWANCE = _WRAP - _WRAP_NAME
"""How much narrower _WRAP_NAME stays than _WRAP once recalculated - the
room reserved for the right-anchored value sharing its line."""
_CONTENT_RIGHT_MARGIN = 8
"""Extra inset subtracted from the content frame's width (see
__on_canvas_resize), so right-anchored values (reward, kills, status) get a
sliver of breathing room from the scrollbar too, not just wrapped text."""
_URGENT_EXPIRY_MINUTES = 120
"""Below this many minutes left, a mission's expiry is shown as a warning."""

_NO_MISSIONS_MESSAGES = (
    "No missions. Go get some!",
    "Board's empty, CMDR.",
    "Nothing assigned. Time to hunt.",
    "All quiet. Go stir something up.",
    "No missions. The stars await.",
)
"""Flavor text for the "nothing assigned at all" empty state - picked at
random on each render, purely cosmetic. Per-category empty pages
(_render_current_page's no_missions_text) stay literal since they name the
specific category, which is useful information while paging through."""

_LINE_PAD = 2
"""Vertical gap between the stacked lines within one card - without it a
2-4 line card reads as one crushed paragraph instead of a legible group."""
_CARD_GAP = 4
"""Vertical padding on each side of the separator drawn between one card
(a faction stack, a mission) and the next, so entries read as distinct rows
instead of running together."""

_MASSACRE_CATEGORIES = (mission_types.MASSACRE_SPACE, mission_types.MASSACRE_GROUND)

_COMMUNITY_GOAL_PAGE = "community_goal"
"""Not a mission_types category - Community Goals aren't missions at all
(see community_goal_state.py) - but it pages the same way, so it's folded
into the same page order/label lookup rather than mission_types.CATEGORY_ORDER,
which stays strictly about classifying MissionAccepted events."""
_PAGE_ORDER: list[str] = mission_types.CATEGORY_ORDER + [_COMMUNITY_GOAL_PAGE]
_PAGE_LABELS: dict[str, str] = {**mission_types.CATEGORY_LABELS,
                                _COMMUNITY_GOAL_PAGE: "Community Goals"}

_MAX_PANEL_HEIGHT = 480
"""Cap on the panel's visible height in pixels before it becomes a scroll
region. EDMC's main window doesn't scroll on its own, so without a cap a
category with many missions (stacked cards run taller than a multi-column
table would) would force the whole EDMC window past screen height - see
the global EDMC-plugin-development instruction on bounding anything that
can size the main window. Below the cap the panel still just sizes to its
content - the scrollbar only appears once it's actually needed."""


def _load_current_category() -> str:
    value = config.get_str(CONFIG_CURRENT_CATEGORY)
    return value if value in _PAGE_ORDER else _PAGE_ORDER[0]


def _save_current_category(value: str) -> None:
    config.set(CONFIG_CURRENT_CATEGORY, value)


_content_bg = ""
"""Background color applied to every dynamically-built row/card Frame (see
_line() and the mission-card wrapper in _display_all_missions_row).
EDMC's theme.update() only colors LEAF widgets (Labels, etc.) among a
frame's direct children - it never sets a Frame's own background. A
freshly-built Frame therefore keeps Tk's plain default (white), which is
invisible only where its content happens to fill it completely - any Label
that isn't leaves the frame's true white background exposed around it.
Recomputed once at the top of every redraw() from the mode frame's own
background."""


def _set_content_bg(bg: str) -> None:
    global _content_bg
    _content_bg = bg


def _recompute_wrap_widths(available_width: int) -> None:
    """Derives _WRAP/_WRAP_NAME from the panel's real current width instead
    of a fixed guess, since EDMC panel width isn't a constant across
    installs (other docked plugins, window resizing, DPI scaling). Called
    once at the top of redraw() with the canvas's measured width."""
    global _WRAP, _WRAP_NAME
    _WRAP = max(available_width - _CONTENT_RIGHT_MARGIN, 80)
    _WRAP_NAME = max(_WRAP - _WRAP_NAME_ALLOWANCE, 60)


@dataclass
class GiverTally:
    required: int = 0
    done: int = 0
    reward: int = 0
    shareable_reward: int = 0
    is_estimate: bool = False
    """True once any contributing mission is Wing or ground: for those, the
    Bounty-event-based kill count is known to be unreliable and should be
    flagged rather than presented as an exact count."""
    has_illegal: bool = False
    """True once any contributing mission is flagged illegal - a stack
    groups every mission from one faction onto a single row, so this can
    be true even when only one of several stacked missions is illegal."""


class MassacreData:
    """
    Kill-stacking data for ONE arena (space or ground - the caller already
    filtered), aggregated per mission-giver faction.
    """

    def __init__(self, missions: list[KillMission]):
        self.mission_count = len(missions)
        self.faction_rows: dict[str, GiverTally] = {}
        self.stack_height = 0
        self.before_stack_height = 0
        self.target_factions: list[str] = []
        self.target_systems: list[str] = []
        self.settlements: list[str] = []
        self.warnings: list[str] = []
        self.reward = 0
        self.shareable_reward = 0

        progress = estimate_progress(missions)
        for mission in missions:
            state = self.faction_rows.setdefault(mission.source_faction, GiverTally())
            state.required += mission.count
            state.done += progress.get(mission.id, 0)
            state.reward += mission.reward
            if mission.is_wing:
                state.shareable_reward += mission.reward
            if mission.is_wing or mission.is_ground:
                state.is_estimate = True
            if mission.is_illegal:
                state.has_illegal = True

            if mission.target_faction not in self.target_factions:
                self.target_factions.append(mission.target_faction)
            if mission.target_system not in self.target_systems:
                self.target_systems.append(mission.target_system)
            if mission.target_settlement and mission.target_settlement not in self.settlements:
                self.settlements.append(mission.target_settlement)

        for state in self.faction_rows.values():
            self.reward += state.reward
            self.shareable_reward += state.shareable_reward
            if state.required > self.stack_height:
                self.stack_height = state.required

        # Second-highest stack, used for the delta column of the top stack
        for state in self.faction_rows.values():
            if state.required != self.stack_height \
                    and state.required > self.before_stack_height:
                self.before_stack_height = state.required
        if self.before_stack_height == 0:
            self.before_stack_height = self.stack_height

        if len(self.target_factions) > 1:
            self.warnings.append(
                f"Several target factions: {', '.join(self.target_factions)}")
        if len(self.target_systems) > 1:
            self.warnings.append(
                f"Several target systems: {', '.join(self.target_systems)}")
        if any(state.is_estimate for state in self.faction_rows.values()):
            self.warnings.append(
                "~kills = estimate, not exact (Wing and/or on-foot kills often "
                "go unreported until the mission completes)")


@dataclass
class DisplaySettings:
    remaining: bool = True
    progress: bool = True
    totals: bool = True
    mission_count: bool = True
    settlement: bool = True
    commodities_needed: bool = True


_fonts: dict[str, tkfont.Font] = {}


def _get_fonts() -> dict[str, tkfont.Font]:
    """Derive header/small fonts from the default font. Built lazily because
    fonts need a Tk root to exist."""
    if not _fonts:
        base = tkfont.nametofont("TkDefaultFont")
        size = base.cget("size")
        bold = base.copy()
        bold.configure(weight="bold")
        small = base.copy()
        small.configure(size=max(abs(size) - 2, 7) * (-1 if size < 0 else 1))
        small_bold = small.copy()
        small_bold.configure(weight="bold")
        nav_arrow = base.copy()
        nav_arrow.configure(size=(abs(size) + 4) * (-1 if size < 0 else 1), weight="bold")
        _fonts.update(base=base, bold=bold, small=small, small_bold=small_bold,
                     nav_arrow=nav_arrow)
    return _fonts


def _apply_theme(widget: tk.Widget) -> None:
    """Theme every nested frame.

    EDMC's ``theme.update`` registers an entire subtree but immediately styles
    only the supplied widget and its direct children. Calling it for nested
    frames ensures their labels are readable on the first render too.
    """
    theme.update(widget)
    for child in widget.winfo_children():
        if isinstance(child, tk.Frame):
            _apply_theme(child)


def _bind_mission_click(widget: tk.Widget, mission_id: int,
                        on_click: Callable[[int], None]) -> None:
    """Makes an entire mission card clickable: binds a hand cursor and
    <Button-1> on every widget in its subtree, not just the outer frame -
    a click can land on any label, or the unfilled gaps between them, and
    all of it should open that mission's detail popup."""
    widget.configure(cursor="hand2")
    widget.bind("<Button-1>", lambda _e: on_click(mission_id))
    for child in widget.winfo_children():
        _bind_mission_click(child, mission_id, on_click)


def _line(frame: tk.Frame, row: int, pady: int = 0) -> tk.Frame:
    """One full-width line of a stacked card. Content packed with side=LEFT
    sits left-anchored and wraps if it's a wraplength'd Label; content packed
    with side=RIGHT sits pinned to the right edge - the two never fight over
    column widths the way grid columns do on a narrow panel."""
    line = tk.Frame(frame, background=_content_bg)
    line.grid(row=row, column=0, sticky="ew", pady=pady)
    return line


def _fmt_millions(credits: int) -> str:
    return "{:.1f}M".format(float(credits) / 1_000_000)


def _parse_expiry(expiry_iso: str) -> Optional[dt.datetime]:
    if not expiry_iso:
        return None
    try:
        return dt.datetime.strptime(expiry_iso, "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=dt.timezone.utc)
    except ValueError:
        return None


def _is_expired(expiry_iso: str) -> bool:
    """Used for Community Goals, which have no "this is gone now" event of
    their own (see community_goal_state.py) - time is the only signal
    available to stop showing one that's run its course."""
    expiry = _parse_expiry(expiry_iso)
    return expiry is not None and expiry <= dt.datetime.now(dt.timezone.utc)


def _tier_number(label: str) -> int:
    """"Tier 6" -> 6. Used to turn a Community Goal's TierReached/TopTier
    strings into a progress-bar fraction; a label with no digits (not
    observed, but journal fields are an external boundary) reads as 0."""
    digits = "".join(ch for ch in label if ch.isdigit())
    return int(digits) if digits else 0


def _format_expiry(expiry_iso: str) -> tuple[str, bool]:
    """Renders a mission's time-to-expiry as e.g. "2d 4h" / "45m", and flags
    it as urgent once it's under _URGENT_EXPIRY_MINUTES. No Expiry field (a
    handful of mission types never expire) reads as "-", never urgent."""
    expiry = _parse_expiry(expiry_iso)
    if expiry is None:
        return "-", False

    total_minutes = int((expiry - dt.datetime.now(dt.timezone.utc)).total_seconds() // 60)
    if total_minutes <= 0:
        return "Expired", True

    days, rem_minutes = divmod(total_minutes, 24 * 60)
    hours, minutes = divmod(rem_minutes, 60)
    if days > 0:
        text = f"{days}d {hours}h"
    elif hours > 0:
        text = f"{hours}h {minutes}m"
    else:
        text = f"{minutes}m"
    return text, total_minutes <= _URGENT_EXPIRY_MINUTES


def _format_location(system: str, station: str) -> str:
    if station and system:
        return f"{system} / {station}"
    return station or system or "-"


def _format_destination(mission: all_missions.MissionSummary) -> str:
    return _format_location(mission.destination_system, mission.destination_station)


def _mission_status(mission_id: int, cmdr: Optional[str]) -> tuple[bool, str]:
    """(is_complete, status text). A mission is "Complete" once its
    MissionRedirected event has fired - the same authoritative signal
    kill_missions.py uses for kill-stack completion, just applied generically
    here rather than to a kill count."""
    is_complete = mission_id in kill_tracker.get_redirected(cmdr)
    return is_complete, ("✓ Complete" if is_complete else "Pending")


def _mission_location(mission: all_missions.MissionSummary, cmdr: Optional[str], is_complete: bool) -> str:
    """Where to go right now: the redirect's new turn-in location once a
    mission is complete (if the event carried one), else its original
    destination."""
    if is_complete:
        dropoff = kill_tracker.get_redirect_destination(cmdr, mission.id)
        if dropoff and (dropoff.get("station") or dropoff.get("system")):
            return _format_location(dropoff.get("system", ""), dropoff.get("station", ""))
    return _format_destination(mission)


def _separator(frame: tk.Frame, row: int, pady: int = 3) -> int:
    sep = tk.Frame(frame, height=1, borderwidth=0)
    sep.configure(background=_separator_color())
    sep.grid(row=row, column=0, sticky="ew", pady=pady)
    return row + 1


def _progress_bar(frame: tk.Frame, done: int, required: int) -> tk.Canvas:
    track = _bar_track_color()
    canvas = tk.Canvas(frame, width=BAR_WIDTH, height=BAR_HEIGHT,
                       highlightthickness=0, borderwidth=0, background=track)
    canvas.create_rectangle(0, 0, BAR_WIDTH, BAR_HEIGHT,
                            fill=track, outline="")
    fraction = 0.0 if required <= 0 else min(done / required, 1.0)
    if fraction > 0:
        color = OK if fraction >= 1.0 else ACCENT
        canvas.create_rectangle(0, 0, int(BAR_WIDTH * fraction), BAR_HEIGHT,
                                fill=color, outline="")
    return canvas


def _display_waiting_notice(frame: tk.Frame, cmdr: Optional[str], row: int) -> int:
    who = f"CMDR {cmdr}" if cmdr else "this commander"
    label = tk.Label(frame, justify=tk.LEFT, wraplength=_WRAP,
                     text=f"No active mission data for {who} yet.\n"
                          "Relog (main menu and back) to sync missions.")
    label.grid(column=0, row=row, sticky=tk.W)
    return row + 1


def _display_no_missions(frame: tk.Frame, row: int, text: str) -> int:
    label = tk.Label(frame, text=text)
    label.grid(column=0, row=row, sticky=tk.W, pady=(2, 0))
    return row + 1


def _display_cmdr_header(frame: tk.Frame, count: Optional[int],
                          settings: DisplaySettings, row: int) -> int:
    """Header: mission count on one line ("Missions: 3/20")."""
    show_count = settings.mission_count and count is not None

    if show_count:
        line = _line(frame, row)
        tk.Label(line, text=f"Missions: {count}/{MISSION_CAP}",
                 font=_get_fonts()["bold"], anchor=tk.W).pack(
            side=tk.LEFT, fill=tk.X, expand=True)
        row += 1

    return row


def _display_category_nav(frame: tk.Frame, current: str, counts: dict[str, int],
                          row: int, on_prev, on_next, on_show_all) -> int:
    """◂ Category Name (count) ▸ All - click either arrow to page between the
    panel's category pages, or "All" to open a popup listing every active
    mission at once (unconstrained by the main panel's narrow width)."""
    nav = _line(frame, row, pady=(0, 4))

    fonts = _get_fonts()

    prev_label = tk.Label(nav, text="◂", font=fonts["nav_arrow"], fg=ACCENT, cursor="hand2")
    prev_label.pack(side=tk.LEFT)
    prev_label.bind("<Button-1>", lambda _e: on_prev())

    all_label = tk.Label(nav, text="All", font=fonts["small"], cursor="hand2")
    all_label.pack(side=tk.RIGHT)
    all_label.bind("<Button-1>", lambda _e: on_show_all())

    next_label = tk.Label(nav, text="▸", font=fonts["nav_arrow"], fg=ACCENT, cursor="hand2")
    next_label.pack(side=tk.RIGHT, padx=(0, 8))
    next_label.bind("<Button-1>", lambda _e: on_next())

    title_text = f"{_PAGE_LABELS[current]} ({counts.get(current, 0)})"
    title_label = tk.Label(nav, text=title_text, font=fonts["small"])
    title_label.pack(side=tk.LEFT, expand=True)

    return row + 1


def _display_row(frame: tk.Frame, faction: str, data: GiverTally, mission_data: MassacreData,
                  settings: DisplaySettings, row: int) -> int:
    """A faction's kill-stack as a 2-line card: faction name + kills fraction
    on top, progress bar + reward (+ delta) below."""
    estimate_marker = "~" if data.is_estimate else ""
    kills_text = (f"{estimate_marker}{data.done}/{data.required}"
                  if settings.progress else str(data.required))
    name_text = f"{faction}  ⚠ Illegal" if data.has_illegal else faction

    top = _line(frame, row, pady=(0, _LINE_PAD))
    tk.Label(top, text=name_text, wraplength=_WRAP_NAME, justify=tk.LEFT, anchor=tk.W).pack(
        side=tk.LEFT, fill=tk.X, expand=True)
    tk.Label(top, text=kills_text).pack(side=tk.RIGHT, anchor="ne")
    row += 1

    reward_text = f"{_fmt_millions(data.reward)} ({_fmt_millions(data.shareable_reward)})"
    bottom = _line(frame, row)
    if settings.progress:
        _progress_bar(bottom, data.done, data.required).pack(side=tk.LEFT)
        tk.Label(bottom, text=reward_text).pack(side=tk.LEFT, padx=(8, 0))
    else:
        tk.Label(bottom, text=reward_text).pack(side=tk.LEFT)
    if settings.remaining:
        delta = mission_data.stack_height - data.required
        text = delta if delta > 0 else mission_data.before_stack_height - mission_data.stack_height
        tk.Label(bottom, text=f"Δ{text}").pack(side=tk.RIGHT)
    row += 1
    return row


def _display_sum(frame: tk.Frame, data: MassacreData, settings: DisplaySettings,
                  row: int) -> int:
    row = _separator(frame, row, pady=2)
    fonts = _get_fonts()
    done_sum = sum(s.done for s in data.faction_rows.values())
    estimate_marker = "~" if any(s.is_estimate for s in data.faction_rows.values()) else ""
    kills_text = (f"{estimate_marker}{min(done_sum, data.stack_height)}/{data.stack_height}"
                  if settings.progress else str(data.stack_height))

    top = _line(frame, row)
    tk.Label(top, text="Sum", font=fonts["bold"]).pack(side=tk.LEFT)
    tk.Label(top, text=kills_text, font=fonts["bold"]).pack(side=tk.RIGHT)
    row += 1

    reward_text = f"{_fmt_millions(data.reward)} ({_fmt_millions(data.shareable_reward)})"
    bottom = _line(frame, row)
    if settings.progress:
        _progress_bar(bottom, min(done_sum, data.stack_height), data.stack_height).pack(side=tk.LEFT)
        tk.Label(bottom, text=reward_text, font=fonts["bold"]).pack(side=tk.LEFT, padx=(8, 0))
    else:
        tk.Label(bottom, text=reward_text, font=fonts["bold"]).pack(side=tk.LEFT)
    row += 1
    return row


def _display_settlements(frame: tk.Frame, data: MassacreData, row: int) -> int:
    if not data.settlements:
        return row
    label = tk.Label(frame, text="Settlements: " + ", ".join(data.settlements),
                     wraplength=_WRAP, justify=tk.LEFT, font=_get_fonts()["small"])
    label.grid(column=0, row=row, sticky=tk.W)
    return row + 1


def _display_warning(frame: tk.Frame, warning: str, row: int) -> int:
    label = tk.Label(frame, text="⚠ " + warning, wraplength=_WRAP,
                     justify=tk.LEFT, font=_get_fonts()["small"])
    label.grid(column=0, row=row, sticky=tk.W)
    return row + 1


def _display_massacre_data(frame: tk.Frame, data: MassacreData, settings: DisplaySettings,
                           row: int, no_missions_text: str) -> int:
    if data.mission_count == 0:
        return _display_no_missions(frame, row, no_missions_text)

    for i, faction in enumerate(sorted(data.faction_rows.keys())):
        if i > 0:
            row = _separator(frame, row, pady=_CARD_GAP)
        row = _display_row(frame, faction, data.faction_rows[faction], data, settings, row)
    if settings.totals:
        row = _display_sum(frame, data, settings, row)
    if settings.settlement:
        row = _display_settlements(frame, data, row)
    for warning in data.warnings:
        row = _display_warning(frame, warning, row)

    return row


def _display_all_missions_row(frame: tk.Frame, mission: all_missions.MissionSummary,
                               row: int, on_click: Callable[[int], None]) -> int:
    """A mission as a stacked card, one field per line: name, faction,
    status + reward, location, expiry. The name gets a full-width line to
    itself (rather than sharing one with the reward) so it only wraps once
    it hits the panel's actual width, not a narrow column.

    Built inside its own `card` frame (rather than laying lines directly
    into `frame` as before) so the whole card - not just one label - can be
    bound clickable in one recursive pass, opening a detail popup for this
    mission."""
    fonts = _get_fonts()
    cmdr = kill_tracker.current_cmdr
    is_complete, status_text = _mission_status(mission.id, cmdr)
    badges = []
    if mission.is_illegal:
        badges.append("⚠ Illegal")
    if mission.is_wing:
        badges.append("🤝 Wing")
    name_text = f"{mission.name}  {'  '.join(badges)}" if badges else mission.name
    reward_text = _fmt_millions(mission.reward) if mission.reward else "-"

    card = tk.Frame(frame, background=_content_bg)
    card.grid(row=row, column=0, sticky="ew")
    card.columnconfigure(0, weight=1)
    card_row = 0

    name_line = _line(card, card_row, pady=(0, _LINE_PAD))
    tk.Label(name_line, text=name_text, wraplength=_WRAP, justify=tk.LEFT,
             anchor=tk.W, font=fonts["bold"]).pack(side=tk.LEFT, fill=tk.X, expand=True)
    card_row += 1

    faction_line = _line(card, card_row, pady=(0, _LINE_PAD))
    tk.Label(faction_line, text=mission.source_faction, wraplength=_WRAP,
             justify=tk.LEFT, font=fonts["small"]).pack(side=tk.LEFT)
    card_row += 1

    if mission.commodity:
        methods_text = mining_methods.format_methods(mining_methods.methods_for(mission.commodity))
        mining_line = _line(card, card_row, pady=(0, _LINE_PAD))
        tk.Label(mining_line, text=f"Mine via: {methods_text}", wraplength=_WRAP,
                 justify=tk.LEFT, font=fonts["small"]).pack(side=tk.LEFT)
        card_row += 1

    status_line = _line(card, card_row, pady=(0, _LINE_PAD))
    tk.Label(status_line, text=status_text, font=fonts["small"]).pack(side=tk.LEFT)
    tk.Label(status_line, text=reward_text).pack(side=tk.RIGHT, anchor="ne")
    card_row += 1

    location = _mission_location(mission, cmdr, is_complete)
    dest_line = _line(card, card_row, pady=(0, _LINE_PAD))
    tk.Label(dest_line, text="→ " + location, wraplength=_WRAP,
             justify=tk.LEFT, font=fonts["small"]).pack(side=tk.LEFT)
    card_row += 1

    expiry_text, urgent = _format_expiry(mission.expiry)
    if urgent:
        expiry_text = "⚠ " + expiry_text
    expiry_line = _line(card, card_row)
    tk.Label(expiry_line, text="Expires: " + expiry_text, font=fonts["small"]).pack(side=tk.LEFT)

    _bind_mission_click(card, mission.id, on_click)
    return row + 1


def _aggregate_commodities_needed(
        missions: dict[int, all_missions.MissionSummary]) -> list[tuple[str, int, int]]:
    """(commodity, total units still needed, mission count), summed across
    missions where the commodity must still be sourced (mined or bought/
    collected - see mission_types.needs_commodity_supply), sorted by name.
    A plain Delivery mission's cargo was already handed over at acceptance,
    so it never contributes here."""
    totals: dict[str, list[int]] = {}
    for mission in missions.values():
        if not mission.needed_commodity:
            continue
        entry = totals.setdefault(mission.needed_commodity, [0, 0])
        entry[0] += mission.needed_commodity_count
        entry[1] += 1
    return sorted((name, count, mission_count) for name, (count, mission_count) in totals.items())


def _display_commodities_needed(frame: tk.Frame, rows: list[tuple[str, int, int]],
                                row: int) -> int:
    """A shopping-list summary at the top of the Trade & Mining page, so a
    commander doesn't have to open every Collect/Mining mission card to
    tally up what's still needed. No-op (returns row unchanged) when
    there's nothing to source."""
    if not rows:
        return row
    fonts = _get_fonts()
    header = _line(frame, row, pady=(0, _LINE_PAD))
    tk.Label(header, text="Commodities needed:", font=fonts["bold"]).pack(side=tk.LEFT)
    row += 1

    for name, count, mission_count in rows:
        line = _line(frame, row, pady=(0, _LINE_PAD))
        unit = "mission" if mission_count == 1 else "missions"
        tk.Label(line, text=f"{name} ({mission_count} {unit})", wraplength=_WRAP_NAME,
                justify=tk.LEFT, anchor=tk.W).pack(side=tk.LEFT, fill=tk.X, expand=True)
        tk.Label(line, text=f"x{count:,}").pack(side=tk.RIGHT, anchor="ne")
        row += 1

    return _separator(frame, row, pady=_CARD_GAP)


def _display_all_missions(frame: tk.Frame, missions: dict[int, all_missions.MissionSummary],
                          row: int, no_missions_text: str,
                          on_click: Callable[[int], None]) -> int:
    if not missions:
        return _display_no_missions(frame, row, no_missions_text)

    # Soonest-to-expire first; missions with no expiry sort last.
    ordered = sorted(missions.values(), key=lambda m: (m.expiry == "", m.expiry))
    for i, mission in enumerate(ordered):
        if i > 0:
            row = _separator(frame, row, pady=_CARD_GAP)
        row = _display_all_missions_row(frame, mission, row, on_click)
    return row


def _display_all_missions_table(frame: tk.Frame, missions: list[all_missions.MissionSummary],
                                on_click: Callable[[int], None]) -> None:
    """A flat, column-based table of every active mission across every
    category, including massacre/settlement ones. Used only in the "All"
    popup: unlike the narrow main panel, a popup is a normal resizable OS
    window with room for actual columns instead of stacked cards. Each row
    is clickable, same as a card on the main panel."""
    fonts = _get_fonts()

    def head(text, column, sticky):
        tk.Label(frame, text=text, font=fonts["bold"]).grid(
            row=0, column=column, sticky=sticky, padx=(0, 12), pady=(0, 4))

    head("Mission", 0, tk.W)
    head("Faction", 1, tk.W)
    head("Reward", 2, tk.E)
    head("Expires", 3, tk.E)

    if not missions:
        tk.Label(frame, text="No active missions.").grid(
            row=1, column=0, columnspan=4, sticky=tk.W)
        return

    for row, mission in enumerate(missions, start=1):
        badges = []
        if mission.is_illegal:
            badges.append("⚠ Illegal")
        if mission.is_wing:
            badges.append("🤝 Wing")
        name_text = f"{mission.name}  {'  '.join(badges)}" if badges else mission.name
        name_label = tk.Label(frame, text=name_text, justify=tk.LEFT)
        name_label.grid(row=row, column=0, sticky=tk.W, padx=(0, 12), pady=(0, 3))
        faction_label = tk.Label(frame, text=mission.source_faction, justify=tk.LEFT)
        faction_label.grid(row=row, column=1, sticky=tk.W, padx=(0, 12), pady=(0, 3))

        reward_text = _fmt_millions(mission.reward) if mission.reward else "-"
        reward_label = tk.Label(frame, text=reward_text)
        reward_label.grid(row=row, column=2, sticky=tk.E, padx=(0, 12), pady=(0, 3))

        expiry_text, urgent = _format_expiry(mission.expiry)
        if urgent:
            expiry_text = "⚠ " + expiry_text
        expiry_label = tk.Label(frame, text=expiry_text)
        expiry_label.grid(row=row, column=3, sticky=tk.E, pady=(0, 3))

        for label in (name_label, faction_label, reward_label, expiry_label):
            _bind_mission_click(label, mission.id, on_click)


def _format_full_datetime(iso: str) -> str:
    """An absolute timestamp rather than _format_expiry's relative
    countdown - used in the mission detail popup, which has room for one."""
    parsed = _parse_expiry(iso)
    return parsed.strftime("%Y-%m-%d %H:%M UTC") if parsed else "-"


def _display_mission_detail(frame: tk.Frame, mission: all_missions.MissionSummary,
                            cmdr: Optional[str]) -> None:
    """One mission's full detail as label:value rows, opened by clicking its
    card/row anywhere else in the panel. A popup isn't fighting the main
    panel's narrow width, so this can afford fields the compact card never
    shows - exact reward, Wing status, the accepted date - on top of
    everything already there."""
    fonts = _get_fonts()
    is_complete, status_text = _mission_status(mission.id, cmdr)
    location = _mission_location(mission, cmdr, is_complete)

    row = 0
    name_text = f"{mission.name}  ⚠ Illegal" if mission.is_illegal else mission.name
    tk.Label(frame, text=name_text, font=fonts["bold"], wraplength=380,
             justify=tk.LEFT).grid(row=row, column=0, columnspan=2, sticky=tk.W, pady=(0, 8))
    row += 1

    def detail_row(label: str, value: str) -> None:
        nonlocal row
        tk.Label(frame, text=label, font=fonts["bold"]).grid(
            row=row, column=0, sticky=tk.NW, padx=(0, 12), pady=(0, 4))
        tk.Label(frame, text=value, wraplength=280, justify=tk.LEFT).grid(
            row=row, column=1, sticky=tk.W, pady=(0, 4))
        row += 1

    detail_row("Faction:", mission.source_faction)
    detail_row("Category:", mission_types.CATEGORY_LABELS.get(mission.category, mission.category))
    detail_row("Status:", status_text)
    if mission.commodity:
        methods_text = mining_methods.format_methods(mining_methods.methods_for(mission.commodity))
        detail_row("Commodity:", mission.commodity)
        detail_row("Mine via:", methods_text)
    detail_row("Reward:", f"{mission.reward:,} CR" if mission.reward else "-")
    detail_row("Wing mission:", "Yes" if mission.is_wing else "No")
    detail_row("Destination:", location)
    detail_row("Accepted:", _format_full_datetime(mission.accepted_at))
    detail_row("Expires:", _format_full_datetime(mission.expiry))


def _display_community_goal_card(frame: tk.Frame, goal: CommunityGoal, row: int) -> int:
    """A Community Goal as a stacked card: title, system/market, a tier
    progress bar (community-wide, not personal - see CommunityGoal.tier_reached),
    this CMDR's own contribution + reward, an optional top-rank badge, and
    expiry (reused from the mission card - same ISO format, same
    urgency threshold)."""
    fonts = _get_fonts()

    title_line = _line(frame, row, pady=(0, _LINE_PAD))
    tk.Label(title_line, text=goal.title, wraplength=_WRAP, justify=tk.LEFT,
             anchor=tk.W, font=fonts["bold"]).pack(side=tk.LEFT, fill=tk.X, expand=True)
    row += 1

    location_line = _line(frame, row, pady=(0, _LINE_PAD))
    tk.Label(location_line, text=_format_location(goal.system, goal.market),
             wraplength=_WRAP, justify=tk.LEFT, font=fonts["small"]).pack(side=tk.LEFT)
    row += 1

    tier_line = _line(frame, row, pady=(0, _LINE_PAD))
    top_tier_num = max(_tier_number(goal.top_tier), 1)
    _progress_bar(tier_line, _tier_number(goal.tier_reached), top_tier_num).pack(side=tk.LEFT)
    tier_text = f"{goal.tier_reached or '-'} of {goal.top_tier or '-'}"
    if goal.is_complete:
        tier_text += "  ✓ Complete"
    tk.Label(tier_line, text=tier_text, font=fonts["small"]).pack(side=tk.LEFT, padx=(8, 0))
    row += 1

    contrib_line = _line(frame, row, pady=(0, _LINE_PAD))
    tk.Label(contrib_line, text=f"Your contribution: {goal.player_contribution:,}",
             font=fonts["small"]).pack(side=tk.LEFT)
    if goal.bonus:
        tk.Label(contrib_line, text=_fmt_millions(goal.bonus)).pack(side=tk.RIGHT, anchor="ne")
    row += 1

    if goal.player_in_top_rank:
        rank_line = _line(frame, row, pady=(0, _LINE_PAD))
        tk.Label(rank_line, text="\U0001F3C6 Top rank", font=fonts["small"]).pack(side=tk.LEFT)
        row += 1

    expiry_text, urgent = _format_expiry(goal.expiry)
    if urgent:
        expiry_text = "⚠ " + expiry_text
    expiry_line = _line(frame, row)
    tk.Label(expiry_line, text="Expires: " + expiry_text, font=fonts["small"]).pack(side=tk.LEFT)
    row += 1

    return row


def _display_community_goal_page(frame: tk.Frame, goals: dict[int, CommunityGoal],
                                 row: int, no_data_text: str) -> int:
    if not goals:
        return _display_no_missions(frame, row, no_data_text)

    ordered = sorted(goals.values(), key=lambda g: (g.expiry == "", g.expiry))
    for i, goal in enumerate(ordered):
        if i > 0:
            row = _separator(frame, row, pady=_CARD_GAP)
        row = _display_community_goal_card(frame, goal, row)
    return row


class MissionsUI:
    def __init__(self):
        self.__parent: Optional[tk.Frame] = None
        self.__massacre_missions: Optional[dict[int, KillMission]] = None
        self.__all_missions_data: Optional[dict[int, all_missions.MissionSummary]] = None
        self.__community_goals: dict[int, CommunityGoal] = community_goal_state.get_goals(
            community_goal_state.current_cmdr)
        self.__canvas: Optional[tk.Canvas] = None
        self.__content: Optional[tk.Frame] = None
        self.__content_window: Optional[int] = None
        self.__scrollbar: Optional[tk.Scrollbar] = None
        self.__popup: Optional[tk.Toplevel] = None
        self.__popup_content: Optional[tk.Frame] = None
        self.__detail_popup: Optional[tk.Toplevel] = None
        self.__detail_content: Optional[tk.Frame] = None
        self.__detail_mission_id: Optional[int] = None
        self.__settings = DisplaySettings()
        self.__current_category = _load_current_category()

    def apply_display_settings(self, settings: DisplaySettings):
        self.__settings = settings
        self.redraw()

    def build_panel(self, parent: tk.Frame):
        """Builds a Canvas/Scrollbar/content-frame trio inside `parent` (the
        "missions" mode frame WNTB's ui.py already grids/gates) - no header
        or collapse toggle of its own, unlike edmmm's original ui.py (see
        module docstring)."""
        parent.columnconfigure(0, weight=1)
        self.__parent = parent

        self.__canvas = tk.Canvas(parent, highlightthickness=0, borderwidth=0,
                                  yscrollincrement=24)
        self.__canvas.grid(column=0, row=0, sticky="ew")
        self.__scrollbar = tk.Scrollbar(parent, orient="vertical",
                                        command=self.__canvas.yview)
        self.__scrollbar.grid(column=1, row=0, sticky="ns")
        self.__canvas.configure(yscrollcommand=self.__scrollbar.set)

        self.__content = tk.Frame(self.__canvas)
        self.__content.columnconfigure(0, weight=1)
        self.__content_window = self.__canvas.create_window(
            (0, 0), window=self.__content, anchor="nw")

        self.__content.bind("<Configure>", self.__sync_scroll_region)
        self.__canvas.bind("<Configure>", self.__on_canvas_resize)
        self.__canvas.bind("<Enter>", lambda _e: self.__bind_mousewheel())
        self.__canvas.bind("<Leave>", lambda _e: self.__unbind_mousewheel())

        parent.bind("<<Refresh>>", lambda _e: self.redraw())
        self.redraw()
        # This first redraw() call almost always lands before Tk has
        # given the canvas real geometry (winfo_width() still 1), so wrap
        # widths fall back to the static defaults - re-run once shortly
        # after so it self-corrects to the real panel width immediately,
        # instead of visibly wrapping wrong until the next mission change
        # or the 60s refresh tick.
        parent.after(100, self.__refresh_if_alive)
        parent.after(REFRESH_INTERVAL_MS, self.__tick)

    def __refresh_if_alive(self):
        """redraw(), but only if the frame is still a live widget - guards
        scheduled (after()) callbacks that may fire post-teardown."""
        if self.__parent is None or not self.__parent.winfo_exists():
            return
        self.redraw()

    def __tick(self):
        self.__refresh_if_alive()
        if self.__parent is not None and self.__parent.winfo_exists():
            self.__parent.after(REFRESH_INTERVAL_MS, self.__tick)

    def __on_canvas_resize(self, event):
        """Keeps the content frame's width matched to the canvas (which
        tracks the EDMC window's actual width) so wraplength-based wrapping
        lines up with the visible area and only vertical scrolling is ever
        needed. Insets by _CONTENT_RIGHT_MARGIN so content never claims the
        canvas's full width, leaving a sliver clear of the scrollbar for
        right-anchored values that don't wrap."""
        width = max(event.width - _CONTENT_RIGHT_MARGIN, 0)
        self.__canvas.itemconfigure(self.__content_window, width=width)

    def __sync_scroll_region(self, _event=None):
        """Recomputes the scrollable region after content changes size, caps
        the canvas's visible height at _MAX_PANEL_HEIGHT, and shows the
        scrollbar only once content actually exceeds that cap.

        Deliberately doesn't touch the scroll position: this also runs as a
        <Configure> callback, which can fire multiple times while deeply
        nested content is still settling its geometry - resetting to the top
        on every one of those incidental passes would fight a user who's
        mid-scroll. redraw() resets to the top itself, once, right after
        it actually rebuilds the page.
        """
        if self.__canvas is None:
            return
        self.__canvas.update_idletasks()
        bbox = self.__canvas.bbox("all")
        content_height = (bbox[3] - bbox[1]) if bbox else 0
        self.__canvas.configure(scrollregion=bbox,
                                height=min(content_height, _MAX_PANEL_HEIGHT))
        if content_height > _MAX_PANEL_HEIGHT:
            self.__scrollbar.grid()
        else:
            self.__scrollbar.grid_remove()

    def __bind_mousewheel(self):
        self.__canvas.bind_all("<MouseWheel>", self.__on_mousewheel)
        self.__canvas.bind_all("<Button-4>", self.__on_mousewheel)
        self.__canvas.bind_all("<Button-5>", self.__on_mousewheel)

    def __unbind_mousewheel(self):
        self.__canvas.unbind_all("<MouseWheel>")
        self.__canvas.unbind_all("<Button-4>")
        self.__canvas.unbind_all("<Button-5>")

    def __on_mousewheel(self, event):
        # 3 units (~72px, given the canvas's 24px yscrollincrement) per wheel
        # notch/swipe-tick - Windows reports multiples of 120 per notch,
        # X11 sends dedicated Button-4/5 events instead of a delta.
        if getattr(event, "num", None) == 4:
            self.__canvas.yview_scroll(-3, "units")
        elif getattr(event, "num", None) == 5:
            self.__canvas.yview_scroll(3, "units")
        elif event.delta:
            self.__canvas.yview_scroll(-3 if event.delta > 0 else 3, "units")

    def __category_counts(self) -> dict[str, int]:
        counts = {key: 0 for key in _PAGE_ORDER}
        for mission in (self.__massacre_missions or {}).values():
            key = mission_types.MASSACRE_GROUND if mission.is_ground else mission_types.MASSACRE_SPACE
            counts[key] += 1
        for mission in (self.__all_missions_data or {}).values():
            if mission.category not in _MASSACRE_CATEGORIES:
                counts[mission.category] += 1
        counts[_COMMUNITY_GOAL_PAGE] = sum(
            1 for g in self.__community_goals.values() if not _is_expired(g.expiry))
        return counts

    def __ensure_valid_category(self, counts: dict[str, int]):
        """If the persisted/current category has no active missions but
        another one does, jump to the first category (in display order)
        that does, so the nav never lands on an empty page."""
        if counts.get(self.__current_category, 0) > 0:
            return
        for key in _PAGE_ORDER:
            if counts[key] > 0:
                self.__current_category = key
                _save_current_category(key)
                return

    def __step_category(self, direction: int):
        counts = self.__category_counts()
        order = _PAGE_ORDER
        if not any(counts.values()):
            return  # nothing anywhere to page to - stay put
        idx = order.index(self.__current_category)
        for _ in range(len(order)):
            idx = (idx + direction) % len(order)
            if counts[order[idx]] > 0:
                break
        self.__current_category = order[idx]
        _save_current_category(self.__current_category)
        self.redraw()

    def __prev_category(self):
        self.__step_category(-1)

    def __next_category(self):
        self.__step_category(1)

    def on_kill_missions(self, data: Optional[dict[int, KillMission]]):
        self.__massacre_missions = data
        self.redraw()

    def on_all_missions(self, data: Optional[dict[int, all_missions.MissionSummary]]):
        self.__all_missions_data = data
        self.redraw()

    def on_community_goals(self, data: dict[int, CommunityGoal]):
        self.__community_goals = data
        self.redraw()

    def __render_current_page(self, frame: tk.Frame, row: int) -> int:
        category = self.__current_category

        if category == _COMMUNITY_GOAL_PAGE:
            active = {cg_id: g for cg_id, g in self.__community_goals.items()
                     if not _is_expired(g.expiry)}
            return _display_community_goal_page(frame, active, row,
                                                "No active Community Goals.")

        no_missions_text = f"No {mission_types.CATEGORY_LABELS[category].lower()} missions on the board."

        if category in _MASSACRE_CATEGORIES:
            want_ground = category == mission_types.MASSACRE_GROUND
            missions = [m for m in (self.__massacre_missions or {}).values()
                       if m.is_ground == want_ground]
            data = MassacreData(missions)
            return _display_massacre_data(frame, data, self.__settings, row, no_missions_text)

        missions = {mid: m for mid, m in (self.__all_missions_data or {}).items()
                   if m.category == category}
        if category == mission_types.TRADE and self.__settings.commodities_needed:
            row = _display_commodities_needed(
                frame, _aggregate_commodities_needed(missions), row)
        return _display_all_missions(frame, missions, row, no_missions_text,
                                     self.__open_mission_detail)

    def redraw(self):
        if self.__parent is None or self.__content is None:
            logger.warning("Missions panel is not built yet; skipping redraw")
            return

        self.__canvas.update_idletasks()
        canvas_width = self.__canvas.winfo_width()
        if canvas_width > 1:  # not yet realized (e.g. very first call) - keep the fallback
            _recompute_wrap_widths(canvas_width)
        _set_content_bg(self.__parent.cget("background"))

        for child in self.__content.winfo_children():
            child.destroy()

        row = 0
        if self.__all_missions_data is None:
            _display_waiting_notice(self.__content, kill_tracker.current_cmdr, row)
        else:
            counts = self.__category_counts()
            total = len(self.__all_missions_data)
            row = _display_cmdr_header(self.__content, total, self.__settings, row)
            if sum(counts.values()) == 0:
                _display_no_missions(self.__content, row, random.choice(_NO_MISSIONS_MESSAGES))
            else:
                self.__ensure_valid_category(counts)
                row = _display_category_nav(self.__content, self.__current_category,
                                            counts, row,
                                            self.__prev_category, self.__next_category,
                                            self.__show_all_missions_popup)
                self.__render_current_page(self.__content, row)

        theme.update(self.__parent)
        _apply_theme(self.__content)
        self.__canvas.configure(background=_content_bg)
        self.__content.configure(background=_content_bg)
        self.__sync_scroll_region()
        self.__canvas.yview_moveto(0)
        self.__refresh_popup()
        self.__refresh_detail_popup()

    def __show_all_missions_popup(self):
        """Opens (or, if already open, raises and refreshes) a popup listing
        every active mission across every category in one flat, column-based
        table - the "All" link next to the category nav."""
        if self.__popup is not None and self.__popup.winfo_exists():
            self.__popup.lift()
            self.__popup.focus_force()
            self.__refresh_popup()
            return

        # Parented to the actual EDMC root window, not self.__parent: EDMC's
        # own theme.update(self.__parent) - called on every panel refresh -
        # recursively walks self.__parent's *widget-tree* children and
        # doesn't know how to handle a Toplevel among them, which would
        # silently abort the rest of redraw() - including
        # __refresh_popup() - every time a mission changed while this popup
        # was open. Rooting it at the real toplevel keeps it out of that walk.
        self.__popup = tk.Toplevel(self.__parent.winfo_toplevel())
        self.__popup.withdraw()  # shown once sized and positioned, below - avoids a flash at default size
        ui_style.skin(self.__popup)  # WNTB's own look, not EDMC's theme - see plugin/uikit
        self.__popup.title("WNTB - All Active Missions")
        self.__popup.columnconfigure(0, weight=1)
        self.__popup.rowconfigure(0, weight=1)
        self.__popup.protocol("WM_DELETE_WINDOW", self.__close_popup)

        self.__popup_content = tk.Frame(self.__popup)
        self.__popup_content.grid(row=0, column=0, sticky="nsew", padx=8, pady=8)

        self.__refresh_popup()

        # Size the window to fit its content (bounded to sane min/max), since
        # mission-name length varies too much for one fixed default to work
        # well; the user can still freely resize this normal OS window after.
        self.__popup.update_idletasks()
        width = min(max(self.__popup_content.winfo_reqwidth() + 20, 400), 800)
        height = min(max(self.__popup_content.winfo_reqheight() + 20, 200), 600)

        # Center over the EDMC window rather than leaving position to the
        # platform default - on a multi-monitor setup, an unpositioned
        # Toplevel doesn't reliably land on the same monitor as EDMC itself.
        # Deliberately not clamped to >=0: a monitor to the left of/above the
        # primary has negative virtual-screen coordinates, and clamping would
        # push the popup onto the wrong monitor there.
        master = self.__parent.winfo_toplevel()
        x = master.winfo_rootx() + (master.winfo_width() - width) // 2
        y = master.winfo_rooty() + (master.winfo_height() - height) // 2
        self.__popup.geometry(f"{width}x{height}+{x}+{y}")
        self.__popup.deiconify()

    def __close_popup(self):
        if self.__popup is not None:
            self.__popup.destroy()
        self.__popup = None
        self.__popup_content = None

    def __refresh_popup(self):
        """Rebuilds the popup's content if it's currently open, so it stays
        live while the panel keeps updating (new missions, kills, expiry)."""
        if self.__popup is None or not self.__popup.winfo_exists():
            return
        for child in self.__popup_content.winfo_children():
            child.destroy()

        missions = sorted((self.__all_missions_data or {}).values(),
                          key=lambda m: (m.expiry == "", m.expiry))
        _display_all_missions_table(self.__popup_content, missions, self.__open_mission_detail)
        # No theme.update()/_apply_theme here: these popups wear WNTB's own
        # look (ui_style.skin on the Toplevel), which EDMC's theme would
        # otherwise recolour.

    def __open_mission_detail(self, mission_id: int):
        """Opens (or, if already open, raises and re-targets) a per-mission
        detail window - the click target for every mission card/row in the
        panel and the "All missions" popup. Follows the same Toplevel
        pattern as that popup: parented to the real EDMC root window, and
        refreshed from redraw() rather than registered as its own
        listener, so it stays live and tolerates the mission it was opened
        for having since disappeared (handed in, abandoned, expired)."""
        self.__detail_mission_id = mission_id
        if self.__detail_popup is not None and self.__detail_popup.winfo_exists():
            self.__detail_popup.lift()
            self.__detail_popup.focus_force()
            self.__refresh_detail_popup()
            return

        self.__detail_popup = tk.Toplevel(self.__parent.winfo_toplevel())
        self.__detail_popup.withdraw()
        ui_style.skin(self.__detail_popup)
        self.__detail_popup.title("WNTB - Mission Details")
        self.__detail_popup.columnconfigure(0, weight=1)
        self.__detail_popup.rowconfigure(0, weight=1)
        self.__detail_popup.protocol("WM_DELETE_WINDOW", self.__close_detail_popup)

        self.__detail_content = tk.Frame(self.__detail_popup)
        self.__detail_content.grid(row=0, column=0, sticky="nsew", padx=8, pady=8)

        self.__refresh_detail_popup()

        self.__detail_popup.update_idletasks()
        width = min(max(self.__detail_content.winfo_reqwidth() + 20, 320), 600)
        height = min(max(self.__detail_content.winfo_reqheight() + 20, 150), 500)

        master = self.__parent.winfo_toplevel()
        x = master.winfo_rootx() + (master.winfo_width() - width) // 2
        y = master.winfo_rooty() + (master.winfo_height() - height) // 2
        self.__detail_popup.geometry(f"{width}x{height}+{x}+{y}")
        self.__detail_popup.deiconify()

    def __close_detail_popup(self):
        if self.__detail_popup is not None:
            self.__detail_popup.destroy()
        self.__detail_popup = None
        self.__detail_content = None
        self.__detail_mission_id = None

    def __refresh_detail_popup(self):
        """Rebuilds the detail popup's content if it's currently open, so it
        stays live while the panel keeps updating (new kills, redirect,
        expiry). Degrades to a "no longer active" message, rather than
        erroring out, if the mission it was opened for has since been
        handed in, abandoned, or expired."""
        if self.__detail_popup is None or not self.__detail_popup.winfo_exists():
            return
        for child in self.__detail_content.winfo_children():
            child.destroy()

        mission = (self.__all_missions_data or {}).get(self.__detail_mission_id)
        if mission is None:
            tk.Label(self.__detail_content,
                    text="This mission is no longer active.").grid(row=0, column=0, sticky=tk.W)
        else:
            self.__detail_popup.title(f"WNTB - {mission.name}")
            _display_mission_detail(self.__detail_content, mission, kill_tracker.current_cmdr)


ui = MissionsUI()


def handle_new_community_goal_state(data: dict[int, CommunityGoal]):
    ui.on_community_goals(data)


kill_missions.view.changed.connect(ui.on_kill_missions)
all_missions.view.changed.connect(ui.on_all_missions)
community_goal_state.community_goal_listeners.append(handle_new_community_goal_state)
