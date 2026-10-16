"""WNTB's built-in overlay: which overlay draws (EDMCModernOverlay or WNTB's own), and the glue between the two.

EDMCModernOverlay is a separate program WNTB talks to over a local socket. The built-in overlay is a window WNTB draws itself (`overlay_window.py`, Windows only) from a scene the
overlay features fill (`overlay_scene.py`, `overlay_raster.py`). The choice is the **Overlay** setting on Settings -> Overlays -> Overlay Connection and is off until the player turns it on.
When it is on, `overlay.OverlayClient` hands every payload to the scene instead of the socket, so no overlay feature changes; placement reads the game window's size and display scaling from
here instead of from EDMCModernOverlay's log. Only one of the two ever draws.
"""

from __future__ import annotations

import logging
import os
import time
from typing import List, Optional

from config import appname, config

from . import overlay_fonts, overlay_layout as layout, overlay_raster, overlay_style, overlay_window
from .overlay_scene import Scene

plugin_name = os.path.basename(os.path.dirname(__file__))
logger = logging.getLogger(f"{appname}.{plugin_name}")

CFG_BACKEND = "wntb_overlay_backend"
CFG_FONT = "wntb_overlay_builtin_font"            # the font file (in WNTB's own fonts folder) the built-in overlay draws in; empty means the bundled one
CFG_KEEP = "wntb_overlay_keep_showing"          # keep drawing when Elite is not the window in front (to take screenshots with another tool)
MODERN = "modern"
BUILTIN = "builtin"
SOURCE = "WNTB built-in overlay"
FALLBACK_SCREEN = (1920, 1080)

scene = Scene()
_groups: List[str] = []


def set_groups(groups) -> None:
    """The id prefixes of the overlay displays (each feature's plugin group), so a display is placed as one piece."""
    _groups[:] = [prefix for _name, prefix in groups]


def groups() -> List[str]:
    return list(_groups)


def fonts_folder() -> str:
    """WNTB's own fonts folder: the bundled font and any font the player adds."""
    return overlay_fonts.own_dir(os.path.dirname(os.path.abspath(__file__)))


def chosen_font() -> str:
    return config.get_str(CFG_FONT) or overlay_fonts.BUNDLED


def save_font(name: str) -> None:
    config.set(CFG_FONT, "" if name == overlay_fonts.BUNDLED else name)


def _font_path() -> str:
    """The font file the built-in overlay draws in: the one chosen (in WNTB's own fonts folder), else the bundled Source Sans 3, else a system font."""
    folder = fonts_folder()
    for name in (chosen_font(), overlay_fonts.BUNDLED):
        path = os.path.join(folder, name)
        if name and os.path.isfile(path):
            return path
    return overlay_raster.default_font_path()


_PATH_SECONDS = 2.0
_path_cache = {"at": 0.0, "path": ""}
_measure_fonts: dict = {}
_widths: dict = {}
_MEASURE_SCALE = 8                      # measured at eight times the size and divided, so whole-pixel hinting does not blur the width


def _current_font_path() -> str:
    now = time.monotonic()
    if now - _path_cache["at"] > _PATH_SECONDS or not _path_cache["path"] and _path_cache["at"] == 0.0:
        _path_cache.update(at=now, path=_font_path())
    return _path_cache["path"]


def measure(text: str, size: str) -> float:
    """The width in logical pixels of `text` at a size name, in the font the built-in overlay draws in (see `overlay_style.set_text_measurer`)."""
    path = _current_font_path()
    key = (path, size, text)
    width = _widths.get(key)
    if width is None:
        fonts = _measure_fonts.get(path)
        if fonts is None:
            fonts = _measure_fonts[path] = overlay_raster.Fonts(path)
        px = overlay_raster.FONT_PX.get(size, overlay_raster.DEFAULT_FONT_PX)
        width = fonts.get(px * _MEASURE_SCALE).getlength(text) / _MEASURE_SCALE
        if len(_widths) > 20000:
            _widths.clear()
        _widths[key] = width
    return width


def install_measurer() -> None:
    """Cards are sized from measured text while the built-in overlay is chosen, and from the character estimates otherwise."""
    overlay_style.set_text_measurer(measure if selected() == BUILTIN else None)


def keep_showing() -> bool:
    return bool(config.get_bool(CFG_KEEP, default=False))


def save_keep_showing(keep: bool) -> None:
    config.set(CFG_KEEP, bool(keep))


window = overlay_window.OverlayWindow(scene, _current_font_path, keep_showing, groups)


def supported() -> bool:
    return overlay_window.supported()


def selected() -> str:
    """BUILTIN when the player chose the built-in overlay and this machine can run it, otherwise MODERN."""
    return BUILTIN if supported() and config.get_str(CFG_BACKEND) == BUILTIN else MODERN


def accepting() -> bool:
    """Whether payloads go to the scene (the built-in overlay is chosen) instead of the socket."""
    return selected() == BUILTIN


def save_choice(choice: str) -> None:
    config.set(CFG_BACKEND, BUILTIN if choice == BUILTIN else MODERN)


def apply_choice() -> None:
    """Starts or stops the window to match the saved choice (and drops what the other overlay was showing)."""
    install_measurer()
    if selected() == BUILTIN:
        window.start()
    else:
        window.stop()
        scene.clear()


def start() -> None:
    install_measurer()
    if selected() == BUILTIN:
        window.start()


def stop() -> None:
    overlay_style.set_text_measurer(None)
    window.stop()
    scene.clear()


def screen() -> Optional[layout.Screen]:
    """The screen as the built-in overlay sees it, for placement: the game window's size and display scaling now, or a stand-in until Elite is running. None when it is not chosen."""
    if selected() != BUILTIN:
        return None
    geometry = window.geometry
    if geometry:
        _x, _y, width, height, ratio = geometry
        return layout.Screen(width, height, layout.MODE_FILL, f"{SOURCE}, Elite's window", None, ratio, True, True)
    return layout.Screen(*FALLBACK_SCREEN, layout.MODE_FILL, f"{SOURCE}, waiting for Elite (assuming 1920 x 1080)", None, 1.0, True, True)


def snapshot(width: int, height: int):
    """The overlay as it is now, drawn onto a transparent picture of the size of a screenshot, or None when the built-in overlay is not on, Elite's window is not known or nothing is showing.
    The scale comes from the game window's size and display scaling, so a screenshot of a different size than the window still lines up."""
    geometry = window.geometry
    if selected() != BUILTIN or not geometry or width <= 0 or height <= 0:
        return None
    items = scene.items()
    if not items:
        return None
    _x, _y, client_w, _h, dpi = geometry
    return overlay_raster.render(items, width, height, dpi * (width / client_w), overlay_raster.Fonts(_font_path()), groups())


def status_text() -> str:
    """One line for the Settings tab."""
    if selected() != BUILTIN:
        return ""
    if window.error:
        return window.error
    if not window.running:
        return "The built-in overlay is on and will start with EDMC."
    geometry = window.geometry
    if not geometry:
        return "The built-in overlay is running; start Elite in borderless or windowed mode and it will appear over it."
    return f"The built-in overlay is running over Elite's window ({geometry[2]} x {geometry[3]}, display scaling {int(round(geometry[4] * 100))}%)."
