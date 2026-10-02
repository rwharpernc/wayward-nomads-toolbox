# Acknowledgements

WNTB is a toolbox I built for the Wayward Nomads exploration squadron. Elite Dangerous has a generous
community of tool authors, and many of WNTB's features were shaped by what they've built. This page
credits the projects and people whose ideas, and in some cases published data and services, helped.

Author: R.W. Harper (CMDR Bocheaux, Wayward Nomads). Licensed under the GNU GPL v3.0; see `LICENSE`.
Notices that a licence requires are in `THIRD-PARTY-NOTICES.md`.

## Ideas and inspiration

- **[NoFoolLikeOne/EDMC-Screenshot](https://github.com/NoFoolLikeOne/EDMC-Screenshot)**: converting the
  game's screenshots to PNG, naming them from a mask, and previewing a crop of the open HUD panel.
- **[CMDR-WDX/EDMC-Massacres](https://github.com/CMDR-WDX/EDMC-Massacres)**: tracking massacre missions
  by stack.
- **[alby666/EDMC-PowerPlayProgress](https://github.com/alby666/EDMC-PowerPlayProgress)** and
  **[Fumlop/EliteMeritTracker](https://github.com/Fumlop/EliteMeritTracker)**: Powerplay merit tracking,
  manual reset counters, a copy-to-clipboard summary and a "nearest rare commodities" view.
- **EDCoPilot**: automatic honking on arrival.
- **EDJP**: boxel survey walking, system age, Earth-like-world rarity and EDSM-upload-status readouts.
- **[njthomson/SrvSurvey](https://github.com/njthomson/SrvSurvey)**: completion tracking, and keeping
  heavy journal-history scans user-triggered.
- **[Fumlop/EDRhinoSpotter](https://github.com/Fumlop/EDRhinoSpotter)**: tons-remaining estimates, a
  driven-coverage minimap, a system bodies overview and a multi-pane browser for surface mining.
- **[mcjohnso/EDPlanetNavigator](https://github.com/mcjohnso/EDPlanetNavigator)**: pointing an overlay
  arrow at a surface waypoint.
- **[aussig/BGS-Tally](https://github.com/aussig/BGS-Tally)**: BGS tracking and overlay integration.
- **[Silarn/EDMC-BioScan](https://github.com/Silarn/EDMC-BioScan)** and
  **[Silarn/EDMC-ExploData](https://github.com/Silarn/EDMC-ExploData)**: exobiology species prediction
  and galactic region lookup.
- **[bbbkada/EDMC-PlanetPOI](https://github.com/bbbkada/EDMC-PlanetPOI)**: its hotspot file and
  share-link format, which WNTB can import.
- **[canonn-science/EDMC-Canonn](https://github.com/canonn-science/EDMC-Canonn)**: codex and site
  data. WNTB is built to sit alongside it, not replace it.
- **[bgol/LandingPad](https://github.com/bgol/LandingPad)**: the landing-pad diagram.

## Overlay

WNTB draws on the game through the optional helper apps
**[inorton/EDMCOverlay](https://github.com/inorton/EDMCOverlay)** and
**[SweetJonnySauce/EDMCModernOverlay](https://github.com/SweetJonnySauce/EDMCModernOverlay)**. It talks
to them over their documented local protocol and ships none of their code; they are the user's own
install.

## Host application

**[EDMC](https://github.com/EDCD/EDMarketConnector)** (GPL-2.0) is the host. WNTB uses its plugin API
and imports its `config`, `theme` and `myNotebook` modules at runtime.

## Data

Game facts such as thresholds, names, coordinates and measured values (the exobiology and region
tables, the pad layout, scan-value constants, mining depletion figures and micro-resource names) come
from the community's published work and from the game itself. Where a source's licence asks for a
notice, it is in `THIRD-PARTY-NOTICES.md`. Micro-resource names come from
**[EDCD/FDevIDs](https://github.com/EDCD/FDevIDs)**.

## Services

[EDSM](https://www.edsm.net/), [Spansh](https://spansh.co.uk/), [edastro.com](https://edastro.com/)
(GEC), Canonn's published site lists and codex catalog, `tick.infomancer.uk` (BGS tick, optional) and
GitHub Releases (self-update, opt-in). [Inara](https://inara.cz/) is linked to only. Every network call
goes to a documented API or a published data file, never to another site's HTML, and most are opt-in or
user-triggered. The Rare Goods Finder's static list was compiled from public game data, with EDSM
coordinates, Inara commodity ids and Spansh system ids looked up once.

## Thanks

Elite's third-party tooling runs on individual authors' spare time. I'm a Patreon supporter of
[EDSM](https://www.patreon.com/EDSM), [Spansh](https://www.patreon.com/cw/spansh),
[Inara](https://www.patreon.com/cw/artieinara), [SrvSurvey](https://www.patreon.com/SrvSurvey) and
[EDCoPilot](https://www.patreon.com/EDCoPilot), and I've donated to
[EDEB](https://forums.frontier.co.uk/threads/edeb-elite-dangerous-exploration-buddy.615445/),
[OD Explorer](https://github.com/WarmedxMints/OD-Explorer) and
[OD Elite Tracker](https://github.com/WarmedxMints/ODEliteTracker). If they're in your toolkit too,
consider chipping in. WNTB asks for nothing except feedback.

## AI assistance

Design and code by R.W. Harper, with code review and documentation help from Claude (Anthropic).
Disclosed for transparency; authorship is unchanged.

*Elite Dangerous* and related marks are trademarks of Frontier Developments plc. WNTB is a fan-made
tool, not official Frontier software, and is not affiliated with the EDMC team or any project above.
