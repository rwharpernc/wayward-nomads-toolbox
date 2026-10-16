# Getting started

This page takes you from nothing to a working WNTB panel, then shows you how to find your way around it.
No programming is needed. If something looks wrong, for example overlay text that looks doubled or is all in capitals, see [Known issues](known-issues.md).

**On this page:** [What you need](#what-you-need) · [Installing](#installing) ·
[Updating](#updating) · [A first five minutes](#a-first-five-minutes) · [Finding your way around](#finding-your-way-around) ·
[Commanders and your data](#commanders-and-your-data) · [If EDMC wasn't running](#if-edmc-wasnt-running) ·
[Opening the pop-out windows](#opening-the-pop-out-windows) · [Button names](#button-names)

## What you need

**1. EDMC.** WNTB is a plugin for [EDMC](https://github.com/EDCD/EDMarketConnector) (Elite Dangerous Market
Connector), a free companion program. EDMC reads the game's journal files while you play and hands the events to
plugins like WNTB. It runs on Windows and Linux. If you already use EDMC, you have it.

**2. An overlay (optional).** An *overlay* draws on top of your game screen.
WNTB only needs one for its on-screen extras: Discovery Alerts, Notable Bodies, Landing Assist, Interdiction
Warning, Flight Alerts, the Route, System targets, Body info, the Exobiology cards, the Expedition Log, the Surface Compass, and the optional overlays for Inventory, Mining, Missions, Colonization and
Screenshots. Everything else works without one. There are two to choose from:

- **WNTB's built-in overlay** (Windows only): nothing to install. Choose it under **Settings → Overlays → Overlay Connection → Which overlay draws**. It draws WNTB's displays only.
- **[EDMCModernOverlay](https://github.com/SweetJonnySauce/EDMCModernOverlay)** (Windows and Linux): a separate program you install. It is what Linux uses, and it is still what other
  plugins' overlays need; you can run it next to the built-in overlay.

Set Elite to **borderless** or **windowed** mode and the overlay will work. The step-by-step guide is
[Setting up the on-screen overlay](../OVERLAY_SETUP.md).

> **Every WNTB overlay is off until you tick it in Settings.** Inventory, Landing Assist and Screenshots used to
> start on. The release that added Trade switched them all off once, on first start, so if you used them before,
> tick the ones you want again.

## Installing

1. **Download the plugin.** Go to the
   [latest release](https://github.com/rwharpernc/wayward-nomads-toolbox/releases/latest) and download
   **`WNTB.zip`** from the **Assets** list. It holds only the plugin, in one folder called `WNTB`.

   > Don't use the green **Code → Download ZIP** button. That downloads the whole source repository, which you
   > don't need and which won't work as a plugin.

2. **Find EDMC's plugins folder.** In EDMC, open **File → Settings → Plugins** and click **Open** next to
   "Plugins folder". A file window opens. On Windows it is usually
   `%LOCALAPPDATA%\EDMarketConnector\plugins\`.

3. **Extract the ZIP into that folder.**
   - *Windows:* right-click `WNTB.zip` → **Extract All…**, and set the destination to the plugins folder itself.
   - *Linux:* `unzip WNTB.zip -d <your plugins folder>`

4. **Check the result.** You should now have `plugins/WNTB/load.py`. If you see `plugins/WNTB/WNTB/load.py`, you
   extracted one level too deep; move the inner folder up.

5. **Restart EDMC.** A **Wayward Nomads Toolbox (WNTB)** panel appears in the main window. It always shows
   (there is no title to fold it away).

If it doesn't, see [Troubleshooting](troubleshooting.md#the-wntb-panel-doesnt-appear). On Linux, also read
[WNTB on Linux](linux.md) before you go further, because EDMC needs a couple of settings there.

## Updating

Download the new `WNTB.zip` and extract it over the existing `WNTB` folder, replacing files when asked.

**Don't delete the old folder first.** Your saved data (mining hotspots, trade sessions, ship builds and so on)
lives inside it.

WNTB can also update itself. Turn on **Automatically download and install updates** under
**File → Settings → WNTB → General → Updates**. It is **off by default**, and it only looks at official published
releases. The **Release notes** link on that tab opens the latest release's page in your browser.

The first line under the mode buttons always says which version you are running (**Plugin: v1.17.0**). While an update is coming
it says **Plugin: v1.17.0 (downloading v1.17.1...)**, and once the update is downloaded it turns bold black on **orange** and reads
**v1.17.0 download - Restart EDMC**. The update only takes effect when EDMC starts again; nothing is swapped in while it runs.
After the restart the line shows **Plugin: v1.17.0 (updated)** in green for a short while. Clicking the line opens the release page.

*Building from source is for developers only. See [DEVELOPMENT.md](../DEVELOPMENT.md).*

## A first five minutes

You don't have to configure anything to get value out of WNTB, but this short tour helps:

1. Look at the row of buttons at the top of the WNTB panel. Those are the eight **modes**. Click one and the panel below
   changes. Hover over a button for a moment to see its full name.
2. Open **File → Settings → WNTB**. Each mode has its own tab. Look through the ones you care about and turn
   things on or off.
3. If you want on-screen alerts, set up an overlay (see above), then press a **Test** button in Settings to
   check it works.
4. **Linux only:** make sure EDMC's *Journal directory* is set. See [WNTB on Linux](linux.md).
5. Play. Most things fill themselves in as you go.
6. Skim the "What the game does and doesn't tell us" section at the end of each mode's guide. It lists what the
   game never records (for example, a fleet carrier's cargo is only exact after you open Carrier Management) and
   how to work around it.

**Why WNTB sometimes can't tell you something.** WNTB, like every third-party tool, only knows what the game writes to its journal
files, and not everything is logged. It fills some gaps from Frontier's servers (through a signed-in EDMC) and from data players and
communities report (Spansh, EDSM, Canonn, edastro, Raven Colonial), and works around the rest with labeled estimates and small steps
you take. See [How WNTB knows what it knows](README.md#how-wntb-knows-what-it-knows).

## Finding your way around

### The mode buttons

WNTB has one panel with eight modes. You switch between them with the button row under the title:
**P.P.** (Powerplay), **BGS**, **EXP** (Exploration), **MIN** (Mining), **TRD** (Trade), **MSN** (Missions),
**OPS** (Field Ops) and **COL** (Colonization).

**Every mode keeps working in the background** while you look at a different one. Nothing pauses. If you're
mining and flip to Trade to check a price, your mining stats keep counting.

### The lines under the mode buttons

Just under the mode buttons, above the page itself, WNTB shows these lines, on every mode:

- **Plugin**: the version you are running, for example `Plugin: v1.17.0` (see "Updating" for what it says during an update).
- **Game mode**: For example *You are in Solo mode.*, *Open*, or *Private Group* with its name.
- **Credits**: what you've earned or lost since you logged in, for example
  `+1,234,567 cr earned (+411,522 cr/hr)` or `-5,000 cr lost`. It is your balance now minus your balance at login.
  The hourly rate appears once the session is a few minutes old. **Click it** to open the Credits Ledger: income by
  activity (trade, exploration data, exobiology data, mission rewards, bounties and bonds), by day, and the game's lifetime totals.
- **Merits**: Powerplay merits earned since you logged in, for example `Merits this session: +1,234 (+567 merits/hr)`. It
  appears after your first merit of the session, so it stays out of the way if you do not play Powerplay. The rate is the
  merits divided by the time since you logged in, so it falls while you stop earning. The Powerplay mode's **CP** figures
  are Control Points, a separate number.
- **Overlays**: `Overlays shown (click to hide)`. Click it to hide every WNTB overlay at once and click again to bring them back (see [Overlay setup](../OVERLAY_SETUP.md#hiding-the-overlays-for-a-while); Windows also has a keyboard shortcut).

### Pages

Mining, Trade and Missions have more than one page. Click the large orange **◀** and **▶** buttons at the top of
the panel to move between them. For example, Trade has **Session**, **Routes** and **Market** pages.

### Collapsing the panel

The panel itself never folds away. Sections inside the modes (Exploration, Notes, Materials and so on) fold: they start folded, click a
section's title (▸ / ▾) to open it. They fold again each time EDMC starts.

### Window height

The EDMC window is small and every plugin shares it. So WNTB **resizes the window's height to fit** whenever you
open it, switch modes, or expand or collapse a section. You never need to drag it taller. It leaves your width and
position alone.

If you'd rather set the height yourself, untick *Resize the EDMC window's height to fit WNTB automatically* under
**File → Settings → WNTB → General → Window**.

## Commanders and your data

**Everything WNTB saves about your play belongs to one commander.** Nothing is shared between commanders, and switching
commander in EDMC switches what every feature shows: Trade sessions and route start, Powerplay and BGS ledgers,
Missions, Mining hotspots and the ground your Rhino has driven, the Boxel Survey position and finds, the Codex tally,
Colonization sites, Ship Builds, Organic Scanning and Powerplay history. Names are matched ignoring case, so
`BOCHEAUX` in the journal and `Bocheaux` in EDMC are the same commander.

The few things that are not about a commander are the same for everyone: your Settings, the downloaded Codex catalog
and the record of which journal files Trade has read.

**After updating from a version before this** (1.5.x or earlier), some data was one shared pile:

| Data | What happens |
|---|---|
| Mining hotspots and driven ground | Given to the **first commander who logs in** (it can't tell whose they were); every other commander starts empty. To give hotspots to another commander, use **I/E** in Mining. |
| Boxel Survey finds | Given to the first commander who logs in, the same way. |
| Codex tally | Not given to anyone: it mixed every commander's finds. Each commander's is **rebuilt from their own journals** the first time they log in. The old tally is removed after 60 days. |
| Powerplay history | Each session already named its commander, so nothing moves; the History tab now shows only yours. |

So log in first as the commander who owns your hotspots and survey finds.

### If EDMC wasn't running

If you start EDMC **before the game**, nothing tells WNTB who is playing until you log in. So a few seconds after start-up
it reads the last commander from your newest journal and every feature starts with their saved data; logging in as
someone else then switches everything to them. (The Game Mode and Credits lines still wait for a running game.)

EDMC only hands WNTB the events that happen while it runs. For anything played with EDMC closed, WNTB reads the game's
journal files when EDMC starts (and, for Trade, once a minute after that). Each feature does it its own way and only
adds what is new, so nothing is counted twice:

| Feature | What it catches up on | How far back |
|---|---|---|
| **Trade** | Session tally, stock, carrier figures, route start | New or grown journal files, every minute |
| **Powerplay** | Merits and Control Points | The gap since EDMC last saw the journal (up to the scan depth in Settings) |
| **BGS** | Your effect on factions this tick | From the start of the tick |
| **Missions** | Active missions, kill progress, cargo progress, Community Goals | The last 2 weeks |
| **Colonization** | Deliveries (also counted into your history) and sites docked at, and transfers to your fleet carrier (its FC column) | 14 days, or back to your oldest site (30 days at most); the delivery history is also rebuilt once from every journal |
| **Codex Completionist** | Codex finds, for the active commander | Everything since the last find it counted (a one-time rebuild from all their journals after updating) |
| **Boxel Survey** | Systems you arrived at, and the notable bodies and biological signals you scanned (systems new to the survey log; a system it already had keeps its scanned count) | The last 14 days |
| **Mining** | The run in progress | The current journal file |
| **Exploration Value** | Region, system scan progress, last data sales | The current journal file |
| **Inventory** | Backpack and ship locker | Taken from EDMC's own rebuilt state |
| **Credits line** | The session, if it is the same journal file | The saved session |

Landing Assist, Interdiction Warning, Discovery Alerts, Notable Bodies, Auto-Honk, Screenshots and the Organic Scanning
sample you are in the middle of only matter at the moment they happen, so there is nothing to catch up. See each
mode's guide for the limits.

### Settings

All settings live under **File → Settings → WNTB**, in tabs: General, Powerplay, Missions, Exploration, Mining,
Trade, BGS, Colonization, Field Ops and Overlays. Some have a row of tabs of their own:

| Tab | Inner tabs |
|---|---|
| **General** | Window (including *Suggest system names from Spansh while typing*), Updates, Help (**Report an issue**, **Copy diagnostics**) |
| **Exploration** | Exploration Value, Organic Scanning, Points of Interest (GEC, Canonn and Codex Completionist settings), Boxel Survey, Region Sweep, Waypoint Route, Auto-Honk |
| **Field Ops** | Screenshots, Inventory, Ship Builds |
| **Overlays** | Overlay Connection (which overlay draws, and EDMCModernOverlay's host and port), Overlay Placement, Appearance (color schemes, text size, opacity and the overlay font), Hide overlays, then one tab for each feature that draws on your screen: Colonization, Discovery, Inventory, Interdiction Warning, Flight Alerts, Route, Expedition Log, System targets, Body info, Exobiology, Missions, Landing, Surface Compass, Mining, Notable Bodies, Screenshots |

This is where you switch things on and off and adjust how they behave.

### Typing a system name

Every box that takes a system name (an expedition stop, the Expedition planner's start and end, the trader finder's *Search from*, Colonization's *Around*, a mining hotspot or ring reserve, a note, a waypoint or a Boxel Survey seed) suggests systems as you type, from the second letter: the systems you have been in this session first, then ones WNTB already holds (expedition stops, notes). **Down** and **Up** move through the list, **Enter** or a click takes the highlighted one, and **Escape** closes it; **Enter** with nothing highlighted does what the box always did (add the stop, run the search). To also get suggestions for systems you have never been to, tick **Suggest system names from Spansh while typing** under Settings → WNTB → General → Window. It is off until you tick it, and then the letters you have typed so far go to Spansh ([what goes on the internet](internet-and-privacy.md)).

### What you can and can't switch off

The eight mode buttons are always there: **a mode can't be hidden**, so if you never explore, Exploration simply sits
unused. Switches exist for individual features:

| | |
|---|---|
| **Have a switch** | Auto-Honk, Discovery Alerts, Notable Bodies, Organic Scanning, Codex Completionist, Exploration Value (and its two online extras), BGS (and its tick detection), Landing Assist, Interdiction Warning, Flight Alerts, the Surface Compass, the Trade and Mining online lookups, and every overlay |
| **Have no switch** | The core of Powerplay, Missions, Mining and Trade tracking, screenshot conversion, Inventory tracking, Materials and Engineering, the Expedition planner, Colonization, Ship Builds, Boxel Survey, and the GEC and Canonn POI finders. Some of these (Boxel Survey, the POI finders) only fold away and do nothing until you press a button |

Most online lookups are off until you switch them on, or only run when you press a button. The exceptions are listed
in [what goes on the internet](internet-and-privacy.md).

### Pop-out windows

Sessions, rare goods, inventory, the BGS report, the Mining Book and others open as their own windows. They have a
dark look, remember their size and position, and close with **Esc** or the ✕. The main panel itself follows your
EDMC theme.

## Opening the pop-out windows

Switch to the mode first, then use the button listed here.

| Window | Mode | How to open it |
|---|---|---|
| Powerplay Sessions (tabs: Current session, Systems, Cycles, Daily, Megaships, History) | Powerplay | **SES** button (bottom row of the panel) |
| Rare Goods Finder | Powerplay | **RARES** button, next to SES |
| BGS Report | BGS | **REPORT** button |
| Codex Completionist | Exploration | **DET** button in the Codex Completionist section |
| Notes | Exploration | **NOTES** button in the Notes section |
| Expedition | Exploration | **EXPEDITION** button in the Expedition section |
| Nearest place to land | Exploration | **FIND** button in the Nearest place to land section |
| Marks (for the Surface Compass) | Exploration | **MARKS** button in the Compass section |
| Watch list | Trade | **WATCH** button in the Watch list section |
| Missions window (tabs: Active, By place) | Missions | **Missions window** button at the very bottom of the panel, or click a mission's card |
| Source commodities | Missions | **Find sources** button at the very bottom of the panel (or **Sources** in the Missions window) |
| Inventory | Field Ops | Click one of the **inventory bars** (there is no button) |
| Materials | Field Ops | **MATERIALS** button in the Materials section |
| Engineering (blueprints, wishlist, ship and Odyssey upgrade planners, engineers) | Field Ops | **BLUEPRINTS** button in the Materials section |
| Material trader | Field Ops | **Find a trader** button in the Materials window |
| Ship Builds | Field Ops | **SHIPS** button |
| Colonization Sites | Colonization | **DASHBOARD** button |
| Mining Book | Mining | **BOOK** button, on both the Space Mining and Surface Mining pages |
| Trade History (tabs: Overview, Commodities, Stations, Route, Trades, Stock & carrier, Lookups) | Trade | **History** button on the Session page |

Notes:

- You don't need to be mining to open the Mining Book. It lists your saved hotspots either way.
- In Missions, the **Missions window** button is a table of every active mission with its progress, where to go and time left; you can pin
  missions there so they show on the overlay. Clicking a mission card opens the window on that mission.
- If you can't find the BGS or Codex Completionist sections, each can be switched off under
  **File → Settings → WNTB**. Both are on by default.

## Button names

The EDMC main window is small, so WNTB's buttons use short names. **Hover over any button for a moment and a tooltip
shows its full name.** Buttons inside pop-out windows and Settings keep their full names.

| Button | Full name | Where |
|---|---|---|
| **P.P.** | Powerplay | Mode buttons (top of the panel) |
| **BGS** | BGS | Mode buttons |
| **EXP** | Exploration | Mode buttons |
| **MIN** | Mining | Mode buttons |
| **TRD** | Trade | Mode buttons |
| **MSN** | Missions | Mode buttons |
| **OPS** | Field Ops | Mode buttons |
| **COL** | Colonization | Mode buttons |
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
| **ADD** | Save the line you typed as a note about the system you are in | Exploration (Notes section) |
| **NOTES** | Open the Notes window | Exploration (Notes section) |
| **EXPEDITION** | Open the Expedition window | Exploration (Expedition section) |
| **COPY** | Copy the next expedition stop's system name to the clipboard, to paste into the galaxy map | Exploration (Expedition section) |
| **FIND** | Open the Nearest place to land window | Exploration (Nearest place to land section) |
| **MARK** | Save where you are as a mark for the Surface Compass | Exploration (Compass section) |
| **TARGET** | Aim the compass at the next target: the nearest hotspot, each mark on this body, then none | Exploration (Compass section) |
| **MARKS** | Open the Marks window | Exploration (Compass section) |
| **BKF** | Backfill from journal history (Codex Completionist) | Exploration |
| **MATERIALS** | Open the Materials window | Field Ops (Materials section) |
| **BLUEPRINTS** | Open the Engineering window (blueprints, wishlist, ship and Odyssey upgrade planners, engineers) | Field Ops (Materials section) |
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
| **Best picks** | Closest, best local, cheapest or highest anywhere, and a price within 10% of the best, for the commodity in the box | Trade (Market page) |
| **Price finder** | The Mining PRICE finder, for any commodity | Trade (Market page) |
| **REFRESH** | Ask Spansh for the best buy and sell price of each watched commodity near you (needs Trade lookups on) | Trade (Watch list section) |
| **WATCH** | Open the Watch list window | Trade (Watch list section) |
| **◀** / **▶** | Previous / next page | Mining, Trade, Missions |
| **Missions window** | Open the window listing every active mission, with progress and pinning | Missions (bottom of every page) |
| **Find sources** | Where to buy the cargo your Collect and Mining missions need (needs Trade lookups on) | Missions (bottom of every page) |
| **SHIPS** | Manage ship builds | Field Ops |
| **DASHBOARD** | Colonization sites | Colonization |
| **OVERLAY** | Force the colonization shopping list onto the overlay (lit while on), press again to let go | Colonization |

---

Next: pick a mode from the [guide index](README.md), or see [what goes on the internet](internet-and-privacy.md).
