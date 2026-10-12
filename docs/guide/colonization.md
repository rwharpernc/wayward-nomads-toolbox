# Colonization

Colonization has its own mode: press the **COL** button. The page has two parts, the project you are building now and
your history, and a **REPORT** button that opens the full sites window. It works the same for a commander with a fleet
carrier and for one without; the wording changes to match, and the carrier lines are left out when you have none.

> **Work in progress.** Co-op building (several commanders on one project) and colony tracking are planned, through a separate
> app that is in development. For now this page is about your own deliveries, ship and carrier, and details may change.

**On this page:** [The COL page](#the-col-page) · [Tracking a site](#tracking-a-site) ·
[The Colonization Sites window](#the-colonization-sites-window) · [Where to buy](#where-to-buy) · [Planned builds](#planned-builds) ·
[The shopping list on the overlay](#the-shopping-list-on-the-overlay) ·
[What the game does and doesn't tell us](#what-the-game-does-and-doesnt-tell-us-and-how-to-work-around-it)

## The COL page

**Current project** is your most recently updated active site:

| Line | What it says |
|---|---|
| Name, system and a bar | The site, and how far its build has come (the bar turns green when the build is complete) |
| Progress, Delivered, Still needed | The build's percentage, the tons handed over by everyone against the tons it needs, and what is left |
| Covered | Of the commodities still needed, how many are **fully** covered, **partly** covered and **not yet** covered, counting your ship, or your ship and carrier together if you have one |
| On hand | Tons of needed commodities in your ship now |
| Carrier | (Only with a fleet carrier.) Tons of needed commodities you have moved onto it |
| Still to get | What is left to buy or mine after your ship (and carrier) |
| Trips left | **Without a carrier:** the loads of your current ship it takes to finish (one trip buys and delivers). **With a carrier:** trips to buy what is missing and trips to haul everything to the site |
| Biggest gaps | The four commodities with the most still to get |
| Next | One sentence on what to do now |

**History** is yours alone (everything is per commander):

| Line | What it says |
|---|---|
| Sites | How many tracked sites are done, in progress and failed |
| You delivered | The tons and number of deliveries you made |
| Recently | Tons in the last 7 and 30 days |
| Last 14 days | A row of blocks, one a day (oldest first), as tall as that day's tons against your busiest of the 14; a dot is a day with nothing delivered. The peak is named beside it |
| Best day | Your biggest single day |
| Busiest site | The site you delivered the most tons to, with the tons |
| Claims | How many systems you have claimed (`ColonisationSystemClaim`), how many of those you released, and how many colonisation beacons you deployed. Counts only: the game does not say when a claim ends, so WNTB does not list which systems are still yours |
| Most delivered | Your top three commodities |
| Average build | Days from the first time WNTB saw a site to the day the depot reported it complete, over the sites for which both are known |
| Note | "Counted since [date]": the first delivery WNTB has counted |

**How far back the history goes.** The game does not keep a delivery history for a plugin to read, but your journal files
do. The first time WNTB sees a commander it reads **all** of that commander's journals once, in the background, and
rebuilds the history from every delivery in them, so it reaches back as far as your journals do. After that it counts each
delivery as it happens, and when EDMC starts it catches up from the recent journals (14 days, or back to your oldest active
site, never more than 30). If you have deleted old journals, the figures can only go back as far as what is left; the
page says what date it is counting since, and a rebuild never replaces figures that are larger than it can find. A site's build time is only known for a site WNTB saw
being started or finished after this version; for the others the average leaves it out. The tons at the top
("Delivered") are everyone's, because the game reports them for the whole depot; "You delivered" is yours only.

## Tracking a site

Keeps track of what each colonization construction site still needs delivered. You can read it from anywhere, not
just while docked, and it shows what's left to find after counting the cargo already in your ship. There is no
on/off setting for it.

**Where the data comes from.** The journal writes a `ColonisationConstructionDepot` event when you dock at a
construction depot or open its market, and a `ColonisationContribution` event each time you hand cargo over.

**To start tracking a site:**

1. Dock at the construction depot, or open its market, **once**. There is nothing to type in.
2. The **COL** page shows that site under **Current project** (see below). It is your most recently updated active
   site, with a line `+N more active sites` if you have others. With none it says `No active construction site`.
3. Press **REPORT** to open the **Colonization Sites** window.

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

## The Colonization Sites window

Sites are listed on the left (name, tons left, and its progress as a percentage, or `complete` or `failed`);
finished ones are grayed out. The subtitle reads `<commander> — N active of M sites`. Click a site to see it on the right:
its name, system, a progress bar, six totals, two filters and a table with one row per commodity **still
outstanding**. The first active site is picked when the window opens.

The totals are always for the whole site, whatever the filters hide:

| Total | Meaning |
|---|---|
| t still to get | What you still have to buy or mine: Remaining, less what is in your ship and what you have moved onto your fleet carrier |
| t on your carrier | Of the remaining need, what you have moved onto your fleet carrier (never more than the site needs). A dash without a carrier |
| t already in your ship | Of the remaining need, what your ship is carrying now (never more than the site needs) |
| t ship capacity | Your current ship's cargo capacity, as EDMC reports it. It follows you when you swap ships; a dash until EDMC has given it |
| trips to buy | Loads of that capacity to gather what is **still to get**, rounded up. **0** once everything is in your ship or on your carrier |
| trips to haul | Loads of that capacity to carry **all** the tons the site still needs to the site, rounded up. What you carry is the start of the first load, and what is on your carrier still has to be carried over, so this does not fall when you move cargo to the carrier |

Building a colony has two legs, and the window counts them apart. **Buying** takes cargo from the markets to your carrier (or
straight to the site). **Hauling** takes it from the carrier, or your ship, to the construction site. A commodity you have
already stored on the carrier needs no more buying trips but still needs its hauling trips.

The **Filter** box keeps the commodities whose names contain what you type, and **Hide rows already covered**
drops the rows you needn't buy any more (see the colors below for what counts as covered). **Only what [station] sells**
keeps just the commodities the station you are docked at has for sale: open its commodity market once and the box
names the station and becomes usable. It switches itself off when you leave the station.

Click a column heading to sort by it, and again to reverse; the default is alphabetical, so rows stay put while numbers change.

| Column | Meaning |
|---|---|
| Required | What the site needs in total |
| Delivered | What's been handed over |
| Remaining | Required minus delivered |
| In Cargo | What is in your ship (or SRV) now |
| FC | Tons of that commodity you have transferred onto your **fleet carrier** (only shown once WNTB has seen you have one) |
| Buy Trips | Loads of **your current ship** to gather what is still missing of that commodity: what is left to get (Remaining less your ship and your carrier) divided by your ship's cargo capacity. **0** when you already have enough, wherever it is stored |
| Haul Trips | Loads of your current ship to carry all of that commodity's Remaining to the site. This stays above 0 for a commodity sitting on your carrier, because it still has to be moved |

Both trip columns use at most two decimals (`4`, `1.5`, `1.25`, `0.33`), never round a small remainder down to 0, and show a dash
until EDMC has given your ship's capacity.

**Row colors.** The whole row is tinted by what you already have for that commodity, counting your ship **plus** what
you have moved onto your fleet carrier (the FC column):

- **Green:** the two together cover what the site still needs, exactly or with room to spare. Nothing more to buy.
- **Orange:** together they are **more** than the site still needs.
- **No tint:** you are still short. This is the normal look while you work on it.

The carrier figure is what WNTB saw you transfer (see the FC column notes), so it can drift from the carrier's real
cargo. The **t still to get** total and the copied shopping list count it too, so they drop when you move cargo onto the
carrier, and so does Buy Trips. Haul Trips does not: everything still has to be carried to the site, whatever is stored where.

**The FC column.** It adds up the journal's `CargoTransfer` events made while docked at your fleet carrier: tons
moved to the carrier minus tons moved back to the ship. It appears for a commander WNTB knows has a fleet carrier, using the **same knowledge as Trade**: your
choice for that commander in the Trade settings (None, Fleet, Squadron, Both or Auto) decides when it names the
carriers, and on Auto a fleet carrier Trade has recorded counts (it reads your recent journals at start-up and
remembers them). Failing that, it appears once WNTB has seen one of yours itself (a transfer, opening Carrier
Management, buying one, or docking at one). It is per commander. It does lower the **t still to get** total.

- **Transfers made with EDMC closed are found.** They are in the journal, and at start-up WNTB reads the recent
  journals and adds any transfer it hasn't counted. A transfer is never counted twice, even if EDMC also saw it live.
- **How far back it reads:** 14 days, or back to the last transfer it counted if that is older, never more than 30.
  Transfers older than that are never counted, so stock you moved to the carrier before then won't show. Taking
  stock back off the carrier that was moved before then just leaves the figure at zero.
- **It is what WNTB saw you transfer, not the carrier's actual hold.** Changes that are not transfers are not in the
  journal as transfers, so they are not counted: buying from or selling to the carrier's market, trade orders, and a
  squadron mate moving cargo. The figure can therefore drift from the real contents.

## Where to buy

Under the commodity table, **Where to buy** finds the closest places to buy a commodity. Click a commodity row, check
the options and press **Find nearest**. It asks [Spansh](https://spansh.co.uk) (a community-run map of the game), so it
needs an internet connection, and nothing is fetched until you press the button. Only the commodity name and the
system you search around are sent.

| Option | Meaning |
|---|---|
| Around | The system to measure from. It starts as the site's system; type another, or press **Here** for the system you are in now |
| Within | How far to look: 25, 50, 100, 200 or 500 ly, or no limit. Default 50 |
| Sort | **Closest first** (default) or **Cheapest first**. This decides which stations Spansh returns, not just their order. Click a result heading to re-sort what came back |
| Landing pad | **Any size** (default), **Medium or larger**, or **Large only**. Any size lists stations whose biggest pad is small, so you can swap to a smaller cargo ship when a commodity isn't sold at a large-pad station. The **Pad** column shows each station's largest pad |
| Include fleet carriers | Off by default. When ticked, carriers are searched separately and listed under their own **Fleet carriers** heading after the stations |

The options are **remembered** (within, sort, landing pad and fleet carriers) for the next time you open the window. The
search system is not: it starts as the site's system again.

**Find all** searches every commodity you still have to buy, using the same options, and lists the closest 5 stations
(and, if carriers are ticked, the closest 2 carriers) under a heading for each commodity. It follows the table as you
have it filtered: rows already covered are left out, and so are rows the Filter box or **Only what [station] sells** hide.
Spansh can only look up one commodity per request, so it sends one request per commodity, about half a second apart; a
list of 20 takes some seconds, and the note under the buttons shows how far it has got. Press **Stop** (the same button)
to stop after the search in progress, keeping what it found. A commodity that fails is named and the others still
show; press **Find all** again to retry. Commodities with no source in range are listed in the note.

**Suggested route.** Find all also works out a shopping route and puts it first in the results: the few stops (at most 6) that
between them supply the most of what you still have to get. A station that sells several of your commodities counts for all of
them, so it is taken first; ties go to the nearer, then the cheaper. Each stop shows what to buy there and the price, and the stops
are listed nearest first, which is the order to fly them. What no station in range can supply is named in the note. It only
considers the stations Find all returned (the nearest 25 per commodity within your radius), and stock changes, so treat it as a plan
to check on arrival. **Copy Route** copies it as plain lines to paste into a note or chat.

Each result shows the station, system, type, whether it is **Planetary**, largest pad, distance in light years,
distance from the arrival star, the price per ton and the stock. **Planetary: Yes** means a base on a planet's
surface, so you have to descend to land (planetary ports and outposts, settlements); **No** means an orbital
station, asteroid base, megaship or fleet carrier, which you dock at in space. Click the heading to sort by it. **Copy System** copies the selected row's system name, to paste into the galaxy map.

Things worth knowing:

- Only stations whose market was updated in the last 7 days are listed, because older figures are probably out of date.
  The prices and stock come from players' own market updates, so confirm on arrival.
- A fleet carrier can move or sell out at any time, and its prices are set by its owner, which is why carriers are
  opt-in and kept in their own section.
- A station for which Spansh gives no pad figures is kept in the list (its Pad shows `?`) rather than hidden.
- If Spansh is busy or unreachable, the panel says the search failed; try again shortly. Nothing else in WNTB is affected.
- The search looks for stock that is **for sale**. It does not know what a station's market will have tomorrow.

**Buttons.** They act on the site picked on the left:

- **Copy Shopping List** copies that site's list to the clipboard, as lines like `1,200 t  Steel`, biggest first.
  The amounts are the **t still to get** figures, so what is on your ship and on your carrier is taken off. If nothing is needed it says
  so.
- **Remove Site** stops tracking that site.
- **Remove Finished** deletes every complete or failed site.

## Planned builds

The journal only reports a construction site once you have docked at it, so a build you have only **planned** never appears
in WNTB. Press **Planned Builds** (top right of the Colonization Sites window) to see what [Raven Colonial](https://ravencolonial.com),
the community planning site, has for the selected site's system: every site there with its status (**Building**, **Planned**,
**Complete**), its type and the body it is on, building first. The top of the window also names the system's **architect** (the
commander who planned it there) and whether Raven Colonial has it **open** or **locked**, as Raven Colonial reports them. A site you have docked at and WNTB tracks is marked **yes** under
*In WNTB*.

For a planned or building site it also shows the **full cost**: the tons the whole building needs, from a table of what each kind
of building costs that is bundled with WNTB (compiled by SrvSurvey's author, see the Acknowledgements). Click a row to see its
building and its five biggest commodities in the footer, and the top of the window adds up what all the *planned* builds in the
system will need. The table is a snapshot: if the game changes a building's cost, it can be out of date until WNTB is updated, and a
building the table does not know shows no cost.

It asks Raven Colonial once, when the window opens or you press **Refresh**, and sends only the system's name (nothing about you
or your deliveries is ever sent). The answer is remembered for a minute. It shows what *other people* have entered there, so a
system nobody has planned on that site shows nothing. See [what goes on the internet](internet-and-privacy.md).

## The shopping list on the overlay

Optional, and **off by default**. It needs an overlay running; see [Setting up the overlay](../OVERLAY_SETUP.md). Turn
it on in **Settings → Overlays → Colonization**: **Show the shopping list on the in-game overlay**.

It draws a table, with the site name as its title and the columns **Commodity**, **Required**, **Remaining**,
**FC**, **Cargo** and **To buy**:

- **Required** is the site's full requirement for that commodity.
- **Remaining** is what the site still requires (required less delivered). It does **not** drop as you load up, so you can
  see what you need and what you have side by side. It falls when you deliver.
- **FC** appears only if you have a fleet carrier (see the FC column above): what you have moved onto it. It is blue
  once it covers the remaining amount, gray while it doesn't, and blank when none.
- **Cargo** is what is in your ship's hold right now, so you can see what you just bought. A **✓** after the name means
  your hold **plus** what is on your fleet carrier already covers it (the row turns green, the same rule as the
  window's green rows); the row turns amber if together they are **more** than the site needs.
- **To buy** is what is left to get after your hold and your carrier (remaining less both). Blank once it is covered.

Commodities are alphabetical so rows stay put while numbers change. A last line gives the tons remaining and the
trips in your current ship, and they need your ship's cargo capacity, which EDMC supplies. **With a fleet carrier** it gives both legs, as
the COL page and the window do: `► 32,769 remaining  ► 21 to buy  ► 33 to haul`. **To buy** is the loads to gather what is still to
get after your ship and your carrier (0 once it is all stocked); **to haul** is the loads to carry everything still needed to the
site. **Without a carrier** there is one figure, `► 32,769 remaining  ► 33 trips to finish`, since one trip buys and delivers.

- **When it shows:**
  - In a **commodity market** at a station. It hides when you leave the screen, open another service such as
    outfitting or the shipyard, or undock. Backing out of the market to the station-services menu can't be detected, so
    the card stays until you leave that menu.
  - At **your own carrier**, in the station-services screens. The game writes nothing when you open a carrier's market,
    so any services screen shows it there, except after the carrier's outfitting or shipyard screens (which are
    logged).
  - Whenever you are **docked at a carrier** and have the **right-hand cockpit panel** open (where your cargo is and
    where you transfer to the carrier). The game writes nothing when you open that, so the open panel is what WNTB
    goes by; it hides when you close the panel or undock.
  - Whenever you are **docked at a construction site** (looking out of the cockpit or at the station services, but not
    in a map or another panel).
  - In the carrier's **Carrier Management** screen. The game announces both opening and closing it, so the card
    appears and goes exactly with the screen.
  - Optionally, **whenever the right-hand cockpit panel is open, anywhere** (even in flight). Off by
    default; tick it in the Colonization settings.

  And you can always force it: the **OVERLAY** button beside REPORT on the COL page (it lights up while forced on; press it again to let go) puts the card on the overlay
  now, whatever screen you are on, even if the overlay option is off; the button then reads **HIDE**. It lasts until you
  press it again or restart EDMC.

  Most of these rely on the game's `Status.json` reporting which screen is open.
- **Which site:** your most recently updated active site, the one the Colonization mode summary line names. Completed and
  failed sites are never shown. The card disappears when nothing is left to get.
- **Settings:** where the card sits (Settings → Overlays → Overlay Placement; the default is the left edge, vertically
  centered, on any screen shape), and **Rows**,
  how many commodities to list (1 to 60; any more are summarized as `+N more`). The default, 0, lists them all. **Test Overlay** shows a
  sample card for a few seconds, even while the option is off.
- It is cleared when EDMC closes. If the overlay program isn't running, nothing is drawn and nothing breaks.

## What the game does and doesn't tell us, and how to work around it

| What you might expect | What the game gives | What to do |
|---|---|---|
| Everything on your carrier to count | The journal only records cargo you **transfer** to or from the carrier. Stock that arrived any other way is invisible to it. Frontier's carrier data lists the real hold, but only when EDMC is signed in, and it is fetched when you open Carrier Management (or about every 15 minutes) and can lag. | Sign EDMC in to Frontier, then open Carrier Management once; the Covered line and the Carrier row then follow the real hold. |
| Colonization sites to appear on their own | The game writes the depot event only when you **dock or open the depot market**. A delivery to a site WNTB has never seen a depot snapshot for is ignored. | Dock at the depot (or open its market) once for each new site. Docking again replaces WNTB's figures with the game's own. Deliveries made with EDMC closed are caught up from the last 14 to 30 days of journals at start-up. |
| A site to have its real name | The name is taken from the last time you docked at that market. Otherwise it is `Construction site <number>`. | Dock at the market once to pick up the name. |
| A full history of everything you ever delivered | The journal records each delivery as it happens. WNTB rebuilds your history once from every journal file you still have, so deliveries from journals you deleted are missing. | The history counts from the first delivery it found (shown on the page) and keeps growing. |
| Your teammates' work on the same project | The depot reports only the project's totals, not who delivered what. | Today the page shows your deliveries and the project's overall progress. Team support is planned. |
