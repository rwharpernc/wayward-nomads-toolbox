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
| **Flight Alerts** | A small card with the fleet carrier jump countdown and the low-fuel and unscoopable-star warnings |
| **Route** | A card with your fuel and jump range, the jumps left and the plotted route (neutron stars and white dwarfs picked out), and the running expedition |
| **Bio status**, **Biology**, **Bio radar**, **Sample popup** | The Exobiology cards: sampling progress and distance, predicted species and what they pay, a plot of your samples and their circles, and a popup after each sample |
| **System targets** | A list of scanned bodies worth mapping and bodies with life not yet analysed, with the scan progress |
| **Body info** | A card describing the body you have targeted or are close to |
| **Missions** | A small card of your missions: those here and at the next jump first, then the rest by urgency |
| **Inventory** | Capacity bars and pickup messages |
| **Mining** | Live stats |
| **Surface Compass** | An arrow, a name and a distance pointing at a hotspot or a mark on the planet you are on |
| **Screenshots** | A short "Screenshot saved" message |

## Step 1: Choose an overlay

**EDMCModernOverlay is the recommended one.** It works on Windows and Linux.

- **[EDMCModernOverlay](https://github.com/SweetJonnySauce/EDMCModernOverlay)** (recommended). Its own
  installation guide is on its project wiki, so follow that for your system.

WNTB does not install or start the overlay for you.

## Step 2: Set Elite up so the overlay can show

The overlay draws a transparent layer on top of the game. In Elite's graphics options, use **borderless**
or **windowed** mode, which work with every overlay. (EDMCModernOverlay also supports fullscreen; check
its own notes if you want that.)

## Step 3: Check WNTB's connection settings

In EDMC, open **File → Settings → WNTB**, choose **Overlays**, then the **Overlay Connection** tab. The defaults are:

- **Host:** `127.0.0.1`
- **Port:** `5010`

These match EDMCModernOverlay as they come, so you normally don't need to change anything.
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
| **Flight Alerts** | The carrier jump countdown and fuel warnings card | **Test Card** |
| **Route** | The route card (how many systems to list, whether to show the running expedition) | **Test Card** |
| **Exobiology** | Four switches, one for each Exobiology card | **Test Cards** |
| **System targets** | The list of bodies to map and sample (value threshold, rows, life list) | **Test Card** |
| **Body info** | The body card (targeted body, nearby body) | **Test Card** |
| **Missions** | The missions card (rows to show, next jump, urgent limit) | **Test Card** |
| **Landing** | The assigned pad and diagram | **Test Overlay** |
| **Mining** | The mining stats | |
| **Surface Compass** | The arrow, name and distance pointing at a hotspot or a mark on the planet you are on | **Test Compass** |
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

**Why not just x and y numbers?** An overlay program places things on a fixed 1280 × 960 canvas and maps it onto your game
window, and it treats *positions* and *sizes* differently. A position is a fraction of the screen (x ÷ 1280 across, y ÷ 960
down), so the canvas is stretched over the whole screen. A size, though, is in screen pixels, scaled by Windows' display
scaling. On a 3840 × 2160 screen at 125% scaling that makes a 360-pixel-wide card only 12% of the screen's width. A raw
number therefore means a different place on every monitor, and a "right edge" position depends on how big the display is.

**How to place something.** Pick one of nine spots (Top left, Top center, Top right, Middle left, Center, Middle right,
Bottom left, Bottom center, Bottom right) and two offsets **in screen pixels**. For the edge spots the offsets move the
display inward from the edge you chose; for Center and Middle they nudge it. "Bottom left, 40 and 40" is 40 pixels in from the
bottom left corner of your screen on any monitor, whatever size the display is. **Exact position** is there if you want an
overlay-canvas x and y instead.

**Hiding a display.** Each row has a **Show** checkbox. Untick it and that display is never drawn, whatever its own settings say, and
what is already on screen goes the next time it would redraw. The spot and offsets are kept, so ticking it again puts it back where it
was. It works for every display on the tab (Colonization shopping list, Discovery, Notable, Flight alerts, Route, Interdiction, Missions, Landing, Inventory, Mining
stats, Surface compass, Screenshot messages). **Reset all to defaults** shows them all again.

**How WNTB knows your screen.** It reads what the overlay itself is using: the window size, fit or fill mode and display
scaling from EDMCModernOverlay's own log (its newest "Overlay scaling updated" line). If that isn't there it falls back to
Elite's `DisplaySettings.xml` (in `Options\Graphics`; on Linux inside the Proton prefix) for the size, Windows' display scaling,
and EDMCModernOverlay's settings for the mode. The tab shows what it found, for example *3840 x 2160, full screen, display
scaling 125% (EDMCModernOverlay log); overlay mode fill*. You can set the display scaling and the mode yourself on that tab if
they are wrong.

**The right-hand edge.** Across a wide screen EDMCModernOverlay limits a shape's left position plus its pixel width to the
canvas width, and squashes the shape if it would pass that, so a display cannot simply be drawn against the right edge. The
overlay does apply a *group offset* after that limit (it is how its own Overlay Controller moves things), and offers it to
plugins. So for a display on the right, WNTB draws it as far right as the limit allows and sets that display's group offset
through EDMCModernOverlay's own plugin API to carry it the rest of the way. You will see these as offsets on WNTB's groups in
the Overlay Controller. If you move one of WNTB's groups in the Overlay Controller yourself, that wins over WNTB's setting.
This needs EDMCModernOverlay; without it (or if the call fails) a display on the right stops where the limit allows, a little
short of the edge. The Overlay Placement tab has a switch, **Carry displays on the right to the screen edge**, that turns this off
(and clears the offsets) if displays end up in the wrong place. The bottom edge needs none of this. The two Mining displays share one overlay group, so they stop at the limit
rather than being offset.

**Default spots.** On a 1920 x 1080 screen or larger the default spots do not overlap each other (the Route card is at the top left; the right-hand column runs Notable, Surface compass, Inventory, Mining stats, Flight alerts, Missions and Screenshot messages from the top; System targets and Body info sit one above the other in the lower middle of the right half of the screen). The Exobiology cards start at the top center (Bio status), the bottom center left of the Body info card (Biology), the left middle (Bio radar) and above Biology (Sample popup); the radar and the popup share a spot with the Colonization list, and Bio status with the Interdiction warning, because those are never up at the same time (a planet's surface, a construction depot, supercruise). The displays are sized in pixels, so on a
smaller screen they take up more of it and some can overlap: use **Show placement preview** and move them. A position you chose yourself
is never changed.

**Check it on your real screen.** **Show placement preview** draws a labeled box for every display, at its real size, for
12 seconds, using the values currently typed (even before you press OK). **Reset all to defaults** puts everything back, and
**Detect screen again** re-reads the overlay's log and the game's files.

An **Exact position** that would leave a display off the overlay's canvas (for example a leftover `x = 1280` on a 1280-wide screen) is ignored: the
display uses its default spot instead, and the EDMC log says so. Your saved text is not changed.

Positions you set in the older per-feature x/y boxes are carried over as **Exact position** the first time. Defaults for
the displays that used to sit in fixed places (Landing, Interdiction, Mining, Screenshots) now follow your screen, so they
may sit slightly differently than before.

### Appearance: colors and text size

**Settings → WNTB → Overlays → Appearance** sets how every WNTB overlay looks, all at once:

- **Color scheme**: Elite orange (the default), Ice blue, Phosphor green, Amber mono, High contrast, or Color-blind safe
  (Okabe-Ito colors, so good, short and warning never rest on red against green). The chips show each color's role.
- **Text size**: Default or Larger. It starts at **Larger**, the size the displays have had since 1.9.0, so nothing
  changes until you choose. If the overlays look too big on a small or high-resolution screen, try Default. Overlay text is never drawn below the
  overlay's "normal" size, which stays readable over the game.
- **Show sample** draws the Colonization card with the scheme and size currently picked (before you press OK); **Reset appearance**
  puts the defaults back.

Padding and line spacing are **fixed**, so columns stay lined up. Every card uses the same padding, so its text sits the same distance from the
border on all four sides, and every line of text starts at the card's left edge (no card centers its text). EDMCModernOverlay cannot measure text
for a plugin, so each card's
width and height are worked out from the character count at the chosen size, with a further 10% added to every width, so text sits
inside the border. The overlay's own font limits (EDMCModernOverlay's `min_font_point` and `max_font_point`) still apply on top.
Placement accounts for the new size too (a display anchored to the bottom or right keeps its edge). The Interdiction warning
keeps its fixed red alert colors whatever scheme is chosen. The default look is slightly roomier than older versions.

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
8. **Does only one display never show?** Its saved position may be off the screen. Reset it on the Overlay Placement tab; see
   [Troubleshooting](guide/troubleshooting.md#one-display-never-shows-though-test-and-the-overlay-window-both-work).

## A note for the curious

WNTB sends its drawings to the overlay over a local network connection on your own computer (the port
above). Nothing leaves your machine. WNTB keeps a single connection open for every feature, and registers
a "Plugin Group" with EDMCModernOverlay for each on-screen card so its background draws properly. The
technical details are in [TECHNICAL.md](TECHNICAL.md) section 10.
