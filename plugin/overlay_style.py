"""How WNTB's overlay displays look: one set of choices that every overlay in the plugin follows. Pure logic (no Tk, no EDMC).

Four choices, all on the Overlays -> Appearance Settings tab:

- **Color scheme**: a named palette. Every display takes its colors from roles (title, text, covered, warning ...) so changing
  the scheme recolors them all together.
- **Text size**: steps each display's text up or down through the overlay's four sizes (small, normal, large, huge). The
  overlay offers only those four, so the steps are about a third of a size apart; a display already at the largest size stays
  there.
- **Padding**: extra space between a card's border and its text.
- **Line spacing**: extra space between lines.

**Why text size changes the cards too.** The overlay cannot measure text, so every card is sized from the text it will show:
width from the number of characters times an estimated character width for the size being drawn, height from the number of
lines times the line height for that size. `Look` supplies those estimates (`text_width`, `line`, `pad_x`, `pad_y`), so a larger
size makes a larger card and the text still fits inside the border instead of running past it or wrapping.

A `Look` with no extras (`LEGACY`) reproduces the geometry and Elite-orange colors the displays had before this existed, which is
what the pure drawing functions use when no look is passed, so they stay testable on their own.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional, Tuple

SIZES = ("small", "normal", "large", "huge")

# Estimated width of one character, and the height of one line, at each size, in the pixels the overlay draws in (it offers no
# text measurement; these were tuned on EDMCModernOverlay and err a little wide, since a card slightly too wide looks fine and
# text running past a card that is too narrow does not). The larger sizes are widened further: EDMCModernOverlay steps its font
# by a fixed number of points, and that step does not shrink with the window, so large and huge text outgrow a proportional
# estimate first and ran past the right edge of their cards.
CHAR_PX: Dict[str, float] = {"small": 6.0, "normal": 8.0, "large": 12.5, "huge": 16.5}
LINE_PX: Dict[str, int] = {"small": 16, "normal": 20, "large": 26, "huge": 34}

# Text widths are estimates, so every one is padded by this much on top: the overlay's own font sizing depends on the window and on
# its font limits, which differ from one screen to the next, and a box a little too wide looks fine where text past its edge does not.
WIDTH_PAD = 1.10

# The sizes the Appearance tab offers. A fourth step ("Largest") was dropped: it is where text used to run past its box.
TEXT_CHOICES: Tuple[Tuple[str, int], ...] = (("Smaller", -1), ("Default", 0), ("Larger", 1))
PADDING_CHOICES: Tuple[Tuple[str, int], ...] = (("Compact", 0), ("Comfortable", 6), ("Roomy", 14))
SPACING_CHOICES: Tuple[Tuple[str, int], ...] = (("Tight", 0), ("Normal", 3), ("Loose", 7))

DEFAULT_SCHEME = "Elite orange"
DEFAULT_TEXT_LEVEL = 0
DEFAULT_PADDING = 6        # a little roomier than before, so a border has some separation from its text
DEFAULT_SPACING = 3


WIDE_CHARS = "MWmw@%&"           # glyphs wider than the average the character estimates are tuned on
WIDE_FACTOR = 1.3
CAPITAL_FACTOR = 1.2             # capitals and digits run wider than lower-case letters, so a title in capitals or a body name full of them outgrew its card


def _em(text: str) -> float:
    """`text` as a count of average-width characters: a capital, digit or wide glyph counts for more than one, a space or narrow mark for less,
    so a card sized from it holds capitals ("NEW SYSTEM DISCOVERY"), catalog names ("HIP 12345 AB 1 a") and the like without clipping."""
    total = 0.0
    for ch in text:
        if ch in WIDE_CHARS:
            total += WIDE_FACTOR
        elif ch.isupper() or ch.isdigit():
            total += CAPITAL_FACTOR
        elif ch in " .,'|:;!ilIjt-":
            total += 0.6
        else:
            total += 1.0
    return total


@dataclass(frozen=True)
class Palette:
    """The colors of one scheme, by role. Colors are '#rrggbb', or '#aarrggbb' where the overlay takes an alpha."""
    name: str
    border: str          # a card's border
    fill: str            # a card's background
    title: str           # a card's heading
    header: str          # column headings and secondary labels
    text: str            # ordinary text
    muted: str           # de-emphasized text
    ok: str              # good: covered, approved
    warn: str            # attention: more than needed, a caution
    info: str            # a second kind of information (the fleet carrier column)
    danger: str          # bad: denied, a warning
    accents: Tuple[str, str, str]      # three distinct highlights (system discovery, body discovery, notable body)
    series: Tuple[str, str, str, str]  # four distinct bar colors (inventory bars)


def darken(color: str, factor: float) -> str:
    """'#rrggbb' (or '#aarrggbb', alpha kept) with each channel scaled by `factor` (0 to 1)."""
    if len(color) not in (7, 9) or not color.startswith("#"):
        return color
    head, rgb = color[:-6], color[-6:]
    scaled = "".join(f"{int(int(rgb[i:i + 2], 16) * max(0.0, min(1.0, factor))):02x}" for i in (0, 2, 4))
    return head + scaled


def with_alpha(color: str, alpha: int) -> str:
    """'#rrggbb' as '#aarrggbb' with the given alpha (0 to 255); a color that already has one is returned unchanged."""
    if len(color) == 7 and color.startswith("#"):
        return f"#{max(0, min(255, alpha)):02x}{color[1:]}"
    return color


ELITE_ORANGE = Palette(
    "Elite orange", "#f97316", "#e6000000", "#fdba74", "#c2790e", "#e5e7eb", "#9ca3af", "#86efac", "#fbbf24", "#7dd3fc",
    "#f87171", ("#fbbf24", "#67e8f9", "#c4b5fd"), ("#4fc3f7", "#81c784", "#ba68c8", "#ff8c0d"))
ICE_BLUE = Palette(
    "Ice blue", "#38bdf8", "#e6000000", "#bae6fd", "#0ea5e9", "#f0f9ff", "#94a3b8", "#86efac", "#fde047", "#a5b4fc",
    "#fca5a5", ("#7dd3fc", "#5eead4", "#c4b5fd"), ("#38bdf8", "#34d399", "#a78bfa", "#fbbf24"))
PHOSPHOR_GREEN = Palette(
    "Phosphor green", "#22c55e", "#e6000000", "#86efac", "#16a34a", "#dcfce7", "#86a38f", "#bef264", "#fde047", "#67e8f9",
    "#fca5a5", ("#4ade80", "#a3e635", "#5eead4"), ("#4ade80", "#a3e635", "#2dd4bf", "#facc15"))
AMBER_MONO = Palette(
    "Amber mono", "#f59e0b", "#e6000000", "#fcd34d", "#b45309", "#fef3c7", "#a8a29e", "#d9f99d", "#fb923c", "#fde68a",
    "#fca5a5", ("#fcd34d", "#fbbf24", "#fdba74"), ("#fcd34d", "#fbbf24", "#f59e0b", "#d97706"))
HIGH_CONTRAST = Palette(
    "High contrast", "#ffffff", "#f2000000", "#ffff00", "#ffffff", "#ffffff", "#d4d4d8", "#00ff7f", "#ffb000", "#00e5ff",
    "#ff5555", ("#ffff00", "#00e5ff", "#ff80ff"), ("#00e5ff", "#00ff7f", "#ff80ff", "#ffb000"))
COLOR_BLIND_SAFE = Palette(      # the Okabe-Ito set, which stays distinct for the common kinds of color blindness
    "Color-blind safe", "#56b4e9", "#e6000000", "#f0e442", "#e69f00", "#ffffff", "#bdbdbd", "#56b4e9", "#e69f00", "#cc79a7",
    "#d55e00", ("#f0e442", "#56b4e9", "#cc79a7"), ("#56b4e9", "#009e73", "#cc79a7", "#e69f00"))

SCHEMES: Dict[str, Palette] = {p.name: p for p in (
    ELITE_ORANGE, ICE_BLUE, PHOSPHOR_GREEN, AMBER_MONO, HIGH_CONTRAST, COLOR_BLIND_SAFE)}

ROLES = ("border", "fill", "title", "header", "text", "muted", "faint", "ok", "warn", "info", "danger")
FAINT_FACTOR = 0.5   # "faint" is the scheme's muted color at this fraction of its brightness: clearly lesser than muted


def scheme_named(name: Optional[str]) -> Palette:
    """The palette called `name`, or the default one for anything unknown."""
    return SCHEMES.get(name or "", SCHEMES[DEFAULT_SCHEME])


@dataclass(frozen=True)
class Look:
    """What every display needs to draw itself: colors, and the size estimates that make a card fit its text."""
    palette: Palette = ELITE_ORANGE
    text_level: int = 0       # steps up (+) or down (-) the four text sizes
    pad_extra: int = 0        # pixels added to each side of a card's own padding
    line_extra: int = 0       # pixels added between lines

    # --- colors ------------------------------------------------------------------------------------------------
    def color(self, role: str) -> str:
        """The color for a role ('title', 'text', 'ok', 'border' ...)."""
        if role not in ROLES:
            raise ValueError(f"unknown color role: {role!r}")
        if role == "faint":
            return darken(self.palette.muted, FAINT_FACTOR)
        return getattr(self.palette, role)

    def accent(self, index: int) -> str:
        return self.palette.accents[index % len(self.palette.accents)]

    def series(self, index: int) -> str:
        return self.palette.series[index % len(self.palette.series)]

    def soft(self, color: str) -> str:
        """`color` at half opacity, for a card border that should not shout."""
        return with_alpha(color, 0x80)

    # --- text and card geometry ---------------------------------------------------------------------------------
    def size(self, base: str = "normal") -> str:
        """The overlay text size to ask for where a display would normally use `base`, stepped by the chosen text size. Stops
        at the smallest and largest sizes the overlay has."""
        index = SIZES.index(base) if base in SIZES else SIZES.index("normal")
        return SIZES[max(0, min(len(SIZES) - 1, index + self.text_level))]

    def char_px(self, base: str = "normal") -> float:
        """Estimated width of one character drawn where a display would normally use size `base`."""
        return CHAR_PX[self.size(base)]

    def line_px(self, base: str = "normal") -> int:
        """Height of one line at that size, plus the chosen line spacing."""
        return LINE_PX[self.size(base)] + self.line_extra

    def text_width(self, text: str, base: str = "normal") -> int:
        """Estimated width in pixels of `text` at that size, padded by WIDTH_PAD so a box sized from it holds the text."""
        return int(round(len(text) * self.char_px(base) * WIDTH_PAD))

    def measured_width(self, text: str, base: str = "normal") -> int:
        """Like `text_width` but counting capitals, digits and wide glyphs as wider and spaces and narrow marks as narrower, for a card that must
        hold text of any mix (a title in capitals, a body name such as "HIP 12345 AB 1 a") without clipping. Never less than `text_width`."""
        return max(self.text_width(text, base), int(round(_em(text) * self.char_px(base) * WIDTH_PAD)))

    def pad_x(self, base_pad: int) -> int:
        """A card's side padding: its own base padding plus the chosen extra."""
        return base_pad + self.pad_extra

    def pad_y(self, base_pad: int) -> int:
        return base_pad + self.pad_extra

    def scale(self, base: str = "normal") -> float:
        """How much bigger a line is at the chosen text size than at `base`: for scaling a fixed gap or offset along with the text."""
        return LINE_PX[self.size(base)] / LINE_PX[base if base in SIZES else "normal"]


