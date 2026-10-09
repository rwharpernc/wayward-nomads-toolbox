# Development guide

How to set up, build, test and try out changes to WNTB. If you just want to *use* the plugin, the
[README](../README.md) is what you want. For how the code is organised and why, read
[TECHNICAL.md](TECHNICAL.md) next.

## What you need

- **Python 3** (a recent version; the code uses modern type hints). The plugin itself runs inside
  EDMC's own Python, so you only need your own copy to run the tests and checks.
- **Node.js** (22.2 or newer), for the small build scripts (`npm run build`, `deploy` and `package`).
  Node is only used to copy and zip files. There is nothing to install with `npm install`.
- **[EDMC](https://github.com/EDCD/EDMarketConnector)**, to try the plugin for real.
- **Git**, to get the code and share changes.

## Get the code

```bash
git clone https://github.com/rwharpernc/wayward-nomads-toolbox.git
cd wayward-nomads-toolbox
```

The plugin source is the `plugin/` folder. Tests are in `tests/`, build scripts in `scripts/`, and
documentation in `docs/`. [TECHNICAL.md](TECHNICAL.md) section 2 has the full layout and [MODULES.md](MODULES.md)
names every module. Adding a module means adding its row there (a test checks).

## Build

```bash
npm run build      # copies plugin/ to dist/WNTB (plus LICENSE and THIRD-PARTY-NOTICES.md)
npm run package    # builds, then zips the contents of dist/WNTB into dist/WNTB.zip
```

`dist/` is ignored by git. The version number comes from `plugin/__init__.py` (and is mirrored in
`package.json`).

## Try your changes in EDMC

1. Run `npm run deploy`. It builds, detects which OS you are on, and merges the result into EDMC's
   plugins folder as `WNTB`:
   - Windows: `%LOCALAPPDATA%\EDMarketConnector\plugins`
   - Linux: `~/.local/share/EDMarketConnector/plugins`, or the Flatpak equivalent
     (`~/.var/app/io.edcd.EDMarketConnector/data/EDMarketConnector/plugins`), whichever exists
   - macOS: `~/Library/Application Support/EDMarketConnector/plugins`

   For a non-standard location, set `WNTB_PLUGINS_DIR` or pass `--plugins-dir <path>`
   (`node scripts/build.mjs --install --plugins-dir <path>`). `npm run build` alone just builds and
   prints where it would copy to.
2. Restart EDMC. It loads plugin code at start-up, so every change needs a restart.

**Merge the files; don't delete and re-copy the folder.** A live plugin folder also holds per-commander
data and plugin-managed files that aren't part of the build (saved hotspots, sessions, logs, backups,
downloaded updates). Overwrite the files the build produces and leave everything else alone.

Settings and window positions are stored in EDMC's own config, under keys starting `wntb_`.

## Working on Windows and Linux

The same repo is developed on both. Each machine builds and installs for itself, because the build
detects the OS and EDMC's plugins folder (see "Try your changes in EDMC" above).

**Setting up a fresh machine**

1. Install Python 3, Node.js 22.2 or newer, and Git. On Linux the Python Tk bindings are separate
   (Arch/CachyOS: `sudo pacman -S --needed tk nodejs npm`). Without Tk the UI tests and the import
   smoke test fail with `libtk8.6.so` errors.
2. Clone the repo, then run `git config core.autocrlf false` inside it. The `.gitattributes` keeps
   everything LF; leaving `autocrlf` on can fight it.
3. Set your Git name and email for the repo (`git config user.name` / `user.email`).
4. Check it works: `python -m unittest discover -s tests`, `python tests/import_smoke.py`,
   `npm run build` (the first line should name the right OS) and `npm run package`.

**Day to day**

- Before starting on a machine: `git pull`. Before switching machines: commit and `git push`.
- `npm run deploy` builds and copies into EDMC's plugins folder for that OS. Restart EDMC after.
- EDMC on Linux may be a Flatpak. Its log is
  `~/.var/app/io.edcd.EDMarketConnector/data/EDMarketConnector/logs/EDMarketConnector-debug.log`
  (on Windows: `%TEMP%\EDMarketConnector\EDMarketConnector-debug.log`). Check it first when something
  works on one OS and not the other.
- Not synced by Git (ignored on purpose): `.claude/`, `docs/roadmap.md`, `docs/TODO.md`, `dist/`. Copy local notes
  between machines yourself. `CLAUDE.md` is committed (it holds the two-machine guidance for both installs).

**Keep code portable**

- Don't use Windows-only Tk values such as `SystemWindow` colour names, and don't call `powershell.exe`
  or Win32 APIs outside the existing `IS_WINDOWS` branches. Use `platform_support` helpers.
