# Changelog

All notable changes to Wayward Nomads Toolbox (WNTB) are documented here. See
`docs/ATTRIBUTIONS.md` for acknowledgements.

## 1.4.2 - 2026-10-10

### Fixed
- **The landing pad diagram on the overlay could stay blank.** If the overlay was not running yet when docking was
  approved (EDMCModernOverlay can take a minute to start), the draw was lost until the next event. It is now retried
  until the overlay is up, and only the newest draw is kept. Switching between station types also now clears the old
  diagram straight away instead of leaving it up for 20 seconds.
- **Trade: the unsold-stock list is gone from the Session page.** Its total was a journal estimate (tonnes bought minus
  sold) and drifted high whenever cargo left without a sale WNTB could see, so it did not match what you actually have.
  The Session page now shows only exact figures: "In your ship" (the hold, with an "In hold" column) and the carrier's
  cargo. The estimate is still kept and saved with each session, and Trade History's Stock & carrier tab shows it
  labelled as a journal estimate. The **Clear stock** button went with the list.
- **Trade: ship and carrier wording is distinct.** "Ship hold" and "in / not in ship hold" for the ship; "Carrier cargo
  used / free / reserved for orders" for the fleet carrier.
- **Carrier cargo could read more than the bay holds.** Cargo can leave a carrier without a journal entry (a trade
  order or sale), so transfers alone could add up past capacity. The figure is now capped at the bay size, shown with
  a `~`, and a note asks you to open Carrier Management; the next `CarrierStats` clears it.

### Added
- **New journals are found and read automatically.** Trade now looks for journal files it hasn't read a few seconds
  after EDMC starts and then once a minute (copied over from your other computer, or played with EDMC closed), reads each
  once and adds its trades, costs, stock and carrier transfers. It remembers what it read in
  `trade_journal_scan.json`, and the foot of the Session page says how many files it has read and when it last looked.
  Nothing is counted twice and an older file never overwrites a newer carrier figure. See "Using Trade on two computers"
  in the README.
- **Documentation:** a "Using Trade on two computers" section, and the carrier quirks (open Carrier Management for the
  real figure, what `~` means) written out in the README and Trade spec.
- **Rebuild** button on the Trade Session page. The trade ledger file is local to each computer and only the journals
  sync, so a session begun on another machine was missing everything before this one first saw it. Rebuild counts
  the journals from a start time you give (UTC) and replaces the tally. (Checked on Linux only.)

## 1.4.1 - 2026-10-09

### Fixed
- **Settings pages taller than the screen pushed the OK button out of view.** Every Settings page now scrolls
  inside a height-capped frame (`settings_scroll.py`), sized to the screen; short pages look as before and the
  mouse wheel scrolls from anywhere over a page.
- **Grey bands on the Settings pages.** Rows built from plain `tk.Frame`s were painted the system grey on EDMC's
  white pages; they now take the page colour.

### Changed
- **Trade stock rows are clearer.** "aboard" and "elsewhere" became "in your hold" and "not in your hold", with a
  note under the list saying that cargo not in your hold has usually been moved to your carrier and stays listed
  until it is sold.
- **Saving a trade session now says what to do next**: the message ends "Press Reset to start a new session."
  Save never ends a session; only Reset starts the next one. The README and Trade spec explain the Save, then Reset flow.

## 1.4.0 - 2026-10-09

### Action needed
- **Every overlay is switched off once on first start** (see Changed). Tick the overlays you want again in Settings.

### Added
- **Trade mode** (the new **TRD** button), with three pages (see [docs/TRADE_TECH_SPEC.md](docs/TRADE_TECH_SPEC.md)):
  - **Session** (works offline):
    - Profit, credits per hour, tonnes bought and sold and your best sales for the session (`trade_ledger.py`,
      saved to `trade_ledger.json`). A session belongs to a commander and lasts until Reset, across game logins and EDMC
      restarts. Profit uses the game's `AvgPricePaid`.
    - **Running costs**: fuel (`RefuelAll`, `RefuelPartial`), repairs (`Repair`, `RepairAll`), **Advanced
      Maintenance** (its own line: a `Repair` whose items include "Wear"), rearm (`BuyAmmo`,
      `RestockVehicle`) and limpets (`BuyDrones` less `SellDrones`). Once any is recorded the headline is
      **Net profit** (credits per hour is the net), with the trade profit and each cost under it. Insurance
      rebuys and fines aren't counted.
    - Your ship and the landing pad it needs, the hold as used / capacity / free, and what the docked station
      would pay for it (`trade_market.py`, read from `Market.json`).
    - **Fleet and squadron carrier cargo space** (`trade_carrier.py`): used, free and reserved tonnes.
  - **Routes**: **Find routes** asks Spansh's trade-route planner for the most profitable route from where you
    are (`trade_spansh_client.py`: submit a job, poll every 5 s for up to 4 minutes). Uses your cargo size,
    credits and jump range; asks for large-pad stations when your ship needs one. **Cancel**, and **Copy next
    system**.
    Route filters (Settings → Trade): ignore prices older than N hours (default 72), ground facilities, fleet carriers
    and permit systems, all sent to Spansh's planner. Each route shows an **estimated profit per hour** (fixed
    allowances for jumps, supercruise and the stop) and the supply and demand behind each hop. The **Hops** button
    cycles 2 to 5; a route that ends where it began with every leg loaded is marked a repeatable loop.
    **Round trip** (Routes page) finds the best back-and-forth pair itself (`trade_roundtrip.py`): one station search
    for the markets near you, then a pair only counts if both legs make a profit, so there is never an empty leg. Each
    leg fills the hold best commodity first, limited by supply, demand and your credits; pairs are ranked by estimated
    profit per hour; least supply and least demand are settings (200 t). `tests/test_trade_roundtrip.py`.
    Routes start from the last real station when you're docked at a fleet carrier (Spansh can't plan from one), and a
    refusal from Spansh is shown with its reason instead of "check the EDMC log".
  - **Market**: a commodity box with type-ahead (`trade_commodity_entry.py`), a **Sell** / **Buy** choice and
    **Near me** / **Galaxy** searches. Selling ranks by what *your load* would earn (`trade_prices.py`: price x
    min(tonnes, demand)); buying uses your free hold space and puts stations that can supply it all first,
    cheapest first. Every result says whether the station is **orbital or on the ground**, its type and its
    distance from the star. Stations your ship can't dock at are left out; fleet carriers get their own section;
    a verdict line says whether the galaxy-wide best beats the best nearby and by how much. **Price finder**
    opens Mining's price finder. All the page's buttons now carry full labels.
  - The Spansh lookups are **off until enabled** (Settings → WNTB → Trade) and only run when you press a button.
