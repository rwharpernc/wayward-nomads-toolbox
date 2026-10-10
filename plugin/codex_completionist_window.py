"""Detail popup for Codex Completionist: what you've found (grouped by
category) and what you haven't (the "Not found" tab), with the same
`show(parent, ...)` entry point and geometry-persistence convention as the
other WNTB windows. Built on the shared window kit (plugin/uikit - see
docs/WINDOW_FRAMEWORK_SPEC.md).

Both tabs sort by clicking a column heading (click again to reverse). The
tables are grouped, so sorting is done here - each group's rows are
re-inserted in the new order - rather than by DataTable's own flat sort.

"Not found" is the Canonn entry catalog (codex_catalog.py) minus what the
journal tally holds. The catalog is cached on disk and refreshed in the
background when stale, so the window never waits on the network. Every row,
found or not, links to a Canonn reference search for that entry (double-click
or "Open Reference").
"""

from __future__ import annotations

import logging
import os
import queue
import threading
import tkinter as tk
import webbrowser
from typing import Dict, List, Optional, Tuple

from config import appname, config

from . import codex_catalog
from .codex_catalog import CatalogEntry
from .codex_completionist import CodexEntryRecord, CodexTally
from .uikit import palette as P
from .uikit.shell import WindowShell
from .uikit.table import Column, DataTable
from .uikit.widgets import Tabs

plugin_name = os.path.basename(os.path.dirname(__file__))
logger = logging.getLogger(f"{appname}.{plugin_name}")

CONFIG_GEOMETRY = "wntb_codex_completionist_window_geometry"

MIN_WIDTH = 560
MIN_HEIGHT = 420
DEFAULT_SIZE = (760, 580)

_FOUND_COLUMNS = (
    Column("entry", "Entry", 300, stretch=True, max_chars=70),
    Column("found", "Times found", 110, anchor="e"),
    Column("system", "First found in", 200, max_chars=40),
)
_MISSING_COLUMNS = (
    Column("entry", "Entry", 300, stretch=True, max_chars=70),
    Column("type", "Type", 140, max_chars=24),
    Column("platform", "Platform", 100, max_chars=12),
)

_FOUND_TAB, _MISSING_TAB = 0, 1
# First click on a heading sorts this way; clicking it again reverses.
_FIRST_DIRECTION_DESC = {"found"}

_window: Optional["CodexCompletionistWindow"] = None


def refresh_if_open(tally: CodexTally) -> None:
    """The active commander changed (or a rebuild finished): show this tally if the window is open."""
    if _window is not None and _window.alive:
        _window.refresh(tally)


def show(parent: tk.Misc, tally: CodexTally, plugin_dir: str) -> None:
    """Open the details window, or raise/refresh it if already open."""
    global _window
    if _window is not None and _window.alive:
        _window.refresh(tally)
        _window.lift()
        return
    _window = CodexCompletionistWindow(parent, tally, plugin_dir)


def sort_records(records: List[CodexEntryRecord], key: str, descending: bool) -> List[CodexEntryRecord]:
    """Found-tab ordering. Ties always fall back to the entry name, so equal
    counts stay alphabetical in either direction."""
    def name(r: CodexEntryRecord) -> str:
        return (r.name_localised or r.name).casefold()
    if key == "found":
        return sorted(records, key=lambda r: (-r.times_found if descending else r.times_found, name(r)))
    if key == "system":
        return sorted(records, key=lambda r: (r.first_system.casefold(), name(r)), reverse=descending)
    return sorted(records, key=name, reverse=descending)


def sort_missing(entries: List[CatalogEntry], key: str, descending: bool) -> List[CatalogEntry]:
    if key == "type":
        return sorted(entries, key=lambda e: (e.sub_class.casefold(), e.english_name.casefold()), reverse=descending)
    if key == "platform":
        return sorted(entries, key=lambda e: (e.platform.casefold(), e.english_name.casefold()), reverse=descending)
    return sorted(entries, key=lambda e: e.english_name.casefold(), reverse=descending)


