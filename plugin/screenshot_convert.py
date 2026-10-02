"""Screenshot conversion: source BMP/PNG -> renamed PNG, plus thumbnails."""

from __future__ import annotations

import errno
import io
import logging
import os
from collections import deque
from typing import Iterable, Optional, Tuple

from config import appname
from PIL import Image

plugin_name = os.path.basename(os.path.dirname(__file__))
logger = logging.getLogger(f"{appname}.{plugin_name}")


def find_source_file(candidate_dirs: Iterable[str], journal_filename: str) -> Optional[str]:
    """
    Return the first existing path for `journal_filename`'s basename across
    `candidate_dirs`, in order — the configured Screenshot Directory is
    always tried first (see `screenshots.candidate_source_dirs`), so this
    only changes behaviour when that configured directory turns out to be
    wrong (e.g. a stale setting from before a OneDrive redirect was
    detected).

    `journal_filename` values look like "\\ED_Pictures\\Screenshot_0001.bmp"
    — a leading path fragment Elite writes but that isn't a real filesystem
    path. Only the basename is used.
    """
    basename = os.path.basename(journal_filename)
    for directory in candidate_dirs:
        candidate = os.path.join(directory, basename)
        if os.path.isfile(candidate):
            return candidate
    return None


def ensure_directory(path: str) -> None:
    try:
        os.makedirs(path, exist_ok=True)
    except OSError as exc:
        if exc.errno != errno.EEXIST:
            raise


def describe_os_error(exc: OSError) -> str:
    """
    A log/status-friendly description of an OSError hit while reading,
    writing, or deleting a screenshot file.

    A bare PermissionError here reads like a plugin bug, but is usually
    Windows itself denying EDMarketConnector.exe access to the folder —
    most often Controlled Folder Access (Windows Security > Virus & threat
    protection > Ransomware protection) or another antivirus's real-time
    protection, either of which fails silently from the plugin's point of
    view unless this is spelled out.
    """
    if isinstance(exc, PermissionError) and os.name != "nt":
        return f"{exc} — check that your user can read and write that folder (permissions or mount options)"
    if isinstance(exc, PermissionError):
        return (
            f"{exc} — likely blocked by Windows security (Controlled Folder "
            "Access or antivirus real-time protection); check Windows Security "
            "> Virus & threat protection > Ransomware protection > Controlled "
            "folder access and allow EDMarketConnector.exe if it's enabled"
        )
    return str(exc)


def convert_to_png(source_file: str, destination_file: str) -> Image.Image:
    """Load `source_file` and save it as PNG at `destination_file`; returns the image."""
    ensure_directory(os.path.dirname(destination_file))
    image = Image.open(source_file)
    image.load()  # force the read now, before the source may be deleted
    image.save(destination_file, "PNG")
    return image


def crop(image: Image.Image, box: Tuple[int, int, int, int]) -> Image.Image:
    return image.crop(box)


def thumbnail_photo_data(image: Image.Image, max_height: int = 140, max_width: int = 200) -> bytes:
    """
    Return GIF bytes suitable for tk.PhotoImage(data=...).

    Both dimensions are bounded — not just height — so an ultrawide or
    triple-monitor (Surround) screenshot's aspect ratio can't stretch this
    thumbnail wide enough to widen the main EDMC window. PIL's thumbnail()
    fits within the (max_width, max_height) box on whichever axis is
    tighter, preserving aspect ratio.
    """
    copy = image.copy()
    copy.thumbnail((max_width, max_height), Image.Resampling.LANCZOS)

    buffer = io.BytesIO()
    copy.convert("RGB").save(buffer, format="GIF")
    return buffer.getvalue()


def open_thumbnail_data(path: str, *, max_height: int, max_width: int) -> bytes:
    """
    Thumbnail bytes for an already-saved output file — used for the recent
    captures history strip, which shows what actually ended up on disk for
    older captures rather than an in-memory image (only the newest
    capture's full-resolution PIL Image is kept around).
    """
    with Image.open(path) as image:
        image.load()
        return thumbnail_photo_data(image, max_height=max_height, max_width=max_width)


class DeleteQueue:
    """Deletes original source files after a grace period, oldest first.

    The grace period gives other plugins a chance to see/process the
    original screenshot file before it disappears.
    """

    def __init__(self, scheduler) -> None:
        """`scheduler(delay_ms, callback)` — typically a Tk widget's `.after`."""
        self._scheduler = scheduler
        self._pending: "deque[str]" = deque()

    def schedule(self, path: str, delay_ms: int) -> None:
        self._pending.append(path)
        self._scheduler(delay_ms, self._delete_next)

    def _delete_next(self) -> None:
        if not self._pending:
            return
        path = self._pending.popleft()
        try:
            os.remove(path)
            logger.debug("Deleted original screenshot: %s", path)
        except OSError as exc:
            logger.warning("Could not delete original screenshot %s: %s", path, describe_os_error(exc))
