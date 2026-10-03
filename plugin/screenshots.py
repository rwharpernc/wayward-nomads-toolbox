"""Field Ops mode: screenshot capture/conversion/thumbnail management.

Watches for the game's `Screenshot` journal event, converts the raw
BMP/PNG into a renamed PNG (per a user-selected filename mask), shows an
auto-cropped preview based on which HUD panel had focus, and can
optionally auto-trigger a capture on a timer or when scanning a Thargoid
signal. `PANEL_PLACEMENT = "fieldops"` per the feature-module contract.
Overlay drawing goes through the shared `overlay.OverlayClient`.
"""

from __future__ import annotations

import ctypes
import logging
import os
import subprocess
import threading
import time
from collections import deque
from dataclasses import dataclass
from sys import platform
from tkinter import filedialog
from typing import Any, Deque, Dict, List, NamedTuple, Optional, Tuple
from uuid import UUID

import tkinter as tk

import myNotebook as nb
from config import appname, config
from theme import theme
from ttkHyperlinkLabel import HyperlinkLabel

from .uikit import style as ui_style
from . import overlay, panelkit, platform_support, screenshot_automation, screenshot_convert, screenshot_gui_focus, screenshot_naming

plugin_name = os.path.basename(os.path.dirname(__file__))
logger = logging.getLogger(f"{appname}.{plugin_name}")

PANEL_PLACEMENT = "fieldops"

_CFG_SOURCE_DIR = "wntb_screenshot_source_dir"
_CFG_OUTPUT_DIR = "wntb_screenshot_output_dir"
_CFG_DELETE_ORIGINAL = "wntb_screenshot_delete_original"
_CFG_GROUP_BY_SYSTEM = "wntb_screenshot_group_by_system"
_CFG_SHOW_TIMER_ICON = "wntb_screenshot_show_timer_icon"
_CFG_MASK = "wntb_screenshot_mask"
_CFG_HIRES_ON_TIMER = "wntb_screenshot_hires_on_timer"
_CFG_THARGOID_CAPTURE = "wntb_screenshot_thargoid_capture"
_CFG_OVERLAY_ENABLED = "wntb_screenshot_overlay_enabled"
_CFG_POLL_INTERVAL_S = "wntb_screenshot_poll_interval_s"

# Default/fallback auto-timer poll interval (now configurable — see
# ScreenshotConfig.poll_interval_s/_poll_interval_ms below), and how long a
# simulated key press is held before being released (see
# screenshot_automation.press_screenshot_keys).
_DEFAULT_POLL_INTERVAL_S = 1.0
# A hard floor, not just a UI default: press_screenshot_keys() sends a real
# Alt+F10 key event to the game, so a commander mistyping "0" (or a
# corrupt/hand-edited config value) must never be able to hammer that key
# combo faster than this, however the value got set.
_MIN_POLL_INTERVAL_S = 0.2
_KEY_HOLD_MS = 60
# Original file is only deleted after a grace period, so other plugins get
# a chance to see it first.
_DELETE_GRACE_MS = 60_000
# Preview popup shown on a thumbnail click — much larger than the inline
# thumbnail, but still an explicit, bounded box (see
# screenshot_convert.thumbnail_photo_data). The actual bound is also capped
# to a fraction of the screen (see _preview_bounds) so this ceiling only
# matters on large/multi-monitor setups.
_PREVIEW_MAX_WIDTH = 1800
_PREVIEW_MAX_HEIGHT = 1300
_PREVIEW_SCREEN_FRACTION = 0.85
# Recent-captures history strip: the newest capture stays "live" (full-res
# image held in memory); this many older captures are kept alongside it as
# view-only thumbnails, each generated from what's actually on disk rather
# than an in-memory image — see _snapshot_current_as_history. Wrapped onto
# multiple rows of _HISTORY_COLUMNS each (see _history_grid_position)
# rather than one ever-widening row — EDMC's main window auto-sizes to fit
# the widest visible row across every loaded plugin, so growing this strip
# taller (more rows) is fine but growing it wider is not.
_HISTORY_SIZE = 8
_HISTORY_COLUMNS = 4
_HISTORY_THUMB_MAX_WIDTH = 100
_HISTORY_THUMB_MAX_HEIGHT = 70


def _history_grid_position(index: int) -> Tuple[int, int]:
    """(row, column) within the history strip's own sub-frame for the
    `index`-th (0 = newest) history thumbnail, wrapping every
    _HISTORY_COLUMNS entries onto a new row."""
    return index // _HISTORY_COLUMNS, index % _HISTORY_COLUMNS

_THARGOID_MATERIAL_NAMES = {"tg_shipflightdata", "unknownshipsignature"}
_THARGOID_MUSIC_TRACKS = {"Unknown_Encounter", "Combat_Unknown"}

_ICON_DIR = os.path.join(os.path.dirname(__file__), "icons")

# --- Overlay notification (rewired onto the shared OverlayClient) --------

_ID_PREFIX = "wntb_screenshot_"
_BG_ID = f"{_ID_PREFIX}bg"

# This feature's own EDMCModernOverlay Plugin Group - same treatment as
# landing.py's GROUP_NAME/GROUP_PREFIX (see load.py's registration call),
# needed so the notification panel's background rect actually renders
# under EDMCModernOverlay instead of collapsing to just its border stroke.
GROUP_NAME = "wntb_screenshot"
GROUP_PREFIX = _ID_PREFIX
_MAX_LINES = 3
_TTL_SECONDS = 6
# Legacy overlay coordinates are on a 1280x960 virtual screen.
_ORIGIN_X = 30
_ORIGIN_Y = 700
_LINE_HEIGHT = 18
_COLOUR = "#00d9ff"
_TEXT_SIZE = "normal"
# "#aarrggbb" (alpha first) per the EDMCOverlay wire protocol.
_BG_FILL = "#a0101820"
_BG_PADDING_X = 10
_BG_PADDING_Y = 6
# No font metrics are available over the protocol, so panel width is
# estimated from character count rather than measured. Deliberately
# generous: a slightly wide panel looks fine, but text spilling past a too-
# narrow one doesn't.
_CHAR_WIDTH_PX = 10