class CodexCompletionistWindow:
    def __init__(self, parent: tk.Misc, tally: CodexTally, plugin_dir: str) -> None:
        self._tally = tally
        self._plugin_dir = plugin_dir
        self._catalog: Optional[List[CatalogEntry]] = None
        self._catalog_note = ""
        self._fetching = False
        self._fetch_results: "queue.Queue[Tuple[Optional[List[CatalogEntry]], Optional[str]]]" = queue.Queue()
        self._sort: Dict[int, Tuple[str, bool]] = {_FOUND_TAB: ("entry", False), _MISSING_TAB: ("entry", False)}
        self._reference: Dict[int, Dict[str, str]] = {_FOUND_TAB: {}, _MISSING_TAB: {}}

        self._shell = WindowShell(
            parent, "Codex Completionist", "", size=DEFAULT_SIZE, min_size=(MIN_WIDTH, MIN_HEIGHT),
            load_geometry=lambda: config.get_str(CONFIG_GEOMETRY) or "",
            save_geometry=lambda geometry: config.set(CONFIG_GEOMETRY, geometry))
        self._shell.window.protocol("WM_DELETE_WINDOW", self.close)
        self._toplevel = self._shell.window

        self._shell.add_action("Open Reference", self._on_open_reference, accent=True)
        self._shell.add_action("Refresh Catalog", self._on_refresh_catalog)

        self._tabs = Tabs(self._shell.body)
        self._tabs.pack(fill="both", expand=True, pady=(0, P.PAD_SM))
        self._found_table = DataTable(
            self._tabs.add("Found"), _FOUND_COLUMNS, sortable=False,
            on_header=lambda key: self._on_header(_FOUND_TAB, key),
            on_activate=lambda iid: self._open(_FOUND_TAB, iid))
        self._found_table.pack(fill="both", expand=True)
        self._missing_table = DataTable(
            self._tabs.add("Not found"), _MISSING_COLUMNS, sortable=False,
            on_header=lambda key: self._on_header(_MISSING_TAB, key),
            on_activate=lambda iid: self._open(_MISSING_TAB, iid))
        self._missing_table.pack(fill="both", expand=True)

        self._catalog = codex_catalog.load_cache(plugin_dir)
        if self._catalog is None or codex_catalog.cache_is_stale(plugin_dir):
            self._start_fetch()
        self.refresh(tally)

    @property
    def alive(self) -> bool:
        return self._shell.alive

    def lift(self) -> None:
        self._toplevel.deiconify()
        self._toplevel.lift()

    # --- data -----------------------------------------------------------------

    def refresh(self, tally: CodexTally) -> None:
        if not self.alive:
            return
        self._tally = tally
        self._fill_found()
        self._fill_missing()
        self._update_subtitle()

    def _missing(self) -> Optional[List[CatalogEntry]]:
        if self._catalog is None:
            return None
        records = self._tally.records
        return codex_catalog.missing_entries(
            self._catalog, (r.name for r in records), (r.entry_id for r in records))

    def _update_subtitle(self) -> None:
        owner = f"CMDR {self._tally.owner} — " if self._tally.owner else ""
        text = f"{owner}{self._tally.total_distinct:,} distinct entries — {self._tally.total_finds:,} total finds"
        missing = self._missing()
        if missing is not None and self._catalog:
            found = len(self._catalog) - len(missing)
            text += f" — {found:,} of {len(self._catalog):,} catalogued entries found ({found / len(self._catalog):.0%})"
        self._shell.set_subtitle(text)

    # --- tables ---------------------------------------------------------------

    def _fill_found(self) -> None:
        key, descending = self._sort[_FOUND_TAB]
        table = self._found_table
        table.clear()
        self._reference[_FOUND_TAB].clear()
        for category, entries in sorted(self._tally.by_category().items()):
            category_id = table.append((f"{category} ({len(entries)})", "", ""), group=True)
            for record in sort_records(entries, key, descending):
                name = record.name_localised or record.name
                label = name + ("  ⭐" if record.was_first_discovery else "")
                iid = table.append((label, f"{record.times_found:,}", record.first_system), parent=category_id)
                self._reference[_FOUND_TAB][iid] = name
        table.mark_sorted(key, descending)

    def _fill_missing(self) -> None:
        key, descending = self._sort[_MISSING_TAB]
        table = self._missing_table
        table.clear()
        self._reference[_MISSING_TAB].clear()
        missing = self._missing()
        if missing is None:
            self._shell.set_status(self._catalog_note or "Loading the entry catalog from Canonn...")
            table.append((self._catalog_note or "Loading the entry catalog from Canonn...", "", ""))
            table.mark_sorted(key, descending)
            return
        by_category: Dict[str, List[CatalogEntry]] = {}
        for entry in missing:
            by_category.setdefault(entry.category, []).append(entry)
        if not missing:
            table.append(("Nothing missing - every catalogued entry has been found.", "", ""))
        for category, entries in sorted(by_category.items()):
            category_id = table.append((f"{category} ({len(entries)})", "", ""), group=True)
            for entry in sort_missing(entries, key, descending):
                iid = table.append((entry.english_name, entry.sub_class, entry.platform), parent=category_id)
                self._reference[_MISSING_TAB][iid] = entry.english_name
        table.mark_sorted(key, descending)
        self._shell.set_status(
            "Not found = Canonn's catalog of biological, civilisation and stellar-body entries, minus yours. "
            "Double-click a row for its Canonn reference.")

    def _on_header(self, tab: int, key: str) -> None:
        current, descending = self._sort[tab]
        self._sort[tab] = (key, not descending) if key == current else (key, key in _FIRST_DIRECTION_DESC)
        if tab == _FOUND_TAB:
            self._fill_found()
        else:
            self._fill_missing()

    # --- references -----------------------------------------------------------

    def _open(self, tab: int, iid: str) -> None:
        name = self._reference[tab].get(iid)
        if name:
            webbrowser.open(codex_catalog.reference_url(name))

    def _on_open_reference(self) -> None:
        tab = self._tabs.selected
        table = self._found_table if tab == _FOUND_TAB else self._missing_table
        selection = table.selection()
        if not selection or selection[0] not in self._reference[tab]:
            self._shell.set_status("Select an entry first (or double-click one) to open its Canonn reference.")
            return
        self._open(tab, selection[0])

    # --- catalog fetch ----------------------------------------------------------

    def _on_refresh_catalog(self) -> None:
        if not self._fetching:
            self._start_fetch()

    def _start_fetch(self) -> None:
        self._fetching = True
        self._catalog_note = "Loading the entry catalog from Canonn..." if self._catalog is None else ""
        if self._catalog is not None:
            self._shell.set_status("Refreshing the entry catalog from Canonn...")
        threading.Thread(target=self._fetch_worker, name="WNTB-codex-catalog", daemon=True).start()
        self._toplevel.after(250, self._poll_fetch)

    def _fetch_worker(self) -> None:
        try:
            self._fetch_results.put((codex_catalog.fetch_catalog(), None))
        except Exception as exc:  # noqa: BLE001 - any failure is reported, never raised into Tk
            logger.warning("Codex catalog fetch failed: %s", exc)
            self._fetch_results.put((None, str(exc)))

    def _poll_fetch(self) -> None:
        if not self.alive:
            return
        try:
            entries, error = self._fetch_results.get_nowait()
        except queue.Empty:
            self._toplevel.after(250, self._poll_fetch)
            return
        self._fetching = False
        if entries is not None:
            self._catalog = entries
            self._catalog_note = ""
            codex_catalog.save_cache(self._plugin_dir, entries)
        elif self._catalog is None:
            self._catalog_note = f"Couldn't load the entry catalog from Canonn ({error}). Try Refresh Catalog."
        else:
            self._shell.set_status(f"Couldn't refresh the catalog ({error}); showing the saved copy.")
        self.refresh(self._tally)

    def close(self) -> None:
        self._shell.close()
