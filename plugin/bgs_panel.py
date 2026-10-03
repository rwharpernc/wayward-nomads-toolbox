"""BGS (Background Simulation) tracking — a new mode (PANEL_PLACEMENT =
"bgs"), its own top-level main-panel mode alongside Powerplay/Exploration/
Mining/Missions/Field Ops (see ui.py's PANEL_MODES).

All four phases from docs/BGS_TECH_SPEC.md are implemented here:

- Phase 1: faction-state snapshots (War/Election/Boom/Bust/etc.) - see
  bgs_tracker.py's FactionSnapshot/parse_faction_entry.
- Phase 2: mission INF and bounty/combat-bond voucher tallying - see
  bgs_tracker.py's FactionActivity/parse_mission_faction_effects/
  parse_bounty_voucher/parse_combat_bond.
- Phase 3: BGS-tick detection (bgs_tick_client.py, polled every 60s off the
  main thread via the queue.Queue/generation-counter/threading.Thread/
  after()-poll pattern already established by canonn_poi_panel.py/
  boxel_survey.py) - rolls the activity tally into a new period whenever a
  new tick is detected.
- Phase 4: trade profit/loss and exploration-data-sold tallying, attributed
  to the current station's controlling faction (captured on `Docked`).

Deliberately scoped to systems/factions the commander explicitly tracks,
never "everything, everywhere" - a commander configures which systems and/or faction names
matter to them, in this mode's Settings tab or via the panel's own
Track/Untrack buttons, and only those get shown or persisted.

Per-commander state (tracked systems/factions, faction snapshots, activity
tally, last-known tick) is persisted via bgs_state.py - restored on cmdr
switch/plugin start and re-saved after every state-changing journal event,
same save-cadence/lifecycle convention as organic_scan_panel.py's own
per-body persistence.
"""

from __future__ import annotations

import logging
import os
import queue
import threading
from dataclasses import asdict
from typing import Any, Dict, List, Optional, Tuple

import tkinter as tk

import myNotebook as nb
from config import appname, config
from theme import theme

from . import bgs_state, bgs_tick_client, bgs_tracker, bgs_window, panelkit, platform_support
from .bgs_tracker import FactionActivity, FactionSnapshot

plugin_name = os.path.basename(os.path.dirname(__file__))
logger = logging.getLogger(f"{appname}.{plugin_name}")

PANEL_PLACEMENT = "bgs"

_CFG_ENABLED = "wntb_bgs_enabled"
_CFG_TICK_ENABLED = "wntb_bgs_tick_enabled"

_DISABLED_TEXT = "BGS tracking is disabled — see Settings."
_NO_CONFIG_TEXT = "BGS: no tracked systems/factions configured — see Settings."
_NO_DATA_TEXT = "BGS: tracking {count} faction(s) — waiting on data (fly through a tracked system)."

_TICK_POLL_INTERVAL_MS = 60_000  # once a minute is plenty for a tick that moves daily
_TICK_FIRST_CHECK_DELAY_MS = 3_000  # let Tk/EDMC settle before the first network call
_TICK_QUEUE_POLL_MS = 300


def enabled() -> bool:
    # On by default - pure journal parsing, no network calls, same
    # reasoning as organic_scan_panel.py's own default.
    return config.get_bool(_CFG_ENABLED, default=True)


def tick_enabled() -> bool:
    """Gates the one network call this mode makes (Phase 3's tick-time
    poll) - separate from `enabled()` so a commander can keep faction-
    state/activity tracking fully local if they'd rather not have WNTB
    talk to a third-party community service at all. On by default per the
    scoping decision behind this feature ("detect ticks")."""
    return config.get_bool(_CFG_TICK_ENABLED, default=True)


