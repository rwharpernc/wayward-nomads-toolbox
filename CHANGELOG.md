# Changelog

All notable changes to Wayward Nomads Toolbox (WNTB) are documented here. See
`docs/ATTRIBUTIONS.md` for acknowledgements.

## Unreleased

### Added
- **System targets card.** A list of what is left to do in the system you are in: scanned planets and moons worth mapping that you have not mapped (an estimated scan value at or above a threshold you choose, most valuable first), and bodies with life you have not finished analysing, until you map or analyse them. It shows the scan progress after the honk and clears when you jump. Off until ticked in Settings → Overlays → System targets.
- **Body info card.** A card describing the body you have targeted or are close to: class, flags (undiscovered, terraformable, mapped), estimated scan value, temperature, gravity, pressure, atmosphere, volcanism, life and geology signals, distance and main materials. Off until ticked in Settings → Overlays → Body info.
- Both cards have a Test Card, their own entry on Overlay Placement (new default spots in the lower middle of the right half of the screen), and are rebuilt from the newest journal when EDMC starts in the middle of a system.
- **System targets can look up bodies other commanders have scanned** (EDSM), so it lists worthwhile planets with an estimated value right after the honk instead of waiting for your own scans. Off until you tick *Also look up bodies other commanders have scanned* in Settings → Overlays → System targets; it asks once per system and sends only the system name. Looked-up bodies are marked `EDSM` and your own scan replaces them.
- **Exobiology cards** (Settings → Overlays → Exobiology): four overlay cards for the body you are on. *Bio status* shows how many biological signals you have analysed and, while sampling, the species and color variant with three sample circles, the reward (five times as much on a first footfall) and how far you are from the last sample against the distance the genus needs. *Biology* lists each genus with the species it could be or is and what each pays. *Bio radar* plots your samples with a circle at each as wide as the genus's minimum distance (red while you are inside it), your ship and your SRV. *Sample popup* names each sample as it is taken. A plant identified with the Composition Scanner is named until you sample it. They use Organic Scanning's own prediction and tracking.
- **The Biology card shows the range a body could pay.** A genus whose species is not yet named shows `1.0M - 5.3M CR` and each candidate its value and a percentage (an even share, `~50%`, because the data says which species the body's conditions allow and not how likely each is); the footer reads `Rewards: 7.6M - 11.9M CR`, with the first footfall figure on its own line (`First footfall (5x): 38.2M - 59.6M CR`) so it does not wrap. Bio status shows the first footfall bonus on its own line too.
- **The Exobiology cards lead you back to plants you identified.** The location of a plant scanned with the Composition Scanner is kept (up to four plants of each genus per body, across restarts). The Bio radar and Bio status follow the most recent unsampled plant of **each genus** you have identified (three genera, three pointers), each in its own color: a ring with the genus's letter and a line from you on the radar, a row under the plot with a little pointer turned toward it and the distance, and a line on Bio status with the distance and direction. A plant drops off when you sample it and the genus moves to its next plant; analysing a genus clears its pointers.
- **First footfall.** The Body info card now flags a landable body nobody has set foot on (`First footfall`) and says exobiology pays five times there, and the System targets card marks a body with life where the first footfall is still open (`1/3 life FF`). It comes from the scan's `WasFootfalled`, the same field the Exobiology cards use for the five times reward.
- **Element symbols and formulas on the Body info card.** Materials are written as element symbols (`Fe 18.4% · S 18.2% · Na 3.0%`), and the atmosphere, its composition and the volcanism as formulas (`thin CO2`, `CO2 100.0%`, `minor SO2 magma`), the way the periodic table and ordinary chemistry write them; a choice on the Body info tab gives full names instead. The names live in one place (`chemistry.py`).
- **Mapping estimates.** The estimated value of scanning and mapping a planet (first discovered and first mapped, first mapped only, or already mapped, with the efficiency and Odyssey bonuses) is now worked out (`scan_value.py`), added to the Expedition Log's unsold estimate when you map a body, and shown as `Mapped value` on the Body info card for a planet you have not mapped.
- **Expedition Log.** An archive of your exploration expeditions: the new **Expedition Log** row in Exploration (START, STOP, LOG) and the LOG window to start, stop, resume, reset and **rescan** an expedition from your journals, name it, and edit its start and end, start and end location, ships used and notes, with a table of every expedition, a recap, Copy summary and Export CSV. Each expedition counts, from your journal, systems, jumps and light-years, bodies scanned and first discoveries, bodies mapped, landings, new codex entries, the credits earned from selling exploration data, and for exobiology the samples, species analysed, first footfalls and the credits earned from selling exobiology data, with estimates of the unsold scans and species. An overlay card keeps the running expedition's totals in view (Settings → Overlays → Expedition Log). Kept per commander; separate from the Expedition planner.
- **Start since my last sale** (Expedition Log window): begins an expedition just after your last exploration or exobiology sale (the earlier of the two), takes the totals your journals give since then, and carries on counting live, so you can pick up an expedition you were already on. For Mactavious Actual this gives an expedition from 2026-09-25, whose exobiology estimate matches OD Explorer's to the credit (209,995,500) and whose exploration estimate is within 0.2% of it.
- **System targets remembers where you left off.** Each system's survey is now saved for each commander (the 60 most recently visited systems) and comes back when you return, whether
  after a relog, a break or a later visit; for a system you were in before this existed it is rebuilt from your own journals (the newest 80). The card has a summary line (`1 mapped · life 1 of 3 done`)
  and a **Done** section listing the bodies you have finished, so after a break you see what is left and what is finished. The card no longer shows `1 of 27 scanned` when you had scanned them all on an earlier visit.
- **A drag-and-drop layout editor on Overlay Placement.** A to-scale picture of your screen with a grid (20, 40, 60 or 120 pixels) and a box for every display: drag a box where you want it and the spot and offset are filled in for you. A box dropped near an edge snaps flush to it (offset 0), near the middle snaps to the center line, and otherwise to the grid. The table below it still works and the two stay in step. A **Picture size** choice (Default, Large, Extra large) makes the picture bigger and is remembered.
- **Panel opacity** (Settings → Overlays → Appearance): choose how solid every WNTB display's background is, from 100% down to 25% (90% is the default and the scheme's own); the text stays solid.

### Changed
- **Plain card panels.** The Route, System targets, Body info and Exobiology cards (and the Bio radar) are now a plain dark panel: the wide colored bar down the left edge and the outline around the card are gone, leaving the text, thin dividers and progress bars.
- **A cleaner look for the Route, System targets and Body info cards.** A heading, a progress bar for the system scan, thin dividers, section labels, values aligned to the right (or in a second column), and a muted second column for tags and distances. A long message now continues on the next line instead of being cut off.
- The System targets and Body info cards now hide when the game closes or is at its main menu (so they no longer linger while another commander signs in), while docked, and in hyperspace, and a different commander loading in clears the system the last one had scanned.
- Every genus is shown in full: the System targets card lists a body's genera on lines of their own under its row, and the Body info card wraps long values (genera, atmosphere, volcanism) within their column instead of cutting them with an ellipsis.
- The Body info card now appears for a body you have targeted but not scanned yet, and says to scan it (the journal has nothing else on it until then).
- Organic Scanning now keeps where each sample was taken, the color variant the sample named, and whether the body had been footfalled before.
- The overlay card drawing is shared (`overlay_card.py`) by the Route, System targets and Body info cards, and the scan-value formula is its own module (`scan_value.py`). The Route card looks the same.

### Fixed
- **The Expedition Log card now says what to do when nothing is running.** With the card switched on and no expedition started it showed nothing at all; it now reads `No expedition is running` with how to start one (START in the Exploration panel, or LOG → Start since my last sale).
- **A plant you have sampled now leaves the tracked list reliably.** A Log or Sample drops the genus's nearest tracked plant within about 100 m (about 150 m when it is the same color variant), up from 40 m, because the scanner names a plant from a distance, so the position it records can be well away from where you stand to take the sample; with no position to go by it drops the plant identified last.
- **The scan value estimate was wrong.** The base value used the mass to the power 0.566 instead of 0.566 times the mass to the power 0.2, and an Earth-like world was not always counted as terraformable, so the estimates on the Exploration Value readout, System targets, Body info and the Expedition Log were off (too high for most bodies). The formula now matches EDDiscovery's (Apache-2.0), and OD Explorer's figures agree with it.
- **The cards reset when you leave a planet.** The Exobiology cards (Bio status, Biology, Bio radar) stayed on the planet you had finished until another body was named; they now clear as soon as `Status.json` names no body (you have left the planet), and what you sampled is kept and comes back if you return. The Body info card no longer holds on to a targeted body that is finished (mapped by you and all its life analysed), so it can show the next one; it still shows a body you are close to. System targets already drops a body once you have mapped it or analysed its life.
- **A relog no longer loses the system's scans.** The System targets, Body info and Exobiology cards are rebuilt from the journals when EDMC starts or you log in, and now read back through the earlier journals of the same commander while you have stayed in the same system (up to eight), so a body scanned before a relog still shows, with its first footfall flag. The Exobiology cards also take the first footfall flag from that rebuilt survey when Organic Scanning has not seen the body's scan.
- The Bio status progress bar now moves with each sample (a third of a genus per Log or Sample, all of it once analysed) instead of only when a genus is analysed, and the sample in progress is still shown after EDMC or the game restarts part-way through.
- **Exobiology circles and the Bio radar drew away from their cards.** Circles were not moved with the rest of a placed card, so the sample dots and the radar's circles landed at the card's unplaced position and could drag the rest of the card with them.
- **A zero offset at a bottom or right edge now sits on the edge.** Cards (Route, System targets, Body info and the Exobiology cards) were placed using their largest possible size, so a card shorter than that stopped short of the edge; they are now placed from the size they are drawn at.

