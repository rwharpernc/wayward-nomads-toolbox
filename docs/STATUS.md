# Where things stand

Read this first when picking the project up on a machine that has not seen the recent work (for example the Linux test machine). It is
kept in Git because Git is the only thing shared between the Windows and Linux machines. Last updated 2026-10-14, on Windows.

## Releases

- **1.10.2** is the current release (2026-10-14, tag `v1.10.2`): long names in the main panel wrap instead of being cut off, the Colonization History heading names the commander, and the busiest site shows its name. Tested on Windows only; the Linux check is Materials and Expedition on a narrow window.
- **1.10.1** (2026-10-14, tag `v1.10.1`): the Expedition and Materials sections no longer widen the main panel on
  Linux. Tested on Windows.
- **1.10.0** (2026-10-14, tag `v1.10.0`) added Materials and Engineering (Field Ops), the Expedition planner
  (Exploration), the material trader finder, Spansh route buttons and system-name suggestions. Tested on Linux; see `docs/LINUX_TESTING.md`.
- **1.9.1** (2026-10-13, tag `v1.9.1`) held the fixes found while testing 1.9.0 on Windows and Linux.
- **1.9.0** (2026-10-13, tag `v1.9.0`) added the Surface Compass and Marks, Notes, Flight Alerts, the Trade Watch list, overlay default
  spots that no longer overlap, and the Colonization improvements.

## Branches

There is one long-lived branch, `master`, and it matches the 1.10.2 release. For a fix to a released version, cut a short branch from
`master` (for example `bugfix/1.10.3`), and merge it back.

## Testing

- **Windows:** being tested by the project owner, using the `master` build (`npm run deploy`). Bugs found are fixed on `master` or a short
  bug fix branch.
- **Linux:** the steps and the ordered list of what to check are at the top of `docs/LINUX_TESTING.md` ("Testing: start here"). When
  reporting, give the distro, desktop, X11 or Wayland, native or Flatpak EDMC, and the relevant lines of EDMC's log
  (`~/.local/share/EDMarketConnector/EDMarketConnector.log`).
- The in-game checks for Materials, Engineering and Expedition are in `docs/TODO.md`, which Git ignores on purpose: it only exists on the
  machine where it was written. The Linux versions are in `docs/LINUX_TESTING.md`.

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
