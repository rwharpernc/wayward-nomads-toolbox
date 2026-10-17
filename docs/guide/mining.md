# Mining

Mining mode tracks two kinds of mining, plus your own catalog of known hotspots:

- **Space Mining**, in your ship.
- **Surface Mining**, in the Rhino SRV.

Use the **◀** and **▶** buttons at the top of the panel to switch between the two pages. Each page shows live stats
for your current run.

> **Where this comes from:** the journal records what you prospect, refine and collect, but not a ring's deposit amounts or density, which you type in. The hotspot catalog is your own, and ring reserve and hotspot lookups use what players have uploaded to EDSM and Spansh. See [How WNTB knows what it knows](README.md#how-wntb-knows-what-it-knows).

## What each page shows

Lines come and go with the settings listed at the end of this page.

**Space Mining** (in your ship, from undocking):

- your cargo, and the ring you are at with its reserve level (once *Enable EDSM ring reserve lookup* is ticked and EDSM knows it);
- **Asteroids prospected**, with how many of each content grade, and the **materials seen** in them;
- **Asteroids cracked** (core mining);
- **Limpets launched** by type, with an approximate count still on board (bought less launched);
- **Refined**, by commodity (with the mining method that usually suits it, when prospector hints are on) and the **Refining rate** in refinements a
  minute, worked out from the last 10 seconds;
- a **Paused** note while you are in supercruise.

**Surface Mining** (in the Rhino SRV):

- whether the Rhino is deployed or stowed, its cargo and your ship's;
- **Refined**, the **Refining rate**, what was **Transferred to ship** and the **Raw materials** picked up;
- the **Last DSS scan**: how many mining locations the scan found on which body;
- **Known hotspots here**: the ones you have saved on the body you are on;
- the **coverage minimap** (if ticked in Settings): ground the Rhino has driven over, with your position and your saved hotspots. In your
  ship it appears only close to the ground (under about 2 km).

Both pages carry the buttons above, and the Mining Book and the coverage map are per commander.

## The buttons

The buttons sit side by side in one row, in this order. Which ones you see depends on the page and on your
Settings. Hover for the full name.

| Button | What it does | Shown when |
|---|---|---|
| **BOOK** (Mining Book) | Opens your catalog (see below). | Always |
| **+H.S.** (save hotspot here) | Saves the current ring as a hotspot. | On the pages that offer it |
| **H.S.** (find nearby hotspots) | Finds rings with a confirmed hotspot for a commodity, using Spansh. | Space Mining page, once *Enable Spansh nearby hotspot finder* is ticked |
| **PRICE** (find best price) | Finds the best-paying station for a commodity, using Spansh. | Once *Enable Spansh best price finder* is ticked |
| **RES** (check ring reserve level) | Looks up a ring's reserve level, using EDSM. | Space Mining page, once *Enable EDSM ring reserve lookup* is ticked |
| **I/E** | Import or export your saved hotspots. | On the pages that offer it |

The three online lookups are **off until you turn them on in Settings**. Note that the EDSM ring reserve lookup,
once on, also contacts edsm.net **automatically every time you drop into a ring**, as well as when you search by
hand. See [what goes on the internet](internet-and-privacy.md).

## A typical run

1. Fly to a ring and start mining. The page fills in live stats for your run.
2. Found a good deposit? Press **+H.S.** to save the spot.
3. Done for the day? Open **BOOK** to see everything you've saved, including tons mined and an estimate of tons left.
4. Next time you're in the system, the Mining Book lists the bodies you've scanned and your hotspots there.

## The Mining Book

Press **BOOK** on either Mining page. You don't need to be mining to open it; it lists your saved hotspots either
way.

It lists the bodies you've scanned in this system and every hotspot you've saved. You can:

- filter by material or number of rigs,
- see tons mined and an estimate of tons left,
- add a hotspot by hand (**Add hotspot**, top right),
- edit a hotspot or mark it as depleted,
- copy its coordinates,
- view a zoomable map,
- see the best **stops** on a body you are on (below).