### Documentation
- A new guide, [Exobiology](docs/guide/exobiology.md), brings the Organic Scanning panel, the four overlay cards, plant waypoints and first footfall into one place (they were spread across the Exploration guide); the Organic Scanning specification covers the overlay view, waypoints and first footfall; Troubleshooting, Getting started, Overlay setup, Technical notes, Status, Linux testing and the attributions are brought up to date.
- Added a note on Linux support to the README and the Linux and platform guides: the author uses Linux (CachyOS) and Windows about equally, and new features are proven on Windows first, so Linux follows slightly behind.

## 1.15.0 - 2026-10-16

### Added
- **The running expedition on the Route card, and survey tracking per stop.** With the Route overlay on, the card shows the running Expedition: its name and progress, what was found at the stop you are at, the next stop with its distance, that stop's note, and the stop just reached (a tick under Settings → Overlays → Route turns it off). Each stop now counts the bodies scanned, the first discoveries and the bodies mapped in its system (and how many bodies the system has, once you have honked), shown in the Expedition row, in a new **Found here** column of the window, and on the card.
- **Route overlay.** A card with the ship's travel status (fuel, jump range, the fuel the last jump used, jumps and light years left, the next supercharge) over the systems of the route plotted in the game. Neutron stars and white dwarfs are picked out so the supercharge can be prepared for, and other stars that cannot be scooped are marked. Off until ticked in Settings → Overlays → Route; it has a Test Card and its own entry on Overlay Placement. It follows the ship along the route and clears when the route ends, is cleared, or the ship jumps off it.

### Changed
- **Default overlay spots moved** to make room for the Route card: it takes the top left; Surface Compass moved to the top right (between Notable and Inventory), and Mining stats, Flight Alerts and Missions each moved down the right-hand column. A spot you chose yourself is not changed.
- **Every overlay is left-justified.** The Discovery and Notable Bodies alerts centered their title and name inside the card; they now start at the card's left padding, like Landing, Interdiction, Missions and the rest.
- **Every overlay card uses the same padding.** Text sits the same distance from the border on all sides in Colonization, Discovery, Notable Bodies, Interdiction, Landing, Missions, Flight Alerts, Mining, Surface Compass and Screenshots (`CARD_PAD_X`/`CARD_PAD_Y` in `overlay_style.py`). The Discovery and Interdiction cards no longer have a minimum width, so they fit their text instead of leaving a blank strip on the right.
- **Documentation.** American spelling throughout; text that no longer matched the program was corrected; new notes on where Odyssey stat data was looked for, how it is checked in the game, and a checklist of data that is missing or still to be verified (`docs/data_verification/`). The project's method is stated in `docs/ATTRIBUTIONS.md`.
- **Overlay text is never drawn at the overlay's "small" size**, which is hard to read over the game. The Text size choice is now Default or Larger; a saved "Smaller" is treated as Default.

## 1.14.1 - 2026-10-15

### Fixed
- **The Credits Ledger's Lifetime tab was empty.** The game's totals were read in the background but only picked up while a journal rebuild was running, so a commander whose rebuild had finished saw nothing. They now appear after start-up.
- **Rebuild from journals now shows what it is doing.** The window says "Reading your journals...", greys the button while it runs, and ends with how many income events were read and how the total changed (or why it could not run).

## 1.14.0 - 2026-10-15

### Changed
- **Sections always start folded.** Expedition, Boxel Survey, Materials, Notes and the other fold sections now start folded every time EDMC starts; opening one lasts for that session only. **Ship Builds** (Field Ops) is now a fold section too.
- **Bigger page names in Mining and Trade.** The name between the arrows is bold, as in Missions.
- **The main panel no longer folds.** The "Wayward Nomads Toolbox (WNTB)" title row that collapsed the whole panel is gone; the mode buttons are always shown. Sections inside the modes still fold, and start folded.
- **No history on the mode panels.** A panel now shows the present only; the past lives in report windows. Trade's Session page no longer shows the game's lifetime totals (which mixed in Mining and Exobiology) or the "Journals reviewed" line, and the Colonization panel no longer lists its History block. Colonization history is in a new **Colonization History** window (the **HISTORY** button: Overview, By day, Commodities and Sites tabs).

### Added
- **Credits Ledger.** Click the "Credits this session" line under the mode buttons. It adds up what you earned by activity and by day, per commander, kept apart: Trade (market profit), Exploration data, Exobiology data, Mission rewards, and Bounties and bonds, with Today, Last 7 days, Last 30 days and All counted. Past income is counted once from your journals in the background, and **Rebuild from journals** does it again. The **Lifetime** tab holds the game's own career totals (trading, mining, exobiology, fleet carrier), moved off Trade. Mining has no per-day income because the journal does not say which commodity sold was mined; its lifetime profit is on the Lifetime tab.

## 1.13.0 - 2026-10-15

### Fixed
- **Notable-body alerts show their full text.** The card cut a body name at 24 characters and a title at 28 with an ellipsis, and sized its width from a plain character count, so capitals and digits ran past the edge. Real names and titles now show in full (the limits are only a guard against runaway text), and the card width is measured with capitals, digits and wide letters counted wider. The new-system and new-body discovery cards use the same measure.
- **Missions overlay card no longer cuts a long place.** When a mission's title and place do not fit on one line, the place goes on a line under the title, in the same color, so a long station or system name shows in full.

### Added
- **Progress you can see, in color.** The Missions window now shows progress for source-and-return (Collect) missions, which the game does not report until you hand cargo in: the tonnes of that commodity in your hold against what the mission asks for (`36/60 held`), updating as you buy and sell. Progress is also drawn as a small bar, and rows and overlay lines are colored by it: green when ready, lime when half or more done, blue when started (time pressure, red and amber, still comes first). The overlay card colors massacres too, using the combined progress of a stack.

## 1.12.0 - 2026-10-15

### Added
- **Missions window, and pinned missions.** The Missions panel gets two buttons at the very bottom, **Missions window** and **Find sources** (they replace the **All** link and the Commodities needed link), and the first opens a full window (it replaces the old All popup and the per-mission detail popup): an **Active** tab with every mission's title, kind, faction, where to go now, progress (cargo `80/200`, kills `~18/40`), reward and time left, ready ones first in green and the soonest to expire in red or amber; a **By place** tab grouping the missions by the system to hand them in at, with your system and the next jump first; a summary line (missions, ready, expiring under an hour, pinned, rewards held); and a detail strip for the selected mission. **Pin / Unpin**, **Pin all here**, **Unpin all**, **Copy system** and **Sources** (the Source commodities window) are in the header. A pinned mission is listed first on the Missions overlay card under **PINNED**; pins are kept per commander and go with their mission.
- **Best picks (Trade → Market) and Source commodities (Missions).** Four answers to "where do I buy or sell this?", the way EDCoPilot gives them: **Closest** (the nearest station with it in stock, or that wants it, for the landing pad you need), **Best local** (the best price within your Near me radius), **Cheapest anywhere** (or highest, when selling) and **Recommended** (the nearest station within 10% of the best price in the galaxy). If no station has the whole amount, the pick says how much the nearest has; a fleet carrier is only mentioned if it beats the cheapest station. In Missions, **Find sources** on the Commodities needed list opens a window with the four picks for each commodity your Collect and Mining missions still need, measured from where you are or from the turn-in system, with **Copy system** for the galaxy map. Both ask Spansh only when you press the button and only with Trade's online lookups on; about four requests per commodity. The price search can now ask for a minimum stock and a price range.
- **Missions on the overlay.** A small card for flying, off until you tick it (Settings → Overlays → Missions): the missions for the system you are in (**HERE**), then those for the system you have targeted for the next jump (**NEXT**), then the rest soonest to expire, up to the number of rows you set, then `+N more in M systems`. A finished mission shows a tick and the place to hand it in and is listed first; under an hour left is red, under six hours amber, and a mission ready to hand in is always green. Massacres and raids against one faction, and any missions with the same title for the same station, stack into one line with a count; a cargo mission shows its progress. Lines are cut to one fixed width (the time left always shows) and the card sits in a corner (bottom-right by default, above the screenshot messages; move it in Overlay Placement). Everything comes from the Missions mode and the journal's jump events; nothing is sent or stored.
- **The Upgrade planner can read your own suits and weapons.** **Read my gear** lists the suits and weapons you own from your journal (the loadouts the game writes when you log in on foot, plus later upgrades); picking one fills in the item, its class now and the modifications it already carries, which use up modification slots and are not planned again. It reads only the commander of your newest journal and nothing is stored.
- **Upgrade planner** (Engineering window, Upgrade planner tab). Pick an Odyssey suit (Artemis, Dominator, Maverick) or weapon (Karma, Manticore, TK), the class it is now and the class you want, and up to four modifications, and see each step's materials and credits; **Add to wishlist** puts the steps and modifications on the Wishlist tab in one go (all or nothing), so its shopping list shows what you hold and what you are short of. Credits are shown for the eight items whose cost has been seen in real journals (Karma AR-50, C-44 and L-6, Manticore Tormentor and Executioner, and the three suits); for the others the planner says the credits are not recorded and still plans the materials. A modification's engineer fee is not counted, and there is no stat preview.
- **Megaship scans per Powerplay cycle.** WNTB now keeps a list of the megaships whose datalink you scanned (the *Scan datalinks at Megaships* activity): the new **Megaships** tab of the Powerplay Sessions window has one row per megaship with its name, the system, when you scanned it and the merits the scan earned, the live cycle first, and the Powerplay panel has a line under the cycle tally (`Cycle 103 megaships: 5 (2,340 merits)`). The journal does not name the ship in the scan, so the name is the megaship you dropped out of supercruise at just before it, checked against the FSS list for the system or the word "class" in its name; a scan at anything else is not counted. A megaship counts once per system per cycle. The first start after this release reads your journals back (the Settings scan depth, 4 cycles by default) and fills in the earlier cycles. Each commander has their own list. The idea of counting these scans follows ODEliteTracker; the code is WNTB's own.
- **The Ship planner can subtract what your current ship already has.** Tick **Subtract what my current ship already has** and WNTB reads the ship you are flying from your newest journal (its last `Loadout` event; nothing is stored) and leaves out what it holds: for a module in the same slot with the same blueprint, the grades up to its level, and an experimental effect it already carries. A module that is completely done says **already done**, and the summary counts them. It only subtracts when the build is the same kind of ship as yours, and says so when it is not; a different blueprint in the slot is not subtracted from. With no ship found it says so and subtracts nothing.

