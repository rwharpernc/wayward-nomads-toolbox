# Acknowledgements

WNTB is a toolbox I built for the Wayward Nomads exploration squadron. Elite Dangerous has a generous
community of tool authors, and many of WNTB's features were shaped by what they've built. This page
credits the projects and people whose ideas, and in some cases published data and services, helped.

Author: R.W. Harper: CMDR Bocheaux (Wayward Nomads, WWNS). Licensed under the GNU GPL v3.0; see `LICENSE`.
Notices that a licence requires are in `THIRD-PARTY-NOTICES.md`.

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
  [EDPlanetNavigator](https://github.com/mcjohnso/EDPlanetNavigator).
- **Surface compass and marks** (an arrow and distance to a chosen latitude and longitude, with saved spots):
  [SrvSurvey](https://github.com/njthomson/SrvSurvey)'s target tracking and [ODEliteTracker](https://github.com/WarmedxMints/ODEliteTracker)'s
  compass and bookmarks. WNTB's is its own: it grew out of Mining's own hotspot arrow, and no code was taken from either.
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
- **Odyssey inventory tracking:** EDMC's own ship locker data, ED Recon and the Odyssey Materials
  Helper.
- **Nearest neutron star and white dwarf lookups:** [Spansh](https://spansh.co.uk/) answers the N.S. and W.D.
  buttons.
- **Nearby points of interest:** [Canonn](https://canonn.science/) and
  [edastro.com](https://edastro.com/) publish the lists WNTB looks up.

## Ports, and reusing WNTB

Some of WNTB's features were ported from projects written in other languages: C#, TypeScript, React and others. A port here means the
rules, tables or layout were carried over into Python, not that the original's code runs inside WNTB. Where a port needed a licence
notice, it is in `THIRD-PARTY-NOTICES.md`, which names each source, its licence and what was taken. Where a project is only an idea
or a reference, the list above says so, and no code was taken.

WNTB is GPL-3.0, so anyone may reuse its ports, and the rest of it, on GPL-3.0 terms. That means passing on the licence and keeping
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
from the community's published work and from the game itself. Where a source's licence asks for a
notice, it is in `THIRD-PARTY-NOTICES.md`. Micro-resource and commodity names come from
**[EDCD/FDevIDs](https://github.com/EDCD/FDevIDs)**, and the landing-pad size of each ship (Trade mode) from
**[EDCD/coriolis-data](https://github.com/EDCD/coriolis-data)**.

## Services

[EDSM](https://www.edsm.net/), [Spansh](https://spansh.co.uk/), [edastro.com](https://edastro.com/)
(GEC), Canonn's published site lists and codex catalog, `tick.infomancer.uk` (BGS tick, optional) and
GitHub Releases (self-update, opt-in). [Inara](https://inara.cz/) is linked to only. Every network call
goes to a documented API or a published data file, never to another site's HTML, and most are opt-in or
user-triggered. The Rare Goods Finder's static list was compiled from public game data, with EDSM
coordinates, Inara commodity ids and Spansh system ids looked up once.

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
