# WNTB user guide

Plain-language guides for using the Wayward Nomads Toolbox. New here? Start with
[Getting started](getting-started.md).

## How WNTB knows what it knows

Like every third-party tool for Elite Dangerous, WNTB only knows what the game writes to its journal files. Much of what makes play easier starts there, and not everything is logged. Where the journal is silent, WNTB adds what it can from other places: figures Frontier's own servers give a signed-in EDMC (such as a fleet carrier's cargo), and data that players and community services report (Spansh, EDSM, Canonn, edastro, Raven Colonial and others). Where none of that exists, WNTB works around the gap with an estimate that it marks as one, or with a step you take (such as opening Carrier Management so the game reports the figure). Until Frontier expands the journal or offers a broader API, these workarounds are part of how WNTB works, and every guide lists the gaps it knows of.

Three layers, in the order WNTB prefers them:

1. **The journal** is the source for everything about *you*: your trades, scans, missions, deliveries, merits and so on. If the game
   doesn't write it down, WNTB can't see it, and no setting changes that.
2. **Other places that know more**: Frontier's servers (through a signed-in EDMC) and the data players and communities report. WNTB
   uses these to fill gaps the journal leaves, never to overrule it, and the [internet page](internet-and-privacy.md) lists every one.
3. **Workarounds, marked as such**: WNTB's own bookkeeping (for example, tallying what you transfer to a fleet carrier), estimates
   labeled as estimates, and steps you can take (such as opening Carrier Management) to make the game write what it normally doesn't.

**Every mode guide ends with a section called "What the game does and doesn't tell us, and how to work around it"** listing each gap we
know of, how it looks on screen, and what to do. Where a figure is an estimate, WNTB marks it as one.

## Setting up

| Guide | What's in it |
|---|---|
| [Getting started](getting-started.md) | What you need, installing, updating, finding your way around, opening windows, button names |
| [Setting up the overlay](../OVERLAY_SETUP.md) | The on-screen helper for alerts and diagrams |
| [Windows and Linux](platforms.md) | What works where |
| [WNTB on Linux](linux.md) | Step-by-step Linux and Flatpak setup |
| [What goes on the internet](internet-and-privacy.md) | Every feature that contacts an outside site |
| [Reporting a problem](reporting-problems.md) | The **Report an issue** and **Copy diagnostics** buttons, step by step, and what they include |

## The modes

| Mode | Guide |
|---|---|
| **Powerplay** | [Powerplay](powerplay.md): merits, cycles, sessions, rare goods |
| **Exploration** | [Exploration](exploration.md): Auto-Honk, alerts, Boxel Survey, exobiology, Codex, Notes, Expedition planner, Compass |
| **Mining** | [Mining](mining.md): space and surface mining, the Mining Book |
| **Trade** | [Trade](trade.md): profit, routes, prices, Watch list, carrier cargo, History |
| **Missions** | [Missions](missions.md): every mission in one view, the Missions window and pinning, progress colours, where to buy mission cargo |
| **Field Ops** | [Field Ops](field-ops.md): screenshots, inventory, engineering materials, blueprints, a wishlist, ship and Odyssey upgrade planners, where the engineers are, material traders, ship builds |
| **Colonization** | [Colonization](colonization.md): your current project, your history, the sites window, where to buy |
| **BGS** | [BGS](bgs.md): factions, states and your effect on them |
| *Always on* | [Landing Assist, Interdiction Warning and Flight Alerts](always-on.md) |

## When something's wrong

[Troubleshooting](troubleshooting.md) lists symptoms and fixes. If it is a bug, [Reporting a problem](reporting-problems.md) shows how to file
one in a few clicks.

## For developers

Technical documentation lives one level up in [docs/](..): [DEVELOPMENT.md](../DEVELOPMENT.md),
[TECHNICAL.md](../TECHNICAL.md), [MODULES.md](../MODULES.md), the feature specifications, and [TODO.md](../TODO.md), the list of open work.
