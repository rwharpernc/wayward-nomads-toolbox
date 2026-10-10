# Exploration

Exploration mode is one scrolling panel with several sections stacked top to bottom. Some sections start folded:
click a section's title (▸ / ▾) to open it. WNTB remembers which ones you left open.

**On this page:** [Auto-Honk](#auto-honk) · [Discovery Alerts](#discovery-alerts) ·
[Notable Bodies](#notable-bodies) · [Boxel Survey](#boxel-survey) · [Exploration Value](#exploration-value) ·
[Organic Scanning](#organic-scanning) · [Codex Completionist](#codex-completionist) ·
[GEC Nearby POI](#gec-nearby-poi) · [Canonn Nearby POI](#canonn-nearby-poi)

Anything that draws on your game screen needs an overlay. See [Getting started](getting-started.md#what-you-need)
and [Setting up the overlay](../OVERLAY_SETUP.md).

## Auto-Honk

Fires your Discovery Scanner automatically every time you jump into a system, so you never forget to honk.

**How to use it:**

1. Turn it on with its toggle button (**A.H.**) or the **Enable Auto-Honk** box in Settings. It is **off by default**.
2. Open **Settings → Exploration → Alerts** to choose which fire button it uses (**Primary** or **Secondary**; the
   default is Secondary) and how many seconds it holds it (**Hold**, default 10).
3. Two other options there: *Focus game window first* and *Skip systems already visited* (both on by default).
4. Press **Test Honk Now** to check it works without waiting for a real jump. **Rescan** re-reads your key
   bindings.

If you also run EDCoPilot with its own auto-honk, turn one of the two off, or they'll fight each other.

*On Linux this needs `xdotool` and a keyboard key bound to your fire button. See [WNTB on Linux](linux.md).*

## Discovery Alerts

Puts a banner on your in-game screen the moment you jump into a system nobody has scanned, or the moment you're the
first to scan or map a body.

**How to use it:**

1. Click its toggle button (**D.A.**) or tick **Enable Discovery Alerts** in Settings. It is **off by default**.
2. Make sure an overlay is running. The connection details are on the **Overlay Connection** Settings tab.
3. Use **Settings → Exploration → Alerts** to move the banner (X and Y boxes) or send a test one.

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

1. Open **Settings → Exploration → Alerts → Notable Bodies**.
2. Tick **Enable**. It is off until you do.
3. Choose which rules you want.
4. Press **Test Notable** to see a sample banner. The X and Y boxes move it.

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
  game never records a planet's colour, so treat this as a lead, not a fact.

**Off to start with** (because they're common): large landable, landable with rings, close orbit, close binary, high
eccentricity, fast orbit, fast rotation and wide ring.

### How alerts behave

- If a body matches several rules you get **one banner**, for example "High-value body +2".
- A body only alerts **once per rule**.
- Banners take turns if several come at once.
- The limits are Elite Observatory's own defaults.
- If the banner lands on top of another plugin's overlay text (Canonn's, for example), change X and Y.

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
   A grey hint under it says whether the name looks like a boxel name.
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
`boxel_survey_export.csv` and is saved **in the WNTB plugin folder**; you do not choose where.

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
system counts as done when you arrive there, or, if you turn on *Require a full FSS scan*, when it is fully scanned.

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
- which of the galaxy's 42 named regions you're in (for example "Inner Orion Spur").

All of that is worked out on your computer.

The readout itself is on by default (*Show estimated scan value, system age, and current region*). Two extras are
optional in **Settings → Exploration → Exploration Value**, and both are off until you tick them because they
contact the internet:

- *Show ELW rarity comparison when you scan an Earthlike World* (Spansh)
- *Show EDSM upload status when you select a system on the galaxy map* (EDSM)

## Organic Scanning

Helps you find and identify exobiology life on a planet's surface.

**How to use it:**

1. Detect biological signals on a body and get on the ground.
2. WNTB shows which species each signal is likely to be, based on the planet's atmosphere, gravity, temperature and
   more, with an estimated credit value.
3. When you start sampling, it tracks your progress and tells you when you've walked far enough for the next sample
   to count.

It uses only your own journal and makes no internet connection. It is designed to work alongside
[EDMC-Canonn](https://github.com/canonn-science/EDMC-Canonn) if you run that too. Detail is in the
[specification](../ORGANIC_SCANNING_TECH_SPEC.md).

## Codex Completionist

*(Starts folded: click the title to open it.)*

A running tally of the Codex entries your game has reported, such as biological, geological, Guardian, human and
Thargoid finds. It is built from the `CodexEntry` events in your journal. The panel shows one summary line, for
example `120 distinct entries, 340 total finds` followed by your three biggest categories, and two buttons:
**DET** and **BKF**. It is on by default; switch it off with *Track codex entries* in **Settings → Exploration →
Points of Interest**, where there is also a *View Canonn Codex* link.

**One thing to know:** the tally is **one per install, not per commander**. Every commander's entries on this
install go into the same list.

**BKF** (backfill from journal history) is a button you press yourself, because reading years of journals takes a
while. It reads **all** the journal files in EDMC's journal folder, with no date limit.

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
- **Not found**: Canonn's catalogue of **biological, civilisation and stellar-body** entries, minus the ones you
  have found. Columns: **Entry**, **Type**, **Platform** (Odyssey or Legacy). It sorts the same way. Canonn's
  catalogue has no geological or anomaly entries, so those never appear here.

**Buttons:** **Open Reference** and **Refresh Catalog**. Double-click a row, or select it and press **Open
Reference**. This opens a **search** on canonn.science for that entry's name in your browser, not a fixed page for
the entry.

**The catalogue** is downloaded from Canonn the first time you open the window and whenever the saved copy is
more than 14 days old, and **Refresh Catalog** fetches it again on demand. It is saved in the plugin folder, so
after the first download it opens instantly and works offline. If the download fails, the tab says so, and shows
the saved copy if there is one.

Codex Completionist has no specification page of its own. The code is `codex_completionist.py`,
`codex_completionist_window.py`, `codex_catalog.py` and `codex_backfill.py` in the plugin folder.

## GEC Nearby POI

*(Starts minimized.)*

Finds the nearest point of interest from edastro.com's exploration catalogue. Click **FIND**. It only looks
something up when you ask.

## Canonn Nearby POI

*(Starts minimized.)*

The same idea, using Canonn's lists of Thargoid and Guardian sites. Click **FIND**.

- The first click downloads the lists, which are then kept for the rest of your session.
- **REF** fetches fresh copies.
- Choose which kinds of site to include in **Settings → Exploration → Points of Interest**.
- By default it skips sites you've already logged in Codex Completionist, so it points you somewhere new. You can
  turn that off in the same place.
