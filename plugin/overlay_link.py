"""The "Get EDMCModernOverlay" link at the top of each overlay feature's Settings page.

Every overlay page used to carry it, which is noise on Windows once WNTB's built-in overlay is chosen (EDMCModernOverlay is then needed only
for other plugins' overlays). It now shows only while EDMCModernOverlay is the overlay in use: on Linux, or when it is chosen on Settings →
Overlays → Overlay Connection, which keeps the link always.
"""
from __future__ import annotations

import tkinter as tk

import myNotebook as nb
from ttkHyperlinkLabel import HyperlinkLabel

URL = "https://github.com/SweetJonnySauce/EDMCModernOverlay"
TEXT = "Get EDMCModernOverlay (needed on Linux, and for other plugins' overlays)"


def wanted() -> bool:
    """Whether the built-in overlay is not the one drawing (so the link is of use)."""
    from . import overlay_native
    return overlay_native.selected() != overlay_native.BUILTIN


def add(frame: tk.Misc, row: int = 1) -> bool:
    """Put the link on `frame` at `row` when it is wanted. Returns whether it was added."""
    if not wanted():
        return False
    HyperlinkLabel(frame, text=TEXT, background=nb.Label().cget("background"), url=URL, underline=True).grid(
        row=row, column=0, sticky=tk.W, padx=10, pady=(0, 8))
    return True
