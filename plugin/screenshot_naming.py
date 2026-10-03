"""
Output filename generation for Field Ops screenshot capture.

Builds the converted PNG's path from a user-selected mask template
(SYSTEM/BODY/CMDR/DATE/NNNNN tokens) plus a per-directory sequence number.
"""

from __future__ import annotations

import glob
import os
import re
from datetime import datetime, timezone
from typing import Optional

#: Presets offered in the settings dropdown. "NNNNN" is a 5-digit sequence
#: number, unique per output directory; "DATE" is a UTC timestamp.
MASK_PRESETS = [
    "SYSTEM(BODY)_NNNNN.png",
    "SYSTEM(BODY)_DATE.png",
    "SYSTEM(CMDR)_NNNNN.png",
    "SYSTEM(CMDR)_DATE.png",
    "BODY(CMDR)_NNNNN.png",
    "BODY(CMDR)_DATE.png",
    "SYSTEM_(BODY)_CMDR_NNNNN.png",
    "SYSTEM_(BODY)_CMDR_DATE.png",
    "SYSTEM BODY (CMDR) NNNNN.png",
    "SYSTEM BODY (CMDR) DATE.png",
    "DATE_SYSTEM_BODY.png",
    "DATE_SYSTEM_CMDR.png",
    "DATE_SYSTEM_BODY_CMDR.png",
]

DEFAULT_MASK = MASK_PRESETS[0]

_SEQUENCE_TOKEN = "NNNNN"
_SEQUENCE_GLOB = "[0-9][0-9][0-9][0-9][0-9]"
_SEQUENCE_RE = re.compile(r"(\d{5})(?=\.[^.]+$)")

# Characters kept as-is in a generated filename; everything else not
# alphanumeric is stripped, since SYSTEM/BODY names can contain characters
# Windows and other filesystems reject.
_SAFE_CHARS = set(" ._+-(),#'[]")

_HIGH_RES_PREFIX = "HighRes_"


def journal_basename(journal_filename: str) -> str:
    """The file name part of a Screenshot event's `Filename`.

    Elite writes these Windows-style (`\\ED_Pictures\\Screenshot_0001.bmp`)
    even when it runs under Proton on Linux, where `os.path.basename` does
    not treat a backslash as a separator and would return the whole string.
    """
    return journal_filename.replace("\\", "/").rsplit("/", 1)[-1]


def is_high_res(source_filename: str) -> bool:
    """Elite Dangerous prefixes hi-res (Alt+F10) screenshots with 'HighRes'."""
    return journal_basename(source_filename).startswith("HighRes")


def build_output_path(
    mask: str,
    output_dir: str,
    *,
    system: Optional[str],
    body: Optional[str],
    cmdr: str,
    source_filename: str,
) -> str:
    """Render `mask` against the given fields and return a unique output path."""
    resolved = _substitute_tokens(mask, system=system, body=body, cmdr=cmdr)
    sanitized = _sanitize(resolved)

    if is_high_res(source_filename):
        sanitized = _HIGH_RES_PREFIX + sanitized

    if _SEQUENCE_TOKEN in mask:
        sanitized = _apply_next_sequence(sanitized, output_dir)

    return os.path.join(output_dir, sanitized)


def _substitute_tokens(mask: str, *, system: Optional[str], body: Optional[str], cmdr: str) -> str:
    resolved = mask
    body_label = _strip_system_prefix(body, system) if body else "Unknown"
    resolved = resolved.replace("SYSTEM", system or "Unknown")
    resolved = resolved.replace("BODY", body_label)
    resolved = resolved.replace("CMDR", cmdr or "Unknown")
    resolved = resolved.replace(
        "DATE", datetime.now(timezone.utc).strftime("%Y-%m-%d_%H-%M-%S"),
    )
    return resolved


def _strip_system_prefix(body: str, system: Optional[str]) -> str:
    """Elite's Body field is often "<System> <Body>" — drop the system part
    so a mask combining SYSTEM and BODY doesn't repeat it."""
    if system and body.startswith(system):
        stripped = body[len(system):].strip()
        return stripped or body
    return body


def _sanitize(name: str) -> str:
    return "".join(c for c in name if c.isalnum() or c in _SAFE_CHARS).strip()


def _apply_next_sequence(filename_with_token: str, output_dir: str) -> str:
    pattern = filename_with_token.replace(_SEQUENCE_TOKEN, _SEQUENCE_GLOB)
    existing = glob.glob(os.path.join(output_dir, pattern))

    highest = 0
    for path in existing:
        match = _SEQUENCE_RE.search(os.path.basename(path))
        if match:
            highest = max(highest, int(match.group(1)))

    sequence = format(highest + 1, "05d")
    return filename_with_token.replace(_SEQUENCE_TOKEN, sequence)
