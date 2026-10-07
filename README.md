<p align="center">
  <a href="https://waywardnomads.org/" target="_blank" rel="noopener noreferrer">
    <img src="docs/images/wwns-patch.png" alt="Wayward Nomads squadron patch - visit waywardnomads.org" width="220">
  </a>
</p>

# Wayward Nomads Toolbox (WNTB)

A free add-on for **Elite Dangerous** that puts a set of handy tools in one panel: Powerplay tracking,
exploration helpers, mining, missions, on-foot and cargo tracking, and more. It was built for the
**Wayward Nomads** exploration squadron (WWNS) and is open to anyone who wants it.

It runs inside [EDMC](https://github.com/EDCD/EDMarketConnector) (Elite Dangerous Market Connector), a
free companion program many commanders already use. You don't need to know any programming to use WNTB.

> **Download the latest release, not the repository.** See [Installing](#installing). If you hit a
> problem, see [Getting help](#getting-help).

Built and maintained by R.W. Harper: CMDR Bocheaux (Wayward Nomads, WWNS) and CMDR Mactavious (Easy Day, EZPZ).

---

## Contents

1. [What's in the toolbox](#whats-in-the-toolbox)
2. [What you need](#what-you-need)
3. [Platform support: Windows and Linux](#platform-support-windows-and-linux)
4. [Installing](#installing)
5. [Finding your way around](#finding-your-way-around)
6. [What goes on the internet](#what-goes-on-the-internet)
7. [Powerplay](#powerplay)
8. [Exploration](#exploration)
9. [Mining](#mining)
10. [Missions](#missions)
11. [Field Ops](#field-ops)
12. [BGS](#bgs)
13. [Landing Assist and Interdiction Warning](#landing-assist-and-interdiction-warning)
14. [Using WNTB on Linux](#using-wntb-on-linux)
15. [Troubleshooting](#troubleshooting)
16. [Getting help](#getting-help)
17. [For developers, credits and licence](#for-developers-credits-and-licence)

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
- **For features that draw on your game screen,** a small helper program running alongside the game.
  **[EDMCModernOverlay](https://github.com/SweetJonnySauce/EDMCModernOverlay) is the recommended one**
  (Windows and Linux). The older [EDMCOverlay](https://github.com/inorton/EDMCOverlay) (Windows only)
  also works. An overlay is only needed for on-screen alerts such as Discovery Alerts, Landing Assist
  and Interdiction Warning. Everything else works without it. Borderless or windowed mode in Elite works
  with every overlay. A step-by-step guide is in [docs/OVERLAY_SETUP.md](docs/OVERLAY_SETUP.md).

## Platform support: Windows and Linux

WNTB runs on **Windows and Linux**, wherever EDMC does. Almost everything is the same on both, because it
only reads the game's journal. A handful of features touch the operating system, and those are the ones
that differ. The Settings tab for each of them says which systems it works on and whether it can work on
*yours* right now (look for the **Works on:** line).

| Feature | Windows | Linux (Elite under Steam Proton or Wine) |
|---|---|---|
| Everything driven by the journal: Powerplay, Exploration, Mining, Missions, BGS, Colonisation, Inventory tracking, Ship Builds, Boxel Survey, Codex, Landing Assist, Interdiction Warning, Discovery Alerts | Yes | Yes, once EDMC's **Journal directory** points at the game's journals inside the Proton/Wine folder |
| **Game mode and credits lines** under the mode buttons | Yes | Yes (same journal data; the Journal directory must be set) |
| **Auto-Honk** (presses your Discovery Scanner key for you) | Yes | Yes, needs **`xdotool`**; X11 or XWayland windows only, not a native Wayland window |
| **Screenshot auto-timer** and **Thargoid-scan capture** (press the screenshot key for you) | Yes | Yes, needs **`xdotool`** |
| Screenshot conversion and renaming | Yes | Yes (Elite's `Pictures` folder inside the Proton/Wine folder) |
| Pickup **sound** (Field Ops → Inventory) | Yes (system beep) | Yes, needs `canberra-gtk-play` or `paplay` |
| On-screen overlay features | EDMCModernOverlay **or** the older EDMCOverlay | EDMCModernOverlay only |
| Self-update | Yes | Yes |

**Windows only:**
- **The older EDMCOverlay** overlay program. (EDMCModernOverlay replaces it and works on both. The
  Overlay Connection tab says so.)
- **OneDrive folder-redirect handling** for the Screenshot Directory, and the **Controlled Folder Access**
  hint when Windows blocks writing screenshots. Both are automatic and only appear on Windows.

**Linux only:**
- The **Elite Wine/Proton prefix** box in Settings → Auto-Honk (blank means auto-detect Steam), and the
  hint about EDMC's Journal directory.

**macOS** is not supported or tested. Journal-driven features may work, but key simulation and sounds
don't, and nothing has been checked there.

For exactly which files, folders and commands each system uses, see
[docs/TECHNICAL.md section 18](docs/TECHNICAL.md#18-platform-support-windows-and-linux). Linux setup is in
[Using WNTB on Linux](#using-wntb-on-linux).

## Installing

1. **Download the plugin.** Get **`WNTB.zip`** from the
   [latest release](https://github.com/rwharpernc/wayward-nomads-toolbox/releases/latest) (under
   **Assets**). It contains only the plugin, in a single folder called **`WNTB`**. Don't use the green
   **Code → Download ZIP** button: that downloads the whole source repository, which you don't need.
2. **Put it in EDMC's plugins folder.** In EDMC, open **File → Settings → Plugins** and click **Open**
   next to "Plugins folder". (On Windows it's usually
   `%LOCALAPPDATA%\EDMarketConnector\plugins\`.) Extract the ZIP
   into that folder (on Windows, right-click → **Extract All…** and set the destination to the plugins
   folder itself; on Linux, `unzip WNTB.zip -d <plugins folder>`). The ZIP contains a single folder
   called `WNTB`, so you end up with `plugins/WNTB/load.py`.
3. **Restart EDMC.** A **Wayward Nomads Toolbox (WNTB)** panel should appear.

**Updating:** download the new ZIP and extract it over the existing `WNTB` folder, replacing files when
asked. Don't delete the old folder first, because your saved data (hotspots, sessions and so on) lives
inside it. WNTB can also update itself: turn on **Automatic updates** in its settings (it's off by
default, and only looks at published releases).

**Building from source** is only for developers: see [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md).
`npm run package` creates the same ZIP.

## Finding your way around

- **Switch modes** with the button row under the WNTB title. Every mode keeps working in the
  background while you look at a different one. Nothing pauses.
- **Your game mode and credits** are shown just under the mode buttons, whichever mode you are in, with a
  rule below them before the page itself. The first line says which mode you are flying in ("You are in
  Solo mode.", Open, or Private Group with its name). The second is the credits you have earned or lost
  since you logged in, such as "+1,234,567 cr earned (+411,522 cr/hr)" or "-5,000 cr lost" (your balance now
  minus your balance at login; the rate appears once the session is a few minutes old). These two lines are
  the only place either appears.
- **Collapse the panel** by clicking the "WNTB" title. Click it again to expand (the credits line folds
  away with the rest).
- **Settings** for each feature are under **File → Settings → WNTB**, in tabs. This is where you turn
  things on and off and adjust how they behave.
- **Pop-out windows** (sessions, rare goods, inventory, the BGS report, the Mining Book and so on)
  have their own dark look, remember their size and position, and close with **Esc** or the ✕. The
  main panel itself follows your EDMC theme.

### Opening the pop-out windows

Switch to the mode, then use the button listed here.

| Window | Mode | How to open it |
|---|---|---|
| Powerplay Sessions (tabs: Current session, Systems, Cycles, Daily, History) | Powerplay | **Sessions** button (bottom row of the panel) |
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
| Rare Goods Finder | Spansh | The first time you open the window for each system, to see which Power controls it; remembered until you restart EDMC |
| Codex Completionist "Not found" tab | Canonn | Downloads a list when you open the details window (if it has none, or it's over two weeks old), or when you click **Refresh Catalog** |
| GEC Nearby POI | edastro.com | Only when you click **Find Nearest POI** |
| Canonn Nearby POI | Canonn | Downloads site lists when you click **Find Nearest POI** |
| Boxel Survey lookups | EDSM (and Spansh for Region Sweep) | When you use its lookup buttons; some automatic checks are optional in Settings |
| Exploration Value extras | Spansh, EDSM | **Off** until you turn them on in Settings |
| Mining lookups (hotspots, prices, ring reserves) | Spansh, EDSM | **Off** until you turn them on in Settings |
| BGS tick detection | A community tick-time service | Every 60 seconds while BGS is on; can be turned off in Settings |
| Automatic updates | GitHub | **Off** by default |

Everything else (Powerplay tracking, Missions, Inventory, Screenshots, Colonisation, Organic Scanning,
Ship Builds, Landing Assist and so on) makes no internet connection at all.

WNTB is built to ask these services for as little as it can: lookups are started by you or switched on
by you, answers are remembered, and every request says who it's from. The details are in
[docs/TECHNICAL.md](docs/TECHNICAL.md#keeping-api-traffic-low).

These services are run and funded by volunteers. If WNTB is useful to you, please consider supporting
them, as I do: [EDSM](https://www.patreon.com/EDSM), [Spansh](https://www.patreon.com/cw/spansh) and [Inara](https://www.patreon.com/cw/artieinara).

---

## Powerplay

> **Work in progress.** Powerplay is still being built, and I'd really appreciate your feedback: if something
> looks wrong, or you have a suggestion, please [open an issue](https://github.com/rwharpernc/wayward-nomads-toolbox/issues) or find me in the Wayward
> Nomads squadron. See [Getting help](#getting-help).

Tracks the merits and Control Points you earn for your pledged Power: live on the panel, and in the Sessions
window per session, per system, per Powerplay cycle and per day. Everything is kept **separately for each
commander**, so a commander pledged to another Power, or to none, has their own numbers.

**How to use it:** just play. The panel shows your current system's Powerplay state, what you've
earned in that system, and running merit totals for the session (your game mode and credits are on
the lines under the mode buttons). Click **Sessions** to open the Sessions window, or **Rescan** if a
session's numbers ever look wrong (it re-reads your journal from scratch).

### The Sessions window

| Tab | What it shows |
|---|---|
| **Current session** | This login: merits and estimated Control Points by system and by activity, and the Power context WNTB is using. |
| **Systems** | One tab per system for the cycle (see below), with the system's standing and what you earned there. |
| **Cycles** | One row per Powerplay cycle, newest first: period, the Power you were pledged to, systems worked, merits, estimated CP, merits by activity. |
| **Daily** | Merits and estimated CP (whole numbers) for each day of a cycle, with a total. |
| **History** | Every past session. |

**Cycles.** A Powerplay cycle runs from Thursday 07:00 UTC to the next Thursday 07:00 UTC and is numbered
(cycle 101 began on 2026-10-01). Each day of a cycle also runs 07:00 to 07:00 UTC, so day 1 is the Thursday.
The Systems, Cycles and Daily tabs all have a drop-down to look at an earlier cycle.

**Systems tab.**
- A line above the tabs totals the cycle: merits, estimated CP and how many systems you worked.
- Each system's **Standing** table compares a baseline (the system's last reading before the cycle began, or
  your first reading this cycle) with the latest: state, controlling Power, control progress, reinforcement
  and undermining, with the change. These are whole-system figures from the journal, everyone's work and not
  just yours, so you can see a system you're defending gaining or losing ground. They only update when you
  jump into or log in at the system, so they are as fresh as your last visit.
- **What you did** shows your own merits there by activity, with estimated Control Points.
- It shows your last 6 systems plus up to **5 you pin**. Click **☆ Pin** on a tab, or type a name in
  **Show a system** (it suggests as you type) and press **Add system**; **× Close tab** hides a system. Pinned
  tabs stay, in every cycle, even with no data. Pins and hidden tabs are remembered for each commander.

**Catching up from your journals.** The first time WNTB sees a commander it reads their journals to fill in the
last few cycles (4 by default; change it under **Settings > Powerplay > Journal scan**, 1 to 12), and after that it
reads only what happened while EDMC was closed, so playing without it running doesn't lose a cycle. It works out
what cycle it is, which cycles aren't in that commander's history yet and how many days back to read, and does
nothing when there's nothing new. The **Cycles** tab shows what it did. It can't read journals you've deleted, and
your own totals are never replaced by smaller ones.

**Good to know.** The journal doesn't say which activity merits came from, so WNTB infers it from the system
you're in (the same for the per-system and daily numbers). Control Points are estimates from merits using ratios
you can edit. Delivery and unattributed merits count as merits only. The detail is in the
[Powerplay specification](docs/POWERPLAY_TECH_SPEC.md).

**Rare Goods Finder:** click **Rares** to see the rare commodities closest to where you are. Each
row shows the origin system, station, landing-pad size, and which Power currently controls that
system, which is handy for Powerplay hauling. Double-click a row to open that commodity on Inara. Use
**Show nearest** to choose how many rows to see (up to all 141). The list needs your position, so it
says "Awaiting system data" until your first jump or login after EDMC starts. A "—" in the Power
column means unclaimed or couldn't be checked.

**Settings:** adjust the merit-per-Control-Point ratios (only needed if Frontier changes them), change the
text used when you click **Copy Progress** to paste a summary into Discord or a forum post, and choose how many
cycles the start-up journal scan covers.

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

**Short button names:** on the Exploration row, **A.H.** is Auto-Honk and **D.A.** is Discovery Alerts;
hover any button to see its full name.

**N.S. and W.D. buttons:** next to the toggle, find the nearest system whose *primary* star is a neutron
star (**N.S.**) or a white dwarf (**W.D.**), measured from where you are now. They show the system name and
distance and copy the name to your clipboard so you can paste it into the galaxy map. Manual only: they
contact spansh.co.uk when you click and never on their own. Jump or reload first so WNTB knows your position.

### Boxel Survey

> **Work in progress.** Boxel Survey is still being built, and I'd really appreciate your feedback: if something
> looks wrong, or you have a suggestion, please [open an issue](https://github.com/rwharpernc/wayward-nomads-toolbox/issues) or find me in the Wayward
> Nomads squadron. See [Getting help](#getting-help).

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

> **Work in progress.** BGS tracking is still being built, and I'd really appreciate your feedback: if something
> looks wrong, or you have a suggestion, please [open an issue](https://github.com/rwharpernc/wayward-nomads-toolbox/issues) or find me in the Wayward
> Nomads squadron. See [Getting help](#getting-help).


Tracks the Background Simulation (BGS): faction states, and the effect of your own missions, bounties,
trade, exploration and crimes on them. Nothing to set up: it records wherever you act.

**The panel** shows only the system you're in: each faction present (★ marks the controller), its state
and influence, and under each faction what you've done to it since the last server tick. Influence and
state show how far they moved since before the tick, for example `45.0% (+5.0)` or `None → Boom`.

**What it counts, increases and decreases:** missions completed (influence pips gained or lost),
missions failed or abandoned, bounty voucher and combat bond redemptions, trade profit or loss, exploration
data sold, and crimes committed against a faction.

**View BGS Report** opens a window with a drop-down to pick the tick (the current one, or an earlier one
from the archive) and one tab per system you've acted in during it. Each tab lists every faction there
(state, influence and change, pending, recovering and active states) and a table of what you did to each.
Tabs show the last 6 systems you've been in (the one you're in first), with each tab's full system name.
Click **Pin** on a tab to keep it: a pinned system (marked ★) stays at the front however long ago you were
there, and shows a ★ on the panel when you're in it. **Close tab** hides one you don't want. To show any
system, use the **Show a system** box: click its arrow to pick from every system you've been in, or
just start typing and the list narrows as you type (names starting with what you typed come first). Press
Enter or click **Add system** - that pins it, and it's also how you bring back a closed tab. Any name can
be typed, not only ones from the list. A key at the bottom of the window explains the tabs and every column. **Copy Summary** copies every tick and system as plain text.

**Resets and history:** the totals reset at each tick and the closed tick is archived. When EDMC starts,
WNTB re-reads your last few journals so the totals are cumulative since the tick even if EDMC wasn't
running the whole time. Everything is kept separately for each commander.

WNTB checks a community tick-time service once a minute to notice the real tick. That's the only internet
connection BGS makes, and you can turn it off in Settings. Without it the totals never reset on their own
and the journals can't be replayed, because WNTB doesn't know when the tick was.

**Settings:** turn BGS on or off, turn tick detection on or off, and choose how many days of previous ticks
to keep (default 7).

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

Linux support is **new and not yet verified on a real install**: it is tested with mocked tools and
temporary folders, and by reading every module for Windows-only assumptions, but please report anything
odd. Elite runs under Steam Proton or Wine on Linux, which needs a few extras:

- **Install `xdotool`** (for example `sudo apt install xdotool`). Auto-Honk and the screenshot
  auto-timer use it to press keys in Elite's window. It works on X11, and on Wayland through XWayland
  (which is where a Proton game's window lives), but not with a native Wayland window.
- **WNTB finds your Steam Proton folder automatically**, including extra Steam library folders and
  Flatpak Steam. If you use Lutris, Heroic or a custom setup, enter that folder under **Settings →
  Auto-Honk → Elite Wine/Proton prefix**.
- **Point EDMC at the game's journals.** Set EDMC's own **Journal directory** setting to the
  `Saved Games/Frontier Developments/Elite Dangerous` folder inside that Proton/Wine folder. Linux has
  no default for it, and without it WNTB's journal-based features (including BGS rebuilding the tick's
  totals) have nothing to read. WNTB shows a hint under **Settings → Auto-Honk** and **Settings → BGS**
  if it looks wrong, and logs one at startup.
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
- **Feature specifications**, each covering what a feature reads, its rules and its limits:
  [Missions](docs/MISSIONS_TECH_SPEC.md), [Mining](docs/MINING_TECH_SPEC.md),
  [Boxel Survey](docs/BOXEL_SURVEY_TECH_SPEC.md), [BGS](docs/BGS_TECH_SPEC.md),
  [Organic Scanning](docs/ORGANIC_SCANNING_TECH_SPEC.md), [Powerplay](docs/POWERPLAY_TECH_SPEC.md) and
  [Screenshots and input automation](docs/SCREENSHOTS_AND_INPUT_TECH_SPEC.md).
- **[docs/OVERLAY_SETUP.md](docs/OVERLAY_SETUP.md)**: setting up the on-screen overlay (for everyone).
- **[CHANGELOG.md](CHANGELOG.md)**: what has changed.
- **[docs/ATTRIBUTIONS.md](docs/ATTRIBUTIONS.md)**: thanks and acknowledgements to the projects and
  services that helped.

Copyright (c) 2026 R.W. Harper. Released under the [GNU General Public License v3.0](LICENSE).
Third-party notices are in [THIRD-PARTY-NOTICES.md](THIRD-PARTY-NOTICES.md).

*Elite Dangerous* is a trademark of Frontier Developments plc. WNTB is a fan-made tool and is not
official Frontier software.
