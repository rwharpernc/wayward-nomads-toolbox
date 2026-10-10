# Troubleshooting

Find your symptom below. Most problems are a missing setting or a missing permission.

**Jump to:** [General](#general) · [Overlay](#overlay) · [Linux](#linux) · [Trade](#trade) · [Still stuck?](#still-stuck)

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

Many features read the game's journal, so they only know what has happened since EDMC started, plus a bit of recent
history. Each has a way to catch up:

- Powerplay has a **RESCAN** button.
- Codex Completionist has **BKF** (backfill from journal history).
- Trade catches its session up from the journals by itself; see
  [How a trading session works](trade.md#how-a-trading-session-works).

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
- If the numbers still look wrong, open an issue with the `CarrierStats` line from your journal (it is in the latest
  `Journal.*.log`).

## Still stuck?

EDMC's **Help** menu can open its log folder. The log often says exactly what went wrong, and including it in a
report helps a lot. See [Getting help](../../README.md#getting-help).
