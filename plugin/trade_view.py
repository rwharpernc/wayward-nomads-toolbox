"""
Draws Trade mode's page (`trade_blocks`) with real layout: section headings with a rule above, label/value
rows with the value pinned right, and tables whose number columns line up.

Sizing: EDMC sizes its main window to the widest row of every plugin and WNTB's mode holder is pinned to the
mode-button row's width (docs/TECHNICAL.md section 5), so anything wider is clipped, not shown. Nothing here can
widen it: every label has an explicit `wraplength` worked out from the width actually available, and the table's
title column gets what the number columns leave over. The number columns are measured with the real font, so
this holds at any screen scaling. When the available width changes the page is drawn again.

EDMC's theme only auto-colours a widget that had no colour of its own when first registered, and leaves a Frame's
background alone (see missions_ui.py's notes), so colours and fonts are set here at creation, and the container
takes its parent's background.
"""
from __future__ import annotations

import tkinter as tk
from typing import Dict, List, Optional, Sequence

from . import panelkit
from .trade_blocks import Block, Columns, Heading, Item, Note, Pair

ACCENT = "#ff8c0d"           # Elite orange: section headings and things to watch
_MIN_WIDTH = 260             # never lay out narrower than this
_FALLBACK_WIDTH = 300        # before the first real width is known
_NUMERIC_COLUMNS = 3         # columns 1..3 hold table numbers; column 0 is the title
_GAP = 12                    # pixels between columns
_PAD = 4                     # a label's own internal padding, on top of its text
_INDENT = 14                 # pixels per indent level
# A label and its value share one row: their wrap widths plus the gap between them must stay under the width.
_LABEL_SHARE = 0.36
_VALUE_SHARE = 0.56


