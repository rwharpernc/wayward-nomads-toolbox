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
| Codex Completionist "Not found" tab | Canonn (its data service runs on Google's cloud) | Downloads a list when you open the details window (if it has none, or it's over two weeks old), or when you click **Refresh Catalog** |
| GEC Nearby POI | edastro.com | Only when you click **FIND**: the first press of a session downloads their whole list (about 2 MB), then it is reused for six hours |
| Canonn Nearby POI | Canonn's published site lists, which are hosted on Google Sheets and Google Drive, so Google also sees the request | Downloads the lists when you click **FIND** |
| Boxel Survey lookups | EDSM (and Spansh for Region Sweep) | When you use its lookup buttons. Some automatic checks are optional in Settings |
| Exploration Value extras | Spansh, EDSM | **Off** until you turn them on in Settings |
| Mining lookups (hotspots, prices, ring reserves) | Spansh, EDSM | **Off** until you turn them on in Settings. Once on, the ring reserve lookup also runs by itself each time you drop into a ring |
| Colonization: Planned Builds (button in the Colonization Sites window) | Raven Colonial (ravencolonial.com) | Only when you press **Planned Builds** or **Refresh** in that window. Sends the name of the site's system and nothing else; answers are remembered for a minute. It only reads |
| Colonization: sharing progress with Raven Colonial (Settings → Colonization → Raven Colonial, **off by default**) | Raven Colonial (ravencolonial.com) | Only live events, one request each, and only for a site Raven already has a project for (WNTB first reads the system's plan to find it). **Progress:** the depot's figures and what is still needed of each commodity. **Deliveries:** the commodities and tons you hand over, under your commander name, plus a one-time link of your commander to the project. **Carrier cargo** (a second switch): the tons moved to and from your fleet carrier, as plus and minus amounts. Your Raven key, if you saved one, goes in a header and nowhere else. Nothing from before the event, and no other journal data |
| Colonization: Raven Progress (button in the Colonization Sites window) | Raven Colonial (ravencolonial.com) | Only when you press it. Reads the system's plan, then that project's figures; sends only the system name and the project's id |
| Colonization: Report Complete to Raven (button in the Colonization Sites window) | Raven Colonial (ravencolonial.com) | Only when you press **Report Complete to Raven** on a site your journal shows complete and confirm. Sends your Raven Colonial key and that one project's id (an empty request to its `complete` address), after first reading the system's plan to find the project. No deliveries, cargo or journal data |
| Colonization: Where to buy (**Find nearest**, **Find all**) | Spansh | Only when you press the button. Sends the commodity name and the system you search around, one request per commodity for **Find all**, plus one that sends the names of all of them together to find a station that sells the whole list. Identical searches are answered from memory for 2 minutes |
| Trade lookups (best routes; where to buy or sell a commodity) | Spansh | **Off** until you turn them on in Settings. See below for how often |
| BGS tick detection | A community tick-time service (`tick.infomancer.uk`) | **On** by default. Every 60 seconds while BGS is on. Can be turned off in Settings → BGS. The service has no HTTPS, so this one request is **unencrypted**; it asks only for the time of the last tick and sends nothing about you but WNTB's name and version |
| Automatic updates | GitHub | **Off** by default |

Links that open a web page (Inara, Canonn or edastro.com pages, GitHub) open it in **your browser**, only when you click them; that is your
browser connecting, not WNTB.

### How often do Trade lookups ask?

Only when you press a button:

- **Find routes**: sends one request, then checks for the answer every 5 seconds, for up to 4 minutes, until you
  press **Cancel**.
- **Near me** / **Galaxy**: two requests each (stations, then fleet carriers). One if you hide carriers.
- **Round trip**: one to three requests of up to 100 stations each.

## What never goes online

Everything else makes **no internet connection at all**: Powerplay tracking, Missions, Inventory, Screenshots,
Colonisation tracking, history and the shopping list overlay (Where to buy and Planned Builds are the only parts that go online,
above), Organic Scanning, Ship Builds, Landing Assist, Interdiction Warning, and Trade's session profit,
stock, carrier cargo and History.

## How WNTB keeps its traffic low

WNTB is built to ask these services for as little as it can:

- Lookups are started by **you**, or switched on by **you**.
- Answers are remembered, so asking twice doesn't mean two requests.
- Every request says who it's from.

The technical details are in [TECHNICAL.md](../TECHNICAL.md#keeping-api-traffic-low).

## Please support the services

These services are run and funded by volunteers. If WNTB is useful to you, please consider supporting them: the
[Acknowledgements](../ATTRIBUTIONS.md) page has links.