- **Trade History** (saved sessions). **Save session** on the Session page keeps the current trading session when you
  ask (nothing is saved automatically; saving again updates the same entry, however many logins the session spans), and **History** opens
  a pop-out window like the BGS and Powerplay ones: pick a saved session (newest first, with a commander filter) and see
  its **Overview** (net and trade profit, running costs, per hour, tonnes, balance change, jumps, per-tonne and per-jump
  figures), **Commodities**, **Stations**, the **Route** flown (the stations visited in order with what was bought and
  sold and a running net), the full **Trades** log (paged), **Stock & carrier** as they stood when saved, and the
  **Lookups** (Spansh routes and market searches) made during it. **Copy summary**, **Export log (CSV)** and **Delete
  session**. **Reset** now offers to save an unsaved session first. New: `trade_history.py`, `trade_stats.py`,
  `trade_history_window.py`, `trade_history.json`; the live ledger now also keeps a bounded log of trades and costs with
  their station, jumps and the starting balance.
- **A trading session now spans play sessions.** It belongs to a **commander** and lasts **until Reset**, however many
  game logins, journal files and EDMC runs that takes (loading a fleet carrier over several evenings is one session), and
  each commander has their own (`LedgerBook`). Previously a new login silently replaced the session, discarding it.
- **Catch-up from the journals** (`trade_ledger.catch_up`): the first time EDMC sees a commander after starting, the
  session is brought up to date from the journal files written since its last counted event, so play with EDMC closed is
  included, with the station-by-station route. It only adds (every event is idempotent: `already_counted`), reads only the
  commander's own events, and nothing reaches History unless you press Save session. On a real journal it found the 3,795 t
  of purchases a running plugin had missed across an EDMC restart. Commodity names the journal gives in lowercase
  (`superconductors`) are now resolved to the game's name in the ledger.
