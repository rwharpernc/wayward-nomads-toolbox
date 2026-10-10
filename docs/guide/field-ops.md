# Field Ops

Field Ops holds the on-foot and housekeeping tools: screenshots, your inventory, saved ship builds, and
colonisation sites.

**On this page:** [Screenshots](#screenshots) · [Inventory](#inventory) · [Ship Builds](#ship-builds) ·
[Colonisation](#colonisation) ·
[What the game does and doesn't tell us](#what-the-game-does-and-doesnt-tell-us-and-how-to-work-around-it)

## Screenshots

Converts Elite's screenshots to PNG automatically, with an optional crop to just the relevant HUD panel.

**How to use it:** nothing to do. Screenshots convert as you take them.

- Click **"Click to expand"** in the panel to see thumbnails of recent ones.
- An optional auto-capture timer (a small clock icon) takes screenshots periodically for you.

**Settings → Field Ops → Screenshots:**

- where converted screenshots are saved,
- whether to delete the originals,
- the file-name format,
- the auto-capture timing,
- an optional "Screenshot saved" message on your game screen (off by default; needs an overlay; has a **Test
  Overlay** button),
- *Group converted files into a per-system subfolder* (off by default),
- *Show the auto-capture timer icon on the main window* (on by default),
- *Automatically capture a screenshot when scanning a Thargoid signal* (on by default),
- *Use high-resolution capture on the auto-timer (Solo play only)* (off by default).

*On Linux, the auto-timer needs `xdotool`, and a Flatpak EDMC needs the screenshots permission. See
[WNTB on Linux](linux.md). On Windows, OneDrive-redirected folders are handled automatically.*

## Inventory

Tracks your Odyssey **microresources** and your cargo hold as capacity bars. For microresources it follows the
game's three categories: **Assets**, **Goods** and **Data** (the journal calls these Component, Item and Data).

**On the panel:** a status line (`Awaiting Odyssey loot…` until something happens), then up to four bars. Each shows
`count/capacity`, or just the count where WNTB doesn't know the capacity.

| Bar | Capacity | When it appears |
|---|---|---|
| **Backpack** | From your suit, if known (see below) | Always |
| **Ship Locker** | 1,000 each of Assets, Goods and Data (3,000 in all) | Always |
| **Carrier Locker** | Not shown | Only once WNTB has real fleet carrier locker data for this commander |
| **Cargo** | Your ship's cargo capacity; Scarab 4 t, Scorpion 2 t; Rhino capacity unknown | While you are in a ship or SRV. Hidden while on foot. The label reads Ship Cargo, Scarab Cargo and so on |

**Click any bar** to open the Inventory window.

### The Inventory window

Tabs: **Backpack**, **Ship Locker**, **Carrier Locker** (only once a carrier is confirmed) and **Cargo**. Each of the
first three lists **Resource**, **Category** and **Held**; the Cargo tab lists **Commodity** and **Tonnes** for the
hold you are using (ship or SRV).

- The **Filter** box at the top filters every tab at once. **Clear** empties it.
- **Refresh** redraws the window.
- The subtitle shows your current suit.
- A note on the Backpack tab says `Not yet synced this session` if the game hasn't yet reported your backpack
  (for example if you logged in already on foot). Loot, resupply or disembark to refresh it.
- Capacity colours change as a category fills: amber near the limit, red when full. The ship locker warning level
  is **90%** of 1,000 for a category.

### Things worth knowing

- **Carrier Locker comes from Frontier's servers, not the journal.** EDMC must be signed in to Frontier, and the
  data can **lag the game by 15 to 30 minutes**.
- **Backpack capacity is a built-in table, not something the game reports.** WNTB looks up your suit and whether it
  has the *Extra Backpack Capacity* mod. The table cannot see engineering grade, and has no figure for the Flight
  Suit (so its bar shows a count with no limit). The Settings tab lets you type in the real number for each of your
  suit loadouts.

| Suit | Assets | Goods | Data |
|---|---|---|---|
| Maverick (unmodded / extra capacity) | 60 / 120 | 40 / 80 | 20 / 40 |
| Artemis | 40 / 80 | 20 / 40 | 10 / 20 |
| Dominator | 20 / 40 | 10 / 20 | 10 / 20 |

### Settings (Settings → Field Ops → Inventory)

| Setting | Default |
|---|---|
| Show pillage notifications on the in-game overlay | Off |
| Pillage message (placeholders `{item}`, `{total}`) | `[{item}] pillaged! New Inventory Total: {total}` |
| Play a sound on pickup | Off |
| Show these inventory bars on the overlay (one tick per bar) | All off |
| Overlay position X / Y | 900 / 120 |
| Announce pickups for (Assets, Goods, Data) | All three |
| Suit Backpack Capacity (per suit loadout) | The built-in table |

Unticking a category in *Announce pickups for* only mutes its notifications. It is still counted.
The overlay settings need an overlay running; see [Setting up the overlay](../OVERLAY_SETUP.md).

On Linux, the pickup sound needs `canberra-gtk-play` or `paplay`; see [Windows and Linux](platforms.md).

## Ship Builds

A place to keep ship builds you've designed on sites like Coriolis, EDSY or Spansh, one list per commander. WNTB
doesn't design ships itself. This just helps you find a build again later.

**To save a build:**

1. Design your build on whichever site you like.
2. Click **SHIPS** (manage ship builds) in the WNTB panel.
3. Click **Add**.
4. Give it a name, and optionally a role such as "PvE Exploration".
5. Pick the site and paste the build's web address.
6. Click **Save**.

**Example:** name `Krait Phantom explorer`, role `Exploration`, site `Coriolis`, and paste the link from your
browser's address bar.

**To use it later:** select a saved build and use **Open Link** to open it in your browser, or **Copy Link** to copy
the address. **Edit** and **Delete** work the same way.

## Colonisation

Keeps track of what each colonisation construction site still needs delivered. You can read it from anywhere, not
just while docked, and it shows what's left to find after counting the cargo already in your hold. There is no
on/off setting for it.

**Where the data comes from.** The journal writes a `ColonisationConstructionDepot` event when you dock at a
construction depot or open its market, and a `ColonisationContribution` event each time you hand cargo over.

**To start tracking a site:**

1. Dock at the construction depot, or open its market, **once**. There is nothing to type in.
2. The Field Ops panel shows a line such as `Colonisation: <site name> - 45%, 1,234 t to go (+2 more)`. That is
   your most recently updated active site, with `(+N more)` if you have others. With none it says
   `Colonisation: no active construction sites`.
3. Press **REPORT** to open the **Colonisation Sites** window.

**Who is playing.** At start-up WNTB takes the commander from the newest journal (the last login in it), so the
summary line shows your sites straight away instead of `waiting for commander login`. After you log in as someone
else it follows them.

**The site name** is taken from the most recent time you docked at that depot's market. If WNTB hasn't seen you dock
there, the site is called `Construction site <number>`.

**Keeping it right.** Each time you dock or open the depot market again, WNTB replaces its figures with the game's
own. Between visits it adds what you deliver, as reported in the journal. Everything is kept **per commander**.

**Deliveries made with EDMC closed** are found again when EDMC starts: WNTB reads the recent journals (14 days, or
back to the oldest site it is tracking, never more than 30) and applies each depot snapshot and delivery once. It also
registers a site you docked at in that time. A delivery to a site that no journal in that window has a depot snapshot
for is ignored, since there is nothing to add it to.

### The Colonisation Sites window

The subtitle reads `<commander> — N active of M sites`. Each site is a group with its system name and, on the same
row, the tonnes remaining and a status: its progress as a percentage, or `complete` or `failed`. Active sites start
open; finished ones are greyed. Under each site is one row per commodity **still outstanding**:

| Column | Meaning |
|---|---|
| Required | What the site needs in total |
| Delivered | What's been handed over |
| Remaining | Required minus delivered |
| In Cargo | What is in your hold now (ship or SRV) |
| To Source | Remaining minus what you're already carrying: what you still have to buy or mine |
| FC | Tonnes of that commodity you have transferred onto your **fleet carrier** (only shown once WNTB has seen you have one) |

**The FC column.** It adds up the journal's `CargoTransfer` events made while docked at your fleet carrier: tonnes
moved to the carrier minus tonnes moved back to the ship. It appears for a commander WNTB knows has a fleet carrier, using the **same knowledge as Trade**: your
choice for that commander in the Trade settings (None, Fleet, Squadron, Both or Auto) decides when it names the
carriers, and on Auto a fleet carrier Trade has recorded counts (it reads your recent journals at start-up and
remembers them). Failing that, it appears once WNTB has seen one of yours itself (a transfer, opening Carrier
Management, buying one, or docking at one). It is per commander. It does not change To Source.

- **Transfers made with EDMC closed are found.** They are in the journal, and at start-up WNTB reads the recent
  journals and adds any transfer it hasn't counted. A transfer is never counted twice, even if EDMC also saw it live.
- **How far back it reads:** 14 days, or back to the last transfer it counted if that is older, never more than 30.
  Transfers older than that are never counted, so stock you moved to the carrier before then won't show. Taking
  stock back off the carrier that was moved before then just leaves the figure at zero.
- **It is what WNTB saw you transfer, not the carrier's actual hold.** Changes that are not transfers are not in the
  journal as transfers, so they are not counted: buying from or selling to the carrier's market, trade orders, and a
  squadron mate moving cargo. The figure can therefore drift from the real contents.

**Buttons.** For these you **select a commodity row** under the site you mean (selecting the site's heading is not
enough):

- **Copy Shopping List** copies that site's list to the clipboard, as lines like `1,200 t  Steel`, biggest first.
  The amounts are the **To Source** figures, so what you already carry is taken off. If nothing is needed it says
  so.
- **Remove Site** stops tracking that site.
- **Remove Finished** needs no selection. It deletes every complete or failed site, because those have no
  commodity rows to select.

### The shopping list on the overlay

Optional, and **off by default**. It needs an overlay running; see [Setting up the overlay](../OVERLAY_SETUP.md). Turn
it on in Settings under Field Ops, in the Colonisation settings: **Show the shopping list on the in-game overlay**.

It draws a table laid out like SRVSurvey's, with the site name as its title and the columns **Commodity**, **Need**,
**FC** and **Ship**:

- **Need** is what the site still requires (required less delivered). It does **not** drop as you load up, so you can
  see what you need and what you have side by side. It falls when you deliver.
- **FC** appears only if you have a fleet carrier (see the FC column above): what you have moved onto it. It is blue
  once it covers the need, grey while it doesn't, and blank when none.
- **Ship** is what is in your ship's hold right now, so you can see what you just bought. A **✓** after the name means
  your hold already covers it (the row turns green); the row turns amber if you carry **more** than the site needs.

Commodities are alphabetical so rows stay put while numbers change. A last line gives the tonnes remaining and the
trips that is in your current ship, such as `► 32,769 remaining  ► 33 trips in this ship` (the trips need your ship's
cargo capacity, which EDMC supplies).

- **When it shows:** while you are in a commodity market, or in the carrier's inventory (Carrier Management and cargo
  transfer), at a station or carrier; and also whenever you are **docked at a construction site** (looking out of the
  cockpit or at the station services, but not in a map or another panel). It hides when you leave the market or
  inventory screen, open another station service such as outfitting or the shipyard (except at a construction site),
  or undock. Backing out of the market to the station-services menu can't be detected, so the card stays until you
  leave that menu. It relies on the game's `Status.json` reporting which screen is open.
- **Which site:** your most recently updated active site, the one the Field Ops summary line names. Completed and
  failed sites are never shown. The card disappears when nothing is left to source.
- **Settings:** the card's X and Y position on the overlay's 1280 x 960 virtual screen (default 20, 300), and **Rows**,
  how many commodities to list (1 to 40, default 20); any more are summarized as `+N more`. **Test Overlay** shows a
  sample card for a few seconds, even while the option is off.
- It is cleared when EDMC closes. If the overlay program isn't running, nothing is drawn and nothing breaks.

## What the game does and doesn't tell us, and how to work around it

WNTB can only show what Elite Dangerous writes to its journal files and what the online services it asks (Frontier's servers for the Carrier Locker) publish. Where it can't be sure, WNTB says so rather than guess quietly.

| What you might expect | What the game gives | What to do |
|---|---|---|
| Screenshots cropped perfectly | The crop rectangles are **fixed measurements** and may need adjusting if Frontier changes the HUD. | Turn the crop off, or report it, if a crop is wrong after a game update. |
| The screenshot timer to press any button | It can only press **keyboard** keys. macOS isn't supported for key simulation, and Linux on Wayland without XWayland isn't either (conversion and cropping still work). | Bind a keyboard key to the screenshot control. |
| Screenshots to always save | Windows Controlled Folder Access or antivirus can block file access. The error message says so. | Allow EDMC through, or choose another save folder. |
| Your backpack capacity to be reported | The game doesn't report it. WNTB uses a **built-in table** by suit and the Extra Backpack Capacity mod. It can't see engineering grade and has no figure for the Flight Suit. | Type the real number for each suit loadout in the Inventory settings. |
| The inventory to show after restarting EDMC mid-game | EDMC does not replay the session to plugins, but it rebuilds its own state from the journal. WNTB now syncs the backpack and ship locker from that state when EDMC starts. | If a bar still shows nothing, loot, resupply or disembark to refresh it. This relies on EDMC's state and has not been checked against every EDMC version. |
| The Backpack to be known at login | If you log in already on foot, the game hasn't yet reported it (the tab says `Not yet synced this session`). | Loot, resupply or disembark to refresh it. |
| The Carrier Locker to be live | It comes from **Frontier's servers**, not the journal. EDMC must be signed in to Frontier, and the data can **lag the game by 15 to 30 minutes**. | Sign EDMC in, and allow time after changes. The locker is hidden until real data arrives. |
| The Rhino's cargo capacity | Not confirmed against a real journal entry, so the bar shows the count with no limit. | Read the tonnes, not a percentage. |
| Colonisation sites to appear on their own | The game writes the depot event only when you **dock or open the depot market**. A delivery to a site WNTB has never seen a depot snapshot for is ignored. | Dock at the depot (or open its market) once for each new site. Docking again replaces WNTB's figures with the game's own. Deliveries made with EDMC closed are caught up from the last 14 to 30 days of journals at start-up. |
| A site to have its real name | The name is taken from the last time you docked at that market. Otherwise it is `Construction site <number>`. | Dock at the market once to pick up the name. |
| Ship Builds to be checked | WNTB only stores the link and name you give it. It doesn't read or check the build. | Keep your link current if the site changes. |

