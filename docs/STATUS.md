# Where things stand

Read this first when picking the project up on a machine that has not seen the recent work (for example the Linux test machine). It is
kept in Git because Git is the only thing shared between the Windows and Linux machines. Last updated 2026-10-15, on Windows.

## Releases

- **Unreleased on `master`** (uncommitted, 2026-10-15, Windows only): history moved off the mode panels. Trade's Session page and the Colonization panel show the present only; the Credits Ledger window (click the Credits line) and the Colonization History window (HISTORY button) hold the past. Still to check on Linux: both windows open and fit, and the Credits line click works.
- **1.13.0** is the current release (2026-10-15, tag `v1.13.0`): progress for source-and-return missions from the hold (`36/60 held`) with bars and colour by progress in the Missions window and on the overlay, Notable Bodies and Discovery cards that show full names, and the Missions overlay card putting a long place on its own line. Tested on Windows only; the Linux checks are in `docs/LINUX_TESTING.md` section 6.
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

There is one long-lived branch, `master`, and it matches the 1.13.0 release. For a fix to a released version, cut a short branch from
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
- Guardian ruin surveying and landing-pad diagrams are out of scope (the journal lacks what they would need).