- **Ship and landing pads** (`trade_ship.py`): the ship from the journal's `Loadout` gives the pad size it needs
  (pad classes from Coriolis ship data; EDMC's own ship-name table is used when available). Override in Settings.
- **Stock bought, not yet sold** (`trade_stock.py`, `trade_stock.json`): what you have spent on cargo that is still
  unsold, at average cost, with how much is aboard and how much is elsewhere. One book for both ways of trading
  (a station-to-station run, or loading a carrier for a bulk sale): buys add, sells remove, carrier transfers
  change nothing. It follows the cargo across logins and catches up from your recent journals at start. **Clear
  stock** forgets it.
- **Per-commander carrier choice** (Settings → Trade): Auto, None, Fleet, Squadron or Both, for each commander
  WNTB has seen, because not every commander has a carrier and some have both.
- **Commodity list** (`trade_commodities.py`, generated `trade_commodities_data.py` from FDevIDs): 173 sellable
  commodities for the suggestions, plus Salvage names that still resolve when typed.
- `tests/test_trade.py`, `tests/test_trade_search.py` and `tests/test_own_data_files.py`.
- Documentation: a module index (`docs/MODULES.md`, kept complete by `tests/test_docs_modules.py`), a new Trade specification, and updates to the README, the technical guide, the Mining spec, the
  development guide, the Linux checklist (section 6d) and the third-party notices.

### Fixed
- **A galaxy-wide Buy search could say "no station sells it" when many did.** Fleet carriers sell very cheaply, so
  in one price-sorted list they filled all 40 results and left no real station. Stations and carriers are now
  asked for separately (Spansh's `type` filter, two requests per search, or one if carriers are hidden), weighted
  75% stations to 25% carriers, and the "no station" message says how many were left out for pad size.
- **"The newest journal files" were chosen by name, which is wrong for this folder.** The game has used two
  file-name styles that don't sort chronologically together, so the carrier backfill could pick the wrong 40 files.
  Both backfills now order by modified time, and their line pre-filter tolerates spacing differences.
- **Mining's price finder** now uses the game's exact commodity name. Spansh's market search is case-sensitive
  ("Liquid oxygen" finds markets, "Liquid Oxygen" finds none), so typing a name in the wrong case silently
  found nothing. The price search also accepts "no distance limit" (used by Trade's Galaxy search).
- **Carrier cargo was lost whenever EDMC restarted after the carrier screen was opened.** `CarrierStats` is only
  written when Carrier Management is opened and EDMC doesn't replay old events, so every later transfer was
  ignored. The newest 40 journal files are now replayed at startup to find the last baseline and the transfers
  since. Commander names are matched ignoring case (the journal says `BOCHEAUX`, EDMC says `Bocheaux`). A
  transfer is counted for the carrier you are docked at, so another player's carrier is never mixed in.
- `trade_ledger.json` and `trade_carrier.json` are now in the updater's protected data-file list, so a
  pre-update backup no longer sweeps them up; a new test fails whenever a data file is missing from that list.

### Changed
- **Every overlay is now off by default, and existing installs are reset once.** The Inventory, Landing
  Assist and Screenshots overlays used to start on; they now start off like the rest (Discovery, Notable,
  Interdiction, Mining and the mining waypoint). On the first start of this version every overlay switch is
  turned off (`_reset_overlays_once` in `load.py`, marked by `wntb_overlay_reset_v1`), so you need to tick
  the overlays you want again in Settings. The reset runs once; your choices afterwards are kept.
- **The page arrows are much larger** in Mining, Missions and Trade: one shared `panelkit.nav_arrow`, a raised,
  bordered, padded orange button with a big bold ◀ / ▶, because the small triangles were too hard to see.
- The mode buttons at the top of the panel are left-justified instead of centered.
- **Trade's pages are laid out properly.** They were one block of text lines padded with spaces. Each page is now
  drawn in sections (orange headings with rules between them), label/value rows with the value on the right, and
  tables whose numbers line up in columns, with the station's system, type and distance on a smaller line beneath.
  Long names wrap instead of being cut off, and the page's controls (Commodity box, Sell / Buy, buttons) sit above the
  results instead of below them. New: `trade_blocks.py` (the page model), `trade_view.py` (the drawing),
  `tests/test_trade_blocks.py` and `tests/trade_view_smoke.py`.
- **Ground facilities can be left out of price searches** (Settings → Trade), like fleet carriers, so you can search
  orbital stations only.
- **The "Credits this session" line** now shows on Powerplay, BGS, Mining, Missions and Field Ops, and is hidden on
  Exploration and Trade (Trade's net profit already counts running costs). The game-mode line is unchanged.
- Settings now has nine top-level tabs (Trade sits between Mining and BGS).
- **The screenshot overlay message stays up longer** (10 seconds, 20 for the Settings test message) so it isn't
  missed when switching from EDMC to the game.

### Checked
- **Linux** (2026-10-09): the Trade panel, its type-ahead popup and the larger arrows were checked against the Linux
  checklist (section 6d) with no new issues. Windows was checked as each part was built.
- Still assumed: a squadron carrier's `CarrierStats` looks like a fleet carrier's (`CarrierType`); no real one was seen.

## 1.3.1 - 2026-10-08

### Fixed (Linux)
- **Auto-Honk stopped after about a second.** WNTB pressed the key with one `xdotool` call and released it
  with another, and XWayland releases a synthetic key roughly a second after the process that pressed it
  exits, so any hold longer than that was cut short whatever the hold-time setting said. The whole hold is
  now one `xdotool` call (`platform_support.hold_key`), so the key stays down for the full time.
- **`xdotool` and `pgrep` were invisible to a Flatpak EDMC.** The sandbox cannot see programs on your
  system, so Auto-Honk, the screenshot timer and the companion-app check reported "xdotool isn't installed"
  even when it was. Inside a Flatpak WNTB now runs them on the host through `flatpak-spawn --host`. The call
  uses `--directory=/` because EDMC's own working directory (`/app/edmarketconnector`) does not exist on the
  host and made every host call fail. A failed lookup is no longer remembered for the session, and a
  failure is logged with its reason ("Host lookup of ... failed").
- **Overlays did not draw with a Flatpak EDMC.** EDMCModernOverlay starts its drawing window through the
  host, which a Flatpak is not allowed to do by default, so WNTB's **Check connection** passed (the port was
  open) while nothing appeared. The fix is a one-time permission, now documented with the other Flatpak
  permissions in the README.
- **Keybindings and screenshots were unreadable from a Flatpak EDMC**, so Auto-Honk reported "no usable
  keybind found". The Bindings and Pictures folders need Flatpak permissions; the README lists the exact
  commands.

### Changed
- README: the Linux section is now a step-by-step setup guide (helper tools, journal folder, the four
  Flatpak permissions, binding a keyboard key for the honk, checking the overlay), and Troubleshooting has
  Linux entries for each symptom above. The "known issue" notices for Linux are removed; the Settings panel
  and the overlays have been confirmed working on Linux.
- Docs: `docs/LINUX_TESTING.md` has checks for the Flatpak permissions and `docs/TECHNICAL.md` section 18
  describes how host tools are reached from a Flatpak.

## 1.3.0 - 2026-10-08

### Known issues
- **Linux:** the WNTB Settings panel may not display correctly, and on-screen overlays do not always show.
  A fix is planned for an upcoming release. Everything that only reads the journal works as before.
  *(Resolved in 1.3.1: the Settings panel was confirmed fine, and the overlay problem was the missing
  Flatpak permission described under 1.3.1. See the new Linux setup guide in the README.)*

### Added
- **Exploration: Notable Bodies alerts.** A violet card on your in-game overlay when a body you scan matches a
  rule you have switched on. Fifteen rules: high-value body (any terraformable, plus every Earth-like,
  water and ammonia world, landable or not; it says if the body is undiscovered or unmapped), terraformable
  landable, landable above about 3 g, shepherd moon,
  5 or 6 of the premium FSD materials, green gas giant (from the Codex, or a gas giant whose class and surface
  temperature match a confirmed green one; the journal never records colour, so it is a lead to check in the
  system map), colliding binary, and eight more that start off (large landable, landable ringed, close orbit,
  close binary, high eccentricity, fast orbit, fast rotation, wide ring). Off by default; only the seven rare
  rules start ticked. Settings only, under **Exploration → Alerts**, so the main panel stays the same size.
  A moon scanned before its parent is judged when the parent arrives, a body alerts once per rule, and
  several matches in a row take turns. The thresholds are Elite Observatory's own defaults.
- **Exploration: N.S. and W.D. buttons**, next to Discovery Alerts. **N.S.** finds the nearest system whose
  **primary star** is a neutron star, and **W.D.** the nearest whose primary star is a white dwarf (any class);
  a companion star doesn't count. Both measure from your current position, show the system name and distance,
  and copy the name to the clipboard so you can paste it into the galaxy map. If you're already in such a
  system you get the next one. The lookup asks spansh.co.uk, and only when you click; nothing runs on its own.
- **Tooltips** on the shortened Exploration buttons: hover one for its full name. A.H. (Auto-Honk), D.A.
  (Discovery Alerts), N.S. (neutron), W.D. (white dwarf), RND (Random), FIND (nearest POI, GEC and Canonn),
  REF (refresh Canonn data), DET (Codex details) and BKF (Codex backfill).
- **Short button names on the other pages too**, each with a tooltip: Powerplay SES / RARES / RESCAN (Sessions,
  Rares, Rescan), BGS REPORT (report), Mining H.S. / +H.S. / PRICE / RES / I/E / BOOK, and Field Ops SHIPS / REPORT
  (Ship Builds, Colonisation). The EDMC main window is small and shared with every other plugin, so the
  abbreviations keep WNTB's panel compact. The README has a new "Button names" table.
- **Mode-select buttons shortened the same way**: P.P. (Powerplay), BGS, EXP (Exploration), MIN (Mining),
  MSN (Missions) and OPS (Field Ops), with a tooltip giving the full name and what the mode is for.
  The panel keeps the width the full-label button row had, so EDMC still opens at its usual width.

### Changed
- **Mining buttons are in one row** instead of stacked one per row: BOOK, +H.S., H.S., PRICE, RES and I/E, showing
  only the ones that apply to the page (Space or Surface) and are switched on in Settings.
- **Settings tab consolidated.** The 23 tabs across the top are now 8: General, Powerplay, Missions,
  Exploration, Mining, BGS, Field Ops and Always On, each with its own row of tabs inside where it has more
  than one. In Exploration, GEC Nearby POI, Canonn Nearby POI and Codex Completionist share one **Points of
  Interest** page, and Auto-Honk and Discovery share one **Alerts** page. Overlay Connection, Window and
  Updates are under General; Interdiction Warning and Landing under Always On. Nothing was removed.
- **The EDMC window now resizes its height to fit** when it opens, when you switch modes, and when you
  expand or collapse a section, so you no longer have to drag it taller to see everything. It also shrinks
  back when the content gets shorter. Your width and window position are left alone. Turn it off under
  **Settings → WNTB → Window**.
- **Exploration: Codex Completionist, Canonn Nearby POI and GEC Nearby POI start minimized.** Click a title
  (▸ / ▾) to expand or collapse it; WNTB remembers which you left open. The three buttons on the
  A.H. / D.A. / N.S. / W.D. row now sit 6px apart, like the mode buttons.
- **Boxel Survey's Random button moved** onto that same row (A.H., D.A., N.S., W.D., RND), so
  it's reachable while Boxel Survey is collapsed. Its status line now shows under the row.

## 1.2.0 - 2026-10-07

### Added
- **Powerplay: a Systems tab** in the Sessions window, the counterpart of the BGS report. One tab per system
  for the current Powerplay cycle (Thursday 07:00 UTC to Thursday 07:00 UTC) with a drop-down to look back at
  earlier cycles. Each tab shows the system's **standing** (state, controlling Power, control progress,
  reinforcement and undermining: baseline against latest, so a gain or loss shows even when it wasn't you) and
  **what you did** there (merits, events and estimated Control Points per activity).
- It shows the last 6 systems you've been in plus up to **5 pinned** ones (☆ Pin / ★ Unpin, × Close tab, and a
  "Show a system" box with type-ahead). Pinned and hidden tabs and the history are **per commander**
  (`powerplay_state.json`, protected from updates). Merit totals in the sessions themselves are unchanged.
- **Cycle numbers and history.** Cycles are numbered (cycle 101 began 2026-10-01 07:00 UTC; the number counts
  weeks from there). The Systems tab shows a **cycle total** line (merits, estimated Control Points and
  systems worked across every system), and a new **Cycles** tab lists every cycle for the commander: period,
  the Power they were pledged to, systems, merits, CP and a per-activity breakdown. Up to 52 closed cycles
  are kept. Each commander has their own history and Power; an unpledged commander still gets standing
  readings and shows "not pledged".
- **Daily tab**: the merits and estimated Control Points (whole numbers) earned on each day of a cycle, with a
  cycle total. Day 1 starts when the cycle does (Thursday 07:00 UTC) and each day runs 07:00 to 07:00 UTC; pick
  the current cycle or any in the history. A ledger saved before days were tracked is rebuilt once from the
  journals on the next start to fill them in.
- **Start-up journal scan** for each commander, done only as far as needed. WNTB works out what cycle it
  is, which cycles aren't in that commander's history yet and how many days back to read (a new commander
  rebuilds the last 4 cycles; after that only the gap since EDMC last saw the journal is read, and nothing
  when you were just playing). Cycles you played while EDMC was closed are counted, archived in order and
  never double counted; a cycle with no activity shows as an empty row, so the history has no holes. The
  Cycles tab says what the scan did. New setting: **Powerplay > Journal scan > Cycles to scan** (1-12).
- Reads `PowerplayStateControlProgress`, `PowerplayStateReinforcement` and `PowerplayStateUndermining` from
  `FSDJump`, `Location` and `CarrierJump`. New `powerplay_ledger.py`, `powerplay_state.py`,
  `powerplay_systems_tab.py` and `tests/test_powerplay_ledger.py`. See `docs/POWERPLAY_TECH_SPEC.md` section 11.

### Changed
- **Settings tab consolidated.** The 23 tabs across the top are now 8: General, Powerplay, Missions,
  Exploration, Mining, BGS, Field Ops and Always On, each with its own row of tabs inside where it has more
  than one. In Exploration, GEC Nearby POI, Canonn Nearby POI and Codex Completionist share one **Points of
  Interest** page, and Auto-Honk and Discovery share one **Alerts** page. Overlay Connection, Window and
  Updates are under General; Interdiction Warning and Landing under Always On. Nothing was removed.
- **Powerplay Current Session tab:** its explanatory notes now span the full window width, re-wrap on resize and are
  pinned to the bottom of the tab. The Systems tab's cycle summary line is pinned to the bottom as well.
- **Notes at the bottom of the Powerplay Systems, Cycles and Daily tabs** now span the full width of the window
  and re-wrap as it is resized (they wrapped at a fixed width, leaving a narrow column), in larger text. The
  Systems legend is shorter, and each system's tab scrolls so a short window never hides a table.
- **Work in progress.** Boxel Survey, Powerplay and BGS now say so, with a request for feedback, in the README
  and at the foot of their Settings tabs. The Powerplay README section and specification were rewritten to cover
  the Systems, Cycles and Daily tabs, cycles, the journal scan and the per-commander separation.

### Fixed
- **Powerplay Sessions window freezing** while open (it showed when clicking the Cycles tab). Every journal event
  rebuilt all five tabs (about 0.6 to 1.2 seconds on a real history), so a burst of events locked up EDMC. The
  window now redraws once, shortly after the last change, only for the tab being shown (others are drawn when you
  select them), and a table whose rows haven't changed is left alone (`DataTable.set_rows`). `Tabs` gained an
  `on_select` callback for this.

## 1.1.5 - 2026-10-03

### Fixed
- BGS: mission influence is now credited to the system it actually lands in, not the system the mission was
  handed in at. Each influence entry's `SystemAddress` is resolved to a system (as BGSTally does); if it is
  unknown, the issuing faction's influence goes to the system the mission was accepted in, and only as a last
  resort to the hand-in system. See `docs/BGS_TECH_SPEC.md` section 4.2.

## 1.1.4 - 2026-10-03

### Added
- **"You are in <mode> mode."** (Open, Solo or Private Group, with the group's name) and **Credits this
  session** now sit directly under the mode buttons, visible in every mode, in one section with a separator
  before the page content. Each is its own module (`game_mode.py`, `session_credits.py`) and neither depends on
  Powerplay any more: they track the game mode and the balance themselves, from the journal, and keep their own
  saved record (`session_credits.json`). The credits line reads "+N cr earned" or "-N cr lost", with an hourly
  rate once the session is a few minutes old.
- Settings now state which systems each OS-dependent feature works on, and whether it can work on your
  machine right now (a **Works on:** line, green or orange): Auto-Honk, the Screenshots auto-timer and Thargoid
  capture, the Inventory pickup sound, and the Overlay Connection tab (which says the older EDMCOverlay is
  Windows-only). The BGS tab shows the Linux journal-folder hint.
- README has a new **Platform support: Windows and Linux** section (what works where, what is Windows-only,
  what is Linux-only). `docs/TECHNICAL.md` section 18 lists every file, folder and command each system uses and
  records the audit of all 126 modules. A BGS section was added to the Linux test checklist
  (`docs/LINUX_TESTING.md`).

### Changed
- **Settings tab consolidated.** The 23 tabs across the top are now 8: General, Powerplay, Missions,
  Exploration, Mining, BGS, Field Ops and Always On, each with its own row of tabs inside where it has more
  than one. In Exploration, GEC Nearby POI, Canonn Nearby POI and Codex Completionist share one **Points of
  Interest** page, and Auto-Honk and Discovery share one **Alerts** page. Overlay Connection, Window and
  Updates are under General; Interdiction Warning and Landing under Always On. Nothing was removed.
- Powerplay no longer shows or tracks credits or the game mode: gone from its page, from the Sessions window's
  Current tab, and from the Sessions history table and totals (old saved sessions keep their data, it is just
  not shown).
- EDMC's `monitor.logfile` can be a `Path` or a `str` depending on the version; WNTB now always treats it as a
  string, so saving the session records can't fail on a `Path` (Powerplay's session store included).
- Corrected out-of-date wording in the BGS code comments.

### Fixed
- **Linux: screenshots were not found.** Elite writes the screenshot path with Windows backslashes even under
  Proton, and Linux didn't split on them, so WNTB couldn't find the file to convert and treated hi-res shots as
  normal ones.
- **Linux: modal dialogs could fail to open.** Seven dialogs (Mining hotspot add/edit, find hotspots, find best
  price, check ring reserve, import/export hotspots, and ship builds) now wait until the window is on screen
  before taking the modal grab, which X11 requires.
- Linux hardening for the BGS report: the close-tab button uses a character every font has, and the "Show a
  system" suggestion list sizes itself correctly on X11 and no longer closes on a stray focus event while you
  type. With no Journal directory set (the Linux default), BGS now logs why it can't rebuild the tick's totals
  from your journals instead of skipping silently.
- The Screenshots tab said auto-capture "requires Windows", although it also works on Linux with `xdotool`.
- The self-updater no longer writes a zip entry that points outside the plugin folder (`..`, absolute path or
  another drive).
- **The WNTB Settings tab disappeared (Windows and Linux)** in one of the withdrawn builds: a "Works on:" note
  was packed into one of EDMC's own frames, which EDMC does not allow, so building the Auto-Honk tab raised an
  error and EDMC dropped the whole WNTB Settings tab. Two new tests (one that builds the whole Settings tab with
  EDMC-faithful stand-ins, one that checks the source) stop it happening again.

## 1.1.0 - 2026-10-03

### Changed
- **Settings tab consolidated.** The 23 tabs across the top are now 8: General, Powerplay, Missions,
  Exploration, Mining, BGS, Field Ops and Always On, each with its own row of tabs inside where it has more
  than one. In Exploration, GEC Nearby POI, Canonn Nearby POI and Codex Completionist share one **Points of
  Interest** page, and Auto-Honk and Discovery share one **Alerts** page. Overlay Connection, Window and
  Updates are under General; Interdiction Warning and Landing under Always On. Nothing was removed.
- **BGS panel now shows only the system you're in**: each faction's state and influence (with how far
  each moved since before the tick) and what you've done to it this tick. The Track/Untrack buttons and
  the tracked systems/factions lists are gone - BGS records wherever you act, so there's nothing to set up.
- **BGS Report rebuilt**: pick the tick from a drop-down, then one tab per system you've acted in, each
  with a Factions table and a "What you did" table.
- BGS now counts decreases as well as increases: failed and abandoned missions, trade losses, and crimes
  against a faction, alongside the existing mission INF (+/-), vouchers, trade and exploration data.
- **Report tabs**: they show the last 6 systems you've been in, each with its full name. **Pin** keeps a
  system's tab (marked with a star) at the front; **Close tab** hides one; **Show a system** shows any system (it pins it,
  and brings back a closed tab): pick from a dropdown of every system you've been in, or type and the list
  filters as you go. The panel shows the star when you're in a pinned system.
  Pins and closed tabs are saved per commander.
- The report's activity columns have plain-English headings, and a key at the bottom of the window explains
  each one.
- Totals are per tick. On start, WNTB re-reads your recent journals so they are cumulative since the last
  tick even if EDMC wasn't running; each closed tick is archived. New setting **Keep previous ticks for
  N days** (default 7) under Settings -> BGS.

### Fixed
- The WNTB settings tab now appears on Linux. The Mining and BGS settings lists used Windows-only
  colour names, which made the whole tab fail to build on other systems.

### Development
- `npm run package` no longer needs PowerShell, so it works on Linux. `npm run build` now detects your
  OS and EDMC's plugins folder, and the new `npm run deploy` copies the build straight into it.
- Added `.gitattributes` so line endings stay LF on Windows and Linux.

## 1.0.1 - 2026-10-02

### Fixed
- The release ZIP now extracts correctly on Linux and macOS. It was built with backslash path
  separators, so those systems created flat files with names like `icons	imer.gif` instead of folders.
  The ZIP is now named `WNTB.zip` (no version number) and contains a single `WNTB/` folder.
- README install steps now cover Linux as well as Windows.

## 1.0.0 - 2026-10-02

First public release. The entries below are everything 1.0.0 ships with, built up during development
before release.

### Code optimisation and maintenance
- Missions and Mining code reorganised for clarity and easier maintenance, with no change to how they behave.
- Removed unused code.
- More unit tests for Missions and Mining.
- Documentation brought up to date across the README and `docs/`.
- Overlay: when no overlay program is running, WNTB now stops retrying for 30 seconds after a failed
  connection, so it costs almost nothing, and logs it once. A new **Check connection** button on the
  Overlay Connection settings tab tests the host and port, and a changed host or port applies straight away.
- Fewer web requests: Earth-like-world rarity and EDSM upload-status lookups are now remembered, so
  repeating them for the same system costs no extra calls. Every request to an outside service now says
  it comes from WNTB, with its version and project address.
- New "Keeping API traffic low" section in `docs/TECHNICAL.md`, and a note in the README on supporting
  the services WNTB uses.

### Codex Completionist: sorting, Not found tab, references
- **Found** tab: click the **Entry** heading to sort A–Z / Z–A and **Times found** for most/least found first.
  Sorting keeps the category groups intact.
- New **Not found** tab: every biological, civilisation and stellar-body entry in Canonn's catalog that you
  haven't found, grouped by category and sortable by entry, type or platform. The catalog is cached
  (`codex_catalog.json`) and refreshed in the background when over two weeks old, or with **Refresh Catalog**.
- Double-click an entry on either tab (or **Open Reference**) to search for it on canonn.science.
- Found entries now remember their journal `EntryID` for matching against the catalog.

### Field Ops: Inventory Cargo tab
- The **Inventory** window now has a **Cargo** tab: tonnes carried against hold capacity, with the same
  near-full and full colour cues as the other tabs, and the commodities aboard (Filter box applies).
  It follows the vehicle you are in (ship or SRV hold) and says so when on foot.

### Field Ops: Colonisation
- New **Colonisation** section in Field Ops: tracks each construction depot's outstanding commodities
  from the `ColonisationConstructionDepot` / `ColonisationContribution` journal events, and compares
  them to the cargo in your hold. **Colonisation Sites** window with per-site groups, Copy Shopping
  List, Remove Site and Remove Finished. Per-commander data in `colonisation_sites.json`.

### New look for every external window (shared `plugin/uikit` kit)
- All of WNTB's pop-out windows now share one dark design: **Powerplay Sessions**, **Rare Goods**,
  **Inventory**, **BGS Report**, **Codex Completionist**, **Ship Builds** (window and dialog), the
  Missions popups, the Screenshots preview and the Mining dialogs. Tables are flat, striped and
  sortable; tabs, buttons, dropdowns and scrollbars are WNTB's own.
- Main-window panels are unchanged and still follow EDMC's theme. The new look never touches EDMC's
  global theme or other plugins.
- Behaviour and wording in those windows are unchanged. Window sizes scale with display scaling, and
  windows now appear once, fully drawn, instead of flashing at a default size first.

### Mining: Mining Book
- New **Mining Book** window (button on both Mining pages): bodies you've scanned plus every saved hotspot
  on the left, a body's hotspots grouped by location in the middle, and a detail card with a
  zoomable map on the right. Filter by material or rig count; Edit, Mark depleted, Copy coordinates
  and Delete from the card, plus a one-line summary of the materials you've saved on the body.
- **Tons left** is shown as a range worked out from Rigs, Amount and Density. Note a lower Density label
  means a larger deposit.
- Rigs is limited to 1-7. Saving a hotspot within 100 m of an existing one on the same body updates
  it instead of adding a duplicate. Refined tons are credited to the nearest hotspot, so a depleted
  deposit shows what it gave (`depleted (612 t)`).
- **Your own rates:** for a scanned body the browser shows what *you* have found so far on that kind
  of body (share of your saved deposits per material, with the sample size), marking the ones you
  have already saved there. Picking a material in the filter keeps the scanned bodies whose kind you
  have found it on, highest share first. It starts empty and fills in as you save hotspots.
- The coverage minimap uses colour-blind-safe markers (shape carries "depleted") and, in the ship,
  only appears below 2 km altitude.

### Powerplay: Rare Goods Finder
- New **Rares** button in Powerplay mode opens a window listing the nearest rare commodities to your
  current system (origin system, station, pad size), with each origin system's **current controlling
  Power** looked up live from Spansh. Double-click a row to open it on Inara; **Show nearest** sets how
  many rows (1–141, remembered).
- Bundled static dataset of 141 rare goods (`plugin/rare_goods.json`); only the controlling Power is
  a network call, cached for the EDMC session.
- New modules: `rare_goods.py`, `rare_goods_window.py`, `powerplay_control_lookup.py`, with unit tests.
  Config keys `wntb_rares_window_geometry` and `wntb_rares_limit`.

### Linux support (new, experimental)
- **Auto-Honk** and **timed screenshot capture** now work on Linux through `xdotool` (X11 and
  XWayland). Elite's bindings and screenshot folders are found inside the Steam Proton prefix
  automatically (including extra library folders and Flatpak Steam), with a Settings override for
  Lutris, Heroic or custom prefixes.
- New shared `plugin/platform_support.py`, with unit tests. Pickup notification sound uses
  `canberra-gtk-play`/`paplay`.
- Codex backfill and screenshot GuiFocus no longer misbehave when EDMC has no default journal
  folder (common on Linux).
- **Journal folder hint:** Settings → Auto-Honk (and the EDMC log) warn when EDMC's Journal
  directory doesn't match Elite's folder inside the Proton prefix.
- **Fixes for case-sensitive filesystems:** the screenshot GuiFocus lookup asked for `status.json`
  and now asks for `Status.json`, which Elite actually writes. `journal_scan.py` no longer fails when
  no journal folder is configured.
- **Windows-only text gated:** OneDrive folder handling and the Windows security-blocked message no
  longer apply on Linux.
- Overlay features work on Linux through EDMCModernOverlay; no code change was needed (documented).
- Not yet verified on a real Linux install; see `docs/LINUX_TESTING.md`.

### Docs
- **README** rewritten as a plain-language user manual: what each mode does, install steps for the
  pre-release, which features use the internet, Linux setup, troubleshooting and how to get help.
- **New `docs/DEVELOPMENT.md`**: setting up to build, test and change WNTB.
- **New feature specifications** for Missions, Mining, Organic Scanning, Powerplay and Screenshots and input
  automation, and a plain-language **overlay setup guide** (`docs/OVERLAY_SETUP.md`).
- **New `docs/TECHNICAL.md`**: architecture and design rationale.

### License
- **WNTB is GPL-3.0.** See `LICENSE`.

### Fixes
- **Window width** — EDMC's main window no longer widens and narrows as you switch between modes. Every
  mode now shares one fixed width (the width of the mode buttons) and wraps its content to fit; Mining and
  Missions were the widest because of a default scroll-area width.
- **Self-updater** — `_OWN_DATA_FILES` listed only four of WNTB's data files, so backups swept up
  the rest. It now lists all of them, and `mining_sessions/` is in `_OWN_DIRS`. (Updates never
  overwrote data files, since none are in the release zip.)
- **Mode buttons** — BGS now sits next to Powerplay (was at the end, after Field Ops).
- **Organic Scanning** — Active scan now lists one species per line, matching Predicted Species'
  own one-per-line formatting (was pipe-joined onto a single line).
- **Organic Scanning** — Predicted Species and Active Scan now clear immediately on a system
  change (FSDJump/Location), instead of continuing to show the previous system's body until
  Status.json happened to report a new BodyName.
- **Discovery Alerts** — System-discovery and first-scan/first-map alerts now render inside a
  bordered, semi-transparent card (matching Landing's own chrome), instead of appearing as bare
  floating text over the HUD.
- **Overlay backgrounds (Discovery, Interdiction, Mining, Screenshots)** — Every card-style overlay
  now registers an EDMCModernOverlay Plugin Group, like Landing/Inventory already did. Without one,
  a card's background rect rendered invisible under EDMCModernOverlay, so only the text and border were
  showing.
- **Settings window** — WNTB's entire Settings panel (every tab, not just BGS) failed to open at
  all, throwing `_tkinter.TclError: unknown option "-fg"` from a BGS tab label that used the
  classic Tk `fg=` option on a themed `ttk`-backed `nb.Label`, which only accepts `foreground=`.
- **Discovery Alerts** — Title and system/body name are now horizontally centered in their card
  (independently, since they're usually different lengths), instead of left-aligned.

### BGS mode (new)
- New BGS mode, all four planned phases: faction-state tracking (War, Election, Boom, Bust,
  Outbreak, etc.), mission/bounty/combat-bond/trade/exploration activity tallying, and BGS-tick
  detection that automatically rolls the tally into a new period when a real tick happens (polls a
  community tick-time service every 60s — the only network call this mode makes, toggleable
  separately in Settings). See `docs/BGS_TECH_SPEC.md` for the full field-by-field breakdown and
  the known gaps (murder/crime, combat-zone participation, Thargoid states, Discord export) that
  are deliberately out of scope.
- **Track**/**Untrack** buttons directly on the BGS panel, acting on whatever system you're
  currently in — no need to alt-tab to Settings and retype the system name. Unlimited systems.
- The panel always shows a live breakdown of your *current* system regardless of tracking status:
  "no factions present" for uninhabited systems, or a count of every faction present, who controls
  it, and each one's current state.
- **View BGS Report** now has two tabs — Faction States, and Activity Tally (split into This Tick /
  Previous Tick) — with Copy Summary covering both.
- All BGS data (tracked lists, faction snapshots, activity tally, last-known tick) is per-commander
  and persists across restarts.

### Field Ops mode
- **Ship Builds** — moved from always-visible to Field Ops mode only, alongside Screenshots and
  Inventory.

### Exploration mode
- **Organic Scanning** — per-body habitability conditions, detected genera, and confirmed-species
  scan progress now persist per commander (`organic_scan_state.json`), so a body's known biology is
  still there after logging out and back in instead of resetting (a relog starts a new journal file,
  which replays none of the original `FSSBodySignals`/`Scan`/`ScanOrganic` events).
- **Boxel Survey (Sequence)** — Export Survey Log moved off the main panel to Settings → Boxel
  Survey, where it's joined by two new opt-in checks: an automatic EDSM lookup that suggests a
  nearby real system after 3 consecutive Next clicks with no actual jump (a small mass-code boxel
  running out of real candidates), and "Confirm off-sequence arrivals against EDSM," which catches
  a target that resolved under a different in-game display name instead of silently stalling.
- **Boxel Survey (Region Sweep)** — new "Auto-discover more nearby cubes (EDSM)" Settings toggle
  keeps the queue topped up from EDSM once you're down to your last incomplete cube, so it keeps
  handing you new ones instead of running dry.
- **Boxel Survey** — Sequence/Region Sweep/Waypoints target position now persists per commander,
  restored automatically when that commander is next seen (including switching commanders on the
  same install) instead of being shared globally.
- **Boxel Survey** — new "Random" button above the whole panel (works regardless of sub-mode, even
  collapsed): finds a real EDSM-known boxel near your live position, then probes candidate names in
  it until it finds one EDSM has no record of at all, and copies that name straight to the clipboard
  for pasting into the galaxy map search — a quick way to go looking for something genuinely
  undiscovered nearby.
- **Boxel Survey (Random)** — Random now also checks a persistent, per-commander log of every system
  you've actually jumped to (recorded regardless of sub-mode), so a system you've already visited but
  haven't uploaded to EDSM yet is never re-suggested as "new." Settings → Boxel Survey shows a live
  count and a "Clear Visited Systems Log" button for wiping it per-commander.
- README's Boxel Survey section now includes a which-mode-should-I-use guide (Sequence vs. Region
  Sweep vs. Waypoint Route).

### Initial build
WNTB is a mode-switching toolbox: one plugin, one panel with a collapsible section per mode.

- **Powerplay mode** — Merit/CP/income tracking, session log, Inara-clipboard export.
- **Exploration mode**:
  - Auto-Honk, Discovery Alerts — shown side by side.
  - **Boxel Survey** — Sequence / Region Sweep / Waypoint Route boxel-walking with EDSM-assisted
    skip filtering and a notable-finds survey log; collapsed by default.
  - **Exploration Value** — estimated scan payout, current system age, and current galactic region
    (one of the 42 named regions, e.g. "Inner Orion Spur"), plus opt-in ELW rarity comparison
    (Spansh) and EDSM upload-status readouts. The region readout backfills from the current journal
    on a mid-session EDMC restart.
  - **Organic Scanning** — exobiology species prediction, scan-stage tracking, distance guidance,
    and galactic-region/Guardian-proximity/trace-atmosphere/tuber-zone/co-located-body matching.
  - **Codex Completionist** — personal per-species scan tally with a journal-history backfill.
  - **GEC Nearby POI** — on-demand nearest-point-of-interest lookup against edastro.com's Galactic
    Exploration Catalog.
  - **Canonn Nearby POI** — on-demand nearest-Thargoid/Guardian-site lookup against Canonn
    Interstellar Research's own published site lists, skipping sites you've already logged in the
    Codex.
- **Mining mode** — Space/surface (Rhino) mining tracking, hotspot catalog, EDSM ring-reserve and
  Spansh price lookups, driven-coverage minimap, scanned-bodies list.
- **Missions mode** — Active mission tracking across every category, massacre kill-progress
  estimation, Community Goals, wing-status badges.
- **Field Ops mode**:
  - Screenshot capture, auto-crop, and thumbnail management.
  - On-foot/cargo inventory tracking, suit/backpack capacity bars, pillage notifications.
- **Always visible** — Landing Assist (pad diagram/overlay) and Interdiction Warning (Settings-tab
  only); **Ship Builds**, a per-commander catalog of links to builds designed on external shipyard
  sites (Coriolis, EDSY, Spansh, etc.).
- **Shared infrastructure** — One EDMCOverlay/EDMCModernOverlay connection, one self-updater, one
  Settings-driven main panel with a collapsible section per mode.
