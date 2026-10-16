# Landing Assist, Interdiction Warning, Flight Alerts and the Route overlay

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

- **Fleet carrier jump countdown.** When you schedule a jump, the card counts down to the departure time the game gave, on short lines:
  `Carrier jump in 14:32`, then `To: Eorld Byoi XX-X d1-23` (the system, on a line of its own), then `Body: A 2` when the jump is to a
  particular body (just the part of the body's name after the system's, not the whole name again). It turns red for the last minute, and
  says `Carrier departing now` at the time. A cancelled
  jump, or the jump itself, clears it. WNTB reads the request back from your newest journals when it starts, so restarting the
  game or EDMC during the countdown does not lose it.
- **Fuel warnings.** `Low fuel` with `Tank 22% (7.0 t)` under it when the tank is at or under the percentage you choose (the game's own
  cockpit warning comes at 25%), and `No scoop at next star`, `(neutron star)`, `Fuel 38% (12.2 t)` when the star you have
  plotted to is one you cannot scoop (neutron stars, white dwarfs, black holes and the other non-main-sequence stars) and the
  tank is at or under a second percentage. That second warning is the one the game does not give you.

**To set it up:**

1. Open **Settings → Overlays → Flight Alerts**.
2. Tick **Enable Flight Alerts**. It is **off by default**. The countdown and the fuel warnings are two ticks under it (both on),
   with a percentage for each fuel warning (25% for low fuel, 50% for the unscoopable star).
3. Optionally tick **Play a sound when an alert starts**: it plays when a fuel alert starts and at 10 minutes, 5 minutes, 1 minute
   and departure for a carrier jump. The box is grayed out where WNTB cannot play a sound (on Linux it needs `canberra-gtk-play`
   or `paplay`).
4. Press **Test Card** to see it. The test works even while the feature is off, and reports whether an overlay could be reached.

The card is always the same width and wraps what it says onto more lines (at the end of a sentence first), growing downward, so nothing
runs off the screen however long a system name is. Fuel warnings show only while you are flying your main ship, not docked, landed or scooping. Where the card sits is set on
**Overlay Placement** ("Flight alerts"); by default it is on the right, below the Inventory display.

## Route overlay

One card on your game screen for a trip. It has no panel button, only Settings.

- **Travel status, at the top.** `Fuel 38%  12.2 / 32 t` (red when the tank is at or under 25%), `Range 61.4 ly   Last jump 3.2 t`,
  `19 jumps left   412 ly`, and `Next supercharge: 2 jumps, neutron star` (or `No supercharge on the route`). A line the game has not
  given you yet is left out.
- **The systems you are jumping to, below it.** The route you plotted in the game, in order, one system to a row with its star beside it.
  A **neutron star** and a **white dwarf** are picked out in color, name and all, so you can get ready to line up
  the supercharge. Another star you cannot scoop (a black hole, a Wolf-Rayet or carbon star, a brown dwarf) is marked in a warning color so you can
  plan the fuel; an ordinary star shows its class letter, dim. A last line counts the systems beyond the list and how many of them are
  neutron stars or white dwarfs (`+ 14 more (3 neutron, 1 white dwarf)`).

**To set it up:**

1. Open **Settings → Overlays → Route**.
2. Tick **Enable the Route overlay**. It is **off by default**. **Systems listed** (3 to 20, 8 to start) is how many of the next systems
   the card lists.
3. Optionally untick **Show the active expedition on this card**. With it ticked (the default), a running Expedition (Exploration mode) adds its name and
   progress, what you have found at the stop you are at, the next stop with its distance and its note, and the stop you have just reached, between the status lines and
   the route. An expedition with no plotted route still draws the card.
4. Press **Test Card** to see it with a made-up trip. The test works even while the feature is off, and reports whether an overlay could be reached.

The card follows you along the route as you jump, and clears when you reach the end, clear the route, or jump to a system that is not on
it. After a restart it reads the route the game has saved, so it comes straight back. Every line starts at the same left edge, the card's
padding and text size follow **Appearance**, and where it sits is set on **Overlay Placement** ("Route and ship status"); by default it
is at the top left, above the Colonization list.

**What it cannot tell you:** the journal does not say what the next jump will cost in fuel, so the card shows the fuel on board and what
your last jump used, not whether the tank is enough. The range is your ship's maximum with its current modules, from the game's `Loadout`
event, not the range with the cargo and fuel it carries now. Distances are straight lines between the systems on the route.

## Overlay connection

All three use the connection settings on the **Overlay Connection** Settings tab (Settings → Overlays), and where they appear
on screen is set on **Overlay Placement** (same place). That tab is also where you choose which overlay draws: WNTB's own built-in overlay (Windows) or EDMCModernOverlay. For EDMCModernOverlay the defaults
(`127.0.0.1`, port `5010`) match it as they come. **Check connection** tells you
whether the overlay is reachable. See [Setting up the overlay](../OVERLAY_SETUP.md).

## What the game does and doesn't tell us, and how to work around it

WNTB, like every third-party tool, only knows what Elite Dangerous writes to its journal files. It needs no outside service here, so the journal is the whole story. Where it can't be sure, WNTB says so rather than guess quietly. See [How WNTB knows what it knows](README.md#how-wntb-knows-what-it-knows).

| What you might expect | What the game gives | What to do |
|---|---|---|
| Landing Assist to show which way the pad faces | The journal gives only a **pad number** and the station type, with no orientation. | Use the diagram for which pad is yours; line up by the pad numbers in the game. |
| A diagram for every kind of facility | Some facilities have no diagram, and the journal does not say enough (which layout, which way it faces) to draw one. | Use the pad number and follow the game's own docking guidance. |
| Interdiction Warning to fire before the game confirms | It combines three early signals, then the game's own `Interdicted` and `EscapeInterdiction` events, because they arrive separately. | Treat the alert as a prompt. The in-game screen is the final word. |
| A fuel warning that says whether you can make the next jump | The journal does not say what a jump costs in fuel. | WNTB compares **percentages** of the tank, so choose the percentages that suit your ship. |
| A fuel percentage the moment EDMC starts | The tank size comes from the game's `Loadout` event, written at login and when you change ship or a module. Until then WNTB has fuel in tonnes, but no percentage. | Only the game's own low-fuel flag is used until then. Log in again, or change a module or ship, to make the game write it. |
| A countdown for a jump you did not schedule | WNTB only knows a request the game wrote to your journal. | Use the in-game carrier screen for jumps scheduled by someone else. |
| An unscoopable-star warning for a star you have not plotted to | The star class comes from the target the game reports (`FSDTarget`). | Plot or select the next jump as usual; the warning appears then. |
| An overlay to be found automatically | WNTB can only draw if an overlay is listening on the connection details. | Use **Check connection**, **Test Overlay**, **Test Warning** and **Test Card** in Settings. |

