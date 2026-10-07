"""BGS (Background Simulation) tracking — a mode (PANEL_PLACEMENT = "bgs"),
its own top-level main-panel mode alongside Powerplay/Exploration/Mining/
Missions/Field Ops (see ui.py's PANEL_MODES).

The main panel shows only the system the commander is in: each faction's
state and influence, plus what the commander has done to it since the last
galaxy tick. Every other system with activity this tick, and archived earlier
ticks, are in the BGS Report window (one tab per system) - see bgs_window.py.

All the bookkeeping is in bgs_ledger.TickLedger (pure, no Tk), fed by:

- live journal events (`handle_event`), and
- a replay of the commander's recent journal files (bgs_journal.py), run once
  per session whenever both the commander and the current tick time are known,
  so the totals are cumulative since the tick even if EDMC wasn't running for
  all of it.

Tick detection (bgs_tick_client.py, polled every 60s off the main thread via
the queue.Queue/generation-counter/threading.Thread/after()-poll pattern from
canonn_poi_panel.py/boxel_survey.py) closes the period: it is archived (kept
for the "archive days" setting) and a fresh period begins.

Per-commander state is persisted via bgs_state.py - restored on cmdr switch/
plugin start and re-saved after every state-changing journal event.
"""

from __future__ import annotations

import logging
import os
import queue
import threading
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import tkinter as tk

import myNotebook as nb
from config import appname, config

from . import bgs_format, bgs_journal, bgs_ledger, bgs_state, bgs_tick_client, bgs_window, panelkit, platform_support
from .bgs_ledger import PeriodView, TickLedger
from .bgs_tracker import snapshot_key

plugin_name = os.path.basename(os.path.dirname(__file__))
logger = logging.getLogger(f"{appname}.{plugin_name}")

PANEL_PLACEMENT = "bgs"

_CFG_ENABLED = "wntb_bgs_enabled"
_CFG_TICK_ENABLED = "wntb_bgs_tick_enabled"
_CFG_ARCHIVE_DAYS = "wntb_bgs_archive_days"

DEFAULT_ARCHIVE_DAYS = 7
MAX_ARCHIVE_DAYS = 90
MAX_FACTIONS_SHOWN = 8  # a system holds at most 7; the cap is a width/height backstop

_DISABLED_TEXT = "BGS tracking is disabled — see Settings."

_TICK_POLL_INTERVAL_MS = 60_000  # once a minute is plenty for a tick that moves daily
_TICK_FIRST_CHECK_DELAY_MS = 3_000  # let Tk/EDMC settle before the first network call
_TICK_QUEUE_POLL_MS = 300


def enabled() -> bool:
    # On by default - pure journal parsing, no network calls, same
    # reasoning as organic_scan_panel.py's own default.
    return config.get_bool(_CFG_ENABLED, default=True)


def tick_enabled() -> bool:
    """Gates the one network call this mode makes (the tick-time poll) -
    separate from `enabled()` so a commander can keep faction-state/activity
    tracking fully local if they'd rather not have WNTB talk to a third-party
    community service at all. On by default per the scoping decision behind
    this feature ("detect ticks")."""
    return config.get_bool(_CFG_TICK_ENABLED, default=True)


def archive_days() -> int:
    """How many days of closed ticks to keep (Settings), clamped to 1-90."""
    try:
        value = int(config.get_str(_CFG_ARCHIVE_DAYS) or DEFAULT_ARCHIVE_DAYS)
    except ValueError:
        value = DEFAULT_ARCHIVE_DAYS
    return max(1, min(MAX_ARCHIVE_DAYS, value))


