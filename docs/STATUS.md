# Where things stand

Read this first when picking the project up on a machine that has not seen the recent work (for example the Linux test machine). It is
kept in Git because Git is the only thing shared between the Windows and Linux machines. Last updated 2026-10-13, on Windows.

## Releases

- **1.9.1** is the current release (2026-10-13, tag `v1.9.1`). It holds the fixes found while testing 1.9.0 on Windows and Linux: the
  Colonization card watching `Market.json`, an off-canvas overlay position falling back to its default, the Text size choice, the
  layout fixes for large fonts, and the troubleshooting additions. Both fixes that came from Linux were confirmed on Windows.
- **1.9.0** (2026-10-13, tag `v1.9.0`) added the Surface Compass and Marks, Notes, Flight Alerts, the Trade Watch list, overlay default
  spots that no longer overlap, and the Colonization improvements.

## Branches

There is one long-lived branch, `master`, and it is ahead of the 1.9.1 release. The feature branches and `bugfix/1.9.1` are merged and
deleted. For a fix to a released version, cut a short branch from `master` (for example `bugfix/1.9.2`), and merge it back.

`master` holds, under "Unreleased" in `CHANGELOG.md`, two pieces of work that no release has yet:

- **Materials and Engineering** (Field Ops): the engineering materials you hold, a blueprint browser with a wishlist and shopping list,
  engineers (including the four Colonia on-foot engineers, added by hand) and a material trader finder.
- **The Expedition planner** (Exploration): named expeditions of stops with notes, progress from arrivals, import from the plotted route
  or a CSV.

Both are built, with unit and window tests, and neither has been seen working in the game on either OS. The next release will be a minor
version (1.10.0) once they have been tried in the game; place the "Unreleased" entries under that heading at release time.

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
