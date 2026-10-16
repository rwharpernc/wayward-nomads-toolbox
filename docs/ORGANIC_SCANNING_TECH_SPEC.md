# Technical Specification — Organic Scanning

**Author:** R.W. Harper (CMDR Bocheaux)
**Last updated:** 2026-10-16 (see `CHANGELOG.md`)

The standing reference for Organic Scanning (exobiology): what it predicts, the rules behind the
prediction, how scan progress is tracked, and where its answers can be wrong. For how to use it, see the
[Exobiology guide](guide/exobiology.md). For how the code is organized in general, see
[TECHNICAL.md](TECHNICAL.md).

> **Design principle.** Like all of WNTB, this is journal-first: a third-party tool only knows what the game writes to its journal files, and not everything is logged. Gaps are filled from Frontier's own data or from community services where those exist, and otherwise worked around, and each gap and its workaround is written down. See [the design principle in TECHNICAL.md](TECHNICAL.md).

## 1. Goals

- Given the biological signals on a planet, say which **species** each is likely to be, from the planet's
  conditions.
- Track your **Log → Sample → Analyze** progress for each organism, and tell you when you've moved far
  enough from the last sample for the next one to count.
- Show the **credit value** of each species.
- Remember a body's biology across a relog or an EDMC restart.
- Feed the Exobiology overlay cards (section 11): a per-body view of the genera, the predicted and confirmed species, the sample positions and the way back to
  plants the commander identified.

## 2. Non-goals

- **No network access, and nothing submitted anywhere.** It is a local, read-only companion and never
  submits codex or biology data.
- **No first-discovery bonus.** Exobiology analysis pays a flat per-species value regardless of who found
  it first. The one multiplier WNTB shows is the **first footfall** bonus (five times the value for the first
  commander on a body, from the body's `WasFootfalled`), which is a property of the body, not of the species.
- **No certainty before a sample.** Until a scan names the species, the answer is a candidate list.

## 3. Architecture

All modules live in `plugin/`; `PANEL_PLACEMENT = "exploration"`.

```
organic_scan.py         Pure logic: BodyConditions, the matching rules, scan-stage tracking, distance.
organic_scan_state.py   Per-commander persistence of each body's biology (organic_scan_state.json).
organic_scan_panel.py   The panel: reads journal events, builds conditions, shows predictions and progress, and builds the overlay view.
organic_species_data.py Generated reference data: genera, species, values and habitability rulesets.
organic_region_data.py  Generated reference data: the galactic region grid and the named zones.
exobiology_overlay.py   The four overlay cards (bio status, biology, sample popup; radar via exo_radar.py).
exo_radar.py            The Bio radar's geometry (offsets, bearings, circles, little pointers) and drawing.
```

`organic_scan.py` has no screen code, no EDMC imports beyond the logger, and is unit-testable.

## 4. Inputs

| Source | What is used |
|---|---|
| `Scan` (a body) | Planet class, atmosphere type and its trace gases, surface gravity, temperature, pressure, volcanism, landable status |
| `Scan` (stars) and the arrival system | The system's main star type |
| `FSSBodySignals`, `SAASignalsFound` | Which genera are present on a body |
| `ScanOrganic` | The genus and species named at each stage (Log, Sample, Analyze) |
| `FSDJump`, `Location` | The system's own position (`StarPos`, in light years), for the region lookup |
| `Status.json` | Your surface latitude, longitude, heading and planet radius (the sample-distance check, the radar), and the body you are near (`BodyName`; absent once you have left it) |
| `Scan` (a body) | also `WasFootfalled`: false means nobody has set foot there, so the first footfall bonus is open |
| `SAASignalsFound`, `FSSBodySignals` | also the count of biological signals |
| `ScanOrganic` | also the color variant (`Variant_Localised`) and, with the position from `Status.json` at that moment, where each Log and Sample was taken |
| `CodexEntry` (organic structures) | the plant's name and latitude and longitude, kept as a waypoint |
| `Touchdown`, `Liftoff`, `LaunchSRV`, `DockSRV`, `Disembark`, `Embark` | where the ship touched down and where the SRV was launched or left |

Gravity is converted from m/s² to G and pressure from pascals to atmospheres, to match the data's units.

## 5. How a species is predicted

For each genus detected on a body, WNTB checks every species of that genus. A species has one or more
**rulesets** (alternative sets of conditions); the species is a candidate if **any one ruleset matches**.
A ruleset matches only if **every** condition it states is satisfied:

- atmosphere type, planet class, and ranges for gravity, temperature and pressure;
- the star type, and a specific system, where the data names one;
- volcanism required, forbidden, or of a named kind;
- the **galactic region** (a list of allowed and "not in" region groups);
- **Guardian proximity** (within range of a known Guardian nebula or site);
- a **trace gas** present above a given percentage;
- the **tuber zone** distance band (for the species that depend on it);
- that the system has a **co-located body** of a named type.

**Region lookup** is local: the system's `StarPos` is turned into a grid cell and looked up in a compact
table of the game's 42 named regions. No network call.

**Unknown never eliminates.** If WNTB doesn't yet know something (no position seen this session, no other
bodies scanned yet), that condition is skipped rather than failing. The result is deliberately
**conservative in one direction**: a species may show as a candidate a little more often than the real
game would allow, but a real candidate is never hidden.

Conditions the data describes but WNTB doesn't check (such as orbital period, parent star and the body's
own distance requirement) are simply not evaluated, which has the same effect: possibly an extra
candidate, never a missing one.

The candidates carry no likelihood: the data lists the species a body's conditions allow, not how common each is, so the overlay's percentages are an even share (100 divided by
the number of candidates) and the value range of an open genus is the lowest and highest of its candidates' values. A genus usually narrows to one species once enough conditions are known. A body holds at most one species
per genus, so the answer is a list per genus. A species with no usable rules in the data can't be
predicted and is never listed.

