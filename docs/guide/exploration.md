# Exploration

Exploration mode is one scrolling panel with several sections stacked top to bottom. Some sections start folded:
click a section's title (▸ / ▾) to open it. They fold again each time EDMC starts.

> **Where this comes from:** your scans, jumps, honks and Codex finds come from the journal, so everything about *your* exploring is exact. What the journal can't say (which systems exist or are unvisited, a gas giant's color, which species a planet hosts before you sample it) is filled from what EDSM, Spansh, Canonn and edastro report, or worked out and labeled as a lead to check. See [How WNTB knows what it knows](README.md#how-wntb-knows-what-it-knows).

**On this page:** [Auto-Honk](#auto-honk) · [Discovery Alerts](#discovery-alerts) ·
[Notable Bodies](#notable-bodies) · [Boxel Survey](#boxel-survey) · [Exploration Value](#exploration-value) ·
[Organic Scanning](#organic-scanning) ([Exobiology guide](exobiology.md)) · [Codex Completionist](#codex-completionist) ·
[GEC Nearby POI](#gec-nearby-poi) · [Canonn Nearby POI](#canonn-nearby-poi) · [Notes](#notes) · [Expedition](#expedition) · [Expedition Log](#expedition-log) · [System targets and Body info](#system-targets-and-body-info) · [Compass](#compass) ·
[What the game does and doesn't tell us](#what-the-game-does-and-doesnt-tell-us-and-how-to-work-around-it)

Anything that draws on your game screen needs an overlay. See [Getting started](getting-started.md#what-you-need)
and [Setting up the overlay](../OVERLAY_SETUP.md).

## Auto-Honk

Fires your Discovery Scanner automatically every time you jump into a system, so you never forget to honk.

**How to use it:**

1. Turn it on with its toggle button (**A.H.**) or the **Enable Auto-Honk** box in Settings. It is **off by default**.
2. Open **Settings → Exploration → Auto-Honk** to choose which fire button it uses (**Primary** or **Secondary**; the
   default is Secondary) and how many seconds it holds it (**Hold**, default 10).
3. Two other options there: *Focus game window first* and *Skip systems already visited* (both on by default).
4. Press **Test Honk Now** to check it works without waiting for a real jump. **Rescan** re-reads your key
   bindings.

If another program also fires your Discovery Scanner for you (some co-pilot apps do), turn one of the two off, or they'll fight each other.

*On Linux this needs `xdotool` and a keyboard key bound to your fire button. See [WNTB on Linux](linux.md).*

## Discovery Alerts

Puts a banner on your in-game screen the moment you jump into a system nobody has scanned, or the moment you're the
first to scan or map a body.

**How to use it:**

1. Click its toggle button (**D.A.**) or tick **Enable Discovery Alerts** in Settings. It is **off by default**.
2. Make sure an overlay is running. The connection details are on the **Overlay Connection** tab under Settings → Overlays.
3. Use **Settings → Overlays → Discovery** to send a test one, and **Settings → Overlays → Overlay Placement** to move the banner.

### N.S. and W.D. buttons

Next to the toggle, these find the nearest system whose *primary* star is a **neutron star (N.S.)** or a **white
dwarf (W.D.)**, measured from where you are now. They show the system name and distance, and copy the name to your
clipboard so you can paste it into the galaxy map.

They are manual only: they contact Spansh when you click and never on their own. Jump or reload first so WNTB knows
your position.

## Notable Bodies

Puts a violet banner on your in-game screen when a body you scan is worth a second look. A match comes from the scan
data, so check the body in the system map before you plan around it. It needs the same overlay as Discovery Alerts.

**How to use it:**

1. Open **Settings → Overlays → Notable Bodies**.
2. Tick **Enable**. It is off until you do.
3. Choose which rules you want.
4. Press **Test Notable** to see a sample banner. Move it under **Settings → Overlays → Overlay Placement**.

It has no button on the main panel.

### What it looks for

**On to start with** (the rarer finds):

- **High-value body**: any terraformable world, and every Earth-like, water and ammonia world, whether or not you
  can land on it. The log line says if it is undiscovered or unmapped.
- **Terraformable landable**
- **High-g landable** (about 3 g or more)
- **Shepherd moon**
- **Good FSD injection** (5 or 6 of the premium boost materials on a landable)
- **Colliding binary**
- **Green gas giant**: from the Codex, or a gas giant whose surface temperature matches a confirmed green one. The
  game never records a planet's color, so treat this as a lead, not a fact.

**Off to start with** (because they're common): large landable, landable with rings, close orbit, close binary, high
eccentricity, fast orbit, fast rotation and wide ring.

### How alerts behave

- If a body matches several rules you get **one banner**, for example "High-value body +2".
- A body only alerts **once per rule**.
- Banners take turns if several come at once.
- The banner widens to fit the body's name and the rule's title, so a long catalog name shows in full (only text past about 56 characters is cut with "…").
- The limits are fixed defaults.
- If the banner lands on top of other overlay text, move it under **Settings → Overlays → Overlay Placement**.

## Boxel Survey

> **Work in progress.** Boxel Survey is still being built, and I'd really appreciate your feedback. Please
> [open an issue](https://github.com/rwharpernc/wayward-nomads-toolbox/issues) or find me in the squadron.

A helper for exploring the galaxy system by system, using Elite's procedurally generated system names. A name like
`Outotz LS-K d8-0` has four parts: a sector name (`Outotz`), a three-character cube ID (`LS-K`), a mass-code letter
a to h (`d`), and a number or number pair at the end (`8-0`). The "boxel" is the cube of space that shares the
first three parts; the trailing number picks one system inside it.

The section is **folded by default**: click `▸ Boxel Survey` to open it. Inside, three buttons choose a sub-mode:
**Sequence**, **Region Sweep** and **Waypoints**. WNTB remembers which one you used last.

**What WNTB does and doesn't know.** It works with *names*, not coordinates. It counts through the trailing number
to make the next candidate name, and it does not know whether a candidate actually exists. The in-game galaxy map
is what tells you. Real positions only come from EDSM or Spansh lookups.

### Which sub-mode should I use?

| If you want to... | Use |
|---|---|
| Work through one boxel from start to finish, in order | **Sequence** |
| Clear a whole region (several boxels), tracking what's left across all of them | **Region Sweep** |
| Visit a fixed list of specific systems in a sensible order (a rendezvous, a squadron staging route) | **Waypoints** |

If you're not sure, start with **Sequence**. Waypoints is the odd one out: it accepts any system name, not just
procedurally named ones.

All three are remembered **per commander**.

### Sequence

The panel shows a **Target**, **< Prev**, **Next >** and **Copy** buttons, a **Seed system** box with **Use
Current** and **Set**, a **Find Nearby (EDSM)** button, a line of survey counts and a status line.

**To start a survey:**

1. Type a procedural system name into **Seed system** (or press **Use Current** to fill in the system you are in).
   A gray hint under it says whether the name looks like a boxel name.
2. Press **Set**. The seed becomes the first target.
3. Paste the target into the galaxy map (**Copy** puts it on your clipboard) and jump.
4. When you arrive at the target, WNTB marks it visited and moves to the next candidate. With *Auto-copy next
   target to clipboard on jump* on (the default), it also copies that next name for you.

**If a candidate doesn't exist:** the galaxy map won't find it. Press **Next >** to skip it. (**< Prev** steps
back; at the very start it says "Already at the start of the sequence".) After **3** manual **Next >** presses in a
row without a confirmed jump, WNTB asks EDSM for the nearest real procedurally named system outside the current
cube, and fills the Seed box with it. It does not switch automatically: press **Set** to move the survey there.

**Find Nearby (EDSM)** does the same lookup on demand. It needs to know your position, so jump or reload first.

**What it keeps.** The line under the buttons counts what you've found in surveyed systems:
`Surveyed: N systems | ELW | WW | AW | terraformable | bio`. These come from your scans: Earth-like, water and
ammonia worlds, terraformable planets, and bodies with biological signals. Open **Settings → Exploration → Boxel
Survey** and press **Export Survey Log** to write them to a CSV file. The file is always called
`boxel_survey_export.csv` and is saved **in the WNTB plugin folder**; you do not choose where. The survey log is kept
**per commander** and the export holds the active commander's finds, so exporting as another commander replaces the file.

**Scans made while EDMC was closed.** At start-up WNTB reads the last 14 days of your journals and adds the notable bodies and biological
signals it finds there to the survey log, and the systems that were missing from it. It is careful not to count anything twice: a system
the log already had keeps its "bodies scanned" number (only its missing finds are added), a system new to the log gets one count per
body, and running it again changes nothing. Scans older than 14 days, made with EDMC closed, are not found. The game's journals are
only read, never changed.

**Settings → Exploration → Boxel Survey:**

| Setting | Default |
|---|---|
| Auto-copy next target to clipboard on jump | On |
| Skip systems already visited this session | On |
| Skip systems already visited by anyone (EDSM) | Off (adds a network call per advance) |
| Skip systems already fully scanned in EDSM | Off (another network call per candidate) |
| Confirm off-sequence arrivals against EDSM (catches a target that resolved under a different display name) | Off |

### Region Sweep

For clearing several cubes and seeing what's left. It keeps a **queue of cubes**. Each entry in the list looks
like `> Outotz LS-K d [3/12]`: the `>` marks the current cube and `[3/12]` is systems done out of systems known.

**Setting up the queue:**

1. Type a seed system under *Add cube — seed system* and press **Add** (or **Use Current**, then **Add**).
2. Press **Discover Nearby Cubes (EDSM)** to add cubes near your current position, and fill in the systems EDSM
   knows. It needs your position.
3. Select a cube and press **Discover Known Systems (Spansh)** to fill in the systems Spansh knows for that cube.

**Working through it:** the **Target**, **< Prev**, **Next >** and **Copy** buttons work as in Sequence, on the
current cube. **Set Current** makes the selected cube the current one, and **Remove** deletes it from the queue.

**What "complete" means.** A cube is complete once *every system WNTB knows about in it* is done, or once you mark
it **Empty**. WNTB can't know a cube's true total, only what EDSM, Spansh and your own visits have revealed. A
system counts as done when you arrive there, or, if you turn on *Require a full FSS scan*, when the game reports that your FSS has found every body in it (the `FSSAllBodiesFound` journal event). That check uses only your journal, with no internet lookup.

**Mark Empty / Unmark Empty** flags the selected cube as having nothing worth surveying (the list shows `[empty]`).
Empty cubes count as complete and are skipped. When you arrive at a cube's target and that cube is complete, the
sweep moves on to the next unfinished cube in the queue (wrapping round to the start).

**Settings → Exploration → Region Sweep:**

| Setting | Default |
|---|---|
| Auto-copy next target to clipboard on jump | On |
| Skip systems already visited this session | On |
| Skip systems already visited by anyone (EDSM) | Off |
| Require a full FSS scan (not just arrival) to mark a system complete | Off |
| Auto-discover more nearby cubes (EDSM) when the queue is running low | Off. When on, runs the Discover Nearby lookup after a jump once one or fewer cubes still have work left |

### Waypoints

A plain route tool. It takes any system names, not only procedural ones: a rendezvous, a point of interest, a
squadron staging system.

1. Type a name under *Add waypoint* and press **Add**, or press **Use Current**, or load a list with **Import
   CSV…**. The CSV import reads **one system name per row, from the first column**. Blank rows and a header row
   (a first cell like `system`, `name` or `waypoint`) are skipped, and names already in the list aren't added twice.
   Or press **From plotted route** to add the systems of the route you have plotted on the galaxy map in the game (the system you
   are in is left out). They come with their coordinates, so the reorder below needs no lookup for them.
2. **Move Up** and **Move Down** change the order by hand. **Remove** deletes the selected waypoint.
3. **Reorder (Nearest-Neighbor, EDSM)** asks EDSM for each system's coordinates, then builds a route that starts at
   your current position and always goes to the nearest unvisited waypoint next. Waypoints you've already visited
   keep their place at the front, and ones EDSM can't locate keep their order at the end. It needs your position.
4. **Copy** copies the current target. With *Auto-copy next waypoint to clipboard on jump* on, WNTB copies the next
   one when you arrive.

### RND: find something nobody has discovered

**RND** sits on the Exploration button row, next to A.H., D.A., N.S. and W.D., so it is visible even while the
Boxel Survey section is folded, and works whichever sub-mode is selected. It does not touch your Sequence target.

When you press it, WNTB:

1. asks EDSM for known systems near your position, and takes the nearest procedurally named ones as starting
   points;
2. makes random candidate names in the same boxel (the trailing number nudged by up to 500 either way);
3. discards any name in your own visited-systems log, and checks the others against EDSM, up to **20 attempts**;
4. copies the first name EDSM has **no record of** to your clipboard.

Paste it into the galaxy map. A status line says what happened, for example `Copied: <name> (not listed in EDSM)`
or `No undiscovered candidate found after 20 tries - try again`. "Not in EDSM" means nobody has uploaded it, not
that it is guaranteed to exist.

The visited-systems log records every system you arrive at, whichever sub-mode is selected. Clear it under
**Settings → Exploration → Boxel Survey → Clear Visited Systems Log**.

More detail: [Boxel Survey specification](../BOXEL_SURVEY_TECH_SPEC.md).

## Exploration Value

A quiet readout of what you're finding. Nothing to turn on. It shows:

- the estimated payout for your last scan,
- the age of the current system,
- which of the galaxy's 42 named regions you're in (for example "Inner Orion Spur"),
- how many of the system's bodies you have scanned out of the number the honk found (for example "System bodies: 6
  scanned of 14 — all found"),
- what your last data sales actually paid, to set against the estimate ("Last data sale: exploration 1,234,567 cr,
  organic 350,000 cr").

All of that is worked out on your computer. The estimate is the value of scanning the body (with the first-discovery multiplier when nobody had found it); the value of
mapping it as well is on the [Body info](#system-targets-and-body-info) card (**Mapped value**) and counted in the [Expedition Log](#expedition-log).

The readout itself is on by default (*Show estimated scan value, system age, and current region*). Two extras are
optional in **Settings → Exploration → Exploration Value**, and both are off until you tick them because they
contact the internet:

- *Show ELW rarity comparison when you scan an Earthlike World* (Spansh)
- *Show EDSM upload status when you select a system on the galaxy map* (EDSM)

## Organic Scanning

Helps you find and identify exobiology life on a planet's surface: which species each signal is likely to be, with an estimated credit value, your Log,
Sample and Analyse progress, and when you have walked far enough for the next sample. It also has four overlay cards for the body you are on (bio status,
predicted species, a sample radar and a popup after each sample), leads you back to plants you identified, and shows the first footfall bonus.

All of it is in its own guide: **[Exobiology](exobiology.md)**. You can switch the panel's section off under **Settings → Exploration → Organic Scanning**
(**Show predicted species and scan progress**); it uses only your own journal and makes no internet connection.

## Codex Completionist

*(Starts folded: click the title to open it.)*

A running tally of the Codex entries your game has reported, such as biological, geological, Guardian, human and
Thargoid finds. It is built from the `CodexEntry` events in your journal. The panel shows one summary line, for
example `120 distinct entries, 340 total finds` followed by your three biggest categories, and two buttons:
**DET** and **BKF**. It is on by default; switch it off with *Track codex entries* in **Settings → Exploration →
Points of Interest**, where there is also a *View Canonn Codex* link.

**Each commander has their own tally.** Switching commander switches the tally (the window's subtitle names whose it is),
and one commander's finds never appear in another's. **After updating from a version before this**, the old tally mixed
every commander's finds and can't be split, so each commander's is rebuilt automatically from their own journals the
first time they log in (one time). Years of journals can take a minute. While it reads, the Codex Completionist title
reads **"- rebuilding..."** (even when the section is folded) and the summary line says it is rebuilding that
commander's tally; the summary fills in when it finishes. The old tally is kept unused for 60 days and then removed.

**Finds made while EDMC was closed** are counted automatically: each time EDMC starts, WNTB reads only the journal files
written since the last find it counted and adds the newer ones, once each. The first start after updating only sets
that starting point for a brand-new install, so press **BKF** once to bring in older history. (The rebuild after updating
does this for you.)

**BKF** (backfill from journal history) is a button you press yourself, because reading years of journals takes a
while. It reads **all** the journal files in EDMC's journal folder, with no date limit, and counts only the
**current commander's** entries (a journal file says whose events follow, and one file can hold several commanders).

BKF is safe to press more than once. For each entry it compares how many times your journals record it with the
count already in the tally and keeps the larger, so nothing is counted twice, and finds from journals you've since
deleted are kept. It can also fill in an earlier first sighting and a first-discovery star. If your counts were
inflated by pressing BKF in an earlier version, they are not corrected automatically.

### The details window (DET)

It has a subtitle such as `120 distinct entries — 340 total finds — 95 of 1,070 catalogued entries found (9%)`
and two tabs:

- **Found**: your entries grouped by category, with the columns **Entry**, **Times found** and **First found in**.
  A ⭐ means that at least one of your sightings was reported by the game as a new entry (a first discovery). Click
  a column heading to sort; click again to reverse. (**Times found** sorts highest first on the first click.)
- **Not found**: Canonn's catalog of **biological, civilisation and stellar-body** entries, minus the ones you
  have found. Columns: **Entry**, **Type**, **Platform** (Odyssey or Legacy). It sorts the same way. Canonn's
  catalog has no geological or anomaly entries, so those never appear here.

**Buttons:** **Open Reference** and **Refresh Catalog**. Double-click a row, or select it and press **Open
Reference**. This opens a **search** on canonn.science for that entry's name in your browser, not a fixed page for
the entry.

**The catalog** is downloaded from Canonn the first time you open the window and whenever the saved copy is
more than 14 days old, and **Refresh Catalog** fetches it again on demand. It is saved in the plugin folder, so
after the first download it opens instantly and works offline. If the download fails, the tab says so, and shows
the saved copy if there is one.

Codex Completionist has no specification page of its own. The code is `codex_completionist.py`,
`codex_completionist_window.py`, `codex_catalog.py` and `codex_backfill.py` in the plugin folder.

## GEC Nearby POI

*(Starts minimized.)*

Finds the nearest point of interest from edastro.com's exploration catalog (the GEC). Click **FIND**. It only looks
something up when you ask, and it shows the point of interest, its category, **the system to look for in the galaxy
map**, how far away it is, its region and rating, with a link to its page. The system name is also copied to your
clipboard so you can paste it into the galaxy map.

It needs to know where you are, so jump (or log in) first. If EDMC started after you were already in the game, it reads
your position from the current journal. **The first FIND of a session downloads edastro's whole list** (about 2 MB, 650
points of interest) and works out the nearest one itself; later presses use that list for six hours without another
download.

## Canonn Nearby POI

*(Starts minimized.)*

The same idea, using Canonn's lists of Thargoid and Guardian sites. Click **FIND**.

- The first click downloads the lists, which are then kept for the rest of your session.
- **REF** fetches fresh copies.
- A **View site details** link under the result opens that site's page in your browser.
- Choose which kinds of site to include in **Settings → Exploration → Points of Interest**.
- By default it skips sites you've already logged in Codex Completionist, so it points you somewhere new. You can
  turn that off in the same place.

## Notes

*(Starts minimized.)*

Your own notes on a system or a body: "come back for the rings", "ELW with a moon, scan the other side". The journal has no place
for a commander's own words, so these are kept by WNTB, on your computer, **for the commander who wrote them** (another commander on
the same install does not see them). Nothing is sent anywhere.

The section says how many notes the system you are in has, and shows the newest, so a note you wrote on an earlier visit is in front of
you when you arrive. With the section folded, the title says `- 2 here`.

- **Quick note:** type a line in the box and press **ADD** (or Enter). It is saved against the system you are in, and the body too
  when you are near one (the game's `Status.json` names it).
- **NOTES** opens the Notes window: a **Search** box (every word you type must appear in the system, body or note), a list of every
  note, newest change first, and an editor underneath. Select a note to change it, press **New note** to write another. **Here**
  beside the System and Body boxes fills in where you are now. Tick **Only the system I am in** to see just this system's notes.
- **Delete** asks you to press it a second time, because a note cannot be got back.
- A note can be up to 2,000 characters, a system or body name up to 100, and you can keep 2,000 notes. Past a limit WNTB tells you
  rather than cutting the note short.

Notes are matched to a system by its name (ignoring capitals and spaces at the ends), so a note about `Sol` shows when you are in Sol.

## Expedition

A planner for a trip. An **expedition** is a named list of **stops** (systems, each with an optional body and note). Start it and WNTB ticks stops
off as you arrive and keeps the totals; you can keep several expeditions and run one at a time.

**The Expedition row** (a collapsible section in Exploration mode) shows the one running: its name, `7 of 20 stops`, the jumps and light-years
flown and the time since you started, the next stop with its distance (and its note), and the stop you have just reached. **COPY** puts the next
stop's system name on the clipboard to paste into the galaxy map, and **Copy on arrival** does it for you every time you arrive anywhere (off until
ticked). **EXPEDITION** opens the window.

**What you find at each stop.** While an expedition is running, WNTB counts what you do in each stop's system against that stop: the bodies you scan,
how many nobody had discovered before (the game says so in the scan), and how many you map. Once you have honked, it also knows how many bodies the system
has, so a stop reads `5 of 12 scanned · 2 first · 1 mapped`. The row shows the running totals (`Found: ...`), the window has a **Found here** column
for every stop, and the Route overlay card can show the stop you are at. A body scanned twice counts once, belt clusters are not counted, and nothing is
counted in a system that is not a stop you have reached.

**On your screen.** The Route overlay (Settings → Overlays → Route; see [Always on](always-on.md#route-overlay)) can show the running expedition on its
card: the name and `7 of 20`, what you have found at the stop you are at, the next stop with its distance, that stop's note, and the stop you have just
reached. It is on by default once the Route overlay is on, and there is a tick to turn it off.

**The window**
1. Type a name and press **New**. Pick an expedition from the list at the top; **Rename**, **Reset** and **Delete** act on it (to rename, press **Rename**: the current name appears in the Name box; change it and press **Rename** again. Reset forgets the
   progress and keeps the stops; Reset and Delete ask twice).
2. Add stops: type the system (or press **Here** for the one you are in) and press **Add stop** or Enter. Only the system is needed: the body and the note are optional. **Capitals do not matter**: type `sol` and the stop is `Sol`. WNTB uses the spelling of the system you are in or of a stop you already have, and (while *Check system names on EDSM when adding* is ticked under the editor, as it is by default) asks EDSM, which fixes the capitals of any system and fills in the stop's position. It sends only the system name. A system EDSM does not know, because nobody has charted it or because of a typo, is kept as you typed it and the status line says so. Untick the box to stay offline. If you have no expedition yet, the first stop makes one called "My expedition" (or the name you typed in the Name box), so you can start straight away. Select a stop to
   change it (**Save changes**), move it (**Up**, **Down**), tick it off yourself (**Mark visited**) or **Remove** it (asks twice).
3. Or add many at once (these also make an expedition if you have none): **From plotted route** adds the systems of the route you plotted in the game (the one you are in is left out; they come with
   their positions), and **Import CSV** reads a file with the columns system, body and note (a one-column list of systems works too).
4. **Make an expedition with Spansh.** **Road to Riches** and **Exomastery** (a row above the other tools) ask [Spansh](https://spansh.co.uk/)'s route planners for places worth visiting and turn the answer into a new expedition.
   - **Road to Riches** picks the bodies worth the most credits to scan (tick *Count what mapping pays* to include mapping), near a route, in a good order. **Exomastery** (Spansh's Expressway to Exomastery) picks planets with the most valuable biological signals.
   - A small window asks where to **start** (the system you are in is filled in), an optional place to **end**, your **jump range** (taken from your last loadout; change it), how far from the route to look, the most results (up to 100), how far from the arrival star, and the **least a body or planet is worth** (raise it for fewer, better places). **Avoid Thargoid systems** is ticked; **Come back to the start** is not.
   - Press **Plot**. Spansh can take from a few seconds to a couple of minutes; while it works, the **Plot** button reads *Plotting...*, a bar moves along the window and a timer counts what you have waited, with Spansh's own word beside it (waiting in the queue, or calculating), so you can see it has not stalled. **Cancel** stops waiting. When the answer arrives it becomes a new expedition (named, for example, *Road to Riches from Sol*) with a stop for each system: the best body, a note of what is worth scanning there and its position. Check the order, then press **Start**.
   - This is online, and only when you press **Plot**. It sends Spansh the start system, the end system if you typed one, and the numbers above, nothing else (see [what goes on the internet](internet-and-privacy.md)). If Spansh cannot find a system, it says so in the window. If nothing worth stopping for is found, no expedition is made: lower the least worth or look further from the route.
5. **Locate and reorder (EDSM)** asks EDSM for the positions of the unvisited stops that have none, then puts the unvisited stops in order,
   always going to the nearest next, starting from where you are. This is the only part of the Expedition planner that goes online, and it sends
   only system names. A stop EDSM cannot place keeps its place at the end.
6. Press **Start**. From then on, arriving in a stop's system (a jump, a carrier jump, or logging in there) ticks off the first unvisited stop of that
   name, wherever it is in the list, and each jump adds to the totals. **Pause** stops counting and keeps the progress; starting another expedition
   pauses this one. When the last stop is ticked the expedition stays running until you press **Finish**.
7. Share it: **Copy list** puts a text list on the clipboard, **Export CSV** saves the stops (it can be imported again), **Copy next** copies the
   next stop's name.

The expeditions are kept on your computer for each commander, and nothing is sent anywhere except the EDSM lookup above. It does not replace
**Waypoints** (Boxel Survey), which stays a single quick list; **From plotted route** and the CSV import work the same way in both.

## Expedition Log

An archive of your exploration expeditions, and a card that keeps the running one in view. It is separate from the [Expedition planner](#expedition) above, which plans stops to
visit; the log records what **happened** on a trip, whether or not you planned a route.

**Starting an expedition you are already on.** In the LOG window, **Start since my last sale** begins an expedition just after your last exploration or exobiology sale (the earlier of the two) and fills it in from your journals since then, so the data you are still holding is what the expedition covers; it then carries on counting live. It is how to pick up a trip that was under way before you used the log.

**The row** (Exploration panel, *Expedition Log*; it starts folded like the other sections, so click its title (▸) to open it; the title says what is running even while it is folded) shows the expedition that is running (its name, how long, systems, jumps and light-years, bodies and species, and what you have
earned), with **START**, **STOP** and **LOG**. START begins a new expedition now, from the system you are in and in the ship you are flying, and stops the one that was running.

**What it counts**, from your journal, while an expedition runs:

| | |
|---|---|
| **Exploration** | systems visited, jumps and light-years, honks, bodies scanned (each once) and first discoveries, Earth-likes, water worlds, ammonia worlds and terraformables, bodies mapped and first maps, landings, new codex entries, **the credits earned when you sell exploration data**, and an estimate of what the scans and mapping you have not yet sold are worth (with the first discovery, first map, efficiency and Odyssey bonuses) |
| **Exobiology** | samples taken, species analysed, genera, first footfalls, **the credits earned when you sell exobiology data**, and an estimate of what the species you have analysed but not yet sold are worth (five times as much on a first footfall) |
| **Ships** | each ship you flew (type, name and ident), added as you load into it |

Earned figures are what the game reports when you sell, so they count when you sell, not when you scan. The unsold figures are estimates, marked `~`; selling clears them, since the
game sells what you hold. The estimates follow the community formula (the base value of the body from its class and mass, the first-discovery multiplier, the mapping multipliers for a
first map, a first map of an already discovered body and an already mapped body, the efficiency bonus when your probe run met the target, and the Odyssey bonus); expect them to be close, not exact.

**The LOG window** is the archive. A table lists every expedition, newest first. Select one to read everything it recorded and to **edit** its name, when it started and ended (UTC;
`2026-10-16` or `2026-10-16 18:30`), where it started and ended, the ships used and your notes, then **Save changes**. The buttons: **Start** (with an optional name), **Stop**,
**Resume** (carry on counting one that was stopped), **Reset** (clear its totals and count again from now; it asks twice), **Rescan** (work its totals out again from *your* journals
between its start and its end, which fills in an expedition that missed events or one you gave an earlier start), **Delete** (asks twice), **Copy summary** and **Export CSV** (the
whole archive, for a spreadsheet).

**The overlay card** (Settings → Overlays → Expedition Log, off until ticked) shows (while no expedition is running it says so and how to start one) the running expedition's exploration and exobiology totals and what it has earned, with its name and
how long it has run in the heading and the total earned at the foot; it can keep showing the last expedition after you stop it. Place it on **Overlay Placement** ("Expedition Log").

Everything is kept for your commander only (another commander has their own archive) and never leaves your computer.

**What it cannot tell you:**

| What you might expect | What the game gives | What to do |
|---|---|---|
| Earnings the moment you scan | Credits are paid when you sell the data at a station | Sell as usual; the unsold estimate shows what is waiting |
| Counting while EDMC was closed | The journal is read live; events written while EDMC was closed are not seen | Press **Rescan** on the expedition |
| Which sale was for which expedition | The game reports a sale, not what it covered | A sale counts for the expedition running when you sell |
| The exact value of a map | The journal gives the figures the estimate uses, not the payout, which is reported when you sell | The estimate is close (OD Explorer's agreed to within 0.2% on one expedition); the sale reports the exact figure in the earned total |

## System targets and Body info

Two cards on your game screen for working a system. Both are **off by default**, have no panel button, and are set up under **Settings → Overlays**.
They need [EDMCModernOverlay](../OVERLAY_SETUP.md); nothing is sent anywhere, they read your journal.

**System targets** (Settings → Overlays → System targets) is a list of what is left to do in the system you are in:

- After you have scanned bodies, it lists the planets and moons **worth mapping that you have not mapped**: those whose estimated value is at or above a
  threshold you choose (100,000 credits to start), most valuable first. The value is what **scanning and then mapping** the body pays by default (a choice in Settings → Overlays → System targets switches it to the scan alone), so a body worth mapping is ranked by what mapping it earns. Each row has the body's short name (`A 1`), a tag for the classes that matter
  (`ELW`, `WW`, `AW`, `HMC`, `MR`, and `TF` for any other terraformable world) and the value (`1.2M`, with `first` when nobody had discovered it).
- Below that it lists the bodies **with life that you have not finished analysing**, as `1/3 life`.
- A body leaves the list when you **map it** or **analyse its last organism**. The card's heading is the system name with a progress bar for the system scan
  and a count (`4 of 8 scanned`) once you have honked, and a message says so when nothing at or above your threshold is left (`Nothing over 100k left to map or sample`;
  a long message continues on the next line). Each row shows the body, a muted tag and distance (`HMC  82k ls`) or the genera once known, and the value on the right.
- **Also look up bodies other commanders have scanned** (off until you tick it): right after you honk, WNTB asks [EDSM](https://www.edsm.net/) once for the system's planets (it sends only the system name; see [What goes on the internet](internet-and-privacy.md)) and lists the worthwhile ones with their estimated value, marked `EDSM`, before you have scanned anything. Your own scan then replaces what EDSM said, and the Body info card shows them as `From EDSM, not scanned by you`. EDSM does not say who has mapped a body, so a looked-up body stays on the list until you map it.
- Under the heading a **summary line** says how far you have got (`1 mapped · life 1 of 3 done · 4 of 9 analysed`: the bodies with life you have finished, and every biological signal in the system you have analysed), and a third section, **Done**, lists the bodies you have finished (mapped,
  and any life analysed) as `2 d  mapped · life 3/3`, so after a break you can see where you left off as well as what is left. You can switch the Done list off.
- **Coming back to a system.** WNTB keeps each system's survey for you between sessions (the 60 most recently visited, kept separately for each commander), so leaving a system,
  logging out, or visiting it again later brings the card back as you left it. For a system you were in before this was saved it rebuilds the survey from your journals
  (your own commander's, at most the newest 80 files).
- **Rows shown** (3 to 16, 6 to start) caps the list, and the rest are counted (`+ 3 more`). You can switch the life list off.

**Body info** (Settings → Overlays → Body info) describes one body: its name and class; flags (`Undiscovered`, `Terraformable`, and `Unmapped`, `Mapped before`
or `Mapped by you`); its materials, written as element symbols (`Fe 18.4% · S 18.2%`); and then the estimated scan value, temperature, gravity (in the warning color at 2.0 g and over), pressure, atmosphere and its composition (formulas such as `CO2`),
volcanism, life signals (how many, how many are done, and the genera once you have mapped it), geology signals and distance. It shows for **the body you have
targeted** in the galaxy or system map or the nav panel, and for **the body you are close to**; each can be switched off.

**What they cannot tell you:**

| What you might expect | What the game gives | What to do |
|---|---|---|
| A body to be listed as soon as you honk | The honk gives only a count. A body's class and mass come with its **scan** (the system scan, or a detailed scan), so a body appears when you have scanned it. | Scan the bodies, and they appear. Or tick **Also look up bodies other commanders have scanned** (below). |
| Bodies in a system nobody has scanned | The EDSM lookup only knows what other commanders have uploaded. A system nobody has surveyed returns nothing. | Scan the bodies. |
| Whether a body has been stood on | The scan's `WasFootfalled` says whether anyone has set foot on a landable body. WNTB flags a first footfall (Body info: `First footfall`, and the five times exobiology reward; System targets: `FF` on a life row). It reflects the scan you made; a body scanned by someone before you but not yet footfalled in the data may show as footfalled. | Treat the flag as a strong hint and check the in-game body info if it matters. |
| What mapping pays | The **Scan value** is the estimated value of scanning (the same estimate the [Exploration Value](#exploration-value) readout uses); Body info's **Mapped value** is the estimate of scanning and mapping it with an efficient probe run. The System targets list is ranked by the mapped value by default (the scan value if you choose it in Settings). | Use the threshold as a guide to which bodies are worth a probe run. |
| The kinds of life before you map | The system scan gives the **number** of biological signals; the genera are given when you map the body. | Map it to see the genera. |
| The cards to remember a system after a restart, a relog or a visit later | The survey of each system is saved for each commander and merged back when you return; for a system visited before it was saved, it is rebuilt from your journals (your commander's, the newest 80 files). | Nothing: it happens by itself. Bodies the journals never recorded (a system you never scanned) cannot be recovered. |

**When the cards show.** They follow the commander and the situation, so they are there when you are exploring and gone when you are not: they hide in hyperspace, while docked
or on a carrier, when the game is closed or at its main menu (including while another commander signs in), and a different commander loading in starts with a clean slate.
They come back when you arrive in a system. The cards are drawn by the overlay over your game window; the overlay's own settings decide whether they show when another window has focus.

Where each card sits is set on **Overlay Placement** ("System targets" and "Body info"). They start in the lower middle of the right half of the screen,
one above the other; move them to suit your HUD.

The Exobiology cards (bio status, predicted species, the sample radar and the sample popup) are described in the [Exobiology guide](exobiology.md#the-overlay-cards).

## Nearest place to land

For deep space and emergencies: the nearest station that can take your ship and has what you need, and the nearest fleet carriers that let anyone dock. **Exploration → Nearest place to land → FIND** opens the window.

- **It starts from where you are.** The position comes from the journal (`StarPos`, set by each jump), not from a system name, so it works in a system nobody has charted yet. If WNTB has not seen a jump this session it reads the newest journals; if it still has no position, jump once.
- **It knows your ship's pad.** The pad comes from your ship (`Loadout`): a Python is never sent to an outpost with only small pads. Choose a pad size yourself, or *Any size*, if you want something else.
- **Say what you need:** fuel, repairs, rearming, outfitting (fuel and repairs are ticked at first). Only stations that offer all of them are listed.
- **Stations** (starports, outposts, planetary ports and outposts, megaships and colonization sites) are listed nearest first with their pads, the distance in light years and where they are in the system.
- **Fleet carriers** are listed only when Spansh says docking is open to everyone, and only if its record is recent (7, 14, 30 or 90 days, your choice), because carriers jump and change who may dock. The age of each record is shown; check it before you rely on a carrier.
- **Double-click a row** to copy its system name, to paste into the galaxy map.
- **It is online, and only when you press Find**, once you have ticked the box that allows it. It sends Spansh your position, the pad size and your choices, and nothing about you (see [What goes on the internet](internet-and-privacy.md)).

What this cannot tell you is in the last section of this guide.

## Compass

*(Starts minimized.)*

Points you at a spot on the planet you are on, from wherever you are on its surface (on foot, or in a vehicle), in any mode. It replaces
Mining's Surface Waypoint arrow, which could only point at the nearest hotspot and only while Mining's Surface page was open.

What it can point at:

- **The nearest hotspot** you have recorded on this body (the default, and what the old arrow did). Hotspots with no position yet are
  skipped.
- **One of your marks**: a name, a body and a latitude and longitude, kept for you alone (another commander on the same install does
  not see them) and never sent anywhere.
- **Nothing.**

The section shows what it is aiming at and how far (`↗ Ship - 340m NE`) and has three buttons and a box:

- **MARK** saves where you are now as a mark, named with what you typed in the box (or `Mark 1`, `Mark 2` ... if it is empty). The body
  comes from the game's `Status.json`.
- **TARGET** steps through what to aim at: the nearest hotspot, then each mark on this body, then nothing, then round again.
- **MARKS** opens the Marks window: every mark with how far it is from you now (when it is on your body), an editor to change a mark's
  name, body, latitude and longitude (**Here** fills in where you are), **Delete** (press twice), and buttons to aim at the nearest
  hotspot, at the selected mark, or at nothing. You can type a position, for example one from a guide or a screenshot.

To see the arrow on your game screen, tick **Settings → Overlays → Surface Compass → Enable Surface Compass** (**off by default**) and
press **Test Compass**. Where it sits is set on **Overlay Placement** ("Surface compass"). If you had the old Mining waypoint arrow on,
the compass is on and keeps its position.

The distance and direction are great-circle on a sphere the size of the body (from the body's radius in `Status.json`), good for "which
way and how far", not for the last few metres. The compass only points at things on the body you are on, and shows nothing until you
have a surface position.

## What the game does and doesn't tell us, and how to work around it

WNTB, like every third-party tool, only knows what Elite Dangerous writes to its journal files. It adds what EDSM, Spansh, Canonn and edastro report and works around the rest. Where it can't be sure, WNTB says so rather than guess quietly. See [How WNTB knows what it knows](README.md#how-wntb-knows-what-it-knows).

| What you might expect | What the game gives | What to do |
|---|---|---|
| The planner to know a stop was visited when you were not in the game | It counts arrivals the journal reports while the expedition is **running** (Start). A system you reached while it was paused, or before you started, is not ticked. | Use **Mark visited** for those. |
| Scans to count in a system that is not a stop, or at a stop you have not reached | Survey counts go to a stop you have reached, in the system the scan happened in, while the expedition is running. | Add the system as a stop, or use **Mark visited** for a stop you reached while it was paused. |
| The distance to the next stop on every stop | A distance needs a position for both ends. The game gives yours on every jump; a stop has one only if it came from a plotted route or EDSM. | Press **Locate and reorder (EDSM)**. A stop EDSM does not know shows `-`. |
| The jump total to include carrier jumps | A fleet carrier jump is not your ship's jump, so it ticks stops but does not add to the jump count or the light-years. | Nothing needed. |
| The light-years to be the whole route | It adds each jump's own distance as the game reports it, so it is the distance you flew, not the straight line between stops. | Nothing needed. |
| A note to know which body you are at | The body comes from `Status.json` (`BodyName`), which the game writes only while you are near a body, and not in supercruise between bodies. | Press **Here** in the Notes window beside Body, or type the name. A note can be about the system alone. |
| The nearest place to land to include a carrier that has only just jumped, or one whose docking access Spansh does not know | Spansh reports a carrier as it last saw it (when a commander's EDMC sent it), and a carrier's docking access is in the data for only some carriers. A carrier whose access is not "All", or not known, is left out. | Check the age shown for a carrier; for one you want to try, request docking when you arrive. |
| The nearest place to land to know a station's state right now | Spansh's records are what EDMC users last reported. A station that was attacked, or a carrier that moved, may differ, and a place nobody has visited recently may not be listed. | Treat the list as where to try first. |
| The compass to work in space or in a ship above the ground | The game gives a latitude and longitude only on a landable surface (on foot or in a vehicle). | Land, or get out, and it appears. |
| A mark to know which body it is on | The body comes from `Status.json` (`BodyName`), which the game writes only near a body. Marks are matched by body name. | Use **Here** while standing there, or type the body's full name as the game shows it. |
| Auto-Honk to press any control | It can only press **keyboard** keys, so your fire button must be bound to one. On Linux it needs `xdotool`; Wayland without XWayland is unsupported. | Bind a keyboard key to your fire button and use **Rescan** after changing bindings. |
| Boxel Survey to know where a system is | It works with **names**, not coordinates. It counts through the trailing number to make the next name and does not know whether that system exists. | The galaxy map is the judge. Press **Next >** to skip a name that won't plot. |
| The game to tell WNTB a candidate failed to plot | Nothing is written to the journal when the galaxy map can't find a name. | After 3 skips WNTB asks EDSM for a real nearby system. Press **Set** to move there. |
| "Not in EDSM" to mean undiscovered or real | It means nobody has uploaded it. It is not a guarantee the system exists or is unvisited. | Treat RND results as leads and confirm in the galaxy map. |
| A cube's real system count | WNTB only knows what EDSM, Spansh and your own visits revealed, so "complete" means every system **known** is done, or you marked it **Empty**. | Use **Mark Empty** when you have judged a cube done. |
| The color of a gas giant | The game never records it. The Green gas giant rule uses the Codex or matches the surface temperature of a confirmed green one. | Treat it as a lead and check the body in the system map. |
| Notable Bodies to be certain | A match comes from scan data, using its default limits. | Check the body before you plan around it. |
| Organic Scanning to name the species | Until a sample names it, the result is a **list of candidates** worked out from the planet's conditions. The main star is assumed to be the illuminating one, which can be wrong near a secondary star. A species with no usable rules can't be predicted, and new species need a WNTB update. | Take a first sample, which replaces the list with the exact species. The in-game exobiology tools are the final word. |
| Systems visited with EDMC closed to be known | The journals record every jump, so each start reads the last 14 days of journals for your arrivals and adds them to the visited list that **Skip systems already visited** and **RND** use. | Nothing needed for the last 14 days. Older jumps made with EDMC closed are not found. |
| Bodies-scanned count to be right after a restart | The honk (`FSSDiscoveryScan`) gives the body count and each scan counts one. If EDMC started after the honk, WNTB replays the current journal file for them. | If it still says to honk, honk again. A system's scans made in another journal file are not included. |
| The sale line to include sales before the current journal file | It is read from the current journal file when EDMC starts, then kept up to date live. | It resets to "none yet" when you restart EDMC after a new game session. |
| Codex Completionist to cover everything | Canonn's catalog has no geological or anomaly entries, so those never appear under **Not found**. The tally is per commander; after updating from a version where it was shared, each commander's is rebuilt from their own journals once (the old mixed tally can't be split). | Use the game's Codex for those. Press **Refresh Catalog** if the saved copy is old. |
| POI lists to be current | They are snapshots from Canonn and edastro, and are fetched only when you ask. | Press **FIND** or **REF** to refresh. |
| edastro's own "nearest" lookup to work | It does not use your position: a check on 2026-10-10 got "The Solar System" for every coordinate and name tried. WNTB downloads the full list and finds the nearest itself. | None needed. If FIND says the lookup failed, edastro's list could not be downloaded; try again later. |

