# Where things stand

Read this first when picking the project up on a machine that has not seen the recent work (for example the Linux test machine). It is
kept in Git because Git is the only thing shared between the Windows and Linux machines. Last updated 2026-10-16, on Windows.

## Releases

- **1.17.2** is the current release (2026-10-17, tag `v1.17.2`; tested on Windows only): System targets can show the life and points of interest other commanders found in a system (an opt-in Spansh lookup, a Known section, and a status line while it asks), says whether you have been in a system before (a per-commander visit history built from your journals, `system_history.json`), and rebuilds a scanned system's survey from just the journals that hold your visits.
- **1.17.1** (2026-10-17, tag `v1.17.1`; tested on Windows only): the Route overlay shows system names up to 32 characters, the Body info, System targets and Bio signals cards keep room for a long name in their title, and the overlay guide covers streaming and recording.
- **1.17.0** (2026-10-16, tag `v1.17.0`; tested on Windows only): WNTB's **built-in overlay** (Windows, optional: a transparent window over Elite, no EDMCModernOverlay needed for WNTB's displays, with its own fonts (Source Sans 3 bundled, any `.ttf` or `.otf` added), cards sized from the measured text, a keep-showing option and Windows capture tools recognized, WNTB's displays in converted screenshots; EDMCModernOverlay stays for Linux and for other plugins' overlays, and the two can run together), **Nearest place to land** (Spansh, by position, the ship's pad, services, open fleet carriers), the **likely color** of a species before it is sampled (from SrvSurvey's data, checked against the owner's journals), tracked-plant marker rings and `~` distances by how the plant was scanned, the Bio radar's north mark, System targets ranked by mapped value with a whole-system biology count, a duplicate-overlay-window warning, and **overlay settings saved per commander** (cards on or off, placement and look). The in-game checks are in `docs/TODO.md` and the Linux ones in `docs/LINUX_TESTING.md`; the design of the built-in overlay and what is left are in `docs/NATIVE_OVERLAY_SPEC.md`.

- **1.16.0** (2026-10-16, tag `v1.16.0`): the System targets and Body info cards (with a saved per-commander survey of each system, an optional EDSM lookup, element symbols and formulas, mapped value and first footfall), the four Exobiology cards (Bio status, Biology with reward ranges, the Bio radar with a pointer for each genus, the Sample popup) with plant waypoints, species written as scientific names, the Expedition Log (archive, window, overlay card, Start since my last sale), a corrected scan value formula, a drag-and-drop layout editor on Overlay Placement, plain card panels, panel opacity, brighter and more legible overlay text, cards that reset when you leave a planet, and the Linux support note. Tested on Windows only; the Linux checks are in `docs/LINUX_TESTING.md` section 6 and `docs/TODO.md`. Known issues (doubled or ghosted overlay text from a second overlay window, all-capital text from the overlay's default font) are in `docs/guide/known-issues.md`. A new guide, `docs/guide/exobiology.md`, covers all of exobiology.

- **1.15.0** (2026-10-16, tag `v1.15.0`): the Route overlay (fuel, jump range, jumps left and the plotted route, with neutron stars and white dwarfs picked out), the running expedition and per-stop survey counts (bodies scanned, first discoveries, mapped) on that card and in the Expedition window, overlay text left-justified with one shared padding, no overlay text below the readable size (the Text size choice is Default or Larger), and new default overlay spots. Cards and route tracking were tested on Windows only; the Linux checks are in `docs/LINUX_TESTING.md` section 6.
- **1.14.1** (2026-10-15, tag `v1.14.1`): the Credits Ledger's Lifetime tab fills in again, and Rebuild from journals reports what it did. Windows only.
- **1.14.0** (2026-10-15, tag `v1.14.0`): history moved off the mode panels (the Credits Ledger window from the Credits line, the Colonization History window from HISTORY), the main panel no longer folds, fold sections start folded, Ship Builds folds, and bold page names in Mining and Trade. Tested on Windows only; the Linux checks are in `docs/LINUX_TESTING.md`.
- **1.13.0** (2026-10-15, tag `v1.13.0`): progress for source-and-return missions from the hold (`36/60 held`) with bars and color by progress in the Missions window and on the overlay, Notable Bodies and Discovery cards that show full names, and the Missions overlay card putting a long place on its own line. Tested on Windows only; the Linux checks are in `docs/LINUX_TESTING.md` section 6.
- **1.12.0** (2026-10-15, tag `v1.12.0`): the Missions window (replacing the All popup) with pinned missions, the Missions overlay card, Source commodities and Trade's Best picks, the Upgrade planner for Odyssey suits and weapons (with Read my gear), Megaship scans per Powerplay cycle, and the Ship planner's subtract-current-ship option. Tested on Windows only; the Linux checks are in `docs/LINUX_TESTING.md` section 6.
- **1.11.0** (2026-10-15, tag `v1.11.0`): the Ship planner (an EDSY or Coriolis build onto the wishlist), the Engineers tab with where each engineer is and how to
  unlock them and a Bubble / Colonia filter, engineering data corrected from EDDiscovery's tables, Settings → General → Help (**Report an issue** and **Copy
  diagnostics**), BGS rebuilding a period that closed while EDMC was not running, and finished Colonization builds shown without the "Construction Site:" prefix.
  Tested on Windows only; the Linux checks are in `docs/LINUX_TESTING.md` section 6.
- **1.10.2** (2026-10-14, tag `v1.10.2`): long names in the main panel wrap instead of being cut off, the Colonization History heading names the commander, and the busiest site shows its name. Tested on Windows only; the Linux check is Materials and Expedition on a narrow window.
- **1.10.1** (2026-10-14, tag `v1.10.1`): the Expedition and Materials sections no longer widen the main panel on
  Linux. Tested on Windows.
- **1.10.0** (2026-10-14, tag `v1.10.0`) added Materials and Engineering (Field Ops), the Expedition planner
  (Exploration), the material trader finder, Spansh route buttons and system-name suggestions. Tested on Linux; see `docs/LINUX_TESTING.md`.
- **1.9.1** (2026-10-13, tag `v1.9.1`) held the fixes found while testing 1.9.0 on Windows and Linux.
- **1.9.0** (2026-10-13, tag `v1.9.0`) added the Surface Compass and Marks, Notes, Flight Alerts, the Trade Watch list, overlay default
  spots that no longer overlap, and the Colonization improvements.

## Branches

There is one long-lived branch, `master`, and it matches the 1.17.2 release. For a fix to a released version, cut a short branch from
`master` (for example `bugfix/1.13.1`), and merge it back.

## Testing

- **Windows:** being tested by the project owner, using the `master` build (`npm run deploy`). Bugs found are fixed on `master` or a short
  bug fix branch.
- **Linux:** the steps and the ordered list of what to check are at the top of `docs/LINUX_TESTING.md` ("Testing: start here"). When
  reporting, give the distro, desktop, X11 or Wayland, native or Flatpak EDMC, and the relevant lines of EDMC's log
  (`~/.local/share/EDMarketConnector/EDMarketConnector.log`).
- The in-game checks for Materials, Engineering, the Ship planner and Expedition are in [`docs/TODO.md`](TODO.md), the public list of open work. The Linux
  versions are in `docs/LINUX_TESTING.md`.

## Working rules for now

- This project's hook runs `npm run deploy` after commits, which copies the checked-out branch's build over the EDMC plugins folder. On
  a branch that is not `master` that replaces the build being tested; the installed copy also does not move to a release until the
  in-app updater or a deploy from `master` puts it there.
- Ask before every commit, push, version bump, tag and release. Staging is fine without asking.
- `git pull --rebase` before starting work, and push when done. Do not commit machine-specific paths or logs.
- American English everywhere; no AI credit anywhere (see `CLAUDE.md`); everything saved about play is per commander
  (`plugin/commander_data.py`); files use LF line endings.
- Releasing is described in `docs/DEVELOPMENT.md` ("Releasing"). The repo is public, so the in-app updater can see releases.

## Decisions already made

- "Mactavious" stays as the second test commander in the tests; it is not to be stripped or renamed.
- Every online lookup is either opt-in in Settings or runs only when a button is pressed, and is listed in
  `docs/guide/internet-and-privacy.md`.
- Guardian ruin surveying, landing-pad diagrams and an FSS spectrum guide are out of scope (the journal lacks what they would need; the spectrum ranges are not in it and no open table of them exists).
