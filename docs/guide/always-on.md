# Landing Assist and Interdiction Warning

These two tools are always available, whichever mode you're in. They don't belong to a mode. Both draw on your game
screen, so both need an overlay running. See [Getting started](getting-started.md#what-you-need) and
[Setting up the overlay](../OVERLAY_SETUP.md).

## Landing Assist

Shows which landing pad you've been assigned while docking, in the panel and as a diagram on your game screen.

**To set it up:**

1. Open **Settings → Always On → Landing**.
2. Turn it on and choose where it appears.
3. Press **Test Overlay** to check the diagram shows.

If the overlay is still starting when docking is approved, WNTB keeps retrying for up to three minutes, so the
diagram appears as soon as the overlay is up.

## Interdiction Warning

Puts an alert on your game screen the moment an interdiction starts. It has no panel button, only Settings.

**To set it up:**

1. Open **Settings → Interdiction Warning**.
2. Turn it on.
3. Press **Test Warning** to see what it looks like.

## Overlay connection

Both use the connection settings on the **Overlay Connection** Settings tab (Settings → General). The defaults
(`127.0.0.1`, port `5010`) match EDMCModernOverlay and EDMCOverlay as they come. **Check connection** tells you
whether an overlay is listening.
