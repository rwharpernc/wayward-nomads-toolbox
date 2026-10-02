"""
Tracks ship-based mining runs (Core / Laser Surface / Sub-surface Deposit,
any vessel) for the Space Mining page.

A run spans one undock-to-dock trip: `Undocked` starts a fresh run,
`Docked` just leaves the finished numbers on screen (mining and selling
don't overlap within a trip, so the next `Undocked` is what actually
starts a new run) - a simpler and more reliable boundary than trying to
infer "mining started" from the first ProspectedAsteroid/MiningRefined
event, and consistent with how mining_surface.py uses LaunchSRV/DockSRV as
its own natural session boundary.

This is a deliberately coarser boundary than a fine-grained "active
mining" window (starting on the first Prospector-drone launch and ending
on `SupercruiseEntry`/`FSDJump`), which resets on every supercruise hop
and would fragment one continuous mining stop at a ring into several
"runs" if the player repositions within it via a supercruise hop - not
obviously better, just a different tradeoff.

Fed from mining_panel.py's handle_event, which forwards:
- `ProspectedAsteroid` - content grade (Low/Medium/High); the material
  composition, for duplicate-asteroid detection, for the commodity names
  behind the "Mine via" extraction-method hint (mining_methods.py), and
  for a per-commodity Proportion-value "% Range" hint (format_yield_range()).
- `LaunchDrone` - prospector/collector/etc. limpet usage.
- `BuyDrones` - limpets purchased, so the panel can show a rough "on
  board" figure (bought minus launched - not exact, since a limpet that
  times out unused isn't distinguished from one that's still deployed).
- `MiningRefined` - the actual commodity output.
- `AsteroidCracked` - a core-mining-specific event (fires when a
  seismic-charged rock actually splits open), tracked as its own count
  since `MiningRefined` alone doesn't say whether a unit came from core
  mining or a surface/sub-surface deposit.
- `Cargo` (Vessel == "Ship") - running ship cargo total.
- `Loadout` - ship cargo capacity, so the cargo total can be shown as a
  fraction rather than a bare number.
- `SupercruiseEntry` / `SupercruiseExit` - a lightweight "paused" flag
  (`SpaceMiningRun.is_paused`) shown on the panel while supercruising
  between belts mid-trip. Doesn't reset or freeze any run data - the
  undock-to-dock boundary above already decided not to fragment a run on
  every supercruise hop; this is purely a UI hint so a lull reads as
  "paused for travel" rather than an unexplained stop in activity.
  `SupercruiseExit` also feeds `SpaceMiningRepository.set_current_ring()`
  when `BodyType` is `"PlanetaryRing"` - not run-scoped, like
  `cargo_capacity`, since "which ring is the ship at" is a ship-position
  fact that outlives one undock-to-dock run. mining_panel.py uses this to
  drive an automatic EDSM reserve-level lookup (see `edsm_client.py`)
  that lands back in `set_ring_caution()`.
"""
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from . import mining_rate


@dataclass
class RingCaution:
    """A completed EDSM reserve-level lookup for whichever ring
    `SpaceMiningRepository` currently has tracked - plain fields rather
    than reusing edsm_client's raw response shape directly, so this
    module (fed only from mining_panel.py, like the rest of its state)
    doesn't need to import the network-lookup module itself;
    mining_panel.py does that translation. See
    `SpaceMiningRepository.set_ring_caution()`."""
    ring_name: str
    reserve_level: Optional[str]
    ring_type: str
    is_metallic: bool


