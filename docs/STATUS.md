# Where things stand

Read this first when picking the project up on a machine that has not seen the recent work (for example the Linux test machine). It is
kept in Git because Git is the only thing shared between the Windows and Linux machines. Last updated 2026-10-13, on Windows.

## Releases

- **1.9.0** was released on 2026-10-13 (tag `v1.9.0`, from `master` at `f7170d6`). It is the version being tested now. On Windows it
  was installed by the in-app updater; Linux testing starts from the same automatic install.
- Everything listed under 1.9.0 in `CHANGELOG.md` is in it: the Surface Compass and Marks, Notes, Flight Alerts, the Trade Watch list,
  overlay default spots that no longer overlap, and the Colonization improvements.

## Branches (all pushed to origin)

| Branch | What it is for | State |
|---|---|---|
| `bugfix/1.9.1` | Fixes for bugs found while testing 1.9.0. Becomes release **1.9.1**. | 1.9.0 plus the documentation audit and the Linux checklist update. The version is still 1.9.0: it is bumped to 1.9.1 together with the first real fix. |
| `master` | The released code. | Equal to `v1.9.0`. |
| `feature/materials-engineering` | Planned **1.10.0**: engineering materials held, a blueprint browser with a wishlist and shopping list, engineers (including the four Colonia on-foot engineers, added by hand), and a material trader finder. | Built, with unit and window tests. **Not yet seen working in the game.** |
| `feature/expedition-planner` | Planned **1.11.0**: named expeditions of stops with notes, progress from arrivals, import from the plotted route or a CSV. | Same: built and tested, **not yet seen in the game**. |

The two feature branches were cut from `master` at 1.9.0 and do not contain each other. When they are merged, the engineering branch goes
first; each adds entries under "Unreleased" in `CHANGELOG.md`, which has to be placed by hand under its own version heading.

## Testing

- **Windows:** being tested by the project owner now, against the installed 1.9.0. Bugs found go to `bugfix/1.9.1`.
- **Linux:** next. The steps and the ordered list of what to check are at the top of `docs/LINUX_TESTING.md` ("Testing 1.9.0: start here").
  When reporting, give the distro, desktop, X11 or Wayland, native or Flatpak EDMC, and the relevant lines of EDMC's log
  (`~/.local/share/EDMarketConnector/EDMarketConnector.log`).
- The in-game checks for the two feature branches are in `docs/TODO.md`, which Git ignores on purpose: it only exists on the machine
  where it was written.

## Working rules for now

- **While 1.9.0 is being tested, commit only on `bugfix/1.9.1`.** This project's hook runs `npm run deploy` after commits, which copies
  the checked-out branch's build over the EDMC plugins folder. On a feature branch that would replace the 1.9.0 being tested.
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
