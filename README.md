# Wayward Nomads Toolbox (WNTB)

A toolbox for members of the **Wayward Nomads** exploration squadron (WWNS). It is an
[EDMC](https://github.com/EDCD/EDMarketConnector) plugin for **Elite Dangerous**: one panel, six
switchable modes, and a collection of tools and ideas for anyone in the squadron who wants them.

Many of these tools were shaped by ideas from other community projects, credited in
[docs/ATTRIBUTIONS.md](docs/ATTRIBUTIONS.md). They're built to suit my own playstyle and may not suit
everyone's. If a feature isn't for you, turn it off in Settings.

Built and maintained by R.W. Harper (CMDR Bocheaux).

**Requirements:** [EDMC](https://github.com/EDCD/EDMarketConnector) on Windows or Linux. Landing Assist, Interdiction Warning, Discovery Alerts and a few other overlays
need [EDMCOverlay](https://github.com/inorton/EDMCOverlay) or EDMCModernOverlay running.

**Linux (experimental, not yet verified on a real install).** Elite runs under Steam Proton or Wine,
so:
- Install `xdotool` (for example `sudo apt install xdotool`). Auto-Honk and timed screenshots use it
  to press keys in Elite's window. It works on X11 and on Wayland desktops through XWayland.
- WNTB finds your Steam Proton prefix automatically, including extra Steam library folders and the
  Flatpak Steam location. For Lutris, Heroic or a custom prefix, enter its folder under
  **Settings → Auto-Honk → Elite Wine/Proton prefix**.
- Point EDMC's own **Journal directory** setting at the `Saved Games/Frontier Developments/Elite
  Dangerous` folder inside that prefix, so EDMC (and so WNTB) can see the game. WNTB logs a warning
  and shows a hint under **Settings → Auto-Honk** if the setting looks wrong.
- Overlay features (Landing, Interdiction, Discovery, Inventory and the rest) need
  [EDMCModernOverlay](https://github.com/SweetJonnySauce/EDMCModernOverlay), which supports Linux.
  The original EDMCOverlay is Windows-only. WNTB's default connection settings (`127.0.0.1`, port
  5010) already match.
- Notification sounds use `canberra-gtk-play` or `paplay` if present.
- A step-by-step checklist for testing on Linux is in [docs/LINUX_TESTING.md](docs/LINUX_TESTING.md).

## Installing

1. Download the latest release `.zip` from the [Releases page](../../releases).
2. Extract it — you'll get a folder named `WNTB`.
3. Copy that `WNTB` folder into your EDMC plugins folder: open EDMC, go to
   **File → Settings → Plugins**, click **Open** next to "Plugins folder" (or find it yourself at
   `%LOCALAPPDATA%\EDMarketConnector\plugins\`), and drop the `WNTB` folder in there.
4. Restart EDMC. You should see a **Wayward Nomads Toolbox (WNTB)** panel appear.

Automatic updates are off by default. Turn them on in **File → Settings → WNTB** and WNTB will
download new releases itself and tell you in the panel when one is ready. A restart applies it.

## The basics

- **Click a mode button** (Powerplay / Exploration / Mining / Missions / Field Ops / BGS) to switch
  between them. Every mode keeps working in the background even while you're looking at a
  different one — nothing pauses when it's not on screen.
- **Click the "WNTB" title** to collapse or expand the whole panel.
- A few things (Landing Assist, Interdiction Warning) aren't tied to any one mode — they're always
  there regardless of which mode you're looking at.
- Most features have their own tab under **File → Settings → WNTB**, where you can turn things on
  or off and tune how they behave.
- Anything that opens in its own window (Powerplay sessions, Rare Goods, Inventory, the BGS report,
  the Mining Book and so on) uses WNTB's own dark look and remembers its size and position.
  The main panel itself still follows your EDMC theme.
- Each pop-out window opens from a button in its mode — see [Opening the windows](#opening-the-windows)
  just below.
- A handful of features can optionally look things up on outside sites (EDSM, Spansh,
  edastro.com, Canonn, and the Rare Goods Finder's Spansh lookup) — every one of those is called out below, and most are off by default. If
  a feature doesn't mention a network lookup, it isn't making one.

### Opening the windows

Switch modes with the button row under the WNTB title (Powerplay / BGS / Exploration / Mining /
Missions / Field Ops), then use the button listed here. Every window closes with **Esc** or its ✕
and remembers its size and position.

| Window | Mode | How to open it |
|---|---|---|
| Powerplay Sessions | Powerplay | **Sessions** button (bottom row of the panel) |
| Rare Goods Finder | Powerplay | **Rares** button, next to Sessions |
| BGS Report | BGS | **View BGS Report** button |
| Codex Completionist | Exploration | **View Details** button in the Codex Completionist section |
| Inventory | Field Ops | Click the **Inventory bars** in the panel (there's no button) |
| Ship Builds | Field Ops | **Manage Ship Builds** button |
| Colonisation | Field Ops | **Colonisation Sites** button |
| Mining Book | Mining | **Mining Book...** button, on both the Space Mining and Surface Mining pages |

Notes:

- You don't need to be mining or have a Rhino deployed to open the Mining Book; it lists your saved
  hotspots either way. (Mining's ◂/▸ arrows switch between the Space Mining and Surface Mining pages.)
- The two **Missions** windows only exist while you have active missions: click **All** next to the
  category arrows for the full table, or click any mission card to see that mission's details.
- The BGS and Codex Completionist sections can each be switched off under
  **File → Settings → WNTB** (both are on by default). If you can't find their buttons, check there.

---

## Powerplay

Tracks your pledged Power's merits and Control Points as you earn them.

**How to use it:** just play — the panel updates itself as you earn merits. It shows your current
system's PowerPlay state, what you've earned *in that system*, and running totals for the whole
session. Click **Sessions** to browse past sessions, or **Rescan** if a session's numbers ever
look wrong (re-reads your journal from scratch).

**Rares:** click **Rares** to open the Rare Goods Finder: the rare commodities closest to wherever
you are, with each one's origin system, station, landing-pad size and — looked up live from
[Spansh](https://spansh.co.uk) — which Power currently controls that system (handy for Powerplay
rare-goods hauling). Double-click a row to open that commodity on Inara. Use **Show nearest** to
choose how many rows (up to all 141). The list needs your position, so it shows "Awaiting system
data" until your first jump or login after EDMC starts. *Network:* the Controlling Power column
asks Spansh each time you open the window; "—" means unclaimed or unreachable.

**Settings tab:** lets you adjust the merit-per-Control-Point ratios (only needed if Frontier
changes them) and customize the text used when you click "Copy" to paste a session summary into
Discord or a forum post.

## Exploration

Everything in this mode lives in one scrolling panel, stacked top to bottom.

### Auto-Honk
Fires your Discovery Scanner (the basic system-wide "honk") automatically every time you jump into
a new system, so you never forget.

**How to use it:** turn it on with the toggle button — that's it. Configure which fire button it
simulates and how long it holds it in **Settings → Auto-Honk**, and use the **Test Honk Now**
button there to check it's working without waiting for a real jump. If you also run EDCoPilot with
its own auto-honk, turn one of the two off — they'll fight each other otherwise.

### Discovery Alerts
Pops a banner on your in-game overlay the moment you jump into a system nobody's ever scanned, or
the moment you're the first to scan/map a body.

**How to use it:** click the toggle button to turn it on. Requires
[EDMCOverlay](https://github.com/inorton/EDMCOverlay) to be running — set its connection details
on the shared **Overlay Connection** Settings tab. Use **Settings → Discovery** to reposition the
banner or send a test one.

### Boxel Survey
A tool for systematically exploring procedurally-named systems, with three modes you switch
between using the buttons at the top of its section.

**Random** — sits above the whole panel and works no matter which mode you're in (even collapsed).
Looks for a real, EDSM-known boxel near where you actually are, then hunts inside it for a candidate
name EDSM has no record of at all, and copies it straight to the clipboard — paste it into the
galaxy map to go find something nobody's discovered yet. It doesn't touch your Sequence/Region Sweep
progress; it's a separate one-off lookup. It also keeps its own persistent, per-commander log of
every system you've actually jumped to, so a system you've already been to (but haven't uploaded to
EDSM yet) never comes back as a "new" suggestion; clear that log any time from Settings → Boxel
Survey → **Clear Visited Systems Log**.

**Which one should you use?**

| If you want to... | Use... |
|---|---|
| Work through one boxel (subsector) from start to finish, in order | **Sequence** |
| Clear a whole region — several boxels — tracking what's left across all of them, without babysitting one at a time | **Region Sweep** |
| Visit a fixed list of specific systems in a sensible order (not a systematic survey at all — a rendezvous, a POI list, a squadron staging route) | **Waypoint Route** |

Sequence and Region Sweep both only ever walk *procedurally-named* systems (`Outotz LS-K d8-0` and
the like) — that's the whole premise of a boxel survey. Waypoint Route is the odd one out: it
accepts any system name, hand-named or procedural, since it's a general point-to-point planner, not
a boxel walker. If your list is a handful of specific places rather than "everything in this area,"
skip Sequence/Region Sweep entirely and start there.

Between Sequence and Region Sweep: Sequence is simpler — one seed, one running sequence, nothing to
manage — and is the better starting point if you're not sure yet. Region Sweep earns its keep once
you're covering enough ground that babysitting one boxel at a time gets tedious: it holds several
boxels' progress at once and auto-advances to the next unfinished one for you (see below).

- **Sequence** — walks one boxel's list of candidate systems in order. Set a starting system,
  then use **Next**/**Prev** to step through, or **Find Nearby (EDSM)** to jump straight to the
  nearest unexplored boxel. If 3 **Next** clicks in a row go by without an actual jump (a sign
  this mass-code boxel has run out of real systems — the sequence numbers are sparse and there's
  no way to know in advance which ones exist), it automatically checks EDSM for the nearest real
  system and drops it into the seed field, ready to **Set**. Notable finds (Earth-likes, water
  worlds, biological signals, etc.) get tallied automatically; **Export Survey Log** (in
  Settings → Boxel Survey) writes them to a CSV file.
- **Region Sweep** — for clearing a whole region instead of one boxel at a time. Add cubes to a
  queue, then let **Discover Nearby Cubes** or **Discover Known Systems** fill in what's already
  known before you even visit. Mark a cube **Empty** once you've confirmed there's nothing worth
  surveying there, so you never waste time on it again. Once one cube's done, it automatically moves
  on to the next incomplete one in the queue; turn on **Auto-discover more nearby cubes** (Settings →
  Region Sweep) to have it top the queue back up from EDSM on its own once you're down to your last
  one, so it keeps handing you new cubes instead of running dry.
- **Waypoint Route** — a point-to-point route planner for any systems you want to visit in order
  (a rendezvous, a POI list, whatever). Add systems one at a time or **Import CSV**, then let
  **Reorder (Nearest-Neighbor)** sort them by actual distance from where you are.

This section is collapsed by default (it's the biggest one here) — click its title to expand it.

### Exploration Value
A quiet running readout of what you're finding as you scan.

**How to use it:** nothing to turn on — it just shows the estimated payout for your last scan, the
age of the current system's star, and which of the galaxy's 42 named regions (e.g. "Inner Orion
Spur") you're currently in, all computed locally from your position, no network call. Two extra
bits are opt-in in **Settings → Exploration Value**: how rare an Earth-like World you just found is
(checks Spansh), and whether EDSM already knows about a system you've selected on the galaxy map.

### Organic Scanning
Helps you find and identify exobiology life as you explore a planet's surface.

**How to use it:** once you've detected biological signals on a body (FSS or DSS) and you're on
the ground, it shows which species each signal is likely to be, based on the planet's atmosphere,
gravity, temperature, and a few other factors — plus an estimated credit value. Once you start
sampling with the Genetic Sampler, it tracks your progress and tells you when you've walked far
enough for the next sample to count. Works entirely from your own journal — no network calls, and
it's designed to play nicely alongside [EDMC-Canonn](https://github.com/canonn-science/EDMC-Canonn)
if you run that too.

### Codex Completionist
A personal tally of every scannable thing you've ever found — biological, geological, Guardian,
human, Thargoid, and more.

**How to use it:** it builds itself automatically as you play. Click **View Details** for the full
breakdown (with a ⭐ next to anything that was a genuine first discovery), or **Backfill from
Journal History** once to pull in everything from your past journals (not automatic, since it can
take a while for a long career).

The details window has two tabs. **Found** is your tally by category; click the **Entry** heading to
sort A–Z or Z–A, or **Times found** for most- or least-found first (click again to reverse).
**Not found** lists the biological, civilisation and stellar-body entries you haven't found yet,
using Canonn's entry catalog — fetched in the background the first time, then saved and refreshed
every couple of weeks (or any time with **Refresh Catalog**). It sorts the same way and the
subtitle shows how many catalogued entries you've found. Double-click any entry on either tab (or
select it and click **Open Reference**) to look it up on Canonn's site. The catalog doesn't include
geological or anomaly entries, so those never appear under Not found.

### GEC Nearby POI
Looks up the nearest point of interest from edastro.com's exploration catalog.

**How to use it:** click **Find Nearest POI**. It's manual on purpose — it only looks something up
when you ask it to, never automatically.

### Canonn Nearby POI
Same idea, but searches Canonn Interstellar Research's own lists of Thargoid and Guardian sites.

**How to use it:** click **Find Nearest POI**. The first click downloads Canonn's site lists and
keeps them cached for the rest of your session; click **Refresh POI Data** if you want a fresh
copy. Choose which categories (Thargoid/Guardian) to include in **Settings → Canonn Nearby POI**.
By default it skips any site you've already logged a matching Guardian/Thargoid entry for in Codex
Completionist, so it points you somewhere new rather than back to a site you've already visited —
turn this off in the same Settings tab if you'd rather always see the true nearest site regardless.

## Mining

Tracks two kinds of mining run — ship-based Space Mining and Rhino-SRV Surface Mining — plus your
own catalog of known hotspots.

**How to use it:** use the ◂/▸ arrows to switch between the Space Mining and Surface Mining pages;
each shows live stats for your current run. Buttons appear as they become relevant: **+ Save
Hotspot Here** to record a deposit you've found, **Mining Book** for a three-pane window over the
bodies you've scanned in this system plus every hotspot you've saved (filter by material or rig
count; per-hotspot tons mined and tons left; edit, mark depleted, copy coordinates, a zoomable map;
and, for a scanned body, what you have found so far on that kind of body — rates built only from the
hotspots you have saved, so they start empty and fill in as you record, not what that body holds),
and **Find Nearby Hotspots** / **Find Best Price** / **Check Ring Reserve Level** to look things up
on Spansh/EDSM (all opt-in — turn them on in Settings first).

**Settings tab:** turn on the optional network lookups above, enable an in-game overlay for live
stats, a surface waypoint arrow pointing to the nearest known hotspot, a small "where have I
driven" minimap for surface runs, and automatic archiving of completed runs.

## Missions

One view of every mission on your board, organized by category, plus Community Goals.

**How to use it:** click a category tab (Massacre, Settlement Raids, Combat, Trade & Mining,
Passenger, Covert, On-Foot Ops, Other, Community Goals) to see what's there. Massacre and
Settlement Raids show grouped kill-progress bars; everything else shows one card per mission —
click a card for full details. Use **All Missions** for one flat, sortable table across every
category at once.

**Settings tab:** choose what shows on each card (kill progress, mission counts, a
commodities-needed summary, etc.).

## Field Ops

### Screenshots
Converts Elite's raw screenshots to PNG automatically, with an optional auto-crop of just the
relevant HUD panel.

**How to use it:** screenshots convert themselves as you take them — no action needed. Click
"Click to expand" in the panel to see thumbnails of your recent captures. There's also an optional
auto-capture timer (a small clock icon) if you want periodic screenshots without pressing the
button yourself.

**Settings tab:** where converted screenshots are saved, whether to delete the originals, filename
format, and auto-capture timing.

### Inventory
Tracks your Odyssey backpack, ship locker, fleet carrier locker, and cargo hold live, as capacity
bars.

**How to use it:** just play — each bar fills and empties as you pick things up, use them, or
transfer them. Click any bar to open a full browsable inventory list.

**Settings tab:** customize pickup notifications (sound, on-screen message, what it says), and
adjust capacity numbers if your loadout doesn't match the defaults.

### Ship Builds
A place to keep track of ship builds you've designed on sites like Coriolis, EDSY, or Spansh — one
list per commander. WNTB doesn't design loadouts itself; this just helps you find a build you made
somewhere else again later.

**How to use it:**
1. Go design your build on whichever site you like (Coriolis, EDSY, Spansh, or anywhere else).
2. Click **Manage Ship Builds** in the WNTB panel.
3. Click **Add**, give it a name (and optionally a role, like "PvE Exploration"), pick the site
   from the dropdown, and paste the build's URL.
4. Click Save.

From then on, select any saved build and use **Open Link** to launch it in your browser or **Copy
Link** to grab the URL — **Edit** and **Delete** work the same way. Builds are kept separate per
commander, so switching who you're logged in as shows a different list.

### Colonisation
Keeps track of what each colonisation construction site still needs delivered, so you can see it
without being docked at the depot — and what you still have to source after counting the cargo
already in your hold.

**How to use it:**
1. Dock at a construction depot (or open its market) once. WNTB registers the site from the game's
   journal; there's nothing to type in.
2. The Field Ops panel shows your most recently updated active site: its progress and tonnes still to go.
3. Click **Colonisation Sites** for the full list: each site is a group with its outstanding
   commodities underneath — required, delivered, remaining, how much of it is in your cargo right now,
   and how much is left **To Source**.

Deliveries are tallied from your journal as you hand cargo over, and the numbers are corrected to the
game's own figures each time you dock at the depot again. Select any commodity row and use **Copy
Shopping List** to put that site's still-to-source list on the clipboard (handy for a squadron
channel), **Remove Site** to stop tracking it, or **Remove Finished** to clear completed and failed
sites. Sites are kept separate per commander.

## BGS

Tracks the Background Simulation (BGS) — faction states, and your own missions/bounties/trade/
exploration activity's effect on them — for systems and factions you designate, with BGS-tick
detection so the activity tally rolls over automatically when the real tick happens.

**How to use it:** the panel always shows what's in your current system, tracked or not — if it's
uninhabited it says so; otherwise it lists every faction present, who controls it (★), and each
one's current state. Click **Track** to start tracking the system (every faction in it) or
**Untrack** to stop, no limit on how many systems you track this way. You can also add systems or
individual faction names from anywhere via **Settings → BGS** (either is enough — tracking a system
covers every faction in it, tracking a faction covers it in every system it appears in).

Once a system/faction is tracked, WNTB tallies what you do there: mission completions (influence
gained/lost), bounty voucher and combat bond redemptions, trade profit/loss, and exploration data
sold. The panel shows a running total "since the last tick"; **View BGS Report** opens the full
breakdown across two tabs — **Faction States** and **Activity Tally** (split into This Tick/Previous
Tick) — with **Copy Summary** for a plain-text copy. Tracked data and the tally are both kept
separate per commander and survive an EDMC restart.

WNTB checks a community tick-time service every 60 seconds to detect the real BGS tick and roll the
tally over automatically — this is the only network call this mode makes, and can be turned off in
Settings if you'd rather keep it fully local (the tally then just keeps accumulating without ever
resetting on its own).

**Settings tab:** enable/disable the feature, turn tick detection on/off, and manage your
tracked-systems and tracked-factions lists.

## Landing Assist & Interdiction Warning

*(Always visible, not tied to any one mode.)*

- **Landing Assist** shows which pad you've been assigned while docking, both in-app and as an
  overlay diagram. Turn it on and choose where it appears in **Settings → Landing**.
- **Interdiction Warning** puts up an overlay alert the instant an interdiction starts. Settings
  only — no main panel widget. Turn it on and try it with the **Test Warning** button in
  **Settings → Interdiction Warning**.

Both need [EDMCOverlay](https://github.com/inorton/EDMCOverlay) running to draw anything on
screen — its connection settings live on the shared **Overlay Connection** Settings tab.

---

## More detail

- **[docs/TECHNICAL.md](docs/TECHNICAL.md)**: how WNTB works and why it's built that way. Start
  here if you want to read or change the code.
- **[docs/ATTRIBUTIONS.md](docs/ATTRIBUTIONS.md)**: acknowledgements.
- **[docs/BOXEL_SURVEY_TECH_SPEC.md](docs/BOXEL_SURVEY_TECH_SPEC.md)**: Boxel Survey in depth (the
  procedural-name algorithm, known gaps).
- **[docs/BGS_TECH_SPEC.md](docs/BGS_TECH_SPEC.md)**: BGS tracking in depth (journal fields per
  activity, tick detection, out-of-scope items).
- **[CHANGELOG.md](CHANGELOG.md)**: what changed in each release.
- **[LICENSE](LICENSE)** and **[THIRD-PARTY-NOTICES.md](THIRD-PARTY-NOTICES.md)**: licensing.

Building from source:

```bash
npm run build      # builds the plugin into dist/WNTB
npm run package    # builds, then zips dist/WNTB into a release archive
```

## License

Copyright (c) 2026 R.W. Harper. Released under the [GNU General Public License v3.0](LICENSE).
Third-party notices are in [THIRD-PARTY-NOTICES.md](THIRD-PARTY-NOTICES.md).
