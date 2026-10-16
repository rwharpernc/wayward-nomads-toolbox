# Known issues

What is known to go wrong in the current release (**1.16.0**), what it looks like, and what to do about it. This page is for things that are bugs or rough edges; the
limits of what the game's journal tells WNTB are in the last section of each mode guide. If you hit something that is not here, see
[Reporting a problem](reporting-problems.md).

## Overlay text looks doubled or ghosted

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
WNTB cannot choose a font for its own cards only, and the overlay cannot draw italics, so species are not italicized.

## Overlays do not show over the game

The overlay window can only sit over Elite when the game runs **borderless or windowed**; a fullscreen game owns the screen and nothing can draw over it. See
[Setting up the overlay](../OVERLAY_SETUP.md) for the steps and [Troubleshooting](troubleshooting.md#overlay) for nothing showing up.

## New in 1.16.0 and tested on Windows only

The Exobiology cards, System targets, Body info, the Expedition Log, the layout editor on Overlay Placement, panel opacity, the overlay font choice, hiding the overlays and the duplicate window
warning have been tried on Windows only. The checks still to do on Linux are listed in [Linux testing](../LINUX_TESTING.md). Expect small fixes in a later update, and please report anything odd.

- **The keyboard shortcut to hide the overlays exists on Windows only.** On Linux use the **Overlays shown** line in the WNTB panel or the button in Settings.
- **The Bio status card is a wide strip now** (about half the screen wide). If you had placed it before, it keeps your old spot and may overlap something; move it in **Settings → WNTB → Overlays →
  Overlay Placement**.

## Estimates and limits worth knowing

These are not bugs, but they surprise people. Each is explained where it belongs:

- **Species percentages are an even share** of the candidates, because the data lists which species a body allows and not how likely each is, and a color variant is only known once you sample.
  See [Exobiology](exobiology.md#what-the-game-does-and-doesnt-tell-us-and-how-to-work-around-it).
- **Scan, mapping and unsold values are estimates**, worked out from a published formula; the game's own figure when you sell is the truth. System targets ranks by scan value, and the mapped
  value appears on Body info and in the Expedition Log. See [Exploration](exploration.md).
- **Plants, samples and the SRV have positions only while EDMC is running**, because the journal does not record them.
- **Linux is checked a little behind Windows.** See [Windows and Linux](platforms.md).

Where the cause is something the journal does not record, each mode guide ends with a section called "What the game does and doesn't tell us, and how to work around it".