class BlockView(tk.Frame):
    """A frame that shows a list of blocks and redraws only when they (or its width) change."""

    def __init__(self, parent: tk.Misc) -> None:
        options = {}
        try:
            options["background"] = parent.cget("background")
        except tk.TclError:
            pass
        super().__init__(parent, **options)
        self._blocks: Optional[List[Block]] = None
        self._width = 0
        self._pending: Optional[str] = None
        self.columnconfigure(0, weight=1)
        self.bind("<Configure>", self._on_configure)

    # --- public --------------------------------------------------------------------------

    def show(self, blocks: Sequence[Block]) -> None:
        blocks = list(blocks)
        if blocks == self._blocks:
            return
        self._blocks = blocks
        self._draw()

    # --- redraw on width change -----------------------------------------------------------

    def _on_configure(self, event: tk.Event) -> None:
        if self._blocks is not None and abs(event.width - self._width) > 4 and self._pending is None:
            self._pending = self.after_idle(self._redraw_for_width)

    def _redraw_for_width(self) -> None:
        self._pending = None
        if self._blocks is not None and self.winfo_exists():
            self._draw()

    # --- drawing ---------------------------------------------------------------------------

    def _draw(self) -> None:
        for child in self.winfo_children():
            child.destroy()
        fonts = panelkit.view_fonts()
        reported = self.winfo_width()
        self._width = reported
        total = max(_MIN_WIDTH, reported if reported > 1 else _FALLBACK_WIDTH)

        # Number columns: as wide as their widest cell or heading, measured with the real font.
        widths = [0] * _NUMERIC_COLUMNS
        for block in self._blocks or []:
            cells = block.cells if isinstance(block, Item) else block.labels if isinstance(block, Columns) else ()
            for position, text in enumerate(cells[-_NUMERIC_COLUMNS:]):
                column = _NUMERIC_COLUMNS - len(cells[-_NUMERIC_COLUMNS:]) + position
                font = fonts["small_bold"] if isinstance(block, Columns) else fonts["normal"]
                widths[column] = max(widths[column], font.measure(text) + _PAD)
        for column, width in enumerate(widths, start=1):
            self.columnconfigure(column, weight=0, minsize=width + (_GAP if width else 0))
        # A label/value row puts its value in the same columns as the table's numbers, so those columns must be
        # wide enough for the wider of the two, and the title column gets what is left.
        value_need = 0
        for block in self._blocks or []:
            if isinstance(block, Pair):
                font = fonts["bold"] if block.bold else fonts["normal"]
                value_need = max(value_need, min(font.measure(block.value) + _PAD, int(total * _VALUE_SHARE)) + _GAP)
        numeric_need = max(sum(w + _GAP for w in widths if w), value_need)
        title_wrap = max(110, total - numeric_need - 6)
        span = _NUMERIC_COLUMNS + 1

        accents: List[tk.Misc] = []
        rules: List[tk.Frame] = []
        row = 0
        first = True
        for block in self._blocks or []:
            if isinstance(block, Heading):
                if not first:
                    rule = tk.Frame(self, height=1, borderwidth=0)
                    rule.grid(row=row, column=0, columnspan=span, sticky="ew", pady=(7 if not block.minor else 4, 2))
                    rules.append(rule)
                    row += 1
                options = {} if block.minor else {"fg": ACCENT}
                label = tk.Label(self, text=block.text, anchor="w", justify="left", wraplength=total - 4,
                                 font=fonts["bold"], **options)
                label.grid(row=row, column=0, columnspan=span, sticky="w")
                if not block.minor:
                    accents.append(label)
                row += 1
            elif isinstance(block, Pair):
                font = fonts["bold"] if block.bold else fonts["normal"]
                tk.Label(self, text=block.label, anchor="w", justify="left", font=font,
                         wraplength=max(90, min(int(total * _LABEL_SHARE), title_wrap) - block.indent * _INDENT)).grid(
                    row=row, column=0, sticky="nw", padx=(block.indent * _INDENT, 0))
                tk.Label(self, text=block.value, anchor="e", justify="right", font=font,
                         wraplength=int(total * _VALUE_SHARE)).grid(
                    row=row, column=1, columnspan=_NUMERIC_COLUMNS, sticky="ne", padx=(_GAP, 0))
                row += 1
            elif isinstance(block, Columns):
                for position, text in enumerate(block.labels[-_NUMERIC_COLUMNS:]):
                    column = 1 + _NUMERIC_COLUMNS - len(block.labels[-_NUMERIC_COLUMNS:]) + position
                    tk.Label(self, text=text, anchor="e", font=fonts["small_bold"]).grid(
                        row=row, column=column, sticky="e", padx=(_GAP, 0))
                row += 1
            elif isinstance(block, Item):
                tk.Label(self, text=block.title, anchor="w", justify="left", font=fonts["bold"],
                         wraplength=max(90, title_wrap - block.indent * _INDENT)).grid(
                    row=row, column=0, sticky="nw", padx=(block.indent * _INDENT, 0), pady=(3, 0))
                cells = block.cells[-_NUMERIC_COLUMNS:]
                for position, text in enumerate(cells):
                    column = 1 + _NUMERIC_COLUMNS - len(cells) + position
                    tk.Label(self, text=text, anchor="e", font=fonts["normal"]).grid(
                        row=row, column=column, sticky="ne", padx=(_GAP, 0), pady=(3, 0))
                row += 1
                if block.detail:
                    tk.Label(self, text=block.detail, anchor="w", justify="left", font=fonts["small"],
                             wraplength=total - 8 - block.indent * _INDENT - _INDENT).grid(
                        row=row, column=0, columnspan=span, sticky="w",
                        padx=(block.indent * _INDENT + _INDENT, 0))
                    row += 1
                if block.warn:
                    warn = tk.Label(self, text=block.warn, anchor="w", justify="left", font=fonts["small"], fg=ACCENT,
                                    wraplength=total - 8 - block.indent * _INDENT - _INDENT)
                    warn.grid(row=row, column=0, columnspan=span, sticky="w",
                              padx=(block.indent * _INDENT + _INDENT, 0))
                    accents.append(warn)
                    row += 1
            elif isinstance(block, Note):
                options = {"fg": ACCENT} if block.warn else {}
                label = tk.Label(self, text=block.text, anchor="w", justify="left", wraplength=total - 4,
                                 font=fonts["bold"] if block.strong else fonts["normal"], **options)
                label.grid(row=row, column=0, columnspan=span, sticky="w", pady=(2, 0))
                if block.warn:
                    accents.append(label)
                row += 1
            first = False

        # EDMC's theme colours the labels; the accent, the rules and the frames' own background are set after it.
        panelkit.apply_theme_deep(self)
        for widget in accents:
            widget.configure(fg=ACCENT)
        colour = panelkit.separator_colour()
        for rule in rules:
            rule.configure(background=colour)
