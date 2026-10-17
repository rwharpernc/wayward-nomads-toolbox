"""
Sharing one saved deposit as a single line of text, and taking one in.

A line looks like `WNTB-SPOT1:<code>:<check>`. The code is the deposit's system, body, material, rigs, signal number, position, Amount,
Density and kind of ground (and the body's radius when it is known, so the receiver can tell whether they already have that spot), as
compact JSON in URL-safe base64; the check is a CRC-32 of the code, so a line cut short or mangled in a chat is refused instead of
half-read. It never carries the commander's name, notes, folder, tons mined or any date: those are the sender's own.

Taking one in is checked as strictly as a hand-typed hotspot: every field is range- and length-checked, and a deposit within
`mining_hotspots.SAME_SPOT_M` of one already saved on the same body is refused (the receiver already has it).

Pure logic, no tkinter and no file access. See tests/test_mining_share.py.
"""
from __future__ import annotations

import base64
import json
import zlib
from dataclasses import dataclass
from typing import Optional, Sequence

from . import mining_bearing as bearing
from . import mining_deposit
from . import mining_hotspots as hotspots

PREFIX = "WNTB-SPOT1"
MAX_TEXT = 80
"""The longest system, body, material or ground text accepted."""
MAX_LINE = 600
"""The longest line accepted; a real one is a few hundred characters."""
ASSUMED_RADIUS_M = 1_000_000.0
"""Used to measure the distance between two spots when neither side knows the body's radius. A real body can be smaller or larger, so
this only decides "the same spot" for positions that are very close."""


class ShareError(ValueError):
    """The text is not a usable shared spot; the message says why, in words for the commander."""


@dataclass(frozen=True)
class Shared:
    hotspot: hotspots.Hotspot
    radius_m: Optional[float]


def can_share(spot: hotspots.Hotspot) -> bool:
    """A spot without a position is of no use to someone else."""
    return spot.has_position()


def encode(spot: hotspots.Hotspot, radius_m: Optional[float] = None) -> str:
    if not can_share(spot):
        raise ShareError("This hotspot has no position, so there is nothing to share.")
    data: dict = {"s": spot.system, "b": spot.body, "m": spot.material, "la": round(spot.latitude, 5), "lo": round(spot.longitude, 5)}
    for key, value in (("r", spot.rigs), ("n", spot.signal_number), ("a", spot.amount), ("d", spot.density), ("g", spot.ground)):
        if value not in (None, ""):
            data[key] = value
    if radius_m and radius_m > 0:
        data["R"] = round(radius_m)
    code = base64.urlsafe_b64encode(json.dumps(data, separators=(",", ":"), ensure_ascii=False).encode("utf-8")).decode("ascii").rstrip("=")
    return f"{PREFIX}:{code}:{zlib.crc32(code.encode('ascii')):08x}"


def _text(data: dict, key: str, label: str, required: bool = False) -> str:
    value = data.get(key)
    if value is None and not required:
        return ""
    if not isinstance(value, str) or not value.strip() or len(value) > MAX_TEXT or any(ord(c) < 32 for c in value):
        raise ShareError(f"The {label} in the line is missing or not usable.")
    return " ".join(value.split())


def _number(data: dict, key: str, label: str, low: float, high: float, whole: bool = False) -> Optional[float]:
    value = data.get(key)
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)) or (whole and not isinstance(value, int)) or not low <= value <= high:
        raise ShareError(f"The {label} in the line is out of range.")
    return value


def decode(text: str) -> Shared:
    """The deposit in a shared line, or ShareError. Surrounding whitespace and quotes (chat apps add them) are ignored."""
    line = (text or "").strip().strip("`\"'<>").strip()
    if not line:
        raise ShareError("There is nothing on the clipboard.")
    if len(line) > MAX_LINE:
        raise ShareError("That is too long to be a shared spot.")
    parts = line.split(":")
    if parts[0] != PREFIX:
        raise ShareError("That is not a shared WNTB spot.")
    if len(parts) != 3:
        raise ShareError("The line is damaged or cut short: copy it again.")
    code, check = parts[1], parts[2]
    try:
        code.encode("ascii")
    except UnicodeEncodeError:
        raise ShareError("The line is damaged (it has odd characters).") from None
    if f"{zlib.crc32(code.encode('ascii')):08x}" != check.lower():
        raise ShareError("The line is damaged or cut short: copy it again.")
    try:
        data = json.loads(base64.urlsafe_b64decode(code + "=" * (-len(code) % 4)).decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        raise ShareError("The line is damaged: copy it again.") from None
    if not isinstance(data, dict):
        raise ShareError("The line is damaged: copy it again.")

    latitude = _number(data, "la", "latitude", -90.0, 90.0)
    longitude = _number(data, "lo", "longitude", -180.0, 180.0)
    if latitude is None or longitude is None:
        raise ShareError("The line has no position.")
    amount, density = data.get("a"), data.get("d")
    if amount is not None and amount not in mining_deposit.AMOUNTS:
        raise ShareError("The Amount in the line is not one the game shows.")
    if density is not None and density not in mining_deposit.DENSITIES:
        raise ShareError("The Density in the line is not one the game shows.")
    rigs = _number(data, "r", "rig count", 1, mining_deposit.MAX_RIGS, whole=True)
    signal = _number(data, "n", "location number", 0, 999, whole=True)
    radius = _number(data, "R", "body radius", 1_000.0, 1_000_000_000.0)
    spot = hotspots.Hotspot(
        system=_text(data, "s", "system", True), body=_text(data, "b", "body", True), material=_text(data, "m", "material", True),
        latitude=float(latitude), longitude=float(longitude), rigs=int(rigs) if rigs is not None else None,
        signal_number=int(signal) if signal is not None else None, amount=amount, density=density, ground=_text(data, "g", "ground") or None)
    return Shared(spot, float(radius) if radius is not None else None)


def find_duplicate(incoming: Shared, saved: Sequence[hotspots.Hotspot], known_radius_m: Optional[float] = None) -> Optional[hotspots.Hotspot]:
    """A saved hotspot on the same body within `SAME_SPOT_M` of the incoming one, if any. The body's radius is the receiver's own if known,
    else the sender's, else an assumed one."""
    radius = known_radius_m or incoming.radius_m or ASSUMED_RADIUS_M
    new = incoming.hotspot
    for existing in saved:
        if not (existing.has_position() and existing.matches_body(new.system, new.body)):
            continue
        if bearing.distance_m(existing.latitude, existing.longitude, new.latitude, new.longitude, radius) <= hotspots.SAME_SPOT_M:
            return existing
    return None