@dataclass
class ScreenshotConfig:
    delete_original: bool = False
    group_by_system: bool = False
    show_timer_icon: bool = True
    mask: str = screenshot_naming.DEFAULT_MASK
    hires_on_timer: bool = False
    thargoid_capture: bool = True
    overlay_enabled: bool = True
    poll_interval_s: float = _DEFAULT_POLL_INTERVAL_S


class _HistoryEntry(NamedTuple):
    dest: str
    thumbnail: bytes


# --- Windows Known Folder API: resolves the Pictures folder properly, so
# OneDrive's "Backup" folder redirection (a Pictures folder
# backed up by OneDrive lives under ...\OneDrive\Pictures, not ...\Pictures)
# is followed rather than silently pointing at a folder that doesn't exist.

_FOLDERID_PICTURES = UUID("{33E28130-4E1E-4676-835A-98395C3BC3BB}")


class _GUID(ctypes.Structure):
    _fields_ = [
        ("Data1", ctypes.c_ulong),
        ("Data2", ctypes.c_ushort),
        ("Data3", ctypes.c_ushort),
        ("Data4", ctypes.c_ubyte * 8),
    ]

    def __init__(self, guid: UUID) -> None:
        super().__init__()
        time_low, time_mid, time_hi_version, clock_seq_hi_variant, clock_seq_low, node = guid.fields
        self.Data1 = time_low
        self.Data2 = time_mid
        self.Data3 = time_hi_version
        self.Data4[0] = clock_seq_hi_variant
        self.Data4[1] = clock_seq_low
        for i, b in enumerate(node.to_bytes(6, "big")):
            self.Data4[2 + i] = b


def _pictures_dir() -> str:
    fallback = os.path.join(os.path.expanduser("~"), "Pictures")
    if platform != "win32":
        return fallback

    try:
        sh_get_known_folder_path = ctypes.windll.shell32.SHGetKnownFolderPath
        buffer = ctypes.c_wchar_p()
        guid = _GUID(_FOLDERID_PICTURES)
        result = sh_get_known_folder_path(ctypes.byref(guid), 0, None, ctypes.byref(buffer))
        if result != 0 or not buffer.value:
            return fallback
        path = buffer.value
        ctypes.windll.ole32.CoTaskMemFree(buffer)
        return path
    except Exception:
        logger.debug("Could not resolve the Pictures known folder; using ~/Pictures", exc_info=True)
        return fallback


def _default_source_dir() -> str:
    """Windows: the shell's Pictures folder. Linux: Elite's Pictures folder
    inside its Wine/Proton prefix if one is found, else ~/Pictures."""
    if platform != "win32":
        prefix_dir = platform_support.elite_pictures_dir()
        if prefix_dir:
            return prefix_dir
    return os.path.join(_pictures_dir(), "Frontier Developments", "Elite Dangerous")


_DEFAULT_SOURCE_DIR = _default_source_dir()
_DEFAULT_OUTPUT_DIR = os.path.join(_DEFAULT_SOURCE_DIR, "Converted")


def _get_float(key: str, default: float) -> float:
    """Same string-backed-number convention as discovery.py's own
    _get_int() — EDMC's config API has no dedicated float getter."""
    raw = config.get_str(key)
    try:
        return float(raw) if raw else default
    except ValueError:
        return default


def _poll_interval_ms(cfg: ScreenshotConfig) -> int:
    return max(int(cfg.poll_interval_s * 1000), int(_MIN_POLL_INTERVAL_S * 1000))


def load_config() -> ScreenshotConfig:
    return ScreenshotConfig(
        delete_original=config.get_bool(_CFG_DELETE_ORIGINAL, default=False),
        group_by_system=config.get_bool(_CFG_GROUP_BY_SYSTEM, default=False),
        show_timer_icon=config.get_bool(_CFG_SHOW_TIMER_ICON, default=True),
        mask=config.get_str(_CFG_MASK) or screenshot_naming.DEFAULT_MASK,
        hires_on_timer=config.get_bool(_CFG_HIRES_ON_TIMER, default=False),
        thargoid_capture=config.get_bool(_CFG_THARGOID_CAPTURE, default=True),
        overlay_enabled=config.get_bool(_CFG_OVERLAY_ENABLED, default=True),
        poll_interval_s=max(_get_float(_CFG_POLL_INTERVAL_S, _DEFAULT_POLL_INTERVAL_S), _MIN_POLL_INTERVAL_S),
    )


def current_source_dir() -> str:
    return config.get_str(_CFG_SOURCE_DIR) or _DEFAULT_SOURCE_DIR


def current_output_dir() -> str:
    return config.get_str(_CFG_OUTPUT_DIR) or _DEFAULT_OUTPUT_DIR


def candidate_source_dirs() -> List[str]:
    """
    Directories to check for a screenshot's source file, in priority order.

    The configured Screenshot Directory is always tried first. If it's
    stale — most commonly because it was saved before OneDrive's "Backup"
    folder redirection was accounted for — the OneDrive-toggled variant of
    that same path, and the freshly computed default, are tried next.
    `ScreenshotsController._correct_source_dir` persists whichever one
    actually works, so this list only matters on the first mismatch.
    """
    configured = current_source_dir()
    candidates = [configured, *_onedrive_toggle_variants(configured), _DEFAULT_SOURCE_DIR]

    seen = set()
    unique: List[str] = []
    for candidate in candidates:
        key = os.path.normcase(os.path.normpath(candidate))
        if key not in seen:
            seen.add(key)
            unique.append(candidate)
    return unique


