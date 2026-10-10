# Getting started

This page takes you from nothing to a working WNTB panel, then shows you how to find your way around it.
No programming is needed.

**On this page:** [What you need](#what-you-need) · [Installing](#installing) ·
[Updating](#updating) · [A first five minutes](#a-first-five-minutes) · [Finding your way around](#finding-your-way-around) ·
[Opening the pop-out windows](#opening-the-pop-out-windows) · [Button names](#button-names)

## What you need

**1. EDMC.** WNTB is a plugin for [EDMC](https://github.com/EDCD/EDMarketConnector) (Elite Dangerous Market
Connector), a free companion program. EDMC reads the game's journal files while you play and hands the events to
plugins like WNTB. It runs on Windows and Linux. If you already use EDMC for EDSM or Inara, you have it.

**2. An overlay (optional).** An *overlay* is a small helper program that draws on top of your game screen.
WNTB only needs one for its on-screen extras: Discovery Alerts, Notable Bodies, Landing Assist, Interdiction
Warning, and the optional overlays for Inventory, Mining and Screenshots. Everything else works without one.

- **[EDMCModernOverlay](https://github.com/SweetJonnySauce/EDMCModernOverlay)** is the recommended one. It works
  on Windows and Linux.
- The older [EDMCOverlay](https://github.com/inorton/EDMCOverlay) also works, on Windows only.

Set Elite to **borderless** or **windowed** mode and either overlay will work. The step-by-step guide is
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

5. **Restart EDMC.** A **Wayward Nomads Toolbox (WNTB)** panel appears in the main window. **On a fresh install
   it starts folded up**, showing only the title (`▸ Wayward Nomads Toolbox (WNTB)`). Click the title to open it.
   WNTB remembers whether you left it open or closed.

If it doesn't, see [Troubleshooting](troubleshooting.md#the-wntb-panel-doesnt-appear). On Linux, also read
[WNTB on Linux](linux.md) before you go further, because EDMC needs a couple of settings there.

## Updating

Download the new `WNTB.zip` and extract it over the existing `WNTB` folder, replacing files when asked.

**Don't delete the old folder first.** Your saved data (mining hotspots, trade sessions, ship builds and so on)
lives inside it.

WNTB can also update itself. Turn on **Automatically download and install updates** under
**File → Settings → WNTB → General → Updates**. It is **off by default**, and it only looks at official published
releases.

*Building from source is for developers only. See [DEVELOPMENT.md](../DEVELOPMENT.md).*

## A first five minutes

You don't have to configure anything to get value out of WNTB, but this short tour helps:

1. Click the WNTB title if the panel is folded up. Then look at the row of buttons under the "WNTB" title. Those are the seven **modes**. Click one and the panel below
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

## Finding your way around

### The mode buttons

WNTB has one panel with seven modes. You switch between them with the button row under the title:
**P.P.** (Powerplay), **BGS**, **EXP** (Exploration), **MIN** (Mining), **TRD** (Trade), **MSN** (Missions) and
**OPS** (Field Ops).

**Every mode keeps working in the background** while you look at a different one. Nothing pauses. If you're
mining and flip to Trade to check a price, your mining stats keep counting.

### Game mode and credits lines

Just under the mode buttons, above the page itself, WNTB shows two lines:

- **Game mode**: always shown. For example *You are in Solo mode.*, *Open*, or *Private Group* with its name.
- **Credits**: what you've earned or lost since you logged in, for example
  `+1,234,567 cr earned (+411,522 cr/hr)` or `-5,000 cr lost`. It is your balance now minus your balance at login.
  The hourly rate appears once the session is a few minutes old.

The credits line is shown on **Powerplay, BGS, Mining, Missions and Field Ops**. It is hidden on **Exploration**
(not useful there) and **Trade** (which has its own net profit that already counts your running costs). It keeps
counting while hidden.

### Pages

Mining, Trade and Missions have more than one page. Click the large orange **◀** and **▶** buttons at the top of
the panel to move between them. For example, Trade has **Session**, **Routes** and **Market** pages.

### Collapsing the panel

Click the WNTB title (it shows ▸ when folded and ▾ when open) to fold the whole panel away. Click it again to expand it. It starts folded on a fresh install. Sections inside Exploration also
fold (look for the ▸ / ▾ marks), and WNTB remembers which ones you left open.

### Window height

The EDMC window is small and every plugin shares it. So WNTB **resizes the window's height to fit** whenever you
open it, switch modes, or expand or collapse a section. You never need to drag it taller. It leaves your width and
position alone.

If you'd rather set the height yourself, untick *Resize the EDMC window's height to fit WNTB automatically* under
**File → Settings → WNTB → General → Window**.

### Settings

All settings live under **File → Settings → WNTB**, in tabs: General, Powerplay, Missions, Exploration, Mining,
Trade, BGS, Field Ops and Always On. Some have a row of tabs of their own:

| Tab | Inner tabs |
|---|---|
| **General** | Overlay Connection, Window, Updates |
| **Exploration** | Exploration Value, Organic Scanning, Points of Interest (GEC, Canonn and Codex Completionist settings), Boxel Survey, Region Sweep, Waypoint Route, Alerts (Auto-Honk, Discovery and Notable Bodies) |
| **Field Ops** | Screenshots, Inventory, Ship Builds, Colonisation |
| **Always On** | Interdiction Warning, Landing |

This is where you switch things on and off and adjust how they behave.

### What you can and can't switch off

The seven mode buttons are always there: **a mode can't be hidden**, so if you never explore, Exploration simply sits
unused. Switches exist for individual features:

| | |
|---|---|
| **Have a switch** | Auto-Honk, Discovery Alerts, Notable Bodies, Organic Scanning, Codex Completionist, Exploration Value (and its two online extras), BGS (and its tick detection), Landing Assist, Interdiction Warning, the Trade and Mining online lookups, and every overlay |
| **Have no switch** | The core of Powerplay, Missions, Mining and Trade tracking, screenshot conversion, Inventory tracking, Colonisation, Ship Builds, Boxel Survey, and the GEC and Canonn POI finders. Some of these (Boxel Survey, the POI finders) only fold away and do nothing until you press a button |

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
| Powerplay Sessions (tabs: Current session, Systems, Cycles, Daily, History) | Powerplay | **SES** button (bottom row of the panel) |
| Rare Goods Finder | Powerplay | **RARES** button, next to SES |
| BGS Report | BGS | **REPORT** button |
| Codex Completionist | Exploration | **DET** button in the Codex Completionist section |
| Inventory | Field Ops | Click one of the **inventory bars** (there is no button) |
| Ship Builds | Field Ops | **SHIPS** button |
| Colonisation | Field Ops | **REPORT** button |
| Mining Book | Mining | **BOOK** button, on both the Space Mining and Surface Mining pages |
| Trade History (tabs: Overview, Commodities, Stations, Route, Trades, Stock & carrier, Lookups) | Trade | **History** button on the Session page |

Notes:

- You don't need to be mining to open the Mining Book. It lists your saved hotspots either way.
- In Missions, click **All** for a table of every active mission, or click a mission card for that mission's
  details.
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

---

Next: pick a mode from the [guide index](README.md), or see [what goes on the internet](internet-and-privacy.md).
