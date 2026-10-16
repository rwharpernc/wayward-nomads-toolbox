# Odyssey stat data: where it might come from

Research note, 2026-10-16. The Upgrade planner ("Odyssey upgrade planner, next step" in [TODO.md](TODO.md)) would need a stat preview: each suit's
and weapon's base stats, what each class (1 to 5) changes, and what each modification changes. This note records where that data was looked for,
what was found, and the license or terms of each source, so that permission can be asked of the right people. **No stat tables are in WNTB yet,
and nothing was decompiled, disassembled or extracted from any program.**

## What is needed

- Per weapon and per suit: base values (damage per shot, rate of fire, magazine and reserve ammo, reload time, effective range, headshot
  multiplier, health, shields, speed and so on) and what each class 2 to 5 changes.
- Per modification: which stat it changes and by how much (for example "Greater Range" and "Magazine Size" on weapons; "Improved Battery
  Capacity" and "Increased Air Reserves" on suits).
- Preferably as a table that can be read as data (CSV or JSON), with a license that allows it to be used and credited in WNTB.

WNTB already has, from the journal, the upgrade materials and credits that have been confirmed in play (`odyssey_upgrade_plan.py`); the journal has
no stat values.

## Sources, and what each holds

| Source | What it has | License or terms | Status |
|---|---|---|---|
| **Elite Dangerous Odyssey Materials Helper** (EDOMH, `jixxed/ed-odyssey-materials-helper`) | An Odyssey loadout view that shows the stats of a suit or weapon at a class with chosen modifications. The values live in its `nl.edomh.core` module (`Stat`, `Loadout`, `Equipment`), which is **not** in the public repository. The public repository has only the stat *names* in `locale/loadout/stat.name.csv`. | Source code in the repository: MIT. Official binaries: **proprietary components, not MIT**; the `EULA.MD` forbids decompiling, reverse engineering and extracting data from them. | **Best candidate, and the one to ask.** Not read from the binaries. The developer is `jixxed` on GitHub. The program itself is not installed on this machine (only its saved user data). |
| **EDDI** (`EDCD/EDDI`) | `DataDefinitions/HandWeapon.cs` and `Suit.cs`: internal name, weapon type, manufacturer and base price only. No stats. | Open source; check the repository's `LICENSE` before using anything from it. | Searched with GitHub code search. Nothing usable for stats. |
| **EDDiscovery** (`EDDiscovery/EDDiscovery`) | Journal handling for `UpgradeWeapon`, `SellWeapon` and the like, with unit tests that mention the weapons. No stat tables were found by code search. | Apache-2.0 (as recorded in [ATTRIBUTIONS.md](ATTRIBUTIONS.md)). | Searched with GitHub code search only; a full clone has not been searched. |
| **Journal schema and parser projects** (`jixxed/ed-journal-schemas`, `rster2002/ed-journals`, `lrbalt/ed-parse-log`) | Names and event shapes (`UpgradeWeapon`, `SuitLoadout`, ...). No stats. | Not checked. | Not useful for stats. |
| **Elite Dangerous Wiki** (`elite-dangerous.fandom.com`) | Search results quote per-weapon figures, for example Karma AR-50: 9.0 base DPS, 2.0x headshot multiplier, 50 m effective range, 40-round magazine, 200 reserve ammo; Manticore Executioner DPS by grade (12.5, 15.68, 20.8 for grades 1 to 3); a magazine-size modification described as +50%. These came from search summaries; the pages themselves could not be fetched (HTTP 402), so **none of these numbers is verified**, and sources disagree in places (one forum post says the magazine modification multiplies rounds by 1.5, which does not match the wiki's own Executioner example). | Fandom wikis are normally CC BY-SA, which requires credit and share-alike; **confirm on the page footer** before use. | Not fetched. Worth reading in a browser. |
| **Inara** (`inara.cz`) | Equipment blueprint pages list each modification with its effect (for example "Greater Range", +50% effective range) and the material and credit costs; logbook guides compare weapons in a table. | Inara's terms were not read. It has an API that needs an application to be registered. Treat the content as not reusable until its terms are read or its author asks. | Pages returned HTTP 503 ("retry after 3600 s") when fetched. Try again later or in a browser. |
| **Frontier forums** ("Odyssey Engineering Cheat Sheet" and others) | Community tables of modification effects. | Forum posts belong to their authors; ask before reuse. | Fetch returned HTTP 403. |
| **EDCoPilot** (closed, installed at `C:\EDCoPilot`) | Its plain-text files (settings, station lists) were searched for the weapon names; none matched. Whether its program holds stat tables is unknown. | Closed source; its terms were not read. | Program files not examined. |
| **EDOMH saved data** (`%LOCALAPPDATA%\odyssey-materials-helper`) | The commander's own loadouts and wishlist (which suit, class and modifications were chosen). The `common.db` file holds star systems only. No stat values. | The commander's own data. | Nothing to use. |
| **The game itself** | The only primary source, but its files are not published as data, and its license restricts taking them apart. | Frontier's EULA. | Not attempted. |

## Suggested next steps

0. To see everything that is missing or unverified in one place, import `docs/data_verification/verification_checklist.csv` into a spreadsheet ([instructions](data_verification/README.md)).
0. To build the data set first-hand instead, follow [ODYSSEY_STAT_COLLECTION.md](ODYSSEY_STAT_COLLECTION.md): what to record in the game, the blank
   templates in `docs/odyssey_stats/`, and the license decision to make before filling anything in.
1. Ask `jixxed` (EDOMH) whether the Odyssey stat tables can be shared under a license WNTB can credit, or exported as a data file. The public
   repository's MIT license covers its source, not the proprietary module that holds these tables.
2. Read the Fandom pages and Inara's terms in a browser; if the numbers are needed from there, confirm each license and credit it in
   [ATTRIBUTIONS.md](ATTRIBUTIONS.md).
3. Ask in the Elite Dangerous community (for example the EDCD organization on GitHub) whether anyone publishes the values as open data.
4. Whatever is obtained: check a sample of values against the in-game stat screens before shipping a preview, and record in the docs which
   values were measured in the game and which came from a source.
