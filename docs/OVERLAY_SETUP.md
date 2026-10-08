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

In EDMC, open **File → Settings → WNTB**, choose **General**, then the **Overlay Connection** tab. The defaults are:

- **Host:** `127.0.0.1`
- **Port:** `5010`

These match EDMCModernOverlay and EDMCOverlay as they come, so you normally don't need to change anything.
If you changed the port in your overlay, enter the same one here.

## Step 4: Turn the features on and test them

Each feature has its own settings under **File → Settings → WNTB**, with a switch and a test button:

| Where | Test button |
|---|---|
| **Exploration → Alerts** (Discovery) | **Test Discovery** |
| **Exploration → Alerts** (Notable Bodies) | **Test Notable** |
| **Always On → Interdiction Warning** | **Test Warning** |
| **Always On → Landing** | **Test Overlay** |
| **Field Ops → Screenshots** | **Test Overlay** |

The test buttons work even while the feature is switched off, and they tell you whether the overlay
could be reached. Inventory and Mining have their own overlay switches in their tabs.

On the **Overlay Connection** tab, **Check connection** tells you whether an overlay is listening at the
host and port shown, without sending anything.

Start the overlay, start the game (or at least have the overlay running), and press a test button. If you
see the message on your screen, you're set.

## Moving things around

- **Discovery** and **Inventory** let you set where they appear, in their Settings tabs.
- Landing, Interdiction and the Screenshots message sit in fixed places.
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
   [Linux section of the README](../README.md#using-wntb-on-linux).

## A note for the curious

WNTB sends its drawings to the overlay over a local network connection on your own computer (the port
above). Nothing leaves your machine. WNTB keeps a single connection open for every feature, and registers
a "Plugin Group" with EDMCModernOverlay for each on-screen card so its background draws properly. The
technical details are in [TECHNICAL.md](TECHNICAL.md) section 10.
