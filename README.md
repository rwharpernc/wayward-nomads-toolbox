<p align="center">
  <img src="https://waywardnomads.org/images/wwns-patch-transp_lg.png" alt="Wayward Nomads squadron patch" width="220">
</p>

# Wayward Nomads Toolbox (WNTB)

A free add-on for **Elite Dangerous** that puts a set of handy tools in one panel: Powerplay tracking,
exploration helpers, mining, missions, on-foot and cargo tracking, and more. It was built for the
**Wayward Nomads** exploration squadron (WWNS) and is open to anyone who wants it.

It runs inside [EDMC](https://github.com/EDCD/EDMarketConnector) (Elite Dangerous Market Connector), a
free companion program many commanders already use. You don't need to know any programming to use WNTB.

> **WNTB is in pre-release testing (version 0.x).** It works, but it's still being tested, and there
> is no official download yet. See [Installing](#installing) for how to try it. Please tell me what you
> find (see [Getting help](#getting-help)).

Built and maintained by R.W. Harper (CMDR Bocheaux).

---

## Contents

1. [What's in the toolbox](#whats-in-the-toolbox)
2. [What you need](#what-you-need)
3. [Installing](#installing)
4. [Finding your way around](#finding-your-way-around)
5. [What goes on the internet](#what-goes-on-the-internet)
6. [Powerplay](#powerplay)
7. [Exploration](#exploration)
8. [Mining](#mining)
9. [Missions](#missions)
10. [Field Ops](#field-ops)
11. [BGS](#bgs)
12. [Landing Assist and Interdiction Warning](#landing-assist-and-interdiction-warning)
13. [Using WNTB on Linux](#using-wntb-on-linux)
14. [Troubleshooting](#troubleshooting)
15. [Getting help](#getting-help)
16. [For developers, credits and licence](#for-developers-credits-and-licence)

---

## What's in the toolbox

WNTB has one panel with six **modes**. You click a button to switch between them.

| Mode | What it's for |
|---|---|
| **Powerplay** | Tracks the merits and Control Points you earn for your Power, and finds rare goods. |
| **Exploration** | Auto-honk, "first discovery" alerts, a boxel survey tool, scan values, exobiology help, and a lifetime tally of everything you've scanned. |
| **Mining** | Tracks space mining and surface (SRV) mining, and keeps your own catalogue of mining hotspots. |
| **Missions** | One view of every mission you have, with kill-progress bars for massacre missions. |
| **Field Ops** | Screenshots, your backpack/locker/cargo, saved ship builds, and colonisation sites. |
| **BGS** | Tracks the Background Simulation: faction states, and what your own activity does to them. |

Two more tools are always on and don't belong to a mode: **Landing Assist** and **Interdiction
Warning**.

Every feature can be turned on or off, so you only see what you want.

## What you need

- **EDMC** on Windows or Linux. Get it from the
  [EDMC page](https://github.com/EDCD/EDMarketConnector).
- **For features that draw on your game screen,** a small helper program running alongside the game:
  [EDMCOverlay](https://github.com/inorton/EDMCOverlay) (Windows) or
  [EDMCModernOverlay](https://github.com/SweetJonnySauce/EDMCModernOverlay) (Windows and Linux). This
  is only needed for on-screen alerts such as Discovery Alerts, Landing Assist and Interdiction
  Warning. Everything else works without it.

## Installing

There are no official releases yet, so there's no download on the Releases page. To try the
pre-release:

1. **Download it.** On this page (the repository's main page), click the green **Code** button, then
   **Download ZIP**. Extract the ZIP somewhere.
2. **Get the plugin folder ready.** Inside the extracted folder is a folder called **`plugin`**. Make a
   copy of it and rename the copy to **`WNTB`**.
   (If you have [Node.js](https://nodejs.org/) installed, you can instead run `npm run build` in the
   extracted folder, which creates a ready-made `dist/WNTB` folder. Developers: see
   [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md).)
3. **Put it in EDMC's plugins folder.** In EDMC, open **File → Settings → Plugins** and click **Open**
   next to "Plugins folder". (On Windows it's usually
   `%LOCALAPPDATA%\EDMarketConnector\plugins\`.) Drop the **`WNTB`** folder in there.
4. **Restart EDMC.** A **Wayward Nomads Toolbox (WNTB)** panel should appear.

**Updating:** repeat the steps, and copy the new files *over* the existing `WNTB` folder. Don't delete
the old folder first, because your saved data (hotspots, sessions and so on) lives inside it.

**Automatic updates** are off by default, and only look for official releases, so they do nothing until
the first one is published.

## Finding your way around

- **Switch modes** with the button row under the WNTB title. Every mode keeps working in the
  background while you look at a different one. Nothing pauses.
- **Collapse the panel** by clicking the "WNTB" title. Click it again to expand.
- **Settings** for each feature are under **File → Settings → WNTB**, in tabs. This is where you turn
  things on and off and adjust how they behave.
- **Pop-out windows** (sessions, rare goods, inventory, the BGS report, the Mining Book and so on)
  have their own dark look, remember their size and position, and close with **Esc** or the ✕. The
  main panel itself follows your EDMC theme.

### Opening the pop-out windows

Switch to the mode, then use the button listed here.

| Window | Mode | How to open it |
|---|---|---|
| Powerplay Sessions | Powerplay | **Sessions** button (bottom row of the panel) |
| Rare Goods Finder | Powerplay | **Rares** button, next to Sessions |
| BGS Report | BGS | **View BGS Report** button |
| Codex Completionist | Exploration | **View Details** button in the Codex Completionist section |
| Inventory | Field Ops | Click one of the **inventory bars** (there's no button) |
| Ship Builds | Field Ops | **Manage Ship Builds** button |
| Colonisation | Field Ops | **Colonisation Sites** button |
| Mining Book | Mining | **Mining Book...** button, on both the Space Mining and Surface Mining pages |

A few notes:
- You don't need to be mining to open the Mining Book. It lists your saved hotspots either way.
- The Missions windows only exist while you have active missions: click **All** for a full table, or
  click a mission card for that mission's details.
- If you can't find the BGS or Codex Completionist sections, they can each be switched off under
  **File → Settings → WNTB**. Both are on by default.

## What goes on the internet

Most of WNTB works entirely on your own computer, reading the game's journal files. Here is every
feature that contacts an outside site, so you can decide what you're comfortable with.

| Feature | Contacts | When |
|---|---|---|
| Rare Goods Finder | Spansh | Each time you open the window, to see which Power controls each origin system |
| Codex Completionist "Not found" tab | Canonn | Downloads a list in the background, then refreshes it about every two weeks (or when you click **Refresh Catalog**) |
| GEC Nearby POI | edastro.com | Only when you click **Find Nearest POI** |
| Canonn Nearby POI | Canonn | Downloads site lists when you click **Find Nearest POI** |
| Boxel Survey lookups | EDSM (and Spansh for Region Sweep) | When you use its lookup buttons; some automatic checks are optional in Settings |
| Exploration Value extras | Spansh, EDSM | **Off** until you turn them on in Settings |
| Mining lookups (hotspots, prices, ring reserves) | Spansh, EDSM | **Off** until you turn them on in Settings |
| BGS tick detection | A community tick-time service | Every 60 seconds while BGS is on; can be turned off in Settings |
| Automatic updates | GitHub | **Off** by default |

Everything else (Powerplay tracking, Missions, Inventory, Screenshots, Colonisation, Organic Scanning,
Ship Builds, Landing Assist and so on) makes no internet connection at all.

---

## Powerplay

Tracks the merits and Control Points you earn for your pledged Power.

**How to use it:** just play. The panel shows your current system's Powerplay state, what you've
earned in that system, and running totals for the session. Click **Sessions** to browse past sessions,
or **Rescan** if a session's numbers ever look wrong (it re-reads your journal from scratch).

**Rare Goods Finder:** click **Rares** to see the rare commodities closest to where you are. Each
row shows the origin system, station, landing-pad size, and which Power currently controls that
system, which is handy for Powerplay hauling. Double-click a row to open that commodity on Inara. Use
**Show nearest** to choose how many rows to see (up to all 141). The list needs your position, so it
says "Awaiting system data" until your first jump or login after EDMC starts. A "—" in the Power
column means unclaimed or couldn't be checked.

**Settings:** adjust the merit-per-Control-Point ratios (only needed if Frontier changes them) and
change the text used when you click **Copy** to paste a session summary into Discord or a forum post.

## Exploration

Everything in this mode sits in one scrolling panel, stacked top to bottom.

### Auto-Honk
Fires your Discovery Scanner automatically every time you jump into a system, so you never forget to
honk.

**How to use it:** turn it on with its toggle button. In **Settings → Auto-Honk** you can choose which
fire button it uses and how long it holds it, and the **Test Honk Now** button checks it's working
without waiting for a real jump. If you also run EDCoPilot with its own auto-honk, turn one of the two
off, or they'll fight each other.

### Discovery Alerts
Puts a banner on your in-game screen the moment you jump into a system nobody has scanned, or the
moment you're the first to scan or map a body.

**How to use it:** click its toggle button. It needs an overlay helper program running (see
[What you need](#what-you-need)); enter its connection details on the **Overlay Connection** Settings
tab. Use **Settings → Discovery** to move the banner or send a test one.

### Boxel Survey
A tool for exploring the galaxy systematically, system by system. (A "boxel" is a small cube of space
that Elite's procedurally generated systems are named after, such as `Outotz LS-K d8-0`.) It has three
modes, which you switch between with the buttons at the top of its section. The section is collapsed
by default. Click its title to expand it.

**Which mode should I use?**

| If you want to... | Use |
|---|---|
| Work through one boxel from start to finish, in order | **Sequence** |
| Clear a whole region (several boxels), tracking what's left across all of them | **Region Sweep** |
| Visit a fixed list of specific systems in a sensible order (a rendezvous, a squadron staging route) | **Waypoint Route** |

If you're not sure, start with **Sequence**. It's the simplest. Waypoint Route is the odd one out: it
accepts any system name, not just procedurally named ones.

- **Sequence:** set a starting system, then use **Next** and **Prev** to step through the candidates, or
  **Find Nearby (EDSM)** to jump to the nearest unexplored boxel. If several **Next** clicks go by
  with no real jump, WNTB can check EDSM for the nearest real system for you. Notable finds
  (Earth-likes, water worlds, biological signals and so on) are tallied automatically, and
  **Export Survey Log** (in Settings → Boxel Survey) saves them to a spreadsheet file.
- **Region Sweep:** for clearing a whole region. Add cubes to a queue, and use **Discover Nearby
  Cubes** or **Discover Known Systems** to fill in what's already known. Mark a cube **Empty** once
  you've confirmed there's nothing worth surveying, and it moves on to the next unfinished cube by
  itself. Turn on **Auto-discover more nearby cubes** (Settings → Region Sweep) to keep the queue
  topped up.
- **Waypoint Route:** add systems one at a time or with **Import CSV**, then click **Reorder
  (Nearest-Neighbor)** to sort them by distance from where you are.

**Random:** sits above the whole panel and works in any mode. It finds a real, known boxel near you,
then looks for a name EDSM has no record of, and copies it to your clipboard. Paste it into the galaxy
map to go find something nobody has discovered. It keeps its own log of every system you've actually
visited, so a place you've already been to isn't suggested as "new". Clear that log any time from
Settings → Boxel Survey → **Clear Visited Systems Log**.

### Exploration Value
A quiet readout of what you're finding. Nothing to turn on: it shows the estimated payout for your
last scan, the age of the current system, and which of the galaxy's 42 named regions you're in (for
example "Inner Orion Spur"), all worked out on your computer. Two extras are optional in **Settings →
Exploration Value**: how rare the Earth-like world you just found is, and whether EDSM already knows
about a system you've selected on the galaxy map.

### Organic Scanning
Helps you find and identify exobiology life on a planet's surface.

**How to use it:** once you've detected biological signals on a body and you're on the ground, it
shows which species each signal is likely to be, based on the planet's atmosphere, gravity,
temperature and more, with an estimated credit value. When you start sampling, it tracks your
progress and tells you when you've walked far enough for the next sample to count. It uses only your
own journal, makes no internet connection, and is designed to work alongside
[EDMC-Canonn](https://github.com/canonn-science/EDMC-Canonn) if you run that too.

### Codex Completionist
A personal tally of everything you've ever scanned: biological, geological, Guardian, human, Thargoid
and more.

**How to use it:** it builds itself as you play. Click **View Details** for the full breakdown (a ⭐
marks a genuine first discovery), or **Backfill from Journal History** once to pull in your past
journals. That button isn't automatic because it can take a while for a long career.

The details window has two tabs:
- **Found** is your tally by category. Click the **Entry** heading to sort A–Z or Z–A, or **Times
  found** for most or least found first. Click again to reverse.
- **Not found** lists the biological, civilisation and stellar-body entries you haven't found yet,
  using Canonn's catalogue. It sorts the same way, and the subtitle shows how many you've found.
  Geological and anomaly entries aren't in that catalogue, so they never appear here.

Double-click any entry (or select it and click **Open Reference**) to look it up on Canonn's website.

### GEC Nearby POI
Finds the nearest point of interest from edastro.com's exploration catalogue. Click **Find Nearest
POI**. It only looks something up when you ask.

### Canonn Nearby POI
The same idea, using Canonn's lists of Thargoid and Guardian sites. Click **Find Nearest POI**. The
first click downloads the lists, which are then kept for the rest of your session. **Refresh POI Data**
fetches fresh copies. Choose which kinds of site to include in **Settings → Canonn Nearby POI**. By
default it skips sites you've already logged in Codex Completionist, so it points you somewhere new;
you can turn that off in the same place.

## Mining

Tracks two kinds of mining: **Space Mining** (in your ship) and **Surface Mining** (in the Rhino SRV),
plus your own catalogue of known hotspots.

**How to use it:** use the ◂ and ▸ arrows to switch between the two pages. Each shows live stats for
your current run. Buttons appear when they're useful:

- **+ Save Hotspot Here** records a deposit you've found.
- **Mining Book** opens a window listing the bodies you've scanned in this system and every hotspot
  you've saved. You can filter by material or number of rigs, see tons mined and an estimate of tons
  left, edit or mark a hotspot as depleted, copy its coordinates, and view a zoomable map. For a
  scanned body it also shows what *you've* found so far on that kind of body. That starts empty and
  fills in as you save hotspots; it describes your own finds, not what a body actually holds.
- **Find Nearby Hotspots**, **Find Best Price** and **Check Ring Reserve Level** look things up on
  Spansh and EDSM. They're off until you turn them on in Settings.

**Settings:** turn on the lookups above, show live stats on your game screen, show a surface arrow
pointing to the nearest known hotspot, show a small "where have I driven" minimap, and archive
completed runs automatically.

## Missions

One view of every mission on your board, sorted by type, plus Community Goals.

**How to use it:** click a category tab (Massacre, Settlement Raids, Combat, Trade & Mining,
Passenger, Covert, On-Foot Ops, Other, Community Goals). Massacre and Settlement Raid missions show
grouped kill-progress bars; everything else shows one card per mission, and you can click a card for
full details. **All Missions** opens one flat, sortable table across every category.

**Settings:** choose what shows on each card (kill progress, mission counts, a commodities-needed
summary and so on).

## Field Ops

### Screenshots
Converts Elite's screenshots to PNG automatically, with an optional crop to just the relevant HUD
panel.

**How to use it:** nothing to do. Screenshots convert as you take them. Click "Click to expand" in the
panel to see thumbnails of recent ones. An optional auto-capture timer (a small clock icon) takes
screenshots periodically for you.

**Settings:** where converted screenshots are saved, whether to delete the originals, the file-name
format, and the auto-capture timing.

### Inventory
Tracks your Odyssey backpack, ship locker, fleet carrier locker and cargo hold as capacity bars.

**How to use it:** just play. Each bar fills and empties as you pick things up, use them or transfer
them. Click any bar to open the full inventory window, which has tabs for **Backpack**, **Ship
Locker**, **Carrier Locker** (once WNTB knows you own a carrier) and **Cargo**. The Cargo tab shows
the hold of whatever you're in, ship or SRV, and has a **Filter** box to find a particular item.

**Settings:** pickup notifications (sound, on-screen message, what it says), and capacity numbers if
your loadout doesn't match the defaults.

### Ship Builds
A place to keep ship builds you've designed on sites like Coriolis, EDSY or Spansh, one list per
commander. WNTB doesn't design ships itself. This just helps you find a build again later.

**How to use it:**
1. Design your build on whichever site you like.
2. Click **Manage Ship Builds** in the WNTB panel.
3. Click **Add**, give it a name (and optionally a role, such as "PvE Exploration"), pick the site and
   paste the build's web address.
4. Click **Save**.

Then select any saved build and use **Open Link** to open it in your browser or **Copy Link** to copy
the address. **Edit** and **Delete** work the same way.

### Colonisation
Keeps track of what each colonisation construction site still needs, so you can see it without being
docked, and what you still have to find after counting the cargo already in your hold.

**How to use it:**
1. Dock at a construction depot (or open its market) once. WNTB registers the site from the game's
   journal. There's nothing to type in.
2. The Field Ops panel shows your most recently updated site: its progress and the tonnes still to go.
3. Click **Colonisation Sites** for the full list. Each site is a group with its outstanding
   commodities underneath: required, delivered, remaining, how much is in your cargo now, and how much
   is left **To Source**.

Deliveries are counted from your journal as you hand cargo over, and corrected to the game's own
figures each time you dock at the depot again. Select a commodity row and use **Copy Shopping List** to
copy that site's list (handy for a squadron channel), **Remove Site** to stop tracking it, or **Remove
Finished** to clear completed and failed sites.

## BGS

Tracks the Background Simulation (BGS): faction states, and the effect of your own missions, bounties,
trade and exploration on them, for the systems and factions you choose.

**How to use it:** the panel always shows your current system, whether tracked or not. It says so if
the system is uninhabited; otherwise it lists every faction present, who controls it (★) and each
faction's current state. Click **Track** to start tracking the system (every faction in it) or
**Untrack** to stop. There's no limit on how many systems you track. You can also add systems or
individual factions under **Settings → BGS**.

Once something is tracked, WNTB tallies what you do there: mission completions (influence gained or
lost), bounty voucher and combat bond redemptions, trade profit or loss, and exploration data sold.
The panel shows a running total since the last "tick" (the daily BGS update). **View BGS Report**
opens the full breakdown with two tabs, **Faction States** and **Activity Tally** (This Tick and
Previous Tick), and **Copy Summary** copies it as plain text. Everything is kept separately for each
commander and survives restarting EDMC.

WNTB checks a community tick-time service once a minute to notice the real tick and start a fresh
tally. That's the only internet connection BGS makes, and you can turn it off in Settings (the tally
then just keeps adding up).

**Settings:** turn BGS on or off, turn tick detection on or off, and manage your tracked systems and
factions.

## Landing Assist and Interdiction Warning

These are always available, whichever mode you're in.

- **Landing Assist** shows which landing pad you've been assigned while docking, in the panel and as
  a diagram on your game screen. Turn it on and choose where it appears in **Settings → Landing**.
- **Interdiction Warning** puts an alert on your game screen the moment an interdiction starts. It has
  no panel button, only Settings. Turn it on and try it with **Test Warning** in **Settings →
  Interdiction Warning**.

Both need an overlay helper program running (see [What you need](#what-you-need)). Its connection
settings are on the **Overlay Connection** Settings tab.

---

## Using WNTB on Linux

Linux support is new and **experimental**. It hasn't been checked on a real install yet, so please
report anything odd. Elite runs under Steam Proton or Wine on Linux, which needs a few extras:

- **Install `xdotool`** (for example `sudo apt install xdotool`). Auto-Honk and timed screenshots use
  it to press keys in Elite's window. It works on X11, and on Wayland through XWayland.
- **WNTB finds your Steam Proton folder automatically**, including extra Steam library folders and
  Flatpak Steam. If you use Lutris, Heroic or a custom setup, enter that folder under **Settings →
  Auto-Honk → Elite Wine/Proton prefix**.
- **Point EDMC at the game's journals.** Set EDMC's own **Journal directory** setting to the
  `Saved Games/Frontier Developments/Elite Dangerous` folder inside that Proton/Wine folder. WNTB
  shows a hint under **Settings → Auto-Honk** if it looks wrong.
- **On-screen features** need [EDMCModernOverlay](https://github.com/SweetJonnySauce/EDMCModernOverlay),
  which supports Linux. The original EDMCOverlay is Windows-only. WNTB's default connection settings
  (`127.0.0.1`, port 5010) already match.
- **Notification sounds** use `canberra-gtk-play` or `paplay` if you have either.

A step-by-step checklist for testers is in [docs/LINUX_TESTING.md](docs/LINUX_TESTING.md).

## Troubleshooting

**The WNTB panel doesn't appear.**
Check that the folder is named exactly `WNTB` and sits directly inside EDMC's plugins folder, with
files such as `load.py` right inside it (not another folder inside it). Then restart EDMC.

**A button or section is missing.**
Open **File → Settings → WNTB** and check the feature hasn't been switched off. The BGS and Codex
Completionist sections can each be hidden there. Also make sure you're in the right mode.

**On-screen alerts don't show up.**
They need EDMCOverlay or EDMCModernOverlay running, and WNTB's **Overlay Connection** settings must
match it. Use the **Test** buttons in each feature's Settings tab to check.

**Numbers look wrong or out of date.**
Many features read the game's journal, so they only know what has happened since EDMC started, plus a
bit of recent history. Powerplay has a **Rescan** button. Codex Completionist has **Backfill from
Journal History**.

**Something else is wrong.**
EDMC's Help menu can open its log folder. The log often says exactly what went wrong, and including it
in a report helps a lot.

## Getting help

Found a bug, or have an idea? Please open an issue on the project's
[Issues page](https://github.com/rwharpernc/wayward-nomads-toolbox/issues), or find me in the Wayward
Nomads squadron. Say what you were doing, what you expected, and what happened. Including EDMC's log
helps. The squadron website is [waywardnomads.org](https://waywardnomads.org/).

## For developers, credits and licence

- **[docs/DEVELOPMENT.md](docs/DEVELOPMENT.md)**: setting up to build, test and change WNTB.
- **[docs/TECHNICAL.md](docs/TECHNICAL.md)**: how WNTB works and why it's built that way.
- **[docs/BOXEL_SURVEY_TECH_SPEC.md](docs/BOXEL_SURVEY_TECH_SPEC.md)** and
  **[docs/BGS_TECH_SPEC.md](docs/BGS_TECH_SPEC.md)**: the two largest features in depth.
- **[CHANGELOG.md](CHANGELOG.md)**: what has changed.
- **[docs/ATTRIBUTIONS.md](docs/ATTRIBUTIONS.md)**: thanks and acknowledgements to the projects and
  services that helped.

Copyright (c) 2026 R.W. Harper. Released under the [GNU General Public License v3.0](LICENSE).
Third-party notices are in [THIRD-PARTY-NOTICES.md](THIRD-PARTY-NOTICES.md).

*Elite Dangerous* is a trademark of Frontier Developments plc. WNTB is a fan-made tool and is not
official Frontier software.
