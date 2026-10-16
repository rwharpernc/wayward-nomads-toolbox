# Exobiology

Everything WNTB does for exobiology (the plants and organisms you sample on a planet's surface) in one place: the **Organic Scanning** panel in Exploration
mode, the four **overlay cards** that follow you across the surface, the way WNTB **leads you back to a plant** you identified, and the **first footfall**
bonus.

> **Where this comes from:** your scans, signals, codex finds and samples come from the journal, and your position, heading and the body you are near come from
> the game's `Status.json`, so everything about *your* sampling is exact. What the game does not say (which species a planet hosts before you sample, or the
> color variant before the first sample, where the game's rules for it are known) is predicted, and marked as a prediction. Nothing here contacts the internet.

**On this page:** [The pieces](#the-pieces) · [Organic Scanning panel](#organic-scanning-panel) · [The overlay cards](#the-overlay-cards) ·
[Finding your way back to a plant](#finding-your-way-back-to-a-plant) · [First footfall](#first-footfall) · [When the cards reset](#when-the-cards-reset) ·
[Setting up](#setting-up) · [What the game does and doesn't tell us](#what-the-game-does-and-doesnt-tell-us-and-how-to-work-around-it)

## The pieces

| Piece | Where | What it does |
|---|---|---|
| **Organic Scanning panel** | Exploration mode | Predicts the species of each signal, tracks Log, Sample and Analyse, and says when you are far enough for the next sample |
| **Bio status** card | Overlay | Progress, the species and color variant being sampled with three circles, the reward, and the distance to the last sample |
| **Biology** card | Overlay | Each genus on the body with the species it could be, or is, and what each pays |
| **Bio radar** | Overlay | A top-down plot of your samples' circles, your ship and SRV, and the plants you are tracking, with little pointers |
| **Sample popup** | Overlay | A few seconds after each sample: what it was and what it pays |

The overlay pieces need [EDMCModernOverlay](../OVERLAY_SETUP.md) and are **off until you tick them**. They use the Organic Scanning panel's own prediction and
sample tracking, so the cards and the panel never disagree.

## Organic Scanning panel

Helps you find and identify exobiology life on a planet's surface.

1. Detect biological signals on a body (the system scan gives how many) and map it, which names the genera.
2. WNTB shows which species each genus is likely to be, based on the planet's atmosphere, gravity, temperature, pressure, volcanism, its star, the region of
   the galaxy and more, with an estimated credit value.
3. When you start sampling, it tracks your progress (Log, Sample, Analyse) and tells you when you have walked far enough from the last sample for the next one
   to count.

You can switch it off under **Settings → Exploration → Organic Scanning** (**Show predicted species and scan progress**). It uses only your own journal and
makes no internet connection, and it submits nothing. The rules behind the prediction are in the [specification](../ORGANIC_SCANNING_TECH_SPEC.md).

## The overlay cards

Species are written as scientific names: the genus with a capital and the species in lower case (`Tussock pennatis`, `Bacterium aurasus`; the game writes both words with capitals), and a color variant keeps its capital (`Tussock pennatis - Lime`). The game's own common names (Bark Mound, Brain Tree, Amphora Plant and the like) are left as the game writes them. The overlay draws plain text, so a name cannot be italicized there.

Four cards for the body you are on, whether you are in the ship, the SRV or on foot. Each has its own switch under **Settings → Overlays → Exobiology** and its
own entry on **Overlay Placement**.

- **Bio status** (top center) is a short, wide strip, so it can sit above the game's compass. The heading is *Biological signals* with a count of how many you have analysed and a progress bar, which moves a third of a genus
  with each Log or Sample and all of it once analysed. While you are sampling a genus it shows the species and color variant in large type with three circles
  (filled as you take each sample), what the species pays at the right end of that row (**five times as much on a first footfall**, marked `FF 5x`), and how far you are from the last sample
  against the distance the genus needs (`Move 122 m further: 78 m of 200 m`, or `Clear` once you can take the next). With nothing in progress it lists each
  genus with the distance it needs between samples, and `Done` once analysed. A plant you have identified with the Composition Scanner is named at the foot
  until you sample it. On a body you have not mapped it says to map it.
- **Biology** (bottom, left of center). Every genus on the body with the species it could be or is once a sample has named it (with its color variant), and what
  it pays. Before a sample names the real color, a genus whose colors follow the **star** the body orbits or a **surface material** shows `Likely color: Emerald` (or `Lime or White` when more than one material fits) under its row.
  While the species is open the genus shows the **range** it could pay (`1.0M - 5.3M CR`), and each candidate its value and a percentage (`~50%`); a single
  likely species has a `~` before its value. The footer is the range the whole body could pay (`Rewards: 7.6M - 11.9M CR`), and with a first footfall the larger figure
  is on its own line (`First footfall (5x): 38.2M - 59.6M CR`). Analysed species are in the good color. **The percentages are an even share:** the data says which
  species the body's conditions allow, not how likely each one is, so with two candidates each shows about 50%. Treat them as a count of the candidates, not as odds.
- **Bio radar**. (**Settings → Overlays → Exobiology → Radar size** makes the plot larger, Large or Extra large, so every sample circle is drawn larger.) A top-down plot centered on you with straight ahead up, and a small arrowhead with an **N** on its edge that shows which way north lies (the plot turns as you turn, so north moves around it). Each sample you took has a circle as wide as the genus's minimum distance between
  samples: **red** while you are inside it (too close for the next sample), **green** once you are clear. The ship (where it touched down) and the SRV (where you
  launched or left it) are marked `S` and `V`. Under the plot: the distance to the ship, the SRV and your first two samples, each with a **little pointer**
  before it, turned to show which way that thing lies relative to the way you face (straight up means straight ahead). The scale adapts so every circle fits.
- **Sample popup**. For ten seconds after each sample: the species and variant, its estimated value, the distance the genus needs, and whether it was logged,
  sampled or analysed.

## Finding your way back to a plant

When you identify a plant with the Composition Scanner, WNTB remembers where it is (the journal gives its latitude and longitude). It follows **one plant for each
genus you have identified**: the most recent one of that genus that you have not sampled. Identify a Tussock, a Bacterium and a Frutexa and you have three pointers
at once. Up to four plants of a genus are kept for the body, and the list survives restarting EDMC.

- The **Bio radar** marks each tracked plant with a ring and the genus's letter, draws a line from you toward it, and lists it under the plot (`Tussock 94 m`) with a
  **little pointer** that turns to show which way it lies. Each genus has its own color, the same for its ring, its line, its row and its line on Bio status.
- **Bio status** has a line for each, with the distance and direction (`Tussock: 94 m, 60° right`, the lines side by side in one row, each in its genus's color; `ahead` or `behind` when it is nearly straight on or off).
- **How exact a marker is.** The Composition Scanner names a plant from a distance, and the journal records where *you* were when it did, not where the plant is. So a marker is only as exact as that distance: scanned **on foot** it is close to the plant; from an **SRV** it can be a
  hundred meters or more off; from a **ship** it can be two hundred or more (a marker about 200 m off was seen after scanning from the air). WNTB remembers which you were in, draws the marker's ring as wide as the marker may be off, and writes the distance with a `~` (`Tussock: ~210 m, 30° right`) unless
  you scanned on foot. Walk to the ring and look: the plant is inside it. **Sampling the plant makes its spot exact.** The numbers are estimates (about 40, 150 and 250 m for foot, SRV and ship).
- **A pointer goes when you sample that plant.** A Log or Sample taken at a plant drops the marker nearest you for that genus when you are within its reach: about 100 m for an on-foot marker, 300 m for an SRV one, 450 m for a ship one (50 m more when the sample names the same color variant). That is the next most recent plant of that genus you identified, or none if there is no other.
  Analysing a genus clears all of its pointers, wherever you did it.
- Bark Mound and a few other genera whose codex names do not follow the usual pattern are not tracked.

## First footfall

The first commander to set foot on a body is paid **five times** the usual exobiology reward there. The game says whether anyone has, in the body's scan
(`WasFootfalled`), and WNTB shows it:

- **Bio status** and **Biology** mark the reward (`first footfall bonus`) and the Biology footer shows what the body could pay with it.
- **Body info** flags the body (`First footfall`) and adds a row saying exobiology pays five times there when it has life.
- **System targets** marks a body with life where the first footfall is still open (`0/3 life FF`).

The flag is kept once seen, because a later scan after you have landed says the body has been footfalled, and the bonus is still yours. A body scanned long ago
may show as footfalled if someone has landed since; treat the flag as a strong hint and check the in-game body information if it matters.

## When the cards reset

- **Leaving the planet** clears the Exobiology cards: the game stops naming a body once you are away from it. What you sampled is kept for the body and returns
  if you come back.
- The cards are also hidden in hyperspace, while docked, when the game is closed or at its main menu (including while another commander signs in), and a
  different commander loading in starts with a clean slate.
- **System targets** and **Body info** move on to the next body to map or sample: a body drops off System targets when you map it or analyse its last organism, and
  Body info does not hold on to a targeted body that is finished (see [System targets and Body info](exploration.md#system-targets-and-body-info)).
- After a relog or an EDMC restart the cards are rebuilt from your journals, reading back through earlier journals of the same commander while you stayed in the
  system, so a body you scanned before the relog still shows.

## Setting up

1. Set up the [overlay](../OVERLAY_SETUP.md).
2. **Settings → Overlays → Exobiology**: tick the cards you want and press **Test Cards**.
3. **Settings → Overlays → Overlay Placement**: drag each card where you want it in the layout editor. The cards start at the top center (Bio status), the bottom
   center left of the Body info card (Biology), the left middle (Bio radar) and above Biology (Sample popup).

The cards are plain dark panels, so they sit quietly over the game; the text size and colors follow **Settings → Overlays → Appearance**.

## What the game does and doesn't tell us, and how to work around it

| What you might expect | What the game gives | What to do |
|---|---|---|
| The species before you map the body | The scan gives only the number of biological signals; the genera come with the mapping scan. | Map the body. Until then Bio status shows the signal count. |
| The color variant before the first sample | The variant is named by the first sample (or the Composition Scanner). For the genera whose colors follow the star or a surface material, WNTB shows the likely color from the body's star and materials; it takes the system's main star as the star, so in a system with several stars it can be wrong, and a material rule can name more than one color. The plants (Brain Trees, Anemones, Sinuous Tubers) follow the environment in ways WNTB does not predict. | Sample, or scan the plant with the Composition Scanner: the real color replaces the guess. |
| A real chance for each candidate species | The data lists which species a body's conditions allow, with no frequency for each, so the percentages are an even share of the candidates. | The sample names the real species. |
| A certain species before a sample names it | The prediction is a list of candidates from the body's conditions; unknown conditions never eliminate a species, so a candidate may be listed that the game would not allow. | The sample names the real species. |
| The position of a sample taken while EDMC was closed | The journal does not record positions; WNTB reads yours from `Status.json` as you sample. | None: samples taken with EDMC running are kept for the body across restarts. |
| The SRV's position | The journal does not give it; WNTB uses where you were when you launched or left it. | None. |
| A plant's position without the Composition Scanner | Only the scanner's codex entry carries a position. | Scan the plant with the Composition Scanner. |
| The first footfall mark on an old body | It comes from the body's own scan (`WasFootfalled`). | Scan the body again if the mark is missing. |
| A new species from a game update | The species data is a snapshot; a species added later cannot be predicted until the data is regenerated. | Sample it: the sample still names it. |

The Odyssey exobiology tools in the game itself remain the final word. The idea of separate cards for status, predicted species and a sample radar follows
[SrvSurvey](https://github.com/njthomson/SrvSurvey)'s biology plotters; WNTB's are its own code (see [Attributions](../ATTRIBUTIONS.md)).
