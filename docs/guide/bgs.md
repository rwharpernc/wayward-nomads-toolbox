# BGS

> **Work in progress.** BGS tracking is still being built, and I'd really appreciate your feedback. If something
> looks wrong, or you have a suggestion, please [open an issue](https://github.com/rwharpernc/wayward-nomads-toolbox/issues)
> or find me in the Wayward Nomads squadron.

The **Background Simulation (BGS)** is the game's behind-the-scenes model of factions and their influence. BGS mode
tracks faction states, and the effect of your own missions, bounties, trade, exploration and crimes on them.

There is nothing to set up: it records wherever you act.

**On this page:** [The panel](#the-panel) · [What it counts](#what-it-counts) ·
[The BGS Report window](#the-bgs-report-window) · [Resets and history](#resets-and-history) ·
[Tick detection](#tick-detection-and-the-internet) · [Settings](#settings)

## The panel

The panel shows **only the system you're in**:

- each faction present (★ marks the controller),
- its state and influence,
- under each faction, what you've done to it **since the last server tick**.

Influence and state show how far they moved since before the tick, for example `45.0% (+5.0)` or `None → Boom`.

## What it counts

Increases and decreases from:

- missions completed (influence pips gained or lost),
- missions failed or abandoned,
- bounty voucher and combat bond redemptions,
- trade profit or loss,
- exploration data sold,
- crimes committed against a faction.

## The BGS Report window

Click **REPORT** (view BGS report).

- A **drop-down** picks the tick: the current one, or an earlier one from the archive.
- There is **one tab per system** you've acted in during that tick.
- Each tab lists every faction there (state, influence and change, pending, recovering and active states) and a
  table of what you did to each.
- A key at the bottom of the window explains the tabs and every column.
- **Copy Summary** copies every tick and system as plain text.

### Which systems get a tab?

Tabs show the last 6 systems you've been in (the one you're in first), each with its full system name.

- **Pin** a tab to keep it. A pinned system (marked ★) stays at the front however long ago you were there, and shows
  a ★ on the panel when you're in it.
- **Close tab** hides one you don't want.
- **Show a system** box: click its arrow to pick from every system you've been in, or just start typing and the list
  narrows as you type (names starting with what you typed come first). Press Enter or click **Add system**. That
  pins it, and it's also how you bring back a closed tab. Any name can be typed, not only ones from the list.

## Resets and history

- The totals **reset at each tick**, and the closed tick is archived.
- When EDMC starts, WNTB re-reads your last few journals, so the totals are cumulative since the tick even if EDMC
  wasn't running the whole time.
- Everything is kept separately for each commander.

## Tick detection and the internet

WNTB checks a community tick-time service **once a minute** to notice the real tick. That is the only internet
connection BGS makes, and you can turn it off in Settings.

Without it, the totals never reset on their own and the journals can't be replayed, because WNTB doesn't know when
the tick was.

## Settings

**Settings → BGS**:

- turn BGS on or off,
- turn tick detection on or off,
- choose how many days of previous ticks to keep (default 7).

More detail: [BGS specification](../BGS_TECH_SPEC.md).
