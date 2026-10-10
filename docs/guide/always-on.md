# Landing Assist and Interdiction Warning

These two tools are always available, whichever mode you're in. They don't belong to a mode. Interdiction Warning draws only on
your game screen, so it needs an overlay running. Landing Assist can show in the EDMC panel without one, but its
diagram on the game screen needs an overlay. See [Getting started](getting-started.md#what-you-need) and
[Setting up the overlay](../OVERLAY_SETUP.md).

## Landing Assist

Shows which landing pad you've been assigned while docking, in the EDMC panel and/or as a diagram on your game
screen (you choose which in Settings).

**To set it up:**

1. Open **Settings → Always On → Landing**.
2. Tick **Enable Landing**. It is **off by default**.
3. Choose where it shows: **Show in EDMC app** (the panel; on by default once Landing is enabled) and/or
   **Show on Overlay** (the diagram on your game screen; off by default).
4. Press **Test Overlay** to check the diagram shows.

If the overlay is still starting when docking is approved, WNTB keeps retrying for up to three minutes, so the
diagram appears as soon as the overlay is up.

## Interdiction Warning

Puts an alert on your game screen the moment an interdiction starts. It has no panel button, only Settings.

**To set it up:**

1. Open **Settings → Always On → Interdiction Warning**.
2. Tick **Enable Interdiction Warning**. It is **off by default**.
3. Press **Test Warning** to see what it looks like. The test works even while the feature is off, and reports
   whether an overlay could be reached.

## Overlay connection

Both use the connection settings on the **Overlay Connection** Settings tab (Settings → General). The defaults
(`127.0.0.1`, port `5010`) match EDMCModernOverlay and EDMCOverlay as they come. **Check connection** tells you
whether an overlay is listening.
