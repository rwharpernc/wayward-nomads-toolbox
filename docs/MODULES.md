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
| `issue_report.py` | The Settings → General → Help **Report an issue** button: builds the prefilled GitHub bug-report address (versions and OS, nothing personal) and opens it in the browser; also **Copy diagnostics**, which puts the versions and the newest WNTB lines of EDMC's log (commander name and home folder redacted) on the clipboard |
| `load.py` | The EDMC entry point: `plugin_start3`, `plugin_app`, `journal_entry`, `dashboard_entry`, `plugin_stop`, the one-time overlay reset, and forwarding to every feature |
| `notifier.py` | A tiny subscribe/notify helper for where one module's data changes and others must redraw |
| `overlay.py` | The one shared overlay client (EDMCModernOverlay over a local TCP port), its Plugin Group registration and group offsets |
| `overlay_layout.py` | Where overlay displays go, the same on any screen: how big a pixel is on the overlay's canvas (positions are screen fractions, sizes are pixels), nine anchor spots plus pixel offsets, the overlay's right-edge clamp, the overlay's clamp and the offset that carries a display past it, a client wrapper that moves a display, and `on_canvas`, which rejects an exact position that would leave a display off the canvas; pure, no Tk |
| `overlay_style.py` | The shared overlay look: six color schemes (color roles), the text sizes with per-size character width and line height estimates (each width padded by 10%, plus a stricter `measured_width` for cards of capitals and catalog names), padding and line spacing; cards are sized from these so larger text never wraps; pure, no Tk |
| `overlay_appearance.py` | The saved color scheme and text size (Default, Larger), the fixed padding and line spacing, `current_look()` which every overlay draws with, and the Overlays > Appearance Settings tab with its sample |
| `overlay_placement.py` | Global overlay placement: reads the real window size, mode and display scaling from EDMCModernOverlay's log (falling back to Elite's `DisplaySettings.xml` and Windows' scaling), keeps every display's saved spot, and the Overlay Placement Settings tab with its preview |
| `overlay_grid.py` | The drag-and-drop layout editor on the Overlay Placement tab: a to-scale picture of the screen with a grid and a box for every display; dropping a box writes the spot and offset (snapping flush to an edge or the center line, and to the grid); the conversions between a dropped box and a placement are pure |
| `panelkit.py` | Shared Tk helpers for the main panel and Settings: wrapping labels (a `min_wrap` per label, so a section can wrap at the window's width without ever widening a narrow one), separators, toggles, tooltips, collapsible sections, page arrows, theming, and `fit_entry` / `fit_button_row`, which cap an entry box and a row of buttons in pixels whatever the font |
| `platform_support.py` | Windows/Linux differences in one place: Elite's folders, key presses (`xdotool`), host programs under Flatpak, "Works on" notes |
| `restore.py` | Names the last commander from the newest journal and tells every feature when EDMC starts without the game running, so nothing waits for a login |
| `settings_scroll.py` | Wraps each Settings page in a height-capped scrolling frame so a long page never pushes the OK button off the screen |
| `ui.py` | The main panel, mode buttons, panel height fitting and the Settings tabs; orchestration only |
| `update.py` | The self-updater: checks GitHub Releases, downloads, stages over the install, and protects per-commander data files (`_OWN_DATA_FILES`) |

## Status lines under the mode buttons

| Module | What it is |
|---|---|
| `game_mode.py` | The "You are in Solo / Open / Private Group" line under the mode buttons |
| `session_merits.py` | The "Merits this session" line under the credits line (Powerplay merits since login, with a per-hour rate) |
| `session_credits.py` | The "Credits this session" line (earned or lost since login, with a per-hour rate); clicking it opens the Credits Ledger |
| `credits_ledger.py` | The Credits Ledger feature's entry point: folds live income events into the commander's book, rebuilds the past from the journals once on a worker thread, reads the newest `Statistics` event, opens the window |
| `income_ledger.py` | The Credits Ledger's data: income per commander by activity (trade profit, exploration data, exobiology data, mission rewards, bounties and bonds) and by day, counted without double counting; pure, no Tk |
| `income_catchup.py` | Reads a commander's income events from every journal file, for the ledger's one-time rebuild |
| `ledger_window.py` | The Credits Ledger window: Income (today, 7 days, 30 days, all), By day, and Lifetime tabs |
| `lifetime_stats.py` | The game's lifetime totals (the `Statistics` event) for the ledger's Lifetime tab: parsing, the grouped rows, and finding each commander's newest event in the journals |

## Powerplay

Spec: [POWERPLAY_TECH_SPEC.md](POWERPLAY_TECH_SPEC.md)

| Module | What it is |
|---|---|
| `formulas.py` | Merit to Control Point conversion for Powerplay activities |
| `powerplay.py` | Powerplay mode: pledged Power, merits, the current system's Powerplay context and activity classification |
| `powerplay_backfill.py` | Rebuilds the per-system ledger, and the megaship scans, from journal files for cycles played while EDMC was closed |
| `powerplay_clipboard.py` | Formats the Sessions window's "Copy Progress" text |
| `powerplay_control_lookup.py` | Spansh lookup of which Power controls a system |
| `megaship_scans.py` | Megaship scans for the Powerplay cycle: reads the journal (`DataScanned` uplink, `SupercruiseDestinationDrop`, the FSS megaship list, `PowerplayMerits`) to say which megaship was scanned, where, and what it earned; no Tk |
| `powerplay_ledger.py` | The per-commander, per-system, per-cycle ledger of what you did and how each system moved, and the megaships scanned each cycle (`live_view()` feeds the panel's cycle tally) |
| `powerplay_megaships_tab.py` | The Megaships tab of the Powerplay Sessions window: one row per megaship scanned, cycle by cycle |
| `powerplay_state.py` | JSON persistence for that ledger |
| `powerplay_systems_tab.py` | The Systems tab of the Powerplay Sessions window |
| `powerplay_window.py` | The Powerplay Sessions window (current session, systems, cycles, daily, megaships, history) |
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
| `codex_catalog.py` | The catalog of every codex entry, for the "Not found" tab |
| `codex_completionist.py` | Pure logic for the lifetime tally of everything scanned, with the `last_event_at` watermark |
| `codex_completionist_panel.py` | The Codex Completionist section of Exploration |
| `codex_completionist_state.py` | JSON persistence for the tally, one per commander (the old shared tally is kept untouched, then tidied away) |
| `codex_completionist_window.py` | The Codex Completionist detail window (found and not found) |
| `discovery.py` | Discovery Alerts: overlay alerts for never-before-discovered systems and bodies, plus the N.S./W.D. buttons |
| `elw_rarity_spansh.py` | Spansh count of known Earth-like worlds around a system |
| `exploration_progress.py` | Bodies scanned against the honk's body count, and what the last exploration and organic data sales paid |
| `exploration_value.py` | Estimated scan payout for the last body scanned, the system's age and region, system scan progress and the last data sales |
| `gec_poi_edastro.py` | edastro.com's Galactic Exploration Catalog: downloads the full list once and finds the nearest point of interest locally (their own nearest endpoint does not use the position) |
| `gec_poi_panel.py` | The GEC Nearby POI section |
| `materials_data.py` | The 146 engineering materials with type and grade: 137 from FDevIDs `material.csv` and nine Thargoid-war and chip materials from EDDiscovery's item list |
| `blueprints_data.py` | 1,176 engineering blueprints (type, name, grade, engineers, ingredients with counts, effects) and where 262 ingredients are found, trimmed from EDEngineer (MIT) and corrected from EDDiscovery's data (five recipes, seven synthesis rows, the Colonia engineers' upgrades) |
| `blueprints.py` | Blueprints as objects: browse by type, name and grade, search, ingredient kinds (ship material, Odyssey micro-resource, commodity) matched to the keys the counts use, and a check that every counted ingredient matches; no Tk |
| `blueprint_wishlist.py` | The commander's blueprint wishlist (blueprints and a number of crafts each), kept per commander in `blueprint_wishlist.json`, with limits, and `add_many` to put a whole ship plan on it at once, all or nothing; no Tk |
| `blueprint_needs.py` | What a blueprint or the whole wishlist needs against what is held (ship materials and the Odyssey ship locker), ready in list order, and the combined shopping list; no Tk |
| `journal_blueprints.py` | Generated by `scripts/gen_journal_blueprints.py`: how the journal names an engineering blueprint (`FSD_LongRange`) and an experimental effect (`special_fsd_heavy`) and what the blueprint table calls them, per module type |
| `ship_plan.py` | The ship engineering planner: reads a pasted ship loadout (SLEF from EDSY or Coriolis, or a journal `Loadout` line), places each engineered module in the blueprint table, and adds up the grades and experimental effects it takes, optionally minus what the current ship already has; no Tk |
| `odyssey_upgrade_plan.py` | The Odyssey upgrade planner: what it costs to take a suit or weapon from one class to another (materials from the blueprint table, credits from a per-item unit seen in real journals) and fit up to four modifications; no Tk |
| `odyssey_gear.py` | The Odyssey suits and weapons the commander owns, from the journal's loadout events: item, class now and fitted modifications, for the Upgrade planner to fill in; read on demand, nothing stored |
| `odyssey_plan_tab.py` | The Upgrade planner tab of the Engineering window: pick the item (or read your own gear), classes and modifications, see the steps and credits, and add them to the wishlist |
| `missions_overlay.py` | The Missions card on the in-game overlay: the missions for this system and the next jump first, the rest by urgency, capped to a row limit; pure layout plus drawing and its Settings tab |
| `ship_current.py` | The ship being flown, from the newest `Loadout` event in the newest journals, read on demand for the Ship planner to subtract; nothing stored |
| `ship_plan_tab.py` | The Ship planner tab of the Engineering window: paste, read, the module table, rolls per grade, and Add plan to wishlist |
| `blueprints_extra.py` | Hand-added entries the blueprint table lacks: Yi Shen's unlock, which asks for three sets of items handed to the other Colonia on-foot engineers, with its sources |
| `engineers_data.py` | Where each of the 38 engineers is (system, base, coordinates, planet) and how to find, be invited by and unlock them, permit and on-foot flag, from EDDiscovery's table (Apache-2.0) |
| `engineers.py` | The commander's standing with each engineer (Known, Invited, Unlocked, rank), from the journal's `EngineerProgress`, kept per commander in `engineers.json`; matches the journal's names (with a nickname in quotes) to the table's; also `info(name)` (where an engineer is and how to unlock them, and whether the region is the Bubble or Colonia), the ship engineers' grade thresholds and the one known quirk; no Tk |
| `blueprints_window.py` | The Engineering window: browse and search blueprints, see one craft's ingredients against what you hold and where each is found, add to the wishlist, the wishlist with a combined shopping list and who can do each entry, and an Engineers tab (standing, what they offer, where they are, what unlocking takes, with the details of the one you select, and a Bubble / Colonia / Both filter) and the Ship planner and Upgrade planner tabs |
| `material_traders.py` | Finding a material trader: the closest Raw, Manufactured or Encoded traders to a system from Spansh's station search, with the pad filter, a two-minute cache and the place described; the search is passed in, so it is tested offline; no Tk |
| `materials.py` | The commander's Raw, Manufactured and Encoded materials, kept per commander in `materials.json`: the login list, every event that changes a count, the grade limits (300 to 100), EDMC's totals for a mid-session start, and unknown materials; no Tk |
| `materials_panel.py` | The Materials row in Field Ops mode: pieces held of each type, the last change, what is at the limit, and the button that opens the window |
| `material_trader_window.py` | The Material trader window: pick a type, distance and pad, search from your system or another, see what you hold of that type by grade, and the closest traders from Spansh; the lookup runs on a worker thread |
| `materials_window.py` | The Materials window: search, type and grade filters, "only at the limit", and a sortable table of held, limit and room |
| `expedition.py` | Expedition planner, the pure part: named expeditions of ordered stops with notes, one active at a time, stops ticked off from arrivals with jump and distance totals, per-stop survey counts (bodies scanned, first discoveries, mapped) from the scan events, nearest-neighbor ordering, CSV and text export, kept per commander in `expeditions.json`; no Tk |
| `expedition_window.py` | The Expedition window: pick, create, start, pause, finish, reset and delete expeditions; a table of stops with the next one marked and the distance from you; an editor with a Here button; import from the plotted route or a CSV, locate and reorder by distance through EDSM, copy and export |
| `system_names.py` | Where system-name suggestions come from: the systems you have been in this session, names other parts of WNTB register (expedition stops, notes), and, only when Settings → Window → *Suggest system names from Spansh while typing* is ticked, Spansh's system-name search (kept in memory for the session); no Tk |
| `system_autocomplete.py` | `attach(entry, var)`: a list of system-name suggestions under any text box as you type (Down and Up, Enter or a click to take one, Escape to close; Enter with nothing highlighted still does what the box did); the Spansh call runs on a worker thread |
| `spansh_planners.py` | Spansh's Road to Riches and Expressway to Exomastery planners: the form sent, the job polled to its end, and each answer turned into expedition stops (system, the best body, a note of what is worth it, position); opt-in, only when Plot is pressed; no Tk |
| `expedition_plan_dialog.py` | The window behind the Expedition window's **Road to Riches** and **Exomastery** buttons: start, optional end, jump range, radius, results, distance and least worth, then **Plot** (worker thread, progress from Spansh, **Cancel**); its answer is handed back to become an expedition |
| `expedition_panel.py` | The Expedition row in Exploration mode: the tracked expedition's stops done, jumps, light-years and time, the next stop with its distance and note, the stop just reached, what was found, COPY and copy-on-arrival, and the lines the Route overlay shows for the running expedition; feeds the planner from the journal |
| `expedition_log.py` | Expedition Log model: an archive of the commander's exploration expeditions, per commander (`expedition_log.json`): `Run` (name, start and end, start and end location, ships, notes, totals), `Tally` (counts journal events: jumps and light-years, systems, bodies scanned, first discoveries, mapped, exploration data sold, scans' estimated value; samples, species analysed, first footfalls, exobiology sold, species' estimated value), `LogBook` (start, stop, resume, reset, delete, edit with date checks, save), `rescan` (the totals worked out again from the commander's journals between start and end), and the summary and CSV text |
| `expedition_log_panel.py` | The Expedition Log's journal hook and the Exploration panel row: the running expedition's summary, START, STOP and LOG; remembers the system and ship so a new expedition starts with them |
| `expedition_log_window.py` | The Expedition Log window: the archive table, what each expedition recorded, an editor for its details, and Start, Stop, Resume, Reset, Rescan, Delete, Copy summary and Export CSV |
| `expedition_log_overlay.py` | Expedition Log overlay: one card with the running expedition's exploration and exobiology totals and what was earned; Settings → Overlays → Expedition Log, one Overlay Placement slot |
| `notes_data.py` | The commander's notes on a system or body, kept per commander in `notes.json`: validation and limits, search, and an add, change and delete that save at once; no Tk |
| `notes_panel.py` | The Notes row in Exploration mode: how many notes the system you are in has and the newest, a one-line quick add, and the button that opens the window |
| `notes_window.py` | The Notes window: search, a list of every note, and an editor with a Here button for the system and body you are at |
| `surface_marks.py` | The commander's named surface marks (body, latitude, longitude) and compass target, kept per commander in `surface_marks.json`: validation and limits, lookup by body, add, change, delete; no Tk |
| `surface_compass.py` | Surface Compass: points an overlay arrow, name and distance at the nearest hotspot or a chosen mark on the body you are on; the Compass section in Exploration mode (MARK, TARGET, MARKS), its Settings tab, and the one-time carry-over of the old Mining waypoint settings |
| `surface_marks_window.py` | The Marks window: every mark with its distance from here, the compass target, and an editor with a Here button |
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
| `survey_catchup.py` | Catching the survey log up from the last 14 days of journals (scans made with EDMC closed): reading them, and replaying them without counting anything twice |
| `survey_log.py` | The notable-finds log, one per commander, and its JSON persistence |
| `visited_systems.py` | JSON persistence for the per-commander visited-systems log, and the start-up catch-up of jumps made while EDMC was closed |
| `waypoint_route.py` | Pure logic for Waypoint Route, Boxel Survey's third sub-mode |
| `waypoint_route_panel.py` | The Waypoint Route section |
| `waypoint_route_state.py` | JSON persistence for Waypoint Route |

