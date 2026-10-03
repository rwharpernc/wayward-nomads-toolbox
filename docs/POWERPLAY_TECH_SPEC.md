# Technical Specification — Powerplay

**Author:** R.W. Harper (CMDR Bocheaux)
**Last updated:** 2026-10-02 (see `CHANGELOG.md`)

The standing reference for Powerplay mode: how merits are attributed to an activity, how Control Points
are estimated, how sessions work, and how the Rare Goods Finder fits in. For how to use it, see the
[README](../README.md#powerplay). For how the code is organised in general, see
[TECHNICAL.md](TECHNICAL.md).

## 1. Goals

- Show the merits (and estimated Control Points) you earn for your pledged Power, live, per session and
  per system.
- Keep a history of sessions and make one easy to copy into Discord or a forum post.
- Credit income and the game mode (Open / Solo / Private Group) are **not** part of Powerplay. They are
  shown on the always-visible lines under the mode buttons (`session_credits.py`, `game_mode.py`).
- Offer a Rare Goods Finder for Powerplay hauling.

## 2. Non-goals

- **No exact Control Points.** The journal never reports them (see §4).
- **No guessing for hand-ins.** Deliveries aren't turned into Control Points (see §3.3).
- **No network access** except the Rare Goods Finder's Power lookup (see §7).

## 3. How an activity is decided

### 3.1 The problem
The journal's `PowerplayMerits` event reports the merits you gained and your new total, after every game
bonus and penalty. It does **not** say which activity earned them. WNTB infers it from **where you are**.

### 3.2 The inference
`FSDJump`, `Location` and `Docked` report the current system's **PowerplayState** and the **Power(s)**
involved whenever the system is Powerplay-relevant. Compared with the Power you're pledged to, that tells
WNTB what kind of activity merits earned there are most likely to be. `classify_current_activity` applies
these rules in order:

1. **A hand-in just happened:** *Delivery/Donation* (see §3.3).
2. **Not pledged:** *Unattributed*.
3. **The system context is stale** (you've moved on from the system it was captured in): *Unattributed*.
   WNTB prefers to say it doesn't know over using another system's data.
4. **The system is controlled** (state Exploited, Fortified, Stronghold, Controlled or Home system):
   - controlled by **your** Power → **Reinforcement**;
   - controlled by **another** Power → **Undermining**;
   - controlled but no controller reported → **Acquisition** if your Power is listed as active there,
     otherwise *Unattributed*.
5. **Any other state** (Unoccupied, Contested, Turmoil and so on, where nobody holds it yet) →
   **Acquisition**.
6. **No state at all:** *Unattributed*.

### 3.3 Deliveries
Handing in Powerplay commodities (`SearchAndRescue` with a Power commodity) or on-foot data
(`DeliverPowerMicroResources`) earns merits through a separate path. The journal doesn't link the hand-in
to the `PowerplayMerits` event it triggers, and the target (Acquisition, Reinforcement or Undermining) is
chosen in the game and isn't reported either. So WNTB marks the **next merit gain** as *Delivery* and
counts it in merits only, never Control Points. The same goes for *Unattributed*.

## 4. Control Points

Control Points depend on the activity, and Frontier hasn't documented the conversion. WNTB therefore uses
**merits-per-Control-Point ratios that you can edit** in Settings, not constants:

| Activity | Default merits per CP |
|---|---|
| Acquisition | 4.0 |
| Reinforcement | 2.5 |
| Undermining | 4.2 |

These are community estimates (Undermining is the least certain), and Frontier retunes Powerplay between
updates, so correct them if your in-game totals don't line up. CP is **not stored**: it is worked out from
the stored merits and the current ratios when displayed, so fixing a ratio corrects past sessions too.

## 5. Pledge status

The journal only says when you **are** pledged: a `Powerplay` event is written at the first login of a
game launch. There's no "not pledged" event, so WNTB starts at *unknown* and, if no `Powerplay` event has
arrived by the next `Location`, concludes *not pledged*. `PowerplayJoin`, `PowerplayLeave` and
`PowerplayDefect` update it as they happen.

If WNTB starts mid-session or after a relog, no new `Powerplay` event is coming, so it **reads the journal
file backwards** to recover the pledge from earlier in the same game launch, the same approach Auto-Honk
uses for the binds file.

## 6. Sessions

A session covers one **game login**, tied to the journal file it started in. This means:
- A logout to the menu and back, or restarting EDMC mid-game, **continues the same session** instead of
  splitting it (same file, no replay).
- A "last merit" timestamp acts as a high-water mark, so a **Rescan** can tell a gain that's already
  counted from one missed while EDMC was closed.

Each session stores raw merits and event counts per activity, the same broken out **per system**, the
Power. History is kept in
`sessions.json` in the plugin folder, **capped at 200 sessions** so it can't grow forever, and is
protected from updates. The **Sessions** window shows the live breakdown and the history, and **Copy**
puts a summary on the clipboard using a format you can edit in Settings.

## 7. Rare Goods Finder

A window listing the rare commodities closest to your current system.

- **The list is bundled** (`rare_goods.json`, 141 rare goods): each has its origin system and station,
  landing-pad size, cost, legality restrictions, Powerplay eligibility, system coordinates, an Inara id and
  a Spansh system id. Rare goods never move, so none of this is fetched at runtime. The coordinates and ids
  were looked up once when the list was compiled.
- **Nearest** is computed locally from your `StarPos`: straight-line distance in light years, nearest
  first, up to the number you choose (1 to 141, remembered).
- **Controlling Power** is the one live lookup: Spansh's public system endpoint, for each origin system,
  because control changes weekly. Results are cached for the session, failures included, at most 5 at a
  time. A "—" means unclaimed or unreachable. See
  [TECHNICAL.md](TECHNICAL.md#keeping-api-traffic-low).
- Double-click a row to open the commodity on Inara, using the stored id.

## 8. Settings

**File → Settings → WNTB → Powerplay** (keys start `wntb_powerplay_`): the three merits-per-CP ratios and
the clipboard format. Sessions and history need no setting.

## 9. Testing

The Rare Goods lookup has unit tests (`tests/test_rare_goods.py`). The merit-to-CP conversion, activity
classification, session handling and clipboard formatting are mostly pure logic but **have no automated
tests yet**; they are exercised by hand in EDMC, along with the panel and windows. Adding tests for them is
the most useful next step for this feature.

## 10. Known gaps

- Activity is an **inference** from system state; an unusual situation can be misattributed. The merit
  totals are always right, since they come straight from the journal.
- The merits-per-CP ratios are estimates.
- Deliveries and unattributed merits don't produce Control Points.
- The Rare Goods list is a snapshot; a new rare good needs the list updated.
