# Field Ops

Field Ops holds the on-foot and housekeeping tools: screenshots, your inventory, your engineering materials (with the blueprints, wishlist, ship planner and engineers) and saved ship builds.
(Colonization has its own mode, with its own page: [Colonization](colonization.md).)

> **Where this comes from:** screenshots, your backpack and ship locker, and ship loadouts come from the journal (or from EDMC's own state, which it rebuilds from the journal). The journal doesn't give your backpack's capacity, so WNTB uses a built-in table, and the Carrier Locker isn't in the journal at all: it comes from Frontier's servers through a signed-in EDMC. See [How WNTB knows what it knows](README.md#how-wntb-knows-what-it-knows).

**On this page:** [Screenshots](#screenshots) · [Inventory](#inventory) · [Materials](#materials) · [Engineering](#engineering-blueprints-and-a-wishlist) (including the [Ship planner](#engineering-blueprints-and-a-wishlist)) · [Ship Builds](#ship-builds) ·
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
- *Include WNTB's built-in overlay in the converted screenshot* (off by default; Windows, needs the built-in overlay chosen under Settings → Overlays): the game's own screenshot never shows an overlay, so WNTB draws the cards that were on screen when you pressed the key onto the converted copy. A failure here never loses the screenshot,
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
- Capacity colors change as a category fills: amber near the limit, red when full. The ship locker warning level
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

**To use it:**
1. Switch to Field Ops mode (**OPS**) and open the **Materials** row if it is folded. Log in to the game once, so WNTB has the full list.
2. Read the row: pieces held of each type, the last change, and anything at the limit.
3. Press **MATERIALS** to search, filter and sort. To find where to swap materials, press **Find a trader** inside that window (see below).
4. To plan crafts, press **BLUEPRINTS** (see [Engineering](#engineering-blueprints-and-a-wishlist)).

**The window** lists every material you hold: its type, grade, how many, the limit and the room left. Type in **Search** (every word must be in
the name), pick a **Type** or **Grade**, tick **Only what is at the limit**, and click a heading to sort.

**Where the counts come from.** The game writes your whole list when you log in, and then one entry for every change: pick-ups, discards,
material trades, synthesis, engineering crafts, the Technology Broker, materials handed to an engineer and mission rewards. WNTB follows
those. If you start EDMC in the middle of a session, WNTB takes EDMC's own running totals once, so the counts are right straight away.
The counts are kept on your computer for the commander they belong to, and nothing is sent anywhere.

**The limits** are 300, 250, 200, 150 and 100 for grades 1 to 5. The names, types and grades are a built-in table of the game's 146 materials;
a new material the table does not know is still counted, with no grade or limit shown, until WNTB is updated.

**Find a trader.** A material trader swaps materials within one category (a Raw trader trades Raw materials, and so on). **Find a trader** in the
Materials window opens a window to look for the closest one: pick the **Type**, how far to look (**Within**, 50 ly up to any distance) and the
smallest landing **Pad** you need, check the system to **Search from** (it starts as the one you are in; type another to plan ahead, or press
**Here**) and press **Find**. The results list the closest first, each with whether the station is in space or on a surface, its distance from the
arrival star and its largest pad; double-click a row to copy its system name for the galaxy map. Above the results, what you hold of that type by
grade, with how many materials are at the game's limit, so you can see what is worth swapping. Pressing **Find** is the only thing that goes online:
it sends Spansh the system name and the type. The same search within two minutes is answered from memory.

## Engineering: blueprints and a wishlist

**BLUEPRINTS** on the Materials row opens the Engineering window. It has five tabs: Blueprints, Wishlist, Ship planner, Upgrade planner and Engineers.

**To use it:**
1. Press **BLUEPRINTS** on the Materials row. On the **Blueprints** tab, search for a module or an effect and pick a blueprint.
2. Read its ingredients: how many one craft takes, how many you hold and where each is found. Set **Crafts** to the number you expect to need.
3. Press **Add to wishlist**. Repeat for everything you plan to build.
4. Open the **Wishlist** tab: it says which entries can be made now, what you are short of, and the shopping list for all of it.
5. Open the **Engineers** tab to see who you have unlocked and what unlocking the others takes. **Put their unlock on the wishlist** adds it.

**Blueprints.** Every engineering blueprint in the table (about 1,180: ship modules, Guardian items, Technology Broker unlocks, engineer
unlocks, synthesis recipes, and Odyssey suit and weapon upgrades). **Search** matches the module, blueprint name, engineer, effect or an
ingredient (every word you type must match), and **Module** narrows to one type. Pick a blueprint to see who offers it, its effects, and what
**one craft** takes: each ingredient with how many you need, how many you hold, and where it is found. Set **Crafts** and press **Add to
wishlist** (or double-click a row to add one craft).

**Wishlist.** Your list of blueprints, with a number of crafts each, kept on your computer for the commander who made it. For each entry it says
whether it **can be made now** and how many pieces it is **short**. Below is one **shopping list** for the whole wishlist: need, have, short and
where each ingredient is found, with what is short at the top. Each entry also says **who can do it**: an engineer you have unlocked,
or a vendor or the synthesis panel (which need no unlocking), or "No engineer unlocked yet". Select an entry to change its crafts, **Remove** it
or **Clear list** (each asks twice). The Materials row shows a line such as `Wishlist: 3 blueprints, 2 can be made, 14 pieces short`.

**Ship planner.** Work out what a whole ship's engineering takes, and put it on the wishlist in one step.

1. In **EDSY** or **Coriolis**, design the ship with its engineering and export it as **SLEF** (the Ship Loadout Exchange Format). You can also paste one
   `Loadout` line from your journal to plan your current ship.
2. In the Engineering window open the **Ship planner** tab and press **Paste from clipboard**, or paste into the box and press **Read loadout**. If
   the text holds several ships, pick one in the **Ship** box.
3. The table lists each engineered module: its slot, the module, the blueprint, the level, the experimental effect and whether it was **counted**.
   Select a row for the detail. A module with no engineering is left out. A **pre-engineered** module (it comes that way from Frontier) says so and
   takes nothing, and anything WNTB's table does not cover says **not counted** and why.
4. Optionally tick **Subtract what my current ship already has**. WNTB reads your newest journal for the ship you are flying and leaves out what it
   already holds: for a module in the same slot with the same blueprint, the grades up to its level are done (only higher ones are planned), and an
   experimental effect it already carries is done. A module that is completely done says **already done**. It only subtracts when the build is the same kind
   of ship as yours (otherwise the line under the table says so), and it assumes the build is meant for the ship you are flying: two ships of one kind
   cannot be told apart. A different blueprint in that slot is not subtracted from. If it finds no ship, the status line says so and nothing is subtracted.
5. Set **Rolls per grade**. To reach level 5 the game applies grades 1 to 5 in order, and how many rolls each grade takes depends on the game's dice,
   which the journal cannot tell, so you say how many to plan for (1 to 10). An experimental effect is one craft. The summary line shows the totals.
6. Press **Add plan to wishlist**. The same blueprint on several modules is added together. The wishlist holds 100 blueprints and 99 crafts of each; if the
   plan would pass either, **nothing is added** and the message says why. Then use the **Wishlist** tab for what you can make now and the shopping list.

Nothing is sent anywhere: the text comes from you and everything is worked out on your computer. What it cannot do: it does not know how many rolls you
need, it cannot tell which of two ships of one kind a build is meant for, and it
only covers module types in the blueprint table. The journal's names for blueprints and effects are matched to the table's from public lists
(see [Technical](../TECHNICAL.md#ship-engineering-planner-ship_planpy-ship_plan_tabpy-journal_blueprintspy)); a name it does not know is shown as **not counted**.

**Upgrade planner.** What it takes to upgrade an Odyssey suit or weapon, and to fit its modifications, onto the wishlist.

1. Open the **Upgrade planner** tab and pick the **Item**: the Artemis, Dominator or Maverick suit, or one of the Karma, Manticore and TK weapons. Or press
   **Read my gear**: WNTB reads the suits and weapons you own from your journal (the loadouts the game lists when you log in on foot, plus any upgrade since)
   and offers them in the box beside it. Picking one fills in the item, the class it is now and the modifications it already carries.
2. Set the **Class now** and the class you **Wanted** (1 to 5). The table lists each step, from the class you have to the class you want, with the materials it takes
   and the credits. A line under the table gives the total.
3. Optionally pick up to four **Modifications** (an item you read from the journal that already carries some has fewer slots left, and the ones it has are
   not offered again). The boxes offer those the table has for the item: a weapon modification marked with a family in brackets,
   such as "(Kinematic kinetic)", is only offered for that family (Karma is kinetic, Manticore is plasma, TK is laser). The table does not say whether the game
   offers every unmarked modification for every weapon.
4. Press **Add to wishlist**. Each class step and each modification goes on the list once, all or nothing (the limits are the wishlist's: 100 blueprints, 99
   crafts). The Wishlist tab then shows the shopping list: what you hold in your ship locker and what you are short of.

What the costs are, and are not:
- **The materials** are the game's current ones: the schematic, the item's family item and Manufacturing Instructions (a Health Monitor for a suit) take 1, 2, 4
  and 5 for classes 2 to 5, and the item's other two materials take 2, 5, 9 and 12. They were read from real upgrade events in the journals of play, for the Karma
  AR-50, C-44 and L-6, the Manticore Tormentor and Executioner, and the Maverick, Artemis and Dominator suits. The counts were the same for every item, so they are
  used for the rest (the Karma P-15, Manticore Intimidator and Oppressor, and the three TK lasers), but those have not been confirmed by an upgrade of their own.
- **The credits** are a unit for the item times 1, 3, 6 and 10 for classes 2 to 5 (the Karma AR-50 costs 625,000 for class 2, so 12,500,000 for classes 2 to 5 together).
  They are shown only for the eight items listed above. For the others the tab says the credits are **not recorded**, and still plans the materials.
- **A modification's engineer fee** is not in the table, so it is not counted.
- **Read my gear** is what the game last listed, not a live inventory: a suit or weapon you bought, sold or changed since the last time you logged in on foot may
  not show, and a session that never went on foot has no loadouts, so WNTB looks back through your newest journals. It reads only the commander of your newest
  journal. A modification the planner has no name for is mentioned in the status line and left out.
- The planner does not preview an item's stats.

**Engineers.** All 38 engineers (ship and on-foot, the Colonia ones included). The **Show** box above the table picks **Both**, **Bubble** (the 30 engineers in the human
bubble) or **Colonia** (the 8 in the Colonia region, about 22,000 ly away: Baltanos, Eleanor Bresa, Etienne Dorn, Marsha Hicks, Mel Brandon, Petra Olmanova, Rosa Dayette and Yi
Shen); the count beside it reads like `8 of 38 engineers`, and WNTB remembers your choice. An engineer the location table lacks (a name only your journal knows) shows under
**Both** only. Each row has where you stand (Known, Invited, or Unlocked with their rank), how many
blueprints they offer, **where they are** (base, system and planet, with "on foot" or "permit needed") and what unlocking them asks for. Until an engineer is
unlocked, the last column gives what gets you invited and what unlocks them, in words, and for an engineer whose unlock is items (such as Yi Shen's three sets)
how much of it you hold; those items can go on the wishlist. Unlocked engineers come first. **Select an engineer** for the full details under the table: how to
find them, who introduces them, what to do to be invited and to unlock them, how to gain standing with them, whether they work on foot (no ranks: every
upgrade is offered once you have met them), and any known quirk (for example, Terra Velasquez's meeting requirement is reported bugged: Covert Theft missions may
not count, Covert Heist missions do). A line below the table gives the net profit that opens each grade for a ship engineer: grade 2 at 500,000 cr, grade 3 at
2,000,000 cr, grade 4 at 8,000,000 cr and grade 5 at 16,000,000 cr (sold at their workshop; the community wiki's figures). **Show their blueprints** lists
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
| The blueprint table to be current | The recipes are a copy of EDEngineer's table, last changed in **March 2024**, with a few spelling fixes and, since October 2026, the suit and weapon upgrade costs brought to the game's current ones (from real upgrade events), five synthesis recipes corrected and seven synthesis rows and nine Thargoid-war and chip materials added from EDDiscovery's data. Neither source is Frontier's own list. A blueprint or material added to the game since may be missing, and a recipe Frontier changed may be out of date. Checked against 4,391 real blueprint crafts from the journals of one commander, every one used exactly the materials the table lists for that grade. Experimental effects are in the table as one-craft entries, but they were **not** part of that check (the journals held 143 further crafts that used them), so their recipes are less certain. | Check the in-game recipe before you spend rare materials, and report a difference. |
| Which upgrades each Colonia engineer offers to be certain | EDEngineer's table (March 2024) lacks the four **Colonia on-foot engineers** (Baltanos, Eleanor Bresa, Rosa Dayette and Yi Shen). Their places and unlock steps are in EDDiscovery's table, and which suit and weapon upgrades each offers follows EDCoPilot's engineer list as applied in the author's ED-DDT; other sources may differ, and none is Frontier's own list. Yi Shen's unlock is the three sets of items handed to the other three. | Check what an engineer offers in the game's Engineers panel before you spend items on it, and report a difference. |
| Engineer places and steps to be current | They come from EDDiscovery's table and can drift when the game changes. Yarden Bond's meeting requirement says 5 Smear campaign plans (EDDiscovery has 8; the wiki and Inara say 5), while the blueprint table's "Unlock" row for him, which is EDEngineer's, asks for 8 to be handed over: the sources disagree on that step. | Check the engineer's requirements in the game's Engineers panel. |
| What unlocking an engineer takes to be complete | The table lists the **materials or goods** an engineer asks for. An invitation can ask for more (a rank, a visit, a referral), which it does not list. | Check the engineer's requirements in the game's Engineers panel. |
| Your materials to match the game after every pick-up | The journal reports almost every gain, but not all of them: replaying real journals, WNTB's counts matched the game's next login list 97% of the time when the game was restarted within ten minutes (737 of 761), and 93% over all gaps (the rest are mostly play on another computer). The misses that remain are exactly 5 more of several materials in the game with no event in between. | The next login list corrects the counts. |
| The Engineering window to know how many crafts you need | The game rolls the result of each craft; nothing in the journal says how many it will take. | Set the number of crafts you expect. |
| On-foot upgrades to count your backpack | The wishlist counts the **ship locker** only. Whether the game also draws on the backpack is not confirmed. | Stow what you carry into the ship locker (or just check the count in the game). |
| The trader finder to say what a trade would give you | It finds the stations. The rates a trader offers are not in the journal or in Spansh's data, so WNTB does not show or work out a rate. | Check the rate at the trader before you swap. |
| The trader finder to be current | The list is Spansh's, from what players have reported: a station can have lost its trader or be closed to you (a permit, a faction state). | Check the station when you arrive; the `Pad` column is the largest pad Spansh knows. |
| Ship Builds to be checked | WNTB only stores the link and name you give it. It doesn't read or check the build. | Keep your link current if the site changes. |