**Depleted marks refill.** The game does not say when a mined-out deposit refills, so WNTB assumes 14 days. A hotspot marked
depleted shows how long is left; after that the mark comes off and the hotspot has no Amount until you read it again. If you
press **Mark depleted** on it and you have not refined anything there since, WNTB takes that as a look at a deposit that is
still empty, keeps the first date and looks again 7 days later (`Still depleted at 15 d; look again in 7 d`). Tons refined
since make it a fresh depletion. Marks made before this feature are dated when you first open the Book or load the commander.

**Stops.** Rigs sit around the Rhino, so deposits close together can be worked from one place. For the body you are on, the Book
takes the saved deposit with the most rigs and every other one within the **stop radius** of it (Settings → Mining, 500 to 2500 m,
default 1250 m) as one stop. The best three, led by a deposit of 5 or more rigs (4 or more if the body has none), are listed
above the hotspots with the tons left added up, circled on the map and tagged `stop 1` to `stop 3` on each row. Deposits that
are depleted, or have no position or rig count, are left out. Stops need the body's radius, which WNTB only has for a body you
have visited this session, so a body you are not on shows none.

**You are here.** With the Rhino on the body, the deposit within 175 m of it is marked `you are here` and selected, so
**Mark depleted** is one click. It is worked out when the Book is opened or refreshed, not while you drive.

**Your hotspots, tons mined, depleted marks and the ground your Rhino has driven over belong to the commander you are
playing.** Switching commander switches the Mining Book and the coverage map; one commander never sees or changes
another's. **After updating from a version before this**, the one shared list and map are given to the first commander
who logs in (it can't tell whose they were), and every other commander starts empty. To give a hotspot list to another
commander, use **I/E** to export it as the first commander and import it as the second.

For a scanned body it also shows what *you've* found so far on that kind of body. That starts empty and fills in as
you save hotspots. It describes your own finds, not what a body actually holds.

## What the game does and doesn't tell us, and how to work around it

WNTB, like every third-party tool, only knows what Elite Dangerous writes to its journal files. It adds what Spansh and EDSM report and works around the rest. Where it can't be sure, WNTB says so rather than guess quietly. See [How WNTB knows what it knows](README.md#how-wntb-knows-what-it-knows).

| What you might expect | What the game gives | What to do |
|---|---|---|
| Ring and deposit amounts read for you | Amount and Density are not given to WNTB. They are **typed in by hand**. | Check the figure you type. A wrong reading gives a wrong range. |
| When a mined-out deposit refills | Nothing in the journal says. WNTB assumes 14 days. | Read the Amount again at the deposit and edit the hotspot; that overrides the assumption. |
| Exact tonnes left in a deposit | The deposit figures are measurements from a handful of deposits, so the ranges are wide. | Treat "tons left" as a guide, not a count. |
| A map of everywhere you have mined | Coverage means ground the Rhino has **driven over**, not ground it has scanned. | Use the minimap to see where you have been, not what is left. |
| An exact count of limpets aboard | "On board" is approximate (bought less launched). | Check your cargo for the real number. |
| Every commodity's best mining method | The method hints are community-sourced and need occasional updating. | If a hint looks wrong, trust the game and open an issue. |
| Ring reserve and hotspot lookups to always answer | They only know what players have uploaded to EDSM or Spansh. | No answer can mean nobody has recorded it. Scan the ring yourself, then save the hotspot with **+H.S.** |

## Settings

**Settings → Mining**:

The checkboxes (the first three are on by default; the rest are off):

- *Show session totals*, *Show the cargo bar*, *Show prospector hints* (on by default),
- the three online lookups above,
- *Enable HUD Overlay*: sends live stats to the overlay,
- The arrow to the nearest known hotspot is now the **Surface Compass** (Settings → Overlays → Surface Compass, and the Compass section
  in [Exploration](exploration.md#compass)). It still points at the nearest hotspot by default, and also works from any mode;
- *Show coverage minimap* (Surface Mining page): a small map of ground the Rhino has driven over on the current
  body,
- *Archive completed mining runs*: writes a JSON file per run,
- *Stop radius in the Mining Book*: how close deposits must be to the lead deposit to share a stop (500 to 2500 m).

More detail: [Mining specification](../MINING_TECH_SPEC.md).
