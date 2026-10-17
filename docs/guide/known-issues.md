# Known issues

What is known to go wrong in the current release (**1.17.4**), what it looks like, and what to do about it. This page is for things that are bugs or rough edges; the
limits of what the game's journal tells WNTB are in the last section of each mode guide. If you hit something that is not here, see
[Reporting a problem](reporting-problems.md).

## Overlay text looks doubled or ghosted

(This is EDMCModernOverlay's behavior. WNTB's own built-in overlay (new in 1.17.0) cannot leave a second window behind; but an EDMCModernOverlay window can still be running beside it.)

**What you see:** every overlay card has a faint second copy of its text beside or behind the real one, often in a different font or in capitals, and some rows look
brighter or dimmer than others. It does not clear when the card refreshes.

**Why:** two copies of EDMCModernOverlay's overlay window are running, and each draws everything it is sent. This happens when an old window is left running after EDMC is
closed or restarted without stopping it (a crash, a forced close, or restarts while testing an update), and it reconnects to the next EDMC session while a new window starts. While both
use the same font the copies sit exactly on top of each other and go unnoticed; if the font or the settings differ, the text looks doubled. It is EDMCModernOverlay's behavior, not
something WNTB starts, and WNTB cannot stop the extra window for you.

**What to do:**
1. Open **Settings → WNTB → Overlays → Overlay Connection** and press **Check connection**. When more than one overlay window is running it says so and names their process numbers.
   (**Copy diagnostics** in the Help tab gives the count too.)
2. Open Task Manager (Windows) or run `ps` (Linux) and look for `overlay_client` (a `python.exe -m overlay_client.overlay_client` for each window; a launcher and the window it starts
   share one start time and count as one).
3. End the older ones, or end them all and restart EDMC. The ghosting goes at once.

## Overlay text is all in capital letters

**What you see:** species, rows and headings all show in capitals, even though WNTB writes `Tussock pennatis`.

**Why:** the overlay draws every plugin's text in one font, and its default (Elite's cockpit font, `Eurocaps.ttf`) has capital letters only.

**What to do:** **Settings → WNTB → Overlays → Appearance → Overlay font**: pick a font with lower case letters (or **Add font file...** to use one you downloaded, for example from Google
Fonts), press OK and restart EDMC. The font is the overlay's, so it changes every plugin's text, and an update of EDMCModernOverlay can put the old list back.
WNTB cannot choose a font for its own cards only, and the overlay cannot draw italics, so species are not italicized. *Next release:* WNTB's built-in overlay (Windows) has a font of its own (Source Sans 3, lower case, and any `.ttf` or `.otf` you add) and does not have this problem; see [Fonts](../OVERLAY_SETUP.md#fonts).

## The built-in overlay is new (1.17.0)

WNTB's own overlay (Windows) is new and has had less time in the game than EDMCModernOverlay. It works with every card and with Overlay Placement, but expect small fixes: a card's box may fit its text a little differently than you are used to, and
the radar's circles and lines and cards at the screen edges are the least tested. It draws WNTB's displays only, so other plugins' overlays still need EDMCModernOverlay (you can run both). See [Setting up the overlay](../OVERLAY_SETUP.md).
It is off until you choose it under **Settings → Overlays → Overlay Connection**, and switching back is one setting.

## A tracked plant's marker can be off by a couple of hundred meters (1.17.0 draws how far)

A marker is where *you* were when the Composition Scanner named the plant, so from a ship or SRV it can be far from the plant. The radar draws the marker's ring as wide as it may be off, and the distance carries a `~`. See
[Exobiology](exobiology.md#finding-your-way-back-to-a-plant) for how it is judged and removed.

## Overlays do not show over the game

The overlay window can only sit over Elite when the game runs **borderless or windowed**; a fullscreen game owns the screen and nothing can draw over it. See
[Setting up the overlay](../OVERLAY_SETUP.md) for the steps and [Troubleshooting](troubleshooting.md#overlay) for nothing showing up.

## Tested on Windows only

The Exobiology cards, System targets, Body info, the Expedition Log, the layout editor on Overlay Placement, panel opacity, the overlay font choice, hiding the overlays and the duplicate window
warning (1.16.0), and the built-in overlay, nearest place to land, likely colors, marker rings and per-commander overlay settings (1.17.0) have been tried on Windows only. The checks still to do on Linux are listed in [Linux testing](../LINUX_TESTING.md). Expect small fixes in a later update, and please report anything odd.

- **The keyboard shortcut to hide the overlays exists on Windows only.** On Linux use the **Overlays shown** line in the WNTB panel or the button in Settings.
- **The Bio status card is a wide strip now** (about half the screen wide). If you had placed it before, it keeps your old spot and may overlap something; move it in **Settings → WNTB → Overlays →
  Overlay Placement**.

## Estimates and limits worth knowing

These are not bugs, but they surprise people. Each is explained where it belongs:

- **Species percentages are an even share** of the candidates, because the data lists which species a body allows and not how likely each is, and a color variant is only known once you sample.
  See [Exobiology](exobiology.md#what-the-game-does-and-doesnt-tell-us-and-how-to-work-around-it).
- **System targets' visit line and Known section have limits.** The visit line comes from your own journals and counts only those that still exist (and a relog in the same system is not a second visit); the first read takes about 40 seconds for thousands of journals. The Known section comes from Spansh, which knows only what other commanders uploaded, so a system nobody scanned shows nothing, and its figures are Spansh's estimates.
- **Scan, mapping and unsold values are estimates**, worked out from a published formula; the game's own figure when you sell is the truth. System targets ranks by the mapped value by default (the scan value if you choose it in Settings), and both
  appear on Body info and in the Expedition Log. See [Exploration](exploration.md).
- **Plants, samples and the SRV have positions only while EDMC is running**, because the journal does not record them.
- **Linux is checked a little behind Windows.** See [Windows and Linux](platforms.md).

Where the cause is something the journal does not record, each mode guide ends with a section called "What the game does and doesn't tell us, and how to work around it".