## Mining

Spec: [MINING_TECH_SPEC.md](MINING_TECH_SPEC.md)

| Module | What it is |
|---|---|
| `mining_bearing.py` | Great-circle distance, bearing and arrow maths, for the Surface Compass and the coverage map |
| `mining_body_survey.py` | The landable bodies the journal has shown in the current system (scans and mining-location signals), which the Mining Book lists and the ground-type rates are worked from |
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
| `mining_overlay.py` | The mining stats overlay |
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
| `trade_history_window.py` | The Trade History window (it widens to fit its widest table) |
| `trade_journal_scan.py` | Finds journal files not read yet (or grown) and applies them to the ledger, stock and carrier; `trade_journal_scan.json` |
| `trade_ledger.py` | The per-commander session ledger, running costs, catch-up from journals and `trade_ledger.json` |
| `trade_market.py` | Reads `Market.json` and values your cargo at the docked station |
| `trade_pages.py` | Trade's page order |
| `trade_panel.py` | Trade mode's entry point: chrome, page rendering, buttons, background jobs, Settings tab, journal dispatch |
| `current_system.py` | The system the commander is in now, asked on demand: what the caller tracked, EDMC's state, then the newest journal |
| `mission_progress.py` | How far along each mission is (the game's cargo count, kills, or tonnes in the hold) and the color band for it; used by the Missions window and the overlay card |
| `current_cargo.py` | The commander's hold by commodity, from EDMC's state, for "held" mission progress |
| `mission_pins.py` | The missions a commander pinned (ids only), kept per commander in `mission_pins.json`; pins go with their mission |
| `missions_board.py` | The Missions window's data: a row per active mission (progress, reward, time left, ready, pinned), the totals line, grouping by place, the detail lines; no Tk |
| `missions_window.py` | The Missions window (Active and By place tabs, detail strip, Pin / Unpin, Pin all here, Unpin all, Copy system, Sources); replaces the old "All" popup |
| `mission_sources.py` | The commodities your Collect and Mining missions still need, and the four source picks looked up for each |
| `mission_sources_window.py` | The Missions "Source commodities" window (Find sources, Copy system) |
| `source_picks.py` | The four answers to "where do I buy or sell this?": closest, best local, cheapest anywhere, recommended (within 10% of the best); used by Trade and Missions |
| `trade_prices.py` | Ranks station offers for your load (sell and buy), carrier split and verdict lines |
| `trade_route_start.py` | Each commander's route start (last real station docked at) and `trade_route_start.json`; the journal scan feeds it docks, newest wins |
| `trade_roundtrip.py` | Finds the best back-and-forth station pair, loaded both ways |
| `trade_ship.py` | Ship to landing-pad size and the fit rule |
| `trade_spansh_client.py` | Spansh trade-route planner client and the profit-per-hour estimate |
| `trade_stats.py` | Every figure and table row shown for a saved session |
| `trade_stock.py` | The stock book: cargo bought and not yet sold, and `trade_stock.json` |
| `trade_view.py` | Draws Trade's page blocks with real layout (figures drop to the small font in a wide font, and the title wraps instead of widening the page) |
| `trade_watch_data.py` | The market watch list: a commander's watched commodities and the prices seen for them at the markets they opened (`Market.json`), kept per commander in `trade_watch.json`, with the Spansh answers held in memory; best buy and sell across both; no Tk |
| `trade_watch_lookup.py` | The watch list's Spansh refresh: the cheapest station to buy and the dearest to sell each watched commodity near a system, stations only, paused between requests and cancellable; the search is passed in, so it is tested offline |
| `trade_watch_panel.py` | The Watch list row in Trade mode: a few short best-price lines, REFRESH (Spansh, on a worker thread; needs Trade's lookups on) and WATCH (the window); reads `Market.json` on the `Market` event |
| `trade_watch_window.py` | The Watch list window: add a commodity with the type-ahead box, remove one, the best buy and sell with where and how old, and every market a commodity was seen at |

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
| `missions_ui.py` | Draws Missions' pages and opens the Missions window |

## Colonization: current project, history, sites window

Guide: [Colonization](guide/colonization.md)

| Module | What it is |
|---|---|
| `colonisation.py` | Pure logic for construction-site tracking |
| `colonisation_carrier.py` | (Includes `scan_journals`, the rebuild behind Rescan Carrier.) Tonnes of each commodity transferred to the commander's fleet carrier, for the window's FC column (per commander, caught up from the journals without double counting) |
| `colonisation_catchup.py` | Folds the recent journals into the saved construction sites at start-up, never counting a delivery twice |
| `colonisation_data.py` | JSON persistence for construction sites (each carries `journal_at`, the newest journal event folded in) |
| `colonisation_history_window.py` | The Colonization History window (HISTORY button): Overview, By day, Commodities and Sites tabs, so the panel itself shows no history |
| `colonisation_history.py` | What the commander has delivered to construction sites (tonnes by commodity, site and day), kept per commander and caught up from the journals without double counting |
| `colonisation_overlay.py` | The shopping-list card on the in-game overlay: what is still to get for the active site (pure formatting plus drawing); its visibility also follows the game rewriting `Market.json`, so the card shows when a market opens even if the journal's Market event is late |
| `colonisation_panel.py` | The Colonization mode's page (current project and history), the overlay card's controller and the settings tabs |
| `build_costs.py` | What each kind of building costs in tons (the bundled `colonisation_costs.json`, a copy of a community-compiled table): looked up by a site's layout name, with its biggest commodities |
| `commodity_categories.py` | The market category of each colonization commodity, so the shopping list can be grouped as the in-game market groups it |
| `rcc_sync.py` | Opt-in sharing of live colonization progress with Raven Colonial: depot snapshot, deliveries, commander link and (separately) carrier cargo deltas, one request per event on a worker thread with a bounded queue |
| `rcc_keys.py` | Each commander's Raven Colonial key, kept in `rcc_keys.json` (one entry per commander) |
| `rcc_client.py` | A thin client for Raven Colonial's API: reading one system's plan (its architect, whether it is open, and its build sites: planned, building, complete), with a bounded read, a user-agent, a timeout and a one-minute memory |
| `colonisation_builds_window.py` | The Planned Builds window: Raven Colonial's sites for the picked site's system, fetched on a worker thread when opened or refreshed |
| `colonisation_sources.py` | Where to buy a colonisation commodity: the closest stations (and optionally fleet carriers) with it in stock, any landing-pad size by default, via Spansh; the whole-list search (one request per commodity) and the remembered search choices; pure shaping around an injected search |
| `colonisation_stats.py` | The figures and wording of the Colonization page: the current project and the history, worded for a commander with or without a fleet carrier; pure, no Tk |
| `colonisation_view.py` | What the Colonisation Sites window shows for a site: the commodity rows after the filters, and the totals (still to get, on the carrier, in the ship, buy and haul trips); pure, no Tk |
| `colonisation_window.py` | The Colonisation Sites window: sites on the left; the picked site's progress, totals, filters and sortable commodity table, and the Where to buy search, on the right |

## Field Ops: screenshots, inventory, ship builds

Spec: [SCREENSHOTS_AND_INPUT_TECH_SPEC.md](SCREENSHOTS_AND_INPUT_TECH_SPEC.md), [TECHNICAL.md](TECHNICAL.md) section 12

| Module | What it is |
|---|---|
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
| `ship_builds_data.py` | Per-commander catalog of ship-build links |
| `ship_builds_dialog.py` | The Add/Edit Ship Build dialog |
| `ship_builds_panel.py` | The Ship Builds section of Field Ops |
| `ship_builds_window.py` | The Ship Builds window |

## BGS

Spec: [BGS_TECH_SPEC.md](BGS_TECH_SPEC.md)

| Module | What it is |
|---|---|
| `bgs_format.py` | Text formatting shared by the BGS panel and report |
| `bgs_journal.py` | Rebuilds the current tick's totals from journal files |
| `bgs_ledger.py` | The per-tick ledger (live events and replay share one path), and the rebuild of a period that just closed from the journals (`repair_record`, `merge_records`) |
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
| `carrier_jump_timer.py` | Fleet carrier jump countdown, the pure part: the planned jump from `CarrierJumpRequest` (cleared by a cancel or the jump), time left, one alert at 10, 5 and 1 minute and at departure, and reading a request back from recent journals |
| `fuel_alerts.py` | Fuel warnings, the pure part: low fuel at a chosen percentage, and a plotted star that cannot be scooped (`FSDTarget`) with a tank at or under a second percentage; tank size from `Loadout`, fuel from `Status.json` |
| `flight_alerts.py` | Flight Alerts: one overlay card for the carrier jump countdown and the fuel warnings, with its Settings tab, optional sound and a one-second tick while a jump is planned |
| `route_plan.py` | Route status, the pure part: the plotted route from `NavRoute.json`, where the ship is on it, jumps and light years left, each star's kind (neutron star, white dwarf, another star that cannot be scooped), the next supercharge, and the fuel and range figures from `Loadout`, `FSDJump` and `Status.json` |
| `route_overlay.py` | Route overlay: one card with the ship's travel status and the systems of the plotted route, neutron stars and white dwarfs picked out, and optionally the running expedition; its Settings tab, Test Card and a one-second tick while there is something to show |
| `overlay_card.py` | The list-style overlay card shared by the Route, System targets and Body info cards: `Card` (header lines, two-column rows, footer), `CardLayout` (fixed top and width, text-based sizes, every line at the left padding, send and clear), `LiveCard` (redraw when changed or every few seconds) and `Ticker` |
| `scan_value.py` | The exploration scan-value estimate (per-class k values, mass exponent, first-discovery multiplier) as a pure module, used by the Exploration Value readout and the System targets and Body info cards |
| `system_survey.py` | The bodies of the current system from the journal (`Scan`, `FSSDiscoveryScan`, `FSSAllBodiesFound`, `FSSBodySignals`, `SAASignalsFound`, `SAAScanComplete`, `ScanOrganic`): estimated scan value, what is left to map and which bodies still have life to analyse; rebuilt from the newest journal when EDMC starts mid-system; no Tk |
| `system_survey_store.py` | The saved surveys of each system, per commander (`system_surveys.json`): the bodies and what their scans said, the honk, what is mapped and which organisms are analysed, written after a short delay and merged back when the commander arrives in, or is restored to, the system, so leaving and coming back shows where they left off; the most recent 60 systems are kept |
| `targets_overlay.py` | System targets overlay: one card listing the scanned bodies worth mapping (a value threshold) and the bodies with life not yet analysed, until you map or analyse them; its Settings tab and Test Card |
| `body_info_overlay.py` | Body info overlay: a card describing the body you have targeted or are close to (class, flags, scan value, temperature, gravity, atmosphere, life and geology signals, materials); its Settings tab and Test Card |
| `chemistry.py` | Element symbols and compound formulas for the Exploration displays: `element` (Sulphur is S), `gas` (CarbonDioxide is CO2), `shorten` ("thin carbon dioxide atmosphere" becomes "thin CO2 atmosphere") and `label`; symbols by default, full names by a setting on the Body info tab |
| `exobiology_overlay.py` | Exobiology overlay cards for the body you are on, each with its own switch (Settings → Overlays → Exobiology) and Overlay Placement slot: Bio status (analysed count and progress; while sampling, the species and color variant with three circles, what it pays with the first-footfall bonus, and the distance to the last sample), Biology (each genus with the species it could be or is and what each pays, and what the body could pay), Bio radar and a Sample popup; all read `organic_scan_panel.overlay_view()`, so they agree with the Organic Scanning panel |
| `exo_radar.py` | The Bio radar's pure geometry and drawing: a top-down plot centered on you, heading up, with a circle at each sample as wide as the genus's minimum distance (red inside, green clear), the ship and the SRV, and the distances to the first two samples; `build_plan` and `RadarLayout` |
| `landing.py` | Landing Assist: assigned pad, diagram on the overlay and in the panel; one render worker that retries until the overlay is up |

## Shared window kit (`plugin/uikit/`)

Spec: [WINDOW_FRAMEWORK_SPEC.md](WINDOW_FRAMEWORK_SPEC.md). Pure tkinter; nothing here imports EDMC.

| Module | What it is |
|---|---|
| `uikit/__init__.py` | Package marker for the shared window kit |
| `uikit/mapview.py` | Canvas map widget (coverage, hotspots, position, zoom) |
| `uikit/palette.py` | Color and font tokens for WNTB's own window look |
| `uikit/shell.py` | The window shell: header, body, status footer, saved geometry |
| `uikit/style.py` | Fonts and per-window skinning |
| `uikit/table.py` | `DataTable`, the replacement for `ttk.Treeview` |
| `uikit/widgets.py` | Reusable widgets (buttons, combobox, scrollbar, progress bar, tabs) |
