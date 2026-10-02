"""Colour and font tokens for WNTB's own window look (spec section 5, option
A: a fixed look independent of EDMC's theme). Every colour used by plugin/uikit
comes from here, so a light variant later is a one-dict change.

Status colours are never the only carrier of meaning: pills always carry a
text label and map markers differ in shape, so the set stays usable without
telling red from green."""
from __future__ import annotations

# Surfaces, darkest to lightest.
BG = "#14171c"        # window background
PANE = "#1a1e25"      # pane background
CARD = "#222831"      # raised card
BUTTON = "#303846"     # buttons (visible on both PANE and CARD)
HOVER = "#2a313c"     # row hover
SELECT = "#33415a"    # selected row
LINE = "#2e3540"      # hairlines

# Text.
TEXT = "#e6e9ee"
MUTED = "#8b94a3"
FAINT = "#5d6675"

# Accents / status.
ACCENT = "#f0a23b"    # amber - primary actions, current selection marker
INFO = "#4aa8ff"      # blue - "you are here"
OK = "#5fbf8f"
WARN = "#e0b341"
DANGER = "#e06c6c"

# Map.
MAP_BG = "#101318"
MAP_GRID = "#2b2a1c"          # dim yellow: visible over driven ground
MAP_COVERAGE = "#2e5c3a"
MAP_HOTSPOT = "#eee8be"       # pale filled dot
MAP_DEPLETED = "#969696"      # hollow ring

PAD = 10
PAD_SM = 5

# (size delta from the system default font, weight)
FONT_BODY = (0, "normal")
FONT_SMALL = (-1, "normal")
FONT_BOLD = (0, "bold")
FONT_TITLE = (4, "bold")
FONT_SECTION = (1, "bold")
FONT_STAT = (8, "bold")