@dataclass
class SpaceMiningRun:
    """One ship-mining trip (Undocked to Docked) for a single commander."""
    prospected_count: int = 0
    duplicate_prospected: int = 0
    """Asteroids re-prospected with an identical material signature to one
    already seen this run - not counted in prospected_count/content_counts,
    since it's almost always the same rock scanned twice rather than a
    second rock with coincidentally identical composition."""
    content_counts: dict[str, int] = field(default_factory=dict)
    """Asteroid content grade ("Low"/"Medium"/"High"/"?") -> count."""
    prospected_commodities: dict[str, int] = field(default_factory=dict)
    """Commodity display name -> times named in a (non-duplicate)
    ProspectedAsteroid's Materials list this run - lets the panel show a
    "Mine via" hint (mining_methods.methods_for()) for materials seen on
    rocks even before any of it is actually refined."""
    prospected_proportions: dict[str, list[float]] = field(default_factory=dict)
    """Commodity display name -> Materials[].Proportion samples from
    (non-duplicate) ProspectedAsteroid events this run - feeds the
    format_yield_range() "% Range" hint (min-avg-max)."""
    refined: dict[str, int] = field(default_factory=dict)
    """Commodity display name -> units refined this run."""
    asteroids_cracked: int = 0
    """Rocks split open via AsteroidCracked (core mining) this run - a
    separate count from prospected_count/refined, since neither says
    whether the yield came from core mining specifically."""
    limpets_launched: dict[str, int] = field(default_factory=dict)
    """Limpet type (Prospector/Collection/...) -> count launched."""
    limpets_bought: int = 0
    """Total limpets purchased this run (BuyDrones), for a rough "on
    board" estimate - bought minus total launched. Not exact: a limpet
    that expires unused looks identical to one still out collecting."""
    cargo: int = 0
    """Most recent ship cargo total (Cargo event, Vessel == "Ship")."""
    is_paused: bool = False
    """True while supercruising mid-trip (SupercruiseEntry seen, no
    SupercruiseExit yet) - a UI-only hint, not a data reset/freeze."""
    refined_timestamps: list[float] = field(default_factory=list, repr=False, compare=False)
    """Wall-clock time.time() of each unit refined this run, for
    mining_rate.current_rate()'s refinements-per-minute display -
    pruned in place by current_rate() itself."""
    _seen_prospect_keys: set = field(default_factory=set, repr=False, compare=False)
    """Material-signature keys already seen this run - see
    SpaceMiningRepository.record_prospected()."""

    def has_data(self) -> bool:
        """Whether this run has anything worth showing/archiving - same
        condition mining_render.py's space-mining page gates its "no
        active run" message on, and mining_panel.py gates JSON
        archiving on."""
        return (self.prospected_count > 0 or bool(self.refined) or bool(self.limpets_launched)
                or self.asteroids_cracked > 0 or self.cargo > 0)


def _content_grade(content: str, content_localised: Optional[str]) -> str:
    """"$AsteroidMaterialContent_Medium;" / "Material Content: Medium" ->
    "Medium". Falls back to the raw Content token if localisation is
    missing (non-English clients may not match the "Material Content: "
    prefix)."""
    if content_localised and ":" in content_localised:
        return content_localised.rsplit(":", 1)[-1].strip()
    return content.strip("$;").rsplit("_", 1)[-1] or "?"


def _prospect_key(materials: Optional[list[dict[str, Any]]]) -> Optional[tuple]:
    """A rock's material composition as a hashable signature, used to spot
    the same asteroid prospected twice (e.g. a re-scan after the
    prospector's cooldown, or a relog while still sitting in the same
    belt) - the journal gives asteroids no identity of their own. Proportion
    is rounded to 1 decimal place since repeat scans of the same rock can
    report tiny floating-point differences."""
    if not materials:
        return None
    parsed = []
    for material in materials:
        name = material.get("Name")
        proportion = material.get("Proportion")
        if not isinstance(name, str) or proportion is None:
            continue
        try:
            parsed.append((name.lower(), round(float(proportion), 1)))
        except (TypeError, ValueError):
            continue
    return tuple(sorted(parsed)) if parsed else None


