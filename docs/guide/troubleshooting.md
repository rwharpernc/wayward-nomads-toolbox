# Troubleshooting

Find your symptom below. Most problems are a missing setting or a missing permission.

**Jump to:** [A number looks wrong](#a-number-looks-wrong-or-missing) · [General](#general) · [Overlay](#overlay) · [Linux](#linux) · [Trade](#trade) · [Still stuck?](#still-stuck)

## General

### The WNTB panel doesn't appear

Check that the folder is named exactly `WNTB` and sits directly inside EDMC's plugins folder, with files such as
`load.py` right inside it (not another folder inside it). So you want `plugins/WNTB/load.py`, not
`plugins/WNTB/WNTB/load.py`. Then restart EDMC.

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
- A feature can only look back a limited way (Missions two weeks, Colonisation 14 to 30 days, Boxel Survey 14 days).
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
- **Powerplay History** now shows only the commander you are playing. The other commanders' sessions are still saved.

## Overlay

### On-screen alerts don't show up

They need EDMCOverlay or EDMCModernOverlay running, and WNTB's **Overlay Connection** settings must match it. Use the
**Test** buttons in each feature's Settings tab to check.

The full checklist is in [Setting up the overlay](../OVERLAY_SETUP.md#if-nothing-shows-up).

### Notable Bodies never shows anything

It is switched off until you tick **Enable** under **Settings → Exploration → Alerts → Notable Bodies**. Only some
rules are on to start with, so tick the ones you want. A banner needs the overlay to be running.

## Linux

See [WNTB on Linux](linux.md) for the setup these refer to.

### On-screen alerts don't show, and Check connection says OK (Flatpak EDMC)

**Check connection** passes even when the overlay window never started. Grant the "run host programs" permission
(Step 3, command 4 in [WNTB on Linux](linux.md#step-3-if-edmc-is-a-flatpak-grant-it-four-permissions)), then
restart EDMC. You can confirm the overlay window is running with:

```bash
ps -eo args | grep overlay_client
```

### Auto-Honk or the screenshot timer say `xdotool` is not installed

Install `xdotool` on your system (Step 1). If EDMC is a Flatpak, also grant the "run host programs" permission
(Step 3, command 4) and restart EDMC. If it still fails, the EDMC log shows a "Host lookup of xdotool failed" line
with the reason.

### Auto-Honk says no usable keybind found

Either your fire button has no keyboard key (Step 4), or WNTB can't read the bindings folder.

- Bind a keyboard key to the second slot of Secondary Fire (Step 4).
- For a Flatpak EDMC, grant Step 3, command 2.
- Make sure **Elite Wine/Proton prefix** in **Settings → Exploration → Alerts** is empty unless you really use a
  custom setup. A wrong value there hides your keybindings.

### Auto-Honk presses the key but the scan stops after about a second

Fixed in 1.3.1 (earlier builds released the key too early under XWayland). Update WNTB.

### Features that read the journal find nothing

EDMC's **Journal directory** isn't set, or points at the wrong place. See
[Step 2](linux.md#step-2-tell-edmc-where-elites-journals-are).

## Trade

### The lookup buttons are greyed out, or there is no Commodity box

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

### Save session is greyed out, or the History window is empty

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

Often it is a limit of what the game records, not a fault. Each mode guide ends with "What the game does and doesn't
tell us, and how to work around it": [Powerplay](powerplay.md#what-the-game-does-and-doesnt-tell-us-and-how-to-work-around-it),
[Exploration](exploration.md#what-the-game-does-and-doesnt-tell-us-and-how-to-work-around-it),
[Mining](mining.md#what-the-game-does-and-doesnt-tell-us-and-how-to-work-around-it),
[Trade](trade.md#what-the-game-does-and-doesnt-tell-us-and-how-to-work-around-it),
[Missions](missions.md#what-the-game-does-and-doesnt-tell-us-and-how-to-work-around-it),
[Field Ops](field-ops.md#what-the-game-does-and-doesnt-tell-us-and-how-to-work-around-it),
[BGS](bgs.md#what-the-game-does-and-doesnt-tell-us-and-how-to-work-around-it) and
[Landing and Interdiction](always-on.md#what-the-game-does-and-doesnt-tell-us-and-how-to-work-around-it).

## Still stuck?

EDMC's **Help** menu can open its log folder. The log often says exactly what went wrong, and including it in a
report helps a lot. See [Getting help](../../README.md#getting-help).
