# Module index

Every Python module that ships in `plugin/`, grouped by feature, with a one-line description. For how the pieces fit
together, see [TECHNICAL.md](TECHNICAL.md) (section 2 is the repository layout); each feature's specification goes
deeper. Trade also has its own module table in [TRADE_TECH_SPEC.md](TRADE_TECH_SPEC.md).

Naming convention: a feature's modules share its prefix (`trade_*.py`), with a suffix for the role: `_panel` (the
feature-module entry point in the main panel), `_window` or `_dialog` (a pop-out), `_state` or `_data` (JSON
persistence), `_client` (a network lookup), and no suffix for pure logic (no Tk, no EDMC) that the unit tests reach
directly. A module with a data file keeps it in the plugin folder beside the code; those files are listed in
`update.py`'s `_OWN_DATA_FILES` so an update never overwrites them.

`tests/test_docs_modules.py` fails if a module is added to `plugin/` without a row here, so this page stays complete.

Non-Python files in `plugin/`: `rare_goods.json` (the rare-goods table behind `rare_goods.py`).

## Entry point, shell and shared services

Spec: [TECHNICAL.md](TECHNICAL.md) sections 3 to 5 and 10

| Module | What it is |
|---|---|
| `commander_data.py` | Per-commander JSON files: a separate payload per commander in one file, the first commander seen claiming data saved before it was per commander |
| `journal_files.py` | Shared start-up catch-up helpers: the journal folder, files changed since a moment, and a filtered event reader |
| `__init__.py` | The package marker; holds `__version__`, the one place the version number lives (mirrored in `package.json`) |
| `http_identity.py` | The User-Agent every web request sends, so services can tell which WNTB feature is calling |
| `load.py` | The EDMC entry point: `plugin_start3`, `plugin_app`, `journal_entry`, `dashboard_entry`, `plugin_stop`, the one-time overlay reset, and forwarding to every feature |
| `notifier.py` | A tiny subscribe/notify helper for where one module's data changes and others must redraw |
| `overlay.py` | The one shared overlay client (EDMCModernOverlay / EDMCOverlay over a local TCP port) and its Plugin Group registration |
| `panelkit.py` | Shared Tk helpers for the main panel and Settings: wrapping labels, separators, toggles, tooltips, collapsible sections, page arrows, theming |
| `platform_support.py` | Windows/Linux differences in one place: Elite's folders, key presses (`xdotool`), host programs under Flatpak, "Works on" notes |
| `settings_scroll.py` | Wraps each Settings page in a height-capped scrolling frame so a long page never pushes the OK button off the screen |
| `ui.py` | The main panel, mode buttons, panel height fitting and the Settings tabs; orchestration only |
| `update.py` | The self-updater: checks GitHub Releases, downloads, stages over the install, and protects per-commander data files (`_OWN_DATA_FILES`) |

## Status lines under the mode buttons

| Module | What it is |
|---|---|
| `game_mode.py` | The "You are in Solo / Open / Private Group" line under the mode buttons |
| `session_credits.py` | The "Credits this session" line (earned or lost since login, with a per-hour rate) |

## Powerplay

Spec: [POWERPLAY_TECH_SPEC.md](POWERPLAY_TECH_SPEC.md)

| Module | What it is |
|---|---|
| `formulas.py` | Merit to Control Point conversion for Powerplay activities |
| `powerplay.py` | Powerplay mode: pledged Power, merits, the current system's Powerplay context and activity classification |
| `powerplay_backfill.py` | Rebuilds the per-system ledger from journal files for cycles played while EDMC was closed |
| `powerplay_clipboard.py` | Formats the Sessions window's "Copy Progress" text |
| `powerplay_control_lookup.py` | Spansh lookup of which Power controls a system |
| `powerplay_ledger.py` | The per-commander, per-system, per-cycle ledger of what you did and how each system moved |
| `powerplay_state.py` | JSON persistence for that ledger |
| `powerplay_systems_tab.py` | The Systems tab of the Powerplay Sessions window |
| `powerplay_window.py` | The Powerplay Sessions window (current session, systems, cycles, daily, history) |
| `rare_goods.py` | Finds the nearest rare commodities to the current system (data in `rare_goods.json`) |
| `rare_goods_window.py` | The Rare Goods Finder window |
| `session.py` | Merit tallies for the current game login |
| `store.py` | JSON persistence for Powerplay session history; every session names its commander, and the history limit and views are per commander |

## Exploration

