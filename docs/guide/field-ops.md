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

**The site name** is taken from the most recent time you docked at that depot's market. If WNTB hasn't seen you dock
there, the site is called `Construction site <number>`.

**Keeping it right.** Each time you dock or open the depot market again, WNTB replaces its figures with the game's
own. Between visits it adds what you deliver, as reported in the journal. A delivery to a site WNTB hasn't
registered yet is ignored. Everything is kept **per commander**.

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

**Buttons.** For these you **select a commodity row** under the site you mean (selecting the site's heading is not
enough):

- **Copy Shopping List** copies that site's list to the clipboard, as lines like `1,200 t  Steel`, biggest first.
  The amounts are the **To Source** figures, so what you already carry is taken off. If nothing is needed it says
  so.
- **Remove Site** stops tracking that site.
- **Remove Finished** needs no selection. It deletes every complete or failed site, because those have no
  commodity rows to select.

## What the game does and doesn't tell us, and how to work around it

WNTB can only show what Elite Dangerous writes to its journal files and what the online services it asks (Frontier's servers for the Carrier Locker) publish. Where it can't be sure, WNTB says so rather than guess quietly.

| What you might expect | What the game gives | What to do |
|---|---|---|
| Screenshots cropped perfectly | The crop rectangles are **fixed measurements** and may need adjusting if Frontier changes the HUD. | Turn the crop off, or report it, if a crop is wrong after a game update. |
| The screenshot timer to press any button | It can only press **keyboard** keys. macOS isn't supported for key simulation, and Linux on Wayland without XWayland isn't either (conversion and cropping still work). | Bind a keyboard key to the screenshot control. |
| Screenshots to always save | Windows Controlled Folder Access or antivirus can block file access. The error message says so. | Allow EDMC through, or choose another save folder. |
| Your backpack capacity to be reported | The game doesn't report it. WNTB uses a **built-in table** by suit and the Extra Backpack Capacity mod. It can't see engineering grade and has no figure for the Flight Suit. | Type the real number for each suit loadout in the Inventory settings. |
| The Backpack to be known at login | If you log in already on foot, the game hasn't yet reported it (the tab says `Not yet synced this session`). | Loot, resupply or disembark to refresh it. |
| The Carrier Locker to be live | It comes from **Frontier's servers**, not the journal. EDMC must be signed in to Frontier, and the data can **lag the game by 15 to 30 minutes**. | Sign EDMC in, and allow time after changes. The locker is hidden until real data arrives. |
| The Rhino's cargo capacity | Not confirmed against a real journal entry, so the bar shows the count with no limit. | Read the tonnes, not a percentage. |
| Colonisation sites to appear on their own | The game writes the depot event only when you **dock or open the depot market**. A delivery to a site WNTB hasn't registered is ignored. | Dock at the depot (or open its market) once for each new site. Docking again replaces WNTB's figures with the game's own. |
| A site to have its real name | The name is taken from the last time you docked at that market. Otherwise it is `Construction site <number>`. | Dock at the market once to pick up the name. |
| Ship Builds to be checked | WNTB only stores the link and name you give it. It doesn't read or check the build. | Keep your link current if the site changes. |

