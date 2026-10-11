"""
The Colonization shopping list on the in-game overlay, laid out like SRVSurvey's: a table of the commodities a
construction site still needs, with the columns Commodity, Need, FC and Ship.

- **Need** is what the site still requires (required less delivered). It does not fall as you load up, so you can see
  how much you need and how much you have side by side.
- **FC** (only for a commander with a fleet carrier) is what has been transferred to the carrier (`colonisation_carrier`).
- **Ship** is what is in the ship's hold now. A ✓ marks a commodity the hold plus the fleet carrier already cover (the
  same rule as the Colonization window's green rows); the row turns amber when together they are more than is needed.

A footer gives the tons remaining and the trips that is in the current ship (from its cargo capacity). Commodities are
alphabetical, so rows stay put as the numbers change.

Which site: the commander's most recently updated active site (the one the Colonization page names as the current project).

The card is shown while the commander is in a commodity market, or in the carrier's inventory (Carrier Management /
cargo transfer), at a station or carrier, or docked at a construction site: that is `Visibility`. The journal says which
service was opened (`Market`, `CarrierStats`, `CargoTransfer`), and `Status.json`'s `GuiFocus` says whether a
station-services screen is open at all (it drops to another value when the commander leaves it, or undocks). Neither
alone is enough: `GuiFocus` cannot tell the commodity market from outfitting, and the journal does not say when a screen
is closed.

Pure layout (`build_card`) is kept apart from the drawing (`render` / `clear`) so it can be tested without an overlay.
Drawing goes through the shared `overlay.OverlayClient`, like every other WNTB overlay; the card registers an
EDMCModernOverlay Plugin Group (`GROUP_NAME` / `GROUP_PREFIX`, wired up in load.py) so its background renders.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import List, Mapping, Optional, Tuple

from . import colonisation, overlay
from .overlay_style import LEGACY, Look
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
DEFAULT_ROWS = 0   # 0 = every commodity
MIN_ROWS = 0
MAX_ROWS = 60

# The card's own geometry at the default look. A `Look` (overlay_style.py) changes the text size, padding, line spacing and colors,
# and the card is sized from the text it will show, so a bigger size makes a bigger card and nothing runs past the border.
LINE_HEIGHT = 20
PAD_X = 10
PAD_Y = 8
CHAR_WIDTH_PX = 8   # rough glyph width, used only to size the card to its longest line (erring wide is harmless)
TTL = 3600          # persistent; re-sent whenever the list changes, and before this runs out
RESEND_AFTER_S = TTL / 2

MARKET_EVENT = "Market"                                       # opening the commodity market
CARRIER_EVENTS = ("CarrierStats", "CargoTransfer")            # opening Carrier Management, moving cargo to or from it
OTHER_SERVICE_EVENTS = ("Outfitting", "Shipyard", "StoreCargo")   # another station service screen opened
RESET_EVENTS = ("Docked", "Undocked", "LoadGame", "StartUp", "Shutdown")
GUI_FOCUS_NONE = 0
GUI_FOCUS_RIGHT_PANEL = 1   # "InternalPanel": the right-hand cockpit panel (cargo, modules, transfer to a carrier)
# Station types of a construction depot (the colonisation ship is one too); a depot's own market-free screens count.
DEPOT_STATION_TYPES = ("SpaceConstructionDepot", "PlanetaryConstructionDepot", "ColonisationShip")
CARRIER_MANAGEMENT_TRACK = "FleetCarrier_Managment"   # sic: the game's spelling
CARRIER_STATION_TYPES = ("FleetCarrier", "SquadronCarrier")


class Visibility:
    """Should the card show right now? Fed every journal event and every `Status.json` change. Two cases:

    - in a commodity market: a station-services screen is open (`GuiFocus`) and the service opened last was the market.
      Backing out of the market to the station-services menu cannot be seen, so the card stays until that menu is left.
      At the commander's own carrier the game writes no `Market` event when its market is opened, so there any
      station-services screen counts unless Outfitting or the Shipyard was the last one opened (they do write events);
    - docked at a carrier with the right-hand cockpit panel open (`GuiFocus` 1), where the ship's cargo and the transfer to
      the carrier live. The game writes nothing when that is opened (`CargoTransfer` comes only after a transfer is made),
      so the open panel is the signal. SRVSurvey does the same with its "Show when looking at right-hand panel" setting,
      though it shows it anywhere, not only docked at a carrier;
    - docked at a construction depot (where the shopping list is what the commander is there for), whether looking at
      the ship's view or the station services, but not in a map or another panel;
    - in the carrier's management screen: the game writes a `Music` event with the track `FleetCarrier_Managment` when it
      opens and another track when it closes, so (unlike the other screens) both ends are known;
    - with the right-hand panel open anywhere, if `right_panel_anywhere` is set (SRVSurvey's default behavior).

    `forced` is the commander's manual "show now", which `visible` does not include (the caller decides how it combines
    with the enabled setting)."""

    def __init__(self) -> None:
        self._service = ""
        self._focus = 0
        self._at_depot = False
        self._at_carrier = False
        self._managing = False
        self.right_panel_anywhere = False
        self.forced = False

    def feed(self, entry: Mapping[str, object]) -> None:
        event = entry.get("event")
        if event in RESET_EVENTS:
            self._service = ""
            self._at_depot = False
            self._at_carrier = False
            self._managing = False
        if event == "Music":
            self._managing = entry.get("MusicTrack") == CARRIER_MANAGEMENT_TRACK
        if event in ("Docked", "Location"):
            docked = event == "Docked" or bool(entry.get("Docked"))
            self._at_carrier = docked and entry.get("StationType") in CARRIER_STATION_TYPES
            self._at_depot = docked and (entry.get("StationType") in DEPOT_STATION_TYPES
                                         or "Construction Site" in str(entry.get("StationName") or ""))
        elif event == colonisation.EVENT_DEPOT:
            self._at_depot = True   # the game writes this when docked at a depot, whatever its station type says
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

    def describe(self) -> str:
        """The state behind `visible`, for the debug log."""
        return (f"focus={self._focus} service={self._service or '-'} depot={self._at_depot} carrier={self._at_carrier} "
                f"mgmt={self._managing} anywhere={self.right_panel_anywhere} forced={self.forced}")

    @property
    def visible(self) -> bool:
        if self._focus == GUI_FOCUS_STATION_SERVICES and (
                self._service in ("market", "carrier") or (self._at_carrier and self._service != "other")):
            return True
        if self._managing:
            return True
        if self._focus == GUI_FOCUS_RIGHT_PANEL and (self._at_carrier or self.right_panel_anywhere):
            return True
        return self._at_depot and self._focus in (GUI_FOCUS_NONE, GUI_FOCUS_STATION_SERVICES)


def _clip(text: str, limit: int) -> str:
    return text if len(text) <= limit else text[:limit - 1] + "…"


# Colors come from the look's roles: border and fill (the card), title, header (column headings), text, ok (the ship plus the fleet
# carrier already cover what is needed), warn (they are more than is needed), info (the carrier column once it covers the need) and
# muted (the carrier column while it does not).
CHECK = "✓"
NAME_CHARS = 30


@dataclass(frozen=True)
class Row:
    name: str
    need: int
    ship: int
    fc: int

    @property
    def covered(self) -> bool:
        """The hold plus the fleet carrier cover the need, exactly or with room to spare."""
        return self.ship + self.fc >= self.need

    @property
    def surplus(self) -> bool:
        """The hold plus the fleet carrier are more than the need."""
        return self.ship + self.fc > self.need


@dataclass(frozen=True)
class Card:
    title: str
    rows: Tuple[Row, ...]
    hidden: int          # commodities beyond the row limit
    remaining: int       # tons still needed in total
    trips: int           # trips that is in the current ship (0 when its capacity is unknown)
    show_fc: bool

    @property
    def slot_count(self) -> int:
        """Text lines drawn: title, column headings, one per row, an optional "+N more", the footer."""
        return 2 + len(self.rows) + (1 if self.hidden else 0) + 1


def build_card(site: Optional[Site], hold: Mapping[str, int], on_carrier: Mapping[str, int], show_fc: bool,
               capacity: int = 0, max_rows: int = DEFAULT_ROWS) -> Optional[Card]:
    """The card for `site`, or None when there is nothing to draw (no site, a finished site, nothing still needed)."""
    if site is None or not site.active:
        return None
    needed = sorted((r for r in site.resources if r.remaining > 0), key=lambda r: r.label.casefold())
    if not needed:
        return None
    limit = max_rows if max_rows > 0 else len(needed)
    rows = tuple(Row(r.label, r.remaining, hold.get(r.key, 0), on_carrier.get(r.key, 0)) for r in needed[:limit])
    remaining = sum(r.remaining for r in needed)
    trips = math.ceil(remaining / capacity) if capacity and capacity > 0 else 0
    return Card(_clip(site.display_name(), 40), rows, max(0, len(needed) - limit), remaining, trips, show_fc)


def _layout(card: Card, look: Look = LEGACY) -> Tuple[int, List[int], int]:
    """(x of the name column relative to the card, right edges of the Need / FC / Ship columns, total text width) in px,
    from character counts at the look's text size - the wire protocol has no text metrics, so this errs a little wide."""
    char = look.char_px("normal")
    name_chars = max([len("Commodity")] + [len(_clip(r.name, NAME_CHARS)) + 2 for r in card.rows])
    columns = [("Need", [r.need for r in card.rows])]
    if card.show_fc:
        columns.append(("FC", [r.fc for r in card.rows]))
    columns.append(("Ship", [r.ship for r in card.rows]))
    widths = [max([len(head)] + [len(f"{v:,}") for v in values]) + 2 for head, values in columns]
    edges, edge = [], name_chars
    for width in widths:
        edge += width
        edges.append(edge * char)
    footer = len(f"► {card.remaining:,} remaining") + (len(f"  ► {card.trips:,} trips in this ship") if card.trips else 0)
    chars = max(name_chars + sum(widths), footer, len(card.title), 12)
    return 0, edges, int(round(chars * char))