class BgsController:
    def __init__(self) -> None:
        self._plugin_dir: Optional[str] = None
        self._cmdr: Optional[str] = None

        self._tracked_systems: List[str] = []
        self._tracked_factions: List[str] = []
        self._snapshots: Dict[str, FactionSnapshot] = {}
        self._current_system: Optional[str] = None
        self._current_system_factions: Optional[List[FactionSnapshot]] = None
        """Every faction present in `_current_system` right now (from the
        most recent FSDJump/Location/CarrierJump event's own `Factions[]`
        array) - unlike `_snapshots`, this is unconditional on tracking and
        never persisted; it's purely "what does this system look like right
        now", reset to None (unknown) on every system change until a fresh
        event repopulates it. None means "no data yet"; an empty list means
        "confirmed uninhabited - zero factions"."""

        self._current_station_faction: Optional[str] = None
        """The controlling faction of whichever station the commander is
        currently docked at, from `Docked`'s own `StationFaction` - used to
        attribute trade profit/loss and exploration-data-sale credit
        (Phase 4), since those events don't carry a faction name of their
        own. Cleared on `Undocked`."""

        self._activity: Dict[str, FactionActivity] = {}
        """This tick period's tally (Phase 2/4) - reset into
        `_previous_activity` whenever a new BGS tick is detected."""
        self._previous_activity: Dict[str, FactionActivity] = {}
        self._tick_last_seen: Optional[str] = None  # ISO timestamp of the last-known galaxy tick

        self._tick_queue: "queue.Queue[Tuple[int, Optional[str], Optional[str]]]" = queue.Queue()
        self._tick_generation = 0
        self._tick_poll_started = False
        self._tick_status_text = "Tick check: not yet run."

        self._parent: Optional[tk.Frame] = None
        self._summary_var: Optional[tk.StringVar] = None
        self._current_system_var: Optional[tk.StringVar] = None
        self._activity_var: Optional[tk.StringVar] = None
        self._tick_status_var: Optional[tk.StringVar] = None
        self._enabled_var: Optional[tk.BooleanVar] = None
        self._tick_enabled_var: Optional[tk.BooleanVar] = None
        self._systems_listbox: Optional[tk.Listbox] = None
        self._factions_listbox: Optional[tk.Listbox] = None
        self._systems_entry: Optional[tk.Entry] = None
        self._factions_entry: Optional[tk.Entry] = None

    # --- lifecycle / persistence -----------------------------------------

    def start(self, plugin_dir: str) -> None:
        self._plugin_dir = plugin_dir
        # Tracked lists/snapshots are per-commander and EDMC doesn't know
        # which commander is active until the first journal event - actual
        # restore happens in _switch_cmdr(), called from handle_event().

    def stop(self) -> None:
        self._persist()

    def _switch_cmdr(self, cmdr: str) -> None:
        """Called whenever the active commander changes, including the
        first journal event of a session - saves the previous commander's
        BGS state (if one was loaded) and loads this commander's own, so
        two commanders on the same install never share or overwrite one
        commander's tracked factions/systems."""
        self._persist()
        self._cmdr = cmdr
        saved = bgs_state.load_state(self._plugin_dir, cmdr) if self._plugin_dir else None
        data = saved if isinstance(saved, dict) else bgs_state.default_state()
        self._tracked_systems = list(data.get("tracked_systems") or [])
        self._tracked_factions = list(data.get("tracked_factions") or [])
        self._snapshots = self._load_snapshot_dict(data.get("snapshots"))
        self._activity = self._load_activity_dict(data.get("activity"))
        self._previous_activity = self._load_activity_dict(data.get("previous_activity"))
        self._tick_last_seen = (data.get("tick") or {}).get("last_seen_at")
        if saved:
            logger.info("Restored BGS state for %s: %d tracked, %d snapshots, %d active",
                        cmdr, len(self._tracked_systems) + len(self._tracked_factions),
                        len(self._snapshots), len(self._activity))
        self._refresh_settings_lists()
        self._refresh_summary()

    @staticmethod
    def _load_snapshot_dict(raw: Any) -> Dict[str, FactionSnapshot]:
        result: Dict[str, FactionSnapshot] = {}
        for key, value in (raw or {}).items():
            try:
                result[key] = FactionSnapshot(**value)
            except TypeError:
                logger.warning("Discarding stale/incompatible saved BGS snapshot for key %r", key)
        return result

    @staticmethod
    def _load_activity_dict(raw: Any) -> Dict[str, FactionActivity]:
        result: Dict[str, FactionActivity] = {}
        for key, value in (raw or {}).items():
            try:
                result[key] = FactionActivity(**value)
            except TypeError:
                logger.warning("Discarding stale/incompatible saved BGS activity for key %r", key)
        return result

    def _persist(self) -> None:
        if self._plugin_dir is None or self._cmdr is None:
            return
        data = {
            "tracked_systems": self._tracked_systems,
            "tracked_factions": self._tracked_factions,
            "snapshots": {key: asdict(snap) for key, snap in self._snapshots.items()},
            "activity": {key: asdict(act) for key, act in self._activity.items()},
            "previous_activity": {key: asdict(act) for key, act in self._previous_activity.items()},
            "tick": {"last_seen_at": self._tick_last_seen},
        }
        bgs_state.save_state(self._plugin_dir, self._cmdr, data)

    # --- journal dispatch -----------------------------------------------

    def handle_event(self, entry: Dict[str, Any], cmdr: str, system: Optional[str], station: Optional[str], state: Dict[str, Any]) -> None:
        if cmdr and cmdr != self._cmdr:
            self._switch_cmdr(cmdr)

        if not enabled():
            return

        event = entry.get("event", "")
        if event in ("FSDJump", "Location", "CarrierJump"):
            star_system = entry.get("StarSystem") or system
            if star_system and star_system != self._current_system:
                self._current_system = star_system
                self._current_system_factions = None  # unknown until this event's own Factions[] is parsed below
            self._handle_faction_data(entry, star_system)
        elif event == "Docked":
            self._current_station_faction = (entry.get("StationFaction") or {}).get("Name")
        elif event == "Undocked":
            self._current_station_faction = None
        elif event == "MissionCompleted":
            self._handle_mission_completed(entry, system)
        elif event == "RedeemVoucher":
            self._handle_redeem_voucher(entry, system)
        elif event == "MarketBuy":
            self._handle_market_buy(entry, system)
        elif event == "MarketSell":
            self._handle_market_sell(entry, system)
        elif event in ("SellExplorationData", "MultiSellExplorationData"):
            self._handle_exploration_sale(entry, system)

    def _handle_faction_data(self, entry: Dict[str, Any], star_system: Optional[str]) -> None:
        factions = entry.get("Factions")
        if not star_system or not isinstance(factions, list):
            return
        controlling_name = (entry.get("SystemFaction") or {}).get("Name")
        timestamp = entry.get("timestamp", "")

        # Every faction present is captured for the live "what's in this
        # system right now" panel display below, regardless of whether it's
        # tracked - only the tracked subset also gets persisted into
        # self._snapshots (bgs_state.json / the report window), same
        # "observe everything, persist only what's configured" split as
        # organic_scan_panel.py's own current-body-vs-persisted state.
        current_factions: List[FactionSnapshot] = []
        changed = False
        for faction_entry in factions:
            if not isinstance(faction_entry, dict):
                continue
            name = faction_entry.get("Name")
            if not name:
                continue
            snapshot = bgs_tracker.parse_faction_entry(
                star_system, faction_entry, name == controlling_name, timestamp,
            )
            if snapshot is None:
                continue
            current_factions.append(snapshot)
            if bgs_tracker.is_tracked(star_system, name, self._tracked_systems, self._tracked_factions):
                self._snapshots[bgs_tracker.snapshot_key(star_system, name)] = snapshot
                changed = True

        self._current_system_factions = current_factions
        self._refresh_current_system_display()

        if changed:
            self._persist()
            self._refresh_summary()
            self._refresh_report_window()

    # --- Phase 2/4: activity tally ---------------------------------------

    def _get_activity(self, system: str, faction: str) -> FactionActivity:
        key = bgs_tracker.snapshot_key(system, faction)
        return self._activity.setdefault(key, FactionActivity(system=system, faction=faction))

    def _handle_mission_completed(self, entry: Dict[str, Any], system: Optional[str]) -> None:
        if not enabled() or not system:
            return
        changed = False
        for faction, plus, minus in bgs_tracker.parse_mission_faction_effects(entry):
            if not bgs_tracker.is_tracked(system, faction, self._tracked_systems, self._tracked_factions):
                continue
            activity = self._get_activity(system, faction)
            activity.missions += 1
            activity.inf_plus += plus
            activity.inf_minus += minus
            changed = True
        if changed:
            self._after_activity_change()

    def _handle_redeem_voucher(self, entry: Dict[str, Any], system: Optional[str]) -> None:
        if not enabled() or not system:
            return
        changed = False
        for faction, amount in bgs_tracker.parse_bounty_voucher(entry):
            if not bgs_tracker.is_tracked(system, faction, self._tracked_systems, self._tracked_factions):
                continue
            self._get_activity(system, faction).bounty_credits += amount
            changed = True
        combat_bond = bgs_tracker.parse_combat_bond(entry)
        if combat_bond is not None:
            faction, amount = combat_bond
            if bgs_tracker.is_tracked(system, faction, self._tracked_systems, self._tracked_factions):
                self._get_activity(system, faction).combat_bond_credits += amount
                changed = True
        if changed:
            self._after_activity_change()

    def _handle_market_buy(self, entry: Dict[str, Any], system: Optional[str]) -> None:
        if not enabled() or not system or not self._current_station_faction:
            return
        if not bgs_tracker.is_tracked(
            system, self._current_station_faction, self._tracked_systems, self._tracked_factions,
        ):
            return
        cost = bgs_tracker.market_buy_cost(entry)
        if cost is None:
            return
        activity = self._get_activity(system, self._current_station_faction)
        activity.trade_buy_credits += cost
        activity.trade_profit_credits -= cost
        self._after_activity_change()

    def _handle_market_sell(self, entry: Dict[str, Any], system: Optional[str]) -> None:
        if not enabled() or not system or not self._current_station_faction:
            return
        if not bgs_tracker.is_tracked(
            system, self._current_station_faction, self._tracked_systems, self._tracked_factions,
        ):
            return
        proceeds = bgs_tracker.market_sell_proceeds(entry)
        if proceeds is None:
            return
        activity = self._get_activity(system, self._current_station_faction)
        activity.trade_sell_credits += proceeds
        activity.trade_profit_credits += proceeds
        self._after_activity_change()

    def _handle_exploration_sale(self, entry: Dict[str, Any], system: Optional[str]) -> None:
        if not enabled() or not system or not self._current_station_faction:
            return
        if not bgs_tracker.is_tracked(
            system, self._current_station_faction, self._tracked_systems, self._tracked_factions,
        ):
            return
        value = bgs_tracker.exploration_sale_value(entry)
        if value is None:
            return
        self._get_activity(system, self._current_station_faction).exploration_credits += value
        self._after_activity_change()

    def _after_activity_change(self) -> None:
        self._persist()
        self._refresh_summary()
        self._refresh_report_window()

    def _refresh_report_window(self) -> None:
        bgs_window.refresh_if_open(
            list(self._snapshots.values()), list(self._activity.values()), list(self._previous_activity.values()),
        )

    # --- Phase 3: BGS-tick detection --------------------------------------

    def _ensure_tick_polling(self, parent: tk.Misc) -> None:
        """Starts the self-rescheduling tick-check loop the first time the
        panel is built - a no-op on any later call (build_panel() only ever
        runs once per EDMC session in practice, but this guard makes that
        assumption non-load-bearing)."""
        if self._tick_poll_started:
            return
        self._tick_poll_started = True
        parent.after(_TICK_QUEUE_POLL_MS, self._poll_tick_queue)
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

    def _poll_tick_queue(self) -> None:
        """Runs on the main thread via after() - safe to touch widgets
        here, same split as canonn_poi_panel.py's own `_poll_queue`."""
        try:
            generation, tick_iso, error = self._tick_queue.get_nowait()
        except queue.Empty:
            pass
        else:
            if generation == self._tick_generation:  # discard a stale in-flight result
                self._handle_tick_result(tick_iso, error)
        if self._parent is not None:
            self._parent.after(_TICK_QUEUE_POLL_MS, self._poll_tick_queue)

    def _handle_tick_result(self, tick_iso: Optional[str], error: Optional[str]) -> None:
        if error is not None:
            logger.debug("BGS tick check failed (will retry): %s", error)
            self._set_tick_status(f"Tick check failed (will retry): {error}")
            return
        self._set_tick_status(f"Last tick check succeeded — current tick: {tick_iso}")
        if self._tick_last_seen is None:
            # First-ever successful check this install - establishes the
            # baseline, not itself a "new tick" (there's nothing to roll
            # over yet).
            self._tick_last_seen = tick_iso
            self._persist()
            return
        if tick_iso != self._tick_last_seen:
            self._roll_tick_period(tick_iso)

    def _roll_tick_period(self, new_tick_iso: str) -> None:
        logger.info("BGS tick detected (%s) - rolling activity tally into previous period", new_tick_iso)
        self._previous_activity = self._activity
        self._activity = {}
        self._tick_last_seen = new_tick_iso
        self._persist()
        self._refresh_summary()
        self._refresh_report_window()
        self._set_tick_status(f"New tick detected at {new_tick_iso} — tally rolled over.")

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

        self._summary_var = tk.StringVar(value=self._summary_text())
        panelkit.wrap_label(parent, textvariable=self._summary_var, anchor="w").grid(
            row=1, column=0, columnspan=3, sticky=tk.W, pady=(2, 0),
        )

        self._current_system_var = tk.StringVar(value=self._current_system_text())
        panelkit.wrap_label(parent, textvariable=self._current_system_var, anchor="w").grid(
            row=2, column=0, columnspan=3, sticky=tk.W, pady=(4, 0),
        )

        self._activity_var = tk.StringVar(value=self._activity_summary_text())
        panelkit.wrap_label(parent, textvariable=self._activity_var, anchor="w").grid(
            row=3, column=0, columnspan=3, sticky=tk.W, pady=(4, 0),
        )

        self._tick_status_var = tk.StringVar(value=self._tick_status_text)
        panelkit.wrap_label(parent, textvariable=self._tick_status_var, anchor="w", fg="grey").grid(
            row=4, column=0, columnspan=3, sticky=tk.W, pady=(2, 0),
        )

        button_row = tk.Frame(parent)
        button_row.grid(row=5, column=0, columnspan=3, sticky=tk.W, pady=(4, 0))
        tk.Button(button_row, text="Track", command=self._on_track_current).grid(row=0, column=0)
        tk.Button(button_row, text="Untrack", command=self._on_untrack_current).grid(row=0, column=1, padx=(4, 0))
        tk.Button(button_row, text="View BGS Report", command=self._on_view_report).grid(row=0, column=2, padx=(10, 0))

        self._ensure_tick_polling(parent)

    def _summary_text(self) -> str:
        if not enabled():
            return _DISABLED_TEXT
        tracked_count = len(self._tracked_systems) + len(self._tracked_factions)
        if tracked_count == 0:
            return _NO_CONFIG_TEXT
        if not self._snapshots:
            return _NO_DATA_TEXT.format(count=tracked_count)
        states = ", ".join(
            f"{snap.faction} ({snap.faction_state or 'None'})"
            for snap in sorted(self._snapshots.values(), key=lambda s: (s.system, s.faction))
        )
        return f"BGS ({len(self._snapshots)} faction(s) tracked): {states}"

    def _refresh_summary(self) -> None:
        if self._summary_var is not None:
            self._summary_var.set(self._summary_text())
        if self._activity_var is not None:
            self._activity_var.set(self._activity_summary_text())

    def _activity_summary_text(self) -> str:
        if not enabled():
            return ""
        active = [a for a in self._activity.values() if not a.is_empty()]
        if not active:
            return "Activity (since last tick): none yet."
        parts = []
        for act in sorted(active, key=lambda a: (a.system, a.faction)):
            bits = []
            if act.missions:
                bits.append(f"{act.missions} mission(s), INF +{act.inf_plus}/-{act.inf_minus}")
            if act.bounty_credits:
                bits.append(f"{act.bounty_credits:,}cr bounties")
            if act.combat_bond_credits:
                bits.append(f"{act.combat_bond_credits:,}cr bonds")
            if act.trade_profit_credits:
                bits.append(f"{act.trade_profit_credits:,}cr trade")
            if act.exploration_credits:
                bits.append(f"{act.exploration_credits:,}cr exploration")
            parts.append(f"{act.faction}: {', '.join(bits)}")
        return "Activity (since last tick):\n" + "\n".join(parts)

    def _is_current_system_tracked(self) -> bool:
        if not self._current_system:
            return False
        return any(self._current_system.casefold() == s.casefold() for s in self._tracked_systems)

    def _current_system_text(self) -> str:
        if not self._current_system:
            return "Current system: (unknown — jump somewhere first)"
        header = f"Current system: {self._current_system}"
        tracked_status = "tracked" if self._is_current_system_tracked() else "not tracked"

        if self._current_system_factions is None:
            return f"{header} — waiting on faction data..."
        if not self._current_system_factions:
            return f"{header} — no factions present (uninhabited system)."

        lines = [f"{header} — {len(self._current_system_factions)} faction(s) present ({tracked_status}):"]
        for snap in sorted(
            self._current_system_factions, key=lambda s: (not s.is_controlling, s.faction.casefold()),
        ):
            marker = "★ " if snap.is_controlling else "   "
            lines.append(f"{marker}{snap.faction} — {snap.faction_state or 'None'}")
        return "\n".join(lines)

    def _refresh_current_system_display(self) -> None:
        if self._current_system_var is not None:
            self._current_system_var.set(self._current_system_text())

    def _on_track_current(self) -> None:
        """Adds the current system to Tracked Systems - the main-panel
        shortcut for what Settings → BGS's own Add button does, so
        tracking a system the commander is actually sitting in doesn't
        require alt-tabbing to Settings and retyping its name. No limit on
        how many systems can be tracked this way."""
        if not self._current_system or self._is_current_system_tracked():
            return
        self._tracked_systems.append(self._current_system)
        self._persist()
        self._refresh_settings_lists()
        self._refresh_current_system_display()
        self._refresh_summary()

    def _on_untrack_current(self) -> None:
        if not self._current_system or not self._is_current_system_tracked():
            return
        self._tracked_systems = [
            s for s in self._tracked_systems if s.casefold() != self._current_system.casefold()
        ]
        self._prune_untracked_data()
        self._persist()
        self._refresh_settings_lists()
        self._refresh_current_system_display()
        self._refresh_summary()
        self._refresh_report_window()

    def _prune_untracked_data(self) -> None:
        """Drops any saved snapshot/activity that no longer matches either
        tracked list - called whenever a system/faction is removed from
        tracking, so stale data doesn't keep showing in the panel/report
        just because it was already cached."""
        self._snapshots = {
            key: snap for key, snap in self._snapshots.items()
            if bgs_tracker.is_tracked(snap.system, snap.faction, self._tracked_systems, self._tracked_factions)
        }
        self._activity = {
            key: act for key, act in self._activity.items()
            if bgs_tracker.is_tracked(act.system, act.faction, self._tracked_systems, self._tracked_factions)
        }
        self._previous_activity = {
            key: act for key, act in self._previous_activity.items()
            if bgs_tracker.is_tracked(act.system, act.faction, self._tracked_systems, self._tracked_factions)
        }

    def _on_view_report(self) -> None:
        if self._parent is None:
            return
        bgs_window.show(
            self._parent, list(self._snapshots.values()), list(self._activity.values()),
            list(self._previous_activity.values()),
        )

    # --- Settings tab --------------------------------------------------

    def build_settings(self, notebook: nb.Notebook) -> None:
        frame = nb.Frame(notebook)
        frame.columnconfigure(0, weight=1)
        frame.columnconfigure(1, weight=1)
        notebook.add(frame, text="BGS")

        self._enabled_var = tk.BooleanVar(value=enabled())
        self._tick_enabled_var = tk.BooleanVar(value=tick_enabled())

        nb.Label(frame, text="BGS Tracking", font=("TkDefaultFont", 9, "bold")).grid(
            row=0, column=0, columnspan=2, sticky=tk.W, padx=10, pady=(10, 4),
        )
        nb.Label(
            frame,
            text=(
                "Tracks faction states (War, Election, Boom, Bust, Outbreak, etc.) and BGS-"
                "needle-moving activity - missions, bounty/combat-bond vouchers, trade profit/"
                "loss, exploration data sold - for factions/systems you designate below. Only "
                "tracks what you list here - nothing shows for anything else. You can also "
                "Track/Untrack whatever system you're currently in directly from the BGS "
                "panel's own buttons, without coming here - both add to the same lists below. "
                "Mission/voucher/trade/exploration numbers are approximations where Frontier "
                "itself doesn't expose an exact figure (mission INF is a +/- pip count, not a "
                "percentage) - see docs/BGS_TECH_SPEC.md for specifics."
            ),
            wraplength=440, justify=tk.LEFT,
        ).grid(row=1, column=0, columnspan=2, sticky=tk.W, padx=10, pady=(0, 6))
        nb.Checkbutton(
            frame, text="Show BGS faction states and activity tally", variable=self._enabled_var,
        ).grid(row=2, column=0, columnspan=2, sticky=tk.W, padx=10, pady=(0, 4))
        nb.Checkbutton(
            frame, text="Detect BGS ticks (polls tick.infomancer.uk every 60s)",
            variable=self._tick_enabled_var,
        ).grid(row=3, column=0, columnspan=2, sticky=tk.W, padx=10, pady=(0, 4))
        nb.Label(
            frame,
            text=(
                "Tick detection is the only network call this mode makes - a community-run, "
                "third-party service (not Frontier's own). Turn it off to keep this mode fully "
                "local; the activity tally then just keeps accumulating without ever resetting "
                "on its own."
            ),
            wraplength=440, justify=tk.LEFT, foreground="grey",
        ).grid(row=4, column=0, columnspan=2, sticky=tk.W, padx=10, pady=(0, 8))

        self._systems_listbox = self._build_list_section(
            frame, row=5, title="Tracked Systems",
            subtitle="Every faction present in these systems is tracked.",
            items=self._tracked_systems, entry_attr="_systems_entry", on_add=self._on_add_system,
            on_remove=self._on_remove_system,
        )
        self._factions_listbox = self._build_list_section(
            frame, row=9, title="Tracked Factions",
            subtitle="These factions are tracked in every system they appear in.",
            items=self._tracked_factions, entry_attr="_factions_entry", on_add=self._on_add_faction,
            on_remove=self._on_remove_faction,
        )

    def _build_list_section(
        self, frame: nb.Frame, row: int, title: str, subtitle: str, items: List[str],
        entry_attr: str, on_add, on_remove,
    ) -> tk.Listbox:
        is_dark = theme.active not in (None, theme.THEME_DEFAULT)
        listbox_bg, listbox_fg = platform_support.listbox_colors(is_dark)

        nb.Label(frame, text=title, font=("TkDefaultFont", 9, "bold")).grid(
            row=row, column=0, columnspan=2, sticky=tk.W, padx=10, pady=(6, 0),
        )
        nb.Label(frame, text=subtitle).grid(row=row + 1, column=0, columnspan=2, sticky=tk.W, padx=10)

        list_row = nb.Frame(frame)
        list_row.grid(row=row + 2, column=0, columnspan=2, padx=10, pady=(4, 0), sticky=tk.W)
        listbox = tk.Listbox(
            list_row, width=50, height=4, background=listbox_bg, foreground=listbox_fg,
            selectbackground="#3a6ea5", exportselection=False,
        )
        listbox.grid(row=0, column=0, sticky="ns")
        scrollbar = tk.Scrollbar(list_row, orient="vertical", command=listbox.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        listbox.configure(yscrollcommand=scrollbar.set)
        for item in items:
            listbox.insert(tk.END, item)

        controls = nb.Frame(frame)
        controls.grid(row=row + 3, column=0, columnspan=2, padx=10, pady=(4, 10), sticky=tk.W)
        entry = tk.Entry(controls, width=32)
        entry.grid(row=0, column=0, padx=(0, 4))
        setattr(self, entry_attr, entry)
        tk.Button(controls, text="Add", command=lambda: on_add(entry, listbox)).grid(row=0, column=1, padx=2)
        tk.Button(controls, text="Remove Selected", command=lambda: on_remove(listbox)).grid(row=0, column=2, padx=2)
        return listbox

    def _refresh_settings_lists(self) -> None:
        if self._systems_listbox is not None:
            self._systems_listbox.delete(0, tk.END)
            for item in self._tracked_systems:
                self._systems_listbox.insert(tk.END, item)
        if self._factions_listbox is not None:
            self._factions_listbox.delete(0, tk.END)
            for item in self._tracked_factions:
                self._factions_listbox.insert(tk.END, item)

    def _on_add_system(self, entry: tk.Entry, listbox: tk.Listbox) -> None:
        self._add_tracked_item(entry, listbox, self._tracked_systems)

    def _on_add_faction(self, entry: tk.Entry, listbox: tk.Listbox) -> None:
        self._add_tracked_item(entry, listbox, self._tracked_factions)

    def _add_tracked_item(self, entry: tk.Entry, listbox: tk.Listbox, target: List[str]) -> None:
        value = entry.get().strip()
        if not value or any(value.casefold() == existing.casefold() for existing in target):
            entry.delete(0, tk.END)
            return
        target.append(value)
        listbox.insert(tk.END, value)
        entry.delete(0, tk.END)
        self._persist()
        self._refresh_current_system_display()
        self._refresh_summary()

    def _on_remove_system(self, listbox: tk.Listbox) -> None:
        self._remove_selected(listbox, self._tracked_systems)

    def _on_remove_faction(self, listbox: tk.Listbox) -> None:
        self._remove_selected(listbox, self._tracked_factions)

    def _remove_selected(self, listbox: tk.Listbox, target: List[str]) -> None:
        selection = listbox.curselection()
        if not selection:
            return
        index = selection[0]
        del target[index]
        listbox.delete(index)
        self._prune_untracked_data()
        self._persist()
        self._refresh_current_system_display()
        self._refresh_summary()
        self._refresh_report_window()

    def save_settings(self) -> None:
        if self._enabled_var is None:
            return
        config.set(_CFG_ENABLED, self._enabled_var.get())
        if self._tick_enabled_var is not None:
            config.set(_CFG_TICK_ENABLED, self._tick_enabled_var.get())
        self._persist()
        self._refresh_summary()


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
