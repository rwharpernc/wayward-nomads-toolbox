"""A Settings page that scrolls instead of growing taller than the screen.

EDMC sizes its Settings window to the tallest page in every plugin's notebook. A long WNTB page (Mining,
Exploration > Alerts, ...) used to push the window past the bottom of the screen, taking the OK button with it.
`scrolled_page` wraps one page in a canvas with a scrollbar and caps the canvas at `height_cap`; a page shorter
than the cap looks exactly as it did before (no scrollbar, no extra space).

Each feature's `build_settings(notebook)` is unchanged: it is handed a `ScrollContent`, which accepts
`add(frame, text=...)` like a notebook does, and the finished page is added to the real notebook.
Widgets inside are only ever placed with `grid` (never `pack` into an nb.Frame; see tests/test_settings_layout.py).
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Any, List

import myNotebook as nb

MIN_CAP = 260           # never shorter than this, so a small screen still shows a usable page
MAX_CAP = 640           # never taller than this, so a huge screen doesn't get an enormous page
CHROME_ALLOWANCE = 460  # window title, EDMC's own tabs, our two tab rows, the version line and the OK/Cancel row
_SKIP_WHEEL = {"Listbox", "Text", "Treeview", "TCombobox"}  # these scroll themselves


def height_cap(screen_height: int) -> int:
    """The tallest a page's visible area may be on a screen this tall."""
    return max(MIN_CAP, min(MAX_CAP, screen_height - CHROME_ALLOWANCE))


class ScrollContent(nb.Frame):
    """What a feature's `build_settings` receives in place of a notebook. Its `add` stacks the frames it is given
    (with a rule between them if there is more than one) and, on the first call, adds the scrolling page to the
    real notebook under the same tab options."""

    def __init__(self, page: "ScrolledPage", canvas: tk.Canvas) -> None:
        super().__init__(canvas)
        self._page = page
        self.columnconfigure(0, weight=1)
        self._next_row = 1  # row 0 is nb.Frame's own gridded spacer

    def add(self, child: tk.Misc, **options: Any) -> None:
        if self._next_row > 1:
            ttk.Separator(self, orient=tk.HORIZONTAL).grid(row=self._next_row, column=0, sticky=tk.EW, padx=10, pady=4)
            self._next_row += 1
        child.grid(row=self._next_row, column=0, sticky=tk.EW)
        self._next_row += 1
        self._page.attach(**options)


class ScrolledPage(tk.Frame):
    """A plain tk.Frame (so it may be packed or gridded freely) holding a canvas, a scrollbar and the content."""

    def __init__(self, notebook: tk.Misc, background: str, cap: int) -> None:
        super().__init__(notebook, background=background)
        self._notebook = notebook
        self._cap = cap
        self._attached = False
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)
        self._canvas = tk.Canvas(self, background=background, highlightthickness=0, borderwidth=0,
                                 yscrollincrement=18)
        self._canvas.grid(row=0, column=0, sticky=tk.NSEW)
        self._bar = ttk.Scrollbar(self, orient=tk.VERTICAL, command=self._canvas.yview)
        self._canvas.configure(yscrollcommand=self._bar.set)
        self.content = ScrollContent(self, self._canvas)
        self._window = self._canvas.create_window(0, 0, window=self.content, anchor=tk.NW)
        self.content.bind("<Configure>", lambda _e: self.refit(), add="+")
        self._canvas.bind("<Configure>", self._canvas_resized, add="+")

    def attach(self, **options: Any) -> None:
        if not self._attached:
            self._attached = True
            self._notebook.add(self, **options)

    def _canvas_resized(self, event: tk.Event) -> None:
        self._canvas.itemconfigure(self._window, width=event.width)

    def refit(self) -> None:
        """Size the visible area to the content, up to the cap; show the scrollbar only if the content is taller."""
        wanted = self.content.winfo_reqheight()
        shown = min(wanted, self._cap)
        self._canvas.configure(height=shown, width=self.content.winfo_reqwidth(),
                               scrollregion=(0, 0, self.content.winfo_reqwidth(), wanted))
        if wanted > self._cap:
            self._bar.grid(row=0, column=1, sticky=tk.NS)
        else:
            self._bar.grid_remove()
            self._canvas.yview_moveto(0)

    def finish(self) -> None:
        """Call once the page is built: fit it, and make the mouse wheel scroll it from anywhere over it."""
        self.update_idletasks()
        self.refit()
        self._bind_wheel(self)

    def _bind_wheel(self, widget: tk.Misc) -> None:
        if widget.winfo_class() not in _SKIP_WHEEL:
            for sequence in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
                widget.bind(sequence, self._on_wheel, add="+")
        for child in widget.winfo_children():
            self._bind_wheel(child)

    def _on_wheel(self, event: tk.Event) -> None:
        if self.content.winfo_reqheight() <= self._cap:
            return
        if getattr(event, "num", None) == 4 or getattr(event, "delta", 0) > 0:
            self._canvas.yview_scroll(-3, "units")
        else:
            self._canvas.yview_scroll(3, "units")


def scrolled_page(notebook: tk.Misc, build: Any, background: str) -> ScrolledPage:
    """Build one feature's Settings page inside a scrolling frame and add it to `notebook`.
    `build` is the feature's `build_settings(notebook)`; it sees a ScrollContent where a notebook would be."""
    page = ScrolledPage(notebook, background, height_cap(notebook.winfo_screenheight()))
    build(page.content)
    page.finish()
    return page
