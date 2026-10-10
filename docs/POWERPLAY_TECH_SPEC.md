# Technical Specification — Powerplay

**Author:** R.W. Harper (CMDR Bocheaux)
**Last updated:** 2026-10-08 (see `CHANGELOG.md`)
**Status:** work in progress. Feedback, bug reports and suggestions are welcome: [open an issue](https://github.com/rwharpernc/wayward-nomads-toolbox/issues) or find me in the Wayward Nomads squadron.

The standing reference for Powerplay mode: how merits are attributed to an activity, how Control Points
are estimated, how sessions work, and how the Rare Goods Finder fits in. For how to use it, see the
[README](guide/powerplay.md). For how the code is organised in general, see
[TECHNICAL.md](TECHNICAL.md).

## 1. Goals

- Show the merits (and estimated Control Points) you earn for your pledged Power, live, per session and
  per system.
- Keep a history of sessions and make one easy to copy into Discord or a forum post.
- Track each commander's activity **per system, per numbered Powerplay cycle and per day**, with each system's
  standing and how it moved, rebuilt from the journals as far back as needed (section 11).
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

**File → Settings → WNTB → Powerplay** (keys start `wntb_powerplay_`): the three merits-per-CP ratios,
the clipboard format, and how many cycles the start-up journal scan covers (`wntb_powerplay_backfill_cycles`,
default 4, 1-12). Sessions, cycles and history need no setting.

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

- The Systems tab (section 11) only knows what the commander's own client has seen: a system's standing
  updates when they jump in or log in there. Cycles from before the feature was installed are rebuilt from the
  journals (section 11.2c), but only as far back as the journals still exist and the scan depth allows.

## 11. Per-system tracking (Systems tab)

The Sessions window's **Systems** tab is the Powerplay counterpart of the BGS report
([BGS_TECH_SPEC.md](BGS_TECH_SPEC.md)): per commander, per system, per cycle.

### 11.1 Cycle
Cycles are numbered: **cycle 101 began 2026-10-01 07:00 UTC** and the number counts weeks from there
(`powerplay_ledger.cycle_number`, anchored by `ANCHOR_CYCLE`/`ANCHOR_START`). The window labels them "Cycle 101".
A cycle is the weekly Powerplay period, **Thursday 07:00 UTC to the next** (`powerplay_ledger.cycle_start_for`).
This is an assumption about Frontier's schedule; it is one constant in the module if it ever moves. There is no
network lookup (BGS needs one for its irregular tick; this does not). A cycle that ends while EDMC is closed
is archived on the next start. `MAX_ARCHIVE` (52) closed cycles are kept.

### 11.2 What is recorded
- **Standing** - from `FSDJump`, `Location` and `CarrierJump` (`Docked` doesn't repeat the fields):
  `PowerplayState`, `ControllingPower`, `Powers`, `PowerplayStateControlProgress` (0-1, shown as %),
  `PowerplayStateReinforcement`, `PowerplayStateUndermining`. `before` is the baseline - the newest reading
  from an earlier cycle, else the first reading this cycle - and `now` the newest. The change is `now - before`,
  so it reflects **everyone's** work on the system, and it is blank until two readings exist. At a rollover each
  system's newest reading becomes the next baseline. Readings are applied in timestamp order, so a replayed
  older one never overwrites a newer one.
- **What you did** - merits and event counts per activity per system, recorded from the same
  `_handle_merits` path (and **Rescan**) that fills the session, using the same activity attribution
  (section 3). CP is derived at display time from the current ratios, as in section 4, and is never stored.
  Merits timestamped before the cycle began are ignored.

The session tallies in section 6 are untouched and remain per game login; the ledger is per **cycle**, so
they can differ (a session can straddle a cycle boundary). Reset Session / Reset Current System act on
sessions only.

### 11.2b Power and totals per cycle
The ledger notes the Power(s) the commander is pledged to (`record_power`, called wherever the session is told:
`Powerplay`, join, defect, merits, pledge recovery). The list is stored with the cycle when it is archived and
carried into the next cycle (still pledged until told otherwise); a defection mid-cycle gives that cycle two
Powers. A commander who is not pledged records none and shows "not pledged" - their standing readings are
still kept, since system standing doesn't depend on a pledge. Leaving a Power doesn't erase it from the cycle
it happened in. `CycleView.merit_totals()` and `systems_worked()` give the cycle-wide figures behind the
cycle total line on the Systems tab and the rows of the **Cycles** tab (one row per cycle, newest first, live
cycle first). Everything is per commander: each has their own ledger, Power and pins in `powerplay_state.json`.

### 11.2c Journal scan (back-fill)
`powerplay_backfill.py` rebuilds what EDMC missed from the commander's `Journal*.log` files, planned by
`PowerplayLedger.plan_scan(now, depth)` which returns a `ScanPlan`: the current cycle number and the day of it
(1-7), the `missing_cycles` (wanted cycles older than `covered_from`), the mode, and `days_back`. It runs in
`PowerplayController._switch_cmdr`, i.e. once when a commander is first seen in a session.

| Mode | When | Reads |
|---|---|---|
| **rebuild** | never scanned (`covered_from` is None), or the history doesn't reach back `depth` cycles | from the oldest wanted cycle start, into a fresh ledger that is merged in (`adopt`) |
| **incremental** | covered, and the journal was last seen more than 2 minutes ago | from `seen_to` (the newest journal timestamp the ledger is current with; every live event moves it), never earlier than the oldest wanted cycle |
| **none** | covered and seen moments ago | nothing |

`depth` is the setting `wntb_powerplay_backfill_cycles` (default 4, 1-12). A cycle is wanted if it is one
of the last `depth`. After a rebuild `covered_from` is the oldest wanted cycle's start, so later starts are
incremental, a bigger depth rebuilds only the new range, and journals that no longer exist are not retried every start.

How it stays correct:
- **Worker thread, no shared state.** The worker only reads files and returns a list of `Op`s (snapshot, merits, power);
  the main thread applies them in time order (`apply_ops`) - so a cycle that ended during the gap is archived in
  its own place by the ledger's normal rollover. Live events that arrive during the scan are buffered and applied after it.
  The cycle is not rolled by the clock while a scan runs (`_tick_cycle`), only after.
- **No double counting.** The ledger keeps `last_merit_ts` and `last_merit_n` (how many merit events share that
  second): a replayed merit older than it is skipped, and at that second only the first `last_merit_n` replayed events are.
  Standing readings are applied in timestamp order, so repeating one is harmless.
- **Per commander.** Each file is read with the commander named by its `Commander`/`LoadGame` events; a different
  commander's events are skipped, and a fresh `PowerplayTracker` starts at each `Fileheader` and whenever the commander
  changes. Everything of the commander's feeds the tracker (the pledge and the system context come from events
  before the window); only events inside the window become ops. After a relog to a *different* commander in one
  launch there is no new `Powerplay` event, so the pledge is learned from the first `PowerplayMerits` (it names the Power).
- **Never lose data.** For a cycle both the saved ledger and the rebuild have, the one with more merits wins.
- **On time.** The cycle rolls on the clock whenever an event arrives or the window refreshes, not only at the next
  merit; `ledger.views()` lists covered cycles with no activity as empty rows, so the history is gap-free and newest first.
- If the journal folder isn't set or readable nothing is learned and nothing is marked covered, so it is tried again next start.

The Cycles tab shows the plan or the result in one line (cycle, day of 7, days read, files, merit events). Reading
28 days of journals took about 0.3 s per commander on a 1.6 GB journal folder (files are chosen by modification
time and lines are pre-filtered before JSON parsing).

### 11.2d Daily breakdown
The ledger tallies merits per activity per **cycle day** (`daily`, keys "1" to "7"): day = whole 24-hour periods since
the cycle start + 1, so day 1 is Thursday 07:00 UTC to Friday 07:00 UTC. It is archived with its cycle and reset at a
rollover. The **Daily** tab (`powerplay_systems_tab.DailyTab`, `daily_rows`) shows merits and estimated CP per day as whole
numbers with a total; the live cycle stops at today. CP is derived from the current ratios (section 4), never stored,
and the delivery and unattributed merits count in merits only, as everywhere else.
`SCHEMA` (2) marks the saved layout: a ledger saved before the daily tally existed (schema 1) is planned as a **rebuild**
once, which fills the days in from the journals, then marked current. A cycle whose journals are gone and which was
kept because its saved merits were larger has no per-day split; the tab says so.

### 11.2e Keeping the window responsive
The Sessions window is a set of table widgets, and the controller asks it to refresh on every journal event. So
`SessionWindow.refresh` only records the new data and schedules one redraw 250 ms later (many calls = one pass); the
redraw updates just the selected tab and marks the others stale, to be drawn when selected (`Tabs.on_select`); and
tables are filled with `DataTable.set_rows`, which skips a table whose rows haven't changed. Before this a refresh
cost 0.6 to 1.2 s on a real history, and a burst of events froze EDMC. The **Refresh** button redraws immediately.

### 11.3 Tabs and pins
Same model as the BGS report (`powerplay_ledger.TabPrefs`, `CycleView.systems`): pinned systems first
(sorted, starred, always shown even with no data, in every cycle), then the `RECENT_SYSTEMS` (6) most
recently active others with the current system leading in the live cycle, minus hidden ones. **Close tab**
hides and unpins; **Show a system** (type-ahead over every known system, free text allowed) pins and un-hides.
Unlike the BGS report, pins are **capped at `MAX_PINNED` (5)**: pinning a sixth, or adding one, shows a
message and changes nothing; re-adding an already pinned system always works. The cap is re-applied when a
state file is loaded.

### 11.4 Persistence
`powerplay_state.json` in the plugin folder, keyed per commander (case-insensitive match, written
atomically, other commanders' entries preserved; `powerplay_state.py`, same convention as `bgs_state.py`).
Holds `ledger` (current cycle + archive), `pinned_systems` and `hidden_systems`. It is protected from
updates (`update.py`). The controller switches ledger and pins whenever the commander changes.

### 11.5 Tests
`tests/test_powerplay_ledger.py` covers cycle boundaries, snapshot parsing, standing changes, merit
tallies, rollover and carried baselines, the archive cap, tab ordering, the pin cap, serialisation and the
per-commander state file. `tests/test_powerplay_backfill.py` covers the replay (attribution, commanders kept apart, files
and the window), applying ops twice, same-second merits, a gap across a cycle boundary, rebuild and adoption, the
scan plan in every mode, empty-cycle rows, the per-day tally (boundaries, archiving, saving, the one-time rebuild) and reading real files. The widgets are exercised by hand in EDMC.
