# Trade mode specification

How Trade mode (the **TRD** button) works, what each module owns, which journal events and web services it
reads, and what has and hasn't been verified. For what it does for the user, see the
[README](../README.md#trade). For the plugin-wide rules it follows (feature contract, main-window sizing,
threading, persistence), see [TECHNICAL.md](TECHNICAL.md).

**Contents**

1. [What it is](#1-what-it-is)
2. [Modules](#2-modules)
3. [The three pages](#3-the-three-pages)
4. [Data sources](#4-data-sources)
5. [Session ledger](#5-session-ledger)
6. [Hold, ship and landing pads](#6-hold-ship-and-landing-pads)
7. [Fleet and squadron carrier cargo space](#7-fleet-and-squadron-carrier-cargo-space)
8. [Routes (Spansh trade planner)](#8-routes-spansh-trade-planner)
9. [Market: commodity search and ranking](#9-market-commodity-search-and-ranking)
10. [Settings, config keys and files](#10-settings-config-keys-and-files)
11. [Limits and network behaviour](#11-limits-and-network-behaviour)
12. [Testing](#12-testing)
13. [Verified, assumed and known gaps](#13-verified-assumed-and-known-gaps)
14. [Platform notes](#14-platform-notes)

---

## 1. What it is

Trade mode is one of the panel's modes (`PANEL_PLACEMENT = "trade"`). It has three pages, switched with the
◀ ▶ arrows at the top:

| Page | Works offline? | Purpose |
|---|---|---|
| Session | Yes | What you bought and sold this login, your ship and hold, and your carrier's cargo space |
| Routes | No (Spansh) | The most profitable trade route from where you are |
| Market | No (Spansh) | Where a commodity sells best, near you and anywhere |

Everything that contacts a web service is **off until enabled** in Settings and runs only when a button is
pressed. The Session page never touches the network.

## 2. Modules

All in `plugin/`. Pure modules have no Tk and no EDMC-only imports, so they are unit-tested directly.

| Module | Kind | Owns |
|---|---|---|
| `trade_panel.py` | UI + controller | The feature-module contract entry point: panel chrome, page rendering, buttons, background jobs, Settings tab, journal dispatch |
| `trade_pages.py` | pure | Page names and order |
| `trade_ledger.py` | pure + file | The session ledger and `trade_ledger.json` |
| `trade_market.py` | pure + file read | `Market.json` parsing and cargo valuation |
| `trade_ship.py` | pure | Ship to landing-pad size, and whether a ship fits a station's pads |
| `trade_carrier.py` | pure + file | Carrier cargo tracking, journal backfill, `trade_carrier.json` |
| `trade_commodities.py` | pure | Matching typed or journal commodity names to Spansh's names; type-ahead suggestions |
| `trade_commodities_data.py` | generated data | The commodity table (from FDevIDs) |
| `trade_prices.py` | pure | Valuing and ranking station offers for your load; carrier split; verdict lines |
| `trade_spansh_client.py` | network | The route planner client (submit, poll, parse) |
| `trade_commodity_entry.py` | UI | The type-ahead entry widget |

Reused from elsewhere: `mining_spansh_client.search_best_price_stations` (the station price search, shared
with Mining's PRICE button), `mining_price_finder_dialog` (the **Price…** button), `inventory_names`
(display-name fallback), `panelkit` (wrapping labels, tooltips, the page arrows, clipboard).

## 3. The three pages

**Session.** `trade_ledger.summary_lines` (profit, tonnes, best sales), then the hold block (`_hold_lines`:
ship and pad size, `used/capacity (free)`, what the docked market would pay, up to four cargo lines), then
the carrier block (`trade_carrier.cargo_lines`). Button: **Reset**.

**Routes.** Idle text shows the start station, ship, cargo size, jump range and budget the search will use.
Buttons: **Find routes** (becomes **Cancel** while searching) and **Copy next system**.

**Market.** A commodity box (type-ahead), then **Near me**, **Galaxy** and **Price…**. The box is shown
only on this page and only when lookups are enabled. Empty box = the commodity you carry most of.

Sizing rule (TECHNICAL.md section 5): the body is one `panelkit.wrap_label`; every station, system and
commodity name is clipped (`_clip`, 34 characters); the buttons are fixed small widgets; the suggestion list
is a separate borderless window of at most eight rows. Nothing can widen EDMC's main window.

## 4. Data sources

Journal events and EDMC state read by `trade_panel.handle_event` (every handler only reads `entry` and
`state`):

| Source | Used for |
|---|---|
| `MarketBuy`, `MarketSell` | Ledger; learning commodity display names (`Type_Localised`) |
| `RefuelAll`, `RefuelPartial`, `Repair`, `RepairAll`, `BuyAmmo`, `RestockVehicle`, `BuyDrones`, `SellDrones` | Running costs in the ledger |
| `Market` (then the `Market.json` file in the journal folder) | The docked market: cargo valuation, "what this station buys" suggestions |
| `Docked`, `Undocked`, `Location` | Route start station; which carrier you are docked at |
| `Loadout` (`Ship`, `MaxJumpRange`) | Your ship and its pad size; jump range for routes |
| `LoadGame`, `StartUp`, `Commander` | Session boundaries; which commander the events belong to |
| `CarrierStats`, `CarrierBuy`, `CargoTransfer` | Carrier cargo space |
| `state["Cargo"]`, `["CargoCapacity"]`, `["Credits"]`, `["ShipType"]` | Hold, capacity, route budget, ship fallback |

The journal folder is `config.get_str("journaldir")` or EDMC's default (same lookup as `journal_scan.py`).

## 5. Session ledger

`trade_ledger.py`. One row per commodity: `bought`, `spent`, `sold`, `revenue`, `cost_basis`; plus an `expenses` map of
category to credits (an older saved ledger without it still loads).

- **Profit** = revenue - cost basis, where cost basis = `AvgPricePaid x Count` from `MarketSell`. The game
  reports what the sold tonnes cost you, so FIFO bookkeeping isn't needed. Stolen and black-market cargo has
  `AvgPricePaid` 0, so the whole sale counts as profit, which matches the credits that arrived.
- **Running costs** are folded in too (`_apply_expense`), from events whose field names were checked against a
  real journal (2026-10-09): `RefuelAll`/`RefuelPartial` (`Cost`) are *fuel*; `Repair`/`RepairAll` (`Cost`) are
  *repairs*; `BuyAmmo` and `RestockVehicle` (`Cost`) are *rearm*; `BuyDrones` (`TotalCost`) adds and `SellDrones`
  (`TotalSale`) subtracts for *limpets*, so that category can read as a gain if you sell back more than you
  bought this session. A zero or missing cost changes nothing. Not counted: insurance rebuys (`Resurrect`) and
  fines (`PayFines`). Costs only count from when WNTB saw them, like trades.
- **Net profit** = trade profit - running costs. With any cost recorded the headline reads "Net profit" with the
  trade profit and each cost beneath it; with none it reads "Profit", as before. Costs before the first trade
  still show ("No trades yet", the costs, "Net: ...").
- **Rate** (credits per hour) is the net figure over first-to-last trade time, so a refuel before the first sale
  doesn't stretch the clock. It appears after 3 minutes (`MIN_HOURS_FOR_RATE`).
- **Session identity** follows `session_credits.py`: one login, tied to the journal file (`monitor.logfile`,
  converted with `str()`) and commander. The same file and commander continue the ledger across a
  logout-to-menu and back; anything else starts fresh.
- **Persistence:** `trade_ledger.json`, atomic write (temp file then `os.replace`), at most once per 30 s plus
  on a new session and on shutdown. Loads tolerate a missing or wrong-shaped file.

## 6. Hold, ship and landing pads

**Hold.** `used/capacity (free)` from EDMC's `state["Cargo"]` and `["CargoCapacity"]`. Display names come
from names learned off market events, then `trade_commodities.resolve`, then `inventory_names.display_name`.

**Ship to pad size** (`trade_ship.py`). Pad class per ship (1 small, 2 medium, 3 large) is a table from the
[Coriolis ship data](https://github.com/EDCD/coriolis-data) (`properties.class`, checked 2026-10-09). The
journal's `Loadout.Ship` is an internal name (`cobramkiii`, `empire_trader`, `type9`); a hand-written map plus
EDMC's own `edmc_data.ship_name_map` (when importable) turns it into a display name first. Names are matched
after lower-casing and dropping everything but letters and digits. An unmatched ship gives `None`, which
means "don't filter" (never "assume small"), and Settings can override the size.

**Fit rule** (`trade_ship.fits`): a ship fits a pad of its own size or larger. Small fits anything; medium
needs a medium or large pad; large needs a large pad. Spansh reports `small_pads`, `medium_pads` and
`large_pads` counts per station; a count Spansh doesn't give (`None`) is treated as "fits" rather than hiding
a good station. Fleet and squadron carriers always fit (they have every pad size and Spansh gives no counts).

The pad filter runs **after** the search, because Spansh's station search has no pad filter we rely on, so a
pad-filtered search asks for 40 stations instead of 20 (`_SELL_FETCH_PAD_FILTERED`).

Routes: Spansh's planner only has a boolean `requires_large_pad`, so a large ship sets it automatically (or
the Settings checkbox does). There is no medium-pad option in that API.

## 7. Fleet and squadron carrier cargo space

`trade_carrier.py`. A commander may have no carrier, a fleet carrier, a squadron carrier or both.

**Records** are `{commander (casefolded): {"FleetCarrier" | "SquadronCarrier": record}}`. A record holds
`id` (CarrierID), `name`, `callsign`, `total`, `capacity`, `cargo`, `reserved`, `free`, `updated`.

**Journal facts used** (the field layout was confirmed on a real `CarrierStats` from 2026-10-09):

- `CarrierStats` carries `CarrierID`, `CarrierType`, `Name`, `Callsign` and `SpaceUsage` (`TotalCapacity`,
  `Crew`, `Cargo`, `CargoSpaceReserved`, `ShipPacks`, `ModulePacks`, `FreeSpace`). It is written **only when
  Carrier Management is opened**, not at login and not after a transfer.
- Cargo bay capacity = `TotalCapacity - Crew - ShipPacks - ModulePacks` (a fresh carrier: 25,000 - 1,280 =
  23,720 t). `free` is the journal's `FreeSpace` when present, else computed.
- `CargoTransfer` (`Direction` `tocarrier` / `toship`) moves tonnes but **does not name the carrier**.

**Attribution** (`CarrierTracker._transfer_target`): a transfer goes to the carrier you are **docked at**.
`Docked` and `Location` (when `Docked`) carry the station's `MarketID` (equal to the carrier's `CarrierID`)
and `StationType`; `Undocked` and `LoadGame` clear it. If you are docked at a carrier that isn't yours, nothing
is counted (real journals show docking at other players' carriers). With no dock information, the transfer
goes to your only carrier if you have exactly one, and is skipped if you have two (it is never guessed).

**Backfill** (`backfill`, `backfill_tracker`). EDMC doesn't replay old events when it starts, and the baseline
only appears when Carrier Management is opened, so a baseline seen before WNTB started would be missed.
At startup a daemon thread reads the newest 40 journal files, parsing only lines that contain one of a few
event names, and replays them oldest first through a `CarrierTracker`. The result is handed to the Tk thread
through a `queue.Queue` and merged (`merge`: a record replaces the held one only if its `updated` timestamp is
newer; ISO timestamps compare as text). The tracker's final dock state is adopted when the live one has none.
Against a real journal folder this took 0.03 s.

**Commander matching** is case-insensitive (`key_for`): the journal wrote `BOCHEAUX` where EDMC says `Bocheaux`.

**Which carriers to show** is a per-commander Settings choice (`visible_types`): Auto (whatever has been
seen), None, Fleet, Squadron or Both. A chosen carrier with no data yet shows "Open Carrier Management once
to read its cargo space." Tracking continues regardless of the choice, so changing it never loses data.

**Staleness.** Reserved space and anything the carrier does itself (trade orders, market sales) only show
on the next `CarrierStats`. The page shows what the journal last said, not a live reading.

## 8. Routes (Spansh trade planner)

`trade_spansh_client.py`. Shape worked out from live calls (2026-10-09); undocumented by Spansh, so this module
is the one place to fix if it changes.

1. `POST https://spansh.co.uk/api/trade/route`, form-encoded: `system`, `station`, `max_hops`,
   `max_hop_distance`, `starting_capital`, `max_cargo`, `max_system_distance` (arrival distance in ls),
   `requires_large_pad`. Returns `{"job": "<id>", "status": "queued"}`.
2. `GET https://spansh.co.uk/api/results/<job>` repeatedly until `state == "completed"` (a small search took
   about 80 s). `result` is a list of hops: `source` and `destination` (`system`, `station`,
   `distance_to_arrival`, `market_updated_at`), `distance` (ly), `commodities` (`name`, `amount`, `profit` per
   tonne, `total_profit`), `total_profit`, `cumulative_profit`.

Inputs come from the game: start = docked station, else the last station docked at; cargo = `CargoCapacity`;
budget = `Credits`; hop distance = the Settings override, else the ship's unladen `MaxJumpRange`, else 30 ly.
Hops default to 3, arrival distance to 5,000 ls.

`parse_hops` skips a malformed hop rather than failing the whole route. The panel shows route profit, up to
four hops (station to station, system, ly, ls, best commodity and profit) and a "+N more" line, and remembers
the first hop's destination system for **Copy next system**.

## 9. Market: commodity search and ranking

**Names.** Spansh's market search is **case-sensitive and exact**: "Liquid oxygen" finds 10,000 stations,
"Liquid Oxygen" finds none, and the journal's plural "Void Opals" finds none where "Void Opal" works (all
checked 2026-10-09). Everything therefore goes through `trade_commodities.resolve`, which accepts typed text,
journal names, internal symbols (`lowtemperaturediamond`) and a plural/singular slip, and returns the exact
name. The table (`trade_commodities_data.py`) is generated from FDevIDs' `commodity.csv` (270 rows; Limpets
dropped). `SUGGESTIBLE` (173 names) leaves out the Salvage category, which is sellable but rarely searched; it
still resolves if typed or carried. An unresolved typed name is searched as typed, and a zero-result answer
says to check the spelling.

**Suggestions** (`suggest`): prefix matches first, then word-start matches, then contains; names you carry and
names the docked station buys lead each group. Empty text lists just those preferred names.

**Search target** (`_search_target`): the box's text if any, else your largest load. Tonnes = what you carry of
it, else a full hold (`CargoCapacity`, or 100 if unknown).

**Scopes.** Near me = `search_best_price_stations(system, name, "Sell", radius_ly)` with the Settings radius
(default 100 ly). Galaxy = the same call with `max_distance_ly=None`, which omits the distance filter (Spansh
accepts that). Results use only markets updated in the last 30 days (`_MARKET_DAYS_OLD_DEFAULT`), because an
unfiltered search returned fleet carrier markets years old.

**Ranking** (`trade_prices.rank_offers`): each station is valued for your load, `price x min(tonnes, demand)`,
and sorted by that (ties: nearer first). Stations wanting none of it or with no suitable pad are dropped.
`split_carriers` separates fleet and squadron carriers; they are listed in their own section ("they can
move") and excluded from the verdict. `verdict(near, galaxy)` says whether the galaxy-wide best beats the best
nearby, by how much and how many ly further; `carrier_note` says when a carrier would pay more than the best
station. Carriers can be hidden entirely in Settings.

## 10. Settings, config keys and files

Settings > WNTB > Trade (a top-level tab between Mining and BGS).

| Config key | Meaning | Default |
|---|---|---|
| `wntb_trade_lookups_enabled` | Allow the Spansh lookups | off |
| `wntb_trade_max_hops` | Route hops (1 to 10) | 3 |
| `wntb_trade_max_arrival_ls` | Furthest a station may be from its star | 5000 |
| `wntb_trade_large_pad` | Always require a large pad on routes | off |
| `wntb_trade_jump_range_override` | Jump range in ly ("" = use the ship's) | "" |
| `wntb_trade_near_radius_ly` | "Near me" radius | 100 |
| `wntb_trade_include_carriers` | Show carriers in price results | on |
| `wntb_trade_ship_pad_override` | small / medium / large ("" = from the ship) | "" |
| `wntb_trade_current_page` | Last page shown | Session |
| `wntb_trade_commanders` | Commanders seen, `\|`-separated, so Settings can list them | "" |
| `wntb_trade_carriers_<commander>` | auto / none / fleet / squadron / both | auto |

Files in the plugin folder (both are commander data and must survive updates; see `_OWN_DATA_FILES`):
`trade_ledger.json` and `trade_carrier.json`. `trade_carrier.json` was a flat `{commander: record}` map in
an earlier build; `load_all` reads that as a fleet carrier.

## 11. Limits and network behaviour

Follows TECHNICAL.md section 11 ("Keeping API traffic low").

- **Opt-in and button-driven.** No lookup runs without the Settings switch and a button press.
- **One job at a time.** `_Job` runs a single background lookup; starting another while one runs does nothing.
  Unlike other features there is no generation counter: a result is consumed by the one waiting job and
  `Cancel` sets its `threading.Event`. Results reach Tk only through `_poll_job` (an `after(500)` poller), never
  from the worker.
- **Route polling:** one request every 5 s, at most 240 s, so at most about 48 polls plus the submit. A failure
  isn't retried. Request timeout 20 s.
- **Price search:** one request per button press (Near me and Galaxy are two presses), 20 or 40 stations.
- **Identification:** every request sends `http_identity.user_agent("trade-routes")` (routes) or the mining
  finder's agent (prices).
- **Failure is quiet:** a failed or cancelled lookup shows a short message in the panel and logs the reason;
  it never interrupts journal handling.

## 12. Testing

`python -m unittest discover -s tests`. Trade's suites are `tests/test_trade.py` (ledger, market parsing,
Spansh client parsing) and `tests/test_trade_search.py` (commodity names, ship pads, offer ranking, carrier
space, the tracker's attribution rules, the per-commander choice and the journal backfill). They run without
EDMC or a display. The Settings tab is built by `tests/test_prefs_smoke.py` (nine top-level tabs now).

Not covered by automation: the panel and the suggestion popup (Tk). During development the panel was driven in
a real Tk window with EDMC and Spansh stubbed; that is not part of the suite.

## 13. Verified, assumed and known gaps

**Verified against live data:**

- Spansh trade-route submit and result shapes; the station search with and without a distance filter; exact
  and case-sensitive market names; pad counts in station results (all 2026-10-09).
- A real `CarrierStats`, `CargoTransfer`, `Docked` and `Location` from a commander's own journal, including
  `CarrierType`, `CarrierID` and `StationType`, and a backfill that reproduced the expected cargo figure.

**Assumed, not yet seen:**

- A **squadron carrier's** `CarrierStats` is assumed to match a fleet carrier's with
  `CarrierType: "SquadronCarrier"`. No real one was available.
- Ship pad sizes come from Coriolis data and a partly hand-written journal-name map; a ship that doesn't match
  shows "pad size unknown" and isn't filtered.

**Known gaps:**

- `CarrierStats` only on opening Carrier Management; reserved space and carrier-side sales are stale until then.
- The commodity list and pad classes are snapshots; a new commodity or ship needs a regeneration or edit.
- Spansh's route planner has no medium-pad option; routes use the unladen jump range.
- Spansh data is player-reported and can be stale; the page can't say a price is current, only that the market
  was updated in the last 30 days.
- No automated UI tests.

## 14. Platform notes

Nothing in Trade is OS-specific: it reads journal events, EDMC state and `Market.json` from the journal folder
(`config.get_str("journaldir")`, which on Linux is the Proton prefix's journal path), and makes HTTPS requests.
Background work is plain `threading`/`queue`. What a Windows-only development machine can't confirm, and
`LINUX_TESTING.md` section 6d lists: the suggestion popup (a borderless `Toplevel`) under each Linux window
manager, the page arrows' glyphs (◀ ▶) with Linux fonts, and the journal backfill finding the Proton journal
folder. Tested on Windows only so far.
