# Technical Specification — BGS Tracking

**Author:** R.W. Harper (CMDR Bocheaux)
**Last updated:** 2026-10-03 (see `CHANGELOG.md`)

## 1. Goals

A WNTB mode that shows what the commander is doing to the Background Simulation (BGS), scoped to *only*
BGS (Powerplay and Colonization are out of scope, handled elsewhere or not at all).

- **The panel shows only the current system**: each faction's state and influence (with the change since
  before the tick) and, under it, what the commander has done to that faction this tick.
- **The BGS Report window** shows every other system the commander has acted in this tick, one tab per
  system, and earlier ticks via a drop-down (the archive).
- **Everything that moves a faction, up and down**: missions done (+/- INF pips), failed and abandoned
  missions, bounty/combat-bond redemptions, trade profit *or loss*, exploration data sold, crimes
  committed against a faction; plus the faction's own influence and state change since before the tick.
- **Per-tick**: totals reset at each tick and the closed tick is archived for a configurable number of
  days (`wntb_bgs_archive_days`, default 7, 1-90). On start the current period is rebuilt from the
  commander's recent journals, so it is cumulative since the tick even if EDMC wasn't running.
- **Per-commander** persistence that survives a relog and a full EDMC restart.
- No "tracked systems/factions" lists: activity is recorded wherever the commander acts. (Earlier
  versions gated everything on those lists; old state files still load and the lists are ignored.)

## 2. Non-goals

- No Discord webhook (deliberately out of scope).
- No combat-zone participation as its own signal, no Thargoid-war state tracking (section 5).

## 3. Architecture

