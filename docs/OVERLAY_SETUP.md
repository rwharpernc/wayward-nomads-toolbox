# Setting up the on-screen overlay

Some WNTB features can draw on top of your game: an alert when you find something new, the landing pad
you've been assigned, a warning when you're being interdicted, cards for the body you are on, and so on. To do that, something has to draw
a transparent layer over Elite. That something is an **overlay**, and WNTB can use one of two.

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
| **Expedition Log** | The running expedition's exploration and exobiology totals and what it has earned |
| **Bio status**, **Biology**, **Bio radar**, **Sample popup** | The Exobiology cards: sampling progress and distance, predicted species and what they pay, a plot of your samples and their circles, and a popup after each sample |
| **System targets** | A list of scanned bodies worth mapping and bodies with life not yet analysed, with the scan progress |
| **Body info** | A card describing the body you have targeted or are close to |
| **Missions** | A small card of your missions: those here and at the next jump first, then the rest by urgency |
| **Inventory** | Capacity bars and pickup messages |
| **Mining** | Live stats |
| **Surface Compass** | An arrow, a name and a distance pointing at a hotspot or a mark on the planet you are on |
| **Screenshots** | A short "Screenshot saved" message |

## Step 1: Choose an overlay

There are two, and you pick one under **Settings → WNTB → Overlays → Overlay Connection → Which overlay draws**.