def _onedrive_toggle_variants(path: str) -> List[str]:
    """Return `path` with its home-relative `OneDrive\\` segment added or
    removed, whichever applies — covers a Known Folder (Pictures,
    Documents, Desktop, ...) that OneDrive has redirected, in either
    direction. Windows-only: OneDrive folder redirection doesn't exist
    elsewhere, and matching case-insensitively would be wrong on a
    case-sensitive filesystem."""
    if os.name != "nt":
        return []
    home = os.path.normpath(os.path.expanduser("~"))
    onedrive_home = os.path.join(home, "OneDrive")
    norm_path = os.path.normpath(path)

    if norm_path.lower().startswith(onedrive_home.lower() + os.sep):
        return [home + norm_path[len(onedrive_home):]]
    if norm_path.lower().startswith(home.lower() + os.sep):
        return [onedrive_home + norm_path[len(home):]]
    return []


def open_folder(path: str) -> None:
    if not path or not os.path.isdir(path):
        return
    if os.name == "nt":
        os.startfile(path)  # noqa: S606 — user-initiated, path is our own output dir
    elif os.name == "posix":
        try:
            subprocess.run(["open", path], check=False)
        except FileNotFoundError:
            subprocess.run(["xdg-open", path], check=False)


class ScreenshotsController:
    def __init__(self) -> None:
        self._overlay_client = overlay.OverlayClient()

        # Overlay notification state (line-stack: newest first).
        self._overlay_lines: List[Tuple[str, str, float, str]] = []  # (key, text, expiry, colour)
        self._overlay_rendered_rows = 0

        self._delete_queue: Optional[screenshot_convert.DeleteQueue] = None
        self._parent: Optional[tk.Frame] = None

        self._game_mode: Optional[str] = None
        self._thargoid_scan_pending = False  # one-shot: force capture + crop on the next tick
        self._thargoid_music_active = False  # ambient: crop the *next* screenshot, don't force one
        self._current_image = None  # PIL Image of the most recently converted screenshot
        self._current_crop = None  # PIL Image of its auto-crop, if any
        self._current_dest: Optional[str] = None
        self._current_folder = ""  # dirname of the live capture's output path

        self._history: Deque[_HistoryEntry] = deque(maxlen=_HISTORY_SIZE)  # newest first

        # Main-panel widgets.
        self._status_label: Optional[tk.Label] = None
        self._toggle_button: Optional[tk.Button] = None
        self._icon_on: Optional[tk.PhotoImage] = None
        self._icon_off: Optional[tk.PhotoImage] = None
        self._disclosure_link: Optional[HyperlinkLabel] = None
        self._thumbs_frame: Optional[tk.Frame] = None
        self._full_thumb: Optional[tk.Label] = None
        self._crop_thumb: Optional[tk.Label] = None
        self._history_frame: Optional[tk.Frame] = None
        self._history_thumbs: List[tk.Label] = []
        self._history_photos: List[Optional[tk.PhotoImage]] = []
        self._history_dests: List[Optional[str]] = []
        self._full_photo: Optional[tk.PhotoImage] = None
        self._crop_photo: Optional[tk.PhotoImage] = None
        self._auto_capture_enabled = False
        self._thumbs_expanded = False  # in-memory only, not persisted

        # Settings-tab vars.
        self._source_var: Optional[tk.StringVar] = None
        self._output_var: Optional[tk.StringVar] = None
        self._delete_var: Optional[tk.BooleanVar] = None
        self._group_var: Optional[tk.BooleanVar] = None
        self._show_timer_icon_var: Optional[tk.BooleanVar] = None
        self._mask_var: Optional[tk.StringVar] = None
        self._hires_var: Optional[tk.BooleanVar] = None
        self._thargoid_var: Optional[tk.BooleanVar] = None
        self._poll_interval_var: Optional[tk.StringVar] = None
        self._overlay_var: Optional[tk.BooleanVar] = None
        self._overlay_result_label: Optional[nb.Label] = None

    def set_overlay_client(self, client: overlay.OverlayClient) -> None:
        self._overlay_client = client

    # --- journal dispatch -----------------------------------------------------

    def handle_event(
        self, entry: Dict[str, Any], cmdr: str, system: Optional[str], station: Optional[str],
        state: Dict[str, Any],
    ) -> None:
        event = entry.get("event", "")

        if event == "LoadGame":
            self._game_mode = entry.get("GameMode")
            return

        if event in ("ShutDown", "Died"):
            if self._auto_capture_enabled:
                self._disable_auto_capture()
                self._set_status("Auto-capture stopped")
                logger.info("Auto-capture stopped (%s)", event)
            return

        if event == "Music":
            self._thargoid_music_active = entry.get("MusicTrack") in _THARGOID_MUSIC_TRACKS
            return

        if event == "MaterialCollected" and entry.get("Name") in _THARGOID_MATERIAL_NAMES:
            if screenshot_automation.SUPPORTED and load_config().thargoid_capture:
                self._thargoid_scan_pending = True
                self._fire_capture(hi_res=False)
                logger.info("Thargoid signal scanned — triggering auto-capture")
            return

        if event == "Screenshot":
            self._handle_screenshot(cmdr, system or "", station or "", entry)

    def _handle_screenshot(self, cmdr: str, system: str, station: str, entry: Dict[str, Any]) -> None:
        journal_filename = entry.get("Filename", "")
        configured_source_dir = current_source_dir()
        source_file = screenshot_convert.find_source_file(candidate_source_dirs(), journal_filename)

        if source_file is None:
            logger.warning(
                "Screenshot source file %r not found in the configured Screenshot Directory "
                "or any known fallback location",
                screenshot_naming.journal_basename(journal_filename),
            )
            self._set_status("Screenshot not found — check Screenshot Directory in Settings")
            return

        resolved_source_dir = os.path.dirname(source_file)
        if os.path.normcase(os.path.normpath(resolved_source_dir)) != os.path.normcase(
            os.path.normpath(configured_source_dir),
        ):
            self._correct_source_dir(configured_source_dir, resolved_source_dir)

        cfg = load_config()
        output_dir = current_output_dir()
        entry_system = entry.get("System") or system
        entry_body = entry.get("Body") or station or ""

        if cfg.group_by_system and entry_system:
            output_dir = os.path.join(output_dir, self._safe_folder_name(entry_system))

        dest = screenshot_naming.build_output_path(
            cfg.mask, output_dir, system=entry_system, body=entry_body, cmdr=cmdr,
            source_filename=journal_filename,
        )

        try:
            image = screenshot_convert.convert_to_png(source_file, dest)
        except OSError as exc:
            message = screenshot_convert.describe_os_error(exc)
            logger.warning("Could not convert screenshot %s: %s", source_file, message)
            self._set_status(f"Conversion failed: {message}")
            return

        self._snapshot_current_as_history()

        self._current_image = image
        self._current_dest = dest
        self._show_full_thumbnail(screenshot_convert.thumbnail_photo_data(image))
        self._show_history_thumbnails([(e.thumbnail, e.dest) for e in self._history])

        width = int(entry.get("Width") or image.width)
        height = int(entry.get("Height") or image.height)
        crop_box = self._select_crop_box(width, height)
        self._thargoid_scan_pending = False

        if crop_box is not None and not screenshot_naming.is_high_res(journal_filename):
            self._current_crop = screenshot_convert.crop(image, crop_box)
            self._show_crop_thumbnail(screenshot_convert.thumbnail_photo_data(self._current_crop))
        else:
            self._current_crop = None
            self._show_crop_thumbnail(None)

        if cfg.delete_original and self._delete_queue is not None:
            self._delete_queue.schedule(source_file, _DELETE_GRACE_MS)

        name = os.path.basename(dest)
        self._set_status(name if len(name) <= 40 else name[:37] + "…", folder=os.path.dirname(dest))
        logger.info("Screenshot converted: %s", dest)
        self._overlay_notify("saved", f"Screenshot saved: {name}")

    def _select_crop_box(self, width: int, height: int):
        if self._thargoid_scan_pending or self._thargoid_music_active:
            return screenshot_gui_focus.thargoid_crop_rect(width, height)

        focus = screenshot_gui_focus.current_gui_focus()
        if focus is None:
            return None
        return screenshot_gui_focus.panel_crop_rect(focus, width, height)

    def _safe_folder_name(self, system: str) -> str:
        return "".join(c for c in system if c.isalnum() or c in " ._-()").strip() or "Unknown"

    def _correct_source_dir(self, old_dir: str, new_dir: str) -> None:
        """
        The configured Screenshot Directory didn't hold the file, but one
        of `candidate_source_dirs`'s fallbacks did — persist the directory
        that actually worked, so this doesn't need re-discovering (or a
        manual Settings edit) on every future screenshot.

        If the Converted Directory is still exactly `<old_dir>/Converted`
        (i.e. the commander never customized it away from the auto-
        computed default), it's moved to match — otherwise a deliberately
        chosen output location is left alone.
        """
        logger.info("Auto-correcting Screenshot Directory: %s -> %s", old_dir, new_dir)
        config.set(_CFG_SOURCE_DIR, new_dir)
        if self._source_var is not None:
            self._source_var.set(new_dir)

        expected_default_output = os.path.join(old_dir, "Converted")
        if os.path.normcase(os.path.normpath(current_output_dir())) == os.path.normcase(
            os.path.normpath(expected_default_output),
        ):
            new_output_dir = os.path.join(new_dir, "Converted")
            config.set(_CFG_OUTPUT_DIR, new_output_dir)
            if self._output_var is not None:
                self._output_var.set(new_output_dir)
            logger.info("Auto-correcting Converted Directory to match: %s", new_output_dir)

    def _snapshot_current_as_history(self) -> None:
        """
        Archive the current live capture into the history strip, right
        before it's replaced by a new one. Reads the thumbnail fresh from
        the saved file rather than from `_current_image` — a cheap, simple
        way to always reflect exactly what's on disk, rather than assuming
        it still matches the in-memory copy.
        """
        if self._current_dest is None:
            return
        try:
            thumbnail = screenshot_convert.open_thumbnail_data(
                self._current_dest, max_height=_HISTORY_THUMB_MAX_HEIGHT, max_width=_HISTORY_THUMB_MAX_WIDTH,
            )
        except OSError as exc:
            logger.debug(
                "Could not build history thumbnail for %s: %s",
                self._current_dest, screenshot_convert.describe_os_error(exc),
            )
            return
        self._history.appendleft(_HistoryEntry(self._current_dest, thumbnail))

    # --- auto-capture timer/automation ---------------------------------------

    def _disable_auto_capture(self) -> None:
        if not self._auto_capture_enabled:
            return
        self._auto_capture_enabled = False
        self._apply_toggle_icon()

    def _tick(self) -> None:
        if self._parent is not None and self._parent.winfo_exists():
            cfg = load_config()
            if self._auto_capture_enabled and screenshot_automation.SUPPORTED:
                if screenshot_automation.is_elite_foreground():
                    self._fire_capture(hi_res=cfg.hires_on_timer)
                else:
                    self._set_status("Auto-capture paused (Elite not focused)")
            # Re-read every tick (not just at startup) so a Settings change
            # takes effect on the very next tick, no restart needed.
            self._parent.after(_poll_interval_ms(cfg), self._tick)

    def _fire_capture(self, *, hi_res: bool) -> None:
        if self._parent is None:
            return
        alt_pressed = screenshot_automation.press_screenshot_keys(hi_res=hi_res, game_mode=self._game_mode)
        self._parent.after(_KEY_HOLD_MS, lambda: screenshot_automation.release_screenshot_keys(alt_pressed))

    # --- overlay notification -------------------------------------------------

    def _overlay_notify(self, key: str, text: str, *, colour: str = _COLOUR, ttl: int = _TTL_SECONDS) -> None:
        if not load_config().overlay_enabled:
            return

        now = time.monotonic()
        self._overlay_lines = [line for line in self._overlay_lines if line[0] != key]
        self._overlay_lines.insert(0, (key, text, now + ttl, colour))
        self._overlay_lines = [line for line in self._overlay_lines if line[2] > now][:_MAX_LINES]

        lines = list(self._overlay_lines)
        rendered_rows = self._overlay_rendered_rows
        self._overlay_rendered_rows = len(lines)

        def worker() -> None:
            try:
                self._render_overlay(lines, rendered_rows, now)
            except OSError:
                logger.debug("Could not reach EDMCOverlay for screenshot notification", exc_info=True)

        threading.Thread(target=worker, name="WNTB-screenshot-overlay", daemon=True).start()

    def _render_overlay(self, lines: List[Tuple[str, str, float, str]], previous_rows: int, now: float) -> None:
        client = self._overlay_client
        # Background panel sized to the widest current line and row count,
        # outlined in the newest line's colour so a differently-coloured
        # notification reads as a distinct panel.
        widest = max(len(text) for _, text, _, _ in lines)
        width = widest * _CHAR_WIDTH_PX + _BG_PADDING_X * 2
        height = len(lines) * _LINE_HEIGHT + _BG_PADDING_Y * 2
        bg_ttl = max(1, int(round(max(expiry for _, _, expiry, _ in lines) - now)))
        outline = lines[0][3]
        client.send_shape(
            _BG_ID, "rect", outline, _BG_FILL, _ORIGIN_X - _BG_PADDING_X, _ORIGIN_Y - _BG_PADDING_Y,
            width, height, ttl=bg_ttl,
        )

        for row, (_key, text, expiry, colour) in enumerate(lines):
            ttl = max(1, int(round(expiry - now)))
            client.send_message(f"{_ID_PREFIX}{row}", text, colour, _ORIGIN_X, _ORIGIN_Y + row * _LINE_HEIGHT, ttl=ttl, size=_TEXT_SIZE)
        for row in range(len(lines), previous_rows):
            client.send_message(f"{_ID_PREFIX}{row}", "", "white", _ORIGIN_X, _ORIGIN_Y + row * _LINE_HEIGHT, ttl=1)

    def _overlay_clear(self) -> None:
        rendered_rows = self._overlay_rendered_rows
        self._overlay_lines = []
        self._overlay_rendered_rows = 0
        if not rendered_rows:
            return
        client = self._overlay_client

        def worker() -> None:
            try:
                for row in range(rendered_rows):
                    client.send_message(f"{_ID_PREFIX}{row}", "", "white", _ORIGIN_X, _ORIGIN_Y + row * _LINE_HEIGHT, ttl=1)
                client.send_shape(_BG_ID, "rect", "", "", _ORIGIN_X - _BG_PADDING_X, _ORIGIN_Y - _BG_PADDING_Y, 1, 1, ttl=1)
            except OSError:
                logger.debug("Could not reach EDMCOverlay to clear screenshot notification", exc_info=True)

        threading.Thread(target=worker, name="WNTB-screenshot-overlay-clear", daemon=True).start()

    # --- main-panel widgets -------------------------------------------------

    def build_panel(self, parent: tk.Frame) -> None:
        parent.columnconfigure(0, weight=1)
        self._parent = parent

        self._status_label = panelkit.wrap_label(parent, text="Waiting for a screenshot…", anchor=tk.W)
        self._status_label.grid(row=0, column=0, sticky=tk.W)
        self._status_label.bind("<Button-1>", lambda _e: open_folder(self._current_folder))

        self._icon_on = tk.PhotoImage(file=os.path.join(_ICON_DIR, "timer_enabled.gif"))
        self._icon_off = tk.PhotoImage(file=os.path.join(_ICON_DIR, "timer_disabled.gif"))

        if screenshot_automation.SUPPORTED:
            self._toggle_button = tk.Button(
                parent, image=self._icon_off, relief=tk.FLAT, command=self._toggle_auto_capture,
            )
            self._toggle_button.grid(row=0, column=1, sticky=tk.E, padx=(4, 0))
            self._apply_show_timer_icon()

        # HyperlinkLabel, not a plain Label: it's EDMC's standard clickable-
        # text widget, so it already picks up correct link styling in every
        # EDMC theme. Its `url` is normally a real link opened on click;
        # here it's repurposed as a click callback that toggles the
        # thumbnail row instead — returning a falsy value keeps
        # HyperlinkLabel from trying to open anything.
        self._disclosure_link = HyperlinkLabel(parent, text="Click to expand", url=self._disclosure_clicked)
        self._disclosure_link.grid(row=0, column=2, sticky=tk.E, padx=(4, 0))

        self._thumbs_frame = tk.Frame(parent)
        self._thumbs_frame.grid(row=1, column=0, columnspan=3, sticky=tk.W, pady=(4, 0))

        self._full_thumb = tk.Label(self._thumbs_frame)
        self._full_thumb.grid(row=0, column=0, padx=(0, 8))
        self._full_thumb.bind("<Button-1>", lambda _e: self._open_preview(self._preview_full, "Full screenshot"))
        self._full_thumb.grid_remove()

        self._crop_thumb = tk.Label(self._thumbs_frame)
        self._crop_thumb.grid(row=0, column=1)
        self._crop_thumb.bind("<Button-1>", lambda _e: self._open_preview(self._preview_crop, "Cropped screenshot"))
        self._crop_thumb.grid_remove()

        tk.Label(self._thumbs_frame, text="Click a thumbnail to preview it", font=("TkDefaultFont", 7)).grid(
            row=1, column=0, columnspan=2, sticky=tk.W, pady=(2, 0),
        )

        tk.Label(self._thumbs_frame, text="Recent — click to preview", font=("TkDefaultFont", 7)).grid(
            row=2, column=0, columnspan=_HISTORY_COLUMNS, sticky=tk.W, pady=(6, 0),
        )

        self._history_frame = tk.Frame(self._thumbs_frame)
        self._history_frame.grid(row=3, column=0, columnspan=_HISTORY_COLUMNS, sticky=tk.W)

        self._history_thumbs = []
        self._history_photos = [None] * _HISTORY_SIZE
        self._history_dests = [None] * _HISTORY_SIZE
        for i in range(_HISTORY_SIZE):
            row, column = _history_grid_position(i)
            thumb = tk.Label(self._history_frame)
            thumb.grid(row=row, column=column, padx=(0, 4), pady=(0, 4))
            thumb.bind("<Button-1>", lambda _e, index=i: self._open_history_preview(index))
            thumb.grid_remove()
            self._history_thumbs.append(thumb)

        self._apply_thumbs_expanded()
        # theme.update() (called once, on the mode frame, from ui.py) only
        # recolors direct children - not enough for _thumbs_frame's own
        # nested thumbnail/hint labels. Walk the whole subtree instead.
        panelkit.apply_theme_deep(parent)

        self._delete_queue = screenshot_convert.DeleteQueue(parent.after)
        parent.after(_poll_interval_ms(load_config()), self._tick)

    def _apply_show_timer_icon(self) -> None:
        if self._toggle_button is None:
            return
        if load_config().show_timer_icon:
            self._toggle_button.grid()
        else:
            self._toggle_button.grid_remove()

    def _toggle_auto_capture(self) -> None:
        self._auto_capture_enabled = not self._auto_capture_enabled
        self._apply_toggle_icon()
        if self._auto_capture_enabled:
            logger.info("Auto-capture enabled")
            self._set_status("Auto-capture enabled")
        else:
            logger.info("Auto-capture disabled")
            self._set_status("Auto-capture disabled")

    def _apply_toggle_icon(self) -> None:
        if self._toggle_button is None:
            return
        self._toggle_button.configure(image=self._icon_on if self._auto_capture_enabled else self._icon_off)

    def _disclosure_clicked(self, _current_text: str) -> str:
        self._thumbs_expanded = not self._thumbs_expanded
        self._apply_thumbs_expanded()
        return ""

    def _apply_thumbs_expanded(self) -> None:
        """Thumbnails always start collapsed on launch — only the status
        row shows until the commander opts in for that session.
        Deliberately not persisted: reset every time EDMC (re)starts."""
        if self._thumbs_frame is None or self._disclosure_link is None:
            return
        if self._thumbs_expanded:
            self._thumbs_frame.grid()
            self._disclosure_link["text"] = "Click to collapse"
        else:
            self._thumbs_frame.grid_remove()
            self._disclosure_link["text"] = "Click to expand"

    def _set_status(self, text: str, *, folder: str = "") -> None:
        if folder:
            self._current_folder = folder
        if self._status_label is not None:
            self._status_label["text"] = text

    def _show_full_thumbnail(self, photo_data: bytes) -> None:
        if self._full_thumb is None:
            return
        self._full_photo = tk.PhotoImage(data=photo_data)
        self._full_thumb["image"] = self._full_photo
        self._full_thumb.grid()

    def _show_crop_thumbnail(self, photo_data: Optional[bytes]) -> None:
        if self._crop_thumb is None:
            return
        if photo_data is None:
            self._crop_thumb.grid_remove()
            return
        self._crop_photo = tk.PhotoImage(data=photo_data)
        self._crop_thumb["image"] = self._crop_photo
        self._crop_thumb.grid()

    def _show_history_thumbnails(self, entries: List[Tuple[bytes, str]]) -> None:
        for i, thumb in enumerate(self._history_thumbs):
            if i < len(entries):
                data, dest = entries[i]
                self._history_photos[i] = tk.PhotoImage(data=data)
                thumb["image"] = self._history_photos[i]
                self._history_dests[i] = dest
                thumb.grid()
            else:
                self._history_dests[i] = None
                thumb.grid_remove()

    # --- preview popups --------------------------------------------------------

    def _preview_bounds(self) -> Tuple[int, int]:
        """(max_width, max_height) for the preview popup: `_PREVIEW_MAX_WIDTH`/
        `_HEIGHT`, further capped to `_PREVIEW_SCREEN_FRACTION` of the
        actual screen so a maximized preview still leaves room for its own
        title bar and button row on a smaller or non-widescreen monitor."""
        if self._parent is None:
            return _PREVIEW_MAX_WIDTH, _PREVIEW_MAX_HEIGHT
        max_width = min(_PREVIEW_MAX_WIDTH, int(self._parent.winfo_screenwidth() * _PREVIEW_SCREEN_FRACTION))
        max_height = min(_PREVIEW_MAX_HEIGHT, int(self._parent.winfo_screenheight() * _PREVIEW_SCREEN_FRACTION))
        return max_width, max_height

    def _preview_full(self) -> Optional[bytes]:
        if self._current_image is None:
            return None
        max_width, max_height = self._preview_bounds()
        return screenshot_convert.thumbnail_photo_data(self._current_image, max_height=max_height, max_width=max_width)

    def _preview_crop(self) -> Optional[bytes]:
        if self._current_crop is None:
            return None
        max_width, max_height = self._preview_bounds()
        return screenshot_convert.thumbnail_photo_data(self._current_crop, max_height=max_height, max_width=max_width)

    def _preview_history(self, index: int) -> Optional[bytes]:
        if index >= len(self._history):
            return None
        entry = self._history[index]
        max_width, max_height = self._preview_bounds()
        try:
            return screenshot_convert.open_thumbnail_data(entry.dest, max_height=max_height, max_width=max_width)
        except OSError as exc:
            logger.warning("Could not open history capture %s: %s", entry.dest, screenshot_convert.describe_os_error(exc))
            self._set_status(f"Could not open {os.path.basename(entry.dest)}")
            return None

    def _open_preview(self, get_preview_data, title: str) -> None:
        """View-only preview — the screenshot is already saved by the time
        any thumbnail is clickable, so there is nothing to choose or
        confirm here: just a larger look, and a way to jump to the file on
        disk."""
        if self._parent is None:
            return
        data = get_preview_data()
        if data is None:
            return
        self._show_preview_dialog(data, title, self._current_folder)

    def _open_history_preview(self, index: int) -> None:
        if self._parent is None:
            return
        if index >= len(self._history_dests) or self._history_dests[index] is None:
            return
        folder = os.path.dirname(self._history_dests[index])
        data = self._preview_history(index)
        if data is None:
            return
        self._show_preview_dialog(data, "Recent capture", folder)

    def _show_preview_dialog(self, data: bytes, title: str, folder: str) -> None:
        # Preview dialogs are separate Toplevels, not part of EDMC's main
        # window, so they don't feed into its cross-plugin auto-sizing —
        # but the image itself is still bounded (see _preview_bounds) so an
        # extreme aspect ratio source can't produce an oversized popup.
        top = tk.Toplevel(self._parent)
        ui_style.skin(top)  # WNTB's own look, not EDMC's theme - see plugin/uikit
        top.title(f"WNTB — {title}")
        top.resizable(False, False)

        photo = tk.PhotoImage(data=data)
        image_label = tk.Label(top, image=photo)
        image_label.image = photo  # keep a reference — PhotoImage has no other owner
        image_label.grid(row=0, column=0, columnspan=2, padx=8, pady=(8, 0))

        tk.Label(top, text="Already saved — Open Folder to find it.", font=("TkDefaultFont", 8)).grid(
            row=1, column=0, columnspan=2, padx=8, pady=(4, 0),
        )

        if folder:
            tk.Button(top, text="Open Folder", command=lambda: open_folder(folder)).grid(
                row=2, column=0, sticky=tk.E, padx=(8, 4), pady=8,
            )
            tk.Button(top, text="Close", command=top.destroy).grid(row=2, column=1, sticky=tk.W, padx=(4, 8), pady=8)
        else:
            tk.Button(top, text="Close", command=top.destroy).grid(row=2, column=0, columnspan=2, pady=8)

    # --- Settings tab --------------------------------------------------------

    def build_settings(self, notebook: nb.Notebook) -> None:
        frame = nb.Frame(notebook)
        frame.columnconfigure(1, weight=1)
        notebook.add(frame, text="Screenshots")
        row = 0

        cfg = load_config()

        self._source_var = tk.StringVar(value=current_source_dir())
        row = self._dir_row(frame, row, "Screenshot Directory", self._source_var)

        self._output_var = tk.StringVar(value=current_output_dir())
        row = self._dir_row(frame, row, "Converted Directory", self._output_var)

        self._delete_var = tk.BooleanVar(value=cfg.delete_original)
        nb.Checkbutton(frame, text="Delete original file after conversion", variable=self._delete_var).grid(
            row=row, column=0, columnspan=3, sticky=tk.W, padx=10, pady=(8, 0),
        )
        row += 1

        self._group_var = tk.BooleanVar(value=cfg.group_by_system)
        nb.Checkbutton(
            frame, text="Group converted files into a per-system subfolder", variable=self._group_var,
        ).grid(row=row, column=0, columnspan=3, sticky=tk.W, padx=10)
        row += 1

        if screenshot_automation.SUPPORTED:
            self._show_timer_icon_var = tk.BooleanVar(value=cfg.show_timer_icon)
            nb.Checkbutton(
                frame, text="Show the auto-capture timer icon on the main window", variable=self._show_timer_icon_var,
            ).grid(row=row, column=0, columnspan=3, sticky=tk.W, padx=10)
            row += 1

        nb.Label(frame, text="Filename Mask").grid(row=row, column=0, sticky=tk.W, padx=10, pady=(10, 0))
        self._mask_var = tk.StringVar(value=cfg.mask)
        tk.OptionMenu(frame, self._mask_var, *screenshot_naming.MASK_PRESETS).grid(
            row=row, column=1, columnspan=2, sticky=tk.W, pady=(10, 0),
        )
        row += 1

        auto_note, auto_supported = platform_support.input_support_note()
        nb.Label(
            frame, text="Auto-timer and Thargoid-scan capture (they press the screenshot key for you). " + auto_note,
            wraplength=440, justify=tk.LEFT, foreground="#2e7d32" if auto_supported else "#c07000",
        ).grid(row=row, column=0, columnspan=3, sticky=tk.W, padx=10, pady=(12, 0))
        row += 1

        if screenshot_automation.SUPPORTED:
            interval_row = tk.Frame(frame)
            interval_row.grid(row=row, column=0, columnspan=3, sticky=tk.W, padx=10, pady=(12, 0))
            nb.Label(interval_row, text="Auto-capture poll interval (seconds):").pack(side=tk.LEFT)
            self._poll_interval_var = tk.StringVar(value=f"{cfg.poll_interval_s:g}")
            nb.EntryMenu(interval_row, textvariable=self._poll_interval_var, width=6).pack(
                side=tk.LEFT, padx=(4, 0),
            )
            nb.Label(interval_row, text=f"(minimum {_MIN_POLL_INTERVAL_S:g})").pack(side=tk.LEFT, padx=(4, 0))
            row += 1

            self._hires_var = tk.BooleanVar(value=cfg.hires_on_timer)
            nb.Checkbutton(
                frame, text="Use high-resolution capture on the auto-timer (Solo play only)", variable=self._hires_var,
            ).grid(row=row, column=0, columnspan=3, sticky=tk.W, padx=10, pady=(4, 0))
            row += 1

            self._thargoid_var = tk.BooleanVar(value=cfg.thargoid_capture)
            nb.Checkbutton(
                frame, text="Automatically capture a screenshot when scanning a Thargoid signal",
                variable=self._thargoid_var,
            ).grid(row=row, column=0, columnspan=3, sticky=tk.W, padx=10)
            row += 1

        self._overlay_var = tk.BooleanVar(value=cfg.overlay_enabled)
        nb.Checkbutton(
            frame, text="Show a notification on the in-game overlay when a screenshot is saved",
            variable=self._overlay_var,
        ).grid(row=row, column=0, columnspan=3, sticky=tk.W, padx=10, pady=(12, 2))
        row += 1

        action_row = tk.Frame(frame)
        action_row.grid(row=row, column=0, columnspan=3, sticky=tk.W, padx=10, pady=(0, 10))
        tk.Button(action_row, text="Test Overlay", command=self._test_overlay).pack(side=tk.LEFT)
        self._overlay_result_label = nb.Label(action_row, text="", wraplength=320, justify=tk.LEFT)
        self._overlay_result_label.pack(side=tk.LEFT, padx=(10, 0))

    def _dir_row(self, frame: nb.Frame, row: int, label: str, var: tk.StringVar) -> int:
        nb.Label(frame, text=label).grid(row=row, column=0, sticky=tk.W, padx=10, pady=(4, 0))
        entry = nb.EntryMenu(frame, textvariable=var)
        entry.grid(row=row, column=1, sticky=tk.EW, pady=(4, 0))
        tk.Button(frame, text="Browse…", command=lambda: self._browse(var)).grid(
            row=row, column=2, sticky=tk.W, padx=(4, 10), pady=(4, 0),
        )
        return row + 1

    def _browse(self, var: tk.StringVar) -> None:
        chosen = filedialog.askdirectory(initialdir=var.get() or os.path.expanduser("~"))
        if chosen:
            var.set(chosen)

    def _test_overlay(self) -> None:
        if self._overlay_result_label is None:
            return
        cfg = overlay.load_config()
        client = overlay.OverlayClient(cfg)
        frame = self._overlay_result_label

        def worker() -> None:
            try:
                client.send_shape(
                    _BG_ID, "rect", _COLOUR, _BG_FILL, _ORIGIN_X - _BG_PADDING_X, _ORIGIN_Y - _BG_PADDING_Y,
                    260, _LINE_HEIGHT + _BG_PADDING_Y * 2, ttl=_TTL_SECONDS,
                )
                client.send_message(
                    f"{_ID_PREFIX}0", "Screenshot saved: Test.png", _COLOUR, _ORIGIN_X, _ORIGIN_Y, ttl=_TTL_SECONDS,
                    size=_TEXT_SIZE,
                )
                outcome, color = "Sent — check your overlay.", "#2e7d32"
            except OSError as err:
                outcome, color = f"Could not reach EDMCOverlay at {cfg.host}:{cfg.port} ({err}).", "#c07000"
            try:
                frame.after(0, lambda: (frame.configure(text=outcome, foreground=color)))
            except tk.TclError:
                pass

        threading.Thread(target=worker, name="WNTB-screenshot-overlay-test", daemon=True).start()

    def save_settings(self) -> None:
        if self._source_var is None:
            return
        config.set(_CFG_SOURCE_DIR, self._source_var.get().strip())
        config.set(_CFG_OUTPUT_DIR, self._output_var.get().strip())
        config.set(_CFG_DELETE_ORIGINAL, self._delete_var.get())
        config.set(_CFG_GROUP_BY_SYSTEM, self._group_var.get())
        if self._show_timer_icon_var is not None:
            config.set(_CFG_SHOW_TIMER_ICON, self._show_timer_icon_var.get())
        config.set(_CFG_MASK, self._mask_var.get())
        if self._poll_interval_var is not None:
            try:
                interval = float(self._poll_interval_var.get().strip())
            except ValueError:
                interval = _DEFAULT_POLL_INTERVAL_S
            config.set(_CFG_POLL_INTERVAL_S, str(max(interval, _MIN_POLL_INTERVAL_S)))
        if self._hires_var is not None:
            config.set(_CFG_HIRES_ON_TIMER, self._hires_var.get())
        if self._thargoid_var is not None:
            config.set(_CFG_THARGOID_CAPTURE, self._thargoid_var.get())
        config.set(_CFG_OVERLAY_ENABLED, self._overlay_var.get())

        self._apply_show_timer_icon()
        if not load_config().overlay_enabled:
            self._overlay_clear()


controller = ScreenshotsController()


def set_overlay_client(client: overlay.OverlayClient) -> None:
    controller.set_overlay_client(client)


def handle_event(entry: Dict[str, Any], cmdr: str, system: Optional[str], station: Optional[str], state: Dict[str, Any]) -> None:
    controller.handle_event(entry, cmdr, system, station, state)


def build_panel(parent: tk.Frame) -> None:
    controller.build_panel(parent)


def build_settings(notebook: nb.Notebook) -> None:
    controller.build_settings(notebook)


def save_settings() -> None:
    controller.save_settings()
