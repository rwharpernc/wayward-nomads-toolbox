# Changelog

All notable changes to Wayward Nomads Toolbox (WNTB) are documented here. See
`docs/ATTRIBUTIONS.md` for acknowledgements.

WNTB hasn't had a real public release yet — everything below is pre-1.0 development, kept under one
running "Unreleased" heading rather than versioned sections, until it's fully tested and ready to
launch as v1.0.0.

## Unreleased (pre-1.0 development)

### Code optimisation and maintenance
- Missions and Mining code reorganised for clarity and easier maintenance, with no change to how they behave.
- More unit tests for Missions and Mining.
- Documentation brought up to date across the README and `docs/`.
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
  and Delete from the card, plus a one-line summary of the materials you've saved on the body. It replaces **Search Known Hotspots** and **Show System Bodies**.
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
- **New `docs/TECHNICAL.md`**: architecture and design rationale.

### License
- **WNTB is GPL-3.0.** See `LICENSE`.

### Fixes
- **Self-updater** — `_OWN_DATA_FILES` listed only four of WNTB's data files, so backups swept up
  the rest. It now lists all of them, and `mining_sessions/` is in `_OWN_DIRS`. (Updates never
  overwrote data files, since none are in the release zip.)

### Fixes
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
  a card's background rect rendered invisible under EDMCModernOverlay (confirmed via a live report,
  2026-09) — only the text and border were showing. See `overlay.py`'s
  `register_modern_overlay_groups()` docstring for the full history (this supersedes an earlier,
  now-disproven "don't group a single background rect" lesson).
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
  Spansh price lookups, driven-coverage minimap, System Bodies survey.
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
