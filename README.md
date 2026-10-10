<p align="center">
  <a href="https://waywardnomads.org/" target="_blank" rel="noopener noreferrer">
    <img src="docs/images/wwns-patch.png" alt="Wayward Nomads squadron patch - visit waywardnomads.org" width="220">
  </a>
</p>

# Wayward Nomads Toolbox (WNTB)

A free add-on for **Elite Dangerous** that puts a set of handy tools in one panel: Powerplay tracking,
exploration helpers, mining, trading (profit tracking, routes, prices and fleet carrier cargo), missions, on-foot and
cargo tracking, and more. It was built for the
**Wayward Nomads** exploration squadron (WWNS) and is open to anyone who wants it.

It runs inside [EDMC](https://github.com/EDCD/EDMarketConnector) (Elite Dangerous Market Connector), a
free companion program many commanders already use. You don't need to know any programming to use WNTB.

> **Download the latest release, not the repository.** See [Installing](#installing). If you hit a
> problem, see [Getting help](#getting-help).

Built and maintained by R.W. Harper: CMDR Bocheaux (Wayward Nomads, WWNS) and CMDR Mactavious (Easy Day, EZPZ).

---

## Contents

- [What's in the toolbox](#whats-in-the-toolbox)
- [Quick start](#quick-start)
- [Guides](#guides)
- [Getting help](#getting-help)
- [For developers, credits and licence](#for-developers-credits-and-licence)

---

## What's in the toolbox

WNTB has one panel with seven **modes**. You click a button to switch between them.

| Mode | What it's for | Guide |
|---|---|---|
| **Powerplay** | Tracks the merits and Control Points you earn for your Power, and finds rare goods. | [Powerplay](docs/guide/powerplay.md) |
| **Exploration** | Auto-honk, "first discovery" and notable-body alerts, a boxel survey tool, scan values, exobiology help, and a lifetime tally of everything you've scanned. | [Exploration](docs/guide/exploration.md) |
| **Mining** | Tracks space mining and surface (SRV) mining, and keeps your own catalogue of mining hotspots. | [Mining](docs/guide/mining.md) |
| **Trade** | Your trading profit after fuel and repairs, your ship hold and fleet carrier cargo space, saved sessions in a Trade History window, and Spansh lookups for the best trade routes and the best place to buy or sell. | [Trade](docs/guide/trade.md) |
| **Missions** | One view of every mission you have, with kill-progress bars for massacre missions. | [Missions](docs/guide/missions.md) |
| **Field Ops** | Screenshots, your backpack/locker/cargo, saved ship builds, and colonisation sites. | [Field Ops](docs/guide/field-ops.md) |
| **BGS** | Tracks the Background Simulation: faction states, and what your own activity does to them. | [BGS](docs/guide/bgs.md) |

Two more tools are always on and don't belong to a mode: **Landing Assist** and **Interdiction Warning**
([guide](docs/guide/always-on.md)).

Most individual features have their own on/off switch in Settings, and the alerts and overlays are off until you turn them on. The seven mode buttons themselves can't be hidden, and a few sections (for example Boxel Survey and the GEC and Canonn POI finders) can only be folded away, not switched off.

**Full disclosure.** WNTB can only show what the game writes to its journal files and what services such as Spansh
and EDSM publish. Some things the game never records, or records late or in part (for example, a fleet carrier's
cargo is only exact after you open Carrier Management). Each mode guide ends with a section, "What the game does and
doesn't tell us, and how to work around it", listing every gap we know of and what to do about it. Estimates are
marked as estimates on screen.

## Quick start

**You need:** [EDMC](https://github.com/EDCD/EDMarketConnector) on Windows or Linux. For on-screen alerts you also
need an overlay ([EDMCModernOverlay](https://github.com/SweetJonnySauce/EDMCModernOverlay) is recommended), but
everything else works without one.

1. Download **`WNTB.zip`** from the [latest release](https://github.com/rwharpernc/wayward-nomads-toolbox/releases/latest)
   (under **Assets**). Don't use the green **Code → Download ZIP** button.
2. In EDMC open **File → Settings → Plugins → Open** (the plugins folder) and extract the ZIP there, so you end up
   with `plugins/WNTB/load.py`.
3. Restart EDMC. The **Wayward Nomads Toolbox (WNTB)** panel appears.
4. Click the mode buttons under the WNTB title to switch modes. Hover over any button to see its full name. Settings
   are under **File → Settings → WNTB**.

On **Linux**, one more step is needed so WNTB can read your game's journals. See [WNTB on Linux](docs/guide/linux.md).

To update, extract the new ZIP over the old `WNTB` folder (don't delete it first: your saved data lives there).

## Guides

**Set up and learn the basics**

- [Getting started](docs/guide/getting-started.md): installing, updating, finding your way around, every pop-out
  window, every button name.
- [Setting up the on-screen overlay](docs/OVERLAY_SETUP.md)
- [Windows and Linux](docs/guide/platforms.md): what works where.
- [WNTB on Linux](docs/guide/linux.md): step-by-step, including Flatpak EDMC.
- [What goes on the internet](docs/guide/internet-and-privacy.md): every feature that contacts an outside site.

**Use the modes**: see the table above, or the [full guide index](docs/guide/README.md).

**When something's wrong**: [Troubleshooting](docs/guide/troubleshooting.md).

## Getting help

Found a bug, or have an idea? Please open an issue on the project's
[Issues page](https://github.com/rwharpernc/wayward-nomads-toolbox/issues), or find me in the Wayward Nomads
squadron. Say what you were doing, what you expected, and what happened. Including EDMC's log (EDMC's Help menu can
open its log folder) helps a lot. The squadron website is [waywardnomads.org](https://waywardnomads.org/).

## For developers, credits and licence

- **[docs/DEVELOPMENT.md](docs/DEVELOPMENT.md)**: setting up to build, test and change WNTB.
- **[docs/TECHNICAL.md](docs/TECHNICAL.md)**: how WNTB works and why it's built that way.
- **[docs/MODULES.md](docs/MODULES.md)**: every module in `plugin/`, by feature, in one line each.
- **Feature specifications**, each covering what a feature reads, its rules and its limits:
  [Missions](docs/MISSIONS_TECH_SPEC.md), [Mining](docs/MINING_TECH_SPEC.md),
  [Trade](docs/TRADE_TECH_SPEC.md), [Boxel Survey](docs/BOXEL_SURVEY_TECH_SPEC.md), [BGS](docs/BGS_TECH_SPEC.md),
  [Organic Scanning](docs/ORGANIC_SCANNING_TECH_SPEC.md), [Powerplay](docs/POWERPLAY_TECH_SPEC.md) and
  [Screenshots and input automation](docs/SCREENSHOTS_AND_INPUT_TECH_SPEC.md).
- **[docs/guide/](docs/guide/README.md)**: the user guides.
- **[docs/OVERLAY_SETUP.md](docs/OVERLAY_SETUP.md)**: setting up the on-screen overlay (for everyone).
- **[CHANGELOG.md](CHANGELOG.md)**: what has changed.
- **[docs/ATTRIBUTIONS.md](docs/ATTRIBUTIONS.md)**: thanks and acknowledgements to the projects and
  services that helped.

Copyright (c) 2026 R.W. Harper. Released under the [GNU General Public License v3.0](LICENSE).
Third-party notices are in [THIRD-PARTY-NOTICES.md](THIRD-PARTY-NOTICES.md).

*Elite Dangerous* is a trademark of Frontier Developments plc. WNTB is a fan-made tool and is not
official Frontier software.