def _material_samples(materials: Optional[list[dict[str, Any]]]) -> list[tuple[str, Optional[float]]]:
    """A ProspectedAsteroid's Materials list, as (display name, Proportion)
    pairs. Display names are in the same form MiningRefined reports (e.g.
    "Painite"), for mining_methods lookups - falls back to a capitalized
    raw Name if Name_Localised is missing (non-English clients), same
    fallback pattern as _content_grade(), and similarly imperfect for
    multi-word commodities. Proportion is None if missing/unparseable -
    still yields the name for prospected_commodities, just not a yield-
    range sample."""
    if not materials:
        return []
    samples = []
    for material in materials:
        localised = material.get("Name_Localised")
        if isinstance(localised, str) and localised:
            name = localised
        else:
            raw = material.get("Name")
            if not (isinstance(raw, str) and raw):
                continue
            name = raw.capitalize()
        proportion = material.get("Proportion")
        try:
            proportion = float(proportion)
        except (TypeError, ValueError):
            proportion = None
        samples.append((name, proportion))
    return samples


def format_yield_range(proportions: list[float]) -> str:
    """[23.5] -> "24%"; [12.0, 38.0] -> "12%-24%-38%" (min-avg-max). This
    is a text summary rather than a clickable histogram popup, which
    doesn't fit WNTB's plain-label panel style."""
    if not proportions:
        return ""
    if len(proportions) == 1:
        return f"{proportions[0]:.0f}%"
    return f"{min(proportions):.0f}%-{sum(proportions) / len(proportions):.0f}%-{max(proportions):.0f}%"