def block_rect(card: Card, x: int = 0, y: int = 0, look: Look = LEGACY) -> Tuple[int, int, int, int]:
    """(left, top, width, height) of the card as `render` draws it with its text origin at (x, y): the panel rectangle.
    The global overlay placement uses this to move the card to wherever the commander put it."""
    _x0, _edges, text_width = _layout(card, look)
    pad_x, pad_y = look.pad_x(PAD_X), look.pad_y(PAD_Y)
    return x - pad_x, y - pad_y, text_width + 2 * pad_x, card.slot_count * look.line_px("normal") + 2 * pad_y


def _id(slot: int, column: int) -> str:
    return f"{ID_PREFIX}s{slot}_{column}"


def render(client: overlay.OverlayClient, card: Card, x: int, y: int, previous_slots: int = 0, look: Look = LEGACY) -> int:
    """Draw the card; returns how many text lines it used. Raises OSError if the overlay cannot be reached (the caller
    decides whether that is silent). Lines left over from a longer previous card are cleared."""
    _x0, edges, text_width = _layout(card, look)
    left, top, width, height = block_rect(card, x, y, look)
    line = look.line_px("normal")
    size = look.size("normal")
    char = look.char_px("normal")
    client.send_shape(CARD_ID, "rect", look.color("border"), look.color("fill"), left, top, width, height, ttl=TTL, thickness=2)

    slots: List[List[Tuple[int, str, str, int]]] = []   # per line: (column, text, colour, x)

    def right(text: str, edge: int) -> int:
        return int(round(x + edge - len(text) * char))

    slots.append([(0, card.title, look.color("title"), x)])
    heads = [("Need", edges[0])] + ([("FC", edges[1])] if card.show_fc else []) + [("Ship", edges[-1])]
    header = look.color("header")
    slots.append([(0, "Commodity", header, x)] + [(i + 1, h, header, right(h, e)) for i, (h, e) in enumerate(heads)])
    for row in card.rows:
        colour = look.color("warn") if row.surplus else look.color("ok") if row.covered else look.color("text")
        name = _clip(row.name, NAME_CHARS) + (f" {CHECK}" if row.covered else "")
        cells = [(0, name, colour, x), (1, f"{row.need:,}", colour, right(f"{row.need:,}", edges[0]))]
        column = 2
        if card.show_fc:
            fc = f"{row.fc:,}" if row.fc else ""
            if fc:
                cells.append((column, fc, look.color("info") if row.fc >= row.need else look.color("muted"), right(fc, edges[1])))
            column += 1
        if row.ship:
            ship = f"{row.ship:,}"
            cells.append((column, ship, colour, right(ship, edges[-1])))
        slots.append(cells)
    if card.hidden:
        slots.append([(0, f"+{card.hidden} more", look.color("title"), x)])
    footer = f"► {card.remaining:,} remaining"
    if card.trips:
        footer += f"  ► {card.trips:,} trip{'s' if card.trips != 1 else ''} in this ship"
    slots.append([(0, footer, look.color("text"), x)])

    for index, cells in enumerate(slots):
        used = {column for column, _t, _c, _x in cells}
        for column, text, colour, cell_x in cells:
            client.send_message(_id(index, column), text, colour, cell_x, y + index * line, ttl=TTL, size=size)
        for column in range(4):
            if column not in used and (index < previous_slots):
                client.send_message(_id(index, column), "", "white", x, y + index * line, ttl=1)
    for index in range(len(slots), previous_slots):
        for column in range(4):
            client.send_message(_id(index, column), "", "white", x, y + index * line, ttl=1)
    return len(slots)


def clear(client: overlay.OverlayClient, x: int, y: int, slots: int) -> None:
    client.send_shape(CARD_ID, "rect", "", "", x, y, 0, 0, ttl=1)
    for index in range(slots):
        for column in range(4):
            client.send_message(_id(index, column), "", "white", x, y + index * LINE_HEIGHT, ttl=1)


def preview_card() -> Card:
    """Sample content for the Settings "Test Overlay" button."""
    return Card("Preview Construction Site",
                (Row("Aluminium", 10055, 0, 0), Row("Steel", 12900, 14000, 1265), Row("Titanium", 8205, 300, 9000),
                 Row("Water", 1609, 1609, 0)),
                hidden=0, remaining=32769, trips=33, show_fc=True)
