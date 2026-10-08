# WNTB (Wayward Nomads Toolbox): notes for Claude

EDMC plugin, Python in `plugin/`, Node build scripts in `scripts/`. See `docs/DEVELOPMENT.md` for setup,
`docs/TECHNICAL.md` section 18 for the platform matrix, and `docs/LINUX_TESTING.md` for the Linux checklist.

## Two dev installs, two platforms

This repo is checked out and tested natively on **both Windows and Linux**, and the two are worked on in
tandem. The only link between them is git (`origin`, branch `master`).

**First, find out which one you are on.** The session environment lists `Platform` / `OS Version`; use that,
not assumptions. Windows is the original dev install; Linux (CachyOS, fish shell) is the second.

- Say which platform a result or test run came from ("verified on Linux", "not yet checked on Windows").
  A pass on one OS says nothing about the other.
- Platform-specific code stays behind `platform_support` (`IS_WINDOWS`, `IS_LINUX`). Never call Win32,
  `powershell.exe`, or Windows-only Tk colour names outside the existing `IS_WINDOWS` branches.
- When a change touches platform behaviour (paths, overlay, screenshots, Auto-Honk, Tk widgets), finish by
  noting what still needs checking on the *other* platform.
- Run `git pull --rebase` before starting and push when done, so the other install picks it up. Keep commits
  small and don't commit machine-specific paths or logs.
- Linux-side test targets: EDMC plugins folder `~/.local/share/EDMarketConnector/plugins` (or the Flatpak
  equivalent), EDMC log `~/.local/share/EDMarketConnector/EDMarketConnector.log`.
- Known Linux issues (Settings panel display, overlays not always showing) are listed in `README.md`; record
  new findings in `docs/LINUX_TESTING.md` rather than here.