class SpaceMiningRepository:
    """Per-commander SpaceMiningRun state, alt-friendly like Missions
    mode's active_missions.py: switching commanders in EDMC switches
    the tracked run with it."""

    def __init__(self) -> None:
        self._runs_by_cmdr: dict[str, SpaceMiningRun] = {}
        self._cargo_capacity_by_cmdr: dict[str, int] = {}
        self._current_ring_by_cmdr: dict[str, Optional[tuple[str, str]]] = {}
        """(system, ring name) the commander last SupercruiseExit'd into
        with BodyType "PlanetaryRing", or None once they leave it (see
        set_current_ring()) - not run-scoped, see RingCaution's docstring."""
        self._ring_caution_by_cmdr: dict[str, Optional[RingCaution]] = {}
        self._current_cmdr: Optional[str] = None
        self._listeners: list[Callable[[Optional[SpaceMiningRun]], None]] = []

    def set_current_cmdr(self, cmdr: str) -> None:
        self._current_cmdr = cmdr
        self._runs_by_cmdr.setdefault(cmdr, SpaceMiningRun())

    def current_run(self) -> Optional[SpaceMiningRun]:
        if self._current_cmdr is None:
            return None
        return self._runs_by_cmdr.get(self._current_cmdr)

    def cargo_capacity(self) -> Optional[int]:
        """The current ship's cargo capacity (from its most recent
        `Loadout` event) - not run-scoped, since the ship (and so its
        capacity) doesn't change just because a new run started."""
        if self._current_cmdr is None:
            return None
        return self._cargo_capacity_by_cmdr.get(self._current_cmdr)

    def start_new_run(self) -> None:
        if self._current_cmdr is None:
            return
        self._runs_by_cmdr[self._current_cmdr] = SpaceMiningRun()
        self._notify()

    def update_cargo_capacity(self, capacity: int) -> None:
        if self._current_cmdr is None:
            return
        self._cargo_capacity_by_cmdr[self._current_cmdr] = capacity
        self._notify()

    def record_prospected(self, content: str, content_localised: Optional[str],
                          materials: Optional[list[dict[str, Any]]] = None) -> None:
        run = self.current_run()
        if run is None:
            return
        key = _prospect_key(materials)
        if key is not None and key in run._seen_prospect_keys:
            run.duplicate_prospected += 1
            self._notify()
            return
        if key is not None:
            run._seen_prospect_keys.add(key)
        run.prospected_count += 1
        grade = _content_grade(content, content_localised)
        run.content_counts[grade] = run.content_counts.get(grade, 0) + 1
        for name, proportion in _material_samples(materials):
            run.prospected_commodities[name] = run.prospected_commodities.get(name, 0) + 1
            if proportion is not None:
                run.prospected_proportions.setdefault(name, []).append(proportion)
        self._notify()

    def record_asteroid_cracked(self) -> None:
        run = self.current_run()
        if run is None:
            return
        run.asteroids_cracked += 1
        self._notify()

    def record_limpet(self, limpet_type: str) -> None:
        run = self.current_run()
        if run is None:
            return
        run.limpets_launched[limpet_type] = run.limpets_launched.get(limpet_type, 0) + 1
        self._notify()

    def record_limpets_bought(self, count: int) -> None:
        run = self.current_run()
        if run is None:
            return
        run.limpets_bought += count
        self._notify()

    def record_refined(self, commodity: str) -> None:
        run = self.current_run()
        if run is None:
            return
        run.refined[commodity] = run.refined.get(commodity, 0) + 1
        mining_rate.record_tick(run.refined_timestamps)
        self._notify()

    def pause_run(self) -> None:
        run = self.current_run()
        if run is None:
            return
        run.is_paused = True
        self._notify()

    def resume_run(self) -> None:
        run = self.current_run()
        if run is None:
            return
        run.is_paused = False
        self._notify()

    def update_cargo(self, count: int) -> None:
        run = self.current_run()
        if run is None:
            return
        run.cargo = count
        self._notify()

    def adjust_cargo(self, delta: int) -> None:
        """Nudges the tracked ship cargo total by `delta` rather than
        replacing it outright - for `CargoTransfer` (Direction ==
        "toship"), where the journal doesn't reliably follow up with a
        `Cargo` (Vessel == "Ship") event confirming the new total. A
        later authoritative `Cargo` event, if one does arrive, still
        overwrites this via update_cargo() same as always - this is just
        the best estimate until then. Clamped at 0 so a delta this run
        never saw the matching pickup for (e.g. a run that started
        mid-transfer on a backfilled restart) can't drive the total
        negative."""
        run = self.current_run()
        if run is None:
            return
        run.cargo = max(run.cargo + delta, 0)
        self._notify()

    def set_current_ring(self, system: Optional[str], ring: Optional[str]) -> None:
        """Called on every `SupercruiseExit` - `ring` is the exact
        `Body` name when `BodyType` is `"PlanetaryRing"`, else None (the
        commander dropped somewhere that isn't a ring, or left one via
        `SupercruiseEntry`). Clears any previous ring's caution
        immediately - it's stale the moment the ring changes, and a slow
        in-flight lookup for the old ring is guarded against overwriting
        this by set_ring_caution()'s own staleness check."""
        if self._current_cmdr is None:
            return
        new_value = (system, ring) if (system and ring) else None
        if self._current_ring_by_cmdr.get(self._current_cmdr) == new_value:
            return
        self._current_ring_by_cmdr[self._current_cmdr] = new_value
        self._ring_caution_by_cmdr[self._current_cmdr] = None
        self._notify()

    def current_ring(self) -> Optional[tuple[str, str]]:
        if self._current_cmdr is None:
            return None
        return self._current_ring_by_cmdr.get(self._current_cmdr)

    def set_ring_caution(self, system: str, ring: str, caution: Optional[RingCaution]) -> None:
        """Applies a completed EDSM lookup's result - only if `(system,
        ring)` still matches the currently tracked ring, so a lookup that
        finishes after the commander has already moved on to a different
        ring (or left ring-space entirely) doesn't overwrite the newer
        state with a stale answer."""
        if self._current_cmdr is None:
            return
        if self._current_ring_by_cmdr.get(self._current_cmdr) != (system, ring):
            return
        self._ring_caution_by_cmdr[self._current_cmdr] = caution
        self._notify()

    def ring_caution(self) -> Optional[RingCaution]:
        if self._current_cmdr is None:
            return None
        return self._ring_caution_by_cmdr.get(self._current_cmdr)

    def add_listener(self, listener: Callable[[Optional[SpaceMiningRun]], None]) -> None:
        self._listeners.append(listener)

    def _notify(self) -> None:
        for listener in self._listeners:
            listener(self.current_run())


space_mining_repository = SpaceMiningRepository()
