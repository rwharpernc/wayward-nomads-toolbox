# Technical Specification — BGS Tracking

**Author:** R.W. Harper (CMDR Bocheaux)
**Last updated:** 2026-10-02 (see `CHANGELOG.md`)

## 1. Goals

A new WNTB mode that tracks Background Simulation (BGS) activity for factions/systems the commander
explicitly designates, scoped to *only* BGS (Powerplay and Colonization are out of scope, handled elsewhere or not at all).

What it covers:

- Faction **state** visibility (War, Election, Boom, Bust, Outbreak, Civil Unrest, etc.) for tracked
  factions/systems — read-only observation, not something the player caused.
- A **tally** of player actions that move the BGS needle: mission completions (faction INF), bounty
  voucher/combat bond redemptions, trade profit/loss, exploration data sold.
- BGS **tick** detection (the real daily tick that BGS state changes apply on), rolling the tally into
  a new period at each tick, not just a manual/session counter.
- **Per-commander** separation and persistence that survives both a relog and a full EDMC restart.
- Output: in-panel summary + a Treeview popup window (two tabs: Faction States, Activity Tally) +
  copy-to-clipboard text summary. No Discord webhook.
- Scope: only systems/factions the commander configures — never "everything, everywhere". The panel's
  own **Track**/**Untrack** buttons act on whatever system the commander is currently in, in addition
  to the Settings-tab list editors.
- The panel always shows a live breakdown of the *current* system regardless of tracking status
  ("no factions present" for an uninhabited system, or every faction present + controller + state), so
  you can see who is where without having to track anything first.

## 2. Non-goals

- No Discord webhook (deliberately out of scope).
- No murder/crime negative-INF tracking, combat-zone participation, or Thargoid-war state tracking —
  flagged as a known gap (§5), not silently assumed covered.

## 3. Architecture

`PANEL_PLACEMENT = "bgs"` — its own top-level mode button (`ui.py`'s `PANEL_MODES`, placed next to
Powerplay), not folded into an existing mode, since none of the other five map to BGS naturally
(the grouping of modes is a working proposal, not locked in).

```
bgs_tracker.py     Pure logic (no Tk, no network):
                    - FactionSnapshot / parse_faction_entry() - faction-state snapshots.
                    - FactionActivity / parse_mission_faction_effects() / parse_bounty_voucher() /
                      parse_combat_bond() / market_buy_cost() / market_sell_proceeds() /
                      exploration_sale_value() - activity-tally extraction.
                    - is_tracked() / snapshot_key() - shared matching/keying for both.
                    Mirrors organic_scan.py's no-Tk/no-network split.
bgs_state.py       Per-commander JSON persistence (bgs_state.json): tracked systems/factions,
                    faction snapshots, this-tick/previous-tick activity tallies, last-known tick
                    timestamp. Same atomic read/write-temp-then-os.replace convention as
                    boxel_state.py/organic_scan_state.py.
bgs_tick_client.py Sync HTTP client (the only network call) - fetch_latest_tick() against
                    tick.infomancer.uk. No Tk/threading here.
bgs_panel.py       Controller: start/stop/handle_event lifecycle (organic_scan_panel.py's own
                    convention). Main-panel widgets: live current-system faction breakdown,
                    Track/Untrack buttons, activity-tally summary, tick-check status line, "View
                    BGS Report" button. Settings tab: enable toggle, tick-detection toggle
                    (network opt-out), two tk.Listbox add/remove sections (tracked systems,
                    tracked factions - mining_hotspot_settings.py's list-editing pattern,
                    simplified for plain strings). Tick polling uses the
                    queue.Queue/generation-counter/threading.Thread/after()-poll pattern already
                    established by canonn_poi_panel.py/boxel_survey.py, re-armed every 60s
                    instead of only on a button click.
bgs_window.py      Treeview popup report (codex_completionist_window.py's singleton-window
                    show()/refresh()/lift()/close() convention): a ttk.Notebook with "Faction
                    States" and "Activity Tally" (This Tick / Previous Tick) tabs, plus "Copy
                    Summary".
```

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

Every faction present is captured into the panel's live "current system" display regardless of
tracking status; only the subset matching `bgs_tracker.is_tracked()` (tracked-systems OR
tracked-factions, case-insensitive) is persisted into `bgs_state.json`/the report window. Snapshots
are **overwritten wholesale**, never merged field-by-field — the journal always sends the complete
current state for a faction, not a delta.

### 4.2 Mission INF

`MissionCompleted`'s `FactionEffects[]` array: each entry has `Faction` and an `Influence[]` array of
`{Trend, Influence}`, where `Influence` is a string of `+`/`-` characters (Frontier never exposes an
exact percentage) and `Trend` is one of `UpGood`/`DownGood`/`UpBad`/`DownBad`.

**Trend → direction mapping**, as observed in real journal entries: `UpGood`/`DownGood` → +INF,
`UpBad`/`DownBad` → -INF; the pip count is the
length of the `Influence` string (e.g. `"++"` → 2 pips). Tallied per faction as `inf_plus`/`inf_minus`
pip counts plus a mission count — never an exact percentage, since Frontier doesn't provide one.

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

### 4.5 BGS tick detection

`bgs_tick_client.fetch_latest_tick()` does a plain HTTP GET against
`http://tick.infomancer.uk/galtick.json` (10s timeout), reads the `lastGalaxyTick` field, and parses it
with `%Y-%m-%dT%H:%M:%S.%fZ`. This is a **community-run, third-party** endpoint, polled every 60 seconds via `bgs_panel.py`'s own `queue.Queue`/generation-counter/
`threading.Thread`/`after()`-poll loop — never blocks the Tk main thread, and any failure (the service
is down, rate-limits, or changes shape) is treated as "tick unknown for now", never fatal to the rest
of BGS tracking. Toggleable independently (`wntb_bgs_tick_enabled`, on by default) from the rest of
BGS tracking, since it's the only network call this mode makes.

The first successful check after startup establishes a baseline (`tick_last_seen`) without rolling
anything over — only a *subsequent* check whose timestamp differs from that baseline triggers
`_roll_tick_period()`, which moves the current `activity` tally into `previous_activity` and starts a
fresh one.

## 5. Known gaps (not silently dropped)

- Murder/crime negative security INF (`CommitCrime`).
- Combat-zone (ground & space) participation as its own signal (only the resulting bounty/combat-bond
  *redemption* is tracked, not CZ presence/wins directly).
- Thargoid war states.
- Discord webhook export (deliberately out of scope, not a gap to fill later).