- Keep the Windows and Linux code paths behind `platform_support` (`IS_WINDOWS`, `IS_LINUX`) and say so in
  the feature's Settings tab with a **Works on:** note (see `platform_support.input_support_note`).
  Full list of what each OS does: [TECHNICAL.md section 18](TECHNICAL.md#18-platform-support-windows-and-linux).
- File names: use the game's exact case (`Status.json`), match journals as `Journal.*.log`, always pass
  `encoding=` to `open`, and take the name from a journal `Filename` with `screenshot_naming.journal_basename`
  (Elite writes backslashes even under Proton).
- New modal dialogs: use `ui.style.grab_when_visible(dialog)`, not `dialog.grab_set()` (X11 refuses a grab
  before the window is mapped).
- Text symbols in the UI: stick to ones every font has (`×`, `★`, `→`, `▾`).
- Settings tabs: never `pack` anything into an `nb.Frame`. EDMC's `myNotebook.Frame` puts a gridded spacer
  child inside every instance, so packing into it raises, EDMC logs `Failed for Plugin "WNTB"` and the whole
  WNTB Settings tab disappears. Use `grid`, or pack into a plain `tk.Frame`. `tests/test_settings_layout.py`
  checks the source and `tests/test_prefs_smoke.py` builds the whole tab with EDMC-faithful stand-ins.
- Where a new feature's Settings go: `ui._build_settings_tabs` lays the tabs out (General, Powerplay, Missions,
  Exploration, Mining, Trade, BGS, Field Ops, Always On). Add the feature to the right group there. A feature with a
  `build_settings` that isn't listed still gets a tab, under "Other". To put two small pages on one tab, wrap
  them with `_stacked_page`: each feature's `build_settings(notebook)` keeps working unchanged, because the
  stack accepts `add(frame, text=...)` like a notebook does.
- `monitor.logfile` (EDMC) is a `str` or a `pathlib.Path` depending on the version: wrap it in `str()` before
  comparing it or saving it to JSON.
- Background threads must never touch a Tk widget; hand results back with a queue and `after()`.
- A bug that makes a Settings tab vanish usually means an exception while building it. EDMC catches it
  and logs `Failed for Plugin "WNTB"`, so look for that line.

## Test

```bash
python -m unittest discover -s tests
```

The tests cover the pure-logic modules (parsing, state, estimates, data handling). They don't need EDMC
or a display, because EDMC's `config` module is stubbed inside the tests. There is also a smoke test that
imports every module:

```bash
python tests/import_smoke.py
```

Two guards worth knowing: `tests/test_prefs_smoke.py` builds every Settings tab (it hard-codes the number of
top-level tabs, so adding a tab means updating it), and `tests/test_own_data_files.py` fails if a module defines a
data file (`*FILENAME = "x.json"`) that `plugin/update.py` doesn't list in `_OWN_DATA_FILES`.

Screens and windows aren't covered by automated tests. For those, build, copy and click through the
feature in EDMC. [TECHNICAL.md](TECHNICAL.md) section 14 explains what is and isn't tested and why.

## Making a change

1. Keep logic that doesn't need the screen in its own module with no EDMC or Tk imports, so it can be
   unit-tested. [TECHNICAL.md](TECHNICAL.md) section 6 explains the split.
2. Follow the feature-module contract when adding a feature (section 4, with a checklist in section 16).
3. Anything that can size the main window (images, long text) needs a fixed upper bound on every
   dimension. Section 5 explains why.
4. Prefix config keys and overlay ids with `wntb_<feature>_`.
   Any new network call must follow the API-usage rules in
   [TECHNICAL.md](TECHNICAL.md#keeping-api-traffic-low): opt-in or user-triggered, cached, capped, with a
   timeout, and identified through `http_identity.user_agent()`.
5. Update the README, the changelog and any affected docs in the same change, including a row in
   [MODULES.md](MODULES.md) for any new module.

### Using other people's work

Write code fresh, in your own way. Before using any code, asset or data from another project, check its
licence. WNTB is GPL-3.0, so anything added must be compatible with that. If a licence asks for a
notice, add it to [../THIRD-PARTY-NOTICES.md](../THIRD-PARTY-NOTICES.md). Credit for ideas goes in
[ATTRIBUTIONS.md](ATTRIBUTIONS.md). Please don't copy code from a project that has no licence, since
that means you have no permission to.

## Releasing

To release: bump the version in `plugin/__init__.py` and `package.json`, add a dated section to
`CHANGELOG.md`, run `npm run package`, commit, tag `v<version>`, and publish `dist/WNTB.zip` as
the asset of a GitHub release. Users download that zip, not the repository. Publish it as a normal release:
the in-app updater (and the README's "latest release" link) only follow official (non-draft,
non-pre-release) GitHub releases.
