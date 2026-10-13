# Field Ops

Field Ops holds the on-foot and housekeeping tools: screenshots, your inventory, your engineering materials and saved ship builds.
(Colonization has its own mode, with its own page: [Colonization](colonization.md).)

> **Where this comes from:** screenshots, your backpack and ship locker, and ship loadouts come from the journal (or from EDMC's own state, which it rebuilds from the journal). The journal doesn't give your backpack's capacity, so WNTB uses a built-in table, and the Carrier Locker isn't in the journal at all: it comes from Frontier's servers through a signed-in EDMC. See [How WNTB knows what it knows](README.md#how-wntb-knows-what-it-knows).

**On this page:** [Screenshots](#screenshots) · [Inventory](#inventory) · [Materials](#materials) · [Engineering](#engineering-blueprints-and-a-wishlist) · [Ship Builds](#ship-builds) ·
[What the game does and doesn't tell us](#what-the-game-does-and-doesnt-tell-us-and-how-to-work-around-it)

## Screenshots

Converts Elite's screenshots to PNG automatically, with an optional crop to just the relevant HUD panel.

**How to use it:** nothing to do. Screenshots convert as you take them.

- Click **"Click to expand"** in the panel to see thumbnails of recent ones. Click a thumbnail to preview it; the preview has an
  **Open Folder** button that opens the folder it was saved in.
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
| Where it sits on screen | Top right area (set on Settings → Overlays → Overlay Placement) |
| Announce pickups for (Assets, Goods, Data) | All three |
| Suit Backpack Capacity (per suit loadout) | The built-in table |

Unticking a category in *Announce pickups for* only mutes its notifications. It is still counted.
The overlay settings are on **Settings → Overlays → Inventory** and need an overlay running; see
[Setting up the overlay](../OVERLAY_SETUP.md).

On Linux, the pickup sound needs `canberra-gtk-play` or `paplay`; see [Windows and Linux](platforms.md).

## Materials

What you hold of each engineering material: **Raw** (mined and scanned), **Manufactured** and **Encoded**, with each one's grade (1 very common to 5
very rare) and the most the game lets you hold of it. A collapsible **Materials** row shows the pieces held of each type, the last pick-up or
discard ("Last: +3 Carbon (now 123)") and which materials are **at the limit**, so you know that collecting more is wasted. **MATERIALS** opens
the window.

**The window** lists every material you hold: its type, grade, how many, the limit and the room left. Type in **Search** (every word must be in
the name), pick a **Type** or **Grade**, tick **Only what is at the limit**, and click a heading to sort.

**Where the counts come from.** The game writes your whole list when you log in, and then one entry for every change: pick-ups, discards,
material trades, synthesis, engineering crafts, the Technology Broker, materials handed to an engineer and mission rewards. WNTB follows
those. If you start EDMC in the middle of a session, WNTB takes EDMC's own running totals once, so the counts are right straight away.
The counts are kept on your computer for the commander they belong to, and nothing is sent anywhere.

**The limits** are 300, 250, 200, 150 and 100 for grades 1 to 5. The names, types and grades are a built-in table of the game's 137 materials;
a new material the table does not know is still counted, with no grade or limit shown, until WNTB is updated.

**Find a trader.** A material trader swaps materials within one category (a Raw trader trades Raw materials, and so on). **Find a trader** in the
Materials window opens a window to look for the closest one: pick the **Type**, how far to look (**Within**, 50 ly up to any distance) and the
smallest landing **Pad** you need, check the system to **Search from** (it starts as the one you are in; type another to plan ahead, or press
**Here**) and press **Find**. The results list the closest first, each with whether the station is in space or on a surface, its distance from the
arrival star and its largest pad; double-click a row to copy its system name for the galaxy map. Above the results, what you hold of that type by
grade, with how many materials are at the game's limit, so you can see what is worth swapping. Pressing **Find** is the only thing that goes online:
it sends Spansh the system name and the type. The same search within two minutes is answered from memory.

## Engineering: blueprints and a wishlist

**BLUEPRINTS** on the Materials row opens the Engineering window. It has three tabs.

**Blueprints.** Every engineering blueprint in the table (about 1,170: ship modules, Guardian items, Technology Broker unlocks, engineer
unlocks, synthesis recipes, and Odyssey suit and weapon upgrades). **Search** matches the module, blueprint name, engineer, effect or an
ingredient (every word you type must match), and **Module** narrows to one type. Pick a blueprint to see who offers it, its effects, and what
**one craft** takes: each ingredient with how many you need, how many you hold, and where it is found. Set **Crafts** and press **Add to
wishlist** (or double-click a row to add one craft).

**Wishlist.** Your list of blueprints, with a number of crafts each, kept on your computer for the commander who made it. For each entry it says
whether it **can be made now** and how many pieces it is **short**. Below is one **shopping list** for the whole wishlist: need, have, short and
where each ingredient is found, with what is short at the top. Each entry also says **who can do it**: an engineer you have unlocked,
or a vendor or the synthesis panel (which need no unlocking), or "No engineer unlocked yet". Select an entry to change its crafts, **Remove** it
or **Clear list** (each asks twice). The Materials row shows a line such as `Wishlist: 3 blueprints, 2 can be made, 14 pieces short`.

**Engineers.** Every engineer the table or your journal knows (and the four Colonia on-foot engineers, whose steps are added by hand), with where you stand (Known, Invited, or Unlocked with their rank), how many
blueprints they offer and what unlocking them asks for, with how much of it you hold (for the Colonia engineers: the steps in words, and for Yi Shen the three sets of items, which can go on the wishlist); unlocked engineers first. **Show their blueprints** lists
what they offer, and **Put their unlock on the wishlist** adds what unlocking them takes. Your standings come from the game's engineer list, sent
at login and whenever one changes (including a rank-up), and are kept on your computer for each commander.

**How "can be made now" works.** Entries are weighed in list order, as you would craft them: an entry that can be made takes what it needs, and the
ones below it only see what is left. An entry that cannot be made takes nothing, so it does not use up materials a later entry could use.

**Crafts are up to you.** A blueprint's ingredients are what one craft takes. How many crafts it takes to reach the result you want depends on the
game's rolls, which no tool can know; set the number you expect.

**What is counted:**
- **Ship materials** (Raw, Manufactured, Encoded): from the Materials counts above.
- **On-foot items** (Odyssey components, goods and data): from your **ship locker**, as the Inventory tracks it. The backpack and a fleet carrier's
  locker are not counted: move what you want to use into the ship locker. This follows the Elite Dangerous Odyssey Materials Helper, whose
  wishlist counts the ship locker as available and shows a carrier's stock apart; Frontier does not say, so it is on the list to confirm in
  the game.
- **Trade goods** (a Technology Broker unlock takes commodities): shown as needed but **not counted**, and an entry that needs them says "Yes, not
  counting ..." rather than guessing.

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

## What the game does and doesn't tell us, and how to work around it

WNTB, like every third-party tool, only knows what Elite Dangerous writes to its journal files. It adds what Frontier's servers give a signed-in EDMC (for the Carrier Locker) and works around the rest. Where it can't be sure, WNTB says so rather than guess quietly. See [How WNTB knows what it knows](README.md#how-wntb-knows-what-it-knows).

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
| Your materials to be right as soon as EDMC starts | The game writes the full list only when you **log in**. Between logins WNTB follows each change, and after a restart it shows the counts from your last session until the next login list arrives (the window says so). | Log in to the game, or start EDMC before the game. |
| Materials you were not able to carry to be counted | When you are at the limit, the game discards what you cannot carry. WNTB never counts above the limit. | Nothing; the login list corrects any difference. |
| Which engineer or blueprint needs a material | Not shown yet. This page counts what you hold; it does not know what you need it for. | Use a site such as Inara or EDSY for what a blueprint takes. |
| The blueprint table to be current | The recipes are a copy of EDEngineer's table, last changed in **March 2024**, with a few spelling fixes. A blueprint or material added to the game since may be missing, and a recipe Frontier changed may be out of date. | Check the in-game recipe before you spend rare materials, and report a difference. |
| Every engineer to appear with their blueprints | The blueprint table is from March 2024 and lacks the four **Colonia on-foot engineers** (Baltanos, Eleanor Bresa, Rosa Dayette and Yi Shen). WNTB adds their unlock steps and Yi Shen's items by hand from community sources, with their places (one guide, unconfirmed). It does **not** know which suit or weapon modification each offers: the sources disagree. | For what each Colonia engineer offers, use the game's Engineers panel or a site such as Inara. |
| What unlocking an engineer takes to be complete | The table lists the **materials or goods** an engineer asks for. An invitation can ask for more (a rank, a visit, a referral), which it does not list. | Check the engineer's requirements in the game's Engineers panel. |
| Your materials to match the game after every pick-up | The journal reports almost every gain, but not all of them: replaying about 6,400 login lists, WNTB's counts matched the game's next list 93% of the time, and most of the misses were counts that were higher in the game with no event in between. | The next login list corrects the counts. |
| The Engineering window to know how many crafts you need | The game rolls the result of each craft; nothing in the journal says how many it will take. | Set the number of crafts you expect. |
| On-foot upgrades to count your backpack | The wishlist counts the **ship locker** only. Whether the game also draws on the backpack is not confirmed. | Stow what you carry into the ship locker (or just check the count in the game). |
| The trader finder to say what a trade would give you | It finds the stations. The rates a trader offers are not in the journal or in Spansh's data, so WNTB does not show or work out a rate. | Check the rate at the trader before you swap. |
| The trader finder to be current | The list is Spansh's, from what players have reported: a station can have lost its trader or be closed to you (a permit, a faction state). | Check the station when you arrive; the `Pad` column is the largest pad Spansh knows. |
| Ship Builds to be checked | WNTB only stores the link and name you give it. It doesn't read or check the build. | Keep your link current if the site changes. |