# The geometry and colors the displays had before appearance settings existed: what a pure drawing function uses when it is given
# no look, so it behaves (and tests) exactly as it always did.
LEGACY = Look(ELITE_ORANGE, 0, 0, 0)

# The look a person gets until they choose another: a little more padding and line spacing than LEGACY.
DEFAULT = Look(ELITE_ORANGE, DEFAULT_TEXT_LEVEL, DEFAULT_PADDING, DEFAULT_SPACING)


def look_from_choices(scheme: Optional[str], text_level: int, pad_extra: int, line_extra: int) -> Look:
    """A `Look` from stored choices, clamping anything out of range so damaged settings never break drawing."""
    levels = [value for _label, value in TEXT_CHOICES]
    return Look(
        scheme_named(scheme),
        max(min(levels), min(max(levels), int(text_level))),
        max(0, min(40, int(pad_extra))),
        max(0, min(20, int(line_extra))),
    )


def label_for(choices: Tuple[Tuple[str, int], ...], value: int) -> str:
    """The menu label for a stored value (the nearest choice when it is not exactly one of them)."""
    return min(choices, key=lambda choice: abs(choice[1] - value))[0]


def value_for(choices: Tuple[Tuple[str, int], ...], label: str, default: int) -> int:
    for name, value in choices:
        if name == label:
            return value
    return default
