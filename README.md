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

> **Download the latest release, not the repository.** See [Quick start](#quick-start). If you hit a
> problem, see [Getting help](#getting-help).

Built and maintained by R.W. Harper: CMDR Bocheaux (Wayward Nomads, WWNS).

---

## Contents

- [How WNTB knows what it knows](#how-wntb-knows-what-it-knows)
- [What's in the toolbox](#whats-in-the-toolbox)
- [Full feature list](#full-feature-list)
- [Planned and being researched](#planned-and-being-researched)
- [Quick start](#quick-start)
- [Tips, quirks and workarounds](#tips-quirks-and-workarounds)
- [Guides](#guides)
- [Getting help](#getting-help)
- [For developers, credits and license](#for-developers-credits-and-license)

---

## How WNTB knows what it knows

Like every third-party tool for Elite Dangerous, WNTB only knows what the game writes to its journal files. Much of what makes play easier starts there, and not everything is logged. Where the journal is silent, WNTB adds what it can from other places: figures Frontier's own servers give a signed-in EDMC (such as a fleet carrier's cargo), and data that players and community services report (Spansh, EDSM, Canonn, edastro, Raven Colonial and others). Where none of that exists, WNTB works around the gap with an estimate that it marks as one, or with a step you take (such as opening Carrier Management so the game reports the figure). Until Frontier expands the journal or offers a broader API, these workarounds are part of how WNTB works, and every guide lists the gaps it knows of.

In practice, three layers:

1. **The journal.** The files Elite Dangerous writes as you play. Everything WNTB shows about *you* starts here: your trades, scans,
   missions, deliveries, merits and so on. If the game doesn't write it down, WNTB can't see it.
2. **Other places that know more.** Frontier's servers (through a signed-in EDMC), and the data players and communities share:
   [Spansh](https://spansh.co.uk), [EDSM](https://www.edsm.net), Canonn, edastro, [Raven Colonial](https://ravencolonial.com).
   These are used to fill in what the journal lacks, never to replace it, and each one is listed on the
   [internet page](docs/guide/internet-and-privacy.md).
3. **Workarounds, marked as such.** WNTB's own bookkeeping (for example, tallying what you transfer to a fleet carrier), estimates
   that are labeled as estimates, and steps you can take (such as opening Carrier Management) to make the game write what the
   journal normally leaves out.

Each guide ends with a table of what the game does and doesn't tell us, and how to work around it. If a number looks wrong, that
table is the first place to look.

## What's in the toolbox

WNTB has one panel with eight **modes**. You click a button to switch between them.

| Mode | What it's for | Guide |
|---|---|---|
| **Powerplay** | Tracks the merits and Control Points you earn for your Power, and finds rare goods. | [Powerplay](docs/guide/powerplay.md) |
| **Exploration** | Auto-honk, "first discovery" and notable-body alerts, a boxel survey tool, scan values and how far through a system you are, what your data sales actually paid, exobiology help, a lifetime tally of everything you've scanned, notes on systems and bodies, an expedition planner (named trips of stops, ticked off as you arrive), and a compass that points at a spot on the planet you are on. | [Exploration](docs/guide/exploration.md) |
| **Mining** | Tracks space mining and surface (SRV) mining, and keeps your own catalog of mining hotspots. | [Mining](docs/guide/mining.md) |
| **Trade** | Your trading profit after fuel and repairs, what fills your ship hold (cargo, mission, stolen, limpets), your fleet carrier's cargo space, tritium, location and orders, saved sessions in a Trade History window, Spansh lookups for the best trade routes and the best place to buy or sell, and a watch list of the commodities you care about with the best buy and sell price. | [Trade](docs/guide/trade.md) |
| **Missions** | One view of every mission you have, with kill-progress bars for massacre missions and collect / delivery progress for cargo missions, a Missions window to see them all and pin some to the overlay, and where to buy the cargo they need. | [Missions](docs/guide/missions.md) |
| **Field Ops** | Screenshots, your backpack/locker/cargo, the engineering materials you hold, a blueprint browser with a wishlist and shopping list, a finder for the closest material traders, and saved ship builds. | [Field Ops](docs/guide/field-ops.md) |
| **Colonization** | The project you are building now, your colonization history, and a window with every site's shopping list, where to buy, and optional links and sharing with Raven Colonial. | [Colonization](docs/guide/colonization.md) |
| **BGS** | Tracks the Background Simulation: faction states, and what your own activity does to them. | [BGS](docs/guide/bgs.md) |

Four more tools are always on and don't belong to a mode: **Landing Assist**, **Interdiction Warning**, **Flight Alerts**
(a fleet carrier jump countdown and fuel warnings) and the **Route overlay** (travel status and the plotted route) ([guide](docs/guide/always-on.md)).

Most individual features have their own on/off switch in Settings, and the alerts and overlays are off until you turn
them on. The eight mode buttons themselves can't be hidden, and a few sections (for example Boxel Survey and the GEC
and Canonn POI finders) can only be folded away, not switched off.

**Each commander's data is separate.** Hotspots, surveys, sessions, Codex tallies and everything else WNTB saves belong
to the commander you are playing; nothing is shared between commanders.

**Playing with EDMC closed is fine.** When EDMC starts, WNTB reads the recent journal files and catches up on what it
missed (trades, missions, colonization deliveries, Codex finds, merits and more), counting nothing twice. Getting
started has a table of what each feature catches up on and how far back.

**Full disclosure.** WNTB works from the game's journal files plus the other sources described in
[How WNTB knows what it knows](#how-wntb-knows-what-it-knows), and some things the game never records, or records late or in part
(for example, a fleet carrier's cargo is only exact after you open Carrier Management). Each mode guide ends with a section, "What
the game does and doesn't tell us, and how to work around it", listing every gap we know of and what to do about it. Estimates are
marked as estimates on screen.

> **Colonization is a work in progress.** The COL page, the Colonization Sites window and the overlay shopping list work
> today, but more is planned: **co-op building** (several commanders working on one project) and **colony tracking**, which
> will come through a separate app that is in development. WNTB will connect to it when it is ready. Until then everything
> on the COL page is about **you**: your deliveries, your ship and your carrier. Expect rough edges and changes.

> **Linux has had a test pass.** The 1.10.0 build was tested on Linux and 1.10.1 fixed a panel-width problem found in that pass. 1.10.2, 1.11.0, 1.12.0, 1.13.0, 1.14.0, 1.14.1 and 1.15.0 have been
> tried on Windows only. The newest parts (the Missions window, the Missions overlay and Source commodities, Best picks, the Upgrade planner, Megaships, the Engineering window's Ship planner and Engineers tab, the Materials and Engineering work, the material trader finder, the
> Expedition planner and the Help buttons) have had less time in the game than the rest, so expect a few small fixes in a later update. If something looks off,
> please [report it](#getting-help) (Settings has a **Report an issue** button that does most of the work).

## Full feature list

Every feature, by mode, with a link to its step-by-step section in the user guide. See [Planned and being researched](#planned-and-being-researched) for what is not built.

### Across the whole toolbox

- **Eight modes in one small panel**, switched with the buttons under the title ([Getting started](docs/guide/getting-started.md)).
- **Game mode, credits and merits lines** under the mode buttons (credits and merits this session, with a per-hour rate), and the version you are running ([Getting started](docs/guide/getting-started.md)).
- **Everything is per commander**: nothing WNTB saves about play is shared between commanders ([Getting started](docs/guide/getting-started.md)).
- **Catches up after EDMC was closed**: it reads the recent journals when EDMC starts, counting nothing twice ([Getting started](docs/guide/getting-started.md)).
- **System-name suggestions** in every box that takes a system name: the systems you have been in, then ones WNTB holds, and, if you tick it, Spansh's search for any system ([Typing a system name](docs/guide/getting-started.md#typing-a-system-name)).
- **Pop-out windows** with a dark look that remember their size and place ([Getting started](docs/guide/getting-started.md#opening-the-pop-out-windows)).
- **Automatic updates** from GitHub releases, and a **Release notes** link ([Getting started](docs/guide/getting-started.md)).
- **On-screen overlay displays** through EDMCModernOverlay, with a Placement tool, six color schemes and a text size ([Overlay setup](docs/OVERLAY_SETUP.md)).
- **Windows and Linux** (native or Flatpak EDMC, Elite under Proton or Wine) ([Windows and Linux](docs/guide/platforms.md), [WNTB on Linux](docs/guide/linux.md)).
- **Every online lookup is listed**, and each is either opt-in or runs only when you press a button ([What goes on the internet](docs/guide/internet-and-privacy.md)).

### Powerplay ([guide](docs/guide/powerplay.md))

- **Live merits and Control Points** for your pledged Power: this system, this session and the whole Powerplay cycle ([Using it](docs/guide/powerplay.md#using-it)).
- **Sessions window** (SES) with tabs for the current session, systems, cycles, days, megaships and history ([The Sessions window](docs/guide/powerplay.md#the-sessions-window)).
- **Catch-up from your journals**, so playing without EDMC running does not lose a cycle, and **RESCAN** to rebuild ([Catching up](docs/guide/powerplay.md#catching-up-from-your-journals)).
- **Megaships**: the megaships whose datalink you scanned this cycle, with a count and where ([Megaships](docs/guide/powerplay.md#megaships)).
- **Rare Goods Finder** (RARES): the rare commodities closest to you, with pad size and which Power controls the system ([Rare Goods Finder](docs/guide/powerplay.md#rare-goods-finder)).

### Exploration ([guide](docs/guide/exploration.md))

- **Auto-Honk**: fires your Discovery Scanner on every jump ([Auto-Honk](docs/guide/exploration.md#auto-honk)).
- **Discovery Alerts**: a banner for an unscanned system or a first scan or map, plus the **N.S.** and **W.D.** buttons for the nearest neutron star and white dwarf ([Discovery Alerts](docs/guide/exploration.md#discovery-alerts)).
- **Notable Bodies**: a banner when a body you scan is worth a second look ([Notable Bodies](docs/guide/exploration.md#notable-bodies)).
- **Boxel Survey**: Sequence, Region Sweep and Waypoints for exploring by procedural system name, and **RND** to find an undiscovered system ([Boxel Survey](docs/guide/exploration.md#boxel-survey)).
- **Exploration Value**: the estimated payout for the last body, system scan progress, the system's age and region, and what your data sales paid ([Exploration Value](docs/guide/exploration.md#exploration-value)).
- **Organic Scanning**: help finding and identifying exobiology on a planet's surface ([Organic Scanning](docs/guide/exploration.md#organic-scanning)).
- **Codex Completionist**: a lifetime tally of your Codex finds, with a details window and a backfill from journal history ([Codex Completionist](docs/guide/exploration.md#codex-completionist)).
- **GEC Nearby POI** and **Canonn Nearby POI**: the nearest point of interest from edastro's catalog or Canonn's Thargoid and Guardian site lists, only when you press FIND ([GEC](docs/guide/exploration.md#gec-nearby-poi), [Canonn](docs/guide/exploration.md#canonn-nearby-poi)).
- **Notes**: your own notes on a system or a body, shown when you arrive, with a searchable window ([Notes](docs/guide/exploration.md#notes)).
- **Expedition planner**: named trips of stops with notes, ticked off as you arrive, with jumps, light-years and time so far, the next stop's distance, COPY for the galaxy map, import from your plotted route or a CSV, and optional nearest-neighbor ordering through EDSM, and one-button expeditions from Spansh's **Road to Riches** and **Exomastery** planners ([Expedition](docs/guide/exploration.md#expedition)).
- **Compass** and **Marks**: an arrow, a name and a distance on your game screen pointing at the nearest recorded hotspot or a mark you saved on the planet you are on ([Compass](docs/guide/exploration.md#compass)).

### Mining ([guide](docs/guide/mining.md))

- **Space Mining** and **Surface Mining** pages with live stats for your run: asteroids prospected and cracked, limpets, what you refined and the refining rate, the Rhino's cargo, and a minimap of the ground it has driven over ([What each page shows](docs/guide/mining.md#what-each-page-shows)).
- **Mining Book**: your own catalog of hotspots, with tons mined and an estimate of what is left ([The Mining Book](docs/guide/mining.md#the-mining-book)).
- **+H.S.** to save a hotspot, and **I/E** to import or export them ([The buttons](docs/guide/mining.md#the-buttons)).
- **Mining stats on the overlay**, optional, and an optional JSON archive of each completed run ([Settings](docs/guide/mining.md#settings)).
- **Opt-in online lookups**: nearby hotspots and the best price (Spansh), and ring reserve level (EDSM) ([The buttons](docs/guide/mining.md#the-buttons)).

### Trade ([guide](docs/guide/trade.md))

- **Session profit** after fuel, repairs and other running costs, with credits per hour, your ship's hold, your fleet carrier's space, what was bought but not yet sold (an estimate) and the game's own lifetime trading totals ([The Session page](docs/guide/trade.md#the-session-page)).
- **Trade History** window for saved sessions, with a CSV export ([Trade History](docs/guide/trade.md#trade-history-saving-sessions)).
- **Routes**: the best trade routes from where you are, and a round trip, from Spansh ([Routes](docs/guide/trade.md#routes)).
- **Market**: where to sell or buy a commodity ([Market](docs/guide/trade.md#market)), and **Best picks**: the closest, best local, cheapest anywhere and recommended (within 10% of the cheapest) station ([Best picks](docs/guide/trade.md#best-picks)).
- **Watch list**: the commodities you care about, with the best buy and sell price for each, where, how much stock or demand, and how old ([Watch list](docs/guide/trade.md#watch-list)).
- **Fleet and squadron carrier cargo** and tritium, kept up to date from the journal ([Your fleet carrier](docs/guide/trade.md#your-fleet-carrier-and-squadron-carrier)).
- **Two computers**: how Trade records behave when you play on Windows and Linux ([Using Trade on two computers](docs/guide/trade.md#using-trade-on-two-computers)).

### Missions ([guide](docs/guide/missions.md))

- **Every mission on one view**, in pages by type, with grouped kill-progress bars for massacre and settlement-raid missions and one card per mission otherwise ([Using it](docs/guide/missions.md#using-it)).
- **Missions window** (button at the bottom of the panel): every mission with progress (including cargo held for source-and-return missions) shown as a bar and in color, reward and time left, grouped by where to hand it in, with a detail strip and **pinned missions** that stay at the top of the overlay card ([The Missions window](docs/guide/missions.md#the-missions-window)).
- **Missions overlay card**: the missions for the system you are in and the one you are jumping to first, ready ones in green and the rest colored by time left and progress, in a corner of the screen ([Missions on the overlay](docs/guide/missions.md#missions-on-the-overlay)).
- **Source commodities**: where to buy the cargo your Collect and Mining missions need, with the closest, best local, cheapest and a recommended station ([Source commodities](docs/guide/missions.md#source-commodities)).
- **Community Goals** and what they paid you.

### Field Ops ([guide](docs/guide/field-ops.md))

- **Screenshots**: automatic PNG conversion with an optional crop to the HUD panel ([Screenshots](docs/guide/field-ops.md#screenshots)).
- **Inventory**: your backpack, ship locker and cargo as bars, and the Carrier Locker, with a pick-up sound ([Inventory](docs/guide/field-ops.md#inventory)).
- **Materials**: how many Raw, Manufactured and Encoded engineering materials you hold, each one's grade and limit, the last change, and what is at the limit, with a searchable window ([Materials](docs/guide/field-ops.md#materials)).
- **Engineering**: about 1,180 blueprints with their ingredients against what you hold and where each is found, a wishlist with a combined shopping list, a ship planner that turns an EDSY or Coriolis build into wishlist entries, an upgrade planner for Odyssey suits and weapons, and an Engineers tab with where each engineer is, where you stand and what unlocking each takes ([Engineering](docs/guide/field-ops.md#engineering-blueprints-and-a-wishlist)).
- **Material trader finder**: the closest Raw, Manufactured or Encoded trader to a system, with distance and pad filters, from Spansh ([Find a trader](docs/guide/field-ops.md#materials)).
- **Ship Builds**: a list of builds from Coriolis, EDSY or Spansh, kept by link ([Ship Builds](docs/guide/field-ops.md#ship-builds)).

### Colonization ([guide](docs/guide/colonization.md))

- **The COL page**: your current project and your history ([The COL page](docs/guide/colonization.md#the-col-page)).
- **Site tracking**: what each construction site still needs, after counting the cargo in your ship, readable from anywhere ([Tracking a site](docs/guide/colonization.md#tracking-a-site)).
- **Colonization Sites window** (DASHBOARD): every site's shopping list, progress and totals, the carrier's contribution, and Rescan Carrier ([The Sites window](docs/guide/colonization.md#the-colonization-sites-window)).
- **Where to buy**: the closest places to buy a commodity, and **Find all** for a whole list ([Where to buy](docs/guide/colonization.md#where-to-buy)).
- **Planned Builds and Raven Colonial**: links, opt-in sharing of your progress and deliveries, and reporting a finished build ([Planned builds](docs/guide/colonization.md#planned-builds)).
- **Shopping list on the overlay**: shown at the market, at your carrier or at a construction site ([The overlay](docs/guide/colonization.md#the-shopping-list-on-the-overlay)).

### BGS ([guide](docs/guide/bgs.md))

- **Faction states** for the system you are in, and what your missions, bounties, trade, exploration and crimes do to them ([The panel](docs/guide/bgs.md#the-panel), [What it counts](docs/guide/bgs.md#what-it-counts)).
- **BGS Report** window with a tab per system, resetting at each tick ([The BGS Report window](docs/guide/bgs.md#the-bgs-report-window)).
- **Tick detection** from a community service, optional ([Tick detection](docs/guide/bgs.md#tick-detection-and-the-internet)).

### Always on, in any mode ([guide](docs/guide/always-on.md))

- **Landing Assist**: your assigned landing pad, in the panel and/or as a diagram on your game screen ([Landing Assist](docs/guide/always-on.md#landing-assist)).
- **Interdiction Warning**: an alert on your game screen the moment an interdiction starts ([Interdiction Warning](docs/guide/always-on.md#interdiction-warning)).
- **Flight Alerts**: a fleet carrier jump countdown and fuel warnings, including when the star you plotted to cannot be scooped ([Flight Alerts](docs/guide/always-on.md#flight-alerts)).
- **System targets and Body info**: two overlay cards for working a system: a list of scanned bodies worth mapping (above a value you choose) and bodies with life you have not analysed yet, until you do; and a card describing the body you have targeted or are close to ([System targets and Body info](docs/guide/exploration.md#system-targets-and-body-info)).
- **Route overlay**: your fuel and jump range, the jumps left, and the systems of the route you plotted, with neutron stars and white dwarfs picked out so you can prepare for the supercharge ([Route overlay](docs/guide/always-on.md#route-overlay)).

## Planned and being researched

Things I would like to add or am still looking into, by feature. This is a wish list, not a promise: there are no dates, the order
can change, and some of it may turn out not to be possible. If one of these matters to you, tell me (see [Getting help](#getting-help)).

**Colonization**
- **Raven Colonial:** sharing your progress, deliveries and carrier cargo is built, strictly **opt-in and off by default**, and the
  internet page lists exactly what is sent and when. **Raven Progress** reads Raven's own figures for a site when you press it. Not
  done: creating or linking a Raven project from WNTB, and reading Raven's progress automatically instead of on a button press.
- **Team projects:** several commanders on one project, with a "what the team still needs" line. Everything today is per commander and
  would stay that way until you choose to share.
- **Co-op building and colony tracking** through a separate app that is in development; WNTB is to connect to it when it is ready.
- *Being researched, may not happen:* tonnes per hour and credits earned per delivery. The journal does not say how long you spent
  hauling, and I have not been able to confirm that the credits a depot lists are what is actually paid.

**Landing Assist**
- **My own pad layouts,** with fore and aft cues and diagrams for facilities that have none today, settlements first. I need to
  confirm the pad numbering of settlements in the game before drawing any, so nothing misleading ships.

**Trade**
- **Round trip:** a Powerplay bonus filter (that depends on what the price service can tell me).

**Overlays**
- **A better fit for small screens.** The default spots no longer overlap on a 1920 x 1080 screen or larger. The displays are sized in
  pixels, so on a smaller screen some can overlap until you move them on Overlay Placement.

**Everywhere**
- **More checking in the game on both Windows and Linux.** Several newer parts have had a first pass only, and each guide ends with
  a list of what the game does not tell us.

## Quick start

**You need:** [EDMC](https://github.com/EDCD/EDMarketConnector) on Windows or Linux. For on-screen alerts you also
need an overlay ([EDMCModernOverlay](https://github.com/SweetJonnySauce/EDMCModernOverlay) is recommended), but
everything else works without one.

1. Download **`WNTB.zip`** from the [latest release](https://github.com/rwharpernc/wayward-nomads-toolbox/releases/latest)
   (under **Assets**). Don't use the green **Code → Download ZIP** button.
2. In EDMC open **File → Settings → Plugins → Open** (the plugins folder) and extract the ZIP there, so you end up
   with `plugins/WNTB/load.py`.
3. Restart EDMC. The **Wayward Nomads Toolbox (WNTB)** panel appears.
4. Click the mode buttons under the WNTB title to switch modes. Hover over any button to see its full name. Settings
   are under **File → Settings → WNTB**.

On **Linux**, one more step is needed so WNTB can read your game's journals. See [WNTB on Linux](docs/guide/linux.md).

To update, extract the new ZIP over the old `WNTB` folder (don't delete it first: your saved data lives there), or turn on
**Automatically download and install updates** under **File → Settings → WNTB → General → Updates** (off by default).

## Tips, quirks and workarounds

Things that surprise people, and what to do about them. Every mode guide has a longer list at its end.

**Installing and updating**
- **Restart EDMC** after installing or updating. The WNTB panel only appears after a restart.
- Extract the ZIP **over** the old `WNTB` folder, don't delete it first: your saved data lives there.
- Use the ZIP from the **Releases** page (Assets), not the green **Code → Download ZIP** button.
- The WNTB panel is a little wider since 1.6.0 (there are eight mode buttons). EDMC sizes its window to the widest
  plugin, so you may see the main window grow slightly.

**EDMC, the journal and catching up**
- **Run EDMC** while you play. If you forget, WNTB catches up from your recent journals when EDMC starts (up to about 14 to 30
  days for most features), counting nothing twice. It cannot catch up on things the game never writes down.
- WNTB, like every third-party tool, only knows what the game writes to its journal, plus what it can add from Frontier's servers and
  community services. Where it can't be sure, it says so. Each guide lists these gaps and
  the workaround in "What the game does and doesn't tell us".
- Everything is kept **per commander**. Switching commanders in EDMC switches the data.
- **Linux:** EDMC's **Journal directory** must point at Elite's journal folder inside the Proton/Wine folder, or most
  features will find nothing. Auto-Honk and the screenshot timer also need `xdotool`, and a Flatpak EDMC needs permissions
  granted. See [WNTB on Linux](docs/guide/linux.md).

**On-screen overlays**
- Overlays need an overlay program running ([EDMCModernOverlay](https://github.com/SweetJonnySauce/EDMCModernOverlay) is
  recommended). Press a **Test** button to check. Everything is **off until you turn it on**.
- All overlay settings are in one place: **Settings → WNTB → Overlays** (Connection, Placement, Appearance, and a tab per feature).
- **Placement** puts each display at one of nine spots plus pixel offsets, read from your real screen. If it looks wrong,
  press **Show placement preview**, then **Detect screen again**, or **Reset all to defaults**. The overlay can't draw
  flush against the right edge by itself; WNTB works around that with an offset (a switch on the Placement tab turns it off).
- **Appearance** sets the color scheme for every overlay; the text size (Default or Larger) is yours to choose, and the spacing is fixed so columns stay aligned. The Interdiction warning always stays red.
- Run Elite in borderless or windowed mode; some overlays can't draw over exclusive fullscreen (see the [overlay setup](docs/OVERLAY_SETUP.md)).

**Colonization (work in progress)**
- Dock at a construction depot (or open its market) **once** to register a site. Nothing is typed in.
- The COL page and window show **your** deliveries and cargo. The depot's totals include everyone's deliveries.
- Your **history is rebuilt once from all your journal files** and counts from the first delivery in them (the page says the date). Deleted journals can't be counted.
- **Fleet carrier cargo:** the journal only records cargo you *transfer* to the carrier. For the real hold, sign EDMC in to
  Frontier and open **Carrier Management** once; WNTB then reads the carrier's actual cargo. It can lag behind the game. If a transfer
  never registered, **Rescan Carrier** (in the Colonization Sites window) rebuilds the tally from your last 30 days of journals.
- Commanders **without** a carrier see simpler wording and one Trips column; the carrier lines appear only if you have one.
- **Where to buy** needs the internet (Spansh) and caches a search for two minutes. Click a result row to copy its system, ready to
  paste into the galaxy map search.
- **Raven Colonial** (ravencolonial.com) is optional. Planned Builds, Raven Progress and the page links only read or open your browser;
  sending anything to Raven is **off until you tick the master switch** in Settings and save your Raven key (the settings page links to
  where you get it). **Test key** checks the key.
- Shopping-list overlay: switch it on and off with the **OVERLAY** button (it stays as you leave it). Tick the automatic option in
  Settings if you want it to appear by itself at a market, in Carrier Management or at a construction site.

**Windows**
- If screenshots don't save, Windows **Controlled Folder Access** or your antivirus may be blocking EDMC. Allow it, or choose
  another folder.

## Guides

**Set up and learn the basics**

- [Getting started](docs/guide/getting-started.md): installing, updating, finding your way around, every pop-out
  window, every button name.
- [Setting up the on-screen overlay](docs/OVERLAY_SETUP.md)
- [Windows and Linux](docs/guide/platforms.md): what works where.
- [WNTB on Linux](docs/guide/linux.md): step-by-step, including Flatpak EDMC.
- [What goes on the internet](docs/guide/internet-and-privacy.md): every feature that contacts an outside site.

**Use the modes**: see the table above, or the [full guide index](docs/guide/README.md).

**When something's wrong**: [Troubleshooting](docs/guide/troubleshooting.md).

## Getting help

Found a bug? **File → Settings → WNTB → General → Help → Report an issue** opens a bug report in your browser with your versions and
operating system already filled in; **Copy diagnostics** (same tab) puts the matching log lines on your clipboard to paste into it. Step by step: [Reporting a problem](docs/guide/reporting-problems.md). Or, for a bug or an idea, open an issue on the project's
[Issues page](https://github.com/rwharpernc/wayward-nomads-toolbox/issues), or find me in the Wayward Nomads
squadron. Say what you were doing, what you expected, and what happened. Including EDMC's log (EDMC's Help menu can
open its log folder) helps a lot. The squadron website is [waywardnomads.org](https://waywardnomads.org/).

## For developers, credits and license

- **[docs/DEVELOPMENT.md](docs/DEVELOPMENT.md)**: setting up to build, test and change WNTB.
- **[docs/TECHNICAL.md](docs/TECHNICAL.md)**: how WNTB works and why it's built that way.
- **[docs/MODULES.md](docs/MODULES.md)**: every module in `plugin/`, by feature, in one line each.
- **Feature specifications**, each covering what a feature reads, its rules and its limits:
  [Missions](docs/MISSIONS_TECH_SPEC.md), [Mining](docs/MINING_TECH_SPEC.md),
  [Trade](docs/TRADE_TECH_SPEC.md), [Boxel Survey](docs/BOXEL_SURVEY_TECH_SPEC.md), [BGS](docs/BGS_TECH_SPEC.md),
  [Organic Scanning](docs/ORGANIC_SCANNING_TECH_SPEC.md), [Powerplay](docs/POWERPLAY_TECH_SPEC.md) and
  [Screenshots and input automation](docs/SCREENSHOTS_AND_INPUT_TECH_SPEC.md).
- **[docs/guide/](docs/guide/README.md)**: the user guides.
- **[docs/OVERLAY_SETUP.md](docs/OVERLAY_SETUP.md)**: setting up the on-screen overlay (for everyone).
- **[CHANGELOG.md](CHANGELOG.md)**: what has changed.
- **[docs/ATTRIBUTIONS.md](docs/ATTRIBUTIONS.md)**: thanks and acknowledgements to the projects and
  services that helped.

Copyright (c) 2026 R.W. Harper. Released under the [GNU General Public License v3.0](LICENSE).
Third-party notices are in [THIRD-PARTY-NOTICES.md](THIRD-PARTY-NOTICES.md).

*Elite Dangerous* is a trademark of Frontier Developments plc. WNTB is a fan-made tool and is not
official Frontier software.
