"""The font every overlay is drawn in, chosen from Settings -> Overlays -> Appearance.

EDMCModernOverlay (the optional overlay helper) draws all text, from every plugin, in one font. It takes the first font in its `overlay_client/fonts/preferred_fonts.txt`
that loads, and its default is Elite's cockpit font, which has capital letters only. The overlay cannot take a font for one message, so WNTB cannot give its own cards a font;
what it can do is keep that one choice for you: list the fonts in that folder, add a font file you downloaded (for example from Google Fonts), and put your pick first in
`preferred_fonts.txt`. The change reaches every plugin's overlay and takes effect when the overlay starts again. Nothing here needs Tk or EDMC; the paths come in as arguments.
"""

from __future__ import annotations

import os
import shutil
from typing import List, Optional, Tuple

FONT_EXTENSIONS = (".ttf", ".otf")
MAX_FONT_BYTES = 20 * 1024 * 1024          # a file larger than this is not a font to put in front of an overlay
PREFERRED_FILE = "preferred_fonts.txt"
HEADER = "; One font filename per line. First successfully loaded entry wins."
DEFAULT_LABEL = "Overlay default"
DEFAULT_FONT = "Eurocaps.ttf"              # the overlay's own first choice
_OVERLAY_FOLDER = "EDMCModernOverlay"


def fonts_dir(plugins_dir: str) -> str:
    """EDMCModernOverlay's fonts folder inside the plugins folder (it may not exist: the overlay may not be installed)."""
    return os.path.join(plugins_dir, _OVERLAY_FOLDER, "overlay_client", "fonts")


def installed(folder: str) -> List[str]:
    """Font files (.ttf, .otf) in the folder, sorted without regard to case; the emoji and symbol fonts the overlay ships are left out."""
    try:
        names = os.listdir(folder)
    except OSError:
        return []
    return sorted((n for n in names if n.lower().endswith(FONT_EXTENSIONS) and "emoji" not in n.lower() and not n.lower().startswith("unifont")), key=str.lower)


def preferred(folder: str) -> List[str]:
    """The font files named in preferred_fonts.txt, in order (comments and blank lines skipped)."""
    try:
        with open(os.path.join(folder, PREFERRED_FILE), encoding="utf-8") as handle:
            lines = handle.read().splitlines()
    except OSError:
        return []
    return [line.strip() for line in lines if line.strip() and not line.strip().startswith(";")]


def current(folder: str) -> str:
    """The font the list asks for first, as it is written there, or "" when the list is empty."""
    names = preferred(folder)
    return names[0] if names else ""


def is_default(name: str) -> bool:
    """True for the overlay's own choice (Eurocaps), or no choice at all."""
    return not name or name.casefold() == DEFAULT_FONT.casefold()


def set_first(folder: str, name: str) -> None:
    """Puts `name` first in preferred_fonts.txt, keeping the others below it; an empty name restores the overlay's default (Eurocaps first). The old file is kept
    once as preferred_fonts.txt.bak."""
    path = os.path.join(folder, PREFERRED_FILE)
    backup = path + ".bak"
    if os.path.exists(path) and not os.path.exists(backup):
        shutil.copyfile(path, backup)
    first = name or DEFAULT_FONT
    names = [first] + [n for n in preferred(folder) if n.casefold() != first.casefold()]
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(HEADER + "\n" + "\n".join(names) + "\n")


def add_font(folder: str, source: str) -> Tuple[Optional[str], str]:
    """Copies a font file into the fonts folder. Returns (file name, "") or (None, why it was refused)."""
    name = os.path.basename(source)
    if not name.lower().endswith(FONT_EXTENSIONS):
        return None, "That is not a .ttf or .otf font file."
    try:
        size = os.path.getsize(source)
    except OSError as err:
        return None, f"Could not read the file ({err})."
    if size <= 0 or size > MAX_FONT_BYTES:
        return None, "The file is empty or too large to be a font."
    if not os.path.isdir(folder):
        return None, "EDMCModernOverlay's fonts folder was not found, so there is nowhere to put the font."
    target = os.path.join(folder, name)
    try:
        if os.path.abspath(source) != os.path.abspath(target):
            shutil.copyfile(source, target)
    except OSError as err:
        return None, f"Could not copy the font ({err})."
    return name, ""
