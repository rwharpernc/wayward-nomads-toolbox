"""The Prediction review window: how the species prediction did against what the game confirmed, with a way to review each find by hand.

Built on the shared window kit (plugin/uikit). The numbers come from `exo_analysis` (pure) over the records `exo_observations.ObservationBook` keeps. Four tabs:
Finds (every confirmed species with whether the prediction listed it, a filter, and under the table the body's conditions, what was predicted and a review
box: a status and a note), Genera (hit rate and how long the predicted list was), Ranges (the temperature, gravity and pressure each species was found at
beside the range its rules allow) and Together (which species shared a body). **Copy report** puts the whole analysis on the clipboard as text.

A review is kept in the same file as the finds (global, naming no commander) and changes nothing about the prediction: it is a note to whoever next tunes the rules.
Module-level show/refresh/close and saved geometry follow notes_window.py.
"""
from __future__ import annotations

import logging
import os
import tkinter as tk
from typing import Callable, Dict, List, Optional, Sequence, Tuple

from config import appname, config

from . import exo_analysis as A
from . import exo_observations, panelkit
from .uikit import palette as P
from .uikit.shell import WindowShell
from .uikit.table import Column, DataTable
from .uikit.widgets import Combobox, FlatButton, NoteLabel, Tabs

plugin_name = os.path.basename(os.path.dirname(__file__))
logger = logging.getLogger(f"{appname}.{plugin_name}")

CONFIG_GEOMETRY = "wntb_exo_review_window_geometry"
DEFAULT_SIZE = (1100, 720)
MIN_SIZE = (860, 520)
ROW_KEY_SEPARATOR = "\t"

# (label, test) - the Finds tab's filter
FILTERS: Tuple[Tuple[str, Callable[[A.Find], bool]], ...] = (
    ("All finds", lambda f: True),
    ("Not on the predicted list", lambda f: not f.hit),
    ("Outside a rule's range", lambda f: bool(f.outside)),
    ("Not reviewed yet", lambda f: not f.status),
    ("Needs a rule change", lambda f: f.status == "rule"),
    ("Look at again later", lambda f: f.status == "later"),
    ("Recorded live only", lambda f: f.source == "live"),
)

_window: Optional["ExoReviewWindow"] = None

_FIND_COLUMNS = (
    Column("result", "Result", 80),
    Column("species", "Species", 200, stretch=True, max_chars=40),
    Column("where", "System and body", 240, max_chars=48),
    Column("kind", "Body type / atmosphere", 230, max_chars=44),
    Column("listed", "Listed", 60, anchor="e"),
    Column("review", "Review", 190, max_chars=40),
)
_GENUS_COLUMNS = (
    Column("genus", "Genus", 200, stretch=True),
    Column("finds", "Finds", 80, anchor="e"),
    Column("hits", "On the list", 100, anchor="e"),
    Column("percent", "Hit rate", 90, anchor="e"),
    Column("average", "Average list length", 150, anchor="e"),
)
_RANGE_COLUMNS = (
    Column("species", "Species", 220, stretch=True, max_chars=40),
    Column("name", "Condition", 110),
    Column("finds", "Finds", 70, anchor="e"),
    Column("observed", "Observed", 200),
    Column("rules", "Rules allow", 200),
    Column("flag", "", 130),
)
_TOGETHER_COLUMNS = (
    Column("kind", "Body type / atmosphere", 250, max_chars=44),
    Column("species", "Found together", 520, stretch=True, max_chars=90),
    Column("bodies", "Bodies", 80, anchor="e"),
)


def show(parent: tk.Misc, book: exo_observations.ObservationBook) -> None:
    """Open the window, or raise it if it is already open."""
    global _window
    if _window is not None and _window.alive:
        _window.refresh()
        _window.lift()
        return
    _window = ExoReviewWindow(parent, book)


def refresh() -> None:
    if _window is not None and _window.alive:
        _window.refresh()


def close() -> None:
    if _window is not None and _window.alive:
        _window.close()


def row_id(find: A.Find) -> str:
    return f"{find.body_key}{ROW_KEY_SEPARATOR}{find.genus_key}"


def find_row(find: A.Find) -> List[str]:
    """The Finds table's cells for one find."""
    result = ("On list" if find.hit else "MISSED") + (" !" if find.outside else "")      # "!": found outside a rule's range
    review = A.REVIEW_LABELS.get(find.status, find.status) if find.status else ""
    return [result, find.species, f"{find.system} {find.body}".strip(), f"{find.planet_class} / {find.atmosphere or 'none'}", str(find.list_length), review]


def filtered(finds: Sequence[A.Find], label: str) -> List[A.Find]:
    test = dict(FILTERS).get(label, FILTERS[0][1])
    return [f for f in finds if test(f)]


