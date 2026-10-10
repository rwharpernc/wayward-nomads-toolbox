<p align="center">
  <a href="https://waywardnomads.org/" target="_blank" rel="noopener noreferrer">
    <img src="docs/images/wwns-patch.png" alt="Wayward Nomads squadron patch - visit waywardnomads.org" width="220">
  </a>
</p>

# Wayward Nomads Toolbox (WNTB)

A free add-on for **Elite Dangerous** that puts a set of handy tools in one panel: Powerplay tracking,
exploration helpers, mining, trading (profit tracking, routes, prices and fleet carrier cargo), missions, on-foot and
cargo tracking, and more. It was built for the
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
10. [Trade](#trade)
11. [Missions](#missions)
12. [Field Ops](#field-ops)
13. [BGS](#bgs)
14. [Landing Assist and Interdiction Warning](#landing-assist-and-interdiction-warning)
15. [Using WNTB on Linux](#using-wntb-on-linux)
16. [Troubleshooting](#troubleshooting)
17. [Getting help](#getting-help)
18. [For developers, credits and licence](#for-developers-credits-and-licence)

---

## What's in the toolbox

WNTB has one panel with seven **modes**. You click a button to switch between them.

| Mode | What it's for |
|---|---|
| **Powerplay** | Tracks the merits and Control Points you earn for your Power, and finds rare goods. |
| **Exploration** | Auto-honk, "first discovery" and notable-body alerts, a boxel survey tool, scan values, exobiology help, and a lifetime tally of everything you've scanned. |
| **Mining** | Tracks space mining and surface (SRV) mining, and keeps your own catalogue of mining hotspots. |
| **Trade** | Your trading profit after fuel and repairs, your ship hold and fleet carrier cargo space, saved sessions in a Trade History window, and Spansh lookups for the best trade routes and the best place to buy or sell. |
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
  **Every WNTB overlay is off until you tick it in Settings** (Inventory, Landing Assist and Screenshots used to start on;
  the release that added Trade switched them all off once on its first start, so tick the ones you want again).

## Platform support: Windows and Linux

WNTB runs on **Windows and Linux**, wherever EDMC does. Almost everything is the same on both, because it
only reads the game's journal. A handful of features touch the operating system, and those are the ones
that differ. The Settings tab for each of them says which systems it works on and whether it can work on
*yours* right now (look for the **Works on:** line).

| Feature | Windows | Linux (Elite under Steam Proton or Wine) |
|---|---|---|
| Everything driven by the journal: Powerplay, Exploration, Mining, Missions, BGS, Colonisation, Inventory tracking, Ship Builds, Boxel Survey, Codex, Landing Assist, Interdiction Warning, Discovery Alerts | Yes | Yes, once EDMC's **Journal directory** points at the game's journals inside the Proton/Wine folder |
| **Game mode and credits lines** under the mode buttons | Yes | Yes (same journal data; the Journal directory must be set) |
| **Trade**: session profit and costs, stock, carrier cargo, Trade History (including **Export log (CSV)**), and the Spansh route and price lookups | Yes | Yes. The Journal directory must be set: Trade reads the journals to catch a session up after EDMC was closed |
| **Auto-Honk** (presses your Discovery Scanner key for you) | Yes | Yes, needs **`xdotool`**; X11 or XWayland windows only, not a native Wayland window |
| **Screenshot auto-timer** and **Thargoid-scan capture** (press the screenshot key for you) | Yes | Yes, needs **`xdotool`** |
| Screenshot conversion and renaming | Yes | Yes (Elite's `Pictures` folder inside the Proton/Wine folder) |
| Pickup **sound** (Field Ops → Inventory) | Yes (system beep) | Yes, needs `canberra-gtk-play` or `paplay` |
| On-screen overlay features | EDMCModernOverlay **or** the older EDMCOverlay | EDMCModernOverlay only |
| Self-update | Yes | Yes |

**Windows only:**
- **The older EDMCOverlay** overlay program. (EDMCModernOverlay replaces it and works on both. The
  Overlay Connection tab (Settings → General) says so.)
- **OneDrive folder-redirect handling** for the Screenshot Directory, and the **Controlled Folder Access**
  hint when Windows blocks writing screenshots. Both are automatic and only appear on Windows.

**Linux only:**
- The **Elite Wine/Proton prefix** box in Settings → Exploration → Alerts (blank means auto-detect Steam), and the
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

- **Switch modes** with the button row under the WNTB title (**P.P.**, **BGS**, **EXP**, **MIN**, **TRD**,
  **MSN**, **OPS**; hover for the full name). Every mode keeps working in the
  background while you look at a different one. Nothing pauses.
- **Your game mode and credits** are shown just under the mode buttons, with a rule below them before the
  page itself. The first line says which mode you are flying in ("You are in Solo mode.", Open, or Private
  Group with its name) and is always there. The second is the credits you have earned or lost since you logged
  in, such as "+1,234,567 cr earned (+411,522 cr/hr)" or "-5,000 cr lost" (your balance now minus your balance
  at login; the rate appears once the session is a few minutes old). It is shown on **Powerplay, BGS, Mining,
  Missions and Field Ops**, and hidden on **Exploration** (not useful there) and **Trade** (which has its own
  net profit that already counts your running costs). It keeps counting while hidden.
- **Pages.** Mining, Trade and Missions have several pages. Click the large orange **◀** and **▶** buttons
  at the top of the panel to move between them.
- **Collapse the panel** by clicking the "WNTB" title. Click it again to expand (the credits line folds
  away with the rest).
- **Buttons have short names.** The EDMC main window is small, and every plugin shares it, so WNTB's
  buttons use abbreviations to keep the panel compact rather than widening your window. **Hover over any
  button for a moment and a tooltip shows its full name.** The full list is in
  [Button names](#button-names) below.
- **The EDMC window resizes its height to fit** when you open it, switch modes, or expand or collapse a
  section, so you never have to drag it taller. It leaves your width and position alone. If you'd rather set
  the height yourself, untick it under **File → Settings → WNTB → Window**.
- **Settings** for each feature are under **File → Settings → WNTB**, in tabs grouped by mode (General,
  Powerplay, Missions, Exploration, Mining, Trade, BGS, Field Ops, Always On; Exploration, Field Ops and the others
  hold a row of tabs of their own). This is where you turn
  things on and off and adjust how they behave.
- **Pop-out windows** (sessions, rare goods, inventory, the BGS report, the Mining Book and so on)
  have their own dark look, remember their size and position, and close with **Esc** or the ✕. The
  main panel itself follows your EDMC theme.

### Opening the pop-out windows

Switch to the mode, then use the button listed here.

| Window | Mode | How to open it |
|---|---|---|
| Powerplay Sessions (tabs: Current session, Systems, Cycles, Daily, History) | Powerplay | **SES** button (bottom row of the panel) |
| Rare Goods Finder | Powerplay | **RARES** button, next to SES |
| BGS Report | BGS | **REPORT** button |
| Codex Completionist | Exploration | **DET** button in the Codex Completionist section |
| Inventory | Field Ops | Click one of the **inventory bars** (there's no button) |
| Ship Builds | Field Ops | **SHIPS** button |
| Colonisation | Field Ops | **REPORT** button |
| Mining Book | Mining | **BOOK** button, on both the Space Mining and Surface Mining pages |
| Trade History (tabs: Overview, Commodities, Stations, Route, Trades, Stock & carrier, Lookups) | Trade | **History** button on the Session page |

A few notes:
- You don't need to be mining to open the Mining Book. It lists your saved hotspots either way.
- The Missions windows only exist while you have active missions: click **All** for a full table, or
  click a mission card for that mission's details.
- If you can't find the BGS or Codex Completionist sections, they can each be switched off under
  **File → Settings → WNTB**. Both are on by default.

### Button names

Hover over any button for a moment to see its full name.

| Button | Full name | Where |
|---|---|---|
| **P.P.** | Powerplay | Mode buttons (top of the panel) |
| **BGS** | BGS | Mode buttons |
| **EXP** | Exploration | Mode buttons |
| **MIN** | Mining | Mode buttons |
| **TRD** | Trade | Mode buttons |
| **MSN** | Missions | Mode buttons |
| **OPS** | Field Ops | Mode buttons |
| **SES** | Sessions | Powerplay |
| **RARES** | Rares (rare goods finder) | Powerplay |
| **RESCAN** | Rescan | Powerplay |
| **REPORT** | View BGS report | BGS |
| **A.H.** | Auto-Honk | Exploration |
| **D.A.** | Discovery Alerts | Exploration |
| **N.S.** | Nearest neutron star (primary star) | Exploration |
| **W.D.** | Nearest white dwarf (primary star) | Exploration |
| **RND** | Random (an undiscovered system nearby) | Exploration |
| **FIND** | Find nearest POI (GEC and Canonn) | Exploration |
| **REF** | Refresh POI data (Canonn) | Exploration |
| **DET** | View details (Codex Completionist) | Exploration |
| **BKF** | Backfill from journal history (Codex Completionist) | Exploration |
| **H.S.** | Find nearby hotspots | Mining |
| **+H.S.** | Save hotspot here | Mining |
| **PRICE** | Find best price | Mining |
| **RES** | Check ring reserve level | Mining |
| **I/E** | Import/export hotspots | Mining |
| **BOOK** | Mining Book | Mining |
| **Reset** | End this session and start a new tally (offers to save first) | Trade (Session page) |
| **Save session** | Keep this session in Trade History (the tally keeps running; press Reset to start a new one) | Trade (Session page) |
| **History** | Open the Trade History window | Trade (Session page) |
| **Rebuild** | Recount the session from the journals from a start time you give (UTC); for a session that began on another computer | Trade (Session page) |
| **Find routes** / **Cancel** | Ask Spansh for trade routes / stop waiting | Trade (Routes page) |
| **Hops** | Cycle the route length through 2, 3, 4 and 5 hops | Trade (Routes page) |
| **Round trip** | Find the best back-and-forth pair of stations, loaded both ways | Trade (Routes page) |
| **Copy next system** | Copy the first destination to the clipboard | Trade (Routes page) |
| **Sell** / **Buy** | Choose whether the search is for selling or buying | Trade (Market page) |
| **Near me** / **Galaxy** | Best place to sell or buy, near you / anywhere | Trade (Market page) |
| **Price finder** | The Mining PRICE finder, for any commodity | Trade (Market page) |
| **◀** / **▶** | Previous / next page | Mining, Trade, Missions |
| **SHIPS** | Manage ship builds | Field Ops |
| **REPORT** | Colonisation sites | Field Ops |

The buttons inside pop-out windows and Settings keep their full names.

## What goes on the internet

Most of WNTB works entirely on your own computer, reading the game's journal files. Here is every
feature that contacts an outside site, so you can decide what you're comfortable with.

| Feature | Contacts | When |
|---|---|---|
| N.S. and W.D. buttons (nearest neutron star / white dwarf) | Spansh | Only when you click **N.S.** or **W.D.** |
| Rare Goods Finder | Spansh | The first time you open the window for each system, to see which Power controls it; remembered until you restart EDMC |
| Codex Completionist "Not found" tab | Canonn | Downloads a list when you open the details window (if it has none, or it's over two weeks old), or when you click **Refresh Catalog** |
| GEC Nearby POI | edastro.com | Only when you click **FIND** |
| Canonn Nearby POI | Canonn | Downloads site lists when you click **FIND** |
| Boxel Survey lookups | EDSM (and Spansh for Region Sweep) | When you use its lookup buttons; some automatic checks are optional in Settings |
| Exploration Value extras | Spansh, EDSM | **Off** until you turn them on in Settings |
| Mining lookups (hotspots, prices, ring reserves) | Spansh, EDSM | **Off** until you turn them on in Settings |
| Trade lookups (best routes; where to buy or sell a commodity) | Spansh | **Off** until you turn them on in Settings. Only when you press **Find routes** (it then checks for the answer every 5 seconds, for up to 4 minutes, until you press **Cancel**) or **Near me** / **Galaxy** (two requests each: stations, then fleet carriers; one if you hide carriers) or **Round trip** (one to three requests of up to 100 stations each) |
| BGS tick detection | A community tick-time service | Every 60 seconds while BGS is on; can be turned off in Settings |
| Automatic updates | GitHub | **Off** by default |

Everything else (Powerplay tracking, Missions, Inventory, Screenshots, Colonisation, Organic Scanning,
Ship Builds, Landing Assist, and Trade's session profit, stock, carrier cargo and History, and so on) makes no
internet connection at all.

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
the lines under the mode buttons). Click **SES** to open the Sessions window, or **RESCAN** if a
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

**Rare Goods Finder:** click **RARES** to see the rare commodities closest to where you are. Each
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

**How to use it:** turn it on with its toggle button. In **Settings → Exploration → Alerts** you can choose which
fire button it uses and how long it holds it, and the **Test Honk Now** button checks it's working
without waiting for a real jump. If you also run EDCoPilot with its own auto-honk, turn one of the two
off, or they'll fight each other.

### Discovery Alerts
Puts a banner on your in-game screen the moment you jump into a system nobody has scanned, or the
moment you're the first to scan or map a body.

**How to use it:** click its toggle button. It needs an overlay helper program running (see
[What you need](#what-you-need)); enter its connection details on the **Overlay Connection** Settings
tab. Use **Settings → Exploration → Alerts** to move the banner or send a test one.

**Short button names:** on the Exploration row, **A.H.** is Auto-Honk and **D.A.** is Discovery Alerts
(see [Button names](#button-names)).

**N.S. and W.D. buttons:** next to the toggle, find the nearest system whose *primary* star is a neutron
star (**N.S.**) or a white dwarf (**W.D.**), measured from where you are now. They show the system name and
distance and copy the name to your clipboard so you can paste it into the galaxy map. Manual only: they
contact spansh.co.uk when you click and never on their own. Jump or reload first so WNTB knows your position.

### Notable Bodies
Puts a violet banner on your in-game screen when a body you scan is worth a second look. A match comes
from the scan data, so check the body in the system map before you plan around it. It needs the same
overlay helper as Discovery Alerts (see [What you need](#what-you-need)).

**How to use it:** open **Settings → Exploration → Alerts → Notable Bodies**, tick **Enable**, and choose
which rules you want. It is off until you do. **Test Notable** shows a sample banner, and the X and Y boxes
move it. It has no button on the main panel.

**What it looks for.** These are on to start with, because they are the rarer finds:

- **High-value body**: any terraformable world, and every Earth-like, water and ammonia world, whether or
  not you can land on it. The log line says if it is undiscovered or unmapped.
- **Terraformable landable**, **High-g landable** (about 3 g or more), **Shepherd moon**,
  **Good FSD injection** (5 or 6 of the premium boost materials on a landable), **Colliding binary**.
- **Green gas giant**: from the Codex, or a gas giant whose surface temperature matches a confirmed green
  one. The game never records a planet's colour, so treat this as a lead.

These are off to start with, because they are common: large landable, landable with rings, close orbit,
close binary, high eccentricity, fast orbit, fast rotation and wide ring.

If a body matches several rules you get one banner (for example "High-value body +2"). A body only alerts
once per rule, and banners take turns if several come at once. The limits are Elite Observatory's own
defaults. If the banner lands on top of another plugin's overlay text (Canonn's, for example), change X and
Y.

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
  **Export Survey Log** (in Settings → Exploration → Boxel Survey) saves them to a spreadsheet file.
- **Region Sweep:** for clearing a whole region. Add cubes to a queue, and use **Discover Nearby
  Cubes** or **Discover Known Systems** to fill in what's already known. Mark a cube **Empty** once
  you've confirmed there's nothing worth surveying, and it moves on to the next unfinished cube by
  itself. Turn on **Auto-discover more nearby cubes** (Settings → Exploration → Region Sweep) to keep the queue
  topped up.
- **Waypoint Route:** add systems one at a time or with **Import CSV**, then click **Reorder
  (Nearest-Neighbor)** to sort them by distance from where you are.

**RND** (random): sits on the Exploration button row, next to A.H., D.A., N.S. and W.D., so it stays
visible even while this section is collapsed, and works in any mode. It finds a real, known boxel near you,
then looks for a name EDSM has no record of, and copies it to your clipboard. Paste it into the galaxy
map to go find something nobody has discovered. It keeps its own log of every system you've actually
visited, so a place you've already been to isn't suggested as "new". Clear that log any time from
Settings → Exploration → Boxel Survey → **Clear Visited Systems Log**.

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
(Starts minimized: click the title to open it.)

A personal tally of everything you've ever scanned: biological, geological, Guardian, human, Thargoid
and more.

**How to use it:** it builds itself as you play. Click **DET** for the full breakdown (a ⭐
marks a genuine first discovery), or **BKF** (backfill from journal history) once to pull in your past
journals. That button isn't automatic because it can take a while for a long career.

The details window has two tabs:
- **Found** is your tally by category. Click the **Entry** heading to sort A–Z or Z–A, or **Times
  found** for most or least found first. Click again to reverse.
- **Not found** lists the biological, civilisation and stellar-body entries you haven't found yet,
  using Canonn's catalogue. It sorts the same way, and the subtitle shows how many you've found.
  Geological and anomaly entries aren't in that catalogue, so they never appear here.

Double-click any entry (or select it and click **Open Reference**) to look it up on Canonn's website.

### GEC Nearby POI
Finds the nearest point of interest from edastro.com's exploration catalogue. Click **FIND**. It only
looks something up when you ask. This section starts minimized: click its title (▸ / ▾) to open it.
WNTB remembers which sections you left open.

### Canonn Nearby POI
(Starts minimized, like GEC Nearby POI and Codex Completionist: click the title to open it.)

The same idea, using Canonn's lists of Thargoid and Guardian sites. Click **FIND**. The
first click downloads the lists, which are then kept for the rest of your session. **REF**
fetches fresh copies. Choose which kinds of site to include in **Settings → Exploration → Points of Interest**. By
default it skips sites you've already logged in Codex Completionist, so it points you somewhere new;
you can turn that off in the same place.

## Mining

Tracks two kinds of mining: **Space Mining** (in your ship) and **Surface Mining** (in the Rhino SRV),
plus your own catalogue of known hotspots.

**How to use it:** use the ◀ and ▶ buttons to switch between the two pages. Each shows live stats for
your current run. Buttons appear when they're useful, side by side in one row (hover for the full name):

- **+H.S.** (save hotspot here) records a deposit you've found.
- **BOOK** (the Mining Book) opens a window listing the bodies you've scanned in this system and every hotspot
  you've saved. You can filter by material or number of rigs, see tons mined and an estimate of tons
  left, edit or mark a hotspot as depleted, copy its coordinates, and view a zoomable map. For a
  scanned body it also shows what *you've* found so far on that kind of body. That starts empty and
  fills in as you save hotspots; it describes your own finds, not what a body actually holds.
- **H.S.** (find nearby hotspots), **PRICE** (find best price) and **RES** (check ring reserve level) look things up on
  Spansh and EDSM. They're off until you turn them on in Settings.

**Settings:** turn on the lookups above, show live stats on your game screen, show a surface arrow
pointing to the nearest known hotspot, show a small "where have I driven" minimap, and archive
completed runs automatically.

## Trade

Everything about buying and selling: what you've earned after fuel and repairs, what you still have tied up in
cargo, your hold and your carrier's space, and where to find the best routes and prices. Trade mode has three pages,
**Session**, **Routes** and **Market**; use the large orange **◀** and **▶** buttons at the top of the panel to move
between them. A pop-out **Trade History** window keeps the sessions you choose to save.

Each page is laid out in sections (orange headings with a rule between them), with label-and-value rows (the value on
the right) and tables whose numbers line up in columns. Long station names wrap instead of being cut off. A page's
buttons are at the top, under the page arrows.

### How a trading session works

- **A session is your running tally, and it belongs to a commander.** It starts the first time WNTB sees you and lasts
  **until you press Reset**, however many times you log in or restart EDMC. That is what makes a long job, such as
  loading a fleet carrier over several evenings, one session.
- **Each commander has their own.** Switching to another commander never loses anyone's tally.
- **Playing with EDMC closed is fine.** The next time EDMC sees that commander it catches the session up from the game's
  journal files and adds what it missed. It only adds what is new, so it can't count anything twice. (On Linux this
  needs EDMC's **Journal directory** to be set; see [Using WNTB on Linux](#using-wntb-on-linux).) Journal files copied
  over from another computer are found and read the same way, while EDMC is running; see
  [Using Trade on two computers](#using-trade-on-two-computers).
- **Only what WNTB has seen is counted.** Trades made before WNTB first ran, or in a session you reset, aren't included.
- **Nothing is kept for good unless you ask.** Press **Save session** to put it in Trade History (below).
- **Finishing a session and starting the next: Save session, then Reset.** There is no Start or Track button, because
  tracking never stops. **Save session** only copies the tally into Trade History; the tally keeps running and the
  button stays **Save session** (saving again updates the same entry). **Reset** is what begins a new session, and if
  the current one has unsaved trades it offers to save it first. If you skip Reset, your next trades are added to the
  old session.

### Using Trade on two computers

If you play on more than one computer (say Windows and Linux), each one keeps **its own** Trade records. The game's
journals are the only thing that has to travel between them, and WNTB reads them for you.

**What lives on each computer** (files in the WNTB plugin folder, never shared): the session tally
(`trade_ledger.json`), the stock list (`trade_stock.json`), the carrier figures (`trade_carrier.json`), saved sessions
(`trade_history.json`) and the list of journals already read (`trade_journal_scan.json`). Copying these between
computers is not needed and not recommended.

**What to do:**

1. Copy the journal files from the computer you played on into the other computer's journal folder (the one EDMC's
   **Journal directory** points at). Copy them all, not just the newest; copying a file that is already there is fine.
   Doing it while the game is closed is best, because a file that is still being written is read again later.
2. That's it. WNTB looks for journal files it hasn't read **a few seconds after EDMC starts and then once a minute**.
   It reads each new file (and any file that has grown since) once, and adds its trades, costs, stock and carrier
   transfers to this computer's records. The foot of the Session page says how many files it has read and when it last
   looked, for example "Journals read: 85 file(s). Last check 08:12 UTC, 1 new or grown."
3. It only ever **adds what is new**. Reading a file twice, or reading files out of order, never counts anything twice
   and never overwrites a newer carrier figure with an older one.

**Things that are not obvious:**

- **The file you are playing right now is left alone** (EDMC already delivers its events live). It is read on a later
  look, after the game has moved on to a new file or after EDMC restarts.
- **The first time, only the 80 newest files are read**; older history is not crawled. If your session began before
  that, use **Rebuild** (below).
- **A session that began on the other computer is not copied, only the journals are.** If this computer first met the
  commander partway through, its tally starts from there. Press **Rebuild** on the Session page and give the date and
  time (UTC) the session began: WNTB recounts the journals from then on and replaces the tally. Check the totals against
  the other computer, adjusting the start time until they match, then **Save session** if you want to keep it.
- **Reset and Save session only affect the computer you press them on.** Press Reset on both if you start
  a fresh session.
- **Carrier cargo only becomes exact when you open Carrier Management** (see
  [Your fleet carrier and squadron carrier](#your-fleet-carrier-and-squadron-carrier)). Copying journals does not change that.

### The Session page (works offline)

It reads your journal only; nothing is sent anywhere. Top to bottom:

- **Profit.** Trade profit is what you were paid minus what the sold tonnes cost you, as the game reports it; stolen or
  black-market cargo counts the whole sale. Credits per hour appears once you've traded for a few minutes (it uses first
  trade to last trade). With tonnes bought and sold and your best-selling commodities.
- **Running costs**, so the profit is honest: **fuel** (refuelling), **repairs**, **advanced maintenance** (the game logs it
  as a repair that includes module "Wear"; the whole charge goes on its own line), **rearm** (ammunition, and restocking
  an SRV or fighter) and **limpets** (bought, less any sold back). Once you've spent anything the headline becomes **Net
  profit** (trade profit less those costs; the credits per hour is the net), with the trade profit and each cost listed
  under it. Insurance rebuys and fines aren't counted, and a cost only counts once WNTB has seen it.
- **Ship hold**: your ship and the landing pad it needs (for example "Type-9 Heavy, large"), how many tonnes are used,
  the capacity and how much is free, what the station you're docked at would pay for the whole hold, and what each
  commodity aboard would sell for there.
- **Carrier cargo** (your carrier's cargo storage, shown as **Carrier cargo used**, **Carrier cargo free** and **Carrier
  reserved for orders**, so it is never mistaken for your ship hold), if you have one (see [Your fleet carrier and squadron carrier](#your-fleet-carrier-and-squadron-carrier)).

Buttons: **Reset** starts the tally again (if the session has trades you haven't saved, it asks whether to save it to
Trade History first), **Save session** and **History** are described next.
On a second row, **Rebuild** recounts the session from the journals starting at a time you give (UTC, as
`YYYY-MM-DD` or `YYYY-MM-DD HH:MM`) and replaces the tally; use it when the session began on another computer (see
[Using Trade on two computers](#using-trade-on-two-computers)). It asks first if the current tally is unsaved.

### Trade History (saving sessions)

When you want to keep a trading session, press **Save session**. It saves the session as it stands; you can keep trading
and press it again, which updates that same entry instead of adding a second one. **Reset** starts a new session, which
becomes a new entry if you save it. **Save session** is greyed out until there is something to save.

Press **History** to open the **Trade History** window, a pop-out like the BGS and Powerplay ones (dark look, remembers
its size and position, closes with **Esc**). A drop-down at the top picks a saved session, newest first; with more than
one commander there is also a commander filter. The tabs show everything about the session:

- **Overview**: net profit, trade profit, running costs, net per hour, tonnes sold and trading time at a glance, then
  the commander, ship, start and end, your balance at the start and when you saved, tonnes bought and sold, profit per
  tonne, margin, jumps and light years, profit per jump and per light year, and each running cost with its share of sales.
- **Commodities**: for each one, tonnes bought and sold, what you paid and received, average buy and sell price, profit,
  margin, profit per tonne and what was left unsold.
- **Stations**: the same added up for each station you traded at (visits, bought, sold, profit, costs, net).
- **Route**: the stations you traded at in the order you flew them, with what was bought and sold at each, the net on that
  visit and a running net. Going back to a station later is a new visit.
- **Trades**: every purchase, sale and cost with its time, price, total, profit, station and system, 200 at a time.
- **Stock & carrier**: what was bought but not sold (a journal estimate), the ship hold, and your carrier's cargo space when you saved.
- **Lookups**: the Spansh routes and market searches you made during the session, and the best result of each.

**Copy summary** puts a plain-text report on the clipboard, **Export log (CSV)** saves the full trade log to a file you
choose, and **Delete session** removes a saved session (it asks first).

Good to know: the balance change is your real credits difference, so it also includes anything else you earned; times are
UTC; and a session keeps its most recent 5,000 trades and costs (the totals are always exact). History is kept in
`trade_history.json` in the WNTB plugin folder, which updates leave alone.

### Routes (needs the Spansh lookups on)

**Find routes** asks Spansh for the most profitable trade route from where you are. It starts from the station you're
docked at, or the last one you docked at, and uses your cargo size and credits from the game and your ship's jump range.
That range is the *unladen* one, so lower it in Settings if a full hold jumps shorter. If your ship needs a large pad, only
stations with one are considered. Before you search, the page shows what it will use (start, ship, cargo, jump range,
budget).

Spansh's planner doesn't know fleet carriers, so a route never starts from one: if you're docked at your carrier it starts from the last real station you docked at (the page says where). If Spansh refuses a search, the page shows its reason.

The **Hops** button on the page cycles 2, 3, 4 or 5 hops (the same setting as in Settings). **2 hops** is the choice for a back-and-forth pair: when the route ends at the station it started from and every leg carries cargo, the result is headed "repeatable loop" and says you can fly it again; otherwise the page says why it isn't one. A leg with no cargo is flagged.

**Round trip** finds the best back-and-forth pair itself, because Spansh's planner returns the best *chain*, which doesn't always come back. One search asks Spansh for the markets of the nearest stations (up to 300, within twice your jump range, but never less than 20 ly or more than 100 ly), then works out for each neighbour what to carry out and what to bring back. A pair only counts when **both legs make a profit, so you never fly empty**. Each leg fills the hold with the most profitable commodity first and tops up with the next, limited by the supply where you buy, the demand where you sell and what you can afford. Pairs are ranked by estimated profit per hour and the top three are shown with what to carry each way. It uses the same filters as Find routes (price age, ground facilities, fleet carriers, your ship's pad size, distance from the star) plus the **least supply** and **least demand** settings (200 t each by default), so thin markets are left out. It takes about 20 seconds and makes one to three Spansh requests (100 stations each).

Spansh can take a minute or two; **Cancel** stops waiting. The result is the route's total profit, an **estimated profit per hour**, and each hop (stations,
system, distance, best commodity and profit, with the supply at the buying station and the demand at the selling one; the first four are shown, with "+N more" after). **Copy next system** puts the
first destination on your clipboard so you can paste it into the galaxy map.

### Market (needs the Spansh lookups on)

Finds where to **sell** or where to **buy** a commodity.

1. Choose what you want to do with the **Sell** / **Buy** buttons under the Commodity box (the lit one is chosen). It is
   remembered.
2. Click the **Commodity** box and start typing. Suggestions fill in as you type, starting with what you carry and what the
   station you're at buys, then every commodity. When selling, you can leave it empty to search for the commodity you carry
   the most of. When buying, type what you want.
3. Press **Near me** to look within a radius of your system (100 ly unless you change it in Settings), or **Galaxy** to look
   everywhere. You can press both.
4. **Selling:** results are ranked by what *your load* would earn, price per tonne times the tonnes the station still
   wants. A station paying more per tonne but wanting 40 t is worth less to a 200 t hold. If you haven't got any of it,
   a full hold is assumed.
   **Buying:** the amount is your *free hold space*. Stations that can supply all of it come first, cheapest first;
   stations that can only supply part come after, marked "only N t in stock".
5. Once you've run both searches it tells you which is better and by how much (more money when selling, a lower price when
   buying), and how much further away it is.
6. Every result says what kind of place it is: **orbital** or **ground** (on a planet's surface), the station type
   (Coriolis Starport, Planetary Outpost and so on), and how far it is from the arrival star in light seconds. Stations with
   no landing pad your ship fits are left out.
7. **Fleet carriers are listed in their own section**, marked "they can move", because a carrier can jump away before you
   arrive. They are asked for separately and weighted about one carrier to every three stations, so cheap carriers never
   crowd the real stations out of the list, and a line says when a carrier would beat the best station. In
   **Settings → WNTB → Trade** you can stop searching for fleet carriers, for **ground facilities** (planetary ports and
   outposts, and settlements), or both, which leaves only stations in space.

**Price finder** opens the finder Mining's **PRICE** button also uses, for any commodity, to buy or sell, with its own
distance box.

Prices are only as fresh as the last player who docked there (markets older than 30 days are ignored), so check the market
when you arrive.

### Your fleet carrier and squadron carrier

Not every commander has a carrier, and some have a fleet carrier, a squadron carrier or both. Under **Settings → WNTB →
Trade**, each commander WNTB has seen gets a choice: **Auto** (show whatever your journal has revealed), **None**,
**Fleet**, **Squadron** or **Both**. Nothing is shown for a carrier you haven't chosen. For each one the Session page shows
the carrier cargo used, free, and reserved for orders, for example "5,060 / 23,720 t used, 18,660 t free".

How it stays up to date:

- The game only reports a carrier's space when you **open Carrier Management**, so do that once. WNTB also reads your recent
  journal files when it starts, so it finds the last time you did, even if EDMC was restarted since.
- After that it follows your cargo transfers. A transfer is counted for the carrier you're docked at, so docking at
  someone else's carrier never changes your figure.
- Reserved space, and anything your carrier does itself (trade orders, sales), only update the next time you open Carrier
  Management.

**To get the real, up-to-date cargo figure, open Carrier Management** (the carrier's management screen, where you see its
services and cargo). The game writes a fresh report of the carrier's whole inventory at that moment and WNTB shows it within
a couple of seconds. Nothing else in the game's files lists what is in the carrier's hold; there is no other way to read it.

**Quirks worth knowing:**

- **A `~` before the figure (for example `~23,720 / 23,720 t`) means an estimate.** The transfers WNTB has seen add up to
  more than the carrier can hold (or take out more than it holds), so cargo left the carrier without the game writing
  anything down, usually a trade order or a sale made from the carrier. A note under the figure says so. Open Carrier
  Management and the `~` goes away.
- **Playing on another computer, or with EDMC closed, leaves the figure stale** until the journals are copied over and
  read, and even then it is only as good as the last time you opened Carrier Management.
- **The figure can look wrong right after you unload.** The unload is in the journal, but the total is not; open Carrier
  Management after a big load to put an exact number back.

### Trade settings

**Settings → WNTB → Trade**:

- *Enable Spansh trade lookups*: off until you tick it. The Routes and Market pages do nothing without it.
- *Route hops* (1 to 10, default 3), *Max distance from the star* in light seconds (default 5,000), *Jump range override*
  (blank uses your ship's unladen range) and *Only stations with a large landing pad*, for Routes.
- *Round trip: least supply / least demand* in tonnes (200 each), *Routes: ignore prices older than* a number of hours (default 72; 0 means any age), and *Routes may use systems that need a permit* (off).
- *"Near me" price search radius* in light years (default 100).
- *Include fleet carriers* and *Include ground facilities* in prices **and routes** (both on by default).
- *Ship size (landing pad)*: **From my ship** (the default), or Small, Medium or Large if it guesses wrong.
- The carrier choice for each commander (above).

See [What goes on the internet](#what-goes-on-the-internet) for exactly what is contacted, and
[docs/TRADE_TECH_SPEC.md](docs/TRADE_TECH_SPEC.md) for how it all works.

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
2. Click **SHIPS** (manage ship builds) in the WNTB panel.
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
3. Click **REPORT** (colonisation sites) for the full list. Each site is a group with its outstanding
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

**REPORT** (view BGS report) opens a window with a drop-down to pick the tick (the current one, or an earlier one
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
  a diagram on your game screen. Turn it on and choose where it appears in **Settings → Always On → Landing**.
  If the overlay is still starting when docking is approved, WNTB keeps retrying for up to three minutes, so the
  diagram appears as soon as the overlay is up.
- **Interdiction Warning** puts an alert on your game screen the moment an interdiction starts. It has
  no panel button, only Settings. Turn it on and try it with **Test Warning** in **Settings →
  Interdiction Warning**.

Both need an overlay helper program running (see [What you need](#what-you-need)). Its connection
settings are on the **Overlay Connection** Settings tab (Settings → General).

---

## Using WNTB on Linux

WNTB runs on Linux wherever EDMC does. It has been tested on a real install (KDE Plasma on Wayland, Elite
under Steam Proton, EDMC as a Flatpak): the Settings panel, the on-screen overlays (test overlay, Discovery
Alerts, Notable Bodies), Auto-Honk, the screenshot features and Trade all work. Please report anything odd.
Elite runs under Steam Proton or Wine on Linux, which needs a few extras. Work through the steps in order.

### Step 1: Install the helper tools

- **`xdotool`** presses keys in Elite's window for Auto-Honk and the screenshot auto-timer. Install it
  **on your system** (not inside anything): Debian/Ubuntu `sudo apt install xdotool`, Arch/CachyOS
  `sudo pacman -S xdotool`, Fedora `sudo dnf install xdotool`. It works on X11, and on Wayland through
  XWayland (which is where a Proton game's window lives), but not with a native Wayland window.
- **EDMCModernOverlay** draws the on-screen cards. Install it as an EDMC plugin from its
  [project page](https://github.com/SweetJonnySauce/EDMCModernOverlay). The original EDMCOverlay is
  Windows-only. WNTB's default connection settings (`127.0.0.1`, port 5010) already match it.
- Optional: `canberra-gtk-play` or `paplay` for notification sounds.

### Step 2: Tell EDMC where Elite's journals are

Set EDMC's own **Journal directory** (File → Settings → Configuration) to the
`Saved Games/Frontier Developments/Elite Dangerous` folder inside Elite's Proton folder, which is usually
`~/.local/share/Steam/steamapps/compatdata/359320/pfx/drive_c/users/steamuser/Saved Games/Frontier Developments/Elite Dangerous`.
Linux has no default for it, and without it WNTB's journal-based features (including BGS rebuilding the
tick's totals) have nothing to read. WNTB shows a hint under **Settings → Exploration → Alerts** and
**Settings → BGS** if it looks wrong, and logs one at startup. WNTB finds the Proton folder itself
(including extra Steam library folders and Flatpak Steam). Only if you use Lutris, Heroic or a custom
setup, enter the folder under **Settings → Exploration → Alerts → Elite Wine/Proton prefix**; otherwise
**leave that field empty**. A wrong value there stops WNTB from finding your keybindings, because it
deliberately does not fall back to auto-detection.

### Step 3: If EDMC is a Flatpak, grant it four permissions

A Flatpak runs in a sandbox that cannot see your Steam folders, your keyboard tools or your desktop. Without
these, WNTB looks fine in its settings but does nothing. Run each command once in a terminal, then
**restart EDMC**. They only widen what EDMC can reach; nothing else about the sandbox changes.

```bash
# Set this to your Elite Proton folder (the same one as Step 2, without the trailing parts).
PFX="$HOME/.local/share/Steam/steamapps/compatdata/359320/pfx/drive_c/users/steamuser"

# 1. Journals (EDMC reads the journal and Status.json, and keeps a lock file there)
flatpak override --user --filesystem="$PFX/Saved Games/Frontier Developments/Elite Dangerous" io.edcd.EDMarketConnector

# 2. Keybindings (read-only; Auto-Honk needs to know which key you bound)
flatpak override --user --filesystem="$PFX/AppData/Local/Frontier Developments/Elite Dangerous/Options/Bindings:ro" io.edcd.EDMarketConnector

# 3. Screenshots (read and write; WNTB converts and files them)
flatpak override --user --filesystem="$PFX/Pictures/Frontier Developments/Elite Dangerous" io.edcd.EDMarketConnector

# 4. Run host programs: lets the overlay window start, and lets WNTB use your system's xdotool
flatpak override --user --talk-name=org.freedesktop.Flatpak io.edcd.EDMarketConnector
```

Check them with `flatpak override --user --show io.edcd.EDMarketConnector`. If you use Flatpak Steam, your
Proton folder is under `~/.var/app/com.valvesoftware.Steam/.local/share/Steam/` instead. EDMC installed as
a Flatpak keeps its plugins in `~/.var/app/io.edcd.EDMarketConnector/data/EDMarketConnector/plugins`. If EDMC
is not a Flatpak (a native or AppImage install), skip this step.

Why permission 4 matters: EDMCModernOverlay starts its drawing window through the host, and WNTB runs
`xdotool` the same way. Without it, WNTB's **Check connection** still reports success (the overlay's port is
open) but nothing is drawn, and Auto-Honk says `xdotool` is not installed even though it is.

### Step 4: Bind a keyboard key for the honk (Auto-Honk only)

Auto-Honk can only press **keyboard** keys. If your fire buttons are bound only to a mouse button or a HOTAS
button, it reports "only bound to a joystick/HOTAS button". In Elite, open Options → Controls → Ship →
Cockpit Modes, and add a keyboard key to the **second** slot of **Secondary Fire** (keep your mouse or stick
binding in the first slot). Then in EDMC open **Settings → Exploration → Alerts**, press **Rescan**, and it
should say "Will press <your key>". Press **Test Honk Now** with the ship able to use its scanner. Set
the **hold time** to the seconds the scan needs (8 to 10 is typical); it is kept down for the full time.

### Step 5: Check the overlay

Start EDMC and Elite (borderless or windowed), open **Settings → WNTB → General → Overlay Connection**, and
press **Check connection**, then press a **Test** button, such as **Test Discovery** or **Test Notable** under
**Exploration → Alerts**. Cards should appear over the game. If they do not, see the Linux items in
[Troubleshooting](#troubleshooting) below.

### Step 6: Trade (nothing extra to install)

Trade mode needs nothing beyond Step 2, but it leans on it more than most features. EDMC's **Journal directory** is what
lets WNTB catch a trading session up after you played with EDMC closed, rebuild your carrier's cargo history and the
unsold stock list at start-up, and read the docked station's `Market.json`. If it is wrong or empty those quietly find
nothing, and the session only counts what EDMC delivered while it was running. For a Flatpak EDMC the journals permission in
Step 3 already covers it. The Spansh lookups just need the network. **Export log (CSV)** in Trade History uses a standard
file dialog; if EDMC is a Flatpak and the save fails, pick a folder EDMC is allowed to write to (WNTB shows the error).

A step-by-step checklist for testers is in [docs/LINUX_TESTING.md](docs/LINUX_TESTING.md). The platform
differences and the reasoning behind them are in
[docs/TECHNICAL.md section 18](docs/TECHNICAL.md#18-platform-support-windows-and-linux).

## Troubleshooting

**The WNTB panel doesn't appear.**
Check that the folder is named exactly `WNTB` and sits directly inside EDMC's plugins folder, with
files such as `load.py` right inside it (not another folder inside it). Then restart EDMC.

**A button or section is missing.**
Open **File → Settings → WNTB** and check the feature hasn't been switched off. The BGS and Codex
Completionist sections can each be hidden there. Also make sure you're in the right mode.

**On-screen alerts don't show up.**
They need EDMCOverlay or EDMCModernOverlay running, and WNTB's **Overlay Connection** settings must
match it. Use the **Test** buttons in each feature's Settings tab to check. On Linux with a Flatpak EDMC,
**Check connection** passes even when the overlay window never started; see Step 3 of
[Using WNTB on Linux](#using-wntb-on-linux) (the "run host programs" permission). You can confirm the window is
running with `ps -eo args | grep overlay_client`.

**Auto-Honk or the screenshot timer say `xdotool` is not installed (Linux).**
Install `xdotool` on your system (Step 1). If EDMC is a Flatpak, also grant the "run host programs"
permission (Step 3, command 4) and restart EDMC. The EDMC log then shows a "Host lookup of xdotool failed"
line with the reason if it still fails.

**Auto-Honk says no usable keybind found (Linux).**
Either your fire button has no keyboard key (Step 4), or WNTB can't read the bindings folder. For a Flatpak
EDMC grant Step 3, command 2. Also make sure **Elite Wine/Proton prefix** in **Settings → Exploration →
Alerts** is empty unless you really use a custom setup; a wrong value there hides your keybindings.

**Auto-Honk presses the key but the scan stops after about a second (Linux).**
Fixed in 1.3.1 (earlier builds released the key too early under XWayland). Update WNTB.

**Trade: the lookup buttons are greyed out, or there is no Commodity box.**
The Spansh lookups are off until you tick **Enable Spansh trade lookups** under **Settings → WNTB → Trade**. The Commodity
box only appears on the Market page, and only once lookups are on.

**Trade: I can't tell whether it's searching for a place to buy or to sell.**
The **Sell** and **Buy** buttons under the Commodity box choose the side; the lit one is active, and the results heading
says "Selling" or "Buying". Changing the side clears the old results.

**Trade: the Market search finds nothing for a commodity.**
Pick the name from the suggestion list. Spansh only knows commodities by their exact in-game name (for example "Void Opal",
not "Void Opals"), and an unknown name finds no markets. Also check that your ship's pad size is right under
**Settings → WNTB → Trade**: stations without a pad your ship fits are left out, and the result says how many were.

**Trade: the Session page seems to have lost some trades.**
A session lasts until you press **Reset**, across logins and EDMC restarts, and catches up from the journals when EDMC next
sees you. Check you didn't press **Reset** (it asks to save first if there was anything unsaved), and on Linux that EDMC's
**Journal directory** is set: without it the catch-up can't read the journals. Trades made before WNTB first ran aren't
counted.

**Trade: Save session is greyed out, or the History window is empty.**
**Save session** needs at least one trade or running cost in the session. The History window only lists sessions you saved,
so press **Save session** first.

**Trade History says I had cargo unsold that I'd already sold.**
The "Bought, not yet sold" estimate on the Stock & carrier tab only comes down when WNTB sees you sell. Cargo your carrier
sold on a trade order, or that you lost or jettisoned, stays in it. The Session page does not show this estimate; it shows
only your ship hold and the carrier's cargo figures.

**Trade: my carrier doesn't show, or its cargo looks wrong.**
Check your carrier choice for that commander under **Settings → WNTB → Trade** (Auto, Fleet, Squadron or Both, not None),
and open **Carrier Management** in the game once so the game reports its space. If the numbers still look wrong, open an
issue with the `CarrierStats` line from your journal (it is in the latest `Journal.*.log`).

**Notable Bodies never shows anything.**
It is switched off until you tick **Enable** under **Settings → Exploration → Alerts → Notable Bodies**.
Only some rules are on to start with, so tick the ones you want. A banner needs the overlay to be running.

**Numbers look wrong or out of date.**
Many features read the game's journal, so they only know what has happened since EDMC started, plus a
bit of recent history. Powerplay has a **RESCAN** button. Codex Completionist has **BKF** (backfill from
journal history). Trade catches its session up from the journals by itself; see
[How a trading session works](#how-a-trading-session-works).

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
- **[docs/MODULES.md](docs/MODULES.md)**: every module in `plugin/`, by feature, in one line each.
- **Feature specifications**, each covering what a feature reads, its rules and its limits:
  [Missions](docs/MISSIONS_TECH_SPEC.md), [Mining](docs/MINING_TECH_SPEC.md),
  [Trade](docs/TRADE_TECH_SPEC.md), [Boxel Survey](docs/BOXEL_SURVEY_TECH_SPEC.md), [BGS](docs/BGS_TECH_SPEC.md),
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
