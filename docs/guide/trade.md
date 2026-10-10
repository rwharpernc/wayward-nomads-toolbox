# Trade

Trade is about buying and selling: what you've earned after fuel and repairs, how much of your cargo is still
unsold, your ship hold and your carrier's space, and where to find the best routes and prices.

It has three pages. Use the large orange **◀** and **▶** buttons at the top of the panel to move between them:

| Page | What it's for | Needs internet? |
|---|---|---|
| **Session** | Your running profit, costs, hold and carrier cargo | No |
| **Routes** | The best trade routes from where you are | Yes (Spansh, off until you tick it) |
| **Market** | Where to sell or buy a commodity | Yes (Spansh, off until you tick it) |

A pop-out **Trade History** window keeps the sessions you choose to save.

Each page is laid out in sections (orange headings with a rule between them), with label-and-value rows and tables
whose numbers line up in columns. Long station names wrap instead of being cut off. A page's buttons are at the top,
under the page arrows.

**On this page:** [How a trading session works](#how-a-trading-session-works) ·
[The Session page](#the-session-page) · [Trade History](#trade-history-saving-sessions) · [Routes](#routes) ·
[Market](#market) · [Fleet and squadron carriers](#your-fleet-carrier-and-squadron-carrier) ·
[Using Trade on two computers](#using-trade-on-two-computers) · [Settings](#trade-settings)

## How a trading session works

**A session is your running tally, and it belongs to a commander.** It starts the first time WNTB sees you and lasts
**until you press Reset**, however many times you log in or restart EDMC. That is what makes a long job, such as
loading a fleet carrier over several evenings, one session.

- **Each commander has their own.** Switching commander never loses anyone's tally.
- **Playing with EDMC closed is fine.** The next time EDMC sees that commander, WNTB catches the session up from the
  game's journal files and adds what it missed. It only adds what is new, so it can't count anything twice. (On
  Linux this needs EDMC's **Journal directory** to be set; see [WNTB on Linux](linux.md#step-2-tell-edmc-where-elites-journals-are).)
- **Only what WNTB has seen is counted.** Trades made before WNTB first ran, or in a session you reset, aren't
  included.
- **Nothing is kept for good unless you ask.** Press **Save session** to put it in Trade History.

### Finishing a session and starting the next

There is no Start or Track button, because tracking never stops. Instead:

1. Press **Save session** to copy the tally into Trade History. The tally keeps running, and the button stays
   **Save session** (saving again updates the same entry).
2. Press **Reset** to begin a new session. If the current one has unsaved trades, it offers to save first.

> **If you skip Reset, your next trades are added to the old session.**

**Example.** You spend Saturday hauling Tritium to your carrier. Saturday night: **Save session**, then **Reset**.
Sunday you do a mining run and sell the lot: that's a fresh session with its own profit figure, and Saturday's is
safe in History.

## The Session page

It reads your journal only. Nothing is sent anywhere. Top to bottom:

**Profit.** Trade profit is what you were paid minus what the sold tonnes cost you, as the game reports it. Stolen or
black-market cargo counts the whole sale. Credits per hour appears once you've traded for a few minutes (it uses
first trade to last trade). You also see tonnes bought and sold and your best-selling commodities.

**Running costs**, so the profit is honest:

- **Fuel** (refuelling)
- **Repairs**
- **Advanced maintenance** (the game logs it as a repair that includes module "Wear"; the whole charge goes on its
  own line)
- **Rearm** (ammunition, and restocking an SRV or fighter)
- **Limpets** (bought, less any sold back)

Once you've spent anything, the headline becomes **Net profit** (trade profit less those costs; the credits per hour
is the net), with the trade profit and each cost listed under it. Insurance rebuys and fines aren't counted, and a
cost only counts once WNTB has seen it.

**Ship hold.** Your ship and the landing pad it needs (for example "Type-9 Heavy, large"), how many tonnes are used,
the capacity and how much is free, what the station you're docked at would pay for the whole hold, and what each
commodity aboard would sell for there.

**Carrier cargo.** Your carrier's cargo storage, shown as **Carrier cargo used**, **Carrier cargo free** and
**Carrier reserved for orders**, so it is never mistaken for your ship hold. Only shown if you have a carrier; see
[below](#your-fleet-carrier-and-squadron-carrier).

### Buttons

- **Reset**: starts the tally again (asks whether to save first if there are unsaved trades).
- **Save session**: keeps the session in Trade History. Greyed out until there is something to save.
- **History**: opens the Trade History window.
- **Rebuild** (second row): recounts the session from the journals starting at a time you give, in UTC, as
  `YYYY-MM-DD` or `YYYY-MM-DD HH:MM`, and replaces the tally. Use it when the session began on another computer.
  It asks first if the current tally is unsaved.

## Trade History (saving sessions)

Press **Save session** to keep a session. You can keep trading and press it again; that updates the same entry
instead of adding a second one. **Reset** starts a new session, which becomes a new entry if you save it.

Press **History** to open the **Trade History** window. It has a drop-down at the top to pick a saved session
(newest first), and, with more than one commander, a commander filter. The tabs:

| Tab | What it shows |
|---|---|
| **Overview** | Net profit, trade profit, running costs, net per hour, tonnes sold and trading time at a glance. Then commander, ship, start and end, balance at start and when saved, tonnes, profit per tonne, margin, jumps and light years, profit per jump and per light year, and each running cost's share of sales. |
| **Commodities** | For each one: tonnes bought and sold, what you paid and received, average buy and sell price, profit, margin, profit per tonne and what was left unsold. |
| **Stations** | The same, added up for each station you traded at (visits, bought, sold, profit, costs, net). |
| **Route** | The stations in the order you flew them, with what was bought and sold at each, the net on that visit and a running net. Going back to a station later is a new visit. |
| **Trades** | Every purchase, sale and cost with its time, price, total, profit, station and system, 200 at a time. |
| **Stock & carrier** | What was bought but not sold (a journal **estimate**), the ship hold, and your carrier's cargo space when you saved. |
| **Lookups** | The Spansh routes and market searches you made during the session, and the best result of each. |

Buttons: **Copy summary** puts a plain-text report on the clipboard, **Export log (CSV)** saves the full trade log
to a file you choose, and **Delete session** removes a saved session (it asks first).

**Good to know:**

- The balance change is your real credits difference, so it also includes anything else you earned.
- Times are UTC.
- A session keeps its most recent 5,000 trades and costs. The totals are always exact.
- History is kept in `trade_history.json` in the WNTB plugin folder, which updates leave alone.

## Routes

*Needs the Spansh lookups switched on (Settings → WNTB → Trade).*

**Find routes** asks Spansh for the most profitable trade route from where you are.

**What it uses:**

- *Start:* the station you're docked at, or the last one you docked at.
- *Cargo size and credits:* from the game.
- *Jump range:* your ship's **unladen** range. Lower it in Settings if a full hold jumps shorter.
- *Pad size:* if your ship needs a large pad, only stations with one are considered.

Before you search, the page shows what it will use (start, ship, cargo, jump range, budget), so you can check it.

**Fleet carriers:** Spansh's planner doesn't know them, so a route never starts from one. If you're docked at your
carrier, it starts from the last real station you docked at, and the page says where. If Spansh refuses a search,
the page shows its reason.

### Hops

The **Hops** button cycles the route length through 2, 3, 4 or 5 (the same setting as in Settings).

**2 hops** is the choice for a back-and-forth pair. When the route ends at the station it started from and every leg
carries cargo, the result is headed "repeatable loop" and says you can fly it again. Otherwise the page says why it
isn't one. A leg with no cargo is flagged.

### Round trip

Spansh's planner returns the best *chain*, which doesn't always come back. **Round trip** finds the best
back-and-forth pair itself.

How it works, in plain terms:

1. It asks Spansh for the markets of the nearest stations (up to 300, within twice your jump range, but never less
   than 20 ly or more than 100 ly).
2. For each neighbour, it works out what to carry out and what to bring back.
3. A pair only counts when **both legs make a profit, so you never fly empty**.
4. Each leg fills the hold with the most profitable commodity first and tops up with the next, limited by the supply
   where you buy, the demand where you sell and what you can afford.
5. Pairs are ranked by estimated profit per hour, and the top three are shown with what to carry each way.

It uses the same filters as Find routes (price age, ground facilities, fleet carriers, your ship's pad size,
distance from the star), plus the **least supply** and **least demand** settings (200 t each by default), so thin
markets are left out. It takes about 20 seconds and makes one to three Spansh requests (100 stations each).

### Reading the result

Spansh can take a minute or two. **Cancel** stops waiting. The result shows:

- the route's total profit and an **estimated profit per hour**,
- each hop: stations, system, distance, best commodity and profit, with the supply at the buying station and the
  demand at the selling one (the first four are shown, with "+N more" after).

**Copy next system** puts the first destination on your clipboard so you can paste it into the galaxy map.

## Market

*Needs the Spansh lookups switched on.*

Finds where to **sell** or where to **buy** a commodity.

1. **Choose Sell or Buy** with the buttons under the Commodity box (the lit one is chosen). It is remembered.
2. **Pick a commodity.** Click the **Commodity** box and start typing. Suggestions fill in as you type: first what
   you carry and what the station you're at buys, then every commodity.
   - When *selling*, you can leave it empty to search for the commodity you carry the most of.
   - When *buying*, type what you want.
3. **Press Near me** to look within a radius of your system (100 ly unless you change it), or **Galaxy** to look
   everywhere. You can press both.

**Example.** You're hauling 200 t of Palladium and want to sell. Leave the box empty (it picks Palladium), press
**Sell**, then **Near me**. You get a list of stations within 100 ly ranked by what your whole load would earn.

### How results are ranked

- **Selling:** by what *your load* would earn: price per tonne times the tonnes the station still wants. A station
  paying more per tonne but wanting only 40 t is worth less to a 200 t hold. If you haven't got any of it, a full
  hold is assumed.
- **Buying:** the amount is your *free hold space*. Stations that can supply all of it come first, cheapest first.
  Stations that can only supply part come after, marked "only N t in stock".

Once you've run both searches (near and galaxy), it tells you which is better and by how much (more money when
selling, a lower price when buying), and how much further away it is.

### What each result tells you

Every result says what kind of place it is: **orbital** or **ground** (on a planet's surface), the station type
(Coriolis Starport, Planetary Outpost and so on), and how far it is from the arrival star in light seconds. Stations
with no landing pad your ship fits are left out.

### Fleet carriers in results

**Fleet carriers are listed in their own section**, marked "they can move", because a carrier can jump away before
you arrive. They are asked for separately and weighted about one carrier to every three stations, so cheap carriers
never crowd the real stations out of the list. A line says when a carrier would beat the best station.

In **Settings → WNTB → Trade** you can stop searching for fleet carriers, for **ground facilities** (planetary ports
and outposts, and settlements), or both, which leaves only stations in space.

### Price finder

Opens the finder that Mining's **PRICE** button also uses, for any commodity, to buy or sell, with its own distance
box.

> **Prices are only as fresh as the last player who docked there.** Markets older than 30 days are ignored. Check the
> market when you arrive.

## Your fleet carrier and squadron carrier

Not every commander has a carrier, and some have a fleet carrier, a squadron carrier or both. Under
**Settings → WNTB → Trade**, each commander WNTB has seen gets a choice:

**Auto** (show whatever your journal has revealed) · **None** · **Fleet** · **Squadron** · **Both**

Nothing is shown for a carrier you haven't chosen. For each one, the Session page shows cargo used, free, and
reserved for orders, for example "5,060 / 23,720 t used, 18,660 t free".

### How the number stays up to date

The game only reports a carrier's space when you **open Carrier Management**, so do that once. WNTB also reads your
recent journal files when it starts, so it finds the last time you did, even if EDMC was restarted since.

After that:

- It follows your cargo transfers. A transfer is counted for the carrier you're **docked at**, so docking at
  someone else's carrier never changes your figure.
- Reserved space, and anything your carrier does itself (trade orders, sales), only update the next time you open
  Carrier Management.

**To get the real, exact cargo figure, open Carrier Management** (the carrier's management screen, where you see its
services and cargo). The game writes a fresh report of the whole inventory and WNTB shows it within a couple of
seconds. Nothing else in the game's files lists what is in the carrier's hold, so there is no other way to read it.

### Quirks worth knowing

- **A `~` before the figure** (for example `~23,720 / 23,720 t`) **means an estimate.** The transfers WNTB has seen
  add up to more than the carrier can hold (or take out more than it holds), so cargo left the carrier without the
  game writing anything down, usually a trade order or a sale made from the carrier. A note under the figure says
  so. Open Carrier Management and the `~` goes away.
- **Playing on another computer, or with EDMC closed, leaves the figure stale** until the journals are copied over
  and read, and even then it is only as good as the last time you opened Carrier Management.
- **The figure can look wrong right after you unload.** The unload is in the journal but the total is not. Open
  Carrier Management after a big load to put an exact number back.

## Using Trade on two computers

If you play on more than one computer (say Windows and Linux), each one keeps **its own** Trade records. The game's
journals are the only thing that has to travel between them, and WNTB reads them for you.

**What lives on each computer** (files in the WNTB plugin folder, never shared):

| File | Holds |
|---|---|
| `trade_ledger.json` | the session tally |
| `trade_stock.json` | the stock list |
| `trade_carrier.json` | the carrier figures |
| `trade_history.json` | saved sessions |
| `trade_journal_scan.json` | the list of journals already read |

Copying these between computers is not needed and not recommended.

### What to do

1. **Copy the journal files** from the computer you played on into the other computer's journal folder (the one
   EDMC's **Journal directory** points at). Copy them all, not just the newest. Copying a file that is already there
   is fine. Doing it while the game is closed is best, because a file that is still being written is read again
   later.
2. **That's it.** WNTB looks for journal files it hasn't read **a few seconds after EDMC starts and then once a
   minute**. It reads each new file (and any file that has grown since) once, and adds its trades, costs, stock and
   carrier transfers to this computer's records.

   The foot of the Session page tells you how it's going, for example: *"Journals read: 85 file(s). Last check
   08:12 UTC, 1 new or grown."*
3. It only ever **adds what is new**. Reading a file twice, or out of order, never counts anything twice and never
   overwrites a newer carrier figure with an older one.

### Things that are not obvious

- **The file you are playing right now is left alone** (EDMC already delivers its events live). It is read on a
  later look, after the game has moved on to a new file or after EDMC restarts.
- **The first time, only the 80 newest files are read.** Older history is not crawled. If your session began before
  that, use **Rebuild**.
- **A session that began on the other computer is not copied, only the journals are.** If this computer first met
  the commander partway through, its tally starts from there. Press **Rebuild** on the Session page and give the
  date and time (UTC) the session began. WNTB recounts the journals from then on and replaces the tally. Check the
  totals against the other computer, adjusting the start time until they match, then **Save session** if you want to
  keep it.
- **Reset and Save session only affect the computer you press them on.** Press Reset on both if you start a fresh
  session.
- **Carrier cargo only becomes exact when you open Carrier Management.** Copying journals does not change that.

## Trade settings

**Settings → WNTB → Trade**:

| Setting | Default | Notes |
|---|---|---|
| Enable Spansh trade lookups | Off | The Routes and Market pages do nothing without it. |
| Route hops | 3 (range 1 to 10) | Also set by the **Hops** button. |
| Max distance from the star | 5,000 ls | For Routes. |
| Jump range override | blank | Blank uses your ship's unladen range. |
| Only stations with a large landing pad | | For Routes. |
| Round trip: least supply / least demand | 200 t each | Leaves thin markets out. |
| Routes: ignore prices older than | 72 hours (0 = any age) | |
| Routes may use systems that need a permit | Off | |
| "Near me" price search radius | 100 ly | |
| Include fleet carriers / ground facilities | On / On | Applies to prices **and routes**. |
| Ship size (landing pad) | From my ship | Or Small, Medium or Large if it guesses wrong. |
| Carrier choice, per commander | Auto | See above. |

See [what goes on the internet](internet-and-privacy.md) for exactly what is contacted, and the
[Trade specification](../TRADE_TECH_SPEC.md) for how it all works.

Stuck? See [Troubleshooting](troubleshooting.md#trade).
