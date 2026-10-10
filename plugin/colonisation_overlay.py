"""
The Colonization shopping list on the in-game overlay: a small card listing what is still to be sourced for one
construction site (the same figures as the Colonization Sites window's To Source column and its Copy Shopping List
button), biggest first, so a hauler can see it while flying.

Which site: the commander's most recently updated active site (the one the Field Ops summary line names). Each line is a
commodity and the tonnes still to find after what is in the hold; where the commander has moved some onto a fleet
carrier, that is shown too (`colonisation_carrier.py`), since it is stock they can pick up there.

The card is only shown while the commander is in a commodity market, or in the carrier's inventory (Carrier Management /
cargo transfer), at a station or carrier: that is `Visibility`. The journal says which service was opened (`Market`,
`CarrierStats`, `CargoTransfer`), and `Status.json`'s `GuiFocus` says whether a station-services screen is open at all
(it drops to another value when the commander leaves it, or undocks). Neither alone is enough: `GuiFocus` cannot tell the
commodity market from outfitting, and the journal does not say when a screen is closed.

Pure formatting (`card_lines`) is kept apart from the drawing (`render` / `clear`) so it can be tested without an overlay.
Drawing goes through the shared `overlay.OverlayClient`, like every other WNTB overlay; the card registers an
EDMCModernOverlay Plugin Group (`GROUP_NAME` / `GROUP_PREFIX`, wired up in load.py) so its background renders.
"""
from __future__ import annotations

from typing import List, Mapping, Optional, Tuple

from . import colonisation, overlay
from .colonisation import Site
from .screenshot_gui_focus import GUI_FOCUS_STATION_SERVICES

ID_PREFIX = "wntb_colonisation_"
GROUP_NAME = "wntb_colonisation"
GROUP_PREFIX = ID_PREFIX
CARD_ID = f"{ID_PREFIX}card"

# The overlay's legacy virtual screen is 1280 x 960.
MAX_ORIGIN_X = 1280
MAX_ORIGIN_Y = 960
DEFAULT_X = 20
DEFAULT_Y = 300
DEFAULT_ROWS = 10
MIN_ROWS = 1
MAX_ROWS = 25

LINE_HEIGHT = 20
PAD_X = 10
PAD_Y = 8
CHAR_WIDTH_PX = 8   # rough glyph width, used only to size the card to its longest line (erring wide is harmless)
TTL = 3600          # persistent; re-sent whenever the list changes, and before this runs out
RESEND_AFTER_S = TTL / 2

FILL = "#000000"
BORDER = "#f97316"
TITLE_COLOUR = "#fdba74"
TEXT_COLOUR = "#e5e7eb"
CARRIER_COLOUR = "#7dd3fc"

Line = Tuple[str, str]   # (text, colour)


MARKET_EVENT = "Market"                                       # opening the commodity market
CARRIER_EVENTS = ("CarrierStats", "CargoTransfer")            # opening Carrier Management, moving cargo to or from it
OTHER_SERVICE_EVENTS = ("Outfitting", "Shipyard", "StoreCargo")   # another station service screen opened
RESET_EVENTS = ("Docked", "Undocked", "LoadGame", "StartUp", "Shutdown")


class Visibility:
    """Is the commander in a commodity market or carrier inventory right now? Fed every journal event and every
    `Status.json` change. Shown only while a station-services screen is open (`GuiFocus`) and the service opened last
    was the market or the carrier's inventory. Backing out of the market to the station-services menu cannot be
    seen, so the card stays until that menu is left."""

    def __init__(self) -> None:
        self._service = ""
        self._focus = 0

    def feed(self, entry: Mapping[str, object]) -> None:
        event = entry.get("event")
        if event in RESET_EVENTS:
            self._service = ""
        elif event == MARKET_EVENT:
            self._service = "market"
        elif event in CARRIER_EVENTS:
            self._service = "carrier"
        elif event in OTHER_SERVICE_EVENTS:
            self._service = "other"

    def set_focus(self, focus: object) -> None:
        self._focus = focus if isinstance(focus, int) else 0
        if self._focus != GUI_FOCUS_STATION_SERVICES:
            self._service = ""   # the screen was closed; the next one opened announces itself

    @property
    def visible(self) -> bool:
        return self._focus == GUI_FOCUS_STATION_SERVICES and self._service in ("market", "carrier")


def _clip(text: str, limit: int) -> str:
    return text if len(text) <= limit else text[:limit - 1] + "…"


def card_lines(site: Optional[Site], hold: Mapping[str, int], on_carrier: Mapping[str, int],
               max_rows: int = DEFAULT_ROWS) -> List[Line]:
    """The card's text, title first. Empty when there is no site, or nothing is left to source (so no card is drawn).
    Shows at most `max_rows` commodities; the rest are summarized on a final line."""
    if site is None or not site.active:
        return []
    needed = colonisation.shopping_list(site, hold)
    if not needed:
        return []
    carrier_by_label = {}
    for resource in site.resources:
        if on_carrier.get(resource.key):
            carrier_by_label[resource.label] = on_carrier[resource.key]
    name = _clip(site.display_name(), 34)
    lines: List[Line] = [(f"To source: {name}", TITLE_COLOUR)]
    for label, amount in needed[:max_rows]:
        text = f"{amount:,} t  {_clip(label, 28)}"
        at_carrier = carrier_by_label.get(label)
        if at_carrier:
            text += f"  (FC {at_carrier:,})"
        lines.append((text, CARRIER_COLOUR if at_carrier else TEXT_COLOUR))
    if len(needed) > max_rows:
        lines.append((f"+{len(needed) - max_rows} more", TITLE_COLOUR))
    return lines


def render(client: overlay.OverlayClient, lines: List[Line], x: int, y: int, previous_rows: int = 0) -> int:
    """Draw the card; returns how many text rows were sent. Raises OSError if the overlay cannot be reached (the caller
    decides whether that is silent). Rows left over from a longer previous list are cleared."""
    if not lines:
        clear(client, x, y, previous_rows)
        return 0
    width = max(len(text) for text, _colour in lines) * CHAR_WIDTH_PX + 2 * PAD_X
    height = len(lines) * LINE_HEIGHT + 2 * PAD_Y
    client.send_shape(CARD_ID, "rect", BORDER, FILL, x - PAD_X, y - PAD_Y, width, height, ttl=TTL, thickness=2)
    for index, (text, colour) in enumerate(lines):
        client.send_message(f"{ID_PREFIX}row_{index}", text, colour, x, y + index * LINE_HEIGHT, ttl=TTL)
    for index in range(len(lines), previous_rows):
        client.send_message(f"{ID_PREFIX}row_{index}", "", "white", x, y + index * LINE_HEIGHT, ttl=1)
    return len(lines)


def clear(client: overlay.OverlayClient, x: int, y: int, rows: int) -> None:
    client.send_shape(CARD_ID, "rect", "", "", x, y, 0, 0, ttl=1)
    for index in range(rows):
        client.send_message(f"{ID_PREFIX}row_{index}", "", "white", x, y + index * LINE_HEIGHT, ttl=1)


def preview_lines() -> List[Line]:
    """Sample content for the Settings "Test Overlay" button."""
    return [("To source: Preview Construction Site", TITLE_COLOUR),
            ("12,900 t  Steel", TEXT_COLOUR), ("1,251 t  Liquid oxygen  (FC 1,265)", CARRIER_COLOUR),
            ("145 t  Computer Components", TEXT_COLOUR)]