### Changed
- The Missions panel's category title between the arrows is now bold and full size (it was two points smaller than the rest of the panel and hard to read).
- **Find sources, From where I am, did not know your system** when EDMC was started after the game (or reloaded) and you had not jumped since. It now asks EDMC, then reads your newest journal; if even that has nothing it measures from the turn-in system and says so, instead of stopping. **Pin all here** in the Missions window uses the same lookup.
- **Find sources** is always reachable (a button at the bottom of the panel, on every page) and, when Trade's online lookups are off, asks whether to turn them on instead of doing nothing; with no cargo missions it says so.

### Fixed
- **The suit and weapon upgrade costs in the blueprint table were out of date.** They were EDEngineer's old figures (1, 5, 10 and 15 of each material); the game now charges 1, 2, 4 and 5 for the schematic, the family item and Manufacturing Instructions (or Health Monitor) and 2, 5, 9 and 12 for the other two materials, for classes 2 to 5, and a suit no longer needs a Power Regulator. Corrected from 17 upgrade events in real journals. The Manticore Oppressor's duplicate "Opressor" row is merged.

### Documentation
- `THIRD-PARTY-NOTICES.md` gained an entry for the Rare Goods Finder's table (game facts with ids looked up once from EDSM, Inara and Spansh); every bundled data table now has one.

## 1.11.0 - 2026-10-15

### Added
- **Show only Bubble or Colonia engineers.** The Engineers tab has a **Show** box (Both, Bubble, Colonia) with a count (`8 of 38 engineers`). Colonia is the 8 engineers within 500 ly of Colonia (Baltanos, Eleanor Bresa, Etienne Dorn, Marsha Hicks, Mel Brandon, Petra Olmanova, Rosa Dayette, Yi Shen); the other 30 are the Bubble. The choice is remembered, and an engineer filtered out is deselected.
- **Ship planner** (Engineering window, Ship planner tab). Paste a ship loadout exported from EDSY or Coriolis as SLEF (or a `Loadout` line from your journal), see each engineered module with its blueprint, level and experimental effect, and press **Add plan to wishlist** to put every grade on the wishlist at once. **Rolls per grade** (1 to 10) says how many crafts to plan for, since the journal cannot tell how many rolls a grade takes; an experimental effect is one craft. The same blueprint on several modules is added together, a pre-engineered module takes nothing, and a module WNTB's table does not cover is listed as not counted with the reason. If the plan would pass the wishlist's limits (100 blueprints, 99 crafts each) nothing is added. Nothing goes online. The journal's blueprint names (80) and experimental effects (90) are matched to the table's by `plugin/journal_blueprints.py`, generated by the new `scripts/gen_journal_blueprints.py`. The idea follows Odyssey Materials Helper's ship builder; no code or data was taken from it.
- **Report an issue** button (Settings → WNTB → General → Help). It opens a new bug report on GitHub in your browser with the WNTB, EDMC and Python versions and your operating system (Windows build, or Linux distro, X11 or Wayland and Flatpak) already filled in. Nothing is sent by WNTB: you read and edit the form, and submit it with your own GitHub account. No commander name, system or file path is included. The form is `.github/ISSUE_TEMPLATE/bug_report.yml`.
- **Copy diagnostics** button (same Help tab). It copies the version lines and the newest WNTB lines of EDMC's log (up to 80 lines, tracebacks included) to the clipboard, to paste into the report's log box. Your commander name is replaced by `<commander>` and your home folder by `~` first; WNTB's own lines only, and the text stays on your clipboard until you paste it. A commander name is only caught if WNTB can tell it (EDMC's current one and the one in the newest journal), so read the text before posting it.

### Changed
- **Engineering data brought in line with the author's ED-DDT**, which applied EDDiscovery's data (Apache-2.0; notice in `THIRD-PARTY-NOTICES.md`):
  - Five synthesis recipes corrected: AX Remote Flak Munitions +10%, Chaff Launcher 100% Refill +2 Seconds Duration, Flechette Launcher Munitions +10%, Guardian Gauss Cannon Munitions, Guardian Plasma Charger Munitions +30%.
  - Seven synthesis rows added (Caustic Sinks, Configurable Small Calibre Munitions in two grades, Mining Rig, Nanite Munitions, Seismic Charge Munitions, Sub-Surface Displacement Munitions) and nine Thargoid-war and chip materials (146 materials; 1,176 blueprints).
  - Three duplicate "Higher Accuracy" weapon rows removed (the "Improved Hip Fire Accuracy" rows already cover them).
  - **The four Colonia on-foot engineers now offer their suit and weapon upgrades** in the blueprint table (31 rows), so the wishlist's "who can do it" counts them.
