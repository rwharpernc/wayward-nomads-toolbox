# Mining

Mining mode tracks two kinds of mining, plus your own catalogue of known hotspots:

- **Space Mining**, in your ship.
- **Surface Mining**, in the Rhino SRV.

Use the **◀** and **▶** buttons at the top of the panel to switch between the two pages. Each page shows live stats
for your current run.

## The buttons

The buttons sit side by side in one row, in this order. Which ones you see depends on the page and on your
Settings. Hover for the full name.

| Button | What it does | Shown when |
|---|---|---|
| **BOOK** (Mining Book) | Opens your catalogue (see below). | Always |
| **+H.S.** (save hotspot here) | Saves the current ring as a hotspot. | On the pages that offer it |
| **H.S.** (find nearby hotspots) | Finds rings with a confirmed hotspot for a commodity, using Spansh. | Space Mining page, once *Enable Spansh Nearby Hotspot Finder* is ticked |
| **PRICE** (find best price) | Finds the best-paying station for a commodity, using Spansh. | Once *Enable Spansh Best Price Finder* is ticked |
| **RES** (check ring reserve level) | Looks up a ring's reserve level, using EDSM. | Space Mining page, once *Enable EDSM Ring Reserve Lookup* is ticked |
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
- edit a hotspot or mark it as depleted,
- copy its coordinates,
- view a zoomable map.

For a scanned body it also shows what *you've* found so far on that kind of body. That starts empty and fills in as
you save hotspots. It describes your own finds, not what a body actually holds.

## Settings

**Settings → Mining**:

The checkboxes (the first three are on by default; the rest are off):

- *Display Session Totals*, *Display Cargo Bar*, *Display Prospector Hints* (on by default),
- the three online lookups above,
- *Enable HUD Overlay*: sends live stats to the overlay,
- *Enable Surface Waypoint Overlay*: an arrow and distance to the nearest known hotspot on the current body,
- *Show Coverage Minimap* (Surface Mining page): a small map of ground the Rhino has driven over on the current
  body,
- *Archive Completed Mining Runs*: writes a JSON file per run.

More detail: [Mining specification](../MINING_TECH_SPEC.md).
