# Exploration

Exploration mode is one scrolling panel with several sections stacked top to bottom. Some sections start folded:
click a section's title (▸ / ▾) to open it. WNTB remembers which ones you left open.

**On this page:** [Auto-Honk](#auto-honk) · [Discovery Alerts](#discovery-alerts) ·
[Notable Bodies](#notable-bodies) · [Boxel Survey](#boxel-survey) · [Exploration Value](#exploration-value) ·
[Organic Scanning](#organic-scanning) · [Codex Completionist](#codex-completionist) ·
[GEC Nearby POI](#gec-nearby-poi) · [Canonn Nearby POI](#canonn-nearby-poi)

Anything that draws on your game screen needs an overlay. See [Getting started](getting-started.md#what-you-need)
and [Setting up the overlay](../OVERLAY_SETUP.md).

## Auto-Honk

Fires your Discovery Scanner automatically every time you jump into a system, so you never forget to honk.

**How to use it:**

1. Turn it on with its toggle button (**A.H.**).
2. Open **Settings → Exploration → Alerts** to choose which fire button it uses and how long it holds it.
3. Press **Test Honk Now** to check it works without waiting for a real jump.

If you also run EDCoPilot with its own auto-honk, turn one of the two off, or they'll fight each other.

*On Linux this needs `xdotool` and a keyboard key bound to your fire button. See [WNTB on Linux](linux.md).*

## Discovery Alerts

Puts a banner on your in-game screen the moment you jump into a system nobody has scanned, or the moment you're the
first to scan or map a body.

**How to use it:**

1. Click its toggle button (**D.A.**).
2. Make sure an overlay is running. The connection details are on the **Overlay Connection** Settings tab.
3. Use **Settings → Exploration → Alerts** to move the banner (X and Y boxes) or send a test one.

### N.S. and W.D. buttons

Next to the toggle, these find the nearest system whose *primary* star is a **neutron star (N.S.)** or a **white
dwarf (W.D.)**, measured from where you are now. They show the system name and distance, and copy the name to your
clipboard so you can paste it into the galaxy map.

They are manual only: they contact Spansh when you click and never on their own. Jump or reload first so WNTB knows
your position.

## Notable Bodies

Puts a violet banner on your in-game screen when a body you scan is worth a second look. A match comes from the scan
data, so check the body in the system map before you plan around it. It needs the same overlay as Discovery Alerts.

**How to use it:**

1. Open **Settings → Exploration → Alerts → Notable Bodies**.
2. Tick **Enable**. It is off until you do.
3. Choose which rules you want.
4. Press **Test Notable** to see a sample banner. The X and Y boxes move it.

It has no button on the main panel.

### What it looks for

**On to start with** (the rarer finds):

- **High-value body**: any terraformable world, and every Earth-like, water and ammonia world, whether or not you
  can land on it. The log line says if it is undiscovered or unmapped.
- **Terraformable landable**
- **High-g landable** (about 3 g or more)
- **Shepherd moon**
- **Good FSD injection** (5 or 6 of the premium boost materials on a landable)
- **Colliding binary**
- **Green gas giant**: from the Codex, or a gas giant whose surface temperature matches a confirmed green one. The
  game never records a planet's colour, so treat this as a lead, not a fact.

**Off to start with** (because they're common): large landable, landable with rings, close orbit, close binary, high
eccentricity, fast orbit, fast rotation and wide ring.

### How alerts behave

- If a body matches several rules you get **one banner**, for example "High-value body +2".
- A body only alerts **once per rule**.
- Banners take turns if several come at once.
- The limits are Elite Observatory's own defaults.
- If the banner lands on top of another plugin's overlay text (Canonn's, for example), change X and Y.

## Boxel Survey

> **Work in progress.** Boxel Survey is still being built, and I'd really appreciate your feedback. Please
> [open an issue](https://github.com/rwharpernc/wayward-nomads-toolbox/issues) or find me in the squadron.

A tool for exploring the galaxy systematically, system by system. A "boxel" is a small cube of space that Elite's
procedurally generated systems are named after, such as `Outotz LS-K d8-0`.

The section is collapsed by default. It has three modes, which you switch between with the buttons at its top.

### Which mode should I use?

| If you want to... | Use |
|---|---|
| Work through one boxel from start to finish, in order | **Sequence** |
| Clear a whole region (several boxels), tracking what's left across all of them | **Region Sweep** |
| Visit a fixed list of specific systems in a sensible order (a rendezvous, a squadron staging route) | **Waypoint Route** |

If you're not sure, start with **Sequence**. It's the simplest. Waypoint Route is the odd one out: it accepts any
system name, not just procedurally named ones.

### Sequence

1. Set a starting system.
2. Use **Next** and **Prev** to step through the candidates, or **Find Nearby (EDSM)** to jump to the nearest
   unexplored boxel.
3. If several **Next** clicks go by with no real jump, WNTB can check EDSM for the nearest real system for you.

Notable finds (Earth-likes, water worlds, biological signals and so on) are tallied automatically.
**Export Survey Log** (in Settings → Exploration → Boxel Survey) saves them to a spreadsheet file.

### Region Sweep

For clearing a whole region.

1. Add cubes to a queue.
2. Use **Discover Nearby Cubes** or **Discover Known Systems** to fill in what's already known.
3. Mark a cube **Empty** once you've confirmed there's nothing worth surveying. It moves on to the next unfinished
   cube by itself.
4. Optionally turn on **Auto-discover more nearby cubes** (Settings → Exploration → Region Sweep) to keep the queue
   topped up.

### Waypoint Route

1. Add systems one at a time, or with **Import CSV**.
2. Click **Reorder (Nearest-Neighbor)** to sort them by distance from where you are.

### RND: find something nobody has discovered

**RND** (random) sits on the Exploration button row next to A.H., D.A., N.S. and W.D., so it stays visible even
while this section is collapsed, and works in any mode.

It finds a real, known boxel near you, then looks for a name EDSM has no record of, and **copies it to your
clipboard**. Paste it into the galaxy map to go find something new.

It keeps its own log of every system you've actually visited, so a place you've already been to isn't suggested as
"new". Clear that log any time from **Settings → Exploration → Boxel Survey → Clear Visited Systems Log**.

## Exploration Value

A quiet readout of what you're finding. Nothing to turn on. It shows:

- the estimated payout for your last scan,
- the age of the current system,
- which of the galaxy's 42 named regions you're in (for example "Inner Orion Spur").

All of that is worked out on your computer.

Two extras are optional in **Settings → Exploration Value**: how rare the Earth-like world you just found is, and
whether EDSM already knows about a system you've selected on the galaxy map. They contact Spansh and EDSM, so
they're off until you tick them.

## Organic Scanning

Helps you find and identify exobiology life on a planet's surface.

**How to use it:**

1. Detect biological signals on a body and get on the ground.
2. WNTB shows which species each signal is likely to be, based on the planet's atmosphere, gravity, temperature and
   more, with an estimated credit value.
3. When you start sampling, it tracks your progress and tells you when you've walked far enough for the next sample
   to count.

It uses only your own journal and makes no internet connection. It is designed to work alongside
[EDMC-Canonn](https://github.com/canonn-science/EDMC-Canonn) if you run that too. Detail is in the
[specification](../ORGANIC_SCANNING_TECH_SPEC.md).

## Codex Completionist

*(Starts minimized: click the title to open it.)*

A personal tally of everything you've ever scanned: biological, geological, Guardian, human, Thargoid and more.

**How to use it:** it builds itself as you play.

- Click **DET** for the full breakdown. A ⭐ marks a genuine first discovery.
- Click **BKF** (backfill from journal history) **once** to pull in your past journals. It isn't automatic because
  it can take a while for a long career.

The details window has two tabs:

- **Found** is your tally by category. Click the **Entry** heading to sort A–Z or Z–A, or **Times found** for most
  or least found first. Click again to reverse.
- **Not found** lists the biological, civilisation and stellar-body entries you haven't found yet, using Canonn's
  catalogue. It sorts the same way, and the subtitle shows how many you've found. Geological and anomaly entries
  aren't in that catalogue, so they never appear here.

**Double-click any entry** (or select it and click **Open Reference**) to look it up on Canonn's website.

## GEC Nearby POI

*(Starts minimized.)*

Finds the nearest point of interest from edastro.com's exploration catalogue. Click **FIND**. It only looks
something up when you ask.

## Canonn Nearby POI

*(Starts minimized.)*

The same idea, using Canonn's lists of Thargoid and Guardian sites. Click **FIND**.

- The first click downloads the lists, which are then kept for the rest of your session.
- **REF** fetches fresh copies.
- Choose which kinds of site to include in **Settings → Exploration → Points of Interest**.
- By default it skips sites you've already logged in Codex Completionist, so it points you somewhere new. You can
  turn that off in the same place.