class BgsController:
    def __init__(self) -> None:
        self._plugin_dir: Optional[str] = None
        self._cmdr: Optional[str] = None

        self._ledger = TickLedger()
        self._archive: List[Dict[str, Any]] = []
        """Closed tick periods, newest first (bgs_ledger.TickLedger.archive_record)."""
        self._pinned: List[str] = []
        """Systems the commander pinned in the report: always given a tab."""
        self._hidden: List[str] = []
        """Systems whose tab the commander closed (Add system brings one back)."""

        self._tick_current: Optional[str] = None  # newest tick the API reported this session
        self._tick_queue: "queue.Queue[Tuple[int, Optional[str], Optional[str]]]" = queue.Queue()
        self._tick_generation = 0
        self._tick_poll_started = False
        self._tick_status_text = "Tick check: not yet run."

        self._backfill_queue: "queue.Queue[Tuple[int, str, Optional[TickLedger], set]]" = queue.Queue()
        self._backfill_generation = 0
        self._backfill_running = False
        self._backfill_done_for: Optional[Tuple[str, str]] = None  # (cmdr, tick) already replayed
        self._live_buffer: List[Dict[str, Any]] = []
        """Live entries that arrived while a replay was running; re-applied on
        top of it (minus any the replay already saw) when it finishes."""

        self._parent: Optional[tk.Frame] = None
        self._current_system_var: Optional[tk.StringVar] = None
        self._tick_status_var: Optional[tk.StringVar] = None
        self._enabled_var: Optional[tk.BooleanVar] = None
        self._tick_enabled_var: Optional[tk.BooleanVar] = None
        self._archive_days_var: Optional[tk.StringVar] = None

    # --- lifecycle / persistence -----------------------------------------

    def start(self, plugin_dir: str) -> None:
        self._plugin_dir = plugin_dir
        # State is per-commander and EDMC doesn't know which commander is
        # active until the first journal event - the actual restore happens
        # in _switch_cmdr(), called from handle_event().

    def stop(self) -> None:
        self._persist()

    def _switch_cmdr(self, cmdr: str) -> None:
        """Called whenever the active commander changes, including the first
        journal event of a session - saves the previous commander's BGS state
        (if one was loaded) and loads this commander's own."""
        self._persist()
        self._cmdr = cmdr
        self._backfill_done_for = None
        self._live_buffer = []
        saved = bgs_state.load_state(self._plugin_dir, cmdr) if self._plugin_dir else None
        data = saved if isinstance(saved, dict) else bgs_state.default_state()
        self._ledger = TickLedger.from_dict(data.get("ledger"))
        if self._ledger.tick_start is None:
            # A pre-ledger state file: its last-seen tick is still the best
            # guess at when this period began.
            self._ledger.set_tick_start((data.get("tick") or {}).get("last_seen_at"))
        self._pinned = self._load_names(data.get("pinned_systems"))
        self._hidden = self._load_names(data.get("hidden_systems"))
        raw_archive = data.get("archive")
        self._archive = [r for r in raw_archive if isinstance(r, dict)] if isinstance(raw_archive, list) else []
        self._archive = bgs_ledger.prune_archive(self._archive, datetime.now(timezone.utc), archive_days())
        if saved:
            logger.info("Restored BGS state for %s: %d faction(s) with activity, %d archived tick(s)",
                        cmdr, len(self._ledger.activity), len(self._archive))
        self._refresh_display()
        self._reconcile_tick()

    def _persist(self) -> None:
        if self._plugin_dir is None or self._cmdr is None:
            return
        bgs_state.save_state(self._plugin_dir, self._cmdr, {
            "ledger": self._ledger.to_dict(),
            "archive": self._archive,
            "pinned_systems": self._pinned,
            "hidden_systems": self._hidden,
        })

    # --- journal dispatch -----------------------------------------------

    def handle_event(self, entry: Dict[str, Any], cmdr: str, system: Optional[str], station: Optional[str], state: Dict[str, Any]) -> None:
        if cmdr and cmdr != self._cmdr:
            self._switch_cmdr(cmdr)

        if not enabled():
            return

        if self._backfill_running:
            self._live_buffer.append(entry)
        if self._ledger.process(entry, system):
            self._persist()
            self._refresh_display()
        elif entry.get("event") in ("Docked", "Undocked"):
            self._refresh_display()

    def _refresh_display(self) -> None:
        self._refresh_current_system_display()
        self._refresh_report_window()

    # --- views -----------------------------------------------------------

    def _views(self) -> List[PeriodView]:
        """The live period first, then archived ones (newest first)."""
        return [self._ledger.view(current=True)] + [bgs_ledger.view_from_archive(r) for r in self._archive]

    def _refresh_report_window(self) -> None:
        bgs_window.refresh_if_open(self._views(), self._ledger.current_system, self._pinned, self._hidden)

    def _on_view_report(self) -> None:
        if self._parent is None:
            return
        bgs_window.show(
            self._parent, self._views(), self._ledger.current_system, self._pinned, self._hidden,
            bgs_window.TabActions(self._toggle_pin, self._close_tab, self._add_system),
        )

    @staticmethod
    def _load_names(raw: Any) -> List[str]:
        return [str(n) for n in raw if n] if isinstance(raw, list) else []

    @staticmethod
    def _without(names: List[str], system: str) -> List[str]:
        return [n for n in names if n.casefold() != system.casefold()]

    def _toggle_pin(self, system: str) -> None:
        """Pin a system's tab so it always shows, or unpin it."""
        if bgs_format.is_pinned(system, self._pinned):
            self._pinned = self._without(self._pinned, system)
        else:
            self._pinned.append(system)
            self._hidden = self._without(self._hidden, system)
        self._after_tab_change()

    def _close_tab(self, system: str) -> None:
        """Hide a system's tab (unpinning it too)."""
        self._pinned = self._without(self._pinned, system)
        if not bgs_format.is_pinned(system, self._hidden):
            self._hidden.append(system)
        self._after_tab_change()

    def _add_system(self, name: str) -> None:
        """Show a system by name: pins it (so it stays) and un-hides it."""
        known = {n.casefold(): n for view in self._views() for n in view.systems()}
        system = known.get(name.casefold(), name)
        self._hidden = self._without(self._hidden, system)
        if not bgs_format.is_pinned(system, self._pinned):
            self._pinned.append(system)
        self._after_tab_change()

    def _after_tab_change(self) -> None:
        self._persist()
        self._refresh_display()

    # --- tick handling + journal replay ----------------------------------

    def _ensure_tick_polling(self, parent: tk.Misc) -> None:
        """Starts the self-rescheduling tick-check loop the first time the
        panel is built - a no-op on any later call (build_panel() only ever
        runs once per EDMC session in practice, but this guard makes that
        assumption non-load-bearing)."""
        if self._tick_poll_started:
            return
        self._tick_poll_started = True
        parent.after(_TICK_QUEUE_POLL_MS, self._poll_queues)
        parent.after(_TICK_FIRST_CHECK_DELAY_MS, self._schedule_tick_check)

    def _schedule_tick_check(self) -> None:
        if self._parent is None:
            return
        if tick_enabled():
            self._start_tick_check()
        self._parent.after(_TICK_POLL_INTERVAL_MS, self._schedule_tick_check)

    def _start_tick_check(self) -> None:
        self._tick_generation += 1
        generation = self._tick_generation
        threading.Thread(target=self._tick_worker, args=(generation,), daemon=True).start()

    def _tick_worker(self, generation: int) -> None:
        """Runs off the main thread - must never touch a Tk widget
        directly, same rule as canonn_poi_panel.py's own `_worker`."""
        try:
            tick_dt = bgs_tick_client.fetch_latest_tick()
        except Exception as exc:  # a third-party community service - any failure is just "unknown for now"
            self._tick_queue.put((generation, None, str(exc)))
        else:
            self._tick_queue.put((generation, tick_dt.isoformat(), None))

    def _poll_queues(self) -> None:
        """Runs on the main thread via after() - safe to touch widgets
        here, same split as canonn_poi_panel.py's own `_poll_queue`."""
        try:
            generation, tick_iso, error = self._tick_queue.get_nowait()
        except queue.Empty:
            pass
        else:
            if generation == self._tick_generation:  # discard a stale in-flight result
                self._handle_tick_result(tick_iso, error)
        try:
            generation, cmdr, replayed, seen = self._backfill_queue.get_nowait()
        except queue.Empty:
            pass
        else:
            self._finish_backfill(generation, cmdr, replayed, seen)
        if self._parent is not None:
            self._parent.after(_TICK_QUEUE_POLL_MS, self._poll_queues)

    def _handle_tick_result(self, tick_iso: Optional[str], error: Optional[str]) -> None:
        if error is not None:
            logger.debug("BGS tick check failed (will retry): %s", error)
            self._set_tick_status(f"Tick check failed (will retry): {bgs_format.clip(error, 60)}")
            return
        self._tick_current = tick_iso
        self._set_tick_status(f"Last tick: {bgs_format.when_text(tick_iso)}")
        self._reconcile_tick()

    def _reconcile_tick(self) -> None:
        """Bring the ledger in line with the newest known tick, once both a
        commander and a tick time are known: close the stored period if a
        newer tick has happened since (it may have, while EDMC was closed),
        then rebuild the current period from the journals."""
        if self._cmdr is None or self._tick_current is None or not enabled():
            return
        newest = bgs_ledger.parse_timestamp(self._tick_current)
        stored = bgs_ledger.parse_timestamp(self._ledger.tick_start)
        if newest is None:
            return
        if stored is not None and newest > stored:
            self._roll_period(self._tick_current)
        elif stored is None:
            self._ledger.set_tick_start(self._tick_current)
            self._persist()
        self._start_backfill()

    def _roll_period(self, new_tick_iso: str) -> None:
        logger.info("BGS tick detected (%s) - archiving the closed period", new_tick_iso)
        record = self._ledger.roll(new_tick_iso)
        if record is not None:
            self._archive.insert(0, record)
        now = datetime.now(timezone.utc)
        self._archive = bgs_ledger.prune_archive(self._archive, now, archive_days())
        self._ledger.prune_tracks(now, archive_days())
        self._backfill_done_for = None  # the new period must be rebuilt from the journals too
        self._persist()
        self._refresh_display()
        self._set_tick_status(
            f"New tick at {bgs_format.when_text(new_tick_iso)} — totals reset, previous tick archived.")

    def _start_backfill(self) -> None:
        if self._backfill_running or self._cmdr is None or not self._tick_current or not self._ledger.tick_start:
            return
        if self._backfill_done_for == (self._cmdr, self._ledger.tick_start):
            return
        self._backfill_running = True
        self._live_buffer = []
        self._backfill_generation += 1
        threading.Thread(
            target=self._backfill_worker,
            args=(self._backfill_generation, self._cmdr, self._ledger.tick_start, dict(self._ledger.open_missions)),
            daemon=True,
        ).start()

    def _backfill_worker(
        self, generation: int, cmdr: str, tick_start: str, open_missions: Dict[str, Tuple[str, str]],
    ) -> None:
        """Off the main thread: replay the journals into a fresh ledger."""
        try:
            events = bgs_journal.read_events(cmdr, tick_start)
            replayed = bgs_ledger.rebuild(events, tick_start, open_missions) if events else None
            seen = {bgs_ledger.fingerprint(e) for e in events}
        except Exception:  # never let a journal quirk take the thread (or plugin) down
            logger.exception("BGS journal replay failed")
            replayed, seen = None, set()
        self._backfill_queue.put((generation, cmdr, replayed, seen))

    def _finish_backfill(self, generation: int, cmdr: str, replayed: Optional[TickLedger], seen: set) -> None:
        self._backfill_running = False
        buffered, self._live_buffer = self._live_buffer, []
        if generation != self._backfill_generation or cmdr != self._cmdr or replayed is None:
            return  # stale (commander switched) or nothing to replay - keep the live ledger
        if replayed.tick_start != self._ledger.tick_start:
            return  # a tick rolled meanwhile; the next reconcile redoes it
        for entry in buffered:
            if bgs_ledger.fingerprint(entry) not in seen:
                replayed.process(entry)
        self._ledger = replayed
        self._backfill_done_for = (cmdr, replayed.tick_start or "")
        logger.info("BGS journal replay done for %s: %d faction(s) with activity", cmdr, len(replayed.activity))
        self._persist()
        self._refresh_display()

    def _set_tick_status(self, text: str) -> None:
        self._tick_status_text = text
        if self._tick_status_var is not None:
            self._tick_status_var.set(text)

    # --- main-panel widgets -----------------------------------------------

    def build_panel(self, parent: tk.Frame) -> None:
        self._parent = parent
        tk.Label(parent, text="BGS", font=panelkit.bold_font(parent)).grid(
            row=0, column=0, columnspan=3, sticky=tk.W,
        )

        self._current_system_var = tk.StringVar(value=self._current_system_text())
        panelkit.wrap_label(parent, textvariable=self._current_system_var, anchor="w").grid(
            row=1, column=0, columnspan=3, sticky=tk.W, pady=(2, 0),
        )

        self._tick_status_var = tk.StringVar(value=self._tick_status_text)
        panelkit.wrap_label(parent, textvariable=self._tick_status_var, anchor="w", fg="grey").grid(
            row=2, column=0, columnspan=3, sticky=tk.W, pady=(2, 0),
        )

        button_row = tk.Frame(parent)
        button_row.grid(row=3, column=0, columnspan=3, sticky=tk.W, pady=(4, 0))
        report_button = tk.Button(button_row, text="RPT", command=self._on_view_report)
        report_button.grid(row=0, column=0)
        panelkit.add_tooltip(report_button, "View BGS Report - open the BGS report window")

        self._ensure_tick_polling(parent)

    def _current_system_text(self) -> str:
        """Only the system the commander is in: each faction's state and
        influence (with the change since the tick) and what they've done to
        it this tick. Everything else lives in the report window."""
        if not enabled():
            return _DISABLED_TEXT
        ledger = self._ledger
        if not ledger.current_system:
            return "Current system: (unknown — jump somewhere first)"
        star = "★ " if bgs_format.is_pinned(ledger.current_system, self._pinned) else ""
        header = star + bgs_format.clip(ledger.current_system, 40)
        factions = ledger.current_system_factions
        if factions is None:
            return f"{header} — waiting on faction data..."
        if not factions:
            return f"{header} — no factions present (uninhabited system)."

        activity = {a.faction.casefold(): a for a in ledger.activity.values()
                    if a.system.casefold() == ledger.current_system.casefold()}
        lines = [f"{header} — {len(factions)} faction(s):"]
        ordered = sorted(factions, key=lambda s: (not s.is_controlling, s.faction.casefold()))
        for snap in ordered[:MAX_FACTIONS_SHOWN]:
            track = ledger.tracks.get(snapshot_key(ledger.current_system, snap.faction))
            marker = "★ " if snap.is_controlling else "   "
            if track is not None:
                parts = [bgs_format.state_change_text(track), bgs_format.influence_change_text(track)]
            else:
                parts = [snap.faction_state or "None", bgs_format.influence_text(snap)]
            lines.append(f"{marker}{bgs_format.clip(snap.faction)} — {', '.join(p for p in parts if p)}")
            act = activity.get(snap.faction.casefold())
            if act is not None and not act.is_empty():
                lines.append(f"      ↳ {'; '.join(bgs_format.activity_bits(act))}")
        if len(ordered) > MAX_FACTIONS_SHOWN:
            lines.append(f"   …and {len(ordered) - MAX_FACTIONS_SHOWN} more")
        if not activity:
            lines.append("Nothing done here yet this tick.")
        return "\n".join(lines)

    def _refresh_current_system_display(self) -> None:
        if self._current_system_var is not None:
            self._current_system_var.set(self._current_system_text())

    # --- Settings tab --------------------------------------------------

    def build_settings(self, notebook: nb.Notebook) -> None:
        frame = nb.Frame(notebook)
        frame.columnconfigure(0, weight=1)
        frame.columnconfigure(1, weight=1)
        notebook.add(frame, text="BGS")

        self._enabled_var = tk.BooleanVar(value=enabled())
        self._tick_enabled_var = tk.BooleanVar(value=tick_enabled())
        self._archive_days_var = tk.StringVar(value=str(archive_days()))

        nb.Label(frame, text="BGS Tracking", font=("TkDefaultFont", 9, "bold")).grid(
            row=0, column=0, columnspan=2, sticky=tk.W, padx=10, pady=(10, 4),
        )
        nb.Label(
            frame, text=panelkit.WORK_IN_PROGRESS_NOTE, wraplength=440, justify=tk.LEFT, foreground="#c07000",
        ).grid(row=99, column=0, columnspan=2, sticky=tk.W, padx=10, pady=(14, 10))
        nb.Label(
            frame,
            text=(
                "The BGS panel shows the system you're in: each faction's state and influence, "
                "and what you've done to it since the last server tick - missions (done, failed, "
                "abandoned) with their +/- INF, bounty and combat-bond vouchers, trade, "
                "exploration data and crimes. The BGS Report window has a tab for every system "
                "you've acted in this tick, plus earlier ticks. Totals reset at each tick and "
                "are rebuilt from your recent journals when EDMC starts. Mission INF is a +/- "
                "pip count, not a percentage - Frontier doesn't expose one. See "
                "docs/BGS_TECH_SPEC.md for specifics."
            ),
            wraplength=440, justify=tk.LEFT,
        ).grid(row=1, column=0, columnspan=2, sticky=tk.W, padx=10, pady=(0, 6))
        nb.Checkbutton(
            frame, text="Show BGS faction states and activity", variable=self._enabled_var,
        ).grid(row=2, column=0, columnspan=2, sticky=tk.W, padx=10, pady=(0, 4))
        nb.Checkbutton(
            frame, text="Detect BGS ticks (polls tick.infomancer.uk every 60s)",
            variable=self._tick_enabled_var,
        ).grid(row=3, column=0, columnspan=2, sticky=tk.W, padx=10, pady=(0, 4))
        nb.Label(
            frame,
            text=(
                "Tick detection is the only network call this mode makes - a community-run, "
                "third-party service (not Frontier's own). It is what resets the totals each "
                "tick and tells WNTB which journal entries to replay. Turn it off to keep this "
                "mode fully local; the totals then just keep accumulating without ever "
                "resetting on their own."
            ),
            wraplength=440, justify=tk.LEFT, foreground="grey",
        ).grid(row=4, column=0, columnspan=2, sticky=tk.W, padx=10, pady=(0, 8))

        if platform_support.IS_LINUX:
            # Rebuilding the tick's totals needs EDMC's Journal directory, which has no default on Linux.
            advice = platform_support.journal_dir_advice(config.get_str("journaldir") or "")
            if advice:
                nb.Label(frame, text=advice, wraplength=440, justify=tk.LEFT, foreground="#c07000").grid(
                    row=6, column=0, columnspan=2, sticky=tk.W, padx=10, pady=(0, 8))

        archive_row = nb.Frame(frame)
        archive_row.grid(row=5, column=0, columnspan=2, sticky=tk.W, padx=10, pady=(0, 4))
        nb.Label(archive_row, text="Keep previous ticks for").grid(row=0, column=0)
        tk.Spinbox(
            archive_row, from_=1, to=MAX_ARCHIVE_DAYS, width=4, textvariable=self._archive_days_var,
        ).grid(row=0, column=1, padx=6)
        nb.Label(archive_row, text=f"days (1-{MAX_ARCHIVE_DAYS})").grid(row=0, column=2)

    def save_settings(self) -> None:
        if self._enabled_var is None:
            return
        config.set(_CFG_ENABLED, self._enabled_var.get())
        if self._tick_enabled_var is not None:
            config.set(_CFG_TICK_ENABLED, self._tick_enabled_var.get())
        if self._archive_days_var is not None:
            try:
                days = int(self._archive_days_var.get())
            except ValueError:
                days = DEFAULT_ARCHIVE_DAYS
            config.set(_CFG_ARCHIVE_DAYS, str(max(1, min(MAX_ARCHIVE_DAYS, days))))
        self._archive = bgs_ledger.prune_archive(self._archive, datetime.now(timezone.utc), archive_days())
        self._persist()
        self._refresh_display()
        self._reconcile_tick()


controller = BgsController()


def start(plugin_dir: str) -> None:
    controller.start(plugin_dir)


def stop() -> None:
    controller.stop()


def handle_event(entry: Dict[str, Any], cmdr: str, system: Optional[str], station: Optional[str], state: Dict[str, Any]) -> None:
    controller.handle_event(entry, cmdr, system, station, state)


def build_panel(parent: tk.Frame) -> None:
    controller.build_panel(parent)


def build_settings(notebook: nb.Notebook) -> None:
    controller.build_settings(notebook)


def save_settings() -> None:
    controller.save_settings()