- **The Engineers tab shows where each engineer is and how to unlock them.** All 38 engineers are listed with their base, system and planet ("on foot" or "permit needed" where it applies), and until unlocked what gets you invited and what unlocks them. Select one for how to find them, how to gain standing, whether they work on foot (no ranks), and a known quirk (Terra Velasquez's meeting requirement is reported bugged). A line below gives the net profit that opens each ship-engineer grade. This replaces the hand-written notes for the Colonia four, whose places the table now confirms.

### Fixed
- **The field-ops guide no longer says the blueprint table lacks experimental effects.** It has them (as grade 0 entries). They were not part of the check against real journals, so the guide now says their recipes are less certain.
- **BGS history now includes play made while EDMC was closed.** A period that closed while EDMC was not running was filed with only what WNTB had seen live, so a tick that ended while it was closed showed nothing (or too little) in the history. When a tick closes a period, that period is now rebuilt from your journals (the journals are the source of truth) and filed over the live record, keeping any faction only the live record had. It reads back 14 days at most; an older period stays as it was filed. Several ticks missed in a row cannot be told apart, so the play across them lands in the period that closed. Matches a fix the author made in ED-DDT.
- **A finished colonization build no longer shows the game's "Construction Site:" prefix** in the sites window, the shopping list and the history (`Orbital Construction Site: Wayward Station` becomes `Wayward Station`). A finished build becomes an ordinary station under a new market ID, so the depot's saved name never changed. The saved name itself is untouched, and a site still being built keeps its full name.

## 1.10.2 - 2026-10-14

### Changed
- **Long names in the main panel wrap instead of being cut off.** The Colonization page cut a site name at 30 characters (`Orbital Construction Site: Wa...`) and a project, system or commodity name at 22 to 40; those limits are now 64 and 40, and the text wraps at the window's width. The Expedition, Materials, Notes and Trade watch list lines used to wrap at a fixed 200 px even in a wide window; they now use the whole width of the window (never less than 200 px, so a narrow window is still never widened), and their name limits are higher (expedition name 60, system 64, note 160; material 40; Notes system 64 and note preview 120; watch list commodity 32).
- **The Colonization panel's History heading names the commander** (`History - SILAS KADE`), so it is clear whose figures are shown.

### Fixed
- **Busiest site shows its name, not `Construction site <number>`**, for depots WNTB is not tracking. The journal's delivery event names a depot only by number, so WNTB now learns the name and system from the `Docked` at it (read once from your journals for each commander, and kept as you dock). A depot never docked at in the journals still shows its number.

## 1.10.1 - 2026-10-14

### Fixed
- **The Expedition and Materials sections no longer make the main panel wider** on Linux. In Expedition, "Copy on arrival" now sits on its own line under COPY and EXPEDITION; in Materials, BLUEPRINTS sits under MATERIALS instead of beside it.

## 1.10.0 - 2026-10-14

### Added
- **System-name suggestions in every box that takes a system name** (Expedition stops and planner, the trader finder, Colonization's *Around*, mining
  hotspots and ring reserve, Notes, Waypoint Route and the Boxel Survey and Region Sweep seeds). From the second letter it suggests the systems you have
  been in and ones WNTB already holds, and **Down**/**Up**, **Enter**, a click and **Escape** work as you would expect; **Enter** with nothing highlighted
  still does what the box did. A new setting, **Suggest system names from Spansh while typing** (Settings → Window, off until ticked), also asks Spansh
  for matching systems from the third letter, so systems you have never visited come up too; the letters typed so far are all that is sent.
- **Material trader finder** (**Find a trader** in the Materials window). Finds the closest station with a Raw, Manufactured or Encoded material trader
  to your system (or one you type), nearest first, with whether it is in space or on a surface, its distance from the star and its largest landing
  pad; filter by distance and pad size, and double-click a row to copy its system name. It shows what you hold of that type by grade and how many
  are at the game's limit. Pressing Find sends Spansh the system name and the type, nothing else.
- **Engineering blueprints and a wishlist** (Field Ops, the **BLUEPRINTS** button on the Materials section opens the Engineering window). Browse
  about 1,170 blueprints (ship modules, Guardian items, Technology Broker and engineer unlocks, synthesis, Odyssey suit and weapon upgrades) by
  search and module type, see who offers each, its effects and what one craft takes against what you hold and where each ingredient is found. Add
  blueprints to a wishlist with a number of crafts; it says which can be made now (worked out in list order) and gives one shopping list for the
  whole wishlist. Ship materials are counted from the Materials counts and on-foot items from your ship locker; trade goods are shown but not
  counted. An **Engineers** tab shows where you stand with each engineer (from the game's engineer list: Known, Invited, Unlocked with rank,
  including rank-ups), what they offer and what unlocking them asks for, and the wishlist says who can do each entry. The four Colonia on-foot
  engineers, which the recipe table lacks, are added by hand: their unlock steps, places (from one guide, unconfirmed) and the items Yi Shen needs. The recipes are a copy of EDEngineer's table (MIT, last changed March 2024), so newer game content may be missing. Kept on your
  computer for each commander.
- **Materials: what you hold of each engineering material** (Field Ops mode, a **Materials** section; **MATERIALS** opens the window). Raw,
  Manufactured and Encoded materials with their grade, the most the game lets you hold (300, 250, 200, 150 or 100) and the room left. The
  section shows the pieces of each type, the last pick-up or discard, and which materials are at the limit. The window has a search box, type and
  grade filters, "only what is at the limit" and sortable columns. Counts follow the journal (the full list at login, then pick-ups, discards,
  trades, synthesis, engineer crafts, the Technology Broker, engineer contributions and mission rewards) or, when WNTB starts mid-session,
  EDMC's own totals. Kept on your computer for each commander and never sent anywhere. Engineers and blueprint needs are not here yet.
- **Expedition planner** (Exploration mode, an **Expedition** section; **EXPEDITION** opens the window). Plan a trip as a named list of stops, each
  with an optional body and a note, then press Start: arriving in a stop's system ticks it off, and the section shows how many stops are done, the
  jumps, light-years and time so far, the next stop with its distance and note, and the stop you just reached. **COPY** (or **Copy on arrival**, off
  until ticked) puts the next stop's name on the clipboard for the galaxy map. Add stops by hand, from the route plotted in the game or from a CSV;
  reorder by nearest neighbor (the positions come from EDSM, the only online part, which sends only system names); share as a list or a CSV. Keep
  several expeditions and run one at a time. **Road to Riches** and **Exomastery** buttons in the window ask Spansh's planners for the most valuable
  bodies to scan, or the most valuable biological planets, near a route and turn the answer into a new expedition (only when you press **Plot**; it
  sends Spansh the start system, the end if you give one, and the numbers you chose). A system typed in any case is spelled properly (`sol` becomes `Sol`) from the game's own spelling or from EDSM, which also supplies its position (a box under the editor turns that check off; it sends only the name). Adding the first stop makes an expedition for you, and
  **Rename** offers the current name to edit. Kept on your computer for each commander. Waypoints (Boxel Survey) is unchanged.

## 1.9.1 - 2026-10-13

### Fixed
- **Colonization overlay: the card shows when the journal's Market event reaches EDMC late.** The overlay now also watches the game's
  `Market.json`, so the card appears even when the Market event arrives late (seen on Linux under Proton).
- **Overlay placement: a position that is off the overlay's canvas no longer hides the display.** An exact position outside the canvas
  (such as a leftover `x = 1280`) now falls back to the display's default spot.
- **Layout fits any font.** Quick-add boxes and button rows are capped in pixels, the Trade page's figures drop to the small font and its
  title wraps instead of widening the window, and the Trade History window widens to fit its tables.

### Changed
- **Overlay appearance: a Text size choice is back** (Smaller, Default, Larger; it starts at Larger), and every text-width estimate is
  padded by 10% so overlay boxes hold their text.

### Documentation
- Troubleshooting: a workaround for a display saved off the screen, an entry for Raven Colonial not updating (sharing is off until the
  master switch is ticked), and a list of the settings that start off and need ticking when a feature seems to do nothing.

## 1.9.0 - 2026-10-13

### Added
- **Trade: a Watch list of the commodities you care about** (a collapsible **Watch list** row in Trade mode; **WATCH** opens the window).
  Add commodities with the type-ahead box and see the best price to buy and to sell each. Prices come from the markets you open (read from the
  game's own market file, nothing sent anywhere) and, when you press **REFRESH** with Trade's lookups on, from Spansh near your system. The
  window shows where each price is, how much stock or demand it has, where it is from and how old it is, every market a commodity was seen
  at, and Spansh's five best stations for each side. Kept on your computer, per commander.
- **Surface Compass, with marks: the Mining waypoint arrow, grown up.** An arrow, a name and a distance on your game screen pointing at a spot on
  the planet you are on, from any mode (not only while Mining's Surface page is open). It points at the nearest hotspot you have recorded, as the
  old arrow did, or at a **mark** you made, or at nothing. A new **Compass** section in Exploration mode has **MARK** (save where you are, with a
  name you type or `Mark 1`, `Mark 2`...), **TARGET** (step through the hotspot, the marks on this body, and nothing) and **MARKS**, a window to
  see every mark with its distance from you, change a name, body or position (typing one is fine) and delete. Marks are kept on your computer,
  for the commander who made them, and never sent anywhere. Off until ticked (Settings → Overlays → Surface Compass, with **Test Compass**).
- **Notes on a system or body** (Exploration mode, a **Notes** section; a **NOTES** button opens the window). Write a line about the system you
  are in, and the section shows how many notes it has and the newest when you arrive. The window has a search box, a list of every note
  and an editor, with **Here** to fill in where you are. Notes are kept on your computer for the commander who wrote them, are never
  sent anywhere, and Delete asks twice.
- **Flight Alerts: a fleet carrier jump countdown and fuel warnings on one small overlay card** (Settings → Overlays → Flight Alerts, off
  until ticked). The countdown follows a scheduled jump to its departure time, turns red in the last minute and is read back from your
  journals if the game or EDMC is restarted. The fuel warnings say when the tank is low (at a percentage you choose) and, the one the game
  does not give, when the star you have plotted to cannot be scooped and the tank is at or under a second percentage. An optional sound plays
  when an alert starts. The journal gives no per-jump fuel cost, so the fuel warnings compare percentages of the tank, and the guide says so.

### Changed
- **Overlay default spots no longer overlap, on a 1920 x 1080 screen or larger.** The Interdiction warning moved up (above the Discovery
  alerts, which moved down a little), the Notable find card moved to the top right (above the Inventory display, clear of the
  Colonization list), and the Flight alerts card is anchored from the top so it stays below the Inventory display on any screen height. This
  changes where a display sits only if you have not placed it yourself; a position you chose on Overlay Placement is unchanged. A test now
  fails if any two defaults overlap. On a smaller screen the displays, which are sized in pixels, take up more of it and can overlap: use
  Overlay Placement there.
- **The Mining tab's *Enable Surface Waypoint Overlay* tick is gone**: that arrow is now the Surface Compass. If you had it on, the compass is on
  and keeps the position you gave it (and whether you had hidden it). The overlay placement row is now called "Surface compass".
- **The COL page's REPORT button is now DASHBOARD.** It still opens the Colonization Sites window; only the name changed (button, tooltip
  text, guide and testing notes).
- **Colonization, Find all: fewer requests and better coverage from the "sells everything" search.** That search now runs first. A
  commodity one of its stations can supply in full is not searched on its own, and when the route still leaves two or more commodities
  uncovered, one more request finds stations that sell all of them, using each returned whole market to cover any other listed commodity
  the nearest-five searches missed.

### Documentation
- **One common thread through the documentation: WNTB works from what the game writes to its journal.** A third-party tool only knows
  what Elite Dangerous journals, and not everything is logged. A new section, "How WNTB knows what it knows", in the README and the
  guide index sets out the three layers (the journal; Frontier's data through a signed-in EDMC and what players and community services
  report; and labelled workarounds), and the theme is now carried through every mode guide (an opening note on where that mode's
  information comes from, and a rewritten "What the game does and doesn't tell us" introduction), Getting started, the internet page,
  Troubleshooting, the technical guide and its mode specifications, and the development guide. Until Frontier expands the journal or
  offers a broader API, the workarounds are part of how WNTB works.

## 1.8.1 - 2026-10-13

### Fixed
- **Landing overlay: the "no diagram" box and its caption are laid out as one centered picture.** The caption beside the placeholder
  box used a fixed-width area, which left a wide empty strip to its right and wrapped it unevenly. It now wraps into three even lines,
  and the card is as wide as the box and caption need. The pair is centered in the card allowing for the fact that the overlay's text
  runs narrower than WNTB's (deliberately wide) estimate, so it no longer sits to the left with a gap on the right. A longer station
  name still widens the card, and the pair stays centered in it. At a larger text size the lines get wider rather than reflowing.
- **Shopping list overlay: the title line is no longer cut short.** The title is the game's full site name ("Orbital Construction
  Site: Wayward Station"), and anything past 40 characters was cut off with "…". It now holds 64, and the card widens to fit it.

### Documentation
- Colonization guide checked line by line against the COL page, the Sites window, Planned Builds and the settings. Corrected: the overlay
  setting's name, a "HIDE" button label that never existed, the window's filters, the header buttons and menus (all now listed), the
  COL page's "Others" line, and the site name (a renamed site follows on the next dock). Carrier Management and Rescan Carrier are
  explained side by side in the guide, the README and Troubleshooting.

### Changed
- **Colonization Sites window: the Remove menu is now called Manage Sites.** It still holds Remove Site and Remove Finished.

## 1.8.0 - 2026-10-13

### Added
- **Links to Raven Colonial.** Settings → Colonization → Raven Colonial has a link to the page where you get your key
  (ravencolonial.com/user). The Raven Colonial menu in the Colonization Sites window can open the selected site's own project page,
  its system, or the Raven Colonial home page in your browser.
- **Settings → Colonization → Raven Colonial: a Test key button.** It asks Raven whether the key in the box is accepted, with a read
  that changes nothing, and shows the name Raven gives you. The settings text is corrected too: the master switch is about writing to
  Raven (the two lookups in the sites window never needed it), and the key is saved when Settings closes.
- **Colonization, Find all: finds stations that sell the whole list.** Find all now makes one extra Spansh request for the nearest
  stations (and carriers, if asked) that have every commodity in stock, and adds any it finds under each commodity. The shopping route
  can then use a station that is not among the nearest few for any single commodity. Spansh seldom has one station for a long list,
  so for most lists nothing is added; if the request fails, Find all carries on without it.
- **Colonization: click a search result to copy its system.** Clicking a row in the where-to-buy results (a station, or a stop in the
  suggested route) copies its system name, ready to paste into the galaxy map search. Copy System still works.
- **A Show checkbox for every display on the Overlay Placement tab.** Unticking it hides that display whatever its own settings say; its
  spot and offsets are kept for when you tick it again. Reset all to defaults shows everything.
- **Share your colonization progress with Raven Colonial (opt-in, off by default).** Settings → Colonization → Raven Colonial, behind a
  master switch that stops every write to Raven at once (including Report Complete) while keeping your other choices. WNTB
  sends the depot's figures and your deliveries as they happen, links your commander to the project, and (a second switch) the tons you
  move to and from your fleet carrier as plus and minus amounts. It only sends live events for a site Raven already has a project for,
  one request each, and never uses Raven's `supply` call. A **Raven Progress** button in the Colonization Sites window reads Raven's
  figures for the selected site and sets them beside WNTB's. Not yet checked against the live write API, which needs a key; see the
  guide for what is sent and for the warning not to run two reporting tools at once.
- **Rescan Carrier.** A button in the Colonization Sites window that rebuilds the fleet carrier (FC) tally from the last 30 days of
  journals, for a transfer that did not register, for example after Frontier's lagging copy of the carrier's cargo replaced it.
- **Report a finished build to Raven Colonial.** A **Report Complete to Raven** button in the Colonization Sites window marks the
  selected site complete on Raven Colonial. It asks first, needs your Raven key (saved per commander) and sends only that key and the
  project's id. Not yet checked against the live Raven Colonial write API, which needs a real key.
- **A "Merits this session" line** under the credits line, e.g. `Merits this session: +1,234 (+567 merits/hr)`. It appears after
  your first Powerplay merit of the session and shows on every mode.

### Fixed
- **Writes to Raven Colonial now name the commander as well as the key.** Raven Colonial's own web page sends both with every call
  (`rcc-key` and the commander's name in `rcc-cmdr0`); WNTB sent only the key, so Raven may have turned its writes away. Report
  Complete, progress, deliveries, carrier cargo and Test key now send both. Not yet seen to work against a real key: use Test key.
- **Raven sharing sends nothing without a key.** Progress and deliveries used to be sent with no key at all. Raven's published API
  description does not say whether it accepts that, so WNTB now looks up and sends nothing until a key is saved for the commander, and
  says so in the status line. The Settings text and the guide now list what each option needs; Raven Progress and Planned Builds only
  read, and need no key or switch.
- **Colonization: a renamed site takes its new name.** WNTB kept the name it first saw for a site. Docking at a site you already track
  now updates its name (and system) to what the game calls it, both live and when WNTB catches up from the journals at start-up. Raven
  Progress and the Raven sharing find the project by that name for a build in progress, so they follow a rename too. WNTB does not
  rename anything on Raven Colonial; rename it there yourself, as you did.
- **Raven Progress (and sharing to Raven) said there was no project for a build in progress.** Raven Colonial only records a site's
  market id once the build is finished, so matching on the market id found nothing for a site still being built. The match now falls
  back to the station's name (a build in progress first). This also fixes sharing depot progress and deliveries, and Report Complete,
  for those sites.
- **Powerplay: the pledge rank (and merit total) was the one from login after restarting EDMC mid-game.** WNTB recovered the
  pledge from the login `Powerplay` event only, so a rank that had climbed since (for example 15 at login, 32 now) showed the old
  number. It now also reads the newest `PowerplayRank` and `PowerplayMerits` events for your Power from the same journal.

### Changed
- **Colonization Sites window: tidier header.** Planned Builds, Raven Progress and Report Complete to Raven now sit under one
  **Raven Colonial** menu, and Remove Site and Remove Finished under a **Remove** menu. Copy Shopping List and Rescan Carrier stay as
  buttons. Nothing else about them changed.
- **Shopping list overlay: the OVERLAY button is the switch.** It now turns the card on or off and stays as you left it, even after a restart.
  The Settings option is renamed "Also show the shopping list automatically" and explains that leaving it unticked means only the button
  controls the overlay.
- **Colonization Sites window: the commodity table is a shopping list like the overlay.** A **Group by category** checkbox (on by default)
  puts the commodities under market-category headings, alphabetical inside, in SrvSurvey's order, and a commodity the docked market does not
  sell is grayed out with "(not available here)" unless your ship and carrier cover it. Sorting by a column shows a plain list.
- **Overlay shopping list: SrvSurvey's order, and dimming what the market does not sell.** At a construction site the rows are
  alphabetical as before; at a market or the carrier's inventory they are grouped under the market's categories (a heading for each,
  alphabetical within it). A commodity the market you are docked at does not sell is grayed out (a much fainter gray) with "not available" after its name, unless
  your hold and carrier already cover it. Category headings are in capitals in the title color, and the commodities under them are indented.
- **Overlay text size and spacing are fixed.** Settings -> Overlays -> Appearance now only has the color scheme. Every overlay uses one
  size (one step above normal) with the default padding and line spacing, so the shopping list's columns stay aligned. Earlier saved
  size, padding and spacing choices are ignored.
- **Colonization shopping list on the overlay: more columns, and a wider card.** It now shows **Commodity, Required, Remaining,
  FC, Cargo and To buy** (FC only with a fleet carrier). **Need** is now called **Remaining** and **Ship** is now **Cargo**; **To buy**
  is remaining less the hold and the carrier. The card widens to fit.
- **The lines under the mode buttons show on every mode.** The credits line is no longer hidden on Exploration and Trade, so the
  whole block (plugin version, game mode, credits) is the same everywhere.

### Documentation
- Documentation audit for this release: the README's Colonization notes and its planned list now describe the opt-in Raven Colonial
  sharing, Test key and the page links; the Colonization guide lists the new menus, links, click-to-copy and what each Raven option
  needs; the internet page covers every new request and link; two new Troubleshooting entries (Raven Progress finding no project, Test
  key refused); the technical notes describe the Raven headers, key check, name matching and renames; Linux checklists cover the new
  header menus, links and Test key; the version examples in Getting started follow 1.8.0.

## 1.7.1 - 2026-10-12

### Added
- **A plugin version line in the EDMC panel.** The first line under the mode buttons says **Plugin: vX.Y.Z**. When an automatic
  update has been downloaded it becomes a bold black-on-orange **vX.Y.Z download - Restart EDMC**, so the restart is hard to miss
  (it replaces the small notice in the title row, which could be missed if the download finished while EDMC was still starting).
  Clicking it opens the release page.

### Fixed
- **The "update downloaded" notice could be missed.** If an automatic update finished downloading before EDMC had built the WNTB
  panel, the notice was dropped. The panel now shows the current state when it is built.

### Documentation
- The README and Acknowledgements credit CMDR Bocheaux (Wayward Nomads) only.
- Getting started describes the plugin version line and the restart that applies an update.
- The Linux checklist has the version line and the 1.7.0 features to check.

### Developer
- `tests/test_powerplay_backfill.py` no longer depends on today's date.
- New smoke test for the plugin version line (`tests/test_version_line_smoke.py`).

## 1.7.0 - 2026-10-12

### Added
- **Powerplay panel: a cycle tally under the session tally.** Two new lines, **Cycle N merits** and **Cycle N CP**, total
  what you have earned across every system in the current Powerplay cycle (Thursday 07:00 UTC to the next). Unlike the
  session lines they carry over between game sessions, include what the start-up journal scan filled in, and reset when
  the cycle rolls over. They come from the same per-commander ledger as the Sessions window's Systems tab.
- **Boxel Survey: the survey log catches up from recent journals.** Notable bodies and biological signals scanned while EDMC was closed (the
  last 14 days) are now added at start-up, along with the systems that were missing. A system the log already had keeps its scanned count,
  nothing is counted twice, and the game's journals are only read.
- **Trade, Round trip can start from a fleet carrier.** When you are docked at a fleet carrier (your own, say) the round trip now starts
  from its market instead of the last ordinary station, and the result says where it started. Routes still cannot, because Spansh's
  route planner does not know carriers.
- **Trade, Round trip: more detail on every pair's loads.** Each leg of each of the three pairs now lists its commodities with tonnes,
  profit, the price you pay, the price you get, the profit per tonne and the supply and demand behind it (three per leg, then "+N more").
- **Planned Builds shows what each building costs.** Each planned or building site gets a **Full cost** (the tons the whole build needs,
  from a table bundled with WNTB), the window adds up what the system's planned builds need, and clicking a row names the building
  and its five biggest commodities. The table is a copy of SrvSurvey's cost data (GPL-3.0; credited in the Acknowledgements and the
  third-party notices) and can lag the game.
- **Colonization: Planned Builds.** A new button in the Colonization Sites window opens a window with the build sites Raven Colonial has for
  the selected site's system, including builds that are only planned (the journal never reports those): building first, then planned,
  then complete, with the type and body, and a mark on the ones you track, and it names the system's architect and whether it is open or
  locked. It asks only when you press the button and sends only the system's name.
- **Trade, Routes: the wait says what Spansh is doing.** While a route search runs, the page now says whether it is waiting in Spansh's
  queue or being calculated, instead of only counting seconds.
- **Colonization, Find all: a suggested shopping route.** After Find all, the results start with the few stops (at most 6) that between
  them supply the most of what you still have to get, with what to buy at each and the stops nearest first. **Copy Route** copies it.
  Find all's commodity headings also no longer get cut off.
- **Trade: choose the round trip search radius.** A new Trade setting sets how far around your start the round trip search looks (5 to 500
  ly); 0, the default, keeps the old behavior of twice your jump range between 20 and 100 ly.
- **Colonization History: a Claims line.** How many systems you have claimed, how many you released and how many colonisation beacons
  you deployed, counted from the game's `ColonisationSystemClaim`, `ColonisationSystemClaimRelease` and `ColonisationBeaconDeployed`
  events (the history rebuild runs once more after updating so it can find the older ones).
- **Trade: lifetime totals.** The Session page now ends with the game's own career totals for the commander (trading, mining, exobiology
  and, with a fleet carrier, the carrier), from the `Statistics` event the game writes at login. They are labelled with that login's
  date and kept apart from the session.
- **Trade: count fines and bounties paid as a running cost (optional).** A new Trade setting, off by default, adds a **Fines and
  bounties paid** line to the running costs for payments made after you turn it on.
- **Missions: Community Goal payouts.** The Community Goals page now lists the latest three payouts under **Paid out** (the goal, the
  credits and the day), read from the game's `CommunityGoalReward` event, including ones from the last two weeks of journals.
- **Exploration, Waypoint Route: From plotted route.** A new button adds the systems of the route you have plotted in the game
  (read from the game's `NavRoute.json`), with their coordinates, so the nearest-neighbor reorder needs no EDSM lookup for them.
- **Colonization History: a 14-day chart and your busiest site.** Two new lines on the COL page: a row of blocks showing the tons you
  delivered each of the last 14 days, and the construction site you have delivered the most to.

### Changed
- **Colonization history now goes back as far as your journals do.** The first time WNTB sees a commander it rebuilds their delivery
  history once, in the background, from every journal file they have, instead of only the last 14 to 30 days. It never replaces
  larger figures (so deleted journals don't shrink it), and a delivery made while it reads is still counted once.
- **Colonization overlay card footer gives both legs for a fleet carrier owner.** It now reads `► 32,769 remaining  ► 21 to buy  ► 33 to haul`
  (the same words as the COL page and the sites window) instead of one "trips in this ship" figure that was the haul count.
  Without a carrier it reads `► 32,769 remaining  ► 33 trips to finish`.
- **Easier-to-read panels.** The Powerplay panel groups its tallies (here, this session, this cycle) with thin rules, shows
  the system and the merit totals in bold, and the CP and last-event lines in the smaller font. The other modes' status and
  secondary lines (Exploration Value's age, rarity and upload lines, Codex Completionist, Boxel Survey, Discovery Alerts,
  BGS tick status, and Inventory's last event and hint) use the smaller font too, so the headline lines stand out. Nothing
  gets wider: labels still wrap to the panel.

- **Colonization window, Where to buy: three follow-ups.**
  - **Find all** searches every commodity you still have to buy (the table as filtered, covered rows left out) and lists
    the closest 5 stations, plus 2 carriers if you ticked them, under a heading per commodity. Spansh looks up one commodity per
    request, so it sends one per commodity about half a second apart; the button turns into **Stop** while it runs and
    keeps what it found. A commodity that fails is named and the rest still show.
  - **Your search choices are remembered** (within, sort, landing pad, fleet carriers) between sessions. They are window
    preferences, shared by every commander, like the window's size.
  - **Only what [station] sells** (next to Hide rows already covered) keeps the commodities the station you are docked at
    has for sale, from the market you opened. It is greyed out until you open a commodity market and switches off when you
    leave.

### Documentation
- **What goes on the internet** now says that the Canonn Nearby POI lists are hosted on Google Sheets and Google Drive (Google sees
  those requests), that the BGS tick check is plain unencrypted HTTP because that service has no HTTPS, and that web links
  open in your browser.
- The Powerplay guide now describes the Sessions window's buttons (Refresh, Copy Progress, Reset Current System, Reset
  Session). The guides also name the Mining Book's Add hotspot, the Trade History Earlier/Later buttons, the Release notes link,
  the screenshot preview's Open Folder and the Organic Scanning switch, none of which were mentioned.

- Fixed a link in the Landing Assist guide that pointed to a private notes file, and `<placeholder>` text in the Colonization
  guide and test checklist that GitHub hid when displaying the page.

### Removed
- **Mining: importing hotspots from another plugin's file or share link.** The I/E dialogs and the Settings tab no longer
  offer **Import from Link**, and **Import** reads only files WNTB exported. Hotspots you already imported are kept.
- **The older EDMCOverlay is no longer listed as supported.** The docs and the Overlay Connection text now name only
  EDMCModernOverlay. WNTB still talks to the same local port, so an older overlay may keep working, but it is not tested.
- Documentation and comments no longer mention other tools or their authors; those credits are on the Acknowledgements page.

### Developer
- New tests for the Boxel Survey EDSM and Spansh clients (`tests/test_boxel_clients.py`).
- New tests for Powerplay's merit-to-CP conversion, session handling and "Copy Progress" line
  (`tests/test_powerplay_session.py`), and for screenshot file names, crop rectangles, conversion, thumbnail limits and the
  delayed delete (`tests/test_screenshot_files.py`).
- Files are LF on Windows and Linux: new `.editorconfig`, and `tests/test_line_endings.py` fails on any CRLF in a text file.
- A `commit-msg` hook (`.githooks/`, enabled with `git config core.hooksPath .githooks`) and `tests/test_no_ai_credit.py` keep
  assistant credit lines out of commit messages and files; acknowledgements live only on the Acknowledgements page.
- Opening a ship build's link now checks it starts with http:// or https://, even if the saved file was edited by hand.
- Removed unused imports, dead constants left over from the old x/y overlay settings and the pre-Appearance overlay sizing, a
  comment naming an npm script that does not exist, and two invalid-escape warnings in a test.

## 1.6.0 - 2026-10-11

### Changed
- **Colonization moved out of Field Ops** into its own mode (the **COL** button). The REPORT button moved with it, and the SHOW / HIDE button is now **OVERLAY** (it lights up while the card is forced on).
  The mode row is now eight buttons wide, so the WNTB panel is a little wider than before. Colonization's guide is its own page.
- **One Overlays tab in Settings.** Every overlay setting and toggle is now under **Settings -> Overlays**, with a tab for
  the shared **Overlay Connection**, one for **Overlay Placement**, and one for each feature that draws on your screen:
  Colonization, Discovery, Inventory, Interdiction Warning, Landing, Mining, Notable Bodies and Screenshots. The overlay
  parts moved out of the Colonisation, Inventory, Mining and Screenshots tabs (their other settings stay there), and the
  old **Always On** tab and the Exploration **Alerts** page are gone: Interdiction Warning, Landing, Discovery and Notable
  Bodies are now under Overlays, and **Auto-Honk** has its own Exploration tab.
- **Overlay positions are no longer raw x/y boxes.** Discovery, Notable Bodies, Colonization and Inventory lost their X/Y
  boxes (see Overlay Placement below). A position you had set by hand carries over as an **Exact position**. Landing,
  Interdiction, Mining and Screenshots, which sat in fixed places, can now be moved too, and their defaults follow your
  screen shape, so they may sit slightly differently than before.
- **Colonization Sites window: the "To Source" column is now two trip columns, Buy Trips and Haul Trips.** Building a colony
  has two legs, and the window counts them apart. **Buy Trips** is how many loads of your current ship it takes to gather
  what is still missing of a commodity (0 once your ship and your fleet carrier together have enough, so a commodity stored
  on the carrier shows 0). **Haul Trips** is how many loads it takes to carry all of that commodity's remaining tons to the
  site; it stays above 0 for stock sitting on the carrier, because it still has to be moved. Both use at most two decimals
  such as `1.5` or `1.25`. The old column was Remaining less what your ship carried, so with the cargo stored on a fleet
  carrier it just repeated Remaining. The tons figure lives on as the **t still to get** total and in the copied shopping
  list, and both now take your carrier's cargo off as well. The window and its status line say "ship" instead of "hold".
- **Colonization overlay card follows the window's coverage rule.** The green text and the ✓ now mean your ship plus
  what you moved onto your fleet carrier cover the need, and amber means together they are more than needed (before, only
  the ship counted).

### Added
- **Colonization page: the Covered line now says how many commodities are fully covered, partly covered and not yet covered**, and
  the fleet carrier's cargo comes from Frontier's own carrier data when EDMC is signed in (fetched when you open Carrier
  Management or at most every 15 minutes), so stock that reached the carrier by buying or a trade order counts too. Before it
  counted only cargo you transferred, so some of what was really on the carrier showed as missing.
- **Colonization has its own mode, with a COL button.** The page shows the project you are building now (name and system, a
  progress bar, what is delivered and still needed, how many commodities your ship and carrier cover, what is still to get,
  the trips left, the biggest gaps and a one-line next step) and your colonization history (sites done, in progress and
  failed; tonnes and deliveries; the last 7 and 30 days; your best day; your top commodities; the average build time).
  The history is kept per commander in a new file, `colonisation_history.json`, counted from the journals as you deliver
  and caught up at start-up (14 to 30 days back; the page says which date it counts since). Sites now remember when they
  were first seen and when they completed. **The wording follows your ship:** without a fleet carrier there is no carrier
  line and trips are simply loads of your ship to finish; with one you get trips to buy and trips to haul. The
  Colonization Sites window does the same (one Trips column and no carrier figure without a carrier).
- **Overlay Appearance: text size, padding, line spacing and color schemes for every overlay.** A new **Settings -> Overlays
  -> Appearance** tab picks a color scheme (Elite orange, Ice blue, Phosphor green, Amber mono, High contrast, Color-blind
  safe), a text size (Smaller to Largest), padding and line spacing, with a sample and **Reset to defaults**. All eight
  displays adopt it: Colonization, Discovery, Notable Bodies, Interdiction (which keeps its red alert colors), Landing,
  Inventory, Mining and Screenshots. Cards are sized from their text at the chosen size, so larger text does not wrap or spill
  past the border, and placement uses the new size. The default look is a little roomier than before (more space between
  border and text, and between lines).
- **Overlay Placement: one place to say where every on-screen display goes, correct on any monitor.** Overlay programs
  place things on a fixed 1280 x 960 canvas, and EDMCModernOverlay treats positions and sizes differently: a position is a
  fraction of the screen, but a size is in screen pixels (after Windows' display scaling), so a raw x/y number means a
  different place on every monitor and a "right edge" depends on how big the display is. Each display is now placed by one
  of nine spots (top left, top center, ... bottom right) plus offsets in screen pixels. WNTB reads
  the real window size, mode and display scaling from EDMCModernOverlay's own log (falling back to Elite's
  `DisplaySettings.xml` and Windows' scaling); the scaling and mode can be overridden. **Show placement preview** draws a
  labeled box for every display, at its real size, on your screen so you can judge a position; **Reset all to defaults**
  and **Detect screen again** are there too. Applies to the Colonization card, Discovery alerts, Notable Bodies card,
  Interdiction warning, Landing assist, Inventory pickups and bars, the two Mining displays and the Screenshot message.
  Displays on the right-hand side are carried past EDMCModernOverlay's right-edge limit (it squashes a shape pushed past
  `1280 - its width`) by an offset set on the display's overlay group through the overlay's own plugin API, so they can sit
  against the right edge (a switch on the Overlay Placement tab turns this off). Without EDMCModernOverlay they stop where the
  limit allows.
- **Where to buy: a Planetary column.** Each result says Yes or No for whether you have to land on a planet's
  surface to reach it. The window's minimum width grew a little to fit it.
- **Colonization Sites window: your ship's capacity, what is on your carrier, and the trips to buy and to haul.** The totals
  row gains **t ship capacity** (your current ship's cargo capacity, kept up to date when you swap ships), **t on your
  carrier**, **trips to buy** (loads to gather what is still missing) and **trips to haul** (loads to carry everything the
  site still needs to the site).
- **Colonization Sites window: row colors by coverage.** A commodity row now turns green when your ship plus the tons
  you moved onto your fleet carrier cover what the site still needs, and orange when together they are more than it
  needs; while you are still short it keeps the normal look. The whole row is tinted, not just the text. **Hide rows
  already covered** follows the same rule.
- **Colonization: where to buy.** The Colonisation Sites window gains a **Where to buy** panel: pick a commodity row
  and press **Find nearest** to list the closest stations with it in stock, from Spansh. Choose the system to measure
  from (the site's, or **Here**), how far to look, closest or cheapest first, and the **landing pad** size: **Any
  size** by default (so you can swap to a smaller cargo ship when a commodity isn't sold at a large-pad station),
  **Medium or larger**, or **Large only**. **Include fleet carriers** is a switch, off by default, and carriers are
  listed under their own heading. **Copy System** copies a result's system name. Nothing is fetched until you press the
  button. The shared Spansh price search gained a distance sort and a pad-size filter for this.
- **Colonization Sites window: sites on the left, the shopping list on the right.** Click a site to see its progress bar, six
  totals (tons still to get, on your carrier, in your ship, your ship's capacity, trips to buy and trips to haul), a filter box,
  a "Hide rows already covered" switch and a commodity table you can sort by any column. A row turns green when your ship plus
  your fleet carrier cover what the site still needs and orange when together they are more. The buttons now act on the picked
  site, so you no longer have to select a commodity row first. The window is larger by default (1300 x 780).
- **Colonization: FC column.** The Colonization Sites window gains an **FC** column for a commander with a fleet
  carrier: the tons of each commodity transferred to it (net of any taken back), from the journal's `CargoTransfer`
  events made at the carrier. It is per commander, caught up from the journals at start-up without counting a transfer
  twice, and uses Trade's knowledge of whether you have a fleet carrier (including your Trade carrier setting). It is
  what WNTB saw you transfer, not the carrier's real hold.
- **Colonization: shopping list on the overlay.** Optional, off by default: a table of
  **Commodity, Need, FC and Ship** for your most recently updated active site, a tick where your hold covers a
  commodity, and a footer with the tons remaining and trips in your current ship. It shows in a commodity market, at
  your own carrier's services screens, with the right-hand cockpit panel open when docked at your carrier (the cargo
  transfer), in Carrier Management, and when docked at a construction site; optionally whenever the right-hand panel is
  open anywhere. A **SHOW / HIDE** button in the Field Ops panel forces it on or off. Settings: position, and how many
  rows (default all). The EDMC debug log records why it showed or hid.
- **Start-up commander.** If EDMC starts before the game, WNTB reads the last commander from the newest journal a few
  seconds later and every feature loads their data, so nothing waits for a login. The colonization panel also knows
  the commander straight away.

### Fixed
- **Colonization window: Find nearest did nothing after a single click.** The site list and the commodity rows only
  reacted to a double-click, so picking a commodity with one click left Find nearest saying to pick one. A single click
  now picks a site or a commodity.
- The open Colonization Sites window now follows the active commander instead of staying on the previous one's sites.

## 1.5.2 - 2026-10-10

### Added
- **Catching up after an EDMC restart, more widely.** Features that only saw live events now read the recent journals
  when EDMC starts, each with a rule that never counts anything twice (see Getting started, "If EDMC wasn't
  running"): **Colonisation** deliveries and depot visits (14 to 30 days), **Codex Completionist** finds (everything
  since the last one counted; press BKF once after updating for older history), **Boxel Survey** visited systems (14
  days), and the **Inventory** now syncs from EDMC's rebuilt state at start-up instead of waiting for the next login.
  A shared `journal_files.py` does the file finding and reading.
- **Exploration Value: system progress and real sale totals.** "System bodies: 6 scanned of 14 — all found" (from the
  honk and your scans) and "Last data sale: exploration 1,234,567 cr, organic 350,000 cr" (what the game actually paid),
  both rebuilt from the current journal file if EDMC started mid-session.
- **Trade: mission and stolen cargo in Hold space**, for example "312 t cargo (40 t mission, 12 t stolen)", from the
  game's cargo list.
- **Missions: cargo mission progress.** Collect and delivery missions show how much is collected and delivered (from the
  game's `CargoDepot` events, also read from the last two weeks of journals at start-up), and the "commodities needed"
  total no longer counts what you have already collected.
- **Trade: running the carrier.** Under the carrier's cargo lines the Session page now shows its tritium, where it is,
  a planned jump (destination and departure time), its balance and the trade orders you have set (what it is selling
  or buying, tonnes and price). They come from journal events WNTB did not read before (`CarrierDepositFuel`,
  `CarrierLocation`, `CarrierJumpRequest`/`CarrierJumpCancelled`, `CarrierTradeOrder`, `CarrierFinance` and more of
  `CarrierStats`). The game records an order when it is placed or cancelled, not as it fills, so the cargo figure
  still needs Carrier Management for an exact value.

### Changed
- **Documentation pass.** Stale statements corrected against the code: the README's broken "Installing" link, the
  Troubleshooting claim that features only know what happened since EDMC started, the Powerplay and Missions specs
  (deliveries, active set, combat bonds, cargo progress, test coverage), the Boxel Survey spec (visited-systems
  catch-up, Region Sweep's FSS check, test counts), the Trade spec (hold split, carrier operations, route start in the
  scan, tests), TECHNICAL.md (catch-up rules, known gaps, "adding a feature" steps) and the module index. The Linux
  checklist has a new section for the catch-up features, which have only been tried on Windows.

### Fixed
- **GEC Nearby POI always gave the same answer.** edastro's own "nearest" lookup does not use the position (a live check
  returned "The Solar System" for every coordinate and name tried; it had only ever been checked at Sol itself). FIND now downloads edastro's full list once
  (about 2 MB, kept for six hours) and works out the nearest point of interest itself. The result also names the system
  to look for in the galaxy map and copies it to the clipboard, and the position is read from the current journal if EDMC
  started after you were already in the game.
- **Nothing is shared between commanders any more.** An audit found four things that were one pile for everyone:
  **Mining hotspots and the Rhino's driven ground**, the **Boxel Survey finds**, the **Codex tally**, and the
  **Powerplay History** tab (which listed every commander's sessions and added their merits into one total; the
  200-session limit was also shared). Each is now per commander. After updating, hotspots, driven ground and survey
  finds go to the **first commander who logs in** (it can't tell whose they were); the Codex tally mixed everyone's finds,
  so each commander's is rebuilt from their own journals once, and the old tally is removed after 60 days. Powerplay
  sessions already named their commander, so nothing moves. Trade History now opens on the active commander. Switching
  commander also clears the previous commander's ship, hold, route results and last data sales from the screen, and
  cancels a search still running for them. New `commander_data.py` helper, and tests that fail for any new data file
  that isn't classified as per commander.
- **Missions: combat-bond kills count toward massacre missions.** Combat-zone kills are written as
  `FactionKillBond`, not `Bounty`, and were ignored. In a check against real journals, some massacre missions reached
  their kill count only with the bonds included.
- **Region Sweep: "Require a full FSS scan" uses your journal.** It now waits for the game's `FSSAllBodiesFound`
  event instead of asking EDSM after every scan, so it needs no internet and no longer makes a request per scan.
- **Powerplay: commodity and data hand-ins are now recognised as deliveries.** Current journals write
  `PowerplayDeliver` before the merits a hand-in earns, and WNTB ignored it, so those merits were guessed from the
  system you were in (and given Control Points). The merit events that follow a `PowerplayDeliver` are now labelled
  Delivery (merits only, no CP estimate). Merits already recorded keep the label they were given; only new ones (and
  journals read for the first time) use the fix.
- **Missions: your active missions show after restarting EDMC, without logging in again.** The game lists active
  missions only in its login event, so after an EDMC restart mid-game the panel waited for the next login. WNTB now
  also works the active set out from the last two weeks of journals (the newest login list, plus every mission
  accepted, completed, abandoned or failed since) and the next real login list replaces it. A mission that expired
  without a journal entry can show until then.

## 1.5.1 - 2026-10-10

### Fixed
- **Trade: the route start is remembered per commander.** Switching commander could start a route from the previous
  commander's last station. Each commander now has their own, saved in `trade_route_start.json`, so it also survives
  restarting EDMC. The journal scan feeds it too, so docks made with EDMC closed
  (or on another computer) count; an older journal never overwrites a newer dock. A commander who has never docked
  has none until they do.

## 1.5.0 - 2026-10-10

### Added
- **Trade: where your space goes.** The Session page shows **Hold space** under the landing pad (cargo, limpets and
  free tonnes), and, under **Carrier cargo free**, **Carrier crew services** and **Carrier ship / module packs**.
  A carrier last read by an older version shows one combined "crew and packs" line until its next space report.

### Changed
- **Trade: the Session page's journal line** shows when the journals were last reviewed (in your local time) and
  whether that review found new journals.
- **Guides: full disclosure of the game's data gaps.** Every mode guide (Trade, Powerplay, Exploration, Mining,
  Missions, Field Ops, BGS, Landing and Interdiction) now ends with "What the game does and doesn't tell us, and how
  to work around it": what the journal never records or records late, how it shows on screen and what to do. The
  README, guide index, Getting started and Troubleshooting point to it.

### Fixed
- **Trade: the journal scan's "new or grown" count** now counts only files that were actually applied, not ones that
  failed and will be retried.
- **Codex Completionist: BKF (backfill) no longer double-counts.** Backfill read every `CodexEntry` in your journals
  and added each one to "Times found", including ones already counted while you played, so pressing it again doubled
  the counts. It now compares the journals' count for each entry with the tally's and keeps the larger, so it can be
  pressed any number of times. Counts already inflated by earlier backfills are not corrected automatically.

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
  white pages; they now take the page color.

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
  temperature match a confirmed green one; the journal never records color, so it is a lead to check in the
  system map), colliding binary, and eight more that start off (large landable, landable ringed, close orbit,
  close binary, high eccentricity, fast orbit, fast rotation, wide ring). Off by default; only the seven rare
  rules start ticked. Settings only, under **Exploration → Alerts**, so the main panel stays the same size.
  A moon scanned before its parent is judged when the parent arrives, a body alerts once per rule, and
  several matches in a row take turns. The thresholds are fixed defaults.
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
  handed in at. Each influence entry's `SystemAddress` is resolved to a system; if it is
  unknown, the issuing faction's influence goes to the system the mission was accepted in, and only as a last
  resort to the hand-in system. See `docs/BGS_TECH_SPEC.md` section 4.2.

## 1.1.4 - 2026-10-03

### Added
- **"You are in [mode] mode."** (Open, Solo or Private Group, with the group's name) and **Credits this
  session** now sit directly under the mode buttons, visible in every mode, in one section with a separator
  before the page content. Each is its own module (`game_mode.py`, `session_credits.py`) and neither depends on
  Powerplay any more: they track the game mode and the balance themselves, from the journal, and keep their own
  saved record (`session_credits.json`). The credits line reads "+N cr earned" or "-N cr lost", with an hourly
  rate once the session is a few minutes old.
- Settings now state which systems each OS-dependent feature works on, and whether it can work on your
  machine right now (a **Works on:** line, green or orange): Auto-Honk, the Screenshots auto-timer and Thargoid
  capture, the Inventory pickup sound, and the Overlay Connection tab. The BGS tab shows the Linux journal-folder hint.
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
  color names, which made the whole tab fail to build on other systems.

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
  near-full and full color cues as the other tabs, and the commodities aboard (Filter box applies).
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
- Behavior and wording in those windows are unchanged. Window sizes scale with display scaling, and
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
- The coverage minimap uses color-blind-safe markers (shape carries "depleted") and, in the ship,
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
