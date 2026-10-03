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
documentation in `docs/`. [TECHNICAL.md](TECHNICAL.md) section 2 has the full layout.

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
5. Update the README, the changelog and any affected docs in the same change.

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
