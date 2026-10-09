# WNTB Technical Guide

How Wayward Nomads Toolbox works, and why it's built that way. This is a learning and reference
document: it explains the design decisions, including the mistakes that produced some of them. For
what each feature does for the user, see the [README](../README.md). For features in depth, see the
specifications: [Missions](MISSIONS_TECH_SPEC.md), [Mining](MINING_TECH_SPEC.md),
[Trade](TRADE_TECH_SPEC.md), [Boxel Survey](BOXEL_SURVEY_TECH_SPEC.md), [BGS](BGS_TECH_SPEC.md),
[Organic Scanning](ORGANIC_SCANNING_TECH_SPEC.md), [Powerplay](POWERPLAY_TECH_SPEC.md) and
[Screenshots and input automation](SCREENSHOTS_AND_INPUT_TECH_SPEC.md). For setting up on-screen
overlays, see [OVERLAY_SETUP.md](OVERLAY_SETUP.md). For acknowledgements, see
[ATTRIBUTIONS.md](ATTRIBUTIONS.md); for licence notices, see
[THIRD-PARTY-NOTICES.md](../THIRD-PARTY-NOTICES.md).

**Contents**

1. [Where WNTB runs](#1-where-wntb-runs)
2. [Repository layout, build and deploy](#2-repository-layout-build-and-deploy)
3. [Startup and event flow](#3-startup-and-event-flow)
4. [The feature-module contract](#4-the-feature-module-contract)
5. [Keeping the main window from growing](#5-keeping-the-main-window-from-growing)
6. [Pure logic versus UI](#6-pure-logic-versus-ui)
7. [Threading and network calls](#7-threading-and-network-calls)
8. [Persistence](#8-persistence)
9. [Journal, Status.json and CAPI](#9-journal-statusjson-and-capi)
10. [The overlay](#10-the-overlay)
11. [External services](#11-external-services)
12. [Feature notes](#12-feature-notes)
13. [Self-update](#13-self-update)
14. [Testing](#14-testing)
15. [Gotchas](#15-gotchas)
16. [Adding a feature](#16-adding-a-feature)
17. [Known gaps](#17-known-gaps)
18. [Platform support: Windows and Linux](#18-platform-support-windows-and-linux)

---

## 1. Where WNTB runs

WNTB is not a program. It is a plugin loaded into **EDMC** (Elite Dangerous Market Connector), a
Python/Tkinter desktop app that watches the game's journal files and lets plugins react to them.
Three consequences shape almost everything below:

- **EDMC owns the process, the window and the event loop.** WNTB never starts its own Tk root or
  main loop. It receives a parent frame and fills it.
- **EDMC calls WNTB; WNTB doesn't poll.** The game writes journal events, EDMC reads them, and EDMC
  calls the plugin's hooks. Status.json and CAPI data arrive through separate hooks (section 9).
- **The main window is shared.** Every installed plugin lives in the same window (section 5).

EDMC discovers a plugin by finding `load.py` in a folder under its `plugins` directory. It then calls
a fixed set of module-level functions if they exist.

## 2. Repository layout, build and deploy

```
plugin/           everything that ships; becomes the WNTB folder
  load.py         EDMC entry point (the hooks)
  ui.py           main panel, mode buttons, Settings tab: orchestration only
  panelkit.py     shared Tk helpers (wrapping, separators, toggles, tooltips, collapsible sections, theming)
  overlay.py      the one shared overlay client
  update.py       the one self-updater
  <feature>*.py   one or more modules per feature (every module is listed in MODULES.md)
tests/            unittest suites for the pure-logic modules
scripts/          build.mjs, package.mjs
docs/             this file, the development guide, the feature specs, the overlay guide, acknowledgements
```

[MODULES.md](MODULES.md) lists every module with a one-line description; `tests/test_docs_modules.py` keeps it complete.

`npm run build` copies `plugin/` to `dist/WNTB`, skipping `__pycache__` and `.pyc`, and also copies
`LICENSE` and `THIRD-PARTY-NOTICES.md` into it. `npm run package` zips that folder, keeping the
`WNTB/` folder as the zip's top level so extraction produces a ready-to-copy folder.

**Why Node for a Python project?** The scripts only copy files and call a zip tool, and `package.json`
gives a memorable `npm run build` entry point. There is no Python packaging step because EDMC loads
plugin source directly.

**Why the license files are copied into the build:** WNTB is GPL-3.0 and carries some third-party
data whose notices must accompany it. Copying at build time means the notices travel with every
installed copy, not just the repo.

To try a build in EDMC, copy `dist/WNTB` into EDMC's plugins folder as a *merge*, never
delete-then-copy, because a live plugin folder holds per-commander data files that are not in the
build (section 8). EDMC must be restarted to load the new code. See [DEVELOPMENT.md](DEVELOPMENT.md).

## 3. Startup and event flow

`load.py` implements EDMC's hooks:

| Hook | When EDMC calls it | What WNTB does |
|---|---|---|
| `plugin_start3(plugin_dir)` | Once, at load | Starts stateful features, wires the shared overlay client into each overlay feature, registers overlay groups, starts the update check |
| `plugin_app(parent)` | When building the main window | `ui.create_plugin_app(parent)` builds the panel |
| `plugin_prefs(parent, cmdr, is_beta)` | When Settings opens | Builds the WNTB Settings tab |
| `prefs_changed(cmdr, is_beta)` | When Settings is saved | Each feature persists its settings |
| `journal_entry(...)` | For every journal event | Forwards to every feature (below) |
| `dashboard_entry(cmdr, is_beta, entry)` | Whenever Status.json changes | Forwards flags and position to the features that need them |
| `capi_fleetcarrier(data)` | When fleet carrier CAPI data arrives | Inventory only |
| `plugin_stop()` | EDMC closing | Flushes state, closes the overlay connection |

### Forward unconditionally, gate inside

`journal_entry` does one thing:

```python
for feature in _FEATURES:
    feature.handle_event(entry, cmdr, system, station, state)
```

Every feature receives every event and decides itself whether it cares and whether it is enabled.

**Why not route events by type in `load.py`?** Because then `load.py` would need to know which events
each feature reads, and adding or changing a feature would mean editing a central file. Calling every
handler is cheap: each returns after a dictionary lookup or two. The cost is a few microseconds per
event. The benefit is that `load.py` never changes when a feature does. The one rule that makes this
safe is that handlers only *read* `entry` and `state`; none mutate them, so handler order doesn't
matter.

## 4. The feature-module contract

Every feature module exposes the same small interface, which `ui.py` and `load.py` rely on:

| Name | Purpose |
|---|---|
| `PANEL_PLACEMENT` | A mode key (`"exploration"`, `"mining"`, ...) to build inside that mode's frame; `"always"` to build once outside any mode; or `None` for a Settings-only feature |
| `build_panel(parent)` | Build the main-window widgets (skipped when placement is `None`) |
| `build_settings(notebook)` / `save_settings()` | Build and persist this feature's Settings tab |
| `handle_event(entry, cmdr, system, station, state)` | React to journal events |

Larger features add `start(plugin_dir)` and `stop()` for loading and flushing state, and optionally
`set_overlay_client(client)`.

**Why a contract instead of `ui.py` building everything?** A `ui.py` that every feature reaches into
tends to grow into a thousand-line file. With the contract, `ui.py`
stays a thin orchestrator: it walks the `FEATURES` tuple, builds each feature into its own child
frame with a separator between, and never learns feature internals. Adding a feature means writing
one module and adding it to two tuples (`FEATURES` in `ui.py`, `_FEATURES` in `load.py`).

**Why `panelkit.py` exists.** Feature modules import `panelkit`, never `ui`. If a popup window imported helpers back out of
`ui.py`, that would create a circular dependency. Putting shared, content-agnostic helpers in a third module that both sides import breaks that cycle
by construction.

**Stacking and pairing.** `ui._stack_features` gives each feature its own frame and inserts a
separator between consecutive ones. Earlier, features picked their own grid rows, which produced a
real row-collision bug and a "too jumbled" visual report. Frame-per-feature removes the possibility.
A small `_SIDE_BY_SIDE_PAIRS` table puts two narrow features (Auto-Honk and Discovery Alerts) in one
row to save vertical space. That one row also carries the N.S. and W.D. buttons (built by `discovery.py`)
and Boxel Survey's RND button (`boxel_survey.build_random_button`, called from `ui.py` with
`discovery.controller.button_row`, so it stays usable while Boxel Survey is collapsed). Every button there
is packed with the same 6px gap as the mode buttons; the N.S./W.D. result line and RND's status line sit
below the row.

**Short button names and tooltips.** The EDMC window is small and shared, so main-panel buttons use
abbreviations (the table is in the README's "Button names"), and `panelkit.add_tooltip` shows the full name on
hover. The tooltip is a borderless `Toplevel`, so it can't affect the main window's size. The mode buttons use
`ui._MODE_BUTTON_TEXT`; their tooltips (`ui._MODE_TOOLTIPS`) give the full name and a one-line description, and `PANEL_MODES` keeps the full labels for the "coming soon" placeholder. EDMC sizes its window to the widest row across all plugins, and the mode row used to be WNTB's widest, so the mode row is held at the size measured from a throwaway row of full-label buttons (`ui._mode_row_full_label_size`), with the short buttons centered inside it; without that the shortened labels made EDMC open far narrower. Don't implement this with a thin spacer widget in the same grid cell: it draws a line across the buttons.

**Settings layout.** `ui._build_settings_tabs` builds nine top-level Settings tabs: General (Overlay
Connection, Window, Updates), Powerplay, Missions, Exploration, Mining, Trade, BGS, Field Ops and Always On
(Interdiction, Landing). A group is a plain tab holding its own `nb.Notebook` (`_settings_group`). In
Exploration, GEC, Canonn and Codex share one "Points of Interest" page and Auto-Honk and Discovery share an
"Alerts" page: `_SectionStack` is an `nb.Frame` whose `add()` grids each feature's frame one under the other,
so features still call `notebook.add(frame, text=...)` unchanged. Everything is placed with `grid`. Features
not listed fall into "Other" rather than losing their tab. A group page adds about 53px for its tab strip,
and the tallest page (Alerts, 632px, in the Exploration group) now sets the Settings window height.

**Height fitting.** Once a window has an explicit size, Tk stops fitting it to its content. `ui._sync_mode_holder_height` is the single place the panel's height changes (mode switch, startup, a section expanding), and it schedules `ui._fit_window_height` once at idle: it sets the top-level window's geometry to its current width and the height its content requests (`winfo_reqheight`), so a taller mode is never cut off. It is skipped when the window is maximized, minimized or not yet visible, and keeps the width and position. The Settings → Window tab has a checkbox (`wntb_fit_window_height`, default on) that turns it off; that tab is built with `grid` only, per the Settings rule in the development guide.

**Collapsible sections.** `panelkit.collapsible_section` gives GEC Nearby POI, Canonn Nearby POI and Codex
Completionist a clickable ▸/▾ title over a body frame, collapsed unless the saved flag
(`wntb_gec_poi_collapsed`, `wntb_canonn_poi_collapsed`, `wntb_codex_completionist_collapsed`) says otherwise.
Boxel Survey keeps its own equivalent (`wntb_boxel_collapsed`)

**Modes.** `PANEL_MODES` in `ui.py` is the ordered list of mode buttons. Each mode has its own frame.
Switching modes shows one frame and hides the others (`grid_remove`), so it never destroys or
rebuilds widgets. Hidden modes keep receiving journal events (section 3), which is why nothing
pauses when a mode isn't on screen.

## 5. Keeping the main window from growing

**The problem.** EDMC sizes its main window to the widest row among *all* loaded plugins. One plugin
that lets external content set a widget's width widens the window for the whole app, including every
other plugin's panel. For example, a thumbnail capped by height only lets an ultrawide screenshot
produce a very wide image.

**The rule.** Any widget in the main window whose size comes from variable data must have a hard
upper bound on *every* dimension that affects layout.

**Session strip.** Directly under the mode buttons (a frame at row 2 of the main frame, with a separator at
row 3) are two lines shown in every mode; only the master collapse toggle hides them. Each is a feature
module of its own, independent of Powerplay and of each other:

- `game_mode.py`: "You are in Solo mode." (Open / Solo / Private Group with its name). Set from `LoadGame`'s
  `GameMode`/`Group`, recovered on `StartUp` (EDMC attached to a running game, no journal replay) by reading
  the `LoadGame` line from the top of the current journal file, cleared on `Shutdown`.
- `session_credits.py`: "Credits this session: +N cr earned (+R cr/hr)" or "-N cr lost". It keeps its own
  record of the current session (login balance, balance now, journal file, commander) in
  `session_credits.json`, read from `LoadGame`'s `Credits` and EDMC's `state["Credits"]` on every event.
  The same journal file and commander is one session (a logout to the menu and back, or an EDMC restart,
  continues it); anything else starts a new one. Writes are throttled to one per 30 s plus start and stop.

Both are registered in `load.py`'s `_FEATURES` for journal events (and `session_credits` in start/stop) and
built into the strip by `ui.py`. Text builders and session logic are pure functions with tests
(`tests/test_game_mode.py`, `tests/test_session_credits.py`); the labels are `panelkit.wrap_label`s, so a
long number or private-group name wraps instead of widening EDMC's window. `session_credits.json` is on the
updater's keep-list. Powerplay no longer knows about either: its session store has no credit fields (old
`sessions.json` files keep theirs, ignored).

**Switching modes must not change the width.** Every mode's content sits in one holder in `ui.py` whose
width is pinned to the mode-button row's, and whose height follows whichever mode is showing, so the
window never grows or shrinks as you switch. Content wraps to that width instead of asking for more.
Two traps to remember: a bare `tk.Canvas` asks for 10 cm (about 378 px) of width, so scrolling panels
(Mining, Missions) set `width=1` and stretch instead; and the panel's feature frames put spare space in
their second column, so a panel with a scrollbar column must give that column weight 0.
`tests/test_panel_width.py` guards both.

How that plays out:

- **Text from the game or journal** (station names, system names, faction names) is unbounded. Use
  `panelkit.wrap_label`, which creates a label whose `wraplength` tracks its container's width but
  never drops below `MIN_WRAP` (300 px). A long name wraps instead of stretching the window. The
  top-level frame's `<Configure>` event calls `panelkit.on_frame_configure` to update all of them.
- **Images** are resized into a fixed box, on both axes, before display. `screenshots.py` defines
  explicit max width and height constants for the inline thumbnail (a genuine two-dimensional box),
  the history thumbnails and the preview popup, and hands them to
  `screenshot_convert.thumbnail_photo_data`. Bounding only one axis and letting the other follow the
  source's aspect ratio is exactly the failure this rule exists to prevent.
- **Overlay-drawn or canvas content** uses fixed sizes decided in code, never derived from data (for
  example the Rhino coverage minimap is a fixed square).

Ask of every new widget: *what is the worst-case size of this content, and where is the cap?*

### External windows (`plugin/uikit/`)

Every external (Toplevel) window uses WNTB's own dark look rather than EDMC's theme; main-window
panels still follow EDMC. See `docs/WINDOW_FRAMEWORK_SPEC.md`. The rules that matter when touching
one:

- **Never change ttk globally.** ttk themes and stock styles (`TButton`, `Treeview`, ...) are
  application-wide, so `theme_use()` or restyling them would recolour EDMC's main window and every
  other plugin. The kit uses classic tk widgets plus its own `FlatButton`, `Combobox`,
  `SlimScrollbar`, `Tabs`, `ProgressBar` and `DataTable` (a Label grid, not a Treeview).
  `tests/test_ui_kit.py` fails if `plugin/uikit` touches the ttk theme or styles.
- **Shell.** `ui.shell.WindowShell` gives a Toplevel a header (title, subtitle, action buttons), a
  body, a wrapping status footer, a minimum size and saved geometry. It never touches EDMC config:
  the window passes `load_geometry`/`save_geometry` callables. Windows are built hidden and shown
  once, after their content is laid out (`_present`), so they never flash at a default size. Windows keep the module-level
  `show`/`refresh`/`close` singleton convention.
- **Skinning.** `ui.style.skin(window)` colours the classic widgets created inside a Toplevel via
  Tk's option database, scoped by the window's own *name* (option patterns match names, not full
  paths). Call it right after creating the Toplevel, before adding widgets. Explicit `fg=`/`bg=`
  still win, which is how status colours work. Don't also call `theme.update()` on these windows.
- **Tables.** `DataTable` mirrors the small part of Treeview the windows used (`insert`, `append`,
  `set`, `exists`, `clear`, `selection`, double-click) and adds sorting, `group=True` collapsible
  headings, and `visible_rows` (fit to content up to N rows). A bare `tk.Canvas` requests 7 cm of
  height, which silently props up whatever contains it: give canvases an explicit height.
- **Display scaling.** Default and minimum window sizes are written in 96-dpi pixels and multiplied
  by `ui.style.dpi_factor` inside `WindowShell`; keep new layouts expressed that way.
- **Width discipline.** Displayed text goes through `ui.widgets.clip` / per-column `max_chars`.

## 6. Pure logic versus UI

Most features split into layers:

```
xxx.py / xxx_tracker.py    pure logic, no Tk, no network        -> unit-testable
xxx_state.py               JSON load/save
xxx_client.py              network calls, no Tk
xxx_panel.py               Tk widgets, wiring
xxx_window.py / _dialog.py popups
```

Examples: `bgs_tracker.py` (pure parsing and tallying) versus `bgs_panel.py` (widgets and polling);
`organic_scan.py` versus `organic_scan_panel.py`; `boxel.py` and `boxel_walker.py` versus
`boxel_survey.py`.

**Why.** Tk code can't run in a plain test, and EDMC-only imports (`config`, `theme`, `myNotebook`)
don't exist outside EDMC. Keeping logic free of both means it can be tested with `unittest` without
launching anything, and bugs in rules (name parsing, merit math, species matching) get caught by a
test run rather than by playing.

Where a logic module needs only EDMC's `appname` for a logger, it uses a fallback so tests can import
it:

```python
try:
    from config import appname
except ImportError:
    appname = "EDMarketConnector"
```

## 7. Threading and network calls

**Rule: Tkinter is not thread-safe.** Only the main thread may touch widgets. Slow work (HTTP) must
not run on the main thread either, or EDMC freezes while waiting. So network features use one
pattern (see `canonn_poi_panel.py`, `boxel_survey.py`, `bgs_panel.py`):

1. A button click bumps a **generation counter**, then starts a daemon `threading.Thread`.
2. The worker does the network call and puts `(generation, result)` onto a `queue.Queue`.
3. The main thread polls the queue with `widget.after(200, ...)`.
4. On each result, the poller compares its generation to the current one and **drops stale results**.

**Why a generation counter?** If a user clicks Find twice, or changes commander or system while a
lookup is in flight, the first lookup's result would arrive later and overwrite the newer state. The
counter makes "latest request wins" cheap and correct. Each new request invalidates all earlier ones.

**Why `after()` polling instead of calling back from the worker?** A callback from the worker thread
would run *on* the worker thread, and touching Tk from there can crash or corrupt the UI. The queue
hands data across the thread boundary safely; `after()` runs the consumer on the main thread.

The updater follows the same rule: it works in a thread, then calls back with a plain version string,
and `load.py` schedules the UI change with `frame.after(0, ...)`.

Trade mode (`trade_panel.py`) uses two simpler variants of the same rule, because each has exactly one
consumer. A lookup is a `_Job`: a daemon thread that fills in `result`/`error` and sets `done`, which an
`after(500)` poller on the Tk thread reads; only one job runs at a time and **Cancel** sets a
`threading.Event` the worker checks while it waits. The startup journal read for carrier cargo puts one
result on a `queue.Queue` that the Tk thread merges. Neither touches a widget from the worker, and there is
no generation counter because a second request can't start while one is running. If a feature can have
several requests in flight, use the generation counter above instead.

## 8. Persistence

### Two kinds of storage

- **EDMC's `config`** (EDMC's own settings store) holds small settings and toggles: booleans, ints,
  strings. Every key is prefixed `wntb_<feature>_...`, which avoids collisions with EDMC and other
  plugins and lets one look-up show everything WNTB owns. There is deliberately no legacy-key
  compatibility layer.
- **JSON files in the plugin folder** hold real data: sessions, hotspot catalog, survey log, BGS
  tallies, visited systems, ship builds. Examples: `sessions.json`, `boxel_state.json`,
  `region_sweep_state.json`, `waypoint_route_state.json`, `visited_systems.json`, `survey_log.json`,
  `organic_scan_state.json`, `codex_completionist_state.json`, `bgs_state.json`, `powerplay_state.json`,
  `mining_hotspots.json`, `mining_coverage.json`, `ship_builds.json`, `colonisation_sites.json`,
  `trade_ledger.json`, `trade_carrier.json`, `trade_stock.json`, `trade_history.json`. `codex_catalog.json` is a cache of a downloaded list rather
than commander data, but it is protected from updates the same way.

**Why files instead of `config`?** `config` is for settings, not structured or growing data. JSON
files are inspectable, easy to back up and easy to hand-repair. The tradeoff is that data lives beside
the code, so deleting the plugin folder deletes it. Section 13 covers how updates avoid that.

### Per-commander keys

Data that belongs to a commander is stored as `{ "<commander>": {...} }` in one file. The commander
name keeps its original casing on disk but is matched case-insensitively (`casefold`). **Why:**
players can have several commanders, and their surveys, tallies and hotspots must not mix. Matching
case-insensitively avoids a duplicate entry if the journal reports the same name with different
casing.

Trade's carrier records and per-commander carrier choice take this a step further: they are keyed by the
*casefolded* name (`trade_carrier.key_for`), because a real journal was seen writing `BOCHEAUX` where EDMC
supplies `Bocheaux`. The list of commanders seen is kept in one config key (`wntb_trade_commanders`) so the
Settings tab can offer a choice for each, since Settings can't ask the game who your commanders are.

### Atomic writes

State is written to `path.tmp`, then `os.replace(tmp, path)`. **Why:** if EDMC is killed or the
machine loses power mid-write, a plain overwrite can leave a truncated, unparseable file. `os.replace`
is atomic on the same volume, so the file is always either the old version or the new one. Loads treat
an unreadable or wrong-shaped file as "nothing saved" and log a warning instead of crashing at
startup.

### Bounded growth

Data that would otherwise grow forever is capped (for example `sessions.json` keeps the most recent
200 sessions). Derived numbers aren't stored when they can be recomputed: Powerplay stores raw
merits per activity and computes Control Points at display time from the current ratio settings, so
correcting a ratio retroactively fixes old sessions' estimates.

## 9. Journal, Status.json and CAPI

Three different data sources reach WNTB through three different hooks.

- **Journal events** (`journal_entry`): discrete things the game logs, such as `FSDJump`, `Scan`,
  `Docked`, `MissionCompleted`. Most features run on these.
- **Status.json** (`dashboard_entry`): a live snapshot the game rewrites about once a second. It is
  the only place to get continuous position (latitude and longitude, used for Mining's surface bearing
  and coverage map) and the flags bitmask (used for the earliest interdiction signal). Position and
  flags are not journal events, so features that need them can't be driven by the journal alone.
- **CAPI** (`capi_fleetcarrier`): Frontier's authenticated web API, delivered by EDMC on a throttle.
  Only used for fleet carrier locker contents.

### Catching up on state EDMC missed

Two situations mean a feature can start with an incomplete picture:

- **EDMC starts while the game is already running.** EDMC synthesizes a `StartUp` event. Features
  that need current state (current system, region, active mining run) handle it by reading the
  current journal file backward for the last `FSDJump` or `Location`.
- **The player relogs.** A relog creates a new journal file that does *not* replay earlier
  `FSSBodySignals`, `Scan` or `ScanOrganic` events. So Organic Scanning persists per-body state to
  disk (`organic_scan_state.json`) rather than relying on the journal to re-tell it.

- **A job that spans play sessions.** Trade's working session belongs to a commander and lasts until Reset, across logins,
  journal files and EDMC runs. When EDMC next sees the commander it catches the session up from the journal files written
  since the last event it counted (`trade_ledger.catch_up`), through the same code the live events use, and only adds:
  every event is idempotent (`already_counted`, by time and fingerprint), so replays and live repeats can't double count.
- **A baseline event that is only written on request.** `CarrierStats` (the fleet or squadron carrier's
  cargo space) is written only when the Carrier Management screen is opened, and EDMC does not replay it when
  it starts. Trade mode therefore replays the newest 40 journal files on a background thread at startup,
  parsing only the few event names it needs, to find the last baseline and the transfers after it (about 0.03 s
  on a real journal folder). See the [Trade spec](TRADE_TECH_SPEC.md#7-fleet-and-squadron-carrier-cargo-space).

Some things are deliberately *not* automatic. Codex Completionist's "Backfill from Journal History" (BKF)
is a button because reading years of journal files is real I/O; it does no work until asked.

### Reading journals defensively

Fields the game documents poorly are handled conservatively. Interdiction Warning combines three
signals (Status.json flag, NPC `ReceiveText` taunts restricted to `Channel == "npc"`, and the
authoritative `Interdicted`/`EscapeInterdiction` events) because they arrive via independent
callbacks with no ordering guarantee. The channel gate exists because squadron and system chat are
other commanders casually typing words like "pirate" with no interdiction happening.

## 10. The overlay

Overlay features (Landing, Interdiction, Discovery, Inventory bars, Mining, Screenshots) draw over the
game window through a separate helper app, **EDMCModernOverlay** (recommended) or the older **EDMCOverlay**, which listen
on a local TCP port. WNTB is only a client.

**Every overlay switch defaults to off.** The Inventory, Landing and Screenshots overlays used to default on; on the first
start after that change `load._reset_overlays_once` sets every switch in `_OVERLAY_ENABLE_KEYS` to off, once, recorded by the
`wntb_overlay_reset_v1` config key, before any feature reads its settings. A new overlay switch must be added to
`_OVERLAY_ENABLE_KEYS` and default to off.

**Protocol.** Connect, send one JSON object plus a newline per graphic, for example
`{"id": "x", "text": "hi", "color": "red", "x": 200, "y": 100, "ttl": 4}`. Nothing is read back; sends
are fire-and-forget. WNTB's protocol notes come from observed behaviour.

### One shared, persistent connection

`overlay.OverlayClient` holds a single connection open for the plugin's lifetime and reconnects
lazily if it drops.

**Why persistent?** The overlay server tags every graphic with the ID of the connection that sent it,
and *wipes all of a connection's graphics the moment it disconnects*, regardless of each graphic's
`ttl`. Connect-send-close would make everything vanish immediately. So the connection must stay open
as long as its graphics should be visible.

**When no overlay is running.** After a failed connection the client fails new sends immediately for 30
seconds (`COOLOFF_S`) instead of trying again, so a user with no overlay program costs almost nothing:
no thread waiting on a connection per pickup, screenshot or Mining update. The failure is logged once at
INFO, and a changed host or port is applied straight away. The Settings test buttons build their own
client, so they always try for real, and the Overlay Connection tab (Settings → General) has a **Check connection** button.

**Why one for everything?** A connection per mode would duplicate work, and each would need its own
reconnect logic.

Connect timeout is 1 second. It's a loopback connection to an app that is either running (instant)
or not (fails fast); a long timeout would stall journal processing waiting for an app that isn't
there.

### Plugin Groups (EDMCModernOverlay)

EDMCModernOverlay groups a feature's shapes and text so they scale and anchor as one unit.
`overlay.register_modern_overlay_groups` takes `(group_name, id_prefix)` pairs, so each feature
supplies its own without `overlay.py` naming any feature. Registration is best-effort: it silently
does nothing if ModernOverlay isn't installed, and swallows errors, because a cosmetic nicety must
never break startup.

**Why every card registers a group.** Without a group, a card's background rectangle can render
invisible under ModernOverlay, and registering one fixes it, so every card-style overlay registers one.
(The tempting rule "don't group a single rectangle behind narrower text" was tried and turned out to be
wrong.) The general point: when overlay rendering seems wrong, check ModernOverlay's own payload and
debug log before assuming a rule is right, and don't turn one observation into a permanent blanket rule.

Overlay message IDs use `wntb_<feature>_*` so a group's prefix matches exactly its own shapes.

## 11. External services

| Service | Used for | Trigger |
|---|---|---|
| EDSM | Nearby systems, "does EDSM know this system", bodies, ring reserves | Buttons; some opt-in automatic checks |
| Spansh | Mining price finder, hotspot and boxel lookups, ELW rarity, rare-goods origin Power, nearest neutron star / white dwarf (N.S./W.D.), Trade routes and best-price searches | Buttons; opt-in; the Rares window looks up on open |
| edastro.com (GEC) | Nearest exploration POI | Button only |
| Canonn sheets | Thargoid and Guardian site lists | Button; downloaded once per session |
| tick.infomancer.uk | BGS tick time | 60-second poll; can be turned off |
| GitHub Releases | Update check | Opt-in, once per EDMC run |

Design decisions that apply to all of them:

- **API endpoints only, never HTML.** Scraping is fragile and impolite. Every call goes to a
  documented API or a published data file.
- **Degrade to "no result", never crash.** `edsm_client.py` says so in its docstring: any failure
  (offline, service down, unexpected shape) returns an empty result. A network feature failing must
  not break journal handling. The BGS tick client is the deliberate exception: it *raises*, and the
  caller decides, because a fabricated or stale tick would corrupt the tally. It never returns a
  guessed value.
- **Identify WNTB in every request.** Every call sends a User-Agent naming WNTB, its version and the
  project's address (`http_identity.py`, for example `WNTB/1.0.0 (rare-goods; +https://github.com/...)`),
  so a service operator who sees the traffic can tell what it is and get in touch. EDSM returns HTTP 403
  to the default `python-requests` agent, so its client sends EDMC's own `config.user_agent` followed by
  WNTB's.
- **Respect documented limits.** EDSM's `cube-systems` caps edge length at 200 ly; WNTB uses 100 as a
  middle ground between catching a few procedural systems and keeping responses small.
- **Opt-in by default, and stated.** Anything that phones home on its own is off until enabled.
  The README lists which features make network calls.
- **Bundle no service data.** Live queries mean nothing goes stale in the release and no service's
  content is redistributed. The exceptions are static game facts (section 12).
- **Plain HTTP for the tick API.** That is the only address the service offers. It carries a public
  timestamp and nothing sensitive.

### Keeping API traffic low

WNTB is a small, volunteer-made tool that leans on services other volunteers run, so it is built to ask
for as little as it can. These are the measures that are in the code today.

**Nothing runs in the background by default, apart from three small exceptions.**
- Every lookup is started by a button or is opt-in (off until enabled in Settings). That covers the
  Mining lookups, the Exploration Value extras (Spansh and EDSM), the Boxel Survey skip checks and
  alias confirmation, Region Sweep's auto-discover, and the update check.
- The exceptions: the BGS tick poll, one small request a minute to the tick service while BGS is on
  (it can be switched off); the Codex Completionist catalogue, downloaded when you open its details
  window and the saved copy is missing or over 14 days old; and the Rare Goods window, which looks up
  each origin system the first time you open it (see below).

**Remember answers instead of asking again.**
- Rare Goods: a system's controlling Power is cached for the whole EDMC session, and failed lookups
  are cached too, so a dead network isn't hit on every redraw. Lookups run at most 5 at a time.
- Canonn site lists are downloaded once per session. The Codex catalogue is saved on disk
  (`codex_catalog.json`) and reused for 14 days.
- The automatic ring-reserve check (opt-in) is remembered per ring for the session, and is never run
  while the journal is being replayed at start-up.
- Earth-like-world rarity is remembered per system for the session, and EDSM upload status per
  system for 10 minutes, so re-selecting the same target costs no extra calls.
- The Boxel Survey keeps a local log of systems you've visited, so the RND (Random) button never spends an
  EDSM call on a system it already knows you've been to.

**Hard limits on how much one click can do.**
- A skip-check run (Sequence mode) makes at most 20 EDSM lookups. RND makes at most 20, and at
  most 3 per anchor system. Sequence's automatic "nearest real system" suggestion happens only in
  response to your own clicks, at most once per 3 **Next** clicks in a row with no jump.
- EDSM nearby-system queries use a 100 ly cube, half the documented 200 ly maximum.
- Reordering a Waypoint Route uses one bulk coordinate request for the whole list, not one per system.

**One at a time, and no retry loops.**
- Each lookup carries a generation number, so a newer request supersedes an older one and a stale
  result is dropped. Region Sweep's auto-discover only fires when the queue is nearly empty, and only
  one lookup is ever in flight (so at most one per jump).
- A failed request returns "no result" and is not retried. The only repeat is the BGS tick's next
  scheduled poll, a minute later.
- Every request has a timeout (8 to 60 seconds), so a slow service never leaves a request hanging.
- Trade's route search is the one lookup that polls: Spansh queues a job and WNTB asks for the result every
  5 seconds, for at most 4 minutes (about 48 requests), then gives up. It stops at once on **Cancel**. A
  Near me or Galaxy price search is two requests per press (stations, then fleet carriers; one if carriers are
  hidden), because carriers are priced so differently that in one list they can fill the page.

**Fewer calls by design.**
- The Rare Goods list is bundled, with EDSM coordinates and Inara and Spansh ids looked up once, so
  those aren't requested at runtime. The exobiology and region tables are bundled for the same reason.
- Only documented APIs and published data files are used, never page scraping.

**If you add a network call,** follow the same rules: opt-in or user-triggered, cache what you can,
cap what one action can do, set a timeout, and identify WNTB with `http_identity.user_agent()`.

**Support the services.** These services are funded by their authors and their supporters. If WNTB is
useful to you, please consider supporting them as I do: [EDSM](https://www.patreon.com/EDSM), [Spansh](https://www.patreon.com/cw/spansh) and [Inara](https://www.patreon.com/cw/artieinara).

## 12. Feature notes

Short explanations of the non-obvious decisions in each area. Filenames are in `plugin/`.

### Powerplay (`powerplay.py`, `session.py`, `store.py`, `formulas.py`, `powerplay_ledger.py`, `powerplay_state.py`, `powerplay_backfill.py`, `powerplay_systems_tab.py`)

The journal's `PowerplayMerits` event reports what you earned, after every game multiplier. It does
not say how many Control Points that is; that depends on the activity, and Frontier hasn't documented
it. So the merit-per-CP ratios are **user-editable settings**, not constants, because they are
community estimates that Frontier retunes. Sessions are tied to the journal file, so a logout to the
menu and back, or an EDMC restart mid-game, continues the same session instead of splitting it. A
"last merit timestamp" high-water mark lets a journal rescan tell an already-counted gain from one
missed during an EDMC restart.

**Rare Goods Finder** (`rare_goods.py`, `rare_goods_window.py`, `powerplay_control_lookup.py`,
`rare_goods.json`). Rare-good origins never move, so the 141-entry dataset (coordinates, Inara id and
Spansh id64 included) ships as a static file and the "nearest" calculation is plain 3D distance from
the latest `StarPos` the Powerplay controller saw. Only the origin system's controlling Power changes
(weekly), so that alone is fetched live from Spansh's `system/<id64>` endpoint on a small thread
pool. Results are cached per process, including failures, so a redraw or a dead network never
re-requests; the window marshals results back onto the Tk thread and drops any that belong to a
superseded refresh.

### Boxel Survey (`boxel*.py`, `region_sweep_*.py`, `waypoint_route*.py`, `edsm_client.py`)

Procedural system names have a fixed shape: sector words, a cube id, a mass letter, and a sequence
number. WNTB parses that string well enough to step forward and back and to build the next candidate
name; the galaxy map then confirms whether it exists. It deliberately does **not** decode names into
coordinates, which needs Frontier's id64 math. That decision was tested: an "increment the cube
number" shortcut was built and then reverted because it produced candidates nowhere near the player.

Spatial adjacency therefore comes from a real source. EDSM's `cube-systems` query, centered on the
journal's `StarPos`, supplies nearby real systems. Region Sweep never invents a "next cube" itself; it
only tracks completion for cubes it was given by a typed seed, EDSM or Spansh. **RND** (Random) asks EDSM
for a known boxel nearby, hunts inside it for a name EDSM has no record of, and checks a local
per-commander visited-systems log first, because EDSM sync can lag or a commander may not upload, so
a system you already visited could otherwise come back as "new". Details and open questions are in the [Boxel Survey spec](BOXEL_SURVEY_TECH_SPEC.md).

### Exploration Value (`exploration_value.py`, `elw_rarity_spansh.py`)

Estimates the scan payout from the formula the community has reverse-engineered (a per-planet-class
constant, a terraforming bonus, a mass exponent and a first-discovery multiplier). Only *scan* value
is estimated; mapped value needs extra correlation and was scoped out. System age needs no formula:
a star's `Scan` event already carries `Age_MY`. The region readout is a local lookup on `StarPos`
against a coordinate grid with no network call.

### Discovery Alerts (`discovery.py`)

Uses fields the journal already carries. On arrival the game auto-scans the star (`ScanType:
"AutoScan"`); its `WasDiscovered` is `False` if nobody has scanned it. Any `Scan` has its own
`WasDiscovered`. `SAAScanComplete` has no flag, so whether you are first to map is taken from the
*previous* `Scan` event's `WasMapped` for the same body, cached per body and cleared on system change
so a stale entry can't leak into the next system. It stays silent in the common already-discovered
case: it's a celebration, not a status readout.

### Notable Bodies (`notable_rules.py`, `notable.py`)

`notable_rules.py` is pure (no EDMC or Tk imports): a table of `Rule`s, each a function of one `Scan`
event plus the other scans already seen in the system (`bodies`, by `BodyID`), returning a one-line
detail or `None`. `evaluate()` runs the enabled rules and never raises on a malformed event. Units are the
journal's own: metres, seconds, m/s^2. The rules and limits are Elite Observatory's defaults
(`DefaultCriteria.cs`, MIT): landable above 29.4 m/s^2 (about 3 g), landable radius above 18,000 km, rotation
or orbit under 8 h, eccentricity above 0.9, 5 of 6 premium FSD materials on a landable, ring wider than 5x the
body's radius, orbit under 3x the parent's radius, a shepherd moon is one orbiting inside the *outermost*
ring's outer edge, and a close or colliding binary is a pair sharing a barycentre whose radius/semi-major-axis
is above 0.4 for both (colliding when their periapsis distances are less than their radii). A high-value body is any terraformable or any Earth-like, water or ammonia world, landable or not
(its detail says "undiscovered" or "unmapped" from `WasDiscovered` and `WasMapped`). Fast rotation
and fast orbit apply to planets only here (a neutron star spins in milliseconds), and fast rotation skips
tidally locked bodies. Green gas giants are matched on planet class plus a table of confirmed surface
temperatures (+/-0.001 K), from community research credited in THIRD-PARTY-NOTICES.md.

`notable.py` follows `discovery.py`. `NotableTracker` keeps the current system's scans keyed by `BodyID`
(reset on a new `SystemAddress`), and when a body arrives it also re-judges the already-scanned bodies that
orbit it, since a moon is often scanned before its parent. `(BodyID, rule)` pairs alert once. One card per
body, with the first rule's label as the title and `+N` for more. Cards show for 6 s; three can wait and the
rest are only counted ("(N more)"). Title and name are capped (28 and 24 characters) because the card's
centring maths estimates text width from character count. Rule choices are saved as a JSON dict in
`wntb_notable_rules`; a rule missing from it uses its default, so a later release can add rules without a
migration. There are 15 rules, 7 on by default. A body matching several rules gets one card (first label
plus `+N`). The feature has no panel widget, only a Settings page (Exploration → Alerts).

### Nearest neutron star / white dwarf (`neutron_finder.py`, buttons in `discovery.py`)

The **N.S.** and **W.D.** buttons ask Spansh's `bodies/search` for the nearest system whose *primary* star is
a neutron star or a white dwarf. The filters are `subtype` (`Neutron Star`, or the 14 `White Dwarf (xx) Star`
classes, which Spansh lists separately) and `is_main_star: true`, sorted by distance, with the origin given as
`reference_coords` taken from the journal `StarPos`, so it works from a system Spansh has never seen. The
request shape was worked out from live calls (Spansh doesn't document it); `neutron_finder.py` is the one place
to fix if it changes. It asks for two results so it can skip the commander's own system. The lookup runs on a
worker thread with a result queue polled via `after()` (same as the GEC panel), is manual only, copies the full
system name to the clipboard, and truncates the displayed name (`MAX_NAME_CHARS`) so a long name can't widen
the window. `tests/test_neutron_finder.py` covers the result-picking against canned responses.

### Organic Scanning (`organic_scan*.py`, `organic_*_data.py`)

Predicts species per body from atmosphere, gravity, temperature, pressure, region and other rules,
and tracks the Log, Sample, Analyse progression plus how far you must walk between samples. It
shows estimated credits (a flat per-species value; there is no first-discovery bonus for
exobiology). It is a local, read-only companion to EDMC-Canonn and submits nothing.

The two `*_data.py` files are **generated** and marked "do not hand-edit", so a new species is a
regeneration, not a hand transcription that could silently introduce errors. Region lookup holds the
game's 42 region boundaries as a coordinate grid indexed from an origin offset. See the
[Organic Scanning spec](ORGANIC_SCANNING_TECH_SPEC.md).

### Mining (`mining_*.py`)

- **Runs** are bounded by `Undocked` and `Docked` (space) and `LaunchSRV`/`DockSRV` (surface). This
  is coarser than "from first prospector to next jump" but more reliable: that alternative fragments
  one stop at a ring into several runs whenever the player supercruise-hops.
- **Deposit estimate** (`mining_deposit.py`) turns Rigs count plus the HUD's Amount and Density
  readings into a *range* of tons, not a number, because the bands come from measured depletion
  traces, not a documented formula (125-175 t per rig position x a Density factor of High 1, Medium 2,
  Low 3). Density readings are entered on trust; unknown values widen the range rather than guess.
  Rigs is capped at 7 in the hotspot dialog. While the Rhino is out, each `MiningRefined` ton is
  credited to the nearest positioned hotspot within 200 m (`Hotspot.mined_tons`, written on a 5 s
  throttle and on shutdown), so a Depleted deposit reads "depleted (612 t)". Saving a hotspot from
  the panel within 100 m of an existing one on the same body updates it instead of adding a second.
- **Windows** (`plugin/uikit/`, `mining_ledger.py`) use WNTB's own dark look - see "External
  windows" in section 5. The Mining Book (`mining_ledger.py`, data in
  `mining_ledger_data.py`) is the browser for scanned bodies and saved hotspots.
- **Your own rates** (`mining_ground.py`): no third-party dataset is bundled or downloaded. The
  journal never reports what a surface deposit holds, so `OwnRates` tallies the commander's saved
  hotspots per kind of ground: "of the deposits you recorded on this kind of body, what share were
  this material", with the sample size shown. `classify(PlanetClass, Volcanism)` maps a scanned body
  to a ground key (rocky bodies split on volcanism, tested before anything else; "silicate magma"
  before "silicate"). A hotspot saved from the panel is stamped with `Hotspot.ground` when its body
  is in the current system's survey; older or imported ones count via the survey while their body is
  scanned, and are skipped otherwise. Only recorded deposits count, so treat it as "what I have found
  so far", not what a body holds. The Mining Book hides the section until something is recorded.
- **Minimap markers** are colour-blind-safe: pale filled dot = live hotspot, hollow grey ring =
  depleted, blue outlined dot = you. In the ship (no Rhino out) the map shows only under 2 km
  altitude, from Status.json's `Altitude`.
- **Coverage** (`mining_coverage.py`) paints a fixed-radius disc at each recorded point. It records
  where the Rhino has *driven*, not what has been scanned, because nothing in the journal or
  Status.json says a scan happened. The module says so, and the UI shouldn't claim otherwise.
- **Bearing** (`mining_bearing.py`) computes the relative bearing to a saved hotspot from live
  Status.json position and draws an overlay arrow.

### Trade (`trade_*.py`)

Full detail is in the [Trade spec](TRADE_TECH_SPEC.md); the decisions worth knowing here:

- **Profit uses the game's own number.** `MarketSell` carries `AvgPricePaid` (what the sold tonnes cost), so
  profit is `TotalSale - AvgPricePaid x Count` with no stock-lot bookkeeping; stolen cargo has `AvgPricePaid` 0.
  Running costs (fuel, repairs, rearm, limpets) are summed from the journal's cost events and subtracted to give
  a net figure; insurance rebuys and fines are not included.
- **Names go through one resolver.** Spansh's market search is case-sensitive and exact, and the journal's
  plural ("Void Opals") finds nothing where the list's "Void Opal" works. `trade_commodities.resolve` maps
  typed text, journal names and internal symbols to Spansh's exact name, from a table generated off FDevIDs;
  Mining's price finder uses it too.
- **Offers are ranked for your load**, not by price per tonne: `price x min(tonnes, demand)`. A station
  paying more per tonne but wanting 40 t is worth less to a 200 t hold.
- **Pad filtering is client-side.** Stations your ship can't dock at are dropped after the search (so a
  filtered search asks for 40 stations, not 20). Unknown ship or missing pad data means "don't filter", never
  a guess. Carriers always fit and are listed apart because they can move.
- **History is saved on request, from a richer ledger.** The live ledger keeps a bounded log of every trade and cost
  with its station, plus jumps and the starting balance; **Save session** snapshots it (and the stock, hold and carrier) into
  `trade_history.json`, re-saving the same session (however many logins it spans) updates the same record, and `trade_stats.py` works out every figure and
  table row so the Trade History window (`trade_history_window.py`) only lays them out. Totals are exact; the log can be
  shorter on a very long session.
- **Unsold stock is one book, not two trackers.** `trade_stock.py` follows cargo bought and not yet sold per
  commander across logins, with average cost; a carrier-loading run and a station-to-station run are the same
  thing to it (buys add, sells remove, carrier transfers change nothing). It applies each event once using the
  last-event time plus fingerprints of same-second events, and catches up at start by replaying recent journals
  synchronously, before any live event.
- **A transfer goes to the carrier you are docked at.** `CargoTransfer` doesn't name one; `Docked`/`Location`
  carry the station's `MarketID`, which equals the carrier's `CarrierID`. Docked at someone else's carrier,
  nothing is counted; with two carriers and no dock information, the transfer is skipped rather than guessed.
- **The page is blocks, not text.** Each page is a list of typed blocks (`trade_blocks.py`) drawn by `BlockView`
  (`trade_view.py`), so headings, label/value rows and number columns are real layout instead of text padded with spaces.
  The builders are pure and testable, and an unchanged page isn't redrawn. See the Trade spec for the sizing rules.
- **The page arrows** are the shared `panelkit.nav_arrow` (a raised, bordered, padded label with a large bold
  glyph), also used by Mining and Missions, because the bare triangles they replaced were too small to see in
  EDMC's small window.

### Missions (`missions*.py`, `mission_*.py`, `active_missions.py`, `kill_missions.py`, `all_missions.py`, `kill_tracker.py`)

Data-layer modules keep per-commander state and announce changes through `Notifier` objects
(`notifier.py`); derived views and the UI subscribe to them. That avoids the data layer importing UI code. A bounded lookback
journal scan (`journal_scan.py`, two weeks) restores missions on startup: long enough to catch
anything still active, short because missions expire.

### BGS (`bgs_*.py`)

Pure logic: `bgs_tracker.py` parses journal fields; `bgs_ledger.py` (`TickLedger`) holds one tick
period's per-faction snapshots (pre-tick `before` and latest `now`) and activity, and runs identically on
live events and on a replay of journal files (`bgs_journal.py`). Trade and exploration credit are
attributed to the *station's* faction, which spans two events (`Docked`, then the market event), so the
ledger carries that context. `bgs_format.py` is the shared wording. The tick client polls every 60
seconds; a new tick archives the closed period (kept for the "archive days" setting) and starts a fresh
one, and the current period is rebuilt from the journals once per session. See the
[BGS spec](BGS_TECH_SPEC.md).

### Field Ops (`screenshots*.py`, `screenshot_*.py`, `inventory*.py`, `ship_builds*.py`, `colonisation*.py`)

Screenshots convert the game's raw file into a renamed PNG on the `Screenshot` event, with a
crop chosen by which HUD panel had focus. Inventory works out which vehicle you are in
(ship, on foot or SRV) purely from `Embark`, `Disembark`, `LaunchSRV` and `DockSRV`, because EDMC
only tracks on-foot versus not, and micro-resource names resolve through a
bundled table, then names learned from the journal, then a title-cased fallback. Ship Builds is a
per-commander list of URLs to builds designed elsewhere; WNTB doesn't design loadouts.

Colonisation (`colonisation.py` is pure logic, `colonisation_data.py` the repository, `colonisation_panel.py`
and `colonisation_window.py` the UI) is built on two journal events. `ColonisationConstructionDepot` is an
authoritative snapshot of a depot's `ResourcesRequired`, so it replaces the stored list wholesale;
`ColonisationContribution` only carries the amounts just handed over, so it advances `provided` between
snapshots (clamped to `required`). Neither event names the station, only a `MarketID`, so the name is
remembered from the latest `Docked` for that market and never overwrites one already known. Names in these
events are decorated (`$steel_name;`) while `state["Cargo"]` is plain (`steel`), so both go through
`commodity_key` before being compared. The repository only saves when a site really changed, because
re-docking re-sends an identical snapshot.

### Auto-Honk (`autohonk.py`)

Reads the commander's active Elite binds file to find which physical key the chosen fire button is
bound to, then simulates that key being held for a configurable time. On Windows that is
`user32.keybd_event` through `ctypes`, which avoids an extra dependency. On Linux it is `xdotool`
(section 18). Each platform's calls are behind an explicit platform check because EDMC itself runs
on more than Windows.

## 13. Self-update

`update.py` is the single updater for the whole plugin: one version number, one GitHub Releases
target.

Flow, all off the main thread: check the latest non-draft, non-prerelease release; compare versions
numerically (padded to equal length so `1.2` versus `1.2.0` compares correctly); download the zip;
back up the current install; unpack over it; tell the UI to show "restart to apply".

Design decisions:

- **Opt-in.** Auto-update is off unless enabled in Settings. A `disable-auto-update.txt` file in the
  plugin folder forces it off regardless, a handbrake for a folder you're hand-editing.
- **Staged, not hot-reloaded.** Python modules already imported can't be safely swapped in a running
  process. Files are replaced on disk and take effect at the next EDMC start.
- **Data survives updates.** The updater only writes files that are *in the release zip*. Data files
  aren't in the zip, so they are never overwritten. `_OWN_DATA_FILES` and `_OWN_DIRS` add a second
  layer: they keep listed data out of the pre-update backup and out of unpacking. Keep them in sync
  when adding a data file (section 16).
- **Backups.** The last three (`BACKUPS_KEEP`) are kept as timestamped zips.
- **Failure is quiet.** A failed check or download logs and returns; it never interrupts play.

## 14. Testing

```bash
python -m unittest discover -s tests
```

Suites cover the pure-logic modules: procedural name parsing and sequence walking (with real boxel
data used to cross-validate), region-sweep queues, waypoint routing, survey log, Canonn data
parsing, organic species matching, Codex tallying, deposit estimates and Rhino coverage. Test files
add the repo root to `sys.path` and import `plugin.<module>` directly, which works because those
modules avoid EDMC-only imports (section 6).

Trade mode's logic is covered by `tests/test_trade.py` and `tests/test_trade_search.py` (ledger, market
parsing, Spansh response parsing, commodity names, ship pads, offer ranking, carrier cargo tracking and the
journal backfill). `tests/test_own_data_files.py` reads the sources and fails if any plugin module defines a
`*FILENAME` data file that is missing from `update.py`'s `_OWN_DATA_FILES`.

`tests/test_import_smoke.py` additionally imports every plugin module (including `load.py`) with
EDMC's modules stubbed, in a subprocess, to catch import-time breakage that single-module tests miss.

Trade mode's drawn page and its History window are the Tk exceptions:
`tests/trade_history_window_smoke.py` opens the History window the same way and visits every tab. The drawn page: `tests/trade_view_smoke.py` draws it in a real window with EDMC
stubbed, in a subprocess (skipped when there is no display), and checks widths, redraws and column alignment.

Not covered by automation: anything else that needs a live EDMC or a Tk window (panels, dialogs, overlay
rendering). Those are checked by hand in a real EDMC install, and overlay rendering changes should
be verified against ModernOverlay's own payload log.

## 15. Gotchas

Things that cost time once and are recorded so they don't again.

- **Themed widgets take `foreground=`, not `fg=`.** EDMC's `nb.Label` is ttk-backed. Passing the
  classic `fg=` raises `TclError: unknown option "-fg"`. One such label broke WNTB's *entire* Settings
  window, because the error aborted building the whole tab.
- **`theme.update()` may silently do nothing.** During `plugin_app`, EDMC's theme registry is still
  empty and `theme.update(widget)` returns early without registering. Separately, it only recolors
  direct children. `ui.py` therefore retries `panelkit.apply_theme_deep` at 0.5, 1.5, 3 and 6
  seconds, walking the whole subtree.
- **Clipboard needs `update()`.** After `clipboard_append`, `panelkit.copy_to_clipboard` calls
  `update()` so ownership actually transfers before focus returns to the game. Without it, a paste
  can grab stale content.
- **Separator color is set statically** from a light-or-dark choice, not read back through the
  theme, for the same registry-timing reason as above.
- **A package beats a same-named module.** The window kit is `plugin/uikit/`, not `plugin/ui/`,
  because `ui.py` (the main-panel builder) already exists; a `ui/` directory silently replaced it and
  EDMC reported `module 'WNTB.ui' has no attribute 'create_plugin_app'`. `tests/test_ui_kit.py` and
  `tests/test_import_smoke.py` guard this. Also: the deploy is a merge-copy that never deletes, so
  renaming or removing a module leaves the old one in the installed plugin folder - delete stale
  files there by hand.
- **ttk is global.** Anything that changes a ttk theme or stock style from a window affects the whole
  EDMC process. Namespaced style names (`WNTB.X.Treeview`) are safe; stock ones are not.
- **Tk option patterns match widget names**, not paths: `.!toplevel3*Label.background` is read as an
  application name and silently matches nothing.
- **A `tk.Label` can't take a tuple `padx`** (only `pack`/`grid` can); indent with spaces instead.
- **Case in commander and system names.** Store the original, compare with `casefold()`.
- **Never assume order between Status.json and the journal.** They are independent callbacks.
- **A label that spans columns can stretch them.** In a Tk grid a widget spanning columns 1 to 3 that is wider than
  those columns' combined width widens them, so a title column sized for the narrower layout overflows the window. Work
  out the width each column really needs (the wider of the table's numbers and any spanning value) before giving the
  title column the remainder; `tests/trade_view_smoke.py` catches it.
- **A price-sorted list can be all fleet carriers.** Carriers sell very cheaply and pay very well, so a
  galaxy-wide search sorted by price returned only carriers and the panel said no station had it. Ask for stations
  and carriers separately with the `type` filter (`trade_prices.STATION_TYPES` / `CARRIER_TYPES`).
- **Spansh market names are exact and case-sensitive.** "Liquid oxygen" works, "Liquid Oxygen" returns zero
  results with no error, and the journal's own plurals can differ from Spansh's. A search that silently finds
  nothing is the symptom; resolve every name through `trade_commodities.resolve`.
- **Journal files don't sort by name.** The game has used two file-name styles
  (`Journal.2026-10-09T053605.01.log`, `Journal.260228162446.01.log`), so "the newest N" must come from modified
  time (`trade_carrier.journal_files`); sorting by name quietly picked the wrong files once it mattered.
- **Journal names and EDMC names differ in case.** `BOCHEAUX` in the journal, `Bocheaux` from EDMC. Key
  anything per commander by `casefold()`.
- **`CarrierStats` isn't automatic and isn't replayed.** It exists only if the player opened Carrier
  Management, so state built from it needs a journal backfill at startup, and a baseline from before WNTB
  started is otherwise missed.
- **A `CargoTransfer` doesn't say where it went.** Use the docked station's `MarketID` against
  `CarrierID`; don't assume "my carrier".

**Settings tab and `pack`.** EDMC's `myNotebook.Frame.__init__` grids a spacer child into every `nb.Frame`, so
`pack` inside one always fails with "cannot use geometry manager pack inside ... which already has slaves
managed by grid". A feature whose `build_settings` raises takes the whole WNTB Settings tab down with it
(`Failed for Plugin "WNTB"` in the EDMC log), on Windows and Linux. Use `grid` inside `nb.Frame`s, or pack
into a plain `tk.Frame` as `autohonk.py`'s rows do. This shipped once, in a build that was withdrawn, because the
unit-test stand-ins had no spacer; `tests/test_prefs_smoke.py` now builds every tab with stand-ins that do, and
`tests/test_settings_layout.py` fails on any `pack` into an `nb.Frame`.

## 16. Adding a feature

1. Put pure logic in its own module with no Tk and no EDMC-only imports; add a `unittest` file.
2. Add `xxx_state.py` if it persists data: per-commander, atomic write, tolerant load. Give any new
   file a unique name and consider `_OWN_DATA_FILES` (section 13).
3. Add the panel module implementing the contract (section 4). Choose `PANEL_PLACEMENT`.
4. Use `panelkit.wrap_label` for any text from the game, and a hard box for any image (section 5).
5. Put network calls behind the worker, queue and generation-counter pattern (section 7; Trade's
   one-job-at-a-time variant is described there too). Fail to an empty result, and make automatic lookups
   opt-in.
6. If it draws an overlay: use the shared client, a `wntb_<feature>_` ID prefix, and register a group.
7. Prefix config keys `wntb_<feature>_`.
8. Add the module to `FEATURES` (`ui.py`) and `_FEATURES` (`load.py`); call `start`/`stop` from
   `load.py` if it has them.
9. If it uses another project's code, assets or data, check the licence and update
   `THIRD-PARTY-NOTICES.md` (and `ATTRIBUTIONS.md` for ideas) *in the same change*, before it ships.
10. Update the README and this guide.

## 17. Known gaps

- **`_OWN_DATA_FILES` is a hand-kept list.** A new data file must be added to it (and a new data
  folder to `_OWN_DIRS`) or it will be swept into the pre-update backup. Data was never at risk of
  being overwritten, since it isn't in the release zip. `tests/test_own_data_files.py` now fails when a
  `*FILENAME` constant isn't listed (it caught Trade's two files); a data *folder* is still unchecked.
- **Mining and other panels have no automated UI tests** (section 14).
- **Tick detection depends on a third-party, plain-HTTP service** with no SLA; when it is down the
  tally simply doesn't roll over.
- **Trade mode's gaps** are listed in its [spec](TRADE_TECH_SPEC.md#13-verified-assumed-and-known-gaps): a
  squadron carrier's `CarrierStats` is assumed to match a fleet carrier's, the commodity list and ship pad
  classes are snapshots, and carrier reserved space is only as fresh as the last Carrier Management visit.
- **Exobiology and region data are a snapshot.** New species from a game update require a
  regeneration.

## 18. Platform support: Windows and Linux

Everything except a few features is platform-neutral Python and Tk. The platform-specific parts are
isolated in `platform_support.py` (plus the Windows branches in `autohonk.py` and
`screenshot_automation.py`), so a new platform touches few files.

| Concern | Windows | Linux |
|---|---|---|
| Journals and `Status.json` | EDMC's Journal directory setting (EDMC finds the default) | The same setting, but it has no default: it must point at `<prefix>/drive_c/users/<user>/Saved Games/Frontier Developments/Elite Dangerous`. An empty value means "nothing to scan" |
| Elite's bindings folder | `%LOCALAPPDATA%\Frontier Developments\Elite Dangerous\Options\Bindings` | The same path inside the Wine/Proton prefix (below) |
| Elite's screenshot folder | Shell "Pictures" known folder (`SHGetKnownFolderPath`), with OneDrive redirect handling | `Pictures/Frontier Developments/Elite Dangerous` inside the prefix, else `~/Pictures` |
| Screenshot event `Filename` | `\ED_Pictures\Screenshot_0001.bmp` | Same Windows-style string (Elite writes it even under Proton), so the file name is taken with `screenshot_naming.journal_basename`, not `os.path.basename` |
| Find the game window | `FindWindowW` (ctypes) | `xdotool search --name "^Elite - Dangerous"` |
| Is the game in the foreground | `win32gui.GetForegroundWindow` (bundled pywin32) | `xdotool getactivewindow getwindowname` |
| Send a key | `keybd_event` (ctypes for Auto-Honk, pywin32 for screenshots) | `xdotool` (XTEST); a hold is one `keydown`, `sleep`, `keyup` call (`platform_support.hold_key`) |
| Is a companion app running | `tasklist` | `pgrep -f` |
| Notification sound | `winsound.MessageBeep` | `canberra-gtk-play`, else `paplay` with the freedesktop theme file |
| Overlay | EDMCOverlay or EDMCModernOverlay | EDMCModernOverlay (or edmcoverlay2); same TCP protocol |
| Modal dialogs | `grab_set` works at once | `ui.style.grab_when_visible`: X11 refuses a grab until the window is mapped, so it retries briefly |
| Plain `tk.Listbox` colours | `SystemWindow` / `SystemWindowText` | `white` / `black` (those names are Windows-only Tk colours) |
| Text symbols in the UI | Any | Only symbols every font has (`×`, `★`, `→`); `✕` was replaced because some Linux fonts lack it |
| Settings notes | "This system: Windows - supported" | "This system: Linux, xdotool found / NOT found" (`platform_support.input_support_note`, `sound_support_note`) |

**Why the prefix.** Elite is a Windows game. Under Steam Proton it sees a fake Windows profile stored
at `.../steamapps/compatdata/359320/pfx/drive_c/users/steamuser/`, so its "Local AppData" and
"Pictures" are ordinary Linux folders inside that prefix. `find_elite_prefix` looks in the usual
Steam roots (native, `~/.steam` symlinks, Flatpak), follows `libraryfolders.vdf` to other drives, and
also accepts a user-set path (the prefix, its `pfx` folder, or the `compatdata/<id>` folder). Lutris
and plain Wine use the real username instead of `steamuser`, which `prefix_user_dir` handles. A bad
override deliberately does *not* fall back to auto-detect, so a typo is visible instead of silently
using a different prefix.

**Why xdotool through `subprocess`.** It adds no Python dependency to EDMC's bundled environment, and
it works on X11 and on XWayland, which is where a Proton game's window lives even on a Wayland
desktop. The alternatives are worse fits: `python-xlib` needs installing into EDMC's Python, and
`evdev`/`uinput` needs device permissions. Keys are sent with XTEST after focusing the window,
because per-window synthetic events (`--window`) are ignored by most games. This mirrors Windows,
where `keybd_event` goes to the foreground window.

**One process per hold.** XWayland releases a synthetic (XTEST) key about a second after the `xdotool`
process that pressed it exits. A separate `keydown` process, a Python `sleep`, then a `keyup` process
therefore held the key for only about a second, and a honk needs several. `hold_key` runs
`xdotool keydown K sleep N keyup K` as one process, which keeps the key down for the full time.

**Flatpak EDMC.** The sandbox sees neither host programs nor the game's folders. `platform_support._tool_command`
uses a sandbox copy of a tool when one exists, and otherwise runs `flatpak-spawn --host --directory=/ <tool>`
after probing that the host has it (only a successful probe is cached). `pgrep` prefers the host, because
the sandbox only sees its own processes. `--directory=/` is required: `flatpak-spawn` starts the host command
in the sandbox's working directory, which for EDMC (`/app/edmarketconnector`) does not exist on the host. The
user must grant `--talk-name=org.freedesktop.Flatpak` and filesystem access to the journals, Bindings and
Pictures folders (see the README, Linux, Step 3). EDMCModernOverlay needs the same talk permission to start
its overlay window, so a missing one makes the overlay's port answer while nothing is drawn.

**Failure behavior.** Every wrapper returns `False`, `None` or an empty list, never raises. A missing
`xdotool` produces a clear outcome ("xdotool isn't installed") rather than a silent no-op, and
`screenshot_automation.SUPPORTED` is false without it, so the timed-capture controls simply don't
appear.

**Journal location.** EDMC's own Journal directory setting is the source of truth for journals and
`Status.json`. On Linux it usually has no default, so code that reads it treats an empty value as
"nothing to scan" (a bare `Path("")` would silently scan the current directory, and `Path(None)`
raises). `platform_support.journal_dir_advice` compares that setting with the prefix's
`Saved Games/Frontier Developments/Elite Dangerous` (following symlinks) and returns a one-line
hint, shown in Settings and logged at startup. It only advises: people legitimately link that folder
elsewhere, so WNTB never changes EDMC's setting itself.

**Overlay.** WNTB's overlay client is plain loopback TCP with newline-delimited JSON, so it is
platform-neutral. EDMCModernOverlay runs a legacy listener on `127.0.0.1:5010` on both Windows and
Linux, and edmcoverlay2 does the same on Linux, so no WNTB code changed. The original EDMCOverlay is a
Windows program. Plugin Group registration imports ModernOverlay's own module and is a silent no-op
if it is absent.

**Case sensitivity.** Windows ignores filename case and Linux does not. Elite writes `Status.json`
(capital S), so code must ask for that exact name; a lowercase `status.json` works on Windows and
silently fails on Linux. Journals match `Journal.*.log`. When adding file access, use the game's exact
spelling.

**Windows-only behavior stays Windows-only.** OneDrive folder-redirection handling, the "Controlled
Folder Access" error text and the shell Pictures lookup are gated on Windows, so Linux users don't
see irrelevant advice.

**Settings labelling.** Any feature that depends on the operating system shows a **Works on:** line in
its Settings tab, coloured green when this machine can run it and orange when it cannot (and why):
Auto-Honk, the Screenshots auto-timer and Thargoid capture, the Inventory pickup sound, and the Overlay
Connection tab (which says the older EDMCOverlay is Windows-only). The BGS tab shows the Linux journal
folder hint. Wording lives in one place, `platform_support.py`, and is unit-tested.

**Status.** The Linux paths are unit-tested with mocked subprocess calls and temporary directories
(`tests/test_platform_support.py`), but have not been run against a real Elite install. Wayland
without XWayland, and macOS, are unsupported for key simulation.

### 18.2 Platform notes for the session strip (`game_mode.py`, `session_credits.py`)

Both modules are platform-neutral by construction; what was checked, and why it holds on each system:

- **Journal source.** They read only journal events (`LoadGame`, `StartUp`, `Shutdown`) and EDMC's
  `state["Credits"]`, which EDMC supplies identically on Windows and Linux. `StartUp` recovery reads the top
  of the current journal file with an explicit UTF-8 encoding and tolerates a missing or unreadable file.
- **`monitor.logfile`** is a `str` on some EDMC versions and a `pathlib.Path` on others. It is imported lazily
  (so tests run without EDMC), then converted with `str()` before it is compared or written to JSON. Powerplay's
  session store got the same conversion. Journal-file identity is compared as the exact string EDMC gives, so
  Windows drive-letter paths and Linux Wine/Proton paths behave the same.
- **Saved state.** `session_credits.json` is written to a temp file then `os.replace`d (atomic on both), at most
  once per 30 seconds plus on start and stop; a read-only plugin folder only logs a warning. Time stamps are UTC
  and parsed with `calendar.timegm`, not the local-time `mktime`, so a DST change or a different time zone
  cannot skew the hourly rate.
- **Display.** Number formatting is fixed (`f"{n:,}"`), not locale-dependent. The glyphs used are the ellipsis
  and ordinary punctuation. Both labels are `panelkit.wrap_label`s inside one frame, so a long private-group
  name wraps instead of widening EDMC's window, which matters most on Linux where window managers resize
  more eagerly. The credits line is hidden (`grid_remove`) on the Exploration and Trade modes
  (`ui._MODES_WITHOUT_CREDITS`) and its record keeps updating while hidden.

### 18.3 Platform notes for Trade mode (`trade_*.py`)

Added after the audit below, so not part of its counts. Nothing in Trade is OS-specific: it reads journal events,
EDMC's `state`, and `Market.json` from the journal folder (`config.get_str("journaldir")`, which on Linux is the
Proton prefix's journal path), and makes HTTPS requests with `urllib`. All file reads use an explicit UTF-8
encoding (`errors="replace"` for journals), writes are temp-file-then-`os.replace`, and the carrier backfill
ignores a missing folder. Background work is a plain daemon thread plus `queue`/polling; no thread touches Tk.
Checked on Windows while building, then on Linux on 2026-10-09 against `LINUX_TESTING.md` section 6d with no new
issues: the type-ahead popup (a borderless `Toplevel`, so it depends on the window manager for stacking and focus), the
◀ ▶ glyphs in the page arrows with Linux fonts, and the backfill finding a Proton journal folder.

### 18.1 Audit of every module (2026-10-03)

All 126 modules in `plugin/` and `plugin/uikit/` (about 33,600 lines) were checked for Windows-only or
Linux-only assumptions, in three passes:

1. **Mechanical scan of every module** (AST + text) for platform signals: Win32 and `ctypes` use,
   `subprocess`, `winsound`, `os.startfile`, `sys.platform` branches, `.exe`/PowerShell/`xdotool`
   strings, Windows-only Tk colour names, Windows paths and environment variables, `open()` without an
   explicit encoding, `strftime` directives that differ by platform, and file-name case. 89 modules had
   no platform signal at all (pure logic or plain Tk) and were covered by the scan and the
   cross-cutting checks below; the other 37 had their platform-relevant code read directly
   (`platform_support`, `inventory_sound` and `screenshot_automation` in full; the key-injection,
   Settings and path code of `autohonk`, `screenshots`, `screenshot_convert`, `screenshot_naming`,
   `overlay`, `load`, `update` and the three journal readers `codex_backfill`,
   `mining_journal_backfill`, `exploration_value`; the rest were flagged only for ordinary imports such
   as `urllib`, `webbrowser`, `PIL` or `tkinter.font`).
2. **Cross-cutting checks over all modules:** all 361 relative imports match the real file names
   exactly (a case mismatch passes on Windows and fails on Linux); no two tracked paths differ only by
   case; every `threading.Thread` target (40 of them) was checked and none touches a Tk widget directly;
   every `grab_set` call was found; every mouse-wheel binding handles both Windows deltas and X11
   `Button-4/5`; all generated file names avoid characters Windows rejects.
3. **Fixes that came out of it:**
   - Screenshot `Filename` values are Windows-style even under Proton, and `os.path.basename` doesn't
     split on a backslash on Linux, so the source file was not found and hi-res shots were not
     recognised. Fixed with `screenshot_naming.journal_basename` (tested).
   - Seven modal dialogs called `grab_set()` straight after creating the window, which X11 can refuse.
     They now use `ui.style.grab_when_visible`.
   - The self-updater now refuses a zip entry that would be written outside the plugin folder
     (`..`, an absolute path, another drive), which also hardens it on both systems.
   - The BGS report's suggestion list and close button, and BGS's silent skip when no journal folder is
     set (now logged and shown in Settings).
   - Settings tabs for OS-dependent features now state where they work and whether they can here; the
     Screenshots tab wrongly said auto-capture "requires Windows" when Linux with `xdotool` also works.

Not verifiable from a Windows development machine, and so covered only by `docs/LINUX_TESTING.md`:
real `xdotool` behaviour, Tk popup stacking and focus under each Linux window manager, Proton prefix
layouts other than Steam's, and sound players.
