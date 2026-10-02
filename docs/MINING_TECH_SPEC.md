# Technical Specification — Mining

**Author:** R.W. Harper (CMDR Bocheaux)
**Last updated:** 2026-10-02 (see `CHANGELOG.md`)

The standing reference for Mining mode: what it tracks, the rules and numbers behind its estimates, the
files it keeps, and the outside lookups it can make. For how to use it, see the
[README](../README.md#mining). For how the code is organised in general, see
[TECHNICAL.md](TECHNICAL.md).

## 1. Goals

- Track **Space Mining** (any ship) and **Surface Mining** (the Rhino SRV) runs live: what you've
  refined, how fast, and what's in the hold.
- Keep the commander's **own catalogue of surface hotspots**, with an estimate of the tons left in
  each, and let it be found again later in the **Mining Book**.
- Help on the ground: a "where have I driven" minimap and an arrow to the nearest saved hotspot.
- Offer optional lookups (nearby ring hotspots, best prices, ring reserve levels) that are off until
  switched on.

## 2. Non-goals

- **No knowledge of what a surface deposit holds.** The journal never says. Everything about deposits
  comes from what the commander records, plus the in-game scanner readout they type in.
- **No shipped hotspot database.** WNTB carries no third-party deposit or hotspot data. The only
  prospecting figures are the commander's own saved hotspots (§6).
- **No real scan coverage.** The minimap records where the Rhino has *driven*, not what was scanned
  (§7).
- **No exact tons-remaining.** It's a range (§5).

## 3. Architecture

All modules live in `plugin/`; `PANEL_PLACEMENT = "mining"`.

```
mining_panel.py          Entry point (feature-module contract). Page navigation, buttons, Settings tab,
                         and the journal and Status.json dispatch.
mining_render.py         What goes on each page (Space or Surface), redrawn on events and once a second.
mining_pages.py          Page order (kept separate to avoid a circular import).
mining_space.py          Ship-mining runs and the shared ring state.
mining_surface.py        Rhino surface-mining runs and the current body and system.
mining_rate.py           Refinements-per-minute over a sliding 10-second window, shared by both pages.
mining_methods.py        Commodity -> typical mining method(s). Static, community-sourced.
mining_hotspots.py       The saved-hotspot repository and its import and export formats.
mining_deposit.py        The tons-left estimate.
mining_ground.py         Kind-of-ground classification, and "your own rates" built from saved hotspots.
mining_body_survey.py    Landable bodies seen in the current system (Scan and SAASignalsFound).
mining_ledger.py         The Mining Book window.   mining_ledger_data.py: its data shaping (pure).
mining_coverage.py       The driven-ground record.  mining_coverage_render.py: draws the minimap (PIL).
mining_live_position.py  The live surface position from Status.json.
mining_bearing.py        Distance and bearing between two surface points.
mining_overlay.py        The optional on-screen stats panel and waypoint arrow.
mining_session_archive.py Optional JSON archive of finished runs.
mining_journal_backfill.py Replays today's journal on a mid-session EDMC start.
mining_location.py       The commander's current system.
mining_*_dialog.py       The Add/Edit Hotspot form and the three lookup dialogs.
mining_spansh_client.py  The Spansh lookups (hotspots, best price). edsm_client.py: ring reserves.
```

Pure logic (`mining_hotspots`, `mining_deposit`, `mining_ground`, `mining_ledger_data`,
`mining_body_survey`, `mining_coverage`, `mining_bearing`, `mining_rate`) has no screen code and is
unit-tested.

## 4. Runs

### 4.1 Space Mining
A run is one **undock-to-dock trip**: `Undocked` starts a fresh run; `Docked` leaves the finished numbers
on screen until the next undock. This is coarser than "from the first prospector to the next jump", but
more reliable: a finer boundary would split one stop at a ring into several runs whenever you hop in
supercruise. While in supercruise mid-trip the panel shows a "paused" hint. It does not reset anything.

Events used: `ProspectedAsteroid` (content grade, composition, with duplicate-asteroid detection),
`LaunchDrone` and `BuyDrones` (limpets used, and a rough "on board" figure that can't tell an unused
timed-out limpet from one still deployed), `MiningRefined` (the actual output), `AsteroidCracked`
(core mining), `Cargo` and `Loadout` (hold and capacity), and `SupercruiseEntry` / `SupercruiseExit`.

### 4.2 Surface Mining
A run is one **Rhino deployment**: `LaunchSRV` with `SRVType == "mev_rhino"` starts it and the matching
`DockSRV` ends it. The Rhino reuses the ordinary `MiningRefined` event, so WNTB only routes it to the
Surface page while a Rhino is deployed. It also tracks the SRV hold (capacity 72), cargo handed to the
ship mid-run (`CargoTransfer`, so it isn't mistaken for a loss), and materials collected. Docking the
Rhino moves whatever is left in its hold to the ship.

### 4.3 Rate
`mining_rate` counts refinements in the last 10 seconds and scales to a per-minute figure, recomputed on
each refinement and on the page's timer, so the displayed rate decays toward zero during a lull instead
of freezing.

### 4.4 Mid-session start
If EDMC starts while you are already out mining, WNTB replays **today's journal file** through the same
handlers so the current run is picked up. Older files are ignored: a run never outlives its undock or
deployment.

## 5. The tons-left estimate

The journal reports neither a deposit's size nor how much of it is left. The in-game mining scanner shows
two readings, **Amount** (High, Medium, Low, Depleted) and **Density** (High, Medium, Low), which the
commander enters on a hotspot. Nothing here is exact, so the answer is a **range**.

The model (`mining_deposit.reserve_range`), from measured depletion of real deposits (credited in
`THIRD-PARTY-NOTICES.md`):
- A full deposit holds a fixed number of tons **per rig position**, set by Density. A *lower* Density
  label means a *larger* reserve: roughly 125–175 t per position at High, 250–350 at Medium and 375–525
  at Low.
- The Amount label then gives the **share still left** (High about 57–100%, Medium 27–67%, Low 0–34%,
  Depleted 0).
- Range = rigs × tons per position × share left, rounded to the nearest 10 t. With no Density, the
  range spans the smallest low end to the largest high end.

At most **7 rigs** can be recorded (six can be worked at once; a seventh can be placed but not run).
When the Rhino is out, each refined ton is credited to the nearest saved hotspot within **200 m**, so a
depleted deposit reads "depleted (612 t)". Tons are counted in memory and written at most every 5
seconds. These figures are measurements and may need refitting as more deposits are mined.

## 6. Hotspots, the Mining Book and "your own rates"

### 6.1 The hotspot file
`mining_hotspots.json` (in the plugin folder, never part of a release) is a flat list of hotspots. Each
has a system, body and material, plus optional notes, latitude and longitude, a folder label, rigs, a
signal number, the Amount and Density readings, the tons mined so far, and the kind of ground (§6.3).
Material, rigs, signal number, Amount and Density are entered by the commander on trust; only the mined
tons are derived from the journal. Saving a hotspot within **100 m** of an existing one on the same body
updates it instead of adding a duplicate.

### 6.2 Import and export
WNTB exports and re-imports its own file format, with a merge or replace choice. It can also import a
**PlanetPOI** `poi.json` export or a single shared POI link. The material is pulled out of PlanetPOI's
free-text description using a list of known materials, and anything it can't read is kept in the notes.
Imports are converted to WNTB's own format, so there's no ongoing dependency on the source format.

### 6.3 The Mining Book
A three-pane window: bodies (the current system's scanned landable bodies plus every saved hotspot,
anywhere), a body's hotspots grouped by location, and a detail card with a zoomable map. Filters are by
material and by rig count; the card offers Edit, Mark depleted, Copy coordinates and Delete.

**Your own rates.** For a scanned body, the Mining Book shows what *you* have found so far on that kind of
ground: the share of your saved deposits, per material, with the sample size. `mining_ground.classify`
turns the journal's `PlanetClass` and `Volcanism` into a ground (for example "Rocky body, silicate
magma"). A new hotspot is stamped with its ground when saved; older or imported ones count while their
body is in the current survey. These are tallies of **your recorded deposits only**, not a statement about
what any body holds, and the section stays empty until you record something.

## 7. On the ground

### 7.1 Live position
Latitude, longitude and heading come from `Status.json` through EDMC's dashboard hook (about once a
second), and are only valid on a landable body's surface. The body radius also comes from `Status.json`,
with the radius from the body's `Scan` event as a fallback.

### 7.2 The coverage minimap
While a Rhino is deployed and a radius is known, a point is recorded as you drive (at least **250 m**
from the last one), and the map paints a **2,000 m** disc at each. This records where the Rhino has
*driven*, because nothing in the journal or `Status.json` says a scan happened, so it can't claim real
scan coverage. The map is a fixed 220 px square, 12 km across, north up, with hotspots (a pale filled
dot for live, a hollow grey ring for depleted, so shape carries the meaning for colour-blind players) and
your position. Without a Rhino deployed it only shows below 2 km altitude. It uses a flat-earth
projection, accurate enough at this scale.

### 7.3 The waypoint arrow
The overlay's arrow points to the **nearest saved hotspot with a position on the current body**, using
great-circle distance and initial bearing between your live position and the hotspot. There is no
per-hotspot target to pick.

## 8. Optional lookups

All are **off until switched on** in the Mining Settings tab. See
[TECHNICAL.md](TECHNICAL.md#keeping-api-traffic-low) for how call volume is kept down.

| Lookup | Service | Trigger |
|---|---|---|
| Find Nearby Hotspots (rings with a confirmed hotspot for a commodity, nearest first) | Spansh | Button |
| Find Best Price (best-price stations for a commodity) | Spansh | Button |
| Check Ring Reserve Level | EDSM | Button; and automatically on dropping into a ring, if enabled |

The automatic ring check runs only when enabled, never while replaying the journal at start-up, and the
answer is remembered for the session for each ring. A non-Metallic ring shows a laser-mining caution.
Spansh does not publish the request shape used for its ring and station searches; it was worked out from
live calls and checked against independent callers, and `mining_spansh_client.py` is the one place to fix
if Spansh changes it. An earlier plan to use Inara was dropped because Inara has no commodity or market
lookup to call.

## 9. Optional extras

- **On-screen stats panel and waypoint arrow** (overlay; two separate switches). Both register an
  EDMCModernOverlay Plugin Group so their backgrounds draw.
- **Archive completed runs.** Off by default. When a run that has data ends, a JSON file is written to
  `mining_sessions/` for analysis outside WNTB. Empty trips write nothing.

## 10. Settings

Under **File → Settings → WNTB → Mining** (keys start `wntb_mining_`): session totals, cargo bar,
prospector hints, the three lookups, the two overlays, the coverage minimap, and run archiving. The last
page you viewed is remembered.

## 11. Files

| File | What | Notes |
|---|---|---|
| `mining_hotspots.json` | Saved hotspots | The commander's data; never in a release |
| `mining_coverage.json` | Driven-ground record per body | The commander's data |
| `mining_sessions/` | Archived runs | Only if archiving is on |

All are listed in the updater's protected set so an update never overwrites them (see TECHNICAL.md §13).

## 12. Testing

`tests/test_mining_deposit.py`, `test_mining_hotspots.py`, `test_mining_ground.py`,
`test_mining_ledger_data.py`, `test_mining_body_survey.py` and `test_mining_coverage.py` cover the pure
logic. The bearing and rate maths, the panel, overlays and map are exercised by hand in EDMC.

## 13. Known gaps

- Amount and Density are typed in by hand; a wrong reading gives a wrong range.
- The deposit figures are measurements from a handful of deposits, so the ranges are wide.
- Coverage means "driven", not "scanned".
- Limpets "on board" is approximate.
- Commodity-to-method hints (`mining_methods.py`) are community-sourced and need occasional upkeep.