**Approximation to know about.** The star type used is the system's main (arrival) star. For a body
orbiting a secondary star in a multi-star system, that can be wrong.

### Color variants

`organic_scan.predict_variants(species, cond)` says which color a species would take on the body, from rules in `organic_variant_data.py` (generated by `scripts/gen_organic_variants.py` from SrvSurvey's `bio-criteria` files, GPL-3.0; see THIRD-PARTY-NOTICES.md): a genus or species follows the **class of the star** the body orbits (`star_class`: O to M, L, T, Y, TTS, Ae, W, D, N), or a **surface material** the body's Scan lists (`BodyConditions.materials`), or has one fixed color; a color can also need a kind of body. A species' own rule comes before its genus's, and the plants (Brain Trees, Anemones, Sinuous Tubers) have none. The star is the system's main star, as the rest of the prediction approximates it. `GenusView.variant_hint` carries the answer for the Biology card when every candidate agrees and no sample has named the color yet. `scripts/verify_organic_variants.py` checks the predictions against a commander's own journals (397 of 397 matched on 2026-10-16).

## 6. Scan progress and distance

A scan runs through three stages: **Log** (first sample), **Sample** (second, far enough from the first)
and **Analyze** (third, far enough from the second), and the third is the one that pays out. A
`ScanOrganic` event confirms the exact species (replacing the candidate list), sets its value, and moves
the stage on. Each genus has a **minimum distance** between samples (it varies by genus), and WNTB
measures your distance from the last sample using great-circle distance on the body's radius and tells you
when you've gone far enough. The **credit estimate** is the species' value from the data.

## 7. Persistence

Per commander, in `organic_scan_state.json` (in the plugin folder, listed in the updater's protected
files): each body's conditions, the genera detected, and each organism's confirmed species and progress.
Also kept per body: where each sample was taken, the color variant, the first footfall flag and the plant waypoints. A planet's biology doesn't reset when you log out, and a relog starts a new journal file that replays none
of the earlier scan events, so without this the picture would vanish. Moving to a different body resets
the live tracker, and returning restores the saved progress. When `Status.json` names no body (the commander has left the planet) the live view is
cleared in the same way, so the overlay cards stop showing a finished planet.

## 8. The reference data

`organic_species_data.py` and `organic_region_data.py` are **generated files, not to be hand-edited**: a
table of genera, species, values and rulesets, and the region grid with the Guardian and tuber zones.
They are a snapshot of community-measured game data (credited in `THIRD-PARTY-NOTICES.md`), so **a new
species added by a game update needs the tables regenerated**. Until then it simply can't be predicted.

## 9. Testing

`tests/test_organic_scan.py` covers the pure logic in `organic_scan.py` (the matching rules, region and
zone handling, scan stages and distances) without needing EDMC. `tests/exobiology_checks.py` (run by
`tests/test_exobiology_overlay.py` in its own process) covers the overlay cards, the radar geometry, the little
pointers, the waypoints and the per-body view built from journal events and `Status.json`. The panel itself is
exercised by hand in a live game, by visiting a planet with biological signals.

## 10. Known gaps

- Predictions are candidates, not answers, until a sample names the species.
- The main star is assumed to be the illuminating star.
- Some game rules in the data aren't evaluated (see §5).
- New species need the data regenerated.
- The Odyssey exobiology tools in the game itself remain the final word.
- A plant's position is known only from the Composition Scanner's codex entry, and genera whose codex names do not follow the usual pattern (such as Bark Mound)
  are not tracked.
- The color variant is not predicted, only reported once a sample or the Composition Scanner names it.
- The SRV's position is where the commander was when it was launched or left, not a reading of the SRV.

`organic_scan.display_species` writes a species as a scientific name (genus capitalized, species epithet in lower case, a color variant after a dash kept as is, the game's common names such as Bark Mound left alone); the per-body view, the sample popup, the Composition Scanner footer and the panel use it, while the stored names stay as the game wrote them.

## 11. The overlay view

`organic_scan_panel.overlay_view()` builds an `organic_scan.BodyView` from the controller's state without any widgets: for the body the commander is at, each
genus (`GenusView`: predicted candidates with values, the confirmed species and variant, the stage, the positions of the samples and the distance from the
last one), the first footfall flag, the biological signal count, the commander's position and heading, the ship and SRV positions, the genus in progress and
the plants identified and not yet sampled (`Waypoint`s of every genus, oldest first; `exo_radar.tracked` picks the latest of each genus). The cards in `exobiology_overlay.py` are built from it, and `exo_radar.py` turns the positions
into pixels (a flat-earth offset rotated to the heading, accurate over the few hundred meters of a sampling walk). The genus a codex name belongs to comes from
`organic_scan.genus_key_for_codex_name`. Each genus keeps `WAYPOINTS_PER_GENUS` plants. The Composition Scanner names a plant from a distance (from a ship or an SRV, a long way), and the journal gives where the *commander* was, not the plant, so a waypoint remembers what the commander was in (`organic_scan.scan_mode`, from `Status.json`'s `Flags` and `Flags2`: `foot`, `srv`, `ship` or unknown) and how far off it may be (`WAYPOINT_ERROR_M`: 40, 150, 250 and 150 m, estimates): the radar draws its ring that wide and the distances carry a `~` unless it was scanned on foot. A Log or Sample drops the waypoint of its genus nearest the commander within `WAYPOINT_MATCH_M` for that mode (100, 300, 450 and 250 m, plus `WAYPOINT_SAME_VARIANT_EXTRA_M`, 50 m, when the sample names the same color variant), or, with no position to go by, the plant identified last; the mode is saved with the waypoint (a fifth element, absent in older saves).
