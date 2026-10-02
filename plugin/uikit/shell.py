"""Window shell: a Toplevel with a header bar (title, subtitle, action
buttons), a body, a status footer, a minimum size and saved geometry. The
shell never touches EDMC's config - the owning window passes
`load_geometry`/`save_geometry` callables (a `config.get_str` / `config.set`
pair in the real windows), which also keeps this demoable standalone."""
from __future__ import annotations

import re
import tkinter as tk
from typing import Callable, Optional

from . import palette as P
from . import style
from .widgets import FlatButton

_GEOMETRY = re.compile(r"^(\d+)x(\d+)([+-]-?\d+[+-]-?\d+)?$")


class WindowShell:
    def __init__(self, parent: tk.Misc, title: str, subtitle: str = "",
                 size: tuple[int, int] = (1180, 720), min_size: tuple[int, int] = (900, 520),
                 load_geometry: Optional[Callable[[], str]] = None,
                 save_geometry: Optional[Callable[[str], None]] = None) -> None:
        self.window = tk.Toplevel(parent)
        # Built hidden and shown once (see _present): a window that maps first
        # and is then sized, positioned and filled flashes at its default size.
        self.window.withdraw()
        style.skin(self.window)
        factor = style.dpi_factor(self.window)
        size = (int(size[0] * factor), int(size[1] * factor))
        min_size = (int(min_size[0] * factor), int(min_size[1] * factor))
        self.window.title(title)
        self.window.configure(bg=P.BG)
        self.window.minsize(*min_size)
        self._save_geometry = save_geometry
        self.window.geometry(self._geometry(load_geometry, size, min_size))
        self.window.bind("<Escape>", lambda _e: self.close())
        self.window.protocol("WM_DELETE_WINDOW", self.close)

        header = tk.Frame(self.window, bg=P.BG, padx=P.PAD * 2, pady=P.PAD)
        header.pack(fill="x")
        titles = tk.Frame(header, bg=P.BG)
        titles.pack(side="left")
        tk.Label(titles, text=title, fg=P.TEXT, bg=P.BG, font=style.font(P.FONT_TITLE)).pack(anchor="w")
        self._subtitle = tk.Label(titles, text=subtitle, fg=P.MUTED, bg=P.BG)
        self._subtitle.pack(anchor="w")
        self.actions = tk.Frame(header, bg=P.BG)
        self.actions.pack(side="right")

        # Footer first so it keeps its height when the body is squeezed.
        footer = tk.Frame(self.window, bg=P.BG, padx=P.PAD * 2, pady=P.PAD_SM)
        footer.pack(side="bottom", fill="x")
        self._status = tk.Label(footer, text="", fg=P.MUTED, bg=P.BG, anchor="w",
                                font=style.font(P.FONT_SMALL))
        self._status.pack(fill="x")
        footer.bind("<Configure>", lambda e: self._status.configure(
            wraplength=max(e.width - 2 * P.PAD * 2, 100)))  # long hints wrap instead of clipping

        self.body = tk.Frame(self.window, bg=P.BG, padx=P.PAD * 2)
        self.body.pack(fill="both", expand=True)

        # Runs once the owning window's __init__ has finished adding content.
        self.window.after_idle(self._present)

    def _present(self) -> None:
        """Lay everything out while hidden, then show the finished window."""
        if not self.alive:
            return
        self.window.update_idletasks()   # also runs content layout queued with after_idle
        self.window.deiconify()
        self.window.lift()

    @staticmethod
    def _geometry(load: Optional[Callable[[], str]], size: tuple[int, int],
                  min_size: tuple[int, int]) -> str:
        """Saved geometry grown to the minimum size; the default otherwise."""
        saved = load() if load else ""
        match = _GEOMETRY.match(saved or "")
        if not match:
            return f"{size[0]}x{size[1]}"
        width = max(int(match.group(1)), min_size[0])
        height = max(int(match.group(2)), min_size[1])
        return f"{width}x{height}{match.group(3) or ''}"

    def add_action(self, text: str, command: Callable[[], None], accent: bool = False) -> FlatButton:
        button = FlatButton(self.actions, text, command, kind="accent" if accent else "normal")
        button.pack(side="left", padx=(6, 0))
        return button

    def set_subtitle(self, text: str) -> None:
        self._subtitle.configure(text=text)

    def set_status(self, text: str) -> None:
        self._status.configure(text=text)

    @property
    def alive(self) -> bool:
        try:
            return bool(self.window.winfo_exists())
        except tk.TclError:
            return False

    def close(self) -> None:
        if self.alive:
            if self._save_geometry:
                self._save_geometry(self.window.winfo_geometry())
            self.window.destroy()