class ExoReviewWindow:
    def __init__(self, parent: tk.Misc, book: exo_observations.ObservationBook) -> None:
        self._book = book
        self._finds: Dict[str, A.Find] = {}
        self._picked: Optional[str] = None

        self._shell = WindowShell(
            parent, "Prediction review", "", size=DEFAULT_SIZE, min_size=MIN_SIZE,
            load_geometry=lambda: config.get_str(CONFIG_GEOMETRY) or "",
            save_geometry=lambda geometry: config.set(CONFIG_GEOMETRY, geometry))
        self._shell.window.protocol("WM_DELETE_WINDOW", self.close)
        self._shell.add_action("Copy report", self._copy_report)

        tabs = Tabs(self._shell.body)
        tabs.pack(fill="both", expand=True, pady=(0, P.PAD_SM))
        self._build_finds(tabs.add("Finds"))
        self._genus_table = self._plain_table(tabs.add("Genera"), _GENUS_COLUMNS, _GENUS_NOTE,
                                              "Nothing recorded yet. Sample something with WNTB running and it appears here.")
        self._range_table = self._plain_table(tabs.add("Ranges"), _RANGE_COLUMNS, _RANGE_NOTE, "Nothing recorded yet.")
        self._range_table.tag_configure("outside", foreground=P.DANGER)
        self._together_table = self._plain_table(tabs.add("Together"), _TOGETHER_COLUMNS, _TOGETHER_NOTE, "No body with more than one species recorded yet.")
        self.refresh()

    # --- building ------------------------------------------------------------------------------------------------------

    @staticmethod
    def _plain_table(frame: tk.Frame, columns: Sequence[Column], note: str, empty: str) -> DataTable:
        NoteLabel(frame, text=note, bg=P.PANE).pack(fill="x", padx=P.PAD, pady=(P.PAD_SM, 0))
        table = DataTable(frame, columns, empty_text=empty)
        table.pack(fill="both", expand=True, padx=P.PAD_SM, pady=P.PAD_SM)
        return table

    def _build_finds(self, frame: tk.Frame) -> None:
        bar = tk.Frame(frame, bg=P.PANE)
        bar.pack(fill="x", padx=P.PAD, pady=(P.PAD_SM, 0))
        tk.Label(bar, text="Show", fg=P.MUTED, bg=P.PANE).pack(side="left")
        self._filter = tk.StringVar(value=FILTERS[0][0])
        box = Combobox(bar, textvariable=self._filter, values=[label for label, _t in FILTERS], state="readonly", width=28)
        box.pack(side="left", padx=P.PAD_SM)
        box.bind("<<ComboboxSelected>>", lambda _e: self._fill_finds())
        self._count = tk.Label(bar, text="", fg=P.MUTED, bg=P.PANE)
        self._count.pack(side="left", padx=P.PAD)

        self._finds_table = DataTable(frame, _FIND_COLUMNS, on_select=self._pick, empty_text="No finds match.", visible_rows=9)
        self._finds_table.tag_configure("miss", foreground=P.DANGER)
        self._finds_table.tag_configure("outside", foreground=P.WARN)
        self._finds_table.pack(fill="x", padx=P.PAD_SM, pady=P.PAD_SM)

        detail = tk.Frame(frame, bg=P.CARD, padx=P.PAD, pady=P.PAD)
        detail.pack(fill="both", expand=True, padx=P.PAD_SM, pady=(0, P.PAD_SM))
        detail.columnconfigure(1, weight=1)
        self._detail_title = tk.Label(detail, text="Pick a find to see its conditions and review it.", fg=P.TEXT, bg=P.CARD, anchor="w")
        self._detail_title.grid(row=0, column=0, columnspan=3, sticky="ew")
        self._detail = NoteLabel(detail, text="", bg=P.CARD)
        self._detail.grid(row=1, column=0, columnspan=3, sticky="ew", pady=(2, P.PAD_SM))
        tk.Label(detail, text="Review", fg=P.MUTED, bg=P.CARD).grid(row=2, column=0, sticky="w")
        self._status = tk.StringVar(value=A.REVIEW_LABELS[A.UNREVIEWED])
        self._status_box = Combobox(detail, textvariable=self._status, values=[label for _k, label in A.REVIEW_STATUSES], state="readonly", width=26)
        self._status_box.grid(row=2, column=1, sticky="w", padx=P.PAD_SM, pady=2)
        tk.Label(detail, text="Note", fg=P.MUTED, bg=P.CARD).grid(row=3, column=0, sticky="w")
        self._note = tk.StringVar()
        self._note_box = tk.Entry(detail, textvariable=self._note, bg=P.PANE, fg=P.TEXT, insertbackground=P.TEXT, relief="flat")
        self._note_box.grid(row=3, column=1, sticky="ew", padx=P.PAD_SM, pady=2)
        self._save_button = FlatButton(detail, "Save review", self._save_review, kind="accent")
        self._save_button.grid(row=3, column=2, sticky="e")
        self._save_button.set_enabled(False)

    # --- the window ----------------------------------------------------------------------------------------------------

    @property
    def alive(self) -> bool:
        return self._shell.alive

    def lift(self) -> None:
        self._shell.window.deiconify()
        self._shell.window.lift()

    def close(self) -> None:
        self._shell.close()

    def refresh(self) -> None:
        if not self.alive:
            return
        bodies = self._book.bodies()
        rows = A.finds(bodies)
        self._finds = {row_id(f): f for f in rows}
        misses = sum(1 for f in rows if not f.hit)
        self._shell.set_subtitle(f"{len(rows)} find{'s' if len(rows) != 1 else ''} on {len(bodies)} bod{'ies' if len(bodies) != 1 else 'y'}"
                                 + (f", {misses} not on the predicted list" if rows else ""))
        self._fill_finds()
        self._genus_table.set_rows([[g.genus, g.finds, g.hits, f"{g.percent}%", f"{g.average_list:.1f}"] for g in A.genus_rows(rows)])
        self._range_table.clear()
        for r in A.range_rows(rows):
            self._range_table.append([r.species, f"{r.name} ({r.unit})", r.finds, r.observed_text, r.rule_text, "outside the range" if r.outside else ""],
                                     tag="outside" if r.outside else None)
        self._together_table.set_rows([[f"{t.planet_class} / {t.atmosphere}", " + ".join(t.species), t.bodies] for t in A.together_rows(bodies)])

    def _fill_finds(self) -> None:
        shown = filtered(list(self._finds.values()), self._filter.get())
        keep = self._picked
        self._finds_table.clear()
        for find in shown:
            tag = "miss" if not find.hit else ("outside" if find.outside else None)
            self._finds_table.insert(row_id(find), find_row(find), tag=tag)
        self._count.configure(text=f"{len(shown)} of {len(self._finds)}")
        if keep in {row_id(f) for f in shown}:
            self._finds_table.select(keep)
        else:
            self._picked = None
            self._show_detail()

    def _pick(self, iid: str) -> None:
        self._picked = iid
        self._show_detail()

    def _show_detail(self) -> None:
        find = self._finds.get(self._picked or "")
        self._save_button.set_enabled(find is not None)
        if find is None:
            self._detail_title.configure(text="Pick a find to see its conditions and review it.")
            self._detail.configure(text="")
            self._status.set(A.REVIEW_LABELS[A.UNREVIEWED])
            self._note.set("")
            return
        self._detail_title.configure(text=f"{find.species}{' - ' + find.variant if find.variant else ''}   ({find.system} {find.body})".strip())
        listed = ", ".join(A.predicted_names(find)) or "nothing"
        lines = [A.conditions_text(find.record)]
        if find.record.get("atmosphere_components"):
            lines.append("Atmosphere: " + ", ".join(f"{k} {v:.1f}%" for k, v in sorted(find.record["atmosphere_components"].items(), key=lambda kv: -kv[1])))
        if find.record.get("system_body_types"):
            lines.append("Body types in the system: " + ", ".join(find.record["system_body_types"]))
        lines.append(f"The prediction listed: {listed}." + ("" if find.hit else "  The confirmed species was NOT on that list: a rule is missing or too strict."))
        if find.outside:
            lines.append("Found outside the rules' range for: " + ", ".join(find.outside) + ".")
        if find.source != "live":
            lines.append("Filled in from older saved state, so the listed species are today's rules applied afterward.")
        self._detail.configure(text="\n".join(lines))
        self._status.set(A.REVIEW_LABELS.get(find.status, A.REVIEW_LABELS[A.UNREVIEWED]))
        self._note.set(find.note)

    # --- actions ---------------------------------------------------------------------------------------------------------

    def _save_review(self) -> None:
        find = self._finds.get(self._picked or "")
        if find is None:
            return
        status = next((key for key, label in A.REVIEW_STATUSES if label == self._status.get()), A.UNREVIEWED)
        if self._book.set_review(find.body_key, find.genus_key, status, self._note.get()):
            self._shell.set_status("Review saved.")
            keep = self._picked
            self.refresh()
            if keep in self._finds:
                self._finds_table.select(keep, notify=True)
        else:
            self._shell.set_status("That find is no longer in the record.")

    def _copy_report(self) -> None:
        text = A.report_text(self._book.bodies())
        ok = panelkit.copy_to_clipboard(self._shell.window, text)
        self._shell.set_status("Report copied to the clipboard." if ok else "Could not reach the clipboard.")


_GENUS_NOTE = "How often the species the game confirmed was on the predicted list. Under 100% means the rules missed a species; a long average list means the rules are loose."
_RANGE_NOTE = "The temperature, gravity and pressure each species was found at, beside the range the data allows it. A find outside the range means the range is too tight."
_TOGETHER_NOTE = "Species that grew on the same body, most common first. Bodies with one species are left out."
