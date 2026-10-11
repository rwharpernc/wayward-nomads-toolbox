# Setting up the on-screen overlay

Some WNTB features can draw on top of your game: an alert when you find something new, the landing pad
you've been assigned, a warning when you're being interdicted, and so on. To do that, WNTB needs a
small helper program running alongside the game, called an **overlay**.

You don't have to do any of this. **Every WNTB feature works without an overlay;** you just won't see the
on-screen extras.

## Which features use it

| Feature | What appears on screen |
|---|---|
| **Discovery Alerts** | A banner when you enter an unscanned system, or are first to scan or map a body |
| **Notable Bodies** | A banner when a body you scan matches a rule you chose (terraformable, high-value world, shepherd moon and more) |
| **Landing Assist** | The pad you've been assigned, with a diagram of the station or carrier |
| **Interdiction Warning** | An alert the moment an interdiction starts |
| **Inventory** | Capacity bars and pickup messages |
| **Mining** | Live stats, and an arrow pointing to your nearest saved hotspot |
| **Screenshots** | A short "Screenshot saved" message |

## Step 1: Choose an overlay

**EDMCModernOverlay is the recommended one.** It works on Windows and Linux.

- **[EDMCModernOverlay](https://github.com/SweetJonnySauce/EDMCModernOverlay)** (recommended). Its own
  installation guide is on its project wiki, so follow that for your system.
- The older **[EDMCOverlay](https://github.com/inorton/EDMCOverlay)** also works, on Windows only.

You only need one. WNTB talks to both in the same way, so it works with whichever you run. WNTB does not
install or start the overlay for you.

## Step 2: Set Elite up so the overlay can show

The overlay draws a transparent layer on top of the game. In Elite's graphics options, use **borderless**
or **windowed** mode, which work with every overlay. (EDMCModernOverlay also supports fullscreen; check
its own notes if you want that.)

## Step 3: Check WNTB's connection settings

In EDMC, open **File → Settings → WNTB**, choose **Overlays**, then the **Overlay Connection** tab. The defaults are:

- **Host:** `127.0.0.1`
- **Port:** `5010`

These match EDMCModernOverlay and EDMCOverlay as they come, so you normally don't need to change anything.
If you changed the port in your overlay, enter the same one here.

## Step 4: Turn the features on and test them

Every overlay setting lives in one place, **File → Settings → WNTB → Overlays**, with a tab for the shared connection, a
tab for placement, and a tab for each feature that draws on your screen. Each feature tab has its switch and, where it
makes sense, a test button:

| Overlays tab | What it controls | Test button |
|---|---|---|
| **Colonization** | The shopping list card | **Test Overlay** |
| **Discovery** | New system and body discovery alerts | **Test Discovery** |
| **Inventory** | Pickup notifications and the inventory bars | |
| **Interdiction Warning** | The warning when you are interdicted | **Test Warning** |
| **Landing** | The assigned pad and diagram | **Test Overlay** |
| **Mining** | The mining stats and the surface waypoint arrow | |
| **Notable Bodies** | Alerts for bodies worth a look | **Test Notable** |
| **Screenshots** | The "screenshot saved" message | **Test Overlay** |

The test buttons work even while the feature is switched off, and they tell you whether the overlay
could be reached. A feature's other settings (what it tracks, how it behaves) stay in its own tab elsewhere in
Settings; only the overlay parts moved here.

On the **Overlay Connection** tab, **Check connection** tells you whether an overlay is listening at the
host and port shown, without sending anything.

Start the overlay, start the game (or at least have the overlay running), and press a test button. If you
see the message on your screen, you're set.

## Moving things around

Where each display goes is set once, for every WNTB overlay, on **Settings → WNTB → Overlays → Overlay Placement**.

**Why not just x and y numbers?** An overlay program draws on a fixed 1280 × 960 canvas and maps it onto your game
window. In EDMCModernOverlay's default **fill** mode that means part of the canvas is cut off whenever your screen is
wider than 4:3: on a 16:9 monitor you see the top 1280 × 720 of it, on a 21:9 ultrawide 1280 × 536, and on a 32:9
monitor only 1280 × 360. A number that is fine on one monitor lands off the bottom of another. So WNTB places each
display **relative to the part you can actually see**, the way SRVSurvey places its overlays relative to the game
window.

**How to place something.** Pick one of nine spots (Top left, Top center, Top right, Middle left, Center, Middle right,
Bottom left, Bottom center, Bottom right) and two offsets. For the edge spots the offsets move the display inward from
the edge you chose; for Center and Middle they nudge it. "Bottom right, 20 and 20" is the bottom right corner of your
screen on any monitor. **Exact position** is there if you want an overlay-canvas x and y instead.

**How WNTB knows your screen.** It reads the size from Elite's own `DisplaySettings.xml` (in `Options\Graphics`; on
Linux inside the Proton prefix) and whether the overlay fits or fills the screen from EDMCModernOverlay's settings
(`scale_mode`). The tab shows what it found, for example *3840 x 2160, full screen (DisplaySettings.xml); overlay mode
fill shows 1280 x 720 of the 1280 x 960 canvas*. If either file can't be found, WNTB assumes a 16:9 screen in fill
mode, the smallest common area, so nothing is placed out of sight. You can also choose the screen shape and the mode
yourself on that tab. Elite's `FullScreen` value (windowed, borderless or full screen) is shown for information; the
overlay follows the game window either way.

**Check it on your real screen.** **Show placement preview** draws a labeled box for every display, and an outline of
the visible area, for 12 seconds, using the values currently typed (even before you press OK). **Reset all to
defaults** puts everything back, and **Detect screen again** re-reads the game's files.

Positions you set in the older per-feature x/y boxes are carried over as **Exact position** the first time.
Defaults for the displays that used to sit in fixed places (Landing, Interdiction, Mining, Screenshots) now follow
your screen shape, so they may sit slightly differently than before.

- If the overlay is still starting when Landing Assist has something to draw, WNTB retries for up to three minutes, so
  the diagram shows up once the overlay is ready.
- **EDMCModernOverlay has its own placement tool**, the Overlay Controller, where you can move each
  plugin's display, change anchors and backgrounds, and keep different profiles. See its wiki.

## If you don't use an overlay

Nothing breaks. WNTB tries to reach an overlay when a feature wants to draw something, and if none is
running it gives up quietly for 30 seconds before trying again. You'll see one line in EDMC's log saying no
overlay was found, and the on-screen extras simply don't appear.

## If nothing shows up

1. **Is the overlay running?** WNTB can't start it. Start it first.
2. **Does the port match?** Compare the one on WNTB's Overlay Connection tab with your overlay's.
3. **Is Elite in borderless or windowed mode?** Some overlays can't draw over exclusive fullscreen.
4. **Press the feature's test button.** The result says whether the overlay was reachable. A message like
   "could not reach the overlay" means steps 1 or 2.
5. **Did you restart after installing?** Restart EDMC (and the game, if needed) after installing or
   changing an overlay.
6. **Check the logs.** EDMC's Help menu can open its log folder, and EDMCModernOverlay keeps its own
   logs. Including them helps if you report a problem.
7. **Linux:** you need EDMCModernOverlay (the original is Windows-only). See the
   [Linux guide](guide/linux.md). If EDMC is a **Flatpak** and
   **Check connection** succeeds but nothing is drawn, the Flatpak needs permission to start the overlay
   window; the Linux guide gives the one-line `flatpak override` command.

## A note for the curious

WNTB sends its drawings to the overlay over a local network connection on your own computer (the port
above). Nothing leaves your machine. WNTB keeps a single connection open for every feature, and registers
a "Plugin Group" with EDMCModernOverlay for each on-screen card so its background draws properly. The
technical details are in [TECHNICAL.md](TECHNICAL.md) section 10.