Spec: [ORGANIC_SCANNING_TECH_SPEC.md](ORGANIC_SCANNING_TECH_SPEC.md), [SCREENSHOTS_AND_INPUT_TECH_SPEC.md](SCREENSHOTS_AND_INPUT_TECH_SPEC.md) (Auto-Honk), [TECHNICAL.md](TECHNICAL.md) section 12

| Module | What it is |
|---|---|
| `autohonk.py` | Auto-Honk: holds the Discovery Scanner key on arrival in a system |
| `canonn_poi_data.py` | Canonn's published Thargoid and Guardian site lists, fetched on demand |
| `canonn_poi_panel.py` | The Canonn Nearby POI section: nearest Thargoid or Guardian site |
| `codex_backfill.py` | Journal readers for Codex Completionist, per commander: the full-history scan behind the BKF button and the one-time rebuild, and `scan_since` for the start-up catch-up |
| `codex_catalog.py` | The catalogue of every codex entry, for the "Not found" tab |
| `codex_completionist.py` | Pure logic for the lifetime tally of everything scanned, with the `last_event_at` watermark |
| `codex_completionist_panel.py` | The Codex Completionist section of Exploration |
| `codex_completionist_state.py` | JSON persistence for the tally, one per commander (the old shared tally is kept untouched, then tidied away) |
| `codex_completionist_window.py` | The Codex Completionist detail window (found and not found) |
| `discovery.py` | Discovery Alerts: overlay alerts for never-before-discovered systems and bodies, plus the N.S./W.D. buttons |
| `elw_rarity_spansh.py` | Spansh count of known Earth-like worlds around a system |
| `exploration_progress.py` | Bodies scanned against the honk's body count, and what the last exploration and organic data sales paid |
| `exploration_value.py` | Estimated scan payout for the last body scanned, the system's age and region, system scan progress and the last data sales |
| `gec_poi_edastro.py` | edastro.com's Galactic Exploration Catalog: downloads the full list once and finds the nearest point of interest locally (their own nearest endpoint stopped using the position) |
| `gec_poi_panel.py` | The GEC Nearby POI section |
| `neutron_finder.py` | Spansh search for the nearest neutron-star or white-dwarf primary |
| `notable.py` | Notable Bodies: the overlay banners, queueing and Settings page |
| `notable_rules.py` | The 15 rules deciding which scanned bodies are worth an alert |
| `organic_region_data.py` | Galactic region and Guardian-nebula proximity from a system's coordinates |
| `organic_scan.py` | Pure logic for exobiology tracking |
| `organic_scan_panel.py` | The Organic Scanning section of Exploration |
| `organic_scan_state.py` | JSON persistence for per-body exobiology progress |
| `organic_species_data.py` | Genus and species reference data (thresholds, values) |

## Boxel Survey

Spec: [BOXEL_SURVEY_TECH_SPEC.md](BOXEL_SURVEY_TECH_SPEC.md)

| Module | What it is |
|---|---|
| `boxel.py` | Procedural system-name parsing and boxel sequence walking |
| `boxel_state.py` | JSON persistence for the Boxel Survey walker |
| `boxel_survey.py` | The Boxel Survey section: walks a boxel's sequence and copies the next target |
| `boxel_walker.py` | The "advance on jump" state machine |
| `edsm_client.py` | EDSM client for nearby-system queries |
| `region_sweep_panel.py` | Region Sweep, Boxel Survey's second sub-mode |
| `region_sweep_queue.py` | Pure logic for the Region Sweep cube queue |
| `region_sweep_spansh.py` | Spansh systems typeahead used by Region Sweep |
| `region_sweep_state.py` | JSON persistence for the Region Sweep queue |
| `survey_log.py` | The notable-finds log, one per commander, and its JSON persistence |
| `visited_systems.py` | JSON persistence for the per-commander visited-systems log, and the start-up catch-up of jumps made while EDMC was closed |
| `waypoint_route.py` | Pure logic for Waypoint Route, Boxel Survey's third sub-mode |
| `waypoint_route_panel.py` | The Waypoint Route section |
| `waypoint_route_state.py` | JSON persistence for Waypoint Route |

## Mining

Spec: [MINING_TECH_SPEC.md](MINING_TECH_SPEC.md)

