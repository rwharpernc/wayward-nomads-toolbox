"""
Tracks Rhino surface-mining runs for the Surface Mining page.

A run spans one SRV deployment: `LaunchSRV` with SRVType "mev_rhino"
starts a fresh run, the matching `DockSRV` ends it (numbers stay on
screen until the next deployment, mirroring how mining_space.py freezes
a run at `Docked` rather than clearing it). The Rhino reuses the same
`MiningRefined` event as ship-based mining rather than a dedicated one -
no Rhino-specific mining event exists, which is why mining_panel.py has
to gate `MiningRefined` on whether a Rhino is currently deployed
(`is_active` below) to route it to the right page.

Fed from mining_panel.py's handle_event, which forwards:
- `LaunchSRV` / `DockSRV` (SRVType == "mev_rhino") - run start/end.
- `MiningRefined` - refined commodity output, only while `is_active`.
- `Cargo` (Vessel == "SRV") - running SRV cargo total.
- `CargoTransfer` (Direction == "toship") - cargo handed off to the
  mothership mid-run, tracked separately so it isn't mistaken for cargo
  lost from the run when the SRV hold empties.
- `MaterialCollected` - engineering materials (Raw/Manufactured/Encoded)
  picked up while the Rhino is deployed, only while `is_active`. Rhino
  commodity mining drops these as a side effect alongside the sellable
  commodity itself, so a run tracks both: `refined` for what sells at a
  station, `raw_materials` for what feeds Engineers. Gated the same way
  `MiningRefined` is, since this event isn't Rhino-specific either (it
  also fires for on-foot/SRV pickups outside any mining run).
- `SAASignalsFound` (a "$PlanetaryMiningLocation_Name;" signal) - not
  run-scoped, since it's found by orbital DSS scanning before the Rhino
  ever launches; tracked per-body as a "worth landing here" hint instead.
- `Location` / `FSDJump` (system, clears body) / `ApproachBody` (sets
  body) / `LeaveBody` (clears body) - tracks where the commander
  currently is, for mining_hotspots.py's "known hotspots here" lookup
  and the "Save Hotspot Here" quick-add (mining_render.py/
  mining_hotspot_dialog.py). Field names confirmed as `StarSystem`/`Body`
  (not `BodyName`) against real journal logs.
- `Touchdown` / `Liftoff` - the ship's landed lat/lon, purely to prefill
  the quick-add dialog with an exact spot when one's known; not tracked
  as run data.
- `Scan` (`BodyName`/`Radius`) - a body's radius in meters, kept for the
  session as a fallback for mining_overlay.py's great-circle-to-ground-
  distance conversion. Status.json's own `PlanetRadius` field (see
  mining_live_position.py, fed from load.py's `dashboard_entry` hook
  instead of journal_entry, since Status.json isn't a discrete journal
  event) is preferred when present, since it needs no prior DSS/FSS scan
  of the body - this Scan-derived value only matters when a game/EDMC
  version doesn't populate that field.
"""
from dataclasses import dataclass, field
from typing import Callable, Optional

from . import mining_rate

RHINO_SRV_TYPE = "mev_rhino"

RHINO_CARGO_CAPACITY = 72
"""Tons - the Rhino's fixed cargo hold size, confirmed in-game; not
derivable from the journal itself (no Loadout-equivalent event exists
for the SRV, unlike the ship's own CargoCapacity from `Loadout` - see
mining_space.py), so this is a static constant like mining_methods.py's
commodity table."""

MINING_LOCATION_SIGNAL_TYPE = "$PlanetaryMiningLocation_Name;"
"""The SAASignalsFound signal Type for a DSS-detected surface mining site
- the Rhino's equivalent of a ring hotspot."""


@dataclass
class SurfaceMiningRun:
    """One Rhino deployment (LaunchSRV to DockSRV) for a single commander."""
    refined: dict[str, int] = field(default_factory=dict)
    """Commodity display name -> units refined this deployment."""
    transferred_to_ship: dict[str, int] = field(default_factory=dict)
    """Commodity display name -> units handed off to the mothership."""
    raw_materials: dict[str, int] = field(default_factory=dict)
    """Engineering-material display name -> units collected
    (MaterialCollected) while this Rhino was deployed - separate from
    `refined` since these aren't sellable at a station, they feed
    Engineers instead."""
    cargo: int = 0
    """Most recent SRV cargo total (Cargo event, Vessel == "SRV")."""
    refined_timestamps: list[float] = field(default_factory=list, repr=False, compare=False)
    """Wall-clock time.time() of each unit refined this deployment, for
    mining_rate.current_rate()'s refinements-per-minute display -
    pruned in place by current_rate() itself."""

    def has_data(self) -> bool:
        """Whether this run has anything worth showing/archiving - same
        condition mining_render.py's surface-mining page folds into its
        "has_data" check, and mining_panel.py gates JSON archiving on."""
        return bool(self.refined) or bool(self.transferred_to_ship) or bool(self.raw_materials) or self.cargo > 0


@dataclass
class MiningLocationSignal:
    """Most recent DSS-detected Planetary Mining Location signal - not
    tied to any particular run, since it's found from orbit."""
    body_name: str
    count: int


@dataclass
class TouchdownPosition:
    """Latitude/longitude from the ship's most recent `Touchdown`, cleared
    on `Liftoff` - used only to prefill the "Save Hotspot Here" dialog
    (see mining_render.py/mining_hotspot_dialog.py) with an exact spot
    when one's known, not tracked as part of any run."""
    latitude: float
    longitude: float


