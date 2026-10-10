# What goes on the internet

Most of WNTB works entirely on your own computer, reading the game's journal files. This page lists **every**
feature that contacts an outside site, so you can decide what you're comfortable with.

**The short version:** most lookups only run when you click a button or after you switch them on in Settings. The
exceptions are **BGS tick detection**, which is on by default (turn it off in Settings → BGS), and the **Rare Goods
Finder** and **Codex "Not found" tab**, which have no on/off setting and contact their service when you open them.
The table says exactly when.

| Feature | Contacts | When |
|---|---|---|
| N.S. and W.D. buttons (nearest neutron star / white dwarf) | Spansh | Only when you click **N.S.** or **W.D.** |
| Rare Goods Finder | Spansh | When you open the window, to see which Power controls each listed rare's origin system. Remembered until you restart EDMC |
| Codex Completionist "Not found" tab | Canonn | Downloads a list when you open the details window (if it has none, or it's over two weeks old), or when you click **Refresh Catalog** |
| GEC Nearby POI | edastro.com | Only when you click **FIND** |
| Canonn Nearby POI | Canonn | Downloads site lists when you click **FIND** |
| Boxel Survey lookups | EDSM (and Spansh for Region Sweep) | When you use its lookup buttons. Some automatic checks are optional in Settings |
| Exploration Value extras | Spansh, EDSM | **Off** until you turn them on in Settings |
| Mining lookups (hotspots, prices, ring reserves) | Spansh, EDSM | **Off** until you turn them on in Settings. Once on, the ring reserve lookup also runs by itself each time you drop into a ring |
| Trade lookups (best routes; where to buy or sell a commodity) | Spansh | **Off** until you turn them on in Settings. See below for how often |
| BGS tick detection | A community tick-time service (`tick.infomancer.uk`) | **On** by default. Every 60 seconds while BGS is on. Can be turned off in Settings → BGS |
| Automatic updates | GitHub | **Off** by default |

### How often do Trade lookups ask?

Only when you press a button:

- **Find routes**: sends one request, then checks for the answer every 5 seconds, for up to 4 minutes, until you
  press **Cancel**.
- **Near me** / **Galaxy**: two requests each (stations, then fleet carriers). One if you hide carriers.
- **Round trip**: one to three requests of up to 100 stations each.

## What never goes online

Everything else makes **no internet connection at all**: Powerplay tracking, Missions, Inventory, Screenshots,
Colonisation, Organic Scanning, Ship Builds, Landing Assist, Interdiction Warning, and Trade's session profit,
stock, carrier cargo and History.

## How WNTB keeps its traffic low

WNTB is built to ask these services for as little as it can:

- Lookups are started by **you**, or switched on by **you**.
- Answers are remembered, so asking twice doesn't mean two requests.
- Every request says who it's from.

The technical details are in [TECHNICAL.md](../TECHNICAL.md#keeping-api-traffic-low).

## Please support the services

These services are run and funded by volunteers. If WNTB is useful to you, please consider supporting them, as I
do: [EDSM](https://www.patreon.com/EDSM), [Spansh](https://www.patreon.com/cw/spansh) and
[Inara](https://www.patreon.com/cw/artieinara).