| Module | What it is |
|---|---|
| `mining_bearing.py` | Great-circle distance and bearing to a saved hotspot, for the waypoint arrow |
| `mining_body_survey.py` | The landable bodies in the current system, for the System Bodies overview |
| `mining_coverage.py` | Where the SRV's scanner has driven, per body, one map per commander |
| `mining_coverage_render.py` | Draws that coverage as a small map (PIL, no Tk) |
| `mining_deposit.py` | Estimates tonnes left in a recorded hotspot deposit |
| `mining_ground.py` | Ground type of a body and your own base rates of deposits on it |
| `mining_hotspot_dialog.py` | The shared Add/Edit Hotspot form |
| `mining_hotspot_finder_dialog.py` | The Find Nearby Hotspots dialog (Spansh) |
| `mining_hotspot_import_export.py` | JSON import and export of the hotspot list |
| `mining_hotspot_settings.py` | The hotspot list section of Mining's Settings tab |
| `mining_hotspots.py` | The saved surface-hotspot list, one per commander |
| `mining_journal_backfill.py` | Replays the current journal when EDMC starts mid-session |
| `mining_ledger.py` | The Mining Book window (bodies, hotspots, detail card with map) |
| `mining_ledger_data.py` | The data side of the Mining Book: grouping and map projection |
| `mining_live_position.py` | Live surface position and heading from `Status.json` |
| `mining_location.py` | The current system name for Mining |
| `mining_methods.py` | Which mining method suits each commodity |
| `mining_overlay.py` | The mining stats overlay and waypoint arrow |
| `mining_pages.py` | Mining's page order |
| `mining_panel.py` | Mining mode's entry point: page chrome, Settings tab, event dispatch |
| `mining_price_finder_dialog.py` | The Find Best Price dialog (Spansh), also opened from Trade's Price finder |
| `mining_rate.py` | Refinements per minute over a sliding window |
| `mining_render.py` | Draws each Mining page's content |
| `mining_reserve_lookup_dialog.py` | The Check Ring Reserve Level dialog (EDSM) |
| `mining_session_archive.py` | Optional per-run JSON archive of finished mining runs |
| `mining_space.py` | Tracks ship-based mining runs |
| `mining_spansh_client.py` | Spansh search for hotspots and best-price stations (shared with Trade's price searches) |
| `mining_surface.py` | Tracks SRV surface-mining runs |

## Trade

Spec: [TRADE_TECH_SPEC.md](TRADE_TECH_SPEC.md) (has its own module table with more detail)

| Module | What it is |
|---|---|
| `trade_blocks.py` | The typed page model Trade draws (headings, label/value rows, tables, notes) and its plain-text form |
| `trade_carrier.py` | Fleet and squadron carrier cargo space and records, journal backfill and `trade_carrier.json` |
| `trade_carrier_ops.py` | Running the carrier: tritium, location, planned jump, trade orders and balance from the carrier journal events |
| `trade_commodities.py` | Commodity name matching and the type-ahead list |
| `trade_commodities_data.py` | The generated commodity table (from FDevIDs) |
| `trade_commodity_entry.py` | The type-ahead Commodity box widget |
| `trade_hold.py` | Mission and stolen tonnes in the ship's hold, from the `Cargo` inventory |
| `trade_history.py` | Saved sessions, the `HistoryBook` and `trade_history.json` |
| `trade_history_window.py` | The Trade History window |
| `trade_journal_scan.py` | Finds journal files not read yet (or grown) and applies them to the ledger, stock and carrier; `trade_journal_scan.json` |
| `trade_ledger.py` | The per-commander session ledger, running costs, catch-up from journals and `trade_ledger.json` |
| `trade_market.py` | Reads `Market.json` and values your cargo at the docked station |
| `trade_pages.py` | Trade's page order |
| `trade_panel.py` | Trade mode's entry point: chrome, page rendering, buttons, background jobs, Settings tab, journal dispatch |
| `trade_prices.py` | Ranks station offers for your load (sell and buy), carrier split and verdict lines |
| `trade_route_start.py` | Each commander's route start (last real station docked at) and `trade_route_start.json`; the journal scan feeds it docks, newest wins |
| `trade_roundtrip.py` | Finds the best back-and-forth station pair, loaded both ways |
| `trade_ship.py` | Ship to landing-pad size and the fit rule |
| `trade_spansh_client.py` | Spansh trade-route planner client and the profit-per-hour estimate |
| `trade_stats.py` | Every figure and table row shown for a saved session |
| `trade_stock.py` | The stock book: cargo bought and not yet sold, and `trade_stock.json` |
| `trade_view.py` | Draws Trade's page blocks with real layout |

## Missions

Spec: [MISSIONS_TECH_SPEC.md](MISSIONS_TECH_SPEC.md)

| Module | What it is |
|---|---|
| `active_missions.py` | Which missions each commander has accepted and which are active |
| `all_missions.py` | The All Missions view across every mission type |
| `community_goal_state.py` | Community Goal progress and your contribution |
| `journal_scan.py` | Reads two weeks of journals so Missions survives EDMC restarts: accepted missions, kills, cargo progress and the active set |
| `kill_missions.py` | The massacre and settlement-raid missions and their kill progress |
| `kill_tracker.py` | Per-mission completion evidence, kept per commander |
| `mission_cargo.py` | Collect / delivery progress of cargo missions from the journal's `CargoDepot` events |
| `mission_types.py` | Classifies missions into the panel's categories |
| `missions.py` | Missions mode's entry point and event handling |
| `missions_ui.py` | Draws Missions' pages and pop-ups |

## Field Ops: screenshots, inventory, ship builds, colonisation

Spec: [SCREENSHOTS_AND_INPUT_TECH_SPEC.md](SCREENSHOTS_AND_INPUT_TECH_SPEC.md), [TECHNICAL.md](TECHNICAL.md) section 12

| Module | What it is |
|---|---|
| `colonisation.py` | Pure logic for construction-site tracking |
| `colonisation_catchup.py` | Folds the recent journals into the saved construction sites at start-up, never counting a delivery twice |
| `colonisation_data.py` | JSON persistence for construction sites (each carries `journal_at`, the newest journal event folded in) |
| `colonisation_panel.py` | The Colonisation section of Field Ops |
| `colonisation_window.py` | The Colonisation Sites window |
| `inventory.py` | Backpack, ship locker and carrier locker tracking |
| `inventory_cargo.py` | Ship and SRV cargo-hold tracking |
| `inventory_names.py` | Microresource ID to display name |
| `inventory_names_fdevids.py` | The microresource names imported from FDevIDs |
| `inventory_panel.py` | The Inventory section of Field Ops (bars and overlay) |
| `inventory_sound.py` | The optional pickup sound |
| `inventory_suit.py` | Current suit and backpack capacity |
| `inventory_window.py` | The tabbed inventory window |
| `screenshot_automation.py` | The screenshot timer and key press, detecting Elite running |
| `screenshot_convert.py` | Converts screenshots to renamed PNGs and thumbnails |
| `screenshot_gui_focus.py` | GUI-focus detection and per-panel crop rectangles |
| `screenshot_naming.py` | Output file names for captured screenshots |
| `screenshots.py` | The Screenshots section of Field Ops: capture, conversion, thumbnails, overlay message |
| `ship_builds_data.py` | Per-commander catalogue of ship-build links |
| `ship_builds_dialog.py` | The Add/Edit Ship Build dialog |
| `ship_builds_panel.py` | The Ship Builds section of Field Ops |
| `ship_builds_window.py` | The Ship Builds window |

## BGS

Spec: [BGS_TECH_SPEC.md](BGS_TECH_SPEC.md)

| Module | What it is |
|---|---|
| `bgs_format.py` | Text formatting shared by the BGS panel and report |
| `bgs_journal.py` | Rebuilds the current tick's totals from journal files |
| `bgs_ledger.py` | The per-tick ledger (live events and replay share one path) |
| `bgs_panel.py` | BGS mode's entry point |
| `bgs_state.py` | JSON persistence for BGS tracking |
| `bgs_tick_client.py` | The community galaxy-tick time API client |
| `bgs_tracker.py` | Pure parsing of BGS-relevant journal events |
| `bgs_window.py` | The BGS Report window |

## Always on: Landing Assist and Interdiction Warning

Spec: [TECHNICAL.md](TECHNICAL.md) section 12

| Module | What it is |
|---|---|
| `interdiction.py` | Interdiction Warning overlay and detection |
| `landing.py` | Landing Assist: assigned pad, diagram on the overlay and in the panel; one render worker that retries until the overlay is up |

## Shared window kit (`plugin/uikit/`)

Spec: [WINDOW_FRAMEWORK_SPEC.md](WINDOW_FRAMEWORK_SPEC.md). Pure tkinter; nothing here imports EDMC.

| Module | What it is |
|---|---|
| `uikit/__init__.py` | Package marker for the shared window kit |
| `uikit/mapview.py` | Canvas map widget (coverage, hotspots, position, zoom) |
| `uikit/palette.py` | Colour and font tokens for WNTB's own window look |
| `uikit/shell.py` | The window shell: header, body, status footer, saved geometry |
| `uikit/style.py` | Fonts and per-window skinning |
| `uikit/table.py` | `DataTable`, the replacement for `ttk.Treeview` |
| `uikit/widgets.py` | Reusable widgets (buttons, combobox, scrollbar, progress bar, tabs) |
