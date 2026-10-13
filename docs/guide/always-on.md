# Landing Assist, Interdiction Warning and Flight Alerts

These three tools are always available, whichever mode you're in. They don't belong to a mode. Interdiction Warning and Flight Alerts draw only on
your game screen, so they need an overlay running. Landing Assist can show in the EDMC panel without one, but its
diagram on the game screen needs an overlay. See [Getting started](getting-started.md#what-you-need) and
[Setting up the overlay](../OVERLAY_SETUP.md).

> **Where this comes from:** all three run on what the game writes (the journal, and for fuel the game's `Status.json`). The journal gives Landing Assist a pad number and the station type, with no orientation, and Interdiction Warning combines the game's early signals with its own `Interdicted` and `EscapeInterdiction` events. Flight Alerts reads `CarrierJumpRequest`, `Loadout`, `FSDTarget` and the fuel in `Status.json`. Nothing is looked up online. See [How WNTB knows what it knows](README.md#how-wntb-knows-what-it-knows).

## Landing Assist

Shows which landing pad you've been assigned while docking, in the EDMC panel and/or as a diagram on your game
screen (you choose which in Settings).

**To set it up:**

1. Open **Settings → Overlays → Landing**.
2. Tick **Enable Landing**. It is **off by default**.
3. Choose where it shows: **Show in EDMC app** (the panel; on by default once Landing is enabled) and/or
   **Show on Overlay** (the diagram on your game screen; off by default).
4. Press **Test Overlay** to check the diagram shows.

If the overlay is still starting when docking is approved, WNTB keeps retrying for up to three minutes, so the
diagram appears as soon as the overlay is up.

## Interdiction Warning

Puts an alert on your game screen the moment an interdiction starts. It has no panel button, only Settings.

**To set it up:**

1. Open **Settings → Overlays → Interdiction Warning**.
2. Tick **Enable Interdiction Warning**. It is **off by default**.
3. Press **Test Warning** to see what it looks like. The test works even while the feature is off, and reports
   whether an overlay could be reached.

## Flight Alerts

One small card on your game screen with two jobs. It has no panel button, only Settings.

- **Fleet carrier jump countdown.** When you schedule a jump, the card counts down to the departure time the game gave:
  `Carrier jumps to Sol (Earth) in 14:32`. It turns red for the last minute, and says `Carrier departing` at the time. A cancelled
  jump, or the jump itself, clears it. WNTB reads the request back from your newest journals when it starts, so restarting the
  game or EDMC during the countdown does not lose it.
- **Fuel warnings.** `Low fuel: 22% (7.0 t)` when the tank is at or under the percentage you choose (the game's own cockpit
  warning comes at 25%), and `No scoop at next star (neutron star). Fuel 38% (12.2 t)` when the star you have
  plotted to is one you cannot scoop (neutron stars, white dwarfs, black holes and the other non-main-sequence stars) and the
  tank is at or under a second percentage. That second warning is the one the game does not give you.

**To set it up:**

1. Open **Settings → Overlays → Flight Alerts**.
2. Tick **Enable Flight Alerts**. It is **off by default**. The countdown and the fuel warnings are two ticks under it (both on),
   with a percentage for each fuel warning (25% for low fuel, 50% for the unscoopable star).
3. Optionally tick **Play a sound when an alert starts**: it plays when a fuel alert starts and at 10 minutes, 5 minutes, 1 minute
   and departure for a carrier jump. The box is greyed out where WNTB cannot play a sound (on Linux it needs `canberra-gtk-play`
   or `paplay`).
4. Press **Test Card** to see it. The test works even while the feature is off, and reports whether an overlay could be reached.

Fuel warnings show only while you are flying your main ship, not docked, landed or scooping. Where the card sits is set on
**Overlay Placement** ("Flight alerts"); by default it is on the right, in the middle of the screen.

## Overlay connection

All three use the connection settings on the **Overlay Connection** Settings tab (Settings → Overlays), and where they appear
on screen is set on **Overlay Placement** (same place). The defaults
(`127.0.0.1`, port `5010`) match EDMCModernOverlay as they come. **Check connection** tells you
whether an overlay is listening.

## What the game does and doesn't tell us, and how to work around it

WNTB, like every third-party tool, only knows what Elite Dangerous writes to its journal files. It needs no outside service here, so the journal is the whole story. Where it can't be sure, WNTB says so rather than guess quietly. See [How WNTB knows what it knows](README.md#how-wntb-knows-what-it-knows).

| What you might expect | What the game gives | What to do |
|---|---|---|
| Landing Assist to show which way the pad faces | The journal gives only a **pad number** and the station type, with no orientation. | Use the diagram for which pad is yours; line up by the pad numbers in the game. |
| A diagram for every kind of facility | Some facilities have no diagram today. Own layouts are planned. | Use the pad number and follow the game's own docking guidance. |
| Interdiction Warning to fire before the game confirms | It combines three early signals, then the game's own `Interdicted` and `EscapeInterdiction` events, because they arrive separately. | Treat the alert as a prompt. The in-game screen is the final word. |
| A fuel warning that says whether you can make the next jump | The journal does not say what a jump costs in fuel. | WNTB compares **percentages** of the tank, so choose the percentages that suit your ship. |
| A fuel percentage the moment EDMC starts | The tank size comes from the game's `Loadout` event, written at login and when you change ship or a module. Until then WNTB has fuel in tonnes, but no percentage. | Only the game's own low-fuel flag is used until then. Log in again, or change a module or ship, to make the game write it. |
| A countdown for a jump you did not schedule | WNTB only knows a request the game wrote to your journal. | Use the in-game carrier screen for jumps scheduled by someone else. |
| An unscoopable-star warning for a star you have not plotted to | The star class comes from the target the game reports (`FSDTarget`). | Plot or select the next jump as usual; the warning appears then. |
| An overlay to be found automatically | WNTB can only draw if an overlay is listening on the connection details. | Use **Check connection**, **Test Overlay**, **Test Warning** and **Test Card** in Settings. |

