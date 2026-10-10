# Technical Specification — Organic Scanning

**Author:** R.W. Harper (CMDR Bocheaux)
**Last updated:** 2026-10-02 (see `CHANGELOG.md`)

The standing reference for Organic Scanning (exobiology): what it predicts, the rules behind the
prediction, how scan progress is tracked, and where its answers can be wrong. For how to use it, see the
[README](guide/exploration.md#organic-scanning). For how the code is organised in general, see
[TECHNICAL.md](TECHNICAL.md).

## 1. Goals

- Given the biological signals on a planet, say which **species** each is likely to be, from the planet's
  conditions.
- Track your **Log → Sample → Analyse** progress for each organism, and tell you when you've moved far
  enough from the last sample for the next one to count.
- Show the **credit value** of each species.
- Remember a body's biology across a relog or an EDMC restart.

## 2. Non-goals

- **No network access, and nothing submitted anywhere.** It is a local, read-only companion. It is meant
  to sit alongside the EDMC-Canonn plugin, which submits codex and biology data; WNTB does not duplicate
  that, and does not need it.
- **No first-discovery bonus.** Exobiology analysis pays a flat per-species value regardless of who found
  it first.
- **No certainty before a sample.** Until a scan names the species, the answer is a candidate list.

## 3. Architecture

All modules live in `plugin/`; `PANEL_PLACEMENT = "exploration"`.

```
organic_scan.py         Pure logic: BodyConditions, the matching rules, scan-stage tracking, distance.
organic_scan_state.py   Per-commander persistence of each body's biology (organic_scan_state.json).
organic_scan_panel.py   The panel: reads journal events, builds conditions, shows predictions and progress.
organic_species_data.py Generated reference data: genera, species, values and habitability rulesets.
organic_region_data.py  Generated reference data: the galactic region grid and the named zones.
```

`organic_scan.py` has no screen code, no EDMC imports beyond the logger, and is unit-testable.

## 4. Inputs

| Source | What is used |
|---|---|
| `Scan` (a body) | Planet class, atmosphere type and its trace gases, surface gravity, temperature, pressure, volcanism, landable status |
| `Scan` (stars) and the arrival system | The system's main star type |
| `FSSBodySignals`, `SAASignalsFound` | Which genera are present on a body |
| `ScanOrganic` | The genus and species named at each stage (Log, Sample, Analyse) |
| `FSDJump`, `Location` | The system's own position (`StarPos`, in light years), for the region lookup |
| `Status.json` | Your surface latitude and longitude, for the sample-distance check |

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

A genus usually narrows to one species once enough conditions are known. A body holds at most one species
per genus, so the answer is a list per genus. A species with no usable rules in the data can't be
predicted and is never listed.

**Approximation to know about.** The star type used is the system's main (arrival) star. For a body
orbiting a secondary star in a multi-star system, that can be wrong.

## 6. Scan progress and distance

A scan runs through three stages: **Log** (first sample), **Sample** (second, far enough from the first)
and **Analyse** (third, far enough from the second), and the third is the one that pays out. A
`ScanOrganic` event confirms the exact species (replacing the candidate list), sets its value, and moves
the stage on. Each genus has a **minimum distance** between samples (it varies by genus), and WNTB
measures your distance from the last sample using great-circle distance on the body's radius and tells you
when you've gone far enough. The **credit estimate** is the species' value from the data.

## 7. Persistence

Per commander, in `organic_scan_state.json` (in the plugin folder, listed in the updater's protected
files): each body's conditions, the genera detected, and each organism's confirmed species and progress.
A planet's biology doesn't reset when you log out, and a relog starts a new journal file that replays none
of the earlier scan events, so without this the picture would vanish. Moving to a different body resets
the live tracker, and returning restores the saved progress.

## 8. The reference data

`organic_species_data.py` and `organic_region_data.py` are **generated files, not to be hand-edited**: a
table of genera, species, values and rulesets, and the region grid with the Guardian and tuber zones.
They are a snapshot of community-measured game data (credited in `THIRD-PARTY-NOTICES.md`), so **a new
species added by a game update needs the tables regenerated**. Until then it simply can't be predicted.

## 9. Testing

`tests/test_organic_scan.py` covers the pure logic in `organic_scan.py` (the matching rules, region and
zone handling, scan stages and distances) without needing EDMC. The panel is exercised by hand in a live
game, by visiting a planet with biological signals.

## 10. Known gaps

- Predictions are candidates, not answers, until a sample names the species.
- The main star is assumed to be the illuminating star.
- Some game rules in the data aren't evaluated (see §5).
- New species need the data regenerated.
- The Odyssey exobiology tools in the game itself remain the final word.
