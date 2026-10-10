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
[What the game does and doesn't tell us](#what-the-game-does-and-doesnt-tell-us-and-how-to-work-around-it) · [Rare Goods Finder](#rare-goods-finder) · [Settings](#settings)

## Using it

Just play. The panel shows:

- your current system's Powerplay state,
- what you've earned in that system,
- running merit totals for the session.

Your game mode and credits are on the two lines under the mode buttons.

Two buttons on the bottom row:

- **SES** opens the Sessions window. **RARES** opens the Rare Goods Finder (see below).
- **RESCAN** re-reads your journal from scratch. Use it if a session's numbers ever look wrong.

## The Sessions window

Click **SES**. It has five tabs.

| Tab | What it shows |
|---|---|
| **Current session** | This login: merits and estimated Control Points by system and by activity, and the Power context WNTB is using. |
| **Systems** | One tab per system for the cycle, with the system's standing and what you earned there. |
| **Cycles** | One row per Powerplay cycle, newest first: period, the Power you were pledged to, systems worked, merits, estimated CP, merits by activity. |
| **Daily** | Merits and estimated CP (whole numbers) for each day of a cycle, with a total. |
| **History** | Every past session of the commander you are playing, with their running total. Other commanders' sessions are kept but not shown, and each commander keeps their own last 200. |

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

## What the game does and doesn't tell us, and how to work around it

WNTB can only show what Elite Dangerous writes to its journal files and what the online services it asks (Spansh for the Rare Goods Power column) publish. Where it can't be sure, WNTB says so rather than guess quietly. Your merit totals always come straight from the journal and are exact.

| What you might expect | What the game gives | What to do |
|---|---|---|
| Each merit tagged with the activity that earned it | The journal does not say. WNTB **infers** the activity from the state of the system you are in; an unusual situation can be misattributed. This also applies to the per-system and daily numbers. | Trust the merit totals. Treat the activity split as a good guess. |
| Control Points reported | The game reports merits only. CP is **estimated** with ratios you can edit in Settings. | Only change the ratios if Frontier changes them. |
| Deliveries counted as CP | The game writes a `PowerplayDeliver` event (what and how many) just before the merits a hand-in earns, but it does not say which kind you chose (Acquisition, Reinforcement or Undermining). WNTB labels the merit events that follow a hand-in *Delivery*: the first one within 10 minutes, and any within 10 seconds of the last. It counts **merits only**. Unattributed merits are the same. A merit from something else that lands inside that window can be mislabelled. | Expect Delivery and Unattributed to add merits but no CP. Hand in as a separate step, away from other merit work, if the split matters. |
| Live standing for any system | Whole-system figures update only when you **jump into or log in** at that system, so they are as fresh as your last visit. | Visit the system again for a fresh reading. |
| Old cycles from before WNTB | They are rebuilt from journals only as far back as the files still exist and the scan depth allows (1 to 12 cycles, 4 by default). | Raise the depth in Settings, and keep your journal files. |
| The Rare Goods list to include new rares | The list is a snapshot (141 rare goods). A new rare needs a WNTB update. | Update WNTB. The Power column also needs Spansh and shows "—" when it can't be checked. |

- The detail is in the [Powerplay specification](../POWERPLAY_TECH_SPEC.md).

## Rare Goods Finder

Click **RARES** to see the rare commodities closest to where you are. Each row shows:

- the origin system and station,
- the landing-pad size,
- which Power currently controls that system, which is handy for Powerplay hauling.

**Tips:**

- **Double-click a row** to open that commodity on Inara.
- Use **Show nearest** (type a number and press Enter or **Apply**) to choose how many rows to see. The list holds
  141 rare goods.
- The list needs your position, so it says "Awaiting system data" until your first jump or login after EDMC starts.
- A "—" in the Power column means unclaimed, or couldn't be checked.

To fill in the Power column, WNTB asks Spansh which Power controls each rare's origin system. Answers are kept until
you restart EDMC (a failed lookup is also kept, so it isn't retried until then). See
[what goes on the internet](internet-and-privacy.md).

## Settings

**Settings → Powerplay**:

- The merit-per-Control-Point ratios. Only change these if Frontier changes them.
- The format of the lines **Copy Progress** copies. That button is in the Sessions window; it puts a summary on
  your clipboard to paste into Discord or a forum post. A **Reset to default** button restores the standard format.
- How many cycles the start-up journal scan covers.