`PANEL_PLACEMENT = "bgs"` - its own top-level mode button (`ui.py`'s `PANEL_MODES`, next to Powerplay).

```
bgs_tracker.py     Pure parsing: FactionSnapshot / parse_faction_entry(), FactionActivity,
                    parse_mission_faction_effects(), parse_bounty_voucher(), parse_combat_bond(),
                    parse_crime(), market_*(), exploration_sale_value().
bgs_ledger.py      Pure engine. TickLedger = one tick period for one commander: activity per
                    system+faction, FactionTrack per system+faction (`before` = last snapshot before
                    the tick, `now` = newest since), open missions (MissionID -> issuing faction, for
                    scoring failed/abandoned), and where the commander is / which station faction is
                    docked at. process(entry) takes a live OR replayed journal entry; entries older
                    than tick_start update context and `before` but never count as activity.
                    roll() closes the period into an archive record and starts the next (every
                    faction's newest snapshot becomes the next `before`). Also PeriodView (read-only
                    view for the window), prune_archive(), rebuild() and fingerprint().
bgs_journal.py     Reads the commander's recent Journal*.log files (from 3 days before the tick) and
                    returns just the relevant events, filtered by the file's Commander event.
bgs_format.py      Shared wording (panel, window, Copy Summary); clips every journal-sourced name.
bgs_state.py       Per-commander JSON (bgs_state.json): `ledger` (current period) and `archive`
                    (closed periods, newest first). Atomic write-temp-then-os.replace.
bgs_tick_client.py Sync HTTP client (the only network call) - fetch_latest_tick().
bgs_panel.py       Controller + main-panel widgets + Settings tab. Feeds live events to the ledger,
                    polls the tick (queue.Queue/generation-counter/threading.Thread/after() pattern),
                    runs the journal replay on a worker thread, archives on a new tick.
bgs_window.py      Report window (uikit): tick drop-down + one tab per system, each with a "Factions"
                    table and a "What you did" table. Up to 8 tabs (the tab bar doesn't wrap); Copy
                    Summary always has every system.
```

### 3.1 Tick lifecycle

1. A journal event reveals the commander (`_switch_cmdr` loads the saved ledger + archive).
2. The tick poll returns the latest galaxy tick `T`. Once both are known, `_reconcile_tick()` runs:
   - stored `tick_start` older than `T` (a tick passed, maybe while EDMC was closed) -> archive the
     stored period, start a new one at `T`;
   - no stored `tick_start` -> adopt `T`.
3. `_start_backfill()` (once per commander + tick per session) replays the journals on a worker thread
   into a fresh `TickLedger`. Live events that arrive meanwhile are buffered; when the replay finishes
   they are applied on top, skipping any the replay already saw (matched by `fingerprint()`). If no
   journal events are found (folder unset/unreadable) the live ledger is kept untouched.
4. Later ticks while running: same as step 2's roll, then a new replay.

If tick detection is off or unreachable and no tick was ever stored, there is no period boundary: the
ledger just accumulates live and no replay happens.

Archive limits: ledgers keep `before` baselines for factions seen within the archive-days window
(`prune_tracks`); archived periods keep faction tracks only for systems with activity.

## 4. Journal fields

### 4.1 Faction-state snapshot

`FSDJump`/`Location`/`CarrierJump` events each carry:

- `StarSystem` (string) — used instead of the `system` argument EDMC passes into `handle_event`
  where available, falling back to it otherwise.
- `SystemFaction: {Name, FactionState}` — the system's current controller, used only to flag
  `is_controlling` on the matching faction's snapshot.
- `Factions: [...]` — one entry per minor faction present, each with `Name`, `FactionState`,
  `Government`, `Allegiance`, `Influence` (0.0–1.0 fraction, displayed ×100 as a percentage),
  `Happiness`/`Happiness_Localised`, `PendingStates: [{State, Trend}]`, `RecoveringStates: [...]`,
  `ActiveStates: [{State}]`.

Every faction present is stored on the ledger as a `FactionTrack`: a sighting before the tick replaces
`before`, a sighting since replaces `now`. Snapshots are **overwritten wholesale**, never merged
field-by-field — the journal always sends the complete current state for a faction, not a delta. The
influence change shown is `now - before` in percentage points; it is blank when either end is unknown
(e.g. a system first seen after the tick with no earlier journal record).

### 4.2 Mission INF

`MissionCompleted`'s `FactionEffects[]` array: each entry has `Faction` and an `Influence[]` array of
`{Trend, Influence}`, where `Influence` is a string of `+`/`-` characters (Frontier never exposes an
exact percentage) and `Trend` is one of `UpGood`/`DownGood`/`UpBad`/`DownBad`.

**Trend → direction mapping**, as observed in real journal entries: `UpGood`/`DownGood` → +INF,
`UpBad`/`DownBad` → -INF; the pip count is the
length of the `Influence` string (e.g. `"++"` → 2 pips). Tallied per faction as `inf_plus`/`inf_minus`
pip counts plus a mission count — never an exact percentage, since Frontier doesn't provide one.

### 4.2b Failed and abandoned missions

`MissionFailed` and `MissionAbandoned` carry only a `MissionID`, no faction. The ledger remembers each
`MissionAccepted`'s `Faction` and the system it was accepted in, and scores the failure/abandonment
against that faction there (an INF decrease). Missions accepted before the replay window are unknown and
skipped; the open-mission map is persisted (capped at 400) to cover missions that outlive a restart.

### 4.3 Bounty vouchers & combat bonds

`RedeemVoucher` — the authoritative BGS-credit source (the effect applies at redemption, not at the
kill, so there's no need to correlate with `Bounty`/`FactionKillBond` events at all):

- `Type == "bounty"`: carries a `Factions: [{Faction, Amount}]` array — a single redemption can cover
  bounties earned against several factions at once.
- `Type == "CombatBond"`: carries a single top-level `Faction`/`Amount` pair instead — **not** a
  `Factions[]` array (a combat bond is always earned fighting for one faction's side in one conflict
  zone).

This asymmetry is observed in real journal entries — easy to get wrong by assuming both shapes match.

### 4.4 Trade profit/loss & exploration data sold

`MarketBuy`/`MarketSell` (using `TotalCost`/`TotalSale`) and `SellExplorationData`(legacy)/
`MultiSellExplorationData` (using `TotalEarnings`, falling back to `BaseValue + Bonus` for the legacy
event, which has no `TotalEarnings` field) are all attributed to **the current station's controlling
faction** — captured from the preceding `Docked` event's own `StationFaction.Name` field, not the system's overall controller. Trade
profit is `trade_sell_credits - trade_buy_credits`, net of nothing else — an approximation (net
credits transacted, not an exact supply/demand BGS-rules model), called out explicitly in the
Settings-tab description.

### 4.4b Crimes

`CommitCrime`: `Faction` (the faction the crime was committed against) and `Fine` or `Bounty`. Counted
per faction as a crime plus the credits incurred; shown as an INF decrease. Attributed to the current
system.

### 4.5 BGS tick detection

`bgs_tick_client.fetch_latest_tick()` does a plain HTTP GET against
`http://tick.infomancer.uk/galtick.json` (10s timeout), reads the `lastGalaxyTick` field, and parses it
with `%Y-%m-%dT%H:%M:%S.%fZ`. This is a **community-run, third-party** endpoint, polled every 60 seconds
via `bgs_panel.py`'s own `queue.Queue`/generation-counter/`threading.Thread`/`after()`-poll loop — never
blocks the Tk main thread, and any failure is treated as "tick unknown for now", never fatal. Toggleable
independently (`wntb_bgs_tick_enabled`, on by default), since it's the only network call this mode makes.
See section 3.1 for what a new or first-seen tick triggers.

## 5. Known gaps (not silently dropped)

- Murder/crime beyond what `CommitCrime` reports (e.g. no victim-faction attribution for kills).
- Ticks before this feature was installed: the tick API only gives the *latest* tick, so earlier
  periods can't be reconstructed from old journals; the archive starts filling from the first tick
  WNTB sees roll.
- Combat-zone (ground & space) participation as its own signal (only the resulting bounty/combat-bond
  *redemption* is tracked, not CZ presence/wins directly).
- Thargoid war states.
- Discord webhook export (deliberately out of scope, not a gap to fill later).
