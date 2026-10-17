# Acknowledgements

WNTB is a toolbox I built for the Wayward Nomads exploration squadron. Elite Dangerous has a generous
community of tool authors, and many of WNTB's features were shaped by what they've built. This page
credits the projects and people whose ideas, and in some cases published data and services, helped.

Author: R.W. Harper: CMDR Bocheaux (Wayward Nomads, WWNS). Licensed under the GNU GPL v3.0; see `LICENSE`.
Notices that a license requires are in `THIRD-PARTY-NOTICES.md`.

## Ideas that belong to the community

Every feature in WNTB is an idea that many people in the Elite Dangerous community have built, in many
forms, over many years. None of them belongs to one tool. The projects below are examples of the
community's work in each area: tools I've used, looked at or learned from. The list isn't complete, and
being listed doesn't mean a tool was the first or the only one.

- **Boxel surveying** (walking a boxel's systems in order, skipping ones already visited):
  [EDJP](https://edjp.colacube.net/), [SrvSurvey](https://github.com/njthomson/SrvSurvey),
  [VoxStellar](https://voxstellar.com/), [Elite Observatory](https://github.com/Xjph/EliteObservatory)
  and [SectorLister](https://github.com/mpfj/SectorLister).
- **Auto-honk** (firing the Discovery Scanner on arrival): EDCoPilot, VoiceAttack profiles and
  autopilot tools such as [EDAPGui](https://github.com/SumZer0-git/EDAPGui).
- **Notable Bodies alerts:** the rules and thresholds follow the default criteria of
  [Elite Observatory](https://github.com/Xjph/ObservatoryCore)'s Explorer plugin (MIT). The green gas
  giant temperature table is community research: CMDR Arcanic's [ED GGG](https://ed-ggg.github.io/edggg/)
  work, compiled for Observatory by DaftMav and CMDR Julian Ford's "Custom Criteria for Everyone".
  Discovery Watch, a standalone journal watcher, was a useful reference for which rules commanders want.
  No code was taken from any of them.
- **Exploration value, system age and rarity readouts:** EDJP, EDDiscovery, Elite Observatory and
  many other exploration tools.
- **The drag-and-drop layout editor on Overlay Placement:** a grid for placing overlay displays was suggested by the layout tool in EDDDT; WNTB's editor (a to-scale picture of the screen with a box per display that snaps to edges and a grid) is its own design and code, and EDDDT's code was not consulted.
- **Exploration value formula and mapping multipliers:** the base value (k + k x 0.56591828 x mass^0.2, at least 500), the first-discovery multiplier of 2.6, the three mapping multipliers (3.699622554 for a body nobody had discovered or mapped, 8.0956 for one discovered but never mapped, 3.3333333 for one already mapped), the efficiency bonus (1.25) and the Odyssey bonus (30% on the mapping part) are from [EDDiscovery](https://github.com/EDDiscovery/EliteDangerousCore)'s `EstimatedValues.cs` (Apache-2.0); the per-class k values come from the same table and from Faber38/CMDRHelper. [OD Explorer](https://github.com/WarmedxMints/OD-Explorer)'s estimates were used as a check: on the same journals its exobiology estimate matched WNTB's to the credit and its cartography estimate was within 0.2%. No code was copied.
- **Exobiology overlay cards (bio status, predicted species, sample radar, sample popup):** the idea of showing sampling progress, predicted species with their values, the first footfall bonus and a radar of sample circles as separate cards over the cockpit follows [SrvSurvey](https://github.com/njthomson/SrvSurvey)'s biology plotters (GPL-3.0, the same license as WNTB); the small pointers beside each distance, a circle-and-hand in SrvSurvey and an arrowhead in WNTB, and leading the commander back to plants they identified follow SrvSurvey's tracking of scan sites. The cards are WNTB's own code, built on Organic Scanning's prediction and sample tracking and the journal's `ScanOrganic`, `CodexEntry` and `Status.json`; no code was taken from SrvSurvey.
- **Hiding the overlays for a while:** that the overlays can be switched off at a keystroke without leaving the game follows [SrvSurvey](https://github.com/njthomson/SrvSurvey)'s overlay toggle. WNTB's is its own code (a switch in the overlay connection plus a Windows hotkey); no code was taken from SrvSurvey.
- **What is left to scan, map and sample in a system, and a card for the body you target:** [SrvSurvey](https://github.com/njthomson/SrvSurvey)'s system status (scan progress, bodies still worth a DSS, bodies with life remaining) and body info plotters shaped the idea and which facts to show. WNTB's System targets and Body info cards are its own code, built on the journal events, the scan-value estimate described below, and the system model in `system_survey.py`; no code was taken from SrvSurvey (GPL-3.0, the same license as WNTB). The optional **Known** section (the life and points of interest other commanders found in a system) reads [Spansh](https://spansh.co.uk/)'s public system record, only when you tick the setting; the visit history is built from your own journals (`system_history.py`).
- **The built-in overlay's default font:** Source Sans 3 (Adobe, SIL Open Font License 1.1), bundled unmodified with its license (see THIRD-PARTY-NOTICES.md). The idea of an overlay that WNTB draws itself follows [SrvSurvey](https://github.com/njthomson/SrvSurvey)'s own overlay windows; no code was taken from it, and [EDMCModernOverlay](https://github.com/SweetJonnySauce/EDMCModernOverlay) remains the overlay for Linux and for other plugins.
- **Exobiology color variants (the likely color of a species before it is sampled):** the rules that tie a species' color to the star its body orbits or to a surface material come from [SrvSurvey](https://github.com/njthomson/SrvSurvey)'s `bio-criteria` data (GPL-3.0, the same license as WNTB), read and turned into WNTB's own table by `scripts/gen_organic_variants.py`; the code that uses it is WNTB's own and no SrvSurvey code was taken. The predictions were checked against the commander's own journals (397 samples, all matched).
- **Exobiology species prediction and sampling help:**
  [EDMC-BioScan](https://github.com/Silarn/EDMC-BioScan),
  [Artemis Scanner Tracker](https://github.com/Balvald/ArtemisScannerTracker), SrvSurvey and the
  [EDMC-Canonn](https://github.com/canonn-science/EDMC-Canonn) plugin.
- **Codex and scan tallies:** Artemis Scanner Tracker, EDMC-BioScan, EDMC-Canonn, EDDiscovery and
  [edastro.com](https://edastro.com/).
- **Massacre and kill-mission tracking:** [EDMC-Massacres](https://github.com/CMDR-WDX/EDMC-Massacres),
  [EDMC-CombatTracker](https://github.com/lunarplasma/EDMC-CombatTracker),
  [EDCarnage](https://github.com/mmomtchev/EDCarnage) and
  [EDMMC](https://github.com/tautomer/EDMMC).
- **Powerplay merit tracking:**
  [EDMC-PowerPlayProgress](https://github.com/alby666/EDMC-PowerPlayProgress),
  [EliteMeritTracker](https://github.com/Fumlop/EliteMeritTracker),
  [EDMC Merit Tracker](https://gitlab.com/valdidan-edtools/edmc_merittracker) and BGS-Tally.
- **Rare goods lookups:** EDMC-PowerPlayProgress, [Inara](https://inara.cz/) and many rare-commodity
  guides.
- **BGS tracking:** [BGS-Tally](https://github.com/aussig/BGS-Tally) and its forks,
  [EliteFactionTracker](https://github.com/Haelnorr/EliteFactionTracker) and other faction trackers.
- **Surface mining aids** (tons-remaining estimates, driven-coverage maps, hotspot lists, waypoint
  arrows): [EDRhinoSpotter](https://github.com/Fumlop/EDRhinoSpotter),
  [Rhino Surface Mapper](https://github.com/pbgaspar/rhino-surface-mapper), EDSMT, EliteMining and
  [EDPlanetNavigator](https://github.com/mcjohnso/EDPlanetNavigator). The Mining Book's dated Depleted marks with an optional assumed refill time (and a shorter wait after a look at a deposit that is still empty), its Rhino stops (deposits grouped around the one with the most rigs, the best three circled) and its pick of the deposit you are standing at follow ideas in [EDRhinoSpotter](https://github.com/Fumlop/EDRhinoSpotter) (GPL-3.0, the same license as WNTB). The code is WNTB's own and none was taken from it. Market research in the Mining Book (the markets in a system that buy what you could mine there) follows an idea in [Rhino Surface Mapper](https://github.com/pbgaspar/rhino-surface-mapper) (GPL-3.0), but takes its commodities from your own records instead of a table. Waiting for a `Market.json` that the game wrote late follows the fix in [BGS-Tally](https://github.com/aussig/BGS-Tally) (MIT). The **Neutron route** is [Spansh](https://spansh.co.uk/)'s neutron plotter, called when you press **Plot**. None of their code was taken.
- **Expeditions** (a named trip as an ordered list of stops with notes and progress): [EDDiscovery](https://github.com/EDDiscovery/EDDiscovery)'s expeditions and Boxel Survey's own Waypoint Route. WNTB's is its own, and no code was taken. System positions come from [EDSM](https://www.edsm.net/) when you ask, and the Road to Riches and Expressway to Exomastery route planners are [Spansh](https://spansh.co.uk/)'s, called when you press **Plot**.
- **Surface compass and marks** (an arrow and distance to a chosen latitude and longitude, with saved spots):
  [SrvSurvey](https://github.com/njthomson/SrvSurvey)'s target tracking and [ODEliteTracker](https://github.com/WarmedxMints/ODEliteTracker)'s
  compass and bookmarks. WNTB's is its own: it grew out of Mining's own hotspot arrow, and no code was taken from either.
- **Megaship scans** (a count of the megaships scanned each Powerplay cycle, with name and system):
  [ODEliteTracker](https://github.com/WarmedxMints/ODEliteTracker)'s BGS data store keeps the same list. Its source (no license is declared, so none of it is
  copied) was read for how it names the ship: the megaship you dropped to just before the uplink scan. WNTB's is its own code, checked against real
  journals, with the merits each scan earned, a check that the destination really is a megaship, and a journal back-fill.
- **Colonisation tracking:** Architect Tracker, [Raven Colonial](https://ravencolonial.com/),
  ED Colonization Helper, EDColony and BGS-Tally. The shopping-list overlay card follows
  [SrvSurvey](https://github.com/njthomson/SrvSurvey)'s layout. Raven Colonial publishes its API as OpenAPI, which SrvSurvey and
  BGS-Tally use and which informed WNTB's plans for it. WNTB's **Planned Builds** window reads one public, key-free endpoint of it (the
  build sites of a system) when you press a button. Anything WNTB sends to Raven Colonial (progress, deliveries, carrier cargo, a
  completion) is opt-in, off by default, and listed in the privacy page.
- **What each building costs:** the cost table behind the Planned Builds window is a copy of
  [SrvSurvey](https://github.com/njthomson/SrvSurvey)'s `colonization-costs2.json` (GPL-3.0; notice in `THIRD-PARTY-NOTICES.md`),
  compiled by its author from the game. Raven Colonial's own totals for the same buildings agree with it where I checked.
- **Shopping list order:** the overlay shopping list follows [SrvSurvey](https://github.com/njthomson/SrvSurvey)'s shopping overlay: alphabetical
  at a construction site, grouped under the market's categories elsewhere, with what the market does not sell dimmed. The category
  table (`plugin/commodity_categories.py`) is taken from its `ColonyData.mapCargoType` (GPL-3.0; notice in `THIRD-PARTY-NOTICES.md`). The code is WNTB's own.
- **Where to buy a colonisation commodity:** [Spansh](https://spansh.co.uk/)'s station search, the same one the Mining and Trade
  finders use.
- **Overlay placement:** SrvSurvey places each overlay relative to the game window (left, center or right; top, middle or
  bottom; plus pixels), which is the model WNTB's Overlay Placement follows. EDMCModernOverlay's open source made it possible to
  check how it maps positions and sizes onto the screen.
- **Landing pad guidance:** [LandingPad](https://github.com/bgol/LandingPad) and ED Recon.
- **Screenshot conversion and renaming:** EDMC's own built-in screenshot handling and
  [EDMC-Screenshot](https://github.com/NoFoolLikeOne/EDMC-Screenshot).
- **Engineering materials** (what you hold of each Raw, Manufactured and Encoded material, with its grade and limit):
  [Elite Dangerous Odyssey Materials Helper](https://github.com/jixxed/ed-odyssey-materials-helper) (source MIT),
  [EDEngineer](https://github.com/msarilar/EDEngineer) (MIT) and EDDiscovery. WNTB's is its own, built from the journal's events, and no
  code was taken from any of them. (What is taken is data, below.) Material names, types and grades come from
  **[EDCD/FDevIDs](https://github.com/EDCD/FDevIDs)** (`material.csv`; see Data below).
- **Engineering blueprints** (what each blueprint takes and where its ingredients are found): the recipes and the "where found" text are a
  trimmed copy of [EDEngineer](https://github.com/msarilar/EDEngineer)'s `blueprints.json` and `entryData.json` (MIT; notice in
  `THIRD-PARTY-NOTICES.md`), compiled by its contributors from the game. That project is archived, its data last changed in March 2024, and newer
  game content may be missing. [Elite Dangerous Odyssey Materials Helper](https://github.com/jixxed/ed-odyssey-materials-helper) shaped the idea.
  [EDDiscovery](https://github.com/EDDiscovery/EliteDangerousCore) (Apache-2.0; notice in `THIRD-PARTY-NOTICES.md`) corrected five synthesis recipes,
  supplied seven synthesis families and nine Thargoid-war and chip materials, and its engineer table is `plugin/engineers_data.py` (each engineer's
  place and how to find, be invited by and unlock them). The four Colonia on-foot engineers (Baltanos, Eleanor Bresa, Rosa Dayette and Yi Shen), whom
  EDEngineer's table lacks, are in that table; which suit and weapon upgrades each offers comes from EDCoPilot's engineer list (read for facts only, as
  in the author's ED-DDT), and Yi Shen's three sets of referral items are game facts as stated in the Materials Helper's English text (MIT) and the
  engineering checklist on [edblackbox.com](https://edblackbox.com/guides/engineering/engineering-manuals/checklist.html). The grade thresholds for
  ship engineers are facts from the community wiki. No code was taken, and none of it is from Frontier.
- **Odyssey upgrade planner** (a suit's or weapon's upgrade and modifications as a wishlist): the idea follows [Elite Dangerous Odyssey Materials Helper](https://github.com/jixxed/ed-odyssey-materials-helper)'s
  loadout editor, which WNTB's is not a copy of: its stat tables are not public and none of its data or code was taken. The upgrade costs are read from the game's own `UpgradeSuit` and
  `UpgradeWeapon` journal events (game facts), and the modification recipes are the blueprint table's (EDEngineer, MIT).
  The names the journal uses for suit and weapon modifications (`suit_nightvision`, `weapon_range`) and for the weapons are the game's, as [EDDI](https://github.com/EDCD/EDDI)'s
  definitions and real journals agree; WNTB's own table maps them to the planner's names. No code was taken.
- **Ship engineering planner** (a ship's engineering as a wishlist): the idea follows
  [Elite Dangerous Odyssey Materials Helper](https://github.com/jixxed/ed-odyssey-materials-helper)'s ship builder and wishlist import from EDSY and Coriolis,
  which WNTB's is not a copy of: no code or data was taken, and its design here is the journal's own `Loadout` shape. The journal's blueprint and
  effect names come from [EDCD/coriolis-data](https://github.com/EDCD/coriolis-data) (names only; notice in `THIRD-PARTY-NOTICES.md`), and
  [EDSY](https://edsy.org/) and [Coriolis](https://coriolis.io/) are where a build is designed and exported (SLEF).
- **Material trader finder:** [ODEliteTracker](https://github.com/WarmedxMints/ODEliteTracker)'s material trader finder shaped the idea. WNTB's is its own,
  and no code was taken. The stations are [Spansh](https://spansh.co.uk/)'s station search, filtered by its material trader field.
- **Odyssey inventory tracking:** EDMC's own ship locker data, ED Recon and the Odyssey Materials
  Helper.
- **System-name suggestions** (the optional list of matching systems while you type): [Spansh](https://spansh.co.uk/)'s system-name search, only when you tick the setting.
- **Nearest neutron star and white dwarf lookups:** [Spansh](https://spansh.co.uk/) answers the N.S. and W.D.
  buttons.
- **Nearby points of interest:** [Canonn](https://canonn.science/) and
  [edastro.com](https://edastro.com/) publish the lists WNTB looks up.

## Ports, and reusing WNTB

Some of WNTB's features were ported from projects written in other languages: C#, TypeScript, React and others. A port here means the
rules, tables or layout were carried over into Python, not that the original's code runs inside WNTB. Where a port needed a license
notice, it is in `THIRD-PARTY-NOTICES.md`, which names each source, its license and what was taken. Where a project is only an idea
or a reference, the list above says so, and no code was taken.

WNTB is GPL-3.0, so anyone may reuse its ports, and the rest of it, on GPL-3.0 terms. That means passing on the license and keeping
the original authors' notices in `THIRD-PARTY-NOTICES.md` with whatever you reuse. A nod to WNTB is welcome and not required. If you
reuse a port, it also helps to pass on where the original came from, so credit reaches the people who wrote it first.

## Overlay

WNTB draws on the game through the optional helper app
**[SweetJonnySauce/EDMCModernOverlay](https://github.com/SweetJonnySauce/EDMCModernOverlay)**. It talks
to it over its documented local protocol and ships none of its code; it is the user's own
install.

## Host application

**[EDMC](https://github.com/EDCD/EDMarketConnector)** (GPL-2.0) is the host. WNTB uses its plugin API
and imports its `config`, `theme` and `myNotebook` modules at runtime.

## Data

Game facts such as thresholds, names, coordinates and measured values (the exobiology and region
tables, the pad layout, scan-value constants, mining depletion figures and micro-resource names) come
from the community's published work and from the game itself. Where a source's license asks for a
notice, it is in `THIRD-PARTY-NOTICES.md`. Micro-resource and commodity names come from
**[EDCD/FDevIDs](https://github.com/EDCD/FDevIDs)**, and the landing-pad size of each ship (Trade mode) from
**[EDCD/coriolis-data](https://github.com/EDCD/coriolis-data)**. Engineering material names, types and grades (Field Ops → Materials)
come from FDevIDs' `material.csv` too.

**How the data is gathered and verified.** The game changes, and a lot of old data about it is still in circulation, so the aim is to collect what can be found and keep it current. Other authors' published work is reviewed with respect for what they have built: it is checked against the game by the project owner, used once it has been verified, and credited here and in `THIRD-PARTY-NOTICES.md` with its license. What is not available as open data is measured in the game by the project owner, each value recorded with the game version, the date and a screenshot. A value that has not yet been checked in the game is marked as such. `docs/data_verification/verification_checklist.csv` lists every item that is still missing or still to be checked, with its source and license, and shows which have been verified in the game and which have not (tables added before the checklist existed are on it too). No Odyssey suit or weapon stat values are in WNTB yet; when they are, they will be the owner's own in-game measurements, or another author's published values that were checked in the game (`docs/ODYSSEY_STAT_COLLECTION.md`). Nothing was taken from any program's compiled files.

I try to tread carefully and to respect all the work that came before: where someone's published work helped, I say so, and I would rather over-credit than under-credit. If I have missed a credit or got one wrong, please tell me and I will fix it.

In the same spirit of the community, WNTB's data is open under the project's license (GPL-3.0) and not restricted any further. If you reuse or repurpose it, a word of acknowledgement for WNTB, and through it for the authors credited here whose work it was checked against, is all that is asked.

## Services

[EDSM](https://www.edsm.net/), [Spansh](https://spansh.co.uk/), [edastro.com](https://edastro.com/)
(GEC), Canonn's published site lists and codex catalog, `tick.infomancer.uk` (BGS tick, optional) and
GitHub Releases (self-update, opt-in). [Inara](https://inara.cz/) is linked to only. Every network call
goes to a documented API or a published data file, never to another site's HTML, and most are opt-in or
user-triggered. The Rare Goods Finder's static list was compiled from public game data, with EDSM
coordinates, Inara commodity ids and Spansh system ids looked up once (notice in `THIRD-PARTY-NOTICES.md`).

## Thanks

Elite's third-party tooling runs on individual authors' spare time, and WNTB leans on several of these services. I'm a Patreon supporter of
[EDSM](https://www.patreon.com/EDSM), [Spansh](https://www.patreon.com/cw/spansh),
[Inara](https://www.patreon.com/cw/artieinara), [SrvSurvey](https://www.patreon.com/SrvSurvey) and
[EDCoPilot](https://www.patreon.com/EDCoPilot), and I've donated to
[EDEB](https://forums.frontier.co.uk/threads/edeb-elite-dangerous-exploration-buddy.615445/),
[OD Explorer](https://github.com/WarmedxMints/OD-Explorer) and
[OD Elite Tracker](https://github.com/WarmedxMints/ODEliteTracker). If they're in your toolkit too,
consider chipping in. WNTB asks for nothing except feedback.

## AI assistance

**Design and coding by R.W. Harper**, with **code review and documentation** (including this page) **by
Claude** (Anthropic). Disclosed for transparency; authorship is unchanged.

*Elite Dangerous* and related marks are trademarks of Frontier Developments plc. WNTB is a fan-made
tool, not official Frontier software, and is not affiliated with the EDMC team or any project above.