| | **WNTB's built-in overlay** | **EDMCModernOverlay** |
|---|---|---|
| What it is | A transparent window WNTB itself lays over Elite, drawn from inside EDMC | A separate program (an EDMC plugin with its own helper window) WNTB sends its drawings to |
| Systems | **Windows only** | Windows and Linux |
| Install | Nothing: it is part of WNTB | Install it yourself ([project page](https://github.com/SweetJonnySauce/EDMCModernOverlay) and its wiki) |
| Draws | **WNTB's displays only** | WNTB's and every other plugin that supports it |
| Chosen with | The setting above (off until you choose it) | The same setting (it is the default) |
| Font | Its own: Source Sans 3 (lower case), or any `.ttf` / `.otf` you add; changes at once | One font for all plugins, in its own list; takes effect after a restart |
| Cards fit their text | Exactly (the text is measured in the font in use) | By estimate, a little roomier |
| Card corners | Rounded (your choice: square to very rounded) | Square |
| Stray windows | Cannot happen: it ends with EDMC | An old window can be left running (see [Known issues](guide/known-issues.md)) |
| Elite must run | Borderless or windowed | Borderless or windowed (it also lists fullscreen: check its notes) |

### Do I still need EDMCModernOverlay?

- **For WNTB's displays on Windows: no.** Choose the built-in overlay and WNTB needs nothing else. It no longer requires EDMCModernOverlay.
- **On Linux: yes.** The built-in overlay is Windows only, so Linux uses EDMCModernOverlay.
- **For other plugins' overlays: yes.** The built-in overlay draws WNTB's displays and nothing else. A plugin that draws through EDMCModernOverlay (or the older EDMCOverlay) still needs it,
  and it will keep drawing there whatever WNTB does.

### Using both

You can keep EDMCModernOverlay installed and running next to the built-in overlay:

- **Only one draws WNTB's displays.** With the built-in overlay chosen WNTB sends nothing to EDMCModernOverlay, so nothing of WNTB's is drawn twice. EDMCModernOverlay keeps drawing the other plugins' displays.
- **Two windows over Elite is fine.** Each is transparent and lets clicks through. They do not know about each other, so if another plugin's display and one of WNTB's land on the same spot they overlap; move WNTB's
  in Overlay Placement.
- **Switching** takes effect when you press OK. Restart EDMC after switching, so anything the other overlay was still showing from WNTB expires (most displays last a few seconds; the Colonization card is left up for up to an hour).
- **Fonts stay separate.** The built-in overlay's font and EDMCModernOverlay's are chosen independently (see [Fonts](#fonts)).
- **The Hide overlays switch hides WNTB's displays only**, in whichever overlay draws them.

WNTB does not install or start EDMCModernOverlay for you. The built-in overlay starts and stops with EDMC.

## Step 2: Set Elite up so the overlay can show

An overlay draws a transparent layer on top of the game, so Elite cannot be in exclusive fullscreen: in Elite's graphics options use **borderless**
or **windowed** mode. (EDMCModernOverlay also supports fullscreen; check its own notes if you want that. The built-in overlay does not.)

## Step 3: Check the settings

In EDMC, open **File → Settings → WNTB**, choose **Overlays**, then the **Overlay Connection** tab.

- **Built-in overlay:** pick **WNTB built-in overlay (Windows)** under *Which overlay draws* and press OK. The tab then says whether it is running over Elite. Nothing else is needed.
- **EDMCModernOverlay:** the defaults are **Host** `127.0.0.1` and **Port** `5010`. These match EDMCModernOverlay as they come, so you normally don't need to change anything. If you changed the
  port in your overlay, enter the same one here.

## Step 4: Turn the features on and test them

Every overlay setting lives in one place, **File → Settings → WNTB → Overlays**, with a tab for the shared connection, a
tab for placement, a tab for appearance, a tab for hiding, and a tab for each feature that draws on your screen. Each feature tab has its switch and, where it
makes sense, a test button:

| Overlays tab | What it controls | Test button |
|---|---|---|
| **Overlay Connection** | Which overlay draws; EDMCModernOverlay's host and port; keep showing for screenshots | **Check connection** |
| **Overlay Placement** | Where every display sits (layout editor) | **Show placement preview** |
| **Appearance** | Color scheme, text size, panel opacity and the overlay font | **Show sample** |
| **Hide overlays** | The keyboard shortcut (Windows) and a button to hide or show every overlay | **Hide / show now** |
| **Colonization** | The shopping list card | **Test Overlay** |
| **Discovery** | New system and body discovery alerts | **Test Discovery** |
| **Inventory** | Pickup notifications and the inventory bars | |
| **Interdiction Warning** | The warning when you are interdicted | **Test Warning** |
| **Flight Alerts** | The carrier jump countdown and fuel warnings card | **Test Card** |
| **Route** | The route card (how many systems to list, whether to show the running expedition) | **Test Card** |
| **Expedition Log** | The card of the running expedition's totals (and whether to keep showing the last one after it is stopped) | **Test Card** |
| **Exobiology** | Four switches, one for each Exobiology card | **Test Cards** |
| **System targets** | The list of bodies to map and sample (value threshold, what the value is judged by, rows, life list) | **Test Card** |
| **Body info** | The body card (targeted body, nearby body, symbols or full names for elements and compounds) | **Test Card** |
| **Missions** | The missions card (rows to show, next jump, urgent limit) | **Test Card** |
| **Landing** | The assigned pad and diagram | **Test Overlay** |
| **Mining** | The mining stats | |
| **Surface Compass** | The arrow, name and distance pointing at a hotspot or a mark on the planet you are on | **Test Compass** |
| **Notable Bodies** | Alerts for bodies worth a look | **Test Notable** |
| **Screenshots** | The "screenshot saved" message | **Test Overlay** |

The test buttons work even while the feature is switched off, and they tell you whether the overlay
could be reached. A feature's other settings (what it tracks, how it behaves) stay in its own tab elsewhere in
Settings; only the overlay parts moved here.

**Check connection** tells you whether the overlay is reachable: for EDMCModernOverlay, whether one is listening at the host and port shown (it sends nothing); for the built-in overlay, whether it is running and
whether it has found Elite's window. It also says when more than one EDMCModernOverlay window is running.

Start the overlay (EDMCModernOverlay) or just start EDMC (the built-in overlay), start the game, and press a test button. If you
see the message on your screen, you're set.

## Moving things around

Where each display goes is set once, for every WNTB overlay, on **Settings → WNTB → Overlays → Overlay Placement**.

**Overlay settings are per commander.** Which cards are switched on, their options, where each one sits, which are hidden, the
screen scaling and the look (color scheme, text size, panel opacity, font, corners) are saved for the commander who is playing,
so a commander who never uses the Expedition card can leave it off while another has it on. The first time a commander is seen
after updating, they start with a copy of the choices already in place, so nothing moves. A commander's choices are filed when
Settings are saved and when you switch commanders (log in as another one, or restart EDMC). Which overlay draws (the built-in
one or EDMCModernOverlay), its host and port and the hide hotkey describe your computer, so they are shared. Choices saved when
EDMC does not yet know the commander go to the first commander it sees.

**Why not just x and y numbers?** Both overlays place things on a fixed 1280 × 960 canvas and maps it onto your game
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
was. It works for every display on the tab (Colonization shopping list, Discovery, Notable, Flight alerts, Route, Expedition Log, Biology, Bio status, Bio radar, Sample popup, System targets, Body
info, Interdiction, Missions, Landing, Inventory, Mining stats, Surface compass, Screenshot messages). **Reset all to defaults** shows them all again.

**How WNTB knows your screen.** With the built-in overlay it reads Elite's own window: its size and the display scaling where it sits, live, so it follows you when you move or resize the game. With
EDMCModernOverlay it reads what that overlay itself is using: the window size, fit or fill mode and display
scaling from EDMCModernOverlay's own log (its newest "Overlay scaling updated" line). If that isn't there it falls back to
Elite's `DisplaySettings.xml` (in `Options\Graphics`; on Linux inside the Proton prefix) for the size, Windows' display scaling,
and EDMCModernOverlay's settings for the mode. The tab shows what it found, for example *3840 x 2160, full screen, display
scaling 125% (EDMCModernOverlay log); overlay mode fill*. You can set the display scaling and the mode yourself on that tab if
they are wrong.

**The right-hand edge (EDMCModernOverlay only; the built-in overlay has no such limit and draws against any edge).** Across a wide screen EDMCModernOverlay limits a shape's left position plus its pixel width to the
canvas width, and squashes the shape if it would pass that, so a display cannot simply be drawn against the right edge. The
overlay does apply a *group offset* after that limit (it is how its own Overlay Controller moves things), and offers it to
plugins. So for a display on the right, WNTB draws it as far right as the limit allows and sets that display's group offset
through EDMCModernOverlay's own plugin API to carry it the rest of the way. You will see these as offsets on WNTB's groups in
the Overlay Controller. If you move one of WNTB's groups in the Overlay Controller yourself, that wins over WNTB's setting.
This needs EDMCModernOverlay; without it (or if the call fails) a display on the right stops where the limit allows, a little
short of the edge. The Overlay Placement tab has a switch, **Carry displays on the right to the screen edge**, that turns this off
(and clears the offsets) if displays end up in the wrong place. The bottom edge needs none of this. The two Mining displays share one overlay group, so they stop at the limit
rather than being offset.

**Opacity and clicking through.** Both overlays let clicks and keys through to the game, and neither takes the focus. **Settings → Overlays → Appearance → Panel opacity** sets how solid every WNTB display's background is (100%, 90% by default, 75%, 60%, 40% or 25%); the text stays solid, so a faint panel lets the game show through behind readable text. EDMCModernOverlay's window is click-through except while its own drag or controller mode is on, so there is nothing to set in WNTB, and it also has an overall opacity in its own settings that dims everything it draws, text included. If clicks do not pass through, see that program's click-through notes (on GNOME its extension is needed).

**Plain panels.** The Route, System targets, Body info and Exobiology cards and the Bio radar are plain dark panels, with no colored bar or outline, so they sit quietly over the game.

**The layout editor.** Above the table is a to-scale picture of your screen with a grid and a box for every display. Drag a box and drop it: WNTB works out the spot (the third of the screen its center is in) and the offset in screen pixels and fills in the table. A box dropped within a few pixels of an edge snaps flush to it (offset 0), one near the middle snaps to the center line, and the rest snap to the grid you choose (20, 40, 60 or 120 pixels); untick *Snap to the grid and to edges* to place a box exactly. Boxes are drawn at each display's size at your text size, so what you see is the room it takes; a card that grows (a list with more rows) is placed from the size it is drawn at, so a zero offset at the bottom or right is the screen edge. **Picture size** (Default, Large or Extra large) makes the picture bigger for finer placement; the choice is remembered. Typing in the table moves the box, and *Show placement preview* draws the real thing on your screen.

**Default spots.** On a 1920 x 1080 screen or larger the default spots do not overlap each other (the Route card is at the top left; the right-hand column runs Notable, Surface compass, Inventory, Mining stats, Flight alerts, Missions and Screenshot messages from the top; System targets and Body info sit one above the other in the lower middle of the right half of the screen). The Exobiology cards start at the top center (Bio status), the bottom center left of the Body info card (Biology), the left middle (Bio radar) and above Biology (Sample popup); the Expedition Log card sits at the top left, to the right of the Route card; the radar and the popup share a spot with the Colonization list, and Bio status and the Expedition Log with the Interdiction warning, because those are never up at the same time (a planet's surface, a construction depot, supercruise). The displays are sized in pixels, so on a
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
- **Panel opacity**: how solid every display's background is (100%, 90% by default, 75%, 60%, 40% or 25%). The text stays solid, so a faint panel lets the game show through
  behind readable text; over a bright scene, 75% or more keeps small text easiest to read. Every text color in every scheme keeps strong contrast over a dark panel.
- **Corners (built-in overlay)**: how rounded every card's corners are: Square, Slightly rounded, **Rounded** (the default), or Very rounded. It applies to the panels only (dividers and bars stay square) and only to WNTB's built-in overlay: EDMCModernOverlay cannot draw rounded rectangles, so its cards stay square.
- **Overlay font**: the font the overlay draws in; see [Fonts](#fonts) below. It follows whichever overlay is chosen.
- **Show sample** draws the Colonization card with the scheme and size currently picked (before you press OK); **Reset appearance**
  puts the defaults back.

Padding and line spacing are **fixed**, so columns stay lined up. Every card uses the same padding, so its text sits the same distance from the
border on all four sides, and every line of text starts at the card's left edge (no card centers its text). With the built-in overlay each card's box is sized from the text itself, measured in the font in use (with 5% to spare for the font's rounding), so the box fits closely and right-hand values sit against its edge. EDMCModernOverlay cannot measure text
for a plugin, so with it each card's
width and height are worked out from the character count at the chosen size, with a further 10% added to every width, so text sits
inside the border; its own font limits (`min_font_point` and `max_font_point`) apply on top.
Placement accounts for the new size too (a display anchored to the bottom or right keeps its edge). The Interdiction warning
keeps its fixed red alert colors whatever scheme is chosen. The default look is slightly roomier than older versions.

- If the overlay is still starting when Landing Assist has something to draw, WNTB retries for up to three minutes, so
  the diagram shows up once the overlay is ready.
- **EDMCModernOverlay has its own placement tool**, the Overlay Controller, where you can move each
  plugin's display, change anchors and backgrounds, and keep different profiles. See its wiki.

## The built-in overlay (Windows)

WNTB's own overlay is a transparent window it lays over Elite, drawn from inside EDMC. Choose it under **Settings → WNTB → Overlays → Overlay Connection → Which overlay draws**, press OK, and start
Elite in **borderless or windowed** mode (a fullscreen game cannot be drawn over). It is off until you choose it, and choosing EDMCModernOverlay again switches back. See
[the comparison above](#step-1-choose-an-overlay) for when you would pick which.

**How it behaves**
- It follows Elite's window as you move or resize it, and uses the display scaling where the window is.
- It shows only while Elite is the window you are in, and hides when you alt-tab away (a stale card is never left over another program). It lets clicks and keys through to the game and never takes the focus.
- When you bring Elite back to the front the overlay puts itself back above it; it checks every half second.
- It lives and dies with EDMC, so it cannot leave a second overlay window behind (see [Known issues](guide/known-issues.md)).
- It draws all of WNTB's displays, with Overlay Placement and its layout editor, panel opacity, color schemes, text size and Hide overlays working as they do with EDMCModernOverlay.
- **Check connection** reports whether it is running and whether it has found Elite's window.

**Screenshots**
- Elite's own screenshot key (F10) never includes an overlay.
- **Windows' capture tools** (the Snipping Tool, Win+Shift+S, Print Screen and the Game Bar) take the focus while you pick what to capture. WNTB recognizes them, so the overlay stays up and is in the picture.
- For any **other tool** that takes the focus, tick **Keep showing when Elite is not the window in front** in the same box; the overlay then stays up whenever Elite is running.
- To have the cards in a screenshot Elite itself takes, tick **Include WNTB's built-in overlay in the converted screenshot** under **Settings → WNTB → Field Ops → Screenshots**: the converted copy then has
  the cards that were on screen when you pressed the key drawn onto it.

**Limits**
- Windows only; Linux uses EDMCModernOverlay.
- It draws WNTB's displays only. Other plugins' displays need EDMCModernOverlay (see [Do I still need EDMCModernOverlay?](#do-i-still-need-edmcmodernoverlay)).
- It is new: report anything that looks off. The design and what is left are in [the built-in overlay specification](NATIVE_OVERLAY_SPEC.md).

## Fonts

**Settings → WNTB → Overlays → Appearance → Overlay font** chooses the font the overlay draws in. Which font that is depends on the overlay you chose:

**Built-in overlay: WNTB's own fonts**
- It starts with **Source Sans 3**, which WNTB ships (a clear font with lower case letters; SIL Open Font License, the license is in the `fonts` folder next to it).
- **Add font file...** copies a `.ttf` or `.otf` you pick into WNTB's own `fonts` folder (inside the plugin folder) and chooses it. The change is used straight away: no restart. **Open fonts folder** shows the folder;
  you can also drop font files into it yourself and pick them from the list.
- A font you add **stays through WNTB updates** (an update only replaces the files it ships). You can remove one by deleting the file.
- Where to find fonts: [Google Fonts](https://fonts.google.com/) has many free ones. **Keep a font's license with it**: WNTB does not install or license fonts for you, and not every font may be redistributed.
  A font used only on your own machine is yours to use as its license allows.
- A very large or unusual font file may draw slowly or oddly; a plain regular weight works best. If a chosen file is missing or unreadable WNTB falls back to Source Sans 3.

**EDMCModernOverlay: its font, for every plugin**
- The overlay takes the first font it can load from the list in its `overlay_client/fonts/preferred_fonts.txt`, and its default is Elite's cockpit font, which has **capital letters only**: every plugin's text shows in capitals.
- WNTB can edit that list for you: pick a font from the folder, or **Add font file...** to copy one in, and WNTB puts it first (keeping a `.bak` of the old list once). **Overlay default** goes back to the cockpit font.
- It takes effect when EDMCModernOverlay starts again (restart EDMC), and it changes every plugin's text, since the overlay takes one font. WNTB cannot give its own cards a different font here.
- An EDMCModernOverlay update can put its own list back.

**Both:** the font choices are independent. WNTB's species names are written `Tussock pennatis`; in the cockpit font they show as `TUSSOCK PENNATIS`. No overlay can draw italics, so scientific names are not italicized.

## Streaming and recording

Both overlays (WNTB's built-in one and EDMCModernOverlay) draw in a separate transparent window laid over Elite. They do not draw inside the game's own graphics, so whether a stream or a recording includes them depends on how it captures the picture. This has not been tested with every program; what follows is how the capture methods work in general.

- **Display capture** (OBS "Display Capture", or any capture of the whole monitor) records everything on the screen, so it should include the overlay.
- **Game capture** (OBS "Game Capture") hooks Elite's own rendering, so it most likely does not include the overlay window.
- **Window capture** (OBS "Window Capture" pointed at Elite) records only Elite's window, so it most likely does not include the overlay either. The result can differ between capture programs and versions.

Two things to know when you use display capture:
- The built-in overlay shows only while Elite is the window you are in (see [The built-in overlay](#the-built-in-overlay-windows)). If you click over to your streaming program, the overlay hides and the capture loses it. Tick **Keep showing when Elite is not the window in front** in the same box to keep it up whenever Elite is running.
- Elite must run borderless or windowed.

If your capture method does not include the overlay, Elite's screenshot feature is a separate route: tick **Include WNTB's built-in overlay in the converted screenshot** under **Settings -> WNTB -> Field Ops -> Screenshots** (Windows, built-in overlay only).

## Hiding the overlays for a while

To take a clean screenshot or look at the game without cards over it, hide every WNTB overlay at once and bring them back where they were:

- Click the **Overlays shown (click to hide)** line in the WNTB panel (under the credits and merits lines); it then reads **Overlays are hidden (click to show)**.
- On Windows, press the keyboard shortcut, which works while Elite has the focus. **Settings → WNTB → Overlays → Hide overlays** sets it (Ctrl+Alt+H by default; the other
  choices are Ctrl+Alt+O, Ctrl+Shift+H, Ctrl+Shift+O, Ctrl+Alt+F10 and Ctrl+Alt+F11, or Off) and has a **Hide / show now** button. If another program already holds the combination,
  Settings says so after you press OK; pick another.
- Hiding clears what is on screen at once, and showing puts back what had not run out, including the Colonization card, which is drawn once and left up.

Limits: it hides WNTB's overlays only, not another plugin's. It is not saved, so the overlays are shown whenever EDMC starts. The keyboard shortcut exists on Windows only,
because a Linux desktop gives a program no portable way to hear keys while another window has the focus (and Wayland gives none); on Linux use the panel line.
It does not hide overlays automatically, for example in the galaxy map.

## If you don't use an overlay

Nothing breaks. With EDMCModernOverlay chosen, WNTB tries to reach it when a feature wants to draw something, and if none is
running it gives up quietly for 30 seconds before trying again. You'll see one line in EDMC's log saying no
overlay was found, and the on-screen extras simply don't appear.

## If nothing shows up

**With the built-in overlay (Windows)**
1. Is **WNTB built-in overlay** chosen under Overlay Connection, and did you press OK? **Check connection** says whether it is running and whether it has found Elite.
2. Is Elite in **borderless or windowed** mode? A fullscreen game cannot be drawn over.
3. Are you in the game window? The overlay hides when another program is in front (tick **Keep showing...** if you want it to stay).
4. Did you hide the overlays (the line in the WNTB panel reads *Overlays are hidden*)? Click it to show them again.
5. Press a feature's test button; check the placement preview; reset a display to its default spot on Overlay Placement if only one is missing.
6. Check EDMC's log (Help menu) for a line from WNTB about the overlay; include it if you report a problem.

**With EDMCModernOverlay**
1. **Is the overlay running?** WNTB can't start it. Start it first.
2. **Does the port match?** Compare the one on WNTB's Overlay Connection tab with your overlay's.
3. **Is Elite in borderless or windowed mode?** Some overlays can't draw over exclusive fullscreen.
4. **Press the feature's test button.** The result says whether the overlay was reachable. A message like
   "could not reach the overlay" means steps 1 or 2.
5. **Did you restart after installing?** Restart EDMC (and the game, if needed) after installing or
   changing an overlay.
6. **Check the logs.** EDMC's Help menu can open its log folder, and EDMCModernOverlay keeps its own
   logs. Including them helps if you report a problem.
7. **Linux:** you need EDMCModernOverlay (the built-in overlay is Windows only; the original EDMCOverlay is Windows-only too). See the
   [Linux guide](guide/linux.md). If EDMC is a **Flatpak** and
   **Check connection** succeeds but nothing is drawn, the Flatpak needs permission to start the overlay
   window; the Linux guide gives the one-line `flatpak override` command.
8. **Does text look doubled or ghosted?** Two overlay windows may be running; see [Known issues](guide/known-issues.md).

**Either:** does only one display never show? Its saved position may be off the screen. Reset it on the Overlay Placement tab; see
[Troubleshooting](guide/troubleshooting.md#one-display-never-shows-though-test-and-the-overlay-window-both-work).

## A note for the curious

With EDMCModernOverlay, WNTB sends its drawings to the overlay over a local network connection on your own computer (the port
above). Nothing leaves your machine. WNTB keeps a single connection open for every feature, and registers
a "Plugin Group" with EDMCModernOverlay for each on-screen card so its background draws properly. With the built-in overlay nothing is sent anywhere: WNTB draws the
window itself, from Pillow (the imaging library EDMC ships), and reads Elite's window position and size. The
technical details are in [TECHNICAL.md](TECHNICAL.md) section 10 and the [built-in overlay specification](NATIVE_OVERLAY_SPEC.md).
