# Troubleshooting

Find your symptom below. Most problems are a missing setting or a missing permission.

**Jump to:** [Nothing happens (settings that start off)](#nothing-happens-settings-that-start-off) · [A number looks wrong](#a-number-looks-wrong-or-missing) · [General](#general) · [Overlay](#overlay) · [Linux](#linux) · [Missions](#missions) · [Trade](#trade) · [Still stuck?](#still-stuck)

## Nothing happens (settings that start off)

Before anything else, check whether the feature is simply **switched off**. WNTB starts conservative: every on-screen display, every
online lookup and every write to another site is **off until you tick it** in Settings (**File → Settings → WNTB**). A feature that is
off does not show an error. It just does nothing, which looks exactly like a bug.

| If this does nothing... | ...tick this | Where |
|---|---|---|
| Any card on your game screen | The feature's own **Enable** box, below, and the overlay itself must be running ([setup](../OVERLAY_SETUP.md)) | Settings → Overlays |
| Landing Assist diagram | **Enable Landing**, then **Show on Overlay** (the diagram on the game screen is a separate tick, also off) | Settings → Overlays → Landing |
| Interdiction warning | **Enable Interdiction Warning** | Settings → Overlays → Interdiction Warning |
| The missions list on the game screen | **Enable** under Missions; pinned missions need the overlay too | Settings → Overlays → Missions |
| Carrier jump and fuel alerts | **Enable Flight Alerts** | Settings → Overlays → Flight Alerts |
| Route and ship status card | **Enable the Route overlay** | Settings → Overlays → Route |
| Discovery alerts | **Enable Discovery Alerts**, or the **D.A.** button | Settings → Overlays → Discovery |
| Notable find banners | **Enable Notable Bodies alerts**, then pick the rules you want | Settings → Overlays → Notable Bodies |
| The arrow to a mark or hotspot on a planet | **Enable Surface Compass** | Settings → Overlays → Surface Compass |
| Inventory pickups and bars | The inventory bars you want, one tick per bar | Settings → Overlays → Inventory |
| Mining stats on the game screen | **Enable HUD Overlay** | Settings → Mining |
| "Screenshot saved" message on the game screen | The overlay message option for screenshots | Settings → Field Ops → Screenshots |
| The Colonization shopping list appears by itself at markets | **Also show the shopping list automatically**. Otherwise only the **OVERLAY** button on the COL page shows it | Settings → Overlays → Colonization |
| Auto-Honk | **Enable Auto-Honk** or the **A.H.** button | Settings → Exploration → Auto-Honk |
| **Find sources** (Missions) and **Best picks** (Trade) | **Enable Spansh trade lookups**; Find sources asks to turn it on when you press it | Settings → WNTB → Trade |
| Routes and Market on the Trade page | **Enable Spansh trade lookups** ([details](#the-lookup-buttons-are-grayed-out-or-there-is-no-commodity-box)) | Settings → WNTB → Trade |
| The **H.S.**, **PRICE** or **RES** buttons in Mining | **Enable Spansh Nearby Hotspot Finder**, **Enable Spansh Best Price Finder**, **Enable EDSM Ring Reserve Lookup** (each separately) | Settings → Mining |
| ELW rarity or EDSM upload status in Exploration | The two options under Exploration Value | Settings → Exploration → Exploration Value |
| Fleet carriers missing from "where to buy" results | **Include fleet carriers** in the Colonization sites window | Colonization sites window |
| Raven Colonial not updating | The master switch and the two options under it ([steps](#raven-colonial-doesnt-update-as-i-deliver)) | Settings → Colonization → Raven Colonial |
| Something else is wrong | **Report an issue**, then **Copy diagnostics** to paste the log lines into it ([how](reporting-problems.md)) | Settings → WNTB → General → Help |
| WNTB never updates itself | **Automatically download and install updates** | Settings → WNTB → General → Updates |

Notes:
- **Test buttons work even when a feature is off.** A passing **Test** shows the overlay is reachable; it does not mean the live feature is on.
- **Settings are per computer.** A tick on one machine does not carry to another, so check each one you play on.
- **Press OK** in Settings to keep a change.
- Anything that contacts the internet is listed, with what it sends, on [what goes on the internet](internet-and-privacy.md).

## General

### The WNTB panel doesn't appear

Check that the folder is named exactly `WNTB` and sits directly inside EDMC's plugins folder, with files such as
`load.py` right inside it (not another folder inside it). So you want `plugins/WNTB/load.py`, not
`plugins/WNTB/WNTB/load.py`. Then restart EDMC.

### A name in the panel ends in "..."

The panel wraps a long name onto the next line rather than cutting it, and only shortens one that is very long (past about 64
characters for a station, system or site name, 40 for a commodity or material). A wrapped line uses the width EDMC's window
already has; widening the window gives it more room.

### A button or section is missing

Open **File → Settings → WNTB** and check the feature hasn't been switched off. The BGS and Codex Completionist
sections can each be hidden there. Also make sure you're in the right mode, and on the right page (some buttons
only appear on one page).

### Numbers look wrong or out of date

EDMC only passes WNTB what happens while it is running. For play with EDMC closed, WNTB reads the recent journal files
when EDMC starts and catches up by itself; the table in
[If EDMC wasn't running](getting-started.md#if-edmc-wasnt-running) shows what each feature catches up on and how far
back. Things to try if a figure is still off:

- Powerplay has a **RESCAN** button.
- Codex Completionist has **BKF** (backfill from journal history) for the commander you are playing, for finds older than the automatic catch-up.
- Trade's **Rebuild** button recounts a session from a start time you give; see
  [How a trading session works](trade.md#how-a-trading-session-works).
- Missions shows what the journals say is active. If a mission expired without the game writing anything, log in
  again and the game's own list replaces it.
- **Starting EDMC before the game.** WNTB reads the last commander from your newest journal a few seconds after
  start-up, so your saved data and panels appear without logging in. If you then log in as someone else, everything
  switches to them.
- A feature can only look back a limited way (Missions two weeks, Colonization, including its FC column, 14 to 30 days, Boxel Survey 14 days).
  Older play with EDMC closed isn't found.

### My hotspots, survey finds or Codex tally are missing for a commander

They belong to one commander each, so a commander you have not used before starts empty (see
[Commanders and your data](getting-started.md#commanders-and-your-data)). If you **just updated** from a version where
they were shared:

- **Mining hotspots, driven ground and Boxel Survey finds** went to whichever commander logged in first. Log in as the
  one who owns them. To give hotspots to another commander, use **I/E** in Mining: export as the first commander, then
  import as the second.
- **The Codex tally** is rebuilt from each commander's own journals the first time they log in; the panel says so
  while it reads (the section title shows "rebuilding..." even when folded) and the summary fills in when it finishes (a
  minute or two for years of journals). If it was
  interrupted, log in again or press **BKF**.
- The Powerplay Sessions window's **History** tab now shows only the commander you are playing. The other commanders' sessions are still saved.

### EDMC shows "Frontier CAPI query failure" for a commander with no fleet carrier

This line comes from **EDMC itself**, not from WNTB. WNTB never asks Frontier for anything; it only receives carrier data
when EDMC fetches it.

EDMC's **Enable Fleetcarrier CAPI Queries** option (in EDMC's own Settings) is one switch for every commander. When it is on,
EDMC asks Frontier for the fleet carrier at game start-up and on other events that any commander produces (a cargo
transfer, buying a commodity), without first checking that the commander owns a carrier. Frontier answers with nothing for a
commander who has none, and EDMC reports that as a failure. It does no harm, and WNTB works normally; the line is noise.

If it bothers you:

- Turn that option off while you play a commander without a carrier, and back on for the one who has one. The carrier's real
  cargo and the Carrier Locker in Inventory only come from this query, so they need it on (see
  [Covered or the Carrier row looks wrong](#covered-or-the-carrier-row-looks-wrong)).
- Or leave it on: the commander with a carrier needs it, and the failures for the others are harmless.

### The Ship planner says a module is "not counted"

The planner only counts what WNTB's blueprint table covers, and it says why in the **Counted?** column and the detail under the table (select the row):
- *Pre-engineered*: the module comes engineered from Frontier, so there is nothing to craft.
- *No module type for this item*: the item is not one the table has blueprints for (a cargo rack, a passenger cabin, a module reinforcement).
- *No blueprint ... for a ...*: the journal's blueprint is not in the table for that module type. The table is EDEngineer's (March 2024) with a few later additions,
  so a blueprint added to the game since may be missing. Check the in-game recipe.
- *Only some grades*: the table has fewer grades of that blueprint than the level asks for.
- The experimental effect is not in the table: the grades are counted and the effect is not.

**Add plan to wishlist** can refuse with a message: no commander yet (log in first), more than 100 blueprints on the list, or more than 99 crafts of one. Nothing
is added when it refuses; remove some entries and try again. If **Paste from clipboard** reports no text, paste into the box by hand and press **Read loadout**.
See [Ship planner](field-ops.md#engineering-blueprints-and-a-wishlist).

## Overlay

### On-screen alerts don't show up

They need EDMCModernOverlay running, and WNTB's **Overlay Connection** settings must match it. Use the
**Test** buttons in each feature's Settings tab to check.

The full checklist is in [Setting up the overlay](../OVERLAY_SETUP.md#if-nothing-shows-up).

### Notable Bodies never shows anything

It is switched off until you tick **Enable** under **Settings → Overlays → Notable Bodies**. Only some
rules are on to start with, so tick the ones you want. A banner needs the overlay to be running.

### Overlay displays are in the wrong place, cut off, or stop short of the right edge

(A display that is not there at all, though the overlay works, is covered under
[Linux](#one-display-never-shows-though-test-and-the-overlay-window-both-work).)

Open **Settings → Overlays → Overlay Placement**. Press **Show placement preview** to see a box for every display at its real
size, then **Detect screen again** if the screen size or scaling line looks wrong. **Reset all to defaults** puts every spot back.
Displays on the right use an offset to reach the screen edge; if that misbehaves, untick **Carry displays on the right to the
screen edge**. The details are in [Setting up the overlay](../OVERLAY_SETUP.md).

### Overlay text wraps, or a card is too small or too big

Open **Settings → Overlays → Appearance** and press **Show sample**. Cards are sized from an estimate of the text at the
chosen size and given 10% extra width, so a card may still be tight on a small screen. Try a smaller **Text size** on the same tab.

## Missions

### A mission shows no progress

- **Source and return (Collect) missions** get nothing from the game until you hand cargo in, so WNTB shows what is in your hold against what the mission asks for (`36/60 held`). It counts every tonne of that commodity aboard, whether or not you bought it for the mission, and it does not count cargo in a fleet carrier or another ship. With an empty hold it reads `0/60 held`.
- **Massacre and settlement-raid kills** marked `~` are estimates, and wing and on-foot kills are often missing from the journal until the mission completes.
- A mission accepted more than two weeks ago, before WNTB could see it, is not on the list at all. See [Missions](missions.md#what-the-game-does-and-doesnt-tell-us-and-how-to-work-around-it).

### Find sources does nothing, or says it does not know where I am

It needs **Enable Spansh trade lookups** (Settings → WNTB → Trade); the window asks to turn it on. "From where I am" uses your current system from EDMC, then from your newest journal, so you do not need to jump first; if neither knows, it falls back to the turn-in system and says so. If none of your missions needs cargo to be found, the window says that too.

## Colonization

### The COL page says "No active construction site"

Dock at the construction depot, or open its market, **once**. The game writes the site's needs only then.

### "Covered" or the Carrier row looks wrong

The journal only records cargo you transfer to the carrier, so WNTB's carrier figure is what it saw you move. Two ways to put it right:

- **For the real hold:** sign EDMC in to Frontier and open **Carrier Management** in the game. WNTB then reads the carrier's actual
  cargo (at most every 15 minutes, and Frontier's copy can lag the game by a little).
- **For a transfer that did not register:** press **Rescan Carrier** in the Colonization Sites window. It rebuilds the tally from the
  last 30 days of journals and drops any figure taken from Frontier, so it is a quick fix, not a replacement for the real hold. See
  [Rescan Carrier](colonization.md#rescan-carrier-when-a-load-did-not-register).

### Raven Colonial doesn't update as I deliver

WNTB sends nothing to Raven Colonial until you turn sharing on. It is **off by default**, and it is separate from the Raven features
that only read (Planned Builds, Raven Progress and the quick links work without it). If your deliveries never reach Raven, this is
almost always why.

In **Settings → Colonization → Raven Colonial**:

1. Tick **Allow WNTB to write to Raven Colonial (master switch)**. The options under it stay grayed out until you do.
2. Tick **Report my construction progress and deliveries to Raven Colonial**.
3. Tick **Also report cargo I move to and from my fleet carrier** if you want that too.
4. Paste your key from [ravencolonial.com/user](https://ravencolonial.com/user) and press **Test key**. Raven answers with your name
   for you when the key is accepted. With no key, nothing is sent.
5. Press **OK** in Settings.

Only deliveries made while sharing is on are sent. WNTB does not backfill earlier ones. The update reaches Raven when the depot's
figures change and when you deliver, so dock at the site or open its market to send the current totals. If another tool such as
SrvSurvey also reports your deliveries to Raven, turn one of them off, or Raven counts each delivery twice. The setting is saved per
computer, so check it on each machine you play on. If it is on and Raven still does not update, the EDMC log shows the failed
request; please [report it](../../README.md#getting-help) with those lines.

### Raven Progress says Raven has no project for my site

Raven Colonial only records a site's market id once the build is finished, so WNTB finds a build in progress by its **name**. If you
renamed the site in the game, dock at it once so WNTB takes the new name; if you renamed it on Raven, give both the same station name.
A site that is only *planned* on Raven has no project yet. See the [guide](colonization.md#sharing-your-progress-with-raven-colonial).

### Test key says Raven did not accept the key

Check that you pasted the key from your account page ([ravencolonial.com/user](https://ravencolonial.com/user)) with no spaces, and
that the commander you are playing is the one the key belongs to (keys are saved per commander). WNTB sends the key and your commander
name together, as Raven's own website does. If a key you know is right is still refused, please [report it](../../README.md#getting-help).

### My history is smaller than what I delivered

The game keeps no delivery history, but your journal files do. The first time WNTB sees a commander it reads all of that
commander's journals once and rebuilds the history from them, so it goes back as far as your journals do (it logs
"Colonization history rebuilt" when it is done). Deliveries from journal files you have deleted are missing. After that
it counts as you play and catches up from 14 to 30 days of journals at start-up. The page says which date it counts since.

## Linux

See [WNTB on Linux](linux.md) for the setup these refer to.

### On-screen alerts don't show, and Check connection says OK (Flatpak EDMC)

**Check connection** passes even when the overlay window never started. Grant the "run host programs" permission
(Step 3, command 4 in [WNTB on Linux](linux.md#step-3-if-edmc-is-a-flatpak-grant-it-four-permissions)), then
restart EDMC. You can confirm the overlay window is running with:

```bash
ps -eo args | grep overlay_client
```

### One display never shows, though Test and the overlay window both work

Its saved position may be off the edge of the screen. This can happen with a position carried over from an older version, such
as a Colonization shopping list saved at x = 1280 on a screen that is 1280 wide. WNTB sends the display and nothing is wrong
with the connection, but it is drawn where you cannot see it. Versions after 1.9.0 notice a saved exact position that is off the
overlay's canvas and use the display's default placement instead (the EDMC log says so), so this fix is only needed on 1.9.0.

To confirm, look in the overlay's log (for a Flatpak EDMC,
`~/.var/app/io.edcd.EDMarketConnector/data/EDMarketConnector/logs/EDMCModernOverlay/overlay_client.log`) for lines such as:

```
Payload 'wntb_colonisation_s14_1' from plugin 'WNTB' rendered completely outside the overlay window (bounds=(2536.0, 420.0)-(2569.0, 446.0), window=2048x1280)
```

To fix it, open **Settings → Overlays → Overlay Placement**, pick the display, and reset it to its default or choose an anchor
(for example left, middle). **Reset all to defaults** puts every spot back. Then restart EDMC.

**Workaround:** on the Overlay Placement tab, choose a named spot such as Top left, which fits any screen, and save. If you type an **Exact position**, keep x between 0 and 1240 and y between 0 and 940 (the overlay's
canvas is 1280 x 960),. Placements are saved per computer in
EDMC's own settings, so a fix on one machine does not carry to another; repeat it there, or update WNTB so it does this itself.

### Auto-Honk or the screenshot timer say `xdotool` is not installed

Install `xdotool` on your system (Step 1). If EDMC is a Flatpak, also grant the "run host programs" permission
(Step 3, command 4) and restart EDMC. If it still fails, the EDMC log shows a "Host lookup of xdotool failed" line
with the reason.

### Auto-Honk says no usable keybind found

Either your fire button has no keyboard key (Step 4), or WNTB can't read the bindings folder.

- Bind a keyboard key to the second slot of Secondary Fire (Step 4).
- For a Flatpak EDMC, grant Step 3, command 2.
- Make sure **Elite Wine/Proton prefix** in **Settings → Exploration → Auto-Honk** is empty unless you really use a
  custom setup. A wrong value there hides your keybindings.

### Auto-Honk presses the key but the scan stops after about a second

Fixed in 1.3.1 (earlier builds released the key too early under XWayland). Update WNTB.

### Features that read the journal find nothing

EDMC's **Journal directory** isn't set, or points at the wrong place. See
[Step 2](linux.md#step-2-tell-edmc-where-elites-journals-are).

## Trade

### The lookup buttons are grayed out, or there is no Commodity box

The Spansh lookups are off until you tick **Enable Spansh trade lookups** under **Settings → WNTB → Trade**. The
Commodity box only appears on the Market page, and only once lookups are on.

### I can't tell whether it's searching for a place to buy or to sell

The **Sell** and **Buy** buttons under the Commodity box choose the side. The lit one is active, and the results
heading says "Selling" or "Buying". Changing the side clears the old results.

### The Market search finds nothing for a commodity

- Pick the name from the suggestion list. Spansh only knows commodities by their exact in-game name (for example
  "Void Opal", not "Void Opals"), and an unknown name finds no markets.
- Check that your ship's pad size is right under **Settings → WNTB → Trade**. Stations without a pad your ship fits
  are left out, and the result says how many were.

### The Session page seems to have lost some trades

A session lasts until you press **Reset**, across logins and EDMC restarts, and catches up from the journals when
EDMC next sees you. So check:

- You didn't press **Reset** (it asks to save first if there was anything unsaved).
- On Linux, that EDMC's **Journal directory** is set. Without it the catch-up can't read the journals.
- Trades made before WNTB first ran aren't counted.

### Save session is grayed out, or the History window is empty

**Save session** needs at least one trade or running cost in the session. The History window only lists sessions you
saved, so press **Save session** first.

### Trade History says I had cargo unsold that I'd already sold

The "Bought, not yet sold" estimate on the Stock & carrier tab only comes down when WNTB sees you sell. Cargo your
carrier sold on a trade order, or that you lost or jettisoned, stays in it. The Session page does not show this
estimate; it shows only your ship hold and the carrier's cargo figures.

### My carrier doesn't show, or its cargo looks wrong

- Check your carrier choice for that commander under **Settings → WNTB → Trade** (Auto, Fleet, Squadron or Both,
  not None).
- Open **Carrier Management** in the game once so the game reports its space.
- Read [what the game does and doesn't tell us](trade.md#what-the-game-does-and-doesnt-tell-us-and-how-to-work-around-it):
  it lists every gap in the game's data and the workaround for each.
- If the numbers still look wrong, open an issue with the `CarrierStats` line from your journal (it is in the latest
  `Journal.*.log`).

## A number looks wrong or missing

Often it is a limit of what the game records, not a fault: WNTB, like every third-party tool, only knows what the game writes to its
journal files (see [How WNTB knows what it knows](README.md#how-wntb-knows-what-it-knows)). Each mode guide ends with "What the game does and doesn't
tell us, and how to work around it": [Powerplay](powerplay.md#what-the-game-does-and-doesnt-tell-us-and-how-to-work-around-it),
[Exploration](exploration.md#what-the-game-does-and-doesnt-tell-us-and-how-to-work-around-it),
[Mining](mining.md#what-the-game-does-and-doesnt-tell-us-and-how-to-work-around-it),
[Trade](trade.md#what-the-game-does-and-doesnt-tell-us-and-how-to-work-around-it),
[Missions](missions.md#what-the-game-does-and-doesnt-tell-us-and-how-to-work-around-it),
[Field Ops](field-ops.md#what-the-game-does-and-doesnt-tell-us-and-how-to-work-around-it),
[Colonization](colonization.md#what-the-game-does-and-doesnt-tell-us-and-how-to-work-around-it),
[BGS](bgs.md#what-the-game-does-and-doesnt-tell-us-and-how-to-work-around-it) and
[Landing and Interdiction](always-on.md#what-the-game-does-and-doesnt-tell-us-and-how-to-work-around-it).

## Still stuck?

EDMC's **Help** menu can open its log folder. The log often says exactly what went wrong, and including it in a
report helps a lot. **Settings → WNTB → General → Help** has a **Report an issue** button and a **Copy diagnostics** button that do most of
the work: see [Reporting a problem](reporting-problems.md).
