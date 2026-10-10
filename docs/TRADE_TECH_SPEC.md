# Trade mode specification

How Trade mode (the **TRD** button) works, what each module owns, which journal events and web services it
reads, and what has and hasn't been verified. For what it does for the user, see the
[README](guide/trade.md). For the plugin-wide rules it follows (feature contract, main-window sizing,
threading, persistence), see [TECHNICAL.md](TECHNICAL.md).

**Contents**

1. [What it is](#1-what-it-is)
2. [Modules](#2-modules)
3. [The three pages](#3-the-three-pages)
4. [Data sources](#4-data-sources)
5. [Session ledger](#5-session-ledger)
   - [Stock bought, not yet sold](#51-stock-bought-not-yet-sold)
   - [Trade History: saved sessions](#52-trade-history-saved-sessions)
   - [Journals from another machine: the scan record](#53-journals-from-another-machine-the-scan-record)
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
| Session | Yes | What you have bought and sold this session (until Reset), your ship and hold, and your carrier's cargo space |
| Routes | No (Spansh) | The most profitable trade route from where you are |
| Market | No (Spansh) | Where a commodity sells best, near you and anywhere |

Everything that contacts a web service is **off until enabled** in Settings and runs only when a button is
pressed. The Session page never touches the network.

## 2. Modules

All in `plugin/`. Pure modules have no Tk and no EDMC-only imports, so they are unit-tested directly.

| Module | Kind | Owns |
|---|---|---|
| `trade_blocks.py` | pure | The page model: `Heading`, `Pair`, `Columns`, `Item`, `Note`, and `to_text` |
| `trade_view.py` | UI | `BlockView`: draws a list of blocks with real layout |
| `trade_panel.py` | UI + controller | The feature-module contract entry point: panel chrome, page rendering, buttons, background jobs, Settings tab, journal dispatch |
| `trade_pages.py` | pure | Page names and order |
| `trade_ledger.py` | pure + file | The session ledger and `trade_ledger.json` |
| `trade_journal_scan.py` | pure + file | Which journal files have been read, finding new or grown ones, and applying them to the ledger, stock and carrier; `trade_journal_scan.json` |
| `trade_route_start.py` | pure + file | Each commander's route start and `trade_route_start.json` |
| `trade_stock.py` | pure + file | The stock book (bought, not yet sold) and `trade_stock.json` |
| `trade_history.py` | pure + file | Saved-session records, the `HistoryBook`, and `trade_history.json` |
| `trade_stats.py` | pure | Every number and table row shown from a saved session |
| `trade_history_window.py` | UI | The Trade History pop-out window (uikit) |
| `trade_market.py` | pure + file read | `Market.json` parsing and cargo valuation |
| `trade_ship.py` | pure | Ship to landing-pad size, and whether a ship fits a station's pads |
| `trade_carrier.py` | pure + file | Carrier cargo tracking, journal backfill, `trade_carrier.json` |
| `trade_commodities.py` | pure | Matching typed or journal commodity names to Spansh's names; type-ahead suggestions |
| `trade_commodities_data.py` | generated data | The commodity table (from FDevIDs) |
| `trade_prices.py` | pure | Valuing and ranking station offers for your load; carrier split; verdict lines |
| `trade_spansh_client.py` | network | The route planner client (submit, poll, parse) and the profit-per-hour estimate |
| `trade_roundtrip.py` | pure + network | The back-and-forth pair finder (one station search, then local pairing) |
| `trade_commodity_entry.py` | UI | The type-ahead entry widget |

Reused from elsewhere: `mining_spansh_client.search_best_price_stations` (the station price search, shared
with Mining's PRICE button), `mining_price_finder_dialog` (the **Price finder** button), `inventory_names`
(display-name fallback), `panelkit` (wrapping labels, tooltips, the page arrows, clipboard).

## 3. The three pages

**Session.** `trade_ledger.summary_blocks` (profit, running costs, tonnes, best sales; `summary_lines` is the
plain-text twin), then the ship hold block (ship and pad size, `used/capacity (free)`, what the docked
market would pay, up to four cargo lines), then the carrier block (`trade_carrier.cargo_blocks`, rows "Carrier cargo used", "Carrier cargo free" and "Carrier reserved for orders"; `cargo_lines` is the
plain-text twin). Buttons: **Reset** (starts the tally again; offers to save an unsaved session first),
**Save session** (greyed out until there is something to save) and **History**, with **Rebuild** on a second row (see 5.2). Save does not end or restart the
session: tracking is always on, the label never changes, and only **Reset** begins a new session.

**Routes.** Idle text shows the start station, ship, cargo size, jump range and budget the search will use.
Buttons: **Find routes** (becomes **Cancel** while searching), **Copy next system**, **Hops: N** (cycles 2 to 5, section 8.1)
and **Round trip** (section 8.2).

**Market.** A commodity box (type-ahead), a **Sell** / **Buy** toggle, then **Near me**, **Galaxy** and
**Price finder**. The box and toggle are shown only on this page and only when lookups are enabled. The toggle
is two buttons using the same on/off look as the mode buttons (`panelkit.apply_toggle_button_state`), not radio
buttons, which EDMC's theme doesn't colour reliably. Every button carries its full label (an earlier "Price…"
was an abbreviation of the finder's name). Selling with an empty box = the commodity you carry most of; buying
needs a typed commodity.

**How a page is drawn.** Each page builds a list of typed blocks (`trade_blocks.py`) rather than lines of text:
`Heading` (a section title; accent-coloured, with a rule above), `Pair` (label left, value right), `Columns` and `Item`
(a table row: a title, up to three right-aligned number cells, and a detail line beneath, with an optional warning in
the accent colour) and `Note` (a wrapped paragraph). The builders (`ledger.summary_blocks`, 
`trade_carrier.cargo_blocks`, and the panel's `_hold_blocks`, `_routes_blocks`, `_market_blocks`,
`_price_result_blocks`) stay free of widgets and can be tested; `to_text` renders any list as plain lines, and the
older `*_lines` functions are thin wrappers over it. `BlockView.show(blocks)` draws them and skips the redraw when
the blocks (frozen dataclasses, so equal by value) and the width haven't changed.

**Layout.** The controls come first, then the page: nav arrows, then (Market only) the Commodity box and the
Sell / Buy toggle, then the page's buttons, then the `BlockView`. A page is one grid of four columns: column 0 is
flexible (titles and labels) and columns 1 to 3 hold numbers.

**Sizing rule** (TECHNICAL.md section 5). Nothing can widen EDMC's main window. Every label has an explicit
`wraplength` derived from the width actually available, never from its text. The number columns are measured with the
real font (`font.measure`, plus the label's own padding) so this holds at any screen scaling. A label/value row puts its
value in the same columns as a table's numbers, so those columns are sized for the wider of the two (`value_need`) and
the title column gets what is left; getting this wrong made a stress page ask for 347 px of 330, which
`tests/trade_view_smoke.py` now checks. When the available width changes the page is redrawn. Names are only
bounded at 64 characters (`_NAME_MAX`), since the view wraps them. The suggestion list is a separate borderless
window of at most eight rows.

**Theming.** EDMC's theme only auto-colours a widget that had no colour when it was first registered, and leaves a
Frame's background alone (see `missions_ui.py`). So the accent colour and fonts are set at creation, the view takes its
parent's background, the rules are coloured after the theme pass (`panelkit.separator_colour`), and the widgets are
themed with `panelkit.apply_theme_deep`. The shared wrapping-label registry (`panelkit.wrap_label`) is deliberately not
used here: it never forgets a label, and these are rebuilt.

## 4. Data sources

Journal events and EDMC state read by `trade_panel.handle_event` (every handler only reads `entry` and
`state`):

| Source | Used for |
|---|---|
| `MarketBuy`, `MarketSell` | Ledger; the stock book; learning commodity display names (`Type_Localised`) |
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
  *repairs*; `BuyAmmo` and `RestockVehicle` (`Cost`) are *rearm*; a `Repair` whose `Items` include `"Wear"` is *Advanced Maintenance* (shown
  as its own line; confirmed with the commander against a real journal, 2026-10-09, where one `Repair` listing the
  cockpit, hull, cargo bay door and Wear cost 905 cr, so the whole charge counts and can't be split); `BuyDrones` (`TotalCost`) adds and `SellDrones`
  (`TotalSale`) subtracts for *limpets*, so that category can read as a gain if you sell back more than you
  bought this session. A zero or missing cost changes nothing. Not counted: insurance rebuys (`Resurrect`) and
  fines (`PayFines`). Costs only count from when WNTB saw them, like trades.
- **Net profit** = trade profit - running costs. With any cost recorded the headline reads "Net profit" with the
  trade profit and each cost beneath it; with none it reads "Profit", as before. Costs before the first trade
  still show ("No trades yet", the costs, "Net: ...").
- **Rate** (credits per hour) is the net figure over first-to-last trade time, so a refuel before the first sale
  doesn't stretch the clock. It appears after 3 minutes (`MIN_HOURS_FOR_RATE`).
- **Session identity.** A session belongs to a **commander** (matched ignoring case) and lasts **until Reset**; it is
  deliberately not tied to a game login or a journal file, because a job such as loading a fleet carrier for a bulk sale
  spans several play sessions, several journal files and several EDMC runs. `LedgerBook` holds one working session per
  commander, so switching commanders never discards anyone's tally; `ensure` returns the existing session (noting the
  journal file now being played) and only creates one if the commander has none; **Reset** replaces it. The Session page
  therefore shows the commander's whole tally, not just this login's. (The credits line under the mode buttons is a
  different feature and still counts per login.)
- **Persistence:** `trade_ledger.json`, atomic write (temp file then `os.replace`), at most once per 30 s plus
  on a new session and on shutdown. Loads tolerate a missing or wrong-shaped file.

### 5.1 Stock bought, not yet sold

`trade_stock.py`. The session ledger now spans logins too, but it ends at Reset, whereas money tied up in cargo
stays tied up until the cargo is sold, whenever that is. So the stock book follows the *cargo*, per commander, in
`trade_stock.json`, and is the **same mechanism for both ways of trading**:

- Station to station: `MarketBuy` adds tonnes and `TotalCost`; `MarketSell` removes tonnes at the commodity's
  average cost so far.
- Loading the carrier: every purchase adds to the stock; `CargoTransfer` to or from the carrier moves the cargo
  but not what was paid, so it is not a stock event. Stock comes out only when sold.

Because there is one list, nothing needs reconciling between "route" and "carrier" tracking, and no purchase
is counted twice. The book is an estimate (see Limits), so it is **not shown on the Session page**, which shows only
exact figures: the ship hold from `state["Cargo"]` and the carrier's cargo from `CarrierStats`. The book is snapshotted into
each saved session (`stock`) and shown on Trade History's Stock & carrier tab, labelled as a journal estimate.

Rules: average cost per commodity; a sale never takes stock below zero; a sale of cargo the book never saw is
ignored. The ledger's profit still uses the game's own `AvgPricePaid`, so the two can differ slightly when
cargo came from outside what the book saw; the ledger is the profit figure and the book is "what is tied up".

**Applying each event exactly once.** The book keeps `as_of` (the timestamp of the last event applied) and
the fingerprints (a short SHA-1 of the event) of events at exactly that second. An event older than `as_of`, or
already fingerprinted at `as_of`, is skipped; anything else is applied. Two sales in the same second (common:
a multi-commodity sale) are therefore both counted, and a replay never doubles one.

**Catching up.** EDMC doesn't replay events and trades made while it was closed would be missed, so `start()`
calls `trade_stock.backfill` **synchronously, before any live event can arrive** (about 0.14 s on a real
journal folder): it replays the newest 60 journal files (chosen by modified time, see below), applying only
events newer than each commander's `as_of`, or, for a commander with no book yet, the last 14 days. Doing it
synchronously removes any race with live events.

**Clearing.** `StockBook.clear` empties the items but keeps `as_of`, so a later replay can't bring the stock
back. There is no button for it now that the Session page no longer lists the stock.

**Limits.** Cargo that leaves some other way (the carrier selling on a trade order, cargo jettisoned or lost,
mission cargo) stays on the books. Stolen cargo bought nowhere has no book entry.

**Journal files are ordered by modified time, not name.** The game has used two naming styles
(`Journal.2026-10-09T053605.01.log` and `Journal.260228162446.01.log`) that do not sort chronologically
together, so "the newest N by name" can be wrong. `trade_carrier.journal_files` sorts by `os.path.getmtime` and
is used by both the carrier backfill and the stock backfill. The pre-filter on journal lines is a
whitespace-tolerant regex rather than an exact `"event":"X"` substring.

### 5.2 Trade History: saved sessions

Sessions are kept **only when the commander presses Save session** (nothing is saved automatically). The live ledger is
a working tally; History is the record the commander chose to keep.

**What the ledger remembers for it.** Beyond the totals, `trade_ledger` keeps:
- `log`: one entry per trade or cost: `{t, e: buy|sell|cost, c, n, u (unit price), tot, paid (average price paid, on
  a sale), sys, stn}`, plus `bm` on a black-market sale. The station and system come from the panel (the `system` and
  `station` EDMC passes to `journal_entry`). Bounded at `LOG_LIMIT` = 5,000; past that the oldest are dropped, which
  affects only the route and trade list, never the totals.
- `meta`: `started` (the `LoadGame` timestamp), `credits_start` (the `LoadGame` `Credits`), `jumps` and `jump_ly`
  (from `FSDJump` and its `JumpDist`).
- `routes` (the last 5 Spansh route searches: start, total, hops) and `searches` (the last 10 market searches: side,
  commodity, tonnes, scope and the best result).
An older ledger without any of this still loads (`meta()` fills in defaults).

**The record** (`trade_history.build_record`) is a deep-copied snapshot: id, commander, saved/started/ended times,
first and last trade, balance at start and at save, ship and pad size, jumps and light years, `rows`, `expenses`, `log`,
`routes`, `searches`, plus what was true at the moment of saving: the unsold `stock`, the `hold` and its `capacity`, and
the commander's `carriers`. Later changes to the live ledger never alter it.

**Catching a session up from the journals.** EDMC doesn't replay old events when it starts, and the game can be played with
EDMC closed, so a session would be missing whatever happened in between. The ledger remembers the last event it counted
(`meta["seen_ts"]` and fingerprints of the events at exactly that second, updated by every `apply_trade_event` and
`note_jump`). The first time the panel sees a commander in an EDMC run (their `StartUp` or `LoadGame`) it calls
`trade_ledger.catch_up(ledger, cmdr, journal_dir)`: every journal file modified since that point is replayed, oldest
first, through the **same functions the live events use** (`apply_trade_event`, `note_jump`, `note_start`), tracking the
system and docked station as EDMC reports them (`Location`, `FSDJump`, `CarrierJump`, `Docked`, `Undocked`). Only the
commander's own events count (`Commander` and `LoadGame` say who is current, since one file can hold several), and it only
**adds**: `already_counted` skips any event at or before the last counted one (and, within that second, any whose
fingerprint was recorded), so replaying twice, or EDMC then delivering live an event the replay already read, never counts
anything twice. Nothing is replaced or discarded, and it reads at most `CATCH_UP_FILES` (80) files, skipping any last
written before the session's last event. A ledger saved before the markers existed falls back on its last logged event.
**Rebuild** (`rebuild_since`, `parse_since`) is for a session that began on another computer: the ledger file is local to each machine and only the journals sync, so the commander gives a UTC start time and the session is rebuilt from every journal from then on (the same replay functions, events before the start ignored), replacing the working tally and keeping its Spansh routes and searches. `rebuild_from_journal` (a fresh session built from one file) remains for recovering a session whose tally was lost.
Catch-up changes only the working session: nothing reaches History until Save session.

**Identity.** `id` = a short SHA-1 of the commander and the moment the session began, so saving again *replaces* that
record (`HistoryBook.save` returns True when it did) instead of adding a duplicate, however many logins the session has
spanned, and **Reset** (a new start time) is a new session. Reset asks to save first when `_unsaved()`: the session has
content and its `(log length, net)` differs from the mark taken at the last save.

### 5.3 Journals from another machine: the scan record

The ledger, stock book, carrier records and history are files in each machine's plugin folder; only the journals are
copied between machines. `trade_journal_scan.py` makes new journals take effect on their own and records what it read.

- **Record.** `trade_journal_scan.json`: `files` (journal name -> `size` when read and when), `floor` (epoch seconds), and
  `last_pass` / `last_found` for the line at the foot of the Session page. A file counts as new or changed when its **size**
  differs from the record (a copy gets a new modified time without changing). Listed in `update.py`'s `_OWN_DATA_FILES`.
- **Passes.** `trade_panel` runs `_scan_tick` 4 s after the panel is built and then every 60 s. A worker thread
  (`WNTB-trade-scan`) calls `pending` (at most 80 files, **oldest first by each file's own first timestamp**, because copying
  scrambles modified times) and `read_events` (only the lines Trade can use, parsed). The Tk thread then calls `apply` for
  each file and `mark`, saves what changed and refreshes. Nothing but the Tk thread mutates the ledger, stock or carrier state.
- **The playing file is skipped** (`skip` = EDMC's current logfile); its events arrive live. It is read on a later pass.
- **First pass.** With nothing recorded, only the newest 80 files are taken and `floor` is set to the oldest of them's
  modified time; older files are never looked at later, so history is not crawled 80 files a minute.
- **`apply`** feeds one file's events to `trade_ledger.replay_entries` for every commander's session that has a starting
  point (`watermark` parses; otherwise it is left alone, like `catch_up`), `trade_stock.replay_entries`, and a
  `CarrierTracker` that shares the live `records` but has its own dock state. Each already refuses to count an event twice
  (watermark and fingerprints; stock `as_of`; carrier timestamps), so applying a file twice, or an older file after a newer
  one, changes nothing. `CarrierTracker.feed` skips a `CargoTransfer` stamped at or before the record's `updated`, and
  never lets an older `CarrierStats` replace a newer record.
- **Carrier estimate.** `apply_transfer` caps cargo at `capacity` (and at 0) and sets `estimate` when the cap bit; the panel
  prefixes the figures with `~` and adds a note. A `CarrierStats` replaces the record, which clears it.
- **Rebuild** (`trade_ledger.rebuild_since`, `parse_since`; the **Rebuild** button) is the manual counterpart for a session
  whose start predates the scan: it reads the journals from a typed UTC start time into a fresh ledger (events before it
  ignored, routes and searches kept) and replaces the working session.
- **Not covered.** Cargo that leaves the carrier on a trade order or sale has no event; only the next `CarrierStats` fixes
  it. Reset and Save session are per machine.

## 6. Hold, ship and landing pads

**Ship hold.** (labelled "Ship hold" on the panel, to keep it apart from the carrier's "Carrier cargo ..." lines) `used/capacity (free)` from EDMC's `state["Cargo"]` and `["CargoCapacity"]`. Display names come
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

**Transfers can overflow.** The journal never says when cargo leaves the carrier on a trade order or sale, so transfers
alone can add up to more than the bay holds. `apply_transfer` then caps `cargo` at `capacity` (or 0) and sets `estimate` on
the record; `cargo_blocks` shows `~` before the figures and a warning note. A `CarrierStats` replaces the record and clears
the flag. `CarrierTracker.feed` also ignores a `CargoTransfer` stamped at or before the record's `updated`, and an older
`CarrierStats` than the held record, so the same journal read twice (or an older one read late, see 5.3) changes nothing.

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

### 8.1 Route filters and the time estimate

`build_form` also sends `allow_planetary`, `allow_player_owned` and `permit` (0/1) and, when set, `max_price_age`.
The last is **the oldest update time allowed, as Unix seconds** (now minus the hours in Settings), not an age; this is
how Spansh's own page sends it (read from its app script, 2026-10-09, and accepted by a live request). Spansh's planner
has no minimum supply or demand and no loop or round-trip option (its only `loop` belongs to the tourist router); each hop's
`source_commodity.supply` and `destination_commodity.demand` are shown instead (`Cargo.supply`, `Cargo.demand`).

`estimate_hop_seconds` / `estimate_profit_per_hour` give the "~N cr" shown on routes: 45 s per jump (hop distance over
the jump range, rounded up), 30 s plus 0.03 s per ls of supercruise to the destination, and 120 s at the station. These are
fixed allowances for comparing routes, not measurements.

The **Hops** button cycles 2, 3, 4, 5 and writes the Settings value. `_finish_routes` marks a result a repeatable loop when
the last hop ends at the first hop's start and every hop has cargo.

### 8.2 Round trip (`trade_roundtrip.py`)

Spansh's planner can't be asked for a pair that comes back, so the pair is found locally.

1. `fetch_stations` posts to `https://spansh.co.uk/api/stations/search` with `distance` (radius = twice the jump range,
   20 to 100 ly), `market_updated_at` (`now-<hours>h`, else `now-30d`), sorted nearest first, 100 per page, at most 3
   pages. With no `market` filter each result still carries the station's **entire** `market` (`commodity`,
   `buy_price` = what it charges you, `sell_price` = what it pays you, `supply`, `demand`), checked live on 2026-10-09
   (300 stations in about 22 s). `Station` also keeps position (`system_x/y/z`), `distance_to_arrival`, `is_planetary`,
   `type` (carriers are `Drake-Class Carrier`) and the pad counts.
2. `best_load(source, dest, cargo, capital, min_supply, min_demand)`: commodities that sell for more at `dest` than they
   cost at `source`, best profit per tonne first, each limited by supply, demand and money left, until the hold is full.
3. `find_round_trips` takes the start station (`find_start`, matched ignoring case; if Spansh has no recent market for
   it the panel says so), and for every other station that passes the filters (ground, carriers, pad size, arrival
   distance) builds the outbound and return loads. **If either is missing the pair is dropped**: that is the no-empty-leg rule.
   The return trip may spend the outbound profit. Pairs are ranked by estimated profit per hour for the whole loop.

The panel shows the top three (`RESULTS_KEPT`) with what to carry each way, remembers the best pair's destination for
**Copy next system** and records it in the session's lookups (two hops). Settings: `wntb_trade_min_supply` and
`wntb_trade_min_demand` (default 200 t). Tested by `tests/test_trade_roundtrip.py`.

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

**Side** (`wntb_trade_market_side`, default sell): chosen with the toggle and remembered. Changing it clears
the results, since they belong to one side, and results are keyed by `(commodity, tonnes, pad, side)`.

**Search target** (`_search_target`). Selling: the box's text if any, else your largest load; tonnes = what you
carry of it, else a full hold (`CargoCapacity`, or 100 if unknown). Buying: only the typed commodity; tonnes =
your *free hold space* (`CargoCapacity` less what is aboard), or a full hold's worth if the hold is already full.

**Scopes.** Near me = `search_best_price_stations(system, name, "Sell", radius_ly)` with the Settings radius
(default 100 ly). Galaxy = the same call with `max_distance_ly=None`, which omits the distance filter (Spansh
accepts that). Results use only markets updated in the last 30 days (`_MARKET_DAYS_OLD_DEFAULT`), because an
unfiltered search returned fleet carrier markets years old.

**Ranking** (`trade_prices.rank_offers`, `side`). Selling: each station is valued for your load,
`price x min(tonnes, demand)`, and sorted by that (ties: nearer first). Buying: the amount that can change hands is
`min(tonnes, supply)`; stations that can supply all of it come first, cheapest first, then partial ones, cheapest
first (each marked "only N t in stock"). Either way, stations with nothing to buy or sell, or with no suitable pad,
are dropped. Spansh is asked with transaction `"Sell"` or `"Buy"` (`search_best_price_stations`), whose `price` and
`quantity` mean sell price and demand, or buy price and supply.
`split_carriers` separates fleet and squadron carriers; they are listed in their own section, one for every
three stations ("they can move") and excluded from the verdict. `verdict(near, galaxy, side)` says whether the galaxy-wide best beats the
best nearby: selling, by how many credits and what percentage more; buying, by how many cr/t cheaper, the saving
on the tonnes involved, and how many ly further. `carrier_note` says when a carrier would pay more (selling) or
charge less (buying) than the best station. Carriers can be hidden entirely in Settings, and so can ground facilities
(`wntb_trade_include_ground`): the station search then asks Spansh only for `trade_prices.ORBITAL_TYPES`, and
`rank_offers(include_ground=False)` also drops any planetary result. Turning off both leaves orbital stations only.

**Where each place is.** Every offer carries Spansh's `is_planetary`, its station type and its distance from the
arrival star, shown as `orbital Coriolis Starport, 1,200 ls` or `ground Planetary Outpost, 80 ls`
(`trade_prices.describe_place`); a fleet carrier is just `carrier`.

## 10. Settings, config keys and files

Settings > WNTB > Trade (a top-level tab between Mining and BGS).

| Config key | Meaning | Default |
|---|---|---|
| `wntb_trade_lookups_enabled` | Allow the Spansh lookups | off |
| `wntb_trade_max_hops` | Route hops (1 to 10) | 3 |
| `wntb_trade_max_arrival_ls` | Furthest a station may be from its star | 5000 |
| `wntb_trade_large_pad` | Always require a large pad on routes | off |
| `wntb_trade_jump_range_override` | Jump range in ly ("" = use the ship's) | "" |
| `wntb_trade_route_price_age_h` | Routes: ignore markets not updated within this many hours (0 = any) | 72 |
| `wntb_trade_route_permit` | Routes may use systems that need a permit | off |
| `wntb_trade_min_supply` | Round trip: least tonnes the buying station must have | 200 |
| `wntb_trade_min_demand` | Round trip: least tonnes the selling station must want | 200 |
| `wntb_trade_near_radius_ly` | "Near me" radius | 100 |
| `wntb_trade_include_carriers` | Fleet carriers in price results and routes (`allow_player_owned`) | on |
| `wntb_trade_include_ground` | Ground facilities in price results and routes (`allow_planetary`) | on |
| `wntb_trade_ship_pad_override` | small / medium / large ("" = from the ship) | "" |
| `wntb_trade_current_page` | Last page shown | Session |
| `wntb_trade_market_side` | Market search side: sell or buy | sell |
| `wntb_trade_commanders` | Commanders seen, `\|`-separated, so Settings can list them | "" |
| `wntb_trade_carriers_<commander>` | auto / none / fleet / squadron / both | auto |
| `wntb_trade_history_window_geometry` | Size and position of the Trade History window | "" |

Files in the plugin folder (all are commander data and must survive updates; see `_OWN_DATA_FILES`, which
`tests/test_own_data_files.py` enforces): `trade_ledger.json`, `trade_carrier.json`, `trade_stock.json`,
`trade_history.json`, `trade_journal_scan.json` and `trade_route_start.json` (`{commander: {system, station, at}}`, where `at` is the dock's time: a dock replaces a start only if it is not older, so scanned files in any order give the right answer). `trade_ledger.json` is `{"ledgers": {commander: ledger}}` (one session per commander; the
single-ledger file of an earlier build is read as the current commander's). `trade_carrier.json` was a flat
`{commander: record}` map in an earlier build; `load_all` reads that as a fleet carrier.

## 11. Limits and network behaviour

Follows TECHNICAL.md section 11 ("Keeping API traffic low").

- **Opt-in and button-driven.** No lookup runs without the Settings switch and a button press.
- **One job at a time.** `_Job` runs a single background lookup; starting another while one runs does nothing.
  Unlike other features there is no generation counter: a result is consumed by the one waiting job and
  `Cancel` sets its `threading.Event`. Results reach Tk only through `_poll_job` (an `after(500)` poller), never
  from the worker.
- **Route polling:** one request every 5 s, at most 240 s, so at most about 48 polls plus the submit. A failure
  isn't retried. Request timeout 20 s.
- **Round trip:** one to three station-search requests (100 stations each, nearest first, stops at the first short
  page), about 20 s, request timeout 30 s, identified as `trade-roundtrip`.
- **Price search:** a press of Near me or Galaxy makes **two requests**, one for stations and one for fleet
  carriers (one if carriers are hidden in Settings), and the two buttons are separate presses. Stations: 20, or 40
  when filtering by pad. Carriers: a third as many (at least 5). Asking separately matters: carriers are priced very
  differently (a galaxy-wide *buy* search sorted by price returned 40 carriers at about 325 cr/t and not one real
  station at about 5,000 cr/t), so in one list they filled the page and the panel reported "no station sells it".
  The `type` filter (`trade_prices.STATION_TYPES`, `CARRIER_TYPES`) was checked live on 2026-10-09; a station
  type missing from `STATION_TYPES` would not be returned. The weighting is 75% stations to 25% carriers, both in
  what is fetched and what is shown (three stations to one carrier per search).
- **Identification:** every request sends `http_identity.user_agent("trade-routes")` (routes) or the mining
  finder's agent (prices).
- **Failure is quiet:** a failed or cancelled lookup shows a short message in the panel and logs the reason;
  it never interrupts journal handling.

## 12. Testing

`python -m unittest discover -s tests`. Trade's suites are `tests/test_trade.py` (ledger, market parsing,
Spansh client parsing) and `tests/test_trade_search.py` (commodity names, ship pads, offer ranking, carrier
space, the tracker's attribution rules, the per-commander choice and the journal backfill) and
`tests/test_trade_stock.py` (average-cost stock, apply-once rules, the backfill, and file ordering) and
`tests/test_trade_roundtrip.py` (the hold fill, supply and demand limits, the no-empty-leg rule, ranking by profit per hour, the
carrier, ground, pad and distance filters) and
`tests/test_trade_blocks.py` (the page model's plain-text form, and the ground-facilities switch) and
`tests/test_trade_history.py` (the ledger's log, jumps and start, rebuilding a session from a journal file or from a start
time, skipping the events it already counted, the record and book, and every number and row in `trade_stats`) and
`tests/test_trade_journal_scan.py` (finding new, grown and copied journal files, oldest-first ordering, the first-pass floor,
and applying a file twice or an older one late). The History window is opened by `tests/trade_history_window_smoke.py` (see below). The drawn page is
checked by `tests/trade_view_smoke.py` (run by `test_trade_view_smoke.py` in a subprocess, skipped without a display):
no label asks for more than the width available, unchanged blocks aren't redrawn, and a table's number columns end
at the same place. They run without
EDMC or a display. The Settings tab is built by `tests/test_prefs_smoke.py` (nine top-level tabs now).

The History window is also drawn in a real Tk window by `tests/trade_history_window_smoke.py` (run by
`test_trade_history_window_smoke.py`, skipped without a display): every tab is visited at the minimum window size and
each table must fit, and the picker, commander filter, Copy, Delete (with and without confirmation), the empty state
and refresh-on-save are exercised.

Not covered by automation: the panel's controls and the suggestion popup (Tk). During development the panel was driven in
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
- Stock: cargo sold by the carrier's own orders or lost stays listed until cleared; a first run only looks back
  14 days, so older purchases still unsold aren't known.
- UI tests are smoke tests only (`tests/trade_view_smoke.py`, `tests/trade_history_window_smoke.py`, run in
  subprocesses and skipped without a display); they check layout and clipping, not looks.

## 14. Platform notes

Nothing in Trade is OS-specific: it reads journal events, EDMC state and `Market.json` from the journal folder
(`config.get_str("journaldir")`, which on Linux is the Proton prefix's journal path), and makes HTTPS requests.
Background work is plain `threading`/`queue`. What a Windows-only development machine couldn't confirm, and
`LINUX_TESTING.md` section 6d lists: the suggestion popup (a borderless `Toplevel`) under each Linux window
manager, the page arrows' glyphs (◀ ▶) with Linux fonts, and the journal backfill finding the Proton journal
folder. Tested on Windows while building and on Linux on 2026-10-09 (the section 6d checklist, no new issues).
