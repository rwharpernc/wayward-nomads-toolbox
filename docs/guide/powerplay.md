# Powerplay

> **Work in progress.** Powerplay is still being built, and I'd really appreciate your feedback. If something looks
> wrong, or you have a suggestion, please [open an issue](https://github.com/rwharpernc/wayward-nomads-toolbox/issues)
> or find me in the Wayward Nomads squadron.

Powerplay mode tracks the **merits** and **Control Points (CP)** you earn for your pledged Power. You see them live
on the panel, and in the Sessions window per session, per system, per Powerplay cycle and per day.

Everything is kept **separately for each commander**. A commander pledged to another Power, or to none, has their
own numbers.

**On this page:** [Using it](#using-it) · [The Sessions window](#the-sessions-window) · [Cycles](#cycles) ·
[The Systems tab](#the-systems-tab) · [Catching up from your journals](#catching-up-from-your-journals) ·
[Good to know](#good-to-know) · [Rare Goods Finder](#rare-goods-finder) · [Settings](#settings)

## Using it

Just play. The panel shows:

- your current system's Powerplay state,
- what you've earned in that system,
- running merit totals for the session.

Your game mode and credits are on the two lines under the mode buttons.

Two buttons on the bottom row:

- **SES** opens the Sessions window.
- **RESCAN** re-reads your journal from scratch. Use it if a session's numbers ever look wrong.

## The Sessions window

Click **SES**. It has five tabs.

| Tab | What it shows |
|---|---|
| **Current session** | This login: merits and estimated Control Points by system and by activity, and the Power context WNTB is using. |
| **Systems** | One tab per system for the cycle, with the system's standing and what you earned there. |
| **Cycles** | One row per Powerplay cycle, newest first: period, the Power you were pledged to, systems worked, merits, estimated CP, merits by activity. |
| **Daily** | Merits and estimated CP (whole numbers) for each day of a cycle, with a total. |
| **History** | Every past session. |

### Cycles

A Powerplay cycle runs from **Thursday 07:00 UTC** to the next Thursday 07:00 UTC, and is numbered. For example,
cycle 101 began on 2026-10-01. Each day of a cycle also runs 07:00 to 07:00 UTC, so **day 1 is the Thursday**.

The Systems, Cycles and Daily tabs all have a drop-down to look at an earlier cycle.

### The Systems tab

A line above the tabs totals the cycle: merits, estimated CP and how many systems you worked. Then, one tab per
system:

- **Standing** compares a baseline with the latest reading. The baseline is the system's last reading before the
  cycle began, or your first reading this cycle. The table shows state, controlling Power, control progress,
  reinforcement and undermining, and the change.

  These are **whole-system figures from the journal**, everyone's work and not just yours. So if you're defending a
  system, you can see it gaining or losing ground. They only update when you jump into or log in at the system, so
  they are as fresh as your last visit.
- **What you did** shows your own merits there by activity, with estimated Control Points.

**Which systems get a tab?** Your last 6 systems, plus up to **5 you pin**.

- Click **☆ Pin** on a tab to keep it. Pinned tabs stay in every cycle, even with no data.
- Or type a name in **Show a system** (it suggests as you type) and press **Add system**.
- **× Close tab** hides a system.

Pins and hidden tabs are remembered for each commander.

## Catching up from your journals

The first time WNTB sees a commander, it reads their journals to fill in the last few cycles (4 by default; change
it under **Settings → Powerplay → Journal scan**, from 1 to 12). After that it reads only what happened while EDMC
was closed, so **playing without EDMC running doesn't lose a cycle**.

It works out what cycle it is, which cycles aren't in that commander's history yet and how many days back to read,
and does nothing when there's nothing new. The **Cycles** tab shows what it did.

It can't read journals you've deleted, and your own totals are never replaced by smaller ones.

## Good to know

- **Where merits came from is a guess.** The journal doesn't say which activity merits came from, so WNTB infers it
  from the system you're in. The same applies to the per-system and daily numbers.
- **Control Points are estimates.** They are worked out from merits using ratios you can edit.
- **Delivery and unattributed merits count as merits only**, with no CP estimate.
- The detail is in the [Powerplay specification](../POWERPLAY_TECH_SPEC.md).

## Rare Goods Finder

Click **RARES** to see the rare commodities closest to where you are. Each row shows:

- the origin system and station,
- the landing-pad size,
- which Power currently controls that system, which is handy for Powerplay hauling.

**Tips:**

- **Double-click a row** to open that commodity on Inara.
- Use **Show nearest** to choose how many rows to see (up to all 141).
- The list needs your position, so it says "Awaiting system data" until your first jump or login after EDMC starts.
- A "—" in the Power column means unclaimed, or couldn't be checked.

The first time you open it for each system it asks Spansh which Power controls it. See
[what goes on the internet](internet-and-privacy.md).

## Settings

**Settings → Powerplay**:

- The merit-per-Control-Point ratios. Only change these if Frontier changes them.
- The text used when you click **Copy Progress**, which puts a summary on your clipboard to paste into Discord or a
  forum post.
- How many cycles the start-up journal scan covers.
