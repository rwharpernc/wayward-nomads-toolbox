# Windows and Linux

WNTB runs on **Windows and Linux**, wherever EDMC does. Almost everything is the same on both, because it only
reads the game's journal. A handful of features touch the operating system, and those are the ones that differ.

Each of those features' Settings tab says which systems it works on and whether it can work on *yours* right now.
Look for the **Works on:** line.

## Side by side

| Feature | Windows | Linux (Elite under Steam Proton or Wine) |
|---|---|---|
| Everything driven by the journal: Powerplay, Exploration, Mining, Missions, BGS, Colonisation, Inventory tracking, Ship Builds, Boxel Survey, Codex, Landing Assist, Interdiction Warning, Discovery Alerts | Yes | Yes, once EDMC's **Journal directory** points at the game's journals inside the Proton/Wine folder |
| **Game mode and credits lines** under the mode buttons | Yes | Yes (same journal data; the Journal directory must be set) |
| **Trade**: session profit and costs, stock, carrier cargo, Trade History (including **Export log (CSV)**), and the Spansh route and price lookups | Yes | Yes. The Journal directory must be set: Trade reads the journals to catch a session up after EDMC was closed |
| **Auto-Honk** (presses your Discovery Scanner key for you) | Yes | Yes, needs **`xdotool`**. X11 or XWayland windows only, not a native Wayland window |
| **Screenshot auto-timer** and **Thargoid-scan capture** (press the screenshot key for you) | Yes | Yes, needs **`xdotool`** |
| Screenshot conversion and renaming | Yes | Yes (Elite's `Pictures` folder inside the Proton/Wine folder) |
| Pickup **sound** (Field Ops → Inventory) | Yes (system beep) | Yes, needs `canberra-gtk-play` or `paplay` |
| On-screen overlay features | EDMCModernOverlay **or** the older EDMCOverlay | EDMCModernOverlay only |
| Self-update | Yes | Yes |

## Windows only

- **The older EDMCOverlay** overlay program. EDMCModernOverlay replaces it and works on both. The Overlay
  Connection tab (Settings → General) says so.
- **OneDrive folder-redirect handling** for the Screenshot Directory, and the **Controlled Folder Access** hint
  when Windows blocks writing screenshots. Both are automatic and only appear on Windows.

## Linux only

- The **Elite Wine/Proton prefix** box in Settings → Exploration → Alerts. Leave it blank to auto-detect Steam.
- The hint about EDMC's **Journal directory**.

Full Linux setup is in [WNTB on Linux](linux.md).

## macOS

macOS is **not supported or tested**. Journal-driven features may work, but key simulation and sounds don't, and
nothing has been checked there.

## For the technical details

Exactly which files, folders and commands each system uses is in
[TECHNICAL.md section 18](../TECHNICAL.md#18-platform-support-windows-and-linux).