class SurfaceMiningRepository:
    """Per-commander SurfaceMiningRun state, alt-friendly like Missions
    mode's active_missions.py: switching commanders in EDMC switches
    the tracked run with it."""

    def __init__(self) -> None:
        self._runs_by_cmdr: dict[str, SurfaceMiningRun] = {}
        self._current_cmdr: Optional[str] = None
        self._active_srv_id: Optional[int] = None
        self._latest_signal: Optional[MiningLocationSignal] = None
        self._current_system: Optional[str] = None
        self._current_body: Optional[str] = None
        self._last_touchdown: Optional[TouchdownPosition] = None
        self._body_radii: dict[str, float] = {}
        self._listeners: list[Callable[[Optional[SurfaceMiningRun]], None]] = []

    @property
    def is_active(self) -> bool:
        """True while a Rhino is currently deployed - mining_panel.py
        uses this to decide whether a `MiningRefined` event belongs here
        or to mining_space.py, since the event itself doesn't say."""
        return self._active_srv_id is not None

    def set_current_cmdr(self, cmdr: str) -> None:
        self._current_cmdr = cmdr
        self._runs_by_cmdr.setdefault(cmdr, SurfaceMiningRun())

    def current_run(self) -> Optional[SurfaceMiningRun]:
        if self._current_cmdr is None:
            return None
        return self._runs_by_cmdr.get(self._current_cmdr)

    def latest_signal(self) -> Optional[MiningLocationSignal]:
        return self._latest_signal

    def start_run(self, srv_id: int) -> None:
        self._active_srv_id = srv_id
        if self._current_cmdr is not None:
            self._runs_by_cmdr[self._current_cmdr] = SurfaceMiningRun()
        self._notify()

    def end_run(self, srv_id: int) -> None:
        if srv_id != self._active_srv_id:
            return  # a different SRV than the one that started this run
        self._active_srv_id = None
        self._notify()

    def force_end_run(self) -> None:
        """Clears `is_active` unconditionally, unlike end_run(): for cases
        where the Rhino is gone but never sends a matching DockSRV - e.g.
        `SRVDestroyed`, or the CMDR dying while deployed. Without this,
        `is_active` would stay stuck True and every subsequent
        MiningRefined event would misroute to this page instead of
        mining_space.py."""
        if self._active_srv_id is not None:
            self._active_srv_id = None
            self._notify()

    def record_refined(self, commodity: str) -> None:
        run = self.current_run()
        if run is None:
            return
        run.refined[commodity] = run.refined.get(commodity, 0) + 1
        mining_rate.record_tick(run.refined_timestamps)
        self._notify()

    def update_cargo(self, count: int) -> None:
        run = self.current_run()
        if run is None:
            return
        run.cargo = count
        self._notify()

    def record_transfer_to_ship(self, commodity: str, count: int) -> None:
        run = self.current_run()
        if run is None:
            return
        run.transferred_to_ship[commodity] = run.transferred_to_ship.get(commodity, 0) + count
        self._notify()

    def record_raw_material(self, material: str, count: int) -> None:
        run = self.current_run()
        if run is None:
            return
        run.raw_materials[material] = run.raw_materials.get(material, 0) + count
        self._notify()

    def record_mining_location_signal(self, body_name: str, count: int) -> None:
        self._latest_signal = MiningLocationSignal(body_name, count)
        self._notify()

    def set_current_location(self, system: Optional[str], body: Optional[str]) -> None:
        """Tracks where the commander currently is, for
        mining_hotspots.py's "known hotspots here" lookup and the "Save
        Hotspot Here" quick-add (mining_render.py) - fed from
        mining_panel.py's `Location`/`FSDJump` (system, clears body),
        `ApproachBody` (sets body), and `LeaveBody` (clears body).
        Changing body clears any stale touchdown position from the body
        just left."""
        if body != self._current_body:
            self._last_touchdown = None
        self._current_system = system
        self._current_body = body
        self._notify()

    def record_body_radius(self, body_name: str, radius_m: float) -> None:
        """From a `Scan` event's BodyName/Radius (meters). Status.json's
        live position doesn't carry the body's radius, but
        mining_overlay.py's distance-to-hotspot calculation needs it.
        Kept for the life of the session rather than cleared on
        LeaveBody/FSDJump - a body's radius doesn't change, and it might
        get scanned well before (or after) any Rhino deployment there."""
        self._body_radii[body_name] = radius_m

    def radius_for_current_body(self) -> Optional[float]:
        if self._current_body is None:
            return None
        return self._body_radii.get(self._current_body)

    def record_touchdown(self, latitude: float, longitude: float) -> None:
        self._last_touchdown = TouchdownPosition(latitude, longitude)
        self._notify()

    def clear_touchdown(self) -> None:
        if self._last_touchdown is not None:
            self._last_touchdown = None
            self._notify()

    @property
    def current_system(self) -> Optional[str]:
        return self._current_system

    @property
    def current_body(self) -> Optional[str]:
        return self._current_body

    @property
    def last_touchdown(self) -> Optional[TouchdownPosition]:
        return self._last_touchdown

    def add_listener(self, listener: Callable[[Optional[SurfaceMiningRun]], None]) -> None:
        self._listeners.append(listener)

    def _notify(self) -> None:
        for listener in self._listeners:
            listener(self.current_run())


surface_mining_repository = SurfaceMiningRepository()
